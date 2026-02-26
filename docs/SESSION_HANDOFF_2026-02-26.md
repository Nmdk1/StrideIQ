# Session Handoff — February 26, 2026

**Date:** February 26, 2026
**Status:** Production healthy. Garmin naming fixed and deployed. All prior features stable.
**Branch:** `main` (latest commit `a6228f1`)
**Prior handoff:** `docs/SESSION_HANDOFF_2026-02-24_STRIPE_AND_GARMIN_REVIEW.md`

---

## Read order before first tool call

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — non-negotiable operating rules
2. `docs/CODEBASE_ORIENTATION.md` — structural facts, shell quirks, friction points (read this early)
3. `docs/PRODUCT_MANIFESTO.md` — the soul of the product
4. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — visual/UX contracts, rejected decisions
5. `docs/RUN_SHAPE_VISION.md` — visual vision for run data
6. `docs/TRAINING_PLAN_REBUILD_PLAN.md` — build priority order and phase gates
7. `docs/SESSION_HANDOFF_2026-02-24_STRIPE_AND_GARMIN_REVIEW.md` — prior session (Stripe, sleep grounding)
8. This document

---

## What happened this session (February 26, 2026)

### 1. Sleep prompt grounding fix — shipped (from prior session, confirmed stable)

All details in prior handoff. 22 tests green. `validate_sleep_claims` live with 0.5h tolerance.

---

### 2. Garmin Activities Missing Splits — shipped (commits `a058c8d` → `227fc1e` → `b58a0b3`)

**Root cause:** Garmin webhook pipeline created `ActivityStream` rows but never created `ActivitySplit` rows. Strava had this right; Garmin never did.

**What shipped:**

**`apps/api/services/garmin_adapter.py`** — new function:
```python
def adapt_activity_detail_laps(raw_detail: Dict[str, Any], samples: list) -> List[Dict[str, Any]]
```
- Sorts laps by `startTimeInSeconds`
- Computes per-lap HR and cadence by filtering `samples` within lap boundaries
- Prioritizes per-lap aggregate fields if present in payload (device may provide them)
- Maps to `ActivitySplit` fields; sets `gap_seconds_per_mile` via Minetti polynomial from elevation + pace
- **Source contract:** no raw Garmin field names ever appear in task layer

**`apps/api/tasks/garmin_webhook_tasks.py`** — `_ingest_activity_detail_item()` refactored:
- Pre-computes `lap_splits` before any early-return check
- Returns early only if *neither* `samples` nor `lap_splits` are present
- `ActivityStream` creation conditional on `samples`; `ActivitySplit` creation conditional on `lap_splits`
- **Idempotency:** delete-then-create pattern (deletes existing `ActivitySplit` for that `activity.id` before inserting)

**GAP computation** (commit `227fc1e`, `b58a0b3`):
- Initially hardcoded `gap_seconds_per_mile = None` as safe default
- Discovered Garmin payloads carry `elevationGain`/`elevationLoss` per lap + pace — sufficient to compute GAP
- Implemented full Minetti polynomial in `garmin_adapter.py`:
  ```python
  grade = net_elevation_m / distance_m
  cmet = 155.4*(grade**5) - 30.4*(grade**4) - 43.3*(grade**3) + 46.3*(grade**2) + 19.5*grade + 3.6
  flat_cmet = 3.6
  gap_pace = actual_pace_spm * (cmet / flat_cmet)
  ```
- Strava GAP uses same polynomial — consistent across both sources

**17 tests** in `apps/api/tests/test_garmin_splits.py` — all passing.

**Live-capture note (still open):** Next real `activityDetails` webhook should be logged to verify actual `laps[]` field names from the device. Adapter degrades gracefully via samples if per-lap aggregate fields are absent.

---

### 3. Garmin backfill — deep backfill shipped (commit `d052e92`)

Multi-window backfill that works around Garmin's 90-day per-request limit:
- Splits the backfill window into 30-day chunks for activities (more reliable)
- 90-day chunks for health endpoints (daily summaries, sleep, body composition)
- Retry logic for 429 rate limiting
- `resp.text` logged on non-202 responses for debugging

**File:** `apps/api/services/garmin_backfill.py`

---

### 4. Garmin Connect naming fix — shipped (commit `a6228f1`, deployed)

**Context:** Garmin Connect Developer Program (Elena Kononova, Partner Services) reviewed the app and requested consistent use of "Garmin Connect" (not "Garmin" alone) in user-facing text.

**24 strings fixed across 7 files:**

| File | Changes |
|------|---------|
| `apps/web/components/integrations/GarminConnectButton.tsx` | Button text + 2 aria-labels |
| `apps/web/components/integrations/GarminConnection.tsx` | 2 error messages, push API description, export ZIP prompt |
| `apps/web/components/integrations/GarminFileImport.tsx` | Section header, subtitle, empty state |
| `apps/web/components/integrations/StravaConnection.tsx` | Strava capacity fallback message |
| `apps/web/app/onboarding/page.tsx` | Sleep source option label, watch connect description, button text |
| `apps/web/app/coach/page.tsx` | Baseline banner |
| `apps/web/app/privacy/page.tsx` | 8 instances throughout |

**Acceptable as-is (do not change):**
- Code comments, variable names, import paths — not user-facing
- `terms/page.tsx`: "Garmin and the Garmin logo are trademarks of Garmin Ltd." — correct legal language
- `terms/page.tsx`: "Garmin Terms of Use", "Garmin Privacy Policy" — official document names

**Deployed:** `a6228f1` is live on production. Site returns 200. All containers healthy.

---

## Current production state

| Item | Status |
|------|--------|
| Droplet | `root@strideiq.run`, commit `a6228f1` |
| API | `strideiq_api` healthy |
| Web | `strideiq_web` healthy |
| Worker | `strideiq_worker` healthy |
| Postgres | `strideiq_postgres` healthy |
| Redis | `strideiq_redis` healthy |
| Caddy | `strideiq_caddy` running |
| Stripe | Live — `prod_U2XZC71b1B6nxX`, monthly `price_1T4SUtLRj4KBJxHa4sq8e35A`, annual `price_1T4SUuLRj4KBJxHat0sHVdrw` |
| Garmin | Founder connected, webhooks flowing, feature flag `garmin_connect_enabled` at rollout 0% / allowlist: founder + father |
| Home briefing p95 | 1.98s (SLO: < 2s) ✅ |
| Sleep grounding | Live — validator + SLEEP SOURCE CONTRACT |
| ActivitySplit (Garmin) | Live — laps + GAP from Minetti polynomial |
| Garmin partner review | **In progress** — Elena Kononova, Garmin Connect Partner Services. Awaiting approval. Naming fix now deployed. |

---

## Open items (priority order)

### Immediate / In-flight

1. **Garmin partner approval** — Elena Kononova is reviewing
   - Naming fix is now deployed (her specific feedback addressed)
   - She may request additional changes — monitor email
   - When approved: flip `garmin_connect_enabled` rollout from 0% to 100%

2. **Garmin splits live-capture schema check**
   - When next real `activityDetails` webhook arrives, log and inspect `raw_item["laps"]` field names
   - Confirm adapter assumptions match actual device payload
   - File: `apps/api/services/garmin_adapter.py` — patch mapping if field names differ
   - Low urgency — adapter already degrades gracefully via samples fallback

### Next build priority (per `docs/TRAINING_PLAN_REBUILD_PLAN.md`)

**Build these in order:**

1. **Monetization tier gating** — Stripe infrastructure is live. 29 xfail contract tests waiting.
   - Free / One-time ($5) / Guided ($15/mo) / Premium ($25/mo)
   - Gate: Phases 1-2 complete ✅
   - Start here. Revenue unlock.

2. **Phase 4 — 50K Ultra** — 37 xfail contract tests
   - New primitives: back-to-back long runs, time-on-feet, RPE zones, nutrition, strength
   - Gate: Phases 1-2 complete ✅
   - New model fields + migration required

3. **Phase 3B — Contextual workout narratives**
   - Code complete, gate accruing
   - Gate: narration accuracy > 90% for 4 consecutive weeks
   - Monitor: `/v1/intelligence/narration/quality`

4. **Phase 3C — N=1 personalized insights**
   - Code complete, gate accruing
   - Gate: 3+ months data + significant correlations (founder rule: immediate if history exists)

### Compliance (Garmin — still open)

- 30-day data display notice screenshots — send to Garmin Connect developer portal
- ToS: review for Garmin-protective liability language
- Document breach notification procedure (72h GDPR requirement)

---

## Infrastructure

### Droplet
- **Host:** `root@strideiq.run`
- **Repo path:** `/opt/strideiq/repo`
- **Deploy:**
  ```bash
  cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
  ```

### Generate auth token (on droplet, no password needed)
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

### Stripe (live mode)
- **Account:** `acct_1T4SGOLRj4KBJxHa`
- **Webhook:** `we_1T4StVLRj4KBJxHaMH3qURqm` → `https://strideiq.run/v1/billing/webhooks/stripe`
- **Events:** `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`

---

## Key file map

| File | Role |
|------|------|
| `apps/api/routers/home.py` | Home briefing pipeline, sleep grounding, `validate_sleep_claims` |
| `apps/api/tasks/home_briefing_tasks.py` | Celery async briefing task |
| `apps/api/services/garmin_adapter.py` | All raw Garmin field translation — `adapt_activity_detail_laps` |
| `apps/api/tasks/garmin_webhook_tasks.py` | Garmin webhook processing, `_ingest_activity_detail_item` |
| `apps/api/services/garmin_backfill.py` | Multi-window historical backfill |
| `apps/api/routers/garmin.py` | Garmin OAuth, disconnect (deletes ActivitySplit before Activity) |
| `apps/api/routers/billing.py` | Stripe checkout, webhooks, customer portal |
| `apps/api/models.py` | ORM: `Athlete`, `Activity`, `ActivitySplit`, `ActivityStream`, `GarminDay`, `DailyCheckin`, `Subscription` |
| `apps/api/tests/test_sleep_prompt_grounding.py` | 22 tests for sleep grounding |
| `apps/api/tests/test_garmin_splits.py` | 17 tests for Garmin splits + GAP |
| `apps/web/components/integrations/GarminConnectButton.tsx` | Garmin OAuth button (aria-label + span both say "Connect with Garmin Connect") |
| `apps/web/components/integrations/GarminConnection.tsx` | Garmin settings panel |
| `docs/BUILDER_NOTE_2026-02-25_GARMIN_SPLITS_GAP.md` | Full spec for the splits implementation |
| `docs/BUILDER_NOTE_2026-02-24_SLEEP_PROMPT_GROUNDING_V2.md` | Full spec for sleep grounding |

---

## Enforced contracts — do not violate

- **Sleep validator tolerance:** 0.5h — intentionally lenient. Do not tighten without founder sign-off.
- **Garmin adapter source contract:** No raw Garmin field names in task layer. All translation in `garmin_adapter.py`.
- **ActivitySplit delete order:** Must delete `ActivitySplit` before `Activity` in any cascade delete (FK constraint). See `apps/api/routers/garmin.py`.
- **Athlete Trust Safety Contract:** Efficiency interpretation — see `n1_insight_generator.py`. System informs; athlete decides. Never override.
- **119 xfail contract tests:** `test_monetization_tiers.py`, `test_phase_3b_*.py`, `test_phase_3c_*.py`, `test_phase_4_*.py` — these become real tests when gates clear. Do not delete them.
- **Scoped commits only:** Never `git add -A`. Stage only the files you touched.
- **No template narratives:** If you can't say something contextual, say nothing.
- **Do not re-propose** anything in `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` marked as rejected.
- **Stripe prices:** Do not change price IDs or product without founder sign-off.
- **Feature flag allowlist:** Do not modify `garmin_connect_enabled` allowlist without founder instruction.

---

## Session commits

| Commit | Description |
|--------|-------------|
| `a058c8d` | feat(garmin): create ActivitySplit rows from webhook activity detail laps |
| `67fbe6d` | fix(garmin): derive splits from samples when laps are missing |
| `9bf5b55` | temp: add Garmin payload capture for GAP field discovery |
| `227fc1e` | fix(garmin): compute GAP from elevation + pace instead of hardcoding None |
| `7fdc387` | fix(garmin): derive split distance/duration from samples when lap fields absent |
| `b58a0b3` | fix(pace): use full Minetti polynomial for NGP instead of broken quadratic |
| `d052e92` | feat(garmin): add deep backfill with multi-window support for historical data |
| `b030c57` | fix(tests): update garmin split tests for computed GAP values |
| `a6228f1` | fix(garmin): use 'Garmin Connect' consistently per partner requirements |

---

## State at handoff

Tree is clean. Tests green (run `pytest apps/api/tests/ -x -q` on droplet to verify). Production healthy at `https://strideiq.run`. Garmin partner review in progress — next action is awaiting Elena's response.

The next builder's first task should be **Monetization tier gating** — Stripe is wired, the xfail contracts are waiting, and that's the revenue unlock.
