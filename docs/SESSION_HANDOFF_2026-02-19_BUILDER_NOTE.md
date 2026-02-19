# Builder Note — Phase 1: Consent Infrastructure

**Date:** February 19, 2026
**Assignment:** Build Phase 1 consent infrastructure (P1-A through P1-D)
**Builder model:** Sonnet 4.6
**Supervisor:** Opus (reviews every output in the conversation loop)
**Founder sign-off:** Approved with all refinements applied

---

## Before your first tool call

Read these documents in this exact order. Do not skip any.

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how you work with this founder. Non-negotiable.
2. `docs/PRODUCT_MANIFESTO.md` — the soul of the product.
3. `docs/PHASE1_CONSENT_INFRASTRUCTURE_AC.md` — your complete spec. 46 tests, 8 gated call sites, 4 deliverables. Everything you need to build is in this document.
4. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — how every screen should feel. Do NOT re-propose rejected decisions.
5. This document — your assignment and execution rules.

---

## What you are building

Consent infrastructure for AI processing. This clears Blocker 0 for the Garmin Connect integration and fixes an existing inference disclosure gap.

**4 deliverables, shipped on `main`:**

| # | Deliverable | Summary |
|---|-------------|---------|
| P1-A | Privacy policy update | Add "AI-Powered Insights" section to `/privacy` page |
| P1-B | Consent data model | `ai_consent` fields on Athlete + `consent_audit_log` table + Alembic migration |
| P1-C | Consent UI | Full-screen opt-in prompt, onboarding step, Settings withdrawal toggle |
| P1-D | LLM pipeline gating | `has_ai_consent()` check at 8 call sites + global kill switch |

**P1-B through P1-D ship together in a single deploy.** P1-A can ship independently first.

---

## Build sequence

### Step 1: P1-A — Privacy policy update

**File:** `apps/web/app/privacy/page.tsx`

Add an "AI-Powered Insights" section. See AC A1-A8 in the spec for exact content requirements. Key points:
- Name Google Gemini and Anthropic Claude as providers
- State StrideIQ does not train models
- State providers do not train on paid API data under current terms (cite February 2026)
- State consent can be withdrawn via Settings
- State non-AI features continue without consent

**Tests:** This is a static content change. Visual verification only. No backend tests needed for this step.

**Commit when done.** This can ship independently.

### Step 2: P1-B — Consent data model + audit trail

**Files to create/modify:**
- New Alembic migration (add `ai_consent`, `ai_consent_granted_at`, `ai_consent_revoked_at` to `athlete` table; create `consent_audit_log` table)
- `apps/api/models.py` — add `ConsentAuditLog` model, add fields to `Athlete`
- `apps/api/services/consent.py` (new) — `has_ai_consent()`, `grant_consent()`, `revoke_consent()` functions
- `apps/api/routers/consent.py` (new) — `GET /v1/consent/ai`, `POST /v1/consent/ai` endpoints
- `apps/api/main.py` — register the new router

**Critical behaviors:**
- `ai_consent` defaults to `False` for all athletes (existing and new)
- Every consent action (grant or revoke) writes to `consent_audit_log`, even idempotent ones
- `has_ai_consent(athlete_id, db)` checks both athlete consent AND the global kill switch (`ai_inference_enabled` feature flag). Returns `False` if either is off.
- Consent endpoints require authentication
- `POST /v1/consent/ai` accepts `{ "granted": true/false }` and records IP, user agent, and source

**Tests:** Write tests 1-18 from the spec (Category 1 + Category 2).

**Do NOT commit until tests pass.** Run: `python -m pytest tests/test_consent.py -v --tb=short`

### Step 3: P1-D — LLM pipeline gating (backend enforcement)

**Do this BEFORE P1-C** — backend enforcement must be in place before the UI ships.

**Files to modify (8 call sites):**

| # | File | Function | What to add |
|---|------|----------|-------------|
| 1 | `services/ai_coach.py` | `AICoach.chat()` | Check `has_ai_consent` before LLM dispatch. If false, return consent-required message. |
| 2 | `routers/home.py` | `_fetch_llm_briefing_sync()` | Check `has_ai_consent` before LLM call. If false, return `None` and set `briefing_state = "consent_required"`. |
| 3 | `tasks/home_briefing_tasks.py` | `generate_home_briefing_task()` | Check `has_ai_consent` at execution time (not enqueue). If false, skip task, log reason. |
| 4 | `services/moment_narrator.py` | `_call_narrator_llm()` | Check `has_ai_consent`. If false, return `None`. |
| 5 | `services/workout_narrative_generator.py` | `_call_llm()` | Check `has_ai_consent`. If false, return `None`. |
| 6 | `services/adaptation_narrator.py` | `generate_narration()` | Check `has_ai_consent`. If false, return `None`. |
| 7 | `routers/progress.py` | `_generate_progress_headline()` | Check `has_ai_consent`. If false, return `None`. |
| 8 | `routers/progress.py` | `_generate_progress_cards()` | Check `has_ai_consent`. If false, return fallback cards (deterministic). |

**Additional changes:**
- Add `CONSENT_REQUIRED = "consent_required"` to `BriefingState` enum in `services/home_briefing_cache.py`
- Create the `ai_inference_enabled` feature flag record (or document the creation command for deploy)

**Prompt fix (while you're in the file):** In `routers/progress.py` `_generate_progress_cards()`, line 836 says "Return card language that is motivating, specific, and actionable." Change to: "Return card language that is specific, evidence-based, and actionable." This removes the sycophantic tone instruction. The safety rules on line 839 already say "no cheerleading, no praise" — make the instruction consistent.

**Do NOT gate `services/knowledge_extraction_ai.py`** — it's admin-only and doesn't process athlete data for athletes.

**Tests:** Write tests 19-34 from the spec (Category 3). Also write tests 35-42 (Category 4 integration) and 43-46 (Category 5 migration).

**Run full test suite:** `python -m pytest tests/test_consent.py -v --tb=short`

### Step 4: P1-C — Consent UI (frontend)

**Files to create/modify:**
- `apps/web/components/ConsentPrompt.tsx` (new) — full-screen consent prompt
- `apps/web/app/onboarding/page.tsx` — add consent step after goals
- `apps/web/app/settings/page.tsx` — add "AI Processing" section with toggle
- App-level layout or provider — fetch `GET /v1/consent/ai` on app load, conditionally render prompt

**Critical behaviors:**
- Consent prompt is a full-screen dedicated view, not a modal over content
- "Enable AI Insights" button calls `POST /v1/consent/ai` with `{ "granted": true }`
- "Not now" dismiss stores flag in `sessionStorage` (not `localStorage`)
- Prompt reappears on new browser session (browser fully closed and reopened)
- Prompt does NOT appear when `ai_consent = True`
- Settings toggle shows confirmation dialog before revoking
- Revocation calls `POST /v1/consent/ai` with `{ "granted": false }`
- No dead-end loops — unconsented user can navigate all non-AI surfaces freely

**Tests:** Frontend tests for consent prompt rendering/hiding (tests 41-42 from spec). Visual verification of UX flow.

---

## Rules you must follow

1. **Show evidence, not claims.** Paste test output. Paste `git diff --name-only --cached`. Paste deploy logs.
2. **Scoped commits only.** Never `git add -A`. Each commit touches only relevant files.
3. **No placeholder tests.** Every test has real assertions. `pass` or TODO is rejected.
4. **No code before tests.** Write the test file first (tests run red), then implement (tests run green).
5. **Run the full existing test suite** before committing to verify no regressions: `python -m pytest tests/ -v --tb=short -x`
6. **PowerShell environment.** The workspace is on Windows. Do not use `&&` to chain commands — use `;` or separate calls. Do not use `tail` — it doesn't exist in PowerShell.
7. **Do not modify `.env` files or commit secrets.**
8. **Do not push to production.** Commit to `main`, push to GitHub, verify CI. Deploy is a separate founder-authorized step.
9. **If you're unsure about anything, stop and ask.** The supervisor (Opus) is in the conversation loop. Ask before guessing.

---

## Test commands

```bash
# Run consent tests only
python -m pytest tests/test_consent.py -v --tb=short

# Run full backend suite (check for regressions)
python -m pytest tests/ -v --tb=short -x

# Check lints on modified files
python -m flake8 services/consent.py routers/consent.py --max-line-length=120
```

Working directory for all commands: `c:\Dev\StrideIQ\apps\api`

---

## Commit message format

```
feat(consent): P1-B — consent data model, audit trail, and endpoints

- Add ai_consent fields to Athlete model
- Create consent_audit_log table
- Add GET/POST /v1/consent/ai endpoints
- Add has_ai_consent() with kill switch check
- 18 tests passing
```

Use descriptive subject, list changes in body. Reference the deliverable ID (P1-A/B/C/D).

---

## What the supervisor will check

After each deliverable, the supervisor (Opus) will verify:

1. All relevant AC IDs from the spec are met
2. Tests pass with pasted evidence
3. No regressions in existing test suite
4. Commit is scoped (only relevant files)
5. Code matches spec exactly (no interpretation, no extras)

If the supervisor flags an issue, fix it before proceeding to the next deliverable.

---

## Current production state

- **Branch:** `main` at `5cf6457` (docs commit — Lane 2A handoff)
- **Droplet:** 2 vCPU / 4GB, all containers healthy
- **Feature flag:** `lane_2a_cache_briefing` enabled for founder only
- **CI:** Green

Do not touch Lane 2A code or the `lane_2a_cache_briefing` flag. They are separate.

---

## Start with P1-A (privacy policy update). Go.
