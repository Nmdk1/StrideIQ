# How to Construct a Training Plan

**Date:** April 10, 2026
**Status:** MANDATORY — the builder must implement this construction order
**Sources:**
- Founder's methodology (`docs/specs/N1_PLAN_ENGINE_SPEC.md`, Steps 2-4)
- Founder's personal coaching approach (`docs/BUILDER_INSTRUCTIONS_2026-04-10_TRAINING_LIFECYCLE.md`, Philosophy §5-6)
- Davis's plan construction process (`docs/references/DAVIS_FULL_SPECTRUM_10K_PLAN_CONSTRUCTION_2026-04-10.md`)
- Davis's five principles (`docs/references/DAVIS_FIVE_PRINCIPLES_MARATHON_TRAINING_2026-04-10.md`)

---

## The Problem with V2's Current Approach

V2 starts at Week 1 and builds forward, applying a mathematical curve
to each variable (long run distance, volume, quality density). This is
how a spreadsheet thinks, not how a coach thinks.

The result: a 20-week first marathon plan where the long run peaks at
15km because a sqrt curve starting from the athlete's L30 doesn't reach
far enough. The math doesn't know the athlete needs to run 20 miles
before race day. A coach does.

**A coach starts from the race and works backward.**

---

## The Construction Order

This is the order in which the generator must build a plan. Not
optional. Not a suggestion. This is how every competent coach on
the planet builds a plan.

### Step 0 — Readiness Gate

Before anything else, determine if this athlete can do this race.

**Marathon:** The athlete must be able to do a 12-mile run BEFORE
starting the plan. If not, route them to Build-Volume instead.
Long runs in a marathon plan do not begin below 14 miles. Below
14 miles is just a regular run for someone doing marathon volume.

**Half Marathon:** Must be able to reach 12mi long run within the
available weeks, or refuse and offer base building.

**Source:** N1 Engine Spec, Step 2.

### Step 1 — Pin Race Day

Place race day on the calendar. This is the fixed point. Everything
else is relative to this date.

### Step 2 — Place Taper (working backward from race day)

Taper duration by distance:
- Marathon: 3 weeks (2 weeks for experienced)
- Half Marathon: 2 weeks
- 10K: 1-2 weeks
- 5K: 1 week
- Ultra 50K: 1 week (or none for advanced)
- Ultra 50mi+: 2 weeks

Taper volume: -30% week 1, -50% week 2, race week minimal.
Long run during taper: drops to 60-70% of peak, then a shakeout.

### Step 3 — Place Specific Phase (working backward from taper)

This is where the money workouts live — the sessions that directly
prepare the athlete for the race. Place these FIRST because they
are non-negotiable. The rest of the plan exists to make the athlete
capable of doing these workouts.

**What goes here:**
- Race-pace work (marathon: MP long runs, alternating km at MP.
  10K: race-pace intervals at 100%. 5K: race-pace intervals)
- Peak long run (marathon: 18-21mi. Half: 13-16mi. 10K: 10-13mi)
- Fatigue resistance workouts (Type C long runs)
- The highest-extension workout in each quality arc
  (e.g., 3×10min threshold, 4×2K at race pace)

**The peak long run distance is determined HERE, not by a curve.**

| Race | Peak Long Run |
|------|---------------|
| 5K | 8-10 mi |
| 10K | 10-13 mi |
| Half Marathon | 13-16 mi |
| Marathon | 18-21 mi |
| 50K | 20-24 mi |
| 50mi+ | 24-30 mi |

Lower end for less experienced. Upper end for experienced.
This is non-negotiable. The plan MUST reach these distances.

**Duration:** 2-6 weeks depending on distance and plan length.
Marathon gets 3 weeks specific (peak plan) to 6 weeks (20-week plan).
10K gets 5-6 weeks specific.

**Source:** Davis 10K construction: "Start with the GOAL (the race
itself). Work BACKWARDS from race day, placing key race-specific
workouts." N1 Engine Spec: "Peak 3 → Taper → Race."

### Step 4 — Place Supportive Phase (working backward from specific)

This phase bridges general fitness to race-specific capability.
The athlete can't jump from easy mileage to 20-mile MP long runs.
They need the bridge.

**What goes here:**
- Speeds within 10% of race pace (90-110% for marathon,
  90-110% of 10K pace for 10K)
- Extension-based threshold progression (6×5min → 4×7min → 3×10min)
- Long runs building toward the specific phase's peak
- Progression runs (general-purpose bridge workout)

**Duration:** 3-6 weeks depending on plan length.

**Source:** Davis: "marathon-supportive phase uses speeds closer to
marathon pace to improve running economy and continue improving SSmax."
N1 Engine Spec: "Build 2 (MP) 3 weeks."

### Step 5 — Place General Phase (fills remaining weeks)

General phase gets whatever weeks are left after specific, supportive,
and taper are placed. This is NOT a "base phase" of pure easy mileage.
It uses the FULL SPECTRUM of speeds.

**What goes here:**
- Easy volume building (the long run starts here at L30 + 1mi)
- Strides (all three variants)
- Hills
- VO2max intervals (lifting the ceiling)
- Sub-threshold work (SSmax development)
- Cutback weeks at phase boundaries

**Duration:** Whatever weeks remain. For a 20-week marathon:
20 - 3 taper - 3 specific - 5 supportive = 9 weeks general.
For a 12-week 10K: 12 - 1 taper - 5 specific - 4 supportive = 2 weeks general.
If < 2 weeks remain for general, skip it — the athlete is already fit.

**Source:** Davis: "general phase uses the full spectrum of speeds to
lift VO2max and SSmax." N1 Engine Spec: "Base 3 → Cut."

### Step 6 — Compute Long Run Staircase (from start to placed peak)

NOW you know where the long run needs to start (general phase Week 1)
and where it needs to peak (specific phase). Build the staircase:

**Starting distance:** From load context — `l30_max_easy_long_mi + 1`.
Marathon minimum: 14 miles. If the athlete's L30 is below 13 miles,
they fail the readiness gate (Step 0) and get routed to base building.

**Peak distance:** Already placed in Step 3.

**Staircase rules:**
- Build for `cutback_frequency - 1` weeks (from fingerprint), then
  cutback for 1 week
- Cutback drops to 60-70% of the cycle's peak (round to whole miles)
- Each new cycle starts at the previous cycle's pre-cutback peak
- Increment: +1 to +2 mi per build week (based on experience)
- All distances round to whole miles
- The staircase reaches the peak during the specific phase

**If the math doesn't fit:** If the gap between start and peak is
too large for the available weeks at +2mi/week, the plan needs more
weeks or the athlete needs a base-building block first. The generator
should detect this and either extend the plan or refuse the distance.

### Step 7 — Place Quality Sessions in Each Week

Now fill each week with the appropriate quality sessions for its phase.

**From the fingerprint:**
- `limiter` determines which quality category dominates
- `primary_quality_emphasis` overrides if set
- `quality_spacing_min_hours` constrains placement
- `cutback_frequency` determines recovery week cadence

**From Davis's four components:**
Each phase must touch all four components (VO2max, SSmax, Economy,
Resilience) but with different emphasis:
- General: VO2max and SSmax primary
- Supportive: SSmax and Economy primary
- Specific: Resilience and Economy primary

**Extension within each arc:**
- Week 1 of the arc: base volume at the target pace
- Each subsequent week: same pace, longer duration
- Cutback weeks: the quality session drops to maintenance volume

**Source:** Founder's personal approach: "400s at 5:50, then 800s
same pace, then 1200s same pace, final week miles same pace."
Davis: "Running the same pace for longer... this strategy yields
much more rapid improvements than repeating the same workouts."

### Step 8 — Fill Easy Volume

LAST. After the key workouts are placed, fill remaining days with
easy runs. Easy runs are the means to the aerobic end — they exist
to support the quality work, not the other way around.

**Easy run distances:** Prescribed as ranges (Green's "plans written
in pencil"). The athlete self-selects within the range based on
how they feel.

**Weekly volume target:** Already computed from load context. The
easy runs absorb whatever volume the quality sessions and long run
don't consume.

**Source:** Davis: "Mileage is a means to an end, so it only makes
sense to think about mileage after we've gotten the key workouts
squared away."

---

## The Key Insight

The current V2 builds forward from Week 1: compute volume curve →
compute long run curve → fill workouts. This is backward.

The correct order is:
1. Race day (fixed)
2. Taper (backward from race)
3. Specific workouts including peak long run (backward from taper)
4. Supportive workouts (backward from specific)
5. General workouts (fills the rest)
6. Long run staircase (connects start to placed peak)
7. Quality sessions (per phase, per fingerprint)
8. Easy volume (fills gaps)

The peak long run distance is determined by the RACE, not by a curve
from L30. The curve connects where the athlete IS to where they NEED
TO BE. The destination is known before the path is computed.

This is how the founder builds plans on a napkin. This is how Davis
builds plans. This is how every competent coach builds plans. The
generator must do the same.

---

## For Build/Maintain Modes

Build and Maintain modes have no race, so Steps 1-3 change:

**Build-Volume:** No race day, no taper, no specific phase. The
"peak" is the BONUS WEEK supercompensation workout. Construction:
place the bonus week → fill 5 weeks of progressive build before it →
compute long run and quality arcs. The staircase still applies —
it just peaks at the bonus week instead of a race.

**Build-Intensity:** No race day. The "peak" is the hardest quality
session in the block. Construction: place the peak sessions in W3 →
build W1-W2 toward them → W4 is cutback.

**Maintain:** No progression, no peak. Rotate quality types weekly.
Flat volume. No staircase needed.

**Onramp:** Time-based only. Fixed weekly structure progressing from
run/hike to continuous running. No staircase, no quality sessions.

---

## Verification

After implementing this construction order, the `first_marathon`
profile should produce:

- Peak long run: 18-21 miles (placed in specific phase, not computed
  from a curve)
- Starting long run: 14 miles (marathon minimum)
- Staircase with real cutbacks (60-70% drops, whole miles)
- Specific phase workouts that include MP-pace sessions at marathon
  effort
- General phase with full-spectrum speeds (not just easy mileage)
- Easy volume filling gaps AFTER quality and long runs are placed

If the plan looks like something the founder would write on a napkin,
it's right. If it looks like a graphing calculator produced it, start
over.
