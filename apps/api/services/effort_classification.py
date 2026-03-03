"""
N=1 Effort Classification

Single shared function for all effort classification across the system.
Replaces every max_hr-gated code path with percentile-based classification
derived from the athlete's own HR distribution.

Three tiers:
  Tier 1 (primary):   HR percentile from athlete's own distribution
  Tier 2 (secondary): HRR with observed peak (earned after data threshold)
  Tier 3 (tertiary):  Workout type + RPE (sparse HR data)

Design reference: docs/specs/EFFORT_CLASSIFICATION_SPEC.md
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Activity, Athlete, DailyCheckin

logger = logging.getLogger(__name__)

TIER_1_HARD_PERCENTILE = 80
TIER_1_EASY_PERCENTILE = 40

TIER_2_MIN_ACTIVITIES = 20
TIER_2_MIN_HARD_SESSIONS = 3
TIER_2_HRR_HARD = 0.75
TIER_2_HRR_EASY = 0.45

TIER_3_MAX_HR_ACTIVITIES = 10

HARD_WORKOUT_TYPES = frozenset({"race", "interval", "tempo_run", "threshold_run"})
EASY_WORKOUT_TYPES = frozenset({"easy_run", "recovery"})

_TIER_TO_RPE = {"hard": 3, "moderate": 2, "easy": 1}
_RPE_TO_TIER = {v: k for k, v in _TIER_TO_RPE.items()}


def classify_effort(
    activity: Activity,
    athlete_id: str,
    db: Session,
) -> str:
    """
    Returns "hard", "moderate", or "easy".

    "The statement 'this session was in the top 20% of effort'
     is always true from the data that exists."

    Tier 1: HR percentile from athlete's own distribution.
    Tier 2: HRR with observed peak (when eligible).
    Tier 3: Workout type + RPE (when HR data sparse).
    """
    thresholds = get_effort_thresholds(athlete_id, db)
    tier = thresholds["tier"]
    avg_hr = activity.avg_hr

    if tier == "percentile" and avg_hr:
        result = _classify_tier1(avg_hr, thresholds)
        logger.debug(
            "effort_classification tier=percentile athlete=%s activity=%s result=%s",
            athlete_id, activity.id, result,
        )
        return result

    if tier == "hrr" and avg_hr:
        result = _classify_tier2(avg_hr, thresholds)
        logger.debug(
            "effort_classification tier=hrr athlete=%s activity=%s result=%s",
            athlete_id, activity.id, result,
        )
        return result

    result = _classify_tier3(activity, athlete_id, db)
    logger.debug(
        "effort_classification tier=workout_type athlete=%s activity=%s result=%s",
        athlete_id, activity.id, result,
    )
    return result


def get_effort_thresholds(
    athlete_id: str,
    db: Session,
) -> dict:
    """
    Returns the athlete's current effort thresholds:
    - p80_hr, p40_hr (Tier 1 boundaries)
    - tier: which classification tier is active
    - observed_peak_hr (if available)
    - resting_hr (if available)
    - activity_count: how many activities with HR data
    - hard_count: how many classified as hard by Tier 1

    Cached in Redis, recalculated when new activities arrive.
    """
    try:
        from core.cache import get_redis_client
        redis = get_redis_client()
        if redis:
            key = f"effort_thresholds:{athlete_id}"
            cached = redis.get(key)
            if cached:
                return json.loads(cached)
    except Exception:
        pass

    result = _compute_thresholds(athlete_id, db)

    try:
        from core.cache import get_redis_client
        redis = get_redis_client()
        if redis:
            key = f"effort_thresholds:{athlete_id}"
            redis.setex(key, 3600, json.dumps(result))
    except Exception:
        pass

    return result


def classify_effort_bulk(
    activities: List[Activity],
    athlete_id: str,
    db: Session,
) -> Dict[UUID, str]:
    """
    Classify multiple activities at once (for aggregation functions).
    Computes thresholds once, applies to all.
    """
    thresholds = get_effort_thresholds(athlete_id, db)
    tier = thresholds["tier"]
    result: Dict[UUID, str] = {}

    for act in activities:
        avg_hr = act.avg_hr
        if tier == "percentile" and avg_hr:
            result[act.id] = _classify_tier1(avg_hr, thresholds)
        elif tier == "hrr" and avg_hr:
            result[act.id] = _classify_tier2(avg_hr, thresholds)
        else:
            result[act.id] = _classify_tier3(act, athlete_id, db)

    return result


def log_rpe_disagreement(
    athlete_id: str,
    activity_id,
    hr_tier: str,
    rpe_value: int,
    db: Session,
) -> None:
    """
    When HR classification and RPE disagree by more than one tier,
    log the event for future correlation input.
    """
    rpe_tier = _rpe_to_tier(rpe_value)
    hr_rank = _TIER_TO_RPE.get(hr_tier, 2)
    rpe_rank = _TIER_TO_RPE.get(rpe_tier, 2)
    gap = abs(hr_rank - rpe_rank)

    if gap <= 1:
        return

    logger.info(
        "rpe_disagreement athlete=%s activity=%s hr_tier=%s rpe=%d rpe_tier=%s gap=%d",
        athlete_id, activity_id, hr_tier, rpe_value, rpe_tier, gap,
    )


def invalidate_effort_cache(athlete_id: str) -> None:
    """Call after new activities sync to bust the cached thresholds."""
    try:
        from core.cache import get_redis_client
        redis = get_redis_client()
        if redis:
            redis.delete(f"effort_thresholds:{athlete_id}")
    except Exception:
        pass


# ─── internals ────────────────────────────────────────────────────────


def _compute_thresholds(athlete_id: str, db: Session) -> dict:
    """Build threshold dict from the athlete's activity history."""
    hr_values = (
        db.query(Activity.avg_hr)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.avg_hr.isnot(None),
        )
        .all()
    )
    hrs = sorted([int(r[0]) for r in hr_values])
    activity_count = len(hrs)

    p80_hr: Optional[float] = None
    p40_hr: Optional[float] = None

    if activity_count >= TIER_3_MAX_HR_ACTIVITIES:
        p80_hr = _percentile(hrs, TIER_1_HARD_PERCENTILE)
        p40_hr = _percentile(hrs, TIER_1_EASY_PERCENTILE)

    # Observed peak HR from max(Activity.max_hr)
    peak_row = (
        db.query(func.max(Activity.max_hr))
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.max_hr.isnot(None),
        )
        .scalar()
    )
    observed_peak_hr = int(peak_row) if peak_row else None

    # Resting HR — prefer GarminDay (most recent), fall back to DailyCheckin
    resting_hr = _get_resting_hr(athlete_id, db)

    # Count hard sessions by Tier 1
    hard_count = 0
    if p80_hr is not None:
        hard_count = sum(1 for h in hrs if h >= p80_hr)

    # Determine active tier
    tier = _select_tier(activity_count, hard_count, observed_peak_hr, resting_hr)

    return {
        "p80_hr": p80_hr,
        "p40_hr": p40_hr,
        "tier": tier,
        "observed_peak_hr": observed_peak_hr,
        "resting_hr": resting_hr,
        "activity_count": activity_count,
        "hard_count": hard_count,
    }


def _select_tier(
    activity_count: int,
    hard_count: int,
    observed_peak_hr: Optional[int],
    resting_hr: Optional[int],
) -> str:
    if activity_count < TIER_3_MAX_HR_ACTIVITIES:
        return "workout_type"
    if (
        activity_count >= TIER_2_MIN_ACTIVITIES
        and hard_count >= TIER_2_MIN_HARD_SESSIONS
        and observed_peak_hr is not None
        and resting_hr is not None
    ):
        return "hrr"
    return "percentile"


def _classify_tier1(avg_hr: float, thresholds: dict) -> str:
    p80 = thresholds["p80_hr"]
    p40 = thresholds["p40_hr"]
    if p80 is not None and avg_hr >= p80:
        return "hard"
    if p40 is not None and avg_hr < p40:
        return "easy"
    return "moderate"


def _classify_tier2(avg_hr: float, thresholds: dict) -> str:
    resting = thresholds["resting_hr"]
    peak = thresholds["observed_peak_hr"]
    if not resting or not peak or peak <= resting:
        return _classify_tier1(avg_hr, thresholds)
    hrr = (avg_hr - resting) / (peak - resting)
    if hrr >= TIER_2_HRR_HARD:
        return "hard"
    if hrr < TIER_2_HRR_EASY:
        return "easy"
    return "moderate"


def _classify_tier3(activity: Activity, athlete_id: str, db: Session) -> str:
    wt = getattr(activity, "workout_type", None)
    if wt and wt.lower() in HARD_WORKOUT_TYPES:
        return "hard"
    if wt and wt.lower() in EASY_WORKOUT_TYPES:
        return "easy"

    # Check RPE from same-day check-in
    if activity.start_time:
        checkin = (
            db.query(DailyCheckin)
            .filter(
                DailyCheckin.athlete_id == athlete_id,
                DailyCheckin.date == activity.start_time.date(),
            )
            .first()
        )
        if checkin and checkin.rpe_1_10 is not None:
            if checkin.rpe_1_10 >= 7:
                return "hard"
            if checkin.rpe_1_10 <= 4:
                return "easy"

    return "moderate"


def _rpe_to_tier(rpe: int) -> str:
    if rpe >= 7:
        return "hard"
    if rpe <= 4:
        return "easy"
    return "moderate"


def _percentile(sorted_values: List[int], pct: int) -> float:
    """Compute the p-th percentile from a sorted list."""
    n = len(sorted_values)
    if n == 0:
        return 0
    k = (pct / 100) * (n - 1)
    f = int(k)
    c = f + 1 if f + 1 < n else f
    d = k - f
    return sorted_values[f] + d * (sorted_values[c] - sorted_values[f])


def _get_resting_hr(athlete_id: str, db: Session) -> Optional[int]:
    """Most recent resting HR from GarminDay or DailyCheckin."""
    try:
        from models import GarminDay
        garmin_rhr = (
            db.query(GarminDay.resting_hr)
            .filter(
                GarminDay.athlete_id == athlete_id,
                GarminDay.resting_hr.isnot(None),
            )
            .order_by(GarminDay.calendar_date.desc())
            .limit(1)
            .scalar()
        )
        if garmin_rhr:
            return int(garmin_rhr)
    except Exception:
        pass

    checkin_rhr = (
        db.query(DailyCheckin.resting_hr)
        .filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.resting_hr.isnot(None),
        )
        .order_by(DailyCheckin.date.desc())
        .limit(1)
        .scalar()
    )
    if checkin_rhr:
        return int(checkin_rhr)

    # Profile fallback
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete and athlete.resting_hr:
        return int(athlete.resting_hr)

    return None
