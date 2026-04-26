# SWAP Dictionary of Effort Terminology — Reference Note

**Source:** SWAP Running Patreon, David and Megan Roche
**Filed:** April 10, 2026
**Relevance:** Defines the effort language the plan generator and coach
model must use in all athlete-facing workout descriptions. This is the
canonical mapping from internal pace calculations to human language.

---

## Why Effort, Not Pace

> "Instead of over-prescribing paces that are subject to dozens of
> variables (some of which we could measure in a perfect world, but
> many of which we never could), we try to develop that sense of feel
> over time so it becomes second nature."

The prescribed efforts are **general zones that provide cues to learn
from.** The athlete takes these cues into the next workout, eventually
developing "feel" from a relatively unstructured starting point.

Example from Roche: A world-class female athlete doing 1-mile
intervals at "1-hour effort" with 3min float recovery. Her measured
lactate threshold is ~2.5 mmol at low-5:00/mi. Her 1-hour race pace
is ~5:00/mi. But the workout prescription says "1-hour effort," and
on any given day that might be:
- 5:30/mi (heavy training, fatigue)
- 5:00-5:15/mi (progressing through)
- 5:45/mi (bad day)

All three are correct. The effort cue IS the prescription. The pace
is a consequence of effort + current state, not the target.

> "We want day-to-day athlete autonomy grounded in long-term
> physiology."

**Implication for StrideIQ:** The generator computes paces internally
using RPI and the pace ladder. But the athlete-facing description
should lead with effort language and include pace as a RANGE (not a
target). "1-mile intervals at 1-hour effort (~6:20-6:40/mi)" — not
"1-mile intervals at 6:28/mi."

---

## The Dictionary

### Easy

**Internal:** ~75-85% MP. Z1-Z2.
**Feel:** Relaxed and smooth. No holding back on good days as long as
recovery isn't impacted.

> "The question to ask yourself is can you absorb the session and
> adapt for the following day's training, while absorbing the volume
> healthily?"

- Beginner: may spend more time in Z2 or even Z3
- Advanced: mostly Z1 with some Z2
- Good days: can flow into Z3, especially on uphills

**Generator usage:** Default for non-quality days. No specific pace
target. Description: "Easy — relaxed and smooth, whatever feels
right today."

### Very Easy

**Internal:** ~70-80% MP. Z1 only.
**Feel:** Intentional recovery. A shuffle.

> "An easy day encompasses some days being very easy, but a very easy
> day should not progress effort much at all."

**Generator usage:** Post-workout days, pre-long-run Fridays. "Very
easy — a shuffle is perfect. Nothing is too slow."

### Easy/Moderate

**Internal:** ~80-90% MP. Z2-Z3, sometimes Z4 on uphills.
**Feel:** NOT a specific effort. A general approach — giving yourself
leeway to use good days.

> "The goal is not to recover for the next day, but to get a solid
> aerobic and mechanical stimulus, but without turning it into a
> hard effort."

- Good days: may push into Z3 or Z4 on uphills, flow on downhills
- Tired days: just nice and easy
- The athlete decides, not the plan

**Generator usage:** Long runs (Saturday). "Easy/mod — run with
purpose. Push the uphills if you feel good, or keep it easy if you
don't. Both are right."

### Running With Intention / Purpose

**Internal:** ~85-90% MP. Z2/Z3 boundary.
**Feel:** A subset of easy/mod. Addresses the problem of doing lots
of easy volume with zero incentive to be efficient in the middle
zones.

> "Athletes who do hard workouts and purely easy runs might be
> economical at faster paces but have a drop-off in the middle zones
> where some of the best aerobic development happens."

**Generator usage:** Mid-week easy runs that aren't pure recovery.
"Run with intention — this isn't a recovery day."

### Moderate

**Internal:** ~88-95% MP. Z3. Context-dependent.
**Feel:** "Lock into middle zones, avoiding pushing hard, but making
it happen."

Two ends of the spectrum:
- Faster: "moderate (think 1-hour effort)" — upper Z3
- Slower: "moderate (think 50k effort)" — lower Z3

When used on threshold work: a cue to NOT push way too hard.
When used on steady runs: a cue to NOT go way too easy.

**Generator usage:** Always pair with a context cue. Never just
"moderate" alone. "Moderate — think 50K effort" or "Moderate —
think 1-hour effort."

### Easy/Mod to Moderate

**Internal:** ~82-92% MP. Z2 into Z3.
**Feel:** Relaxed start progressing to a faster finish.

**Generator usage:** Wednesday steady/progression runs. "Start
relaxed in Z2 and work into a moderate effort by the end."

### Steady

**Internal:** ~90-95% MP. Z3.
**Feel:** Sub-threshold sustained running. Lactate shuttling zone.

> "A training term that usually means something around 50k effort,
> but for pro athletes it might be 50-mile effort, and for less
> advanced athletes it might be a bit faster."

**Generator usage:** Post-workout steady segments and standalone
steady runs. "Steady — think 50K effort. You're shuttling lactate
from the hard work."

### 50K Effort

**Internal:** ~90-93% MP. Z3.
**Feel:** Synonym for "steady." Sustainable for very long periods
with proper fueling.

**Generator usage:** Ultra race-pace segments. "50K effort — moving
with purpose, sustainable all day with fueling."

### Mod/Hard

**Internal:** ~95-105% MP. Z3-Z4.
**Feel:** Context-dependent. On hills: effort is high but controlled
start prevents going out too hard and fading. On threshold: "it's
relatively controlled to start, and it gets hard as the work
accumulates."

> "A classic example of the cue informing the development of feel."

**Generator usage:** Hill intervals and harder threshold sessions.
"Mod/hard — start controlled, let it build. It's ok if it feels
hard by the end."

### "Fast" Strides (≤30 seconds)

**Internal:** ≥120% MP. 800m/mile race pace.
**Feel:** "The fastest pace you can go while using long-distance
form." NOT a sprint.

> "Ease in to avoid a pulled muscle, then get to work as you build
> up."

**Generator usage:** Hill strides and flat strides. "Fast — smooth
and strong, think 800m/mile effort. Not a sprint."

### "Fast" Intervals (>30 seconds)

**Internal:** 108-115% MP. Usually paired with distance-effort cue.
**Feel:** Going fast for mechanical adaptations. "I am ok with
athletes getting freaky with higher output on the good days."

Unlike threshold work (where pace matters less and the aerobic
system is the target), speed work IS about output — faster over
time is the goal.

**Generator usage:** Always paired with a specific effort. "Fast
(think 5K effort)" or "Fast (think 10K effort)."

### 3K Effort

**Internal:** ~115-120% MP.
**Feel:** Less sustainable than 5K, just easier than a stride. Power
and pure speed.

**Generator usage:** Short hill repeats, final push intervals.
"Think 3K effort — powerful but not a sprint."

### 5K Effort

**Internal:** ~110-115% MP. Approximately vVO2max.
**Feel:** "Relaxed, but fatigue accumulates as an interval goes on,
often feeling quite challenging by the end."

> "If you imagine you're a 20-minute 5k runner, imagine you're
> starting a 20-minute hard race. Let that imagination guide you."

**Generator usage:** Main speed intervals. "5K effort — imagine
starting your dream-day 5K race."

### 10K Effort

**Internal:** ~105-110% MP.
**Feel:** More sustainable than 5K, "the ability to gobble up larger
amounts of work."

> "In many cases, athletes will go a bit faster than their 10k race
> pace on the intervals (especially less advanced athletes), and
> that's ok."

**Generator usage:** Longer speed intervals, progression targets.
"10K effort — sustainable speed, nice and relaxed."

### 1-Hour Effort / Threshold

**Internal:** ~103-105% MP. Z3→Z4, sometimes Z5 across a session.
**Feel:** "The crossover point when it's less about working on speed,
and more about developing the aerobic system."

> "At first, it feels relatively controlled with fatigue accumulating
> across 5-10 minutes of work. By the end it often feels challenging
> within 1 minute of starting an interval."

Threshold is a synonym for 1-hour effort. When doing lactate testing,
Roche discusses LT1 and LT2, but notes that LT2 "is not a set number
that we know, changing day-to-day."

**Generator usage:** Threshold intervals and tempos. "1-hour effort
— controlled at first, it'll get hard as you go. That's the point."

### Half Marathon Effort

**Internal:** ~101-103% MP.
**Feel:** Same idea as threshold but "a bit easier and often with
some general paces in mind."

**Generator usage:** Taper-week tempos, supportive-phase runs.
"Half marathon effort — a notch below threshold."

### Marathon Effort

**Internal:** ~98-100% MP.
**Feel:** "Threshold effort minus a few notches."

> "Over time, we're trying to push marathon effort as close to
> threshold effort as possible, so it's often ok to play with fire
> on marathon effort workouts, without being delusional."

> "In training, 'marathon effort' is often slower than 'marathon
> pace,' particularly on big sessions."

**Generator usage:** Extended tempos, race-week priming. "Marathon
effort — sustainable for 2+ hours. It's ok if it's a bit slower
than your goal marathon pace today."

### Strong Downhills

**Internal:** No pace target. Terrain-specific cue.
**Feel:** "Run downhills that are as steep or steeper than your race
faster than you will on race day. Take off the brakes and let your
body flow."

**Generator usage:** Sunday long runs for ultra athletes, training
runs with vert. "Strong downhills — practice owning them. This is
free speed on race day."

### Strong Uphills

**Internal:** Z2→threshold on climbs.
**Feel:** "Athletes will be above Z2 on climbs, but have the leeway
to push up toward threshold." Functionally similar to easy/mod on
a good day.

**Generator usage:** Hilly long runs. "Strong uphills — push into
Z3 or Z4 on the climbs. Let the effort dictate, not the pace."

---

## The Effort Ladder (Internal → Athlete-Facing Mapping)

| Internal % MP | Zone | Athlete-facing term | When to use |
|--------------|------|--------------------|--------------------|
| 70-80% | Z1 | Very easy / shuffle | Recovery, pre-long-run |
| 75-85% | Z1-Z2 | Easy | Default non-quality |
| 80-90% | Z2-Z3 | Easy/mod | Long runs, intention runs |
| 85-90% | Z2/Z3 | Running with intention | Mid-week purpose runs |
| 88-95% | Z3 | Moderate (+ context) | Steady runs, progression |
| 90-95% | Z3 | Steady / 50K effort | Post-workout, ultra pace |
| 95-100% | Z3-Z4 | Marathon effort | Extended tempos |
| 98-103% | Z3-Z4 | Half marathon effort | Supportive tempos |
| 103-105% | Z4 | 1-hour effort / threshold | Key quality sessions |
| 95-105% | Z3-Z4 | Mod/hard (on hills/threshold) | Hills, harder sessions |
| 105-110% | Z4 | 10K effort | Longer speed intervals |
| 110-115% | Z4-Z5 | 5K effort / vVO2 | Main speed work |
| 115-120% | Z5 | 3K effort | Short power intervals |
| ≥120% | Z5+ | Fast / strides (800/mile) | Strides (≤30s) |

**CRITICAL:** These % MP values are APPROXIMATE. The effort terms are
the prescription. The percentages help the generator select appropriate
paces, but the athlete-facing description always leads with the effort
term. If the computed pace doesn't match the effort feel (e.g., the
athlete's threshold pace from RPI would be "too easy" for "1-hour
effort"), the effort cue takes precedence and the generator should flag
the discrepancy for the coach model to investigate.

---

## How The Generator Uses This Dictionary

1. **Compute paces internally** from RPI using `calculate_paces_from_rpi()`
   and `compute_pace_ladder()`.

2. **Select the effort term** from this dictionary based on the
   workout's position on the pace ladder.

3. **Write the athlete-facing description** leading with effort,
   followed by a pace RANGE:
   - "6×5min at 1-hour effort (~6:20-6:40/mi)"
   - "10mi easy/mod — run with intention, push uphills if feeling good"
   - "4×30s fast (800m/mile effort) with jog-down recovery"

4. **Never write a fixed pace** as the primary prescription.
   "6×5min at 6:28/mi" → WRONG.
   "6×5min at 1-hour effort (~6:20-6:40/mi)" → CORRECT.

5. **The range width** depends on the effort band:
   - Easy: no pace shown (just "easy")
   - Moderate/steady: ±15 sec/mi
   - Threshold: ±10 sec/mi
   - 5K/10K effort: ±10 sec/mi
   - Strides: no pace shown (just "smooth and strong")

6. **For beginners (<30K/wk):** Use sensory cues instead of effort
   terms. "Smooth and quick" instead of "5K effort." "Kid at recess"
   instead of "fast." The beginner doesn't have the feel reference
   points yet.
