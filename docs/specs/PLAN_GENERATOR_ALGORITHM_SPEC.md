# Plan Generator Algorithm Spec

**Status:** APPROVED — unified algorithm for Race, Build, and Maintain modes
**Supersedes:** The five separate KB reference notes remain as background reading. This document is the builder's single source of truth for the plan generator rewrite.
**Date:** April 10, 2026

---

## Read Order (mandatory)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. **This file** (algorithm spec — all you need to build)
3. `apps/api/services/plan_framework/n1_engine.py` (current generator — study, then rewrite)
4. `apps/api/services/workout_prescription.py` (pace calculations — keep, extend)
5. `apps/api/services/fitness_bank.py` (inputs — read-only, do not modify)
6. `apps/api/models.py` — `TrainingPlan` (~line 1504), `PlannedWorkout` (~line 1553)

**Background reading — Theory (absorb the principles, not the specifics):**
- `docs/references/ROCHE_SWAP_TRAINING_PHILOSOPHY_UNIFIED_2026-04-10.md` **(START HERE — unified synthesis: hierarchy, sliding bottleneck, speed, threshold, fatigue resistance, voice, N=1)**
- `docs/references/DAVIS_MODERN_MARATHON_APPROACH_REFERENCE_NOTE_2026-04-10.md` (five principles, ladder of support, three-phase periodization)
- `docs/references/DAVIS_FIVE_PRINCIPLES_MARATHON_TRAINING_2026-04-10.md` (four components of marathon fitness)
- `docs/references/DAVIS_MARATHON_EXCELLENCE_AND_TRAINING_LOAD_2026-04-10.md` **(five tiered plans, three-load framework: physiological + biomechanical + psychological)**
- `docs/references/SSMAX_STEADY_STATE_MAX_REFERENCE_NOTE_2026-04-10.md`
- `docs/references/COE_STYLE_TRAINING_REFERENCE_NOTE_2026-04-10.md`
- `docs/references/DAVIS_MARATHON_BUILD_SAMPLE_2026-04-10.md`
- `docs/references/ADVANCED_EXERCISE_PHYSIOLOGY_SYNTHESIS_2026-04-10.md`

**Background reading — Coaching philosophy:**
- `docs/references/GREEN_COACHING_PHILOSOPHY_EXPANDED_2026-04-10.md` **(founder's #1 influence — seven principles: pencil plans, teach don't dictate, fun is performance, unremarkable consistency, athlete knows their body, leave them wanting more, document honestly)**
- `docs/references/GREEN_COACHING_PHILOSOPHY_REFERENCE_NOTE_2026-04-10.md` (original summary: adaptability, doubles theory)

**Background reading — Plan construction & analysis:**
- `docs/references/DAVIS_FULL_SPECTRUM_10K_PLAN_CONSTRUCTION_2026-04-10.md` **(how Davis builds a plan from scratch — the planning PROCESS, not just the output. 10K percentage ladder, float recovery progression, 5% rule for mixed-speed workouts)**
- `docs/references/ROCHE_SWAP_COACHING_PHILOSOPHY_2026-04-10.md` (plan-level analysis: beginner ultra, base building, 5K/10K, champion ultra, onramp, 50K int/adv)
- `docs/references/ROCHE_SWAP_EFFORT_DICTIONARY_2026-04-10.md` **(MANDATORY — effort term mapping for all workout descriptions)**

**Background reading — Quality bars (reference plans):**
- `docs/references/ROCHE_SWAP_12WK_MARATHON_PLAN_2026-04-10.md` (advanced marathon, distance ranges)
- `docs/references/ROCHE_SWAP_PLANS_SUPPLEMENTARY_2026-04-10.md` (HM 6wk, track/vVO2 6wk, 100K-100mi 16wk)

**Background reading — Execution & fueling:**
- `docs/references/ROCHE_SWAP_WORKOUT_EXECUTION_GUIDE_2026-04-10.md` (HOW to execute every workout type: strides, hills, TM threshold/Z2, easy/mod, sustained efforts, fatigue resistance, back-to-backs, combos)
- `docs/references/ROCHE_SWAP_FUELING_REFERENCE_2026-04-10.md` (carb tiers, hydration, caffeine, in-training practice)

---

## 1. The Unified Engine

There is ONE plan generator engine. Race, Build, and Maintain modes are
configurations of the same engine, not separate codebases.

```
┌──────────────────────────────────────────────────────────────────┐
│                       Unified Engine                             │
│                                                                  │
│  Inputs:  FitnessBank + Mode Config                              │
│  Core:    Pace Ladder + Phase Assignment                         │
│           + Workout Selection + Progression                      │
│  Output:  List[WeekPlan] → PlannedWorkout                       │
│                                                                  │
│  Modes:                                                          │
│  ┌──────────┐ ┌────────────────┐ ┌──────────┐                   │
│  │   Race   │ │     Build      │ │ Maintain │                   │
│  │ M/HM:    │ │ Onramp (8wk)  │ │ 4-week   │                   │
│  │ G→S→Sp   │ │ Volume (6wk∞) │ │ blocks   │                   │
│  │ 5K/10K:  │ │ Intensity(4wk)│ │ + renew  │                   │
│  │ variety  │ └────────────────┘ └──────────┘                   │
│  │ Ultra:   │                                                    │
│  │ hybrid   │  Athlete flow: Onramp → Volume → Intensity        │
│  │ + taper  │                  ↘ Race (any distance)             │
│  └──────────┘                  ↘ Maintain                        │
└──────────────────────────────────────────────────────────────────┘
```

**Race mode:** Distance-specific periodization. Marathon/HM use
three-phase (General → Supportive → Specific). 5K/10K use two-phase
(Economy → Race-specific) with variety-based speed rotation. Ultra
uses hybrid alternating (speed ↔ threshold → convergence). Plan
length auto-selected by distance (8wk for 5K, 12-16wk for marathon).

**Build mode:** Three sub-configurations based on athlete level:
- **Build–Onramp (<30K/wk, beginners):** 8-week introduction. 4
  runs per week, hike/x-train on remaining days, sensory effort
  cues. Exits into any other mode. Based on SWAP Lower Volume Plan.
- **Build–Volume (any level, long-term development):** 6-week
  repeatable blocks, ONE quality session per week (Wednesday
  threshold), distance ranges. Auto-inserts BONUS WEEK every
  4-6 blocks. Based on SWAP Long-Term Base Building plan.
- **Build–Intensity (experienced, ≥50K/wk):** 4-week blocks, two
  quality sessions per week. Extension progression on speed +
  threshold. Each block seeds the next via `peak_workout_state`.

**Maintain mode:** Repeating 4-week blocks with flat volume and rotating
workout types. Auto-renews. No progression — hold current fitness.

**Athlete flow:** The generator auto-selects the appropriate mode
based on the athlete's current weekly volume and experience:
- <30K/wk or <6 months running → Build–Onramp
- Onramp complete → athlete chooses: Build–Volume, Race, or Maintain
- Build–Volume → Build–Intensity (when volume supports it) or Race
- Race complete → auto-transition to Build–Volume or Maintain

---

## 2. Inputs

All inputs come from `FitnessBank`. No athlete questionnaire. No form input
beyond mode selection (and race date/distance for Race mode).

### From FitnessBank (read, do not modify)

| Input | FitnessBank field | Usage |
|-------|------------------|-------|
| Current weekly volume | `current_weekly_miles` | Starting volume for the plan |
| Peak weekly volume | `peak_weekly_miles` | Volume ceiling |
| Current long run | `current_long_run_miles` | Starting long run distance |
| Peak long run | `peak_long_run_miles` | Long run ceiling |
| Best RPI | `best_rpi` | Drives the entire pace ladder |
| Experience | `experience_level` | Phase durations, workout complexity |
| Long run day | `typical_long_run_day` | Scheduling preference |
| Quality day | `typical_quality_day` | Scheduling preference |
| Rest days | `typical_rest_days` | Scheduling preference |
| Recent quality count | `recent_quality_sessions_28d` | Readiness for quality work |
| Weeks since peak | `weeks_since_peak` | How much base fitness has decayed |
| Constraint type | `constraint_type` | Injury/time/detrained guards |
| Race performances | `race_performances` | Detect endurance-oriented vs speed-oriented |

### From Mode Config

| Input | Race | Build | Maintain |
|-------|------|-------|----------|
| `race_distance` | Required | N/A | N/A |
| `race_date` | Required | N/A | N/A |
| `goal_time` | Optional | N/A | N/A |
| `block_length_weeks` | N/A | 4 (default) | 4 (default) |
| `peak_workout_state` | N/A | From previous block (or null for first) | N/A |

### Derived: Endurance-Oriented Detection

From `race_performances`, compute the ratio of half-marathon equivalent
pace to marathon equivalent pace (both via `rpi_equivalent_time`).

If HM pace is ≤ 103% of MP (instead of the typical ~105%):
- The athlete is **endurance-oriented**
- Adjust 105% MP workouts down to 103% MP
- Adjust 110% MP workouts down to 108% MP
- Can push 90-95% MP long fast runs longer/harder

If HM pace is ≥ 107% of MP:
- The athlete is **speed-oriented**
- Can push 105-110% MP workouts harder
- Shorten 90-95% MP long fast runs (endurance is the weakness)

Store this as `athlete_type: "endurance" | "balanced" | "speed"` on
AthleteState.

---

## 3. The Pace Ladder

### Extending Daniels Zones with the Percentage-Based Pace Ladder

The current engine uses `calculate_paces_from_rpi()` to produce Daniels
zones: easy, marathon, threshold, interval, repetition. **Keep this.**
The math is sound and validated.

The percentage-based ladder EXTENDS these zones by filling the gaps
between them. The Daniels zones become anchor points on the ladder;
the new rungs (90%, 95%, 103%, 108% MP) are derived from the marathon
pace anchor via simple arithmetic.

In practice: `calculate_paces_from_rpi()` stays as-is. A NEW function
`compute_pace_ladder(best_rpi)` sits alongside it, producing the full
set of rungs. Both coexist.

### TRUST CONTRACT: Daniels Zones Are Sacred

**Runners know their paces.** A runner who knows their threshold is 6:31
will immediately reject a plan that calls 6:20 or 6:40 "threshold."
Trust is destroyed in one wrong number.

**Rule: For any workout labeled with a Daniels zone name, the pace comes
from `calculate_paces_from_rpi()`. Always. No exceptions.**

| Label the athlete sees | Pace source | Override allowed? |
|----------------------|------------|-------------------|
| Easy | `paces["easy"]` from Daniels | NO |
| Marathon pace | `paces["marathon"]` from Daniels | NO |
| Threshold / tempo | `paces["threshold"]` from Daniels | NO |
| Interval | `paces["interval"]` from Daniels | NO |
| Repetition | `paces["repetition"]` from Daniels | NO |
| Long run pace | Derived: `paces["easy"]` + 9s | NO |
| Recovery | Derived: `paces["easy"]` + 30s | NO |
| Steady-state pace (90% MP) | `compute_pace_ladder()` | Yes (new zone) |
| Fast long run pace (95% MP) | `compute_pace_ladder()` | Yes (new zone) |
| Half-marathon effort (103% MP) | `compute_pace_ladder()` | Yes (new zone) |
| 10K effort (108% MP) | `compute_pace_ladder()` | Yes (new zone) |

The percentage ladder fills ONLY the gaps where no Daniels zone exists.
If "105% MP" from the ladder disagrees with the Daniels "threshold"
pace (and it will — Daniels accounts for individual variation that a
flat percentage doesn't), the Daniels number wins. The ladder's 105%
is used ONLY for internal workout selection logic, never to override
a named zone pace.

The new pace zones (90%, 95%, 103%, 108% MP) have no existing runner
expectation — the athlete has never been prescribed these paces before.
There is no trust to break. These are genuinely new territory.

**The pace ladder uses marathon pace (MP) as the anchor.** MP comes from
`rpi_equivalent_time(best_rpi, 42195)` converted to pace per km/mile.

| % MP | Daniels zone approx | Workout role |
|------|---------------------|-------------|
| ≤75% | recovery | Recovery runs |
| 80% | easy (slow end) | Very easy runs |
| 85% | easy | Standard easy runs |
| 90% | — (GAP) | Long fast runs, float recovery |
| 95% | — (GAP) | Long fast runs, advanced float |
| 100% | marathon | Marathon pace workouts |
| 103% | — | Endurance-oriented HM proxy |
| 105% | threshold | Half-marathon pace, threshold |
| 108% | — | Endurance-oriented 10K proxy |
| 110% | interval (slow end) | 10K pace, speed support |
| 115% | interval | 5K pace, VO2max work |
| ≥120% | repetition | Strides, neuromuscular |

**The critical gap in the current engine is 90-95% MP.** No workouts
exist in this range. This is where the most important marathon-specific
endurance work happens — stepwise long fast runs and float recoveries.

### Computing the Ladder

```python
def compute_pace_ladder(best_rpi: float) -> Dict[str, float]:
    """
    Returns pace (seconds per km) at each rung of the ladder.
    MP is the anchor; all other paces are derived from it.
    """
    mp_time_sec = rpi_equivalent_time(best_rpi, 42195)
    mp_pace_sec_per_km = mp_time_sec / 42.195

    ladder = {}
    for pct in [75, 80, 85, 90, 92, 94, 95, 96, 100, 103, 105, 108, 110, 115, 120]:
        # % MP refers to pace, not speed.
        # 90% MP = 10% SLOWER than MP = pace * 1.10
        # 110% MP = 10% FASTER than MP = pace * 0.90
        adjustment = (100 - pct) / 100.0
        ladder[f"{pct}pct"] = mp_pace_sec_per_km * (1 + adjustment)

    return ladder
```

Note: for non-integer percentages like 103%, the math is:
`mp_pace * (1 + (100 - 103) / 100) = mp_pace * 0.97`.

### General Phase: 5K Anchor

In the general phase (first phase of Race mode, or Block 1 of Build mode
for athletes without a recent marathon), use 5K pace as the anchor instead
of marathon pace. Reason: athletes may not know their current MP, but RPI
always gives a reliable 5K equivalent.

```python
fiveK_pace = rpi_equivalent_time(best_rpi, 5000) / 5.0  # sec/km
```

Workouts in general phase use % of 5K pace:
- 85% of 5K ≈ ~100% MP (strong continuous run)
- 90-92% of 5K ≈ 10K effort (medium repeats)
- 95-100% of 5K ≈ 5K-3K effort (short repeats)
- 75-80% of 5K ≈ easy/moderate continuous

Transition to % MP at the start of the supportive phase (Race mode) or
after Block 1 (Build mode) when the athlete has demonstrated current
fitness through completed workouts.

---

## 4. Periodization

### Race Mode: General → Supportive → Specific

Phase duration depends on total plan length, race distance, and
experience. Plan length is auto-selected by race distance unless
the athlete overrides.

**Default plan lengths by race distance:**

| Distance | Default plan length | Min | Max |
|----------|-------------------|-----|-----|
| 5K | 8 weeks | 6 | 10 |
| 10K | 8-10 weeks | 6 | 12 |
| Half marathon | 10-12 weeks | 8 | 16 |
| Marathon | 12-16 weeks | 10 | 18 |
| 50K-50mi | 12-16 weeks | 10 | 20 |

**Marathon/Half marathon phase splits (General → Supportive → Specific):**

| Plan length | Experienced (G/S/Sp) | Intermediate | Beginner |
|-------------|--------------------|--------------------|-----------------|
| 13 weeks | 5 / 4 / 4 | 6 / 4 / 3 | 7 / 3 / 3 |
| 16 weeks | 6 / 5 / 5 | 8 / 4 / 4 | 9 / 4 / 3 |
| 18 weeks | 7 / 6 / 5 | 9 / 5 / 4 | 10 / 5 / 3 |
| 12 weeks | 4 / 4 / 4 | 5 / 4 / 3 | 6 / 3 / 3 |

**5K/10K phase structure (different from marathon):**

5K/10K plans do NOT use the three-phase General→Supportive→Specific
model. They use a two-phase approach:

| Phase | Duration | Focus |
|-------|----------|-------|
| **Economy + aerobic** | Weeks 1-6 | Variety-based speed rotation (different workout structure each week), threshold, long runs with structured elements |
| **Race-specific** | Weeks 7-8 | Race simulation, nervous system prime, taper |

The key difference: marathon plans use **extension-based progression**
(same structure, growing duration). 5K/10K plans use **variety-based
progression** (different structures weekly, underlying volume growth).
Both work; the physiological targets differ:
- Marathon progression targets SSmax and resilience → needs sustained
  stimulus at similar intensities
- 5K/10K progression targets VO2max and economy → needs novel stimuli
  to provoke neuromuscular adaptation

**5K/10K Wednesday speed rotation:**

| Week | Structure | Effort |
|------|-----------|--------|
| 1 | 4×(4×1min/1min easy), 2min between sets | 5K |
| 2 | 4×(3/2/1min), 1min/3min rest | 10K |
| 3 | 3×(30/60/90/60/30s), 1min/3min rest | 5K |
| 4 | 6×2min hills + 5×45s hills | 5K/3K |
| 5 | 3×(3×90s/90s easy), 3min between sets | 5K (push) |
| 6 | 6×5min @ threshold + 4×30s fast | Threshold + speed |
| 7 | 1mi hard + 6×1/1 @ 5K + 1mi @ threshold | Race simulation |
| 8 | 4×2min @ 10K + 4×1min @ 3K → RACE | Nervous system prime |

**5K/10K Saturday long run (structured, not pure easy):**

Every Saturday includes a structured element within the long run:

| Week | Structured element |
|------|--------------------|
| 1 | Fartlek: at 20min and every 5min, 1min @ 1hr effort |
| 2 | 4×6min @ 1hr effort, 2min easy |
| 3 | Pure easy/mod (aerobic emphasis) |
| 4 | 20min moderately hard @ 1hr effort (continuous) |
| 5 | 6min hard near end (fatigue resistance) |
| 6 | Pure easy/mod Z2 (aerobic emphasis) |
| 7 | 4×5min @ 1hr effort, 90s easy |
| 8 | RACE |

**5K/10K effort-based pacing:** All workouts in 5K/10K plans use
effort descriptions paired with RPI-derived pace RANGES:
- "5K effort (~5:30-5:45/mi)" — not a fixed pace
- "10K effort (~5:50-6:05/mi)" — not a fixed pace
- "1-hour effort (~6:15-6:30/mi)" — not a fixed pace
The athlete targets effort; the pace range is a sanity check.

**Terrain guidance for 5K/10K plans:**
- Speed work (Wednesday): flat, fast terrain. Supershoes recommended.
- Threshold: trails are fine.
- Easy runs: any terrain.
- Masters/injury-prone: hill variants for speed work instead of flat.

Ref: `docs/references/ROCHE_SWAP_COACHING_PHILOSOPHY_2026-04-10.md`
→ "The 5K/10K Speed Plan" section.

**Ultra (50K-50mi) phase structure:**

Ultra plans have TWO periodization variants based on athlete level:

**Intermediate/Advanced ultra (default for most athletes):** Uses a
clean three-phase approach similar to marathon but with ultra-specific
workout types (steady runs, back-to-back weekends, downhill emphasis).

| Phase | Weeks | Focus |
|-------|-------|-------|
| **Speed + power** | 1-3 | Hill intervals, flat VO2 work, strides |
| **Threshold bridge** | 4-6 | Steady runs (SSmax), threshold tempos (20→30min), alternating-km long runs |
| **Race-specific** | 7-12 | Longer intervals (3×8min), race simulation (13.1mi), peak back-to-back, extended tempo, taper |

Key elements unique to this variant:
- **Steady runs** as standalone sessions (moderate, sub-threshold, "50K effort")
- **Alternating-km long runs** (1mi threshold / 1mi float for 12mi)
- **Back-to-back weekends** peaking at W9 (20-26mi + 14-20mi)
- **Race simulation at W8** (~4 weeks out, not 2)

**Champion ultra (experienced athletes chasing podiums):** Uses
hybrid alternating — speed and threshold weeks alternate in the
first 8 weeks, then converge into race-specific work in weeks 9-12.

| Phase | Weeks | Focus |
|-------|-------|-------|
| **Speed + threshold alternation** | 1-8 | Speed weeks (hills, track, VO2max) alternate with threshold weeks (uphill TM, sustained efforts). Both progress in parallel. |
| **Race-specific convergence** | 9-10 | Race simulation, merge speed and threshold into race-pace work |
| **Taper** | 11-12 | Reduced volume, short sharp stimuli, race |

Key elements unique to this variant:
- **Post-workout steady** segments for lactate shuttling
- **Track workouts** (600m, 800m) with specific distances
- **"Power Hour"** (1hr mod/hard within long run)
- **Structured double workouts** (threshold PM sessions)
- **Uphill TM as standalone Z2 training day**

**How the generator chooses:** Based on athlete's weekly volume and
experience. <50 mi/wk or <2 years running → intermediate variant.
≥50 mi/wk with ultra race history → champion variant. The athlete
can override.

Both variants share: downhill emphasis, fatigue resistance hills,
back-to-back weekends, hill strides throughout, distance ranges,
and 12-week duration.

**Ultra Wednesday quality — intermediate/advanced (three-phase):**

| Week | Structure | Effort | Phase |
|------|-----------|--------|-------|
| 1 | 6×2min hills + 5×45s hills | 5K | Speed |
| 2 | 15×1min/1min + 5×30s hills | 5K | Speed |
| 3 | 6×2min/1min + 8×1min/1min | 10K + 5K | Speed |
| 4 | 8-12mi easy/mod steady progression | Marathon/50K | Threshold bridge |
| 5 | Pyramid 1/2/3/4/3/2/1min + 5×1min | 10K + 5K | Speed+threshold |
| 6 | 5×5min + 5×30s hills | 10K (progress) | Big threshold |
| 7 | 3×8min + 6×1min hills | 10K + 5K | Long intervals |
| 8 | 20min mod/hard + 6×1min/30s | 1hr + 5K | Threshold/speed combo |
| 9 | 15min mod/hard + 4×3min | 1hr effort | Major threshold |
| 10 | 2×(10×1min/1min) | 10K | Final speed |
| 11 | 30min moderate + 4×30s hills | HM effort | Taper stimulus |
| 12 | 20min @ marathon effort → RACE | Marathon | Race week |

**Ultra Saturday long run — intermediate/advanced:**

| Week | Distance | Structured element |
|------|----------|--------------------|
| 1 | 8-14 mi | Easy/mod on feel |
| 2 | 10-16 mi | 20min mod/hard @ threshold |
| 3 | 10-16 mi | Fartlek: 1min @ threshold every 5min from 20min |
| 4 | 12-18 mi | 30min mod/hard @ threshold |
| 5 | 10-16 mi | Steady at 50K effort |
| 6 | 14-20 mi | 12mi alternating 1mi @ 1hr / 1mi float |
| 7 | 16-24 mi | Easy on trails (aerobic weekend) |
| 8 | 13.1 mi | RACE SIMULATION (hard on race-like trails) |
| 9 | 20-26.2 mi | Easy/mod with strong uphills @ 50K effort (peak) |
| 10 | 16-22 mi | 1hr moderate @ marathon effort, faster to finish |
| 11 | 12-16 mi | Easy/mod taper |
| 12 | 50K RACE | Race day |

**Back-to-back weekends (intermediate/advanced ultra):**

| Week | Saturday | Sunday | Purpose |
|------|----------|--------|---------|
| 2 | 10-16 mi (tempo) | 8-14 mi easy | First back-to-back |
| 7 | 16-24 mi easy | 12-16 mi easy | Aerobic weekend |
| 9 | 20-26.2 mi | 14-20 mi easy + hills | Peak musculoskeletal |
| 10 | 16-22 mi (tempo) | 10-16 mi easy + downs | Eccentric adaptation |

Ref: `docs/references/ROCHE_SWAP_COACHING_PHILOSOPHY_2026-04-10.md`
→ "The 50K Intermediate/Advanced Plan" section.

**Ultra Wednesday quality — champion (hybrid alternating):**

| Week | Type | Structure | Effort |
|------|------|-----------|--------|
| 1 | Speed (hills) | 6×2min hills + 2mi steady (50K effort) | 5K + race |
| 2 | Speed (flat) | 16×1/1 + 2mi steady | 10K→5K + race |
| 3 | Speed (pyramid) | 4-6×(120/60/30s) | 10K/5K/3K |
| 4 | **Threshold (TM)** | 6-10×5min, 2min recovery | 1hr effort |
| 5 | Speed (bridge) | 6-10×3min + 4×30s | 1hr→mile |
| 6 | Speed (track) | 6-10×600 + 4×200 | 10K→mile |
| 7 | **Threshold (TM)** | 8-12×5min, 2min recovery | 1hr effort |
| 8 | Speed (track) | 6-10×800 + 4×200 | 10K→mile |
| 9 | **Threshold (bridge)** | 4-6×5min + 2mi steady + PM double | 1hr + race |
| 10 | Speed (hills+tempo) | 5×3min hills + 15-20min moderate | 10K + HM |
| 11 | Threshold (taper) | 6-10×2min + 2mi steady | 1hr→10K + race |
| 12 | Final stimulus | 3-4×5min + 5×30s hills → RACE | Threshold + power |

**Post-workout "steady" segments:** Ultra speed sessions end with
"2 miles steady (think 50K)" — sub-threshold running under fatigue
for lactate shuttling training. The `segments` schema should support
this as a post-workout segment.

**Ultra Saturday long run — three types rotating:**

| Type | Example weeks | Structure |
|------|--------------|-----------|
| Easy/mod with vert | W1,2,5,8 | Terrain emphasis, strong downhills |
| Structured threshold | W4 (5×1mi@T), W7 ("Power Hour"), W9 (race sim) | Race-pace work within the long run |
| Fatigue resistance | W3,6,10 | Easy/mod run + 4-5×30-45s hills at END |

**Fatigue resistance hills:** 4-5×30-45s hills at the END of long
runs (not the beginning). After 14-22mi of easy running, glycogen is
partially depleted — the hills train neuromuscular power output under
fatigue, which is the defining demand of the final third of an ultra.

**Downhill emphasis:** "Strong downs" on long runs for eccentric
contraction training. Generator should prescribe hilly long runs for
ultra athletes and include terrain guidance: "Run downhills with
purpose — this builds the eccentric strength for race day."

**Uphill TM as standalone training day:** 75-105 min Z2 at 10-15%
grade. Not threshold — pure aerobic development with minimal impact.
A distinct workout type from "easy run" or "cross-training."

**Strength periodization:** Heavy (Mountain Legs + Full Strength)
in weeks 1-6, light (Mountain Legs only) in weeks 7-10, none in
taper (weeks 11-12). Generator should annotate strength on workout
days, reducing as race approaches.

**Heat training:** Passive heat (sauna/hot tub) on rest days for
blood volume adaptation. Heat suit doubles for hot-race preparation.
Weight vest hiking doubles for hiking-heavy races. Generator should
include race-condition-specific recommendations.

Ref: `docs/references/ROCHE_SWAP_COACHING_PHILOSOPHY_2026-04-10.md`
→ "The Champion Ultra Plan" section.

Taper is folded INTO the final phase (last 1-2 weeks).
Not a separate phase. The biggest workouts happen 2-3 weeks before race
day, then volume drops naturally.

**Phase labels on PlannedWorkout.phase:**
- `"general"` (replaces `"base"`)
- `"supportive"` (replaces `"build"` / `"build_1"` / `"build_2"`)
- `"specific"` (replaces `"peak"`)
- `"taper"` (last 1-2 weeks, still within the specific block conceptually)

### Build Mode: Two Sub-Configurations

**Build–Intensity (experienced, ≥50K/wk):** 4-week blocks, two quality
sessions per week. Extension-based progression on speed and threshold.

| Week | Volume | Quality intensity | Long run |
|------|--------|-------------------|----------|
| W1 | Current | Baseline extension | Current LR |
| W2 | +5-7% | Extension step 1 | +1 mi |
| W3 | +10-12% (peak) | Extension step 2 (peak) | +1 mi (peak) |
| W4 | -15% (cutback) | Regenerative or strides | -2 mi |

Phase label: `"build"` for all weeks.

**Build–Volume (any level, long-term aerobic development):** 6-week
repeatable blocks with ONE quality session per week (Wednesday). Based
on the SWAP Long-Term Base Building architecture.

Ref: `docs/references/ROCHE_SWAP_COACHING_PHILOSOPHY_2026-04-10.md`
→ "Long-Term Base Building Plan" section.

| Week | Wed quality | Long run | Character |
|------|-------------|----------|-----------|
| W1 | Easy/moderate volume | Current LR easy/mod | Rebuild from range floor |
| W2 | Threshold: N × 5min @ 1hr effort | LR easy/mod hills | Structured quality |
| W3 | Easy volume day | LR easy + hill strides | Absorb |
| W4 | Threshold: N+2 × 5min @ 1hr effort | LR easy/mod hills | Extension step |
| W5 | Easy/moderate volume | LR easy (peak) | Aerobic peak |
| W6 | Threshold: N × 10min @ 1hr effort | LR easy/mod hills (peak) | Rep duration jump |

Phase label: `"build_volume"` for all weeks.

**Distance ranges:** Every non-quality session uses a distance range, not
a fixed value. Range width is determined by athlete's current volume band:
- Low band (<30 mi/wk): narrow ranges (e.g., 3-5 mi easy)
- Mid band (30-60 mi/wk): medium ranges (e.g., 5-8 mi easy)
- High band (>60 mi/wk): wide ranges (e.g., 8-12 mi easy)

**Weekly structure (7-day pattern):**

| Day | Role |
|-----|------|
| Monday | Rest (+ heat recommendation for advanced) |
| Tuesday | Easy run + 4-5 × 20-30s hill strides |
| Wednesday | KEY SESSION (threshold or moderate run, alternating) |
| Thursday | Cross-training day (60-120 min bike/elliptical at Z2) OR easy run |
| Friday | Easy run (shortest of the week) |
| Saturday | Long run (easy or easy/mod over hills) |
| Sunday | Aerobic flex: easy run + hills, x-train, or hike |

**BONUS WEEK (auto-inserted every 4-6 blocks):**

| Day | Session |
|-----|---------|
| Wednesday | 12-20 × 1min fast (5K effort) / 1min easy (vVO2 stimulus) |
| Saturday | Long run with 30-60 min mod/hard to hard (tempo effort) |

The bonus week prevents aerobic ceiling by touching VO2max and tempo
paces that the standard weeks deliberately avoid. The generator
auto-schedules this; the athlete does not need to request it.

**Cross-training as a prescribed session:** Thursday is NOT a rest day.
It is a prescribed Z2 aerobic session on a non-impact modality with
fueling guidance for sessions >60 min. Workout description:
"60-90 min bike/elliptical at Z2 heart rate. Fuel with carbs if
>60 min." Fallback for athletes without x-train access: easy run.

**Progressive doubles unlock:**
- Blocks 1-2: X-train doubles only (bike, elliptical, swim)
- Blocks 3+: Optional easy jog doubles for athletes >50K/wk
- Never on long run days. Always optional.

### Build–Onramp (beginners, <30K/wk): 8-Week Introduction

For athletes under ~30K/wk (or <6 months of consistent running),
the generator should produce an on-ramp plan before placing the
athlete into any other mode. Based on SWAP Lower Volume Plan.

Ref: `docs/references/ROCHE_SWAP_COACHING_PHILOSOPHY_2026-04-10.md`
→ "The Lower Volume Plan: The On-Ramp" section.

| Week | Runs/wk | Approx weekly miles | Quality session | Long run |
|------|---------|-------------------|-----------------|----------|
| 1 | 4 | 12-16 | Hill strides (6×30s) | 4-6 mi easy/mod |
| 2 | 4 | 12-16 | Flat intervals (4×1min + 4×30s) | 4-6 mi moderate |
| 3 | 4 | 14-18 | Flat intervals (8×1min) | 6-8 mi easy |
| 4 | 4-5 | 18-24 | Moderate run (no intervals) | 6-8 mi moderate |
| 5 | 4-5 | 20-26 | Descending pyramid | 8-10 mi easy |
| 6 | 4-5 | 22-30 | Hill intervals (6×1min) | 8-10 mi moderate |
| 7 | 4-5 | 24-32 | Check-in mile + strides | 10-12 mi easy |
| 8 | 4-5 | 24-33 | Moderate run (peak volume) | 8-10 mi moderate |

Phase label: `"onramp"` for all weeks.

Key constraints:
- **4 runs per week**, not 5-7. Hike/x-train fills remaining days.
- **Distance-effort alternation:** Never increase both distance AND
  effort in the same week. When distance steps up, effort steps down.
- **Hike/x-train days are prescribed training**, not optional rest.
  Thursday (60-90 min) and Sunday (1-2+ hours).
- **Run/hike is part of long run prescription:** "Hike as much as
  you need to for the mileage."
- **5th run day unlocks optionally from W4.**
- **Bodyweight strength only:** Single-leg step-ups (30→50 reps) +
  Core Snack routine. No gym-based strength.
- **Sensory effort cues:** "Smooth and quick," "kid at recess."
  NOT "5K effort" or "threshold" — the beginner doesn't have
  those reference points yet.
- **Exit state = entry state for all other plans.** After 8 weeks,
  the athlete should be at 20-33 mi/wk, capable of entering the
  base building plan, 5K/10K plan, or beginner ultra plan at the
  low end of distance ranges.

After completion, auto-prompt: "You're ready! Choose your next
plan: Base Building (aerobic development), 5K/10K Speed (race
prep), or a race-specific plan."

### Maintain Mode: 4-Week Blocks

Flat volume, rotating workout types:

| Week | Volume | Quality type |
|------|--------|-------------|
| W1 | Current | Type A (threshold) |
| W2 | Current | Type B (intervals) |
| W3 | Current | Type C (fartlek / progression) |
| W4 | -10-15% | Regenerative or strides |

Phase label: `"maintain"` for all weeks.

---

## 5. Workout Categories and Structures

### The Seven Categories

Each training plan should draw from these categories. The emphasis shifts
by phase (Race mode) or rotates (Build/Maintain modes).

| Category | % MP range | Example workout | Phase emphasis |
|----------|-----------|-----------------|---------------|
| **Long easy** | 75-85% | 25-30K easy through hills | General |
| **Long fast** | 90-96% | 10-8-8-6K stepwise at 90-92-94-96% | Supportive → Specific |
| **Marathon/race pace** | 100% (+ 85% float) | 6×(3K at 100%, 1K at 85%) | Specific |
| **Threshold/HM** | 103-105% (+ 85-90% float) | 6×(1K at 105%, 1K at 90%) | Supportive → Specific |
| **Speed support** | 108-110% | 4×2K at 110%, 4min jog | Supportive |
| **VO2max/5K** | 115% | 4×(3min, 2min, 1min) at 5K paces | General |
| **Strides/neuromuscular** | ≥120% | 6-8×100m strides | All phases |
| **Fatigue resistance** | varies | Long easy run + 4-5×30-45s hills at END | Specific (ultra) |
| **Uphill TM aerobic** | Z2 | 75-105min Z2 at 10-15% grade | All (ultra/trail) |
| **Steady (race effort)** | race-specific | 2mi steady at "50K effort" post-workout | Specific (ultra) |

### Segments Schema (unified)

All structured workouts MUST populate `PlannedWorkout.segments` as a
list of dicts with this unified schema:

```json
[
  {
    "type": "warmup",
    "distance_km": 2.0,
    "pace_pct_mp": 80,
    "pace_sec_per_km": 330,
    "description": "Easy warmup"
  },
  {
    "type": "work",
    "distance_km": 3.0,
    "pace_pct_mp": 100,
    "pace_sec_per_km": 300,
    "reps": 1,
    "description": "Marathon pace"
  },
  {
    "type": "float",
    "distance_km": 1.0,
    "pace_pct_mp": 85,
    "pace_sec_per_km": 353,
    "description": "Float recovery"
  },
  {
    "type": "work",
    "distance_km": 3.0,
    "pace_pct_mp": 100,
    "pace_sec_per_km": 300,
    "reps": 1,
    "description": "Marathon pace"
  },
  {
    "type": "float",
    "distance_km": 1.0,
    "pace_pct_mp": 85,
    "pace_sec_per_km": 353,
    "description": "Float recovery"
  },
  {
    "type": "cooldown",
    "distance_km": 2.0,
    "pace_pct_mp": 80,
    "pace_sec_per_km": 330,
    "description": "Easy cooldown"
  }
]
```

**Segment types:** `warmup`, `cooldown`, `work`, `float`, `jog_rest`,
`easy`, `threshold`, `interval`, `stride`, `steady`, `hike`,
`fatigue_resistance`, `uphill_tm`.

Ultra/trail-specific additions:
- `steady`: Post-workout race-effort running ("2mi steady at 50K
  effort"). Used after speed sessions for lactate shuttling.
- `hike`: Fast hiking segment. Time/distance-based with effort
  prescription. For beginner ultra and race-specific hiking.
- `fatigue_resistance`: Short hard hills placed at the END of a long
  run. Separate from `stride` because the intent is power under
  depletion, not neuromuscular activation.
- `uphill_tm`: Uphill treadmill segment. Grade and speed prescribed.
  Used for standalone Z2 days and threshold sessions.

**Required fields:** `type`, `pace_pct_mp`, `pace_sec_per_km`.
**Optional fields:** `distance_km`, `duration_min`, `reps`,
`description`, `rest_min` (for traditional jog-rest intervals),
`grade_pct` (for `uphill_tm` and hill segments),
`fueling_target_g_per_hr` (integer, for long runs ≥90 min and race
simulations — prescribes carb intake rate for the workout).

**Fueling in segments:**
When a workout's total planned duration ≥90 min, the generator MUST
set `fueling_target_g_per_hr` on the parent workout (or on long
continuous segments). Values scale with training age:
- Early development: 60 g/hr (building gut tolerance)
- Developing: 75 g/hr (standard trained)
- Established: 75-90 g/hr (race-ready)
- Race day: athlete's practiced rate (stored in athlete profile)

The fueling target also appears in the workout `description` in plain
language: "Practice race fueling: target 75+ g/hr carbs, start at
minute 30."

Every segment includes BOTH `pace_pct_mp` (internal engine metadata —
NEVER shown to the athlete) AND `pace_sec_per_km` (the concrete number
the athlete sees, formatted as min/mi or min/km per their preference).

**The athlete NEVER sees "105% MP" or "90% MP."** They see effort
language from the SWAP Effort Dictionary. The percentage system is
how the generator DECIDES what to prescribe; the effort terms are
what the athlete READS.

Ref: `docs/references/ROCHE_SWAP_EFFORT_DICTIONARY_2026-04-10.md`
— the canonical mapping from internal % MP to athlete-facing effort
language. MANDATORY reading for the builder.

The `pace_pct_mp` field exists for two internal purposes only:
1. Weather adjustment: the system can recompute `pace_sec_per_km` for
   current conditions while preserving the workout's position on the ladder
2. Post-workout analysis: the coach model can compare actual pace to
   intended ladder position to assess execution quality

**Internal → athlete-facing effort mapping:**

| Internal % MP | Athlete-facing term | Pace display |
|--------------|--------------------|----|
| 70-85% | Easy / very easy | No pace shown |
| 80-90% | Easy/mod | No pace shown, context cue only |
| 88-95% | Moderate / steady / 50K effort | ±15 sec/mi range |
| 95-100% | Marathon effort | ±15 sec/mi range |
| 101-103% | Half marathon effort | ±10 sec/mi range |
| 103-105% | 1-hour effort / threshold | ±10 sec/mi range |
| 105-110% | 10K effort (fast) | ±10 sec/mi range |
| 110-115% | 5K effort (fast) | ±10 sec/mi range |
| 115-120% | 3K effort | ±10 sec/mi range |
| ≥120% | Fast strides (800/mile effort) | No pace shown |

**Description format:** Always lead with effort, follow with pace
RANGE. Never a fixed pace as primary prescription.
- CORRECT: "6×5min at 1-hour effort (~6:20-6:40/mi)"
- WRONG: "6×5min at 6:28/mi"
- CORRECT: "10mi easy/mod — run with intention"
- WRONG: "10mi at 8:45/mi"

**For beginners (<30K/wk):** Use sensory cues instead of named
efforts. "Smooth and quick" instead of "5K effort." "Kid at recess"
instead of "fast." Beginners don't have feel reference points yet.

### Concrete Workout Structures

#### Stepwise Long Fast Run (Long fast category)

The signature marathon endurance workout. Decreasing pace across blocks:

```json
{
  "title": "Stepwise Long Run — 32K",
  "workout_type": "long_fast",
  "segments": [
    {"type": "work", "distance_km": 10, "pace_pct_mp": 90},
    {"type": "work", "distance_km": 8, "pace_pct_mp": 92},
    {"type": "work", "distance_km": 8, "pace_pct_mp": 94},
    {"type": "work", "distance_km": 6, "pace_pct_mp": 96}
  ]
}
```

Progression across weeks (within the plan):
- Early: 10-8-7K at 90-92-94% (25K total)
- Mid: 30-32K at 90-92% (all at 90-92%)
- Peak: 10-8-8-6K at 90-92-94-96% (32K total)

For lower-volume athletes (< 80 km/wk), scale distances proportionally
but preserve the stepwise pace structure.

#### Alternating Kilometer Marathon Pace (MP category)

Continuous running with structured float recovery:

```json
{
  "title": "Alternating KM — 24K at Marathon Pace",
  "workout_type": "marathon_pace",
  "segments": [
    {"type": "warmup", "distance_km": 2, "pace_pct_mp": 80},
    {"type": "work", "distance_km": 3, "pace_pct_mp": 100},
    {"type": "float", "distance_km": 1, "pace_pct_mp": 85},
    {"type": "work", "distance_km": 3, "pace_pct_mp": 100},
    {"type": "float", "distance_km": 1, "pace_pct_mp": 85},
    {"type": "work", "distance_km": 3, "pace_pct_mp": 100},
    {"type": "float", "distance_km": 1, "pace_pct_mp": 85},
    {"type": "work", "distance_km": 3, "pace_pct_mp": 100},
    {"type": "float", "distance_km": 1, "pace_pct_mp": 85},
    {"type": "work", "distance_km": 3, "pace_pct_mp": 100},
    {"type": "float", "distance_km": 1, "pace_pct_mp": 85},
    {"type": "work", "distance_km": 3, "pace_pct_mp": 100},
    {"type": "float", "distance_km": 1, "pace_pct_mp": 85},
    {"type": "cooldown", "distance_km": 2, "pace_pct_mp": 80}
  ]
}
```

Progression: continuous MP (12K) → continuous MP (16K) → 8×(2K/1K) →
6×(3K/1K). Extension increases within the work segments.

#### Alternating Kilometer Threshold (Threshold/HM category)

```json
{
  "title": "Alt KM Threshold — 12K",
  "workout_type": "threshold_alt",
  "segments": [
    {"type": "warmup", "distance_km": 2, "pace_pct_mp": 80},
    {"type": "work", "distance_km": 1, "pace_pct_mp": 105},
    {"type": "float", "distance_km": 1, "pace_pct_mp": 90},
    {"type": "work", "distance_km": 1, "pace_pct_mp": 105},
    {"type": "float", "distance_km": 1, "pace_pct_mp": 90},
    {"type": "work", "distance_km": 1, "pace_pct_mp": 105},
    {"type": "float", "distance_km": 1, "pace_pct_mp": 90},
    {"type": "work", "distance_km": 1, "pace_pct_mp": 105},
    {"type": "float", "distance_km": 1, "pace_pct_mp": 90},
    {"type": "work", "distance_km": 1, "pace_pct_mp": 105},
    {"type": "float", "distance_km": 1, "pace_pct_mp": 90},
    {"type": "work", "distance_km": 1, "pace_pct_mp": 105},
    {"type": "float", "distance_km": 1, "pace_pct_mp": 90},
    {"type": "cooldown", "distance_km": 2, "pace_pct_mp": 80}
  ]
}
```

Key progression insight: the FLOAT PACE improves over the cycle (85% →
88% → 90% MP). This is the best indicator of marathon-specific fitness.

#### Speed Support Repeats (Speed support category)

Traditional interval structure with jog rest:

```json
{
  "title": "10K Pace Repeats — 4×2K",
  "workout_type": "speed_support",
  "segments": [
    {"type": "warmup", "distance_km": 2, "pace_pct_mp": 80},
    {"type": "work", "distance_km": 2, "pace_pct_mp": 110, "reps": 4},
    {"type": "jog_rest", "duration_min": 4, "pace_pct_mp": 75},
    {"type": "cooldown", "distance_km": 2, "pace_pct_mp": 80}
  ]
}
```

Progression: 8×1K → 5×1600m → 4×2K (same total volume, more extension).

#### Kenyan-Style Progression Run (General phase)

```json
{
  "title": "Progression Run — 12K",
  "workout_type": "progression",
  "segments": [
    {"type": "easy", "distance_km": 4, "pace_pct_mp": 80},
    {"type": "work", "distance_km": 3, "pace_pct_mp": 90},
    {"type": "work", "distance_km": 3, "pace_pct_mp": 95},
    {"type": "work", "distance_km": 2, "pace_pct_mp": 100}
  ]
}
```

#### Regenerative Workout

A quality-touch session between big workouts. 7/10 difficulty, not 9/10:

```json
{
  "title": "Regenerative Threshold — 6K",
  "workout_type": "regenerative",
  "difficulty": 7,
  "segments": [
    {"type": "warmup", "distance_km": 2, "pace_pct_mp": 80},
    {"type": "work", "distance_km": 6, "pace_pct_mp": 105},
    {"type": "cooldown", "distance_km": 2, "pace_pct_mp": 80}
  ]
}
```

---

## 6. Extension-Based Progression

### The Core Principle

> Within a training block, workouts progress by increasing the duration
> of effort at the SAME pace, not by increasing the pace of the same
> duration.

This is the single most important principle in the generator. The founder's
own training validates it:
- Speed: 400m → 800m → 1200m → 1 mile at the same pace
- Threshold: 6×5min → 4×7min → 3×10min at the same pace

### Implementation

Each workout category tracks three progression variables:

```python
@dataclass
class WorkoutProgression:
    category: str           # "speed", "threshold", "long_fast", "marathon_pace"
    segment_distance_m: int # Current extension level (e.g., 400, 800, 1200, 1600)
    pace_pct_mp: int        # Target pace (e.g., 110)
    reps: int               # Number of repetitions
    float_pace_pct_mp: int  # Float/recovery pace (for alternating km)
    total_work_km: float    # Total work volume at target pace
```

### Within-Block Progression Rules

For a 4-week block:

**Speed (110-115% MP):**
| Week | Extension | Reps | Total work |
|------|-----------|------|-----------|
| W1 | 400m | 8 | 3.2K |
| W2 | 800m | 5 | 4.0K |
| W3 | 1200m | 4 | 4.8K |
| W4 | cutback: 400m | 4-6 | 2.0K |

Pace is constant across all four weeks.

**Threshold (105% MP):**
| Week | Extension | Reps | Total work |
|------|-----------|------|-----------|
| W1 | 5 min | 6 | 30 min |
| W2 | 7 min | 4 | 28 min |
| W3 | 10 min | 3 | 30 min |
| W4 | cutback: 5 min | 3 | 15 min |

Pace is constant. Volume is roughly constant. Extension increases.

**Long fast (90-96% MP):**
| Week | Structure | Total |
|------|-----------|-------|
| W1 | 8K at 90% | 8K |
| W2 | 10-8K at 90-92% | 18K |
| W3 | 10-8-6K at 90-92-94% | 24K |
| W4 | cutback: 10K at 90% | 10K |

### Progression Priority Order

1. **Extension** — longer uninterrupted segments at the same pace (PRIMARY)
2. **Float/recovery pace** — faster recovery between segments (SECONDARY)
3. **Total volume** — more total work at the target pace (TERTIARY)
4. **Target pace** — faster target pace (LAST RESORT — only across blocks)

### What This Means for the Code

The `_build_quality` / `_plan_quality_sessions` functions in the current
n1_engine use `week_ratio` to scale dose (volume at target pace) and
rep length. This is partially correct — it does increase rep length via
a ladder. But it ALSO tightens paces via `week_ratio`, which violates
the extension principle.

The rewrite should:
1. Set pace from RPI at plan start (or block start for Build mode)
2. Hold pace constant within the block/phase
3. Increase extension week over week per the tables above
4. Allow pace to update ONLY at phase transitions (Race mode: general →
   supportive → specific) or block boundaries (Build mode: block N → N+1)

---

## 7. Build-Over-Build Progression

### The Problem

Every plan generation today is stateless. `generate_n1_plan` reads
FitnessBank and writes a plan from scratch. If the athlete just finished
a 4-week Build block where they peaked at 1200m repeats at 5:50 pace,
the next block has no idea. It would start them back at whatever the
default extension level is.

### The Solution: peak_workout_state

When a block completes (auto-renewal fires), the engine reads the peak
week's (W3) workouts and records the highest extension achieved per
category:

```json
{
  "speed": {
    "segment_distance_m": 1200,
    "pace_sec_per_km": 228,
    "reps": 4,
    "float_pace_pct_mp": null,
    "total_work_km": 4.8
  },
  "threshold": {
    "segment_duration_min": 10,
    "pace_sec_per_km": 252,
    "reps": 3,
    "float_pace_pct_mp": 85,
    "total_work_km": 5.0
  },
  "long_fast": {
    "max_distance_km": 24,
    "peak_pace_pct_mp": 94,
    "structure": "stepwise"
  }
}
```

This is stored on `TrainingPlan.peak_workout_state` (JSONB).

### Seeding the Next Block

When the auto-renewal task generates Block N+1:

1. Read `peak_workout_state` from Block N
2. Read current RPI from refreshed FitnessBank
3. Compute new paces from updated RPI

**Seeding rules:**

| Category | Block N+1 W1 starts at | Block N+1 W3 peaks at |
|----------|----------------------|---------------------|
| Speed | Block N's ~W2 extension, new RPI pace | Block N's W3 extension + 1 step, or same extension at new pace |
| Threshold | Block N's ~W2 extension, new RPI pace | Block N's W3 extension + 1 step, or longer total work |
| Long fast | Block N's W1 distance, new RPI pace | Block N's W3 distance + 1-2K |

**If RPI improved** (athlete got faster from the training):
- New paces are faster → same extension at faster pace IS progression
- The athlete does the same 1200m reps but at 5:45 instead of 5:50

**If RPI is flat** (no measurable pace improvement):
- Progression is pure extension: 1200m → mile → 2K reps at same pace
- Or increase total work volume at the same extension

**If RPI declined** (injury, illness, life disruption):
- Back off BOTH pace (new lower RPI) AND extension (start at Block N's W1)
- The block is effectively a recovery/rebuild block

**If athlete skipped most quality workouts in Block N:**
- `peak_workout_state` will show the PLANNED peak, but actual completion
  data (from `PlannedWorkout.completed` flags) shows they didn't do the work
- Generate a conservative block that repeats Block N's starting level
- Log warning: "Athlete skipped N/M quality sessions — repeating block level"

### Long-Term Trajectory

Over multiple blocks, the trajectory looks like:

```
Block 1: 400m → 800m → 1200m (at 5:50 pace)
Block 2: 800m → 1200m → mile (at 5:45 pace — RPI improved)
Block 3: 1200m → mile → 2K (at 5:45 pace — RPI flat, pure extension)
Block 4: mile → 2K → 2.5K (at 5:42 pace — RPI improved again)
```

This is what separates a plan generator from a training system.
The system remembers you across months and years.

---

## 8. Full-Spectrum Distribution

### Race Mode: Workout Distribution by Phase

#### General Phase

Focus: Build raw capabilities across wide range of speeds.

| Day | Workout | Category |
|-----|---------|----------|
| Tue | Progression run or Kenyan-style fartlek | VO2max/multi-pace |
| Wed | Easy or moderate | Recovery |
| Thu | Medium repeats at 90-92% 5K (track) | Speed support |
| Fri | Easy | Recovery |
| Sat | Long easy through hills OR long fast (every 2-3 weeks) | Long easy / Long fast |
| Sun | Rest or very easy | Recovery |
| Mon | Strong continuous at ~85% 5K | Threshold touch |

All paces anchored to 5K via RPI. 1-2 quality sessions per week.
Long fast runs introduced every 2-3 weeks, replacing the long easy run.

#### Supportive Phase

Focus: 90% and 110% MP — endurance support and speed support.

| Day | Workout | Category |
|-----|---------|----------|
| Tue or Wed | Speed support (5×1600m at 110% MP) OR threshold alt-km | Speed support / Threshold |
| Sat | Long fast run (stepwise at 90-96% MP) OR MP continuous | Long fast / Marathon pace |

Midweek: alternating between speed support and threshold each week.
Weekend: alternating between long fast and marathon pace.

1-2 quality sessions per week. Marathon pace workouts introduced here
as continuous runs (12-18K at 100% MP) before progressing to alt-km.

#### Specific Phase

Focus: 95-105% MP — marathon pace and its immediate neighbors.

| Day | Workout | Category |
|-----|---------|----------|
| Wed | Threshold alt-km (1K at 105%, 1K at 90%) OR regenerative | Threshold / Regenerative |
| Sat | Long fast stepwise (peak: 32K) OR MP alt-km (peak: 24K) | Long fast / Marathon pace |

Big stress → big recovery. 5-6 easy days between major workouts.
Mileage is a RANGE, not a target. Emphasis on being fresh for the
big sessions, not hitting volume numbers.

The last 1-2 weeks: reduce volume, maintain one quality session,
final dress rehearsal workout 10-14 days out.

### Build–Intensity Mode: Workout Distribution

Two quality sessions per week (for experienced; one for intermediate):

| Session | Block 1 focus | Block 2 focus | Block 3 focus |
|---------|--------------|--------------|--------------|
| Midweek | Threshold (extension progression) | Speed (extension progression) | Mixed (threshold + speed) |
| Weekend | Long run (progression: easy → fast finish → stepwise) | Long run (continued progression) | Long run (continued progression) |

Quality type rotation across blocks ensures all four fitness components
(VO2max, SSmax, economy, resilience) are addressed over time.

### Build–Volume Mode: Workout Distribution

ONE quality session per week (Wednesday), plus hill strides on 2-3 days:

| Wed type | Block cycle position | Focus |
|----------|---------------------|-------|
| Threshold | Blocks 1, 2, 3, ... | Extension-based: growing reps at 5min, then jump to 10min reps |
| Moderate steady | Alternating weeks within block | "Start relaxed and work into it" — no pace target |
| Easy volume | Recovery weeks within block | Pure aerobic consolidation |
| **BONUS: vVO2** | Every 4th-6th block | 12-20 × 1min fast/1min easy (5K effort) |

Threshold extension across blocks (Build–Volume):

| Block | Wed threshold structure |
|-------|----------------------|
| Block 1 | 3-6 × 5min @ 1hr effort |
| Block 2 | 4-8 × 5min @ 1hr effort |
| Block 3 | 4-10 × 5min @ 1hr effort |
| Block 4 | 6-12 × 5min @ 1hr effort |
| Block 5 | 3-6 × 10min @ 1hr effort (duration jump) |
| Block 6 | 4-8 × 10min @ 1hr effort |
| ...BONUS... | 12-20 × 1min fast/1min easy + tempo long run |

The rep count range is selected based on athlete's current volume band:
low-end athletes use low rep count, high-end use high rep count.

Hill strides (economy maintenance): 4-5 × 20-30s hills appear on
Tuesday, Saturday, or Sunday. These are NOT structured speed work —
they are neuromuscular maintenance run at 800m-mile effort with
walk/jog-down recovery. The generator places them on 2-3 days per
week outside of Wednesday.

### Maintain Mode: Workout Distribution

One quality session per week, rotating:

| Week | Quality type | Purpose |
|------|-------------|---------|
| W1 | Tempo/threshold | SSmax maintenance |
| W2 | Intervals/speed | VO2max maintenance |
| W3 | Fartlek/progression | Multi-pace maintenance |
| W4 | Cutback (strides only) | Recovery |

No progression. Same paces, same extension level. The goal is to
maintain current fitness, not improve it.

---

## 9. Modulation: Big Stress, Big Recovery

### The Pattern

As the plan progresses toward race day (Race mode) or toward the peak
week within a block (Build mode), the daily volume/intensity variability
increases.

**Early in training (General phase / Block W1):**
- Moderate daily variation
- Quality sessions at 7-8/10 difficulty
- Easy days at normal easy volume

**Late in training (Specific phase / Block W3):**
- Large daily variation
- Quality sessions at 9-9.5/10 difficulty
- Easy days shorter and easier
- Rest days more frequent

**Example specific-phase week:**
```
Sat: Stepwise 32K at 90-96% MP (9/10 difficulty)
Sun: Rest
Mon: 6-10K very easy
Tue: 10-14K easy
Wed: Regenerative 6-8K at 105% (7/10)
Thu: 12-14K easy
Fri: 10-12K easy
Sat: 6×(3K at 100%, 1K at 85%) (9/10)
Sun: Rest
```

**This is why mileage doesn't matter in the specific phase.** The
pattern is: big stress → big recovery → regenerate → big stress. Weekly
mileage falls out of this pattern naturally — it's a RANGE (65-80K),
not a target.

### Regenerative Workouts

Between big sessions, include "regenerative" workouts:
- Touch on a fitness quality without pushing hard
- 7/10 difficulty, not 9/10
- Shorter distance (6-8K instead of 12-14K)
- Same pace as the target category but less volume
- The athlete can choose the low end of a distance range if still tired

The generator should mark regenerative workouts explicitly:
`PlannedWorkout.workout_subtype = "regenerative"`.

---

## 10. Output Format

### Mapping to Existing Models

The engine produces `List[WeekPlan]` which the save path converts to
`TrainingPlan` + `PlannedWorkout` rows. The existing `_save_plan` in
`plan_generation.py` handles this.

**New/changed fields on PlannedWorkout:**

| Field | Change |
|-------|--------|
| `segments` | MUST be populated with the unified schema (section 5) for ALL structured workouts. Easy and rest days can have null segments. |
| `phase` | New values: `"general"`, `"supportive"`, `"specific"`, `"taper"`, `"build"`, `"maintain"` |
| `workout_type` | New values: `"long_fast"`, `"marathon_pace"`, `"threshold_alt"`, `"speed_support"`, `"regenerative"`, `"progression"` (in addition to existing `"easy"`, `"long"`, `"rest"`, `"threshold"`, `"intervals"`) |

**New fields on TrainingPlan** (from Training Lifecycle doc):

| Field | Purpose |
|-------|---------|
| `block_number` | Integer, current block count |
| `peak_workout_state` | JSONB, peak extension per workout category |

### Workout Description Quality Bar

Every `PlannedWorkout.description` must be specific enough that the
athlete knows exactly what to do without guessing. The quality bar is
the Davis sample schedule.

**BAD (current generator):**
```
"Threshold workout. Run at threshold pace."
```

**GOOD (target quality):**
```
"3×10min at threshold (6:45/mi) with 2min easy jog. Hold pace steady —
the progression from last week's 4×7min is the same pace for longer.
This is the peak extension for this block."
```

**EXCELLENT (target quality bar):**
```
"Alternating KM at half-marathon pace: 6×(1K at 4:03/km, 1K float
at 4:24/km). The float is NOT easy — maintain rhythm at steady-state
pace. Progression note: your float recovery pace has come down from
4:42 to 4:24 since week 6. That's the clearest sign your marathon
fitness is building."
```

The description should reference:
1. The specific paces in real numbers (min/km or min/mi — never % MP)
2. The progression context (what changed from last week, in concrete terms)
3. The training intent in plain language (why this workout matters)
4. **Fueling guidance** for any workout over 90 minutes or any race-day
   simulation: "Practice race fueling: target 75+ g/hr carbs, start
   fueling at minute 30."

**Fueling in descriptions — mandatory triggers:**
- Long runs ≥90 min → include fueling reminder with g/hr target
- Race simulation workouts → include full fueling protocol reference
- Race-day workout → include pre-race meal + in-race fueling plan
- Easy runs <60 min → no fueling guidance needed

**Example with fueling:**
```
"16-mile long run: start easy, progress to moderate in the final third.
Practice race fueling — aim for 75+ g/hr carbs starting at mile 4.
This is training your gut as much as your legs."
```

**The athlete's vocabulary is: easy, long run, threshold, tempo,
interval, race pace, recovery, fartlek, progression, steady-state,
half-marathon effort, 10K effort, 5K effort.** Use those words.
Never use "105% MP" or "90% MP" in any athlete-facing text.

---

## 11. Race Mode Worked Example: 13 Weeks to Marathon, 90 km/wk

This maps the Davis 13-week London plan to the generator's output format.

### Phase Split: 5 General / 4 Supportive / 4 Specific

### General Phase (Weeks 1-5) — Paces from 5K anchor

| Wk | Primary (midweek) | Secondary (midweek) | Weekend |
|----|-------------------|---------------------|---------|
| 1 | 10K progression run | 7×3min at 90-92% 5K, 1min jog | 8-10K at 85% 5K |
| 2 | 4×(3min at 95% 5K, 1min jog, 2min at 100% 5K, 3min jog) | 8×3min at 90-92% 5K, 45s jog | 16-18K at 75-80% 5K |
| 3 | 12K progression run | 4×(3min, 2min, 1min) at 98-100-102% 5K, 1min jog | 22-24K easy through hills |
| 4 | 10-12K at 85% 5K | 5-6×1200m at 90-92% 5K, 1min jog | 20-22K at 75-80% 5K |
| 5 | 4×(1K at 95% 5K, 2min jog, 1K at 98% 5K, 4min jog) | 12K progression w/ fast finish | 27-30K easy through hills |

**Convert fitness estimate to % MP at week 5/6 boundary.**

### Supportive Phase (Weeks 6-9) — Paces from % MP

| Wk | Primary (midweek) | Weekend |
|----|-------------------|---------|
| 6 | 12-14K continuous at 100% MP + 5-6×(1200m at 106%, 400m at 90%) | 10-8-7K stepwise at 90-92-94% MP |
| 7 | 8-10K continuous at 105% MP | 16-18K continuous at 100% MP |
| 8 | 5×1600m at 108-110% MP, 3min jog | 30-32K at 90-92% MP |
| 9 | 7-8×(1K at 105%, 1K at 85% MP) | 8×(2K at 100%, 1K at 85% MP) |

### Specific Phase (Weeks 10-13)

| Wk | Primary (midweek) | Weekend |
|----|-------------------|---------|
| 10 | 4×2K at 108-110% MP, 4min jog | 10-8-8-6K stepwise at 90-92-94-96% MP |
| 11 | 6-8K at 105% MP (REGENERATIVE) | 6×(3K at 100%, 1K at 85% MP) |
| 12 | 6×(1K at 103-105%, 1K at 90% MP) | 14K progression run (taper begins) |
| 13 | 5-6×4min at 104-107% MP, 1min jog | **RACE DAY** |

### Volume Progression

```
Wk:  1    2    3    4    5    6    7    8    9   10   11   12   13
Km: 70   75   80   84   87   90   90   90   90  80-90 72-80 65-80 race
```

Note weeks 10-12: RANGE, not target.

---

## 12. Build–Intensity Worked Example: Block 1 → Block 2

### Block 1 (athlete's first Build block, 60 km/wk current)

| Week | Volume | Speed workout | Threshold workout | Long run |
|------|--------|--------------|-------------------|----------|
| W1 | 60K | 8×400m at 5K pace | — | 16K easy |
| W2 | 63K | 5×800m at 5K pace | 6×5min at threshold | 17K easy |
| W3 | 67K | 4×1200m at 5K pace | 3×9min at threshold | 18K w/ last 3K at 90% MP |
| W4 | 55K | 4×400m at 5K pace (cutback) | strides only | 14K easy |

`peak_workout_state` recorded from W3:
```json
{
  "speed": {"segment_distance_m": 1200, "pace_sec_per_km": 228, "reps": 4},
  "threshold": {"segment_duration_min": 9, "pace_sec_per_km": 252, "reps": 3},
  "long_run": {"distance_km": 18, "peak_effort_pct_mp": 90}
}
```

### Block 2 (RPI improved from 48.2 to 49.0 — paces update)

| Week | Volume | Speed workout | Threshold workout | Long run |
|------|--------|--------------|-------------------|----------|
| W5 | 63K | 5×800m at NEW 5K pace (faster) | 4×7min at NEW threshold | 17K w/ last 2K at 90% MP |
| W6 | 67K | 4×1200m at new pace | 3×10min at new pace | 18K w/ last 3K at 92% MP |
| W7 | 72K | 3×mile at new pace | 2×14min at new pace | 20K w/ last 4K at 90-94% MP |
| W8 | 58K | 4×800m (cutback) | strides only | 15K easy |

Block 2 W5 starts where Block 1 W2 was (800m), not back at 400m.
Block 2 W7 peaks BEYOND Block 1 W3 (mile > 1200m). That's progression.
And the paces are slightly faster because RPI improved.

---

## 12b. Build–Volume Worked Example: 40 mi/wk Athlete

Athlete: 40 mi/wk runner, no race on calendar, wants aerobic development.
RPI: 42.0 (threshold ~7:45/mi). Mid-band volume.

### Initial 10-Week Plan (weeks 1-10)

**First block (weeks 1-4): Introduction**

| Day | W1 | W2 | W3 | W4 |
|-----|----|----|----|----|
| Mon | Rest | Rest | Rest | Rest |
| Tue | 4-6 mi easy + 5×30s hills | 4-7 mi easy + 5×20s hills | 4-7 mi easy + 5×30s hills | 5-7 mi easy |
| Wed | 3-5 mi easy, 5-8×30s hills, 2-4 mi easy | **Threshold:** 3×5min @ 7:45/mi, 2min easy | 5-8 mi easy/mod to moderate | **Threshold:** 4×5min @ 7:45/mi, 2min easy |
| Thu | 60 min x-train (bike Z2) | 60-90 min x-train | 60-90 min x-train | 60-90 min x-train |
| Fri | 3-5 mi easy | 3-5 mi easy | 3-5 mi easy | 3-5 mi easy |
| Sat | 7-9 mi easy/mod hills | 8-10 mi easy/mod hills | 9-11 mi easy hills + 5×30s hills | 8-10 mi easy/mod hills |
| Sun | 4-6 mi easy + 4×30s hills | 4-7 mi easy + hills | 4-7 mi easy | 4-6 mi easy + 4×30s hills |

**Second block (weeks 5-10): The Repeatable Core**

| Day | W5 | W6 | W7 | W8 | W9 | W10 |
|-----|----|----|----|----|----|----|
| Mon | Rest | Rest | Rest | Rest | Rest | Rest |
| Tue | 5-7 mi easy | 5-7 mi easy + 5×30s hills | 5-7 mi easy + 5×20s hills | 5-7 mi easy + 5×30s hills | 5-7 mi easy | 5-7 mi easy + 5×30s hills |
| Wed | 5-8 mi easy | **T:** 5×5min @ 7:45 | 5-9 mi easy/mod | **T:** 7×5min @ 7:45 | 5-8 mi easy | **T:** 3×10min @ 7:45 |
| Thu | 60-90 min x-train | 60-90 min x-train | 60-90 min x-train | 60-90 min x-train | 60-90 min x-train | 60-90 min x-train |
| Fri | 3-5 mi easy | 3-5 mi easy | 3-5 mi easy | 3-5 mi easy | 3-5 mi easy | 3-5 mi easy |
| Sat | 9-12 mi easy | 9-11 mi easy/mod hills | 10-13 mi easy | 10-12 mi easy/mod hills | 8-10 mi easy | 10-13 mi easy/mod hills |
| Sun | 4-7 mi easy + hills | 4-7 mi easy | 5-8 mi easy + hills | 5-8 mi easy | 4-7 mi easy + hills | 4-7 mi easy + hills |

**Threshold extension is visible:** 3×5min → 4×5min → 5×5min → 7×5min → 3×10min.
Same effort ("1-hour effort" = threshold), growing reps, then duration jump.

### When the Athlete Repeats (Block 3, weeks 5-10 again)

Volume nudges up slightly (now targeting 42-45 mi/wk range). Threshold
paces update if RPI has improved. The same week-by-week structure
runs again with higher rep counts and/or longer reps.

### BONUS WEEK (inserted after every 4th repetition)

| Day | Session |
|-----|---------|
| Tue | 4-7 mi easy + 5×20s hills |
| **Wed** | **3-5 mi easy, 14×1min fast (5K effort)/1min easy, 2-4 mi easy** |
| Thu | 60-90 min x-train |
| Fri | 3-5 mi easy |
| **Sat** | **10-12 mi easy/mod with 30-45 min moderate/hard** |
| Sun | 4-6 mi easy + 4×30s hills |

The bonus week is the ONLY time this athlete sees vVO2 work (1min fast
repeats) and tempo long run effort. It prevents the aerobic system
from plateauing at the threshold ceiling.

### Distance Ranges as Built-In Flexibility

"5-7 mi easy" means: if you feel great, do 7. If you're tired, do 5.
If you're somewhere in the middle, do 6. The plan breathes WITH the
athlete. This is "plans written in pencil" at the structural level.

The generator determines the range for each session based on:
- Athlete's current weekly volume (places them in the band)
- Day-of-week role (Friday is always the shortest)
- Block position (peak weeks get slightly wider ranges)

---

## 13. Validation Criteria

### Generator Output Quality

- [ ] Every structured workout has populated `segments` with unified schema
- [ ] Every segment includes both `pace_pct_mp` and `pace_sec_per_km`
- [ ] Workout descriptions include specific paces, progression context, and intent
- [ ] Race mode uses three phases: general, supportive, specific (not base/build/peak/taper)
- [ ] General phase workouts are anchored to 5K pace, not marathon pace
- [ ] 90-95% MP gap is filled with stepwise long fast runs and float recoveries
- [ ] No workout categories have gaps wider than 10% in the pace ladder
- [ ] Every workout ≥90 min includes `fueling_target_g_per_hr` and a fueling reminder in the description
- [ ] Race-day workouts include full fueling protocol (pre-race + in-race targets)

### Extension-Based Progression

- [ ] Within a block: pace is CONSTANT, extension increases week over week
- [ ] Speed: 400m → 800m → 1200m → mile (or similar ladder) at same pace
- [ ] Threshold: segment duration increases at same pace
- [ ] Long fast: distance increases with stepwise structure progression
- [ ] W4 / cutback week reduces both volume and extension

### Build-Over-Build

- [ ] `peak_workout_state` is computed and stored at block completion
- [ ] Next block's W1 starts at previous block's ~W2 extension level
- [ ] If RPI improved, paces update; extension starts at mid-level
- [ ] If RPI flat, paces hold; extension is the only progression lever
- [ ] If RPI declined, both pace and extension back off
- [ ] If athlete skipped most quality sessions, block repeats previous level

### Modulation

- [ ] Specific phase / peak weeks: big workouts (9/10) followed by 2-3 easy days
- [ ] Regenerative workouts (7/10) placed between big sessions
- [ ] Specific phase mileage is a range, not a target
- [ ] Easy day volume decreases as quality session volume increases

### Full Spectrum

- [ ] Race mode (marathon/HM) general phase includes work at 80%, 85-90%, 100%, 110%, 115%+
- [ ] Race mode (marathon/HM) supportive phase emphasizes 90% and 110% MP
- [ ] Race mode (marathon/HM) specific phase emphasizes 95-105% MP
- [ ] Race mode (5K/10K) uses variety-based speed rotation (different structure each week)
- [ ] Race mode (5K/10K) Saturday long runs include a structured element (fartlek, threshold, fatigue resistance)
- [ ] Race mode (5K/10K) uses effort-based pacing with RPI-derived pace ranges, not fixed paces
- [ ] Race mode (5K/10K) includes race simulation session 10-14 days before race
- [ ] Race mode (5K/10K) terrain guidance: speed on flat, threshold on any, hills for masters
- [ ] Race mode (5K/10K) plan length defaults to 8 weeks (not 12-16)
- [ ] Race mode (ultra int/adv) uses three-phase: speed→threshold bridge→race-specific
- [ ] Race mode (ultra int/adv) includes steady runs as standalone sub-threshold sessions
- [ ] Race mode (ultra int/adv) includes alternating-km long runs (1mi threshold / 1mi float)
- [ ] Race mode (ultra int/adv) includes back-to-back weekends peaking ~3 weeks out
- [ ] Race mode (ultra int/adv) places race simulation ~4 weeks out (not 2)
- [ ] Race mode (ultra champion) uses hybrid alternating progression (speed ↔ threshold weeks)
- [ ] Race mode (ultra champion) speed sessions end with post-workout "steady" segment at race effort
- [ ] Race mode (ultra champion) includes "Power Hour" (1hr mod/hard within long run) ~3 weeks out
- [ ] Race mode (ultra champion) includes uphill TM as standalone Z2 day and structured doubles
- [ ] Race mode (ultra, both) long runs rotate: easy/mod+vert, structured threshold, fatigue resistance hills at END
- [ ] Race mode (ultra, both) prescribes "strong downs" for eccentric contraction training
- [ ] Race mode (ultra, both) periodizes strength: heavy→light→none across the plan
- [ ] Race mode (ultra, both) auto-selects variant based on volume/experience (<50mi/wk → int/adv, ≥50mi/wk → champion)
- [ ] Build–Intensity mode touches threshold, speed, and long run in every block
- [ ] Build–Volume mode has exactly ONE quality session per week (Wednesday)
- [ ] Build–Volume uses distance ranges, not fixed distances, for all non-quality sessions
- [ ] Build–Volume auto-inserts BONUS WEEK (vVO2 + tempo long run) every 4-6 blocks
- [ ] Build–Volume threshold follows extension: growing reps at 5min, then jump to 10min
- [ ] Build–Volume prescribes x-train day (Thursday) as a training session, not rest
- [ ] Build–Volume includes hill strides on 2-3 non-quality days per week
- [ ] Build–Onramp: 4 runs/wk (not more) for athletes <30K/wk
- [ ] Build–Onramp: hike/x-train days are prescribed training, not rest
- [ ] Build–Onramp: distance-effort alternation — never increase both in the same week
- [ ] Build–Onramp: sensory effort cues ("smooth and quick"), NOT zone names ("5K effort")
- [ ] Build–Onramp: run/hike is part of the long run prescription for beginners
- [ ] Build–Onramp: bodyweight strength only (step-ups + core), no gym routines
- [ ] Build–Onramp: exit state matches entry state for all other plans (20-33 mi/wk)
- [ ] Build–Onramp: auto-prompts next plan selection after completion
- [ ] Maintain mode rotates through all three quality types

### Physiological Constraints (from Advanced Physiology Synthesis)

- [ ] **80/20 rule:** No more than 20% of weekly volume is at or above threshold pace (≥105% MP). The generator must audit its own output against this constraint.
- [ ] **Biomechanical load limit:** Speed work at ≥110% MP limited to 1-2 sessions per week maximum. Three speed sessions in a week is an injury risk regardless of physiological readiness.
- [ ] **Masters athlete modifier:** For athletes over 40, generator uses longer blocks (5-6 weeks), more conservative extension steps, additional recovery days after speed work, and hill variants for speed work instead of flat (lower impact, same neuromuscular stimulus).
- [ ] **Float recovery pace:** Float/recovery segments in alternating-km workouts are at 85-90% MP, NOT at easy pace. This is a specific physiological prescription for lactate clearance training.

### Backward Compatibility

- [ ] Existing Race mode plans for 5K, 10K, HM, Marathon still generate correctly
- [ ] `PlannedWorkout` rows created by the new engine are compatible with existing calendar UI, briefing, and correlation engine
- [ ] Existing `_save_plan` path works with new output format
- [ ] `segments` schema is backward compatible (old consumers still function)

---

## 14. Files to Change

| File | Action |
|------|--------|
| `apps/api/services/plan_framework/n1_engine.py` | **REWRITE** — implement unified engine with pace ladder, three-phase periodization, extension-based progression |
| `apps/api/services/workout_prescription.py` | **EXTEND** — add `compute_pace_ladder()`, update `DayPlan` to include segments with unified schema |
| `apps/api/services/plan_framework/general_plan_generator.py` | **NEW** — Build + Maintain mode configs that call the unified engine |
| `apps/api/models.py` | **MODIFY** — add `block_number`, `peak_workout_state` to TrainingPlan; make race fields nullable |
| `apps/api/routers/plan_generation.py` | **MODIFY** — add `POST /v2/plans/general` endpoint |
| `apps/api/tasks/plan_renewal_tasks.py` | **NEW** — auto-renewal with peak_workout_state computation and seeding |
| `apps/api/services/plan_framework/workout_scaler.py` | **MODIFY** — update segment schema to unified format |

## What Does NOT Change

- `fitness_bank.py` — read-only input source
- `constraint_aware_planner.py` — race plan wrapper (calls n1_engine internally)
- `rpi_calculator.py` — pace calculations (source of truth for RPI → pace)
- Correlation engine — reads PlannedWorkout rows regardless of format
- Calendar UI — renders PlannedWorkout rows (may need minor updates for new segment display)
- Briefing pipeline — reads PlannedWorkout rows (benefits from richer descriptions)
