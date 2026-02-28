"""
Garmin Ingestion Health Service

Read-only monitoring helper that computes GarminDay coverage statistics
for every Garmin-connected athlete.  Used by both the admin API endpoint
and the daily Celery Beat health-check task so the metric logic is shared
and deterministic.

Contract:
- Query only. No writes, no Garmin API calls, no ingestion side-effects.
- Coverage window: last 7 calendar days (UTC), including today.
- Threshold for "underfed": sleep_coverage_7d < 0.50 OR hrv_coverage_7d < 0.50.
"""

import logging
from datetime import date, timedelta, timezone, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from models import Athlete, GarminDay

logger = logging.getLogger(__name__)

UNDERFED_THRESHOLD = 0.50  # < 50% days with data → underfed


def _utc_today() -> date:
    return datetime.now(tz=timezone.utc).date()


def compute_garmin_coverage(db: Session) -> Dict[str, Any]:
    """
    Compute 7-day GarminDay coverage for all Garmin-connected athletes.

    Returns a dict with:
      checked_at_utc           — ISO timestamp
      total_connected_garmin_athletes — int
      athletes_below_threshold_count  — int
      athletes                 — list of per-athlete dicts (see below)

    Per-athlete dict fields:
      athlete_id, email, last_row_date,
      days_with_rows_7d, sleep_days_non_null_7d, hrv_days_non_null_7d,
      resting_hr_days_non_null_7d,
      sleep_coverage_7d, hrv_coverage_7d, resting_hr_coverage_7d,
      is_underfed (bool)
    """
    today = _utc_today()
    window_start = today - timedelta(days=6)  # 7-day window inclusive

    connected_athletes = (
        db.query(Athlete)
        .filter(Athlete.garmin_connected.is_(True))
        .order_by(Athlete.created_at.asc())
        .all()
    )

    if not connected_athletes:
        return {
            "checked_at_utc": datetime.now(tz=timezone.utc).isoformat(),
            "total_connected_garmin_athletes": 0,
            "athletes_below_threshold_count": 0,
            "athletes": [],
        }

    athlete_ids = [a.id for a in connected_athletes]

    # Single query: aggregate per-athlete stats over the 7-day window.
    rows = (
        db.query(
            GarminDay.athlete_id,
            func.count(GarminDay.id).label("days_with_rows"),
            func.max(GarminDay.calendar_date).label("last_row_date"),
            func.count(GarminDay.sleep_total_s).label("sleep_days"),
            func.count(GarminDay.hrv_overnight_avg).label("hrv_days"),
            func.count(GarminDay.resting_hr).label("resting_hr_days"),
        )
        .filter(
            GarminDay.athlete_id.in_(athlete_ids),
            GarminDay.calendar_date >= window_start,
            GarminDay.calendar_date <= today,
        )
        .group_by(GarminDay.athlete_id)
        .all()
    )

    stats_by_athlete: Dict[UUID, Dict] = {r.athlete_id: r for r in rows}
    athlete_by_id: Dict[UUID, Athlete] = {a.id: a for a in connected_athletes}

    results = []
    below_threshold = 0

    for athlete in connected_athletes:
        row = stats_by_athlete.get(athlete.id)

        days_with_rows = int(row.days_with_rows) if row else 0
        sleep_days = int(row.sleep_days) if row else 0
        hrv_days = int(row.hrv_days) if row else 0
        rhr_days = int(row.resting_hr_days) if row else 0
        last_row_date = row.last_row_date if row else None

        sleep_cov = round(sleep_days / 7, 4)
        hrv_cov = round(hrv_days / 7, 4)
        rhr_cov = round(rhr_days / 7, 4)
        is_underfed = sleep_cov < UNDERFED_THRESHOLD or hrv_cov < UNDERFED_THRESHOLD

        if is_underfed:
            below_threshold += 1

        results.append(
            {
                "athlete_id": str(athlete.id),
                "email": athlete.email,
                "last_row_date": last_row_date.isoformat() if last_row_date else None,
                "days_with_rows_7d": days_with_rows,
                "sleep_days_non_null_7d": sleep_days,
                "hrv_days_non_null_7d": hrv_days,
                "resting_hr_days_non_null_7d": rhr_days,
                "sleep_coverage_7d": sleep_cov,
                "hrv_coverage_7d": hrv_cov,
                "resting_hr_coverage_7d": rhr_cov,
                "is_underfed": is_underfed,
            }
        )

    return {
        "checked_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "total_connected_garmin_athletes": len(connected_athletes),
        "athletes_below_threshold_count": below_threshold,
        "athletes": results,
    }


def emit_health_log_lines(coverage: Dict[str, Any]) -> None:
    """
    Emit one structured log line per athlete in the coverage report.

    Format:
      [garmin-health] athlete=<id> sleep=<x>/7 hrv=<y>/7 resting_hr=<z>/7 last_row=<date> [status=underfed]

    Underfed athletes → WARNING level; healthy → INFO level.
    """
    for a in coverage.get("athletes", []):
        sleep = a["sleep_days_non_null_7d"]
        hrv = a["hrv_days_non_null_7d"]
        rhr = a["resting_hr_days_non_null_7d"]
        last_row = a["last_row_date"] or "none"
        athlete_id = a["athlete_id"]
        status_suffix = " status=underfed" if a["is_underfed"] else ""

        line = (
            f"[garmin-health] athlete={athlete_id} "
            f"sleep={sleep}/7 hrv={hrv}/7 resting_hr={rhr}/7 "
            f"last_row={last_row}{status_suffix}"
        )

        if a["is_underfed"]:
            logger.warning(line)
        else:
            logger.info(line)
