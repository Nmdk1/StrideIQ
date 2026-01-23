## StrideIQ: Phased Work Plan (Private Beta → Viral-Safe Launch)

**Date:** 2026-01-20  
**Owner intent:** Invite-led launch with near-term open signups, “viral-safe” behavior under load spikes.  
**Constraint:** Do not start implementation work until explicit approval per phase.

**Manifesto + voice sources of truth:**
- Product manifesto: `_AI_CONTEXT_/00_MANIFESTO.md`
- Brand voice: `TONE_GUIDE.md`

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
| 3 | Onboarding Workflow (“Latency Bridge”) | Not started | |
| 4 | Admin “Heartbeat” | Not started | |
| 5 | Operational Visibility + Reliability | Not started | |
| 6 | Subscription/Tier/Payment Productionization | Not started | |
| 7 | Data Provider Expansion (Garmin/Coros) | Not started | |
| 8 | Security, Privacy, Compliance Hardening | Not started | |
| 9 | Automated Release Safety (Golden Paths + CI) | Not started | |

---

## Progress Ledger (append-only)

- **2026-01-20**: Established phased plan and workflow contract. Updated guiding principles to match the manifesto and clarified outcomes are multi-objective (efficiency, PBs, age-graded %, body comp).
- **2026-01-21 (Phase 1 / Sprint 1)**: Fixed 3 blockers: (1) Calendar day drilldown “Coach” action 500 due to missing `coach_chat` table (added migration), (2) Plan adjustments (“swap days” / “adjust load”) 500 due to missing `plan_modification_log` table + swap-days request/schema mismatch (added migration + fixed endpoint), (3) Analytics “Why This Trend” 500 caused by schema drift in `DailyCheckin` fields (made attribution collection backward-compatible). Next: hover uniformity, chart styling, and Insights trust repairs.
- **2026-01-22 (Phase 1 / Sprint 2 - partial, degraded session)**: Attempted to enforce **uniform UX** by unifying the global page background and removing `bg-[#0a0a0f]` styling drift across many logged-in routes/components. **Result:** base background is now consistent (`bg-slate-900`), but **Home still reads as a different theme** because it relies on translucent card surfaces (`bg-slate-800/50`, nested `bg-slate-900/30`) while Analytics/Calendar primarily use solid `bg-slate-800 border-slate-700`. Next: standardize Home to match Analytics card surfaces, and introduce a shared page wrapper component to prevent future drift.
- **2026-01-21 (Phase 1 / Sprint 2 - accepted)**: Fixed Home dashboard “trapped whitespace” and row-height rhythm issues (single Signals spans full width; row cards stretch to equal height; “Yesterday” is no longer orphaned and is stacked with Quick Access). Fixed trust-breaking Insights intelligence generation by replacing placeholder/incorrect logic (ISO week bug, “need more history”) with time-scoped, evidence-backed “micro insights” computed from ~2 years of run history and explicit rebuild/return-to-run context. Next: improve the correlation engine so every candidate input is measurable and evaluated (individually + in defined clusters) against explicit outcomes (efficiency trend, PBs, injury proxies) with receipts and minimum-sample guards.
- **2026-01-22 (Phase 1 / Sprint 3 - accepted, Phase 1 complete)**: Hardened the Coach “trust contract” so answers stay conversational while remaining auditable: receipts are now compact and collapsible in the UI, evidence is human-readable (date + run name + key values), and units preference (miles/min‑mi) is enforced and persisted. Added a Phase 1 mobile QA sweep script (detects horizontal overflow and verifies Coach mobile behavior). Removed hardcoded credential strings from repo artifacts and added a CI guardrail to prevent regressions. Phase 1 is complete; Phase 2 (public pages) is approved to start.
- **2026-01-23 (Phase 2 / Sprint 1 - accepted, Phase 2 complete)**: Refined public “front door” pages to align with the manifesto and reduce cognitive load: landing page copy/hierarchy tightened around N=1 intelligence, evidence-backed coaching, and a clear conversion path; About page added as the canonical “why/how” for interested athletes, including founder story and race photo. Removed temporary preview/mock routes and ensured navigation/footer surface the new About page.

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
- “Public conversion” golden path (landing → signup → Strava → questionnaire → dashboard).
- “Subscriber value” golden path (PBs/insights/coach citations).
- “Plan generation” golden path.
- CI gate: run the highest-value checks on every merge.

---

## Suggested Execution Order (recommended)
1. **Phase 1**: Logged-in UX uniformity (so new users land in a polished product)
2. **Phase 2**: Landing + About (so acquisition messaging matches reality)
3. **Phase 3**: Onboarding choreography (so conversion doesn’t drop)
4. **Phase 4**: Admin heartbeat (so you can safely scale support)
5. **Phase 5**: Ops visibility (so spikes become manageable)
6. **Phase 6+**: Payments and broader productionization

