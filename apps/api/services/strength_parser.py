"""
Strength exercise set parser and idempotent writer.

Parses Garmin exerciseSets API responses into StrengthExerciseSet rows.
Applies the movement pattern taxonomy and computes estimated 1RM at write time.

Parser → writer is idempotent: for each activity_id, DELETE existing rows
then INSERT new rows in a single transaction.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import Activity, StrengthExerciseSet
from services.strength_taxonomy import (
    classify_session_type,
    estimate_1rm,
    is_unilateral,
    lookup_movement_pattern,
)

logger = logging.getLogger(__name__)


def parse_exercise_sets(
    raw_response: dict,
    activity_id: str,
    athlete_id: str,
) -> List[dict]:
    """Parse Garmin exerciseSets response into StrengthExerciseSet-ready dicts.

    Expected Garmin structure (from FIT SDK / community research):
    {
        "exerciseSets": [
            {
                "setType": "ACTIVE" | "REST",
                "exerciseCategory": "DEADLIFT",
                "exerciseName": "BARBELL_DEADLIFT",
                "repetitionCount": 5,
                "weight": 133.8,        # kg
                "duration": 45.0,       # seconds
                "setOrder": 1,
            },
            ...
        ]
    }

    Field names will be validated against Brian's first real webhook.
    If field names differ, update this parser — session_detail JSONB
    preserves the original payload for re-processing.
    """
    if isinstance(raw_response, list):
        exercise_sets_raw = raw_response
    else:
        exercise_sets_raw = raw_response.get("exerciseSets") or []

    parsed = []
    set_order = 0

    for raw_set in exercise_sets_raw:
        set_order += 1
        set_type_raw = (raw_set.get("setType") or "ACTIVE").upper()
        set_type = "rest" if set_type_raw == "REST" else "active"

        exercise_category = raw_set.get("exerciseCategory") or raw_set.get("category") or "UNKNOWN"
        exercise_name = raw_set.get("exerciseName") or raw_set.get("name") or exercise_category

        exercise_category = exercise_category.upper()
        exercise_name = exercise_name.upper()

        pattern, muscle_group = lookup_movement_pattern(exercise_name)
        if pattern == "compound_other":
            cat_pattern, cat_muscle = lookup_movement_pattern(exercise_category)
            if cat_pattern != "compound_other":
                pattern, muscle_group = cat_pattern, cat_muscle
            else:
                logger.warning(
                    "Unknown Garmin exercise: %s (category: %s) — classified as compound_other",
                    exercise_name,
                    exercise_category,
                    extra={
                        "exercise_name": exercise_name,
                        "exercise_category": exercise_category,
                        "athlete_id": athlete_id,
                        "activity_id": activity_id,
                    },
                )

        reps = raw_set.get("repetitionCount") or raw_set.get("reps")
        if reps is not None:
            try:
                reps = int(reps)
            except (ValueError, TypeError):
                reps = None

        weight_kg = raw_set.get("weight") or raw_set.get("weight_kg")
        if weight_kg is not None:
            try:
                weight_kg = float(weight_kg)
                if weight_kg <= 0:
                    weight_kg = None
            except (ValueError, TypeError):
                weight_kg = None

        duration_s = raw_set.get("duration") or raw_set.get("duration_s")
        if duration_s is not None:
            try:
                duration_s = float(duration_s)
            except (ValueError, TypeError):
                duration_s = None

        e1rm = estimate_1rm(weight_kg, reps)

        garmin_order = raw_set.get("setOrder")
        if garmin_order is not None:
            try:
                effective_order = int(garmin_order)
            except (ValueError, TypeError):
                effective_order = set_order
        else:
            effective_order = set_order

        parsed.append({
            "activity_id": activity_id,
            "athlete_id": athlete_id,
            "set_order": effective_order,
            "exercise_name_raw": exercise_name,
            "exercise_category": exercise_category,
            "movement_pattern": pattern,
            "muscle_group": muscle_group,
            "is_unilateral": is_unilateral(exercise_name),
            "set_type": set_type,
            "reps": reps,
            "weight_kg": weight_kg,
            "duration_s": duration_s,
            "estimated_1rm_kg": e1rm,
        })

    return parsed


def write_exercise_sets(db: Session, activity_id: str, parsed_sets: List[dict]) -> int:
    """Idempotent write: delete existing rows for this activity, then insert new.

    Returns the number of rows written.
    """
    db.query(StrengthExerciseSet).filter(
        StrengthExerciseSet.activity_id == activity_id
    ).delete(synchronize_session=False)

    rows = [StrengthExerciseSet(**s) for s in parsed_sets]
    db.add_all(rows)
    db.flush()
    return len(rows)


def classify_and_store_session_type(
    db: Session,
    activity: Activity,
    parsed_sets: List[dict],
) -> Optional[str]:
    """Classify session intensity and store on the Activity.

    Queries the athlete's historical peak 1RM per exercise category
    to compute relative intensity for classification.
    """
    from sqlalchemy import func as sa_func

    peak_1rm_rows = (
        db.query(
            StrengthExerciseSet.exercise_category,
            sa_func.max(StrengthExerciseSet.estimated_1rm_kg),
        )
        .filter(
            StrengthExerciseSet.athlete_id == activity.athlete_id,
            StrengthExerciseSet.estimated_1rm_kg.isnot(None),
        )
        .group_by(StrengthExerciseSet.exercise_category)
        .all()
    )

    peak_1rm_by_category = {cat: val for cat, val in peak_1rm_rows if val}

    session_type = classify_session_type(parsed_sets, peak_1rm_by_category)
    activity.strength_session_type = session_type
    return session_type


def process_strength_activity(
    db: Session,
    activity: Activity,
    raw_exercise_sets: dict,
) -> Dict[str, Any]:
    """Full pipeline: parse → write → classify → store raw.

    Returns a summary dict with keys: sets_written, session_type, unknown_exercises.
    """
    parsed = parse_exercise_sets(
        raw_exercise_sets,
        str(activity.id),
        str(activity.athlete_id),
    )

    active_parsed = [s for s in parsed if s["set_type"] == "active"]

    unknown = [
        s["exercise_name_raw"]
        for s in parsed
        if s["movement_pattern"] == "compound_other" and s["set_type"] == "active"
    ]

    sets_written = write_exercise_sets(db, str(activity.id), parsed)

    session_type = classify_and_store_session_type(db, activity, active_parsed)

    activity.session_detail = {
        **(activity.session_detail or {}),
        "exercise_sets_raw": raw_exercise_sets,
    }

    return {
        "sets_written": sets_written,
        "session_type": session_type,
        "unknown_exercises": unknown,
    }
