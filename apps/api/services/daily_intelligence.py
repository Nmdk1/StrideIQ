"""
Daily Intelligence Engine (Phase 2C)

NOT a rules engine that swaps workouts. An intelligence engine that surfaces
information, learns from outcomes, and intervenes ONLY at extremes.
The athlete decides. The system learns.

Three operating modes:
    INFORM (default):  Surface data the athlete can't easily hold in their head.
    SUGGEST (earned):  Surface personal patterns from outcome data.
    FLAG (extreme):    Flag sustained negative trends. Still not an override.

Seven intelligence rules:
    1. LOAD_SPIKE           → INFORM: volume/intensity change detected
    2. SELF_REG_DELTA       → LOG + LEARN: planned ≠ actual
    3. EFFICIENCY_BREAK     → INFORM: efficiency breakthrough detected
    4. PACE_IMPROVEMENT     → INFORM: faster pace + lower HR
    5. SUSTAINED_DECLINE    → FLAG: 3+ weeks declining efficiency
    6. SUSTAINED_MISSED     → ASK: pattern of missed sessions
    7. READINESS_HIGH       → SUGGEST: consistently high readiness, not increasing

Sources:
    - _AI_CONTEXT_/KNOWLEDGE_BASE/TRAINING_PHILOSOPHY.md
    - docs/TRAINING_PLAN_REBUILD_PLAN.md (Phase 2C spec)
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID

import logging

logger = logging.getLogger(__name__)


class InsightMode(str, Enum):
    """Operating mode for an intelligence insight."""
    INFORM = "inform"       # Surface data — no action taken
    SUGGEST = "suggest"     # Surface personal patterns — earned through data
    FLAG = "flag"           # Sustained negative trend — prominent, still not override
    ASK = "ask"             # Ask the athlete for context
    LOG = "log"             # Silent logging — no user-facing output


@dataclass
class IntelligenceInsight:
    """A single intelligence insight from the daily engine."""
    rule_id: str                              # e.g., "LOAD_SPIKE"
    mode: InsightMode                         # Operating mode
    message: str                              # Human-readable insight
    data_cited: Dict[str, Any] = field(default_factory=dict)  # Evidence
    confidence: float = 0.0                   # 0-1 confidence in the insight
    workout_swap: bool = False                # MUST be False in INFORM/SUGGEST mode
    suggested_action: Optional[str] = None    # Only in SUGGEST/FLAG mode


@dataclass
class IntelligenceResult:
    """Result of running all intelligence rules for an athlete on a date."""
    athlete_id: UUID
    target_date: date
    insights: List[IntelligenceInsight] = field(default_factory=list)
    readiness_score: Optional[float] = None
    self_regulation_logged: bool = False       # Whether a planned≠actual delta was detected

    @property
    def highest_mode(self) -> Optional[InsightMode]:
        """Return the highest-severity mode across all insights."""
        if not self.insights:
            return None
        priority = {InsightMode.LOG: 0, InsightMode.INFORM: 1,
                    InsightMode.ASK: 2, InsightMode.SUGGEST: 3, InsightMode.FLAG: 4}
        return max(self.insights, key=lambda i: priority.get(i.mode, 0)).mode

    @property
    def has_workout_swap(self) -> bool:
        """Check if ANY insight attempted to swap a workout."""
        return any(i.workout_swap for i in self.insights)


# The 7 intelligence rules
INTELLIGENCE_RULES = [
    "LOAD_SPIKE",           # 1. Volume/intensity spike detected
    "SELF_REG_DELTA",       # 2. Planned ≠ actual (self-regulation)
    "EFFICIENCY_BREAK",     # 3. Efficiency breakthrough
    "PACE_IMPROVEMENT",     # 4. Faster pace + lower HR
    "SUSTAINED_DECLINE",    # 5. 3+ weeks declining efficiency
    "SUSTAINED_MISSED",     # 6. Pattern of missed sessions
    "READINESS_HIGH",       # 7. Consistently high readiness
]

# --- Thresholds (cold-start, will become per-athlete) ---
LOAD_SPIKE_THRESHOLD = 0.15          # 15% week-over-week volume increase
LOAD_SPIKE_MIN_VOLUME_KM = 10.0     # Ignore spikes below this base volume
EFFICIENCY_BREAK_THRESHOLD = 0.03   # 3% EF improvement = breakthrough
SUSTAINED_DECLINE_WEEKS = 3         # Minimum weeks of decline to FLAG
SUSTAINED_DECLINE_STEP_PCT = 0.015  # 1.5% per-step decline threshold
SUSTAINED_MISSED_MIN_SKIPS = 3      # Minimum skips to trigger ASK
SUSTAINED_MISSED_MIN_PLANNED = 6    # Minimum planned workouts for pattern detection
SUSTAINED_MISSED_RATE = 0.25        # 25% skip rate to trigger
READINESS_HIGH_THRESHOLD = 60.0     # Readiness score above this = "high"
READINESS_HIGH_MIN_DAYS = 10        # Minimum days of easy-only to suggest increase
PACE_IMPROVEMENT_SECONDS = 10       # Seconds/mile faster than target to trigger


class DailyIntelligenceEngine:
    """
    Run intelligence rules for an athlete on a given date.

    Default mode is INFORM — no workout swapping without explicit athlete opt-in.
    FLAG mode fires only on sustained (3+ week) negative trends.
    """

    def evaluate(
        self,
        athlete_id: UUID,
        target_date: date,
        db: Any,
        readiness_score: Optional[float] = None,
    ) -> IntelligenceResult:
        """
        Evaluate all intelligence rules for an athlete.

        Args:
            athlete_id: The athlete's UUID
            target_date: Date to evaluate
            db: Database session
            readiness_score: Pre-computed readiness (optional)

        Returns:
            IntelligenceResult with insights and metadata
        """
        result = IntelligenceResult(
            athlete_id=athlete_id,
            target_date=target_date,
            readiness_score=readiness_score,
        )

        # Run each rule, collecting insights
        # Rules are independent — each may or may not fire
        try:
            self._rule_load_spike(athlete_id, target_date, db, result)
        except Exception as e:
            logger.warning(f"Rule LOAD_SPIKE failed for {athlete_id}: {e}")

        try:
            self._rule_self_reg_delta(athlete_id, target_date, db, result)
        except Exception as e:
            logger.warning(f"Rule SELF_REG_DELTA failed for {athlete_id}: {e}")

        try:
            self._rule_efficiency_breakthrough(athlete_id, target_date, db, result)
        except Exception as e:
            logger.warning(f"Rule EFFICIENCY_BREAK failed for {athlete_id}: {e}")

        try:
            self._rule_pace_improvement(athlete_id, target_date, db, result)
        except Exception as e:
            logger.warning(f"Rule PACE_IMPROVEMENT failed for {athlete_id}: {e}")

        try:
            self._rule_sustained_decline(athlete_id, target_date, db, result)
        except Exception as e:
            logger.warning(f"Rule SUSTAINED_DECLINE failed for {athlete_id}: {e}")

        try:
            self._rule_sustained_missed(athlete_id, target_date, db, result)
        except Exception as e:
            logger.warning(f"Rule SUSTAINED_MISSED failed for {athlete_id}: {e}")

        try:
            self._rule_readiness_high(athlete_id, target_date, db, result, readiness_score)
        except Exception as e:
            logger.warning(f"Rule READINESS_HIGH failed for {athlete_id}: {e}")

        # Persist insights to InsightLog
        self._persist_insights(result, db)

        logger.info(
            f"Intelligence {athlete_id} on {target_date}: "
            f"{len(result.insights)} insights, "
            f"highest_mode={result.highest_mode}, "
            f"self_reg={result.self_regulation_logged}"
        )

        return result

    # ==================================================================
    # Rule 1: LOAD_SPIKE → INFORM
    # ==================================================================

    def _rule_load_spike(
        self, athlete_id: UUID, target_date: date, db: Any,
        result: IntelligenceResult,
    ) -> None:
        """
        Detect volume spike: 7-day rolling volume vs previous 7 days.

        Fires INFORM when recent volume is >15% above previous period.
        Does NOT fire when previous period has insufficient data.
        """
        from models import Activity

        current_start = target_date - timedelta(days=6)
        prev_start = target_date - timedelta(days=13)
        prev_end = target_date - timedelta(days=7)

        def _sum_distance_km(start: date, end: date) -> float:
            acts = (
                db.query(Activity)
                .filter(
                    Activity.athlete_id == athlete_id,
                    Activity.start_time >= datetime.combine(start, datetime.min.time()),
                    Activity.start_time < datetime.combine(end + timedelta(days=1), datetime.min.time()),
                )
                .all()
            )
            return sum(float(a.distance_m or 0) / 1000.0 for a in acts)

        current_km = _sum_distance_km(current_start, target_date)
        prev_km = _sum_distance_km(prev_start, prev_end)

        # Need sufficient data in both periods
        if prev_km < LOAD_SPIKE_MIN_VOLUME_KM:
            return

        ratio = current_km / prev_km if prev_km > 0 else 0
        pct_increase = (ratio - 1.0) * 100

        if ratio > (1.0 + LOAD_SPIKE_THRESHOLD):
            # Find biggest session this week
            current_acts = (
                db.query(Activity)
                .filter(
                    Activity.athlete_id == athlete_id,
                    Activity.start_time >= datetime.combine(current_start, datetime.min.time()),
                    Activity.start_time < datetime.combine(target_date + timedelta(days=1), datetime.min.time()),
                )
                .order_by(Activity.distance_m.desc())
                .all()
            )
            biggest = current_acts[0] if current_acts else None
            biggest_desc = ""
            if biggest and biggest.distance_m:
                biggest_mi = float(biggest.distance_m) / 1609.344
                biggest_name = biggest.name or biggest.workout_type or "session"
                biggest_desc = f" Your biggest session was {biggest_name} ({biggest_mi:.1f} mi)."

            result.insights.append(IntelligenceInsight(
                rule_id="LOAD_SPIKE",
                mode=InsightMode.INFORM,
                message=(
                    f"Volume up {pct_increase:.0f}% this week "
                    f"({current_km:.1f} km vs {prev_km:.1f} km).{biggest_desc}"
                ),
                data_cited={
                    "current_km": round(current_km, 1),
                    "previous_km": round(prev_km, 1),
                    "pct_increase": round(pct_increase, 1),
                },
                confidence=min(1.0, pct_increase / 50.0),
                workout_swap=False,  # NEVER swap in INFORM mode
            ))

    # ==================================================================
    # Rule 2: SELF_REG_DELTA → LOG
    # ==================================================================

    def _rule_self_reg_delta(
        self, athlete_id: UUID, target_date: date, db: Any,
        result: IntelligenceResult,
    ) -> None:
        """
        Detect planned ≠ actual and log the delta.

        Uses the SelfRegulationDetector from Phase 2B.
        Fires LOG for every detected delta — no judgment, just recording.
        """
        from services.self_regulation import SelfRegulationDetector

        detector = SelfRegulationDetector(db)
        deltas = detector.detect_for_date(
            athlete_id, target_date,
            readiness_score=result.readiness_score,
        )

        if deltas:
            # Log each delta
            detector.log_deltas(deltas, readiness_score=result.readiness_score)
            result.self_regulation_logged = True

            for delta in deltas:
                direction = delta.delta_direction
                planned = delta.planned_type or "none"
                actual = delta.actual_type or "none"

                if delta.delta_type == "skipped":
                    msg = f"Planned {planned} was skipped."
                elif delta.delta_type == "unplanned":
                    msg = f"Unplanned {actual} session detected."
                elif delta.delta_type == "distance_change":
                    planned_km = delta.planned_distance_km or 0
                    actual_km = delta.actual_distance_km or 0
                    msg = (
                        f"Distance change: planned {planned_km:.1f} km, "
                        f"actual {actual_km:.1f} km ({direction})."
                    )
                else:
                    msg = (
                        f"Workout type change: planned {planned}, "
                        f"actual {actual} ({direction})."
                    )

                result.insights.append(IntelligenceInsight(
                    rule_id="SELF_REG_DELTA",
                    mode=InsightMode.LOG,
                    message=msg,
                    data_cited={
                        "planned_type": planned,
                        "actual_type": actual,
                        "delta_type": delta.delta_type,
                        "direction": direction,
                        "distance_delta_km": delta.distance_delta_km,
                    },
                    confidence=0.9,
                    workout_swap=False,
                ))

    # ==================================================================
    # Rule 3: EFFICIENCY_BREAK → INFORM
    # ==================================================================

    def _rule_efficiency_breakthrough(
        self, athlete_id: UUID, target_date: date, db: Any,
        result: IntelligenceResult,
    ) -> None:
        """
        Detect efficiency breakthrough: newer EF significantly better than older EF.

        Computes EF (speed/HR) for activities in the last 14 days, splits into
        older and newer halves, and fires INFORM if improvement >= 3%.
        """
        efs_with_dates = self._get_ef_series(athlete_id, target_date, db, days=14)

        if len(efs_with_dates) < 4:
            return

        efs = [ef for _, ef in efs_with_dates]
        mid = len(efs) // 2
        older_avg = sum(efs[:mid]) / mid
        newer_avg = sum(efs[mid:]) / (len(efs) - mid)

        if older_avg <= 0:
            return

        pct_change = (newer_avg - older_avg) / older_avg

        if pct_change >= EFFICIENCY_BREAK_THRESHOLD:
            result.insights.append(IntelligenceInsight(
                rule_id="EFFICIENCY_BREAK",
                mode=InsightMode.INFORM,
                message=(
                    f"Efficiency improved {pct_change * 100:.1f}% over the last 2 weeks. "
                    f"Your body is adapting — real fitness gain."
                ),
                data_cited={
                    "older_ef_avg": round(older_avg, 5),
                    "newer_ef_avg": round(newer_avg, 5),
                    "improvement_pct": round(pct_change * 100, 1),
                    "sample_size": len(efs),
                },
                confidence=min(1.0, len(efs) / 10.0),
                workout_swap=False,
            ))

    # ==================================================================
    # Rule 4: PACE_IMPROVEMENT → INFORM
    # ==================================================================

    def _rule_pace_improvement(
        self, athlete_id: UUID, target_date: date, db: Any,
        result: IntelligenceResult,
    ) -> None:
        """
        Detect when athlete ran faster than target pace.

        Compares completed planned workouts with target pace to actual activity pace.
        Fires INFORM when actual is >=10s/mi faster than target.
        """
        from models import PlannedWorkout, Activity

        # Get completed planned workouts for today with target metrics
        planned_today = (
            db.query(PlannedWorkout)
            .filter(
                PlannedWorkout.athlete_id == athlete_id,
                PlannedWorkout.scheduled_date == target_date,
            )
            .all()
        )

        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
        activities_today = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.start_time >= day_start,
                Activity.start_time < day_end,
                Activity.distance_m.isnot(None),
                Activity.distance_m > 0,
                Activity.duration_s.isnot(None),
                Activity.duration_s > 0,
            )
            .all()
        )

        for pw in planned_today:
            # Need target pace (from duration + distance)
            if not pw.target_duration_minutes or not pw.target_distance_km:
                continue

            target_pace_min_per_mi = (
                pw.target_duration_minutes / (pw.target_distance_km / 1.60934)
            )

            # Find matching activity
            for act in activities_today:
                actual_distance_mi = float(act.distance_m) / 1609.344
                actual_duration_min = float(act.duration_s) / 60.0

                if actual_distance_mi < 1.0:
                    continue

                actual_pace_min_per_mi = actual_duration_min / actual_distance_mi
                pace_diff_seconds = (target_pace_min_per_mi - actual_pace_min_per_mi) * 60

                if pace_diff_seconds >= PACE_IMPROVEMENT_SECONDS:
                    result.insights.append(IntelligenceInsight(
                        rule_id="PACE_IMPROVEMENT",
                        mode=InsightMode.INFORM,
                        message=(
                            f"You ran {pace_diff_seconds:.0f}s/mi faster than target pace "
                            f"({actual_pace_min_per_mi:.1f} vs {target_pace_min_per_mi:.1f} min/mi). "
                            f"Pace zones may need updating."
                        ),
                        data_cited={
                            "target_pace_min_mi": round(target_pace_min_per_mi, 2),
                            "actual_pace_min_mi": round(actual_pace_min_per_mi, 2),
                            "diff_seconds": round(pace_diff_seconds, 0),
                            "actual_hr": act.avg_hr,
                        },
                        confidence=0.8,
                        workout_swap=False,
                        suggested_action="Update training paces",
                    ))
                    return  # One insight per day is enough

    # ==================================================================
    # Rule 5: SUSTAINED_DECLINE → FLAG
    # ==================================================================

    def _rule_sustained_decline(
        self, athlete_id: UUID, target_date: date, db: Any,
        result: IntelligenceResult,
    ) -> None:
        """
        Detect sustained efficiency decline: 3+ consecutive weeks with
        declining EF (each step >= 1.5% decline).

        Does NOT fire for:
        - Less than 3 weeks of data
        - Single-week dips (normal post-load-spike)
        - Taper periods (detected via planned workout phase)
        """
        from models import PlannedWorkout

        # Check if athlete is in taper phase — decline is expected
        recent_planned = (
            db.query(PlannedWorkout)
            .filter(
                PlannedWorkout.athlete_id == athlete_id,
                PlannedWorkout.scheduled_date >= target_date - timedelta(days=14),
                PlannedWorkout.scheduled_date <= target_date,
            )
            .all()
        )
        if any(pw.phase == "taper" for pw in recent_planned):
            return  # Don't flag during taper

        # Compute weekly EF averages for the last 4 weeks
        weekly_efs = []
        for week_idx in range(4):
            week_end = target_date - timedelta(days=week_idx * 7)
            week_start = week_end - timedelta(days=6)
            efs = self._get_ef_series(athlete_id, week_end, db, days=7)
            if efs:
                avg_ef = sum(ef for _, ef in efs) / len(efs)
                weekly_efs.append((week_idx, avg_ef))

        if len(weekly_efs) < 3:
            return  # Not enough data for sustained trend

        # Sort by week_idx (0 = most recent, 3 = oldest)
        weekly_efs.sort(key=lambda x: x[0])

        # Count consecutive declining weeks (from most recent backward)
        # week_idx 0 vs 1, 1 vs 2, 2 vs 3
        consecutive_declines = 0
        for i in range(len(weekly_efs) - 1):
            newer_ef = weekly_efs[i][1]
            older_ef = weekly_efs[i + 1][1]

            if older_ef <= 0:
                break

            decline_pct = (older_ef - newer_ef) / older_ef
            if decline_pct >= SUSTAINED_DECLINE_STEP_PCT:
                consecutive_declines += 1
            else:
                break  # Chain broken

        if consecutive_declines >= SUSTAINED_DECLINE_WEEKS:
            # Compute overall decline
            newest_ef = weekly_efs[0][1]
            oldest_ef = weekly_efs[min(consecutive_declines, len(weekly_efs) - 1)][1]
            total_decline = ((oldest_ef - newest_ef) / oldest_ef) * 100 if oldest_ef > 0 else 0

            result.insights.append(IntelligenceInsight(
                rule_id="SUSTAINED_DECLINE",
                mode=InsightMode.FLAG,
                message=(
                    f"Efficiency has been declining for {consecutive_declines + 1} weeks "
                    f"({total_decline:.1f}% total). This is longer than typical "
                    f"post-load dips. Worth reviewing your recovery."
                ),
                data_cited={
                    "weeks_declining": consecutive_declines + 1,
                    "total_decline_pct": round(total_decline, 1),
                    "weekly_efs": [
                        {"week_ago": w, "avg_ef": round(ef, 5)}
                        for w, ef in weekly_efs
                    ],
                },
                confidence=min(1.0, consecutive_declines / 4.0),
                workout_swap=False,
                suggested_action="Review recovery and training load",
            ))

    # ==================================================================
    # Rule 6: SUSTAINED_MISSED → ASK
    # ==================================================================

    def _rule_sustained_missed(
        self, athlete_id: UUID, target_date: date, db: Any,
        result: IntelligenceResult,
    ) -> None:
        """
        Detect pattern of missed sessions over the last 14 days.

        Fires ASK when >= 3 skips AND skip rate >= 25% AND enough planned data.
        Single skips are normal (life happens). Patterns need context.
        """
        from models import PlannedWorkout

        lookback = target_date - timedelta(days=14)
        planned = (
            db.query(PlannedWorkout)
            .filter(
                PlannedWorkout.athlete_id == athlete_id,
                PlannedWorkout.scheduled_date >= lookback,
                PlannedWorkout.scheduled_date <= target_date,
            )
            .all()
        )

        if len(planned) < SUSTAINED_MISSED_MIN_PLANNED:
            return

        skipped = sum(1 for pw in planned if pw.skipped)
        skip_rate = skipped / len(planned)

        if skipped >= SUSTAINED_MISSED_MIN_SKIPS and skip_rate >= SUSTAINED_MISSED_RATE:
            result.insights.append(IntelligenceInsight(
                rule_id="SUSTAINED_MISSED",
                mode=InsightMode.ASK,
                message=(
                    f"I noticed {skipped} missed sessions in the last 2 weeks "
                    f"({skip_rate * 100:.0f}% of planned). Injury, life, or strategic? "
                    f"This helps me learn your patterns."
                ),
                data_cited={
                    "skipped_count": skipped,
                    "total_planned": len(planned),
                    "skip_rate": round(skip_rate, 2),
                    "period_days": 14,
                },
                confidence=min(1.0, skipped / 6.0),
                workout_swap=False,
            ))

    # ==================================================================
    # Rule 7: READINESS_HIGH → SUGGEST
    # ==================================================================

    def _rule_readiness_high(
        self, athlete_id: UUID, target_date: date, db: Any,
        result: IntelligenceResult,
        readiness_score: Optional[float] = None,
    ) -> None:
        """
        Detect consistently high readiness with no increase in training intensity.

        Fires SUGGEST when readiness is high AND the athlete has only done
        easy work for an extended period. The athlete may be ready for more.
        """
        from models import Activity, PlannedWorkout
        from services.self_regulation import QUALITY_TYPES

        if readiness_score is None or readiness_score < READINESS_HIGH_THRESHOLD:
            return

        # Check recent activities: are they all easy/low intensity?
        lookback = target_date - timedelta(days=14)
        recent_acts = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.start_time >= datetime.combine(lookback, datetime.min.time()),
                Activity.start_time < datetime.combine(target_date + timedelta(days=1), datetime.min.time()),
            )
            .all()
        )

        if len(recent_acts) < READINESS_HIGH_MIN_DAYS:
            return

        # Check for quality work in recent activities
        has_quality = any(
            a.workout_type in QUALITY_TYPES
            for a in recent_acts
            if a.workout_type
        )

        if has_quality:
            return  # Athlete is already doing quality work

        # Check planned workouts: are they all easy?
        recent_planned = (
            db.query(PlannedWorkout)
            .filter(
                PlannedWorkout.athlete_id == athlete_id,
                PlannedWorkout.scheduled_date >= lookback,
                PlannedWorkout.scheduled_date <= target_date,
            )
            .all()
        )

        if recent_planned:
            has_quality_planned = any(
                pw.workout_type in QUALITY_TYPES
                for pw in recent_planned
            )
            if has_quality_planned:
                return  # Quality work is in the plan

        result.insights.append(IntelligenceInsight(
            rule_id="READINESS_HIGH",
            mode=InsightMode.SUGGEST,
            message=(
                f"Your readiness has been high ({readiness_score:.0f}) and "
                f"you've been running easy for {len(recent_acts)} sessions over 2 weeks. "
                f"Your body may be ready for more."
            ),
            data_cited={
                "readiness_score": readiness_score,
                "easy_sessions_count": len(recent_acts),
                "days_all_easy": 14,
            },
            confidence=0.7,
            workout_swap=False,
            suggested_action="Consider adding a quality session",
        ))

    # ==================================================================
    # Shared helpers
    # ==================================================================

    def _get_ef_series(
        self, athlete_id: UUID, target_date: date, db: Any, days: int = 14,
    ) -> List[tuple]:
        """
        Get efficiency factor (speed/HR) time series for recent activities.

        Returns list of (date, ef) tuples sorted by date.
        """
        from models import Activity

        window_start = target_date - timedelta(days=days - 1)
        activities = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.start_time >= datetime.combine(window_start, datetime.min.time()),
                Activity.start_time < datetime.combine(target_date + timedelta(days=1), datetime.min.time()),
                Activity.avg_hr.isnot(None),
                Activity.avg_hr > 0,
                Activity.average_speed.isnot(None),
                Activity.average_speed > 0,
            )
            .order_by(Activity.start_time)
            .all()
        )

        result = []
        for a in activities:
            hr = float(a.avg_hr)
            speed = float(a.average_speed)
            if hr > 0 and speed > 0:
                ef = speed / hr
                act_date = a.start_time.date() if hasattr(a.start_time, 'date') else a.start_time
                result.append((act_date, ef))

        return result

    def _persist_insights(self, result: IntelligenceResult, db: Any) -> None:
        """Persist all insights to InsightLog for audit trail."""
        try:
            from models import InsightLog

            for insight in result.insights:
                log_entry = InsightLog(
                    athlete_id=result.athlete_id,
                    rule_id=insight.rule_id,
                    mode=insight.mode.value,
                    message=insight.message,
                    data_cited=insight.data_cited,
                    trigger_date=result.target_date,
                    readiness_score=result.readiness_score,
                    confidence=insight.confidence,
                )
                db.add(log_entry)
        except Exception as e:
            # Don't let persistence failure break the engine
            logger.warning(f"Failed to persist insights for {result.athlete_id}: {e}")
