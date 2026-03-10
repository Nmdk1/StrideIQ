# Session Handoff — February 17, 2026 (Session 2)

## Where we left off

Droplet is being resized from 1 vCPU / 2GB to **2 vCPU / 4GB Regular** on Digital Ocean (CPU+RAM only, reversible). Once resize completes, containers auto-restart.

## Exact next steps (in order)

### Step 1: Verify droplet resize
- SSH into droplet, confirm 2 vCPU / 4GB
- Confirm all containers came back up: `docker compose -f docker-compose.prod.yml ps`
- Confirm site is reachable: `curl -s https://strideiq.run/health`

### Step 2: Config-only deploy — `--workers 3`
- **This is a config-only change. No other code changes in this deploy.**
- Capture pre-deploy baseline: latency for `/v1/health`, `/v1/auth/login`, `/v1/home`
- Change `docker-compose.prod.yml` API command to `--workers 3`
- Deploy: `git pull origin main && docker compose -f docker-compose.prod.yml up -d --build api`
- Capture post-deploy checks: same three endpoints, compare latency + success
- Verify login works, home loads, coach responds

### Step 3: Draft Lane 2 scope — home briefing Celery+cache
- **Discuss first. Do not code until founder signs off.**
- Write implementation plan with acceptance criteria + test design
- Architecture: Celery precomputes home briefing → Redis cache → `/v1/home` serves cache instantly
- Staleness: 15 min fresh target, 60 min stale max
- Regeneration triggers: check-in saved, new activity ingested, plan change, race goal update
- Periodic beat refresh every 15 min for active athletes
- If cache miss/stale: enqueue refresh, return deterministic payload without briefing (never block)

### Step 4 (separate mini-project): Coach container split
- Dedicated `strideiq_coach` container for `/v1/coach/*` routes
- Caddy routing isolation so coach latency can't impact core API
- Scoped separately — do not combine with Lane 2

## Agreed architecture (founder + advisor approved)

### Lane 1: Reliability shield (immediate)
- Droplet upgrade to 2 vCPU / 4GB ← IN PROGRESS
- `--workers 3` ← next deploy
- Existing timeouts stay (15s home, 120s coach, 135s frontend idle)
- Hard rule: auth/health/home base payload must never block on LLM

### Lane 2: Remove LLM from hot request paths (real fix)
- Home briefing → Celery + Redis cache (first)
- Other LLM surfaces later (activity moments, progress, insights — only if they're request-time)
- Coach chat stays inline (interactive UX) but gets isolated to its own container

## SEV-1 hotfix already shipped (do not reopen)
- `ai_coach.py`: 120s timeout, try/except, SSE error/done events
- `home.py`: DB on request thread, LLM on worker thread via `asyncio.to_thread` + `asyncio.wait_for`
- `ai-coach.ts`: 135s client idle timeout, error event handling
- `docker-compose.prod.yml`: currently 1 worker (will become 3 after resize)

## Production state
- **Branch:** `main` at commit `0a91ddf`
- **Droplet:** resizing to 2 vCPU / 4GB (in progress)
- **Containers:** will auto-restart after resize
- **Site:** was healthy before resize began

## Garmin Connect Developer Program — APPROVED

Garmin integration is targeted for **this weekend**. Compliance doc: `docs/GARMIN_CONNECT_DEVELOPER_COMPLIANCE.md`.

### Priority order for tomorrow
1. Verify droplet resize (2 vCPU / 4GB) + config-only `--workers 3` deploy
2. Scope Garmin integration build plan (discuss first, no code until sign-off)
3. Scope Lane 2 home briefing Celery+cache

### Garmin key decisions to discuss
- **Consent system**: build unified (Strava + Garmin) or Garmin-only?
- **Build sequence**: consent/privacy first (compliance gate), then provider adapter, then UI attribution
- **Section 15.10 is the hard gate**: no Garmin sync until privacy policy + consent flow + withdrawal mechanism are live
- **30-day display notice**: send proactively for existing visualizations now
- **Section 4.6 write-back**: never push proprietary intelligence to Garmin
- **Adapter pattern**: follows Strava's shape — OAuth, token management, activity sync, map to internal models at boundary

### Reference docs for Garmin work
- `docs/GARMIN_CONNECT_DEVELOPER_COMPLIANCE.md` — contractual obligations
- `docs/GARMIN_API_APPLICATION.md` — application details

## Key constraints (from today's incident)
- Never pass request-scoped `db` session to `asyncio.to_thread`
- Every LLM call needs SDK-level timeout AND callsite-level `asyncio.wait_for`
- SSE streams must always emit a terminal event (done or error)
- Research code AND infrastructure before writing — anti-pattern #7 in Founder Operating Contract
