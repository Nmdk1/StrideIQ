# SSmax (Steady-State Max) — Reference Note

**Source:** John J. Davis, Ph.D. — "Steady-state max (SSmax) for runners: The maximal metabolic steady state"
**Published:** August 19, 2024
**Filed:** April 10, 2026
**Relevance:** Plan generator workout intensity prescription, coach post-workout analysis, Operating Manual limiter detection

---

## Core Concept

SSmax is the boundary between metabolically sustainable and metabolically
unsustainable running intensities. Below SSmax, oxygen consumption, blood
lactate, intramuscular pH, and phosphocreatine levels are all stable over
time. Above SSmax, all of these biomarkers progressively crash toward their
limiting values until the athlete must stop.

SSmax is the underlying biological phenomenon. Lactate threshold (LT2),
maximal lactate steady-state (MLSS), and critical speed (CS) are all
methods of ESTIMATING SSmax. They are not SSmax itself.

---

## Three Intensity Domains Relative to SSmax

| Domain | % of 5K pace | Metabolic state | Training purpose |
|--------|-------------|-----------------|------------------|
| Sub-SSmax | ~90-92% | Stable steady-state | Volume of quality work, aerobic power development |
| At SSmax | ~93-96% | Unpredictable, unstable | Avoid prescribing here — inconsistent physiological response |
| Supra-SSmax | ~98-100% | Unsustainable, progressive deterioration | Forces adaptation, lifts SSmax ceiling |

The "soccer ball on a ridge" analogy: running exactly at SSmax is like
balancing a ball on a narrow ridge — it rolls unpredictably one way or
the other. Prescribe workouts BELOW or ABOVE SSmax, not AT it.

---

## Mapping to RPI Pace System

StrideIQ's RPI calculator provides 5K equivalent pace. SSmax zones derive
directly from this anchor:

```
5K pace = RPI-derived 5K equivalent

Sub-SSmax floor:  5K pace × 1.087  (90% of 5K pace → ~8% slower)
Sub-SSmax ceiling: 5K pace × 1.042  (92% of 5K pace → ~4% slower)
SSmax estimate:    5K pace × 1.042  (96% of 5K pace → ~4% slower)
Supra-SSmax floor: 5K pace × 1.020  (98% of 5K pace → ~2% slower)
Supra-SSmax ceil:  5K pace × 1.000  (100% of 5K pace)
```

These percentages are approximate and fitness-level dependent. Davis notes
the final analysis will include confidence intervals. For coaching purposes,
the key insight is the THREE-ZONE model, not precise cutoffs.

---

## Implications for Plan Generator

### Build Mode Quality Session Prescription

The Build mode generator should distinguish between two types of "quality"
work, not just "threshold" as a single category:

**Sub-threshold sessions (below SSmax):**
- Purpose: rack up volume at a fast but metabolically sustainable intensity
- Example: 3-5 × 2K at ~91% of 5K pace, 90s rest
- Feel: steady-state throughout — the last rep should feel similar to the first
- Norwegian-style cruise intervals, Daniels cruise intervals at the easier end
- Adaptation: improves time-to-exhaustion at SSmax fraction, aerobic power

**Supra-threshold sessions (above SSmax):**
- Purpose: intentionally exceed SSmax to force adaptation ("crisis" stimulus)
- Example: 6-8 × 1K at ~99% of 5K pace, 2-3min rest
- Feel: progressive difficulty — each rep harder than the last
- Ingebrigtsen-style 400m/1K repeats at 10K-8K pace
- Adaptation: lifts SSmax itself — raises the ceiling

**Do not prescribe "at SSmax":**
- Workouts at exactly SSmax pace produce unpredictable responses
- The athlete might be in a steady-state or might be slowly deteriorating
- This is NOT a useful training stimulus because the response is inconsistent

### Build Mode Block Rotation (refined)

| Block | Quality focus | SSmax relationship |
|-------|--------------|-------------------|
| Block 1 | Sub-threshold (cruise intervals, tempo) | Below SSmax — volume of quality |
| Block 2 | Supra-threshold (track intervals, fartlek) | Above SSmax — raise the ceiling |
| Block 3 | Mixed (one sub, one supra per week) | Both stimuli |
| Block 4+ | Repeat cycle | Progressive overload within each type |

### Maintain Mode

Maintain mode quality sessions should stay sub-threshold (below SSmax).
The goal is maintenance, not adaptation crisis. One sub-threshold session
per week, rotating type (cruise intervals, tempo, fartlek at controlled
effort). No supra-threshold work unless the athlete is building toward
a race (at which point they should switch to Build or Race mode).

---

## Implications for AI Coach

### Post-Workout SSmax Detection

The coach has stream data from every workout: pace, HR, cadence over time.
It can detect whether the athlete was in a metabolic steady-state or not:

**Steady-state indicators:**
- Cardiac drift < 3% (stable HR at stable pace)
- Pace drift near zero across work intervals
- HR recovery between intervals is consistent

**Non-steady-state indicators:**
- Progressive cardiac drift > 5% across the workout
- Pace decay from early to late intervals at similar HR
- HR recovery between intervals progressively lengthening

**Coaching insight the coach can surface:**
- "Your cruise intervals showed stable HR and pace through all 5 reps —
  you were in a genuine steady-state. That's the right stimulus."
- "Your threshold session showed HR climbing 8bpm from rep 1 to rep 6 at
  the same pace — you crossed above SSmax around rep 4. The first three
  reps were productive sub-threshold work; the last three were supra-
  threshold crisis work. Both are useful, but know that this wasn't a
  steady-state workout."
- "Your long run showed 12% cardiac drift in the last 3 miles — you
  drifted above SSmax at the end. For a long run, that's too much
  intensity in the back half."

### Pacing Guidance

When prescribing threshold workouts, the coach should specify WHICH
side of SSmax the athlete should target:

- "Today's cruise intervals target sub-threshold — stay at 7:00/mi. It
  should feel controlled and repeatable. If the last rep feels significantly
  harder than the first, you went too fast."
- "Today's 1K repeats target supra-threshold — 6:15/mi. This should get
  progressively harder. That's the point. The difficulty IS the stimulus."

---

## Implications for Operating Manual

### Limiter Detection

The Manual can surface which side of the SSmax equation the athlete needs:

**Needs higher SSmax (raise the ceiling):**
- 5K relatively fast, but half marathon pace is far from SSmax estimate
- Strong short efforts, poor sustained efforts
- Signal: "Your speed is ahead of your endurance. Supra-threshold work
  will lift your ceiling."

**Needs better endurance at SSmax (sustain the ceiling longer):**
- Good SSmax estimate relative to peers, but marathon/half underperforms
- Can hit threshold pace for 20 minutes but deteriorates at 40
- Signal: "Your ceiling is high but you can't maintain it. Sub-threshold
  volume and long run progression are your priority."

This maps to Davis's three coaching examples:
1. Middle-distance runner → needs higher SSmax (doesn't need duration)
2. College 5K runner underperforming in marathon → needs endurance at SSmax
3. BQ-chasing runner → needs both

---

## Key Quotes for KB / Coach Prompt Context

> "If the workout is getting progressively more difficult as you continue,
> you're likely not at a metabolic steady-state, even if you're hitting
> the 'correct' pace."

> "You don't necessarily want to run exactly at your SSmax... it's more
> useful to think of SSmax as a boundary between different physiological
> domains, as opposed to a magic intensity."

> "There's no guarantee that running at SSmax is the best way to improve
> SSmax. One effective way to stimulate your body to improve SSmax is to
> intentionally exceed it to put your body into a bit of a crisis and
> force it to adapt."

> "Improving SSmax is a worthy goal in most cases, but isn't always the
> top priority. Sometimes, you'll want to focus on sustaining a metabolic
> steady-state for longer."

---

## Connection to Existing StrideIQ Concepts

| StrideIQ concept | SSmax mapping |
|-----------------|---------------|
| RPI pace calculator | Provides the 5K anchor from which SSmax zones derive |
| Threshold workout type | Should specify sub-threshold or supra-threshold |
| Cardiac drift (stream analysis) | Direct detector of steady-state vs non-steady-state |
| Efficiency metric | Relates to metabolic cost of running — VO2 proxy |
| AdaptationNeed.THRESHOLD | Maps to "improve SSmax" |
| AdaptationNeed.DURABILITY | Maps to "sustain SSmax longer" |
| Build mode quality rotation | Should alternate sub-threshold and supra-threshold blocks |
| Heat adjustment | SSmax itself doesn't change in heat, but the PACE at SSmax does — the adjustment is correct |

---

## What NOT to Do with This

- Do NOT create a new "SSmax pace" field in the database. SSmax is derived
  from 5K pace (RPI), not independently measured.
- Do NOT present SSmax terminology to athletes. Use coaching language:
  "steady-state effort" and "above steady-state" instead of "sub-SSmax"
  and "supra-SSmax."
- Do NOT treat the 90-92% / 96% / 98-100% cutoffs as precise. They are
  population approximations. The correlation engine should learn each
  athlete's individual SSmax boundary over time from cardiac drift patterns
  at different intensities.
- Do NOT use lactate values. We don't have lactate data. We have HR and
  pace, which are sufficient proxies for steady-state detection.
