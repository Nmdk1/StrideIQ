# Easy / recovery / rest / neuromuscular-touch pilot — variant definitions (v1)

**Spec:** `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md` v0.2.20
**Stems in this file:** `easy`, `recovery`, `easy_strides`, `rest`, **`hills`** (alias **`hill_sprints`**), **`strides`**

**Why `hills` / `strides` live here:** Same **session architecture** as easy days—**easy (or compatible aerobic) first**, neuromuscular touch **only at the end**. Founder intent: these touches primarily support **running economy** and **safe neuromuscular adaptation** (including options that would be **higher injury risk on flat ground** at similar intent). Engine categories may show `SPEED` for some stems; product narrative still treats them as **not** a VO2 day and **not** a threshold substitute.

**Engine reference:** `apps/api/services/plan_framework/workout_scaler.py` — **`easy`**, **`easy_run`**, **`recovery`** → `_scale_easy`; **`easy_strides`** → `_scale_easy_with_strides`; **`rest`** → `_scale_rest`; **`hills`** / **`hill_sprints`** → `_scale_hills`; **`strides`** → `_scale_strides`. Treat **`easy_run`** as an alias of **`easy`** for mapping tables; do not invent a separate variant id for the alias.

**SME approval:** **Founder approved** the **four** core easy/rest variants **2026-03-20** (batch “approve”). **Two** neuromuscular-touch variants (**`easy_run_hill_sprints_neuromuscular`**, **`strides_after_easy_neuromuscular`**) are **`draft`** until explicit founder sign-off per `id`. Rollup table is authoritative for each row’s status. Runtime wiring remains gated per spec §2.

---

## Deterministic selection logic (founder SME — algo contract)

This block is **input to the selection matrix + plan builder**, not athlete-facing copy. It states **why** these tools exist so implementers encode **logic**, not slogans.

**Training principle (whole product):** A week should **touch the systems that need stimulus** with **enough quality and progression** to invite adaptation, then provide **enough easy / rest / consolidation** for those adaptations to land. Neuromuscular touches are **low recovery-debt** tools to fill **gaps** in that picture—not to **duplicate** what heavy sessions already did.

**Placement:** Strides and hill sprints are **always appended after** the easy (or easy-dominant) portion of the session—never the structural “main event” of a quality day.

**Dose shape:** Stride-like reps stay **short—15–30 seconds max**—enough to **touch** a speed/rhythm system without building **recovery debt**. Hill sprints stay **very short / alactic** with **full** walk-back or easy return; they are **not** VO2 hill repeats.

**Stride “gear” (pace / rhythm target—not a second workout):** The same mechanical session can vary **which system is lightly touched**, e.g. **~half marathon**, **~10K**, **~5K**, **~1500** rhythm strides, with **progression across mesocycles** when appropriate. This is a **selector parameter** (future registry field or sub-dispatch), not a different athlete-facing “workout type” unless product chooses to label it.

**Weekly complementarity (non-negotiable for good automation):** The selector must read a **resolved weekly stimulus ledger** (what quality sessions already hit this week / phase—threshold, VO2, reps, floats, MP, etc.). **Do not** prescribe stride **gear** that **redundantly** retrains a system already **heavily** loaded that week. **Do** prescribe stride gear that **fills an intentional gap** (founder example: heavy **5K-style** rep session with floats → **no** additional **5K gear** strides on easies that week; **little or no threshold** in the week → **10K** or **half-marathon gear** strides on an easy may be appropriate to **touch that system lightly**).

**Hill sprints vs strides:** Same **economy / neuromuscular / resilience** job family; hills add **gravity-constrained** loading often **safer** than trying to extract similar neuromuscular stress **on the flat** at riskier mechanics. For **injury-prone** profiles, **well-dosed** hills or strides are often a **resilience** path—not an excuse to add volume of “invisible intensity.”

**Frequency:** **N-of-1.** Do **not** hard-code caps from **age bracket** or pop research. Inputs: recovery signals, training tolerance, recent neuromuscular density, injury constraints, life load—**founder exemplar:** **twice weekly** strides for a specific high-tolerance masters athlete is valid; another athlete may need **less** or **more**.

**Geography:** The product **cannot manufacture hills**. If hills are selected but **not executable**, the matrix must **substitute** (e.g. strides or flat neuromuscular touch), **suppress** hills, or surface **execution truth**—planner choice, but never pretend terrain exists.

**Coexistence in a week:** Valid outputs include **strides-only** weeks, **hills-only** touches, **one of each**, or **alternating** patterns—chosen by the **ledger + fingerprint**, not a fixed global recipe.

**`easy_strides` vs `strides` stem:** For **automation**, treat as **one logical prescription** (easy block + end strides). Prefer a **single** planner output path; keep **`strides`** stem only for **legacy / mapping** compatibility until dispatch is unified.

---

## StrideIQ easy-day intent (SME — product)

**Ceiling, not a target pace**

- **Easy is easy:** the athlete must **not** exceed **easy** effort / easy pace **ceiling** for the prescribed easy portion. **Slower is always allowed**—especially heat, hills, poor sleep, or returning from disruption.
- **Miles in:** the primary job of most easy days is **aerobic time and distance** at sustainable, repeatable effort—not squeezing pace.
- **Calculator alignment:** when the product exposes an **easy** zone from the **Training Pace Calculator**, prescribed copy should treat it as a **ceiling band** (do not coach athletes to “run as close to the fast end as possible” on standard easy days).

**Relationship to quality**

- Easy days **anchor** the week around threshold, long, and VO2 work. Neuromuscular touches (`easy_strides`, `hills`) **fill system gaps with low recovery debt**—see **Deterministic selection logic** above—rather than piling **redundant** stimulus on top of what hard sessions already trained. **`threshold_pilot_v1.md`** cross-cutting logic remains compatible: touches are **not** a second threshold or VO2 day.

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
- **definition:** **Easy run** with strides **only at the end**—**economy + safe neuromuscular touch** for systems that need a **light** stimulus, **not** a VO2 or threshold session and **not** a duplicate of what the week’s hard work already trained (**Deterministic selection logic**).
- **execution:** **Easy** main volume at or below easy ceiling. **Strides:** **15–30 s max** per rep; accelerations to the **selected stride gear** (~half marathon / ~10K / ~5K / ~1500 **rhythm**—selector-chosen, progressable over mesocycles). **Relaxed mechanics**, **not** all-out sprints; **full** recovery so breathing returns to easy before the next. Engine sketch today: easy miles + **6×** short strides (`workout_scaler._scale_easy_with_strides`)—**illustrative** until wiring carries **gear** + rep count from the matrix.
- **primary_adaptations:** Running economy; neuromuscular coordination; **light** touches to speed/rhythm systems **without** anaerobic recovery debt (founder-approved claims).
- **systems_stressed:** Brief neuromuscular spikes—**low** vs intervals; Achilles/calf history may need fewer reps, flatter surface, or different touch (e.g. hills) per fingerprint.
- **benefits:** Trains **gaps** in the weekly stimulus map; often appropriate when **one** structured quality day/week (or conservative week) still needs **rhythm** and **stiffness** without a second hard day.
- **risks:** Wrong **gear** vs weekly ledger (**redundant** 5K touch after heavy 5K week); too many reps; **kicking** too hard; doing on **trashed** legs without reducing load elsewhere.
- **when_to_avoid:** Acute hamstring/calf flare; **injury_return** where any fast mechanics are barred.
- **n1_selection_notes:** **Frequency is N-of-1** (recovery, tolerance, neuromuscular density, injury, life load)—**not** age tables. **Gear** and **reps** come from **weekly stimulus ledger + fingerprint**, not a global “most people” cap.
- **typical_build_context_tags:** `full_featured_healthy`, `base_building`, `race_specific`, `peak_fitness`, `minimal_sharpen` (reduced reps), `durability_rebuild` (optional, fewer reps + SME)
- **typical_placement:** After easy volume; which **easy day** is chosen from the **plan builder + ledger**, not a fixed weekday recipe.
- **pairs_poorly_with:** **Redundant** stride **gear** when the week already **saturated** that system (see **complementarity** in Deterministic selection logic)—this is the primary **algorithm** failure mode to avoid.
- **source_notes:** Tier A — founder session **2026-03-20** (stride gear, complementarity, N-of-1 frequency); Tier B — general post-easy stride patterns.

---

## `easy_run_hill_sprints_neuromuscular`

- **stem:** `hills` (alias input: `hill_sprints`)
- **display_name:** Easy run with hill sprints
- **sme_status:** `draft`
- **volume_family:** `composite`
- **definition:** **Easy** aerobic base plus **very short** uphill sprints at the **end** of the session—**economy + neuromuscular / resilience** loading that is often **safer** than extracting similar neuromuscular stress **on the flat** at higher injury risk. **Alactic** character, full recovery between reps. **Not** VO2 hill repeats; **not** threshold substitute.
- **execution:** **Easy** volume at or below easy ceiling, then **steep-enough** hills for brief maximal **uphill** pushes (engine sketch: **6–10× ~10 s** with **~90 s** walk/jog back—tier scales reps in `_scale_hills`). **Walk-back** or easy return mandatory. Easy portion stays **true easy** before sprints.
- **primary_adaptations:** Running economy; neuromuscular recruitment; **resilience** stimulus when dosed to tolerance—founder: especially valuable for **injury-prone** runners when progression is sane.
- **systems_stressed:** Brief CNS spikes; calves / Achilles / plantar on steep push-off; **eccentric** load if downhills or footing are careless.
- **benefits:** Touches **power / stiffness** dimensions with **low** anaerobic debt; complements **rolling** race prep when hills are **available**.
- **risks:** Reps **too long** (drifts to VO2 hill work); **too many** reps; bad footing; ignoring **weekly ledger** and stacking with other **power** stimuli.
- **when_to_avoid:** Acute lower-leg / foot pain; **injury_return** until easy running is consistently tolerated; **no suitable hill**—then **substitute** per **Geography** rule (e.g. **`easy_strides`** with appropriate gear), do not ghost-prescribe hills.
- **n1_selection_notes:** **Frequency and rep scheme are N-of-1** from fingerprint + ledger. Week may be **hills-only** touch, **strides-only**, **both**, or **alternating**—matrix output, not a universal “once a week max.”
- **typical_build_context_tags:** `full_featured_healthy`, `base_building`, `race_specific` (rolling race), `peak_fitness`, `minimal_sharpen` (fewer reps), `durability_rebuild` (omit or SME-microdose only)
- **typical_placement:** After easy volume; adjacency vs long or quality days is a **tolerance + ledger** decision, not a static ban list.
- **pairs_poorly_with:** **Uncontrolled** stacking of **multiple** high-density power touches without recovery narrative—detect via **ledger**, not a single hard-coded pair.
- **source_notes:** Tier A — founder session **2026-03-20** (economy, safety vs flat, resilience, geography); Tier B — alactic hill sprint patterns.

---

## `strides_after_easy_neuromuscular`

- **stem:** `strides`
- **display_name:** Strides (after easy running)
- **sme_status:** `draft`
- **volume_family:** `E`
- **definition:** **Same logical prescription** as **`easy_strides_neuromuscular_touch`**: strides **always** come **after** easy (or easy-dominant) running. The **`strides`** stem exists in the engine separately from **`easy_strides`**; **automation target** is **one** planner concept with **unified** selection rules (**Deterministic selection logic**). Keep this row for **ID → engine map** until dispatch is merged.
- **execution:** Same as **`easy_strides_neuromuscular_touch`** (15–30 s cap, **stride gear**, full recovery, **ledger-driven** gear choice). Engine sketch: `_scale_strides` fixed template—**illustrative** until wiring aligns with volume + gear from the matrix.
- **primary_adaptations:** Same as **`easy_strides_neuromuscular_touch`**.
- **systems_stressed:** Same as **`easy_strides_neuromuscular_touch`**.
- **benefits:** Same as **`easy_strides_neuromuscular_touch`**.
- **risks:** **Duplicate** sessions if both **`strides`** and **`easy_strides`** emit in the same week without intent—Phase 2/3 must enforce **at most one** logical end-strides touch per plan slice unless SME-deliberate.
- **when_to_avoid:** Same as **`easy_strides_neuromuscular_touch`**.
- **n1_selection_notes:** Prefer **`easy_strides`** path for **volume-scaled** easy blocks when merging stems; **`strides`** stem is **compatibility** until code paths unify.
- **typical_build_context_tags:** Same as **`easy_strides_neuromuscular_touch`**.
- **typical_placement:** Same as **`easy_strides_neuromuscular_touch`**.
- **pairs_poorly_with:** Same **ledger redundancy** rules as **`easy_strides_neuromuscular_touch`**.
- **source_notes:** Tier A — founder **2026-03-20** (placement, single logical tool); Tier B — engine duplication note for Phase 2 map.

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
