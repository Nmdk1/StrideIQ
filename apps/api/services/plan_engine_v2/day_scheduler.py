"""
Day Scheduler — assign workout types to days of the week.

Respects athlete's preferred days from FitnessBank:
  - typical_long_run_day
  - typical_quality_day
  - typical_rest_days

Phase-aware: different distributions for General vs Specific.
Fingerprint-aware: quality spacing from FingerprintParams.

The scheduler assigns SLOTS, not workouts.  The workout library
fills each slot with a concrete structure.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from services.fitness_bank import ExperienceLevel, FitnessBank
from services.plan_framework.fingerprint_bridge import FingerprintParams

logger = logging.getLogger(__name__)


# Slot types that the scheduler assigns
SLOT_REST = "rest"
SLOT_EASY = "easy"
SLOT_EASY_SHORT = "easy_short"
SLOT_EASY_STRIDES = "easy_strides"
SLOT_QUALITY_PRIMARY = "quality_primary"
SLOT_QUALITY_SECONDARY = "quality_secondary"
SLOT_LONG_RUN = "long_run"
SLOT_MEDIUM_LONG = "medium_long"
SLOT_REGENERATIVE = "regenerative"


def schedule_week(
    bank: FitnessBank,
    fingerprint: FingerprintParams,
    phase_name: str,
    quality_density: int,
    is_cutback: bool,
    week_in_phase: int,
    long_run_is_workout: bool = False,
    weekly_target_km: float = 0.0,
) -> List[dict]:
    """Assign workout slots to the 7 days of the week.

    Structure A/B alternation (from Training Philosophy):
      A = Intensity week + easy long run (long_run_is_workout=False)
      B = Easy week + workout long run (long_run_is_workout=True)
    Never three quality days.

    Returns list of 7 dicts (Mon=0 .. Sun=6):
      {"day": 0, "slot": "rest", "role": "primary_rest"}
    """
    if long_run_is_workout:
        quality_density = min(quality_density, 1)
    long_day = bank.typical_long_run_day if bank.typical_long_run_day is not None else 5
    quality_day = bank.typical_quality_day if bank.typical_quality_day is not None else 2
    rest_days = bank.typical_rest_days if bank.typical_rest_days else [0]
    primary_rest = rest_days[0] if rest_days else 0

    # Build the 7-day skeleton
    days = [{"day": d, "slot": SLOT_EASY, "role": "filler"} for d in range(7)]

    # 1. Rest day(s)
    days[primary_rest] = {"day": primary_rest, "slot": SLOT_REST, "role": "primary_rest"}

    if is_cutback or phase_name == "taper":
        # Extra rest on cutback/taper weeks
        second_rest = (primary_rest + 3) % 7
        if second_rest != long_day and second_rest != quality_day:
            days[second_rest] = {"day": second_rest, "slot": SLOT_REST, "role": "cutback_rest"}

    # 2. Long run
    days[long_day] = {"day": long_day, "slot": SLOT_LONG_RUN, "role": "long_run"}

    # 3. Quality sessions
    if is_cutback:
        # Cutback: strides only, no real quality
        days[quality_day] = {"day": quality_day, "slot": SLOT_EASY_STRIDES, "role": "cutback_strides"}
    elif quality_density >= 1:
        days[quality_day] = {"day": quality_day, "slot": SLOT_QUALITY_PRIMARY, "role": "quality_1"}

        if quality_density >= 2:
            # Second quality session: place with appropriate spacing
            secondary = _find_secondary_quality_day(
                quality_day, long_day, primary_rest,
                fingerprint.quality_spacing_min_hours,
            )
            if secondary is not None:
                days[secondary] = {"day": secondary, "slot": SLOT_QUALITY_SECONDARY, "role": "quality_2"}

    # 4. Regenerative day (specific phase, between big sessions)
    if phase_name in ("specific", "supportive") and not is_cutback:
        regen_day = _find_regenerative_day(quality_day, long_day, primary_rest, days)
        if regen_day is not None:
            days[regen_day] = {"day": regen_day, "slot": SLOT_REGENERATIVE, "role": "regenerative"}

    # 5. Medium-long run (gated by volume and experience)
    _MI_TO_KM = 1.60934
    _ML_VOLUME_FLOOR_KM = 40.0 * _MI_TO_KM  # ~65 km, roughly 40 mpw
    if (
        not is_cutback
        and phase_name != "taper"
        and weekly_target_km >= _ML_VOLUME_FLOOR_KM
        and bank.experience_level != ExperienceLevel.BEGINNER
    ):
        ml_day = _find_medium_long_day(long_day, quality_day, primary_rest, days)
        if ml_day is not None:
            days[ml_day] = {"day": ml_day, "slot": SLOT_MEDIUM_LONG, "role": "medium_long"}

    # 6. Pre-long-run day: short easy (fresh legs)
    pre_long = (long_day - 1) % 7
    if days[pre_long]["slot"] == SLOT_EASY:
        days[pre_long] = {"day": pre_long, "slot": SLOT_EASY_SHORT, "role": "pre_long"}

    # 7. Strides on one easy day (all phases)
    if not is_cutback:
        strides_day = _find_strides_day(days, quality_day, long_day)
        if strides_day is not None:
            days[strides_day] = {"day": strides_day, "slot": SLOT_EASY_STRIDES, "role": "strides"}

    return days


def _find_secondary_quality_day(
    primary_day: int,
    long_day: int,
    rest_day: int,
    min_spacing_hours: int,
) -> Optional[int]:
    """Find the best day for a second quality session.

    HARD CONSTRAINT: must be >= min_spacing_hours from primary quality
    AND from long run. 48h = 2 days, 72h = 3 days.
    If no valid day exists under the hard constraint, return None
    (the athlete gets one quality session, not two placed too close).
    """
    min_gap_days = max(2, min_spacing_hours // 24)
    candidates = []

    for d in range(7):
        if d == primary_day or d == long_day or d == rest_day:
            continue
        gap_from_primary = min(abs(d - primary_day), 7 - abs(d - primary_day))
        gap_from_long = min(abs(d - long_day), 7 - abs(d - long_day))
        if gap_from_primary >= min_gap_days and gap_from_long >= min_gap_days:
            candidates.append((d, gap_from_primary + gap_from_long))

    if not candidates:
        # Hard constraint not satisfiable — skip second quality
        logger.info(
            "Cannot place secondary quality: no day >= %dh from primary (day %d) "
            "and long run (day %d). Dropping to 1 quality session.",
            min_spacing_hours, primary_day, long_day,
        )
        return None

    candidates.sort(key=lambda x: -x[1])
    return candidates[0][0]


def _find_regenerative_day(
    quality_day: int,
    long_day: int,
    rest_day: int,
    days: List[dict],
    min_gap: int = 2,
) -> Optional[int]:
    """Find a day for a regenerative workout (7/10 effort).

    Must be at least min_gap days from both quality and long run days
    to respect quality spacing constraints.
    """
    hard_days = {quality_day, long_day}

    def _is_valid(candidate: int) -> bool:
        if days[candidate]["slot"] != SLOT_EASY or candidate == rest_day:
            return False
        for hd in hard_days:
            gap = min(abs(candidate - hd), 7 - abs(candidate - hd))
            if gap < min_gap:
                return False
        return True

    for offset in (2, 3, 4):
        candidate = (quality_day + offset) % 7
        if _is_valid(candidate):
            return candidate

    for offset in (2, 3, 4):
        candidate = (long_day + offset) % 7
        if _is_valid(candidate):
            return candidate

    return None


def _find_medium_long_day(
    long_day: int,
    quality_day: int,
    rest_day: int,
    days: List[dict],
) -> Optional[int]:
    """Find a mid-week day for a medium-long run.

    Scores all eligible days (currently SLOT_EASY, not rest) by:
      1. Gap from long run (>= 2 required — MLR day before long is worse than no MLR)
      2. Gap from quality (>= 2 preferred, >= 1 acceptable fallback;
         MLR is aerobic volume, not intensity — Pfitzinger frequently
         places MLR adjacent to quality)

    Returns the day with the best combined spacing, or None if no
    valid placement exists.
    """
    candidates: list = []

    for d in range(7):
        if days[d]["slot"] != SLOT_EASY or d == rest_day:
            continue

        gap_from_long = min(abs(d - long_day), 7 - abs(d - long_day))
        gap_from_quality = min(abs(d - quality_day), 7 - abs(d - quality_day))

        if gap_from_long < 2:
            continue
        if gap_from_quality < 1:
            continue

        # Score: prefer max separation from long run, then from quality
        quality_bonus = 1 if gap_from_quality >= 2 else 0
        score = gap_from_long + gap_from_quality + quality_bonus
        candidates.append((d, score, gap_from_quality))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[1], -x[2]))
    return candidates[0][0]


def _find_strides_day(
    days: List[dict],
    quality_day: int,
    long_day: int,
) -> Optional[int]:
    """Find a day for easy + strides. Prefer day after quality."""
    # Day after quality (activation for recovery)
    candidate = (quality_day + 1) % 7
    if days[candidate]["slot"] == SLOT_EASY:
        return candidate

    # Any remaining easy day
    for d in days:
        if d["slot"] == SLOT_EASY and d["role"] == "filler":
            return d["day"]

    return None
