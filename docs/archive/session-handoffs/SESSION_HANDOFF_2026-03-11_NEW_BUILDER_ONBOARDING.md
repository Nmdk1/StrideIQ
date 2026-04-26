# New Builder Onboarding — Session Handoff

**Date:** March 11, 2026
**Purpose:** Everything a new builder agent needs to start working on StrideIQ without hitting walls.
**Written by:** Outgoing builder after ~15 sessions spanning correlation engine, experience guardrail, athlete fact extraction, Garmin integration, and 50+ features.

---

## Part 1: How This Founder Works

**Read `docs/FOUNDER_OPERATING_CONTRACT.md` before your first tool call. No exceptions.**

The three things that will get you killed fastest:

1. **Coding before you're told to code.** When the founder says "discuss," they mean discuss. They have an advisor agent. They will refine requirements through 3-5 rounds of conversation. If you receive a feature description and immediately start writing code, you will be replaced.

2. **Claiming results without evidence.** "All tests pass" without pasted output is not acceptable. "Production is healthy" without `docker ps` or log output is not acceptable. Paste the evidence. Every time.

3. **`git add -A`.** Never. Scoped commits only. Show `git diff --name-only --cached` before every commit. The founder reviews the file list.

**The founder's workflow is:**
```
discuss → scope → plan → test design → build → evidence → commit → deploy → verify
```

**The founder is:**
- A solo developer. There is no team. There are no PRs. Push directly to `main`.
- A competitive runner (57 years old, ran in college, still racing). They have deep domain expertise in running science and coaching.
- Direct. Short messages carry full weight. "go" means proceed. "no" means stop.
- They have an advisor agent they consult for architecture and risk. When they return with advisor output, treat it as refined requirements.

---

## Part 2: Guided Reading Order

Read these in order. Each builds on the last.

| # | Document | Why |
|---|----------|-----|
| 1 | `docs/FOUNDER_OPERATING_CONTRACT.md` | How to work. Non-negotiable rules. Anti-patterns that killed previous agents. |
| 2 | `docs/PRODUCT_MANIFESTO.md` | The soul. "The chart makes you open the app. The intelligence makes you trust it. The voice makes you need it." |
| 3 | `docs/PRODUCT_STRATEGY_2026-03-03.md` | The moat. 16 priority-ranked product concepts. Every feature flows from here. |
| 4 | `docs/BUILD_ROADMAP_2026-03-09.md` | The build north star. Horizons, gates, dependency graph. Know which horizon item you're building before writing code. |
| 5 | `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` | How every screen should feel. What's been agreed. **What's been rejected** — do NOT re-propose rejected decisions. |
| 6 | `docs/TRAINING_PLAN_REBUILD_PLAN.md` | Phase summary table: what's complete, what's gated, what's contract-only. 119 xfail tests waiting for gates to clear. |
| 7 | `docs/specs/CORRELATION_ENGINE_ROADMAP.md` | The 12-layer engine roadmap. Layers 1-4 are built. |
| 8 | `docs/SITE_AUDIT_LIVING.md` | Honest assessment of current state. |

**Context docs for active work:**
- `docs/FINGERPRINT_VISIBILITY_ROADMAP.md` — how backend intelligence connects to product strategy
- `docs/RUN_SHAPE_VISION.md` — visual vision for run data
- `docs/BUILD_SPEC_HOME_AND_ACTIVITY.md` — spec for home/activity pages
- `docs/AGENT_WORKFLOW.md` — build loop mechanics

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
│   ├── api/                    # FastAPI backend (this is 90% of the codebase)
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── models.py           # 53 SQLAlchemy models (single file)
│   │   ├── schemas.py          # Pydantic schemas
│   │   ├── core/               # Auth, config, database, cache, security
│   │   ├── services/           # ~120 service files (business logic)
│   │   ├── routers/            # ~55 route files
│   │   ├── tasks/              # 14 Celery task modules
│   │   ├── tests/              # 175 test files, 3,575+ tests
│   │   ├── scripts/            # Ops/verification scripts
│   │   ├── alembic/versions/   # 91 migration files
│   │   └── Dockerfile
│   └── web/                    # Next.js frontend
│       ├── app/                # App Router pages
│       ├── components/         # React components
│       └── lib/                # API client, hooks, types
├── _AI_CONTEXT_/               # Knowledge base, coaching philosophy, session context
│   └── KNOWLEDGE_BASE/         # Coaching sources, training methodology
├── docs/                       # 275 files: specs, ADRs, handoffs, roadmaps
│   ├── adr/                    # 60+ Architecture Decision Records
│   └── specs/                  # Feature specifications
├── plans/                      # Training plan JSON archetypes
├── Caddyfile                   # Reverse proxy config
└── docker-compose.prod.yml     # Production stack definition
```

### Key Services (the ones you'll touch most)

| Service | What it does |
|---------|-------------|
| `correlation_engine.py` | Core N=1 engine. Finds input signals that correlate with performance metrics per athlete. 70 input signals, 9 output metrics. Persistence, significance testing, time-shifted analysis. |
| `n1_insight_generator.py` | Turns correlation findings into athlete-facing insights. Contains the **Athlete Trust Safety Contract** (8 clauses) and `OutputMetricMeta` registry. Read this before writing any coach output. |
| `daily_intelligence.py` | Phase 2C: 7 intelligence rules (INFORM/SUGGEST/FLAG). Load spike detection, efficiency breakthrough, sustained decline. The brain that runs every morning. |
| `ai_coach.py` | Conversational AI coach. Gemini Flash + Claude Opus routing, persistent sessions, tool calls, cost caps. Fact injection from `AthleteFact` table. |
| `home_briefing_cache.py` | ADR-065: Redis-cached morning briefing. Fresh/stale/missing/refreshing states. Circuit breaker. Cooldown. |
| `experience_guardrail.py` | 25 assertions across 6 categories. Runs daily at 06:15 UTC. Catches "technically correct but experientially wrong" bugs. |
| `finding_persistence.py` | Living Fingerprint: stores `AthleteFinding` with supersession logic. |
| `correlation_layers.py` | Layers 1-4: threshold detection, asymmetry analysis, decay curves, cascade scoring. |
| `correlation_persistence.py` | Persists `CorrelationFinding` with reproducibility tracking. |
| `fingerprint_context.py` | Formats correlation findings for LLM prompts (morning voice, coach). |
| `race_input_analysis.py` | Investigation engine: mines race inputs, heat tax, stride economy, etc. |
| `pre_race_fingerprinting.py` | Racing fingerprint: best vs worst race patterns. |

### Key Models

| Model | Table | Purpose |
|-------|-------|---------|
| `Athlete` | `athlete` | User account, subscription tier, Strava/Garmin tokens, RPI |
| `Activity` | `activity` | Every run/activity from Strava or Garmin |
| `GarminDay` | `garmin_day` | Daily wearable data: sleep, HRV, stress, body battery, steps |
| `CorrelationFinding` | `correlation_finding` | N=1 correlation results with threshold/asymmetry/decay parameters |
| `AthleteFinding` | `fingerprint_finding` | Investigation results (heat resilience, stride economy, etc.) |
| `AthleteFact` | `athlete_fact` | Coach memory: facts extracted from chat conversations |
| `CoachChat` | `coach_chat` | Conversation history with incremental extraction checkpoint |
| `DailyReadiness` | `daily_readiness` | Readiness score with component breakdown |
| `TrainingPlan` | `training_plan` | Race-specific training plan |
| `PlannedWorkout` | `planned_workout` | Individual scheduled workouts |
| `ExperienceAuditLog` | `experience_audit_log` | Daily guardrail assertion results |

---

## Part 4: Deployment Pipeline

### The Process (non-negotiable)

```
code → commit (scoped) → push main → CI green → deploy → verify
```

There are no PRs. There are no feature branches (unless you choose to use one locally). Push to `main`. Wait for CI green. Deploy.

### Deploy Commands (on production server)

```bash
# SSH in
ssh root@187.124.67.153

# Pull and rebuild
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build

# Check containers
docker ps

# Check API logs
docker logs strideiq_api --tail=50

# Check worker logs
docker logs strideiq_worker --tail=50
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

### Generate Auth Token (for API testing)

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
| Backend Tests | Full pytest suite (3,575+ tests, ~12 min) | Yes — must pass |
| Backend Smoke | 9 golden-path test files | Yes |
| Migration Integrity | Alembic head check against `EXPECTED_HEADS` | Yes |
| Backend Lint | Ruff + Black (continue-on-error) | No — warnings only |
| Frontend Build | ESLint + tsc + Next.js build | Yes |
| Frontend Tests | Jest smoke suite | Yes |
| Security Scan | Secret scan + pip-audit | Partial — secret scan is hard fail |
| Docker Build | Build images (no push) | Yes |

### CI Environment Notes

- CI uses Postgres **15**, production uses **16**. Usually not a problem.
- `pytest-timeout` is installed. Each test has a 120s timeout. The entire Backend Tests job has a 20-minute timeout.
- `EXPECTED_HEADS` in `.github/scripts/ci_alembic_heads_check.py` is currently `{"athlete_fact_001"}`. When you add a new migration, update this.

---

## Part 5: Things That Will Bite You

### 1. PowerShell Quoting

The founder's dev machine runs Windows with PowerShell. Inline Python code in SSH commands will be mangled by PowerShell. **Always write Python scripts to files and execute them remotely** rather than trying to pass inline Python through SSH.

```powershell
# THIS WILL FAIL — PowerShell eats Python syntax
ssh root@server "docker exec api python -c 'from models import X; print(X)'"

# DO THIS INSTEAD — write a script file
# 1. Write script to apps/api/scripts/my_script.py
# 2. Commit and push
# 3. Deploy
# 4. ssh root@server "docker exec -w /app strideiq_api python scripts/my_script.py"
```

Git commit messages also can't use heredoc syntax in PowerShell. Use multiple `-m` flags:

```powershell
git commit -m "feat: description" -m "Details here"
```

### 2. Docker Build Context

The API Dockerfile's build context is `./apps/api`. Only files inside `apps/api/` make it into the container. Scripts at the repo root (`scripts/`) are NOT accessible inside the container. Put operational scripts in `apps/api/scripts/` and add `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` at the top so they can import from `core`, `models`, `services`, etc.

### 3. Script Hygiene Test

`test_scripts_hygiene.py` scans all Python files in the `scripts/` directory for forbidden patterns, including email addresses (regex). If you put an email in a script (even in a docstring or usage example), CI will fail. Use `<email>` as a placeholder.

### 4. Alembic Migration Heads

When you create a new migration:
1. Set `down_revision` to the current head (currently `athlete_fact_001`)
2. Update `EXPECTED_HEADS` in `.github/scripts/ci_alembic_heads_check.py` to your new migration's revision ID
3. If you forget step 2, CI will fail on Migration Integrity

### 5. `get_db_sync()` Returns a Session, Not a Generator

```python
# WRONG — will raise TypeError
db = next(get_db_sync())

# RIGHT
db = get_db_sync()
```

The FastAPI dependency `get_db()` is a generator (used with `Depends`). The sync version `get_db_sync()` returns a `SessionLocal()` directly. Tasks and scripts use `get_db_sync()`.

### 6. Celery Task Registration

New task modules must be imported in `apps/api/tasks/__init__.py`. If you create `tasks/my_new_task.py`, add `from . import my_new_task` to `tasks/__init__.py` or the worker will report the task as unregistered.

### 7. Garmin Sync Tests Are Flaky

`test_garmin_d5_activity_sync.py` and `test_garmin_d6_health_sync.py` occasionally hang in CI. This is a known issue that needs a proper root-cause fix (likely a mock that doesn't properly terminate or a session that deadlocks). The `pytest-timeout` of 120s will kill them if they hang, but that results in failures, not passes. **Fix the root cause when you encounter it.**

### 8. Date Boundary Sensitivity in Tests

Tests that create activities with `datetime.now(timezone.utc)` can fail when the UTC time crosses midnight during the test run. Use explicit dates:

```python
# WRONG — can cross midnight boundary
now = datetime.now(timezone.utc)
activity1 = Activity(start_time=now, ...)
activity2 = Activity(start_time=now + timedelta(hours=4), ...)

# RIGHT — deterministic date
base = datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc)
activity1 = Activity(start_time=base, ...)
activity2 = Activity(start_time=base + timedelta(hours=4), ...)
```

### 9. The Athlete Trust Safety Contract

Before writing ANY athlete-facing text about metrics (efficiency, pace, HR, etc.), read the `OutputMetricMeta` registry in `n1_insight_generator.py`. Efficiency (pace/HR ratio) is **directionally ambiguous** — the system must not claim "lower efficiency is better" or "higher efficiency is better" without per-athlete evidence. Six metrics have approved directional language. Everything else gets neutral observation text. Violating this will break trust contract enforcement tests.

### 10. Test Fixtures: `db_session` vs `db`

The test `conftest.py` provides `db_session` (with transaction rollback) and `test_athlete`. Some older tests use `db` directly. When writing new tests, use `db_session` and `test_athlete` from conftest. If you see errors like `AttributeError: 'function' object has no attribute 'query'`, you're using the wrong fixture name.

### 11. Feature Flags

Many features are gated behind `FeatureFlag` rows in the database. Check `core/feature_flags.py` for the gating mechanism. The experience guardrail, for example, runs for the founder only (filtered by athlete email in the task).

### 12. Redis Cache Invalidation

When you change data that affects cached outputs (briefings, correlations), use targeted invalidation:
- `invalidate_correlation_cache(athlete_id)` — clears correlation results
- `mark_briefing_dirty(athlete_id)` + `enqueue_briefing_refresh(...)` — refreshes morning briefing
- **NEVER** `redis.flushall()`. The founder has explicitly forbidden global Redis flushes.

---

## Part 6: Current State (March 11, 2026)

### What Just Shipped

1. **Full Correlation Engine Input Wiring** — 49 new input signals wired across 5 phases. Engine now has 70 inputs (up from 21). Includes GarminDay wearable signals, activity-level signals, feedback/reflection signals, checkin/composition/nutrition, and derived training patterns.

2. **Fingerprint Backfill** — Script at `apps/api/scripts/backfill_correlation_fingerprint.py`. Already run for founder. Results: 38 active findings, 23 surfaceable. Uses bounded bootstrap promotion (cap at `times_confirmed = 3`, no overlap inflation).

3. **Athlete Fact Extraction** — Coach memory layer 1. Facts extracted from chat conversations, stored in `athlete_fact` table. Injected into coach prompts (15 fact cap, ordered by confirmed then recent). Concurrency-safe upsert with savepoints.

4. **Daily Experience Guardrail** — 25 assertions, 6 categories, runs daily at 06:15 UTC. Logs to `experience_audit_log`.

### What Needs Attention

1. **CI flaky tests** — `test_garmin_d5_activity_sync.py` and `test_garmin_d6_health_sync.py` hang intermittently. The `pytest-timeout` catches them but they fail instead of passing. Root cause needs investigation.

2. **Horizon 1 items** (from `BUILD_ROADMAP_2026-03-09.md`):
   - 1a: Findings pinned to chart timestamps on activity detail
   - 1b: Weather-adjusted effort coloring on pace chart
   - 1c: Shape icons on activity list cards
   - 1d: Morning voice references specific findings (partially wired)
   - 1e: "What this run taught us" narrative block

3. **Race-week weather (P0)** — Michael's marathon is Saturday March 15. Weather forecast + personal heat model surfaced in morning voice. See `docs/BUILD_ROADMAP_2026-03-09.md` Priority 0.

### Production State

- All 8 containers running healthy on Hostinger KVM 8 (8 vCPU, 32 GB RAM)
- Latest deployed commit: `9a6dd59`
- Database: `running_app` on PostgreSQL 16 (TimescaleDB)
- Correlation engine: 70 input signals active, 38 active findings for founder, 23 surfaceable

---

## Part 7: Key Patterns

### How the Correlation Engine Works

```
Daily sweep (08:00 UTC)
  → For each athlete with new data:
    → For each output metric (efficiency, pace_easy, pace_threshold, etc.):
      → aggregate_daily_inputs() → 70 input signals from the last 90 days
      → Pearson correlation + significance testing (scipy.stats.t.sf)
      → Time-shifted analysis (0-14 day lags)
      → Persist to CorrelationFinding (create/confirm/deactivate)
  → Layer pass (L1-L4) on confirmed findings:
    → L1: threshold detection
    → L2: asymmetry analysis
    → L3: decay curve fitting
    → L4: cascade scoring
```

### How the Home Briefing Works

```
Request to /v1/home
  → Check Redis cache (key: briefing:{athlete_id})
  → If fresh (<2h): return cached
  → If stale (2-24h): return cached + enqueue refresh
  → If missing: generate sync (Claude Opus), cache, return
  → Background refresh: Celery task generates new briefing with fingerprint context
```

### How Finding Surfacing Works

```
CorrelationFinding (times_confirmed >= 3, is_active = true)
  → fingerprint_context.py formats for prompt injection
  → Morning voice (home.py) includes top findings in briefing prompt
  → Coach (ai_coach.py) includes findings in system instruction
  → N1 insight generator turns findings into athlete-facing sentences
```

---

## Part 8: Files You'll Edit Most

| File | Why |
|------|-----|
| `apps/api/services/correlation_engine.py` | Adding inputs, modifying discovery logic |
| `apps/api/services/n1_insight_generator.py` | FRIENDLY_NAMES, insight generation, trust contract |
| `apps/api/routers/home.py` | Morning voice, home page API |
| `apps/api/services/ai_coach.py` | Coach behavior, prompt engineering |
| `apps/api/models.py` | New tables, new columns |
| `apps/api/services/daily_intelligence.py` | Intelligence rules |
| `apps/api/services/experience_guardrail.py` | New assertions |
| `apps/api/tasks/` | New Celery tasks |
| `.github/workflows/ci.yml` | CI configuration |
| `.github/scripts/ci_alembic_heads_check.py` | Migration head tracking |

---

## Part 9: Common Operations

### Run Tests Locally

```bash
cd apps/api
pytest tests/test_specific_file.py -v
pytest -k "test_name_pattern" -v
pytest tests/ -v --timeout=120  # full suite with timeout
```

### Check CI Status

```bash
gh run list -L 1 --json status,conclusion
gh run view <run_id> --log-failed  # see failure details
gh run watch <run_id> --exit-status  # watch to completion
```

### Database Access (production)

```bash
ssh root@187.124.67.153
docker exec -it strideiq_postgres psql -U postgres -d running_app
```

Note: the database name is `running_app`, not `strideiq`. The Postgres user is `postgres`.

### Run a Script on Production

```bash
ssh root@187.124.67.153 "docker exec -w /app strideiq_api python scripts/my_script.py"
```

---

## Part 10: What I Would Fix First

If I had one more session, I would:

1. **Fix the Garmin sync test hangs.** Root-cause `test_garmin_d5_activity_sync.py` and `test_garmin_d6_health_sync.py`. Likely a mock that doesn't terminate properly or a session/connection that deadlocks. These are my tests from previous sessions and they intermittently hang CI. This is the highest-priority technical debt.

2. **Clean up the `git add -A` commit.** Commit `a7b7060` swept in unrelated files (`docs/BUILDER_INSTRUCTIONS_2026-03-10_HEAT_CORRELATION_INPUT.md`, `scripts/verify_correlation_inputs.py`, and modifications to `athlete_profile.py`, `attribution_engine.py`, `pre_race_fingerprinting.py`, `trend_attribution.py`). These changes are harmless but the commit is not scoped. The founder's contract says scoped commits only.

3. **Build P0: Race-week weather** for the March 15 marathon.

---

*This document is a companion to `docs/FOUNDER_OPERATING_CONTRACT.md`, not a replacement. The operating contract is the law. This handoff is the field guide.*
