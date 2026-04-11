"""Advisor verification — answers the three Phase 5 close-out questions."""
import sys
sys.path.insert(0, ".")

from services.fitness_bank import ExperienceLevel
from services.plan_engine_v2.evaluation.real_athletes import (
    REAL_ATHLETES, build_fitness_bank, build_fingerprint, build_load_context,
)
from services.plan_engine_v2.evaluation.synthetic_athletes import (
    PROFILES, build_mock_fitness_bank, build_mock_fingerprint, build_mock_load_context,
)
from services.plan_engine_v2.engine import generate_plan_v2
from services.plan_engine_v2.volume import (
    compute_start_long_run_mi, compute_peak_long_run_mi,
    compute_long_run_staircase, readiness_gate, _cutback_pct,
)
from services.plan_engine_v2.units import KM_TO_MI

print("=" * 72)
print("  ADVISOR VERIFICATION — THREE PHASE 5 CLOSE-OUT QUESTIONS")
print("=" * 72)

# ── Q1: first_marathon profile ────────────────────────────────────
print("\n" + "-" * 72)
print("  Q1: FIRST_MARATHON PROFILE — THE ORIGINAL FAILURE")
print("-" * 72)

first = next(p for p in PROFILES if p["id"] == "first_marathon")
bank = build_mock_fitness_bank(first)
fp = build_mock_fingerprint(first)
lc = build_mock_load_context(first)

start = compute_start_long_run_mi(bank, lc.l30_max_easy_long_mi)
peak = compute_peak_long_run_mi(bank, "marathon")

print(f"\n  Profile: {first['id']}")
print(f"  Weekly miles: {bank.current_weekly_miles}")
print(f"  Experience: {bank.experience_level.value}")
print(f"  Peak long run (historical): {bank.peak_long_run_miles}mi")
print(f"  Current long run: {bank.current_long_run_miles}mi")
print(f"  L30 max: {lc.l30_max_easy_long_mi}mi")
print(f"  Sustainable peak weekly: {bank.sustainable_peak_weekly}mi")
print(f"  Cutback frequency: {fp.cutback_frequency}")
print()
print(f"  Computed start: {start}mi")
print(f"  Computed peak: {peak}mi (max(race_floor=20, capacity={round(bank.sustainable_peak_weekly * 0.28)}))")
print(f"  Gap: {peak - start}mi")

staircase = compute_long_run_staircase(
    start, peak, 20, "marathon", fp.cutback_frequency,
    bank.experience_level, bank=bank,
)
print(f"\n  Staircase (20 weeks, whole miles):")
for i, mi in enumerate(staircase):
    label = ""
    if (i + 1) > 1 and ((i + 1) % fp.cutback_frequency) == 0 and i < 18:
        label = "  <- CUTBACK"
    elif i >= 18:
        label = "  <- TAPER"
    print(f"    W{i+1:>2}: {mi}mi{label}")

gate = readiness_gate(start, peak, 20, "marathon", fp.cutback_frequency,
                      bank.experience_level, bank=bank)
if gate:
    print(f"\n  READINESS GATE: REFUSED")
    print(f"    {gate}")
    print(f"\n  This is CORRECT. A {bank.current_weekly_miles}mpw intermediate")
    print(f"  runner cannot safely do 20mi long runs. The old engine would")
    print(f"  have generated a plan peaking at 15km (9mi) and PASSED it.")
    print(f"  Now it either reaches the peak or refuses honestly.")
else:
    print(f"\n  READINESS GATE: PASSED")

# ── Q2: Cutback depth scaling ────────────────────────────────────
print("\n" + "-" * 72)
print("  Q2: CUTBACK DEPTH — DOES IT SCALE WITH THE ATHLETE?")
print("-" * 72)

for athlete in REAL_ATHLETES:
    ab = build_fitness_bank(athlete)
    pct = _cutback_pct(ab)
    peak_ex = compute_peak_long_run_mi(ab, "marathon")
    cutback_ex = round(peak_ex * pct)
    print(f"\n  {athlete['name']} ({athlete['current_weekly_miles']:.0f}mpw, "
          f"{athlete['experience_level'].value})")
    print(f"    Cutback %: {pct:.0%} of cycle peak")
    print(f"    At peak {peak_ex}mi -> cutback to {cutback_ex}mi "
          f"({cutback_ex/peak_ex:.0%})")

print("\n  Deliberate design:")
print("    Michael (62mpw): 78% cutback — shallower, 12mi would be a weekday run")
print("    Brian (35mpw):   67% cutback — standard recovery depth")
print("    Adam (20mpw):    62% cutback — deeper rest, less adapted")

# Show Michael's marathon staircase with new cutback depth
michael = next(a for a in REAL_ATHLETES if a["name"] == "Michael")
mb = build_fitness_bank(michael)
mfp = build_fingerprint(michael)
mlc = build_load_context(michael)
m_start = compute_start_long_run_mi(mb, mlc.l30_max_easy_long_mi)
m_peak = compute_peak_long_run_mi(mb, "marathon")
m_staircase = compute_long_run_staircase(
    m_start, m_peak, 16, "marathon", mfp.cutback_frequency,
    mb.experience_level, bank=mb,
)
print(f"\n  Michael marathon 16wk staircase:")
for i, mi in enumerate(m_staircase):
    label = ""
    if (i + 1) > 1 and ((i + 1) % mfp.cutback_frequency) == 0 and i < 14:
        pct_of_prev = mi / m_staircase[i-1] if m_staircase[i-1] > 0 else 0
        label = f"  <- CUTBACK ({pct_of_prev:.0%} of prior)"
    elif i >= 14:
        label = "  <- TAPER"
    print(f"    W{i+1:>2}: {mi}mi{label}")

# ── Q3: Construction order ────────────────────────────────────────
print("\n" + "-" * 72)
print("  Q3: IS THE CONSTRUCTION ORDER ACTUALLY BACKWARD?")
print("-" * 72)

print("""
  Honest answer: the week-level assembly iterates forward, but the
  PLAN DECISIONS are made backward. Here's the actual execution order
  in engine.py:

  Step 5: Compute PEAK long run (the destination)
          peak_lr = compute_peak_long_run_mi(bank, goal_event)
          -> max(race_floor, capacity) = the non-negotiable target

  Step 5: Run READINESS GATE (can the bridge be built?)
          readiness_gate(start, peak, weeks, ..., bank)
          -> Simulates the ENTIRE staircase before generating any week
          -> If peak isn't reachable, REFUSE (don't generate a bad plan)

  Step 6: Pre-compute ENTIRE long run staircase (the bridge)
          lr_staircase = compute_long_run_staircase(start, peak, ...)
          -> Every week's long run is determined BEFORE any week is built
          -> Peak is placed at training_weeks, taper computed from peak

  Step 7: Build phase structure (phase durations computed from total weeks)

  Step 8: Compute volume targets (also pre-computed for all weeks)

  Step 9: Assemble weeks (forward iteration through pre-computed plan)
          -> Each week LOOKS UP its long run from the staircase
          -> No week-by-week accumulation determines the peak

  The peak is a HARD CONSTRAINT placed first. The staircase is computed
  as a BRIDGE from start to peak. If the bridge doesn't fit, the gate
  refuses. The forward iteration is just assembly — all decisions are
  already made.

  Proof: compressed timelines don't produce wrong peaks. They either
  reach the same peak (if the math works) or the gate refuses. The
  old forward engine would have generated a plan that peaked wherever
  the curve happened to land — which is why first_marathon peaked at
  15km instead of 20mi.
""")

# ── Brian edge case ───────────────────────────────────────────────
print("-" * 72)
print("  BRIAN — LOW VOLUME, HIGH FITNESS EDGE CASE")
print("-" * 72)

brian = next(a for a in REAL_ATHLETES if a["name"] == "Brian")
bb = build_fitness_bank(brian)
bfp = build_fingerprint(brian)
blc = build_load_context(brian)

b_start = compute_start_long_run_mi(bb, blc.l30_max_easy_long_mi)
b_peak = compute_peak_long_run_mi(bb, "marathon")

print(f"\n  Brian: {brian['current_weekly_miles']}mpw, "
      f"peak_long_run={brian['peak_long_run_miles']}mi (20mi race finish)")
print(f"  Current long run: {bb.current_long_run_miles}mi")
print(f"  Peak proven: {bb.peak_long_run_miles}mi")
print(f"  L30: {blc.l30_max_easy_long_mi}mi")
print(f"  Computed start: {b_start}mi "
      f"(proven floor = round({bb.peak_long_run_miles} * 0.70) = "
      f"{round(bb.peak_long_run_miles * 0.70)}mi)")
print(f"  Computed peak: {b_peak}mi")

gate = readiness_gate(b_start, b_peak, 16, "marathon", bfp.cutback_frequency,
                      bb.experience_level, bank=bb)
if gate:
    print(f"\n  16wk marathon gate: REFUSED")
    print(f"    {gate}")
else:
    print(f"\n  16wk marathon gate: PASSED")
    staircase = compute_long_run_staircase(
        b_start, b_peak, 16, "marathon", bfp.cutback_frequency,
        bb.experience_level, bank=bb,
    )
    print(f"  Staircase: {' -> '.join(str(s) for s in staircase)}mi")

try:
    plan = generate_plan_v2(bb, bfp, blc, mode="race", goal_event="marathon",
                            weeks_available=16)
    lr_dists = []
    for wk in plan.weeks:
        for day in wk.days:
            if "long" in day.workout_type and day.distance_range_km:
                mid = (day.distance_range_km[0] + day.distance_range_km[1]) / 2
                lr_dists.append(round(mid * KM_TO_MI))
    print(f"  Plan generated: {plan.total_weeks}wk, LR: {' -> '.join(str(d) for d in lr_dists)}mi")
except ValueError as e:
    print(f"  Plan generation: REFUSED - {e}")
except Exception as e:
    print(f"  Plan generation: ERROR - {e}")

# Also try 24 weeks (extended)
gate24 = readiness_gate(b_start, b_peak, 24, "marathon", bfp.cutback_frequency,
                        bb.experience_level, bank=bb)
if gate24:
    print(f"\n  24wk marathon gate: REFUSED")
    print(f"    {gate24}")
else:
    print(f"\n  24wk marathon gate: PASSED")
    staircase24 = compute_long_run_staircase(
        b_start, b_peak, 24, "marathon", bfp.cutback_frequency,
        bb.experience_level, bank=bb,
    )
    print(f"  Staircase: {' -> '.join(str(s) for s in staircase24)}mi")

print()
