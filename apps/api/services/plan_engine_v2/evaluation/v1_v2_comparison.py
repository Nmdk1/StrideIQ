"""
V1 vs V2 Plan Engine — Side-by-Side Comparison Report.

Runs both engines against the same athlete profiles and distances,
then produces a structured comparison for founder review.

V1 = constraint_aware_planner (DB-dependent, monkeypatched here)
V2 = plan_engine_v2 (pure engine, no DB)

V1 only supports 5k/10k/half_marathon/marathon.
V2 supports those plus ultra distances — ultras are V2-only in the report.

Usage:
  cd apps/api
  python -m services.plan_engine_v2.evaluation.v1_v2_comparison
"""
from __future__ import annotations

import os
import sys
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
os.environ.setdefault("SETTINGS_MODULE", "core.settings")

from services.fitness_bank import ConstraintType, ExperienceLevel, FitnessBank
from services.plan_engine_v2.evaluation.real_athletes import (
    REAL_ATHLETES, build_fitness_bank, build_fingerprint, build_load_context,
)
from services.plan_engine_v2.engine import generate_plan_v2
from services.plan_engine_v2.units import KM_TO_MI

V1_DISTANCES = ["5k", "10k", "half_marathon", "marathon"]

V2_TO_V1_DIST = {
    "5K": "5k", "10K": "10k",
    "half_marathon": "half_marathon", "marathon": "marathon",
}

TIMELINES = {
    "5K": 10, "10K": 10, "half_marathon": 12, "marathon": 16,
}


def _build_v1_bank(profile: dict) -> FitnessBank:
    """Build a FitnessBank for V1 from the same profile dict used by V2.

    V1 requires ConstraintType enum and peak_confidence (string or enum).
    build_fitness_bank from real_athletes.py sets constraint_type as a string,
    so we coerce it to the enum V1 expects.
    """
    bank = build_fitness_bank(profile)
    if isinstance(bank.constraint_type, str):
        ct_map = {"none": ConstraintType.NONE, "volume": ConstraintType.NONE,
                  "injury": ConstraintType.INJURY}
        bank.constraint_type = ct_map.get(bank.constraint_type, ConstraintType.NONE)
    if not hasattr(bank, "peak_confidence") or bank.peak_confidence is None:
        bank.peak_confidence = "high"
    return bank


@dataclass
class PlanSummary:
    engine: str
    athlete: str
    distance: str
    weeks: int
    status: str  # "OK", "REFUSED", "ERROR"
    error_msg: str = ""
    phases: List[str] = field(default_factory=list)
    lr_staircase: List[int] = field(default_factory=list)
    quality_types: set = field(default_factory=set)
    week_summaries: List[str] = field(default_factory=list)
    total_quality_sessions: int = 0
    long_run_types: List[str] = field(default_factory=list)
    has_taper: bool = False
    taper_weeks: int = 0
    peak_lr_mi: float = 0.0
    w1_quality_count: int = 0
    fueling_present: bool = False


def _run_v2(profile: dict, distance: str, weeks: int) -> PlanSummary:
    """Run V2 engine and extract summary."""
    bank = build_fitness_bank(profile)
    fp = build_fingerprint(profile)
    lc = build_load_context(profile)

    try:
        plan = generate_plan_v2(
            bank, fp, lc,
            mode="race", goal_event=distance, weeks_available=weeks,
        )
    except ValueError as e:
        return PlanSummary("V2", profile["name"], distance, weeks, "REFUSED", str(e))
    except Exception as e:
        return PlanSummary("V2", profile["name"], distance, weeks, "ERROR", str(e))

    s = PlanSummary("V2", profile["name"], distance, weeks, "OK")
    s.phases = [f"{p['name']}({p['weeks']})" for p in plan.phase_structure]
    s.has_taper = any(p["name"] == "taper" for p in plan.phase_structure)
    s.taper_weeks = sum(p["weeks"] for p in plan.phase_structure if p["name"] == "taper")

    _easy_types = {"easy", "rest", "long_easy", "easy_strides", "regenerative"}

    for wk in plan.weeks:
        lr_mi = 0.0
        lr_type = ""
        q_count = 0
        types_this_week = []
        for day in wk.days:
            types_this_week.append(day.workout_type)
            if "long" in day.workout_type and day.distance_range_km:
                mid = (day.distance_range_km[0] + day.distance_range_km[1]) / 2
                lr_mi = round(mid * KM_TO_MI)
                lr_type = day.workout_type
            if day.workout_type not in _easy_types and day.workout_type != "rest":
                q_count += 1
                s.quality_types.add(day.workout_type)
            if day.fueling:
                s.fueling_present = True

        s.lr_staircase.append(int(lr_mi))
        s.long_run_types.append(lr_type)
        s.total_quality_sessions += q_count
        if wk.week_number == 1:
            s.w1_quality_count = q_count
        cut = " [CUT]" if wk.is_cutback else ""
        s.week_summaries.append(
            f"W{wk.week_number:>2} {wk.phase:<12} LR={lr_mi:>2.0f}mi Q={q_count}{cut}"
        )

    s.peak_lr_mi = max(s.lr_staircase) if s.lr_staircase else 0
    return s


def _run_v1(profile: dict, v1_distance: str, weeks: int) -> PlanSummary:
    """Run V1 constraint-aware engine and extract summary."""
    import services.constraint_aware_planner as cap

    bank = _build_v1_bank(profile)
    original_get = cap.get_fitness_bank
    cap.get_fitness_bank = lambda _id, _db: bank

    try:
        from uuid import uuid4 as _uuid4
        from services.constraint_aware_planner import generate_constraint_aware_plan
        plan = generate_constraint_aware_plan(
            athlete_id=_uuid4(),
            race_date=date.today() + timedelta(weeks=weeks),
            race_distance=v1_distance,
            db=MagicMock(),
        )
    except ValueError as e:
        return PlanSummary("V1", profile["name"], v1_distance, weeks, "REFUSED", str(e))
    except Exception as e:
        tb = traceback.format_exc()
        return PlanSummary("V1", profile["name"], v1_distance, weeks, "ERROR",
                           f"{type(e).__name__}: {e}\n{tb}")
    finally:
        cap.get_fitness_bank = original_get

    s = PlanSummary("V1", profile["name"], v1_distance, weeks, "OK")

    _v1_quality = {
        "cruise_intervals", "threshold_continuous", "tempo", "intervals",
        "speed", "vo2max", "long_mp", "long_hmp", "long_progressive",
        "mp_medium", "race_pace", "fartlek", "hills",
    }

    themes_seen = []
    for wk in plan.weeks:
        theme = wk.theme.value if hasattr(wk.theme, "value") else str(wk.theme)
        if theme not in themes_seen:
            themes_seen.append(theme)

        lr_mi = 0
        lr_type = ""
        q_count = 0
        for d in wk.days:
            if "long" in d.workout_type:
                lr_mi = round(d.target_miles)
                lr_type = d.workout_type
            if d.workout_type in _v1_quality:
                q_count += 1
                s.quality_types.add(d.workout_type)

        s.lr_staircase.append(lr_mi)
        s.long_run_types.append(lr_type)
        s.total_quality_sessions += q_count
        if wk.week_number == 1:
            s.w1_quality_count = q_count

        cut = " [CUT]" if getattr(wk, "is_cutback", False) else ""
        s.week_summaries.append(
            f"W{wk.week_number:>2} {theme:<16} LR={lr_mi:>2.0f}mi Q={q_count}{cut}"
        )

    s.phases = themes_seen
    s.has_taper = any("taper" in t.lower() for t in themes_seen)
    s.taper_weeks = sum(1 for wk in plan.weeks
                        if "taper" in (wk.theme.value if hasattr(wk.theme, "value")
                                       else str(wk.theme)).lower())
    s.peak_lr_mi = max(s.lr_staircase) if s.lr_staircase else 0
    return s


def _comparison_block(v1: PlanSummary, v2: PlanSummary) -> str:
    """Side-by-side comparison of one athlete x one distance."""
    lines = []
    lines.append(f"  {v1.athlete} — {v2.distance} — {v2.weeks}wk")
    lines.append(f"  {'─' * 68}")

    if v1.status != "OK" or v2.status != "OK":
        lines.append(f"  V1: {v1.status}  {v1.error_msg[:70]}")
        lines.append(f"  V2: {v2.status}  {v2.error_msg[:70]}")
        return "\n".join(lines)

    # Structure comparison
    lines.append(f"  {'':>20}  {'V1':<30}  {'V2':<30}")
    lines.append(f"  {'Phases':>20}  {', '.join(v1.phases):<30}  {', '.join(v2.phases):<30}")
    lines.append(f"  {'Peak LR':>20}  {v1.peak_lr_mi:.0f}mi{'':<26}  {v2.peak_lr_mi:.0f}mi")
    lines.append(f"  {'Taper':>20}  {v1.taper_weeks}wk{'':<27}  {v2.taper_weeks}wk")
    lines.append(f"  {'Total quality':>20}  {v1.total_quality_sessions:<30}  {v2.total_quality_sessions}")
    lines.append(f"  {'W1 quality':>20}  {v1.w1_quality_count:<30}  {v2.w1_quality_count}")
    lines.append(f"  {'Quality types':>20}  {len(v1.quality_types)} unique{'':<23}  {len(v2.quality_types)} unique")
    lines.append(f"  {'LR types':>20}  {len(set(v1.long_run_types))} unique{'':<23}  {len(set(v2.long_run_types))} unique")

    # Quality type detail
    v1_only = v1.quality_types - v2.quality_types
    v2_only = v2.quality_types - v1.quality_types
    if v1_only:
        lines.append(f"  {'V1 only':>20}  {', '.join(sorted(v1_only))}")
    if v2_only:
        lines.append(f"  {'V2 only':>20}  {', '.join(sorted(v2_only))}")

    # LR staircase comparison
    v1_lr = " → ".join(str(x) for x in v1.lr_staircase)
    v2_lr = " → ".join(str(x) for x in v2.lr_staircase)
    lines.append(f"  {'V1 LR staircase':>20}  {v1_lr}")
    lines.append(f"  {'V2 LR staircase':>20}  {v2_lr}")

    # LR type variation
    v1_lr_types = [t for t in v1.long_run_types if t]
    v2_lr_types = [t for t in v2.long_run_types if t]
    if v1_lr_types:
        lines.append(f"  {'V1 LR types':>20}  {', '.join(v1_lr_types)}")
    if v2_lr_types:
        lines.append(f"  {'V2 LR types':>20}  {', '.join(v2_lr_types)}")

    # Week-by-week
    lines.append(f"  {'':>20}  {'V1':<35}  {'V2':<35}")
    max_wk = max(len(v1.week_summaries), len(v2.week_summaries))
    for i in range(max_wk):
        w1 = v1.week_summaries[i] if i < len(v1.week_summaries) else ""
        w2 = v2.week_summaries[i] if i < len(v2.week_summaries) else ""
        lines.append(f"  {'':>20}  {w1:<35}  {w2:<35}")

    return "\n".join(lines)


def _scoring_section(all_v1: List[PlanSummary], all_v2: List[PlanSummary]) -> str:
    """Aggregate scoring comparison."""
    lines = []
    lines.append("")
    lines.append("=" * 80)
    lines.append("  AGGREGATE SCORING")
    lines.append("=" * 80)

    ok_v1 = [s for s in all_v1 if s.status == "OK"]
    ok_v2 = [s for s in all_v2 if s.status == "OK"]
    refused_v1 = [s for s in all_v1 if s.status == "REFUSED"]
    refused_v2 = [s for s in all_v2 if s.status == "REFUSED"]
    err_v1 = [s for s in all_v1 if s.status == "ERROR"]
    err_v2 = [s for s in all_v2 if s.status == "ERROR"]

    lines.append(f"")
    lines.append(f"  {'':>25}  {'V1':>10}  {'V2':>10}")
    lines.append(f"  {'Generated OK':>25}  {len(ok_v1):>10}  {len(ok_v2):>10}")
    lines.append(f"  {'Refused':>25}  {len(refused_v1):>10}  {len(refused_v2):>10}")
    lines.append(f"  {'Errors':>25}  {len(err_v1):>10}  {len(err_v2):>10}")

    # Quality metrics (only for plans that both generated)
    if ok_v1 and ok_v2:
        avg_q_v1 = sum(s.total_quality_sessions for s in ok_v1) / len(ok_v1)
        avg_q_v2 = sum(s.total_quality_sessions for s in ok_v2) / len(ok_v2)
        lines.append(f"  {'Avg quality sessions':>25}  {avg_q_v1:>10.1f}  {avg_q_v2:>10.1f}")

        avg_lr_peak_v1 = sum(s.peak_lr_mi for s in ok_v1) / len(ok_v1)
        avg_lr_peak_v2 = sum(s.peak_lr_mi for s in ok_v2) / len(ok_v2)
        lines.append(f"  {'Avg peak LR (mi)':>25}  {avg_lr_peak_v1:>10.1f}  {avg_lr_peak_v2:>10.1f}")

        all_qtypes_v1 = set()
        all_qtypes_v2 = set()
        for s in ok_v1:
            all_qtypes_v1 |= s.quality_types
        for s in ok_v2:
            all_qtypes_v2 |= s.quality_types
        lines.append(f"  {'Unique quality types':>25}  {len(all_qtypes_v1):>10}  {len(all_qtypes_v2):>10}")

        avg_lr_types_v1 = sum(len(set(s.long_run_types)) for s in ok_v1) / len(ok_v1)
        avg_lr_types_v2 = sum(len(set(s.long_run_types)) for s in ok_v2) / len(ok_v2)
        lines.append(f"  {'Avg LR type variety':>25}  {avg_lr_types_v1:>10.1f}  {avg_lr_types_v2:>10.1f}")

        w1_quality_v1 = sum(1 for s in ok_v1 if s.w1_quality_count > 0)
        w1_quality_v2 = sum(1 for s in ok_v2 if s.w1_quality_count > 0)
        lines.append(f"  {'Plans w/ W1 quality':>25}  {w1_quality_v1:>10}  {w1_quality_v2:>10}")

        taper_v1 = sum(1 for s in ok_v1 if s.has_taper)
        taper_v2 = sum(1 for s in ok_v2 if s.has_taper)
        lines.append(f"  {'Plans w/ taper':>25}  {taper_v1:>10}  {taper_v2:>10}")

    lines.append("")
    lines.append("  V1 quality type vocabulary:")
    all_q1 = set()
    for s in ok_v1:
        all_q1 |= s.quality_types
    lines.append(f"    {', '.join(sorted(all_q1))}")
    lines.append("  V2 quality type vocabulary:")
    all_q2 = set()
    for s in ok_v2:
        all_q2 |= s.quality_types
    lines.append(f"    {', '.join(sorted(all_q2))}")

    return "\n".join(lines)


def main():
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("  V1 vs V2 PLAN ENGINE — SIDE-BY-SIDE COMPARISON")
    report_lines.append(f"  Generated: {date.today().isoformat()}")
    report_lines.append(f"  V1 = constraint_aware_planner  |  V2 = plan_engine_v2")
    report_lines.append(f"  Athletes: {len(REAL_ATHLETES)}  |  Distances: {len(V1_DISTANCES)}")
    report_lines.append("=" * 80)
    report_lines.append("")

    all_v1: List[PlanSummary] = []
    all_v2: List[PlanSummary] = []

    for athlete in REAL_ATHLETES:
        name = athlete["name"]
        report_lines.append(f"{'━' * 80}")
        report_lines.append(f"  {name} — {athlete['tag']}")
        report_lines.append(f"  {athlete['current_weekly_miles']:.0f}mpw | "
                            f"RPI {athlete['rpi']} | "
                            f"{athlete['experience_level'].value} | "
                            f"Limiter: {athlete.get('limiter', 'none')}")
        report_lines.append(f"{'━' * 80}")
        report_lines.append("")

        for v2_dist, v1_dist in V2_TO_V1_DIST.items():
            weeks = TIMELINES[v2_dist]

            print(f"  {name} × {v2_dist} ({weeks}wk)...", end=" ", flush=True)

            v1_result = _run_v1(athlete, v1_dist, weeks)
            v2_result = _run_v2(athlete, v2_dist, weeks)

            all_v1.append(v1_result)
            all_v2.append(v2_result)

            report_lines.append(_comparison_block(v1_result, v2_result))
            report_lines.append("")

            print(f"V1={v1_result.status} V2={v2_result.status}")

    report_lines.append(_scoring_section(all_v1, all_v2))

    report = "\n".join(report_lines)

    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    path = os.path.join(report_dir, f"v1_v2_comparison_{date.today().isoformat()}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport saved: {path}")
    print(report[-2000:])


if __name__ == "__main__":
    main()
