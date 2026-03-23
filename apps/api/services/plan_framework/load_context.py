"""
P4 load context — history-aware baselines for plan_framework generation.

Dual threshold policy (document in code; see ADR-061 vs PLAN_COACHED D1):
- AthletePlanProfile long-run identification: 105 min (physiology gate) — elsewhere.
- P4 L30 easy-long max: 90 min + not-race (recent session ceiling for spike baseline).

H2 window: 30 **athlete-local calendar days** inclusive ending at reference_date:
  [reference_date - 29 days, reference_date] inclusive (IANA tz from athlete;
  GPS-backed when `infer_and_persist_athlete_timezone` has run).
  Query bounds: half-open UTC ``[start, end)`` from ``local_day_bounds_utc`` via
  ``get_canonical_run_activities(..., end_time_exclusive=True)`` — no inclusive-end
  microsecond hacks (avoids PG/timestamptz edge cases and empty L30 on CI).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def history_anchor_date(
    plan_start_date: Optional[date],
    db: Optional[Session] = None,
    athlete_id: Optional[UUID] = None,
) -> date:
    """
    Activity history lives in the past. If the plan starts in the future, L30 / 4w
    windows must still intersect synced runs — anchor on the athlete's **local today**
    when `db` + `athlete_id` are provided (`athlete_local_today`), else `date.today()`
    (tests / callers without an athlete).
    If the plan is backdated (start <= that today), anchor on plan start.
    """
    if db is not None and athlete_id is not None:
        from services.timezone_utils import (
            athlete_local_today,
            get_athlete_timezone_from_db,
        )

        today = athlete_local_today(get_athlete_timezone_from_db(db, athlete_id))
    else:
        today = date.today()
    if plan_start_date is None or plan_start_date > today:
        return today
    return plan_start_date


def _athlete_query_window_utc(
    db: Session,
    athlete_id: UUID,
    reference_date: date,
    first_local_day: date,
) -> Tuple[datetime, datetime]:
    """
    Half-open UTC window [start, end) for Activity.start_time, spanning athlete-local
    calendar days first_local_day .. reference_date (inclusive on the calendar).

    ``end`` is ``local_day_bounds_utc(reference_date)[1]`` (exclusive next local midnight).
    Callers must use ``get_canonical_run_activities(..., end_time_exclusive=True)``.
    """
    from services.timezone_utils import get_athlete_timezone_from_db, local_day_bounds_utc

    tz = get_athlete_timezone_from_db(db, athlete_id)
    window_start_utc, _ = local_day_bounds_utc(first_local_day, tz)
    _, window_end_exclusive_utc = local_day_bounds_utc(reference_date, tz)
    return window_start_utc, window_end_exclusive_utc


# Locked 2026-03-22 (BUILDER_INSTRUCTIONS_2026-03-22_P4_LOAD_CONTEXT.md)
P4_C_UPPER = 1.15
P4_D4_N = 8
P4_D4_M_DAYS = 120
P4_L30_INCLUSIVE_DAYS = 30  # span: ref - (30-1) .. ref
P4_EASY_LONG_MIN_DURATION_MIN = 90.0


def _activity_local_calendar_date(start_time: datetime, tz) -> date:
    """Instant → athlete-local calendar date (not UTC calendar)."""
    from services.timezone_utils import to_athlete_local_date

    return to_athlete_local_date(start_time, tz)


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
    from services.timezone_utils import get_athlete_timezone_from_db, local_day_bounds_utc

    tz = get_athlete_timezone_from_db(db, athlete_id)
    _, ref_end_exclusive = local_day_bounds_utc(reference_date, tz)
    start = ref_end_exclusive - timedelta(days=730)
    acts, _ = get_canonical_run_activities(
        athlete_id,
        db,
        start_time=start,
        end_time=ref_end_exclusive,
        end_time_exclusive=True,
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
            d = _activity_local_calendar_date(a.start_time, tz)
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

    l30_first_local = reference_date - timedelta(days=P4_L30_INCLUSIVE_DAYS - 1)
    l30_start_dt, ref_end_exclusive = _athlete_query_window_utc(
        db, athlete_id, reference_date, l30_first_local
    )

    acts_l30, _ = get_canonical_run_activities(
        athlete_id,
        db,
        start_time=l30_start_dt,
        end_time=ref_end_exclusive,
        end_time_exclusive=True,
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

    four_week_first_local = reference_date - timedelta(days=28)
    four_week_start_dt, _ = _athlete_query_window_utc(
        db, athlete_id, reference_date, four_week_first_local
    )
    acts_4w, _ = get_canonical_run_activities(
        athlete_id,
        db,
        start_time=four_week_start_dt,
        end_time=ref_end_exclusive,
        end_time_exclusive=True,
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
    observed_recent_weekly_miles: Optional[float] = None,
) -> Optional[float]:
    """max(L30, tier start long) when L30 present; else None.

    Phase 3 note: this function provides the L30 component to the upstream
    caller (WorkoutPrescriptionGenerator), where it is combined with p75_8w
    and p50_16w from FitnessBank to produce the full Option A floor:
      floor = max(L30, p75_8w, p50_16w)
    via compute_athlete_long_run_floor in plan_quality_gate.py.

    Guard: cap floor to 42% of recent weekly band to prevent one-off ultra/marathon
    long runs from seeding an absurd week-1 long run target. Preserves the tier
    start_long minimum so inexperienced athletes still get a meaningful seed.
    """
    if l30_max_mi is None:
        return None
    from .constants import Distance as DistEnum
    from .workout_scaler import peak_long_miles, standard_start_long_miles

    try:
        goal = DistEnum(distance)
    except ValueError:
        goal = DistEnum.MARATHON
    start_long = min(standard_start_long_miles(goal, tier), peak_long_miles(goal, tier))
    floor = max(float(l30_max_mi), float(start_long))
    # Prevent a single outlier long run (e.g. a 26-mi marathon 8 days ago) from
    # forcing week-1 of a 10K or 5K plan to match that distance.
    if observed_recent_weekly_miles is not None and observed_recent_weekly_miles > 0:
        band_cap = float(observed_recent_weekly_miles) * 0.42
        floor = min(floor, max(float(start_long), band_cap))
    return floor
