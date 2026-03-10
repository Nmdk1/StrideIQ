# Session Handoff — February 17, 2026 (SEV-1 Hotfix)

## What happened

A **SEV-1 production outage** occurred: the coach chat was frozen on "Thinking..." and eventually the entire API became unresponsive. Root cause: a single uvicorn worker blocked by a synchronous LLM call with no timeout.

### Incident timeline

1. Coach chat stream hung indefinitely — no timeout, no error event, no done event
2. `/v1/home` endpoint blocked on synchronous Opus/Gemini briefing calls
3. Single uvicorn worker blocked → all endpoints queued → frontend showed infinite loading
4. Hotfix was developed with three iterations to get thread-safety right
5. Initial deploy included `--workers 3` which caused OOM on the 1 vCPU / 2GB droplet
6. Reverted to 1 worker, API recovered

### What was fixed

| File | Change |
|------|--------|
| `apps/api/routers/ai_coach.py` | 120s hard timeout on coach stream, try/except wrapping `_gen()`, SSE `error` and `done` events always emitted |
| `apps/api/routers/home.py` | Split `generate_coach_home_briefing` into DB phase (request thread) + LLM phase (worker thread via `asyncio.to_thread`). 15s `asyncio.wait_for` timeout. `_fetch_llm_briefing_sync` never touches DB. |
| `apps/web/lib/api/services/ai-coach.ts` | 135s client-side idle timeout on SSE stream, `error` event handling, `onDone({ timed_out: true })` |
| `docker-compose.prod.yml` | Reverted back to single worker (was briefly `--workers 3`, caused OOM) |

### Critical lessons (NEVER forget)

1. **Research before writing.** The first two fix attempts introduced regressions (`ThreadPoolExecutor` blocking, `db` session crossing thread boundary) because the code wasn't fully understood before editing. This cost 30+ minutes on a SEV-1.

2. **1 vCPU / 2GB droplet cannot run multiple uvicorn workers.** `--workers 3` caused OOM and brought down the entire API. Never increase workers without upgrading the droplet first.

3. **Every LLM call needs a hard timeout.** SDK-level timeout AND callsite-level `asyncio.wait_for`. A single hung call blocks the only worker.

4. **Never pass `db` to `asyncio.to_thread`.** SQLAlchemy sessions are not thread-safe. Do all DB work on the request thread, pass pure data to the worker thread.

5. **SSE streams must always terminate.** The frontend was stuck because the backend never sent a `done` or `error` event when something went wrong. Every SSE generator must have a try/except that guarantees a terminal event.

## Production state

- **Branch:** `main`
- **Status:** deployed, healthy, single worker
- **Verified:** `/health` returns 200, login works, home loads
- **Risk:** If multiple users trigger LLM calls simultaneously, the single worker can still queue. The timeout ensures requests fail-fast (15s for home, 120s for coach) rather than hanging indefinitely, but only one request is served at a time.

## What needs attention next

1. **Droplet upgrade evaluation** — If user count grows beyond ~3 concurrent, need to move to 2 vCPU / 4GB and then `--workers 2-3`
2. **LLM call queueing/debouncing** — Consider Redis-based deduplication so concurrent identical home briefing requests share one LLM call
3. **Missing table: `athlete_calibrated_model`** — `fitness_bank.py` queries it, migration doesn't exist. Fails gracefully but logs warnings on every `/v1/home`
4. Resume normal build priority: Monetization tier mapping → Phase 4 (50K Ultra) → Phase 3B (when narration gate clears)
