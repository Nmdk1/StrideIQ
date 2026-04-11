"""Inspect the founder profile (established_marathon) plan in full detail."""

from services.plan_engine_v2.evaluation.synthetic_athletes import (
    PROFILES, build_mock_fitness_bank, build_mock_fingerprint, build_mock_load_context,
)
from services.plan_engine_v2.engine import generate_plan_v2
from services.plan_engine_v2.pace_ladder import format_pace_sec_km

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

p = [x for x in PROFILES if x["id"] == "established_marathon"][0]
bank = build_mock_fitness_bank(p)
fp = build_mock_fingerprint(p)
lc = build_mock_load_context(p)
plan = generate_plan_v2(bank, fp, lc, mode="race", goal_event="marathon", weeks_available=16)

print("=== PACE LADDER (RPI=55, marathon anchor) ===")
for pct in sorted(plan.pace_ladder.keys()):
    mi = format_pace_sec_km(plan.pace_ladder[pct], "mi")
    print(f"  {pct:3d}% = {mi}/mi  ({plan.pace_ladder[pct]:.1f} s/km)")

print(f"\n=== PHASE STRUCTURE ===")
for ph in plan.phase_structure:
    print(f"  {ph['name']:12s}  {ph['weeks']}wk  — {ph['focus']}")

print(f"\n=== FULL 16-WEEK PLAN ===")
d = plan.to_dict()
for week in d["weeks"]:
    wk = week["week_number"]
    cutback = " (CUTBACK)" if week.get("is_cutback") else ""
    print(f"\n{'='*60}")
    print(f"WEEK {wk} — {week['phase'].upper()}{cutback}")
    print(f"{'='*60}")

    for day in week["days"]:
        dow = DAYS[day["day_of_week"]]
        print(f"\n  {dow}: {day['title']}  [{day['workout_type']}]")

        desc_lines = day["description"].split("\n")
        for line in desc_lines:
            print(f"    {line}")

        if day.get("distance_range"):
            rng = day["distance_range"]
            print(f"    Range: {rng['min']}-{rng['max']} {rng.get('unit', 'mi')}")

        if day.get("segments"):
            for i, seg in enumerate(day["segments"]):
                pace_str = seg.get("pace", "")
                dist_val = f"{seg['distance']:.1f}mi" if seg.get("distance") else ""
                dur = f"{seg['duration_min']:.0f}min" if seg.get("duration_min") else ""
                size = dist_val or dur or ""
                print(f"    Seg {i+1}: [{seg['type']}] {size} @ {pace_str}  {seg['description']}")

        if day.get("fueling"):
            f = day["fueling"]
            print(f"    Fueling: {f['carbs_g_per_hr']} g/hr")

print(f"\n=== SUMMARY ===")
print(f"Total weeks: {len(d['weeks'])}")
phases = {}
for w in d["weeks"]:
    phases[w["phase"]] = phases.get(w["phase"], 0) + 1
for ph, cnt in phases.items():
    print(f"  {ph}: {cnt} weeks")
cutbacks = sum(1 for w in d["weeks"] if w.get("is_cutback"))
print(f"Cutback weeks: {cutbacks}")
total_segs = sum(
    len(seg) for w in d["weeks"] for day in w["days"]
    for seg in [day.get("segments", [])]
)
print(f"Total segments: {total_segs}")
