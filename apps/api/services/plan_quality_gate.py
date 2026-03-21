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
    suggested_safe_bounds = {
        "weekly_miles": {"min": round(max(8.0, band_min * 0.85), 1), "max": round(max(12.0, band_max * 1.05), 1)},
        "long_run_miles": {"min": 8.0, "max": 18.0},
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

    if str(getattr(plan, "race_distance", "")).lower() == "10k":
        floor = _compute_personal_long_run_floor(fitness_bank, race_distance="10k")
        if floor > 0:
            suggested_safe_bounds["long_run_miles"]["min"] = round(floor, 1)
        for week in weeks:
            week_total = max(week.total_miles, 1.0)
            for day in week.days:
                if day.workout_type == "long":
                    if day.target_miles > 18.0 or day.target_miles / week_total > 0.33:
                        reasons.append(
                            f"10K long-run dominance breach in week {week.week_number}: "
                            f"{day.target_miles:.1f}mi."
                        )
                        invariant_conflicts.append("tenk_long_run_dominance")
                        break
                    # High-data athlete invariant: first two build weeks keep personal floor.
                    if week.week_number <= 2 and floor > 0 and day.target_miles + 1e-6 < floor:
                        reasons.append(
                            f"10K personal long-run floor breach in week {week.week_number}: "
                            f"{day.target_miles:.1f} < {floor:.1f}."
                        )
                        invariant_conflicts.append("personal_long_run_floor_breach")
                        break
                if day.workout_type in ("threshold", "threshold_short") and day.target_miles > 8.0:
                    reasons.append(
                        f"10K threshold size too large in week {week.week_number}: "
                        f"{day.target_miles:.1f}mi."
                    )
                    invariant_conflicts.append("tenk_threshold_oversize")
                    break
            if reasons:
                break

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
    """
    Locked formula:
    personal_floor = max(recent_8w_p75_long_run, recent_16w_p50_long_run)
    for high-data athletes, with injury adjustment.
    """
    vc = fitness_bank.get("volume_contract", {}) if isinstance(fitness_bank, dict) else {}
    peak = fitness_bank.get("peak", {}) if isinstance(fitness_bank, dict) else {}
    constraint = fitness_bank.get("constraint", {}) if isinstance(fitness_bank, dict) else {}

    run_count_16w = int(vc.get("recent_16w_run_count", 0) or 0)
    peak_long = float(peak.get("long_run", 0) or 0)
    if run_count_16w < 24 or peak_long < 13:
        return 0.0

    p75_8w = float(vc.get("recent_8w_p75_long_run_miles", 0) or 0)
    p50_16w = float(vc.get("recent_16w_p50_long_run_miles", 0) or 0)
    floor = max(p75_8w, p50_16w)
    if floor <= 0:
        return 0.0

    if str(constraint.get("type", "")).lower() == "injury":
        floor *= 0.90
        if race_distance == "marathon":
            floor = max(12.0, floor)
        else:
            floor = max(10.0, floor)
    return round(floor, 1)
