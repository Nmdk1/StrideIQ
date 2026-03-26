# Session Handoff — 2026-03-26
## New Agent Start Here

**Written by:** Outgoing builder agent, end of session 2026-03-26  
**Situation:** Plan generation is broken. Data infrastructure is fixed. A new agent needs to fix plan generation from its core. This document tells you everything you need to know to start working.

---

## STOP. Read These First. In This Order.

Before you touch a single file or write a single line of code, read these documents. They are not optional. Each one will prevent you from building the wrong thing.

| Order | File | What It Gives You |
|-------|------|-------------------|
| 1 | `docs/FOUNDER_OPERATING_CONTRACT.md` | How to work with this founder. The rules that keep you alive. Read every word. |
| 2 | `docs/PRODUCT_MANIFESTO.md` | What this product is and why it exists. "The chart makes you open the app. The intelligence makes you trust it. The voice makes you need it." |
| 3 | `docs/PRODUCT_STRATEGY_2026-03-03.md` | The 10 priority-ranked product concepts. The Pre-Race Fingerprint. The Proactive Coach. Every feature flows from the correlation engine producing true, specific, actionable findings about a single human. |
| 4 | `docs/SESSION_HANDOFF_2026-03-11_NEW_BUILDER_ONBOARDING.md` | Full codebase architecture — stack, services, data model, how sync works, how CI works, how to deploy. Written by a previous agent after ~15 sessions. Still accurate. |
| 5 | `docs/TRAINING_PLAN_REBUILD_PLAN.md` | The phase summary table. T0-T5 has been executed. What passed, what failed, what's gated. |
| 6 | `_AI_CONTEXT_/KNOWLEDGE_BASE/PLAN_GENERATION_FRAMEWORK.md` | The governing rules for plan generation. This is what the code is SUPPOSED to implement. Read it before you look at any code. |
| 7 | `_AI_CONTEXT_/KNOWLEDGE_BASE/03_WORKOUT_TYPES.md` | Long run progression rules. Spacing contracts. Quality session sizing. The source of truth for prescription logic. |
| 8 | `docs/PLAN_GENERATION_HANDOFF_2026-03-26.md` | **Your primary technical brief.** Exact current state, what's broken, what needs to be built, the specific files, and what a correct plan looks like. |

---

## Who You Are Working With

- **Founder:** Michael Shaffer, 57 years old, competitive runner, ran in college, still racing. Deep domain expertise in running science and coaching. The athlete in every test scenario.
- **Communication style:** Direct. Short messages carry full weight. "go" means proceed. "no" means stop. He will not explain himself twice.
- **Non-negotiable:** Do not start coding until he tells you to. Do not claim success without evidence. Do not `git add -A`. Do not re-propose rejected decisions.
- **He is the author of this article (required reading):** https://mbshaf.substack.com/p/forget-the-10-rule — it is in the knowledge base and governs mileage progression rules. The 10% rule is explicitly rejected. Do not reference it.

---

## What Just Happened (This Session)

### What Was Fixed (Working, Deployed, CI Green)

**Data Integrity — these are real fixes that matter:**
- Garmin/Strava duplicate activities were being double-counted. Every run synced from both providers with a 5-hour delay exceeded the old 1-hour dedup window. 164 duplicate pairs were marked. `TIME_WINDOW_S` expanded from 1h to 8h in `services/activity_deduplication.py`.
- Fitness bank was ignoring `is_duplicate` flags and using proximity-based fallback instead. Changed to `require_trusted_duplicate_flags=True` in `services/fitness_bank.py`.
- `_find_best_race()` was using recency-weighted selection — a March 10-mile at RPI 48.66 was beating a December 10K at RPI 53.18 because it was 19 days vs 103 days old. Fixed to use `max(r.rpi * r.confidence)` with no recency decay.
- Post-marathon quality sessions penalty (`-1.5 RPI`) now suppressed within 35 days of a marathon. Not doing intervals for 4 weeks after a marathon is correct behavior, not a fitness red flag.
- Race exclusion from long run floor: activities >24mi excluded from `l30_max_easy_long_mi` calculation (untagged marathons were inflating the floor).
- Plan start normalized to Monday. Horizon weeks uses ceiling division. Workout dates fixed in save function. Duplicate dates safety net added.

**What the fitness bank looks like now (correct values):**
```
current_long_run_miles:   13.0mi
current_weekly_miles:     33.1 mpw  (post-marathon recovery)
peak_weekly_miles:        68.0 mpw  (post-dedup, was falsely 103.5)
best_rpi:                 53.18     (December 10K, was 48.66 from wrong race)
experience_level:         elite
```

**Three code changes are NOT yet deployed** (in `fitness_bank.py` and `constraint_aware_planner.py` — `require_trusted_duplicate_flags`, `_find_best_race`, quality penalty skip). They need to be committed with tests and pushed before the fitness bank fully reflects the fixes above.

---

### What Is Broken (Your Job)

**The plan generator produces generic template plans, not N=1 athlete plans.**

A 65 MPW elite athlete with a 39:14 10K PR just got this plan for a 10K race 7 weeks out:
```
Goal time predicted: 44 minutes  (correct: ~39-41)
Week 1 long run: 14mi            (acceptable)
Week 2 long run: 10mi            (WRONG — drops below 13mi floor)
Week 3 long run: 11mi            (WRONG)
Week 4 long run: 11mi            (WRONG — not building)
Week 5 long run: 8mi             (WRONG — long run day after tune-up race)
Week 6: race day shows easy_strides, day after race shows long run  (CATASTROPHIC)
```

**Root cause:** `WorkoutScaler._scale_long_run()` computes from population-average constants (`peak_long_miles(goal, tier)`, `standard_start_long_miles(goal, tier)`) interpolated linearly. Athlete history enters only as soft override constraints on top. The system builds from population baseline and clips it to history, when it must do the inverse: build from athlete history, use population as guardrail.

**The prescription logic that must replace the current template approach:**
```
LONG RUN:
  Week 1 = l30_max_non_race_miles + 1    (13 + 1 = 14mi for this athlete)
  Week N = Week N-1 + 2mi                (not cutback weeks)
  Cutback week = previous_peak * 0.75    (every 3rd or 4th week)
  10K ceiling = min(18, peak_weekly * 0.28)

VOLUME:
  Week 1 = current_weekly_miles * 1.1   (or l30_median — whichever is higher)
  Target = user-specified peak (65 mpw)
  Ramp = linear from start to peak, no percentage cap, tier-based step ceiling (6-8mi/wk for HIGH/ELITE)

PACES:
  All paces derived from rpi_calculator.calculate_training_paces(bank.best_rpi)
  best_rpi = 53.18 (max confidence-adjusted RPI from valid races, last 24 months)

QUALITY WORK:
  Freeze quality escalation during weeks where volume is increasing (no simultaneous ramp)
  Quality volume = 8-12% of weekly volume

RACE/TUNE-UP SCHEDULING:
  Race day = race workout
  Day before race = pre_race (easy 4-6mi + strides)
  Day after race = rest (not a long run)
  Day after tune-up = easy recovery (not a long run)
```

Full technical detail: `docs/PLAN_GENERATION_HANDOFF_2026-03-26.md`

---

## What a Correct Plan Looks Like for the Test Athlete

**Input:** Michael Shaffer, 10K on May 2 2026, 5K tune-up April 25, peak 65 mpw

```
Week  Volume  Long   Structure
1     40      14mi   Easy base + strides. No quality yet.
2     48      16mi   Easy base + strides. No quality yet.
3     56      18mi   First threshold session. Volume still building.
4     40 CUT  14mi   Cutback week. Single quality session.
5     62      17mi   Peak week. Two quality sessions.
6     TAPER   --     Tune-up 5K Saturday April 25. Sunday rest. ~35 mpw.
7     RACE    --     10K Saturday May 2. Sunday rest. ~20 mpw.

Goal time: 39:30-41:00 (from RPI 53.18, conservatively discounted ~2%)
Easy pace: 8:00-8:30/mi
Threshold pace: 6:35-6:45/mi
Race pace: 6:18-6:22/mi
```

If the plan generator produces this output for this athlete, plan generation is working. That is the test.

---

## Production Environment

```
Server: root@187.124.67.153
Repo: /opt/strideiq/repo
Deploy API: cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build api
Run script in container: docker exec strideiq_api bash -c 'PYTHONPATH=/app python3 /tmp/script.py'
Flush fitness bank cache: docker exec strideiq_redis redis-cli DEL 'fitness_bank:4368ec7f-c30d-45ff-a6ee-58db7716be24'
Auth token: see .cursor/rules/production-deployment.mdc
```

CI: GitHub Actions. Every push to `main` runs 10 jobs. Commits touching `plan_framework/` or `plan_generation` runtime code require `P0-GATE: GREEN` in the commit message or CI fails.

---

## Key Files for Plan Generation

```
services/constraint_aware_planner.py    Main orchestrator. generate_plan() method.
services/plan_framework/workout_scaler.py  Sizes every workout. _scale_long_run() is the core problem.
services/plan_framework/volume_tiers.py  Volume progression (fixed this session — no 10% cap).
services/plan_framework/phase_builder.py  Assigns phases and per-phase modifiers.
services/plan_framework/load_context.py  Computes L30 baselines from athlete history. Working correctly.
services/fitness_bank.py                Athlete fitness profile. Mostly fixed this session.
services/plan_quality_gate.py           Validates plan passes rules. Does not validate coaching quality.
routers/plan_generation.py              API handler and DB save function.
```

---

## CI and Commit Discipline

- Work directly on `main`. No branches. No PRs.
- Scoped commits only — never `git add -A`. Show the file list before committing.
- Paste actual test output. Do not claim tests pass without evidence.
- Check CI with `gh run list --branch main --limit 1` and `gh run view <id> --json jobs`.
- Do not deploy until CI is green.
- When CI fails, read the logs with `gh run view <id> --log-failed`.

---

## The One Thing This Founder Has Said Most Often

> "You are trying to create homogenous population driven plans for individuals. If they wanted that, they could just download a template from the internet. Why come to us? What good is all the work we have done building correlation engines, fingerprints, coaching intelligence, if we aren't using it to coach?"

Every plan must use the athlete's actual history — their long runs, their paces, their peak volume — as the starting point. Population constants are guardrails. Athlete data is the input.
