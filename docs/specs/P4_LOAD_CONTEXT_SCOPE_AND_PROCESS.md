# P4 Load Context — Delivery scope & process

**Status:** Approved (process locked; implementation governed by technical spec rev 2026-03-22)  
**Date:** 2026-03-20  
**Read with:** `docs/FOUNDER_OPERATING_CONTRACT.md`, `docs/specs/PLAN_COACHED_OUTPUT_AND_LOAD_CONTRACT.md`, `docs/specs/P4_LOAD_CONTEXT_TECHNICAL_SPEC.md` (after scope approval)

---

## 1. Purpose

Lock **how** StrideIQ ships **P4** (history-aware load contract for `plan_framework`): **semi-custom** (and optionally **standard**) generation uses synced **`Activity`** history so easy-long and volume baselines reflect **recent reality**, not only tier templates and questionnaire fields—without conflating this work with **P5** (check-in / completion adaptation) or **fluency Phase 4** (registry matrix / codegen).

---

## 2. Approval sequence (logical gates)

| Order | Artifact | Approver | Outcome |
|-------|-----------|----------|---------|
| A | **This document** (scope + process) | Founder | Proceed to technical spec authoring / freeze |
| B | **`P4_LOAD_CONTEXT_TECHNICAL_SPEC.md`** | Founder (+ tech reviewer as you prefer) | Proceed to implementation |
| C | Per-slice **evidence** (pytest + CI; prod per release policy) | Founder / operator | Merge / deploy |

**Rule:** No implementation that changes athlete-facing plan behavior until **B** is approved. **Slice 0** may be documentation-only updates if spec says so.

---

## 3. Non-negotiables (from operating contract)

- **Scoped work only** — commits and PRs stay within the approved slice; no drive-by refactors.
- **CI is source of truth** — green on `main` (or branch policy) before claiming done; local pytest is necessary but not sufficient where CI has Postgres / full chain.
- **Evidence, not claims** — each slice closes with pasted or linked test output; final thread adds CI run + prod smoke notes.
- **Athlete trust** — history informs; **D3 intensity envelope** is not “unlocked” by long-run history alone (see load contract).
- **Suppression over hallucination** — if history is insufficient, fall back to current cold-start behavior; disclose via existing patterns where product already does.

---

## 4. In scope (P4 thread)

| ID | Slice | Intent |
|----|--------|--------|
| **0** | Metric & definition alignment | Single source of truth in docs for **30d L30** vs **ADR-061 105 min** long-run identification for *profile* vs **D1 90 min / 30d** for *P4 easy-long max in window*; note any intentional deltas. |
| **1** | `LoadContext` module | Deterministic builder from `athlete_id` + `db` + `reference_date`; exposes at minimum **`l30_max_easy_long_mi`** and inputs needed for **D4** / scaler `history_override`; **unit tests** with synthetic activities. |
| **2** | Wire **`generate_semi_custom`** | When `athlete_id` and `db` present: merge LoadContext into **starting volume** and **week-1 easy-long seed** per approved formulas; **no** change to endpoints’ public JSON schema unless technical spec explicitly adds fields. |
| **3** | Integration tests + regression | Router or service-level tests proving semi-custom output shifts under fixed fixtures; guardrails so questionnaire **under**-reporting does not collapse a high-mileage athlete incorrectly. |
| **4a** | **Optional** standard path — **implementation** | Code + tests for history-aware **`generate_standard`** when athlete is known—**default off** or behind **explicit flag** until **4b**. |
| **4b** | **Optional** standard path — **product enable** | Founder decision: enable for authenticated `/standard` create/preview; monetization / positioning text unchanged unless spec’d. |

**Explicitly out of scope for this thread**

- **P5:** adaptation from `DailyCheckin` / completion / ≥3 weeks / ≥70% gates.
- **Fluency registry Phase 4:** full eligibility matrix + codegen (`WORKOUT_FLUENCY_BUILD_SEQUENCE.md`).
- **LLM** plan text changes beyond existing narrative layer contracts.
- **Replacing** `AthletePlanProfileService` for **custom** plans—P4 **may read from or align with** it per technical spec, not rewrite 1C.

---

## 5. Build loop (per slice)

Each slice repeats until **pass**:

1. **Spec pointer** — Technical spec section for this slice is the authority; update spec if reality forces it (with approval for material changes).
2. **Tests first (blockers)** — Add or extend failing tests that encode acceptance criteria.
3. **Implement** — Minimal code to satisfy tests and spec.
4. **Retest** — Full targeted pytest set for P4 + required plan_framework regressions (listed in technical spec).
5. **Judge** — Checklist in technical spec § “Completion criteria”; if fail, fix and return to step 4.
6. **Proceed** — Next slice only when current slice judge is **pass**.

**Judge defaults**

- Correctness: assertions on deterministic fixtures.
- No silent definition fork: D1/D2/D4 match approved spec table.
- No new athlete-facing promises without copy/product review if user-visible strings change.

---

## 6. Final bar (end of P4 thread)

When slices **0–3** are complete and **4a/4b** per approval:

- **CI:** Required jobs green; paste run id or URL in handoff.
- **Production:** Deploy per `production-deployment` rule; core containers healthy; **smoke** per technical spec (e.g. authenticated path if touched).
- **Tech post / completion report:** One document or section covering problem, decisions, slices, test strategy, SHAs, CI, prod smoke, known limits, follow-ups (P5, D3 table, etc.).

---

## 7. Document control

| Version | Date | Notes |
|---------|------|--------|
| 0.1 | 2026-03-20 | Initial scope + process |
| 0.2 | 2026-03-22 | Builder go; constants + 4b YES; no structural change |

**Approval line (founder):** Scope + process approved: ______ date ______  

After approval, technical work is governed by **`P4_LOAD_CONTEXT_TECHNICAL_SPEC.md`**.
