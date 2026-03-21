# Workout fluency — build sequence (define → tools → wire)

**Intent:** Do the work in **three waves** so we do not wire half-baked definitions into live plan generation.

**Governing specs:** `WORKOUT_FLUENCY_REGISTRY_SPEC.md` (§2 P0 gate), `WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md`, `PLAN_GENERATION_VISION_ALIGNMENT_RECOVERY_SPEC.md`.

---

## Phase 1 — Define (knowledge base only)

**Goal:** Every workout **stem** the engine can emit has **approved** variant prose (or an explicit “no variants yet” stub) in `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/`.

| Track | Status (rolling) | Files / notes |
|-------|-------------------|---------------|
| Threshold | **Approved** (9 variants) | `threshold_pilot_v1.md` |
| Long / medium-long / MP / HMP | **Partial SME** (1/8 **approved**, 7 **`draft`**) | `long_run_pilot_v1.md` |
| Easy / recovery / easy+strides | Not started | future `easy_pilot_v1.md` |
| VO2 intervals | Not started | future `intervals_pilot_v1.md` |
| Reps / strides / hills | Deferred per spec | after core pilots stable |
| Rest | Optional one-liner | trivial |

**Exit Phase 1 when:** Founder SME has **`approved`** each pilot file you care about for v1 product scope (not every stem on day one—scope v1 explicitly). **As of registry v0.2.12:** threshold pilot **approved**; long-family pilot **per-variant SME** — **1** **`approved`**, **7** **`draft`** (`long_run_pilot_v1.md` rollup is authoritative); easy / VO2 / etc. still **not started** until scoped.

---

## Phase 2 — Tools (no behavior change to plans yet, or only test hooks)

**Goal:** Machine-readable registry + checks so definitions cannot drift silently.

1. **Single registry artifact** (e.g. YAML/JSON) generated from or validated against the markdown pilots—or authored once and mirrored in KB.
2. **Schema validation** — unique ids, required fields, `build_context_tag` ⊆ §6.3, `volume_family` enum, `sme_status` only `approved` in any “shipping” slice.
3. **ID → engine map** — table: `workout_variant_id` → `workout_type` / scaler entry / aliases (matches `workout_scaler.scale_workout`).
4. **Contract tests** — given fixture athlete + resolved primary tag, expected **eligible** variant set (or suppressed) is stable; no LLM.
5. **Optional:** CLI or `pytest` module that fails CI when approved rows violate rules.

**Exit Phase 2 when:** CI runs the validator + mapping tests green on `main`.

---

## Phase 3 — Wire (runtime)

**Goal:** Planner / scaler / narrative use the registry **without** breaking athlete-truth or P0 recovery contracts.

1. **P0 gate** green or **documented waiver** per PR (`P0-GATE:`) when touching `plan_framework` / plan routes.
2. **Dispatch** — internal `workout_variant_id` (or equivalent) plumbed from phase builder / scaler decisions.
3. **Narrative / UI** — athlete-facing copy can cite registry rationale keys where tier allows.
4. **Scenario tests** — distance × experience × injury × cold-start paths from the playbook (Path D).

**Exit Phase 3 when:** End-to-end plan output reflects variant intent under tests + smoke + your spot-check.

---

## Iteration (Path F)

Gap found in prod or review → update spec → update registry → update tests → re-run CI → deploy → paste evidence (SHA, CI URL, smoke).

---

*Created 2026-03-22 — aligns with founder direction: define all (in scope), build tools, then wire.*
