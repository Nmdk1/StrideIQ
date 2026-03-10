# Phase 1: Consent Infrastructure — Acceptance Criteria & Test Design

**Status:** DRAFT — Awaiting founder sign-off before build
**Purpose:** Clear Blocker 0 for Garmin integration; fix existing inference disclosure gap for Strava data
**Branch:** `main` (this is application infrastructure, not Garmin-specific code)

---

## Guiding Principles

1. **No AI request leaves the backend without `has_ai_consent == True`.** Default deny.
2. **StrideIQ does not train models.** It uses third-party inference APIs (Google Gemini, Anthropic Claude). Under current provider API terms (verified February 2026: [Google paid API policy](https://ai.google.dev/gemini-api/docs/billing), [Anthropic API data usage](https://privacy.anthropic.com/en/articles/7996868-is-my-data-used-for-model-training)), neither provider trains on paid API data. **Review cadence: quarterly.** If provider terms change, update privacy policy immediately and evaluate whether a new consent cycle is needed.
3. **Consent is opt-in.** Explicit affirmative action required. Silence is not consent.
4. **Withdrawal prevents new dispatches immediately.** No new AI requests are dispatched after revocation. Queued/background tasks check consent at execution time and skip if revoked. Already-dispatched outbound calls to LLM providers are not cancelable mid-flight — if a response returns from a call dispatched before revocation, it may be cached/served (the user consented when it was dispatched), but no new calls will be made. This is an acceptable edge case; attempting to abort in-flight HTTP requests is impractical and unreliable.
5. **The product works without AI.** Deterministic surfaces (charts, metrics, calendar, splits, pace data, training load) remain fully functional. AI surfaces degrade gracefully to silence or metric-only display. Users who decline consent experience a functional product with no dead-end loops or error states.

---

## Deliverable Sequence

| # | Deliverable | Ships on `main` |
|---|-------------|----------------|
| P1-A | Privacy policy update (inference disclosure) | Yes |
| P1-B | Consent data model + audit trail | Yes |
| P1-C | Consent UI (capture + withdrawal) | Yes |
| P1-D | LLM pipeline gating (backend enforcement) | Yes |

---

## P1-A: Privacy Policy Update

### What changes

Add an "AI-Powered Insights" section to `/privacy` that discloses:

1. StrideIQ sends athlete training data (activity metrics, health data, training history) to third-party AI services to generate personalized coaching insights.
2. The providers are Google (Gemini) and Anthropic (Claude), accessed via paid API tiers.
3. StrideIQ does not train AI models on athlete data.
4. Under current provider API terms, neither Google nor Anthropic uses paid API data to train their models.
5. Users can withdraw AI processing consent at any time via Settings, which immediately stops all AI processing of their data.
6. All non-AI features continue to work without consent.

### What does NOT change

The existing statement "We do NOT use your data to train AI models" stays. It's accurate.

### Acceptance Criteria

| ID | Criterion |
|----|-----------|
| A1 | `/privacy` page contains an "AI-Powered Insights" section |
| A2 | Section names the specific providers (Google Gemini, Anthropic Claude) |
| A3 | Section states StrideIQ does not train models on athlete data |
| A4 | Section states providers do not train on paid API data under current terms, with citation date (February 2026) |
| A5 | Section describes what data is sent (activity metrics, health data, training context) |
| A6 | Section describes why (personalized coaching, insights, narratives) |
| A7 | Section states consent can be withdrawn at any time via Settings |
| A8 | Section states non-AI features continue without consent |

---

## P1-B: Consent Data Model + Audit Trail

### Database changes

**New fields on `Athlete` model:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ai_consent` | `Boolean` | `False` | Whether athlete has granted AI processing consent |
| `ai_consent_granted_at` | `DateTime(tz)` | `null` | Timestamp of most recent consent grant |
| `ai_consent_revoked_at` | `DateTime(tz)` | `null` | Timestamp of most recent consent revocation |

**New table: `consent_audit_log`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | `UUID` PK | |
| `athlete_id` | `UUID` FK | |
| `consent_type` | `Text` | `ai_processing` (extensible for future types) |
| `action` | `Text` | `granted` or `revoked` |
| `ip_address` | `Text` | Client IP at time of action |
| `user_agent` | `Text` | Client user agent |
| `source` | `Text` | Where consent was captured: `onboarding`, `settings`, `consent_prompt`, `admin` |
| `created_at` | `DateTime(tz)` | |

### Acceptance Criteria

| ID | Criterion |
|----|-----------|
| B1 | Alembic migration adds `ai_consent`, `ai_consent_granted_at`, `ai_consent_revoked_at` to `athlete` table |
| B2 | Migration creates `consent_audit_log` table with all specified columns |
| B3 | All existing athletes have `ai_consent = False` after migration (default deny) |
| B4 | `has_ai_consent(athlete_id, db)` function returns `True` only when `ai_consent == True` |
| B5 | Granting consent sets `ai_consent = True`, `ai_consent_granted_at = now()`, clears `ai_consent_revoked_at` |
| B6 | Revoking consent sets `ai_consent = False`, `ai_consent_revoked_at = now()`, preserves `ai_consent_granted_at` |
| B7 | Every grant/revoke writes a row to `consent_audit_log` with athlete_id, action, ip, user_agent, source |
| B8 | `GET /v1/consent/ai` returns `{ "ai_consent": bool, "granted_at": timestamp|null, "revoked_at": timestamp|null }` |
| B9 | `POST /v1/consent/ai` with `{ "granted": true }` grants consent; `{ "granted": false }` revokes |
| B10 | Consent endpoints require authentication |

---

## P1-C: Consent UI

### Existing user prompt (consent capture)

When an existing user loads any page and `ai_consent == False`:

1. A full-screen, single-action prompt appears (not a modal over content — a dedicated screen).
2. Copy explains: StrideIQ uses AI to generate coaching insights. Your data is sent to secure AI services for processing, never for model training. [Link to privacy policy]
3. Single primary button: **"Enable AI Insights"** — grants consent in one tap.
4. Secondary dismiss link: **"Not now"** — closes prompt, AI features remain off.
5. Prompt reappears once per browser session (new `sessionStorage` scope — i.e., after browser is fully closed and reopened). Does NOT reappear on page refresh or navigation within the same browser session.
6. Not nagging — dismissable, no countdown, no dark pattern.

### Onboarding integration

Add a consent step to the onboarding wizard (after `goals`, before `complete`):

1. Same copy as the existing-user prompt.
2. Same single-action grant.
3. Skippable — athlete can proceed without consenting.
4. If skipped, `ai_consent` stays `False`, product works without AI.

### Settings withdrawal

Add an "AI Processing" section to `/settings`:

1. Toggle: "Allow AI-powered insights" — on/off.
2. When toggled off: confirmation dialog explaining what stops working (coach chat, morning briefing, activity moments, progress headlines).
3. Revocation takes effect immediately — no "changes take effect next session."
4. When toggled on: grants consent (same as prompt).

### Graceful degradation (when `ai_consent == False`)

| Surface | With consent | Without consent |
|---------|-------------|-----------------|
| Home briefing | AI-generated coaching briefing | `coach_briefing: null`, `briefing_state: "consent_required"` |
| Coach chat | Full AI coaching conversation | Message: "Enable AI insights to use the coach" |
| Activity moments | AI-narrated moments | Metric-only labels (fallback already exists) |
| Workout narratives | AI-generated narrative | No narrative shown |
| Adaptation narratives | AI-generated narrative | No narrative shown |
| Progress headlines | AI-generated headline | No headline shown |
| Progress coach cards | AI-generated coaching cards | Fallback cards (deterministic, no LLM) |
| Morning voice | AI-generated daily insight | Not shown |
| Charts/metrics/calendar/splits/pace/load | Full functionality | Full functionality (no change) |

### Acceptance Criteria

| ID | Criterion |
|----|-----------|
| C1 | Existing user with `ai_consent = False` sees full-screen consent prompt on page load |
| C2 | Clicking "Enable AI Insights" grants consent via `POST /v1/consent/ai` and prompt disappears |
| C3 | Clicking "Not now" dismisses prompt for the current browser session (stored in `sessionStorage`) |
| C4 | Prompt reappears when browser is fully closed and reopened (new `sessionStorage` scope). Does NOT reappear on page refresh within the same browser session. Does NOT persist in `localStorage`. |
| C5 | Onboarding wizard includes consent step after goals |
| C6 | Onboarding consent step is skippable |
| C7 | Settings page has "AI Processing" section with toggle |
| C8 | Settings toggle off triggers confirmation dialog |
| C9 | Settings toggle off revokes consent immediately (no delay) |
| C10 | After revocation, all AI surfaces show graceful degradation (not errors) |
| C11 | After grant, all AI surfaces resume normal function |
| C12 | Frontend consent state is fetched from `GET /v1/consent/ai` on app load |
| C13 | Consent prompt does NOT appear when `ai_consent = True` |
| C14 | User who declines consent can navigate all non-AI surfaces without dead-end loops or error states |

---

## P1-D: LLM Pipeline Gating (Backend Enforcement)

### Contract

`has_ai_consent(athlete_id, db) -> bool` is checked before every AI inference dispatch. If `False`, the call is suppressed and the surface returns its consent-denied fallback. No data leaves the server.

### Call sites requiring gates (8 athlete-facing)

| # | Location | Function | Fallback behavior |
|---|----------|----------|-------------------|
| 1 | `services/ai_coach.py` | `AICoach.chat()` | Return error message directing user to enable AI insights |
| 2 | `routers/home.py` | `_fetch_llm_briefing_sync()` | Return `null` briefing, `briefing_state: "consent_required"` |
| 3 | `tasks/home_briefing_tasks.py` | `generate_home_briefing_task()` | Skip task, log reason |
| 4 | `services/moment_narrator.py` | `_call_narrator_llm()` | Return `None` (existing fallback to metric labels) |
| 5 | `services/workout_narrative_generator.py` | `_call_llm()` | Return `None` |
| 6 | `services/adaptation_narrator.py` | `generate_narration()` | Return `None` |
| 7 | `routers/progress.py` | `_generate_progress_headline()` | Return `None` |
| 8 | `routers/progress.py` | `_generate_progress_cards()` | Return fallback cards (deterministic, no LLM) |

**Not gated:** `services/knowledge_extraction_ai.py` — admin-only, processes knowledge base content not athlete data.

### `briefing_state` contract change

Adding `"consent_required"` to the `BriefingState` enum:
- Current values: `fresh`, `stale`, `missing`, `refreshing`
- New value: `consent_required`
- This is a backend API contract change. The `HomeResponse.briefing_state` field is `Optional[str]`, so adding a new value is backward-compatible (frontend treats unknown values gracefully).
- Frontend consent UI should recognize `consent_required` and display the appropriate prompt/state.

### Kill switch

Global feature flag `ai_inference_enabled` (server-side, in FeatureFlag table):
- When `False`, ALL AI inference is disabled for ALL users immediately.
- Separate from per-user consent — this is an emergency shutoff.
- Checked at the same point as `has_ai_consent`, before dispatch.

### Acceptance Criteria

| ID | Criterion |
|----|-----------|
| D1 | `has_ai_consent(athlete_id, db)` returns `False` for athletes with `ai_consent = False` |
| D2 | `has_ai_consent(athlete_id, db)` returns `False` when global kill switch `ai_inference_enabled` is `False` |
| D3 | Coach chat returns consent-required message when `has_ai_consent` is `False` |
| D4 | Home briefing returns `null` with `briefing_state: "consent_required"` when unconsented |
| D5 | Home briefing Celery task skips execution when unconsented |
| D6 | Moment narrator returns `None` when unconsented |
| D7 | Workout narrative generator returns `None` when unconsented |
| D8 | Adaptation narrator returns `None` when unconsented |
| D9 | Progress headline returns `None` when unconsented |
| D10 | Progress cards return deterministic fallback (no LLM) when unconsented |
| D11 | No LLM API call is made when `has_ai_consent` returns `False` (verified by mock assertion at all 8 call sites) |
| D12 | Kill switch `ai_inference_enabled = False` disables all AI for all users, even those with `ai_consent = True` |
| D13 | Kill switch is checked at dispatch time, not cached |
| D14 | Background tasks (Celery) check consent at execution time, not enqueue time |
| D15 | `BriefingState.CONSENT_REQUIRED` added to enum; `/v1/home` returns this state when `ai_consent = False` |

---

## Test Design

### Category 1: Unit Tests — Consent Data Model (10 tests)

| # | Test | Description |
|---|------|-------------|
| 1 | `test_default_ai_consent_is_false` | New athlete has `ai_consent = False` |
| 2 | `test_grant_consent_sets_fields` | Granting sets `ai_consent = True`, `granted_at = now()`, clears `revoked_at` |
| 3 | `test_revoke_consent_sets_fields` | Revoking sets `ai_consent = False`, `revoked_at = now()`, preserves `granted_at` |
| 4 | `test_grant_creates_audit_log` | Granting writes audit row with action=`granted`, ip, user_agent, source |
| 5 | `test_revoke_creates_audit_log` | Revoking writes audit row with action=`revoked` |
| 6 | `test_has_ai_consent_true_when_granted` | `has_ai_consent` returns `True` when `ai_consent = True` |
| 7 | `test_has_ai_consent_false_when_not_granted` | `has_ai_consent` returns `False` when `ai_consent = False` |
| 8 | `test_has_ai_consent_false_when_kill_switch_off` | Returns `False` even if athlete consented, when kill switch is disabled |
| 9 | `test_regrant_after_revoke` | Grant -> revoke -> grant cycle works correctly |
| 10 | `test_audit_log_captures_all_transitions` | Full cycle produces correct audit trail |

### Category 2: API Endpoint Tests — Consent Endpoints (8 tests)

| # | Test | Description |
|---|------|-------------|
| 11 | `test_get_consent_status_unauthenticated` | Returns 401 |
| 12 | `test_get_consent_status_default` | Returns `{ ai_consent: false, granted_at: null, revoked_at: null }` |
| 13 | `test_post_consent_grant` | POST `{ granted: true }` -> 200, `ai_consent` now `True` |
| 14 | `test_post_consent_revoke` | POST `{ granted: false }` -> 200, `ai_consent` now `False` |
| 15 | `test_post_consent_creates_audit` | POST consent -> audit log row created |
| 16 | `test_get_consent_after_grant` | GET returns updated `granted_at` timestamp |
| 17 | `test_consent_idempotent_grant_still_logs` | Granting when already granted is a no-op on `ai_consent` field, but still creates an audit log row |
| 18 | `test_consent_idempotent_revoke_still_logs` | Revoking when already revoked is a no-op on `ai_consent` field, but still creates an audit log row |

### Category 3: LLM Pipeline Gating Tests (16 tests)

| # | Test | Description |
|---|------|-------------|
| 19 | `test_coach_chat_blocked_without_consent` | Mock athlete with `ai_consent=False`, POST to coach chat -> consent-required message, no LLM call made |
| 20 | `test_coach_chat_allowed_with_consent` | Mock athlete with `ai_consent=True` -> LLM call proceeds |
| 21 | `test_home_briefing_blocked_without_consent` | `/v1/home` with `ai_consent=False` -> `coach_briefing: null`, `briefing_state: "consent_required"` |
| 22 | `test_home_briefing_allowed_with_consent` | `/v1/home` with `ai_consent=True` -> normal briefing behavior |
| 23 | `test_celery_briefing_task_skips_without_consent` | Task called for unconsented athlete -> no LLM call, task returns skip reason |
| 24 | `test_moment_narrator_returns_none_without_consent` | Unconsented -> returns `None`, no LLM call |
| 25 | `test_workout_narrative_returns_none_without_consent` | Unconsented -> returns `None`, no LLM call |
| 26 | `test_adaptation_narrator_returns_none_without_consent` | Unconsented -> returns `None`, no LLM call |
| 27 | `test_progress_headline_returns_none_without_consent` | Unconsented -> returns `None`, no LLM call |
| 28 | `test_progress_cards_returns_fallback_without_consent` | Unconsented -> returns deterministic fallback cards, no LLM call |
| 29 | `test_kill_switch_blocks_all_ai` | Kill switch off -> all 8 surfaces blocked for all athletes |
| 30 | `test_kill_switch_on_allows_consented` | Kill switch on + consent -> AI proceeds |
| 31 | `test_kill_switch_overrides_consent` | Kill switch off + `ai_consent=True` -> all AI blocked (kill switch takes precedence) |
| 32 | `test_no_llm_call_made_when_blocked` | For each of 8 call sites, mock the LLM client and assert `.generate_content()` / `.messages.create()` NOT called |
| 33 | `test_consent_revoke_stops_background_tasks` | Grant -> enqueue briefing task -> revoke -> task executes -> no LLM call (checks at execution time) |
| 34 | `test_knowledge_extraction_not_gated` | Admin knowledge extraction still works regardless of consent (not athlete-facing) |

### Category 4: Integration Tests — Graceful Degradation (8 tests)

| # | Test | Description |
|---|------|-------------|
| 35 | `test_home_page_loads_without_consent` | Full `/v1/home` response is valid JSON with all deterministic fields intact, AI fields null |
| 36 | `test_home_page_briefing_state_consent_required` | `briefing_state` is `"consent_required"` when unconsented |
| 37 | `test_activity_detail_loads_without_consent` | Activity page returns metrics, splits, charts — moments have no narratives |
| 38 | `test_progress_page_loads_without_consent` | Progress page returns data, no headline, cards are deterministic fallback |
| 39 | `test_consent_then_full_functionality` | Grant consent -> all AI surfaces return non-null on next request |
| 40 | `test_revoke_then_graceful_degradation` | Revoke consent -> all AI surfaces return null/fallback immediately |
| 41 | `test_consent_prompt_hidden_when_consented` | User with `ai_consent = True` loads page — no consent prompt rendered |
| 42 | `test_unconsented_user_no_dead_ends` | User who declines consent can navigate home, activities, progress, settings without error states or redirect loops |

### Category 5: Migration Tests (4 tests)

| # | Test | Description |
|---|------|-------------|
| 43 | `test_migration_adds_ai_consent_fields` | Alembic migration adds all 3 fields to athlete table |
| 44 | `test_migration_creates_consent_audit_log` | Migration creates table with correct schema |
| 45 | `test_existing_athletes_default_false` | After migration, all existing athletes have `ai_consent = False` |
| 46 | `test_migration_reversible` | Downgrade removes fields and table cleanly |

---

## Total: 46 tests across 5 categories

| Category | Count |
|----------|-------|
| Unit — consent data model | 10 |
| API — consent endpoints | 8 |
| LLM pipeline gating | 16 |
| Integration — graceful degradation | 8 |
| Migration | 4 |
| **Total** | **46** |

---

## Existing User Migration

**Approach:** Option B (hard gate / opt-in) with graceful degradation.

- All existing athletes get `ai_consent = False` after migration.
- On next app load, full-screen consent prompt appears.
- Single tap to consent. Dismissable.
- AI features are off until consent is granted.
- All non-AI features continue working.
- Prompt reappears once per session until consented.

---

## Rollout Plan

1. Ship P1-A (privacy policy) to production first.
2. Ship P1-B (data model + migration) — all users get `ai_consent = False`.
3. Ship P1-C (consent UI) — users can now grant consent.
4. Ship P1-D (LLM gating) — enforcement activates.

Steps 2-4 should ship together in a single deploy to avoid a window where the migration runs but the UI to grant consent doesn't exist yet.

**Partial deploy failure mitigation:** If the migration runs (all users get `ai_consent = False`) but the consent UI or gating code fails to deploy, all AI is dead and no one can fix it via the UI. The kill switch doesn't help — toggling it ON would bypass consent, which is worse. Have a rollback script ready that reverses the migration by setting `ai_consent = True` for all existing athletes (restoring the pre-migration implicit state). This is a one-time safety net, not permanent architecture.

```sql
-- Emergency rollback: restore pre-migration implicit consent
-- USE ONLY WITH EXPLICIT FOUNDER APPROVAL during outage mitigation.
-- This is a compliance exception path — not a routine operation.
UPDATE athlete SET ai_consent = TRUE WHERE ai_consent = FALSE;
```

---

## Kill Switch

- Feature flag key: `ai_inference_enabled`
- Default: `True` (AI is on for consented users)
- When `False`: ALL AI inference disabled for ALL users immediately
- Checked at dispatch time alongside `has_ai_consent`
- Server-side only — no deploy required to toggle

### Provider Terms Review Cadence

The privacy policy states provider training claims "under current terms" with a February 2026 verification date.

- **Review frequency:** Quarterly (May 2026, August 2026, November 2026, ...)
- **What to check:** Google Gemini API paid tier data usage policy; Anthropic API data retention and training policy
- **If terms change:** Update privacy policy immediately. If a provider begins training on API data, evaluate: (a) switch to a provider that doesn't, (b) negotiate enterprise terms with zero-training guarantee, or (c) trigger a new consent cycle disclosing the change.
- **Evidence links (verified February 2026):**
  - Google: https://ai.google.dev/gemini-api/docs/billing (paid tier: prompts not used to improve products)
  - Anthropic: https://privacy.anthropic.com/en/articles/7996868-is-my-data-used-for-model-training (API data not used for training by default)

### Rollback

If any issue arises post-deploy:

```bash
# Disable all AI inference immediately (kill switch)
docker exec strideiq_api python -c "
from database import SessionLocal
from models import FeatureFlag
db = SessionLocal()
flag = db.query(FeatureFlag).filter_by(key='ai_inference_enabled').first()
if flag:
    flag.enabled = False
else:
    from models import FeatureFlag
    flag = FeatureFlag(key='ai_inference_enabled', name='AI Inference Kill Switch', enabled=False, rollout_percentage=100)
    db.add(flag)
db.commit()
print('KILL SWITCH: ai_inference_enabled disabled')
db.close()
" && docker exec strideiq_redis redis-cli DEL "flag:ai_inference_enabled"
```
