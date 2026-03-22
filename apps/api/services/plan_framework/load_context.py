"""
P4 load context — history-aware baselines for plan_framework generation.

Dual threshold policy (document in code; see ADR-061 vs PLAN_COACHED D1):
- AthletePlanProfile long-run identification: 105 min (physiology gate) — elsewhere.
- P4 L30 easy-long max: 90 min + not-race (recent session ceiling for spike baseline).

H2 window: 30 **calendar days** inclusive ending at reference_date:
  [reference_date - 29 days, reference_date] inclusive.
  An activity on (reference_date - 30 days) is **out** (31-day gap from window start).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Locked 2026-03-22 (BUILDER_INSTRUCTIONS_2026-03-22_P4_LOAD_CONTEXT.md)
P4_C_UPPER = 1.15
P4_D4_N = 8
P4_D4_M_DAYS = 120
P4_L30_INCLUSIVE_DAYS = 30  # span: ref - (30-1) .. ref
P4_EASY_LONG_MIN_DURATION_MIN = 90.0


def _activity_calendar_date_utc(start_time: datetime) -> date:
    if start_time.tzinfo is not None:
        return start_time.astimezone(timezone.utc).date()
    return start_time.date()


def is_activity_excluded_as_race_for_p4(activity) -> bool:
    """Parity with historical long-run spike logic (race exclusion)."""
    wt_raw = getattr(activity, "workout_type", None) or ""
    wt = str(wt_raw).lower()
    if wt == "race":
        return True
    if getattr(activity, "is_race_candidate", False):
        return True
    return False


def compute_d4_long_run_override_and_stats(
    db: Session,
    athlete_id: UUID,
    reference_date: date,
) -> Tuple[bool, int, Optional[date], int]:
    """
    D4: count_long_15plus >= P4_D4_N in trailing 24 months (non-race),
    and last >=18 mi within P4_D4_M_DAYS before reference_date.

    Returns (override_bool, count_15plus, last_18mi_date_or_none, count_18plus_runs).
    """
    from services.mileage_aggregation import get_canonical_run_activities

    end = datetime.combine(reference_date, time(23, 59, 59), tzinfo=timezone.utc)
    start = end - timedelta(days=730)
    acts, _ = get_canonical_run_activities(
        athlete_id,
        db,
        start_time=start,
        end_time=end,
        require_trusted_duplicate_flags=False,
    )
    count15 = 0
    count18 = 0
    last18: Optional[date] = None
    for a in acts:
        if is_activity_excluded_as_race_for_p4(a):
            continue
        mi = (getattr(a, "distance_m", None) or 0) / 1609.344
        if mi >= 15:
            count15 += 1
        if mi >= 18:
            count18 += 1
            d = _activity_calendar_date_utc(a.start_time)
            if last18 is None or d > last18:
                last18 = d
    if count15 < P4_D4_N or last18 is None:
        return False, count15, last18, count18
    days = (reference_date - last18).days
    return days <= P4_D4_M_DAYS, count15, last18, count18


@dataclass
class LoadContext:
    reference_date: date
    l30_max_easy_long_mi: Optional[float]
    observed_recent_weekly_miles: Optional[float]
    history_override_easy_long: bool
    disclosures: List[str] = field(default_factory=list)
    count_long_15plus: int = 0
    count_long_18plus: int = 0
    recency_last_18plus_days: Optional[int] = None


def build_load_context(
    athlete_id: UUID,
    db: Session,
    reference_date: date,
) -> LoadContext:
    """
    Read-only snapshot for P4 wiring. Safe to call in request path; log+rethrow
    callers may fall back to cold template on exception.
    """
    from services.mileage_aggregation import (
        compute_peak_and_current_weekly_miles,
        get_canonical_run_activities,
    )

    disclosures: List[str] = []

    ref_end = datetime.combine(reference_date, time(23, 59, 59), tzinfo=timezone.utc)
    l30_start = reference_date - timedelta(days=P4_L30_INCLUSIVE_DAYS - 1)
    l30_start_dt = datetime.combine(l30_start, time.min, tzinfo=timezone.utc)

    acts_l30, _ = get_canonical_run_activities(
        athlete_id,
        db,
        start_time=l30_start_dt,
        end_time=ref_end,
        require_trusted_duplicate_flags=True,
    )

    max_l30: Optional[float] = None
    for a in acts_l30:
        if is_activity_excluded_as_race_for_p4(a):
            continue
        dur_m = (getattr(a, "duration_s", None) or 0) / 60.0
        if dur_m < P4_EASY_LONG_MIN_DURATION_MIN:
            continue
        mi = (getattr(a, "distance_m", None) or 0) / 1609.344
        if mi <= 0:
            continue
        max_l30 = mi if max_l30 is None else max(max_l30, mi)

    if max_l30 is None:
        disclosures.append("cold_start_l30")

    four_week_start = reference_date - timedelta(days=28)
    four_week_start_dt = datetime.combine(four_week_start, time.min, tzinfo=timezone.utc)
    acts_4w, _ = get_canonical_run_activities(
        athlete_id,
        db,
        start_time=four_week_start_dt,
        end_time=ref_end,
        require_trusted_duplicate_flags=True,
    )

    observed: Optional[float] = None
    if acts_4w:
        _peak, cur = compute_peak_and_current_weekly_miles(acts_4w, now=reference_date)
        if cur and cur > 0:
            observed = float(cur)
            disclosures.append("observed_4w_mpw")

    d4_ok, count15, last18, count18 = compute_d4_long_run_override_and_stats(
        db, athlete_id, reference_date
    )
    if last18 is not None:
        recency_days = (reference_date - last18).days
    else:
        recency_days = None
    if d4_ok:
        disclosures.append("d4_history_override")

    return LoadContext(
        reference_date=reference_date,
        l30_max_easy_long_mi=max_l30,
        observed_recent_weekly_miles=observed,
        history_override_easy_long=d4_ok,
        disclosures=disclosures,
        count_long_15plus=count15,
        count_long_18plus=count18,
        recency_last_18plus_days=recency_days,
    )


def effective_starting_weekly_miles_semi_custom(
    request_mpw: float,
    load_ctx: LoadContext,
    tier_max_weekly_miles: float,
) -> float:
    """§4.1 semi-custom: max(req, obs) capped by min(obs*C_upper, tier_max)."""
    obs = load_ctx.observed_recent_weekly_miles
    if obs is None:
        return float(request_mpw)
    raw = max(float(request_mpw), float(obs))
    cap = min(float(obs) * P4_C_UPPER, float(tier_max_weekly_miles))
    return min(raw, cap)


def easy_long_floor_miles_from_l30(
    l30_max_mi: Optional[float],
    distance: str,
    tier: str,
) -> Optional[float]:
    """max(L30, tier start long) when L30 present; else None."""
    if l30_max_mi is None:
        return None
    from .constants import Distance as DistEnum
    from .workout_scaler import peak_long_miles, standard_start_long_miles

    try:
        goal = DistEnum(distance)
    except ValueError:
        goal = DistEnum.MARATHON
    start_long = min(standard_start_long_miles(goal, tier), peak_long_miles(goal, tier))
    return max(float(l30_max_mi), float(start_long))
