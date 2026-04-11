"""
Evaluation harness — run V2 engine on synthetic profiles.

Usage:
    cd apps/api
    python -m services.plan_engine_v2.evaluation.harness
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .synthetic_athletes import (
    PROFILES,
    build_mock_fitness_bank,
    build_mock_fingerprint,
    build_mock_load_context,
)
from ..engine import generate_plan_v2
from ..pace_ladder import format_pace_sec_km

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run_single(profile: dict) -> dict:
    """Run V2 on a single profile.  Returns summary dict."""
    pid = profile["id"]

    if profile["rpi"] is None:
        return {
            "profile": pid,
            "status": "skipped",
            "reason": "No RPI (null-RPI profiles handled in Phase 4)",
        }

    try:
        bank = build_mock_fitness_bank(profile)
        fp = build_mock_fingerprint(profile)
        lc = build_mock_load_context(profile)

        plan = generate_plan_v2(
            fitness_bank=bank,
            fingerprint=fp,
            load_ctx=lc,
            mode=profile["mode"],
            goal_event=profile.get("goal_event"),
            weeks_available=profile.get("weeks_to_race"),
        )

        plan_dict = plan.to_dict()

        # Summarize paces
        ladder = plan.pace_ladder
        pace_summary = {}
        for pct, sec_km in sorted(ladder.items()):
            pace_summary[f"{pct}%"] = format_pace_sec_km(sec_km, "mi")

        # Full plan validation
        total_segment_count = 0
        effort_issues = []
        week_summaries = []
        phase_weeks = {}

        for week in plan_dict["weeks"]:
            wk_num = week["week_number"]
            phase = week["phase"]
            phase_weeks[phase] = phase_weeks.get(phase, 0) + 1

            day_count = len(week["days"])
            quality_days = []
            for day in week["days"]:
                segs = day.get("segments", [])
                if segs:
                    total_segment_count += len(segs)
                    for seg in segs:
                        desc = seg.get("description", "")
                        if "%" in desc and "MP" in desc:
                            effort_issues.append(f"W{wk_num} Day {day['day_of_week']}: '{desc}'")
                wt = day.get("workout_type", "")
                if wt not in ("easy", "rest", "easy_strides"):
                    quality_days.append(wt)

            week_summaries.append({
                "week": wk_num,
                "phase": phase,
                "days": day_count,
                "cutback": week.get("is_cutback", False),
                "quality": quality_days,
            })

        return {
            "profile": pid,
            "status": "success",
            "mode": profile["mode"],
            "goal_event": profile.get("goal_event"),
            "rpi": profile["rpi"],
            "anchor_type": plan_dict["anchor_type"],
            "athlete_type": plan_dict["athlete_type"],
            "total_weeks": plan_dict["total_weeks"],
            "actual_weeks": len(plan_dict["weeks"]),
            "pace_summary": pace_summary,
            "total_segments": total_segment_count,
            "effort_language_issues": effort_issues,
            "phases": plan_dict["phase_structure"],
            "phase_weeks": phase_weeks,
            "week_summaries": week_summaries,
        }

    except Exception as e:
        import traceback
        return {
            "profile": pid,
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


def run_all():
    """Run V2 on all profiles.  Print summary and save report."""
    results = []
    for profile in PROFILES:
        result = run_single(profile)
        results.append(result)

    # Print summary
    print("\n" + "=" * 72)
    print("PLAN ENGINE V2 — EVALUATION REPORT")
    print("=" * 72)

    successes = [r for r in results if r["status"] == "success"]
    skipped = [r for r in results if r["status"] == "skipped"]
    errors = [r for r in results if r["status"] == "error"]

    print(f"\nResults: {len(successes)} success, {len(skipped)} skipped, {len(errors)} errors\n")

    for r in results:
        status_icon = {"success": "PASS", "skipped": "SKIP", "error": "FAIL"}[r["status"]]
        print(f"  [{status_icon}] {r['profile']}")

        if r["status"] == "success":
            print(f"         mode={r['mode']} event={r.get('goal_event')} "
                  f"anchor={r['anchor_type']} type={r['athlete_type']}")
            print(f"         weeks={r['actual_weeks']}/{r['total_weeks']} "
                  f"segments={r['total_segments']}")
            print(f"         phase_weeks={r['phase_weeks']}")

            # Show key paces
            ps = r.get("pace_summary", {})
            key_paces = ["80%", "100%", "105%", "115%"]
            pace_line = "  ".join(f"{k}={ps.get(k, '?')}" for k in key_paces if k in ps)
            if pace_line:
                print(f"         paces: {pace_line}")

            if r["effort_language_issues"]:
                print(f"         EFFORT ISSUES: {r['effort_language_issues']}")

        elif r["status"] == "error":
            print(f"         ERROR: {r['error']}")
            if r.get("traceback"):
                # Print last 3 lines of traceback
                tb_lines = r["traceback"].strip().split("\n")
                for line in tb_lines[-3:]:
                    print(f"         {line}")

        print()

    # Save report
    report_dir = Path(__file__).parent / "reports"
    report_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"{timestamp}.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Report saved: {report_path}")

    return results


if __name__ == "__main__":
    run_all()
