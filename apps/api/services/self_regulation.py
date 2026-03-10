"""
Self-Regulation Detection Service (Phase 2B)

Detects when planned ≠ actual and classifies the delta.

When a Strava sync brings in an activity that matches a planned workout date
but differs from the plan (different type, different pace, different distance),
this service detects the delta, classifies it, and logs it as first-class data.

Self-regulation is NOT a problem to fix — it's intelligence to learn from.
A runner who planned easy but ran quality might be making a smart call based
on how they feel. A runner who planned quality but ran easy might be wisely
avoiding overload. The system logs both, tracks outcomes, and learns patterns.

Design:
    1. Match activity → planned workout (by athlete_id + date)
    2. Detect delta (type change, distance change, intensity change)
    3. Classify direction (upgraded, downgraded, shortened, extended)
    4. Log in SelfRegulationLog
    5. Update PlannedWorkout fields (actual_workout_type, planned_vs_actual_delta)
    6. Outcome tracking populated asynchronously (next-day efficiency, check-in)
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID

import logging

logger = logging.getLogger(__name__)


# Workout type categories for delta classification
QUALITY_TYPES = {
    "threshold", "tempo", "tempo_run", "intervals", "interval",
    "long_run", "long_hmp", "long_mp", "race",
}
EASY_TYPES = {"easy", "easy_run", "recovery", "recovery_run"}
REST_TYPES = {"rest", "off"}


@dataclass
class SelfRegulationDelta:
    """A detected delta between planned and actual workout."""
    workout_id: UUID
    activity_id: Optional[UUID]
    athlete_id: UUID
    trigger_date: date

    # What was planned
    planned_type: str
    planned_distance_km: Optional[float]

    # What actually happened
    actual_type: Optional[str]
    actual_distance_km: Optional[float]

    # Classification
    delta_type: str          # "type_change", "distance_change", "unplanned", "skipped"
    delta_direction: str     # "upgraded", "downgraded", "shortened", "extended", "skipped"

    # Magnitude
    distance_delta_km: Optional[float] = None
    type_changed: bool = False

    def to_planned_vs_actual_dict(self) -> Dict[str, Any]:
        """Convert to the JSONB format stored on PlannedWorkout."""
        return {
            "planned_type": self.planned_type,
            "actual_type": self.actual_type,
            "planned_distance_km": self.planned_distance_km,
            "actual_distance_km": self.actual_distance_km,
            "distance_delta_km": self.distance_delta_km,
            "type_changed": self.type_changed,
            "delta_type": self.delta_type,
            "delta_direction": self.delta_direction,
        }


class SelfRegulationDetector:
    """
    Detect and log self-regulation deltas between planned and actual workouts.

    Called when:
    - A Strava sync brings in a new activity
    - A planned workout is marked as completed or skipped
    - Nightly intelligence task reviews the day's data
    """

    def __init__(self, db):
        self.db = db

    def detect_for_date(
        self,
        athlete_id: UUID,
        target_date: date,
        readiness_score: Optional[float] = None,
    ) -> List[SelfRegulationDelta]:
        """
        Detect all self-regulation deltas for an athlete on a given date.

        Matches activities to planned workouts and classifies any differences.

        Returns:
            List of detected deltas (may be empty if no deviation)
        """
        from models import PlannedWorkout, Activity

        # Get planned workouts for this date
        planned = (
            self.db.query(PlannedWorkout)
            .filter(
                PlannedWorkout.athlete_id == athlete_id,
                PlannedWorkout.scheduled_date == target_date,
            )
            .all()
        )

        # Get actual activities for this date
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
        activities = (
            self.db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.start_time >= day_start,
                Activity.start_time < day_end,
            )
            .order_by(Activity.start_time)
            .all()
        )

        deltas = []

        # Case 1: Planned workouts that may have been modified or skipped
        for pw in planned:
            delta = self._match_and_classify(pw, activities, readiness_score)
            if delta:
                deltas.append(delta)

        # Case 2: Unplanned activities (no corresponding planned workout)
        planned_dates = {pw.scheduled_date for pw in planned}
        for act in activities:
            act_date = act.start_time.date() if hasattr(act.start_time, 'date') else act.start_time
            matched = any(
                pw.completed_activity_id == act.id
                for pw in planned
            )
            if not matched and not planned:
                # Truly unplanned session
                delta = self._classify_unplanned(act, athlete_id, target_date, readiness_score)
                if delta:
                    deltas.append(delta)

        return deltas

    def _match_and_classify(
        self,
        planned: Any,
        activities: List[Any],
        readiness_score: Optional[float],
    ) -> Optional[SelfRegulationDelta]:
        """Match a planned workout to an activity and classify the delta."""

        # Find the matching activity (by completed_activity_id or best match)
        matched_activity = None

        if planned.completed_activity_id:
            matched_activity = next(
                (a for a in activities if a.id == planned.completed_activity_id),
                None,
            )

        if not matched_activity and activities:
            # Best guess: first activity of the day that isn't already matched
            matched_activity = activities[0] if len(activities) == 1 else None

        # Case: Skipped workout
        if planned.skipped and not matched_activity:
            return SelfRegulationDelta(
                workout_id=planned.id,
                activity_id=None,
                athlete_id=planned.athlete_id,
                trigger_date=planned.scheduled_date,
                planned_type=planned.workout_type,
                planned_distance_km=planned.target_distance_km,
                actual_type=None,
                actual_distance_km=None,
                delta_type="skipped",
                delta_direction="skipped",
            )

        if not matched_activity:
            return None

        # Extract actual metrics
        actual_type = matched_activity.workout_type
        actual_distance_km = (
            float(matched_activity.distance_m) / 1000.0
            if matched_activity.distance_m else None
        )
        planned_distance_km = planned.target_distance_km

        # Detect type change
        type_changed = False
        if actual_type and planned.workout_type:
            planned_is_quality = planned.workout_type in QUALITY_TYPES
            actual_is_quality = actual_type in QUALITY_TYPES
            planned_is_easy = planned.workout_type in EASY_TYPES
            actual_is_easy = actual_type in EASY_TYPES
            type_changed = (planned_is_quality != actual_is_quality) or (
                planned_is_easy and not actual_is_easy and not actual_type in REST_TYPES
            ) or (
                not planned_is_easy and actual_is_easy
            )

        # Detect distance change
        distance_delta_km = None
        if planned_distance_km and actual_distance_km:
            distance_delta_km = actual_distance_km - planned_distance_km

        # Skip if no meaningful delta
        significant_distance_change = (
            distance_delta_km is not None
            and abs(distance_delta_km) > 1.5  # > 1.5 km (~1 mile) is meaningful
        )
        if not type_changed and not significant_distance_change:
            return None

        # Classify direction
        delta_direction = self._classify_direction(
            planned.workout_type, actual_type, distance_delta_km
        )

        # Determine delta type
        if type_changed:
            delta_type = "type_change"
        elif significant_distance_change:
            delta_type = "distance_change"
        else:
            delta_type = "type_change"  # Fallback

        return SelfRegulationDelta(
            workout_id=planned.id,
            activity_id=matched_activity.id,
            athlete_id=planned.athlete_id,
            trigger_date=planned.scheduled_date,
            planned_type=planned.workout_type,
            planned_distance_km=planned_distance_km,
            actual_type=actual_type,
            actual_distance_km=actual_distance_km,
            delta_type=delta_type,
            delta_direction=delta_direction,
            distance_delta_km=distance_delta_km,
            type_changed=type_changed,
        )

    def _classify_direction(
        self,
        planned_type: str,
        actual_type: Optional[str],
        distance_delta_km: Optional[float],
    ) -> str:
        """Classify the direction of the self-regulation delta."""
        if actual_type is None:
            return "skipped"

        planned_is_easy = planned_type in EASY_TYPES
        actual_is_quality = actual_type in QUALITY_TYPES
        actual_is_easy = actual_type in EASY_TYPES
        planned_is_quality = planned_type in QUALITY_TYPES

        # Type-based classification
        if planned_is_easy and actual_is_quality:
            return "upgraded"
        if planned_is_quality and actual_is_easy:
            return "downgraded"

        # Distance-based classification
        if distance_delta_km is not None:
            if distance_delta_km < -1.5:
                return "shortened"
            if distance_delta_km > 1.5:
                return "extended"

        return "modified"

    def _classify_unplanned(
        self,
        activity: Any,
        athlete_id: UUID,
        target_date: date,
        readiness_score: Optional[float],
    ) -> Optional[SelfRegulationDelta]:
        """Classify an activity that has no corresponding planned workout."""
        actual_type = activity.workout_type
        actual_distance_km = (
            float(activity.distance_m) / 1000.0
            if activity.distance_m else None
        )

        return SelfRegulationDelta(
            workout_id=None,  # No planned workout
            activity_id=activity.id,
            athlete_id=athlete_id,
            trigger_date=target_date,
            planned_type=None,
            planned_distance_km=None,
            actual_type=actual_type,
            actual_distance_km=actual_distance_km,
            delta_type="unplanned",
            delta_direction="unplanned",
        )

    def log_deltas(
        self,
        deltas: List[SelfRegulationDelta],
        readiness_score: Optional[float] = None,
    ) -> List[UUID]:
        """
        Persist detected deltas to the database.

        Updates PlannedWorkout fields and creates SelfRegulationLog entries.

        Returns:
            List of SelfRegulationLog IDs created
        """
        from models import PlannedWorkout, SelfRegulationLog

        log_ids = []

        for delta in deltas:
            # Update PlannedWorkout if we have a workout_id
            if delta.workout_id:
                pw = self.db.query(PlannedWorkout).filter(
                    PlannedWorkout.id == delta.workout_id
                ).first()
                if pw:
                    pw.actual_workout_type = delta.actual_type
                    pw.planned_vs_actual_delta = delta.to_planned_vs_actual_dict()
                    pw.readiness_at_execution = readiness_score

                    # Set execution state
                    if delta.delta_type == "skipped":
                        pw.execution_state = "SKIPPED"
                    elif delta.type_changed:
                        pw.execution_state = "MODIFIED_BY_ATHLETE"
                    elif pw.completed:
                        pw.execution_state = "COMPLETED"
                    else:
                        pw.execution_state = "SCHEDULED"

            # Create SelfRegulationLog entry
            log_entry = SelfRegulationLog(
                athlete_id=delta.athlete_id,
                workout_id=delta.workout_id,
                activity_id=delta.activity_id,
                planned_type=delta.planned_type,
                planned_distance_km=delta.planned_distance_km,
                planned_intensity=None,  # TODO: derive from segments/pace targets
                actual_type=delta.actual_type,
                actual_distance_km=delta.actual_distance_km,
                actual_intensity=None,  # TODO: derive from activity HR zones
                delta_type=delta.delta_type,
                delta_direction=delta.delta_direction,
                readiness_at_decision=readiness_score,
                trigger_date=delta.trigger_date,
            )
            self.db.add(log_entry)
            self.db.flush()
            log_ids.append(log_entry.id)

            logger.info(
                f"Self-regulation logged: {delta.athlete_id} on {delta.trigger_date} "
                f"— {delta.delta_type} ({delta.delta_direction}): "
                f"planned={delta.planned_type}, actual={delta.actual_type}"
            )

        return log_ids

    def detect_and_log(
        self,
        athlete_id: UUID,
        target_date: date,
        readiness_score: Optional[float] = None,
    ) -> List[SelfRegulationDelta]:
        """
        Convenience method: detect deltas and log them in one call.

        Returns the detected deltas.
        """
        deltas = self.detect_for_date(athlete_id, target_date, readiness_score)
        if deltas:
            self.log_deltas(deltas, readiness_score)
        return deltas

    @staticmethod
    def update_outcome(
        log_id: UUID,
        db: Any,
        efficiency_delta: Optional[float] = None,
        subjective_feel: Optional[int] = None,
        classification: Optional[str] = None,
    ) -> None:
        """
        Update outcome fields on a SelfRegulationLog entry.

        Called asynchronously (next day) when outcome data becomes available.
        """
        from models import SelfRegulationLog

        entry = db.query(SelfRegulationLog).filter(
            SelfRegulationLog.id == log_id
        ).first()
        if entry:
            if efficiency_delta is not None:
                entry.outcome_efficiency_delta = efficiency_delta
            if subjective_feel is not None:
                entry.outcome_subjective = subjective_feel
            if classification is not None:
                entry.outcome_classification = classification


def compute_execution_state(planned_workout) -> str:
    """
    Compute the execution state for a PlannedWorkout based on its current fields.

    State transitions:
        SCHEDULED → COMPLETED     (completed=True, no type change)
        SCHEDULED → SKIPPED       (skipped=True)
        SCHEDULED → MODIFIED_BY_ATHLETE (completed=True, actual differs from planned)

    Returns one of: "SCHEDULED", "COMPLETED", "SKIPPED", "MODIFIED_BY_ATHLETE"
    """
    if planned_workout.skipped:
        return "SKIPPED"

    if planned_workout.completed:
        if (
            planned_workout.actual_workout_type
            and planned_workout.actual_workout_type != planned_workout.workout_type
        ):
            return "MODIFIED_BY_ATHLETE"
        return "COMPLETED"

    return "SCHEDULED"
