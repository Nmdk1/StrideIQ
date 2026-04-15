# Builder Instructions — Ledger P0 + Path A (Final)

**Date:** March 9, 2026  
**Author:** Founder + Tech Advisor review complete  
**Execution model:** 3 sequential phases, each with gate. No skipping.

---

## Non-Negotiables

1. Do phases in order: Phase 1 -> Phase 2 -> Phase 3.
2. Each phase must pass gate before moving on.
3. Scoped commits only (no mixed-phase commit).
4. Regenerate ledger at each gate:
   - `python scripts/generate_system_ledger.py`
5. **Do NOT add CI guard in this task.** We add CI guard after P0s are cleared in next clean deploy.

---

## Phase 1 — Foundation Fixes (P0)

### Task 1.1: Remove live `analyze_correlations()` from Home request path

**File:** `apps/api/routers/home.py`

`get_correlation_context()` currently calls `analyze_correlations()` live inside `generate_why_context()`.

**Fix**
- Replace with persisted lookup from `CorrelationFinding`:
  - `is_active=True`
  - `times_confirmed >= 3`
- Use lag/domain to produce short coaching-language sentence.
- If no eligible finding, return `(None, None)` and preserve existing waterfall.
- No live recomputation anywhere in this path.

**Test**
- Unit test for persisted-finding path.
- Unit test for no-finding fallback.
- Assert `analyze_correlations` is not called/imported in Home path logic.

### Task 1.2: Fix broken frontend links

| Source file | Broken target | Fix |
|---|---|---|
| `apps/web/components/onboarding/EmptyStates.tsx` | `/lab-results` | Remove lab-results CTA block entirely |
| `apps/web/app/insights/page.tsx` | `/plans` | Change to `/plans/create` |
| `apps/web/app/components/ConsentPrompt.tsx` | `/privacy#ai-powered-insights` | Add `id="ai-powered-insights"` on privacy section wrapper |
| `apps/web/app/settings/page.tsx` | `/privacy#ai-powered-insights` | Same privacy anchor fix |
| `apps/web/components/activities/RuntoonCard.tsx` | `/settings#runtoon` | Add `id="runtoon"` on settings container wrapping Runtoon section |

**Test**
- Validate each target route/anchor exists.
- Confirm zero remaining `/lab-results` references in frontend.

### Task 1.3: Remove dead lab-results backend router

**Files**
- Delete `apps/api/routers/lab_results.py`
- Remove lab-results import from `apps/api/main.py`

**Non-goal**
- Do not remove lab result models/migrations/tables in this task.

**Test**
- Runtime route registration no longer includes dead lab-results declarations.

### Task 1.4: Morning voice repetition hardening (without breaking trust contract)

**File:** `apps/api/routers/home.py`

Current validator already fail-closes >280 for `morning_voice`.

**Fix**
- Tighten `schema_fields["morning_voice"]` text to:
  - ONE paragraph
  - 2-3 sentences max
  - 40-280 chars
  - no second paragraph
  - no restatement
- Keep existing hard fail-close >280 behavior.
- Add warning telemetry at >240 chars for early drift detection (warning only; existing fail-close remains unchanged).

**Test**
- Ensure schema field text contains one-paragraph/no-restatement constraints.
- Validator test:
  - warning path at >240
  - fail-close remains at >280.

### Phase 1 Gate

- [ ] No live `analyze_correlations()` in Home request path.
- [ ] Broken links fixed.
- [ ] Dead lab-results router removed.
- [ ] Ledger regenerated and **P0 count = 0**.
- [ ] Existing tests + new tests green.
- [ ] Commit, CI green, deploy, production healthy.

---

## Phase 2 — Path A Home Surfaces

### Task 2.1: Weather-adjusted pace on Home last run hero

**Backend (`apps/api/routers/home.py`)**
- Add `heat_adjustment_pct: Optional[float]` to `LastRun`.
- Populate from activity data when building `LastRun`.

**Frontend (`apps/web/app/home/page.tsx`)**
- Show weather-adjusted pace context only when `heat_adjustment_pct > 3`.
- If null or <=3, render nothing.

**Test**
- API response includes `heat_adjustment_pct` when available.
- UI conditional render test for >3 and non-render for <=3/null.

### Task 2.2: One finding on Home + Belle cold-start state

**Backend**
- Define typed model (not raw dict):
  - `class HomeFinding(BaseModel): text, confidence_tier, domain, times_confirmed`
- Add `finding: Optional[HomeFinding]` to `HomeResponse`.
- Add `has_correlations: bool` to `HomeResponse` (used later for nav gating).
- Populate finding from top active `CorrelationFinding` (`is_active=True`, `times_confirmed>=3`), with day-based rotation.

**Frontend**
- Render finding card in Home.
- If no finding: render cold-start state using `total_activities`:
  - `<10`: Getting started
  - `10-30`: Patterns forming
  - `30+` and no confirmed finding: Analysis in progress
- Never leave this section empty.

**Test**
- API tests: with findings + no findings.
- UI tests: finding state + cold-start variants.

### Task 2.3: Weather context on activity detail

**Backend**
- Ensure activity detail response includes `dew_point_f` and `heat_adjustment_pct`.

**Frontend**
- In `apps/web/app/activities/[id]/page.tsx`, render one-line weather context when `heat_adjustment_pct > 3`.

**Test**
- API contract test for both fields.
- UI conditional render test.

### Phase 2 Gate

- [ ] Home shows weather-adjusted pace when notable.
- [ ] Home shows finding OR cold-start progress.
- [ ] Activity detail shows weather context when notable.
- [ ] Belle/new-athlete state is honest and non-empty.
- [ ] Tests green, commit, CI green, deploy, production healthy.

---

## Phase 3 — Activity Intelligence + Navigation + Daily Intelligence

### Task 3.1: Finding annotations on activity detail

**Backend**
- Add endpoint: `GET /v1/activities/{id}/findings`
- Return relevant active `AthleteFinding`/`CorrelationFinding` entries:
  - `text`, `domain`, `confidence_tier`, `evidence_summary`
- Limit 3, return empty list if none.

**Frontend**
- Render below splits as subtle annotation cards.
- Render nothing when empty.

**Test**
- API tests: matched findings + empty response.
- UI render test.

### Task 3.2: Add Discovery/Fingerprint to navigation with data gating

**Files**
- `apps/web/app/components/Navigation.tsx`
- `apps/web/app/components/BottomTabs.tsx` (More menu)

**Critical contract**
- Do **not** fetch `/v1/home` globally in nav to determine gating.
- Use lightweight nav state source:
  - Option A (preferred): include `has_correlations` in auth/me payload and consume from auth context.
  - Option B: add lightweight endpoint `/v1/navigation/state` returning `{has_correlations}`.
- Show Discovery/Fingerprint only when `has_correlations=True`.

**Test**
- Founder account: items visible.
- New athlete with no correlations: items hidden.

### Task 3.3: Wire daily intelligence into Insights page

**Backend source**
- `GET /v1/intelligence/today` (tier gated).

**Frontend (`apps/web/app/insights/page.tsx`)**
- Add “Today’s Intelligence” section at top.
- Render fired rules as cards.
- Tier-safe behavior:
  - if non-guided/403: hide section silently (no scary error card).
  - if guided but empty: render nothing.

**Test**
- UI tests:
  - data present
  - empty
  - forbidden/non-guided hidden behavior.

### Phase 3 Gate

- [ ] Activity finding annotations working.
- [ ] Discovery/Fingerprint discoverable and correctly gated.
- [ ] Daily intelligence visible on Insights when available; hidden safely when not eligible.
- [ ] Tests green.
- [ ] Commit, CI green, deploy, production healthy.
- [ ] Ledger regen confirms P0 remains zero and broken-link count reduced.

---

## Final Gate (All Phases)

- [ ] `python scripts/generate_system_ledger.py` shows zero P0.
- [ ] Full regression suite green.
- [ ] Production healthy.
- [ ] `git status` clean.
- [ ] Update `docs/SITE_AUDIT_LIVING.md` with shipped changes.

---

## Builder Loop Protocol (Enforced)

Per phase:
1. Read phase spec
2. Trace current code paths before edits
3. Implement
4. Run targeted tests
5. Run broader regression
6. Regenerate ledger + validate phase gate
7. Commit scoped changes
8. Push, wait for CI green
9. Deploy
10. Verify production health
11. Proceed only if gate passes
