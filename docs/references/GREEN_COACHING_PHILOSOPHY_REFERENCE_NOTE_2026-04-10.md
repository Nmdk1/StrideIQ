# Jon Green Coaching Philosophy — Reference Note

**Source:** Multiple interviews, Verde Track Club, Molly Seidel coaching record
**Filed:** April 10, 2026
**Relevance:** Replanner philosophy, coach model personality, adaptive training, amateur athlete respect, psychological load management

---

## Background

Jon Green coached Molly Seidel to an Olympic marathon bronze medal
(Tokyo 2020) with zero coaching experience, zero coaching credentials,
and never having run a marathon himself. Former Georgetown All-American
(5K: 13:45, 10K: 29:06). Injury-plagued career (Achilles, IT band from
crossing midline) led to coaching. Founded Verde Track Club in Flagstaff.

## Core Philosophy

### "Plans Written in Pencil"

Green does not believe in rigid training schedules. Everything is
"written in pencil." He relies on daily athlete feedback and will
frequently alter, postpone, or cancel a workout right before it begins
if the athlete feels off or fatigued.

**Implication for StrideIQ:** The replanner is not a failure mode — it
IS the coaching model. Green's approach validates the architectural
decision to treat plan adaptation as a core feature. The generator
produces the plan; the replanner IS the coach.

### The "Two Gas Tanks" Theory

Athletes have both a physical gas tank and a mental gas tank. Life
stressors — breakups, moving, work pressure — drain the mental tank
and elevate cortisol, which ruins physical workouts.

**Implication for coach model:** The coach should ask about life context,
not just training data. "How are you feeling outside of running?" is a
legitimate coaching question. The mindset checkin exists for this —
the coach model should reference it.

### Consistency and Volume Over "Flashy" Workouts

Green is a high-volume coach who keeps intensities slightly lower so
athletes don't get "bogged down" or injured. He warns against "flashy"
workouts that look great on social media but leave the athlete too
depleted for consistent weekly mileage.

Seidel: 130 miles/week with very few workouts faster than 10K pace.

**Implication for plan generator:** The generator should resist the
temptation to produce "impressive-looking" workouts. A plan with 3
hard sessions per week looks ambitious but may prevent the athlete
from maintaining consistent volume. Better: 1-2 quality sessions with
the rest at easy/moderate pace. The plan that LOOKS boring but the
athlete can COMPLETE is better than the plan that looks exciting but
the athlete abandons.

### Speed Limits on Progression Runs

Green sets strict speed limits — athletes must not push past 95-97%
of their ability in practice. The ceiling prevents the accumulation
of fatigue that erodes consistency.

**Implication for plan generator:** Quality sessions should have a
CEILING, not just a target. "Threshold at 6:45/mi — do NOT go faster
than 6:35." The ceiling is as important as the floor. The current
generator prescribes targets but not ceilings.

### Double Thresholds — Controlled

Influenced by Mike Smith (NAU), Green uses double threshold days
(e.g., 5:20/mi repeats AM, slightly faster mile repeats PM) to
accumulate high aerobic volume without the central fatigue of a single
massive session.

This aligns with the Norwegian model's clustering principle but with
Green's characteristic restraint — the sessions are controlled, not
maximal.

### Amateur Coaching Without Elitism

Green coaches elite professionals AND everyday amateurs with the same
system. He accommodates low-mileage runners, 3-4 day/week runners,
parents, workers. He applies elite-level knowledge without judgment
or condescension.

**Implication for StrideIQ product:** This is exactly what StrideIQ
must be. The same engine that produces a plan for a 2:30 marathoner
produces a plan for a 4:30 marathoner. The principles are identical.
The volumes and paces scale. The respect is the same.

---

## What This Means for StrideIQ

Green's approach validates three architectural decisions:

1. **The replanner is the coach.** Plans are written in pencil. The
   system that ADAPTS the plan is more important than the system that
   GENERATES it.

2. **The coach model must have personality.** Green's athletes trust
   him because he's human, relatable, and honest. The coach model
   should not sound like a textbook. It should sound like a person
   who cares.

3. **Ceiling enforcement matters.** Prescribing "6:45/mi threshold"
   without a ceiling means the motivated athlete runs 6:30 and
   accumulates unnecessary biomechanical load. The generator should
   prescribe ranges with explicit ceilings: "6:45-6:50/mi. Do not
   go faster."

---

## What NOT to Do

- Do NOT produce plans that look "impressive" at the cost of
  consistency. A boring plan the athlete completes beats an exciting
  plan the athlete abandons.
- Do NOT ignore psychological load. The coach model should reference
  life context when available (mindset checkin data).
- Do NOT treat amateur athletes differently in principle — only in
  volume and pace. The same periodization, the same progression logic,
  the same respect.
