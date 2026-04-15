# New Agent Onboarding — StrideIQ Plan Generation Rebuild

**Date:** March 28, 2026
**Purpose:** Everything a new builder agent needs to understand the StrideIQ codebase, the current state of plan generation, and how to avoid the mistakes of the last two sessions.
**Written by:** Outgoing agent after a failed plan generation session.

---

## Part 1: How This Founder Works

**Read `docs/FOUNDER_OPERATING_CONTRACT.md` before your first tool call. No exceptions.**

The four things that will get you killed instantly:

1. **Coding before you're told to code.** When the founder says "discuss," they mean discuss. They have an advisor agent. They will refine requirements through multiple rounds. If you receive a feature description and start writing code, you will be replaced.

2. **Claiming results without evidence.** "All tests pass" without pasted output is not acceptable. "Production is healthy" without logs is not acceptable. Paste the evidence. Every time.

3. **`git add -A`.** Never. Scoped commits only. Show `git diff --name-only --cached` before every commit.

4. **Making up rules instead of reading the knowledge base.** This is what killed the last two sessions. The knowledge base at `_AI_CONTEXT_/KNOWLEDGE_BASE/` contains the governing rules for plan generation. If you cannot cite the specific KB document that defines the rule you're implementing, you are inventing it. Invented rules produce plans that pass tests and fail athletes.

**The founder's workflow:**
```
discuss → scope → plan → test design → build → evidence → commit → deploy → verify
```

**The founder:**
- Michael Shaffer, 57 years old. Ran in college, still racing competitively. Deep domain expertise in running science and coaching.
- Solo developer. No team. No PRs. Push directly to `main`.
- Direct communicator. Short messages carry full weight. "go" = proceed. "no" = stop. He will not explain himself twice.
- He has an advisor agent for architecture and risk reviews. When he returns with advisor output, treat it as refined requirements.
- Author of this article (required reading, it's in the KB): https://mbshaf.substack.com/p/forget-the-10-rule — the 10% rule is explicitly rejected. Do not reference it.

---

## Part 2: Mandatory Reading Order

### VISION DOCUMENTS — Read ALL before proposing ANYTHING

| # | Document | What It Gives You |
|---|----------|-------------------|
| 1 | `docs/FOUNDER_OPERATING_CONTRACT.md` | How to work. Non-negotiable rules. Anti-patterns that killed previous agents. |
| 2 | `docs/PRODUCT_MANIFESTO.md` | The soul. "The chart makes you open the app. The intelligence makes you trust it. The voice makes you need it." StrideIQ gives an athlete's body a voice — 150+ intelligence tools studying YOU. |
| 3 | `docs/PRODUCT_STRATEGY_2026-03-03.md` | The moat. 16 priority-ranked product concepts. Pre-Race Fingerprint, Proactive Coach, Injury Fingerprint, Personal Operating Manual. Every feature flows from the correlation engine. |
| 4 | `docs/specs/CORRELATION_ENGINE_ROADMAP.md` | The 12-layer engine roadmap. Layers 1-4 are built. Know what exists before proposing what to build next. |
| 5 | `docs/FINGERPRINT_VISIBILITY_ROADMAP.md` | How built backend intelligence connects to product strategy. |
| 6 | `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` | How every screen should feel. What's agreed. **What's been rejected** — do NOT re-propose rejected decisions. |

### KNOWLEDGE BASE — Read BEFORE touching plan generation code

This is where the last two agents failed. They skipped these and invented their own rules.

| # | Document | What It Gives You |
|---|----------|-------------------|
| 7 | `_AI_CONTEXT_/KNOWLEDGE_BASE/00_GOVERNING_PRINCIPLE.md` | Philosophical foundation of the coaching system. |
| 8 | `_AI_CONTEXT_/KNOWLEDGE_BASE/01_PHILOSOPHY.md` | Training philosophy — how the system thinks about coaching. |
| 9 | `_AI_CONTEXT_/KNOWLEDGE_BASE/PLAN_GENERATION_FRAMEWORK.md` | **THE governing rules for plan generation.** Volume progression, phase structure, emphasis scheduling, quality limits. This is what the code is supposed to implement. |
| 10 | `_AI_CONTEXT_/KNOWLEDGE_BASE/03_WORKOUT_TYPES.md` | Workout types, long run progression, spacing contracts, quality session sizing. Source of truth for prescription logic. |
| 11 | `_AI_CONTEXT_/KNOWLEDGE_BASE/02_PERIODIZATION.md` | Periodization model — how training blocks are structured. |
| 12 | `_AI_CONTEXT_/KNOWLEDGE_BASE/TRAINING_PHILOSOPHY.md` | Extended training philosophy and methodology. |
| 13 | `_AI_CONTEXT_/KNOWLEDGE_BASE/TRAINING_METHODOLOGY.md` | Practical methodology — how philosophy translates to prescription. |
| 14 | `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/long_run_pilot_v1.md` | SME-approved long run variant definitions and progression rules. |
| 15 | `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/threshold_pilot_v1.md` | Threshold workout definitions and sizing. |
| 16 | `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/intervals_pilot_v1.md` | Interval workout definitions. |
| 17 | `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/easy_pilot_v1.md` | Easy run definitions. |
| 18 | `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/workout_registry.json` | Machine-readable workout variant registry. |
| 19 | `_AI_CONTEXT_/KNOWLEDGE_BASE/michael/TRAINING_PROFILE.md` | The founder's training profile. His long runs don't start until 15mi. Use this as the gold-standard test case. |

### CONTEXT DOCUMENTS — Read for current work

| # | Document | What It Gives You |
|---|----------|-------------------|
| 20 | `docs/TRAINING_PLAN_REBUILD_PLAN.md` | Phase summary table. What's complete, gated, contract-only. 119 xfail tests for future phases. |
| 21 | `docs/PLAN_GENERATION_HANDOFF_2026-03-26.md` | Full technical brief for plan generation. What's broken, what a correct plan looks like, the exact prescription logic. |
| 22 | `docs/SESSION_HANDOFF_2026-03-28_FAILED_PLAN_GEN_SESSION.md` | What the last agent did wrong and why. Read this to avoid repeating the same mistakes. |
| 23 | `docs/SESSION_HANDOFF_2026-03-26_NEW_AGENT_PLAN_GEN.md` | Previous handoff with data infrastructure fixes and the target plan output. |

### COACHING SOURCES — Reference as needed

The knowledge base also contains 8 coaching source philosophies that were synthesized into the governing documents above:

```
_AI_CONTEXT_/KNOWLEDGE_BASE/coaches/
├── source_A/   PHILOSOPHY.md, WORKOUT_DEFINITIONS.md, PLANS.md
├── source_B/   PHILOSOPHY.md, WORKOUT_DEFINITIONS.md
├── source_C/   80_20_PHILOSOPHY.md, PERFECT_RACE.md
├── source_D/   PHILOSOPHY.md
├── source_E/   PHILOSOPHY.md
├── source_F/   PHILOSOPHY.md
├── source_G/   PHILOSOPHY.md
├── source_H/   PHILOSOPHY.md
└── verde_tc/   PHILOSOPHY.md
```

---

## Part 3: Codebase Architecture

### Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI 0.104.1, Python 3.11 |
| Database | PostgreSQL 16 (TimescaleDB), SQLAlchemy 2.0.23 |
| Migrations | Alembic 1.12.1 |
| Task queue | Celery 5.3.4, Redis 7, gevent pool |
| Frontend | Next.js 14 (App Router), React 18, TypeScript |
| LLMs | Google Gemini (Flash for narration, coaching), Anthropic Claude (Opus for briefings) |
| Storage | MinIO (S3-compatible) |
| Reverse proxy | Caddy 2 (auto-TLS) |
| CI | GitHub Actions |

### Directory Map

```
c:\Dev\StrideIQ\
├── apps/
│   ├── api/                    # FastAPI backend (90% of codebase)
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── models.py           # 53 SQLAlchemy models (single file)
│   │   ├── schemas.py          # Pydantic schemas
│   │   ├── core/               # Auth, config, database, cache, security
│   │   ├── services/           # ~120 service files (business logic)
│   │   │   ├── plan_framework/ # ← Plan generation lives here
│   │   │   ├── fitness_bank.py # ← N=1 athlete data source
│   │   │   └── constraint_aware_planner.py  # ← Plan orchestrator
│   │   ├── routers/            # ~55 route files
│   │   ├── tasks/              # 14 Celery task modules
│   │   ├── tests/              # 175 test files, 3,900+ tests
│   │   ├── scripts/            # Ops/verification scripts
│   │   ├── alembic/versions/   # 91 migration files
│   │   └── Dockerfile
│   └── web/                    # Next.js frontend
│       ├── app/                # App Router pages
│       ├── components/         # React components
│       └── lib/                # API client, hooks, types
├── _AI_CONTEXT_/               # Knowledge base, coaching philosophy
│   └── KNOWLEDGE_BASE/         # 43 MD files + 1 JSON registry
├── docs/                       # 275+ files: specs, ADRs, handoffs, roadmaps
│   ├── adr/                    # 60+ Architecture Decision Records
│   └── specs/                  # Feature specifications
├── plans/                      # Training plan JSON archetypes
├── Caddyfile                   # Reverse proxy config
└── docker-compose.prod.yml     # Production stack definition
```

### Key Services

| Service | What it does |
|---------|-------------|
| `correlation_engine.py` | Core N=1 engine. 70 input signals, 9 output metrics. Finds per-athlete correlations with significance testing and time-shifted analysis. |
| `n1_insight_generator.py` | Turns correlations into athlete-facing insights. Contains the **Athlete Trust Safety Contract** (8 clauses) and `OutputMetricMeta` registry. Read before writing any coach output. |
| `fitness_bank.py` | Computes athlete fitness profile from activity history. `current_weekly_miles`, `peak_weekly_miles`, `current_long_run_miles`, `experience_level`, `best_rpi`. This is the N=1 data source for plans. |
| `constraint_aware_planner.py` | Orchestrates plan generation. `generate_plan()` method calls the KB-driven generator and maps output to the plan schema. |
| `plan_framework/kb_driven_generator.py` | The current plan generator. **This is what needs to be rebuilt.** |
| `plan_framework/load_context.py` | Computes L30 baselines from athlete history. Working correctly. |
| `plan_framework/workout_scaler.py` | Sizes individual workouts. `_scale_long_run()` was the old core problem. |
| `plan_framework/pace_engine.py` | Derives training paces from athlete's best RPI. |
| `plan_quality_gate.py` | Validates plan passes structural rules. Does NOT validate coaching quality. |
| `daily_intelligence.py` | 7 intelligence rules (INFORM/SUGGEST/FLAG). Morning daily sweep. |
| `ai_coach.py` | Conversational AI coach. Gemini Flash + Claude Opus routing. |
| `home_briefing_cache.py` | Redis-cached morning briefing with circuit breaker. |
| `experience_guardrail.py` | 25 assertions across 6 categories. Runs daily at 06:15 UTC. |

### Key Models

| Model | Table | Purpose |
|-------|-------|---------|
| `Athlete` | `athlete` | User account, subscription tier, Strava/Garmin tokens, RPI |
| `Activity` | `activity` | Every run/activity from Strava or Garmin |
| `GarminDay` | `garmin_day` | Daily wearable data: sleep, HRV, stress, body battery |
| `CorrelationFinding` | `correlation_finding` | N=1 correlation results |
| `AthleteFinding` | `fingerprint_finding` | Investigation results (heat, stride economy) |
| `AthleteFact` | `athlete_fact` | Coach memory: facts extracted from chat |
| `TrainingPlan` | `training_plan` | Race-specific training plan |
| `PlannedWorkout` | `planned_workout` | Individual scheduled workouts |
| `DailyReadiness` | `daily_readiness` | Readiness score with components |

---

## Part 4: Plan Generation — Current State

### What's Deployed (CI Green, Production Running)

**Latest CI-green commit:** `924f014` — "P0-GATE: GREEN -- fix: remove unused imports from constraint_aware_planner (lint)"

**What the deployed generator does:**
- `constraint_aware_planner.py` calls `kb_driven_generator.generate_plan()` to build weeks
- `kb_driven_generator.py` produces volume curves, long run curves, emphasis schedules, and populates day-by-day prescriptions
- The output is mapped to `WeekPlan`/`DayPlan` dataclasses and then saved as `PlannedWorkout` rows

**What's wrong with the deployed version:**
- Long runs are capped at 30% of weekly volume (`vol_cap = vol * 0.30`). This means a 45mpw athlete's long run peaks at 13.5mi — catastrophically low for marathon training.
- Volume progression uses conservative constants that prevent rebuilding athletes from reaching race-appropriate fitness.
- The generator passes all 3,900+ tests but produces uncoachable plans for every athlete profile except high-volume BQ chasers.

### What's NOT Deployed (Uncommitted Changes)

**File:** `apps/api/services/plan_framework/kb_driven_generator.py` — 86 insertions, 53 deletions vs committed version.

Changes attempted:
1. Removed `vol_cap = vol * 0.30` throttle on long runs
2. Added `_DISTANCE_LONG_RUN_ABS_CAP` and `_DISTANCE_LONG_RUN_MINIMUM_PEAK`
3. Rewrote volume peak to support long runs (`target_peak_long / 0.33`)
4. Fixed week templates for 3/4/5-day plans (back-to-back quality prevention)

These changes are directionally better but still don't implement the KB rules. They are the outgoing agent's invention, not the knowledge base's rules. The founder rejected them.

### The Test That Matters

The `PLAN_GENERATION_HANDOFF_2026-03-26.md` defines what a correct plan looks like for the founder's profile:

```
Input: Michael Shaffer, 10K on May 2 2026, 5K tune-up April 25, peak 65 mpw

Week  Volume  Long   Structure
1     40      14mi   Easy base + strides. No quality yet.
2     48      16mi   Easy base + strides. No quality yet.
3     56      18mi   First threshold session. Volume still building.
4     40 CUT  14mi   Cutback week. Single quality session.
5     62      17mi   Peak week. Two quality sessions.
6     TAPER   --     Tune-up 5K Saturday April 25. Sunday rest. ~35 mpw.
7     RACE    --     10K Saturday May 2. Sunday rest. ~20 mpw.
```

If the plan generator produces this for this athlete, it's working.

### The Correct Prescription Logic (from KB + handoff)

```
LONG RUN:
  Week 1 = l30_max_non_race_miles + 1    (e.g., 13 + 1 = 14mi)
  Week N = Week N-1 + 2mi                (non-cutback weeks)
  Cutback week = previous_peak * 0.75    (every 3rd or 4th week)
  Distance ceiling by race (e.g., 18mi for 10K, 22mi for marathon)
  NO volume-percentage cap

VOLUME:
  Week 1 = current_weekly_miles * 1.1 (or l30_median — whichever is higher)
  Target = user-specified peak
  Ramp = linear from start to peak, tier-based step ceiling (6-8mi/wk for HIGH/ELITE)
  10% rule explicitly REJECTED — see founder's article

QUALITY WORK:
  Freeze quality escalation during weeks where volume is increasing
  Quality volume = 8-12% of weekly volume
  Max 2 quality sessions per week
  Never place quality on the day before the long run
  Recovery day required between quality sessions

PACES:
  All paces from rpi_calculator.calculate_training_paces(bank.best_rpi)

RACE WEEK:
  Race day = race workout
  Day before = pre_race (easy 4-6mi + strides)
  Day after = rest (NOT a long run)
```

### Key Plan Generation Files

```
services/constraint_aware_planner.py          Main orchestrator
services/plan_framework/kb_driven_generator.py  Current generator (broken)
services/plan_framework/load_context.py         L30 baselines (working)
services/plan_framework/workout_scaler.py       Sizes workouts (old approach)
services/plan_framework/pace_engine.py          RPI → training paces
services/plan_framework/volume_tiers.py         Volume progression
services/plan_framework/phase_builder.py        Phase/emphasis assignment
services/plan_framework/workout_variant_dispatch.py  Maps to variant IDs
services/plan_quality_gate.py                   Structural validation
services/fitness_bank.py                        N=1 athlete data
routers/plan_generation.py                      API handler + save logic
```

### Test Files for Plan Generation

```
tests/test_constraint_aware_smoke_matrix.py            Core plan matrix
tests/test_constraint_aware_load_context_wiring.py     Load context integration
tests/test_constraint_aware_recovery_contract.py       Recovery rules
tests/test_constraint_aware_recovery_contract_real.py  Recovery with real data
tests/test_plan_validation_matrix.py                   Strict validation matrix
tests/test_plan_quality_recovery_v2.py                 Quality recovery
tests/test_plan_content_quality_matrix.py              Content quality checks
tests/test_plan_mileage_invariance.py                  Mileage invariance
tests/test_plan_framework_system_coverage.py           System coverage
```

### Qualitative Evaluation Tool

`apps/api/eval_realistic_athletes.py` — 12 synthetic athletes with diverse profiles:

| Athlete | Profile | Key Test |
|---------|---------|----------|
| Michael | Post-marathon rebuilder, 28mpw current, 65mpw peak, elite | Long runs must start at 14-15mi, not 8-10mi |
| Sarah | First-time marathoner, 30mpw, 4d/wk | Long runs must reach 20mi or refuse the plan |
| James | BQ chaser, 55mpw, 6d/wk | Long runs should reach 20-22mi |
| Maria | Injury comeback, 20mpw | Conservative progression, no aggressive ramps |
| Derek | Beginner 10K, 15mpw, 3d/wk | Should NOT get marathon training |
| Tom | Time-crunched half, 25mpw, 4d/wk | Realistic long runs for half prep |
| Lisa | 5K speedster, 40mpw | Quality-focused, not volume-heavy |
| Carlos | Ultra transition, 50mpw | Long runs 18-22mi, fueling practice |
| Amy | 3d/wk runner, 18mpw | Must NOT get marathon plan |
| Frank | Senior runner, 30mpw | Conservative, injury prevention |
| Rachel | Rebuilder from burnout, 20mpw | Gentle progression, rebuild confidence |
| Kevin | Advanced half, 45mpw | Solid half plan with 12-14mi long runs |

---

## Part 5: Fitness Bank — The N=1 Data Source

The fitness bank (`services/fitness_bank.py`) computes the athlete's current state from activity history. After fixes from the prior session, it produces:

```
current_long_run_miles:   13.0   (max non-race run in last 4 weeks, excluding >24mi)
current_weekly_miles:     33.1   (trailing 4-week average)
peak_weekly_miles:        68.0   (best 4-consecutive-week rolling average, post-dedup)
best_rpi:                 53.18  (max confidence-adjusted RPI from valid races)
experience_level:         elite
```

**Data integrity fixes from the prior session (committed, deployed):**
- Dedup window expanded from 1h to 8h (Garmin/Strava sync delay)
- `require_trusted_duplicate_flags=True` (no proximity fallback)
- `_find_best_race()` uses `max(rpi * confidence)` with no recency decay
- Post-marathon quality session penalty suppressed within 35 days
- Activities >24mi excluded from long run floor calculation

**Partially deployed fixes:**
- `_find_best_race()` fix, `require_trusted_duplicate_flags`, and quality penalty skip are in committed code but check `docs/SESSION_HANDOFF_2026-03-26_NEW_AGENT_PLAN_GEN.md` for full status.

---

## Part 6: The Intelligence Stack (Beyond Plans)

StrideIQ is much more than a plan generator. The plan generator is the current broken piece, but the intelligence infrastructure is extensive and working:

### Correlation Engine
```
Daily sweep (08:00 UTC)
  → For each athlete with new data:
    → For each output metric (efficiency, pace_easy, pace_threshold, etc.):
      → aggregate_daily_inputs() → 70 input signals from the last 90 days
      → Pearson correlation + significance testing
      → Time-shifted analysis (0-14 day lags)
      → Persist to CorrelationFinding (create/confirm/deactivate)
  → Layer pass (L1-L4) on confirmed findings:
    → L1: threshold detection
    → L2: asymmetry analysis
    → L3: decay curve fitting
    → L4: cascade scoring
```

### Home Briefing
```
/v1/home → Check Redis cache (briefing:{athlete_id})
  → Fresh (<2h): return cached
  → Stale (2-24h): return cached + enqueue refresh
  → Missing: generate sync (Claude Opus), cache, return
```

### Finding Surfacing
```
CorrelationFinding (times_confirmed >= 3, is_active = true)
  → fingerprint_context.py formats for prompt injection
  → Morning voice includes top findings in briefing prompt
  → Coach includes findings in system instruction
```

### Daily Intelligence
```
7 rules: INFORM / SUGGEST / FLAG
  → Load spike detection, efficiency breakthrough, sustained decline
  → Runs every morning
```

---

## Part 7: Deployment Pipeline

### Process (non-negotiable)

```
code → commit (scoped) → push main → CI green → deploy → verify
```

No PRs. No feature branches. Push to `main`. Wait for CI green. Deploy.

### Deploy Commands (on production server)

```bash
ssh root@187.124.67.153
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
docker ps                          # verify containers
docker logs strideiq_api --tail=50  # check API logs
```

### Container Names

| Service | Container | Port |
|---------|-----------|------|
| API | strideiq_api | 8000 (internal) |
| Web | strideiq_web | 3000 (internal) |
| Worker | strideiq_worker | — |
| Beat | strideiq_beat | — |
| Postgres | strideiq_postgres | 5432 (internal) |
| Redis | strideiq_redis | 6379 (internal) |
| Caddy | strideiq_caddy | 80, 443 |
| MinIO | strideiq_minio | 9000 (internal) |

### Generate Auth Token

```bash
docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
"
```

### Smoke Check

```bash
TOKEN=$(docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
") && curl -s -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/home | python3 -m json.tool
```

### CI Structure

| Job | What | Critical? |
|-----|------|-----------|
| Backend Tests | Full pytest suite (3,900+ tests, ~12 min) | Yes |
| Backend Smoke | 9 golden-path test files | Yes |
| Plan Validation Strict | Strict plan validation matrix | Yes |
| Migration Integrity | Alembic head check against `EXPECTED_HEADS` | Yes |
| Backend Lint | Ruff + Black (continue-on-error) | Warnings only |
| Frontend Build | ESLint + tsc + Next.js build | Yes |
| Frontend Tests | Jest smoke suite | Yes |
| Security Scan | Secret scan + pip-audit | Partial |
| Docker Build | Build images (no push) | Yes |

**P0-GATE:** Commits touching `plan_framework/` or `plan_generation` runtime code require `P0-GATE: GREEN` in the commit message or CI fails.

---

## Part 8: Things That Will Bite You

### 1. PowerShell Quoting
The founder's dev machine runs Windows with PowerShell. Inline Python code in SSH commands will be mangled. Write Python scripts to files and execute them remotely. Git commit messages can't use heredoc syntax — use multiple `-m` flags.

### 2. Docker Build Context
The API Dockerfile's build context is `./apps/api`. Only files inside `apps/api/` make it into the container. Scripts at the repo root are NOT accessible inside the container. Put operational scripts in `apps/api/scripts/`.

### 3. Script Hygiene Test
`test_scripts_hygiene.py` scans Python files in `scripts/` for forbidden patterns including email addresses. Use `<email>` as a placeholder.

### 4. Alembic Migration Heads
Current head: `athlete_fact_001`. When creating a new migration, update `EXPECTED_HEADS` in `.github/scripts/ci_alembic_heads_check.py`.

### 5. `get_db_sync()` Returns a Session, Not a Generator
```python
db = get_db_sync()     # CORRECT — returns SessionLocal() directly
db = next(get_db())    # WRONG for scripts/tasks
```

### 6. Celery Task Registration
New task modules must be imported in `apps/api/tasks/__init__.py`.

### 7. Date Boundary Sensitivity
Use explicit dates in tests, not `datetime.now()`.

### 8. Athlete Trust Safety Contract
Before writing ANY athlete-facing text about metrics, read the `OutputMetricMeta` registry in `n1_insight_generator.py`. Efficiency is directionally ambiguous.

### 9. CI uses Postgres 15, Production uses 16
Usually not a problem. Each test has 120s timeout. Backend Tests job has 20-minute timeout.

### 10. Redis Cache
When you change data affecting cached outputs, use targeted invalidation. **NEVER** `redis.flushall()`.

---

## Part 9: The Coaching Philosophy You Must Internalize

These are not suggestions. These are the rules that define whether a plan is acceptable:

1. **N=1 over population norms.** Every plan starts from the athlete's actual history (long runs, paces, peak volume). Population constants are guardrails, not the foundation.

2. **Long runs are the most important workout for distance runners.** They are NOT capped by a percentage of weekly volume. Real marathon training at 50mpw routinely has 20mi long runs (40% of volume). Weekly volume is built to SUPPORT the long run, not the other way around.

3. **Minimum long run standards by distance:**
   - Marathon: peak long run must reach 20mi. If it can't, the athlete needs more base building — don't generate a garbage plan.
   - Half marathon: peak long run must reach 12mi.
   - 10K: peak long run should reach 8-10mi (elite athletes do 14-18mi).
   - If a plan gives a long run less than 14 miles for an experienced runner, it is wrong.

4. **The 10% rule is rejected.** The founder has written about this publicly. Volume progression is tier-based with step ceilings (6-8mi/week for HIGH/ELITE), not a flat percentage.

5. **StrideIQ is NOT a "finish at any cost" plan generator.** If a runner can't do a real long run for their distance, they need more base building, not a plan that sets them up for failure. The system should refuse rather than produce garbage.

6. **For experienced athletes rebuilding post-race:** Their long run floor is based on recent demonstrated capacity, not their current recovery volume. An athlete who just ran a marathon and is at 28mpw recovery has a long run floor of 14-15mi, not 8-10mi.

7. **Quality sessions:** Max 2 per week. Never place on the day before a long run. Recovery day required between quality sessions. 80/20 rule (quality ≤ 20% of volume).

8. **3-day/week, low-mileage runners should NOT get marathon training** unless they are doing significant cross-training.

---

## Part 10: What the Last Agent Got Wrong (Anti-Pattern Warning)

**Anti-pattern #10: Iterating on code without reading the source material.**

Two consecutive agents received a task to fix plan generation. Both relied on conversation summaries and invented their own rules instead of reading the 43 knowledge base documents that define how plans should work. Both produced plans that passed tests and failed athletes. Both were stopped by the founder.

Specific invented rules that failed:
- `vol_cap = vol * 0.30` — capping long runs at 30% of weekly volume
- `target_peak = min(peak * 1.05, current * 1.30)` — preventing rebuilding athletes from reaching race-appropriate fitness
- `vol_share = {3: 0.45, 4: 0.38, 5: 0.30}` — day-count-based volume shares
- Linear interpolation for long runs instead of the KB's `+2mi/week` rule

**The fix:** Read the knowledge base first. Every rule in the generator must trace back to a specific KB document. If you can't cite the document, you're making it up.

---

## Part 11: Common Operations

### Run Tests Locally

```bash
cd apps/api
python -m pytest tests/test_specific_file.py -v
python -m pytest -k "test_name_pattern" -v
python -m pytest tests/ -q --timeout=120    # full suite
```

### Check CI Status

```bash
gh run list -L 1 --json status,conclusion
gh run view <run_id> --log-failed
gh run watch <run_id> --exit-status
```

### Database Access (production)

```bash
ssh root@187.124.67.153
docker exec -it strideiq_postgres psql -U postgres -d running_app
```

Note: database name is `running_app`, not `strideiq`. Postgres user is `postgres`.

### Run Script on Production

```bash
ssh root@187.124.67.153 "docker exec -w /app strideiq_api python scripts/my_script.py"
```

---

## Part 12: Your First Steps

1. **Read the knowledge base.** All of it. Before touching code.
2. **Present your understanding** to the founder. Show how you interpret the long run rules, volume progression, quality placement, and emphasis scheduling. Get sign-off.
3. **Rebuild the generator** from the KB rules, not from invented constants.
4. **Evaluate qualitatively** using `eval_realistic_athletes.py` before running tests. If Michael's long runs are under 14mi, if Sarah's marathon plan doesn't reach 20mi — the code is wrong regardless of test results.
5. **Then run the full test suite** and fix any failures.
6. **Show evidence** to the founder before deploying.

---

*This document is a companion to `docs/FOUNDER_OPERATING_CONTRACT.md`, not a replacement. The operating contract is the law. This is the field guide.*

*The postmortem for the failed session is at `docs/SESSION_HANDOFF_2026-03-28_FAILED_PLAN_GEN_SESSION.md`.*
