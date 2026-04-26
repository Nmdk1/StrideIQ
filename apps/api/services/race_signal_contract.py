"""
Authoritative race-signal contract for activity-derived race evidence.

This centralizes the race candidate rules used by pace and anchor consumers:
- user_verified_race == True, OR
- normalized workout_type in {"race", "race_effort"}, OR
- is_race_candidate == True AND race_confidence >= 0.7
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, func, or_


AUTHORITATIVE_RACE_WORKOUT_TYPES = {"race", "race_effort"}


def normalize_distance_alias(distance: Optional[str]) -> str:
    raw = str(distance or "").strip().lower()
    if raw in {"half", "half_marathon", "hm"}:
        return "half_marathon"
    if raw in {"5k", "10k", "10_mile", "marathon"}:
        return raw
    return raw


def workout_type_is_race(workout_type: Optional[str]) -> bool:
    wt = str(workout_type or "").strip().lower()
    return wt in AUTHORITATIVE_RACE_WORKOUT_TYPES


def activity_is_authoritative_race(activity) -> bool:
    if bool(getattr(activity, "user_verified_race", False)):
        return True
    if workout_type_is_race(getattr(activity, "workout_type", None)):
        return True
    return bool(getattr(activity, "is_race_candidate", False)) and float(
        getattr(activity, "race_confidence", 0.0) or 0.0
    ) >= 0.7


def authoritative_race_filter(ActivityModel):
    """Return SQLAlchemy OR expression for authoritative race activities."""
    normalized_workout_type = func.lower(func.coalesce(ActivityModel.workout_type, ""))
    return or_(
        ActivityModel.user_verified_race == True,  # noqa: E712
        normalized_workout_type.in_(tuple(AUTHORITATIVE_RACE_WORKOUT_TYPES)),
        and_(
            ActivityModel.is_race_candidate == True,  # noqa: E712
            ActivityModel.race_confidence >= 0.7,
        ),
    )
