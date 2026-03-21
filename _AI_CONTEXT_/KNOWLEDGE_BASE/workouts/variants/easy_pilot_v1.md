# Easy / recovery / rest pilot — variant definitions (v1)

**Spec:** `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md` v0.2.16  
**Stems covered:** `easy`, `recovery`, `easy_strides`, `rest`

**Engine reference:** `apps/api/services/plan_framework/workout_scaler.py` — `scale_workout` accepts **`easy`**, **`easy_run`**, **`recovery`** (all routed through `_scale_easy`), **`easy_strides`** (`_scale_easy_with_strides`), **`rest`** (`_scale_rest`). Treat **`easy_run`** as an alias of **`easy`** for mapping tables; do not invent a separate variant id for the alias.

**SME approval:** **Founder approved** all **four** Pilot 3 easy-family variants **2026-03-20** (session: batch “approve”). Each row below is **`sme_status: approved`** for KB / product-copy purposes; runtime wiring remains gated per spec §2. Future edits: **do not** infer promotion—explicit founder sign-off per `id`.

---

## StrideIQ easy-day intent (SME — product)

**Ceiling, not a target pace**

- **Easy is easy:** the athlete must **not** exceed **easy** effort / easy pace **ceiling** for the prescribed easy portion. **Slower is always allowed**—especially heat, hills, poor sleep, or returning from disruption.
- **Miles in:** the primary job of most easy days is **aerobic time and distance** at sustainable, repeatable effort—not squeezing pace.
- **Calculator alignment:** when the product exposes an **easy** zone from the **Training Pace Calculator**, prescribed copy should treat it as a **ceiling band** (do not coach athletes to “run as close to the fast end as possible” on standard easy days).

**Relationship to quality**

- Easy days **anchor** the week around threshold, long, and VO2 work. See **`threshold_pilot_v1.md`** cross-cutting logic: many athletes benefit from **strides on one or two easy days** (`easy_strides`) rather than adding another heavy quality session.

**Display names**

- Athlete-facing strings use **normal session names** only (e.g. “Easy run”, “Recovery run”)—never internal ids or engine tokens.

---

## `easy_conversational_staple`

- **stem:** `easy` (alias input: `easy_run` → same intent)
- **display_name:** Easy run
- **sme_status:** `approved`
- **volume_family:** `E`
- **definition:** Default **aerobic** day—conversational effort, **at or below** easy ceiling, distance scaled to weekly structure. Not disguised steady-state “sort of hard”; not race-specific work.
- **execution:** Continuous easy running (or walk breaks only if athlete-led or protocol allows). **Pace:** relaxed; **breathing** should stay comfortable; **finish** feeling like more miles were possible. **Terrain / conditions:** same ceiling rule—ease off before violating easy definition.
- **primary_adaptations:** Aerobic base; recovery between stimuli; habit and tissue tolerance for volume.
- **systems_stressed:** Low musculoskeletal peak load; low CNS demand; primary constraint is often **time** and **consistency**, not intensity.
- **benefits:** High **mileage ROI** with low injury risk when truly easy; supports durability for quality days and long runs.
- **risks:** **Running too fast** (“moderate”) on days labeled easy—accumulates fatigue without labeling it; blurs recovery. **Pace obsession** on hilly or hot routes.
- **when_to_avoid:** Acute injury where running is contraindicated; replace with rest or cross-train per medical guidance—not a variant selection problem.
- **n1_selection_notes:** Default filler for most **full_featured_healthy** and **base_building** weeks. For **injury_return** / **durability_rebuild**, often **shorter** easy pieces or **more** recovery days—still **must not** exceed easy ceiling when running. Cold or **minimal_sharpen** weeks: preserve **easy** character even when total volume drops.
- **typical_build_context_tags:** `full_featured_healthy`, `base_building`, `race_specific`, `peak_fitness`, `durability_rebuild`, `minimal_sharpen`, `injury_return`
- **typical_placement:** Most non-quality, non-long days; between hard sessions.
- **pairs_poorly_with:** None inherently—**errors are pace**, not pairing.
- **source_notes:** Tier B — licensed easy-run / aerobic corpus; StrideIQ voice is effort-ceiling + miles-in, not third-party labels.

---

## `recovery_run_aerobic`

- **stem:** `recovery`
- **display_name:** Recovery run
- **sme_status:** `draft`
- **volume_family:** `E`
- **definition:** **Extra-conservative** easy day—same **ceiling** rule as `easy`, but **intent** is active recovery after load or life stress; **shorter** and **slower** bias is normal even when the scaler maps to similar distances as generic easy in code today.
- **execution:** Same movement pattern as easy; **emphasis** on **relaxation**, **mobility**, and **patience**—often **shorter duration** or **lower** volume than staple easy when N=1 selection applies. **No** quality pickup unless a distinct `easy_strides` variant is explicitly chosen.
- **primary_adaptations:** Facilitate blood flow and light aerobic touch without adding meaningful stress.
- **systems_stressed:** Minimal; psychological “reset” and routine continuity matter.
- **benefits:** Maintains rhythm for athletes who do not tolerate full rest between every hard day; reduces guilt-driven “moderate” junk miles if narrative reinforces **easy ceiling**.
- **risks:** Athlete treats “recovery” as permission to **prove fitness**—same failure mode as easy run too fast.
- **when_to_avoid:** When **complete rest** is clearly better (illness, acute pain, severe fatigue)—prefer **`rest_day_complete`** or off-feet guidance.
- **n1_selection_notes:** After races, hard long runs, or **high acute load** spikes; in **injury_return** when some movement is approved but volume must stay **trivially stressful**. Often alternates with **rest** in conservative templates.
- **typical_build_context_tags:** `durability_rebuild`, `injury_return`, `minimal_sharpen`, `full_featured_healthy`, `base_building`
- **typical_placement:** Day after quality or long run; mid-week after poor sleep (when still running).
- **pairs_poorly_with:** **Back-to-back** recovery runs used to avoid scheduling a real easy or rest—usually a **planning smell** unless athlete-specific.
- **source_notes:** Tier B — recovery jog concepts; distinct **intent** from `easy` for selection matrix even when engine scaler shares implementation.

---

## `easy_strides_neuromuscular_touch`

- **stem:** `easy_strides`
- **display_name:** Easy run with strides
- **sme_status:** `approved`
- **volume_family:** `E`
- **definition:** **Easy run** plus **short, controlled strides** after the aerobic portion—**neuromuscular** and turnover touch, **not** a VO2 or threshold session.
- **execution:** **Easy** main volume at or below easy ceiling. **Strides:** very short (e.g. **~20–30 s**) accelerations to **fast but relaxed** mechanics—**not** all-out sprints; **full** walk/jog recovery so breathing returns to easy before the next. Engine sketch today: easy miles + **6×** short strides with generous rest (`workout_scaler._scale_easy_with_strides`)—treat as **illustrative** until registry wiring; N=1 may reduce reps or omit.
- **primary_adaptations:** Running economy / neuromuscular coordination; light speed exposure without anaerobic debt.
- **systems_stressed:** Brief spikes in neuromuscular load; **low** compared to intervals; Achilles/calf history may need fewer reps or flatter surface.
- **benefits:** Cheap speed maintenance for athletes with **only one** heavy quality day per week; complements threshold family guidance in **`threshold_pilot_v1.md`**.
- **risks:** **Kicking** strides too hard; **too many** reps; doing strides on **trashed legs** without reducing volume elsewhere.
- **when_to_avoid:** Acute hamstring/calf flare; **injury_return** phases where any fast mechanics are barred.
- **n1_selection_notes:** Prefer **1–2** days per week with strides **max** for most non-elite programs—not on **every** easy day. Strong pairing with **one-quality-per-week** athletes.
- **typical_build_context_tags:** `full_featured_healthy`, `base_building`, `race_specific`, `peak_fitness`, `minimal_sharpen` (reduced reps), `durability_rebuild` (optional, fewer reps + SME)
- **typical_placement:** Mid-week easy or day before/after quality depending on tolerance—avoid sandwiching **two** heavy days around strides without intent.
- **pairs_poorly_with:** **VO2** or **repetitions** day immediately after poor recovery—strides are not the culprit; **weekly density** is.
- **source_notes:** Tier B — strides post-easy patterns; engine segment structure must stay sub-threshold in narrative.

---

## `rest_day_complete`

- **stem:** `rest`
- **display_name:** Rest day
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** **No running** prescribed; complete rest or optional **non-impact** cross-training only if athlete and policy allow—**not** a stealth easy run.
- **execution:** **Zero** run miles. Copy should reinforce **adaptation happens on rest** without moralizing. If the product allows optional cross-training, it must **not** rewrite this variant into a run.
- **primary_adaptations:** Recovery and supercompensation between stimuli.
- **systems_stressed:** None from running; life stress still exists—do not promise “full recovery” from rest alone in copy.
- **benefits:** Reduces injury risk from chronic overload; necessary for **most** athletes at least **1–2** days/week without running.
- **risks:** **Athlete anxiety** leading to “junk” unscheduled runs—address with trust-forward framing, not shame.
- **when_to_avoid:** N/A as a **safety** concept—avoidance is about **plan balance**, not contraindication.
- **n1_selection_notes:** **Mandatory** in many weeks for novices and **injury_return**; elite high-volume plans may still use **rest** strategically—density is not a virtue without tolerance data.
- **typical_build_context_tags:** `full_featured_healthy`, `base_building`, `race_specific`, `peak_fitness`, `minimal_sharpen`, `durability_rebuild`, `injury_return`
- **typical_placement:** After hardest sessions; before quality when **freshness** priority; weekly anchor slots.
- **pairs_poorly_with:** **Zero** rest weeks for populations that require rest—selection error.
- **source_notes:** SME-original structural definition; aligns with `WorkoutCategory.REST` emission.

---

## Rollup (authoritative `sme_status`)

| `id` | `stem` | `volume_family` | `sme_status` |
|------|--------|-----------------|--------------|
| `easy_conversational_staple` | `easy` | `E` | `approved` |
| `recovery_run_aerobic` | `recovery` | `E` | `approved` |
| `easy_strides_neuromuscular_touch` | `easy_strides` | `E` | `approved` |
| `rest_day_complete` | `rest` | `composite` | `approved` |

**Counts:** 4 approved / 0 draft.
