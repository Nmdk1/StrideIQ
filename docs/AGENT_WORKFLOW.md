# Agent Workflow — How To Build With This Founder

**First read `docs/FOUNDER_OPERATING_CONTRACT.md` — that is the operating
contract. This document covers the mechanics of building.**

---

## The Build Loop

Every task — no matter how small — follows this loop. No shortcuts. No exceptions.

```
┌─────────────────────────────────────────────────────┐
│  1. RESEARCH                                         │
│     Deep dive into relevant code. Trace full call    │
│     chain. Explain what you found. If you skip this, │
│     you will introduce regressions and lose trust.   │
├─────────────────────────────────────────────────────┤
│  2. FULL TEST PLAN                                   │
│     Define acceptance criteria AND the full test plan │
│     across ALL applicable categories (6 categories   │
│     below). What does "done" look like? What should  │
│     each test category assert? Which categories      │
│     apply? Get FOUNDER SIGN-OFF before proceeding.   │
│     This is the most important step.                 │
├─────────────────────────────────────────────────────┤
│  3. WRITE TESTS                                      │
│     Encode the full test plan as tests FIRST.        │
│     Tests define the contract. They run red until    │
│     implementation is complete. Tests cover:         │
│     - Unit: functions + edge cases                   │
│     - Integration: components wired together         │
│     - Plan validation: coaching rules (if applicable)│
│     - Training logic: scenario tests (if applicable) │
│     - Coach evaluation: contract tests (if coach)    │
├─────────────────────────────────────────────────────┤
│  4. IMPLEMENT                                        │
│     Write the code. Trace root causes, don't patch   │
│     symptoms. If something looks wrong, go deeper.   │
├─────────────────────────────────────────────────────┤
│  5. VALIDATE                                         │
│     Run the build validation script (see below).     │
│     Show evidence — paste output, not claims.        │
│     Pass → commit. Fail → fix and retest.           │
│     No moving forward until green.                   │
├─────────────────────────────────────────────────────┤
│  6. COMMIT                                           │
│     Scoped commits only. Never git add -A. Show      │
│     git diff --name-only --cached before committing. │
│     Commit message follows repo conventions.         │
├─────────────────────────────────────────────────────┤
│  7. CI                                               │
│     Push. Verify CI green. Local pass is not enough. │
│     If CI red, fix before moving on.                 │
└─────────────────────────────────────────────────────┘
```

### ADRs for Architectural Decisions

If there's a meaningful architectural choice (not a simple implementation), document:
- The options considered
- Trade-offs of each
- Rationale for the chosen approach
- Save to `docs/adr/ADR-NNN-<name>.md`

Don't just pick one and code it.

---

## Testing Pyramid (All Six Categories Required)

Nothing is good until it is tested. Every task requires all applicable categories.

### Category 1: Unit Tests (every commit)
Individual functions. Happy path + edge cases + error cases + boundary cases.
5-10 tests per function for anything with logic. Not 1 test that proves it works — tests that prove it can't break.

### Category 2: Integration Tests (every commit)
Components wired together against the test database. Plan generator → pace engine → RPI calculator → athlete data. API endpoints: HTTP in, JSON out, correct shape, correct fields.

### Category 3: Plan Validation Tests (every commit)
Generate real plans and validate the COACHING, not just the code.
Parametrized matrix: every distance × tier × duration variant.
Assertions encode the KB rules (Source B limits, phase rules, alternation, progression, taper).
If a regression sneaks in that puts threshold in the base phase, this catches it.

### Category 4: Training Logic / Scenario Tests (every commit)
Construct a training state. Trigger the system. Assert the coaching decision.
"Given 7 days of declining efficiency + scheduled threshold → system swaps to easy."
Tests the BRAIN, not the output format. Tests whether the system would actually help an athlete.

### Category 5: Coach LLM Evaluation Tests (nightly / pre-deploy)
Tagged `@pytest.mark.coach_integration`. Costs tokens. Catches real coach failures.
Send real prompts, get real responses, assert against coaching contract:
- No raw metrics dumped
- No VDOT (trademark)
- Validates athlete feelings before contradicting
- Uses tools (calls get_training_paces, not guessing)
- Tone rules followed
Every failure the founder has found manually becomes a regression test here.

### Category 6: Production Smoke Tests (post-deploy)
Exact commands run on the droplet. Founder pastes output. Agent verifies.
Feature-specific verification against real data. "It works on my machine" dies here.

---

## Build Validation Commands

Run this after every implementation step. Paste the output as evidence.

### Backend Tests (from workspace root)

```bash
# Start test infrastructure (if not running)
docker compose -f docker-compose.test.yml up -d postgres redis

# Run all backend tests (Categories 1-4)
docker compose -f docker-compose.test.yml run --rm api_test pytest -x -q

# Run specific test file (during development)
docker compose -f docker-compose.test.yml run --rm api_test pytest -x -q tests/<test_file>.py

# Run plan validation matrix
docker compose -f docker-compose.test.yml run --rm api_test pytest -x -q tests/test_plan_validation_matrix.py -v

# Run training logic scenarios
docker compose -f docker-compose.test.yml run --rm api_test pytest -x -q tests/test_training_logic_scenarios.py -v

# Run coach evaluation suite (costs tokens — nightly/pre-deploy only)
docker compose -f docker-compose.test.yml run --rm api_test pytest -x -q -m coach_integration tests/test_coach_evaluation.py -v

# Run with coverage (before final commit)
docker compose -f docker-compose.test.yml run --rm api_test pytest -v --cov=. --cov-report=term-missing
```

### Frontend Tests (from workspace root)

```bash
cd apps/web && npm test -- --watchAll=false --silent
```

### Production Smoke Tests (post-deploy, founder runs on droplet)

```bash
# 1. All containers healthy
docker compose -f docker-compose.prod.yml ps

# 2. API responding
curl -s http://localhost:8000/health | python3 -m json.tool

# 3. Feature-specific smoke (agent provides exact command per task)
docker compose -f docker-compose.prod.yml exec api python -c "<specific verification>"

# 4. Frontend loading
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000

# 5. Recent logs clean
docker compose -f docker-compose.prod.yml logs --tail 20 api 2>&1 | grep -i error
```

### Full Validation (run before every commit)

```bash
# 1. Backend tests
docker compose -f docker-compose.test.yml run --rm api_test pytest -x -q

# 2. Frontend tests
cd apps/web && npm test -- --watchAll=false --silent && cd ../..

# 3. Frontend lint + type check
cd apps/web && npm run lint && npx tsc --noEmit && cd ../..

# 4. Show what changed
git diff --name-only
git diff --stat

# 5. Stage ONLY the files for this change (NEVER git add -A)
git add <specific files>

# 6. Show staged files for review
git diff --name-only --cached

# 7. Commit with descriptive message
git commit -m "<type>(<scope>): <description>"
```

### Deploy (production — exact commands, no guessing)

**SSH access:**
```bash
ssh root@strideiq.run
```

**Standard deploy (run from the droplet, already SSH'd in):**
```bash
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build --remove-orphans && docker compose -f docker-compose.prod.yml ps
```

**Force rebuild if Docker caching issues (old code still running after deploy):**
```bash
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml build --no-cache api && docker compose -f docker-compose.prod.yml build --no-cache web && docker compose -f docker-compose.prod.yml up -d --remove-orphans
```

**Flush Redis (after coach/prompt changes):**
```bash
cd /opt/strideiq/repo && docker compose -f docker-compose.prod.yml exec redis redis-cli FLUSHALL
```

**Verify health after deploy:**
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail 20 api 2>&1 | grep -i error
```

### Networking (critical — do not guess)

The API container (`strideiq_api`) does **not** expose ports to the host.
It is only accessible via the internal Docker network through the Caddy
reverse proxy. Caddy routes `/v1/*` to `api:8000` internally.

- **From the host or outside:** use `https://strideiq.run/v1/...`
- **`localhost:8000` will NOT work** — the port is not published.
- Health check from inside the container: `docker exec strideiq_api curl -s http://localhost:8000/health`

### Generating auth tokens for smoke tests

The founder may not know what a JWT token is. Here is how to generate one
on the droplet for authenticated API calls:

```bash
# Generate a 30-day token for the founder's account
docker exec strideiq_api python -c "from core.security import create_access_token;from core.database import SessionLocal;from models import Athlete;db=SessionLocal();a=db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first();print(create_access_token(data={'sub':str(a.id),'email':a.email,'role':a.role}));db.close()"

# Set the token for subsequent curl commands
export TOKEN="<paste-token-from-above>"

# Use in smoke tests
curl -s -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/home | python3 -m json.tool
```

### Container names (do not guess)

| Service  | Container Name     | Image      |
|----------|--------------------|------------|
| API      | strideiq_api       | repo-api   |
| Worker   | strideiq_worker    | repo-worker|
| Web      | strideiq_web       | repo-web   |
| Caddy    | strideiq_caddy     | caddy:2    |
| Postgres | strideiq_postgres  | timescale/timescaledb:latest-pg16 |
| Redis    | strideiq_redis     | redis:7-alpine |

### Migrations

Migrations run **automatically** on container start (`python run_migrations.py`
in the API entrypoint). No manual step needed.

### Migration conflict recovery (production)

If deploy logs show a duplicate-object failure while applying
`corr_persist_001` (for example duplicate `correlation_finding` relation/type),
the schema object exists but Alembic version tracking is behind. Use:

```bash
docker compose -f docker-compose.prod.yml exec api alembic current
docker compose -f docker-compose.prod.yml exec api alembic heads
docker compose -f docker-compose.prod.yml exec api alembic stamp corr_persist_001
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
docker compose -f docker-compose.prod.yml exec api alembic current
```

Important: when running direct `psql` checks in prod, use the configured
`POSTGRES_USER` (defaults to `postgres` in `docker-compose.prod.yml`) unless
the environment overrides it.

### Domain verification (always use real domain)

Do not hand the founder placeholder hostnames for final smoke checks.
Use the actual production host:

```bash
curl -I https://strideiq.run
curl -s https://strideiq.run/health
dig +short strideiq.run
dig +short www.strideiq.run
```

### Docker caching lesson

If you deploy and the old code is still running, it is almost always Docker
layer caching. Use the `--no-cache` variant above. This was learned the hard
way with the `scipy` dependency addition.

### CI Verification

```bash
# Check CI status after push
gh run list --branch main --limit 3
gh run view <run-id>

# If a job fails, inspect its logs (only available after run completes)
gh run view --job=<job-id> --log-failed
```

### CI gates to be aware of

- **Migration Integrity:** `EXPECTED_HEADS` in `.github/scripts/ci_alembic_heads_check.py`
  must be updated whenever a new Alembic migration is added. If you add a migration,
  update this file to match the new head revision.
- **Frontend Build:** Runs `npx tsc --noEmit`. All TypeScript must pass strict type checking.
  Common pitfalls: `Set` spread requires `downlevelIteration` (use `Array.from()` instead),
  untyped mock parameters in test files.

---

## Phase Execution Plan

Each phase from `docs/TRAINING_PLAN_REBUILD_PLAN.md` breaks into tasks.
Each task follows the build loop above.

### Phase 1: World-Class Plans by Distance

#### Task 1A: Pace Injection Audit & Fix

**Research:**
- Trace pace injection through all 5 active generators
- Map which tiers get paces and which don't
- Identify the `paces=None` path in standard tier

**Acceptance Criteria:** (from TRAINING_PLAN_REBUILD_PLAN.md, section 1A)

**Tests:**
- `test_standard_plan_has_paces_when_rpi_exists`
- `test_standard_plan_has_effort_descriptions_when_no_rpi`
- `test_all_tiers_inject_paces_consistently`

**Files:** `generator.py`, `pace_engine.py`, `plan_generation.py`

---

#### Task 1B: Marathon A-Level Quality

**Research:**
- Read full archetype JSON, verify against KB framework
- Trace T-block progression, verify volumes
- Check MP total, long run progression, cutback structure
- Verify alternation rule compliance

**Acceptance Criteria:** (from TRAINING_PLAN_REBUILD_PLAN.md, section 1B)

**Tests:**
- `test_marathon_tblock_progression_matches_kb`
- `test_marathon_mp_total_volume`
- `test_marathon_long_run_respects_athlete_practice`
- `test_marathon_alternation_rule`
- `test_marathon_volume_limits_source_b`

**Files:** `marathon_mid_6d_18w.json`, `plan_generator.py`, `generator.py`

---

#### Task 1C: N=1 Override System

**ADR Required:** ADR for athlete_plan_profile design — what signals drive which overrides, fallback behavior, data freshness requirements.

**Research:**
- How Strava data flows into plan generation today
- What athlete fields exist on the model
- How the Intelligence Bank stores patterns
- Current constants.py structure and override points

**Acceptance Criteria:** (from TRAINING_PLAN_REBUILD_PLAN.md, section 1C)

**Tests:**
- `test_athlete_plan_profile_derives_long_run_from_strava`
- `test_athlete_plan_profile_derives_volume_tier`
- `test_overrides_propagate_to_plan_generation`
- `test_cold_start_falls_back_to_tier_defaults`
- `test_experienced_runner_long_run_not_capped`

**Files:** New `athlete_plan_profile.py`, `constants.py`, `generator.py`

---

#### Task 1D: Taper Democratization

**Research:**
- How τ1-aware taper works in `individual_performance_model.py`
- How pre-race fingerprinting detects patterns
- Current taper construction in `phase_builder.py`
- What data exists for non-Elite athletes

**Acceptance Criteria:** (from TRAINING_PLAN_REBUILD_PLAN.md, section 1D)

**Tests:**
- `test_taper_uses_individual_tau_when_available`
- `test_taper_estimates_from_recovery_pattern_when_no_tau`
- `test_taper_maintains_intensity_reduces_volume`
- `test_fingerprinting_available_at_subscription_tier`

**Files:** `individual_performance_model.py`, `pre_race_fingerprinting.py`, `phase_builder.py`

---

#### Tasks 1E-1G: Half Marathon, 10K, 5K

Each follows the same pattern:
1. Research existing phase builder for that distance
2. Define acceptance criteria (from TRAINING_PLAN_REBUILD_PLAN.md)
3. Write tests for distance-specific periodization, workout progressions, volume limits
4. Implement in `phase_builder.py` and `workout_scaler.py`
5. Validate
6. Commit

---

### Phase 2: Daily Adaptation Engine

#### Task 2A: Readiness Score

**ADR Required:** ADR for readiness score composition — signal weights, HRV exclusion policy, score normalization.

**Research:**
- How TSB is computed (`training_load.py`)
- How efficiency trend is calculated (`coach_tools.py`)
- How PlannedWorkout completion is tracked
- How recovery half-life is determined
- Current HRV data flow in correlation engine

**Acceptance Criteria:** (from TRAINING_PLAN_REBUILD_PLAN.md, section 2A)

**Tests:**
- `test_readiness_score_computes_from_available_signals`
- `test_readiness_excludes_hrv_without_individual_correlation`
- `test_readiness_includes_hrv_when_correlation_proven`
- `test_readiness_degrades_gracefully_with_missing_signals`
- `test_daily_readiness_model_stores_components`

---

#### Task 2B: Workout State Machine

**Research:**
- Current PlannedWorkout model fields and states
- How completion/skip tracking works today
- What the calendar UI renders

**Tests:**
- `test_workout_state_transitions`
- `test_adaptation_log_records_all_changes`
- `test_original_workout_preserved_after_adaptation`
- `test_migration_preserves_existing_plans`

---

#### Task 2C: Adaptation Rules Engine

**Research:**
- Build 20+ historical scenarios from founder's training data
- Map each scenario to expected rule output
- Verify signal availability for each rule

**Tests:**
- One test per rule, with specific scenarios
- `test_rules_priority_ordering`
- `test_no_rule_fires_without_sufficient_data`
- `test_rules_feature_flag_toggles`
- Integration test: readiness → rules → adaptation → log

---

#### Task 2D: Nightly Replan

**Tests:**
- `test_nightly_task_runs_for_all_active_plans`
- `test_nightly_task_handles_errors_per_athlete`
- `test_adaptation_visible_on_calendar`
- `test_no_notification_when_no_changes`

---

#### Task 2E: No-Race-Planned Modes

**Tests:**
- `test_maintenance_mode_generates_rolling_plan`
- `test_base_building_mode_progressive_volume`
- `test_transition_from_no_race_to_race_plan`

---

### Phase 3: Contextual Coach Narratives

**Gate:** Phase 2 running. Coach trust milestones met.

#### Task 3A: Adaptation Narration

**Tests:**
- `test_narration_generated_for_every_adaptation`
- `test_narration_cites_specific_data`
- `test_narration_does_not_contradict_rules_decision`
- `test_fallback_to_structured_reason_on_low_quality`

---

## Founder Working Style

These are non-negotiable. Violating any of them costs trust immediately.

1. **Research first, always.** Before touching a single file, do a deep dive into the relevant code, understand the full call chain, and explain what you found.

2. **Acceptance criteria before implementation.** Get sign-off before proceeding.

3. **Build loop — no shortcuts.** Criteria → Tests → Implement → Validate → Commit.

4. **ADRs for decisions.** Document options, trade-offs, rationale.

5. **Scoped commits only.** Never `git add -A`. Show `git diff --name-only --cached` before committing.

6. **Show evidence, don't claim results.** Paste test output. Paste deploy logs. "It should work" is not acceptable.

7. **CI must be green.** Local passing is not sufficient.

8. **Deploy commands must be exact.** Use the correct compose file, container names, flags. If unsure, ask.

9. **Don't be lazy.** Trace root causes. Don't patch symptoms. Thorough work is respected. Shallow work is called out immediately.

10. **Test EVERYTHING before accepting.** Not just code — test the training logic (does the system make correct coaching decisions?), test the plans (do they follow coaching rules across all distances?), test the coach (does it give non-harmful, actually useful responses?). The founder has spent $1000+ in tokens finding things that don't work. That era ends now. Every task gets a full test plan across all 6 categories (unit, integration, plan validation, training logic scenarios, coach evaluation, production smoke). Define the full test plan BEFORE writing tests. Get founder sign-off on the test plan. Then build.

11. **No threshold is assumed universal.** Readiness thresholds, adaptation triggers, HRV direction — all per-athlete parameters that start conservative and calibrate from outcome data. Never hardcode a coaching opinion as a constant.

12. **The system INFORMS, the athlete DECIDES.** The daily intelligence engine surfaces data and patterns. It does NOT swap workouts or override the athlete. Fatigue is a stimulus for adaptation, not an enemy. The system must never prevent a breakthrough by "protecting" the athlete from productive stress. Intervention (flagging, not overriding) only on sustained 3+ week negative trajectories. Self-regulation (athlete modifies their own workout) is first-class data that the system learns from.
