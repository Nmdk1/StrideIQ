## StrideIQ: Phased Work Plan (Private Beta → Viral-Safe Launch)

**Date:** 2026-01-20  
**Owner intent:** Invite-led launch with near-term open signups, “viral-safe” behavior under load spikes.  
**Constraint:** Do not start implementation work until explicit approval per phase.

**Manifesto + voice sources of truth:**
- Product manifesto: `_AI_CONTEXT_/00_MANIFESTO.md`
- Brand voice: `TONE_GUIDE.md`

**Docs index (start here):** `docs/README.md`

---

## Workflow Contract (How we execute every phase)

This document is the **canonical workflow** for all sessions until the final phase is completed.

### Rules
- **Phase-gated work**: no implementation begins for a phase until the owner explicitly approves starting that phase.
- **Sprint rhythm** (for any approved phase):
  - **Decide**: confirm scope + success criteria for the sprint.
  - **Execute**: implement changes.
  - **Verify**: run the relevant checks (UI flow, tests, and/or golden path for that phase).
  - **Document**: update the sprint handoff doc **and** update this plan’s progress ledger.
- **Documentation requirement** (after every sprint):
  - Update the “Phase Status” table (below)
  - Add an entry to “Progress Ledger” (below) describing what changed and what’s next
  - Keep tone aligned with `_AI_CONTEXT_/00_MANIFESTO.md` and `TONE_GUIDE.md`

---

## Phase Status (single source of truth)

Status values: **Not started** | **In progress** | **Blocked** | **Complete**

| Phase | Name | Status | Notes |
|------:|------|--------|------|
| 1 | Finish the Subscriber Experience | Complete | Sprints 1–3 accepted: fixed 500s, improved Home/Insights trust, hardened coach UX (units + receipts), mobile responsiveness + mobile QA sweep, and removed hardcoded credential strings with CI guardrails. |
| 2 | Public Pages (Landing + About) | Complete | Landing + About now match manifesto voice and product reality; conversion CTAs are coherent; About includes founder story + photo; preview/mock routes removed. |
| 3 | Onboarding Workflow (“Latency Bridge”) | Complete | Invite allowlist gating is enforced and auditable; Strava OAuth is state-signed and returns to web; ingestion is queued and progress is deterministic (no “dead air” even if ingestion_state is pending). |
| 4 | Admin “Heartbeat” | Complete | Secure `/admin` + `/v1/admin/*` (role + permission seam), “God Mode” athlete detail, auditable operator actions (comp/reset/retry/block), and impersonation hardened (owner-only + time-boxed + banner + audit). |
| 5 | Operational Visibility + Reliability | Complete | Viral-Safe Shield delivered: Ops Pulse (queue/stuck/errors/deferred), Rate Limit Armor (429 deferral + retry), and Emergency Brake (global ingestion pause + UI banner). |
| 6 | Subscription/Tier/Payment Productionization | Complete | Stripe MVP delivered: hosted Checkout + Portal + webhook-driven subscription mirror + idempotency. Added 7-day trial (self-serve + admin grant/revoke) and converged entitlements to Free vs Pro. Deprecated legacy one-time plan checkout paths. |
| 7 | Data Provider Expansion (Garmin/Coros) | Complete | File import v1 delivered (Garmin DI_CONNECT): `AthleteDataImportJob`, shared uploads mount, upload API + Celery worker, zip-slip protection, idempotent re-imports, cross-provider dedup + calendar display safety, and Settings UI job history (feature-flagged). Legacy Garmin password-connect is admin-only and gated off by default. |
| 8 | Security, Privacy, Compliance Hardening | Complete | |
| 9 | Automated Release Safety (Golden Paths + CI) | **Complete** | Sprints 1–2 accepted: expanded backend + web golden paths and CI gating; documented required checks + branch protection checklist for release safety MVP. |
| 10 | Coach Action Automation (Propose → Confirm → Apply) | **Complete** | **HIGH PRIORITY immediately after Phase 9 completes.** Deterministic, auditable plan changes from Coach with explicit athlete confirmation (no silent/autonomous execution), plus athlete-facing ProposalCard UX + hardening + tests. |
| 11 | Coach LLM Upgrade (Multi-Model Tiering) | **Not started** | Claude Sonnet 4.5 as production default, Opus 4.5 for VIP/Elite tier, Mistral fallback for rate limits. See `docs/LLM_MODEL_RESEARCH.md`. |

---

## Progress Ledger (append-only)

- **2026-01-20**: Established phased plan and workflow contract. Updated guiding principles to match the manifesto and clarified outcomes are multi-objective (efficiency, PBs, age-graded %, body comp).
- **2026-01-21 (Phase 1 / Sprint 1)**: Fixed 3 blockers: (1) Calendar day drilldown “Coach” action 500 due to missing `coach_chat` table (added migration), (2) Plan adjustments (“swap days” / “adjust load”) 500 due to missing `plan_modification_log` table + swap-days request/schema mismatch (added migration + fixed endpoint), (3) Analytics “Why This Trend” 500 caused by schema drift in `DailyCheckin` fields (made attribution collection backward-compatible). Next: hover uniformity, chart styling, and Insights trust repairs.
- **2026-01-22 (Phase 1 / Sprint 2 - partial, degraded session)**: Attempted to enforce **uniform UX** by unifying the global page background and removing `bg-[#0a0a0f]` styling drift across many logged-in routes/components. **Result:** base background is now consistent (`bg-slate-900`), but **Home still reads as a different theme** because it relies on translucent card surfaces (`bg-slate-800/50`, nested `bg-slate-900/30`) while Analytics/Calendar primarily use solid `bg-slate-800 border-slate-700`. Next: standardize Home to match Analytics card surfaces, and introduce a shared page wrapper component to prevent future drift.
- **2026-01-21 (Phase 1 / Sprint 2 - accepted)**: Fixed Home dashboard “trapped whitespace” and row-height rhythm issues (single Signals spans full width; row cards stretch to equal height; “Yesterday” is no longer orphaned and is stacked with Quick Access). Fixed trust-breaking Insights intelligence generation by replacing placeholder/incorrect logic (ISO week bug, “need more history”) with time-scoped, evidence-backed “micro insights” computed from ~2 years of run history and explicit rebuild/return-to-run context. Next: improve the correlation engine so every candidate input is measurable and evaluated (individually + in defined clusters) against explicit outcomes (efficiency trend, PBs, injury proxies) with receipts and minimum-sample guards.
- **2026-01-22 (Phase 1 / Sprint 3 - accepted, Phase 1 complete)**: Hardened the Coach “trust contract” so answers stay conversational while remaining auditable: receipts are now compact and collapsible in the UI, evidence is human-readable (date + run name + key values), and units preference (miles/min‑mi) is enforced and persisted. Added a Phase 1 mobile QA sweep script (detects horizontal overflow and verifies Coach mobile behavior). Removed hardcoded credential strings from repo artifacts and added a CI guardrail to prevent regressions. Phase 1 is complete; Phase 2 (public pages) is approved to start.
- **2026-01-23 (Phase 2 / Sprint 1 - accepted, Phase 2 complete)**: Refined public “front door” pages to align with the manifesto and reduce cognitive load: landing page copy/hierarchy tightened around N=1 intelligence, evidence-backed coaching, and a clear conversion path; About page added as the canonical “why/how” for interested athletes, including founder story and race photo. Removed temporary preview/mock routes and ensured navigation/footer surface the new About page.
- **2026-01-24 (Phase 3 / Sprint 1 - in progress)**: Began “Latency Bridge” onboarding: added **DB-backed invite allowlist** (auditable) and enforced it at **all account-creation boundaries** (register + Strava OAuth callback, plus secured legacy athlete-create). Strava OAuth now uses **signed state** to bind to existing athletes, redirects back to the web app (no JSON dead-end), and queues a **cheap index backfill** immediately. Added onboarding endpoints to bootstrap ingestion and expose ingestion status. Web onboarding + Home now surface deterministic “import in progress” status.
- **2026-01-24 (Phase 3 / Sprint 2 - accepted)**: Eliminated the remaining “dead air” edge case on Home: when Strava is connected but `ingestion_state` hasn’t populated yet, Home now shows an explicit **Import queued** card instead of rendering an ambiguous empty dashboard. Added web regression tests covering both queued and running states.
- **2026-01-24 (Phase 3 - complete)**: Phase 3 closed. Verified: invite-only gating at registration, signed OAuth state round-trip, Strava callback queues ingestion, onboarding intake persists and seeds intent snapshot, Home shows deterministic import status (queued/running), and black-box wiring confirms Intake priors influence deterministic selection.
- **2026-01-24 (Phase 4 - complete)**: Phase 4 closed. Delivered a business-critical admin console: secure `/admin` routes, RBAC seam (`admin_permissions`), append-only admin audit log, “God Mode” athlete detail, and operator actions (comp access, reset onboarding, retry ingestion, block/unblock). **Impersonation hardened** to owner-only with a **time-boxed token**, **global banner**, and **hard audit event** to prevent silent privilege escalation.
- **2026-01-24 (Phase 5 / Ops Visibility v0)**: Added an Ops tab for fast triage: best-effort queue snapshot, stuck ingestion list, and recent ingestion errors, plus API + web regression tests.
- **2026-01-24 (Phase 5 - complete)**: Delivered the “Viral-Safe Shield”: **Ops Pulse** (queue + stuck + errors + deferred + pause toggle), **Rate Limit Armor** (Strava 429 → defer + retry without worker sleep), and **Emergency Brake** (`system.ingestion_paused` enforced in Strava callback + admin retry; calm Home banner when paused). Added targeted backend and web regression tests to prevent meltdown regressions.
- **2026-01-24 (Phase 5 - closure hardening)**: Locked down system-level controls so `system.*` actions (including global ingestion pause) require **explicit permissions** for admins (no implicit bootstrap access). Added an owner-only endpoint to set `admin_permissions` (audited + tested), and added CI smoke suites to continuously exercise the Phase 3 + Phase 5 golden paths (backend + web) to prevent regressions.
- **2026-01-24 (Phase 6 / Stripe MVP - foundation)**: Added `subscriptions` + `stripe_events` tables, implemented signature-verified Stripe webhooks with idempotency, and wired hosted Checkout/Portal endpoints to enable `pro` monthly upgrades with minimal billing surface area (ADR-055).
- **2026-01-24 (Phase 6 - complete)**: Completed Phase 6 monetization + entitlement productionization: fixed Stripe subscription cancellation mirroring under newer API versions, added a self-serve **7-day trial** (plus admin grant/revoke) and exposed trial/subscription mirror in Admin for support. Converged UI/ops semantics to **Free vs Pro** and deprecated legacy one-time plan checkout routes.
- **2026-01-25 (Phase 7 - complete)**: Provider expansion via **file import v1** shipped (ADR-057). Delivered `AthleteDataImportJob` + migrations, shared `/uploads` mount for API+worker, feature flags, Garmin DI_CONNECT importer (zip-safe extraction + unit conversion + idempotent re-imports), and Settings UI (upload + recent job statuses). Hardened duplicate handling: importer prefers `startTimeGmt` for UTC alignment, uses DB-level conflict-safe inserts, and calendar collapses probable cross-provider duplicates for display safety. Legacy Garmin password-connect is admin-only and gated off by default.
- **2026-01-25 (Phase 8 / Sprint 1 - accepted)**: Delivered 3 security golden-path integration tests (auth/RBAC, IDOR on imports, sensitive logging boundary). Tests hermetic with tmp_path; added to backend-smoke CI with Phase 7 E2E. Commit: 2ae7bec. Local smoke green.
- **2026-01-25 (Phase 8 / Sprint 2 - partial accepted)**: Completed items #1 and #3: (1) hardened impersonation tokens against high-risk mutations (403 guard + tests); (2) refactored /v1/gdpr/export to bounded skeleton (metadata/profile/counts/recent N=25, no secrets). CI-gated. Commits: a137ca5, 3e28211, b4c3aef. Local smoke green. Next: Item #4 (CI secret guardrails) or Sprint 3.
- **2026-01-25 (Phase 8 / Sprint 2 - accepted)**: Completed full sprint: (1) impersonation mutation guard + tests; (3) bounded GDPR export skeleton at /v1/gdpr/export (no secrets, N=25 recent); (4) tightened CI secret scan (Stripe/GitHub/JWT/Strava/Garmin patterns + self-test). All CI-gated. Commits: a137ca5, 3e28211, b4c3aef, db60ef1. Local smoke green. Next: consider Sprint 3 or Phase 9 push.
- **2026-01-25 (Phase 8 / Sprint 3 - partial accepted)**: Completed items #1 and #2: (1) added token/JWT invariants tests (valid/expired/tampered/wrong-secret/rotation/impersonation TTL) and gated in backend-smoke. (2) added admin audit log emission tests for high-risk mutations + one-shot retention script (`scripts/clean_audit_events.py --days 90 --dry-run`). CI-gated. Commits: 2762756, 51833f7, 0db88b5. Local smoke green. Next: Sprint 3 item #3 (secrets rotation policy skeleton).
- **2026-01-25 (Phase 8 / Sprint 3 - accepted)**: Completed full sprint: (1) token/JWT invariants tests + smoke gating (expiry/tamper/wrong-secret/rotation/impersonation TTL); (2) admin audit log emission tests + retention script; (3) secrets rotation policy skeleton + CI template presence check + `.env.example`. All CI-gated. Commits: 2762756, 51833f7, 0db88b5, 7b89bd1. Local smoke green. Next: consider Sprint 4 or Phase 9 push.
- **2026-01-25 (Phase 8 - complete)**: Full hardening delivered across 3 sprints: security golden paths + CI gating, impersonation/tokens invariants, GDPR export skeleton, audit log reliability + retention script, secrets rotation policy + CI template presence check. All items tested, CI-gated, documented (docs/SECURITY_SECRETS.md). Commits: see prior Sprint entries. Phase 8 closed; ready for Phase 9 release safety.
- **2026-01-25 (Phase 9 / Sprint 1 - accepted)**: Expanded release-safety golden paths and CI gating: (backend) new smoke tests for Stripe webhook signature verification, entitlement transitions (comp pro/free), and ingestion pause/retry seam; (web) new Jest tests for landing pricing CTA → register and onboarding “import in progress” status; updated `backend-smoke` + `frontend-test` job lists; documented Phase 9 golden paths + local run commands. Commit: 557f93b.
- **2026-01-25 (Phase 9 / Sprint 2 - accepted, Phase 9 complete)**: Expanded release-safety MVP coverage: (backend) plan generation golden paths for standard plan preview/create response shape + negative controls (auth required; model-driven tier gating enforced); (web) new Jest golden paths for plan-create gating (free vs paid) and subscriber value deep dive (Insights evidence cards, PBs table, Coach receipts); updated CI `frontend-test` smoke list and Phase 9 docs (explicit paths + branch protection checklist). Commit: 65a150f.
- **2026-01-25 (Phase 10 / Sprint 1 - accepted)**: Established Coach Action Automation foundation: added `coach_action_proposals` table/migration/model; implemented `/v2/coach/actions/*` propose/confirm/reject endpoints with strict action catalog validation, idempotency, and transactional apply; added backend integration tests (happy path, auth required, reject blocks confirm, cross-user forbid, template replace). Commit: 279d20d.
- **2026-01-25 (Phase 10 / Sprint 1 - accepted, beta-ready)**: Production-beta hardening for Coach Action Automation: blocked propose/confirm/reject under impersonation unless explicit permission (high-signal audit), used proposal row lock + DB savepoint for rollback-safe apply (no partial changes on failure), emitted structured `AdminAuditEvent` for propose/confirm/reject/applied/failed, and expanded integration tests for impersonation block + apply failure rollback/proposal persistence. Commit: 23ef820.
- **2026-01-25 (Phase 10 / Sprint 2 - accepted)**: Added the Coach chat **UX proposal card** for deterministic plan changes: new `ProposalCard` renders header/reason/diff/risk notes and provides Confirm/Reject/Ask follow-up actions; wired into Coach chat message rendering when a proposal payload is present; added web client service for confirm/reject and Jest tests for render + confirm/reject flows. Commit: 2336629.
- **2026-01-25 (Phase 10 / Sprint 2 - accepted, beta-ready reasoning)**: Hardened Coach reasoning against trust-breaking scope errors in return-from-injury/break contexts: added explicit “coming back” ambiguity guardrails, injected compact context flags + recent user snippets for comparison questions, expanded comparison keyword handling (slowest/fastest/best/worst/most/least/hardest/easiest), and added unit tests for the pure context builder to ensure we ask for return date instead of assuming 365‑day/all‑time scope. Commit: b07df78.
- **2026-01-25 (Phase 10 / Sprint 2 - accepted, beta-ready reasoning)**: Dogfood-verified the full Coach lifecycle and patched the last trust seams: added a pre-shortcut “coming back” clarification guardrail (cannot be bypassed by deterministic paths), hid internal context injections from the chat transcript/history, and added a focused unit test to lock the behavior. Commit: 5256e60 (builds on b07df78).
- **2026-01-25 (Phase 10 / Sprint 2 - accepted, streaming + timeout hardening)**: Hardened Coach chat delivery to eliminate trust-breaking cutoffs and client-side timeouts: added SSE streaming endpoint (`/v1/coach/chat/stream`) with heartbeats + chunked deltas, hardened SSE headers (no buffering/keep-alive), raised max wait to 120s (configurable) with a graceful “partial + retry” fallback, fixed frontend truncation (TextDecoder flush + trailing packet handling + CRLF normalization), and auto-scrolls to keep the tail visible while streaming. Dogfood verified full streamed response (no timeout, complete tail). Commit: 0ba19b2.
- **2026-01-25 (Phase 10 / Sprint 2 - accepted, beta-ready intake & reasoning)**: Added a production-beta fallback for thin/no connected history: new low-friction baseline intake questions (runs/week, weekly volume, longest run, return-from-break + date) captured only when history is thin; onboarding status now detects thin history and surfaces baseline-needed; Coach uses the baseline with an explicit “using your answers” banner and conservative-mode guidance (≤~20% ramp, ask pain before hard sessions); and when real data arrives, the UI prompts a non-silent “Rebuild plan?” CTA (no silent overwrite). Removed age-based hard caps per N=1 learning philosophy. Commit: 95a5bea.
- **2026-01-25 (Phase 10 - complete)**: Full Coach Action Automation delivered across 2 sprints: (1) backend schema/endpoints/tests (propose/confirm/reject, validation, idempotency, transactional apply); (2) frontend ProposalCard + chat integration (diff/reason/risks/buttons, confirm → receipt, reject/error handling). All CI-gated, documented. Commits: see prior Sprint entries. Phase 10 closed.
- **2026-01-25 (Beta prep - complete)**: Production-beta operational readiness: re-verified invite-only gating boundaries (register + OAuth + onboarding), added Phase 10 Coach Action monitoring (Ops Pulse counts + top failure reasons), added structured telemetry (logs + Sentry breadcrumbs) for propose/confirm/apply/reject/failed, ensured coach applies emit `plan_modification_log` audit entries (`source="coach"`), and added an end-to-end local dogfood script plus a beta rollout checklist doc. Commit: 04679ce.
- **2026-01-25 (Phase 10 - complete)**: Phase 10 MVP is beta-ready: (1) backend proposal lifecycle + deterministic apply (`/v2/coach/actions` propose/confirm/reject, validation, idempotency, transactional safety) and integration tests; (2) athlete-facing ProposalCard UX (diff/reason/risks, confirm → receipt, reject/error handling) wired into Coach chat; (3) production-rigor hardening (a11y, idempotent confirm UX, retry-on-failure, expanded Jest coverage) plus beta ops visibility (Ops Pulse + telemetry + audit) and dogfood script. Commits: 279d20d, 2336629, cb38191, 04679ce.
- **2026-01-25 (Beta prep fixes)**: Fixed Strava OAuth callback stability and local-network return-path safety: corrected `strava_callback` signature ordering (prevented API startup SyntaxError), added LAN-safe redirect selection in OAuth callback (handles local dev vs remote frontend), and hardened Coach Action Automation confirm flow to allow safe retry from `failed` proposals (clear error, preserve `confirmed_at`) with an expanded integration test covering repair + retry → applied. Commit: ee7b3ce.

---

## Guiding Principles (non-negotiable)
- **N=1 truth**: no hallucinated metrics; claims must be grounded in the athlete’s data and cite receipts.
- **Viral-safe by default**: spikes must queue and degrade gracefully, not break users.
- **Operator-first**: owner/admin can diagnose and fix athlete issues without DB access.
- **Uniform UX**: pages should feel like one product (visual hierarchy, tone, empty/loading states, consistent actions).
- **Primary outcomes are multi-objective**: efficiency (pace@HR / HR@pace), PBs, age-graded %, and body composition. Inputs are evaluated against outcomes.
- **Age-graded integrity**: use WMA standards consistently; reject “decline narrative” framing.
- **Show patterns, don’t prescribe**: UI should be factual, direct, and non-guilt-inducing (per `TONE_GUIDE.md`).

---

## Phase 1: Finish the Subscriber Experience (UX + Uniformity)

**Goal:** Make existing “logged-in” surfaces feel cohesive, legible, and trustworthy. This is polish + consistency, not new algorithms.

### Scope
- **Insights pages**
  - Standardize card layout, headings, and evidence display (date/value/source consistency).
  - Improve empty states (“no insights yet” should explain why + what to do next).
  - Ensure loading states are consistent and non-jarring.
- **Diagnostics page**
  - Clarify section order (start with the highest-signal summary; details below).
  - Reduce “maintenance” affordances in primary UI (rebuild/recompute as subtle icons or admin-only).
  - Make outputs copyable (structured blocks, consistent units, clear labels).
- **Cross-page consistency**
  - Navigation consistency (labels, active states, grouping).
  - Typography and spacing consistency (same density rules).
  - Terminology alignment (ex: “PB” vs “Personal Best”; “TSB” label clarity).
  - Tone compliance: remove prescriptive/guilt copy; ensure “optional” language where applicable (see `TONE_GUIDE.md`).
  - Visual system enforcement: shared background/container/card defaults (see `apps/web/STYLE_GUIDE.md`).

### Definition of Done
- **UX**: key pages have consistent visual hierarchy and no “debug vibes.”
- **Trust**: all data-backed claims show clear provenance (evidence/receipt where applicable).
- **Manifesto alignment**: efficiency and age-graded signals are easy to find and consistently labeled across pages.
- **No regressions**: existing functional flows remain intact (coach, plans, PBs).

### Risks / Watch-outs
- Avoid adding heavy new components that slow pages down.
- Avoid exposing dangerous maintenance actions to non-admin users.

---

## Phase 2: Public Pages (Landing + About)

**Goal:** Build a coherent “front door” that communicates the manifesto clearly and converts the right users.

### Scope
- **Landing page**
  - Copy update to reflect: **N=1** + “sweat and grit are the cover charge.”
  - Tone: **high-performance / inclusive** (Boulder vibe), not exclusive.
  - Primary CTA dominates (“Get Started”).
  - Demote maintenance/ops controls (no prominent “rebuild” style actions).
- **About page**
  - Explain: N=1 philosophy, “no motivational fluff,” evidence/receipts, and how Strava data powers the platform.
  - Include manifesto truths:
    - whole-person inputs (sleep/nutrition/work patterns) mapped to outputs (efficiency/PBs/body comp)
    - WMA age-graded standard + reject “decline narrative”
  - Add clear expectations: onboarding steps, what users will see first, and what “ingestion” means (in plain language).

### Definition of Done
- **Clarity**: a new visitor understands what StrideIQ is and what happens after clicking CTA.
- **Conversion path**: CTA routes cleanly into signup/onboarding without dead-ends.

### Risks / Watch-outs
- Don’t overpromise speed of ingestion; promise transparency + progress.

---

## Phase 3: Onboarding Workflow Completion + Refinement (“Latency Bridge”)

**Goal:** New user reaches a meaningful, populated dashboard without waiting in confusion.

### Target Flow
**Signup → Strava Auth → Questionnaire → Dashboard**

### Scope (Backend + Frontend choreography)
- **Signup**
  - Determine gating policy (invite/allowlist) and implement server-side enforcement (cannot be bypassed).
- **Strava connect**
  - On success: immediately enqueue background ingestion (at least the cheap index pass).
- **Questionnaire**
  - Provide 60–90 seconds of meaningful setup while ingestion runs (all optional-friendly; no “unlock” language).
  - On submit: route to dashboard with an ingestion progress indicator.
- **Dashboard**
  - Must render partial data gracefully:
    - show what’s available immediately
    - show ingestion status + what’s still processing
    - avoid “empty dashboard” ambiguity

### Definition of Done
- **No dead air**: user is never stuck wondering “is it working?”
- **Deterministic progress**: user can see what’s done and what remains.
- **Performance**: onboarding does not require long-running HTTP requests.

### Risks / Watch-outs
- Strava rate limits: onboarding must **queue**, not spike error rates.
- If user has minimal Strava history, UX must explain what the system can/can’t infer yet.

---

## Phase 4: Admin “Heartbeat” (Owner/Admin Console)

**Goal:** You (and future admins/employees) can safely operate the system: diagnose, fix, support, and moderate.

### Scope (MVP)
- **Access model**
  - Owner + admins + a safe “demo mode” for investor/buyer walkthroughs.
- **Athlete ops**
  - Search athlete (email/name/id)
  - View integration state, ingestion status, last errors, last tasks
  - Actions: re-run ingestion tasks, regenerate PBs, clear coach thread, etc.
- **Security/moderation**
  - Block/unblock athlete
  - Password reset (production-standard) + one-time temp password (urgent)
- **Audit log (non-negotiable)**
  - Record actor, target, action, timestamp, and what changed

### Definition of Done
- **No DB needed** for common support tasks.
- **Every admin action is auditable**.
- **Safe defaults**: dangerous actions are protected and clearly labeled.

---

## Phase 5: Operational Visibility + Reliability

**Goal:** The system is debuggable under real usage without guesswork.

### Scope
- Dashboards for ingestion backlog, error rate, and “stuck athletes.”
- Background job retry strategy (what retries, when, and why).
- Rate-limit handling observability (429 rates, wait times, retry-after).
- Incident playbook: “what to check first” when something breaks.

### Definition of Done
- You can answer: **who is stuck, why, and what button fixes it**.

---

## Phase 6: Subscription/Tier/Payment Productionization

**Goal:** Consistent entitlements + upgrade paths without fragile hardcoding.

### Scope
- Define tier semantics (free/pro/elite/etc.) and map to feature flags.
- Purchase/upgrade flows (Stripe or equivalent).
- Trial/invite grants (time-bound) for influencers and early users.
- Downgrade behavior (what happens to plans/features/data access).

### Definition of Done
- Entitlements are deterministic and testable.
- Support can resolve billing/entitlement issues from the admin console.

---

## Phase 7: Data Provider Expansion (Garmin/Coros readiness)

**Goal:** Extend the “effort + activity” model beyond Strava without rewriting analytics.

### Scope
- Canonical provider abstraction (activities, laps/splits, best-efforts equivalents).
- Ingestion pipeline parity (idempotent, resumable, observable).

### Implementation (v1: file import)
- **Backend**
  - `AthleteDataImportJob` table as the operational truth for import runs (queued/running/success/error + bounded stats).
  - Shared uploads directory between API + worker (mounted to `/uploads`).
  - Upload endpoint(s) that create jobs and enqueue Celery processing.
  - Safe zip extraction (zip-slip prevention + extraction byte cap).
  - Garmin DI_CONNECT parsing (start with `*_summarizedActivities.json`) + unit conversion + canonical `Activity` inserts with provider/external id idempotency.
  - Best-effort cross-provider dedup by time+distance to avoid duplicates when Strava already imported the same run.
- **Web**
  - Settings surface for Garmin file import (feature-flagged), showing upload + last N jobs.
- **Security**
  - Legacy Garmin username/password connect endpoints are admin-only and gated behind an explicit “legacy” flag (default off).

### Definition of Done
- Garmin import works end-to-end (upload zip → job queued → worker import → Activities appear).
- Import is safe-by-default (zip-slip blocked, size-bounded, no raw file content logged).
- Import is idempotent (provider+external id unique constraint enforced; reruns don’t duplicate).
- Ops visibility exists (job status + stats; ingestion state updated for provider).
- Settings UI shows upload + recent job history for the athlete.

---

## Phase 8: Security, Privacy, Compliance Hardening

**Goal:** Make it safe to grow users without creating liabilities.

### Scope
- Access control review (admin vs athlete boundaries).
- Token handling and rotation policies.
- GDPR/delete/export workflows validated end-to-end.
- Secrets management and production config checks.

---

## Phase 9: Automated Release Safety (Golden Paths + CI)

**Goal:** Prevent regressions on critical flows.

### Scope
- “Public conversion” golden path (landing → signup → onboarding connect status → dashboard).
- “Subscriber value” golden path (membership/trial UI + paid surfaces remain coherent: Insights evidence cards, PBs table, Coach evidence/receipts).
- “Revenue + ingestion seams” golden path (Stripe webhook signature validation, entitlement transitions, ingestion pause guardrails).
- “Plan generation” golden path (standard plan preview/create shape remains stable; model-driven generation remains tier-gated).
- CI gate: run the highest-value checks on every merge.

### CI golden paths (explicit contract)

**Backend smoke (`backend-smoke`)**
- Runs these fast integration tests (append-only list in `.github/workflows/ci.yml`):
  - `tests/test_phase3_onboarding_golden_path_simulated.py`
  - `tests/test_phase5_rate_limit_deferral.py`
  - `tests/test_admin_actions_onboarding_ingestion_block.py`
  - `tests/test_phase7_garmin_file_import_e2e.py`
  - `tests/test_phase8_security_golden_paths.py`
  - `tests/test_phase8_impersonation_high_risk_blocks.py`
  - `tests/test_phase8_token_jwt_invariants.py`
  - `tests/test_phase9_backend_smoke_golden_paths.py`

**Frontend smoke (`frontend-test`)**
- Runs a small Jest “smoke” list (explicit filenames in `.github/workflows/ci.yml`), including:
  - `admin-access-guard.test.tsx`
  - `admin-ops-visibility.test.tsx`
  - `home-latency-bridge.test.tsx`
  - `home-latency-bridge-queued.test.tsx`
  - `home-ingestion-paused-banner.test.tsx`
  - `coach-scroll-layout.test.tsx`
  - `landing-cta-register.test.tsx`
  - `onboarding-connect-import-status.test.tsx`
  - `settings-trial-membership.test.tsx`
  - `plans-model-driven.test.tsx`
  - `plan-create-gating.test.tsx`
  - `subscriber-value-deep-dive.test.tsx`

### Local run instructions

**Backend smoke (Docker)**
- `docker compose exec -T api pytest -q <list from .github/workflows/ci.yml>`

**Frontend smoke (Docker)**
- `docker compose run --rm --build web_test npm test --silent -- <same file list from .github/workflows/ci.yml>`

### Release gating (branch protection)

When Phase 9 is enforced, branch protection should require these checks (names must match CI job names exactly):
- `Backend Smoke (Golden Paths)`
- `Frontend Tests (Jest)`
- `Security Scan`

**Ops checklist (GitHub UI)**
- Navigate to: repository **Settings** → **Branches** → **Branch protection rules** → **Add rule**
- **Branch name pattern**: `main` (and `develop` if you gate that branch too)
- Enable:
  - **Require a pull request before merging**
  - **Require status checks to pass before merging**
    - Check **Require branches to be up to date before merging**
    - Add required checks:
      - `Backend Smoke (Golden Paths)`
      - `Frontend Tests (Jest)`
      - `Security Scan`
- Recommended (optional, but good defaults for safety):
  - **Require approvals** (at least 1)
  - **Dismiss stale approvals when new commits are pushed**
  - **Require conversation resolution before merging**

---

## Phase 10 (Post-Phase 9): Coach Action Automation (Propose → Confirm → Apply) (HIGH PRIORITY)

**Owner intent:** After Phase 9 is complete (golden paths + CI gates), prioritize unlocking **coaching automation** in a way that preserves the Coach **trust contract** and the platform’s **auditability**.

**Goal:** The Coach can propose precise training changes; the athlete explicitly confirms; the system applies changes via deterministic plan-modification services. **No autonomous execution.**

### Product contract (non-negotiable)
- **Explicit confirmation**: nothing modifies the athlete’s plan until the athlete confirms.
- **Deterministic execution**: the “apply” step is performed by existing deterministic services/endpoints (not by free-form model output).
- **Auditable**: propose/confirm/apply/fail events are append-only and attributable (actor/target/reason/payload).
- **Safe-by-default**: only allow a small, well-defined action catalog behind a feature flag.

### Action catalog (MVP)
MVP should start with an allowlist of “safe, reversible” actions that map cleanly to existing plan operations:
- **Swap days** (move planned workouts across days within a bounded window)
- **Adjust load** (scale a planned workout up/down within validated bounds)
- **Replace workout (template-based)** (swap a planned workout for a known `WorkoutTemplate` variant)
- **Skip / restore** (toggle `skipped` for a planned workout)

Out of scope for MVP (do later, after safety/telemetry exists):
- **Add new workouts** (creates new calendar objects; easy to misuse without constraints)
- **Modify future weeks globally** (requires stronger guardrails and rollback tooling)

### UX requirements (web)
- In Coach chat, proposals render as a **structured “Proposed changes” card** with:
  - **Diff view** (before/after for each affected workout)
  - **Reason** in plain language
  - **Risk notes** (when relevant; non-alarmist)
  - Buttons: **Confirm & apply**, **Reject**, **Ask a follow-up**
- On confirm, show an **apply receipt**: exactly what changed, with timestamps.
- If apply fails, show a deterministic error and keep the proposal for retry (no silent drops).

### Backend requirements (API)
- Add a durable proposal object (example name): `CoachProposedAction` / `CoachActionProposal`
  - Fields (minimum): `id`, `athlete_id`, `created_by` (athlete/admin/coach-system), `status` (proposed/confirmed/rejected/applied/failed),
    `actions_json` (validated schema), `reason`, `created_at`, `confirmed_at`, `applied_at`, `error` (nullable)
- Endpoints (shape; names can vary, but responsibilities must match):
  - `POST /v2/coach/actions/propose` → validates and stores proposal (does not apply)
  - `POST /v2/coach/actions/{id}/confirm` → athlete-confirmed transition + apply (transactional)
  - `POST /v2/coach/actions/{id}/reject` → marks rejected with optional reason
- **Validation**: server-side schema validation + bounds checks; reject proposals that exceed limits (count of actions, date range, intensity bounds).
- **Idempotency**: confirm/apply should be safe against retries and double-submits.
- **Authorization**:
  - Only the athlete (or owner/admin with explicit permission) can confirm/apply.
  - If using impersonation, confirm/apply should be either blocked or explicitly audited with elevated labeling.

### Safety + ops requirements
- Feature flag: `coach.action_automation_v1` (default off)
- Metrics/logging: counts of proposed/confirmed/applied/failed; top failure reasons; latency.
- Audit events (examples):
  - `coach.action.proposed`, `coach.action.confirmed`, `coach.action.rejected`, `coach.action.applied`, `coach.action.apply_failed`

### Test plan (required for acceptance)
- **Backend**:
  - Unit tests for action validation/bounds.
  - Integration “golden path”: propose → confirm → apply modifies plan exactly once + emits audit events.
  - Regression: proposal cannot apply without confirm; confirm cannot apply twice.
- **Frontend**:
  - Renders proposal card with diff + buttons.
  - Confirm triggers apply and displays receipt; reject updates state.

---

## Phase 11: Coach LLM Upgrade (Multi-Model Tiering)

**Owner intent:** Upgrade Coach to use best-in-class reasoning models with cost-optimized tiering. Provide VIP beta user (exercise physiologist) with premium experience while maintaining sustainable unit economics at scale.

**Goal:** Claude Sonnet 4.5 as production default (93% of Opus quality at 20% cost), Claude Opus 4.5 for VIP/Elite tier, Mistral Large 3 as rate-limit fallback.

**Research:** See `docs/LLM_MODEL_RESEARCH.md` for benchmarks, pricing, and architecture.

### Model Selection (verified January 2026)

| Model | Role | Cost/Athlete/Mo | GPQA Score |
|-------|------|-----------------|------------|
| Claude Sonnet 4.5 | Production default | $0.16 | 68.2 |
| Claude Opus 4.5 | VIP/Elite tier | $0.45 | 73.1 |
| Mistral Large 3 | Rate limit fallback | $0.04 | 64.8 |
| GPT-5 Mini | Low-risk scaffolded only | $0.02 | 62.4 |

### Tiering Logic

```
Query → [Risk Classifier]
           ├── HIGH (injury/recovery/load) → Sonnet minimum
           ├── MEDIUM (coaching advice) → Sonnet
           └── LOW (summaries/lookups) → GPT-5 Mini (scaffolded)
           
Athlete Tier Override:
  ├── VIP/Elite → Always Opus 4.5
  └── Standard → Risk-based routing
```

### Scope

**Sprint 1: Anthropic Integration**
- [ ] Add `anthropic` SDK dependency
- [ ] Add `ANTHROPIC_API_KEY` to secrets management
- [ ] Create Claude adapter matching OpenAI assistant pattern
- [ ] Add feature flag: `coach.use_claude_sonnet`
- [ ] Migrate standard queries from GPT-4o → Claude Sonnet 4.5

**Sprint 2: Tiering + VIP Support**
- [ ] Implement `classify_query_risk()` for model routing
- [ ] Add `VIP_ATHLETES` feature flag for Opus routing
- [ ] Add athlete tier → model mapping (Free/Pro/Elite)
- [ ] Test with VIP user's actual training data

**Sprint 3: Rate Limit Resilience**
- [ ] Add `mistralai` SDK dependency
- [ ] Implement fallback handler (Anthropic 429 → Mistral)
- [ ] Add request queuing for sustained load
- [ ] Cache common responses (definitions, FAQs)

**Sprint 4: Cost Optimization**
- [ ] Implement prompt caching (90% savings on repeated context)
- [ ] A/B test: Sonnet vs GPT-5 Mini on low-risk queries
- [ ] Add per-model cost tracking for analytics

### Definition of Done
- [ ] VIP user (exercise physiologist) routes to Claude Opus 4.5
- [ ] Standard users route to Claude Sonnet 4.5
- [ ] Low-risk queries (summaries) use GPT-5 Mini (scaffolded)
- [ ] Anthropic rate limits trigger Mistral fallback (no user-visible errors)
- [ ] LLM costs < 2% of subscription revenue at scale

### Cost Projections

| Scale | Sonnet Default | With Tiering |
|-------|----------------|--------------|
| 500 athletes | $80/mo | $60/mo |
| 5,000 athletes | $800/mo | $600/mo |
| % of MRR | 1.3% | 1.0% |

### Critical Warnings
1. **Never unscaffolded GPT-5 Mini** for injury/recovery advice
2. **Avoid DeepSeek/Grok** — hallucinate on physiology
3. **Anthropic rate limits** at ~50 RPM — queue + fallback required
4. **Latency is a feature** — 2s thoughtful > 0.5s generic

---

## Suggested Execution Order (recommended)
1. **Phase 1**: Logged-in UX uniformity (so new users land in a polished product)
2. **Phase 2**: Landing + About (so acquisition messaging matches reality)
3. **Phase 3**: Onboarding choreography (so conversion doesn’t drop)
4. **Phase 4**: Admin heartbeat (so you can safely scale support)
5. **Phase 5**: Ops visibility (so spikes become manageable)
6. **Phase 6+**: Payments and broader productionization
7. **Phase 9 → Phase 10**: After release safety gates are in place, prioritize Coach Action Automation (propose → confirm → apply)
8. **Phase 11**: Coach LLM Upgrade (after Garmin/Strava API approvals, or in parallel if capacity allows)

