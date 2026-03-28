"""
N=1 Plan Engine

Single engine producing individualized training plans for athletes
from beginner through elite, 5K through marathon.

Architecture (5 steps):
1. Athlete State Resolution
2. Phase Schedule
3. Volume + Long Run Curves
4. Quality Session Scheduling
5. Day-by-Day Assembly

See: docs/specs/N1_PLAN_ENGINE_SPEC.md
See: docs/specs/N1_ENGINE_BUILD_PLAN.md
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from services.fitness_bank import ExperienceLevel
from services.workout_prescription import (
    DayPlan,
    WeekPlan,
    calculate_paces_from_rpi,
    format_pace,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

LONG_RUN_CEILING: Dict[str, float] = {
    "marathon": 22.0,
    "half_marathon": 17.0,
    "10k": 18.0,
    "5k": 15.0,
}

LONG_RUN_CEILING_SLOW_MARATHON = 20.0
MARATHON_LR_FLOOR = 14.0

MLR_RATIO = 0.75
MLR_CAP = 15.0
MLR_MIN_WEEKLY_VOLUME = 40.0

VOLUME_STEP_CEILING: Dict[ExperienceLevel, float] = {
    ExperienceLevel.BEGINNER: 3.0,
    ExperienceLevel.INTERMEDIATE: 5.0,
    ExperienceLevel.EXPERIENCED: 6.0,
    ExperienceLevel.ELITE: 8.0,
}

LR_STEP: Dict[ExperienceLevel, float] = {
    ExperienceLevel.BEGINNER: 1.5,
    ExperienceLevel.INTERMEDIATE: 2.0,
    ExperienceLevel.EXPERIENCED: 2.5,
    ExperienceLevel.ELITE: 3.0,
}

CUTBACK_VOLUME_FACTOR = 0.75
LR_CUTBACK_FACTOR = 0.65
TAPER_VOLUME_FACTORS = [0.70, 0.50, 0.35]

TAPER_WEEKS: Dict[str, int] = {
    "marathon": 3,
    "half_marathon": 2,
    "10k": 2,
    "5k": 1,
}

WARMUP_COOLDOWN: Dict[ExperienceLevel, float] = {
    ExperienceLevel.BEGINNER: 2.0,
    ExperienceLevel.INTERMEDIATE: 3.0,
    ExperienceLevel.EXPERIENCED: 4.0,
    ExperienceLevel.ELITE: 4.0,
}

# T-block: 6-step threshold progression
# (reps, duration_min, rest_min)
T_BLOCK_STANDARD = [
    (6, 5, 2),
    (5, 6, 2),
    (4, 8, 2),
    (3, 10, 3),
    (2, 15, 3),
    (1, 35, 0),
]

T_BLOCK_OVERRIDES: Dict[Tuple[int, ExperienceLevel], Tuple[int, int]] = {
    (0, ExperienceLevel.BEGINNER): (4, 4),
    (0, ExperienceLevel.INTERMEDIATE): (5, 5),
    (5, ExperienceLevel.BEGINNER): (1, 20),
    (5, ExperienceLevel.INTERMEDIATE): (1, 30),
    (5, ExperienceLevel.EXPERIENCED): (1, 35),
    (5, ExperienceLevel.ELITE): (1, 40),
}

PHASE_PROPORTIONS: Dict[str, List[Tuple[str, float]]] = {
    "marathon": [("base", 0.17), ("build_1", 0.23), ("build_2", 0.30), ("peak", 0.30)],
    "half_marathon": [("base", 0.17), ("build_1", 0.25), ("build_2", 0.28), ("peak", 0.30)],
    "10k": [("base", 0.20), ("build", 0.45), ("peak", 0.35)],
    "5k": [("base", 0.20), ("build", 0.45), ("peak", 0.35)],
}


# ═══════════════════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════════════════

class ReadinessGateError(ValueError):
    """Raised when athlete doesn't meet minimum requirements for distance."""


# ═══════════════════════════════════════════════════════════════════════
# Step 1 — Athlete State Resolution
# ═══════════════════════════════════════════════════════════════════════

class TrainingRecency(Enum):
    NEW = "new"
    REBUILDING = "rebuilding"
    BUILDING = "building"
    MAINTAINING = "maintaining"


@dataclass
class AthleteState:
    current_weekly_miles: float
    current_long_run_miles: float
    peak_weekly_miles: float
    best_rpi: Optional[float]
    experience: ExperienceLevel
    days_per_week: int
    training_recency: TrainingRecency
    paces: Optional[Dict[str, float]]
    race_distance: str
    race_date: date
    plan_start: date
    horizon_weeks: int
    goal_time_seconds: Optional[int]
    is_slow_marathoner: bool
    is_abbreviated: bool
    is_day_one: bool


def _parse_goal_time(goal_time: Optional[str]) -> Optional[int]:
    if not goal_time:
        return None
    parts = goal_time.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        pass
    return None


def _determine_recency(
    current: float, peak: float, weeks_since_peak: int,
) -> TrainingRecency:
    if current <= 0:
        return TrainingRecency.NEW
    ratio = current / max(peak, 1.0)
    if ratio < 0.5 and weeks_since_peak > 8:
        return TrainingRecency.REBUILDING
    if ratio < 0.85:
        return TrainingRecency.BUILDING
    return TrainingRecency.MAINTAINING


def resolve_athlete_state(
    *,
    race_distance: str,
    race_date: date,
    plan_start: date,
    horizon_weeks: int,
    days_per_week: int,
    starting_vol: float,
    current_lr: float,
    applied_peak: float,
    experience: ExperienceLevel,
    best_rpi: Optional[float] = None,
    weeks_since_peak: int = 0,
    goal_time: Optional[str] = None,
) -> AthleteState:
    paces = None
    if best_rpi and best_rpi > 0:
        paces = calculate_paces_from_rpi(best_rpi)

    goal_secs = _parse_goal_time(goal_time)

    # Sub-3:45 marathon check — cap LR at 20mi for slower marathoners
    is_slow_marathoner = False
    if race_distance == "marathon":
        if goal_secs and goal_secs > 13500:
            is_slow_marathoner = True
        elif paces and paces.get("marathon", 0) > 8.58:
            is_slow_marathoner = True

    is_abbreviated = horizon_weeks <= 5
    is_day_one = starting_vol <= 0 and current_lr <= 0
    recency = _determine_recency(starting_vol, applied_peak, weeks_since_peak)

    if race_distance == "marathon" and not is_day_one and not is_abbreviated:
        if current_lr < 12:
            raise ReadinessGateError(
                f"Marathon readiness gate: current long run is {current_lr:.0f}mi. "
                "Must complete 12mi before starting a marathon program. "
                "Consider a base-building plan first."
            )

    if race_distance == "half_marathon" and not is_day_one:
        weeks_to_12 = max(0, math.ceil((12 - current_lr) / 2))
        if weeks_to_12 > horizon_weeks:
            raise ReadinessGateError(
                f"Half marathon readiness gate: current long run is {current_lr:.0f}mi. "
                f"Need {weeks_to_12} weeks to reach 12mi but only {horizon_weeks} available."
            )

    return AthleteState(
        current_weekly_miles=starting_vol,
        current_long_run_miles=current_lr,
        peak_weekly_miles=applied_peak,
        best_rpi=best_rpi,
        experience=experience,
        days_per_week=days_per_week,
        training_recency=recency,
        paces=paces,
        race_distance=race_distance,
        race_date=race_date,
        plan_start=plan_start,
        horizon_weeks=horizon_weeks,
        goal_time_seconds=goal_secs,
        is_slow_marathoner=is_slow_marathoner,
        is_abbreviated=is_abbreviated,
        is_day_one=is_day_one,
    )


# ═══════════════════════════════════════════════════════════════════════
# Step 2 — Phase Schedule
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PhaseWeek:
    week_number: int
    phase: str
    is_cutback: bool


def _allocate_phases(
    proportions: List[Tuple[str, float]],
    total_weeks: int,
    taper_weeks: int,
) -> List[PhaseWeek]:
    available = total_weeks - taper_weeks
    if available <= 0:
        return [PhaseWeek(w + 1, "taper", False) for w in range(total_weeks)]

    total_prop = sum(p for _, p in proportions)
    raw: List[Tuple[str, int]] = []
    for name, prop in proportions:
        weeks = max(1, round(available * prop / total_prop))
        raw.append((name, weeks))

    used = sum(w for _, w in raw)
    while used > available:
        for i in range(len(raw) - 1, -1, -1):
            name, w = raw[i]
            if w > 1:
                raw[i] = (name, w - 1)
                used -= 1
                break
        else:
            break
        if used <= available:
            break

    while used < available:
        name, w = raw[0]
        raw[0] = (name, w + 1)
        used += 1

    result: List[PhaseWeek] = []
    week_num = 1
    for idx, (phase_name, count) in enumerate(raw):
        for w in range(count):
            is_last = w == count - 1
            is_cutback = is_last and idx < len(raw) - 1 and count >= 3
            result.append(PhaseWeek(week_num, phase_name, is_cutback))
            week_num += 1

    for _ in range(taper_weeks):
        result.append(PhaseWeek(week_num, "taper", False))
        week_num += 1

    return result


def compute_phase_schedule(state: AthleteState) -> List[PhaseWeek]:
    if state.is_day_one:
        return [PhaseWeek(w + 1, "progression", False)
                for w in range(state.horizon_weeks)]

    if state.is_abbreviated:
        taper = 1
        peak = max(1, state.horizon_weeks - taper)
        result = [PhaseWeek(w + 1, "peak", False) for w in range(peak)]
        result.append(PhaseWeek(peak + 1, "taper", False))
        return result

    taper = TAPER_WEEKS.get(state.race_distance, 2)
    taper = min(taper, max(1, state.horizon_weeks - 3))

    proportions = PHASE_PROPORTIONS.get(
        state.race_distance,
        PHASE_PROPORTIONS["10k"],
    )

    return _allocate_phases(proportions, state.horizon_weeks, taper)


# ═══════════════════════════════════════════════════════════════════════
# Step 3 — Volume + Long Run Curves
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class WeekTargets:
    week_number: int
    phase: str
    is_cutback: bool
    weekly_miles: float
    long_run_miles: float
    medium_long_miles: float


def _first_index_of_phase(phases: List[PhaseWeek], phase_name: str) -> Optional[int]:
    for i, pw in enumerate(phases):
        if pw.phase == phase_name:
            return i
    return None


def compute_curves(
    state: AthleteState,
    phases: List[PhaseWeek],
) -> List[WeekTargets]:
    n = len(phases)
    vol_start = state.current_weekly_miles
    vol_peak = state.peak_weekly_miles
    step_max = VOLUME_STEP_CEILING.get(state.experience, 5.0)
    needs_ramp = vol_start < vol_peak * 0.95

    peak_idx = _first_index_of_phase(phases, "peak")
    if peak_idx is None:
        peak_idx = _first_index_of_phase(phases, "taper") or n
    taper_idx = _first_index_of_phase(phases, "taper")

    # ── Volume ────────────────────────────────────────────────────
    volumes: List[float] = []
    current_vol = vol_start
    vol_high_water = vol_start

    for i, pw in enumerate(phases):
        if pw.phase == "taper":
            offset = i - (taper_idx or i)
            factor = TAPER_VOLUME_FACTORS[min(offset, len(TAPER_VOLUME_FACTORS) - 1)]
            volumes.append(round(vol_high_water * factor, 1))
        elif pw.is_cutback:
            volumes.append(round(current_vol * CUTBACK_VOLUME_FACTOR, 1))
        elif needs_ramp and i < peak_idx:
            ramp_remaining = peak_idx - i
            step = min(step_max, (vol_peak - current_vol) / max(1, ramp_remaining))
            current_vol = min(vol_peak, current_vol + step)
            vol_high_water = max(vol_high_water, current_vol)
            volumes.append(round(current_vol, 1))
        else:
            current_vol = vol_peak
            vol_high_water = max(vol_high_water, current_vol)
            volumes.append(round(vol_peak, 1))

    # ── Long Run ──────────────────────────────────────────────────
    lr_ceiling = LONG_RUN_CEILING.get(state.race_distance, 18.0)
    if state.is_slow_marathoner:
        lr_ceiling = LONG_RUN_CEILING_SLOW_MARATHON

    lr_step = LR_STEP.get(state.experience, 2.0)

    lr_start = state.current_long_run_miles + 1
    if state.race_distance == "marathon":
        lr_start = max(MARATHON_LR_FLOOR, lr_start)

    daily_avg = vol_start / max(1, state.days_per_week)
    lr_start = max(lr_start, round(daily_avg * 1.5, 1))
    lr_start = min(lr_start, lr_ceiling)

    long_runs: List[float] = []
    current_lr = lr_start
    lr_high_water = lr_start
    lr_first_assigned = False

    for i, pw in enumerate(phases):
        if pw.phase == "taper":
            offset = i - (taper_idx or i)
            if offset == 0:
                long_runs.append(round(lr_high_water * 0.65, 1))
            else:
                long_runs.append(round(min(lr_high_water * 0.45, 8.0), 1))
        elif pw.is_cutback:
            long_runs.append(round(current_lr * LR_CUTBACK_FACTOR, 1))
        else:
            if lr_first_assigned:
                current_lr = min(lr_ceiling, current_lr + lr_step)
            lr_first_assigned = True
            lr_high_water = max(lr_high_water, current_lr)
            long_runs.append(round(current_lr, 1))

    # ── Medium-Long ───────────────────────────────────────────────
    medium_longs: List[float] = []
    for i, pw in enumerate(phases):
        wk_vol = volumes[i]
        lr = long_runs[i]
        if wk_vol >= MLR_MIN_WEEKLY_VOLUME and pw.phase != "taper":
            mlr = min(MLR_CAP, round(lr * MLR_RATIO, 1))
            medium_longs.append(mlr)
        else:
            medium_longs.append(0.0)

    return [
        WeekTargets(
            week_number=phases[i].week_number,
            phase=phases[i].phase,
            is_cutback=phases[i].is_cutback,
            weekly_miles=volumes[i],
            long_run_miles=long_runs[i],
            medium_long_miles=medium_longs[i],
        )
        for i in range(n)
    ]


# ═══════════════════════════════════════════════════════════════════════
# Step 4 — Quality Session Scheduling
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class QualityRx:
    workout_type: str
    name: str
    description: str
    miles: float
    intensity: str


def _pace_label(paces: Optional[Dict[str, float]], zone: str) -> str:
    if paces and zone in paces:
        return format_pace(paces[zone]) + "/mi"
    return {
        "easy": "easy effort",
        "marathon": "marathon effort",
        "threshold": "comfortably hard",
        "interval": "hard controlled effort",
        "recovery": "very easy",
    }.get(zone, "moderate effort")


def _t_block_session(
    step: int,
    experience: ExperienceLevel,
    paces: Optional[Dict[str, float]],
) -> QualityRx:
    step = min(step, 5)
    base_reps, base_dur, rest = T_BLOCK_STANDARD[step]
    override = T_BLOCK_OVERRIDES.get((step, experience))
    reps, dur = override if override else (base_reps, base_dur)

    pace = _pace_label(paces, "threshold")
    wu_cd = WARMUP_COOLDOWN.get(experience, 4.0)
    half_wc = round(wu_cd / 2, 1)

    if reps == 1:
        name = f"{dur}min continuous @ T"
        core = f"{dur}min continuous @ {pace}"
    else:
        name = f"{reps}x{dur}min @ T"
        core = f"{reps}x{dur}min @ {pace}, {rest}min jog"

    t_pace_val = paces.get("threshold", 7.0) if paces else 7.0
    quality_time = reps * dur
    quality_miles = quality_time / t_pace_val
    jog_miles = max(0, (reps - 1)) * rest / 9.0
    total = round(wu_cd + quality_miles + jog_miles, 1)

    desc = f"{half_wc:.0f}mi easy + {core} + {half_wc:.0f}mi easy"
    return QualityRx("threshold", name, desc, total, "hard")


def _interval_session(
    experience: ExperienceLevel,
    paces: Optional[Dict[str, float]],
) -> QualityRx:
    pace = _pace_label(paces, "interval")
    wu_cd = WARMUP_COOLDOWN.get(experience, 4.0)
    half_wc = round(wu_cd / 2, 1)

    configs = {
        ExperienceLevel.BEGINNER: ("4x400m", 5.0),
        ExperienceLevel.INTERMEDIATE: ("5x800m", 7.0),
        ExperienceLevel.EXPERIENCED: ("5x1000m", 9.0),
        ExperienceLevel.ELITE: ("6x1000m", 10.0),
    }
    name, miles = configs.get(experience, ("5x800m", 7.0))
    core = f"{name} @ {pace} w/ 400m jog"
    desc = f"{half_wc:.0f}mi easy + {core} + {half_wc:.0f}mi easy"
    return QualityRx("intervals", name, desc, miles, "hard")


def _reps_session(
    experience: ExperienceLevel,
    paces: Optional[Dict[str, float]],
) -> QualityRx:
    pace = _pace_label(paces, "interval")
    if experience == ExperienceLevel.ELITE:
        name = "8x300m reps"
        core = f"8x300m @ {pace} (1500m pace), full 90s rest"
        miles = 8.0
    else:
        name = "6x200m reps"
        core = f"6x200m @ {pace} (1500m pace), full 90s rest"
        miles = 7.0
    desc = f"2mi easy + {core} + 2mi easy"
    return QualityRx("repetitions", name, desc, miles, "hard")


def _mp_long_run(
    long_run_miles: float,
    mp_fraction: float,
    paces: Optional[Dict[str, float]],
) -> QualityRx:
    mp_miles = round(long_run_miles * mp_fraction, 1)
    easy_miles = round(long_run_miles - mp_miles, 1)
    mp_pace = _pace_label(paces, "marathon")
    easy_pace = _pace_label(paces, "easy")
    return QualityRx(
        "long_mp",
        f"{long_run_miles:.0f}mi w/ {mp_miles:.0f}mi @ MP",
        f"{easy_miles:.0f}mi @ {easy_pace} + {mp_miles:.0f}mi @ {mp_pace}",
        long_run_miles,
        "hard",
    )


def _hmp_long_run(
    long_run_miles: float,
    hmp_fraction: float,
    paces: Optional[Dict[str, float]],
) -> QualityRx:
    hmp_miles = round(long_run_miles * hmp_fraction, 1)
    easy_miles = round(long_run_miles - hmp_miles, 1)
    if paces:
        mp = paces.get("marathon", 7.5)
        tp = paces.get("threshold", 6.5)
        hmp_str = format_pace((mp + tp) / 2) + "/mi"
    else:
        hmp_str = "half marathon effort"
    easy_pace = _pace_label(paces, "easy")
    return QualityRx(
        "long_hmp",
        f"{long_run_miles:.0f}mi w/ {hmp_miles:.0f}mi @ HMP",
        f"{easy_miles:.0f}mi @ {easy_pace} + {hmp_miles:.0f}mi @ {hmp_str}",
        long_run_miles,
        "hard",
    )


def _weeks_of_phase(
    targets: List[WeekTargets], phase: str, *, exclude_cutback: bool = True,
) -> List[WeekTargets]:
    return [w for w in targets if w.phase == phase
            and (not exclude_cutback or not w.is_cutback)]


def _phase_index(wt: WeekTargets, phase_weeks: List[WeekTargets]) -> int:
    return next((i for i, w in enumerate(phase_weeks)
                 if w.week_number == wt.week_number), 0)


def schedule_quality(
    state: AthleteState,
    targets: List[WeekTargets],
) -> Dict[int, List[QualityRx]]:
    quality_map: Dict[int, List[QualityRx]] = {}
    t_step = 0
    dist = state.race_distance

    if state.is_abbreviated:
        return _schedule_abbreviated(state, targets)

    for wt in targets:
        wq: List[QualityRx] = []

        if wt.is_cutback or wt.phase == "taper":
            quality_map[wt.week_number] = []
            continue

        if wt.phase == "base":
            if dist in ("5k", "10k") and state.experience in (
                ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE,
            ):
                wq.append(_interval_session(state.experience, state.paces))
            quality_map[wt.week_number] = wq
            continue

        # ── Marathon ──────────────────────────────────────────────
        if dist == "marathon":
            if wt.phase == "build_1":
                wq.append(_t_block_session(t_step, state.experience, state.paces))
                t_step = min(t_step + 1, 5)

            elif wt.phase == "build_2":
                pw = _weeks_of_phase(targets, "build_2")
                idx = _phase_index(wt, pw)
                mp_frac = min(0.55, 0.25 + idx * 0.08)
                wq.append(_mp_long_run(wt.long_run_miles, mp_frac, state.paces))
                if state.current_weekly_miles >= 70:
                    wq.append(_t_block_session(min(t_step, 4), state.experience, state.paces))

            elif wt.phase == "peak":
                pw = _weeks_of_phase(targets, "peak")
                idx = _phase_index(wt, pw)
                if idx < len(pw) - 1:
                    mp_frac = min(0.60, 0.45 + idx * 0.05)
                    wq.append(_mp_long_run(wt.long_run_miles, mp_frac, state.paces))
                else:
                    wq.append(_t_block_session(min(t_step, 4), state.experience, state.paces))

        # ── Half Marathon ─────────────────────────────────────────
        elif dist == "half_marathon":
            if wt.phase == "build_1":
                wq.append(_t_block_session(t_step, state.experience, state.paces))
                t_step = min(t_step + 1, 5)

            elif wt.phase == "build_2":
                pw = _weeks_of_phase(targets, "build_2")
                idx = _phase_index(wt, pw)
                if idx % 2 == 0:
                    hmp_frac = min(0.50, 0.20 + idx * 0.08)
                    wq.append(_hmp_long_run(wt.long_run_miles, hmp_frac, state.paces))
                else:
                    wq.append(_t_block_session(min(t_step, 4), state.experience, state.paces))

            elif wt.phase == "peak":
                pw = _weeks_of_phase(targets, "peak")
                idx = _phase_index(wt, pw)
                if idx == 0:
                    wq.append(_hmp_long_run(wt.long_run_miles, 0.45, state.paces))
                else:
                    wq.append(_t_block_session(min(t_step, 4), state.experience, state.paces))

        # ── 10K ───────────────────────────────────────────────────
        elif dist == "10k":
            if wt.phase == "build":
                wq.append(_t_block_session(t_step, state.experience, state.paces))
                t_step = min(t_step + 1, 5)
                pw = _weeks_of_phase(targets, "build")
                idx = _phase_index(wt, pw)
                if idx % 2 == 1 and state.days_per_week >= 5:
                    wq.append(_interval_session(state.experience, state.paces))

            elif wt.phase == "peak":
                wq.append(_t_block_session(min(t_step, 4), state.experience, state.paces))
                if state.days_per_week >= 5:
                    wq.append(_interval_session(state.experience, state.paces))

        # ── 5K ────────────────────────────────────────────────────
        else:
            if wt.phase == "build":
                wq.append(_interval_session(state.experience, state.paces))
                pw = _weeks_of_phase(targets, "build")
                idx = _phase_index(wt, pw)
                if idx % 2 == 0 and state.days_per_week >= 5:
                    wq.append(_t_block_session(t_step, state.experience, state.paces))
                    t_step = min(t_step + 1, 5)
                if (state.experience in (ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE)
                        and idx % 3 == 2):
                    reps = _reps_session(state.experience, state.paces)
                    if len(wq) > 1:
                        wq[1] = reps
                    else:
                        wq.append(reps)

            elif wt.phase == "peak":
                wq.append(_interval_session(state.experience, state.paces))
                if state.experience in (ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE):
                    wq.append(_reps_session(state.experience, state.paces))

        quality_map[wt.week_number] = wq[:2]

    return quality_map


def _schedule_abbreviated(
    state: AthleteState,
    targets: List[WeekTargets],
) -> Dict[int, List[QualityRx]]:
    qmap: Dict[int, List[QualityRx]] = {}
    t_step = 2
    dist = state.race_distance

    for wt in targets:
        if wt.phase == "taper":
            qmap[wt.week_number] = []
            continue

        wq: List[QualityRx] = []
        if dist == "marathon":
            mp_frac = 0.30
            wq.append(_mp_long_run(wt.long_run_miles, mp_frac, state.paces))
        elif dist == "half_marathon":
            wq.append(_hmp_long_run(wt.long_run_miles, 0.30, state.paces))
        elif dist in ("10k", "5k"):
            wq.append(_t_block_session(t_step, state.experience, state.paces))
            t_step = min(t_step + 1, 5)
            if state.days_per_week >= 5:
                wq.append(_interval_session(state.experience, state.paces))

        qmap[wt.week_number] = wq[:2]

    return qmap


# ═══════════════════════════════════════════════════════════════════════
# Step 5 — Day-by-Day Assembly
# ═══════════════════════════════════════════════════════════════════════

def _rest_day(dow: int) -> DayPlan:
    return DayPlan(
        day_of_week=dow, workout_type="rest", name="Rest",
        description="Complete rest.", target_miles=0.0, intensity="rest",
        paces={}, notes=[],
    )


def _easy_day(
    dow: int, miles: float, paces: Optional[Dict[str, float]],
    strides: bool = False,
) -> DayPlan:
    pace = _pace_label(paces, "easy")
    p_dict: Dict[str, str] = {}
    if paces and "easy" in paces:
        p_dict["easy"] = format_pace(paces["easy"])
    if strides:
        return DayPlan(
            day_of_week=dow, workout_type="easy_strides",
            name="Easy + strides",
            description=f"{miles:.0f}mi @ {pace} + 6x20s strides",
            target_miles=round(miles, 1), intensity="easy",
            paces=p_dict, notes=[],
        )
    return DayPlan(
        day_of_week=dow, workout_type="easy", name="Easy run",
        description=f"{miles:.0f}mi @ {pace}",
        target_miles=round(miles, 1), intensity="easy",
        paces=p_dict, notes=[],
    )


def _long_run_day(
    dow: int, miles: float, paces: Optional[Dict[str, float]],
) -> DayPlan:
    pace = _pace_label(paces, "easy")
    p_dict: Dict[str, str] = {}
    if paces and "easy" in paces:
        p_dict["easy"] = format_pace(paces["easy"])
    return DayPlan(
        day_of_week=dow, workout_type="long",
        name=f"Long run — {miles:.0f}mi",
        description=f"{miles:.0f}mi @ {pace}",
        target_miles=round(miles, 1), intensity="easy",
        paces=p_dict, notes=[],
    )


def _mlr_day(
    dow: int, miles: float, paces: Optional[Dict[str, float]],
) -> DayPlan:
    pace = _pace_label(paces, "easy")
    p_dict: Dict[str, str] = {}
    if paces and "easy" in paces:
        p_dict["easy"] = format_pace(paces["easy"])
    return DayPlan(
        day_of_week=dow, workout_type="medium_long",
        name=f"Medium-long — {miles:.0f}mi",
        description=f"{miles:.0f}mi @ {pace}",
        target_miles=round(miles, 1), intensity="easy",
        paces=p_dict, notes=[],
    )


def _quality_day(
    rx: QualityRx, dow: int, paces: Optional[Dict[str, float]],
) -> DayPlan:
    p_dict: Dict[str, str] = {}
    if paces:
        if "threshold" in rx.workout_type and "threshold" in paces:
            p_dict["threshold"] = format_pace(paces["threshold"])
        elif "interval" in rx.workout_type and "interval" in paces:
            p_dict["interval"] = format_pace(paces["interval"])
        elif "rep" in rx.workout_type and "interval" in paces:
            p_dict["repetition"] = format_pace(paces["interval"])
    return DayPlan(
        day_of_week=dow, workout_type=rx.workout_type,
        name=rx.name, description=rx.description,
        target_miles=rx.miles, intensity=rx.intensity,
        paces=p_dict, notes=[],
    )


def _quality_long_day(
    rx: QualityRx, dow: int, lr_miles: float,
    paces: Optional[Dict[str, float]],
) -> DayPlan:
    p_dict: Dict[str, str] = {}
    if paces:
        if "easy" in paces:
            p_dict["easy"] = format_pace(paces["easy"])
        if "marathon" in paces and "mp" in rx.workout_type:
            p_dict["marathon"] = format_pace(paces["marathon"])
    return DayPlan(
        day_of_week=dow, workout_type=rx.workout_type,
        name=rx.name, description=rx.description,
        target_miles=round(lr_miles, 1), intensity=rx.intensity,
        paces=p_dict, notes=[],
    )


def assemble_weeks(
    state: AthleteState,
    targets: List[WeekTargets],
    quality: Dict[int, List[QualityRx]],
) -> List[WeekPlan]:
    weeks: List[WeekPlan] = []
    long_dow = 6   # Sunday
    rest_dow = 0   # Monday

    for wt in targets:
        days: List[DayPlan] = []
        week_start = state.plan_start + timedelta(weeks=wt.week_number - 1)

        wk_quality = quality.get(wt.week_number, [])
        quality_long: Optional[QualityRx] = None
        midweek_quality: List[QualityRx] = []
        for qrx in wk_quality:
            if qrx.workout_type in ("long_mp", "long_hmp"):
                quality_long = qrx
            else:
                midweek_quality.append(qrx)

        # 1. Long run (Sunday)
        if quality_long:
            days.append(_quality_long_day(quality_long, long_dow, wt.long_run_miles, state.paces))
        else:
            days.append(_long_run_day(long_dow, wt.long_run_miles, state.paces))

        # 2. Rest (Monday)
        days.append(_rest_day(rest_dow))

        # 3. Determine available weekday slots: Tue(1) Wed(2) Thu(3) Fri(4) Sat(5)
        available = [1, 2, 3, 4, 5]
        running_slots_needed = state.days_per_week - 1
        extra_rest_needed = len(available) - running_slots_needed

        extra_rest_dows: List[int] = []
        for candidate in [3, 4, 1]:
            if extra_rest_needed <= 0:
                break
            if candidate in available:
                extra_rest_dows.append(candidate)
                extra_rest_needed -= 1

        # Quality day-of-week placement with spacing
        q_dows: List[int] = []
        if len(midweek_quality) >= 2:
            q_dows = [2, 4]
        elif len(midweek_quality) == 1:
            q_dows = [2]

        assigned = set(q_dows + extra_rest_dows)
        easy_dows = [d for d in available if d not in assigned]

        for rd in extra_rest_dows:
            days.append(_rest_day(rd))

        for i, qd in enumerate(q_dows):
            if i < len(midweek_quality):
                days.append(_quality_day(midweek_quality[i], qd, state.paces))

        # 4. Saturday = always easy (before Sunday long)
        sat_miles = max(3.0, round(wt.weekly_miles / state.days_per_week * 0.7, 1))
        if 5 in easy_dows:
            days.append(_easy_day(5, sat_miles, state.paces))
            easy_dows.remove(5)

        # 5. MLR (Tuesday preferred)
        if wt.medium_long_miles > 0 and 1 in easy_dows:
            days.append(_mlr_day(1, wt.medium_long_miles, state.paces))
            easy_dows.remove(1)

        # 6. Fill remaining easy days
        placed_miles = sum(d.target_miles for d in days)
        remaining_miles = max(0, wt.weekly_miles - placed_miles)
        easy_count = len(easy_dows)
        per_easy = max(3.0, round(remaining_miles / max(1, easy_count), 1))

        needs_strides = wt.phase == "base" and not wk_quality
        for idx_e, ed in enumerate(easy_dows):
            strides = needs_strides and idx_e == 0
            days.append(_easy_day(ed, per_easy, state.paces, strides=strides))

        days.sort(key=lambda d: d.day_of_week)
        total = round(sum(d.target_miles for d in days), 1)

        weeks.append(WeekPlan(
            week_number=wt.week_number,
            theme=wt.phase,
            start_date=week_start,
            days=days,
            total_miles=total,
            is_cutback=wt.is_cutback,
        ))

    return weeks


# ═══════════════════════════════════════════════════════════════════════
# Couch-to-10K (Day-One Athletes)
# ═══════════════════════════════════════════════════════════════════════

def _generate_couch_to_10k(plan_start: date) -> List[WeekPlan]:
    """Founder-specified walk/run progression for never-ran-before athletes."""
    STAGES = [
        (2, "Walk 1mi, Run 1mi, Walk 1mi", 3.0, "Run 3mi", 3.0),
        (1, "Walk 1mi, Run 2mi", 3.0, "Run 4mi", 4.0),
        (3, "Run 3mi", 3.0, "Run 6mi", 6.0),
        (3, "Run 4mi", 4.0, "Run 8mi", 8.0),
    ]

    weeks: List[WeekPlan] = []
    week_num = 1

    for num_weeks, daily_desc, daily_mi, long_desc, long_mi in STAGES:
        wtype = "walk_run" if "Walk" in daily_desc else "easy"
        for _ in range(num_weeks):
            ws = plan_start + timedelta(weeks=week_num - 1)
            days = [
                DayPlan(dow, wtype, daily_desc, daily_desc,
                        daily_mi, "easy", {}, [])
                for dow in range(6)
            ]
            days.append(DayPlan(6, "long", long_desc, long_desc,
                                long_mi, "easy", {}, []))
            total = round(daily_mi * 6 + long_mi, 1)
            weeks.append(WeekPlan(week_num, "progression", ws, days, total))
            week_num += 1

    # Taper + race week
    ws = plan_start + timedelta(weeks=week_num - 1)
    taper_days = [
        DayPlan(dow, "easy", "Easy 3mi", "3mi easy", 3.0, "easy", {}, [])
        for dow in range(5)
    ]
    taper_days.append(_rest_day(5))
    taper_days.append(DayPlan(
        6, "race", "Race Day", "Warm up, execute, celebrate.",
        0.0, "race", {}, [],
    ))
    weeks.append(WeekPlan(week_num, "taper", ws, taper_days, 15.0))

    return weeks


# ═══════════════════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════════════════

def generate_n1_plan(
    *,
    race_distance: str,
    race_date: date,
    plan_start: date,
    horizon_weeks: int,
    days_per_week: int,
    starting_vol: float,
    current_lr: float,
    applied_peak: float,
    experience: ExperienceLevel,
    best_rpi: Optional[float] = None,
    weeks_since_peak: int = 0,
    goal_time: Optional[str] = None,
) -> List[WeekPlan]:
    """Generate an N=1 training plan.

    Returns List[WeekPlan].
    Raises ReadinessGateError if athlete doesn't meet distance requirements.
    """
    state = resolve_athlete_state(
        race_distance=race_distance,
        race_date=race_date,
        plan_start=plan_start,
        horizon_weeks=horizon_weeks,
        days_per_week=days_per_week,
        starting_vol=starting_vol,
        current_lr=current_lr,
        applied_peak=applied_peak,
        experience=experience,
        best_rpi=best_rpi,
        weeks_since_peak=weeks_since_peak,
        goal_time=goal_time,
    )

    if state.is_day_one:
        logger.info("Day-one athlete — generating Couch-to-10K progression")
        return _generate_couch_to_10k(plan_start)

    phases = compute_phase_schedule(state)
    targets = compute_curves(state, phases)
    quality = schedule_quality(state, targets)
    weeks = assemble_weeks(state, targets, quality)

    # Log MP accumulation for marathon plans
    if race_distance == "marathon":
        mp_total = sum(
            d.target_miles
            for w in weeks for d in w.days
            if d.workout_type == "long_mp"
        )
        if mp_total > 0:
            logger.info("Marathon MP accumulation: %.0f miles (target: 40-50+)", mp_total)
            if mp_total < 35:
                logger.warning(
                    "MP accumulation %.0f mi is below 40mi target — "
                    "short plan or insufficient build_2 weeks", mp_total,
                )

    logger.info(
        "N=1 plan: %d weeks, %.0f total miles, %s, "
        "vol %.0f→%.0f, LR %.0f→%.0f",
        len(weeks),
        sum(w.total_miles for w in weeks),
        race_distance,
        state.current_weekly_miles,
        state.peak_weekly_miles,
        state.current_long_run_miles,
        max((t.long_run_miles for t in targets), default=0),
    )

    return weeks
