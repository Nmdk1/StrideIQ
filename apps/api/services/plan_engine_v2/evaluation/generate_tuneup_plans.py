"""Generate full plans with tune-up races for founder review."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
os.environ.setdefault("SETTINGS_MODULE", "core.settings")

from datetime import date, timedelta
from pathlib import Path

from services.plan_engine_v2.engine import generate_plan_v2
from services.plan_engine_v2.models import TuneUpRace
from services.plan_engine_v2.evaluation.real_athletes import (
    REAL_ATHLETES,
    build_fitness_bank,
    build_fingerprint,
    build_load_context,
)

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MI = 0.621371
KM_PER_MI = 1.60934

OUTPUT_DIR = Path(__file__).parent / "plans"
OUTPUT_DIR.mkdir(exist_ok=True)


def _day_distance_mi(d) -> float:
    """Best-effort distance estimate for a day, in miles."""
    if d.workout_type == "rest":
        return 0.0
    if d.target_distance_km:
        return d.target_distance_km * MI
    if d.segments:
        total_km = 0.0
        for s in d.segments:
            if s.distance_km:
                total_km += s.distance_km
            elif s.duration_min and s.pace_sec_per_km and s.pace_sec_per_km > 0:
                total_km += (s.duration_min * 60.0) / s.pace_sec_per_km
        if total_km > 0:
            return total_km * MI
    if d.distance_range_km:
        return ((d.distance_range_km[0] + d.distance_range_km[1]) / 2.0) * MI
    return 0.0


def _fmt_plan(plan, tune_ups, label):
    lines = []
    lines.append("=" * 76)
    lines.append(f"  {label}")
    lines.append(f"  {plan.total_weeks} weeks | {plan.goal_event} | "
                 f"athlete_type={plan.athlete_type}")
    phases = " → ".join(
        f"{p['name']}({p['weeks']}w)" for p in plan.phase_structure
    )
    lines.append(f"  Phases: {phases}")
    for tu in tune_ups:
        lines.append(f"  Tune-up: {tu.name} ({tu.distance}, {tu.purpose}) "
                      f"on {tu.race_date} ({DOW[tu.race_date.weekday()]})")
    lines.append("=" * 76)

    for wk in plan.weeks:
        cut = " [CUTBACK]" if wk.is_cutback else ""
        week_total_mi = 0.0
        day_lines = []
        for d in wk.days:
            day_mi = _day_distance_mi(d)
            week_total_mi += day_mi

            dist = ""
            if d.distance_range_km:
                lo = d.distance_range_km[0] * MI
                hi = d.distance_range_km[1] * MI
                dist = f" ({lo:.0f}mi)" if abs(hi - lo) < 2.5 else f" ({lo:.0f}-{hi:.0f}mi)"
            elif d.target_distance_km:
                dist = f" ({d.target_distance_km * MI:.1f}mi)"

            marker = ""
            if d.workout_type in ("tune_up_race", "pre_race", "recovery"):
                marker = "  <<<"

            seg_info = ""
            if d.segments:
                parts = []
                for s in d.segments:
                    if s.distance_km:
                        parts.append(f"{s.type} {s.distance_km:.1f}km")
                    elif s.duration_min:
                        parts.append(f"{s.type} {s.duration_min:.0f}min")
                    elif s.reps:
                        parts.append(f"{s.reps}x {s.type}")
                if parts:
                    seg_info = f"  [{', '.join(parts)}]"

            fuel = ""
            if d.fueling:
                fuel = f"  [fuel: {d.fueling.during_run_carbs_g_per_hr}g/hr]"

            day_lines.append(
                f"    {DOW[d.day_of_week]}: {d.workout_type}{dist}"
                f"{seg_info}{fuel}{marker}"
            )
            if d.description and d.workout_type in (
                "tune_up_race", "pre_race", "recovery"
            ):
                day_lines.append(f"         -> {d.description}")

        lines.append(f"\n  W{wk.week_number:>2} | {wk.phase:<12}{cut}"
                      f"  ~{week_total_mi:.0f}mi")
        lines.extend(day_lines)

    lines.append("")
    return "\n".join(lines)


def _make_plan(athlete_dict, event, weeks, tune_ups, label):
    bank = build_fitness_bank(athlete_dict)
    fp = build_fingerprint(athlete_dict)
    lc = build_load_context(athlete_dict)
    start = date.today()

    try:
        plan = generate_plan_v2(
            bank, fp, lc,
            mode="race", goal_event=event,
            weeks_available=weeks,
            tune_up_races=tune_ups,
            plan_start_date=start,
            desired_peak_weekly_miles=athlete_dict.get("desired_peak_weekly_miles"),
        )
        return _fmt_plan(plan, tune_ups, label)
    except ValueError as e:
        return f"{'=' * 76}\n  {label}\n  REFUSED: {e}\n{'=' * 76}\n"


def main():
    start = date.today()
    pm = start - timedelta(days=start.weekday())  # plan Monday

    all_output = []
    all_output.append("TUNE-UP RACE INTEGRATION — FULL PLAN OUTPUT")
    all_output.append(f"Generated: {start}")
    all_output.append(f"Plan Monday: {pm}")
    all_output.append("")

    # ── Michael: Marathon 16wk + Half tune-up (W10 Saturday) ─────────
    michael = REAL_ATHLETES[0]
    tu = [TuneUpRace(
        race_date=pm + timedelta(weeks=9, days=5),
        distance="half_marathon", name="Brooklyn Half",
        purpose="threshold",
    )]
    all_output.append(_make_plan(
        michael, "marathon", 16, tu,
        "MICHAEL — Marathon 16wk + Brooklyn Half (W10 Sat, threshold)",
    ))

    # ── Michael: Marathon 16wk + 10K (W8 Sun) + Half (W12 Sat) ──────
    tu2 = [
        TuneUpRace(
            race_date=pm + timedelta(weeks=7, days=6),
            distance="10K", name="Turkey Trot 10K",
            purpose="confidence",
        ),
        TuneUpRace(
            race_date=pm + timedelta(weeks=11, days=5),
            distance="half_marathon", name="Philly Half",
            purpose="threshold",
        ),
    ]
    all_output.append(_make_plan(
        michael, "marathon", 16, tu2,
        "MICHAEL — Marathon 16wk + 10K (W8 Sun) + Philly Half (W12 Sat)",
    ))

    # ── Michael: Half Marathon 12wk + 10K sharpening (W8 Saturday) ───
    tu3 = [TuneUpRace(
        race_date=pm + timedelta(weeks=7, days=5),
        distance="10K", name="Central Park 10K",
        purpose="sharpening",
    )]
    all_output.append(_make_plan(
        michael, "half_marathon", 12, tu3,
        "MICHAEL — Half Marathon 12wk + Central Park 10K (W8 Sat, sharpening)",
    ))

    # ── Brian: Marathon 16wk + Half tune-up (W10 Saturday) ───────────
    brian = REAL_ATHLETES[1]
    tu_brian = [TuneUpRace(
        race_date=pm + timedelta(weeks=9, days=5),
        distance="half_marathon", name="Queens Half",
        purpose="confidence",
    )]
    all_output.append(_make_plan(
        brian, "marathon", 16, tu_brian,
        "BRIAN — Marathon 16wk + Queens Half (W10 Sat, confidence)",
    ))

    # ── Sarah: 10K 10wk + 5K sharpening (W7 Saturday) ───────────────
    sarah = REAL_ATHLETES[2]
    tu_sarah = [TuneUpRace(
        race_date=pm + timedelta(weeks=6, days=5),
        distance="5K", name="Prospect Park 5K",
        purpose="sharpening",
    )]
    all_output.append(_make_plan(
        sarah, "10K", 10, tu_sarah,
        "SARAH — 10K 10wk + Prospect Park 5K (W7 Sat, sharpening)",
    ))

    # ── Mark: Half Marathon 12wk + 10K threshold (W8 Sunday) ─────────
    mark = REAL_ATHLETES[3]
    tu_mark = [TuneUpRace(
        race_date=pm + timedelta(weeks=7, days=6),
        distance="10K", name="NYRR 10K",
        purpose="threshold",
    )]
    all_output.append(_make_plan(
        mark, "half_marathon", 12, tu_mark,
        "MARK — Half Marathon 12wk + NYRR 10K (W8 Sun, threshold)",
    ))

    # ── Lisa: Marathon 16wk + 5K (W6 Sat) + Half (W11 Sat) ──────────
    lisa = REAL_ATHLETES[4]
    tu_lisa = [
        TuneUpRace(
            race_date=pm + timedelta(weeks=5, days=5),
            distance="5K", name="Parkrun",
            purpose="confidence",
        ),
        TuneUpRace(
            race_date=pm + timedelta(weeks=10, days=5),
            distance="half_marathon", name="City Half",
            purpose="threshold",
        ),
    ]
    all_output.append(_make_plan(
        lisa, "marathon", 16, tu_lisa,
        "LISA — Marathon 16wk + Parkrun 5K (W6 Sat) + City Half (W11 Sat)",
    ))

    # ── Michael: NO tune-ups (control) ───────────────────────────────
    all_output.append(_make_plan(
        michael, "marathon", 16, [],
        "MICHAEL — Marathon 16wk (NO TUNE-UPS — control baseline)",
    ))

    # Write output
    out_path = OUTPUT_DIR / "TUNEUP_PLANS.txt"
    content = "\n".join(all_output)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Output written to: {out_path}")
    print(f"Total lines: {content.count(chr(10)) + 1}")

    # Self-validation
    _validate_output(content)


def _validate_output(content: str):
    """Post-generation checks — catch issues before founder sees output."""
    import re
    errors = []

    # No emojis
    emoji_pattern = re.compile(
        "[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FA6F]"
    )
    for i, line in enumerate(content.split("\n"), 1):
        if emoji_pattern.search(line):
            errors.append(f"Line {i}: emoji found — '{line.strip()}'")

    # Check per-day range spreads
    range_pattern = re.compile(r"\((\d+)-(\d+)mi\)")
    for i, line in enumerate(content.split("\n"), 1):
        m = range_pattern.search(line)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            spread = hi - lo
            if spread > 3:
                errors.append(
                    f"Line {i}: day range spread {spread}mi too wide — '{line.strip()}'"
                )

    # Check weekly totals (extracted from "~NNmi" in week headers)
    weekly_pattern = re.compile(r"W\s*(\d+)\s*\|.*~(\d+)mi")
    for i, line in enumerate(content.split("\n"), 1):
        m = weekly_pattern.search(line)
        if m:
            wk_num, total_mi = int(m.group(1)), int(m.group(2))
            if total_mi < 15:
                errors.append(
                    f"Line {i}: W{wk_num} total {total_mi}mi suspiciously low"
                )
            if total_mi > 100:
                errors.append(
                    f"Line {i}: W{wk_num} total {total_mi}mi suspiciously high"
                )

    if errors:
        print(f"\n  VALIDATION FAILED — {len(errors)} issue(s):")
        for e in errors:
            print(f"    {e}")
        raise SystemExit(1)
    else:
        print("\n  VALIDATION PASSED — no emojis, tight ranges, sane totals")


if __name__ == "__main__":
    main()
