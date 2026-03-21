# Easy / recovery / rest / neuromuscular-touch pilot — variant definitions (v1)

**Spec:** `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md` v0.2.17  
**Stems in this file:** `easy`, `recovery`, `easy_strides`, `rest`, **`hills`** (alias **`hill_sprints`**), **`strides`**

**Why `hills` / `strides` live here:** Same coaching bucket as easy days—**mostly easy running** plus a **short, low-CNS-debt** power touch. Engine categories may show `SPEED` for some of these; product narrative still treats them as **not** VO2 day and **not** threshold.

**Engine reference:** `apps/api/services/plan_framework/workout_scaler.py` — **`easy`**, **`easy_run`**, **`recovery`** → `_scale_easy`; **`easy_strides`** → `_scale_easy_with_strides`; **`rest`** → `_scale_rest`; **`hills`** / **`hill_sprints`** → `_scale_hills`; **`strides`** → `_scale_strides`. Treat **`easy_run`** as an alias of **`easy`** for mapping tables; do not invent a separate variant id for the alias.

**SME approval:** **Founder approved** the **four** core easy/rest variants **2026-03-20** (batch “approve”). **Two** neuromuscular-touch variants (**`easy_run_hill_sprints_neuromuscular`**, **`strides_after_easy_neuromuscular`**) are **`draft`** until explicit founder sign-off per `id`. Rollup table is authoritative for each row’s status. Runtime wiring remains gated per spec §2.

---

## StrideIQ easy-day intent (SME — product)

**Ceiling, not a target pace**

- **Easy is easy:** the athlete must **not** exceed **easy** effort / easy pace **ceiling** for the prescribed easy portion. **Slower is always allowed**—especially heat, hills, poor sleep, or returning from disruption.
- **Miles in:** the primary job of most easy days is **aerobic time and distance** at sustainable, repeatable effort—not squeezing pace.
- **Calculator alignment:** when the product exposes an **easy** zone from the **Training Pace Calculator**, prescribed copy should treat it as a **ceiling band** (do not coach athletes to “run as close to the fast end as possible” on standard easy days).

**Relationship to quality**

- Easy days **anchor** the week around threshold, long, and VO2 work. See **`threshold_pilot_v1.md`** cross-cutting logic: many athletes benefit from **strides on one or two easy days** (`easy_strides`) rather than adding another heavy quality session. **Hill sprints after easy** (`hills`) are a parallel tool—**power and hip drive** with **walk-back** recovery—not a second threshold session.

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
- **sme_status:** `approved`
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

## `easy_run_hill_sprints_neuromuscular`

- **stem:** `hills` (alias input: `hill_sprints`)
- **display_name:** Easy run with hill sprints
- **sme_status:** `draft`
- **volume_family:** `composite`
- **definition:** **Easy** aerobic base plus **very short** uphill sprints—**alactic / power**, full recovery between reps. **Not** hill repeats at VO2; **not** a threshold substitute.
- **execution:** **Easy** warm-up volume at or below easy ceiling, then **steep-enough** hills for **~8–12 s** maximal **uphill** pushes (engine sketch: **6–10× ~10 s** with **~90 s** walk/jog back / full recovery—tier scales reps in `_scale_hills`). **Walk-back** or easy loop back is mandatory so each rep starts **fresh**. Easy portion stays **true easy**—do not “preload fatigue” before sprints.
- **primary_adaptations:** Power, hip extension, neuromuscular recruitment; economy on rolling courses; tendon/stiffness stimulus **when** dosage matches tolerance.
- **systems_stressed:** CNS **brief** spikes; calves / Achilles / plantar on steep push-off; **eccentric** load on downhills if route choice is poor.
- **benefits:** High **value-per-minute** for speed–power without a long anaerobic bill—especially for marathon–half athletes who skip track work.
- **risks:** **Too long** reps (becomes VO2 hill work); **too many** reps; poor surface (wet brick, unstable footing); stacking with **heavy** lower-leg week without tapering hill dose.
- **when_to_avoid:** Acute calf / Achilles / foot pain; **injury_return** until running easy is consistently pain-free; no suitable hill (then use **`easy_strides`** on flat or mild grade).
- **n1_selection_notes:** Often **1×/week** max for non–power-specialist distance runners; alternate weeks with **`easy_strides`** if weekly load is sensitive. Strong when athlete races on **hilly** courses or responds well to **stiffness** work.
- **typical_build_context_tags:** `full_featured_healthy`, `base_building`, `race_specific` (rolling race), `peak_fitness`, `minimal_sharpen` (fewer reps), `durability_rebuild` (omit or SME-microdose only)
- **typical_placement:** Mid-week or **not** the day before key long run unless athlete-proven pattern.
- **pairs_poorly_with:** Second **CNS-heavy** day back-to-back for fragile athletes; long **downhill** session same week without recovery narrative.
- **source_notes:** Tier B — short hill sprint / alactic hill patterns; align copy with **FAST uphill, easy everything else**.

---

## `strides_after_easy_neuromuscular`

- **stem:** `strides`
- **display_name:** Strides (after easy running)
- **sme_status:** `draft`
- **volume_family:** `E`
- **definition:** Session anchored on **easy running** with **strides** at the end—same **coaching job** as **`easy_strides_neuromuscular_touch`**, but routed on the engine’s standalone **`strides`** `workout_type` (legacy / alternate dispatch). Selection and narrative should **converge** with `easy_strides` unless a deliberate distinction is kept (e.g. fixed session template vs weekly-volume-scaled easy block).
- **execution:** **Easy** segment at or below easy ceiling, then **6–8× ~20–30 s** relaxed-fast strides with **full** recovery (engine sketch: **~5 mi** easy + strides in `_scale_strides`—treat as **illustrative**; N=1 and volume coherence may prefer **`easy_strides`** scaling instead).
- **primary_adaptations:** Turnover, neuromuscular coordination, light speed exposure—**not** VO2.
- **systems_stressed:** Brief low-volume power spikes; hamstring / calf if athlete **over-kicks**.
- **benefits:** Same family as **`easy_strides`**—cheap speed maintenance when **one** quality day/week pattern is in use.
- **risks:** Duplicate prescription if planner emits **both** `strides` and `easy_strides` in the same week without intent; athlete confuses with **interval** day.
- **when_to_avoid:** Same contraindications as **`easy_strides_neuromuscular_touch`**.
- **n1_selection_notes:** Prefer **one** strides-pattern variant per week for most athletes unless high-volume and proven tolerance. If registry wiring keeps **two** stems, default **volume-scaled** `easy_strides` for plan coherence; reserve `strides` for explicit “strides session” slots if the phase builder still emits them.
- **typical_build_context_tags:** `full_featured_healthy`, `base_building`, `race_specific`, `peak_fitness`, `minimal_sharpen` (fewer reps), `durability_rebuild` (optional, fewer reps + SME)
- **typical_placement:** Same as **`easy_strides_neuromuscular_touch`**.
- **pairs_poorly_with:** Redundant pairing with **`easy_strides`** same week without SME intent; dense **VO2** adjacent without recovery.
- **source_notes:** Tier B — easy + strides session patterns; document **stem coexistence** in Phase 2 **ID → engine map** to prevent silent drift.

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
| `easy_run_hill_sprints_neuromuscular` | `hills` | `composite` | `draft` |
| `strides_after_easy_neuromuscular` | `strides` | `E` | `draft` |
| `rest_day_complete` | `rest` | `composite` | `approved` |

**Counts:** 4 approved / 2 draft.
