"""
V2 Plan Engine — Comprehensive Test Matrix Runner.

Generates plans for every real athlete x every distance x time variants,
collects quality gate results, and produces a founder-readable report.

Usage:
  cd apps/api
  python -m services.plan_engine_v2.evaluation.test_matrix_runner
"""
from __future__ import annotations

import os
import sys
import traceback
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, ".")

from services.plan_engine_v2.evaluation.real_athletes import (
    ALL_DISTANCES,
    REAL_ATHLETES,
    TestCase,
    build_fitness_bank,
    build_fingerprint,
    build_load_context,
    build_test_matrix,
)
from services.plan_engine_v2.engine import generate_plan_v2
from services.plan_engine_v2.models import V2PlanPreview
from services.plan_engine_v2.pace_ladder import format_pace_sec_km
from services.plan_engine_v2.units import KM_TO_MI
from services.plan_engine_v2.volume import _RACE_FLOOR_MI


@dataclass
class TestResult:
    case: TestCase
    plan: Optional[V2PlanPreview]
    gate_failures: List[str]
    refusal: Optional[str]
    error: Optional[str]
    lr_staircase: List[int]


def _find_athlete(name: str) -> dict:
    for a in REAL_ATHLETES:
        if a["name"] == name:
            return a
    raise ValueError(f"Unknown athlete: {name}")


def _quality_gates(plan: V2PlanPreview, profile: dict) -> List[str]:
    """Quality gate checks for the test matrix."""
    failures = []

    # Gate 1: No % MP leak in descriptions
    for wk in plan.weeks:
        for day in wk.days:
            if "% MP" in (day.description or ""):
                failures.append(f"W{wk.week_number} {day.workout_type}: '%% MP' in description")

    # Gate 2: Correct week count
    if len(plan.weeks) != plan.total_weeks:
        failures.append(f"Week count: {len(plan.weeks)} vs {plan.total_weeks}")

    # Gate 3: No empty weeks
    for wk in plan.weeks:
        if not wk.days:
            failures.append(f"W{wk.week_number}: empty")

    # Gate 4: Long run reaches race floor (race mode)
    if plan.mode == "race" and plan.goal_event in _RACE_FLOOR_MI:
        required_mi = _RACE_FLOOR_MI[plan.goal_event]
        max_lr_mi = 0.0
        for wk in plan.weeks:
            for day in wk.days:
                if day.distance_range_km and "long" in day.workout_type:
                    mid = (day.distance_range_km[0] + day.distance_range_km[1]) / 2
                    max_lr_mi = max(max_lr_mi, mid * KM_TO_MI)
        if max_lr_mi < required_mi - 1:
            failures.append(
                f"Peak LR {max_lr_mi:.0f}mi < {required_mi}mi floor"
            )

    # Gate 5: Taper exists (marathon+)
    if plan.mode == "race" and plan.goal_event in ("marathon", "half_marathon", "50K", "50_mile", "100K", "100_mile"):
        phases = [p["name"] for p in plan.phase_structure]
        if "taper" not in phases:
            failures.append("No taper phase")

    # Gate 6: A/B structure check - never 3 quality days
    for wk in plan.weeks:
        quality_types = {
            "threshold_cruise", "threshold_alt_km", "speed_support",
            "vo2max_intervals", "micro_intervals", "marathon_pace_alt_km",
            "progression", "uphill_tm_threshold", "supercompensation_long",
        }
        long_workout_types = {"long_fast_stepwise", "long_fatigue_resistance"}
        q_count = sum(1 for d in wk.days if d.workout_type in quality_types)
        lr_workout = sum(1 for d in wk.days if d.workout_type in long_workout_types)
        total_hard = q_count + lr_workout
        if total_hard > 2:
            failures.append(f"W{wk.week_number}: {total_hard} hard sessions (max 2)")

    # Gate 7: Extension progression visible (threshold cruise should vary)
    if plan.total_weeks >= 8:
        tc_titles = []
        for wk in plan.weeks:
            for day in wk.days:
                if day.workout_type == "threshold_cruise":
                    tc_titles.append(day.title)
        if len(tc_titles) >= 3:
            unique_titles = set(tc_titles)
            if len(unique_titles) < 2:
                failures.append("Threshold cruise never progresses (same title throughout)")

    return failures


def run_single(case: TestCase) -> TestResult:
    """Run a single test case."""
    profile = _find_athlete(case.athlete_name)
    bank = build_fitness_bank(profile)
    fp = build_fingerprint(profile)
    lc = build_load_context(profile)

    is_build_mode = case.distance in ("build_volume", "build_intensity", "maintain")

    try:
        plan = generate_plan_v2(
            bank, fp, lc,
            mode="race" if not is_build_mode else case.distance,
            goal_event=case.distance if not is_build_mode else None,
            weeks_available=case.weeks,
            desired_peak_weekly_miles=profile.get("desired_peak_weekly_miles"),
        )
        gates = _quality_gates(plan, profile)

        lr_dists = []
        for wk in plan.weeks:
            for day in wk.days:
                if "long" in day.workout_type and day.distance_range_km:
                    mid = (day.distance_range_km[0] + day.distance_range_km[1]) / 2
                    lr_dists.append(round(mid * KM_TO_MI))

        return TestResult(case, plan, gates, None, None, lr_dists)

    except ValueError as e:
        return TestResult(case, None, [], str(e), None, [])
    except Exception as e:
        return TestResult(case, None, [], None, f"{type(e).__name__}: {e}", [])


def generate_report(results: List[TestResult]) -> str:
    """Generate the founder-readable test matrix report."""
    lines = []

    lines.append("=" * 80)
    lines.append("  PLAN ENGINE V2 -- COMPREHENSIVE TEST MATRIX REPORT")
    lines.append(f"  Generated: {date.today().isoformat()}")
    lines.append(f"  Athletes: {len(REAL_ATHLETES)}  |  Distances: {len(ALL_DISTANCES) + 3}")
    lines.append(f"  Total test cases: {len(results)}")
    lines.append("=" * 80)

    # Counts
    ok = [r for r in results if r.plan and not r.gate_failures]
    gate_fail = [r for r in results if r.plan and r.gate_failures]
    refused = [r for r in results if r.refusal]
    errors = [r for r in results if r.error]

    lines.append("")
    lines.append(f"  PASS: {len(ok)}  |  GATE FAIL: {len(gate_fail)}  |  "
                 f"REFUSED: {len(refused)}  |  ERROR: {len(errors)}")
    lines.append("")

    # ── Section 1: Per-Athlete Summary ───────────────────────────────
    lines.append("-" * 80)
    lines.append("  SECTION 1: PER-ATHLETE SUMMARY")
    lines.append("-" * 80)

    for athlete in REAL_ATHLETES:
        name = athlete["name"]
        tag = athlete.get("tag", "")
        lines.append("")
        lines.append(f"  {name} ({tag}) -- {athlete['current_weekly_miles']:.0f}mpw, "
                     f"RPI {athlete['rpi']:.0f}, {athlete['experience_level'].value}")

        athlete_results = [r for r in results if r.case.athlete_name == name]

        for r in athlete_results:
            if r.case.distance in ("build_volume", "build_intensity", "maintain"):
                continue

            status = "OK" if r.plan and not r.gate_failures else (
                "GATE" if r.gate_failures else (
                    "REFUSED" if r.refusal else "ERROR"
                )
            )

            if r.plan:
                lr_summary = ""
                if r.lr_staircase:
                    lr_summary = f"LR: {r.lr_staircase[0]}mi->{max(r.lr_staircase)}mi"
                phases = "+".join(f"{p['name'][0].upper()}{p['weeks']}" for p in r.plan.phase_structure)
                lines.append(
                    f"    [{status:>7}]  {r.case.distance:<15} {r.case.weeks:>2}wk "
                    f"({r.case.label:<10}) {phases:<20} {lr_summary}"
                )
                if r.gate_failures:
                    for gf in r.gate_failures[:3]:
                        lines.append(f"             FAIL: {gf}")
            elif r.refusal:
                short = r.refusal[:70] + "..." if len(r.refusal) > 70 else r.refusal
                lines.append(
                    f"    [REFUSED]  {r.case.distance:<15} {r.case.weeks:>2}wk "
                    f"({r.case.label:<10}) {short}"
                )
            elif r.error:
                lines.append(
                    f"    [  ERROR]  {r.case.distance:<15} {r.case.weeks:>2}wk "
                    f"({r.case.label:<10}) {r.error[:60]}"
                )

        # Build/maintain modes
        build_results = [r for r in athlete_results
                         if r.case.distance in ("build_volume", "build_intensity", "maintain")]
        if build_results:
            for r in build_results:
                status = "OK" if r.plan and not r.gate_failures else "FAIL"
                lines.append(
                    f"    [{status:>7}]  {r.case.distance:<15} {r.case.weeks:>2}wk"
                )

    # ── Section 2: Distance-Level Summary ────────────────────────────
    lines.append("")
    lines.append("-" * 80)
    lines.append("  SECTION 2: DISTANCE SUMMARY")
    lines.append("-" * 80)

    for dist in ALL_DISTANCES:
        dist_results = [r for r in results if r.case.distance == dist]
        if not dist_results:
            continue

        ok_count = sum(1 for r in dist_results if r.plan and not r.gate_failures)
        refused_count = sum(1 for r in dist_results if r.refusal)
        fail_count = sum(1 for r in dist_results if r.gate_failures)
        error_count = sum(1 for r in dist_results if r.error)

        lines.append(
            f"  {dist:<15} OK:{ok_count:<3} REFUSED:{refused_count:<3} "
            f"GATE_FAIL:{fail_count:<3} ERROR:{error_count}"
        )

        if refused_count > 0:
            refused_names = [r.case.athlete_name for r in dist_results if r.refusal]
            lines.append(f"    Refused: {', '.join(refused_names)}")

    # ── Section 3: Detailed Founder Review (Michael's Plans) ─────────
    lines.append("")
    lines.append("-" * 80)
    lines.append("  SECTION 3: FOUNDER REVIEW -- MICHAEL'S PLANS")
    lines.append("-" * 80)

    michael_results = [r for r in results
                       if r.case.athlete_name == "Michael"
                       and r.case.label == "standard"
                       and r.plan]

    for r in michael_results:
        plan = r.plan
        lines.append("")
        lines.append(f"  {r.case.distance} ({r.case.weeks}wk)")
        phases = ", ".join(f"{p['name']}({p['weeks']})" for p in plan.phase_structure)
        lines.append(f"    Phases: {phases}")

        if r.lr_staircase:
            lines.append(f"    Long run: {' -> '.join(str(d) for d in r.lr_staircase)}mi")

        # Quality session types used
        q_types = set()
        for wk in plan.weeks:
            for day in wk.days:
                if day.segments and day.workout_type not in ("easy", "long_easy", "rest"):
                    q_types.add(day.workout_type)
        lines.append(f"    Quality types: {', '.join(sorted(q_types))}")

        # Week-by-week summary
        lines.append(f"    {'Wk':>4}  {'Phase':<12}  {'Cut?':<4}  Sessions")
        for wk in plan.weeks:
            day_labels = []
            for day in wk.days:
                label = day.workout_type
                if day.distance_range_km and "long" in day.workout_type:
                    mid_mi = (day.distance_range_km[0] + day.distance_range_km[1]) / 2 * KM_TO_MI
                    label += f"({mid_mi:.0f}mi)"
                elif day.segments:
                    label += f"[{len(day.segments)}seg]"
                day_labels.append(label)

            cut = "Y" if wk.is_cutback else ""
            lines.append(f"    W{wk.week_number:>2}   {wk.phase:<12}  {cut:<4}  {'  '.join(day_labels)}")

        # Gate results
        if r.gate_failures:
            lines.append(f"    GATE FAILURES: {len(r.gate_failures)}")
            for gf in r.gate_failures:
                lines.append(f"      - {gf}")
        else:
            lines.append(f"    GATES: ALL PASSED")

    # ── Section 4: Refusal Analysis ──────────────────────────────────
    lines.append("")
    lines.append("-" * 80)
    lines.append("  SECTION 4: REFUSAL ANALYSIS")
    lines.append("  (These athletes were told they can't safely do this distance.)")
    lines.append("  (Is the refusal correct? Would a coach agree?)")
    lines.append("-" * 80)

    for r in refused:
        prof = _find_athlete(r.case.athlete_name)
        lines.append(
            f"  {r.case.athlete_name} x {r.case.distance} ({r.case.weeks}wk, {r.case.label})"
        )
        lines.append(f"    Athlete: {prof['current_weekly_miles']:.0f}mpw, "
                     f"LR={prof['current_long_run_miles']:.0f}mi, "
                     f"{prof['experience_level'].value}")
        lines.append(f"    Reason: {r.refusal}")
        lines.append("")

    # ── Summary ──────────────────────────────────────────────────────
    lines.append("-" * 80)
    lines.append("  FINAL SUMMARY")
    lines.append("-" * 80)
    lines.append(f"  Total:   {len(results)}")
    lines.append(f"  PASS:    {len(ok)}")
    lines.append(f"  REFUSED: {len(refused)} (review Section 4 for correctness)")
    lines.append(f"  GATE:    {len(gate_fail)}")
    lines.append(f"  ERROR:   {len(errors)}")

    if errors:
        lines.append("")
        lines.append("  ERRORS (need fixing):")
        for r in errors:
            lines.append(f"    {r.case.id}: {r.error}")

    lines.append("")
    return "\n".join(lines)


def main():
    print("Building test matrix...")
    cases = build_test_matrix()
    print(f"Running {len(cases)} test cases...")

    results = []
    for i, case in enumerate(cases):
        result = run_single(case)
        results.append(result)
        status = "OK" if result.plan and not result.gate_failures else (
            "GATE" if result.gate_failures else (
                "REF" if result.refusal else "ERR"
            )
        )
        if (i + 1) % 20 == 0 or status in ("ERR", "GATE"):
            print(f"  [{i+1}/{len(cases)}] {case.id}: {status}")

    report = generate_report(results)
    print(report)

    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    path = os.path.join(report_dir, f"test_matrix_{date.today().isoformat()}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  Report saved: {path}")


if __name__ == "__main__":
    main()
