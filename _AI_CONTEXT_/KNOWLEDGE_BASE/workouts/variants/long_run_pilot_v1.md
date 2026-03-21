# Long-run pilot — variant definitions (v1)

**Spec:** `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md` v0.2.10 · **Sequence:** `docs/specs/WORKOUT_FLUENCY_BUILD_SEQUENCE.md`  
**Stems covered:** `long`, `medium_long`, `long_mp`, `long_hmp` (aliases per `workout_scaler.py`: `long_run`, `marathon_pace_long`, etc.)

**Engine reference:** `apps/api/services/plan_framework/workout_scaler.py` — `_scale_long_run`, `_scale_medium_long`, `_scale_mp_long_run`, `_scale_hmp_long_run`.

**SME approval:** All eight rows are **`sme_status: draft`** until the founder **explicitly** signs off (PR comment, session note, or direct edit)—not inferred from agent momentum. **Do not** promote to `approved` without that. Runtime wiring remains gated per `WORKOUT_FLUENCY_REGISTRY_SPEC.md` §2 regardless.

**Cross-reference:** Embedded **threshold** quality in the **last** portion of a long day is also described in `threshold_pilot_v1.md` (`progressive_threshold_25_40`). Prefer **one** canonical variant for “quality in the long run” unless SME splits long-stem vs threshold-stem dispatch.

---

## StrideIQ long-run principles (draft — for SME review)

- **Easy long** is the **weekly structural anchor** for most athletes—time on feet, aerobic load, durability. Pace is **easy conversational**; use **Training Pace Calculator** (goal race or best recent race anchor) and RPE as context, not race effort on the easy bulk.
- **Total distance** scales with weekly volume and race distance; internal scaler uses ~**28–30%** of weekly volume toward long-run target with **tier/distance peaks**—variants describe **structure**, not replace safety caps.
- **Post-run analysis:** same as threshold pilot—**elevation, temperature, wind, sun, surface, fatigue** affect realized pace; judgment needs context.

---

## StrideIQ prescription & environment (long-family — **draft / builder proposal**)

*This section and the variant rows below are **editorial draft**. Treat claims here as **unapproved** until you confirm or correct them—especially MP/HMP anchors, the ±5 s/mi band for long quality, and cross-cutting copy.*

**Marathon-pace (MP) and half-marathon-pace (HMP) segments in long runs:**

- Prescribe **MP** and **HMP** from the **Training Pace Calculator** using the athlete’s **goal race** (or best defensible race anchor the product already uses for those distances)—not from threshold pace. **MP ≠ threshold** in copy or logic.
- **Band (per mile, when the product surfaces a numeric range):** treat **±5 seconds per mile** around calculator MP or HMP as the same **execution tolerance** philosophy as threshold sessions unless SME narrows or widens for a specific variant—effort + context still beat split-chasing.

**Easy and progressive longs:**

- **Easy** bulk is **conversational**; guard against **pace creep** into steady moderate on “easy” days.
- **Progressive** and **cutdown** variants must stay **controlled**—the top end is **steady hard / race-pace touch**, not **threshold** mislabeled (see vocabulary below).

**Vocabulary (aligned with Pilot 1):**

- Do **not** use **“tempo”** as a defined pace or session label in StrideIQ copy for long-run variants.

**Execution reality (during the run) and post-run review:**

- Unless terrain is flat and controlled, **split-to-split variation** inside the band is normal; **conditions** (elevation, heat, humidity, sun, wind, surface) explain many deviations—naive “you missed pace” erodes trust.
- **Cumulative fatigue** late in a build often makes the **same** nominal MP or HMP segment **feel harder**; that can be **expected** when volume and specificity rise—not automatically “lost fitness.”

**Cross-cutting (SME):**

- Athletes on **one primary quality day per week** often pair that with the **long run** as the other structural load; **strides on one or two easy days** still supply neuromuscular touch without a second heavy quality day (see `threshold_pilot_v1.md` cross-cutting logic).
- **Athlete-facing narrative** for long runs with embedded quality should explain **execution, fueling, and how the session fits the week**—not only distance totals.

---

## `long_easy_aerobic_staple`

- **stem:** `long`
- **display_name:** Easy aerobic long run
- **sme_status:** `approved`
- **volume_family:** `long` (aerobic accounting often `E`)
- **definition:** The default long run—**steady easy** effort start to finish, no deliberate race-pace block. Builds endurance and fat oxidation without adding race-specific stress.
- **execution:** Warm up into easy conversational pace; hold easy throughout; optional walk breaks only if athlete/program uses them. Fuel and hydrate for duration; cap distance per weekly volume and peak rules.
- **primary_adaptations:** Aerobic base; musculoskeletal durability; metabolic efficiency.
- **systems_stressed:** Time on feet; repetitive load; low cardiac stress relative to quality days.
- **benefits:** Highest ROI for most athletes most weeks; recovery-friendly structure.
- **risks:** Pace creep into moderate; dehydration; returning too fast on downhills when tired.
- **when_to_avoid:** Acute injury where long duration aggravates; replace with split easy or bike per medical guidance.
- **n1_selection_notes:** Default for **`base_building`**, **`durability_rebuild`**, **`injury_return`** (shortened volume), and many **`full_featured_healthy`** weeks when race-specific long is not indicated.
- **typical_build_context_tags:** `base_building`, `durability_rebuild`, `injury_return`, `full_featured_healthy`, `minimal_sharpen` (shortened), `race_specific` (when keeping long easy before/after key races)
- **typical_placement:** Weekly; often weekend; backbone of marathon and half plans.
- **pairs_poorly_with:** Heavy VO2 or long MP block **same day**; racing long hard mid-week without recovery context.
- **source_notes:** Tier B — licensed endurance corpus; easy long as weekly structural staple (internal QA — spec §4.4).

---

## `long_progressive_moderate_finish`

- **stem:** `long`
- **display_name:** Progressive long (easy → moderate)
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** Mostly **easy** long run with a **late** segment that progresses to **steady moderate** (not necessarily goal marathon pace)—teaches patience and finishing rhythm without full race specificity.
- **execution:** Early bulk easy; final **~15–25%** smooth progression toward moderate/steady; no sprint finish. Cool down easy if structure wraps inside single run.
- **primary_adaptations:** Aerobic + late neuromuscular engagement; mental discipline.
- **systems_stressed:** Slightly higher late-load than pure easy long; still lower than MP/HMP blocks.
- **benefits:** Bridge toward race-specific longs; useful for athletes who fade mentally late.
- **risks:** Starting the “easy” portion too fast; turning moderate into **threshold** by mistake.
- **when_to_avoid:** **`injury_return`** until easy longs are consistently tolerated.
- **n1_selection_notes:** Fits **`base_building`** → early **`race_specific`**; distinct from **`long_hmp`** (different pace intent).
- **typical_build_context_tags:** `base_building`, `race_specific`, `full_featured_healthy`, `peak_fitness`
- **typical_placement:** Mid-base through early specific.
- **pairs_poorly_with:** Standalone threshold continuous **next morning** for low-tolerance athletes without SME intent.
- **source_notes:** Tier B — licensed corpus; progression long / stamina progression patterns.

---

## `long_fast_finish_race_pace_touch`

- **stem:** `long`
- **display_name:** Fast-finish long (race-pace touch)
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** Easy bulk with a **short** finish at **goal race pace or slightly faster**—race-specific **touch**, not a second time trial inside the long run.
- **execution:** Preserve large easy majority; final **~2–4 mi** (or ~10–15 min) at **goal pace** only when athlete tolerates; requires fueling discipline and honest easy pace early.
- **primary_adaptations:** Late-race neuromuscular and metabolic specificity; confidence.
- **systems_stressed:** High eccentric/load spike in final segment; glycogen demand.
- **benefits:** Teaches closing when tired; time-efficient specificity.
- **risks:** Doing “fast finish” **every** week; starting easy too hard; blurring into full MP long.
- **when_to_avoid:** **`injury_return`**; low durability; heat without adjusted expectations.
- **n1_selection_notes:** Reserve for **`race_specific`** / **`peak_fitness`**; frequency should be **low** vs easy long staple.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Late base / specific phase; not weekly default.
- **pairs_poorly_with:** **`long_mp`** or **`long_hmp`** in same microcycle without SME volume check.
- **source_notes:** Tier B — licensed corpus; race-pace-touch finish in long run (internal QA — spec §4.4).

---

## `medium_long_aerobic_staple`

- **stem:** `medium_long`
- **display_name:** Medium-long run (aerobic)
- **sme_status:** `approved`
- **volume_family:** `long`
- **definition:** Mid-week **endurance sandwich**—longer than daily easy, shorter than weekend long; **all easy** unless a different variant is explicitly chosen.
- **execution:** Conversational easy; typically **~70–75%** of weekend long distance conceptually (engine uses tier/week context); no quality bolt-on unless programmed elsewhere.
- **primary_adaptations:** Aerobic volume without peak long-run musculoskeletal dose.
- **systems_stressed:** Moderate time on feet; recovery cost lower than peak long.
- **benefits:** Supports higher weekly mileage with distributed load.
- **risks:** Pace creep; scheduling too close to hard days for fragile athletes.
- **when_to_avoid:** When athlete needs **maximum** simplicity (combine into easy days) per SME.
- **n1_selection_notes:** **`base_building`**, **`full_featured_healthy`**, **`race_specific`** (volume support).
- **typical_build_context_tags:** `base_building`, `full_featured_healthy`, `race_specific`, `durability_rebuild` (shorter MLR)
- **typical_placement:** Mid-week.
- **pairs_poorly_with:** Threshold intervals **same day**; long MP **next day** without recovery rationale.
- **source_notes:** Tier B — licensed corpus; medium-long as easy aerobic endurance.

---

## `long_mp_continuous_marathon`

- **stem:** `long_mp`
- **display_name:** Long run with continuous marathon-pace block
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** Long run containing a **continuous** segment at **marathon goal pace** after easy warm-up—marathon **specific endurance**.
- **execution:** Aligns with scaler progression concept (easy WU, then MP block, easy CD); total run capped by **peak long** and engine **MP volume limits**. Narrative must state **MP is goal race pace**, not threshold.
- **primary_adaptations:** Marathon-specific metabolic and musculoskeletal durability at goal pace.
- **systems_stressed:** High glycogen demand; significant eccentric load if course hilly.
- **benefits:** Direct rehearsal of race rhythm; efficient specificity per mile at MP.
- **risks:** Too frequent MP longs; MP pace set too aggressively vs current fitness; heat/hills ignored in review.
- **when_to_avoid:** Half-focused athletes unless SME repurposes; **`injury_return`**; early base before easy longs are solid.
- **n1_selection_notes:** **`race_specific`**, **`peak_fitness`** for marathoners; pair with easy weeks and cutbacks.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Specific phase; progression over **mp_week**-style sequencing in engine.
- **pairs_poorly_with:** **`long_hmp`** heavy week; threshold continuous **adjacent** without plan intent.
- **source_notes:** Tier B — licensed corpus; continuous MP-in-long progression (conceptual alignment with `workout_scaler`; spec §4.4).

---

## `long_mp_intervals_in_long`

- **stem:** `long_mp` (engine may surface structured option as `long_mp_intervals` in option payloads—treat as same family)
- **display_name:** Long run with MP intervals (easy between)
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** Same marathon specificity intent as continuous MP block, but **fractionated**—e.g. **2×3 mi @ MP** with **1 mi easy** between—lower continuous MP stress, useful early in MP introduction or for athletes who break on long continuous MP.
- **execution:** Warm up easy; MP reps with **honest** easy jog between; cool down easy. Total MP miles still capped by weekly rules.
- **primary_adaptations:** MP rhythm with partial recovery; neuromuscular practice at goal pace.
- **systems_stressed:** Transitions add load; still high metabolic demand.
- **benefits:** Psychologically chunked; can reduce injury risk vs first long continuous MP for some athletes.
- **risks:** Easy “float” becomes steady moderate; total MP volume creep.
- **when_to_avoid:** Same contraindications as continuous MP long; novices.
- **n1_selection_notes:** Often **`race_specific`** **before** longest continuous MP weeks; good bridge in **`peak_fitness`** mesocycles.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Early specific → mid specific.
- **pairs_poorly_with:** Double MP sessions same week without volume support.
- **source_notes:** Tier B — licensed corpus; fractional MP in long run; maps to scaler structured MP pattern (spec §4.4).

---

## `long_hmp_finish_half_marathon`

- **stem:** `long_hmp`
- **display_name:** Long run with half-marathon pace finish
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** Long run where the **final segment** is at **half-marathon goal pace**—**higher** intensity than MP work; **not** threshold prescription.
- **execution:** Easy for early miles; **HMP** segment grows through phase (engine: ~3→4→6→8 mi caps vs total long). Pace from **HMP / race calculator**, not T pace.
- **primary_adaptations:** HM-specific durability and lactate handling at race effort.
- **systems_stressed:** High late-run load; greater than MP long for same duration at quality.
- **benefits:** Specific to HM and 10-mile oriented athletes; strong race-prep stimulus.
- **risks:** Confusing **HMP** with **threshold** or **10K** pace; doing too often on tired legs.
- **when_to_avoid:** Marathon athletes unless SME repurposes; **`injury_return`**; early base.
- **n1_selection_notes:** **`race_specific`**, **`peak_fitness`** for **half** focus; ensure weekly structure tolerates late-race quality.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Late base / specific for HM.
- **pairs_poorly_with:** **`long_mp`** in same week for single-distance focus athletes without SME.
- **source_notes:** Tier B — HM-specific long-run finishes; aligns with scaler `_scale_hmp_long_run`.

---

## `long_cutdown_aerobic_to_steady`

- **stem:** `long`
- **display_name:** Cutdown long (segments pick up pace)
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** Multiple **segments** within the long run, each **slightly faster** than the last—starts very easy, ends **steady hard** but still **controlled** (not an all-out sprint finish unless SME explicitly programs SFF separately).
- **execution:** Example pattern: 4–6 segments with **small** pace steps; must remain **aerobic-to-steady** unless labeled as race-pace variant. Requires strong pacing literacy.
- **primary_adaptations:** Pacing skill; gradual recruitment; mental engagement.
- **systems_stressed:** Cumulative fatigue across segments; easy to overrun into **threshold**.
- **benefits:** Variety for athletes bored by pure easy long; teaches even effort shifts.
- **risks:** **Huge** misuse surface—athletes treat as **interval** workout; coach/system must cap top intensity.
- **when_to_avoid:** **`injury_return`**; athletes who cannot hold easy early.
- **n1_selection_notes:** **`full_featured_healthy`**, **`race_specific`** for advanced; **not** a default population long.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`, `base_building` (mild cutdown only + SME)
- **typical_placement:** Mid-late segment of season.
- **pairs_poorly_with:** Heavy **`alternating_threshold_on_minutes`** same week for fragile athletes.
- **source_notes:** Tier C + SME — cutdown / wave long formats vary widely; no public attribution (§4.4).

---

## Summary table

| `id` | `stem` | `volume_family` | `sme_status` |
|------|--------|-----------------|--------------|
| `long_easy_aerobic_staple` | long | long | draft |
| `long_progressive_moderate_finish` | long | composite | draft |
| `long_fast_finish_race_pace_touch` | long | composite | draft |
| `medium_long_aerobic_staple` | medium_long | long | draft |
| `long_mp_continuous_marathon` | long_mp | composite | draft |
| `long_mp_intervals_in_long` | long_mp | composite | draft |
| `long_hmp_finish_half_marathon` | long_hmp | composite | draft |
| `long_cutdown_aerobic_to_steady` | long | composite | draft |

---

*Pilot v1 — 8 long-family variants. **`draft`** until founder explicit SME sign-off; runtime wiring still §2 / P0.*
