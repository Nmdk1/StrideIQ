# Phase 5 Fix: first_marathon Long Run Progression

**Date:** April 10, 2026
**Status:** BLOCKING — Phase 5 cannot be marked complete until this is resolved
**Affected profile:** `first_marathon`

---

## The Problem

The `first_marathon` synthetic profile produces a 20-week marathon plan
where the long run peaks at 15km (9.3 miles). This athlete is preparing
for a 42.2km (26.2mi) race and will never run farther than 9.3 miles
in training. That is dangerous and disqualifying for any marathon plan.

Every credible marathon plan — Hal Higdon Novice, Pfitzinger, Daniels,
Hanson, our own V1 — peaks the long run at 30-34km (18-21 miles). A
15km ceiling means the athlete hits the wall at mile 14 on race day
having never experienced that distance in training. The long run is
where resilience, fueling practice, and mental preparation happen.
Without it, the plan is irresponsible.

## Root Cause (suspected)

The `l30_max_easy_long_mi` from `build_load_context()` is being applied
as a **hard ceiling across all weeks** rather than as a **Week 1 cap**.

The correct behavior:
- **Week 1 long run:** Capped by `l30_max_easy_long_mi` — don't
  prescribe farther than the athlete has recently run
- **Weeks 2-N:** Progression takes over, building from the Week 1
  value toward a race-appropriate peak
- **Peak long run:** Determined by the race distance, NOT by L30

The `compute_athlete_long_run_floor()` from the quality gate provides
the FLOOR (minimum long run), not the ceiling. L30 provides the
STARTING POINT, not the maximum. These are different constraints
applied at different points.

## The Fix

### 1. Separate starting cap from race-appropriate peak

```
Week 1 long run distance = min(l30_max_easy_long_mi, tier_week_1_cap)
Peak long run distance   = race_peak_table[race_distance]
```

Race peak table (non-negotiable minimums):

| Race Distance | Peak Long Run (mi) | Peak Long Run (km) |
|---------------|--------------------|--------------------|
| 5K            | 8-10               | 13-16              |
| 10K           | 10-13              | 16-21              |
| Half Marathon | 13-16              | 21-26              |
| Marathon      | 18-21              | 29-34              |
| 50K           | 20-24              | 32-39              |
| 50mi+         | 24-30              | 39-48              |

These are peak values during the specific phase. The exact value
within the range depends on experience level (beginners toward the
lower end, experienced toward the upper).

### 2. Build a progression curve from start to peak

The long run should follow a progression curve from Week 1's
starting value to the peak, with cutback weeks:

```
progress = week_in_plan / (total_weeks - taper_weeks)
long_run_km = start_km + (peak_km - start_km) * sqrt(progress)
```

Apply cutback modulation per fingerprint's `cutback_frequency`.
During cutback weeks, long run drops to ~70% of the previous
week's value.

### 3. Never let L30 cap the progression ceiling

L30 answers: "What has this athlete done recently?"
The race peak answers: "What must this athlete do to be ready?"

If L30 is 10 miles and the race requires a 20-mile long run,
the plan builds from 10 to 20 over the available weeks. That's
what the plan is FOR.

The only constraint on the ceiling is the rate of progression —
don't increase the long run by more than ~10% per week (standard
overload principle). A 20-week plan has plenty of runway to build
from 10 miles to 20 miles at 10% per week.

## Existing V1 Reference

V1's Couch-to-10K plan (founder-built) in `n1_engine.py` lines
1182-1225 shows the founder's own beginner progression:

```
Week 1-2: Walk 1mi, Run 1mi, Walk 1mi → Long: Run 3mi
Week 3:   Walk 1mi, Run 2mi         → Long: Run 4mi
Week 4-6: Run 3mi                   → Long: Run 6mi
Week 7-9: Run 4mi                   → Long: Run 8mi
Week 10:  Taper (3mi easy) + Race
```

This builds from 3 miles to 8 miles over 9 weeks. A 20-week
first marathon plan starting post-10K (from 8 miles) has 18+
weeks to build from 8 to 20 miles. That's ~0.67 miles/week —
extremely conservative and safe.

## Verification

After the fix, re-run the `first_marathon` profile and provide
the week-by-week long run progression:

```
Week  1: [distance]
Week  2: [distance]
...
Week 20: [distance]
```

The peak long run (during specific phase, weeks 16-18) must be
between 29-34km (18-21 miles). If it's below 29km, the fix is
incomplete.

Also re-run ALL 15 profiles to confirm no regressions. The other
13 passing profiles must still pass.

## Quality Gate Addition

Add a new quality gate check:

```
For any Race mode plan where race_distance >= half_marathon:
  assert max(long_run_distances) >= RACE_PEAK_TABLE[race_distance].min
```

This ensures no marathon or longer plan can ever pass the gate
with a long run that doesn't reach race-appropriate distance.

---

## Other Phase 5 Status

- `established_marathon`: APPROVED
- `onramp_brand_new`: APPROVED
- `advanced_50k`: APPROVED
- `first_marathon`: BLOCKED (this fix)

Phase 5 is complete when `first_marathon` shows a 29-34km peak
long run and all 15 profiles pass all gates including the new one.
