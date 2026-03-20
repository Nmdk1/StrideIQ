from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class QualityGateResult:
    passed: bool
    reasons: List[str]


def evaluate_constraint_aware_plan(plan: Any) -> QualityGateResult:
    reasons: List[str] = []
    weeks = getattr(plan, "weeks", []) or []
    vc: Dict[str, Any] = getattr(plan, "volume_contract", {}) or {}
    band_max = float(vc.get("band_max", 0) or 0)

    if not weeks:
        reasons.append("No generated weeks.")
        return QualityGateResult(False, reasons)

    if band_max > 0:
        for week in weeks:
            if week.total_miles > band_max * 1.15:
                reasons.append(
                    f"Week {week.week_number} exceeds trusted band ceiling: "
                    f"{week.total_miles:.1f} > {band_max * 1.15:.1f}."
                )
                break

    if str(getattr(plan, "race_distance", "")).lower() == "10k":
        for week in weeks:
            week_total = max(week.total_miles, 1.0)
            for day in week.days:
                if day.workout_type == "long":
                    if day.target_miles > 16.0 or day.target_miles / week_total > 0.30:
                        reasons.append(
                            f"10K long-run dominance breach in week {week.week_number}: "
                            f"{day.target_miles:.1f}mi."
                        )
                        break
                if day.workout_type in ("threshold", "threshold_short") and day.target_miles > 8.0:
                    reasons.append(
                        f"10K threshold size too large in week {week.week_number}: "
                        f"{day.target_miles:.1f}mi."
                    )
                    break
            if reasons:
                break

    return QualityGateResult(len(reasons) == 0, reasons)


def evaluate_starter_plan_quality(plan: Any) -> QualityGateResult:
    """
    Guardrail contract for true cold-start plans.
    """
    reasons: List[str] = []
    workouts = getattr(plan, "workouts", []) or []
    if not workouts:
        reasons.append("No workouts generated.")
        return QualityGateResult(False, reasons)

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

    return QualityGateResult(len(reasons) == 0, reasons)
