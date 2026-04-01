"""
N=1 Plan Engine v3 — Coach-thinks-first rebuild.

The algorithm:
  1. What is the goal? (distance, time, athlete state)
  2. What systems need to adapt? (ceiling, threshold, durability, specificity)
  3. What tools hit those systems? (from KB variant library)
  4. What's the target weekly volume? Anchor sessions placed first.
  5. Easy fills the gaps — easy IS a tool (recovery).
  6. Progression: each tool gets harder week to week.

No phases driving workout selection. Adaptation needs drive tool selection.
Phases are labels applied AFTER the plan is built, for communication only.

See: docs/specs/N1_ENGINE_ADR_V2.md
KB:  _AI_CONTEXT_/KNOWLEDGE_BASE/03_WORKOUT_TYPES.md
     _AI_CONTEXT_/KNOWLEDGE_BASE/04_RECOVERY.md
     _AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/*.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from services.fitness_bank import ExperienceLevel
from services.plan_framework.fingerprint_bridge import FingerprintParams
from services.workout_prescription import (
    DayPlan,
    WeekPlan,
    calculate_paces_from_rpi,
    format_pace,
)

logger = logging.getLogger(__name__)


class ReadinessGateError(ValueError):
    pass


# ═══════════════════════════════════════════════════════════════════════
# Step 1 — Athlete State & Diagnosis
# ═══════════════════════════════════════════════════════════════════════

class AdaptationNeed(Enum):
    CEILING = "ceiling"
    THRESHOLD = "threshold"
    DURABILITY = "durability"
    RACE_SPECIFIC = "race_specific"
    NEUROMUSCULAR = "neuromuscular"
    AEROBIC_BASE = "aerobic_base"


@dataclass
class AthleteState:
    current_weekly_miles: float
    current_long_run_miles: float
    peak_weekly_miles: float
    best_rpi: Optional[float]
    experience: ExperienceLevel
    days_per_week: int
    paces: Optional[Dict[str, float]]
    race_distance: str
    race_date: date
    plan_start: date
    horizon_weeks: int
    goal_time_seconds: Optional[int]
    is_slow_marathoner: bool
    is_abbreviated: bool
    is_day_one: bool
    taper_weeks_override: Optional[int] = None
    adaptation_needs: List[AdaptationNeed] = field(default_factory=list)
    fingerprint: FingerprintParams = field(default_factory=FingerprintParams)


def _parse_goal_time(gt: Optional[str]) -> Optional[int]:
    if not gt:
        return None
    parts = gt.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        pass
    return None


def _diagnose_adaptation_needs(
    dist: str, exp: ExperienceLevel, horizon: int, is_abbreviated: bool,
) -> List[AdaptationNeed]:
    """What systems need work for this race? This is the coaching decision."""
    needs = []

    if dist in ("5k", "10k"):
        needs.append(AdaptationNeed.CEILING)
        needs.append(AdaptationNeed.THRESHOLD)
        if dist == "10k":
            needs.append(AdaptationNeed.DURABILITY)
        if exp in (ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE):
            needs.append(AdaptationNeed.NEUROMUSCULAR)

    elif dist == "half_marathon":
        needs.append(AdaptationNeed.THRESHOLD)
        needs.append(AdaptationNeed.DURABILITY)
        needs.append(AdaptationNeed.CEILING)

    elif dist == "marathon":
        needs.append(AdaptationNeed.RACE_SPECIFIC)
        needs.append(AdaptationNeed.THRESHOLD)
        needs.append(AdaptationNeed.DURABILITY)
        if exp in (ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE):
            needs.append(AdaptationNeed.CEILING)

    if not is_abbreviated and horizon >= 8:
        needs.append(AdaptationNeed.AEROBIC_BASE)

    return needs


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
    taper_weeks: Optional[int] = None,
    fingerprint: Optional[FingerprintParams] = None,
) -> AthleteState:
    paces = None
    if best_rpi and best_rpi > 0:
        paces = calculate_paces_from_rpi(best_rpi)

    goal_secs = _parse_goal_time(goal_time)
    is_slow = False
    if race_distance == "marathon":
        if goal_secs and goal_secs > 13500:
            is_slow = True
        elif paces and paces.get("marathon", 0) > 8.58:
            is_slow = True

    is_abbreviated = horizon_weeks <= 5
    is_day_one = starting_vol <= 0 and current_lr <= 0

    if race_distance == "marathon" and not is_day_one and current_lr < 12:
        raise ReadinessGateError(
            f"Marathon readiness gate: current long run is {current_lr:.0f}mi. "
            "Must complete 12mi before starting a marathon program."
        )

    is_comeback = weeks_since_peak > 0 and experience in (
        ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE,
    )
    if (
        race_distance == "half_marathon"
        and not is_day_one
        and not is_comeback
        and current_lr < 8
    ):
        raise ReadinessGateError(
            f"Half-marathon readiness gate: current long run is {current_lr:.0f}mi. "
            "Must complete 8mi before starting a half-marathon program."
        )

    needs = _diagnose_adaptation_needs(
        race_distance, experience, horizon_weeks, is_abbreviated,
    )

    return AthleteState(
        current_weekly_miles=starting_vol,
        current_long_run_miles=current_lr,
        peak_weekly_miles=applied_peak,
        best_rpi=best_rpi,
        experience=experience,
        days_per_week=days_per_week,
        paces=paces,
        race_distance=race_distance,
        race_date=race_date,
        plan_start=plan_start,
        horizon_weeks=horizon_weeks,
        goal_time_seconds=goal_secs,
        is_slow_marathoner=is_slow,
        is_abbreviated=is_abbreviated,
        is_day_one=is_day_one,
        taper_weeks_override=taper_weeks,
        adaptation_needs=needs,
        fingerprint=fingerprint or FingerprintParams(),
    )


# ═══════════════════════════════════════════════════════════════════════
# Step 2 — Tool Selection (what workouts serve the adaptation needs)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class WeekRx:
    """What a coach prescribes for one week, before day assignment."""
    week_number: int
    phase_label: str
    target_volume: float
    is_cutback: bool
    long_run_miles: float
    long_run_type: str
    mlr_miles: float
    quality_sessions: List[Dict[str, Any]]


LR_CEILING = {
    "marathon": 22.0, "half_marathon": 17.0, "10k": 18.0, "5k": 15.0,
}
LR_CEILING_SLOW = 20.0
MARATHON_LR_FLOOR = 14.0
MLR_CAP = 15.0
MLR_FLOOR_VOL = 50.0
TAPER_WEEKS = {"marathon": 3, "half_marathon": 2, "10k": 2, "5k": 1}


def _pace_label(paces, zone):
    if paces and zone in paces:
        return format_pace(paces[zone]) + "/mi"
    return {
        "easy": "easy effort", "marathon": "marathon effort",
        "threshold": "comfortably hard", "interval": "hard controlled effort",
        "repetition": "fast, relaxed turnover", "recovery": "very easy",
    }.get(zone, "moderate effort")


def plan_weeks(state: AthleteState) -> List[WeekRx]:
    """Coach thinks backward: target volume → anchor sessions → fill."""
    n = state.horizon_weeks
    dist = state.race_distance

    if state.is_day_one:
        return []

    if state.taper_weeks_override is not None:
        taper_n = min(state.taper_weeks_override, max(1, n - 3))
    else:
        taper_n = min(TAPER_WEEKS.get(dist, 2), max(1, n - 3))
    build_n = n - taper_n

    vol_start = state.current_weekly_miles
    vol_peak = state.peak_weekly_miles
    if state.is_abbreviated:
        vol_peak = min(vol_peak, vol_start * 1.10)

    lr_ceiling = LR_CEILING.get(dist, 18.0)
    if state.is_slow_marathoner:
        lr_ceiling = LR_CEILING_SLOW
    if state.current_long_run_miles > 0:
        if state.is_abbreviated:
            lr_ceiling = min(lr_ceiling, state.current_long_run_miles)
        else:
            lr_ceiling = min(lr_ceiling, state.current_long_run_miles * 1.25)

    lr_step = 2.0
    if state.experience == ExperienceLevel.ELITE:
        lr_step = 2.5
    elif state.experience == ExperienceLevel.BEGINNER:
        lr_step = 1.5

    if state.is_abbreviated:
        lr_start = state.current_long_run_miles
    else:
        lr_start = state.current_long_run_miles + 1
    if dist == "marathon":
        lr_start = max(MARATHON_LR_FLOOR, lr_start)

    # Cutback frequency: fingerprint-driven when available, else every 3rd week.
    # Fast recoverers (e.g. 23.8h half-life) go every 4th-5th week.
    # Slow recoverers (e.g. 51.3h half-life) go every 3rd week.
    cutback_freq = state.fingerprint.cutback_frequency
    if cutback_freq < 3:
        cutback_freq = 3
    cutback_set = set()
    counter = 0
    for i in range(build_n):
        counter += 1
        if counter >= cutback_freq and i < build_n - 1 and i > 0:
            cutback_set.add(i)
            counter = 0

    # Volume curve (only non-cutback weeks grow)
    volumes = _build_volume_curve(vol_start, vol_peak, build_n, taper_n, state)

    # Apply cutback and sawtooth: post-cutback > pre-cutback
    for i in sorted(cutback_set):
        prev_vol = volumes[max(0, i - 1)]
        volumes[i] = round(prev_vol * 0.50, 1)
        if i + 1 < build_n and i + 1 not in cutback_set:
            at_peak = prev_vol >= vol_peak * 0.95
            if at_peak:
                bump = prev_vol + 2.0
            else:
                bump = max(prev_vol * 1.10, prev_vol + 5.0)
            volumes[i + 1] = max(volumes[i + 1], round(bump, 1))

    # Long run raw growth
    lr_raw = _build_lr_growth(lr_start, lr_ceiling, lr_step, build_n)

    # Quality sessions per week — driven by adaptation needs
    quality_plan = _plan_quality_sessions(state, build_n, taper_n, lr_raw, volumes)

    # Assemble WeekRx with ceiling alternation on actual non-cutback weeks
    weeks = []
    ceiling_idx = 0

    for i in range(n):
        is_taper = i >= build_n
        is_cutback = i in cutback_set

        vol = volumes[i]
        lr_type, lr_quality = quality_plan["long_types"][i]

        if is_cutback:
            prev_lr = lr_raw[max(0, i - 1)]
            lr = round(prev_lr * 0.55, 1)
            lr_type = "long"
            lr_quality = None
        elif is_taper:
            offset = i - build_n
            hw = max(lr_raw[:build_n]) if build_n > 0 else lr_start
            if offset == 0:
                lr = round(hw * 0.60, 1)
            elif offset == 1:
                lr = round(hw * 0.40, 1)
            else:
                lr = round(min(hw * 0.30, 8.0), 1)
        else:
            base_lr = lr_raw[i]
            if base_lr >= lr_ceiling:
                cycle = [lr_ceiling, lr_ceiling - 2]
                lr = cycle[ceiling_idx % 2]
                ceiling_idx += 1
            else:
                lr = base_lr

        # Taper volume
        if is_taper:
            offset = i - build_n
            hw = max(volumes[:build_n]) if build_n > 0 else vol_start
            factors = [0.55, 0.40, 0.28]
            f = factors[min(offset, len(factors) - 1)]
            vol = round(hw * f, 1)

        mlr = 0.0
        if vol >= MLR_FLOOR_VOL and not is_taper and not is_cutback:
            from_lr = round(lr * 0.75, 1)
            from_athlete = round(state.current_long_run_miles * 0.75, 1)
            mlr = min(MLR_CAP, max(from_lr, from_athlete))
            mlr = min(mlr, round(lr * 0.75, 1))

        phase = _label_phase(i, build_n, taper_n, is_cutback, dist)
        q_sessions = quality_plan["midweek"][i] if not is_cutback else []

        if lr_quality and not is_cutback:
            # Sync LR quality miles with the alternated LR value
            lr_q = dict(lr_quality)
            if abs(lr_q["miles"] - lr) > 0.5:
                lr_q = _rescale_lr_quality(lr_q, lr)
            q_sessions = [lr_q] + q_sessions

        weeks.append(WeekRx(
            week_number=i + 1,
            phase_label=phase,
            target_volume=vol,
            is_cutback=is_cutback,
            long_run_miles=round(lr, 1),
            long_run_type=lr_type,
            mlr_miles=mlr,
            quality_sessions=q_sessions,
        ))

    return weeks


def _build_volume_curve(vol_start, vol_peak, build_n, taper_n, state):
    n = build_n + taper_n
    volumes = []
    cur = vol_start
    step_max = {
        ExperienceLevel.BEGINNER: 3.0, ExperienceLevel.INTERMEDIATE: 5.0,
        ExperienceLevel.EXPERIENCED: 6.0, ExperienceLevel.ELITE: 8.0,
    }.get(state.experience, 5.0)

    for i in range(n):
        if i >= build_n:
            volumes.append(0.0)  # placeholder, taper computed in plan_weeks
        elif cur < vol_peak * 0.95:
            remaining = build_n - i
            step = min(step_max, (vol_peak - cur) / max(1, remaining))
            cur = min(vol_peak, cur + step)
            volumes.append(round(cur, 1))
        else:
            cur = vol_peak
            volumes.append(round(vol_peak, 1))
    return volumes


def _build_lr_growth(lr_start, lr_ceiling, lr_step, build_n):
    """Raw LR growth curve — ceiling alternation handled in plan_weeks."""
    lrs = []
    cur = lr_start
    if lr_ceiling - cur < lr_step:
        cur = lr_ceiling
    for i in range(build_n):
        if i > 0 and cur < lr_ceiling:
            nxt = cur + lr_step
            if nxt >= lr_ceiling or (lr_ceiling - nxt) < lr_step:
                nxt = lr_ceiling
            cur = nxt
        lrs.append(round(cur, 1))
    return lrs


def _rescale_lr_quality(q: Dict, new_lr: float) -> Dict:
    """Adjust a LR quality dict's miles and description for the alternated LR."""
    old = q["miles"]
    if old <= 0:
        return q
    q["miles"] = round(new_lr, 1)
    q["name"] = q["name"].replace(f"{old:.0f}mi", f"{new_lr:.0f}mi")
    if "desc" in q:
        for val in [old, round(old)]:
            q["desc"] = q["desc"].replace(f"{val:.0f}mi", f"{new_lr:.0f}mi", 1)
    return q


def _label_phase(i, build_n, taper_n, is_cutback, dist):
    if i >= build_n:
        return "taper"
    ratio = i / max(1, build_n)
    if dist in ("5k", "10k") and build_n < 8:
        return "build" if ratio < 0.55 else "peak"
    if ratio < 0.20:
        return "base"
    if dist == "marathon":
        if ratio < 0.45:
            return "build_1"
        if ratio < 0.70:
            return "build_2"
        return "peak"
    if ratio < 0.55:
        return "build"
    return "peak"


# ═══════════════════════════════════════════════════════════════════════
# Step 3 — Quality Planning (adaptation-driven tool selection)
# ═══════════════════════════════════════════════════════════════════════

def _plan_quality_sessions(state, build_n, taper_n, lr_raw, volumes):
    """Select and progress quality tools based on adaptation needs.

    Key principles:
      - Workout dose scales to athlete capacity (KB B1 percentages)
      - Progression is week-over-week, not step-through-a-fixed-table
      - For 10K/5K experienced: both threshold + intervals from week 1
      - Short plans (≤6w): no base phase, both systems immediately
    """
    n = build_n + taper_n
    dist = state.race_distance
    exp = state.experience
    paces = state.paces
    needs = state.adaptation_needs

    has_base = not state.is_abbreviated and build_n >= 8

    long_types = []
    midweek = []

    for i in range(n):
        is_taper = i >= build_n
        ratio = i / max(1, build_n) if not is_taper else 1.0
        week_ratio = i / max(1, build_n - 1) if build_n > 1 and not is_taper else (0.0 if i == 0 else 1.0)
        lr_mi = lr_raw[i] if i < len(lr_raw) else 10.0
        weekly_vol = volumes[i] if i < len(volumes) else state.peak_weekly_miles

        lr_type, lr_quality = _select_long_run_tool(
            dist, exp, paces, ratio, i, lr_mi, is_taper, state, needs,
        )
        long_types.append((lr_type, lr_quality))

        if is_taper:
            midweek.append(_taper_tools(state, i - build_n))
        elif has_base and ratio < 0.20:
            midweek.append(_base_quality(state, needs, week_ratio, weekly_vol))
        else:
            midweek.append(_build_quality(state, needs, week_ratio, weekly_vol, lr_type))

    return {"long_types": long_types, "midweek": midweek}


# ── Capacity-scaled quality session builders ──────────────────────────

def _threshold_capacity(weekly_vol, exp):
    """KB B1: threshold session max = 10% of weekly volume."""
    cap = weekly_vol * 0.10
    if exp == ExperienceLevel.BEGINNER:
        return min(cap, 3.5)
    if exp == ExperienceLevel.INTERMEDIATE:
        return min(cap, 5.0)
    return cap


def _interval_capacity(weekly_vol, exp):
    """KB B1: interval session max = min(8% of weekly volume, 10K = 6.2mi)."""
    cap = min(weekly_vol * 0.08, 6.2)
    if exp == ExperienceLevel.BEGINNER:
        return min(cap, 2.5)
    if exp == ExperienceLevel.INTERMEDIATE:
        return min(cap, 4.0)
    return cap


def _wu_cd(exp):
    return {ExperienceLevel.BEGINNER: 2.0, ExperienceLevel.INTERMEDIATE: 3.0}.get(exp, 4.0)


def _make_threshold_scaled(week_ratio, weekly_vol, exp, paces, dist="10k"):
    """Progressive threshold session scaled to athlete capacity.

    Structure by distance:
      5K/10K: cruise intervals only (never continuous — same adaptation, less
              recovery cost). Rep duration progresses 5min → 8-10min.
      Half:   cruise intervals → continuous at peak, capped 25min.
      Marathon: cruise intervals → continuous at peak, capped 40min.
    """
    t_cap = _threshold_capacity(weekly_vol, exp)
    dose = 0.60 + 0.40 * week_ratio
    target_mi = max(2.0, round(t_cap * dose, 1))

    pace = _pace_label(paces, "threshold")
    t_pace_val = paces.get("threshold", 7.0) if paces else 7.0
    target_min = round(target_mi * t_pace_val)

    wcd = _wu_cd(exp)
    half = round(wcd / 2, 1)

    continuous_ok = dist in ("marathon", "half_marathon") and week_ratio >= 0.70
    if continuous_ok:
        max_cont = 40 if dist == "marathon" else 25
        cont_min = min(target_min, max_cont)
        cont_mi = round(cont_min / t_pace_val, 1)
        total = round(wcd + cont_mi, 1)
        name = f"{cont_min}min continuous @ T"
        desc = f"{half:.0f}mi easy + {cont_min}min @ {pace} + {half:.0f}mi easy"
        return {"type": "threshold_continuous", "name": name, "desc": desc, "miles": total, "intensity": "hard"}

    if week_ratio < 0.40:
        rep_dur = 5
    else:
        rep_dur = min(10, 5 + round(week_ratio * 8))
    reps = max(2, round(target_min / rep_dur))
    rest = 1.5 if week_ratio < 0.40 else 2.0
    jog_mi = (reps - 1) * rest / 9.0
    total = round(wcd + target_mi + jog_mi, 1)
    name = f"{reps}x{rep_dur}min @ T"
    desc = f"{half:.0f}mi easy + {reps}x{rep_dur}min @ {pace}, {rest:.0f}min jog + {half:.0f}mi easy"
    return {"type": "cruise_intervals", "name": name, "desc": desc, "miles": total, "intensity": "hard"}


def _make_intervals_scaled(week_ratio, weekly_vol, exp, paces):
    """Progressive interval session scaled to athlete capacity.

    Progression: 400m → 800m → 1000m → 1200m → mile, rep count fills capacity.
    Volume progresses from 65% to 100% of capacity across build weeks.
    """
    i_cap = _interval_capacity(weekly_vol, exp)
    dose = 0.65 + 0.35 * week_ratio
    target_mi = max(1.5, round(i_cap * dose, 1))

    if week_ratio < 0.30:
        rep_mi, rep_label = 0.25, "400m"
    elif week_ratio < 0.55:
        rep_mi, rep_label = 0.50, "800m"
    elif week_ratio < 0.75:
        rep_mi, rep_label = 0.625, "1000m"
    elif week_ratio < 0.90:
        rep_mi, rep_label = 0.75, "1200m"
    else:
        rep_mi, rep_label = 1.0, "1mi"

    reps = max(3, round(target_mi / rep_mi))
    quality_mi = reps * rep_mi

    pace = _pace_label(paces, "interval")
    wcd = _wu_cd(exp)
    half = round(wcd / 2, 1)
    jog_mi = (reps - 1) * 0.25
    total = round(wcd + quality_mi + jog_mi, 1)

    core = f"{reps}x{rep_label}"
    desc = f"{half:.0f}mi easy + {core} @ {pace} w/ 400m jog + {half:.0f}mi easy"
    return {"type": "intervals", "name": core, "desc": desc, "miles": total, "intensity": "hard"}


def _make_reps(exp, paces):
    pace = _pace_label(paces, "repetition")
    if exp == ExperienceLevel.ELITE:
        return {"type": "repetitions", "name": "8x300m reps",
                "desc": f"2mi easy + 8x300m @ {pace}, 90s full rest + 2mi easy",
                "miles": 8.0, "intensity": "hard"}
    return {"type": "repetitions", "name": "6x200m reps",
            "desc": f"2mi easy + 6x200m @ {pace}, 90s full rest + 2mi easy",
            "miles": 7.0, "intensity": "hard"}


# ── Quality selection by phase ────────────────────────────────────────

def _base_quality(state, needs, week_ratio, weekly_vol):
    """Base phase: volume building only — no midweek quality sessions.

    Base is for building the aerobic engine. Strides (placed automatically
    on easy days) and hill sprints provide neuromuscular prep without
    metabolic cost or recovery burden. Quality sessions start in build.
    """
    return []


def _build_quality(state, needs, week_ratio, weekly_vol, lr_type):
    """Build/Peak: select tools based on distance + athlete capacity."""
    dist = state.race_distance
    exp = state.experience
    paces = state.paces
    mq = []

    if dist == "10k":
        mq.append(_make_threshold_scaled(week_ratio, weekly_vol, exp, paces, dist))
        lr_share = state.current_long_run_miles / max(weekly_vol, 1.0)
        volume_allows_second = lr_share < 0.45
        if volume_allows_second:
            if exp in (ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE):
                mq.append(_make_intervals_scaled(week_ratio, weekly_vol, exp, paces))
            elif week_ratio > 0.50:
                mq.append(_make_intervals_scaled(week_ratio, weekly_vol, exp, paces))

    elif dist == "5k":
        mq.append(_make_intervals_scaled(week_ratio, weekly_vol, exp, paces))
        if exp == ExperienceLevel.BEGINNER:
            pass
        elif week_ratio > 0.70 and AdaptationNeed.NEUROMUSCULAR in needs:
            mq.append(_make_reps(exp, paces))
        else:
            mq.append(_make_threshold_scaled(min(week_ratio, 0.6), weekly_vol, exp, paces, dist))

    elif dist == "half_marathon":
        mq.append(_make_threshold_scaled(week_ratio, weekly_vol, exp, paces, dist))

    elif dist == "marathon":
        mq.append(_make_threshold_scaled(week_ratio, weekly_vol, exp, paces, dist))

    return mq


# ── Long run tool selection ───────────────────────────────────────────

def _select_long_run_tool(dist, exp, paces, ratio, week_idx, lr_miles, is_taper, state, needs):
    if is_taper:
        return "long", None
    if ratio < 0.20:
        return "long", None

    if dist == "marathon":
        return _marathon_lr_tool(ratio, week_idx, lr_miles, paces, state)
    if dist == "half_marathon":
        return _half_lr_tool(ratio, week_idx, lr_miles, paces)
    return _short_distance_lr_tool(ratio, week_idx, lr_miles, paces, exp, dist)


def _marathon_lr_tool(ratio, week_idx, lr_miles, paces, state):
    mp_pace = _pace_label(paces, "marathon")
    easy_pace = _pace_label(paces, "easy")

    if ratio < 0.45:
        if week_idx % 2 == 1:
            cut = round(lr_miles * 0.15, 1)
            easy_mi = round(lr_miles - cut, 1)
            return "long_progressive", {
                "type": "long_progressive", "name": f"{lr_miles:.0f}mi progressive",
                "desc": f"{easy_mi:.0f}mi @ {easy_pace}, last {cut:.0f}mi descending to {mp_pace}",
                "miles": lr_miles, "intensity": "moderate",
            }
        return "long", None

    # Build_2 / Peak: MP long 2 out of 3 weeks, progressive on the 3rd
    mp_frac = 0.30 + (ratio - 0.45) * 1.0
    mp_mi = round(lr_miles * min(mp_frac, 0.70), 1)

    if week_idx % 3 != 2:
        easy_mi = round(lr_miles - mp_mi, 1)
        return "long_mp", {
            "type": "long_mp",
            "name": f"{lr_miles:.0f}mi w/ {mp_mi:.0f}mi @ MP",
            "desc": f"{easy_mi:.0f}mi @ {easy_pace} + {mp_mi:.0f}mi @ {mp_pace}",
            "miles": lr_miles, "intensity": "hard",
        }
    ff = round(min(3.0, lr_miles * 0.12), 1)
    easy_mi = round(lr_miles - ff, 1)
    t_pace = _pace_label(paces, "threshold")
    return "long_fast_finish", {
        "type": "long_fast_finish",
        "name": f"{lr_miles:.0f}mi w/ fast finish",
        "desc": f"{easy_mi:.0f}mi @ {easy_pace}, last {ff:.0f}mi @ {t_pace}",
        "miles": lr_miles, "intensity": "moderate",
    }


def _half_lr_tool(ratio, week_idx, lr_miles, paces):
    easy_pace = _pace_label(paces, "easy")
    if ratio < 0.45:
        return "long", None

    if week_idx % 2 == 0:
        if paces:
            mp = paces.get("marathon", 7.5)
            tp = paces.get("threshold", 6.5)
            hmp_str = format_pace((mp + tp) / 2) + "/mi"
        else:
            hmp_str = "half marathon effort"
        hmp_mi = round(lr_miles * 0.35, 1)
        easy_mi = round(lr_miles - hmp_mi, 1)
        return "long_hmp", {
            "type": "long_hmp",
            "name": f"{lr_miles:.0f}mi w/ {hmp_mi:.0f}mi @ HMP",
            "desc": f"{easy_mi:.0f}mi @ {easy_pace} + {hmp_mi:.0f}mi @ {hmp_str}",
            "miles": lr_miles, "intensity": "hard",
        }
    cut = round(lr_miles * 0.25, 1)
    easy_mi = round(lr_miles - cut, 1)
    return "long_progressive", {
        "type": "long_progressive",
        "name": f"{lr_miles:.0f}mi progressive",
        "desc": f"{easy_mi:.0f}mi @ {easy_pace}, last {cut:.0f}mi picking up",
        "miles": lr_miles, "intensity": "moderate",
    }


def _short_distance_lr_tool(ratio, week_idx, lr_miles, paces, exp, dist):
    if exp == ExperienceLevel.BEGINNER:
        return "long", None
    easy_pace = _pace_label(paces, "easy")
    if ratio > 0.55 and week_idx % 3 == 0:
        ff = round(min(2.0, lr_miles * 0.12), 1)
        easy_mi = round(lr_miles - ff, 1)
        t_pace = _pace_label(paces, "threshold")
        return "long_fast_finish", {
            "type": "long_fast_finish",
            "name": f"{lr_miles:.0f}mi w/ fast finish",
            "desc": f"{easy_mi:.0f}mi @ {easy_pace}, last {ff:.0f}mi @ {t_pace}",
            "miles": lr_miles, "intensity": "moderate",
        }
    if ratio > 0.35 and week_idx % 3 == 1:
        cut = round(lr_miles * 0.20, 1)
        easy_mi = round(lr_miles - cut, 1)
        return "long_progressive", {
            "type": "long_progressive",
            "name": f"{lr_miles:.0f}mi progressive",
            "desc": f"{easy_mi:.0f}mi @ {easy_pace}, last {cut:.0f}mi descending",
            "miles": lr_miles, "intensity": "moderate",
        }
    return "long", None



def _taper_tools(state, offset):
    """Taper: sharp and short. Maintain neuromuscular edge."""
    paces = state.paces
    exp = state.experience
    wu_cd = {ExperienceLevel.BEGINNER: 2.0, ExperienceLevel.INTERMEDIATE: 3.0}.get(exp, 4.0)
    half = round(wu_cd / 2, 1)

    if offset == 0:
        if state.race_distance in ("marathon", "half_marathon"):
            pace = _pace_label(paces, "threshold")
            return [{"type": "threshold_continuous", "name": "Taper threshold",
                     "desc": f"{half:.0f}mi easy + 15min @ {pace} + {half:.0f}mi easy",
                     "miles": round(wu_cd + 2.5, 1), "intensity": "hard"}]
        pace = _pace_label(paces, "interval")
        return [{"type": "intervals", "name": "Taper sharpener",
                 "desc": f"{half:.0f}mi easy + 4x400m @ {pace} w/ 400m jog + {half:.0f}mi easy",
                 "miles": round(wu_cd + 2.5, 1), "intensity": "hard"}]

    return [{"type": "easy_strides", "name": "Easy + strides",
             "desc": f"{half + 2:.0f}mi @ easy effort + 6x20s strides",
             "miles": round(half + 2.5, 1), "intensity": "easy"}]


# ═══════════════════════════════════════════════════════════════════════
# Step 4 — Day-by-Day Assembly
# ═══════════════════════════════════════════════════════════════════════

MIDWEEK_QUALITY_TYPES = frozenset({
    "threshold", "threshold_continuous", "cruise_intervals",
    "broken_threshold", "intervals", "repetitions",
})


def assemble_plan(state: AthleteState, week_rxs: List[WeekRx]) -> List[WeekPlan]:
    weeks = []
    long_dow = 6

    for rx in week_rxs:
        days: List[DayPlan] = []
        week_start = state.plan_start + timedelta(weeks=rx.week_number - 1)

        # Separate LR quality from midweek quality
        lr_quality_rx = None
        midweek_rx = []
        for q in rx.quality_sessions:
            if q["type"] in ("long_mp", "long_hmp", "long_progressive", "long_fast_finish"):
                lr_quality_rx = q
            else:
                midweek_rx.append(q)

        # 1. Long run
        if lr_quality_rx:
            days.append(_make_day(long_dow, lr_quality_rx, state.paces))
        else:
            days.append(_long_run_day(long_dow, rx.long_run_miles, state.paces))

        # 2. Rest — 7-day athletes run every day, no forced rest
        has_forced_rest = state.days_per_week < 7
        if has_forced_rest:
            days.append(_rest_day(0))

        # 3. Available weekday slots (include Mon for 7-day athletes)
        available = [0, 1, 2, 3, 4, 5] if not has_forced_rest else [1, 2, 3, 4, 5]
        running_needed = state.days_per_week - 1
        extra_rest = max(0, len(available) - running_needed)

        # Quality DOWs — wider spacing for slow recoverers (72h+).
        # Standard (48h): Tue/Thu or Mon/Thu patterns.
        # Wide (72h): Tue/Fri or Wed/Sat-adjacent patterns.
        #
        # Graceful degradation: 3 midweek quality sessions with 72h spacing
        # cannot fit in a Mon-Sat window.  Drop to 2 rather than compress
        # spacing — the athlete's data says spacing matters more than volume
        # of quality work.
        odd = rx.week_number % 2 == 1
        wide_spacing = state.fingerprint.quality_spacing_min_hours >= 72
        effective_midweek = midweek_rx
        if wide_spacing and len(midweek_rx) >= 3:
            effective_midweek = midweek_rx[:2]
            logger.info(
                "W%d: 72h spacing constraint — dropping from %d to 2 midweek quality sessions",
                rx.week_number, len(midweek_rx),
            )
        q_dows = []
        if len(effective_midweek) >= 3:
            q_dows = [1, 3, 5] if odd else [2, 4, 5]
        elif len(effective_midweek) >= 2:
            if wide_spacing:
                q_dows = [1, 4] if odd else [2, 5]
            else:
                q_dows = [2, 4] if odd else [1, 4]
        elif len(effective_midweek) == 1:
            q_dows = [2] if odd else [4]

        remaining_for_rest = [d for d in available if d not in q_dows]
        extra_rest_dows = []
        for c in [3, 4, 1]:
            if extra_rest <= 0:
                break
            if c in remaining_for_rest:
                extra_rest_dows.append(c)
                extra_rest -= 1
        if extra_rest > 0:
            for c in remaining_for_rest:
                if extra_rest <= 0:
                    break
                if c not in extra_rest_dows:
                    extra_rest_dows.append(c)
                    extra_rest -= 1

        for rd in extra_rest_dows:
            days.append(_rest_day(rd))

        for i, qd in enumerate(q_dows):
            if i < len(effective_midweek):
                days.append(_make_day(qd, effective_midweek[i], state.paces))

        assigned = set(q_dows[:len(effective_midweek)] + extra_rest_dows)
        easy_dows = [d for d in available if d not in assigned]

        # Pre-long Saturday: lighter, parity-varied for week-to-week variety
        sat_factor = 0.40 if rx.week_number % 2 == 0 else 0.55
        sat_miles = max(2.0, round(rx.target_volume / state.days_per_week * sat_factor, 1))
        is_taper_week = rx.phase_label == "taper"
        if 5 in easy_dows:
            sat_strides = is_taper_week and not any(
                d.workout_type == "easy_strides" for d in days)
            days.append(_easy_day(5, sat_miles, state.paces, strides=sat_strides))
            easy_dows.remove(5)

        # MLR placement
        if rx.mlr_miles > 0 and 1 in easy_dows:
            days.append(_mlr_day(1, rx.mlr_miles, state.paces))
            easy_dows.remove(1)

        # Fill easy — varied by adjacency
        placed = sum(d.target_miles for d in days)
        remaining = max(0, rx.target_volume - placed)
        easy_count = len(easy_dows)

        if easy_count > 0:
            raw_weights = []
            for ed in easy_dows:
                is_post_quality = any(
                    d.day_of_week == (ed - 1) % 7
                    and d.workout_type in MIDWEEK_QUALITY_TYPES
                    for d in days
                )
                is_pre_long = any(
                    d.day_of_week == (ed + 1) % 7
                    and d.workout_type.startswith("long")
                    for d in days
                )
                is_pre_quality = any(
                    d.day_of_week == (ed + 1) % 7
                    and d.workout_type in MIDWEEK_QUALITY_TYPES
                    for d in days
                )
                if is_post_quality:
                    raw_weights.append(0.45)
                elif is_pre_long:
                    raw_weights.append(0.50)
                elif is_pre_quality:
                    raw_weights.append(0.70)
                else:
                    raw_weights.append(1.30)

            wt_sum = sum(raw_weights) or 1.0
            norm = [w / wt_sum for w in raw_weights]

            easy_cap = min(14.0, rx.target_volume / max(state.days_per_week, 3) * 1.6)
            post_quality_cap = min(8.0, rx.target_volume / max(state.days_per_week, 3) * 0.8)
            for idx_e, ed in enumerate(easy_dows):
                mi = round(remaining * norm[idx_e], 1)
                if raw_weights[idx_e] <= 0.50:
                    mi = min(mi, post_quality_cap)
                else:
                    mi = min(mi, easy_cap)
                floor = 4.0 if raw_weights[idx_e] >= 1.0 else 2.0
                mi = max(floor, mi)

                stride_parity = rx.week_number % 2 == 0
                low_days = state.days_per_week <= 3
                is_post_q = raw_weights[idx_e] <= 0.45
                is_taper_week = rx.phase_label == "taper"
                needs_strides = (
                    not any(d.workout_type == "easy_strides" for d in days)
                    and (
                        is_taper_week
                        or (
                            not is_post_q
                            and (
                                (stride_parity and idx_e == 0)
                                or (not stride_parity and idx_e == easy_count - 1)
                                or low_days
                            )
                        )
                    )
                )
                days.append(_easy_day(ed, mi, state.paces, strides=needs_strides))

        days.sort(key=lambda d: d.day_of_week)

        # Cap assembled volume at target to preserve sawtooth fidelity
        raw_total = sum(d.target_miles for d in days)
        if raw_total > rx.target_volume > 0:
            overshoot = raw_total - rx.target_volume
            easy_pool = sorted(
                [d for d in days if d.workout_type in ("easy", "easy_strides", "recovery")],
                key=lambda d: -d.target_miles,
            )
            for d in easy_pool:
                if overshoot <= 0:
                    break
                trim = min(overshoot, d.target_miles - 2.0)
                if trim > 0:
                    d.target_miles = round(d.target_miles - trim, 1)
                    overshoot -= trim

        total = round(sum(d.target_miles for d in days), 1)

        weeks.append(WeekPlan(
            week_number=rx.week_number,
            theme=rx.phase_label,
            start_date=week_start,
            days=days,
            total_miles=total,
            is_cutback=rx.is_cutback,
        ))

    return weeks


# ── Day helpers ───────────────────────────────────────────────────────

def _rest_day(dow):
    return DayPlan(dow, "rest", "Rest", "Complete rest.", 0.0, "rest", {}, [])


def _easy_day(dow, miles, paces, strides=False):
    pace = _pace_label(paces, "easy")
    p_dict = {}
    if paces and "easy" in paces:
        p_dict["easy"] = format_pace(paces["easy"])
    if strides:
        return DayPlan(
            dow, "easy_strides", "Easy + strides",
            f"{miles:.0f}mi @ {pace} + 6x20s strides",
            round(miles, 1), "easy", p_dict, [],
        )
    return DayPlan(
        dow, "easy", "Easy run",
        f"{miles:.0f}mi @ {pace}",
        round(miles, 1), "easy", p_dict, [],
    )


def _long_run_day(dow, miles, paces):
    pace = _pace_label(paces, "easy")
    p_dict = {}
    if paces and "easy" in paces:
        p_dict["easy"] = format_pace(paces["easy"])
    return DayPlan(
        dow, "long", f"Long run -- {miles:.0f}mi",
        f"{miles:.0f}mi @ {pace}",
        round(miles, 1), "easy", p_dict, [],
    )


def _mlr_day(dow, miles, paces):
    pace = _pace_label(paces, "easy")
    p_dict = {}
    if paces and "easy" in paces:
        p_dict["easy"] = format_pace(paces["easy"])
    return DayPlan(
        dow, "medium_long", f"Medium-long -- {miles:.0f}mi",
        f"{miles:.0f}mi @ {pace}",
        round(miles, 1), "easy", p_dict, [],
    )


def _make_day(dow, rx_dict, paces):
    p_dict = {}
    if paces:
        if "threshold" in rx_dict["type"] or rx_dict["type"] in ("cruise_intervals", "broken_threshold"):
            if "threshold" in paces:
                p_dict["threshold"] = format_pace(paces["threshold"])
        elif "interval" in rx_dict["type"]:
            if "interval" in paces:
                p_dict["interval"] = format_pace(paces["interval"])
        elif "rep" in rx_dict["type"]:
            if "repetition" in paces:
                p_dict["repetition"] = format_pace(paces["repetition"])
            elif "interval" in paces:
                p_dict["repetition"] = format_pace(paces["interval"])
        elif "mp" in rx_dict["type"]:
            if "marathon" in paces:
                p_dict["marathon"] = format_pace(paces["marathon"])
            if "easy" in paces:
                p_dict["easy"] = format_pace(paces["easy"])
        elif "hmp" in rx_dict["type"]:
            if "threshold" in paces and "marathon" in paces:
                mp = paces["marathon"]
                tp = paces["threshold"]
                p_dict["half_marathon"] = format_pace((mp + tp) / 2)
            if "easy" in paces:
                p_dict["easy"] = format_pace(paces["easy"])
        if "easy" in paces and rx_dict["type"].startswith("long"):
            p_dict["easy"] = format_pace(paces["easy"])

    return DayPlan(
        dow, rx_dict["type"], rx_dict["name"], rx_dict["desc"],
        rx_dict["miles"], rx_dict["intensity"], p_dict, [],
    )


# ═══════════════════════════════════════════════════════════════════════
# Couch-to-10K (day-one path)
# ═══════════════════════════════════════════════════════════════════════

def _generate_couch_to_10k(plan_start, horizon_weeks, race_date, days_per_week=6):
    STAGES = [
        ("Walk 1mi, Run 1mi, Walk 1mi", 3.0, "Run 3mi", 3.0),
        ("Walk 1mi, Run 1mi, Walk 1mi", 3.0, "Run 3mi", 3.0),
        ("Walk 1mi, Run 2mi", 3.0, "Run 4mi", 4.0),
        ("Run 3mi", 3.0, "Run 6mi", 6.0),
        ("Run 3mi", 3.0, "Run 6mi", 6.0),
        ("Run 3mi", 3.0, "Run 6mi", 6.0),
        ("Run 4mi", 4.0, "Run 8mi", 8.0),
        ("Run 4mi", 4.0, "Run 8mi", 8.0),
        ("Run 4mi", 4.0, "Run 8mi", 8.0),
    ]
    budget = max(1, horizon_weeks - 1)
    selected = STAGES[:budget]
    total_plan = len(selected) + 1
    race_monday = race_date - timedelta(days=race_date.weekday())
    start = race_monday - timedelta(weeks=total_plan - 1)

    weekday_running = min(days_per_week - 1, 6)
    rest_dows = list(range(weekday_running, 6))

    weeks = []
    for idx, (dd, dm, ld, lm) in enumerate(selected):
        ws = start + timedelta(weeks=idx)
        wtype = "walk_run" if "Walk" in dd else "easy"
        d = [DayPlan(dow, wtype, dd, dd, dm, "easy", {}, [])
             for dow in range(weekday_running)]
        for rd in rest_dows:
            d.append(_rest_day(rd))
        d.append(DayPlan(6, "long", ld, ld, lm, "easy", {}, []))
        total = round(dm * weekday_running + lm, 1)
        weeks.append(WeekPlan(idx + 1, "progression", ws, d, total))

    tw = len(selected) + 1
    ws = start + timedelta(weeks=len(selected))
    taper_running = min(days_per_week - 1, 5)
    td = [DayPlan(dow, "easy", "Easy 3mi", "3mi easy", 3.0, "easy", {}, [])
          for dow in range(taper_running)]
    for rd in range(taper_running, 6):
        td.append(_rest_day(rd))
    td.append(DayPlan(6, "race", "Race Day", "Warm up, execute, celebrate.",
                       0.0, "race", {}, []))
    weeks.append(WeekPlan(tw, "taper", ws, td, round(3.0 * taper_running, 1)))
    return weeks


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def _apply_tune_up_races(
    weeks: List[WeekPlan],
    tune_up_races: List[Dict],
    plan_start: date,
) -> List[WeekPlan]:
    """Modify plan weeks for tune-up races.

    Tune-up week becomes mini-taper: keep one sharpening session,
    drop MLR, reduce easy days, insert race day + pre-race shakeout.
    Following week becomes hard taper: all quality converted to easy,
    deep volume cut for absorption and compensation.
    """
    if not tune_up_races:
        return weeks

    for tune in tune_up_races:
        tune_date = tune["date"]
        if isinstance(tune_date, str):
            tune_date = date.fromisoformat(tune_date)

        days_offset = (tune_date - plan_start).days
        if days_offset < 0:
            continue
        wk_idx = days_offset // 7
        race_dow = days_offset % 7

        if wk_idx >= len(weeks):
            continue

        race_dist = tune.get("distance", "10k")
        dist_miles = {"5k": 3.1, "10k": 6.2, "10_mile": 10.0,
                      "half_marathon": 13.1}.get(race_dist, 6.2)
        race_name = tune.get("name") or f"{race_dist} tune-up"

        week = weeks[wk_idx]

        race_day = DayPlan(
            day_of_week=race_dow,
            workout_type="tune_up_race",
            name=race_name,
            description=f"RACE: {race_name}",
            target_miles=dist_miles,
            intensity="race",
            paces={},
            notes=[tune.get("purpose", "sharpening")],
        )

        new_days = []
        kept_one_quality = False
        for d in week.days:
            if d.day_of_week == race_dow:
                continue

            prev_day_dow = (race_dow - 1) % 7
            if d.day_of_week == prev_day_dow and d.workout_type not in ("rest",):
                new_days.append(DayPlan(
                    day_of_week=prev_day_dow,
                    workout_type="easy",
                    name="Pre-race shakeout",
                    description="Short easy shakeout before tune-up race.",
                    target_miles=min(d.target_miles, 3.0),
                    intensity="easy",
                    paces=d.paces,
                ))
                continue

            if d.workout_type == "medium_long":
                new_days.append(DayPlan(
                    day_of_week=d.day_of_week,
                    workout_type="easy",
                    name="Easy run",
                    description="Easy run — taper week, MLR dropped.",
                    target_miles=min(d.target_miles, 7.0),
                    intensity="easy",
                    paces=d.paces,
                ))
                continue

            if d.workout_type in MIDWEEK_QUALITY_TYPES and not kept_one_quality:
                kept_one_quality = True
                new_days.append(d)
                continue

            if d.workout_type in MIDWEEK_QUALITY_TYPES:
                new_days.append(DayPlan(
                    day_of_week=d.day_of_week,
                    workout_type="easy",
                    name="Easy run",
                    description="Easy run — mini-taper, quality capped.",
                    target_miles=min(d.target_miles, 6.0),
                    intensity="easy",
                    paces=d.paces,
                ))
                continue

            new_days.append(d)

        new_days.append(race_day)

        for j, d in enumerate(new_days):
            if d.workout_type in ("easy", "easy_strides") and d.target_miles > 6.0:
                new_days[j] = DayPlan(
                    day_of_week=d.day_of_week,
                    workout_type=d.workout_type,
                    name=d.name,
                    description=d.description,
                    target_miles=round(d.target_miles * 0.70, 1),
                    intensity=d.intensity,
                    paces=d.paces,
                )

        new_days.sort(key=lambda d: d.day_of_week)
        new_total = round(sum(d.target_miles for d in new_days), 1)
        weeks[wk_idx] = WeekPlan(
            week_number=week.week_number,
            theme=week.theme,
            start_date=week.start_date,
            days=new_days,
            total_miles=new_total,
            is_cutback=week.is_cutback,
        )

        post_idx = wk_idx + 1
        if post_idx < len(weeks):
            pw = weeks[post_idx]
            lr_quality_types = frozenset({
                "long_mp", "long_hmp", "long_progressive", "long_fast_finish",
            })
            recovery_days = []
            for d in pw.days:
                if d.workout_type in MIDWEEK_QUALITY_TYPES:
                    recovery_days.append(DayPlan(
                        day_of_week=d.day_of_week,
                        workout_type="easy",
                        name="Post-race recovery",
                        description="Easy — hard taper, let the body absorb.",
                        target_miles=max(3.0, round(d.target_miles * 0.5, 1)),
                        intensity="easy",
                        paces=d.paces,
                    ))
                elif d.workout_type in lr_quality_types:
                    recovery_days.append(DayPlan(
                        day_of_week=d.day_of_week,
                        workout_type="long",
                        name=f"Long run -- {d.target_miles:.0f}mi",
                        description=f"Easy long run — absorption week, no quality.",
                        target_miles=round(d.target_miles * 0.75, 1),
                        intensity="easy",
                        paces=d.paces,
                    ))
                elif d.workout_type == "medium_long":
                    recovery_days.append(DayPlan(
                        day_of_week=d.day_of_week,
                        workout_type="easy",
                        name="Easy run",
                        description="Easy — hard taper, MLR dropped.",
                        target_miles=min(d.target_miles, 6.0),
                        intensity="easy",
                        paces=d.paces,
                    ))
                else:
                    recovery_days.append(d)
            recovery_days.sort(key=lambda d: d.day_of_week)
            rtotal = round(sum(d.target_miles for d in recovery_days), 1)
            weeks[post_idx] = WeekPlan(
                week_number=pw.week_number,
                theme=pw.theme,
                start_date=pw.start_date,
                days=recovery_days,
                total_miles=rtotal,
                is_cutback=pw.is_cutback,
            )

    return weeks


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
    personal_lr_floor: float = 0.0,
    tune_up_races: Optional[List[Dict]] = None,
    taper_weeks: Optional[int] = None,
    fingerprint: Optional[FingerprintParams] = None,
) -> List[WeekPlan]:
    if taper_weeks is not None:
        taper_weeks = max(1, min(taper_weeks, 3))

    state = resolve_athlete_state(
        race_distance=race_distance, race_date=race_date,
        plan_start=plan_start, horizon_weeks=horizon_weeks,
        days_per_week=days_per_week, starting_vol=starting_vol,
        current_lr=current_lr, applied_peak=applied_peak,
        experience=experience, best_rpi=best_rpi,
        weeks_since_peak=weeks_since_peak, goal_time=goal_time,
        taper_weeks=taper_weeks,
        fingerprint=fingerprint,
    )

    if state.is_day_one:
        return _generate_couch_to_10k(plan_start, horizon_weeks, race_date,
                                      days_per_week=days_per_week)

    week_rxs = plan_weeks(state)
    weeks = assemble_plan(state, week_rxs)

    if tune_up_races:
        weeks = _apply_tune_up_races(weeks, tune_up_races, plan_start)

    logger.info(
        "N=1 plan: %d weeks, %.0f total miles, %s, needs=%s",
        len(weeks), sum(w.total_miles for w in weeks),
        race_distance, [n.value for n in state.adaptation_needs],
    )
    return weeks
