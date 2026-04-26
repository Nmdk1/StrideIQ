# Davis Marathon Build Sample — Reference Note

**Source:** John J. Davis, Ph.D. — actual coaching plan for a 2:24 marathon athlete
**Filed:** April 10, 2026
**Relevance:** Plan generator output format, coach communication quality bar, workout description standard, fueling integration, RPE calibration

---

## Why This Matters

This is not a theoretical framework. This is how a Ph.D.-level coach with
published research on SSmax and periodization actually writes training for
a real athlete. Every aspect of this plan — the workout descriptions, the
coaching notes, the flexibility markers, the fueling cues, the difficulty
ratings — sets the quality bar for what StrideIQ's plan generator and AI
coach should produce.

---

## The Two-Week Block

### Week 1 (90-94 miles)

| Day | Workout | Difficulty | Strength |
|-----|---------|-----------|----------|
| Mon | 5-7 mi very easy | — | Pedestal + Hip |
| Tue | AM: 4-5 mi very easy (optional) / PM: 7-9 mi easy w/ 5×25s strides | — | Pedestal + Hip |
| Wed | AM: 9-10 mi easy→moderate w/ 40min of (1min strong, 3min easy) / PM: 5-6 mi easy | — | Pedestal + Hip |
| Thu | 2mi progressive + 4 strides → 3×2mi at 5:08→4:58/mi (10K→8K effort), 3-4min jog recovery → 2mi cooldown | 8-8.5/10 | Pedestal + Hip |
| Fri | 10 mi easy | — | Pedestal + Hip |
| Sat | 10-11 mi easy→moderate | — | Pedestal + Hip |
| Sun | 1.5mi progressive + 4 strides → 7mi at 6:01-5:56 → 6mi at 5:52-5:47 → 5mi at 5:48-5:42 → 2-3mi at 5:36-5:29 (optional) → 0.5mi cooldown | 8.5-9/10 | Pedestal + Hip |

### Week 2 (92-95 miles)

| Day | Workout | Difficulty | Strength |
|-----|---------|-----------|----------|
| Mon | Off or 5-7 mi very easy | — | Hip |
| Tue | 7-9 mi easy w/ 5×25s strides | — | Pedestal + Hip |
| Wed | AM: 4-5 mi easy (optional) / PM: 8-10 mi easy or easy→moderate | — | Pedestal + Hip |
| Thu | AM: 1mi easy + 7mi moderate→strong (6:15-5:52) / PM: 1mi easy + 7mi strong (6:04-5:52) | — | Pedestal + Hip |
| Fri | 10 mi easy w/ 40min of (1min strong every 4min) | — | Pedestal + Hip |
| Sat | AM: 13 mi easy→moderate / PM: 5-6 mi easy | — | Pedestal + Hip |
| Sun | 1.5mi progressive + 4 strides → 4 sets of (3K at 5:30→5:20, 1K at 6:05-6:00, 2K at 5:30→5:20, 1K at 6:05-6:00) → optional 3K at 5:30-5:20 → 0.5mi cooldown | 8.5/10 | Pedestal + Hip |

---

## What the Plan Generator Should Learn From This

### 1. Workout descriptions are specific AND flexible

Not "Threshold Run" — instead:

> "3 × 2 mi at 5:08 → 4:58/mi (controlled 10k → controlled 8k effort)
> w/ 3–4 min easy jog recovery"

Every workout description includes:
- **Exact structure** (reps × distance)
- **Pace range** (not a single number — a range that acknowledges reality)
- **Effort translation** ("controlled 10K → controlled 8K effort")
- **Recovery specification** (3-4 min easy jog, not just "rest")
- **Warm-up and cool-down** (always included, always specific)

The plan generator currently writes titles like "Threshold Run" and
descriptions like "Run at threshold pace." That is inadequate. The
output should match this level of specificity.

### 2. Difficulty ratings anchor expectations

Davis uses a 0-10 difficulty scale:
- Thursday threshold session: 8-8.5/10
- Sunday stepwise long run: 8.5-9/10
- Easy days: unrated (implying <5/10)

**Mapping to StrideIQ:** The `PlannedWorkout` model has no difficulty
rating field. Adding one (integer 1-10, nullable) would allow the plan
generator to communicate expected difficulty. The coach can then compare
actual RPE (from check-in) against expected difficulty to detect
over/under-performance.

### 3. Progressive runs are a distinct workout type

Multiple workouts use "easy progressing to moderate" or "progressive +
strides" as a warm-up before quality work. This is neither easy nor
threshold — it's a controlled build-up that primes the body.

The plan generator should support progressive runs as a first-class
workout type, not just "easy run."

### 4. Stepwise long runs are marathon-specific structure

Sunday W1 is a 4-segment descending-pace long run:
- 7 mi at 6:01-5:56 (easy-moderate)
- 6 mi at 5:52-5:47 (moderate)
- 5 mi at 5:48-5:42 (moderate-strong)
- 2-3 mi at 5:36-5:29 (strong, optional)

This is NOT a steady long run. It's a structured progression that
simulates the marathon's negative-split demand. The plan generator's
Race mode for marathon should include this workout type in the build
and peak phases.

### 5. AM/PM doubles are volume accumulation, not intensity

Thursday W2 has AM/PM strong runs — the coaching note explicitly says
"it's more about accumulating total volume at a strong pace, versus
trying to do each run faster." This is sub-SSmax work: metabolically
sustainable, done in volume.

### 6. Fueling is integrated into the workout prescription

> "Let's do gels at 4-8-12-16 mi into this run"
> "I would take one gel in the middle of each 3K repeat"

Fueling is not an afterthought or a separate system. It's part of the
workout specification. The nutrition product should wire into the plan
generator so that long runs and marathon-specific sessions include
fueling cues from the athlete's fueling shelf.

### 7. The coaching notes are the real product

The notes section is where coaching happens. Look at what Davis does:

- **Explains the why:** "effort level should start at 10K pace and work
  down to ~8K-ish pace by the end"
- **Sets RPE caps:** "don't let it get above 8.5/10 difficulty"
- **Gives permission to underperform:** "Even if the whole thing is
  5:0x, that's ok"
- **Offers training partner coordination:** "same as what [partner] is
  doing for the first three segments, so you can both run together"
- **Connects to previous workouts:** "very similar to the 1K/1K workout
  you just did; the only difference is that the extension is a bit
  longer"
- **Frames the stimulus:** "just sustaining a similar-ish pace for 2x
  or 3x the distance is more than enough to get a new stimulus"
- **Ends with encouragement:** "As always, have fun and keep me posted"

**This is the quality bar for StrideIQ's AI coach.** When the coach
describes a planned workout, it should hit these same notes: why this
workout, what to expect, what's OK if things don't go perfectly, and
how it connects to the training arc.

### 8. Strength is daily maintenance, not a separate session

"Pedestal + Hip" appears every single day. This is 10-15 minutes of
core and hip stability work — not a gym session, not cross-training,
just maintenance. It's prescribed as part of the day, not as an
optional add-on.

**Mapping to StrideIQ:** The plan generator should include daily
strength/mobility prescriptions as part of the workout day, not as
a separate "strength day." For athletes who do Garmin-tracked strength
sessions, these are distinct activities. For maintenance work like
Pedestal + Hip, it's a note on the workout card.

---

## What the AI Coach Should Learn From the Notes

### Communication patterns to adopt:

1. **Reference the previous workout when prescribing the next one:**
   "The pace ranges are adjusted based on the previous workout, though
   they're only a couple of seconds per K faster." The coach has memory.

2. **Anchor difficulty to the athlete's experience:**
   "This workout can be reasonably challenging but don't let it get
   above 8.5/10 difficulty." Not arbitrary — calibrated to what the
   athlete knows an 8.5 feels like.

3. **Give the athlete agency:**
   "Depending on how you feel, you may not be able to get down to the
   fast end of the pace range, which is totally fine."

4. **Name the stimulus, not just the prescription:**
   "Just sustaining a similar-ish pace for 2x or 3x the distance is
   more than enough to get a new stimulus to your body."

5. **Integrate logistics:**
   Training partner coordination, gel timing, track vs road option.
   The coach thinks about the whole experience, not just the physiology.

### Communication patterns to avoid:

- Generic encouragement without specificity
- Prescribing workouts without explaining why
- Rigid pace targets without ranges
- Ignoring the athlete's recent performance context
- Treating fueling, logistics, and warmup as separate concerns

---

## SSmax Mapping of This Training Block

| Workout | SSmax zone | Purpose |
|---------|-----------|---------|
| Easy runs (5-10 mi) | Well below SSmax | Recovery, volume |
| Easy→moderate progressions | Below SSmax | Aerobic development |
| 1min/3min fartlek | Sub-SSmax | Aerobic power at sustainable effort |
| 3×2mi at 10K→8K pace | SSmax boundary | Controlled supra-SSmax stimulus |
| Stepwise long run (7+6+5+3 mi) | Sub-SSmax → approaching SSmax | Marathon-specific endurance |
| AM/PM strong doubles | Sub-SSmax | Volume accumulation at quality |
| 4×(3K+1K+2K+1K) marathon workout | Sub-SSmax | Race-specific pacing and fueling |
| Strides (5×25s) | Above SSmax (neuromuscular) | Speed maintenance |

Notice: NONE of these workouts are "at SSmax." They're all either below
or above it. This confirms Davis's own SSmax article: don't prescribe
at SSmax, prescribe to one side or the other for predictable response.

---

## Action Items for Plan Generator

1. Add `difficulty_rating` (Integer, nullable, 1-10) to `PlannedWorkout`
2. Workout descriptions should include pace RANGES, not single values
3. Effort translations ("controlled 10K effort") alongside pace numbers
4. Recovery specifications as part of the workout segments
5. Progressive warm-up included in structured workout descriptions
6. Fueling cues from athlete's fueling shelf on long runs and race-pace work
7. Coaching notes (the "why") on quality sessions — drawn from the
   athlete's training context, not generic
