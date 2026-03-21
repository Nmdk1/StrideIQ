# Threshold pilot — variant definitions (v1)

**Spec:** `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md` v0.2.16  
**Stems covered:** `threshold` (continuous or broken continuous T-pace work), `threshold_intervals` (repetitions at ~threshold with recoveries)

**Engine reference:** `apps/api/services/plan_framework/workout_scaler.py` — canonical emission **`threshold`** / **`threshold_intervals`**. A legacy **`tempo`** string may still be accepted internally for backward compatibility; it is **not** StrideIQ vocabulary (see below).

**SME approval:** **Founder approved** all nine Pilot 1 threshold variants **2026-03-22** (session). Each row below is **`sme_status: approved`** for KB / product-copy purposes; runtime wiring remains gated per `WORKOUT_FLUENCY_REGISTRY_SPEC.md` §2. **Founder SME direction (2026-03-21; pace band + environment/fatigue 2026-03-22)** is incorporated in prose below.

---

## StrideIQ pace & environment (SME — product intent)

**Prescription (plan / training pace calculator):**

- Derive **threshold pace** from the **Training Pace Calculator**, using the best available **recent race** anchor within the **last 6 months**:
  1. **5K PR** when available within the window.  
  2. If no qualifying 5K: **1 mile or 10K** within the window — when more than one distance qualifies, prefer the **shorter** race performance as the calculator input for threshold (SME: shorter race is the better anchor for this derivation).
- **Prescribed pace band (per mile):** apply **±5 seconds per mile** around the calculator threshold pace. **Example (founder SME):** calculator threshold **6:30/mi** → prescribed session pace range **6:25–6:35/mi** (not a single number the athlete must nail every split).

**Execution reality (during the run):**

- Unless the athlete is on a **track** or **very flat, controlled** terrain, **split-to-split variation inside the band is normal**—and sometimes **outside** the band on short segments is acceptable when **conditions** explain it (see below). Narrative and post-run analysis should teach **effort + context**, not blind pace-chasing.

**Factors that change sustainable pace (prescription vs realization):**

- **Elevation:** incline vs decline (and cumulative gain/loss over the session).
- **Weather:** heat, cold, **humidity**, **direct sun vs shade**.
- **Wind:** **headwinds** and **tailwinds** (and gusts).
- **Surface:** road vs trail vs treadmill; footing quality.
- **Fatigue state:** **cumulative fatigue late in a build** often makes the same nominal threshold pace **harder to hold** for the full duration—that is **expected**; **progressive** formats and **periodized** continuous builds exist partly to build **durability** for that phase (see `threshold_continuous_progressive`, `progressive_threshold_25_40`).

**Post-action analysis (after the run is done):**

- When comparing **actual** pace to the prescribed band, the engine and copy must account for **elevation, temperature, wind, sun exposure, and surface** (as data allows)—not only temperature. Naive “you missed pace” without context misleads athletes and erodes trust.

---

## Vocabulary (SME — non-negotiable for product language)

- There is **no** “tempo” as a **defined pace** in StrideIQ copy, registry display names, or athlete-facing narrative. Colloquial “tempo” maps to nothing precise.
- Coaching literature uses overlapping labels (**threshold pace**, **critical velocity**, **steady-state** / lactate-threshold-adjacent work). They are **related but distinct** constructs—do not treat them as interchangeable in product logic or copy; StrideIQ uses **threshold** / **threshold_intervals** as canonical stems.
- Use **threshold** / **threshold intervals** / **continuous threshold** / **cruise intervals** (defined variants)—never “tempo” as a system term.

---

## Cross-cutting logic for all threshold variants (SME)

- **Late-build durability:** Many athletes find **holding** threshold effort (and the prescribed **pace band**) harder as **cumulative fatigue** rises—this is a normal training phenomenon, not automatically “lost fitness.” **Progressions** (continuous and progressive-threshold variants) are partly there to **build** tolerance for that demand.
- **Injury-prone athletes**, those **not yet accustomed to more than one quality session per week**, or those who **do not tolerate much intensity** may use **one** primary threshold stimulus per week (with the **long run** as the other structural load) as the staple pattern. For them, prescribe **strides on at least one easy day, ideally two**, so they still gain **neuromuscular** benefit of short reps without depending on a second heavy VO2 day.
- **Athlete-facing narrative** (how to execute, why it’s there, how it fits the week) is **required** wherever the product surfaces these sessions—not only distances and splits.
- The **advanced / fractured** variants (repeats, floats, broken blocks, on/off minutes) follow the **population scope** in the next paragraph unless a variant is explicitly the staple continuous session.

### Advanced / fractured formats — who they are for (SME)

These patterns are **excellent** for **very advanced** athletes—often **doubling**—because they allow **more accumulated time at threshold-like effort** with **less** recovery debt than a single long continuous threshold block. **Double threshold days** (and similar) belong to athletes on **very high mileage** (e.g. **85+ mpw**), with **strong injury resistance**, who have **already progressed through many other stimulus combinations** and **plateaued**—a profile that overlaps heavily with **professional** programs. **Very few** StrideIQ users should see these as defaults; the **staple** for most is **continuous threshold**, periodized as in variant `threshold_continuous_progressive`.

---

## `threshold_continuous_progressive`

- **stem:** `threshold`
- **display_name:** Continuous threshold (periodized staple)
- **sme_status:** `approved`
- **volume_family:** `T`
- **definition:** The **staple** continuous **threshold** session—one steady block at **calculator-derived threshold pace** (see **StrideIQ pace & environment**), progressed week to week within caps. **Not** marathon pace; **not** 5K race pace.
- **execution:** Standard warm-up (easy 15–25 min or ~2–3 mi). Main set: **one continuous** segment at threshold. **Periodization (typical):** week 1 often **~20–25 min** at threshold; add **~5 minutes** per week until **capped at ~40 min** for most athletes. **Elite / high-mileage half-marathon or marathon training** may extend toward **~45 min** only when volume, durability, and SME judgment support it. Easy cool-down. Terrain: flat to rolling when learning the effort; avoid first hard threshold on steep downhills if Achilles/calf sensitive.
- **primary_adaptations:** Lactate threshold / stamina; economy at a single sustainable “hard” gear.
- **systems_stressed:** Cardiovascular sustained load; musculoskeletal repetitive stress; moderate metabolic strain.
- **benefits:** High quality-per-minute when the athlete tolerates **continuous** load; simple to execute and verify against pace band (**±5 s/mi** around calculator T).
- **risks:** Overreach if weekly threshold density is already high; form breakdown late in the block; glycogen debt if under-fueled; ignoring heat/elevation when judging success post hoc.
- **when_to_avoid:** Acute injury pain; illness; extreme heat without acclimation and adjusted expectations; first quality day back after layoff (shorter continuous block or fewer intervals first).
- **n1_selection_notes:** Strong default for athletes who recover well from **continuous** threshold. For **one-quality-per-week** athletes, this can be **the only** structured quality plus long run—pair with **strides on 1–2 easy days** (see **Cross-cutting logic**). Poor fit if history shows HR blow-up or injury flare after long continuous moderate-hard work—shorten block, slow progression, or use cruise intervals variant instead.
- **typical_build_context_tags:** `full_featured_healthy`, `base_building`, `race_specific`, `peak_fitness`, `injury_return` (short blocks only + SME), `minimal_sharpen` (short blocks), `durability_rebuild` (conservative progression only)
- **typical_placement:** Mid-base through specific; usually **one** primary threshold stimulus per week unless volume and tolerance clearly support more.
- **pairs_poorly_with:** Heavy VO2 session next day; long marathon-pace segment the same day; race week except experienced athletes under explicit guidance.
- **source_notes:** Tier B — licensed endurance-training corpus (threshold / steady-state family); distinguish threshold vs other steady-state labels in internal logic only—**no** third-party names in user-facing surfaces (spec §4.4).

**Deprecated id (do not use in new code/docs):** `tempo_continuous_20_40` → use **`threshold_continuous_progressive`**.

---

## `progressive_threshold_25_40`

- **stem:** `threshold`
- **display_name:** Progressive threshold run
- **sme_status:** `approved`
- **volume_family:** `T`
- **definition:** Easy-to-moderate start with a **late** smooth ramp into threshold (or upper steady zone) in the **final portion** of the main run—teaches patience before quality.
- **execution:** Majority easy aerobic; final **~15–35%** of main duration progresses **smoothly** toward threshold (no abrupt surges to VO2). Cool-down easy. Often a bridge before full continuous threshold. **Also fits the tail end of a long run** to build **late-race durability** when programming intentionally embeds quality in the final segment (SME-approved context only).
- **primary_adaptations:** Aerobic base + late threshold touch; neuromuscular preparation for sustained hard running without starting “hot.”
- **systems_stressed:** Lower peak musculoskeletal spike than intervals; CNS load rises mainly in the final segment.
- **benefits:** Discipline and pacing literacy; useful when athletes start quality days too fast; **long-run finish** application for durability when appropriate.
- **risks:** Athlete pushes the early miles too hard despite “progressive” label—coach/system narrative must emphasize **smooth** ramp, not mid-run time trial.
- **when_to_avoid:** Athletes who cannot self-regulate early pace; **injury_return** where any late hard segment is contraindicated.
- **n1_selection_notes:** Strong for **base_building** and early **race_specific** blocks; for **long-run embedded** quality, ensure fueling, surface, and weekly load align—this is **not** a default add-on for novices.
- **typical_build_context_tags:** `base_building`, `race_specific`, `full_featured_healthy`, `durability_rebuild` (only after shorter progressions + SME)
- **typical_placement:** Base → early specific; optional **final segment of selected long runs** for advanced durability work.
- **pairs_poorly_with:** All-out long run the next morning; adjacent threshold days for low-tolerance athletes.
- **source_notes:** Tier B — licensed corpus; progressive stamina / threshold-finish patterns (conceptual).

---

## `threshold_continuous_short_block`

- **stem:** `threshold`
- **display_name:** Short continuous threshold
- **sme_status:** `approved`
- **volume_family:** `T`
- **definition:** A **brief** continuous threshold segment (~**10–20 min** at threshold, or distance-capped equivalent)—for caps, tolerance limits, or return-to-work.
- **execution:** Full warm-up; short continuous threshold at calculator pace (±5 s/mi band); cool-down. Aligns conceptually with “intro week” scaler floors; N=1 may need **shorter** still.
- **primary_adaptations:** Introduce or maintain threshold stimulus with constrained musculoskeletal dose.
- **systems_stressed:** Moderate; lower than long continuous threshold or long threshold-interval sessions.
- **benefits:** Fits low-volume weeks, **injury_return** windows, **minimal_sharpen**, or a **second** light threshold touch in high-mpw athletes when SME-intended.
- **risks:** Running **too fast** because the block is short—still **threshold**, not mile repeats.
- **when_to_avoid:** Same as continuous threshold when systemic fatigue is extreme; redundant if another dense threshold session exists the same week without SME intent.
- **n1_selection_notes:** Default lean for **injury_return** and **minimal_sharpen** when some threshold maintenance is desired; pair with **strides** on easy days per cross-cutting logic.
- **typical_build_context_tags:** `injury_return`, `minimal_sharpen`, `durability_rebuild`, `full_featured_healthy`
- **typical_placement:** Any phase; often early week or after an easy day.
- **pairs_poorly_with:** Another threshold-dense day immediately after for fragile athletes.
- **source_notes:** Tier A/B — aligns with internal `workout_scaler.py` continuous threshold floors (implementation reference).

---

## `cruise_intervals_classic`

- **stem:** `threshold_intervals`
- **display_name:** Cruise intervals (easy jog recovery)
- **sme_status:** `approved`
- **volume_family:** `T`
- **SME population:** **Common** structured threshold work for many **competitive amateurs** when weekly load and tolerance support it—**not** the same rarity as double-threshold / 85+ mpw patterns (see **Advanced / fractured formats**).
- **definition:** Repeats at **threshold** with **easy jog** recovery (not standing)—classic “cruise” / threshold-repeat rhythm.
- **execution:** Warm-up; reps at threshold pace (e.g. 4–6 × 5–12 min or mile repeats at T); jog recovery roughly **~1:4 to 1:5** time ratio vs rep; cool-down. Cap total time at threshold to weekly **T%** rules. **Never label this as “continuous threshold”** in copy—it is **`threshold_intervals`**.
- **primary_adaptations:** Threshold with lower continuous load per bout; rep-to-rep pace discipline.
- **systems_stressed:** Repeated submax loading; metabolic transitions rep to rep.
- **benefits:** Often better tolerated than one long continuous block for athletes who stiffen or lose focus in long steady runs.
- **risks:** Total threshold time creeps up; recovery too fast → session drifts toward **VO2**.
- **when_to_avoid:** Athlete turns jog into stride; acute calf/Achilles irritation from turnover changes.
- **n1_selection_notes:** Primary lever to keep **cruise intervals** distinct from **continuous threshold** in generation and narrative.
- **typical_build_context_tags:** `full_featured_healthy`, `base_building`, `race_specific`, `peak_fitness`
- **typical_placement:** Mid-week in base and specific phases.
- **pairs_poorly_with:** Heavy eccentric day (long steep downs) prior; VO2 micro-intervals same day.
- **source_notes:** Tier B — licensed corpus; threshold repeat / cruise-style prescriptions.

---

## `threshold_intervals_5_to_6_min`

- **stem:** `threshold_intervals`
- **display_name:** Threshold intervals — short reps (~5–6 min)
- **sme_status:** `approved`
- **volume_family:** `T`
- **SME population:** **Standard progression** format for a **wide** range of competitive runners; see **Advanced / fractured formats** only for the caveat that **double-threshold** and similar are rare.
- **definition:** Short threshold repeats (e.g. 4–6 × ~5 min) with controlled recovery—density without very long continuous threshold.
- **execution:** e.g. 4×5, 5×5-style progressions; recovery ~1.5–3 min easy jog (heat-adjusted). Pace from calculator T with ±5 s/mi band.
- **primary_adaptations:** Threshold; pacing literacy; neuromuscular rhythm.
- **systems_stressed:** Repeated loading; cardiovascular drift if under-cooled or dehydrated.
- **benefits:** Predictible progression (add rep before lengthening rep).
- **risks:** Chasing rep PRs → **VO2**, not threshold; incomplete recovery stacks acidosis in heat.
- **when_to_avoid:** First quality session off layoff—prefer fewer reps or short continuous block.
- **n1_selection_notes:** Strong default for **base_building** and **full_featured_healthy** when the week needs a clear **threshold_intervals** identity.
- **typical_build_context_tags:** `base_building`, `full_featured_healthy`, `race_specific`, `peak_fitness`
- **typical_placement:** Early-to-mid phase progression weeks.
- **pairs_poorly_with:** Long marathon-pace segment later the same day.
- **source_notes:** Tier B — licensed corpus; internal `workout_scaler.py` early-week threshold-interval shapes (reference).

---

## `threshold_intervals_8_to_12_min`

- **stem:** `threshold_intervals`
- **display_name:** Threshold intervals — longer reps
- **sme_status:** `approved`
- **volume_family:** `T`
- **SME population:** **Progression** from shorter reps—fits many serious amateurs **after** 5–6 min reps are stable; double-threshold-week patterns remain rare (see **Advanced / fractured formats**).
- **definition:** Fewer, longer repeats at threshold (e.g. 3×10 min, 4×10 min)—approaches continuous threshold stress in pieces.
- **execution:** Adequate warm-up; recoveries often 2–4 min easy jog; cap total T time. Late progression may bridge toward continuous threshold.
- **primary_adaptations:** Threshold endurance; mental tolerance for sustained segments.
- **systems_stressed:** Higher per-rep dose than 5-min reps.
- **benefits:** Bridges intervals → continuous threshold; “chunks” for psychology.
- **risks:** Recovery too short → accidental continuous threshold + fatigue; pacing errors compound.
- **when_to_avoid:** Low durability unless volume is cut sharply.
- **n1_selection_notes:** **durability_rebuild** only after shorter progressions + SME clearance.
- **typical_build_context_tags:** `full_featured_healthy`, `race_specific`, `peak_fitness`, `base_building`
- **typical_placement:** Mid-late base, specific phase.
- **pairs_poorly_with:** Heavy long-run fatigue + next-day repeat for injury-prone masters.
- **source_notes:** Tier B — aligns with scaler later-week progression (reference).

---

## `broken_threshold_two_blocks`

- **stem:** `threshold`
- **display_name:** Broken continuous threshold (two blocks)
- **sme_status:** `approved`
- **volume_family:** `T`
- **SME population:** **Advanced**—see **Advanced / fractured formats**; often doubles / high mileage. Not default for typical StrideIQ athletes.
- **definition:** Two separated **threshold** blocks in one session with **easy** between—similar **total** time at threshold as one continuous run, with a metabolic/CNS reset between.
- **execution:** e.g. 2 × (10–15 min @ T) with 3–6 min easy between + WU/CD. Blocks are **steady threshold**, not all-out reps.
- **primary_adaptations:** Threshold with reduced monotonic load per bout; return-to-rhythm after easy.
- **systems_stressed:** Moderate-high cumulative threshold load.
- **benefits:** Heat, treadmill, or athletes who break mentally on one long continuous block.
- **risks:** Running each block too hard because it’s “only” 10–15 min; weekly threshold density still counts.
- **when_to_avoid:** **injury_return** unless blocks are short and SME-approved; **minimal_sharpen** (usually one short touch instead).
- **n1_selection_notes:** **peak_fitness** / high-tolerance weeks; **double-threshold-week** patterns only with elite-style volume and history (see global scope).
- **typical_build_context_tags:** `peak_fitness`, `full_featured_healthy`, `race_specific`
- **typical_placement:** Specific phase; occasional base for advanced athletes.
- **pairs_poorly_with:** Another double-threshold pattern in the same week without volume to support it.
- **source_notes:** Tier C conceptual + Tier A structure (common coaching pattern); no public attribution (§4.4).

**Deprecated id:** `broken_tempo_two_blocks` → **`broken_threshold_two_blocks`**.

---

## `threshold_float_recovery_intervals`

- **stem:** `threshold_intervals`
- **display_name:** Threshold intervals — float recovery
- **sme_status:** `approved`
- **volume_family:** `T`
- **SME population:** **Advanced**—see **Advanced / fractured formats**; requires pace discipline.
- **definition:** Repeats at threshold with **steady float** recovery (moderate easy, not walk)—higher average stress than classic jog recovery if float is dishonest.
- **execution:** e.g. 4–8 × 3–8 min @ T, 1–2 min **float** (upper easy / marathon-effort band—**defined per athlete**). Total on-time capped like other threshold sessions.
- **primary_adaptations:** Threshold under mild residual fatigue; time-efficient session.
- **systems_stressed:** Less complete recovery between reps; elevated cardiovascular load vs cruise intervals.
- **benefits:** Can feel like **race rhythm** for some half/marathon athletes when executed honestly.
- **risks:** Float creeps to steady moderate-hard → duplicate threshold stress in disguise; not for novices or **injury_return**.
- **when_to_avoid:** Novices; **injury_return**; heat without fueling/hydration plan.
- **n1_selection_notes:** Only with proven pace discipline; else default to **`cruise_intervals_classic`**.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Late base / specific; not a first threshold introduction.
- **pairs_poorly_with:** Already-high average intensity week; strides + hills stacked as second hard CNS day.
- **source_notes:** Tier B — licensed corpus; marathon-specific threshold-repeat variants (conceptual).

---

## `alternating_threshold_on_minutes`

- **stem:** `threshold_intervals`
- **display_name:** On-minutes threshold (alternating)
- **sme_status:** `approved`
- **volume_family:** `T`
- **SME population:** **Advanced**; easily misclassified—see **Advanced / fractured formats**.
- **definition:** Alternating **threshold** and **easy** by time (e.g. 1 min on / 1 min off × N)—**not** VO2 if “on” stays true threshold and total on-time is capped.
- **execution:** “On” = threshold pace (calculator ±5 s/mi); “off” = **true** easy; cap total on-time like other threshold sessions (often ~20–40 min on-time equivalent).
- **primary_adaptations:** Threshold with cadence chunking; psychological structure.
- **systems_stressed:** Frequent transitions; calf/Achilles if “on” overshoots to rep pace.
- **benefits:** Track/treadmill logistics; athletes who struggle with long continuous mental monotony.
- **risks:** **Very high** misuse risk—“on” becomes rep PR → **VO2** / anaerobic; must **never** be labeled generic “speed work” in product.
- **when_to_avoid:** **injury_return**, **durability_rebuild** (surge-like loading); anyone who cannot separate threshold from VO2.
- **n1_selection_notes:** Generator and narrative must **preserve threshold intent and caps** explicitly.
- **typical_build_context_tags:** `full_featured_healthy`, `race_specific`, `peak_fitness`
- **typical_placement:** Specific phase; occasional late base for advanced athletes.
- **pairs_poorly_with:** Other high-transition hard sessions same microcycle for fragile athletes.
- **source_notes:** Tier C — format widely used in coaching; quality varies; SME-approved for product claims; no name attribution (§4.4).

---

## Summary table

| `id` | `stem` | `volume_family` | `sme_status` |
|------|--------|-----------------|--------------|
| `threshold_continuous_progressive` | threshold | T | approved |
| `progressive_threshold_25_40` | threshold | T | approved |
| `threshold_continuous_short_block` | threshold | T | approved |
| `cruise_intervals_classic` | threshold_intervals | T | approved |
| `threshold_intervals_5_to_6_min` | threshold_intervals | T | approved |
| `threshold_intervals_8_to_12_min` | threshold_intervals | T | approved |
| `broken_threshold_two_blocks` | threshold | T | approved |
| `threshold_float_recovery_intervals` | threshold_intervals | T | approved |
| `alternating_threshold_on_minutes` | threshold_intervals | T | approved |

---

*Pilot v1 — 9 threshold variants, **founder SME approved 2026-03-22**. Deprecated IDs: `tempo_continuous_20_40`, `broken_tempo_two_blocks`.*
