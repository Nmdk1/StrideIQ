# Advisor Brief — Handoff Letter to Next Opus Agent

**From:** Opus agent (session ended Feb 24–25, 2026)
**To:** Next Opus agent
**Date:** February 25, 2026
**Session type:** Infrastructure + Critical Bug Fixes + Documentation wrap

---

## Read this in order before your first tool call

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — **non-negotiable**, read every word
2. `docs/PRODUCT_MANIFESTO.md` — the soul of the product
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — rejected decisions live here, do not re-propose
4. `docs/RUN_SHAPE_VISION.md` — visual vision for run data
5. `docs/SITE_AUDIT_LIVING.md` — current state of every system
6. `docs/SESSION_HANDOFF_2026-02-24_STRIPE_AND_GARMIN_REVIEW.md` — what happened in the last session
7. `docs/TRAINING_PLAN_REBUILD_PLAN.md` — build priority order
8. `docs/AGENT_WORKFLOW.md` — your build loop mechanics

Do not skip step 1 and jump to code. The founder will catch it. It is fatal to the session.

---

## Who you are working with

**The founder is Mahmoud.** He is a serious endurance athlete, a former competitive runner, and an engineer who has built production systems. He thinks clearly under pressure and has strong intuitions about product quality. He does not want to be managed — he wants a capable partner who does the research and then has an opinion.

**How he communicates:**
- Terse during action phases ("ok", "yes", "go")
- Precise when something is wrong — he will tell you exactly what you got wrong
- Pays close attention to whether you read his prior corrections before your next move
- Does not tolerate rework caused by an agent who didn't read the contract

**What earns trust:**
- Citing specific numbers, specific file paths, specific commit hashes — not claims
- Saying "I don't know" rather than hallucinating
- Completing session documentation before claiming the session is done
- Staying in your lane (do not touch Strava sync, design decisions, or infrastructure without being asked)

**What destroys trust:**
- Writing code before being asked to
- Ignoring a correction and repeating the same mistake
- Fabricating test results or citing approximate code
- Opening a new feature without finishing documentation from the last one

---

## What was accomplished this session

### Stripe — Fully live in production

Stripe is the billing backbone. All infrastructure was built from scratch in this session.

**Account:** `acct_1T4SGOLRj4KBJxHa`

| Item | Value |
|---|---|
| Product | StrideIQ Pro (`prod_U2XZC71b1B6nxX`) |
| Monthly price | $14.99/mo (`price_1T4SUtLRj4KBJxHa4sq8e35A`) |
| Annual price | $149.00/yr (`price_1T4SUuLRj4KBJxHat0sHVdrw`) |
| Webhook endpoint | `https://strideiq.run/v1/billing/webhooks/stripe` |
| Webhook secret | `whsec_d14No78S0mZ8AAYubytWQS7tlBJFihvq` (in prod `.env`) |
| Webhook dest ID | `we_1T4StVLRj4KBJxHaMH3qURqm` |
| Customer Portal | Configured in Stripe Dashboard (live mode) |
| Events | `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted` |

**What this unlocks:** The billing flow is complete. Checkout session → Stripe hosted checkout → webhook → `Subscription` table + `athlete.subscription_tier` flips to `pro`. The **next build task** is tier-gating features behind `subscription_tier`.

**DO NOT** create new Stripe prices or modify the product ID without founder sign-off. The IDs are locked in production `.env` and `.env.example`.

---

### Garmin disconnect bug — Fixed (commit `9b11504`)

`POST /v1/garmin/disconnect` was crashing with 500 for any account that had Garmin activity data.

Root cause: `activity_split` FK constraint on `activity.id`. Disconnect handler was deleting `ActivityStream` → `Activity` but skipping `ActivitySplit`, causing PostgreSQL to reject the `Activity` deletion.

Fix: `apps/api/routers/garmin.py` — import `ActivitySplit`, delete in order:
1. `ActivityStream`
2. `ActivitySplit` (added)
3. `Activity`

Tested in production. Founder disconnected and reconnected successfully.

---

### Garmin partner review — Elena Kononova (in progress)

Garmin Connect Partner Program is reviewing StrideIQ for authorization to use the push API in production.

Elena Kononova (`Elena Kononova <elena.kononova@garmin.com>`) is the contact. She has requested screenshots of the authorization flow.

**Status:** Screenshots sent twice (embedded inline + attached). Awaiting approval. No timeline given.

**What you may NOT do** without founder instruction:
- Contact Elena directly
- Change the Garmin Connect integration (auth flow, scopes, data handling)
- Roll out `garmin_connect_enabled` feature flag to more users

**What Garmin still needs (compliance checklist, from prior handoff):**
- 30-day advance notice display for data deletion — screenshots still owed to Elena
- ToS review for Garmin-protective liability language
- Breach notification procedure documentation

**Feature flag state:** `rollout: 0%`, allowlist: founder (mbshaf@gmail.com) + father.

---

### Sleep prompt grounding — Fixed (commit `494b9e9`)

This was the highest-severity trust issue in production: the AI morning coach was citing the wrong sleep number.

**Scenario:** Athlete slept 6h45 (Garmin device). Manually entered 7.0h on slider. Coach said "7.5h sleep last night." This erodes trust immediately.

**Three root causes, all fixed:**

1. **`sleep_h` numeric was absent from prompt** — only `sleep_label` ("Great") was passed. LLM had no hours, borrowed from historical context. Fix: new `_build_checkin_data_dict()` helper that includes `sleep_h`.

2. **Wellness trends had no temporal grounding** — `"Sleep avg 7.2h (trend: improving)"` looked identical to a "last night" value. Fix: `get_wellness_trends` now prefixes `"Most recent entry (YYYY-MM-DD): sleep=X.Xh …"`.

3. **Garmin device sleep was never in the prompt** — `GarminDay.sleep_total_s` is the highest-fidelity source (raw device, no rounding) and was completely absent. Fix: new `_get_garmin_sleep_h_for_last_night()` queries `GarminDay` by wakeup day (today → yesterday fallback).

**Calendar date semantics (critical for Garmin):** `GarminDay.calendar_date` is the *wakeup* day by Garmin's convention. Monday night's sleep has `calendar_date = Tuesday`. Query for today first, fall back to yesterday if not yet pushed (common before 6am sync).

**SLEEP SOURCE CONTRACT** (now in prompt — do NOT remove or weaken):
```
SLEEP SOURCE CONTRACT:
- TODAY_CHECKIN_SLEEP_HOURS: {sleep_h}h (athlete-reported, from slider)
- GARMIN_LAST_NIGHT_SLEEP_HOURS: {garmin_h}h (device-measured, highest fidelity)
- When citing last night's sleep, use GARMIN value if available, else TODAY_CHECKIN value.
- Do NOT synthesize or average these values. Do NOT cite historical wellness averages as "last night."
```

**Validator:** `validate_sleep_claims()` — scoped to sleep-context sentences, 0.5h tolerance, suppresses `morning_voice` to safe fallback if deviation detected. Do NOT tighten the tolerance without founder sign-off — 0.5h is intentional (accounting for HRV sleep staging margin).

**22 tests in `apps/api/tests/test_sleep_prompt_grounding.py`** — all passing. These are regression tests. If any fail, do not merge.

**See:** `docs/BUILDER_NOTE_2026-02-24_SLEEP_PROMPT_GROUNDING.md` for full details.

---

### Garmin backfill — Still broken (not touched this session)

`request_garmin_backfill_task` returns 400/429 for all endpoints. This was diagnosed in the prior session (`docs/SESSION_HANDOFF_2026-02-22_GARMIN_LIVE.md`) but not fixed yet.

**Required fixes (from prior diagnosis):**
1. Add `resp.text` logging for non-202 responses — currently logging `resp.status_code` only
2. Use **30-day range** for activities/activityDetails (not 90 — Garmin rejects > 30d ranges)
3. Use **90-day range** for health endpoints (HRV, sleep, stress — these allow 90d)
4. Add 429 retry logic with exponential backoff
5. File: `apps/api/services/garmin_backfill.py`

This is the first build task for the next session — the founder is waiting on Garmin historical data for their training analysis.

---

## Infrastructure: what is and isn't running

| Service | Status | Notes |
|---|---|---|
| API (`strideiq_api`) | Healthy | 1 uvicorn worker — do NOT increase |
| Web (`strideiq_web`) | Healthy | Next.js 14 |
| DB (`strideiq_postgres`) | Healthy | TimescaleDB on PostgreSQL 16 |
| Redis (`strideiq_redis`) | Healthy | Celery broker + cache |
| Worker (`strideiq_worker`) | Healthy | Celery — all async tasks |
| Caddy (`strideiq_caddy`) | Healthy | TLS, HTTPS proxy |

**Hard infrastructure rules (burn these into memory):**
- 1 vCPU, 2GB RAM droplet. **Never increase uvicorn workers above 1.** This OOM'd the entire API on Feb 17 and took it down.
- All LLM calls must have both SDK-level AND `asyncio.wait_for` timeouts. A single hung LLM call kills the only uvicorn worker.
- Never pass a request-scoped SQLAlchemy `db` session to `asyncio.to_thread`. DB on request thread, pure data to the worker thread.
- Home page `/v1/home` must never block on LLM. If LLM times out, return `coach_briefing=None`.
- Deploy downtime is real (30s–5min on `docker compose up -d --build`). Do not deploy during a demo.

---

## Build priority order for next session

Per `docs/TRAINING_PLAN_REBUILD_PLAN.md`:

### Immediate (unblocked)

1. **Garmin backfill fix** — `apps/api/services/garmin_backfill.py`
   - 30-day range for activities, 90-day for health endpoints
   - Add `resp.text` logging
   - Add 429 retry logic
   - This unblocks: historical data, training plan quality, correlation engine

2. **Monetization tier gating** — Stripe infrastructure is live, now build the gating logic
   - 29 xfail contract tests will become real tests
   - Gate features behind `athlete.subscription_tier`
   - Free tier: home briefing, basic insights
   - Pro tier ($14.99/mo): AI coach, advanced analysis, training plan

3. **Phase 4 (50K Ultra training plan)** — 37 xfail contract tests ready
   - Build only after tier gating is complete (monetization unlocks this)

### Gated (do not build yet)

4. **Phase 3B** — narration accuracy gate (> 90% for 4 weeks). Monitor `/v1/intelligence/narration/quality`.
5. **Phase 3C** — per-athlete synced history + significant correlations (founder rule: immediate if 3+ months history exists and correlations are significant).

### When Garmin approval comes

6. **Feature flag rollout** — increase `garmin_connect_enabled` rollout percentage
7. **Host migration** — move to larger droplet. Decision deferred until Garmin approval + backfill stable 24h+.

---

## Key files you will definitely touch

| File | Why you'll be there |
|---|---|
| `apps/api/services/garmin_backfill.py` | Backfill fix — first task |
| `apps/api/routers/billing.py` | Tier gating implementation |
| `apps/api/services/stripe_service.py` | Tier gating integration |
| `apps/api/models.py` | `Subscription` model, `athlete.subscription_tier` |
| `apps/api/routers/home.py` | If any home briefing work is needed |

## Key files you must NOT touch without explicit founder instruction

| File | Reason |
|---|---|
| `apps/api/routers/home.py` (validator section) | Sleep validator is live; tolerance tuning requires founder sign-off |
| `apps/api/services/coach_tools.py` (SLEEP SOURCE CONTRACT) | Contract is live; do not weaken or remove |
| `apps/api/routers/garmin.py` (disconnect handler) | Just fixed; leave it |
| `apps/web/` (any UI component) | Design decisions are locked in `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` |
| Feature flag `garmin_connect_enabled` | Partner review pending |

---

## Stripe MCP (you have access to this)

The Cursor Stripe plugin is installed and authenticated. Verify with `list_products` before assuming it's available in your session — the MCP server sometimes needs to be reloaded (`Ctrl+Shift+P` → "Reload MCP Servers").

---

## Operational reminders

**Committing code:**
- PowerShell git commits require escaping: use `git commit -m "message\`n\`ndetail"` format, or write the message to a temp file first
- **Never `git add -A`** — scoped commits only, enumerate files explicitly
- Always verify with `git status` + `git diff --staged` before committing

**Checking production logs:**
```
docker logs strideiq_api --tail=50
docker logs strideiq_worker --tail=50
```
Container name is `strideiq_api`, NOT `api` — the wrong name returns "no such container".

**Deploying:**
```bash
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
```

**Generating auth token (on droplet):**
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

---

## The founder's preferred working style (what kept this session healthy)

1. **He gives terse approval and then disappears** — "ok", "yes", "go". When this happens, execute precisely what was agreed. Don't expand scope.

2. **He gives very specific corrections.** When he says "The statement X is not accurate," he means exactly that. Do not rephrase your error — just accept the correction and incorporate it.

3. **He tracks documentation quality.** He asked for the advisor letter because he pays for the context window and wants the next agent to hit the ground running without re-diagnosing everything. Take this seriously — a vague letter wastes his money.

4. **He goes to sleep and expects the next session to continue.** Treat the session handoff and this letter as the primary product of your session. Tree clean, tests green, production healthy — then handoff.

5. **He appreciates directness.** "I don't know" is better than "possibly/perhaps/might." He knows the difference.

---

## Current production URL

`https://strideiq.run`

Founder account: `mbshaf@gmail.com`
Droplet: `root@strideiq.run`
Repo path: `/opt/strideiq/repo`
