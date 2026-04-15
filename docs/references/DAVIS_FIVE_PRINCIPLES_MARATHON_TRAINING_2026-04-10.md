# Davis Five Principles of Marathon Training — Reference Note

**Source:** John J. Davis, Ph.D. — "The Modern Approach to Marathon Training" (article)
**Filed:** April 10, 2026
**Relevance:** Plan generator decision framework, coach model reasoning, race-day briefing philosophy, adaptation/replanning logic

---

## The Four Components of Marathon Fitness

Davis defines marathon performance as the *literal mathematical product*
of four independent physiological components:

```
Marathon speed = VO2max × SSmax × Running Economy × Resilience
```

| Component | What it determines | How to improve it |
|-----------|-------------------|-------------------|
| **VO2max** | Highest aerobic power output | Intervals at 10K-5K pace (110-115% MP) |
| **SSmax** | Highest sustainable fraction of VO2max | Mix of easy mileage, long intervals, fast continuous runs across wide speed range |
| **Running Economy** | Metabolic power → forward motion efficiency | Consistent high-volume training + workouts at high-end aerobic speeds |
| **Resilience** | How much the other three degrade over 42K | Marathon-specific workouts (glycogen depletion resistance, muscle damage resistance, central fatigue resistance) |

**Key insight for StrideIQ:** The plan generator must target ALL FOUR
components, not just one or two. A plan that only does easy mileage +
tempo runs targets SSmax and maybe economy, but neglects VO2max and
resilience entirely. A plan that only does intervals targets VO2max
but neglects everything else.

The four-component model provides the "why" behind every workout the
generator prescribes. Each workout should be traceable to improving
at least one component.

---

## The Five Principles

### Principle 1: Marathon fitness has physiological roots

Your body constrains your performance. Training must improve the four
components above. This is not ideology — it's biology.

**Implication for plan generator:** Every prescribed workout should map
to at least one of: VO2max development, SSmax development, economy
development, or resilience development. The generator should be able
to answer "why this workout?" with a physiological rationale.

**Implication for coach model:** When analyzing a completed workout,
the coach should identify which component(s) the workout developed,
and whether the execution matched the intent.

### Principle 2: Training is specific

General fitness is necessary but not sufficient. You must specialize
for the marathon with long, fast, marathon-pace workouts.

But you can't jump into marathon-specific work — you need to build up
to it. This creates **second-order specificity:**

```
General fitness → supports → Marathon-supportive training
Marathon-supportive training → supports → Marathon-specific training
Marathon-specific training → supports → Race performance
```

And the specificity goes beyond pace — it includes the actual conditions
of your target race: terrain, elevation, weather.

**Implication for plan generator:** The three-phase periodization
(general → supportive → specific) IS the expression of this principle.
Each phase builds the capability to do the next phase's workouts.
Race-specific conditions (Boston hills, London flat, Singapore heat)
should influence specific-phase workout design.

### Principle 3: Every speed has a place in training

The "ladder of support" — an ascending scale of paces where each pace
provides speed and endurance support for its neighbors.

> Programs that focus on a few "magic paces" or training zones leave
> large gaps in the ladder of support. You need training that spans
> the full spectrum of speeds.

The connection between phases and the ladder:
- **General phase:** Full spectrum, emphasizing outer rungs (115%+, 80%-)
- **Supportive phase:** 90-110% MP emphasis
- **Specific phase:** 95-105% MP emphasis

Each phase narrows the focus toward marathon pace while still touching
all speeds. "Training is to ADD, not to REPLACE" — Canova.

**Implication for plan generator:** The generator should NEVER produce
a plan that has gaps in the speed ladder. If there's no work between
easy pace (75%) and marathon pace (100%), that's a broken plan. The
90-95% MP range is the most commonly neglected — and most important
— gap to fill.

### Principle 4: Improvement comes from stress and recovery

A new challenge → adaptation → greater capability. But:
- Too much stress → overwhelm → no adaptation
- Too little stress → insufficient stimulus → no adaptation
- Same stress repeated → diminishing returns → stagnation

**Modulation** (Canova's term): As workouts become longer and faster,
recovery days must increase. Elite marathoners take 5-6 days of easy
running between their most intense specific sessions.

**Extension as progression:** Improvement is NOT just running faster.
It includes:
- Running the same pace for longer
- Moving from 8×1K → 5×1600m → 4×2K at the same pace (more extension)
- Improving float recovery pace while keeping fast segments stable

This yields faster improvement AND lower biomechanical load than just
trying to run each repeat faster.

**Implication for plan generator:** Workout progressions should
primarily increase EXTENSION (distance per segment) and RECOVERY PACE,
not just fast-segment speed. The generator should track week-over-week
progression within each workout category and ensure each step is
reasonable. The current approach of increasing intensity week over week
is the old-school method — the modern method increases the duration
and continuity of work at a stable pace.

### Principle 5: Great marathons don't happen by accident

Race execution — pacing, fueling, course strategy, mental approach —
determines how much of your fitness you actually access on race day.

Race plans must be:
- Carefully considered but flexible
- Adaptable to conditions
- Potentially ignorable if circumstances demand it

> "You must be pragmatic with your training... you can't let ideology
> get in the way of your goal."

**Implication for race-day briefing:** The pre-race briefing should
include pacing strategy (even splits from predicted MP), fueling plan,
weather adjustment, and course features. But it should also communicate
FLEXIBILITY — "this is the plan, but here's how to adapt if..."

---

## The Philosophical Grounding

### "You can't let ideology get in the way of your goal"

Davis explicitly warns against runners who identify as "high-mileage
runners" or "old-school runners" or "scientific runners" and let that
identity constrain their training choices. The plan generator and
coach should be pragmatic, not ideological.

**Implication for coach model:** The coach should never say "you
should do X because that's what good runners do." It should say
"you should do X because your data shows Y, and X targets the
component you need most."

### "There's an art to improvement, centered around learning to run fast without running hard"

This single sentence captures the difference between the modern and
old-school approaches. The alternating-km sessions, the float
recoveries, the regenerative workouts — they're all expressions of
this principle. Running fast (90-105% MP) without running HARD
(without maximal effort) is the skill that marathon training develops.

**Implication for coach model:** Post-workout analysis should note
when an athlete ran "fast but not hard" (controlled effort at a
meaningful pace) versus "hard but not fast" (high RPE at a modest
pace). The former is the goal state for marathon fitness.

### Adaptation and replanning are not failures

> "It's almost certain that you'll have to adapt, adjust, or rework
> your training on the fly... Adapting your training schedule is a
> necessary part of marathon preparations."

**Implication for plan generator:** The replanner is not a failure
mode — it's the expected behavior. Plans should be designed to be
resilient to disruption. When the replanner fires, it should use
these five principles to make decisions, not just rigid rules.

---

## How This Connects to Existing KB

| Existing reference | Connection |
|-------------------|------------|
| SSmax reference | SSmax is Component 2 of the four-component model. Davis's SSmax article defines the boundary; this article defines SSmax's role in the system |
| Coe-style training | Coe's multi-pace variety IS the full-spectrum principle. Coe's circuit periodization IS extension-based progression |
| Davis webinar / 13-week plan | The webinar is the specific workout implementation of these principles. This article is the "why" |
| Davis sample schedule | The sample schedule is the quality bar. These principles are the constraints the generator must satisfy |

---

## What NOT to Do

- Do NOT build a plan generator that targets only one or two of the four
  fitness components. All four must be addressed across the plan.
- Do NOT progress workouts only by increasing pace. Extension and
  recovery-pace improvement are the primary progression levers.
- Do NOT treat the replanner as an error handler. It's a core feature
  that applies these principles to disrupted plans.
- Do NOT let the coach model adopt an ideological stance ("high mileage
  is always better," "threshold is the key workout"). Be pragmatic and
  data-driven.
- Do NOT generate race plans that are rigid. Pre-race briefings should
  communicate flexibility and adaptation strategies alongside targets.
