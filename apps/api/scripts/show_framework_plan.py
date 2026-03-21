#!/usr/bin/env python3
"""
Print what a framework v2 plan actually contains — dates, titles, distances,
pace line, registry variant id (when resolved). No DB required.

Usage (from apps/api):

  python scripts/show_framework_plan.py
  python scripts/show_framework_plan.py --distance half_marathon --weeks 12 --days 5 --tier mid

This is for founder inspection: abstract phase labels are useless without
seeing the concrete schedule.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

# apps/api as cwd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.plan_framework.generator import PlanGenerator

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _ascii(s: str) -> str:
    """Windows consoles often use cp1252; avoid UnicodeEncodeError on plan copy."""
    if not s:
        return ""
    for src, dst in (
        ("\u00d7", "x"),  # multiplication sign -> x
        ("\u2013", "-"),
        ("\u2014", "-"),
        ("\u2212", "-"),
    ):
        s = s.replace(src, dst)
    return s.encode("ascii", "replace").decode("ascii")


def main() -> int:
    p = argparse.ArgumentParser(description="Print framework plan contents")
    p.add_argument("--distance", default="marathon", help="e.g. marathon, half_marathon, 10k, 5k")
    p.add_argument("--weeks", type=int, default=8, dest="duration_weeks")
    p.add_argument("--days", type=int, default=5, dest="days_per_week")
    p.add_argument("--tier", default="mid", choices=("builder", "low", "mid", "high"))
    p.add_argument(
        "--start",
        type=lambda s: date.fromisoformat(s),
        default=date(2026, 5, 4),
        help="ISO start date (Monday recommended)",
    )
    p.add_argument("--max-weeks-print", type=int, default=0, help="0 = all weeks")
    args = p.parse_args()

    gen = PlanGenerator(None)
    plan = gen.generate_standard(
        distance=args.distance,
        duration_weeks=args.duration_weeks,
        tier=args.tier,
        days_per_week=args.days_per_week,
        start_date=args.start,
    )

    print("=" * 88)
    print("FRAMEWORK PLAN (what the athlete would actually see on the calendar)")
    print("=" * 88)
    print(f"  Distance:        {plan.distance}")
    print(f"  Weeks:           {plan.duration_weeks}")
    print(f"  Days / week:     {plan.days_per_week}")
    print(f"  Volume tier:     {plan.volume_tier}")
    print(f"  Start date:      {plan.start_date}")
    print(f"  End / race-ish:  {plan.end_date} / {plan.race_date}")
    print(f"  Total miles:     {plan.total_miles}")
    print(f"  Quality sessions:{plan.total_quality_sessions}")
    print()

    by_week: dict[int, list] = {}
    for w in plan.workouts:
        by_week.setdefault(w.week, []).append(w)

    weeks_sorted = sorted(by_week.keys())
    limit = args.max_weeks_print
    if limit > 0:
        weeks_sorted = [w for w in weeks_sorted if w <= limit]

    for week in weeks_sorted:
        print("-" * 88)
        print(f"Week {week}")
        print("-" * 88)
        for w in sorted(by_week[week], key=lambda x: x.day):
            d = w.date.isoformat() if w.date else "-"
            dn = DAY_NAMES[w.day] if 0 <= w.day < 7 else str(w.day)
            mi = w.distance_miles
            mi_s = f"{mi:.1f} mi" if mi is not None else "-"
            vid = w.workout_variant_id or "(none)"
            opt_b = ""
            if w.option_b:
                ob = w.option_b
                ob_vid = ob.workout_variant_id or "(none)"
                opt_b = f"      | Option B: {ob.workout_type} | {_ascii(ob.title)} | variant={ob_vid}"
            pace = _ascii((w.pace_description or "")[:72])
            desc = _ascii((w.description or "")[:100])
            title = _ascii(w.title)
            print(f"  {d}  {dn}  {w.workout_type:22}  {mi_s:>10}  variant={vid}")
            print(f"       {title}")
            if pace:
                print(f"       pace: {pace}")
            if desc and desc != title:
                print(f"       note: {desc}")
            if opt_b:
                print(opt_b)
        print()

    non_rest = [x for x in plan.workouts if x.workout_type != "rest"]
    with_vid = [x for x in non_rest if x.workout_variant_id]
    print("=" * 88)
    print(
        f"SUMMARY: {len(non_rest)} stored days (non-rest), "
        f"{len(with_vid)} with workout_variant_id, "
        f"{len(non_rest) - len(with_vid)} without id"
    )
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
