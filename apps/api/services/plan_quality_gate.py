from dataclasses import dataclass
from typing import Any, Dict, List, Optional


MILES_EPS = 0.25
RATIO_EPS = 0.01
TENK_LONG_DOMINANCE_RATIO_CEILING = 0.40


@dataclass
class QualityGateResult:
    passed: bool
    reasons: List[str]
    invariant_conflicts: List[str]
    suggested_safe_bounds: Dict[str, Dict[str, float]]


def evaluate_constraint_aware_plan(plan: Any) -> QualityGateResult:
    reasons: List[str] = []
    invariant_conflicts: List[str] = []
    weeks = getattr(plan, "weeks", []) or []
    vc: Dict[str, Any] = getattr(plan, "volume_contract", {}) or {}
    fitness_bank: Dict[str, Any] = getattr(plan, "fitness_bank", {}) or {}
    band_max = float(vc.get("band_max", 0) or 0)
    band_min = float(vc.get("band_min", 0) or 0)
    race_distance = str(getattr(plan, "race_distance", "")).lower()
    long_run_max = _suggested_long_run_max(race_distance)
    suggested_safe_bounds = {
        "weekly_miles": {"min": round(max(8.0, band_min * 0.85), 1), "max": round(max(12.0, band_max * 1.05), 1)},
        "long_run_miles": {"min": 8.0, "max": long_run_max},
    }

    if not weeks:
        reasons.append("No generated weeks.")
        invariant_conflicts.append("no_weeks_generated")
        return QualityGateResult(False, reasons, invariant_conflicts, suggested_safe_bounds)

    if band_max > 0:
        for week in weeks:
            band_ceiling = band_max * 1.15
            weekly_band_eps = _weekly_band_miles_eps(band_max)
            if _exceeds_with_tolerance(
                float(getattr(week, "total_miles", 0) or 0),
                band_ceiling,
                miles_eps=weekly_band_eps,
            ):
                reasons.append(
                    f"Week {week.week_number} exceeds trusted band ceiling: "
                    f"{float(getattr(week, 'total_miles', 0) or 0):.1f} > {band_ceiling:.1f}."
                )
                invariant_conflicts.append("weekly_volume_exceeds_trusted_band")
                break

    floor = _compute_personal_long_run_floor(fitness_bank, race_distance=race_distance)
    if floor > 0:
        suggested_safe_bounds["long_run_miles"]["min"] = round(min(floor, long_run_max), 1)
    _enforce_personal_floor_in_early_weeks(
        weeks=weeks,
        floor=floor,
        race_distance=race_distance,
        reasons=reasons,
        invariant_conflicts=invariant_conflicts,
    )

    if race_distance == "10k":
        _evaluate_10k_rules(weeks, reasons, invariant_conflicts)
    elif race_distance == "marathon":
        _evaluate_marathon_rules(weeks, len(weeks), reasons, invariant_conflicts)
    elif race_distance in ("half", "half_marathon", "10_mile"):
        _evaluate_half_rules(weeks, reasons, invariant_conflicts)
    elif race_distance == "5k":
        _evaluate_5k_rules(weeks, reasons, invariant_conflicts)

    return QualityGateResult(len(reasons) == 0, reasons, invariant_conflicts, suggested_safe_bounds)


def evaluate_starter_plan_quality(plan: Any) -> QualityGateResult:
    """
    Guardrail contract for true cold-start plans.
    """
    reasons: List[str] = []
    workouts = getattr(plan, "workouts", []) or []
    if not workouts:
        reasons.append("No workouts generated.")
        return QualityGateResult(False, reasons, ["no_workouts_generated"], {
            "weekly_miles": {"min": 15.0, "max": 25.0},
            "long_run_miles": {"min": 6.0, "max": 8.0},
        })

    week_totals: Dict[int, float] = {}
    week_longs: Dict[int, float] = {}
    for w in workouts:
        miles = float(w.distance_miles or 0)
        week_totals[w.week] = week_totals.get(w.week, 0.0) + miles
        if w.workout_type in ("long", "long_mp", "long_hmp"):
            week_longs[w.week] = max(week_longs.get(w.week, 0.0), miles)

    w1_total = week_totals.get(1, 0.0)
    w1_long = week_longs.get(1, 0.0)
    if w1_total > 25.0:
        reasons.append(f"Cold-start week1 total exceeds 25mi: {w1_total:.1f}")
    if w1_long > 8.0:
        reasons.append(f"Cold-start week1 long exceeds 8mi: {w1_long:.1f}")

    first4 = sorted([w for w in week_totals.keys() if w <= 4])
    for prev, cur in zip(first4, first4[1:]):
        prev_val = max(week_totals.get(prev, 0.0), 1.0)
        cur_val = week_totals.get(cur, 0.0)
        if cur_val > prev_val * 1.15:
            reasons.append(
                f"Cold-start ramp breach week {prev}->{cur}: {prev_val:.1f} -> {cur_val:.1f}"
            )
            break

    return QualityGateResult(len(reasons) == 0, reasons, [], {
        "weekly_miles": {"min": 15.0, "max": 25.0},
        "long_run_miles": {"min": 6.0, "max": 8.0},
    })


def _compute_personal_long_run_floor(fitness_bank: Dict[str, Any], race_distance: str) -> float:
    """Compatibility wrapper around unified long-run floor computation."""
    vc = fitness_bank.get("volume_contract", {}) if isinstance(fitness_bank, dict) else {}
    peak = fitness_bank.get("peak", {}) if isinstance(fitness_bank, dict) else {}
    current = fitness_bank.get("current", {}) if isinstance(fitness_bank, dict) else {}
    constraint = fitness_bank.get("constraint", {}) if isinstance(fitness_bank, dict) else {}

    return compute_athlete_long_run_floor(
        l30_max_easy_long_mi=float(current.get("long_run", 0) or 0),
        recent_8w_p75_long_run_miles=float(vc.get("recent_8w_p75_long_run_miles", 0) or 0),
        recent_16w_p50_long_run_miles=float(vc.get("recent_16w_p50_long_run_miles", 0) or 0),
        recent_16w_run_count=int(vc.get("recent_16w_run_count", 0) or 0),
        peak_long_run_miles=float(peak.get("long_run", 0) or 0),
        current_weekly_miles=float(current.get("weekly_miles", 0) or 0),
        constraint_type=str(constraint.get("type", "")),
        race_distance=race_distance,
    )


def compute_athlete_long_run_floor(
    *,
    l30_max_easy_long_mi: float = 0.0,
    recent_8w_p75_long_run_miles: float = 0.0,
    recent_16w_p50_long_run_miles: float = 0.0,
    recent_16w_run_count: int = 0,
    peak_long_run_miles: float = 0.0,
    current_weekly_miles: float = 0.0,
    constraint_type: str = "none",
    race_distance: str = "10k",
) -> float:
    """
    Unified long-run floor contract:
    floor = max(L30, p75_8w, p50_16w) for high-data athletes.
    """
    high_data = int(recent_16w_run_count or 0) >= 24 and float(peak_long_run_miles or 0) >= 13
    high_mileage_history = (
        str(race_distance).lower() == "10k"
        and float(current_weekly_miles or 0) >= 45
        and float(peak_long_run_miles or 0) >= 15
    )
    if not high_data and not high_mileage_history:
        return 0.0

    floor = max(
        float(l30_max_easy_long_mi or 0),
        float(recent_8w_p75_long_run_miles or 0),
        float(recent_16w_p50_long_run_miles or 0),
    )
    if high_mileage_history:
        floor = max(floor, min(15.0, float(peak_long_run_miles or 0) * 0.85))
    if floor <= 0:
        return 0.0

    if str(constraint_type or "").lower() == "injury":
        floor *= 0.90
        injury_min = _injury_floor_minimum(race_distance)
        # Volume guard: injury minimum must not exceed 32% of current weekly volume.
        # A 28mpw comeback runner cannot safely do a 12mi long run.
        if current_weekly_miles > 0:
            volume_cap = current_weekly_miles * 0.32
            injury_min = min(injury_min, volume_cap)
        floor = max(injury_min, floor)
    return round(floor, 1)


def _injury_floor_minimum(race_distance: str) -> float:
    d = str(race_distance).lower()
    if d == "marathon":
        return 12.0
    if d in ("half", "half_marathon", "10_mile", "10k"):
        return 10.0
    if d == "5k":
        return 8.0
    return 8.0


def _is_long_run(workout_type: str) -> bool:
    t = (workout_type or "").lower()
    return t in ("long", "easy_long", "long_mp", "long_hmp")


def _week_long_miles(week: Any) -> float:
    long_miles = [float(day.target_miles or 0) for day in getattr(week, "days", []) if _is_long_run(day.workout_type)]
    return max(long_miles) if long_miles else 0.0


def _has_real_cutback(weeks: List[Any], min_drop_pct: float = 0.15) -> bool:
    totals = [float(getattr(w, "total_miles", 0) or 0) for w in weeks]
    for prev, cur in zip(totals, totals[1:]):
        if prev > 0 and (prev - cur) / prev >= max(0.0, min_drop_pct - RATIO_EPS):
            return True
    return False


def _enforce_personal_floor_in_early_weeks(
    *,
    weeks: List[Any],
    floor: float,
    race_distance: str,
    reasons: List[str],
    invariant_conflicts: List[str],
) -> None:
    if floor <= 0:
        return
    long_run_max = _suggested_long_run_max(race_distance)
    floor_tolerance = _early_week_floor_tolerance(race_distance)
    prev_long_miles: Optional[float] = None
    for week in weeks:
        if int(getattr(week, "week_number", 999)) > 2:
            continue
        week_total = float(getattr(week, "total_miles", 0) or 0)
        effective_floor = min(floor, long_run_max, week_total * 0.33) if week_total > 0 else min(floor, long_run_max)
        required_floor = max(0.0, effective_floor - floor_tolerance)
        long_miles = _week_long_miles(week)
        # Cutback exemption: when the long run drops ≥ 30% week-over-week in the
        # early window, it is an intentional cutback week (PhaseBuilder assigns
        # cutback_weeks every N weeks regardless of plan position). Enforcing the
        # personal floor on cutback W2 would incorrectly flag a planned recovery
        # dip as a breach. Skip the floor check for this week only.
        is_cutback_week = (
            prev_long_miles is not None
            and prev_long_miles > 0
            and long_miles > 0
            and long_miles <= prev_long_miles * 0.72  # ≥ 28% reduction ≈ 0.70× factor
        )
        if not is_cutback_week and long_miles > 0 and long_miles + 1e-6 < required_floor:
            reasons.append(
                f"{race_distance.upper()} personal long-run floor breach in week {week.week_number}: "
                f"{long_miles:.1f} < {required_floor:.1f} (target floor {effective_floor:.1f})."
            )
            invariant_conflicts.append("personal_long_run_floor_breach")
            return
        if long_miles > 0:
            prev_long_miles = long_miles


def _early_week_floor_tolerance(race_distance: str) -> float:
    # Week-level mileage allocation is quantized; avoid hard-failing near-miss floors.
    d = str(race_distance).lower()
    if d in ("5k", "10k", "half", "half_marathon", "10_mile"):
        return 0.75
    return 0.5


def _suggested_long_run_max(race_distance: str) -> float:
    d = str(race_distance).lower()
    if d == "marathon":
        return 22.0
    if d in ("half", "half_marathon", "10_mile", "10k"):
        return 18.0
    if d == "5k":
        return 16.0
    return 18.0


def _evaluate_10k_rules(weeks: List[Any], reasons: List[str], invariant_conflicts: List[str]) -> None:
    has_marathon_pace_work = False
    for week in weeks:
        week_total = max(float(getattr(week, "total_miles", 0) or 0), 1.0)
        for day in getattr(week, "days", []):
            wt = (day.workout_type or "").lower()
            if wt == "long":
                long_miles = float(day.target_miles or 0)
                if _exceeds_with_tolerance(long_miles, 18.0, miles_eps=MILES_EPS) or _exceeds_ratio_with_tolerance(
                    long_miles / week_total, TENK_LONG_DOMINANCE_RATIO_CEILING, ratio_eps=RATIO_EPS
                ):
                    reasons.append(
                        f"10K long-run dominance breach in week {week.week_number}: "
                        f"{long_miles:.1f}mi."
                    )
                    invariant_conflicts.append("tenk_long_run_dominance")
                    return
            if wt in ("threshold", "threshold_short") and _exceeds_with_tolerance(
                float(day.target_miles or 0), 8.0, miles_eps=MILES_EPS
            ):
                reasons.append(
                    f"10K threshold size too large in week {week.week_number}: "
                    f"{float(day.target_miles or 0):.1f}mi."
                )
                invariant_conflicts.append("tenk_threshold_oversize")
                return
            # Marathon pace work is never appropriate for a 10K plan.
            if wt in ("long_mp", "mp_medium"):
                has_marathon_pace_work = True

    if has_marathon_pace_work:
        reasons.append(
            "10K plan contains marathon pace work (long_mp/mp_medium). "
            "MP work is never appropriate for 10K training."
        )
        invariant_conflicts.append("tenk_marathon_pace_artifact")


def _evaluate_marathon_rules(
    weeks: List[Any],
    total_weeks: int,
    reasons: List[str],
    invariant_conflicts: List[str],
) -> None:
    mp_sessions = 0
    mp_total = 0.0
    longs = []
    for week in weeks:
        for day in getattr(week, "days", []):
            wt = (day.workout_type or "").lower()
            if wt == "long_mp":
                mp_sessions += 1
                mp_total += float(day.target_miles or 0)
            elif wt == "mp_medium":
                mp_total += float(day.target_miles or 0)
        longs.append(_week_long_miles(week))

    required_mp_sessions = max(2, total_weeks // 6)
    if mp_sessions < required_mp_sessions:
        reasons.append(f"Marathon MP progression too sparse: {mp_sessions} sessions (< {required_mp_sessions}).")
        invariant_conflicts.append("marathon_mp_progression_missing")
        return

    mp_floor = max(12.0, total_weeks * 0.8)
    if _below_with_tolerance(mp_total, mp_floor, miles_eps=MILES_EPS):
        reasons.append(f"Marathon MP total too low: {mp_total:.1f}mi (< {mp_floor:.1f}mi).")
        invariant_conflicts.append("marathon_mp_total_too_low")
        return

    if longs:
        half = max(1, len(longs) // 2)
        early_peak = max(longs[:half]) if longs[:half] else 0.0
        late_peak = max(longs[half:]) if longs[half:] else 0.0
        if _below_with_tolerance(late_peak, early_peak, miles_eps=MILES_EPS):
            reasons.append("Marathon long-run progression stalls before race-specific block.")
            invariant_conflicts.append("marathon_long_run_progression_stall")
            return

    if not _has_real_cutback(weeks, min_drop_pct=0.15):
        reasons.append("Marathon cutback week missing (no >=15% volume drop detected).")
        invariant_conflicts.append("marathon_cutback_missing")


def _evaluate_half_rules(weeks: List[Any], reasons: List[str], invariant_conflicts: List[str]) -> None:
    has_hmp = False
    has_threshold = False
    has_marathon_artifact = False
    for week in weeks:
        for day in getattr(week, "days", []):
            wt = (day.workout_type or "").lower()
            if wt == "long_hmp":
                has_hmp = True
            if wt == "long_mp":
                name = str(getattr(day, "name", "") or "")
                if "HMP" in name.upper():
                    has_hmp = True
                else:
                    has_marathon_artifact = True
            if wt in ("threshold", "threshold_short", "threshold_intervals"):
                has_threshold = True

    if not has_hmp:
        reasons.append("Half-marathon plan missing long_hmp session(s) in race-specific block.")
        invariant_conflicts.append("half_hmp_missing")
        return
    if not has_threshold:
        reasons.append("Half-marathon plan missing threshold emphasis.")
        invariant_conflicts.append("half_threshold_missing")
        return
    if has_marathon_artifact:
        reasons.append("Half-marathon plan contains marathon artifact long_mp session.")
        invariant_conflicts.append("half_marathon_artifact")


def _evaluate_5k_rules(weeks: List[Any], reasons: List[str], invariant_conflicts: List[str]) -> None:
    race_specific_speed = False
    distance_artifact = False
    has_any_interval = False
    for week in weeks:
        theme_obj = getattr(week, "theme", None)
        # Support both WeekTheme enum (legacy) and plain string (framework phase name).
        theme = (theme_obj.value if hasattr(theme_obj, "value") else str(theme_obj or "")).lower()
        race_like_theme = theme in (
            "sharpen", "peak", "race", "taper_1", "taper_2",  # legacy WeekTheme
            "race_specific", "taper",                          # framework phase_type
        )
        for day in getattr(week, "days", []):
            wt = (day.workout_type or "").lower()
            if wt in ("long_mp", "long_hmp"):
                distance_artifact = True
            if race_like_theme and _is_5k_sharpening_workout(wt):
                race_specific_speed = True
            if wt == "intervals":
                has_any_interval = True

    if not race_specific_speed:
        reasons.append("5K race-specific sharpening missing intervals/repetitions.")
        invariant_conflicts.append("fivek_speed_sharpen_missing")
        return
    if distance_artifact:
        reasons.append("5K plan contains long-distance artifacts (long_mp/long_hmp).")
        invariant_conflicts.append("fivek_distance_artifact")
        return
    # A 5K plan must contain at least one explicit interval session somewhere.
    # Threshold-only 5K plans are a coaching error.
    if not has_any_interval:
        reasons.append("5K plan contains no interval sessions. A threshold-only 5K plan is a coaching error.")
        invariant_conflicts.append("fivek_no_intervals")


def _is_5k_sharpening_workout(workout_type: str) -> bool:
    wt = str(workout_type or "").lower()
    return wt in (
        "intervals",
        "repetitions",
        "threshold_short",
        "hill_sprints",
        "hill_strides",
        "easy_strides",
        "tune_up_race",
    )


def _exceeds_with_tolerance(value: float, ceiling: float, *, miles_eps: float) -> bool:
    return float(value) > float(ceiling) + float(miles_eps)


def _below_with_tolerance(value: float, floor: float, *, miles_eps: float) -> bool:
    return float(value) + float(miles_eps) < float(floor)


def _exceeds_ratio_with_tolerance(value: float, ceiling: float, *, ratio_eps: float) -> bool:
    return float(value) > float(ceiling) + float(ratio_eps)


def _weekly_band_miles_eps(band_max: float) -> float:
    """
    Tiered weekly-band tolerance:
    - low-band athletes get extra quantization room,
    - higher-band athletes keep strict enforcement.
    """
    b = float(band_max or 0.0)
    if b <= 15.0:
        return 1.8
    if b <= 30.0:
        return 0.5
    if b <= 45.0:
        return 0.35
    if b <= 58.0:
        return 0.5
    return MILES_EPS
