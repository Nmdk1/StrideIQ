"""
Volume progression — weekly mileage targets, cutback weeks, distance ranges.

Rules:
- Start from FitnessBank.current_weekly_miles
- Build toward peak by the supportive/specific transition
- Cutback every N weeks (from FingerprintParams.cutback_frequency)
- Specific phase: volume is a RANGE, not a target
- Distance ranges on easy days: width scales with volume band

All units internal to this module are km.
"""

from __future__ import annotations

import logging
import math
from typing import List, Optional, Tuple

from services.plan_framework.load_context import LoadContext

from services.fitness_bank import ExperienceLevel, FitnessBank
from services.plan_framework.fingerprint_bridge import FingerprintParams

from .models import PhaseStructure

logger = logging.getLogger(__name__)

MI_TO_KM = 1.60934

# Max weekly volume increase per week (km)
MAX_WEEKLY_INCREASE_KM = 8.0  # ~5 mi/wk
MAX_WEEKLY_INCREASE_PCT = 0.08  # 8% per week


def compute_volume_targets(
    bank: FitnessBank,
    fingerprint: FingerprintParams,
    phase_structure: PhaseStructure,
    load_ctx: Optional[LoadContext] = None,
    desired_peak_weekly_miles: Optional[float] = None,
) -> List[dict]:
    """Compute weekly volume targets for every week of the plan.

    Load context integration: if observed_recent_weekly_miles is available,
    use it to seed starting volume instead of FitnessBank alone (which may
    be stale or derived from historical peaks).

    When desired_peak_weekly_miles is provided by the athlete, it overrides
    the bank-derived sustainable peak. The athlete knows where they're going
    (e.g. 75mpw marathon build while currently at 62mpw post-injury).

    Returns a list of dicts, one per week:
      {
        "week": 1,
        "phase": "general",
        "target_km": 72.0,
        "range_km": (65.0, 80.0),
        "is_cutback": False,
      }
    """
    current_km = bank.current_weekly_miles * MI_TO_KM

    if load_ctx and load_ctx.observed_recent_weekly_miles is not None:
        observed_km = load_ctx.observed_recent_weekly_miles * MI_TO_KM
        current_km = min(current_km, observed_km)

    if desired_peak_weekly_miles is not None:
        peak_km = desired_peak_weekly_miles * MI_TO_KM
    else:
        peak_km = bank.sustainable_peak_weekly * MI_TO_KM
    cutback_freq = fingerprint.cutback_frequency

    peak_km = max(peak_km, current_km * 1.05)
    peak_km = min(peak_km, bank.peak_weekly_miles * MI_TO_KM * 1.1)

    weeks: List[dict] = []
    week_num = 0

    for phase in phase_structure.phases:
        for w in range(phase.weeks):
            week_num += 1
            phase_progress = w / max(1, phase.weeks - 1) if phase.weeks > 1 else 1.0
            overall_progress = week_num / max(1, phase_structure.total_weeks)

            is_cutback = _is_cutback_week(week_num, cutback_freq, phase.name)
            is_final_phase = phase.name in ("specific", "taper")

            target = _compute_week_target(
                current_km=current_km,
                peak_km=peak_km,
                week_num=week_num,
                total_weeks=phase_structure.total_weeks,
                phase_name=phase.name,
                phase_progress=phase_progress,
                overall_progress=overall_progress,
                is_cutback=is_cutback,
                experience=bank.experience_level,
            )

            # Enforce max increase from previous week
            if weeks:
                prev_target = weeks[-1]["target_km"]
                if not is_cutback and not weeks[-1]["is_cutback"]:
                    max_abs = prev_target + MAX_WEEKLY_INCREASE_KM
                    max_pct = prev_target * (1 + MAX_WEEKLY_INCREASE_PCT)
                    target = min(target, max_abs, max_pct)

            # Range width depends on phase
            range_km = _compute_range(target, phase.name, bank.experience_level)

            weeks.append({
                "week": week_num,
                "phase": phase.name,
                "target_km": round(target, 1),
                "range_km": (round(range_km[0], 1), round(range_km[1], 1)),
                "is_cutback": is_cutback,
            })

    return weeks


def _is_cutback_week(
    week_num: int,
    cutback_freq: int,
    phase_name: str,
) -> bool:
    """Determine if this week should be a cutback."""
    if phase_name == "taper":
        return False  # taper handles its own reduction
    if week_num <= 1:
        return False
    return (week_num % cutback_freq) == 0


def _compute_week_target(
    *,
    current_km: float,
    peak_km: float,
    week_num: int,
    total_weeks: int,
    phase_name: str,
    phase_progress: float,
    overall_progress: float,
    is_cutback: bool,
    experience: ExperienceLevel,
) -> float:
    """Compute a single week's volume target in km."""

    if phase_name == "taper":
        # Taper: progressive reduction from peak
        taper_pct = 0.80 - (phase_progress * 0.25)  # 80% → 55% of peak
        return peak_km * taper_pct

    if is_cutback:
        # Cutback: 75-85% of what the non-cutback target would be
        cutback_pct = 0.80
        base = _build_curve(current_km, peak_km, overall_progress)
        return base * cutback_pct

    if phase_name == "general":
        return _build_curve(current_km, peak_km * 0.92, overall_progress)

    if phase_name == "supportive":
        return _build_curve(current_km, peak_km, overall_progress)

    if phase_name == "specific":
        # Specific phase: near peak, slight oscillation
        return peak_km * (0.93 + 0.07 * math.sin(phase_progress * math.pi))

    return _build_curve(current_km, peak_km, overall_progress)


def _build_curve(start: float, end: float, progress: float) -> float:
    """Smooth volume build curve (square root for front-loaded adaptation)."""
    return start + (end - start) * math.sqrt(min(1.0, progress))


def _compute_range(
    target_km: float,
    phase_name: str,
    experience: ExperienceLevel,
) -> Tuple[float, float]:
    """Compute (min, max) range for a weekly volume target."""
    if phase_name == "specific":
        return (target_km * 0.85, target_km * 1.05)
    if phase_name == "taper":
        return (target_km * 0.90, target_km * 1.05)
    return (target_km * 0.92, target_km * 1.05)


# ── Day-Level Distance Ranges ───────────────────────────────────────

def easy_run_range_km(
    weekly_target_km: float,
    day_role: str,
) -> Tuple[float, float]:
    """Compute distance range for an easy day.

    day_role: "easy", "easy_short", "easy_recovery", "easy_mod"
    """
    if weekly_target_km < 50:  # < ~30 mi/wk
        band = "low"
    elif weekly_target_km < 100:  # 30-60 mi/wk
        band = "mid"
    else:
        band = "high"

    ranges = {
        "low":  {"easy": (5.0, 8.0),  "easy_short": (3.0, 5.0), "easy_recovery": (3.0, 5.0), "easy_mod": (5.0, 8.0)},
        "mid":  {"easy": (8.0, 13.0), "easy_short": (5.0, 8.0), "easy_recovery": (5.0, 8.0), "easy_mod": (8.0, 13.0)},
        "high": {"easy": (13.0, 19.0), "easy_short": (8.0, 13.0), "easy_recovery": (8.0, 11.0), "easy_mod": (10.0, 16.0)},
    }

    return ranges[band].get(day_role, ranges[band]["easy"])


# ── Race Readiness and Long Run Staircase ────────────────────────────
#
# The long run peak is determined by TWO inputs:
#   1. Race floor: the minimum peak long run needed for race readiness
#   2. Athlete capacity: ~28% of sustainable peak weekly miles (N=1)
# Use the HIGHER of the two. No race-distance cap.

_RACE_FLOOR_MI = {
    "5K": 5, "10K": 8, "half_marathon": 12, "marathon": 20,
    "50K": 22, "50_mile": 26, "100K": 28, "100_mile": 30,
}

_TAPER_WEEKS = {
    "5K": 1, "10K": 1, "half_marathon": 1, "marathon": 2,
    "50K": 1, "50_mile": 2, "100K": 2, "100_mile": 2,
}

_BUFFER_DAYS = {
    "5K": 5, "10K": 5, "half_marathon": 7, "marathon": 10,
    "50K": 10, "50_mile": 10, "100K": 10, "100_mile": 10,
}


def _lr_capacity_pct(experience: ExperienceLevel) -> float:
    """LR-to-weekly-volume ratio scaled by experience.

    Experienced runners can safely sustain a higher fraction of weekly
    volume in a single long run (better musculoskeletal durability).
    """
    if experience in (ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE):
        return 0.33
    if experience == ExperienceLevel.INTERMEDIATE:
        return 0.30
    return 0.28


_EVENT_LR_CAP_MI = {
    "5K": 18, "10K": 18, "half_marathon": 18, "marathon": 22,
}


def compute_peak_long_run_mi(
    bank: FitnessBank,
    goal_event: Optional[str],
    desired_peak_weekly_miles: Optional[float] = None,
) -> int:
    """Peak long run from volume capacity, capped by event ceiling.

    Two ceilings applied AFTER volume-capacity calculation:
      - Marathon: 22mi (volume capacity may support more, but
        biomechanical cost past 22 outweighs aerobic return)
      - Non-ultra, non-marathon: 18mi (LR serves aerobic support,
        not race-specific glycogen depletion)
      - Ultra: no distance cap (volume floor gate handles safety)

    A 75mpw 10K runner gets capped at 18 even though volume supports
    more — their 18-miler is well within absorption range, which is ideal.
    """
    race_floor = _RACE_FLOOR_MI.get(goal_event or "", 10)
    peak_vol = desired_peak_weekly_miles or bank.peak_weekly_miles
    lr_pct = _lr_capacity_pct(bank.experience_level)
    capacity = round(peak_vol * lr_pct)

    vol_ceiling = round(bank.sustainable_peak_weekly * 0.85)
    effective_floor = min(race_floor, vol_ceiling)

    peak = max(effective_floor, capacity)

    start = compute_start_long_run_mi(bank)
    increment = _long_run_increment(bank.experience_level)
    min_peak = start + increment * 2
    peak = max(peak, min_peak)

    event_cap = _EVENT_LR_CAP_MI.get(goal_event or "", None)
    if event_cap is not None:
        peak = min(peak, event_cap)

    return peak


def compute_start_long_run_mi(
    bank: FitnessBank,
    l30_max_easy_long_mi: Optional[float] = None,
) -> int:
    """Starting long run distance (whole miles) from current fitness.

    If the athlete has PROVEN capability significantly higher than
    their recent running (e.g. Brian: runs 35mpw but completed a
    20-mile race), we start at ~70% of their proven peak rather
    than their recent L30. The history proves they can handle it.
    """
    start = bank.current_long_run_miles
    if l30_max_easy_long_mi is not None and l30_max_easy_long_mi > 0:
        start = min(start, l30_max_easy_long_mi)

    if bank.peak_long_run_miles > start * 1.5:
        proven_floor = round(bank.peak_long_run_miles * 0.70)
        start = max(start, proven_floor)

    return max(round(start), 3)


def _long_run_increment(experience: ExperienceLevel) -> int:
    """Experienced/elite athletes build +2mi/week, others +1mi."""
    if experience in (ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE):
        return 2
    return 1


def taper_weeks_for_event(goal_event: Optional[str]) -> int:
    return _TAPER_WEEKS.get(goal_event or "", 2)


_RACE_DISTANCE_MI = {
    "50K": 31, "50_mile": 50, "100K": 62, "100_mile": 100,
}


def _ultra_volume_floor(goal_event: str) -> Optional[int]:
    """Minimum sustainable weekly miles to attempt an ultra distance.

    Derived from race distance: ~60% of race miles as minimum weekly
    base. Returns None for non-ultra events.
    """
    race_mi = _RACE_DISTANCE_MI.get(goal_event)
    if race_mi is None:
        return None
    return round(race_mi * 0.6)


def readiness_gate(
    start_mi: int,
    peak_mi: int,
    total_weeks: int,
    goal_event: str,
    cutback_freq: int,
    experience: ExperienceLevel,
    bank: Optional[FitnessBank] = None,
) -> Optional[str]:
    """Return None if the plan is buildable, or a refusal message.

    Checks two things:
    1. Ultra volume floor — is the athlete's base sufficient for this distance?
    2. Staircase reachability — can the LR build to peak_mi in time?
    """
    if bank is not None:
        vol_floor = _ultra_volume_floor(goal_event)
        if vol_floor is not None and bank.sustainable_peak_weekly < vol_floor:
            gap = vol_floor - bank.sustainable_peak_weekly
            months_to_build = max(3, round(gap / 4))
            return (
                f"Your current volume base ({bank.sustainable_peak_weekly:.0f}mpw "
                f"sustainable) is below the minimum for {goal_event} "
                f"({vol_floor}mpw). You need approximately {months_to_build} "
                f"months of progressive base building before starting a "
                f"{goal_event} plan. Start with a Build-Volume block to "
                f"safely raise your weekly mileage first."
            )

    if peak_mi <= start_mi:
        return None

    staircase = compute_long_run_staircase(
        start_mi, peak_mi, total_weeks, goal_event,
        cutback_freq, experience, bank=bank,
    )
    tw = taper_weeks_for_event(goal_event)
    training_weeks = total_weeks - tw
    if training_weeks < 1:
        return (
            f"Not enough time: {total_weeks} weeks total, "
            f"{tw} needed for taper."
        )

    actual_peak = max(staircase[:training_weeks]) if staircase else 0

    if actual_peak < peak_mi:
        increment = _long_run_increment(experience)
        increments_per_cycle = max(1, cutback_freq - 2)
        needed_increments = math.ceil((peak_mi - start_mi) / increment)
        needed_cycles = math.ceil(needed_increments / increments_per_cycle)
        needed_total = needed_cycles * cutback_freq + tw
        return (
            f"Cannot safely build from {start_mi}mi to {peak_mi}mi "
            f"long run in {total_weeks} weeks for {goal_event} "
            f"(staircase peaks at {actual_peak}mi). "
            f"You need approximately {needed_total} weeks. "
            f"Options: extend your timeline, or start a Build-Volume "
            f"block to raise your base first."
        )

    return None


def _cutback_pct(bank: Optional[FitnessBank]) -> float:
    """Cutback depth: 60-65% of cycle peak for everyone.

    Cutbacks exist for mental AND physical deload. A 20mi→16mi "cutback"
    doesn't let you reset — you still plan routes, carry nutrition, commit
    a whole morning. A 20mi→13mi cutback is a genuinely short long run
    that lets you come back hungry for the next hard cycle.
    """
    return 0.63


def compute_long_run_staircase(
    start_mi: int,
    peak_mi: int,
    total_weeks: int,
    goal_event: Optional[str],
    cutback_freq: int,
    experience: ExperienceLevel,
    bank: Optional[FitnessBank] = None,
) -> List[int]:
    """Pre-compute the long run distance (whole miles) for every week.

    Staircase:
      Build weeks: +increment (1 or 2mi depending on experience)
      Cutback weeks: 60-65% of cycle peak
      Post-cutback: resume at pre-cutback level (don't add increment)
      At peak: oscillate distance in a 3-position wave. Wave depth is
        proportional to peak distance (~15%, min 2mi). This creates
        purposeful variation — shorter weeks give the workout library
        room for quality overlays (progression finishes, MP segments,
        threshold finishes) while full-peak weeks serve pure aerobic
        endurance. Distance and quality are inverse levers.
      Taper: event-aware progressive reduction
    All distances are whole miles.
    """
    increment = _long_run_increment(experience)
    tw = taper_weeks_for_event(goal_event)
    training_weeks = max(1, total_weeks - tw)
    cb_pct = _cutback_pct(bank)

    wave_depth = max(2, round(peak_mi * 0.15))

    if start_mi >= peak_mi:
        oscillation_floor = max(round(peak_mi * 0.78), 3)
        cutback_floor = max(round(peak_mi * 0.65), 3)
    else:
        oscillation_floor = start_mi
        cutback_floor = start_mi

    staircase: List[int] = []
    current = start_mi
    pre_cutback = start_mi
    prev_was_cutback = False
    peak_visits = 0

    if goal_event in ("5K", "10K"):
        taper_base, taper_drop = 0.55, 0.10
    elif goal_event == "half_marathon":
        taper_base, taper_drop = 0.60, 0.10
    else:
        taper_base, taper_drop = 0.65, 0.15

    for w in range(1, total_weeks + 1):
        if w > training_weeks:
            taper_pos = (w - training_weeks) / max(1, tw)
            taper_pct = taper_base - taper_drop * taper_pos
            taper_mi = max(round(peak_mi * taper_pct), 3)
            staircase.append(taper_mi)
            continue

        is_cutback = w > 1 and (w % cutback_freq) == 0

        if is_cutback:
            cutback_mi = max(round(pre_cutback * cb_pct), cutback_floor)
            staircase.append(cutback_mi)
            prev_was_cutback = True
        elif w == 1:
            staircase.append(start_mi)
            current = start_mi
            pre_cutback = start_mi
            prev_was_cutback = False
        else:
            if prev_was_cutback:
                current = min(pre_cutback + increment, peak_mi)
                prev_was_cutback = False
            else:
                current = min(current + increment, peak_mi)

            if current >= peak_mi:
                peak_visits += 1
                cycle_pos = (peak_visits - 1) % 3
                if cycle_pos == 0:
                    current = peak_mi
                elif cycle_pos == 1:
                    current = max(peak_mi - max(1, wave_depth - 1),
                                  oscillation_floor)
                else:
                    current = max(peak_mi - wave_depth, oscillation_floor)

            staircase.append(current)
            pre_cutback = current

    return staircase


def long_run_range_for_week(
    staircase: List[int],
    week_num: int,
) -> Tuple[float, float]:
    """Return (lo_km, hi_km) for a given week from the staircase.

    The target is a whole-mile value; range is ±1mi for flexibility.
    """
    idx = week_num - 1
    if idx < 0 or idx >= len(staircase):
        return (8.0 * MI_TO_KM, 13.0 * MI_TO_KM)

    target_mi = staircase[idx]
    lo_mi = max(target_mi - 1, 3)
    hi_mi = target_mi + 1

    return (round(lo_mi * MI_TO_KM, 1), round(hi_mi * MI_TO_KM, 1))
