# Session Handoff — 2026-02-16 (Session 2: CI fixes, demo guard, check-in UX, correlation persistence)

**Builder:** Claude session (long context, crashed mid-session by Cursor update, recovered)
**Duration:** ~3 hours across crash boundary
**Living audit updated:** `docs/SITE_AUDIT_LIVING.md` — read this first in every new session

---

## 1) Primary Outcomes

This session fixed a CI pipeline failure, secured demo accounts from real Strava linking, repaired a beta user's Strava sync, fixed a home page check-in UX race condition, and shipped the correlation persistence + reproducibility tracking system — making check-in data a permanent, accumulating part of the intelligence pipeline.

### Commits shipped to `main`

| SHA | Message | Category |
|-----|---------|----------|
| `ed15747` | `fix(security): block demo accounts from linking real Strava accounts` | Security |
| `2c2eefa` | `fix(home): optimistic cache update on check-in so UI switches instantly` | UX |
| `f70e670` | `feat(intelligence): persist correlation findings with reproducibility tracking` | Intelligence |
| `2915476` | `fix(web): remove invalid ESLint rule suppression in home query hook` | CI |
| `f26a989` | `fix(intelligence): align correlation specificity across surfaced insights` | Intelligence |
| `8992339` | `docs(handoff): capture 2026-02-16 session state and deploy learnings` | Docs |
| `ddc2b01` | `docs: create living site audit for builder session handoffs` | Docs |

---

## 2) What Changed

### A) Demo Account Security (`ed15747`)

**Problem:** A prospect using shared demo credentials connected their real Strava account to the demo. Their personal data appeared on the demo account, and the demo's synthetic charts broke because real activities with no valid stream tokens blocked the pipeline.

**Changes:**
- Added `is_demo` Boolean column to `Athlete` model (`models.py`)
- Alembic migration `demo_guard_001` adds the column with `server_default=false`
- Strava `/v1/strava/auth-url` returns 403 for demo accounts
- Strava `/v1/strava/callback` double-guards with 403 for demo accounts
- `provision_demo_athlete.py` sets `is_demo=True` on create and update paths
- CI hygiene: removed hardcoded email from script, sourced from env var

**Production cleanup performed:**
- Deleted all real (non-synthetic) activities from demo account via surgical SQL
- Cleared foreign key dependencies in correct order: `cached_stream_analysis`, `activity_stream`, `activity_split`, `best_effort`, `personal_best`, `activity_feedback`, `activity_reflection` → then `activity`
- Cleared stale v3 cached analyses for remaining synthetic activities
- Bumped `CURRENT_ANALYSIS_VERSION` to force recompute

**Files modified:**
- `apps/api/models.py` — `is_demo` column
- `apps/api/routers/strava.py` — auth-url + callback guards
- `apps/api/scripts/provision_demo_athlete.py` — env var email, `is_demo=True`
- `apps/api/alembic/versions/demo_guard_001_add_is_demo_to_athlete.py` — new migration
- `.github/scripts/ci_alembic_heads_check.py` — updated expected head

### B) Beta User Strava Sync (ultrarunner26 / Danny Larson)

**Problem:** Danny (`dannylarson26@yahoo.com`) had 557 all-time runs on Strava but StrideIQ showed 0 activities synced.

**Root cause:** Strava token lacked `activity:read_all` scope. The Strava API returned profile data but empty activity list.

**Diagnosis performed:**
- Verified token exists and athlete record is linked
- Direct Strava API call confirmed profile visible but `/athlete/activities` returned `[]`
- Token scope check confirmed missing `activity:read_all`
- Impersonation doesn't work for Strava OAuth (session/cookies are per-browser)

**Resolution:**
- Generated a direct, pre-populated Strava OAuth URL with `activity:read_all` scope for Danny
- URL includes server-side OAuth state token so Danny just clicks the link, checks the box, and authorizes
- Avoids multi-step process (Danny runs 100+ miles/week and has limited time)

**Secondary issue found:** `ensure_fresh_token` has a timezone-aware vs naive datetime comparison bug. Noted for future fix, worked around by using token directly.

### C) Home Page Check-in UX (`2c2eefa`)

**Problem:** Morning check-in on home page showed "Check-in saved" toast on first click but the UI stayed in input form state. Second click would update the UI correctly.

**Root cause:** `invalidateQueries({ queryKey: ['home'] })` triggers a background refetch of `/v1/home`, which is slow (coach briefing, LLM calls). TanStack Query waits for the refetch before updating cached data, so the UI appears stuck in the old state.

**Fix:** Optimistic cache update in `useQuickCheckin` mutation:
- `onSuccess` immediately calls `queryClient.setQueryData(['home'], ...)` to set `checkin_needed: false` and populate `today_checkin` labels
- UI switches from QuickCheckin form → CheckinSummary instantly
- Background `invalidateQueries` still fires for eventual consistency with server data
- Label maps (MOTIVATION_LABELS, SLEEP_QUALITY_LABELS, SORENESS_LABELS) match backend maps

**File:** `apps/web/lib/hooks/queries/home.ts`

### D) Correlation Persistence System (`f70e670`)

**The big feature.** Check-in data (sleep, soreness, motivation) correlations with performance are now stored permanently and tracked for reproducibility.

**New model: `CorrelationFinding`** (`models.py`)
- Natural key: `(athlete_id, input_name, output_metric, time_lag_days)`
- `times_confirmed` — increments each time engine re-confirms the relationship
- `is_active` — set to False when pattern fades below significance
- `last_surfaced_at` — cooldown tracking
- `confidence` — boosted by reproducibility

**New service: `correlation_persistence.py`**
- `persist_correlation_findings()` — upsert: new findings created, existing ones increment `times_confirmed`, faded patterns deactivated
- `get_surfaceable_findings()` — returns reproducible (3+ confirmations), active, not-recently-surfaced findings
- `mark_surfaced()` — stamps `last_surfaced_at` for cooldown
- Statistical gates mirror correlation engine: p < 0.05, |r| >= 0.3, n >= 10

**New migration: `corr_persist_001`**
- Creates `correlation_finding` table with unique natural key index
- Chains off `demo_guard_001`

**Wired into correlation engine** (`correlation_engine.py`):
- After `analyze_correlations()` returns, calls `persist_correlation_findings()` fire-and-forget
- Persistence failures logged but never break the API response

**New intelligence rule: `CORRELATION_CONFIRMED`** (Rule 8 of 8)
- Added to `daily_intelligence.py` as the 8th rule
- Fires when: `times_confirmed >= 3`, `is_active == True`, not surfaced in last 14 days
- Max 2 findings per day per athlete
- Confidence boosted: `confidence * (1 + 0.1 * (times_confirmed - 1))`, capped at 1.0
- Adds reproducibility context to message: "confirmed 3 times — becoming a reliable signal" or "confirmed 5+ times — reliable part of your personal profile"
- Persisted to `InsightLog` → flows through AdaptationNarrator → narrated to athlete
- After surfacing, marks findings with `last_surfaced_at` for 14-day cooldown

**Test updates:** Docstrings in 3 test files updated from "7 rules" to "8 rules"

### E) Correlation Specificity Alignment (`f26a989`)

- Correlation messages aligned across `daily_intelligence.py` and `home.py`
- Messages now include lag timing, confirmation count, and numeric evidence (`r=`)
- New test file: `test_daily_intelligence_correlation_confirmed.py`

### F) Living Site Audit (`ddc2b01`)

- Created `docs/SITE_AUDIT_LIVING.md` — comprehensive end-to-end system audit
- Covers: infrastructure, all 57 models, intelligence pipeline, check-in data flow, frontend pages, build priorities, known issues, operational procedures, migration chain, key file paths
- Protocol: every new session reads it first, updates it before closing

---

## 3) CI and Git Status

### CI
- `22056211900` (commit `f26a989`) → **success** (last code commit)
- `22056945167` (commit `8992339`) → **failure** (GitHub Actions billing exhausted — not a code issue)

**Action needed:** Fix GitHub Actions billing in Settings > Billing & plans. The CI itself is green on code.

### Repository state at handoff
- Branch: `main`
- Local: clean, up to date with `origin/main`
- No uncommitted or untracked files

### Production state
- All 6 containers running: api, web, caddy, postgres, redis, worker
- Migration at head: `corr_persist_001`
- API healthy: `{"status":"healthy"}`
- DNS: `strideiq.run` → `104.248.212.71`, `www.strideiq.run` → `104.248.212.71`

---

## 4) Data Flow: Check-in → Correlation → Insight (New)

```
Athlete morning check-in (home page or /checkin)
    ↓ POST /v1/daily-checkin → DailyCheckin table
    ↓ (optimistic UI update — instant switch to CheckinSummary)
    ↓
Correlation Engine (on-demand via API or daily intelligence task)
    ↓ Aggregates: sleep_h, soreness_1_5, motivation_1_5, stress_1_5, etc.
    ↓ Correlates with: efficiency, pace, completion (0–7 day lags)
    ↓
persist_correlation_findings() → correlation_finding table
    ↓ New finding: times_confirmed = 1
    ↓ Repeat finding: times_confirmed += 1
    ↓ Faded finding: is_active = False
    ↓
Daily Intelligence (Rule 8: CORRELATION_CONFIRMED)
    ↓ Gate: times_confirmed >= 3 AND is_active AND not surfaced in 14 days
    ↓ Max 2 per day
    ↓
InsightLog → AdaptationNarrator (Gemini Flash) → Athlete sees:
    "Your running efficiency noticeably tends to improve within 2 days
     when your sleep hours are higher. This pattern has been confirmed
     4 times — it's becoming a reliable signal."
```

---

## 5) Alembic Migration Chain (Current)

```
... → rsi_cache_001 → sleep_quality_001 → demo_guard_001 → corr_persist_001 (HEAD)
```

CI enforces single-head via `.github/scripts/ci_alembic_heads_check.py` → `EXPECTED_HEADS = {"corr_persist_001"}`

---

## 6) Known Issues & Watch Items

| Issue | Severity | Notes |
|-------|----------|-------|
| GitHub Actions billing exhausted | Medium | CI runs fail with payment error. Fix in GitHub Settings > Billing & plans |
| `ensure_fresh_token` timezone bug | Low | Comparing tz-aware and tz-naive datetimes. Workaround: use token directly. Found during Danny's sync debug |
| Danny Larson Strava scope | Low | Direct OAuth URL was generated. Check if Danny has reconnected and activities are syncing |
| Home page dual voice | Design debt | `compute_coach_noticed` + `morning_voice` overlap. Planned merge into single synthesis |
| Activity moments need narrative | Design debt | Raw numbers, not coached sentences |
| Insights feed noise | Design debt | Duplicate volume alerts, low-quality achievements |
| 8 services with local polarity assumptions | Tech debt | Migrate to `OutputMetricMeta` registry |
| Sleep excluded from readiness score | By design | Until correlation engine proves individual relationship |

---

## 7) Pending Work (Prioritized)

Per `docs/TRAINING_PLAN_REBUILD_PLAN.md`:

1. **Monetization tier mapping** (revenue unlock)
2. **Phase 4** (50K Ultra)
3. **Phase 3B** rollout when narration quality gate clears (>90% for 4 weeks)
4. **Phase 3C** broader rollout when data/stat gates clear

**Gates to monitor:**
- `GET /v1/intelligence/narration/quality` for 3B gate
- Correlated-history sufficiency for 3C non-founder users

---

## 8) Files Modified This Session

### New files
- `apps/api/services/correlation_persistence.py`
- `apps/api/alembic/versions/corr_persist_001_add_correlation_finding.py`
- `apps/api/alembic/versions/demo_guard_001_add_is_demo_to_athlete.py`
- `docs/SITE_AUDIT_LIVING.md`

### Modified files
- `apps/api/models.py` — `is_demo` on Athlete, `CorrelationFinding` model
- `apps/api/routers/strava.py` — demo account guards on auth-url + callback
- `apps/api/services/correlation_engine.py` — persistence call after analysis
- `apps/api/services/daily_intelligence.py` — Rule 8 CORRELATION_CONFIRMED
- `apps/api/scripts/provision_demo_athlete.py` — env var email, is_demo flag
- `apps/web/lib/hooks/queries/home.ts` — optimistic cache update for check-in
- `.github/scripts/ci_alembic_heads_check.py` — updated expected head
- `apps/api/tests/test_monetization_tier_mapping.py` — docstring 7→8 rules
- `apps/api/tests/test_phase4_50k_ultra.py` — docstring 7→8 rules
- `apps/api/tests/test_training_logic_scenarios.py` — docstring 7→8 rules

---

## 9) Quick Reference for Next Session

### Read first
1. `docs/SITE_AUDIT_LIVING.md` — full system audit (update before closing)
2. `docs/TRAINING_PLAN_REBUILD_PLAN.md` — build priorities, gates, contracts
3. `docs/FOUNDER_OPERATING_CONTRACT.md` — how to work with the founder

### Deploy commands
```bash
cd /opt/strideiq/repo
git pull origin main
docker compose up -d --build
docker compose exec api alembic upgrade head   # usually auto-runs on boot
```

### Health check
```bash
docker compose ps
curl -s https://strideiq.run/health
curl -I https://strideiq.run
```

### Key principle
The founder's product insight: **athletes don't need to see their own check-in data — they know how they felt.** The value is in correlation surfacing: patterns they can't see themselves, spoken only when the evidence is reproducible. Silence when it's not. The coach earns trust by being right, not by being frequent.
