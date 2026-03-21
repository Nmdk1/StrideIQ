# Repetitions pilot — variant definitions (v1)

**Spec:** `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md` v0.2.24  
**Sequence:** `docs/specs/WORKOUT_FLUENCY_BUILD_SEQUENCE.md`  
**Stems covered:** `repetitions` (alias input: `reps` → same dispatch in `workout_scaler.scale_workout`)

**Engine reference:** `apps/api/services/plan_framework/workout_scaler.py` — `_scale_repetitions`. **Weekly cap:** Source B **5%** of weekly volume for repetition work (see `WORKOUT_LIMITS` in plan_framework).

**SME approval:** **Two** variant ids below are **`sme_status: approved`** — founder/builder **2026-03-22**. They match **what the scaler emits today** (200m early progression → 300m later). More variants (e.g. mixed sets, track vs road) are **future**; this file removes the “deferred with no KB” gap. Runtime wiring remains gated per spec §2.

---

## StrideIQ repetitions intent (SME — product)

**Not intervals, not threshold, not strides-only**

- **Repetitions** are **short** fast bouts (**about 200m–300m** in the current engine) with **full** recovery between reps. They train **turnover, power, and economy** without the **sustained** aerobic load of **VO2 intervals** or **threshold**.
- **Strides** (see **`easy_pilot_v1.md`**) are **lighter** and usually **shorter per rep**; repetitions are a **main-set** quality when the planner assigns this day.
- **VO2 intervals** (see **`intervals_pilot_v1.md`**) are **longer** reps at **interval** pace; repetitions use **`repetition`** pace from the **Training Pace Calculator** — **faster** than typical **5K race** rhythm in the calculator model.

**Pace**

- Use the calculator **repetition** output, with the same **±5 seconds per mile band idea** as threshold and intervals pilots: a **range**, not split-chasing. Heat, wind, and surface still explain real splits.

**Where plans use it**

- **5K / 10K base_speed** cycles (neuromuscular reps on fresh legs).  
- **5K race_specific** secondary quality: **goal-pace reps** alongside intervals in the generator’s secondary slot.  
- **Cutback** weeks for **5K**: repetitions instead of heavier quality (generator path).

---

## `reps_200m_neuromuscular_early`

- **stem:** `repetitions`
- **display_name:** Reps — 200m (early pattern)
- **sme_status:** `approved`
- **volume_family:** `R` — repetition family per **`WORKOUT_FLUENCY_REGISTRY_SPEC.md`** §7 schema enum (`E`, `M`, `T`, `I`, `R`, `long`, `composite`).
- **definition:** **Early-build** repetition set: **200m** reps, **full** recovery, **repetition** pace — teaches **quick, controlled** mechanics without long anaerobic reps.
- **execution:** Warm-up easy **~2 mi**. Main: **8–10×200m** (volume-capped per engine) with **~200m jog** or **~1 min** easy between — **smooth**, not all-out sprint. Cool-down **~1 mi**. Matches `_scale_repetitions` when `plan_week` early / not yet in late progression.
- **primary_adaptations:** Neuromuscular coordination; **economy** at faster-than-easy speeds; low **total** hard time vs VO2 day.
- **systems_stressed:** CNS and legs in **short** spikes; Achilles/calf-sensitive athletes may need fewer reps or softer surface.
- **benefits:** **Low recovery debt** compared to long interval sessions; good **bridge** for athletes new to structured speed.
- **risks:** **Kicking** into max sprint; **skipping** warm-up; stacking with **heavy** intervals same week without ledger check.
- **when_to_avoid:** Acute hamstring/calf pain; illness; **injury_return** unless SME shortens sharply.
- **n1_selection_notes:** Default early **5K/10K base_speed** emphasis; pair with **`intervals_pilot`** and **`threshold_pilot`** so the week is not **all** short speed.
- **typical_build_context_tags:** `base_building`, `full_featured_healthy`, `race_specific` (light secondary), `minimal_sharpen` (reduced reps)
- **typical_placement:** Mid-week; spacing vs **intervals** and **threshold** per tolerance.
- **pairs_poorly_with:** **Second** heavy speed day for fragile athletes; long **MP** block same day.
- **source_notes:** Tier A — engine `_scale_repetitions` early branch; Tier B — short rep development patterns.

---

## `reps_300m_economy_late`

- **stem:** `repetitions`
- **display_name:** Reps — 300m (build / sharpen)
- **sme_status:** `approved`
- **volume_family:** `R` — same enum as **`reps_200m_neuromuscular_early`** (registry spec §7).
- **definition:** **Later** repetition progression: **300m** reps at **repetition** pace with **full** recovery — slightly **longer** neuromuscular demand than 200m, still **not** VO2 intervals.
- **execution:** Warm-up **~2 mi**. Main: **6–8×300m** with **~200m jog** or **~1.5 min** easy between. Cool-down **~1 mi**. Matches `_scale_repetitions` late / **race_specific** branch in code.
- **primary_adaptations:** **Power endurance** in short windows; **rhythm** at faster speeds; bridges toward **race sharpness** for **5K** without replacing **interval** day.
- **systems_stressed:** Higher per-rep load than 200m; same cautions for calves/Achilles.
- **benefits:** **Clear** progression from **`reps_200m_neuromuscular_early`** when athlete tolerates volume.
- **risks:** **Rep-one** too fast; cumulative fatigue if **threshold + intervals** already dense.
- **when_to_avoid:** Same as 200m variant; **minimal_sharpen** usually shortens or defers to strides.
- **n1_selection_notes:** **5K** secondary quality weeks; late **base** / **race_specific** when generator selects **`repetitions`**.
- **typical_build_context_tags:** `base_building`, `race_specific`, `peak_fitness`, `full_featured_healthy`, `minimal_sharpen` (reduced)
- **typical_placement:** Mid-week.
- **pairs_poorly_with:** **Duplicate** long-rep speed stress without intent.
- **source_notes:** Tier A — engine `_scale_repetitions` late branch.

---

## Rollup (authoritative `sme_status`)

| `id` | `stem` | `volume_family` | `sme_status` |
|------|--------|-----------------|--------------|
| `reps_200m_neuromuscular_early` | `repetitions` | `R` | `approved` |
| `reps_300m_economy_late` | `repetitions` | `R` | `approved` |

**Counts:** **2** approved / **0** draft.

---

*Pilot 5 — closes KB gap for **`repetitions`** stem emitted by `plan_framework`; Phase 2 registry mapping still TBD.*
