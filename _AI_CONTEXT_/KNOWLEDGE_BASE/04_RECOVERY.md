# Recovery Rules, Spacing Contracts, and Day Weighting

**Last Updated:** 2026-03-18
**Authority:** Founder (Michael Shaffer) + implemented spec (`PLAN_COACHED_OUTPUT_AND_LOAD_CONTRACT.md`)
**Read with:** `03_WORKOUT_TYPES.md`, `PLAN_GENERATION_FRAMEWORK.md`

---

## 1. Core Principle

Recovery is training. Adaptation happens during rest, not during the run.
Under-recovery = under-adaptation and injury risk — especially for masters athletes
and any athlete accumulating high cumulative fatigue.

The planner must model recovery cost explicitly. "Hard day → easy day" is the
minimum contract. The rules below define what that means precisely.

---

## 2. Recovery Cost by Session Type

Each session type carries a recovery cost measured in **minimum easy days required
before the next Level 4+ session**. See `03_WORKOUT_TYPES.md` for stress levels.

| Session | Recovery Cost | Required After |
|---|---|---|
| Easy run | Low | No constraint on next session |
| Easy + strides/hills | Low | No constraint; just avoid redundant stimulus gear |
| Medium-long (easy) | Moderate | 1 easy day before next quality or long |
| Long run (easy, < 2:00) | Moderate | 1 easy/recovery day |
| Long run (easy, 2:00+) | High | 1–2 easy/recovery days |
| Threshold session | High | 1 easy day minimum |
| Interval session | High | 1–2 easy days (N=1; more for masters / high-fatigue) |
| MP long run | Very High | 2 easy days minimum (several easy before AND after) |
| Race | Very High | 3–7 days easy (N=1 by distance and effort) |

**Key distinction:** For masters athletes and athletes under cumulative fatigue load
(mid-build, high mileage, stacked MP work), the minimum shifts up one level.
A threshold session that needs 1 easy day for a 30-year-old may need 2 for a
57-year-old mid-build. Use training history signals, not age alone.

---

## 3. Hard Adjacency Rules (never negotiate these)

These are absolute. No volume contract or tier override removes them.

1. **Saturday before Sunday long run is always easy.** Never medium-long, never quality,
   never strides on a hard Saturday. The long run needs fresh legs.

2. **MP long run weeks: no threshold work.** An MP long run and a threshold session
   in the same week is too much quality. One or the other. (Exception: very high
   mileage athletes, 70+ mpw, with explicit recovery days on each side.)

3. **Threshold weeks: long run is easy.** When the week has a threshold session,
   the long run is an easy long — no MP or HMP segments.

4. **Never 3 quality sessions in one week.** Hard limit for all athletes regardless
   of mileage. A "quality session" is any Level 4+ session.

5. **Intervals belong in base phase only** (for most athletes). Not in mid-build,
   not in peak. The exception is 5K/10K-specific sharpening in the peak phase,
   which is race-specific, short, and not VO2 block training.

---

## 4. Weighted Easy Day Volume (P2 Contract)

Implemented in `PlanGenerator._apply_weighted_easy_volume_fill` in `generator.py`.
This is the adjacency weighting system: easy day volume is redistributed based on
what is adjacent to it in the same week.

**Multipliers:**

| Easy day position | Multiplier | Effect |
|---|---|---|
| Day after quality session | 0.7 | Lighter easy day — body is recovering |
| Day before long run | 0.8 | Lighter easy day — saving legs for long |
| Both (after quality AND before long) | 0.56 (0.7 × 0.8) | Significant reduction |
| Standalone easy (no quality adjacent) | 1.2 | Fuller easy day — room to absorb miles |

**Applies to:** `quality` stems (threshold, intervals, mp_touch, long_mp, long_hmp)
and `long` stems (`long`, `long_mp`, `long_hmp`).

**Logic:** Total weekly easy mileage target stays constant. The weights determine
*how those miles are distributed across easy days*, not how many total easy miles.
Days after hard work get fewer; standalone easy days get more.

**This must be kept synchronized with `03_WORKOUT_TYPES.md` stress levels.** If a
new workout type is added at Level 4+, it must be added to the quality set for
the 0.7 post-quality weight.

---

## 5. Weekly Structure Templates

These are the two valid weekly structures. The planner must use one of them each week,
chosen based on whether the week contains MP work in the long run.

### Structure A — Quality midweek + easy long

Use when: threshold or interval session is the quality session for the week.

```
Sunday:    Long run (EASY — no MP, no HMP)
Monday:    Rest / cross-train
Tuesday:   Medium-long easy OR easy (N=1)
Wednesday: Easy
Thursday:  QUALITY (threshold, intervals, or hills)
Friday:    Easy (lighter — after quality)
Saturday:  Easy (lighter — before long)
```

### Structure B — Easy week + MP long run

Use when: marathon pace work is embedded in the long run.

```
Sunday:    Long run WITH MP segments
Monday:    Rest / cross-train (recovery from LR)
Tuesday:   Easy (recovery)
Wednesday: Easy
Thursday:  Easy + strides (no threshold)
Friday:    Easy
Saturday:  Easy (before long)
```

**The rule:** If quality during the week → long run is easy (Structure A).
If MP in long run → no threshold that week (Structure B).
Alternate between A and B in build and peak phases.

**Michael's formula (verified from Nov 2025 PR build):**
> If there are two intense sessions during the week, the long run is easy.
> If only one intense session, the long run can also have a workout.
> Never three quality days.

---

## 6. Cutback Weeks

Cutback weeks reset recovery debt that accumulates across a mesocycle.

| Athlete | Cutback frequency | Volume reduction |
|---|---|---|
| General | Every 4th week | 60–70% of prior week's volume |
| Masters / injury history | Every 3rd week | 65–70% |
| High cumulative fatigue signal | As soon as detected | 60% |

**Long run on cutback week:** 60–70% of prior week's long run.
**Quality on cutback week:** Light or none. Cutback is recovery, not performance.

---

## 7. Cumulative Fatigue Model

This is the single most important concept for plan quality and injury prevention.

The fatigue accumulated **before** the long run IS part of the training stimulus.
A 16-mile long run after 4 days of consistent running is more race-specific than
a 20-mile long run after 2 days of nothing. Strategic weekly volume matters more
than single heroic sessions.

**Danger zone:** When cumulative fatigue is high (mid-build, 60+ mpw, MP work
already stacked), introducing new neuromuscular stimulus (intervals, repetitions)
dramatically increases injury risk. This is the pattern behind Michael's bone injury:
intervals introduced at week 9 of a 65-70 mpw build, on top of two 18-mile MP long
runs already in the legs.

**Planner implication:** The plan generator must track cumulative quality sessions
over the prior 3–4 weeks (not just the current week) before prescribing interval work.
High recent quality density → suppress intervals, favor threshold and easy volume.

---

## 8. Age and Individual Recovery

Age is a variable, not a limiter. Use individual data first.

When individual history is available:
- Track actual recovery patterns (how many days between quality sessions historically)
- Track injury timing relative to cumulative load
- Override any age-based default with the observed pattern

When no history is available:
- Under 50: standard spacing (one easy day after threshold/intervals)
- 50+: add one extra easy day as default, then update from observed patterns
- This default is explicitly overridden by data — it is not a permanent constraint

**From Michael's data:** At 57, can do 2–3 hard days in a row at certain points,
but cannot combine weekly intensity + hard long run simultaneously. The individual
pattern matters more than the age rule.
