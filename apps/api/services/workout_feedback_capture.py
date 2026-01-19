"""
Workout Feedback Capture Service

Captures athlete feedback and updates the N=1 learning models.
This is the critical bridge between ActivityFeedback and AthleteWorkoutResponse.

ADR-036: N=1 Learning Workout Selection Engine

When an athlete submits feedback (RPE, leg feel, etc.) for a quality workout:
1. Identify the workout's stimulus type
2. Calculate RPE gap (actual - expected)
3. Update AthleteWorkoutResponse aggregates
4. Potentially bank new learnings if patterns emerge

This enables the WorkoutSelector to learn from athlete responses over time.
"""

import logging
from typing import Optional, Dict, Tuple
from uuid import UUID
from datetime import datetime, timezone
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


@dataclass
class FeedbackCaptureResult:
    """Result of processing activity feedback for N=1 learning."""
    processed: bool
    stimulus_type: Optional[str]
    rpe_gap: Optional[float]
    new_learning_banked: bool
    learning_type: Optional[str]
    notes: str


# Expected RPE ranges by workout type (population defaults)
# These are initial values - the system learns athlete-specific ranges over time
EXPECTED_RPE_BY_WORKOUT_TYPE = {
    "easy": {"min": 2, "max": 4, "midpoint": 3},
    "recovery": {"min": 1, "max": 3, "midpoint": 2},
    "long_run": {"min": 3, "max": 5, "midpoint": 4},
    "threshold": {"min": 6, "max": 8, "midpoint": 7},
    "tempo": {"min": 6, "max": 7, "midpoint": 6.5},
    "race_pace": {"min": 5, "max": 7, "midpoint": 6},
    "intervals": {"min": 7, "max": 9, "midpoint": 8},
    "strides": {"min": 3, "max": 5, "midpoint": 4},
    "hill_sprints": {"min": 7, "max": 9, "midpoint": 8},
    "sharpening": {"min": 7, "max": 8, "midpoint": 7.5},
    "fartlek": {"min": 6, "max": 8, "midpoint": 7},
    "race": {"min": 9, "max": 10, "midpoint": 9.5},
}

# Stimulus type mapping from workout type
WORKOUT_TYPE_TO_STIMULUS = {
    "threshold": "intervals",
    "tempo": "continuous",
    "intervals": "intervals",
    "strides": "strides",
    "hill_sprints": "hills",
    "sharpening": "intervals",
    "fartlek": "fartlek",
    "race_pace": "race_pace",
    "long_run": "long_run",
    "easy": "easy",
    "recovery": "easy",
    "race": "race",
}


def process_activity_feedback(
    activity_id: UUID,
    athlete_id: UUID,
    perceived_effort: int,
    db: Session,
    leg_feel: Optional[str] = None,
    completion_fraction: float = 1.0
) -> FeedbackCaptureResult:
    """
    Process activity feedback and update N=1 learning models.
    
    This should be called whenever an athlete submits feedback for an activity.
    
    Args:
        activity_id: The activity receiving feedback
        athlete_id: The athlete providing feedback
        perceived_effort: RPE on 1-10 scale
        db: Database session
        leg_feel: Optional leg feel (fresh, normal, tired, heavy, sore)
        completion_fraction: Fraction of workout completed (0-1)
        
    Returns:
        FeedbackCaptureResult with processing details
    """
    from models import Activity, AthleteWorkoutResponse, AthleteLearning
    
    # Get the activity
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        return FeedbackCaptureResult(
            processed=False,
            stimulus_type=None,
            rpe_gap=None,
            new_learning_banked=False,
            learning_type=None,
            notes="Activity not found"
        )
    
    # Determine workout type and stimulus
    workout_type = activity.workout_type or _infer_workout_type(activity)
    if not workout_type:
        return FeedbackCaptureResult(
            processed=False,
            stimulus_type=None,
            rpe_gap=None,
            new_learning_banked=False,
            learning_type=None,
            notes="Could not determine workout type"
        )
    
    stimulus_type = WORKOUT_TYPE_TO_STIMULUS.get(workout_type.lower(), "other")
    
    # Get expected RPE
    expected_rpe = EXPECTED_RPE_BY_WORKOUT_TYPE.get(
        workout_type.lower(), 
        {"midpoint": 5}
    )["midpoint"]
    
    # Calculate RPE gap (positive = felt harder than expected)
    rpe_gap = perceived_effort - expected_rpe
    
    # Update AthleteWorkoutResponse
    response = db.query(AthleteWorkoutResponse).filter(
        AthleteWorkoutResponse.athlete_id == athlete_id,
        AthleteWorkoutResponse.stimulus_type == stimulus_type
    ).first()
    
    if response:
        # Update existing response with running average
        n = response.n_observations
        old_avg = response.avg_rpe_gap or 0
        old_completion = response.completion_rate or 1.0
        
        # Update running averages
        new_n = n + 1
        response.avg_rpe_gap = (old_avg * n + rpe_gap) / new_n
        response.completion_rate = (old_completion * n + completion_fraction) / new_n
        response.n_observations = new_n
        response.last_updated = datetime.now(timezone.utc)
        
        # Calculate new stddev (Welford's online algorithm approximation)
        if n > 0:
            old_stddev = response.rpe_gap_stddev or 0
            # Simple approximation: weight old variance with new deviation
            new_deviation = abs(rpe_gap - response.avg_rpe_gap)
            response.rpe_gap_stddev = (old_stddev * n + new_deviation) / new_n
        
        logger.info(
            f"Updated AthleteWorkoutResponse for {athlete_id}/{stimulus_type}: "
            f"avg_rpe_gap={response.avg_rpe_gap:.2f}, n={new_n}"
        )
    else:
        # Create new response record
        import uuid
        response = AthleteWorkoutResponse(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            stimulus_type=stimulus_type,
            avg_rpe_gap=rpe_gap,
            rpe_gap_stddev=0,
            completion_rate=completion_fraction,
            n_observations=1,
            first_observation=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc)
        )
        db.add(response)
        logger.info(
            f"Created AthleteWorkoutResponse for {athlete_id}/{stimulus_type}: "
            f"first rpe_gap={rpe_gap:.2f}"
        )
    
    # Check for significant patterns that should be banked as learnings
    learning_banked = False
    learning_type = None
    
    if response.n_observations >= 5:  # Enough data to detect patterns
        learning_banked, learning_type = _check_for_learnings(
            athlete_id=athlete_id,
            stimulus_type=stimulus_type,
            response=response,
            db=db
        )
    
    db.commit()
    
    return FeedbackCaptureResult(
        processed=True,
        stimulus_type=stimulus_type,
        rpe_gap=rpe_gap,
        new_learning_banked=learning_banked,
        learning_type=learning_type,
        notes=f"Updated {stimulus_type} response (n={response.n_observations})"
    )


def _infer_workout_type(activity) -> Optional[str]:
    """Infer workout type from activity data if not explicitly set."""
    # Use intensity score or heart rate data to infer
    if hasattr(activity, 'intensity_score') and activity.intensity_score:
        score = activity.intensity_score
        if score < 30:
            return "easy"
        elif score < 50:
            return "long_run"
        elif score < 70:
            return "threshold"
        elif score < 85:
            return "intervals"
        else:
            return "race"
    return None


def _check_for_learnings(
    athlete_id: UUID,
    stimulus_type: str,
    response,  # AthleteWorkoutResponse
    db: Session
) -> Tuple[bool, Optional[str]]:
    """
    Check if response patterns warrant banking a new learning.
    
    Patterns detected:
    - Consistent negative RPE gap (workout feels easier than expected) → what_works_stimulus
    - Consistent positive RPE gap (workout feels harder than expected) → what_doesnt_work_stimulus
    - Very low completion rate → what_doesnt_work_stimulus
    
    Returns:
        Tuple of (learning_banked, learning_type)
    """
    from models import AthleteLearning
    import uuid
    
    # Check if we already have a learning for this stimulus
    existing = db.query(AthleteLearning).filter(
        AthleteLearning.athlete_id == athlete_id,
        AthleteLearning.subject == f"stimulus:{stimulus_type}",
        AthleteLearning.is_active == True
    ).first()
    
    if existing:
        # Already have a learning - update confidence if pattern strengthens
        return False, None
    
    # Detect patterns
    avg_gap = response.avg_rpe_gap or 0
    stddev = response.rpe_gap_stddev or 1.0
    completion = response.completion_rate or 1.0
    n = response.n_observations
    
    # Strong pattern: consistently feels easier than expected (good)
    if avg_gap < -1.0 and n >= 8 and stddev < 1.5:
        learning = AthleteLearning(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            learning_type="what_works",
            subject=f"stimulus:{stimulus_type}",
            evidence={
                "avg_rpe_gap": avg_gap,
                "stddev": stddev,
                "n_observations": n,
                "completion_rate": completion
            },
            confidence=min(0.9, 0.5 + n * 0.05),  # Increases with observations
            discovered_at=datetime.now(timezone.utc),
            source="rpe_analysis",
            is_active=True
        )
        db.add(learning)
        logger.info(
            f"Banked learning: {stimulus_type} WORKS for athlete {athlete_id} "
            f"(avg_gap={avg_gap:.2f}, n={n})"
        )
        return True, "what_works"
    
    # Strong pattern: consistently feels harder than expected (concern)
    if avg_gap > 1.5 and n >= 8 and stddev < 2.0:
        learning = AthleteLearning(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            learning_type="what_doesnt_work",
            subject=f"stimulus:{stimulus_type}",
            evidence={
                "avg_rpe_gap": avg_gap,
                "stddev": stddev,
                "n_observations": n,
                "completion_rate": completion
            },
            confidence=min(0.9, 0.5 + n * 0.05),
            discovered_at=datetime.now(timezone.utc),
            source="rpe_analysis",
            is_active=True
        )
        db.add(learning)
        logger.info(
            f"Banked learning: {stimulus_type} DOESN'T WORK for athlete {athlete_id} "
            f"(avg_gap={avg_gap:.2f}, n={n})"
        )
        return True, "what_doesnt_work"
    
    # Low completion rate pattern
    if completion < 0.7 and n >= 5:
        learning = AthleteLearning(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            learning_type="what_doesnt_work",
            subject=f"stimulus:{stimulus_type}",
            evidence={
                "avg_rpe_gap": avg_gap,
                "completion_rate": completion,
                "n_observations": n
            },
            confidence=min(0.8, 0.4 + n * 0.05),
            discovered_at=datetime.now(timezone.utc),
            source="completion_analysis",
            is_active=True
        )
        db.add(learning)
        logger.info(
            f"Banked learning: {stimulus_type} has low completion for athlete {athlete_id} "
            f"(completion={completion:.1%}, n={n})"
        )
        return True, "what_doesnt_work"
    
    return False, None


def capture_race_outcome(
    athlete_id: UUID,
    race_activity_id: UUID,
    goal_achieved: bool,
    performance_vs_prediction: float,  # Negative = faster than predicted
    db: Session
) -> FeedbackCaptureResult:
    """
    Capture race outcome to update learnings.
    
    When an athlete completes a race:
    - If they exceeded prediction, boost confidence in recent training
    - If they underperformed, flag recent patterns for review
    
    Args:
        athlete_id: The athlete
        race_activity_id: The race activity
        goal_achieved: Whether they met their goal
        performance_vs_prediction: Seconds difference (negative = faster)
        db: Database session
    """
    from models import AthleteLearning, TrainingPlan, PlannedWorkout
    import uuid
    
    # Find the training plan that led to this race
    # This is complex - for now, log the outcome for future analysis
    
    logger.info(
        f"Race outcome captured: athlete={athlete_id}, "
        f"goal_achieved={goal_achieved}, vs_prediction={performance_vs_prediction:+.0f}s"
    )
    
    # If significantly exceeded prediction (ran faster by >1%), boost confidence
    if performance_vs_prediction < -60:  # More than 1 minute faster
        # Could create a "what_works" learning for the training approach
        # This requires knowing what templates were used in the build
        pass
    
    # If significantly underperformed, could flag for review
    if performance_vs_prediction > 120:  # More than 2 minutes slower
        # Could create a "what_doesnt_work" or trigger review
        pass
    
    return FeedbackCaptureResult(
        processed=True,
        stimulus_type="race",
        rpe_gap=None,
        new_learning_banked=False,
        learning_type=None,
        notes=f"Race outcome captured: {'goal achieved' if goal_achieved else 'goal missed'}"
    )


def get_athlete_response_summary(
    athlete_id: UUID,
    db: Session
) -> Dict[str, Dict]:
    """
    Get summary of athlete's workout responses for diagnostics.
    
    Returns:
        Dict mapping stimulus_type to response summary
    """
    from models import AthleteWorkoutResponse
    
    responses = db.query(AthleteWorkoutResponse).filter(
        AthleteWorkoutResponse.athlete_id == athlete_id
    ).all()
    
    return {
        r.stimulus_type: {
            "avg_rpe_gap": r.avg_rpe_gap,
            "rpe_gap_stddev": r.rpe_gap_stddev,
            "completion_rate": r.completion_rate,
            "n_observations": r.n_observations,
            "first_observation": r.first_observation.isoformat() if r.first_observation else None,
            "last_updated": r.last_updated.isoformat() if r.last_updated else None,
        }
        for r in responses
    }


def get_athlete_learnings_summary(
    athlete_id: UUID,
    db: Session
) -> Dict[str, list]:
    """
    Get summary of athlete's banked learnings for diagnostics.
    
    Returns:
        Dict with what_works, what_doesnt_work, injury_triggers lists
    """
    from models import AthleteLearning
    
    learnings = db.query(AthleteLearning).filter(
        AthleteLearning.athlete_id == athlete_id,
        AthleteLearning.is_active == True
    ).all()
    
    result = {
        "what_works": [],
        "what_doesnt_work": [],
        "injury_triggers": [],
        "preferences": []
    }
    
    for learning in learnings:
        entry = {
            "subject": learning.subject,
            "confidence": learning.confidence,
            "source": learning.source,
            "discovered_at": learning.discovered_at.isoformat() if learning.discovered_at else None
        }
        
        if learning.learning_type in result:
            result[learning.learning_type].append(entry)
    
    return result
