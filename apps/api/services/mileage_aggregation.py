"""
Canonical mileage aggregation for planning-critical reads.

Contract:
- Default path trusts DB duplicate flags (Activity.is_duplicate == False).
- Optional fallback near-duplicate collapse can be enabled explicitly for
  historical slices where duplicate flags are known to be stale/untrusted.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session


def _provider_rank(provider: Optional[str]) -> int:
    p = (provider or "").lower()
    if p == "strava":
        return 3
    if p == "garmin":
        return 2
    if p:
        return 1
    return 0


def _activities_are_probable_duplicates(a, b) -> bool:
    try:
        dt_s = abs((a.start_time - b.start_time).total_seconds())
    except Exception:
        return False
    if dt_s > 10 * 60:  # 10 minutes
        return False

    da = a.distance_m or 0
    db = b.distance_m or 0
    if da > 0 and db > 0:
        if abs(da - db) > max(150, int(0.02 * max(da, db))):
            return False

    ta = a.duration_s or 0
    tb = b.duration_s or 0
    if ta > 0 and tb > 0:
        if abs(ta - tb) > max(300, int(0.10 * max(ta, tb))):
            return False

    return True


def collapse_probable_provider_duplicates(activities: List) -> Tuple[List, int]:
    """Collapse probable cross-provider duplicate activities."""
    if not activities:
        return [], 0

    acts = sorted(activities, key=lambda x: x.start_time)
    kept: List = []
    dropped = 0

    for act in acts:
        matched_idx: Optional[int] = None
        for i in range(max(0, len(kept) - 5), len(kept)):
            if _activities_are_probable_duplicates(act, kept[i]):
                matched_idx = i
                break

        if matched_idx is None:
            kept.append(act)
            continue

        incumbent = kept[matched_idx]
        dropped += 1
        if _provider_rank(getattr(act, "provider", None)) > _provider_rank(
            getattr(incumbent, "provider", None)
        ):
            kept[matched_idx] = act

    return kept, dropped


def get_canonical_run_activities(
    athlete_id: UUID,
    db: Session,
    *,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    require_trusted_duplicate_flags: bool = True,
) -> Tuple[List, Dict[str, int]]:
    """
    Canonical run-activity read path for mileage totals.

    Returns (activities, telemetry) where telemetry includes:
    - source_count
    - output_count
    - fallback_dedupe_used (0/1)
    - dedupe_pairs_collapsed
    """
    from models import Activity

    query = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.sport.ilike("run"),
    )

    if start_time is not None:
        query = query.filter(Activity.start_time >= start_time)
    if end_time is not None:
        query = query.filter(Activity.start_time <= end_time)

    if require_trusted_duplicate_flags:
        query = query.filter(Activity.is_duplicate == False)  # noqa: E712
        activities = query.order_by(Activity.start_time.desc()).all()
        return activities, {
            "source_count": len(activities),
            "output_count": len(activities),
            "fallback_dedupe_used": 0,
            "dedupe_pairs_collapsed": 0,
        }

    activities = query.order_by(Activity.start_time.desc()).all()
    collapsed, dropped = collapse_probable_provider_duplicates(activities)
    return collapsed, {
        "source_count": len(activities),
        "output_count": len(collapsed),
        "fallback_dedupe_used": 1,
        "dedupe_pairs_collapsed": dropped,
    }


def compute_weekly_mileage(activities: List) -> Dict[date, float]:
    """Return week_start_date -> mileage for supplied activities."""
    weekly_miles: Dict[date, float] = {}
    for activity in activities:
        if not getattr(activity, "start_time", None):
            continue
        week_start = activity.start_time.date() - timedelta(
            days=activity.start_time.weekday()
        )
        miles = (getattr(activity, "distance_m", 0) or 0) / 1609.344
        weekly_miles[week_start] = weekly_miles.get(week_start, 0.0) + miles
    return weekly_miles


def compute_peak_and_current_weekly_miles(
    activities: List,
    now: Optional[date] = None,
) -> Tuple[float, float]:
    """
    Return (peak_weekly_miles, current_weekly_miles).

    current_weekly_miles = average of observed weeks in the trailing 4-week window.
    """
    if now is None:
        now = date.today()

    weekly_miles = compute_weekly_mileage(activities)
    if not weekly_miles:
        return 0.0, 0.0

    peak_weekly = max(weekly_miles.values())
    four_weeks_ago = now - timedelta(days=28)
    trailing = [m for ws, m in weekly_miles.items() if ws >= four_weeks_ago]
    current_weekly = (sum(trailing) / len(trailing)) if trailing else 0.0
    return peak_weekly, current_weekly


def compute_recent_weekly_band(
    activities: List,
    now: Optional[date] = None,
) -> Tuple[float, float]:
    """
    Return (recent_8w_median_weekly_miles, recent_16w_p90_weekly_miles).
    """
    if now is None:
        now = date.today()

    weekly_miles = compute_weekly_mileage(activities)
    if not weekly_miles:
        return 0.0, 0.0

    eight_weeks_ago = now - timedelta(days=56)
    sixteen_weeks_ago = now - timedelta(days=112)
    weekly_8w = [m for ws, m in weekly_miles.items() if ws >= eight_weeks_ago]
    weekly_16w = [m for ws, m in weekly_miles.items() if ws >= sixteen_weeks_ago]

    def _median(values: List[float]) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        n = len(s)
        mid = n // 2
        if n % 2 == 0:
            return (s[mid - 1] + s[mid]) / 2.0
        return s[mid]

    def _percentile(values: List[float], pct: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        if len(s) == 1:
            return s[0]
        idx = int(round((len(s) - 1) * pct))
        idx = max(0, min(len(s) - 1, idx))
        return s[idx]

    return _median(weekly_8w), _percentile(weekly_16w, 0.90)

