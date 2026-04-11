"""
Workout Library — concrete workout structures for each category.

Every function returns a V2DayPlan with populated segments.
Progression logic (extension across weeks) lives here.

Workout categories from Algorithm Spec §5:
  1. Long easy (75-85% MP)
  2. Long fast / stepwise (90-96% MP)
  3. Marathon/race pace alt-km (100% + 85% float)
  4. Threshold/HM alt-km (105% + 90% float)
  5. Speed support (108-110% MP)
  6. VO2max/5K (115% MP)
  7. Strides/neuromuscular (≥120%)
  8. Progression run (multi-pace)
  9. Regenerative (7/10 difficulty)
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from .effort_mapper import describe_segment, map_effort
from .models import (
    FuelingPlan,
    PaceLadder,
    V2DayPlan,
    WorkoutSegment,
)
from .pace_ladder import format_pace_sec_km, format_pace_range_sec_km
from .segments_builder import (
    _resolve_pace,
    warmup,
    cooldown,
    work_segment,
    float_segment,
    jog_rest,
    stride_segment,
    steady_segment,
    fatigue_resistance_segment,
    uphill_tm_segment,
    hike_segment,
)

logger = logging.getLogger(__name__)

MI_TO_KM = 1.60934


# ── Helpers ──────────────────────────────────────────────────────────

_FUELING_THRESHOLD_MIN = 90

# Module-level context set by build_day_from_slot before calling workout builders
_current_goal_event: Optional[str] = None


def _fueling_for_duration(estimated_min: float, training_age_years: float) -> Optional[FuelingPlan]:
    """Generate fueling plan when the run is long enough to need fuel.

    Any run over 90 minutes needs fueling regardless of goal event —
    glycogen depletion doesn't care what race you're training for.
    A 2-hour 10K-plan long run degrades without carbs just as much as
    a 2-hour marathon-plan long run.
    """
    if estimated_min < _FUELING_THRESHOLD_MIN:
        return None
    if training_age_years < 2:
        return FuelingPlan(60, "Practice fueling: aim for 60 g/hr carbs starting at minute 30.")
    if training_age_years < 5:
        return FuelingPlan(75, "Practice race fueling: target 75 g/hr carbs starting at minute 30.")
    return FuelingPlan(80, "Fuel at your practiced rate (75-90 g/hr). Start early.")


def _est_duration_min(distance_km: float, pace_sec_per_km: float) -> float:
    return (distance_km * pace_sec_per_km) / 60.0


# ── 1. Long Easy ────────────────────────────────────────────────────

def long_easy(
    ladder: PaceLadder,
    distance_range_km: Tuple[float, float],
    is_beginner: bool,
    training_age: float,
    day_of_week: int = 5,
    phase: str = "general",
) -> V2DayPlan:
    """Long run at easy effort. Distance is a range, not a target."""
    target_km = (distance_range_km[0] + distance_range_km[1]) / 2.0
    easy_pace = ladder.easy
    effort = map_effort(80, is_beginner=is_beginner)
    est_min = _est_duration_min(target_km, easy_pace)
    fueling = _fueling_for_duration(est_min, training_age)

    desc = f"Long run — {effort}. Let the run come to you."
    if fueling:
        desc += f"\n{fueling.notes}"

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="long_easy",
        title="Long run",
        description=desc,
        phase=phase,
        distance_range_km=distance_range_km,
        fueling=fueling,
    )


# ── 2. Long Fast Stepwise ───────────────────────────────────────────

def long_fast_stepwise(
    ladder: PaceLadder,
    week_in_phase: int,
    phase_weeks: int,
    distance_range_km: Tuple[float, float],
    is_beginner: bool,
    training_age: float,
    day_of_week: int = 5,
    phase: str = "supportive",
) -> V2DayPlan:
    """Stepwise long run — decreasing pace across blocks (90→92→94→96%)."""
    target_km = (distance_range_km[0] + distance_range_km[1]) / 2.0
    progress = min(1.0, week_in_phase / max(1, phase_weeks - 1))

    # Build stepwise structure based on progression
    if progress < 0.3:
        # Early: simple 2-step
        steps = [(0.55, 90), (0.45, 92)]
    elif progress < 0.6:
        # Mid: 3-step
        steps = [(0.40, 90), (0.30, 92), (0.30, 94)]
    else:
        # Peak: 4-step
        steps = [(0.30, 90), (0.25, 92), (0.25, 94), (0.20, 96)]

    segments: List[WorkoutSegment] = []
    desc_parts = []
    for frac, pct in steps:
        seg_km = round(target_km * frac, 1)
        pace = ladder.pace_for_pct(pct)
        effort = describe_segment(pct, pace, is_beginner=is_beginner)
        segments.append(WorkoutSegment(
            type="work", pace_pct_mp=pct, pace_sec_per_km=pace,
            distance_km=seg_km, description=effort,
        ))
        pace_mi = format_pace_sec_km(pace, "mi")
        desc_parts.append(f"{seg_km:.0f}km at {effort}")

    est_min = _est_duration_min(target_km, ladder.pace_for_pct(92))
    fueling = _fueling_for_duration(est_min, training_age)

    desc = f"Stepwise long run — {' → '.join(desc_parts)}."
    desc += " Each step faster than the last. Don't start too fast."
    if fueling:
        desc += f"\n{fueling.notes}"

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="long_fast_stepwise",
        title=f"Stepwise {target_km:.0f}km",
        description=desc,
        phase=phase,
        segments=segments,
        distance_range_km=distance_range_km,
        fueling=fueling,
    )


# ── 3. Marathon Pace Alt-KM ─────────────────────────────────────────

def marathon_pace_alt_km(
    ladder: PaceLadder,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    training_age: float,
    day_of_week: int = 5,
    phase: str = "specific",
) -> V2DayPlan:
    """Alternating kilometer at marathon pace with float recovery.

    Progression: continuous MP → alt-km with shrinking float.
    Float pace improves: 85% → 88% → 90% MP.
    """
    progress = min(1.0, week_in_phase / max(1, phase_weeks - 1))

    # Scale work/float structure
    if progress < 0.3:
        reps = 4
        work_km = 2.0
        float_km = 1.0
        float_pct = 85
    elif progress < 0.7:
        reps = 5
        work_km = 2.5
        float_km = 1.0
        float_pct = 88
    else:
        reps = 6
        work_km = 3.0
        float_km = 1.0
        float_pct = 90

    segments: List[WorkoutSegment] = [warmup(ladder, is_beginner=is_beginner)]
    for i in range(reps):
        segments.append(work_segment(
            ladder, 100, zone="marathon", distance_km=work_km, is_beginner=is_beginner,
        ))
        if i < reps - 1:
            segments.append(float_segment(
                ladder, float_pct, distance_km=float_km, is_beginner=is_beginner,
            ))
    segments.append(cooldown(ladder, is_beginner=is_beginner))

    total_km = 4 + reps * work_km + (reps - 1) * float_km
    mp_pace_mi = format_pace_sec_km(ladder.marathon, "mi")
    float_pace_mi = format_pace_sec_km(ladder.pace_for_pct(float_pct), "mi")
    est_min = _est_duration_min(total_km, ladder.marathon)
    fueling = _fueling_for_duration(est_min, training_age)

    float_effort = describe_segment(float_pct, ladder.pace_for_pct(float_pct), is_beginner=is_beginner)
    desc = (
        f"{reps}×({work_km:.0f}km at marathon effort ({mp_pace_mi}/mi), "
        f"{float_km:.0f}km {float_effort}). "
        f"The float is NOT easy — maintain rhythm."
    )
    if fueling:
        desc += f"\n{fueling.notes}"

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="marathon_pace_alt_km",
        title=f"Alt-KM Marathon Pace ({reps}×{work_km:.0f}km)",
        description=desc,
        phase=phase,
        segments=segments,
        fueling=fueling,
    )


# ── 4. Threshold Alt-KM ─────────────────────────────────────────────

def threshold_alt_km(
    ladder: PaceLadder,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    day_of_week: int = 2,
    phase: str = "supportive",
) -> V2DayPlan:
    """Alternating kilometer at threshold with float recovery."""
    progress = min(1.0, week_in_phase / max(1, phase_weeks - 1))

    reps = 4 + min(3, int(progress * 4))  # 4 → 7
    float_pct = 85 + int(progress * 5)     # 85 → 90

    segments: List[WorkoutSegment] = [warmup(ladder, is_beginner=is_beginner)]
    for i in range(reps):
        segments.append(work_segment(
            ladder, 105, zone="threshold", distance_km=1.0, is_beginner=is_beginner,
        ))
        if i < reps - 1:
            segments.append(float_segment(
                ladder, float_pct, distance_km=1.0, is_beginner=is_beginner,
            ))
    segments.append(cooldown(ladder, is_beginner=is_beginner))

    t_pace_mi = format_pace_sec_km(ladder.threshold, "mi")
    effort = describe_segment(105, ladder.threshold, is_beginner=is_beginner)
    float_effort = describe_segment(float_pct, ladder.pace_for_pct(float_pct), is_beginner=is_beginner)
    desc = (
        f"{reps}×(1km at {effort} ({t_pace_mi}/mi), "
        f"1km {float_effort}). "
        f"The float pace improvement is your clearest fitness signal."
    )

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="threshold_alt_km",
        title=f"Alt-KM Threshold ({reps}×1km)",
        description=desc,
        phase=phase,
        segments=segments,
    )


# ── 5. Speed Support ────────────────────────────────────────────────

def speed_support(
    ladder: PaceLadder,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    day_of_week: int = 2,
    phase: str = "supportive",
) -> V2DayPlan:
    """Speed support repeats at 110% MP (10K effort).

    Extension progression: 1K → 1600m → 2K.
    """
    progress = min(1.0, week_in_phase / max(1, phase_weeks - 1))

    if progress < 0.3:
        rep_km = 1.0
        reps = 6
    elif progress < 0.6:
        rep_km = 1.6
        reps = 5
    else:
        rep_km = 2.0
        reps = 4

    pace = _resolve_pace(ladder, 110)
    segments: List[WorkoutSegment] = [warmup(ladder, is_beginner=is_beginner)]
    for i in range(reps):
        segments.append(work_segment(
            ladder, 110, distance_km=rep_km, is_beginner=is_beginner,
        ))
        if i < reps - 1:
            segments.append(jog_rest(ladder, 3.0, is_beginner=is_beginner))
    segments.append(cooldown(ladder, is_beginner=is_beginner))

    pace_mi = format_pace_sec_km(pace, "mi")
    effort = describe_segment(110, pace, is_beginner=is_beginner)
    desc = (
        f"{reps}×{rep_km:.1f}km at {effort} ({pace_mi}/mi) "
        f"with 3min jog rest. "
        f"Extension from {rep_km:.1f}km reps — hold pace steady."
    )

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="speed_support",
        title=f"Speed Support ({reps}×{rep_km:.1f}km)",
        description=desc,
        phase=phase,
        segments=segments,
    )


# ── 6. VO2max / 5K Effort ───────────────────────────────────────────

def vo2max_intervals(
    ladder: PaceLadder,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    day_of_week: int = 2,
    phase: str = "general",
) -> V2DayPlan:
    """VO2max intervals at 5K effort (115% MP)."""
    progress = min(1.0, week_in_phase / max(1, phase_weeks - 1))

    if progress < 0.3:
        structure = "pyramid"
        rep_times = [3, 2, 1, 2, 3]  # minutes
    elif progress < 0.6:
        structure = "flat"
        rep_times = [3] * 5
    else:
        structure = "descending"
        rep_times = [4, 3, 2, 1]

    pace = _resolve_pace(ladder, 115, zone="interval")
    segments: List[WorkoutSegment] = [warmup(ladder, is_beginner=is_beginner)]
    for i, mins in enumerate(rep_times):
        segments.append(work_segment(
            ladder, 115, zone="interval", duration_min=float(mins), is_beginner=is_beginner,
        ))
        if i < len(rep_times) - 1:
            segments.append(jog_rest(ladder, float(mins), is_beginner=is_beginner))
    segments.append(cooldown(ladder, is_beginner=is_beginner))

    effort = describe_segment(115, pace, is_beginner=is_beginner)
    pace_mi = format_pace_sec_km(pace, "mi")
    rep_desc = "/".join(f"{m}min" for m in rep_times)
    desc = (
        f"{structure.title()} intervals at {effort} ({pace_mi}/mi): "
        f"{rep_desc} with equal jog rest."
    )

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="vo2max_intervals",
        title=f"VO2max {structure} ({rep_desc})",
        description=desc,
        phase=phase,
        segments=segments,
    )


# ── 7. Progression Run ──────────────────────────────────────────────

def progression_run(
    ladder: PaceLadder,
    total_km: float,
    is_beginner: bool,
    day_of_week: int = 2,
    phase: str = "general",
) -> V2DayPlan:
    """Kenyan-style progression run — start easy, finish at MP."""
    steps = [
        (0.35, 80, "easy"),
        (0.25, 90, None),
        (0.25, 95, None),
        (0.15, 100, "marathon"),
    ]

    segments: List[WorkoutSegment] = []
    desc_parts = []
    for frac, pct, zone in steps:
        seg_km = round(total_km * frac, 1)
        pace = _resolve_pace(ladder, pct, zone=zone)
        effort = describe_segment(pct, pace, is_beginner=is_beginner)
        segments.append(WorkoutSegment(
            type="work" if pct > 80 else "easy",
            pace_pct_mp=pct,
            pace_sec_per_km=pace,
            distance_km=seg_km,
            description=effort,
        ))
        desc_parts.append(f"{seg_km:.0f}km {effort}")

    desc = f"Progression run: {' → '.join(desc_parts)}. Build into it — don't force the early km."

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="progression",
        title=f"Progression run ({total_km:.0f}km)",
        description=desc,
        phase=phase,
        segments=segments,
    )


# ── 8. Regenerative ─────────────────────────────────────────────────

def regenerative_threshold(
    ladder: PaceLadder,
    is_beginner: bool,
    day_of_week: int = 2,
    phase: str = "specific",
) -> V2DayPlan:
    """Regenerative workout — 7/10 difficulty.  Touch on quality without pushing."""
    segments = [
        warmup(ladder, distance_km=2.0, is_beginner=is_beginner),
        work_segment(ladder, 105, zone="threshold", distance_km=6.0, is_beginner=is_beginner),
        cooldown(ladder, distance_km=2.0, is_beginner=is_beginner),
    ]

    effort = describe_segment(105, ladder.threshold, is_beginner=is_beginner)
    t_pace_mi = format_pace_sec_km(ladder.threshold, "mi")
    desc = (
        f"Regenerative threshold: 6km at {effort} ({t_pace_mi}/mi). "
        f"7/10 difficulty — touch the system, don't push it."
    )

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="regenerative",
        title="Regenerative threshold (6km)",
        description=desc,
        phase=phase,
        segments=segments,
    )


# ── 9. Threshold Cruise (extension-based) ───────────────────────────

_T_BLOCK_STEPS = [
    (6, 5.0, 2.0),   # 6×5min w/ 2min jog
    (5, 6.0, 2.0),   # 5×6min w/ 2min jog
    (4, 8.0, 2.0),   # 4×8min w/ 2min jog
    (3, 10.0, 3.0),  # 3×10min w/ 3min jog
    (2, 15.0, 3.0),  # 2×15min w/ 3min jog
    (1, 35.0, 0.0),  # 35-40min continuous
]


def threshold_cruise(
    ladder: PaceLadder,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    day_of_week: int = 2,
    phase: str = "general",
) -> V2DayPlan:
    """Threshold cruise intervals with extension-based progression.

    KB progression: 6×5min → 5×6min → 4×8min → 3×10min → 2×15min → 40min continuous.
    Same pace, longer reps. Total work time stays roughly constant (~30min).
    """
    if phase == "taper":
        reps, rep_min, rest_min = 3, 5.0, 2.0
    else:
        progress = min(1.0, week_in_phase / max(1, phase_weeks - 1))
        step_idx = min(int(progress * len(_T_BLOCK_STEPS)), len(_T_BLOCK_STEPS) - 1)
        reps, rep_min, rest_min = _T_BLOCK_STEPS[step_idx]

    segments: List[WorkoutSegment] = [warmup(ladder, is_beginner=is_beginner)]
    for i in range(reps):
        segments.append(work_segment(
            ladder, 105, zone="threshold", duration_min=rep_min, is_beginner=is_beginner,
        ))
        if i < reps - 1 and rest_min > 0:
            segments.append(jog_rest(ladder, rest_min, is_beginner=is_beginner))
    segments.append(cooldown(ladder, is_beginner=is_beginner))

    effort = describe_segment(105, ladder.threshold, is_beginner=is_beginner)
    t_pace_mi = format_pace_sec_km(ladder.threshold, "mi")

    if reps == 1:
        title = f"Threshold continuous ({rep_min:.0f}min)"
        desc = (
            f"{rep_min:.0f}min continuous at {effort} ({t_pace_mi}/mi). "
            f"This is the endpoint of the extension arc — same pace you "
            f"started with in 5min reps, now held for 35+ minutes."
        )
    else:
        rest_desc = f" with {rest_min:.0f}min easy jog" if rest_min > 0 else ""
        title = f"Threshold cruise ({reps}×{rep_min:.0f}min)"
        desc = (
            f"{reps}×{rep_min:.0f}min at {effort} ({t_pace_mi}/mi){rest_desc}. "
            f"Hold pace steady — extension is the progression, not speed."
        )

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="threshold_cruise",
        title=title,
        description=desc,
        phase=phase,
        segments=segments,
    )


# ── 10. Long Run C — Fatigue Resistance ──────────────────────────────

def long_run_fatigue_resistance(
    ladder: PaceLadder,
    distance_range_km: Tuple[float, float],
    phase_position: float,
    is_beginner: bool,
    training_age: float,
    day_of_week: int = 5,
    phase: str = "specific",
) -> V2DayPlan:
    """Long run with threshold block at ~65% of total distance.

    After the athlete is glycogen-depleted, insert 15-20 min of threshold
    work, then return to easy. Trains form retention under fatigue —
    exactly what miles 20-26 of a marathon demand.
    """
    target_km = (distance_range_km[0] + distance_range_km[1]) / 2.0
    threshold_min = 15.0 + phase_position * 5.0  # 15min early → 20min late

    # Split: 65% easy, threshold block, remaining easy
    easy_first_km = round(target_km * 0.65, 1)
    easy_finish_km = round(target_km * 0.20, 1)

    easy_pace = ladder.easy
    t_pace = ladder.threshold
    t_effort = describe_segment(105, t_pace, is_beginner=is_beginner)
    t_pace_mi = format_pace_sec_km(t_pace, "mi")

    segments = [
        WorkoutSegment(
            type="steady", pace_pct_mp=80, pace_sec_per_km=easy_pace,
            distance_km=easy_first_km,
            description=describe_segment(80, easy_pace, is_beginner=is_beginner),
        ),
        work_segment(ladder, 105, zone="threshold", duration_min=threshold_min,
                     is_beginner=is_beginner),
        WorkoutSegment(
            type="steady", pace_pct_mp=80, pace_sec_per_km=easy_pace,
            distance_km=easy_finish_km,
            description=describe_segment(80, easy_pace, is_beginner=is_beginner),
        ),
    ]

    est_min = _est_duration_min(target_km, easy_pace)
    fueling = _fueling_for_duration(est_min, training_age)

    desc = (
        f"Fatigue resistance long run: {easy_first_km:.0f}km easy, then "
        f"{threshold_min:.0f}min at {t_effort} ({t_pace_mi}/mi), "
        f"then {easy_finish_km:.0f}km easy to finish. "
        f"The hard block comes when you're already loaded — "
        f"that's the point. Hold form, hold economy."
    )
    if fueling:
        desc += f"\n{fueling.notes}"

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="long_run_fatigue_resistance",
        title=f"Fatigue resistance long run ({target_km:.0f}km)",
        description=desc,
        phase=phase,
        segments=segments,
        distance_range_km=distance_range_km,
        fueling=fueling,
    )


# ── 10b. Long Run — Moderate ────────────────────────────────────────

def long_run_moderate(
    ladder: PaceLadder,
    distance_range_km: Tuple[float, float],
    is_beginner: bool,
    training_age: float,
    day_of_week: int = 5,
    phase: str = "general",
) -> V2DayPlan:
    """First half easy, second half at moderate effort (~90% MP).

    Teaches the body to run faster on pre-fatigued legs without
    crossing the threshold line. A general-phase bridge toward
    race-specific long runs later.
    """
    target_km = (distance_range_km[0] + distance_range_km[1]) / 2.0
    easy_km = round(target_km * 0.55, 1)
    mod_km = round(target_km * 0.45, 1)

    easy_pace = ladder.easy
    mod_pace = ladder.pace_for_pct(90)
    mod_effort = describe_segment(90, mod_pace, is_beginner=is_beginner)

    segments = [
        WorkoutSegment(
            type="steady", pace_pct_mp=80, pace_sec_per_km=easy_pace,
            distance_km=easy_km,
            description=describe_segment(80, easy_pace, is_beginner=is_beginner),
        ),
        WorkoutSegment(
            type="work", pace_pct_mp=90, pace_sec_per_km=mod_pace,
            distance_km=mod_km,
            description=mod_effort,
        ),
    ]

    est_min = _est_duration_min(target_km, easy_pace)
    fueling = _fueling_for_duration(est_min, training_age)

    mod_pace_mi = format_pace_sec_km(mod_pace, "mi")
    desc = (
        f"Moderate long run: {easy_km:.0f}km easy, then "
        f"{mod_km:.0f}km at {mod_effort} ({mod_pace_mi}/mi). "
        f"Find a rhythm in the second half — don't race it."
    )
    if fueling:
        desc += f"\n{fueling.notes}"

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="long_run_moderate",
        title=f"Moderate long run ({target_km:.0f}km)",
        description=desc,
        phase=phase,
        segments=segments,
        distance_range_km=distance_range_km,
        fueling=fueling,
    )


# ── 10c. Long Run — Progression Finish ─────────────────────────────

def long_run_progression_finish(
    ladder: PaceLadder,
    distance_range_km: Tuple[float, float],
    is_beginner: bool,
    training_age: float,
    day_of_week: int = 5,
    phase: str = "supportive",
) -> V2DayPlan:
    """Easy → moderate → steady finish. Teaches closing speed on tired legs.

    60% easy, 25% moderate (~90% MP), 15% steady (~95% MP).
    The final segment is short enough to hold without blowing up.
    """
    target_km = (distance_range_km[0] + distance_range_km[1]) / 2.0
    easy_km = round(target_km * 0.60, 1)
    mod_km = round(target_km * 0.25, 1)
    steady_km = round(target_km * 0.15, 1)

    easy_pace = ladder.easy
    mod_pace = ladder.pace_for_pct(90)
    steady_pace = ladder.pace_for_pct(95)

    mod_effort = describe_segment(90, mod_pace, is_beginner=is_beginner)
    steady_effort = describe_segment(95, steady_pace, is_beginner=is_beginner)

    segments = [
        WorkoutSegment(
            type="steady", pace_pct_mp=80, pace_sec_per_km=easy_pace,
            distance_km=easy_km,
            description=describe_segment(80, easy_pace, is_beginner=is_beginner),
        ),
        WorkoutSegment(
            type="work", pace_pct_mp=90, pace_sec_per_km=mod_pace,
            distance_km=mod_km,
            description=mod_effort,
        ),
        WorkoutSegment(
            type="work", pace_pct_mp=95, pace_sec_per_km=steady_pace,
            distance_km=steady_km,
            description=steady_effort,
        ),
    ]

    est_min = _est_duration_min(target_km, easy_pace)
    fueling = _fueling_for_duration(est_min, training_age)

    steady_pace_mi = format_pace_sec_km(steady_pace, "mi")
    desc = (
        f"Progression finish long run: {easy_km:.0f}km easy, "
        f"{mod_km:.0f}km moderate, "
        f"{steady_km:.0f}km at {steady_effort} ({steady_pace_mi}/mi). "
        f"Build into it — the last segment should feel controlled, not maximal."
    )
    if fueling:
        desc += f"\n{fueling.notes}"

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="long_run_progression_finish",
        title=f"Progression finish long run ({target_km:.0f}km)",
        description=desc,
        phase=phase,
        segments=segments,
        distance_range_km=distance_range_km,
        fueling=fueling,
    )


# ── 10d. Long Run — Marathon Pace ──────────────────────────────────

def long_run_mp(
    ladder: PaceLadder,
    distance_range_km: Tuple[float, float],
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    training_age: float,
    day_of_week: int = 5,
    phase: str = "specific",
) -> V2DayPlan:
    """Long run with sustained marathon-pace segment.

    The MP segment progresses across the build:
      General (late): 35-40% of total at MP (~6-8mi in an 18mi run)
      Supportive:     45-55% of total at MP (~8-10mi)
      Specific early:  55-60% of total at MP (~10-12mi)
      Specific late:   65-75% of total at MP (~14-16mi)

    Structure: easy warmup → sustained MP → easy cooldown.
    The MP segment is continuous, not intervals.
    """
    target_km = (distance_range_km[0] + distance_range_km[1]) / 2.0
    progress = min(1.0, week_in_phase / max(1, phase_weeks - 1))

    if phase == "general":
        mp_frac = 0.35 + progress * 0.05
    elif phase == "supportive":
        mp_frac = 0.45 + progress * 0.10
    else:
        mp_frac = 0.55 + progress * 0.20

    mp_km = round(target_km * mp_frac, 1)
    remaining_km = target_km - mp_km
    warmup_km = round(min(remaining_km * 0.60, 6.0), 1)
    cooldown_km = round(max(remaining_km - warmup_km, 3.0), 1)

    mp_pace = ladder.marathon
    easy_pace = ladder.easy
    mp_effort = describe_segment(100, mp_pace, is_beginner=is_beginner)
    easy_effort = describe_segment(80, easy_pace, is_beginner=is_beginner)

    segments = [
        WorkoutSegment(
            type="easy", pace_pct_mp=80, pace_sec_per_km=easy_pace,
            distance_km=warmup_km,
            description=easy_effort,
        ),
        WorkoutSegment(
            type="work", pace_pct_mp=100, pace_sec_per_km=mp_pace,
            distance_km=mp_km,
            description=mp_effort,
        ),
        WorkoutSegment(
            type="easy", pace_pct_mp=80, pace_sec_per_km=easy_pace,
            distance_km=cooldown_km,
            description=easy_effort,
        ),
    ]

    est_min = _est_duration_min(target_km, (easy_pace + mp_pace) / 2)
    fueling = _fueling_for_duration(est_min, training_age)

    mp_mi = round(mp_km / MI_TO_KM, 1)
    mp_pace_mi = format_pace_sec_km(mp_pace, "mi")
    desc = (
        f"Marathon-pace long run: {warmup_km:.0f}km easy warmup, "
        f"{mp_km:.0f}km ({mp_mi:.0f}mi) at marathon effort ({mp_pace_mi}/mi), "
        f"{cooldown_km:.0f}km easy cooldown. "
        f"Sustained — not intervals. Hold the pace honestly."
    )
    if fueling:
        desc += f"\n{fueling.notes}"

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="long_run_mp",
        title=f"MP long run ({mp_mi:.0f}mi at MP)",
        description=desc,
        phase=phase,
        segments=segments,
        distance_range_km=distance_range_km,
        fueling=fueling,
    )


# ── 11. Strides Variants ────────────────────────────────────────────

def flat_strides(
    ladder: PaceLadder,
    distance_range_km: Tuple[float, float],
    is_beginner: bool,
    day_of_week: int,
    phase: str,
) -> V2DayPlan:
    """Flat strides — 6×20s at controlled fast effort, full recovery."""
    effort = map_effort(80, is_beginner=is_beginner)
    stride_effort = map_effort(120, is_beginner=is_beginner)
    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="flat_strides",
        title="Easy + flat strides",
        description=(
            f"Easy run — {effort} + 6x20s flat strides ({stride_effort}). "
            f"Smooth acceleration, full walk-back recovery."
        ),
        phase=phase,
        distance_range_km=distance_range_km,
    )


def uphill_strides(
    ladder: PaceLadder,
    distance_range_km: Tuple[float, float],
    is_beginner: bool,
    day_of_week: int,
    phase: str,
) -> V2DayPlan:
    """Uphill strides — 5×20s on a moderate grade, jog down recovery."""
    effort = map_effort(80, is_beginner=is_beginner)
    stride_effort = map_effort(118, is_beginner=is_beginner)
    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="uphill_strides",
        title="Easy + uphill strides",
        description=(
            f"Easy run — {effort} + 5x20s uphill strides ({stride_effort}). "
            f"Find a 4-6% grade, strong drive off the hill, jog down to recover."
        ),
        phase=phase,
        distance_range_km=distance_range_km,
    )


def fast_strides(
    ladder: PaceLadder,
    distance_range_km: Tuple[float, float],
    is_beginner: bool,
    day_of_week: int,
    phase: str,
) -> V2DayPlan:
    """Fast strides — 6×15s closer to mile effort, full recovery."""
    effort = map_effort(80, is_beginner=is_beginner)
    stride_effort = map_effort(125, is_beginner=is_beginner)
    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="fast_strides",
        title="Easy + fast strides",
        description=(
            f"Easy run — {effort} + 6x15s fast strides ({stride_effort}). "
            f"Closer to mile effort. Quick turnover, full recovery between."
        ),
        phase=phase,
        distance_range_km=distance_range_km,
    )


# ── 12. Uphill Treadmill Threshold ──────────────────────────────────

def uphill_tm_threshold(
    ladder: PaceLadder,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    day_of_week: int = 2,
    phase: str = "supportive",
) -> V2DayPlan:
    """Threshold effort on treadmill at 4-6% incline.

    Distinct from flat threshold — trains hip extension, loads posterior
    chain differently, lower injury risk at same HR.
    """
    progress = min(1.0, week_in_phase / max(1, phase_weeks - 1))
    grade = 4.0 + progress * 2.0  # 4% → 6%

    if progress < 0.3:
        reps = 4
        rep_min = 5.0
    elif progress < 0.6:
        reps = 3
        rep_min = 7.0
    else:
        reps = 3
        rep_min = 10.0

    segments: List[WorkoutSegment] = [warmup(ladder, is_beginner=is_beginner)]
    for i in range(reps):
        segments.append(uphill_tm_segment(
            ladder, pct=105, duration_min=rep_min,
            grade_pct=grade, is_beginner=is_beginner,
        ))
        if i < reps - 1:
            segments.append(jog_rest(ladder, 2.0, is_beginner=is_beginner))
    segments.append(cooldown(ladder, is_beginner=is_beginner))

    t_effort = describe_segment(105, ladder.threshold, is_beginner=is_beginner)
    desc = (
        f"{reps}x{rep_min:.0f}min at {t_effort} on {grade:.0f}% incline. "
        f"Same heart rate as flat threshold but training hip extension "
        f"and posterior chain. Lower injury risk."
    )

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="uphill_tm_threshold",
        title=f"Uphill TM threshold ({reps}x{rep_min:.0f}min @ {grade:.0f}%)",
        description=desc,
        phase=phase,
        segments=segments,
    )


# ── 13. Fatigue Resistance Hills ────────────────────────────────────

def fatigue_resistance_hills(
    ladder: PaceLadder,
    distance_range_km: Tuple[float, float],
    is_beginner: bool,
    training_age: float,
    day_of_week: int = 5,
    phase: str = "specific",
) -> V2DayPlan:
    """10-20 short steep hill sprints (8-12s) at the END of a long easy run.

    Not hill intervals — the effort is maximal for the sprint but the
    training effect is power output under pre-fatigue/glycogen depletion.
    """
    target_km = (distance_range_km[0] + distance_range_km[1]) / 2.0
    reps = 12 if training_age >= 3 else 8
    sprint_sec = 10.0

    easy_pace = ladder.easy
    segments = [
        WorkoutSegment(
            type="easy", pace_pct_mp=80, pace_sec_per_km=easy_pace,
            distance_km=round(target_km * 0.85, 1),
            description=describe_segment(80, easy_pace, is_beginner=is_beginner),
        ),
        fatigue_resistance_segment(ladder, reps=reps, duration_sec=sprint_sec,
                                   is_beginner=is_beginner),
    ]

    est_min = _est_duration_min(target_km, easy_pace)
    fueling = _fueling_for_duration(est_min, training_age)

    stride_effort = map_effort(120, is_beginner=is_beginner)
    desc = (
        f"Long easy run ({target_km:.0f}km), then {reps}x{sprint_sec:.0f}s steep hill "
        f"sprints at the END ({stride_effort}). Walk down recovery between. "
        f"Power under depletion — this is where race-day resilience is built."
    )
    if fueling:
        desc += f"\n{fueling.notes}"

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="fatigue_resistance_hills",
        title=f"Long run + {reps}x hill sprints",
        description=desc,
        phase=phase,
        segments=segments,
        distance_range_km=distance_range_km,
        fueling=fueling,
    )


# ── 14. Steady Run ──────────────────────────────────────────────────

def steady_run(
    ladder: PaceLadder,
    distance_range_km: Tuple[float, float],
    is_beginner: bool,
    day_of_week: int,
    phase: str,
) -> V2DayPlan:
    """Continuous easy-to-moderate effort — the bread-and-butter aerobic session.

    Longer than recovery, shorter than a long run. Not structured.
    """
    target_km = (distance_range_km[0] + distance_range_km[1]) / 2.0
    effort = map_effort(88, is_beginner=is_beginner)

    segments = [
        steady_segment(ladder, pct=88, distance_km=target_km, is_beginner=is_beginner),
    ]

    desc = (
        f"Steady run — {effort}. Not a workout, not a jog. "
        f"Purposeful aerobic volume at a rhythm that feels honest."
    )

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="steady_run",
        title="Steady run",
        description=desc,
        phase=phase,
        segments=segments,
        target_distance_km=target_km,
        distance_range_km=(target_km - 1.5, target_km + 1.5),
    )


# ── 15. Micro-Intervals (Billat 30/30) ──────────────────────────────

def micro_intervals(
    ladder: PaceLadder,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    day_of_week: int = 2,
    phase: str = "general",
) -> V2DayPlan:
    """30s on / 30s off at vVO2max pace, accumulated over 20-30 min.

    Billat 30-30 protocol. Brief recovery prevents full lactate clearance;
    athlete accumulates more total time at VO2max than standard intervals.
    """
    progress = min(1.0, week_in_phase / max(1, phase_weeks - 1))
    total_sets = int(20 + progress * 10)  # 20 → 30 reps of 30/30
    set_min = total_sets  # each 30/30 pair = 1 minute

    pace = _resolve_pace(ladder, 118)
    segments: List[WorkoutSegment] = [warmup(ladder, is_beginner=is_beginner)]
    segments.append(work_segment(
        ladder, 118, duration_min=float(set_min), reps=total_sets,
        rest_min=0.5, is_beginner=is_beginner,
    ))
    segments.append(cooldown(ladder, is_beginner=is_beginner))

    effort = describe_segment(118, pace, is_beginner=is_beginner)
    pace_mi = format_pace_sec_km(pace, "mi")
    desc = (
        f"{total_sets}x(30s at {effort} ({pace_mi}/mi) / 30s easy jog). "
        f"Continuous — no standing rest. The accumulated time at VO2max "
        f"is higher than standard intervals. Stay smooth."
    )

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="micro_intervals",
        title=f"Micro-intervals ({total_sets}x30/30)",
        description=desc,
        phase=phase,
        segments=segments,
    )


# ── 16. Run/Hike Segments ───────────────────────────────────────────

def run_hike(
    ladder: PaceLadder,
    distance_range_km: Tuple[float, float],
    is_beginner: bool,
    training_age: float,
    day_of_week: int,
    phase: str,
) -> V2DayPlan:
    """Alternating running and walking/hiking intervals.

    For beginners: volume-building tool (run 4min / walk 1min).
    For ultra: race-specific practice (run 10min / hike 2min).
    """
    target_km = (distance_range_km[0] + distance_range_km[1]) / 2.0
    easy_pace = ladder.easy

    if is_beginner:
        run_min = 4.0
        hike_min = 1.0
        pattern_desc = "run 4min / walk 1min"
    else:
        run_min = 10.0
        hike_min = 2.0
        pattern_desc = "run 10min / hike 2min"

    segments = [
        WorkoutSegment(
            type="easy", pace_pct_mp=80, pace_sec_per_km=easy_pace,
            duration_min=run_min, description="run",
        ),
        hike_segment(ladder, duration_min=hike_min, is_beginner=is_beginner),
    ]

    est_min = _est_duration_min(target_km, easy_pace * 1.1)
    fueling = _fueling_for_duration(est_min, training_age)

    effort = map_effort(80, is_beginner=is_beginner)
    desc = (
        f"Run/hike — {effort}, alternating {pattern_desc}. "
        f"Hike as much as you need for the distance. "
        f"Building volume without breaking the body."
    )
    if fueling:
        desc += f"\n{fueling.notes}"

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="run_hike",
        title=f"Run/hike ({target_km:.0f}km)",
        description=desc,
        phase=phase,
        segments=segments,
        distance_range_km=distance_range_km,
        fueling=fueling,
    )


# ── 17. Medium-Long Run ──────────────────────────────────────────────

_ML_CAP_MI = 15
_ML_CAP_KM = _ML_CAP_MI * MI_TO_KM


def medium_long_run(
    ladder: PaceLadder,
    long_run_distance_km: float,
    weekly_target_km: float,
    is_beginner: bool,
    training_age: float,
    day_of_week: int = 3,
    phase: str = "general",
) -> V2DayPlan:
    """Mid-week aerobic volume run at easy effort.

    Sized relative to the week's long run distance (55-70%), scaled
    by weekly volume band. Hard cap at 15 miles (24.1km).

    Not for beginners — the aerobic base isn't deep enough to absorb
    it without compromising recovery.
    """
    weekly_mi = weekly_target_km / MI_TO_KM

    if weekly_mi < 55:
        ml_frac = 0.55
    elif weekly_mi < 70:
        ml_frac = 0.62
    else:
        ml_frac = 0.68

    ml_km = round(long_run_distance_km * ml_frac, 1)
    ml_km = min(ml_km, _ML_CAP_KM)
    ml_km = max(ml_km, 12.0)

    distance_range_km = (round(ml_km - 1.5, 1), round(ml_km + 1.5, 1))
    effort = map_effort(80, is_beginner=is_beginner)
    ml_mi = round(ml_km / MI_TO_KM, 1)

    est_min = _est_duration_min(ml_km, ladder.easy)
    fueling = _fueling_for_duration(est_min, training_age)

    desc = (
        f"Medium-long run — {ml_mi:.0f} miles at {effort}. "
        f"Sustained aerobic volume without the full recovery cost "
        f"of the long run. Don't push the pace."
    )
    if fueling:
        desc += f"\n{fueling.notes}"

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="medium_long",
        title=f"Medium-long run ({ml_mi:.0f}mi)",
        description=desc,
        phase=phase,
        distance_range_km=distance_range_km,
        fueling=fueling,
    )


# ── Tune-Up Race Builders ────────────────────────────────────────────

def tune_up_race_day(
    ladder: PaceLadder,
    distance_km: float,
    name: str,
    purpose: str,
    is_beginner: bool,
    day_of_week: int,
    phase: str,
) -> V2DayPlan:
    """The tune-up race itself."""
    from .models import TuneUpRace  # avoid circular at module level

    if purpose == "threshold":
        desc = (
            f"RACE: {name}. Race this HARD — final threshold-level "
            f"effort before goal race. Full race effort, use it to "
            f"calibrate your pacing and test your race-day routine."
        )
    elif purpose == "confidence":
        desc = (
            f"RACE: {name}. Controlled effort — run within yourself. "
            f"The goal is a confidence booster and a process rehearsal, "
            f"not a PB. Save your peak for the goal race."
        )
    else:
        desc = (
            f"RACE: {name}. Sharpening effort — run hard but not "
            f"all-out. This is neuromuscular stimulus at race intensity "
            f"with full recovery before the goal race."
        )

    race_pace = ladder.pace_for_pct(100) if distance_km > 21 else ladder.interval
    if distance_km <= 10:
        race_pace = ladder.pace_for_pct(110)

    segments = [
        WorkoutSegment(
            type="race",
            pace_pct_mp=100 if distance_km > 21 else 110,
            pace_sec_per_km=race_pace,
            description=f"Race: {name}",
            distance_km=round(distance_km, 1),
        ),
    ]

    est_min = _est_duration_min(distance_km, race_pace)
    fueling = _fueling_for_duration(est_min, 5.0) if est_min > _FUELING_THRESHOLD_MIN else None

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="tune_up_race",
        title=name,
        description=desc,
        phase=phase,
        segments=segments,
        target_distance_km=round(distance_km, 1),
        fueling=fueling,
    )


def pre_race_day(
    ladder: PaceLadder,
    is_beginner: bool,
    day_of_week: int,
    phase: str,
) -> V2DayPlan:
    """Day before a tune-up race — short easy with strides."""
    effort = map_effort(80, is_beginner=is_beginner)
    stride_effort = map_effort(120, is_beginner=is_beginner)
    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="pre_race",
        title="Pre-race shakeout",
        description=(
            f"3-5mi easy ({effort}) + 4×100m strides ({stride_effort}). "
            f"Stay loose, save your legs. Confirm your race-day kit and nutrition."
        ),
        phase=phase,
        distance_range_km=(5.0, 8.0),
    )


def post_race_recovery(
    ladder: PaceLadder,
    is_beginner: bool,
    day_of_week: int,
    phase: str,
    weekly_target_km: float = 0.0,
) -> V2DayPlan:
    """Day after a tune-up race — recovery long run.

    For experienced athletes, this is a substantial zone-1 flush run
    (10-15mi for 60+ mpw athletes). The tune-up race provided the
    stimulus; this run maintains weekly volume and promotes recovery
    through easy aerobic blood flow.
    """
    effort = map_effort(75, is_beginner=is_beginner)

    recovery_pct = 0.15 if is_beginner else 0.20
    target_km = max(8.0, weekly_target_km * recovery_pct)

    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="recovery_long",
        title="Recovery long run",
        description=(
            f"Recovery long run ({effort}). Zone 1 effort — "
            f"flush the legs, no pace targets. Volume maintenance."
        ),
        phase=phase,
        distance_range_km=(target_km - 2.0, target_km + 2.0),
    )


# ── Easy Run Builders ────────────────────────────────────────────────

def easy_run(
    ladder: PaceLadder,
    distance_range_km: Tuple[float, float],
    is_beginner: bool,
    day_of_week: int,
    phase: str,
) -> V2DayPlan:
    effort = map_effort(80, is_beginner=is_beginner)
    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="easy",
        title="Easy run",
        description=f"Easy run — {effort}",
        phase=phase,
        distance_range_km=distance_range_km,
    )


def easy_with_strides(
    ladder: PaceLadder,
    distance_range_km: Tuple[float, float],
    is_beginner: bool,
    day_of_week: int,
    phase: str,
) -> V2DayPlan:
    effort = map_effort(80, is_beginner=is_beginner)
    stride_effort = map_effort(120, is_beginner=is_beginner)
    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="easy_strides",
        title="Easy + strides",
        description=f"Easy run — {effort} + 6×20s strides ({stride_effort})",
        phase=phase,
        distance_range_km=distance_range_km,
    )


def rest_day(day_of_week: int, phase: str) -> V2DayPlan:
    return V2DayPlan(
        day_of_week=day_of_week,
        workout_type="rest",
        title="Rest",
        description="Full rest or easy cross-training",
        phase=phase,
    )


# ── Slot → Workout Dispatcher ───────────────────────────────────────

def build_day_from_slot(
    slot: dict,
    ladder: PaceLadder,
    bank,
    phase_name: str,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    training_age: float,
    goal_event: str,
    weekly_target_km: float,
    long_range_km: Tuple[float, float],
    week_num: int,
    total_weeks: int,
    *,
    limiter: Optional[str] = None,
    primary_quality_emphasis: Optional[str] = None,
    is_cutback: bool = False,
    quality_week_index: int = 0,
) -> V2DayPlan:
    """Convert a scheduler slot into a concrete V2DayPlan.

    limiter and primary_quality_emphasis from FingerprintParams drive
    quality session selection — this is what makes V2 an N=1 engine.

    quality_week_index increments only on non-cutback quality weeks,
    ensuring workout rotation doesn't skip variants on cutback weeks.
    """
    global _current_goal_event
    _current_goal_event = goal_event

    from .volume import easy_run_range_km

    d = slot["day"]
    s = slot["slot"]

    if s == "rest":
        return rest_day(d, phase_name)

    if s == "easy":
        rng = easy_run_range_km(weekly_target_km, "easy")
        return easy_run(ladder, rng, is_beginner, d, phase_name)

    if s == "easy_short":
        rng = easy_run_range_km(weekly_target_km, "easy_short")
        return easy_run(ladder, rng, is_beginner, d, phase_name)

    if s == "easy_strides":
        rng = easy_run_range_km(weekly_target_km, "easy")
        return easy_with_strides(ladder, rng, is_beginner, d, phase_name)

    if s == "long_run":
        return _build_long_run(
            ladder, d, phase_name, week_in_phase, phase_weeks,
            is_beginner, training_age, goal_event, long_range_km,
            is_cutback=is_cutback,
            quality_week_index=quality_week_index,
        )

    if s == "quality_primary":
        return _build_primary_quality(
            ladder, d, phase_name, week_in_phase, phase_weeks,
            is_beginner, training_age,
            limiter=limiter,
            primary_quality_emphasis=primary_quality_emphasis,
            goal_event=goal_event,
            week_num=week_num,
            quality_week_index=quality_week_index,
        )

    if s == "quality_secondary":
        return _build_secondary_quality(
            ladder, d, phase_name, week_in_phase, phase_weeks,
            is_beginner,
            limiter=limiter,
            goal_event=goal_event,
            quality_week_index=quality_week_index,
        )

    if s == "medium_long":
        lr_target_km = (long_range_km[0] + long_range_km[1]) / 2.0
        return medium_long_run(
            ladder, lr_target_km, weekly_target_km,
            is_beginner, training_age, d, phase_name,
        )

    if s == "regenerative":
        return regenerative_threshold(ladder, is_beginner, d, phase_name)

    # Fallback
    rng = easy_run_range_km(weekly_target_km, "easy")
    return easy_run(ladder, rng, is_beginner, d, phase_name)


def _build_long_run(
    ladder: PaceLadder,
    day: int,
    phase: str,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    training_age: float,
    goal_event: str,
    distance_range_km: Tuple[float, float],
    *,
    is_cutback: bool = False,
    quality_week_index: int = 0,
) -> V2DayPlan:
    """Select long run type by phase, cutback status, and progression.

    Cutback weeks and taper: always easy.
    General phase: derived from phase_progress — easy early, moderate/
    progression finish in back half.
    Supportive/specific: 5-variant cycle using quality_week_index.
    """
    if is_cutback or phase == "taper":
        return long_easy(
            ladder, distance_range_km, is_beginner, training_age, day, phase,
        )

    phase_progress = week_in_phase / max(1, phase_weeks - 1)

    if phase == "general":
        if phase_progress < 0.4:
            return long_easy(
                ladder, distance_range_km, is_beginner, training_age, day, phase,
            )
        if phase_progress < 0.7:
            if week_in_phase % 2 == 0:
                return long_run_moderate(
                    ladder, distance_range_km, is_beginner, training_age, day, phase,
                )
            return long_easy(
                ladder, distance_range_km, is_beginner, training_age, day, phase,
            )
        if week_in_phase % 2 == 0:
            return long_run_progression_finish(
                ladder, distance_range_km, is_beginner, training_age, day, phase,
            )
        return long_fast_stepwise(
            ladder, week_in_phase, phase_weeks, distance_range_km,
            is_beginner, training_age, day, phase,
        )

    phase_position = min(1.0, week_in_phase / max(1, phase_weeks - 1))

    # Supportive/specific long runs are always purposeful — no easy long
    # runs here. The 4-position rotation guarantees every long run has
    # a training stimulus, which is critical when long_run_is_workout=True
    # (B-week: the long run IS the quality session for that week).

    if goal_event == "marathon":
        rotation = quality_week_index % 4
        if rotation == 0:
            return long_run_mp(
                ladder, distance_range_km, week_in_phase, phase_weeks,
                is_beginner, training_age, day, phase,
            )
        elif rotation == 1:
            return long_run_fatigue_resistance(
                ladder, distance_range_km, phase_position,
                is_beginner, training_age, day, phase,
            )
        elif rotation == 2:
            return long_run_progression_finish(
                ladder, distance_range_km, is_beginner, training_age, day, phase,
            )
        else:
            return long_run_mp(
                ladder, distance_range_km, week_in_phase, phase_weeks,
                is_beginner, training_age, day, phase,
            )

    rotation = quality_week_index % 4
    if rotation == 0:
        return long_run_moderate(
            ladder, distance_range_km, is_beginner, training_age, day, phase,
        )
    elif rotation == 1:
        return long_fast_stepwise(
            ladder, week_in_phase, phase_weeks, distance_range_km,
            is_beginner, training_age, day, phase,
        )
    elif rotation == 2:
        return long_run_fatigue_resistance(
            ladder, distance_range_km, phase_position,
            is_beginner, training_age, day, phase,
        )
    else:
        return long_run_progression_finish(
            ladder, distance_range_km, is_beginner, training_age, day, phase,
        )


def _race_pace_zone(goal_event: Optional[str]) -> Optional[str]:
    """Determine which physiological zone is 'race pace' for this event.

    This is not a lookup table of workouts — it identifies the energy
    system the athlete will race at, so the specific phase can train it.
    """
    if goal_event in ("5K",):
        return "interval"       # VO2max / 5K pace
    if goal_event in ("10K",):
        return "threshold_high" # between threshold and VO2max
    if goal_event in ("half_marathon",):
        return "threshold"
    if goal_event in ("marathon",):
        return "marathon"
    if goal_event in ("50K", "50_mile", "100K", "100_mile"):
        return "steady"         # sub-threshold sustained
    return None


def _build_primary_quality(
    ladder: PaceLadder,
    day: int,
    phase: str,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    training_age: float,
    *,
    limiter: Optional[str] = None,
    primary_quality_emphasis: Optional[str] = None,
    goal_event: Optional[str] = None,
    week_num: int = 1,
    quality_week_index: int = 0,
) -> V2DayPlan:
    """Select primary midweek quality session.

    Derived from three inputs, not a lookup table:
      1. Phase purpose: general → full spectrum, supportive → bridge,
         specific → race-pace, taper → maintenance
      2. Goal event: determines what "race-pace" means (5K-pace, MP, etc.)
      3. Limiter: shifts which system gets extra emphasis

    quality_week_index increments only on non-cutback quality weeks,
    ensuring clean rotation without skipped variants.
    """
    if phase == "taper":
        return _taper_quality(
            ladder, day, phase, week_in_phase, phase_weeks,
            is_beginner, goal_event, week_num,
        )

    race_zone = _race_pace_zone(goal_event)

    if phase == "specific":
        return _specific_phase_quality(
            ladder, day, phase, week_in_phase, phase_weeks,
            is_beginner, training_age, race_zone, week_num,
            quality_week_index=quality_week_index,
        )

    if phase == "supportive":
        return _supportive_phase_quality(
            ladder, day, phase, week_in_phase, phase_weeks,
            is_beginner, training_age, limiter, race_zone, week_num,
            quality_week_index=quality_week_index,
        )

    return _general_phase_quality(
        ladder, day, phase, week_in_phase, phase_weeks,
        is_beginner, training_age, limiter, week_num, goal_event,
        quality_week_index=quality_week_index,
    )


def _taper_quality(
    ladder, day, phase, week_in_phase, phase_weeks,
    is_beginner, goal_event, week_num,
):
    """Event-aware taper quality.

    5K/10K: short, sharp opener at race effort. Race-rehearsal.
    HM: moderate threshold cruise, reduced volume.
    Marathon: week 1 of taper = short threshold, week 2 = strides only.
    Ultra: week 1 = short threshold, week 2 = easy strides.

    Second taper week (week_in_phase >= 1) is always lighter than first.
    """
    ext_denom = max(phase_weeks, week_num + 4)

    if week_in_phase >= 1:
        # Final week before race — sharp opener only
        if goal_event in ("5K", "10K"):
            return speed_support(ladder, week_num - 1, ext_denom, is_beginner, day, phase)
        return easy_with_strides(ladder, (5.0 * MI_TO_KM, 8.0 * MI_TO_KM), is_beginner, day, phase)

    # First taper week
    if goal_event in ("5K", "10K"):
        return vo2max_intervals(ladder, week_num - 1, ext_denom, is_beginner, day, phase)
    if goal_event == "half_marathon":
        return threshold_cruise(ladder, week_num - 1, ext_denom, is_beginner, day, phase)
    # Marathon / ultra
    return threshold_cruise(ladder, 0, 4, is_beginner, day, phase)


def _general_phase_quality(
    ladder, day, phase, week_in_phase, phase_weeks,
    is_beginner, training_age, limiter, week_num,
    goal_event=None, *, quality_week_index: int = 0,
):
    """General phase: full spectrum, but EVENT-BIASED.

    The general phase builds the physiological base relevant to the event:
      - 5K/10K: more speed/VO2max exposure early, threshold secondary
      - HM: balanced threshold + speed
      - Marathon: sustained aerobic + threshold emphasis
      - Ultra: economy + threshold emphasis

    Limiter further shifts emphasis within this event bias.
    Uses quality_week_index for rotation to avoid cutback-induced skips.
    """
    # General phase always leads with threshold — it's the aerobic
    # foundation for every event. Event-specific speed/VO2 emphasis
    # belongs in supportive and specific phases, not general.
    if goal_event in ("5K", "10K"):
        systems = ["threshold", "vo2max", "speed", "economy"]
    elif goal_event in ("50K", "50_mile", "100K", "100_mile"):
        systems = ["threshold", "economy", "vo2max", "speed"]
    elif goal_event == "marathon":
        systems = ["threshold", "economy", "vo2max", "speed"]
    else:
        systems = ["threshold", "vo2max", "economy", "speed"]

    if limiter == "threshold":
        systems.remove("threshold")
        systems.insert(0, "threshold")
    elif limiter == "speed":
        systems.remove("vo2max")
        systems.insert(0, "vo2max")
    elif limiter == "volume":
        systems.remove("economy")
        systems.insert(0, "economy")

    if phase_weeks > 4 and week_in_phase >= phase_weeks - 2:
        race_zone = _race_pace_zone(goal_event)
        if race_zone in ("interval", "threshold_high"):
            systems.insert(0, "vo2max")
        elif race_zone == "marathon":
            systems.insert(0, "economy")
        else:
            systems.insert(0, "threshold")

    pick = systems[quality_week_index % len(systems)]
    return _workout_for_system(
        pick, ladder, day, phase, week_in_phase, phase_weeks,
        is_beginner, training_age, week_num,
        quality_week_index=quality_week_index,
    )


def _supportive_phase_quality(
    ladder, day, phase, week_in_phase, phase_weeks,
    is_beginner, training_age, limiter, race_zone, week_num,
    *, quality_week_index: int = 0,
):
    """Supportive phase: threshold-dominant with race-system exposure.

    Alternates between threshold work and the race-pace system.
    Uses quality_week_index for clean rotation.
    """
    if quality_week_index % 2 == 0:
        return _workout_for_system(
            "threshold", ladder, day, phase, week_in_phase, phase_weeks,
            is_beginner, training_age, week_num,
            quality_week_index=quality_week_index,
        )
    else:
        target = "vo2max" if race_zone in ("interval", "threshold_high") else "speed"
        return _workout_for_system(
            target, ladder, day, phase, week_in_phase, phase_weeks,
            is_beginner, training_age, week_num,
            quality_week_index=quality_week_index,
        )


def _specific_phase_quality(
    ladder, day, phase, week_in_phase, phase_weeks,
    is_beginner, training_age, race_zone, week_num,
    *, quality_week_index: int = 0,
):
    """Specific phase: race-pace is the primary session.

    The workout IS at race pace for the goal event:
      - 5K event → VO2max/5K-pace intervals (1K-1.6K repeats)
      - 10K event → sustained VO2max/threshold (2K-3K repeats)
      - HM event → threshold cruise/alt-km at HM effort
      - Marathon event → MP alternating km or progression
      - Ultra → steady sustained work

    Uses quality_week_index for variant cycling. ext_denom is
    phase-relative so extension spans 0→1 within the specific phase.
    """
    ext_denom = phase_weeks
    ext_pos = quality_week_index

    if race_zone == "interval":
        variant = quality_week_index % 3
        if variant == 0:
            return vo2max_intervals(ladder, ext_pos, ext_denom, is_beginner, day, phase)
        elif variant == 1:
            return speed_support(ladder, ext_pos, ext_denom, is_beginner, day, phase)
        return micro_intervals(ladder, ext_pos, ext_denom, is_beginner, day, phase)

    if race_zone == "threshold_high":
        variant = quality_week_index % 3
        if variant == 0:
            return speed_support(ladder, ext_pos, ext_denom, is_beginner, day, phase)
        elif variant == 1:
            return threshold_alt_km(ladder, ext_pos, ext_denom, is_beginner, day, phase)
        return vo2max_intervals(ladder, ext_pos, ext_denom, is_beginner, day, phase)

    if race_zone == "threshold":
        if quality_week_index % 2 == 0:
            return threshold_cruise(ladder, ext_pos, ext_denom, is_beginner, day, phase)
        return threshold_alt_km(ladder, ext_pos, ext_denom, is_beginner, day, phase)

    if race_zone == "marathon":
        if quality_week_index % 2 == 0:
            return marathon_pace_alt_km(
                ladder, ext_pos, ext_denom, is_beginner, training_age, day, phase,
            )
        return progression_run(ladder, 14.0, is_beginner, day, phase)

    variant = quality_week_index % 3
    if variant == 0:
        return threshold_cruise(ladder, ext_pos, ext_denom, is_beginner, day, phase)
    elif variant == 1:
        return threshold_alt_km(ladder, ext_pos, ext_denom, is_beginner, day, phase)
    return progression_run(ladder, 16.0, is_beginner, day, phase)


def _workout_for_system(
    system: str,
    ladder: PaceLadder,
    day: int,
    phase: str,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    training_age: float,
    week_num: int,
    *,
    quality_week_index: int = 0,
) -> V2DayPlan:
    """Build a concrete workout for a physiological system.

    Uses quality_week_index for within-system alternation so
    cutback weeks don't cause the same variant to repeat.
    """
    ext_denom = max(phase_weeks, week_num + 4)

    if system == "vo2max":
        if quality_week_index % 2 == 0:
            return vo2max_intervals(ladder, week_num - 1, ext_denom, is_beginner, day, phase)
        return micro_intervals(ladder, week_num - 1, ext_denom, is_beginner, day, phase)

    if system == "threshold":
        if quality_week_index % 2 == 0:
            return threshold_cruise(ladder, week_num - 1, ext_denom, is_beginner, day, phase)
        return threshold_alt_km(ladder, week_num - 1, ext_denom, is_beginner, day, phase)

    if system == "economy":
        if quality_week_index % 2 == 0:
            return progression_run(ladder, 12.0, is_beginner, day, phase)
        return steady_run(ladder, (8.0, 13.0), is_beginner, day, phase)

    if system == "speed":
        if quality_week_index % 2 == 0:
            return speed_support(ladder, week_num - 1, ext_denom, is_beginner, day, phase)
        return micro_intervals(ladder, week_num - 1, ext_denom, is_beginner, day, phase)

    return threshold_cruise(ladder, week_num - 1, ext_denom, is_beginner, day, phase)


def _limiter_to_component(
    limiter: Optional[str],
    emphasis: Optional[str],
) -> Optional[str]:
    """Map limiter/emphasis to the component that needs more exposure."""
    if emphasis:
        mapping = {
            "threshold": "threshold", "lactate_threshold": "threshold",
            "speed": "vo2max", "vo2max": "vo2max",
            "endurance": "economy", "aerobic": "economy",
            "economy": "economy",
        }
        return mapping.get(emphasis)

    if limiter:
        mapping = {
            "volume": "economy",
            "threshold": "threshold",
            "speed": "vo2max",
        }
        return mapping.get(limiter)

    return None


def _build_secondary_quality(
    ladder: PaceLadder,
    day: int,
    phase: str,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    *,
    limiter: Optional[str] = None,
    goal_event: Optional[str] = None,
    quality_week_index: int = 0,
) -> V2DayPlan:
    """Secondary quality complements the primary by targeting a different system."""
    race_zone = _race_pace_zone(goal_event)

    if phase == "specific":
        # Specific: secondary is regenerative (touch quality, don't push)
        return regenerative_threshold(ladder, is_beginner, day, phase)

    if phase == "supportive":
        # Supportive: secondary covers what primary doesn't
        if race_zone in ("interval", "threshold_high"):
            return threshold_cruise(ladder, week_in_phase, phase_weeks, is_beginner, day, phase)
        return vo2max_intervals(ladder, week_in_phase, phase_weeks, is_beginner, day, phase)

    # General: secondary complements the limiter
    if limiter == "threshold":
        return vo2max_intervals(ladder, week_in_phase, phase_weeks, is_beginner, day, phase)
    if limiter == "speed":
        return threshold_cruise(ladder, week_in_phase, phase_weeks, is_beginner, day, phase)
    return vo2max_intervals(ladder, week_in_phase, phase_weeks, is_beginner, day, phase)
