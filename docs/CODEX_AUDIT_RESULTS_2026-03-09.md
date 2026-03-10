# Codex Full System Audit — Results

**Date:** March 9, 2026
**Author:** Codex (Tech Advisor)
**Requested by:** Top Advisor
**Purpose:** Machine-extracted, path-level audit of full system wiring state

---

## Evidence Baseline

- Backend router files scanned: **57**
- Backend endpoint declarations found: **330**
- Runtime registered FastAPI paths: **318**
- Frontend API refs (non-test) found: **178**
- Frontend refs matched to backend routes: **176/178**
  - the 2 misses are parser artifacts, not real endpoint mismatches (`insightFeedback` string interpolation parsing, `preferences` normalized mismatch)
- Backend endpoints directly consumed by frontend: **151/330**
- Frontend pages found: **61**
- Hidden/non-nav pages detected: **28** (not all are bugs; many are intentional deep links)

Artifacts generated:
- `tmp_full_audit_inventory.json`
- `tmp_audit_unmatched_clean.json`
- `tmp_router_coverage.json`
- `tmp_audit_path_validity.json`

---

## Critical Breaks (actually broken paths)

- **`/v1/lab-results*` is dead at runtime**
  - `apps/api/routers/lab_results.py` exists
  - `apps/api/main.py` imports `lab_results` but never includes `lab_results.router`
  - runtime check confirms `/v1/lab-results` not registered
  - why broken: router omission in app wiring

- **Frontend link to missing page `/lab-results`**
  - `apps/web/components/onboarding/EmptyStates.tsx` links to `/lab-results`
  - no `apps/web/app/lab-results/page.tsx` exists
  - why broken: UI link points to non-existent route

- **Frontend link to missing page `/plans`**
  - `apps/web/app/insights/page.tsx` links to `/plans`
  - no `apps/web/app/plans/page.tsx` exists (only `plans/[id]`, `plans/create`, `plans/preview`, `plans/checkout`)
  - why broken: wrong target route

---

## High-Severity Productization Gaps (built, but not correctly surfaced)

- **`/v1/progress/narrative` built, not used by active progress page**
  - backend route exists in `apps/api/routers/progress.py`
  - frontend hook exists in `apps/web/lib/hooks/queries/progress.ts` (`useProgressNarrative`)
  - active page `apps/web/app/progress/page.tsx` still uses `useProgressKnowledge`
  - why not working as intended: new narrative lane is dormant in UX

- **Daily intelligence backend lane is built but not wired into frontend**
  - `apps/api/routers/daily_intelligence.py` has `/v1/intelligence/*`
  - no meaningful frontend consumers found for `/v1/intelligence`
  - why not visible: no surface wiring

- **Discovery + Fingerprint are real, but discoverability is weak**
  - pages exist: `apps/web/app/discovery/page.tsx`, `apps/web/app/fingerprint/page.tsx`
  - not present in primary nav/top-level bottom tabs
  - why underperforming: reachable mainly by deep links/internal jumps

---

## Medium-Severity Path/Contract Risks

- **Plan resume path is partially implemented**
  - `apps/api/routers/plan_generation.py` `resume_plan` contains explicit TODO "recalculate future workouts"
  - current behavior: status flip to active, no schedule recompute
  - why risky: endpoint works syntactically, but behavioral contract is incomplete

- **Home request path still contains live correlation computation**
  - `apps/api/routers/home.py` -> `generate_why_context` -> `get_correlation_context` -> `analyze_correlations(...)`
  - why risky: performance/reliability coupling in primary surface

- **Large backend surface is intentionally non-frontend-consumed**
  - webhook/admin/import/internal capability routers (expected)
  - risk is not existence; risk is unclear product boundaries if treated as user-facing by mistake

---

## Full Frontend/Backend Domain Audit (wired-state)

- **Auth/Onboarding:** wired and functional; activation path exists.
- **Home:** wired and functional; contains latency/risk hotspot (live correlations).
- **Calendar:** wired and functional.
- **Activities/Analysis/Reflection/Workout-type/Attribution:** wired and functional.
- **Coach chat + streaming + history + suggestions:** wired and functional.
- **Progress knowledge:** wired and functional.
- **Progress narrative:** backend+hook built, page not switched -> partially wired.
- **Insights feed:** wired and functional; includes one broken `/plans` link.
- **Plans generation/editing:** largely wired; resume behavior partial.
- **Billing/settings:** wired and functional.
- **Fingerprint:** wired, functional, low discoverability.
- **Discovery/correlations:** wired, functional, low discoverability; combinations endpoint not surfaced.
- **Daily intelligence:** backend built, frontend unwired.
- **Lab results:** backend file exists but router not mounted; frontend links to missing page.
- **Diagnostics/admin ops:** wired and functional (admin-only).
- **Public tools:** wired and functional.
- **Webhook/import/provider internals:** backend-only by design.

---

## Proposed vs Built (explicit)

From contract/gated tests:
- xfail/NotImplemented phase-gated test scaffolds remain in:
  - `apps/api/tests/test_phase3c_n1_insights.py`
  - `apps/api/tests/test_phase4_50k_ultra.py`
  - `apps/api/tests/test_phase3b_workout_narratives.py`
  - monetization gate files with xfail/not-implemented contracts
- meaning: several roadmap capabilities are **proposed/gated**, not fully live.

---

## Key Findings for Immediate Action

1. **Speed:** `generate_why_context` → `get_correlation_context` → `analyze_correlations()` is a THIRD live correlation computation on the home request path. The two in `_build_rich_intelligence_context` and `compute_coach_noticed` were removed in commit `1df7eb6`, but this one survived in a different call chain.

2. **Visibility gap:** Daily intelligence has a full backend with zero frontend consumers. Progress narrative is built but dormant. Discovery and Fingerprint pages exist but aren't in primary navigation.

3. **Dead code / broken links:** Lab results router unmounted, onboarding links to 404, insights page links to non-existent `/plans` route. New athletes (Belle) could hit these.

---

## Next Step (Codex recommendation)

Create a single exhaustive ledger file in repo — every route/page/hook with status, failure reason, owner, and fix priority — so builder work is forced through this truth set instead of re-discovering gaps mid-wire.
