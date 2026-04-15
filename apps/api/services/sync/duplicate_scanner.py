"""
Retroactive Duplicate Scanner

Scans an athlete's activities for cross-provider duplicates and marks the
secondary record. The primary record inherits the best fields from both.

Uses the same matching logic as live ingestion (activity_deduplication.py):
±1 hour time window, ±5% distance, ±5 bpm HR.
"""

from __future__ import annotations

import logging
from typing import Dict
from uuid import UUID

from sqlalchemy.orm import Session

from models import Activity
from services.activity_deduplication import TIME_WINDOW_S, match_activities

logger = logging.getLogger(__name__)

# Columns where Garmin has richer sensor data
_GARMIN_PREFERRED = {
    "avg_hr", "max_hr", "avg_cadence", "max_cadence",
    "avg_stride_length_m", "avg_ground_contact_ms",
    "avg_vertical_oscillation_cm", "avg_power_w",
    "garmin_aerobic_te", "garmin_perceived_effort",
}

# Columns where Strava has athlete-curated metadata
_STRAVA_PREFERRED = {
    "name", "is_race_candidate", "workout_type",
}

# GPS/distance: prefer the record with longer moving_time_s
_GPS_COLUMNS = {
    "distance_m", "duration_s", "total_elevation_gain",
    "start_lat", "start_lng", "moving_time_s",
}

# Performance: prefer the higher value
_PERFORMANCE_COLUMNS = {
    "performance_percentage", "race_confidence", "intensity_score",
}


def _choose_primary(a: Activity, b: Activity) -> tuple[Activity, Activity]:
    """Return (primary, secondary). Prefer Garmin for physiology, Strava for names."""
    a_is_garmin = (a.provider or "").lower() == "garmin"
    b_is_garmin = (b.provider or "").lower() == "garmin"

    if a_is_garmin and not b_is_garmin:
        return a, b
    if b_is_garmin and not a_is_garmin:
        return b, a

    # Same provider or both unknown: keep the one with more data
    a_score = sum(1 for c in _GARMIN_PREFERRED if getattr(a, c, None) is not None)
    b_score = sum(1 for c in _GARMIN_PREFERRED if getattr(b, c, None) is not None)
    return (a, b) if a_score >= b_score else (b, a)


def _merge_fields(primary: Activity, secondary: Activity) -> None:
    """Fill gaps on the primary from the secondary."""
    for col in _GARMIN_PREFERRED:
        if getattr(primary, col, None) is None and getattr(secondary, col, None) is not None:
            setattr(primary, col, getattr(secondary, col))

    for col in _STRAVA_PREFERRED:
        prov_s = (secondary.provider or "").lower()
        if prov_s == "strava" and getattr(secondary, col, None) is not None:
            if getattr(primary, col, None) is None:
                setattr(primary, col, getattr(secondary, col))

    # GPS: prefer longer moving_time_s
    p_mt = primary.moving_time_s or 0
    s_mt = secondary.moving_time_s or 0
    if s_mt > p_mt:
        for col in _GPS_COLUMNS:
            val = getattr(secondary, col, None)
            if val is not None:
                setattr(primary, col, val)

    for col in _PERFORMANCE_COLUMNS:
        p_val = getattr(primary, col, None) or 0
        s_val = getattr(secondary, col, None) or 0
        if s_val > p_val:
            setattr(primary, col, getattr(secondary, col))


def scan_and_mark_duplicates(
    athlete_id: UUID,
    db: Session,
) -> Dict[str, int]:
    """
    Scan all activities for an athlete. Identify cross-provider duplicates.

    For each pair:
      - Choose primary (richer data), merge best fields from secondary
      - Mark secondary as is_duplicate=True, duplicate_of_id=primary.id

    Returns: {"pairs_found": int, "marked_duplicate": int}
    """
    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.is_duplicate == False,  # noqa: E712
        )
        .order_by(Activity.start_time)
        .all()
    )

    already_dup: set[UUID] = set()
    pairs_found = 0

    for i in range(len(activities)):
        a = activities[i]
        if a.id in already_dup:
            continue

        for j in range(i + 1, len(activities)):
            b = activities[j]
            if b.id in already_dup:
                continue

            # Activities are sorted ascending.  Once b is more than
            # TIME_WINDOW_S ahead of a, no later activity can match either.
            if (b.start_time - a.start_time).total_seconds() > TIME_WINDOW_S:
                break

            # Same provider can't be a cross-provider dup
            if a.provider and b.provider and a.provider == b.provider:
                continue

            a_dict = {
                "start_time": a.start_time,
                "distance_m": float(a.distance_m) if a.distance_m else None,
                "avg_hr": a.avg_hr,
            }
            b_dict = {
                "start_time": b.start_time,
                "distance_m": float(b.distance_m) if b.distance_m else None,
                "avg_hr": b.avg_hr,
            }

            if not match_activities(a_dict, b_dict):
                # Fallback: duration-based match catches cases where providers
                # report different distances (Garmin DI vs Strava GPS drift).
                # Only applies when distances are close or one is missing.
                ta = a.duration_s or 0
                tb = b.duration_s or 0
                if ta <= 0 or tb <= 0 or abs(ta - tb) / max(ta, tb) > 0.03:
                    continue
                da = float(a.distance_m) if a.distance_m else 0.0
                db_dist = float(b.distance_m) if b.distance_m else 0.0
                if da > 0 and db_dist > 0 and abs(da - db_dist) / max(da, db_dist) > 0.20:
                    continue

            primary, secondary = _choose_primary(a, b)
            _merge_fields(primary, secondary)

            secondary.is_duplicate = True
            secondary.duplicate_of_id = primary.id

            already_dup.add(secondary.id)
            pairs_found += 1

            logger.info(
                "Duplicate pair: %s (%s) kept, %s (%s) marked duplicate",
                primary.id, primary.provider, secondary.id, secondary.provider,
            )
            # One primary gets one secondary.  Stop searching for this `a`
            # so we don't falsely pair the same primary with a later record
            # that happens to have the same distance (e.g. doubles training).
            break

    db.flush()
    return {"pairs_found": pairs_found, "marked_duplicate": len(already_dup)}
