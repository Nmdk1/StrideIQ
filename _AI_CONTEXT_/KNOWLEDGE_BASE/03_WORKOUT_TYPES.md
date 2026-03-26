# Workout Types — Stress Taxonomy, Sizing Rules, and Spacing Contracts

**Last Updated:** 2026-03-18
**Authority:** Founder (Michael Shaffer) — direct instruction + extracted from training data
**Read with:** `04_RECOVERY.md`, `PLAN_GENERATION_FRAMEWORK.md`, `workouts/variants/long_run_pilot_v1.md`

This document is **machine-ingestible spec and planner input**. Every rule here must be
reflected in generation code. If the code contradicts this document, the code is wrong.

---

## 1. Run Stress Taxonomy

Every run type has a stress level. This drives recovery requirements, adjacency rules,
and the weekly stimulus ledger check. Stress level is not a TSS number — it is a
**recovery cost tier** that determines what can follow it.

| Stress Level | Description | Run Types |
|---|---|---|
| 0 | No load | Rest day, complete off |
| 1 | Active recovery | Recovery run (short, extra easy, < 40 min) |
| 2 | Base aerobic | Easy run (conversational, any length up to ~1:30) |
| 2.5 | Low neuromuscular touch | Easy run with strides or hill sprints (appended only, never the main event) |
| 3 | Medium aerobic load | Medium-long run (1:30–15 mi), Saturday easy before long Sunday |
| 4 | High aerobic load | Long run (1:45+), threshold/tempo session, interval session |
| 5 | Maximum stress | MP long run (marathon pace embedded in a long run), race |

**Rules:**
- Level 4+ requires at least one Level ≤2 day before the next Level 4+ session.
- Level 5 requires at least two Level ≤2 days before the next Level 4+ session.
- Two Level 4+ sessions in the same week is the maximum for any athlete. Three is never allowed.
- Level 2.5 (strides/hills) does **not** count as a quality day. It is a neuromuscular touch.
  However, the weekly stimulus ledger must verify the stride "gear" doesn't duplicate
  a system already heavily loaded that week (see `04_RECOVERY.md`).

---

## 2. Long Run Sizing Rules

### 2a. Time-Based Floor (primary rule)

Long runs are sized in **time first, miles second**. The floor is computed from the
athlete's easy pace and a minimum time threshold. Distance is derived from that.

```
long_run_floor_miles = max(
    minimum_time_hours × easy_pace_min_per_mile / 60,
    2 × (weekly_miles / running_days_per_week)   # "double daily average" for lower mileage
)
```

**Minimum time thresholds by athlete tier:**

| Athlete Type | Long Run Minimum | Mid-Long Minimum |
|---|---|---|
| New / <25 mpw | Double daily average (running days only) | — |
| Building (25–40 mpw) | 1:30 | — |
| Established (40+ mpw) | 1:45 | 1:30 |
| High mileage (60+ mpw) | 2:00 | 1:30–1:45 |

**How to convert:** `miles = pace_min_per_mile × time_hours × 60 / pace_min_per_mile`
→ simpler: `miles = time_in_minutes / easy_pace_min_per_mile`

**Example:**
- Athlete with 9:00/mi easy pace, 55 mpw: long run floor = 1:45 = 105 min / 9 = 11.67 mi
- Athlete with 7:30/mi easy pace, 60 mpw: long run floor = 2:00 = 120 min / 7.5 = 16.0 mi

**Double-daily-average rule (for new/lower mileage runners):**
If a runner averages 5 miles per running day (runs 5 days, 25 mpw), their long run floor
is 2 × 5 = 10 miles. Running days only — rest days excluded from the average.
Formula: `weekly_miles / running_days_per_week × 2`

### 2b. Long Run Ceilings

The ceiling is **distance-based, not time-based.** A 22-mile run at easy pace on hilly
terrain can take 3:40+ and is entirely correct. Time is not a cap — athlete history,
weekly volume, handling of training, and race goals drive the ceiling.
Source: founder instruction 2026-03-18.

| Context | Distance Cap |
|---|---|
| Marathon build peak (standard high-mileage) | 22 miles |
| Marathon build peak (advanced elite only) | 24 miles |
| Non-marathon training in regular training blocks | 15–18 miles |
| Many athletes' practical tolerance | 20 miles |
| 10K training | 18 miles |
| 5K training | 15 miles |
| Half marathon training | 16–18 miles |

**There is no time ceiling.** Do not cut a long run short because it will take 3+ hours.
A 9:00/mi runner doing 22 miles runs 3:18. That is correct.

**How the cap is applied:** `LONG_RUN_MAX_MILES_BY_DISTANCE` in `workout_prescription.py`
sets the distance cap per race goal. The plan uses that to size peak-week long runs.
For athletes who have historically only tolerated 20 miles, their 8–16w history is
the input — not a global time ceiling.

### 2c. Long Run Progression

**Primary source: Michael Shaffer, ["Forget the 10% Rule"](https://mbshaf.substack.com/p/forget-the-10-rule)**
The 10% _weekly volume_ rule has no scientific basis. What matters is the **single-session spike**:
> "If you perform a single run that is more than a 10% increase over the distance of your longest session from the previous 30 days, your risk for lower-extremity injury skyrockets." — Nguyen et al. 2025 (5,200-runner cohort study)

**Rule: First long run of any plan = L30_non_race_max + 1 mile.**
This satisfies the ≤10% single-session spike constraint (e.g., 10 miles → 11 miles = 10% increase).

- Week 1 entry: `L30_non_race_max_miles + 1` (races excluded from L30 — a goal race is not a training long run)
- Build weeks: +2 miles per week (or +3 miles for experienced athletes with strong history)
- Cutback: every 3rd or 4th week, reduce by ~4 miles (targeting 60–70% of prior week's long run)
- Volume-awareness cap: long run ≤ 32% of that week's total mileage (may be overridden by L30 history floor)

---

## 3. Medium-Long Run Rules

The medium-long run (mid-long) is a **distinct workout** — not a long easy run and not
a regular easy day. It has its own sizing contract.

### Sizing

```
mid_long_miles = max(
    1:30 at easy pace,                    # time floor
    0.65–0.75 × same_week_long_run_miles  # proportion of long (illustrative, N=1)
)
mid_long_miles = min(mid_long_miles, 15.0)  # HARD CAP: NEVER above 15 miles
```

**The 15-mile cap is absolute and non-negotiable regardless of weekly volume.**
A runner doing 80 mpw still has a mid-long cap of 15 miles. This is coaching philosophy,
not a safety concern — the mid-long is durability, not the peak load session.

### Placement

- Mid-long is typically **mid-week** (Tuesday in the founder's schedule).
- Never the day before a long run (Saturday before Sunday long must be an **easy** run,
  never a medium-long).
- Best separated from the long run by at least 3 days.

### When to use vs standard easy

- Athletes under 40 mpw: mid-long is optional; standard easy days suffice.
- Athletes 40–60 mpw: mid-long is a useful weekly anchor, typically 1–2× per week.
- Athletes 60+ mpw: mid-long is a weekly structural session alongside the long run.

---

## 4. Weekly Stimulus Ledger Contract

Before selecting any workout or neuromuscular touch for a given day, the planner must
resolve the **weekly stimulus ledger** — a record of what quality systems were already
trained that week.

**Systems tracked:**
- `threshold` — lactate threshold work (tempo, cruise intervals, continuous threshold)
- `vo2` — interval sessions, repetitions
- `mp` — marathon pace work (in long runs or standalone)
- `hmp` — half marathon pace work
- `neuromuscular_5k` — 5K-rhythm strides or rep-pace sessions
- `neuromuscular_10k` — 10K-rhythm strides or threshold-adjacent reps
- `neuromuscular_hm` — half marathon rhythm strides

**Rules:**
1. A system already heavily loaded (full quality session) must not also get a neuromuscular
   touch on an easy day that same week. (Example: heavy 5K intervals → no 5K-gear strides.)
2. A system with no stimulus that week is a candidate for a light neuromuscular touch.
   (Example: no threshold work this week → HM-gear strides on an easy day is appropriate.)
3. Two systems cannot both receive full quality sessions in the same week unless the
   athlete is high mileage (70+ mpw) and the sessions are separated by 48+ hours.

**Implementation note:** This is the input to the selection matrix described in
`workouts/variants/easy_pilot_v1.md` (Deterministic selection logic). Currently
qualitative; future Phase 2 will compute it from the week's scheduled workout types.

---

## 5. Quality Session Spacing

| After this session | Minimum before next Level 4+ | Notes |
|---|---|---|
| Threshold / tempo | 1 easy/recovery day | Can be strides-easy, not recovery-only |
| Interval / repetitions | 1–2 easy/recovery days | N=1; older athletes or high cumulative fatigue → 2 |
| Long run (easy) | 1 easy/recovery day | Monday after Sunday long is the anchor |
| MP long run | 2 easy/recovery days | Major stressor; several easy days before AND after |
| Race | 3–7 easy/recovery days | N=1 by distance |

**Hard rules:**
- Saturday before Sunday long run: **always easy**. Never medium-long, never quality.
- Threshold week: long run is easy (no MP work).
- MP long week: no threshold work that week.
- Never: quality + MP long in the same week (for athletes under 70 mpw).

---

## 6. Interval Timing by Phase (Michael-specific, generalizable)

This is captured from Michael's training data and should be used as a general principle:

| Phase | Interval status | Reason |
|---|---|---|
| Base / pre-build | Safe, productive | Low cumulative fatigue; legs fresh |
| Mid-build (high volume, MP stacking) | High risk | Cumulative fatigue amplifies injury risk |
| Peak / specific | Race-specific sharpening only | Short, sharp; not VO2 blocks |

**The principle:** Intervals are not inherently dangerous. Timing relative to cumulative
fatigue is what matters. An athlete at 65+ mpw with 3 weeks of MP work already done
should not be adding interval sessions — not because intervals are bad but because the
recovery debt is already high. An athlete in base phase at 40 mpw with fresh legs can
and should do interval work.

**For plan generation:** Interval sessions belong in base/pre-build for most athletes.
In build and peak phases, threshold and MP work carry the quality load. The constraint-aware
planner's `QUALITY_FOCUS` by distance (intervals for 5K/10K, threshold/MP for half/marathon)
is the implementation of this principle.

---

## 7. Session Type Quick Reference

| Session Type | Stress Level | Floor | Cap | System Trained |
|---|---|---|---|---|
| Rest | 0 | — | — | Recovery |
| Recovery run | 1 | 20 min | 40 min | Active recovery |
| Easy run | 2 | 20 min | 1:30 standard | Base aerobic |
| Easy + strides | 2.5 | same as easy | same + 6×20s | Neuromuscular touch |
| Easy + hills | 2.5 | same as easy | same + 8×10s | Neuromuscular/economy |
| Medium-long | 3 | 1:30 | **15 miles** | Aerobic durability |
| Long run (easy) | 4 | 1:45 (40+ mpw) | 22 mi marathon / 18 mi non-marathon | Aerobic endurance |
| Threshold | 4 | — | 10% weekly volume | Lactate threshold |
| Intervals | 4 | — | 8% weekly volume | VO2 / speed |
| MP long run | 5 | — | 20% weekly volume or 18 mi | Race-specific endurance |
| Race | 5 | — | — | Race |
