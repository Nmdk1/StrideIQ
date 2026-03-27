"""
Knowledge-Base Driven Plan Generator

Builds plans directly from athlete data + KB rules.
No phase builder. No scaler abstraction. No templates.

Each week is constructed by asking:
  1. What is this athlete's volume target this week?
  2. What is the primary adaptation emphasis?
  3. What quality work fits (0-2 sessions)?
  4. What should the long run be?
  5. Fill the rest with easy/recovery/rest.

Rules derived from:
  - PLAN_GENERATION_FRAMEWORK.md
  - threshold_pilot_v1.md, long_run_pilot_v1.md, easy_pilot_v1.md
  - intervals_pilot_v1.md, repetitions_pilot_v1.md
  - michael/TRAINING_PROFILE.md (founder exemplar for Structure A/B)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class DayPlan:
    day: int  # 0=Mon, 6=Sun
    workout_type: str
    variant_id: str
    target_miles: float
    description: str = ""
    segments: Optional[List[Dict[str, Any]]] = None


@dataclass
class WeekPlan:
    week: int
    emphasis: str
    target_volume: float
    long_run_miles: float
    quality_sessions: int
    is_cutback: bool = False
    days: List[DayPlan] = field(default_factory=list)
    notes: str = ""

    @property
    def actual_volume(self) -> float:
        return sum(d.target_miles for d in self.days)


@dataclass
class GeneratedTrainingPlan:
    distance: str
    duration_weeks: int
    days_per_week: int
    weeks: List[WeekPlan] = field(default_factory=list)


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


# ── Volume progression ─────────────────────────────────────────────────
def _build_volume_curve(
    starting_vol: float,
    peak_vol: float,
    duration_weeks: int,
    taper_weeks: int,
) -> tuple:
    """Returns (volumes, is_cutback_flags) lists."""
    build_weeks = duration_weeks - taper_weeks
    volumes = []
    cutbacks = []

    for w in range(1, build_weeks + 1):
        progress = (w - 1) / max(1, build_weeks - 1)
        raw = starting_vol + (peak_vol - starting_vol) * progress
        is_cutback = (w % 4 == 0)
        vol = raw * 0.80 if is_cutback else raw
        volumes.append(round(vol, 1))
        cutbacks.append(is_cutback)

    # Taper
    if taper_weeks >= 3:
        volumes.extend([round(peak_vol * 0.70, 1), round(peak_vol * 0.50, 1),
                         round(peak_vol * 0.40, 1)])
    elif taper_weeks == 2:
        volumes.extend([round(peak_vol * 0.60, 1), round(peak_vol * 0.40, 1)])
    elif taper_weeks == 1:
        volumes.append(round(peak_vol * 0.50, 1))
    cutbacks.extend([False] * taper_weeks)

    return volumes, cutbacks


# ── Long run progression ───────────────────────────────────────────────
_DISTANCE_LONG_RUN_CAP = {
    "5k": 16.0,
    "10k": 18.0,
    "half_marathon": 18.0,
    "marathon": 22.0,
}


def _build_long_run_curve(
    current_long: float,
    peak_long: float,
    weekly_volumes: List[float],
    is_cutback: List[bool],
    taper_weeks: int,
    distance: str = "marathon",
) -> List[float]:
    """
    Long run sized by:
    - 28-30% of weekly volume (cap)
    - +1-2mi per week from current toward peak
    - Distance-specific absolute cap (e.g. 18mi for 10K)
    - Cutback weeks: ~80% of previous non-cutback long
    - Taper: 65%, 45%, 35% of peak
    """
    duration = len(weekly_volumes)
    build_weeks = duration - taper_weeks
    longs = []
    last_non_cutback_long = current_long
    abs_cap = _DISTANCE_LONG_RUN_CAP.get(distance, 22.0)

    for w in range(1, duration + 1):
        vol = weekly_volumes[w - 1]
        vol_cap = vol * 0.30

        if w <= build_weeks:
            progress = (w - 1) / max(1, build_weeks - 1)
            raw_target = current_long + (peak_long - current_long) * progress
            target = min(raw_target, vol_cap, abs_cap)

            if is_cutback[w - 1]:
                target = round(last_non_cutback_long * 0.80, 1)
            else:
                last_non_cutback_long = target

            longs.append(round(max(target, current_long * 0.5), 1))
        else:
            taper_idx = w - build_weeks
            pct = {1: 0.65, 2: 0.45}.get(taper_idx, 0.35)
            lr = round(min(peak_long * pct, vol_cap), 1)
            longs.append(max(lr, 4.0))

    return longs


# ── Emphasis schedule ──────────────────────────────────────────────────
def _assign_emphasis(
    duration_weeks: int,
    taper_weeks: int,
    distance: str,
) -> List[str]:
    """
    Assign weekly emphasis with overlapping progression.
    Emphasis shifts but doesn't prevent touching other systems.
    """
    build_weeks = duration_weeks - taper_weeks
    emphasis = []

    if distance == "marathon":
        base_end = max(2, round(build_weeks * 0.27))
        threshold_end = max(base_end + 2, round(build_weeks * 0.53))
        mp_end = max(threshold_end + 2, round(build_weeks * 0.80))
        for w in range(1, build_weeks + 1):
            if w <= base_end:
                emphasis.append("base")
            elif w <= threshold_end:
                emphasis.append("threshold_emphasis")
            elif w <= mp_end:
                emphasis.append("mp_emphasis")
            else:
                emphasis.append("race_specific")
    elif distance == "half_marathon":
        base_end = max(2, round(build_weeks * 0.30))
        threshold_end = max(base_end + 2, round(build_weeks * 0.60))
        for w in range(1, build_weeks + 1):
            if w <= base_end:
                emphasis.append("base")
            elif w <= threshold_end:
                emphasis.append("threshold_emphasis")
            else:
                emphasis.append("race_specific")
    elif distance == "10k":
        base_end = max(2, round(build_weeks * 0.30))
        threshold_end = max(base_end + 2, round(build_weeks * 0.55))
        for w in range(1, build_weeks + 1):
            if w <= base_end:
                emphasis.append("base")
            elif w <= threshold_end:
                emphasis.append("threshold_emphasis")
            else:
                emphasis.append("race_specific")
    else:  # 5k
        base_end = max(2, round(build_weeks * 0.30))
        for w in range(1, build_weeks + 1):
            if w <= base_end:
                emphasis.append("base")
            else:
                emphasis.append("race_specific")

    for i in range(taper_weeks):
        if i < taper_weeks - 1:
            emphasis.append("taper")
        else:
            emphasis.append("race")

    return emphasis


# ── Week structure templates ───────────────────────────────────────────
# (day_index, role) — roles: long, rest, quality1, quality2, medium_long,
#                            easy, easy_strides, recovery
_WEEK_TEMPLATES = {
    7: [
        (0, "rest"),      # Mon
        (1, "medium_long"),   # Tue
        (2, "easy_strides"),  # Wed
        (3, "quality1"),  # Thu — primary quality
        (4, "easy"),      # Fri
        (5, "recovery"),  # Sat — pre-long
        (6, "long"),      # Sun
    ],
    6: [
        (0, "rest"),
        (1, "medium_long"),
        (2, "easy_strides"),
        (3, "quality1"),
        (4, "easy"),
        (5, "easy"),  # Sat pre-long easy
        (6, "long"),
    ],
    5: [
        (0, "rest"),
        (1, "easy_strides"),
        (2, "quality1"),
        (3, "easy"),
        (4, "rest"),
        (5, "easy"),  # Sat pre-long
        (6, "long"),
    ],
    4: [
        (0, "rest"),
        (1, "easy_strides"),
        (2, "quality1"),
        (3, "rest"),
        (4, "rest"),
        (5, "easy"),
        (6, "long"),
    ],
    3: [
        (0, "rest"),
        (1, "rest"),
        (2, "quality1"),
        (3, "rest"),
        (4, "rest"),
        (5, "rest"),
        (6, "long"),
    ],
}


def _get_quality2_day(days_per_week: int) -> Optional[int]:
    """Day index for second quality session, if available."""
    if days_per_week >= 6:
        return 1  # Tue (replaces medium_long when dual quality)
    if days_per_week >= 5:
        return 3  # Thu (swap easy for quality2)
    return None


# ── Week builder ───────────────────────────────────────────────────────
def _build_week(
    week_num: int,
    emphasis: str,
    target_vol: float,
    long_run_mi: float,
    days_per_week: int,
    distance: str,
    athlete: Dict[str, Any],
    week_in_block: int,
    total_build_weeks: int,
    is_cutback: bool,
    mp_block_week: int = 0,
) -> WeekPlan:
    """Build a single week from emphasis, volume, and athlete data."""
    template = _WEEK_TEMPLATES.get(days_per_week, _WEEK_TEMPLATES[5])
    current_weekly = athlete["current_weekly_miles"]

    # Avg easy run for this athlete: (vol - long) / (running_days - 1)
    avg_easy = (target_vol - long_run_mi) / max(1, days_per_week - 1)
    max_easy = avg_easy * 1.3  # no single easy run > 130% of average

    # ── Pick long run type (cutback weeks always easy long) ─────
    if is_cutback or emphasis in ("taper", "race"):
        long_type, long_variant = ("long", "long_easy_aerobic_staple")
    else:
        long_type, long_variant = _pick_long_run_type(
            emphasis, week_num, distance, long_run_mi, athlete,
            week_in_block, total_build_weeks, mp_block_week,
        )

    # ── Pick quality sessions (cutback: strides only) ──────────
    if is_cutback:
        quality_slots = []
    elif emphasis == "race":
        quality_slots = []
    else:
        quality_slots = _pick_quality_sessions(
            emphasis, week_num, distance, target_vol, athlete,
            week_in_block, total_build_weeks,
        )

    # ── Handle race week specially (before template) ─────────
    if emphasis == "race":
        days = []
        race_day = 6
        race_dist_mi = {"5k": 3.1, "10k": 6.2, "half_marathon": 13.1,
                        "marathon": 26.2}.get(distance, 6.2)
        days.append(DayPlan(day=race_day, workout_type="RACE",
                            variant_id="race_day", target_miles=race_dist_mi,
                            description="RACE DAY"))
        shakeout_mi = round(_clamp(avg_easy * 0.4, 2.0, 3.0), 1)
        days.append(DayPlan(day=5, workout_type="shakeout",
                            variant_id="easy_conversational_staple",
                            target_miles=shakeout_mi))
        days.append(DayPlan(day=4, workout_type="rest",
                            variant_id="rest_day_complete", target_miles=0.0))
        days.append(DayPlan(day=0, workout_type="rest",
                            variant_id="rest_day_complete", target_miles=0.0))

        remaining_target = max(0, target_vol - race_dist_mi - shakeout_mi)
        other_days = [1, 2, 3]
        if days_per_week <= 4:
            other_days = other_days[:max(1, days_per_week - 2)]
        per_day = round(_clamp(remaining_target / max(1, len(other_days)),
                               2.0, max_easy * 0.6), 1)
        for i, d in enumerate(other_days):
            wt = "easy_strides" if i == 0 else "easy"
            vid = ("easy_strides_neuromuscular_touch" if i == 0
                   else "easy_conversational_staple")
            days.append(DayPlan(day=d, workout_type=wt, variant_id=vid,
                                target_miles=per_day))
        for d in range(7):
            if d not in {dp.day for dp in days}:
                days.append(DayPlan(day=d, workout_type="rest",
                                    variant_id="rest_day_complete", target_miles=0.0))
        days.sort(key=lambda d: d.day)
        return WeekPlan(
            week=week_num, emphasis=emphasis, target_volume=target_vol,
            long_run_miles=0.0, quality_sessions=0, is_cutback=False, days=days,
            notes="Race week",
        )

    # ── Build day list from template ───────────────────────────
    # Two-pass: first pass places fixed slots (rest, long, quality1, medium_long).
    # Second pass places remaining quality into available easy slots.
    days: List[DayPlan] = []
    used_vol = 0.0
    non_sized_roles = []
    quality_placed = 0

    for day_idx, role in template:
        if role == "rest":
            days.append(DayPlan(day=day_idx, workout_type="rest",
                                variant_id="rest_day_complete", target_miles=0.0))
        elif role == "long":
            days.append(DayPlan(day=day_idx, workout_type=long_type,
                                variant_id=long_variant, target_miles=long_run_mi))
            used_vol += long_run_mi
        elif role == "quality1":
            if quality_placed < len(quality_slots):
                q = quality_slots[quality_placed]
                quality_placed += 1
                q_miles = round(_clamp(target_vol * q[2], 3.0, max_easy), 1)
                days.append(DayPlan(day=day_idx, workout_type=q[0],
                                    variant_id=q[1], target_miles=q_miles))
                used_vol += q_miles
            else:
                non_sized_roles.append((day_idx, "easy_strides"))
        elif role == "medium_long":
            if len(quality_slots) >= 2 and quality_placed < len(quality_slots):
                # Second quality replaces medium-long (only when there ARE 2+)
                q = quality_slots[quality_placed]
                quality_placed += 1
                q_miles = round(_clamp(target_vol * q[2], 3.0, max_easy), 1)
                days.append(DayPlan(day=day_idx, workout_type=q[0],
                                    variant_id=q[1], target_miles=q_miles))
                used_vol += q_miles
            elif current_weekly >= 30:
                ml_miles = round(min(long_run_mi * 0.70, max_easy), 1)
                days.append(DayPlan(day=day_idx, workout_type="medium_long",
                                    variant_id="medium_long_aerobic_staple",
                                    target_miles=ml_miles))
                used_vol += ml_miles
            else:
                non_sized_roles.append((day_idx, "easy"))
        elif role in ("easy_strides", "easy", "recovery"):
            non_sized_roles.append((day_idx, role))

    # If any quality sessions still unplaced (e.g., 5-day plan with 2 quals),
    # place into an available easy slot. Never place quality on the day
    # before the long run (day 5 = Saturday before Sunday long).
    long_day = next((d.day for d in days if d.workout_type in
                     ("long", "long_mp", "long_hmp", "RACE")), 6)
    pre_long_day = (long_day - 1) % 7

    while quality_placed < len(quality_slots) and non_sized_roles:
        q = quality_slots[quality_placed]
        quality_placed += 1
        q1_day = next((d.day for d in days if d.workout_type not in
                       ("rest", "long", "medium_long", "easy", "easy_strides",
                        "recovery", "shakeout")), -1)
        # Find slot: not pre-long day, prefer separation from quality1
        best_idx = 0
        best_sep = -1
        for i, (di, _) in enumerate(non_sized_roles):
            if di == pre_long_day:
                continue
            sep = abs(di - q1_day) if q1_day >= 0 else 99
            if sep > best_sep:
                best_sep = sep
                best_idx = i
        day_idx, _ = non_sized_roles.pop(best_idx)
        q_miles = round(_clamp(target_vol * q[2], 3.0, max_easy), 1)
        days.append(DayPlan(day=day_idx, workout_type=q[0],
                            variant_id=q[1], target_miles=q_miles))
        used_vol += q_miles

    # ── Distribute remaining volume across easy/recovery days ──
    remaining = target_vol - used_vol
    if non_sized_roles and remaining > 0:
        per_day = round(remaining / len(non_sized_roles), 1)
        per_day = _clamp(per_day, 2.0, max_easy)

        for day_idx, role_type in non_sized_roles:
            actual = min(per_day, remaining)
            actual = max(actual, 2.0)
            remaining -= actual

            if role_type == "easy_strides":
                days.append(DayPlan(day=day_idx, workout_type="easy_strides",
                                    variant_id="easy_strides_neuromuscular_touch",
                                    target_miles=round(actual, 1)))
            elif role_type == "recovery":
                days.append(DayPlan(day=day_idx, workout_type="recovery",
                                    variant_id="recovery_run_aerobic",
                                    target_miles=round(actual * 0.8, 1)))
            else:
                days.append(DayPlan(day=day_idx, workout_type="easy",
                                    variant_id="easy_conversational_staple",
                                    target_miles=round(actual, 1)))

    days.sort(key=lambda d: d.day)

    return WeekPlan(
        week=week_num, emphasis=emphasis, target_volume=target_vol,
        long_run_miles=long_run_mi, quality_sessions=len(quality_slots),
        is_cutback=is_cutback, days=days,
    )


# ── Long run type selection ────────────────────────────────────────────
def _pick_long_run_type(
    emphasis: str,
    week_num: int,
    distance: str,
    long_mi: float,
    athlete: Dict[str, Any],
    week_in_block: int,
    total_build_weeks: int,
    mp_block_week: int = 0,
) -> tuple:
    """
    Returns (workout_type, variant_id) for the long run.
    Structure A/B for marathon: alternates MP longs within the combined
    mp_emphasis + race_specific block (mp_block_week counter).
    """
    if emphasis == "base":
        return ("long", "long_easy_aerobic_staple")

    elif emphasis == "threshold_emphasis":
        if week_in_block >= 3 and week_in_block % 3 == 0:
            return ("long", "long_progressive_moderate_finish")
        return ("long", "long_easy_aerobic_staple")

    elif emphasis in ("mp_emphasis", "race_specific") and distance == "marathon":
        # Builder-tier: athletes below 35mpw don't do MP long runs
        current_vol = athlete.get("current_weekly_miles", 0)
        if current_vol < 35:
            return ("long", "long_progressive_moderate_finish")
        # Structure A/B within the MP block: odd mp_block_weeks = A (easy long),
        # even mp_block_weeks = B (MP long). First non-cutback week starts
        # with easy (A) to establish the pattern.
        if mp_block_week % 2 == 0:
            return ("long_mp", "long_mp_continuous_marathon")
        else:
            return ("long", "long_progressive_moderate_finish")

    elif emphasis == "race_specific" and distance == "half_marathon":
        if week_num % 2 == 0:
            return ("long_hmp", "long_hmp_finish_half_marathon")
        return ("long", "long_progressive_moderate_finish")

    elif emphasis == "race_specific":
        return ("long", "long_progressive_moderate_finish")

    return ("long", "long_easy_aerobic_staple")


# ── Quality session selection ──────────────────────────────────────────
def _pick_quality_sessions(
    emphasis: str,
    week_num: int,
    distance: str,
    target_vol: float,
    athlete: Dict[str, Any],
    week_in_block: int,
    total_build_weeks: int,
) -> List[tuple]:
    """
    Returns list of (workout_type, variant_id, pct_of_volume) tuples.
    Max 2 quality sessions. 80/20 rule.
    """
    if emphasis == "base":
        return [("easy_strides", "easy_strides_neuromuscular_touch", 0.12)]

    elif emphasis == "threshold_emphasis":
        if week_in_block <= 2:
            t_variant = "threshold_intervals_5_to_6_min"
            t_type = "threshold_intervals"
        elif week_in_block <= 4:
            t_variant = "threshold_intervals_8_to_12_min"
            t_type = "threshold_intervals"
        else:
            t_variant = "threshold_continuous_progressive"
            t_type = "threshold"

        sessions = [(t_type, t_variant, 0.12)]

        if distance in ("5k", "10k") and week_in_block >= 3:
            sessions.append(("intervals", "vo2_light_touch_after_threshold_week", 0.08))

        return sessions

    elif emphasis == "mp_emphasis" and distance == "marathon":
        # Structure A: threshold quality (odd weeks)
        # Structure B: MP in long, no hard quality (even weeks)
        if week_num % 2 == 1:
            return [("threshold", "threshold_continuous_progressive", 0.12)]
        return []

    elif emphasis == "race_specific":
        if distance == "marathon":
            if week_num % 2 == 1:
                return [("threshold", "threshold_continuous_progressive", 0.12)]
            return []
        elif distance in ("half_marathon", "10k"):
            sessions = [("intervals", _pick_interval_variant(distance, week_in_block), 0.10)]
            if target_vol >= 25:
                sessions.append(("threshold", "threshold_continuous_short_block", 0.08))
            return sessions
        else:  # 5K
            sessions = [("intervals", _pick_interval_variant(distance, week_in_block), 0.10)]
            if week_in_block % 2 == 0:
                sessions.append(("repetitions", "reps_200m_neuromuscular_early", 0.05))
            return sessions

    elif emphasis == "taper":
        return [("easy_strides", "easy_strides_neuromuscular_touch", 0.10)]

    return []


def _pick_interval_variant(distance: str, week_in_block: int) -> str:
    if distance == "5k":
        if week_in_block <= 2:
            return "vo2_800m_reps_development"
        return "vo2_5k_peak_1000_development"
    elif distance == "10k":
        if week_in_block <= 2:
            return "vo2_1000m_reps_classic"
        return "vo2_1200m_10k_race_rhythm"
    return "vo2_1000m_reps_classic"


# ── Main entry point ───────────────────────────────────────────────────
def generate_plan(
    distance: str,
    duration_weeks: int,
    days_per_week: int,
    current_weekly_miles: float,
    current_long_run_miles: float,
    peak_weekly_miles: Optional[float] = None,
    peak_long_run_miles: Optional[float] = None,
    experience_level: str = "intermediate",
) -> GeneratedTrainingPlan:
    """
    Generate a training plan from athlete data and KB rules.
    """
    taper_weeks = {"marathon": 3, "half_marathon": 2, "10k": 1, "5k": 1}.get(distance, 2)

    if peak_weekly_miles and peak_weekly_miles > current_weekly_miles:
        target_peak = min(peak_weekly_miles * 1.05, current_weekly_miles * 1.30)
    else:
        target_peak = current_weekly_miles * 1.20

    if peak_long_run_miles and peak_long_run_miles > current_long_run_miles:
        target_peak_long = peak_long_run_miles
    else:
        distance_long_caps = {
            "marathon": 22.0, "half_marathon": 16.0, "10k": 12.0, "5k": 10.0
        }
        target_peak_long = min(
            current_long_run_miles * 1.50,
            distance_long_caps.get(distance, 15.0),
        )

    volumes, cutback_flags = _build_volume_curve(
        starting_vol=current_weekly_miles,
        peak_vol=target_peak,
        duration_weeks=duration_weeks,
        taper_weeks=taper_weeks,
    )

    long_runs = _build_long_run_curve(
        current_long=current_long_run_miles,
        peak_long=target_peak_long,
        weekly_volumes=volumes,
        is_cutback=cutback_flags,
        taper_weeks=taper_weeks,
        distance=distance,
    )

    emphasis_schedule = _assign_emphasis(duration_weeks, taper_weeks, distance)

    athlete_ctx = {
        "current_weekly_miles": current_weekly_miles,
        "current_long_run_miles": current_long_run_miles,
        "peak_weekly_miles": peak_weekly_miles,
        "peak_long_run_miles": peak_long_run_miles,
        "experience_level": experience_level,
    }

    plan = GeneratedTrainingPlan(
        distance=distance,
        duration_weeks=duration_weeks,
        days_per_week=days_per_week,
    )

    current_emphasis = None
    block_week = 0
    mp_block_week = 0

    for w in range(duration_weeks):
        emp = emphasis_schedule[w]
        if emp != current_emphasis:
            current_emphasis = emp
            block_week = 1
        else:
            block_week += 1

        if emp in ("mp_emphasis", "race_specific") and not cutback_flags[w]:
            mp_block_week += 1

        week = _build_week(
            week_num=w + 1,
            emphasis=emp,
            target_vol=volumes[w],
            long_run_mi=long_runs[w],
            days_per_week=days_per_week,
            distance=distance,
            athlete=athlete_ctx,
            week_in_block=block_week,
            total_build_weeks=duration_weeks - taper_weeks,
            is_cutback=cutback_flags[w],
            mp_block_week=mp_block_week,
        )
        plan.weeks.append(week)

    return plan
