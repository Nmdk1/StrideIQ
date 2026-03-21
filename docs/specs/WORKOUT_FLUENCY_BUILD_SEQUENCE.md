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
| Long / medium-long / MP / HMP | **8** `approved` + **1** `draft` (MP over-under miles) | `long_run_pilot_v1.md` |
| Easy / recovery / easy+strides / rest / hills / strides | **Partial** — **4** approved + **2** draft neuromuscular rows | `easy_pilot_v1.md` (rollup) |
| VO2 intervals | **9** `approved` + **3** `draft` (advanced / engine-forward) | `intervals_pilot_v1.md` |
| Repetitions stem + long hill-repeat progressions | Deferred per spec | after core pilots stable; short **easy + hill sprints** KB’d as **`draft`** in Pilot 3 |

**Exit Phase 1 when:** Founder SME has **`approved`** **each pilot file in v1 scope** (explicitly list which stems ship in v1—may exclude deferred rows). **As of registry v0.2.20 (2026-03-22):** threshold **fully** **`approved`**; long pilot **8**× **`approved`** + **1**× **`draft`**; easy pilot **4**× **`approved`** + **2**× **`draft`**; intervals pilot **9**× **`approved`** + **3**× **`draft`**; **`repetitions`** / other deferred rows still per table above. **SME-approve** remaining **`draft`** rows in founder **v1** scope before Phase 3. KB variants are **inputs to deterministic plan construction** (spec §7.0).

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

**Prerequisite:** Phase 1 **complete for all v1-scoped stems** (founder gate above) **and** Phase 2 **green** — do not wire half the toolbox.

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
