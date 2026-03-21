# Workout fluency — build sequence (define → tools → wire)

**Intent:** Do the work in **three waves** so we do not wire half-baked definitions into live plan generation.

**Governing specs:** `WORKOUT_FLUENCY_REGISTRY_SPEC.md` (§2 P0 gate), `WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md`, `PLAN_GENERATION_VISION_ALIGNMENT_RECOVERY_SPEC.md`.

**Founder gate (2026-03-22):** **Phase 3 wiring does not start** until **every run-type track in v1 scope** has SME-**approved** variant KB (or explicit stub) — not only threshold + long. Complete Phase 1 for **easy / VO2 / …** per scoped v1 table below, **then** Phase 2 tools, **then** Phase 3 (still subject to §2 P0).

---

## Phase 1 — Define (knowledge base only)

**Goal:** Every workout **stem** the engine can emit has **approved** variant prose (or an explicit “no variants yet” stub) in `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/`.

| Track | Status (rolling) | Files / notes |
|-------|-------------------|---------------|
| Threshold | **Approved** (9 variants) | `threshold_pilot_v1.md` |
| Long / medium-long / MP / HMP | **9** `approved` | `long_run_pilot_v1.md` |
| Easy / recovery / easy+strides / rest / hills / strides | **6** `approved` | `easy_pilot_v1.md` (rollup) |
| VO2 intervals | **12** `approved` (3 advanced ids KB-only until `_scale_intervals` ships shapes) | `intervals_pilot_v1.md` |
| Repetitions | **2** `approved` | `repetitions_pilot_v1.md` |
| Long hill-repeat progressions (sustained VO2 hills) | Deferred per spec | after core pilots + Phase 2 map stable |

**Exit Phase 1 when:** Founder SME has **`approved`** **each pilot file in v1 scope** (explicitly list which stems ship in v1—may exclude deferred rows). **As of registry spec v0.2.25 (2026-03-22; Phase 1 closure landed in rev 0.2.22):** v1-scoped pilot KB has **no** remaining **`draft`** rows in threshold, long, easy, intervals, or repetitions pilots (**38** variant rows **`approved`** in those files). Long **sustained VO2 hill-repeat** progressions remain **deferred** per table (not a pilot-file stub). Phase 2 tools + §2 P0 gate still apply before Phase 3 wiring. KB variants are **inputs to deterministic plan construction** (spec §7.0).

---

## Phase 2 — Tools (no behavior change to plans yet, or only test hooks)

**Goal:** Machine-readable registry + checks so definitions cannot drift silently.

**Shipped (2026-03-22):**

- **Artifact:** `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/workout_registry.json` — schema **0.2**; v1 **38** SME-**`approved`** rows (`id`, `stem`, `volume_family`, `sme_status`, `pilot`, sorted **`build_context_tags`** ⊆ §6.3). Prose stays in `*_pilot_v1.md`.
- **CI tests:** `apps/api/tests/test_workout_registry.py` — unique ids; closed enums; **`stem` → `workout_type`** ⊆ `WorkoutScaler.scale_workout` dispatch; **`## \`id\``** header set matches JSON per pilot; **JSON ↔ pilot `typical_build_context_tags` parity** (incl. Same-as references); **eligibility snapshot** stubs (primary tag + stem).
- **Engine stem inventory (existing):** `STEM_COVERAGE.md` + `test_stem_coverage_sync.py` — scaler/generator emission strings.

**Phase 2 status:** **Closed** at the shipped scope above (registry JSON **0.2** + CI parity tests). Deeper tooling listed below is **mandatory** but **scheduled after Phase 3** — it does **not** block starting Phase 3.

**Exit Phase 2 when:** CI runs **`test_workout_registry.py`** + **`test_stem_coverage_sync.py`** green on `main` (and repo’s standard API test job includes them — they live under `apps/api/tests/`). **Met.**

---

## Phase 3 — Wire (runtime)

**Status:** **Active** — next fluency workstream is runtime wiring (subject to §2 P0).

**Prerequisite:** Phase 1 **complete for all v1-scoped stems** (founder gate above) **and** Phase 2 **green** — do not wire half the toolbox.

**Goal:** Planner / scaler / narrative use the registry **without** breaking athlete-truth or P0 recovery contracts.

1. **P0 gate** green or **documented waiver** per PR (`P0-GATE:`) when touching `plan_framework` / plan routes.
2. **Dispatch** — internal `workout_variant_id` (or equivalent) plumbed from phase builder / scaler decisions.
3. **Narrative / UI** — athlete-facing copy can cite registry rationale keys where tier allows.
4. **Scenario tests** — distance × experience × injury × cold-start paths from the playbook (Path D).

**Exit Phase 3 when:** End-to-end plan output reflects variant intent under tests + smoke + your spot-check.

---

## Phase 4 — Mandatory registry enrichment (post–Phase 3 only)

**Intent:** Items previously listed as Phase 2 “optional” are **required**, but **only after** Phase 3 **exit** — so the selection matrix and runtime dispatch exist first; enrichment then hardens the machine contract against real code paths.

**Prerequisite:** Phase 3 exit satisfied (above).

**Mandatory deliverables:**

1. **Full eligibility matrix (contract tests)** — richer fixture athletes; **`build_context_tag` primary resolution** per `WORKOUT_FLUENCY_REGISTRY_SPEC.md` §6.3.1 (conservative precedence); **suppressed** / ineligible outcomes where applicable; supersedes tag ∩ stem **snapshot** stubs in `test_workout_registry.py` as the authoritative eligibility story.
2. **Codegen or CLI** — regenerate or validate **`workout_registry.json`** from pilot markdown **and/or** extend the artifact toward **full** §7 fields; must be **CI-enforced** (fail on drift).

**Exit Phase 4 when:** Both bullets are implemented, CI green, founder SME sign-off on matrix fixtures.

*Note: This “Phase 4” is **only** the workout-fluency ladder in this document — not `TRAINING_PLAN_REBUILD_PLAN.md` Phase 4 (50K).*

---

## Iteration (Path F)

Gap found in prod or review → update spec → update registry → update tests → re-run CI → deploy → paste evidence (SHA, CI URL, smoke).

---

*Created 2026-03-22 — aligns with founder direction: define all (in scope), build tools, wire, then **mandatory** deep registry enrichment (Phase 4). Updated 2026-03-22: Phase 2 closed; Phase 3 active; Phase 2 “optionals” → Phase 4 mandatory.*
