"""
Plan Engine V2 — orchestrator.

Single public entry point: generate_plan_v2().

Takes FitnessBank + FingerprintParams + LoadContext directly —
decoupled from the database.  The harness creates mocks; production
callers load real data and pass it in.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List, Optional

from services.fitness_bank import FitnessBank, ExperienceLevel, rpi_equivalent_time
from services.plan_framework.fingerprint_bridge import FingerprintParams
from services.plan_framework.load_context import LoadContext

from .models import (
    PaceLadder,
    TuneUpRace,
    V2DayPlan,
    V2PlanPreview,
    V2WeekPlan,
)
from .pace_ladder import compute_pace_ladder
from .periodizer import build_race_phases, build_build_phases, build_maintain_phases
from .volume import (
    compute_volume_targets,
    compute_peak_long_run_mi,
    compute_start_long_run_mi,
    compute_long_run_staircase,
    long_run_range_for_week,
    readiness_gate,
    taper_weeks_for_event,
)
from .day_scheduler import schedule_week
from .workout_library import build_day_from_slot
from .build_workouts import (
    build_onramp_week,
    build_volume_week,
    build_intensity_week,
    build_maintain_week,
    compute_peak_workout_state,
)

try:
    from services.plan_quality_gate import compute_athlete_long_run_floor
except ImportError:
    compute_athlete_long_run_floor = None

logger = logging.getLogger(__name__)


# ── Athlete Type Detection ───────────────────────────────────────────

def _detect_athlete_type(bank: FitnessBank) -> str:
    """Derive endurance/balanced/speed from race history.

    Compares half-marathon equivalent pace to marathon equivalent pace.
    HM pace <= 103% of MP → endurance-oriented.
    HM pace >= 107% of MP → speed-oriented.
    """
    if not bank.race_performances or bank.best_rpi <= 0:
        return "balanced"

    try:
        mp_time = rpi_equivalent_time(bank.best_rpi, 42195)
        hm_time = rpi_equivalent_time(bank.best_rpi, 21097)

        mp_pace = mp_time / 42.195  # sec/km
        hm_pace = hm_time / 21.097  # sec/km

        if mp_pace <= 0:
            return "balanced"

        ratio = hm_pace / mp_pace
        pct_of_mp = (1.0 / ratio) * 100.0

        if pct_of_mp >= 107:
            return "speed"
        elif pct_of_mp <= 103:
            return "endurance"
        return "balanced"
    except Exception:
        return "balanced"


# ── Anchor Type Selection ────────────────────────────────────────────

def _select_anchor_type(mode: str, goal_event: Optional[str]) -> str:
    """Anchor is always marathon. The pace ladder is athlete-derived,
    not event-derived. You don't run threshold slower because you're
    training for a marathon."""
    return "marathon"


# ── Training Age ─────────────────────────────────────────────────────

def _estimate_training_age(bank: FitnessBank) -> float:
    """Rough training age in years from experience level."""
    exp_years = {
        ExperienceLevel.BEGINNER: 0.5,
        ExperienceLevel.INTERMEDIATE: 2.5,
        ExperienceLevel.EXPERIENCED: 6.0,
        ExperienceLevel.ELITE: 10.0,
    }
    return exp_years.get(bank.experience_level, 2.0)


def _is_beginner(bank: FitnessBank) -> bool:
    """True if athlete should get sensory cues instead of zone names."""
    return (
        bank.experience_level == ExperienceLevel.BEGINNER
        or bank.current_weekly_miles < 30  # < 30 mi/wk (field is miles)
    )


# ── Defaults ─────────────────────────────────────────────────────────

def _default_weeks(mode: str, goal_event: Optional[str]) -> int:
    if mode != "race":
        defaults = {
            "build_onramp": 8,
            "build_volume": 6,
            "build_intensity": 4,
            "maintain": 4,
        }
        return defaults.get(mode, 6)

    event_defaults = {
        "5K": 8, "10K": 10, "half_marathon": 12, "marathon": 16,
        "50K": 12, "50_mile": 16, "100K": 16, "100_mile": 16,
    }
    return event_defaults.get(goal_event or "", 12)


# ── Engine ───────────────────────────────────────────────────────────

def generate_plan_v2(
    fitness_bank: FitnessBank,
    fingerprint: FingerprintParams,
    load_ctx: LoadContext,
    *,
    mode: str = "race",
    goal_event: Optional[str] = "marathon",
    target_date: Optional[date] = None,
    weeks_available: Optional[int] = None,
    previous_peak_state: Optional[dict] = None,
    units: str = "imperial",
    desired_peak_weekly_miles: Optional[float] = None,
    goal_time_seconds: Optional[int] = None,
    tune_up_races: Optional[List[TuneUpRace]] = None,
    plan_start_date: Optional[date] = None,
) -> V2PlanPreview:
    """Generate a full V2 plan.

    Produces a multi-week plan with per-phase periodization,
    volume progression, workout scheduling, and concrete segments.
    """
    if fitness_bank.best_rpi <= 0 and mode != "build_onramp":
        raise ValueError(
            "Cannot generate plan: athlete has no RPI. "
            "A race result or manual override is required."
        )

    # 1. Compute pace ladder (onramp can run without one)
    anchor_type = _select_anchor_type(mode, goal_event)
    if fitness_bank.best_rpi > 0:
        ladder = compute_pace_ladder(fitness_bank.best_rpi, anchor_type)
    else:
        ladder = _default_beginner_ladder(anchor_type)

    # 2. Detect athlete type
    athlete_type = _detect_athlete_type(fitness_bank)

    # 3. Training metadata
    training_age = _estimate_training_age(fitness_bank)
    beginner = _is_beginner(fitness_bank)

    # 4. Determine plan length
    if weeks_available is None:
        weeks_available = _default_weeks(mode, goal_event)

    # 5. Readiness gate (race mode only)
    l30_max = load_ctx.l30_max_easy_long_mi if load_ctx else None
    if mode == "race" and goal_event:
        start_lr = compute_start_long_run_mi(fitness_bank, l30_max)
        peak_lr = compute_peak_long_run_mi(
            fitness_bank, goal_event, desired_peak_weekly_miles,
        )
        refusal = readiness_gate(
            start_mi=start_lr,
            peak_mi=peak_lr,
            total_weeks=weeks_available,
            goal_event=goal_event,
            cutback_freq=fingerprint.cutback_frequency,
            experience=fitness_bank.experience_level,
            bank=fitness_bank,
        )
        if refusal:
            raise ValueError(refusal)
    else:
        start_lr = compute_start_long_run_mi(fitness_bank, l30_max)
        peak_lr = compute_peak_long_run_mi(
            fitness_bank, None, desired_peak_weekly_miles,
        )

    # 6. Pre-compute long run staircase (whole miles, cutbacks, taper)
    lr_staircase = compute_long_run_staircase(
        start_mi=start_lr,
        peak_mi=peak_lr,
        total_weeks=weeks_available,
        goal_event=goal_event,
        cutback_freq=fingerprint.cutback_frequency,
        experience=fitness_bank.experience_level,
        bank=fitness_bank,
    )
    logger.info(
        "Long run staircase: start=%dmi peak=%dmi weeks=%d → %s",
        start_lr, peak_lr, weeks_available, lr_staircase,
    )

    # 7. Build phase structure
    phase_structure = _build_phase_structure(
        mode, goal_event, weeks_available, fitness_bank.experience_level,
    )

    # 8. Compute volume targets (load context seeds starting volume)
    volume_targets = compute_volume_targets(
        fitness_bank, fingerprint, phase_structure, load_ctx,
        desired_peak_weekly_miles=desired_peak_weekly_miles,
    )

    # 9. Build every week
    weeks: List[V2WeekPlan] = []
    week_num = 0
    quality_week_index = 0

    for phase in phase_structure.phases:
        # Reset quality rotation at each phase boundary so every phase
        # starts with its highest-priority workout (threshold in general,
        # race-pace in specific, etc.)
        quality_week_index = 0

        for w in range(phase.weeks):
            week_num += 1
            vol = volume_targets[week_num - 1]

            # Long run from pre-computed staircase
            lr_range = long_run_range_for_week(lr_staircase, week_num)

            # Route to mode-specific builder
            if mode == "build_onramp":
                day_plans = build_onramp_week(
                    week_num, ladder, beginner, training_age,
                )
            elif mode == "build_volume":
                is_bonus = _is_bonus_week(week_num, weeks_available)
                day_plans = build_volume_week(
                    week_in_block=((week_num - 1) % 6) + 1,
                    ladder=ladder,
                    bank=fitness_bank,
                    is_beginner=beginner,
                    training_age=training_age,
                    weekly_target_km=vol["target_km"],
                    long_range_km=lr_range,
                    is_bonus_week=is_bonus,
                    previous_peak_state=previous_peak_state,
                )
            elif mode == "build_intensity":
                day_plans = build_intensity_week(
                    week_in_block=((week_num - 1) % 4) + 1,
                    ladder=ladder,
                    bank=fitness_bank,
                    is_beginner=beginner,
                    training_age=training_age,
                    weekly_target_km=vol["target_km"],
                    long_range_km=lr_range,
                    block_number=(previous_peak_state or {}).get(
                        "_block_number", 1,
                    ),
                    previous_peak_state=previous_peak_state,
                )
            elif mode == "maintain":
                day_plans = build_maintain_week(
                    week_in_block=((week_num - 1) % 4) + 1,
                    ladder=ladder,
                    bank=fitness_bank,
                    is_beginner=beginner,
                    training_age=training_age,
                    weekly_target_km=vol["target_km"],
                    long_range_km=lr_range,
                )
            else:
                # Race mode — use slot-based dispatcher
                lr_is_workout = _long_run_is_workout(
                    phase.name, w, vol["is_cutback"], phase.weeks,
                )
                effective_quality = phase.quality_density

                # Return-to-speed gate: athletes returning from break
                # or beginners ease in — week 1 volume only, week 2
                # gets at most 1 quality.
                if week_num == 1 and (
                    fitness_bank.experience_level == ExperienceLevel.BEGINNER
                    or fitness_bank.is_returning_from_break
                ):
                    effective_quality = 0
                elif week_num == 2 and fitness_bank.is_returning_from_break:
                    effective_quality = min(effective_quality, 1)

                # Taper step-down: final taper week (race week) gets
                # no scheduled quality — just strides and easy running.
                if phase.name == "taper" and w == phase.weeks - 1 and phase.weeks >= 2:
                    effective_quality = 0

                day_slots = schedule_week(
                    bank=fitness_bank,
                    fingerprint=fingerprint,
                    phase_name=phase.name,
                    quality_density=effective_quality,
                    is_cutback=vol["is_cutback"],
                    week_in_phase=w,
                    long_run_is_workout=lr_is_workout,
                    weekly_target_km=vol["target_km"],
                )
                day_plans = []
                for slot in day_slots:
                    day_plan = build_day_from_slot(
                        slot=slot,
                        ladder=ladder,
                        bank=fitness_bank,
                        phase_name=phase.name,
                        week_in_phase=w,
                        phase_weeks=phase.weeks,
                        is_beginner=beginner,
                        training_age=training_age,
                        goal_event=goal_event or "marathon",
                        weekly_target_km=vol["target_km"],
                        long_range_km=lr_range,
                        week_num=week_num,
                        total_weeks=weeks_available,
                        limiter=fingerprint.limiter,
                        primary_quality_emphasis=fingerprint.primary_quality_emphasis,
                        is_cutback=vol["is_cutback"],
                        quality_week_index=quality_week_index,
                    )
                    day_plans.append(day_plan)

                # P11: Deduplicate quality sessions within the week.
                day_plans = _deduplicate_quality_sessions(
                    day_plans, ladder, beginner, phase.name, w, phase.weeks,
                    training_age, goal_event or "marathon", week_num,
                )

                # Advance quality_week_index only on non-cutback weeks
                # that actually scheduled quality work.
                if effective_quality > 0 and not vol["is_cutback"]:
                    quality_week_index += 1

            # 9a. Reconcile easy-day distances to hit weekly target
            day_plans = _reconcile_week_distances(
                day_plans, vol["target_km"], ladder.easy,
            )

            weeks.append(V2WeekPlan(
                week_number=week_num,
                phase=phase.name,
                days=day_plans,
                is_cutback=vol["is_cutback"],
            ))

    # 9b. Insert tune-up races (post-process: replace days in affected weeks)
    if tune_up_races and mode == "race" and plan_start_date:
        weeks = _insert_tune_up_races(
            weeks, tune_up_races, plan_start_date, ladder,
            beginner, training_age, volume_targets,
        )

    # 10. Compute peak state for build-over-build seeding
    peak_state = compute_peak_workout_state(weeks)
    if previous_peak_state:
        peak_state["_previous_block"] = previous_peak_state

    block_num = 1
    if previous_peak_state and "_block_number" in previous_peak_state:
        block_num = previous_peak_state["_block_number"] + 1
    peak_state["_block_number"] = block_num

    # 9. Assemble preview
    return V2PlanPreview(
        mode=mode,
        goal_event=goal_event,
        total_weeks=weeks_available,
        weeks=weeks,
        pace_ladder={
            "paces": ladder.paces,
            "easy": ladder.easy,
            "long": ladder.long,
            "marathon": ladder.marathon,
            "threshold": ladder.threshold,
            "interval": ladder.interval,
            "repetition": ladder.repetition,
            "anchor_pace_sec_per_km": ladder.anchor_pace_sec_per_km,
            "anchor_type": ladder.anchor_type,
        },
        anchor_type=anchor_type,
        athlete_type=athlete_type,
        phase_structure=[
            {"name": p.name, "weeks": p.weeks, "focus": p.focus}
            for p in phase_structure.phases
        ],
        units=units,
        peak_workout_state=peak_state,
        block_number=block_num,
    )


def _insert_tune_up_races(
    weeks: List[V2WeekPlan],
    tune_ups: List[TuneUpRace],
    plan_start_date: date,
    ladder: PaceLadder,
    is_beginner: bool,
    training_age: float,
    volume_targets: Optional[list] = None,
) -> List[V2WeekPlan]:
    """Post-process: overlay tune-up race details onto generated weeks.

    For each tune-up race:
      1. Find the week it falls in (by date offset from plan start)
      2. Replace the race day with a tune_up_race workout
      3. Replace day-before with pre-race shakeout
      4. Replace day-after with post-race recovery
      5. Downgrade any remaining quality sessions in that week to easy
         (the race IS the quality for this week)

    Tune-ups in taper or race week are skipped (the goal race takes priority).
    """
    from datetime import timedelta
    from .workout_library import tune_up_race_day, pre_race_day, post_race_recovery

    plan_monday = plan_start_date - timedelta(days=plan_start_date.weekday())

    for tu in tune_ups:
        days_from_start = (tu.race_date - plan_monday).days
        week_idx = days_from_start // 7
        race_dow = tu.race_date.weekday()  # 0=Mon, 6=Sun

        if week_idx < 0 or week_idx >= len(weeks):
            logger.warning(
                "Tune-up race '%s' on %s falls outside plan range, skipping",
                tu.name, tu.race_date,
            )
            continue

        week = weeks[week_idx]

        if week.phase == "taper":
            logger.info(
                "Tune-up race '%s' falls in taper week %d, skipping "
                "(goal race takes priority)",
                tu.name, week.week_number,
            )
            continue

        day_map = {d.day_of_week: i for i, d in enumerate(week.days)}

        if race_dow in day_map:
            week.days[day_map[race_dow]] = tune_up_race_day(
                ladder, tu.distance_km, tu.name, tu.purpose,
                is_beginner, race_dow, week.phase,
            )

        pre_dow = (race_dow - 1) % 7
        pre_wraps = pre_dow > race_dow  # e.g. Mon race → Sun pre-race
        if not pre_wraps and pre_dow in day_map:
            week.days[day_map[pre_dow]] = pre_race_day(
                ladder, is_beginner, pre_dow, week.phase,
            )
        elif pre_wraps and week_idx > 0:
            prev_week = weeks[week_idx - 1]
            prev_day_map = {d.day_of_week: i for i, d in enumerate(prev_week.days)}
            if pre_dow in prev_day_map:
                prev_week.days[prev_day_map[pre_dow]] = pre_race_day(
                    ladder, is_beginner, pre_dow, prev_week.phase,
                )

        post_dow = (race_dow + 1) % 7
        post_wraps = post_dow < race_dow  # e.g. Sun race → Mon recovery
        weekly_km = volume_targets[week_idx]["target_km"] if volume_targets and week_idx < len(volume_targets) else 0.0
        if not post_wraps and post_dow in day_map:
            week.days[day_map[post_dow]] = post_race_recovery(
                ladder, is_beginner, post_dow, week.phase,
                weekly_target_km=weekly_km,
            )
        elif post_wraps and week_idx + 1 < len(weeks):
            next_week = weeks[week_idx + 1]
            next_day_map = {d.day_of_week: i for i, d in enumerate(next_week.days)}
            next_km = volume_targets[week_idx + 1]["target_km"] if volume_targets and week_idx + 1 < len(volume_targets) else 0.0
            if post_dow in next_day_map:
                next_week.days[next_day_map[post_dow]] = post_race_recovery(
                    ladder, is_beginner, post_dow, next_week.phase,
                    weekly_target_km=next_km,
                )

        _downgrade_types = {"long_easy", "long_run_moderate",
                            "long_run_progression_finish", "long_run_mp",
                            "long_run_fatigue_resistance", "long_fast_stepwise",
                            "medium_long"}
        modified_days = {race_dow}
        if not pre_wraps:
            modified_days.add(pre_dow)
        if not post_wraps:
            modified_days.add(post_dow)
        for i, day in enumerate(week.days):
            if day.day_of_week in modified_days:
                continue
            if day.workout_type in _downgrade_types:
                from .workout_library import easy_run
                dist_range = (8.0, 13.0)
                week.days[i] = easy_run(
                    ladder, dist_range,
                    is_beginner, day.day_of_week, week.phase,
                )

        # Re-reconcile the tune-up week's easy distances
        if volume_targets and week_idx < len(volume_targets):
            target_km = volume_targets[week_idx]["target_km"]
            week.days = _reconcile_week_distances(
                week.days, target_km, ladder.easy,
            )

        logger.info(
            "Inserted tune-up race '%s' (%s, %s) into week %d (%s phase)",
            tu.name, tu.distance, tu.purpose, week.week_number, week.phase,
        )

    return weeks


def _rebuild_as_cutback(
    week: V2WeekPlan,
    ladder: PaceLadder,
    is_beginner: bool,
) -> None:
    """Replace day plans in-place with cutback-appropriate workouts.

    Cutback week structure:
      - Rest days stay rest
      - Quality sessions → easy
      - One easy_strides day (the day after the old quality slot)
      - Long run → long_easy at ~75% of its current distance
      - Medium-long → easy
      - Regenerative → easy
      - Second rest day added (replaces the lowest-value easy day)
    """
    from .workout_library import easy_run, easy_with_strides, long_easy, rest_day

    lr_idx = None
    lr_km = 0.0
    quality_idx = None
    _soft_types = {"easy", "rest", "easy_strides", "pre_race",
                   "recovery", "tune_up_race"}

    for i, d in enumerate(week.days):
        if "long" in d.workout_type:
            lr_idx = i
            if d.distance_range_km:
                lr_km = (d.distance_range_km[0] + d.distance_range_km[1]) / 2.0
            elif d.target_distance_km:
                lr_km = d.target_distance_km
        elif d.workout_type not in _soft_types and d.workout_type != "rest":
            if quality_idx is None:
                quality_idx = i

    for i, d in enumerate(week.days):
        if d.workout_type == "rest":
            continue
        if i == lr_idx:
            cutback_lr_km = round(lr_km * 0.75, 1)
            rng = (cutback_lr_km - 1.5, cutback_lr_km + 1.5)
            training_age = 5.0
            week.days[i] = long_easy(
                ladder, rng, is_beginner, training_age,
                d.day_of_week, week.phase,
            )
        elif d.workout_type not in _soft_types:
            week.days[i] = easy_run(
                ladder, (8.0, 13.0), is_beginner,
                d.day_of_week, week.phase,
            )

    # Add strides on one easy day and a second rest day
    strides_placed = False
    rest_count = sum(1 for d in week.days if d.workout_type == "rest")
    for i, d in enumerate(week.days):
        if d.workout_type == "easy" and not strides_placed:
            week.days[i] = easy_with_strides(
                ladder, d.distance_range_km or (8.0, 13.0),
                is_beginner, d.day_of_week, week.phase,
            )
            strides_placed = True
        elif d.workout_type == "easy" and rest_count < 2:
            week.days[i] = rest_day(d.day_of_week, week.phase)
            rest_count += 1
            break


def _default_beginner_ladder(anchor_type: str) -> PaceLadder:
    """Stub ladder for brand-new runners with no RPI.

    Onramp mode is time-based, so paces aren't used for prescription.
    This ladder exists only to avoid None checks downstream.
    Conservative paces: ~7:00/km easy (~11:15/mi).
    """
    easy = 420.0  # 7:00/km
    anchor = 360.0 if anchor_type == "marathon" else 300.0
    paces = {}
    for pct in [75, 80, 85, 90, 92, 94, 95, 96, 100, 103, 105, 108, 110, 115, 120]:
        paces[pct] = anchor / (pct / 100.0)
    return PaceLadder(
        paces=paces,
        anchor_pace_sec_per_km=anchor,
        anchor_type=anchor_type,
        easy=easy,
        long=easy * 1.03,
        marathon=anchor,
        threshold=anchor * 0.95,
        interval=anchor * 0.87,
        repetition=anchor * 0.80,
        recovery=easy * 1.10,
    )


_EASY_TYPES = frozenset({
    "easy", "easy_strides", "pre_race", "recovery", "recovery_long",
})



_MI_TO_KM = 1.60934


def _estimate_day_km(day: V2DayPlan, easy_pace_sec_km: float) -> float:
    """Best-effort distance estimate for a single day plan."""
    if day.workout_type == "rest":
        return 0.0
    if day.target_distance_km:
        return day.target_distance_km
    if day.segments:
        total = 0.0
        for seg in day.segments:
            if seg.distance_km:
                total += seg.distance_km
            elif seg.duration_min and seg.pace_sec_per_km > 0:
                total += (seg.duration_min * 60.0) / seg.pace_sec_per_km
            elif seg.duration_min:
                total += (seg.duration_min * 60.0) / easy_pace_sec_km
        return total
    if day.distance_range_km:
        return (day.distance_range_km[0] + day.distance_range_km[1]) / 2.0
    return 0.0


def _reconcile_week_distances(
    day_plans: List[V2DayPlan],
    weekly_target_km: float,
    easy_pace_sec_km: float,
) -> List[V2DayPlan]:
    """Distribute weekly volume budget across easy days.

    Fixed-distance days (long run, medium-long, quality, regen) keep
    their distances. The remaining budget is split across easy/strides
    days with role-aware and phase-aware constraints.

    If the budget per easy day falls below the minimum useful run
    (5mi/8km), one easy day is converted to rest rather than
    prescribing junk volume.
    """
    if weekly_target_km <= 0:
        return day_plans

    phase = day_plans[0].phase if day_plans else "general"

    fixed_km = 0.0
    easy_indices = []
    for i, dp in enumerate(day_plans):
        if dp.workout_type == "rest":
            continue
        if dp.workout_type in _EASY_TYPES:
            easy_indices.append(i)
        else:
            fixed_km += _estimate_day_km(dp, easy_pace_sec_km)

    if not easy_indices:
        return day_plans

    remaining = max(0.0, weekly_target_km - fixed_km)

    floor_km = 5.0 * _MI_TO_KM     # 8km — minimum useful easy run
    if phase == "taper":
        ceiling_km = 6.0 * _MI_TO_KM   # ~10km — taper easy cap
    else:
        ceiling_km = 10.0 * _MI_TO_KM  # ~16km — normal ceiling

    # If budget per easy day is below floor, convert weakest to rest
    per_easy = remaining / len(easy_indices) if easy_indices else 0
    while per_easy < floor_km and len(easy_indices) > 1:
        drop_idx = easy_indices.pop()
        dp = day_plans[drop_idx]
        day_plans[drop_idx] = V2DayPlan(
            day_of_week=dp.day_of_week,
            workout_type="rest",
            title="Rest",
            description="Full rest or easy cross-training",
            phase=dp.phase,
        )
        per_easy = remaining / len(easy_indices) if easy_indices else 0

    for idx in easy_indices:
        dp = day_plans[idx]
        role = dp.workout_type

        if role == "recovery":
            target = min(per_easy, 5.0 * _MI_TO_KM)
            target = max(target, 3.0 * _MI_TO_KM)
        elif role == "pre_race":
            target = 5.0 * _MI_TO_KM
        else:
            target = max(floor_km, min(per_easy, ceiling_km))

        tolerance = 1.5
        lo = round(target - tolerance, 1)
        hi = round(target + tolerance, 1)
        day_plans[idx] = V2DayPlan(
            day_of_week=dp.day_of_week,
            workout_type=dp.workout_type,
            title=dp.title,
            description=dp.description,
            phase=dp.phase,
            segments=dp.segments,
            target_distance_km=dp.target_distance_km,
            distance_range_km=(max(3.0, lo), hi),
            duration_range_min=dp.duration_range_min,
            fueling=dp.fueling,
        )

    return day_plans


def _deduplicate_quality_sessions(
    day_plans, ladder, is_beginner, phase_name, week_in_phase, phase_weeks,
    training_age, goal_event, week_num,
):
    """If two quality sessions in the same week have the same workout_type,
    swap the second for a complementary workout from a different system."""
    from .workout_library import (
        threshold_cruise, vo2max_intervals, steady_run,
        regenerative_threshold,
    )

    quality_indices = [
        i for i, dp in enumerate(day_plans)
        if dp.workout_type not in ("easy", "rest", "long_run", "easy_strides", "regenerative")
    ]
    if len(quality_indices) < 2:
        return day_plans

    seen_types = set()
    for idx in quality_indices:
        wtype = day_plans[idx].workout_type
        if wtype in seen_types:
            d = day_plans[idx].day_of_week
            ext_denom = max(phase_weeks, week_num + 4)
            if "threshold" in wtype:
                day_plans[idx] = vo2max_intervals(
                    ladder, week_num - 1, ext_denom, is_beginner, d, phase_name,
                )
            elif "vo2max" in wtype or "interval" in wtype:
                day_plans[idx] = threshold_cruise(
                    ladder, week_num - 1, ext_denom, is_beginner, d, phase_name,
                )
            else:
                day_plans[idx] = steady_run(
                    ladder, (8.0, 13.0), is_beginner, d, phase_name,
                )
        else:
            seen_types.add(wtype)

    return day_plans


def _long_run_is_workout(
    phase_name: str,
    week_in_phase: int,
    is_cutback: bool,
    phase_weeks: int = 1,
) -> bool:
    """Determine if the long run for this week is a workout (Type B/C).

    Cutback weeks and taper always get Type A (easy) long runs.
    General phase: easy in front half, moderate/progression in back half.
    Supportive/specific: most non-cutback weeks are quality long runs.
    """
    if is_cutback or phase_name == "taper":
        return False
    if phase_name == "general":
        phase_progress = week_in_phase / max(1, phase_weeks - 1)
        return phase_progress >= 0.4
    if phase_name in ("supportive", "specific"):
        return True
    return False


def _is_bonus_week(week_num: int, total_weeks: int) -> bool:
    """Detect if this week should be a bonus/supercompensation week.

    Auto-inserted every 4-6 blocks (24-36 weeks). For a single block
    (6 weeks), never bonus. For multi-block generation, bonus in the
    last week before the final cutback of the last block.
    """
    # Bonus only on the 5th week of a block (peak week)
    if (week_num % 6) != 5:
        return False
    # Only trigger for blocks >= 4 (week 29+)
    block_number = (week_num - 1) // 6 + 1
    return block_number >= 4 and block_number % 5 == 0


def _build_phase_structure(
    mode: str,
    goal_event: Optional[str],
    weeks: int,
    experience: ExperienceLevel,
):
    """Route to the correct periodizer."""
    if mode == "race":
        return build_race_phases(goal_event or "marathon", weeks, experience)

    if mode in ("build_onramp", "build_volume", "build_intensity"):
        return build_build_phases(mode, weeks, experience)

    if mode == "maintain":
        return build_maintain_phases(weeks)

    return build_race_phases(goal_event or "marathon", weeks, experience)
