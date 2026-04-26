"""
Build/Maintain mode workout builders.

Each mode has its own weekly template. These are NOT phase-based
(General → Supportive → Specific) — they are block-based with
fixed week roles.

Modes:
  - Onramp: time-based, run/hike → continuous, 4 runs/wk
  - Build-Volume: 6-week repeating block, 1 quality/wk (Wed threshold)
  - Build-Intensity: 4-week block, 2 quality/wk, extension progression
  - Maintain: 4-week block, flat volume, rotating quality
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .effort_mapper import describe_segment, map_effort
from .models import (
    FuelingPlan,
    PaceLadder,
    V2DayPlan,
    WorkoutSegment,
)
from .pace_ladder import format_pace_sec_km
from .segments_builder import (
    _resolve_pace,
    warmup,
    cooldown,
    work_segment,
    jog_rest,
    stride_segment,
    steady_segment,
    hike_segment,
)
from .workout_library import (
    _fueling_for_duration,
    _est_duration_min,
    rest_day,
    easy_run,
    threshold_cruise,
    vo2max_intervals,
    speed_support,
    micro_intervals,
    progression_run,
    regenerative_threshold,
    steady_run,
    flat_strides,
    uphill_strides,
    long_easy,
    long_fast_stepwise,
    MI_TO_KM,
)
from .volume import easy_run_range_km

logger = logging.getLogger(__name__)


# ── Onramp Mode ──────────────────────────────────────────────────────
#
# 8 weeks, 4 runs/week, time-based prescription.
# Weeks 1-4: run/hike on most days
# Weeks 5-6: transition to continuous running
# Weeks 7-8: continuous running, longer durations
#
# From Algorithm Spec: distance-effort alternation — never increase
# both distance AND effort in the same week.

_ONRAMP_TEMPLATE = {
    # week_num: {day_of_week: (workout_type, duration_range_min)}
    1: {
        0: ("run_hike", (20, 25)),      # Mon
        2: ("run_hike", (20, 25)),      # Wed
        4: ("easy_timed", (15, 20)),    # Fri
        5: ("run_hike", (25, 30)),      # Sat (long)
    },
    2: {
        0: ("easy_timed", (20, 25)),
        2: ("easy_timed", (25, 30)),
        4: ("run_hike", (20, 25)),
        5: ("run_hike", (30, 35)),
    },
    3: {
        0: ("run_hike", (25, 30)),
        2: ("easy_with_strides_timed", (20, 25)),
        4: ("easy_timed", (20, 25)),
        5: ("run_hike", (30, 40)),
    },
    4: {
        0: ("easy_timed", (25, 30)),
        2: ("easy_timed", (25, 30)),
        4: ("easy_with_strides_timed", (20, 25)),
        5: ("run_hike", (35, 45)),
    },
    5: {
        0: ("easy_timed", (25, 30)),
        2: ("easy_mod_timed", (25, 30)),
        4: ("easy_timed", (20, 25)),
        5: ("easy_timed", (40, 50)),
    },
    6: {
        0: ("easy_timed", (25, 30)),
        2: ("easy_with_strides_timed", (25, 30)),
        4: ("easy_timed", (25, 30)),
        5: ("easy_timed", (45, 55)),
    },
    7: {
        0: ("easy_timed", (30, 35)),
        2: ("easy_mod_timed", (30, 35)),
        4: ("easy_with_strides_timed", (25, 30)),
        5: ("easy_timed", (50, 60)),
    },
    8: {
        0: ("easy_timed", (30, 35)),
        2: ("easy_mod_timed", (30, 40)),
        4: ("easy_timed", (30, 35)),
        5: ("easy_mod_timed", (55, 65)),
    },
}


def build_onramp_week(
    week_num: int,
    ladder: PaceLadder,
    is_beginner: bool,
    training_age: float,
) -> List[V2DayPlan]:
    """Build a complete onramp week — 4 run days, 3 rest/hike/xtrain."""
    template = _ONRAMP_TEMPLATE.get(week_num, _ONRAMP_TEMPLATE[8])
    days: List[V2DayPlan] = []

    for d in range(7):
        if d not in template:
            if d == 6:
                days.append(rest_day(d, "onramp"))
            elif d == 3:
                days.append(_hike_xtrain_day(d, week_num))
            elif d == 1:
                days.append(rest_day(d, "onramp"))
            else:
                days.append(rest_day(d, "onramp"))
            continue

        wtype, dur_range = template[d]
        day_plan = _build_onramp_day(
            wtype, dur_range, d, week_num, ladder, is_beginner, training_age,
        )
        days.append(day_plan)

    return days


def _build_onramp_day(
    wtype: str,
    dur_range: Tuple[int, int],
    day: int,
    week_num: int,
    ladder: PaceLadder,
    is_beginner: bool,
    training_age: float,
) -> V2DayPlan:
    """Build a single onramp day from the template."""
    effort = map_effort(80, is_beginner=True)

    if wtype == "run_hike":
        if week_num <= 2:
            pattern = "run 3min / walk 2min"
        elif week_num <= 4:
            pattern = "run 4min / walk 1min"
        else:
            pattern = "run 5min / walk 1min"

        return V2DayPlan(
            day_of_week=day,
            workout_type="run_hike",
            title=f"Run/hike ({dur_range[0]}-{dur_range[1]}min)",
            description=(
                f"{dur_range[0]}-{dur_range[1]} minutes total, alternating {pattern}. "
                f"Keep the running easy — {effort}. The walk breaks are part of the plan."
            ),
            phase="onramp",
            duration_range_min=dur_range,
        )

    if wtype == "easy_timed":
        return V2DayPlan(
            day_of_week=day,
            workout_type="easy_timed",
            title=f"Easy run ({dur_range[0]}-{dur_range[1]}min)",
            description=(
                f"{dur_range[0]}-{dur_range[1]} minutes continuous easy running — {effort}. "
                f"If you need a walk break, take it. No judgment."
            ),
            phase="onramp",
            duration_range_min=dur_range,
        )

    if wtype == "easy_mod_timed":
        mod_effort = map_effort(88, is_beginner=True)
        return V2DayPlan(
            day_of_week=day,
            workout_type="easy_mod_timed",
            title=f"Moderate run ({dur_range[0]}-{dur_range[1]}min)",
            description=(
                f"{dur_range[0]}-{dur_range[1]} minutes at {mod_effort}. "
                f"Slightly harder than your easy pace — you should still be able to talk."
            ),
            phase="onramp",
            duration_range_min=dur_range,
        )

    if wtype == "easy_with_strides_timed":
        stride_effort = map_effort(120, is_beginner=True)
        return V2DayPlan(
            day_of_week=day,
            workout_type="easy_strides_timed",
            title=f"Easy + strides ({dur_range[0]}-{dur_range[1]}min)",
            description=(
                f"{dur_range[0]}-{dur_range[1]} minutes easy running — {effort}. "
                f"In the last 5 minutes, add 4x15s pickups ({stride_effort}) "
                f"with full walk-back recovery. These wake up the legs."
            ),
            phase="onramp",
            duration_range_min=dur_range,
        )

    return V2DayPlan(
        day_of_week=day,
        workout_type="easy_timed",
        title=f"Easy ({dur_range[0]}-{dur_range[1]}min)",
        description=f"{dur_range[0]}-{dur_range[1]} minutes easy — {effort}.",
        phase="onramp",
        duration_range_min=dur_range,
    )


def _hike_xtrain_day(day: int, week_num: int) -> V2DayPlan:
    """Hike or cross-training day for onramp."""
    return V2DayPlan(
        day_of_week=day,
        workout_type="hike_xtrain",
        title="Hike or cross-training",
        description=(
            "30-45 minutes of hiking, cycling, swimming, or any non-impact "
            "activity. Keep it easy. This builds aerobic fitness without "
            "the pounding of running."
        ),
        phase="onramp",
        duration_range_min=(30, 45),
    )


# ── Build-Volume Mode ────────────────────────────────────────────────
#
# 6-week repeating blocks, ONE quality session per week (Wed).
# Algorithm Spec: fixed weekly template from SWAP Long-Term Base Building.

_VOLUME_WEEK_ROLES = {
    1: {"wed": "easy_mod",      "long": "easy_mod",  "character": "Rebuild from range floor"},
    2: {"wed": "threshold_n",   "long": "hills",     "character": "Structured quality"},
    3: {"wed": "easy_volume",   "long": "strides",   "character": "Absorb"},
    4: {"wed": "threshold_n+2", "long": "hills",     "character": "Extension step"},
    5: {"wed": "easy_mod",      "long": "peak_easy",  "character": "Aerobic peak"},
    6: {"wed": "threshold_10m", "long": "hills_peak", "character": "Rep duration jump"},
}


def build_volume_week(
    week_in_block: int,
    ladder: PaceLadder,
    bank,
    is_beginner: bool,
    training_age: float,
    weekly_target_km: float,
    long_range_km: Tuple[float, float],
    is_bonus_week: bool = False,
    previous_peak_state: Optional[dict] = None,
) -> List[V2DayPlan]:
    """Build a complete Build-Volume week.

    Uses the fixed 6-week template from the spec.
    Bonus week is a supercompensation workout, not high volume.
    """
    if is_bonus_week:
        return _build_bonus_week(
            ladder, bank, is_beginner, training_age,
            weekly_target_km, long_range_km,
        )

    role = _VOLUME_WEEK_ROLES.get(week_in_block, _VOLUME_WEEK_ROLES[1])
    days: List[V2DayPlan] = []

    # Seed threshold reps from peak state or defaults
    base_threshold_reps = 3
    if previous_peak_state and "threshold" in previous_peak_state:
        base_threshold_reps = previous_peak_state["threshold"].get("reps", 3)

    for d in range(7):
        if d == 0:
            days.append(rest_day(d, "build_volume"))
        elif d == 1:
            rng = easy_run_range_km(weekly_target_km, "easy")
            days.append(easy_run(ladder, rng, is_beginner, d, "build_volume"))
        elif d == 2:
            # Wednesday: the ONE quality session
            days.append(_build_volume_wednesday(
                role["wed"], ladder, is_beginner, training_age,
                base_threshold_reps, d, weekly_target_km,
            ))
        elif d == 3:
            # Thursday: prescribed cross-training (not rest)
            days.append(V2DayPlan(
                day_of_week=d,
                workout_type="cross_train",
                title="Cross-training (Z2)",
                description=(
                    "30-60 minutes of Z2 aerobic work on a non-impact modality: "
                    "bike, swim, elliptical, or rower. This is a prescribed session, "
                    "not a rest day."
                ),
                phase="build_volume",
                duration_range_min=(30, 60),
            ))
        elif d == 4:
            rng = easy_run_range_km(weekly_target_km, "easy")
            days.append(easy_run(ladder, rng, is_beginner, d, "build_volume"))
        elif d == 5:
            # Saturday: long run (varies by week role)
            days.append(_build_volume_long_run(
                role["long"], ladder, is_beginner, training_age,
                long_range_km, d,
            ))
        elif d == 6:
            # Sunday: aerobic flex
            rng = easy_run_range_km(weekly_target_km, "easy")
            days.append(V2DayPlan(
                day_of_week=d,
                workout_type="aerobic_flex",
                title="Aerobic flex",
                description="Easy run, hike with hills, or cross-training. Your choice.",
                phase="build_volume",
                distance_range_km=rng,
            ))

    return days


def _build_volume_wednesday(
    role: str,
    ladder: PaceLadder,
    is_beginner: bool,
    training_age: float,
    base_reps: int,
    day: int,
    weekly_target_km: float,
) -> V2DayPlan:
    """Build the Wednesday quality session for Build-Volume."""
    if role == "easy_mod":
        rng = easy_run_range_km(weekly_target_km, "easy")
        effort = map_effort(88, is_beginner=is_beginner)
        return V2DayPlan(
            day_of_week=day,
            workout_type="easy_mod",
            title="Easy/moderate run",
            description=f"Easy to moderate — {effort}. Not a workout, just honest volume.",
            phase="build_volume",
            distance_range_km=rng,
        )

    if role == "easy_volume":
        rng = easy_run_range_km(weekly_target_km, "easy")
        effort = map_effort(80, is_beginner=is_beginner)
        return V2DayPlan(
            day_of_week=day,
            workout_type="easy_volume",
            title="Easy volume day",
            description=f"Easy — {effort}. Let the body absorb the previous weeks.",
            phase="build_volume",
            distance_range_km=rng,
        )

    if role == "threshold_n":
        # N × 5min at threshold
        reps = base_reps
        return threshold_cruise(ladder, 0, 6, is_beginner, day, "build_volume")

    if role == "threshold_n+2":
        # (N+2) × 5min at threshold — extension step
        return threshold_cruise(ladder, 3, 6, is_beginner, day, "build_volume")

    if role == "threshold_10m":
        # N × 10min at threshold — rep duration jump
        return threshold_cruise(ladder, 5, 6, is_beginner, day, "build_volume")

    rng = easy_run_range_km(weekly_target_km, "easy")
    return easy_run(ladder, rng, is_beginner, day, "build_volume")


def _build_volume_long_run(
    role: str,
    ladder: PaceLadder,
    is_beginner: bool,
    training_age: float,
    long_range_km: Tuple[float, float],
    day: int,
) -> V2DayPlan:
    """Build the Saturday long run for Build-Volume."""
    if role == "easy_mod":
        effort = map_effort(85, is_beginner=is_beginner)
        est_min = _est_duration_min(
            (long_range_km[0] + long_range_km[1]) / 2, ladder.easy,
        )
        fueling = _fueling_for_duration(est_min, training_age)
        desc = f"Long run — {effort}. Through hills if you can find them."
        if fueling:
            desc += f"\n{fueling.notes}"
        return V2DayPlan(
            day_of_week=day,
            workout_type="long_easy_mod",
            title="Long easy/moderate",
            description=desc,
            phase="build_volume",
            distance_range_km=long_range_km,
            fueling=fueling,
        )

    if role in ("hills", "hills_peak"):
        return long_easy(
            ladder, long_range_km, is_beginner, training_age, day, "build_volume",
        )

    if role == "strides":
        effort = map_effort(80, is_beginner=is_beginner)
        stride_effort = map_effort(120, is_beginner=is_beginner)
        est_min = _est_duration_min(
            (long_range_km[0] + long_range_km[1]) / 2, ladder.easy,
        )
        fueling = _fueling_for_duration(est_min, training_age)
        desc = (
            f"Long easy — {effort}. "
            f"Add 6x20s hill strides ({stride_effort}) in the last 2km."
        )
        if fueling:
            desc += f"\n{fueling.notes}"
        return V2DayPlan(
            day_of_week=day,
            workout_type="long_easy_strides",
            title="Long easy + hill strides",
            description=desc,
            phase="build_volume",
            distance_range_km=long_range_km,
            fueling=fueling,
        )

    if role == "peak_easy":
        return long_easy(
            ladder, long_range_km, is_beginner, training_age, day, "build_volume",
        )

    return long_easy(
        ladder, long_range_km, is_beginner, training_age, day, "build_volume",
    )


def _build_bonus_week(
    ladder: PaceLadder,
    bank,
    is_beginner: bool,
    training_age: float,
    weekly_target_km: float,
    long_range_km: Tuple[float, float],
) -> List[V2DayPlan]:
    """Supercompensation bonus week.

    NOT a high-volume week. One extremely difficult session (Wednesday)
    that intentionally causes breakdown, surrounded by easy days.
    Saturday long run has sustained MP/threshold work.
    """
    days: List[V2DayPlan] = []

    for d in range(7):
        if d == 0:
            days.append(rest_day(d, "build_volume"))
        elif d == 2:
            # Wednesday: supercompensation session — micro-intervals
            days.append(micro_intervals(
                ladder, 5, 6, is_beginner, d, "build_volume",
            ))
        elif d == 5:
            # Saturday: long run with sustained hard effort
            target_km = (long_range_km[0] + long_range_km[1]) / 2.0
            easy_km = round(target_km * 0.45, 1)
            hard_km = round(target_km * 0.35, 1)
            finish_km = round(target_km * 0.20, 1)

            mp_effort = describe_segment(100, ladder.marathon, is_beginner=is_beginner)
            mp_pace_mi = format_pace_sec_km(ladder.marathon, "mi")

            segments = [
                WorkoutSegment(
                    type="easy", pace_pct_mp=80, pace_sec_per_km=ladder.easy,
                    distance_km=easy_km,
                    description=describe_segment(80, ladder.easy, is_beginner=is_beginner),
                ),
                work_segment(
                    ladder, 100, zone="marathon", distance_km=hard_km,
                    is_beginner=is_beginner,
                ),
                WorkoutSegment(
                    type="easy", pace_pct_mp=80, pace_sec_per_km=ladder.easy,
                    distance_km=finish_km,
                    description=describe_segment(80, ladder.easy, is_beginner=is_beginner),
                ),
            ]

            est_min = _est_duration_min(target_km, ladder.easy)
            fueling = _fueling_for_duration(est_min, training_age)

            desc = (
                f"Supercompensation long run: {easy_km:.0f}km easy, then "
                f"{hard_km:.0f}km at {mp_effort} ({mp_pace_mi}/mi), "
                f"then {finish_km:.0f}km easy. This is the hardest session "
                f"of the block — controlled overreach."
            )
            if fueling:
                desc += f"\n{fueling.notes}"

            days.append(V2DayPlan(
                day_of_week=d,
                workout_type="supercompensation_long",
                title=f"Supercomp long run ({target_km:.0f}km)",
                description=desc,
                phase="build_volume",
                segments=segments,
                distance_range_km=long_range_km,
                fueling=fueling,
            ))
        elif d == 6:
            days.append(rest_day(d, "build_volume"))
        else:
            rng = easy_run_range_km(weekly_target_km, "easy_short")
            days.append(easy_run(ladder, rng, is_beginner, d, "build_volume"))

    return days


# ── Build-Intensity Mode ─────────────────────────────────────────────
#
# 4-week blocks, 2 quality sessions per week.
# Extension progression on speed + threshold.
# W4 is cutback.

def build_intensity_week(
    week_in_block: int,
    ladder: PaceLadder,
    bank,
    is_beginner: bool,
    training_age: float,
    weekly_target_km: float,
    long_range_km: Tuple[float, float],
    block_number: int = 1,
    previous_peak_state: Optional[dict] = None,
) -> List[V2DayPlan]:
    """Build a complete Build-Intensity week.

    W1-W3: progressive extension, 2 quality sessions.
    W4: cutback — strides only, reduced volume.
    """
    is_cutback = (week_in_block == 4)
    phase_weeks = 3  # W1-W3 are the extension window
    w = min(week_in_block - 1, 2)  # 0-indexed, capped at W3

    days: List[V2DayPlan] = []

    # Quality type rotation across blocks
    block_focus = _intensity_block_focus(block_number)

    # A/B structure: if long run is a workout, drop to 1 midweek quality
    progress = min(1.0, w / max(1, phase_weeks - 1))
    long_run_is_workout = not is_cutback and progress >= 0.5

    for d in range(7):
        if d == 0:
            days.append(rest_day(d, "build"))
        elif d == 2:
            # Wednesday: quality 1 (midweek)
            if is_cutback:
                rng = easy_run_range_km(weekly_target_km, "easy")
                days.append(flat_strides(ladder, rng, is_beginner, d, "build"))
            else:
                days.append(_intensity_midweek(
                    block_focus, ladder, w, phase_weeks, is_beginner, d,
                    training_age,
                ))
        elif d == 4:
            # Friday: quality 2 — skip when long run is a workout (A/B alternation)
            if is_cutback or long_run_is_workout:
                rng = easy_run_range_km(weekly_target_km, "easy")
                days.append(easy_run(ladder, rng, is_beginner, d, "build"))
            else:
                days.append(_intensity_secondary(
                    block_focus, ladder, w, phase_weeks, is_beginner, d,
                ))
        elif d == 5:
            # Saturday: long run with progression
            if is_cutback:
                reduced_range = (
                    long_range_km[0] * 0.80,
                    long_range_km[1] * 0.80,
                )
                days.append(long_easy(
                    ladder, reduced_range, is_beginner, training_age, d, "build",
                ))
            else:
                days.append(_intensity_long_run(
                    ladder, w, phase_weeks, is_beginner, training_age,
                    long_range_km, d,
                ))
        elif d == 6:
            days.append(rest_day(d, "build"))
        else:
            rng = easy_run_range_km(weekly_target_km, "easy")
            days.append(easy_run(ladder, rng, is_beginner, d, "build"))

    return days


def _intensity_block_focus(block_number: int) -> str:
    """Rotate quality type across blocks."""
    rotation = ["threshold", "speed", "mixed"]
    return rotation[(block_number - 1) % len(rotation)]


def _intensity_midweek(
    focus: str,
    ladder: PaceLadder,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    day: int,
    training_age: float,
) -> V2DayPlan:
    """Midweek quality session for Build-Intensity."""
    if focus == "threshold":
        return threshold_cruise(ladder, week_in_phase, phase_weeks, is_beginner, day, "build")
    if focus == "speed":
        return speed_support(ladder, week_in_phase, phase_weeks, is_beginner, day, "build")
    # mixed: alternate
    if week_in_phase % 2 == 0:
        return threshold_cruise(ladder, week_in_phase, phase_weeks, is_beginner, day, "build")
    return speed_support(ladder, week_in_phase, phase_weeks, is_beginner, day, "build")


def _intensity_secondary(
    focus: str,
    ladder: PaceLadder,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    day: int,
) -> V2DayPlan:
    """Secondary quality session — complement the primary."""
    if focus == "threshold":
        return vo2max_intervals(ladder, week_in_phase, phase_weeks, is_beginner, day, "build")
    if focus == "speed":
        return threshold_cruise(ladder, week_in_phase, phase_weeks, is_beginner, day, "build")
    # mixed: opposite of midweek
    if week_in_phase % 2 == 0:
        return vo2max_intervals(ladder, week_in_phase, phase_weeks, is_beginner, day, "build")
    return threshold_cruise(ladder, week_in_phase, phase_weeks, is_beginner, day, "build")


def _intensity_long_run(
    ladder: PaceLadder,
    week_in_phase: int,
    phase_weeks: int,
    is_beginner: bool,
    training_age: float,
    long_range_km: Tuple[float, float],
    day: int,
) -> V2DayPlan:
    """Long run for Build-Intensity: easy → fast finish → stepwise."""
    progress = min(1.0, week_in_phase / max(1, phase_weeks - 1))

    if progress < 0.5:
        return long_easy(
            ladder, long_range_km, is_beginner, training_age, day, "build",
        )
    return long_fast_stepwise(
        ladder, week_in_phase, phase_weeks, long_range_km,
        is_beginner, training_age, day, "build",
    )


# ── Maintain Mode ────────────────────────────────────────────────────
#
# 4-week blocks, flat volume, rotating quality types.
# W1: threshold, W2: intervals, W3: fartlek/progression, W4: cutback

def build_maintain_week(
    week_in_block: int,
    ladder: PaceLadder,
    bank,
    is_beginner: bool,
    training_age: float,
    weekly_target_km: float,
    long_range_km: Tuple[float, float],
) -> List[V2DayPlan]:
    """Build a Maintain mode week — flat volume, rotating quality."""
    is_cutback = (week_in_block == 4)
    days: List[V2DayPlan] = []

    for d in range(7):
        if d == 0:
            days.append(rest_day(d, "maintain"))
        elif d == 2:
            # Wednesday: rotating quality
            if is_cutback:
                rng = easy_run_range_km(weekly_target_km, "easy")
                days.append(flat_strides(ladder, rng, is_beginner, d, "maintain"))
            else:
                days.append(_maintain_quality(
                    week_in_block, ladder, is_beginner, d,
                ))
        elif d == 5:
            # Saturday: long run (flat distance, rotate type)
            if is_cutback:
                reduced = (long_range_km[0] * 0.85, long_range_km[1] * 0.85)
                days.append(long_easy(
                    ladder, reduced, is_beginner, training_age, d, "maintain",
                ))
            else:
                days.append(long_easy(
                    ladder, long_range_km, is_beginner, training_age, d, "maintain",
                ))
        elif d == 6:
            days.append(rest_day(d, "maintain"))
        else:
            rng = easy_run_range_km(weekly_target_km, "easy")
            days.append(easy_run(ladder, rng, is_beginner, d, "maintain"))

    return days


def _maintain_quality(
    week_in_block: int,
    ladder: PaceLadder,
    is_beginner: bool,
    day: int,
) -> V2DayPlan:
    """Rotating quality session for Maintain mode."""
    if week_in_block == 1:
        return threshold_cruise(ladder, 0, 4, is_beginner, day, "maintain")
    if week_in_block == 2:
        return vo2max_intervals(ladder, 0, 4, is_beginner, day, "maintain")
    if week_in_block == 3:
        return progression_run(ladder, 12.0, is_beginner, day, "maintain")
    return regenerative_threshold(ladder, is_beginner, day, "maintain")


# ── Peak Workout State ───────────────────────────────────────────────

def compute_peak_workout_state(weeks: List) -> dict:
    """Extract multi-dimensional peak state from a completed block.

    Captures: peak long run distance, peak threshold segment duration,
    peak interval rep count/distance, and peak weekly volume.
    """
    state: Dict[str, dict] = {
        "speed": {
            "segment_distance_km": 0.0,
            "reps": 0,
            "total_work_km": 0.0,
        },
        "threshold": {
            "segment_duration_min": 0.0,
            "reps": 0,
            "total_work_km": 0.0,
        },
        "long_run": {
            "max_distance_km": 0.0,
            "peak_pace_pct_mp": 0,
        },
        "weekly_volume": {
            "peak_km": 0.0,
        },
    }

    for week in weeks:
        week_vol = 0.0
        for day in week.days:
            # Track distance
            if day.distance_range_km:
                mid = (day.distance_range_km[0] + day.distance_range_km[1]) / 2
                week_vol += mid

            if not day.segments:
                continue

            if day.workout_type in ("long_easy", "long_fast_stepwise",
                                     "long_run_fatigue_resistance",
                                     "supercompensation_long"):
                total_km = sum(
                    s.distance_km for s in day.segments if s.distance_km
                )
                if total_km > state["long_run"]["max_distance_km"]:
                    state["long_run"]["max_distance_km"] = round(total_km, 1)
                peak_pct = max(
                    (s.pace_pct_mp for s in day.segments if s.type == "work"),
                    default=0,
                )
                if peak_pct > state["long_run"]["peak_pace_pct_mp"]:
                    state["long_run"]["peak_pace_pct_mp"] = peak_pct

            if day.workout_type in ("speed_support", "vo2max_intervals",
                                     "micro_intervals"):
                work_segs = [s for s in day.segments if s.type == "work"]
                for s in work_segs:
                    if s.distance_km and s.distance_km > state["speed"]["segment_distance_km"]:
                        state["speed"]["segment_distance_km"] = round(s.distance_km, 2)
                if len(work_segs) > state["speed"]["reps"]:
                    state["speed"]["reps"] = len(work_segs)
                total = sum(s.distance_km for s in work_segs if s.distance_km)
                if total > state["speed"]["total_work_km"]:
                    state["speed"]["total_work_km"] = round(total, 1)

            if day.workout_type in ("threshold_cruise", "threshold_alt_km",
                                     "regenerative"):
                work_segs = [s for s in day.segments if s.type == "work"]
                for s in work_segs:
                    if s.duration_min and s.duration_min > state["threshold"]["segment_duration_min"]:
                        state["threshold"]["segment_duration_min"] = round(s.duration_min, 1)
                if len(work_segs) > state["threshold"]["reps"]:
                    state["threshold"]["reps"] = len(work_segs)
                total = sum(s.distance_km for s in work_segs if s.distance_km)
                if total > state["threshold"]["total_work_km"]:
                    state["threshold"]["total_work_km"] = round(total, 1)

        if week_vol > state["weekly_volume"]["peak_km"]:
            state["weekly_volume"]["peak_km"] = round(week_vol, 1)

    return state
