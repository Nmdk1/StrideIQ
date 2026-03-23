from dataclasses import dataclass
from typing import Any, Dict, List


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
            if week.total_miles > band_max * 1.15:
                reasons.append(
                    f"Week {week.week_number} exceeds trusted band ceiling: "
                    f"{week.total_miles:.1f} > {band_max * 1.15:.1f}."
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
        floor = max(_injury_floor_minimum(race_distance), floor)
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
        if prev > 0 and (prev - cur) / prev >= min_drop_pct:
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
    for week in weeks:
        if int(getattr(week, "week_number", 999)) > 2:
            continue
        week_total = float(getattr(week, "total_miles", 0) or 0)
        effective_floor = min(floor, long_run_max, week_total * 0.33) if week_total > 0 else min(floor, long_run_max)
        long_miles = _week_long_miles(week)
        if long_miles > 0 and long_miles + 1e-6 < effective_floor:
            reasons.append(
                f"{race_distance.upper()} personal long-run floor breach in week {week.week_number}: "
                f"{long_miles:.1f} < {effective_floor:.1f}."
            )
            invariant_conflicts.append("personal_long_run_floor_breach")
            return


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
    for week in weeks:
        week_total = max(float(getattr(week, "total_miles", 0) or 0), 1.0)
        for day in getattr(week, "days", []):
            if day.workout_type == "long":
                if day.target_miles > 18.0 or day.target_miles / week_total > 0.33:
                    reasons.append(
                        f"10K long-run dominance breach in week {week.week_number}: "
                        f"{day.target_miles:.1f}mi."
                    )
                    invariant_conflicts.append("tenk_long_run_dominance")
                    return
            if day.workout_type in ("threshold", "threshold_short") and day.target_miles > 8.0:
                reasons.append(
                    f"10K threshold size too large in week {week.week_number}: "
                    f"{day.target_miles:.1f}mi."
                )
                invariant_conflicts.append("tenk_threshold_oversize")
                return


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
    if mp_total < mp_floor:
        reasons.append(f"Marathon MP total too low: {mp_total:.1f}mi (< {mp_floor:.1f}mi).")
        invariant_conflicts.append("marathon_mp_total_too_low")
        return

    if longs:
        half = max(1, len(longs) // 2)
        early_peak = max(longs[:half]) if longs[:half] else 0.0
        late_peak = max(longs[half:]) if longs[half:] else 0.0
        if late_peak + 1e-6 < early_peak:
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
    for week in weeks:
        theme = str(getattr(getattr(week, "theme", None), "value", "")).lower()
        race_like_theme = theme in ("sharpen", "peak", "race", "taper_1", "taper_2")
        for day in getattr(week, "days", []):
            wt = (day.workout_type or "").lower()
            if wt in ("long_mp", "long_hmp"):
                distance_artifact = True
            if race_like_theme and wt in ("intervals", "repetitions"):
                race_specific_speed = True

    if not race_specific_speed:
        reasons.append("5K race-specific sharpening missing intervals/repetitions.")
        invariant_conflicts.append("fivek_speed_sharpen_missing")
        return
    if distance_artifact:
        reasons.append("5K plan contains long-distance artifacts (long_mp/long_hmp).")
        invariant_conflicts.append("fivek_distance_artifact")
