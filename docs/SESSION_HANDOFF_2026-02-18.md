# Session Handoff — February 18, 2026

## What was accomplished

### Lane 2A: Home briefing off request path — SHIPPED (founder-only)

Complete implementation of ADR-065: home briefing served from Redis cache, never inline LLM.

**Commits on `main`:**
| SHA | Description |
|-----|-------------|
| `254a430` | feat(perf): Lane 2A - home briefing off request path ADR-065 |
| `8d139a8` | fix(lane2a): remediate quality gate failures - replace placeholders, enforce timeouts, fix CI |
| `b4f6910` | fix(lane2a): fix CI endpoint test failures - week_summary->week, add get_db override and test activities |
| `55369fc` | fix(lane2a): replace AST trigger tests with runtime integration, rename test 22b |
| `95458b3` | fix(lane2a): remove broad except in trigger tests 24/25b, assert post-enqueue behavior |

**What shipped:**
- `apps/api/services/home_briefing_cache.py` — Redis cache with staleness model (15m fresh / 60m stale max)
- `apps/api/tasks/home_briefing_tasks.py` — Celery task for async briefing generation with deduplication, cooldown, circuit breaker
- `apps/api/routers/home.py` — cache-first logic behind `lane_2a_cache_briefing` feature flag
- `apps/api/celerybeat_schedule.py` — 15-minute periodic refresh for active athletes
- Regeneration triggers wired at: check-in, activity sync, plan creation, intelligence write
- Admin refresh endpoint: `POST /v1/home/admin/briefing-refresh/{athlete_id}` (admin/owner only, audit-logged)
- 42 tests covering cache states, deduplication, circuit breaker, provider timeouts, triggers (runtime integration), admin auth, schema contract

**Production results (flag-enable gate PASSED):**
| Endpoint | Pre-flag p95 | Post-flag p95 | Delta |
|----------|-------------|--------------|-------|
| `/v1/home` | 13.05s | 1.98s | -11.07s (6.6x faster) |
| `/health` | 0.080s | 0.089s | no regression |
| `/v1/auth/login` | — | 0.411s | baseline captured |

**Feature flag state:**
- Key: `lane_2a_cache_briefing`
- `enabled=True`, `rollout_percentage=0`, `allowed_athlete_ids=['4368ec7f-c30d-45ff-a6ee-58db7716be24']`
- Founder-only scope

## Current production state

- **Branch:** `main` at `95458b3`
- **Droplet:** 2 vCPU / 4GB, all 6 containers healthy
- **CI:** Run `22159450543` — all 8 jobs green
- **Feature flag:** `lane_2a_cache_briefing` enabled for founder only

## Immediate next steps (in order)

### 1. Stability soak (24-48h, no code changes)
- Monitor `/v1/home` p95/p99 under real usage
- Watch Celery queue depth, task success/failure/timeout rates
- Watch cache hit/stale/missing ratios
- Alert threshold: p95 > 2s sustained
- If degraded: disable flag via DB + flush Redis cache key

### 2. Increase p95 confidence margin
- Current margin is only 18ms (1.982s vs 2.000s contract)
- Rerun latency with 50-100 request sample after soak period
- If margin insufficient, begin Lane 2B (non-LLM compute optimization in `/v1/home`)

### 3. UX correctness verification
- Confirm `briefing_state` transitions: `missing` -> `refreshing` -> `fresh`
- Confirm briefing content appears on subsequent page loads after Celery task completes
- Verify frontend handles all `briefing_state` values gracefully

### 4. Controlled rollout expansion
- After soak: add 2-3 beta testers to `allowed_athlete_ids`
- After beta: increase `rollout_percentage` in stages (25% -> 50% -> 100%)
- At each stage: measure p95 and error rate before proceeding

### 5. Post-rollout hardening
- Dashboard + runbook for Lane 2A (symptoms, checks, rollback steps)
- Lane 2B scoping if p95 margin remains tight

## Deferred work (not started this session)

- **Garmin Connect integration** — compliance doc exists (`docs/GARMIN_CONNECT_DEVELOPER_COMPLIANCE.md`), build plan not yet scoped
- **Coach container isolation** — separate `strideiq_coach` container for `/v1/coach/*` routes
- **Lane 2B** — precompute heavy DB aggregates (hero_narrative, coach_noticed, etc.)

## Key documents

- `docs/adr/ADR-065-home-briefing-off-request-path.md` — architecture decision record
- `docs/LANE_2A_ACCEPTANCE_CRITERIA.md` — 42 tests mapped to 12 acceptance criteria
- `docs/FOUNDER_OPERATING_CONTRACT.md` — non-negotiable workflow rules
- `docs/PRODUCT_MANIFESTO.md` — product soul
- `docs/GARMIN_CONNECT_DEVELOPER_COMPLIANCE.md` — Garmin compliance requirements

## Rollback procedure (if needed during soak)

```bash
# On droplet:
docker exec strideiq_api python -c "
from database import SessionLocal
from models import FeatureFlag
db = SessionLocal()
flag = db.query(FeatureFlag).filter_by(key='lane_2a_cache_briefing').first()
flag.enabled = False
db.commit()
print('ROLLBACK: lane_2a_cache_briefing disabled')
db.close()
" && docker exec strideiq_redis redis-cli DEL "flag:lane_2a_cache_briefing"
```
