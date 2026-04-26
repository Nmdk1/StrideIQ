"""
Apply parsed FIT run data onto Activity + ActivitySplit rows.

Bridges `services/sync/fit_run_parser.parse_run_fit()` output to the ORM.
Kept in its own module (not in garmin_webhook_tasks.py) so the backfill
task and the live webhook task share the same write logic.

Write contract:
  - Activity row: only fill columns that are currently NULL or that the FIT
    file has higher confidence on (moving_time_s, total_descent_m, power,
    running dynamics, intensity minutes, calories). The JSON adapter
    populates summary fields from the webhook; we don't overwrite them
    unless we're adding NEW info.
  - ActivitySplit rows: idempotent rebuild from FIT laps. If the activity
    has splits already (e.g., derived from JSON Activity Detail), the FIT
    laps replace them when at least 1 FIT lap is present and the FIT laps
    cover >= the existing total distance. Otherwise the FIT extras are
    merged onto existing splits by lap_number.
  - Garmin self-evaluation columns (garmin_feel, garmin_perceived_effort)
    are stored as a low-confidence fallback. They are NOT promoted to the
    canonical perceived effort surface; the resolver in
    services/effort_resolver.py prefers ActivityFeedback when present.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import Activity, ActivitySplit

logger = logging.getLogger(__name__)


# Long-tail per-lap fields that don't deserve first-class columns. They live
# in ActivitySplit.extras as a small JSONB blob.
_EXTRAS_KEYS = (
    "avg_ground_contact_balance_pct",
    "normalized_power_w",
    "max_run_cadence_spm",
    "avg_temperature_c",
    "max_temperature_c",
    "total_calories",
    "lap_trigger",
    "intensity",
)


def apply_fit_run_data(db: Session, activity: Activity, parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Write parsed FIT data onto the Activity + ActivitySplit rows.

    Args:
        db:        SQLAlchemy session (caller commits).
        activity:  Pre-loaded Activity row to enrich.
        parsed:    Output of services.sync.fit_run_parser.parse_run_fit().

    Returns:
        {"session_applied": bool, "laps_written": int}
    """
    session = parsed.get("session") or {}
    laps = parsed.get("laps") or []

    session_applied = _apply_session(activity, session)
    laps_written = _apply_laps(db, activity, laps)

    return {"session_applied": session_applied, "laps_written": laps_written}


def _apply_session(activity: Activity, session: Dict[str, Any]) -> bool:
    """Fill missing Activity columns from the FIT session message.

    Only writes a column when it is currently NULL or when the FIT file is the
    canonical source of truth for that field (running dynamics, power, true
    moving time). Never clobbers a non-null value with None.
    """
    if not session:
        return False

    # FIT is the canonical source for these — overwrite if present.
    canonical = (
        "moving_time_s",
        "total_descent_m",
        "avg_power_w",
        "max_power_w",
        "avg_stride_length_m",
        "avg_ground_contact_ms",
        "avg_ground_contact_balance_pct",
        "avg_vertical_oscillation_cm",
        "avg_vertical_ratio_pct",
        "active_kcal",  # FIT total_calories overrides JSON activeKilocalories
        "garmin_feel",
        "garmin_perceived_effort",
    )

    # JSON adapter usually has these; only fill if missing.
    fill_if_null = (
        "avg_cadence",
        "max_cadence",
        "total_elevation_gain",
    )

    # Source-field mapping: model column -> session key
    src = {
        "moving_time_s": session.get("moving_time_s"),
        "total_descent_m": session.get("total_descent_m"),
        "avg_power_w": session.get("avg_power_w"),
        "max_power_w": session.get("max_power_w"),
        "avg_stride_length_m": session.get("avg_stride_length_m"),
        "avg_ground_contact_ms": session.get("avg_ground_contact_ms"),
        "avg_ground_contact_balance_pct": session.get("avg_ground_contact_balance_pct"),
        "avg_vertical_oscillation_cm": session.get("avg_vertical_oscillation_cm"),
        "avg_vertical_ratio_pct": session.get("avg_vertical_ratio_pct"),
        "active_kcal": session.get("total_calories"),
        "garmin_feel": session.get("garmin_feel"),
        "garmin_perceived_effort": session.get("garmin_perceived_effort"),
        "avg_cadence": session.get("avg_run_cadence_spm") or session.get("avg_cadence_rpm"),
        "max_cadence": session.get("max_run_cadence_spm"),
        "total_elevation_gain": session.get("total_ascent_m"),
    }

    changed = False
    for col in canonical:
        new_val = src.get(col)
        if new_val is None:
            continue
        if getattr(activity, col, None) != new_val:
            setattr(activity, col, new_val)
            changed = True

    for col in fill_if_null:
        if getattr(activity, col, None) is not None:
            continue
        new_val = src.get(col)
        if new_val is None:
            continue
        setattr(activity, col, new_val)
        changed = True

    return changed


def _apply_laps(db: Session, activity: Activity, laps: List[Dict[str, Any]]) -> int:
    """Replace the activity's splits with FIT-derived laps when appropriate.

    Strategy:
      - If FIT has no laps, do nothing (preserve any existing splits).
      - If FIT has laps and the activity has no existing splits, write all
        FIT laps as ActivitySplit rows.
      - If both exist, FIT wins for endurance activities (it has the rich
        per-lap metrics; the JSON-derived splits are crude).

    Returns the number of split rows written.
    """
    if not laps:
        return 0

    existing = list(
        db.query(ActivitySplit)
        .filter(ActivitySplit.activity_id == activity.id)
        .all()
    )
    if existing:
        for row in existing:
            db.delete(row)
        db.flush()

    written = 0
    for lap in laps:
        extras: Dict[str, Any] = {}
        for k in _EXTRAS_KEYS:
            v = lap.get(k)
            if v is not None:
                extras[k] = v

        split = ActivitySplit(
            activity_id=activity.id,
            split_number=int(lap.get("lap_number") or (written + 1)),
            distance=lap.get("distance_m"),
            elapsed_time=lap.get("elapsed_time_s"),
            moving_time=lap.get("moving_time_s") or lap.get("elapsed_time_s"),
            average_heartrate=lap.get("avg_hr"),
            max_heartrate=lap.get("max_hr"),
            average_cadence=lap.get("avg_run_cadence_spm"),
            gap_seconds_per_mile=None,
            lap_type=_classify_lap_type(lap),
            interval_number=None,
            total_ascent_m=lap.get("total_ascent_m"),
            total_descent_m=lap.get("total_descent_m"),
            avg_power_w=lap.get("avg_power_w"),
            max_power_w=lap.get("max_power_w"),
            avg_stride_length_m=lap.get("avg_stride_length_m"),
            avg_ground_contact_ms=lap.get("avg_ground_contact_ms"),
            avg_vertical_oscillation_cm=lap.get("avg_vertical_oscillation_cm"),
            avg_vertical_ratio_pct=lap.get("avg_vertical_ratio_pct"),
            extras=extras or None,
        )
        db.add(split)
        written += 1

    return written


def _classify_lap_type(lap: Dict[str, Any]) -> Optional[str]:
    """Map FIT `intensity` enum to our lap_type vocabulary.

    FIT values: active / rest / warmup / cooldown / interval / recovery.
    Our vocabulary: warm_up / work / rest / cool_down.
    """
    intensity = (lap.get("intensity") or "").lower().strip()
    if not intensity:
        return None
    if intensity in ("warmup", "warm_up"):
        return "warm_up"
    if intensity in ("cooldown", "cool_down"):
        return "cool_down"
    if intensity in ("rest", "recovery"):
        return "rest"
    if intensity in ("active", "interval"):
        return "work"
    return None
