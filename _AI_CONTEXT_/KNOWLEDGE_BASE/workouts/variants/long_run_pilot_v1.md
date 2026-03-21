# Long-run pilot — variant definitions (v1)

**Spec:** `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md` v0.2.12 · **Sequence:** `docs/specs/WORKOUT_FLUENCY_BUILD_SEQUENCE.md`  
**Stems covered:** `long`, `medium_long`, `long_mp`, `long_hmp` (aliases per `workout_scaler.py`: `long_run`, `marathon_pace_long`, etc.)

**Engine reference:** `apps/api/services/plan_framework/workout_scaler.py` — `_scale_long_run`, `_scale_medium_long`, `_scale_mp_long_run`, `_scale_hmp_long_run`.

**SME approval:** Each row carries its own **`sme_status`**. **Do not** promote to `approved` without **explicit** founder sign-off for that id (session, PR comment, or direct edit)—not inferred from agent momentum. **Approved so far:** `long_easy_aerobic_staple` — founder SME **2026-03-20** (session). Runtime wiring remains gated per `WORKOUT_FLUENCY_REGISTRY_SPEC.md` §2 regardless.

**Authoritative status (this file + summary table):** Pilot 2 is **not** “all eight approved.” **Truth:** **1** row **`approved`**, **7** **`draft`** (counts below). Git/spec history **v0.2.9** briefly claimed full Pilot 2 approval without explicit Q&A—**reverted in v0.2.10**. If any handoff, PR, or memory says “all 8 long-run variants approved,” treat that as **stale** unless this table shows eight **`approved`**.

**`draft` semantics:** **`draft`** = not yet promoted to **`approved`** for registry / shipping gates. It does **not** mean “empty placeholder”—prose may already reflect founder session direction; promotion is an explicit **second** step.

**Cross-reference:** Embedded **threshold** quality in the **last** portion of a long day is also described in `threshold_pilot_v1.md` (`progressive_threshold_25_40`). Prefer **one** canonical variant for “quality in the long run” unless SME splits long-stem vs threshold-stem dispatch.

---

## StrideIQ long-run principles (draft — for SME review)

- **Easy long** is the **weekly structural anchor** for most athletes—time on feet, aerobic load, durability. Pace is **easy conversational**; use **Training Pace Calculator** (goal race or best recent race anchor) and RPE as context, not race effort on the easy bulk.
- **Most runners should have a long run** in the week; what counts as “long” **scales with the athlete**. For **newer** runners, a pragmatic floor is **more than double** a typical **single** easy day (when daily volume is small). For **high-mileage** athletes, “double daily” stops being meaningful—long is **no longer linear** off daily miles; use **time on feet**, recent longest session, and plan caps instead.
- **Stops are normal:** brief stops for **fluid, fuel, bathroom, or regrouping** (including short walking) do not invalidate an easy long—the session is defined by **easy effort and duration**, not uninterrupted clock continuity.
- **Total distance** scales with weekly volume and race distance; internal scaler uses ~**28–30%** of weekly volume toward long-run target with **tier/distance peaks**—variants describe **structure**, not replace safety caps.
- **Post-run analysis:** same as threshold pilot—**elevation, temperature, wind, sun, surface, fatigue** affect realized pace; judgment needs context.
- **Injury return and tolerance** are **N=1**; do not treat any exemplar below as a universal rule.

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
- **display_name:** Easy long run
- **sme_status:** `approved`
- **volume_family:** `long` (aerobic accounting often `E` in volume summaries—keep **`long`** as stem family here)
- **definition:** The default **weekly** long run—**steady easy** effort for the moving portions, **no deliberate race-pace block**. Builds endurance and fat oxidation without adding race-specific stress. **Stops** for fluid, fuel, bathroom, or brief regrouping (including short walking) are **normal** and compatible with this variant.
- **execution:** Ease into conversational pace; hold easy for the run as a whole. **Stop as needed** for hydration and fuel on longer outings—especially heat or high sweat loss—without treating the session as “broken.” Cap distance/time per weekly volume, peak rules, and **recent longest-run progression** (avoid abrupt single-session spikes vs what the athlete has tolerated in the prior few weeks). Narrative: prioritize **effort + context**, not uninterrupted clock purity.
- **primary_adaptations:** Aerobic base; musculoskeletal durability; metabolic efficiency.
- **systems_stressed:** Time on feet; repetitive load; low cardiac stress relative to quality days.
- **benefits:** Highest ROI for most athletes most weeks; recovery-friendly structure; supports durable volume when progression is sane.
- **risks:** Pace creep into moderate; dehydration; returning too fast on downhills when tired; **one-off** long that jumps far beyond recent longest sessions (injury risk) even if weekly totals look tame.
- **when_to_avoid:** Acute injury or medical guidance where long duration or impact is contraindicated—use split easy, cross-train, or shorter bouts per **clinical direction**. **`injury_return`:** length and tolerance are **highly individual**; shorten or defer until load is re-established—no universal week template.
- **n1_selection_notes:** **Default long** for most weeks in **`base_building`**, **`durability_rebuild`**, **`full_featured_healthy`**, and often **`race_specific`** when the long stays **easy** (quality lives elsewhere). **`minimal_sharpen`:** usually shortened. **`injury_return`:** only when cleared for progressing duration—scale to N=1. **“Long” definition:** for newer/low-daily-volume athletes, often **> ~2×** a typical easy day; for high-daily-mileage athletes, use **time on feet** and plan caps instead of doubling daily miles. **Time heuristic (illustrative):** many experienced athletes anchor “long” at **~2+ hours**; others may be shorter or longer at the same fitness. **SME exemplar (not a universal prescription):** ~**15–18 mi** when not in marathon-specific build (often **15**, occasional **18**); marathon build may reach **~22–24 mi** at peak when tolerance supports it.
- **typical_build_context_tags:** `base_building`, `durability_rebuild`, `injury_return`, `full_featured_healthy`, `minimal_sharpen` (shortened), `race_specific` (easy long while quality is expressed on other days or as embedded work elsewhere)
- **typical_placement:** Weekly for most competitive distance runners; often weekend; backbone from 5K through marathon **when** a long day fits the athlete’s architecture.
- **pairs_poorly_with:** Heavy VO2 or long MP block **same day**; racing long hard mid-week without recovery context.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer) for stop tolerance, scalable “long” definition, session-spike caution, and injury-return N=1 framing. Founder-authored builder ref (not athlete-facing bibliography): [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4 (no third-party program names in user surfaces).

---

## `long_progressive_moderate_finish`

- **stem:** `long`
- **display_name:** Progressive long (easy → moderate)
- **sme_status:** `draft`
- **volume_family:** `composite`
- **definition:** Mostly **easy** long run with a **late** segment that **smoothly** picks up to **steady moderate**—**not** marathon- or half-marathon **race pace**, and **not** **threshold** work (StrideIQ does not use “tempo” as a system term—§4.2). Teaches patience and a controlled **finish rhythm** without full race specificity.
- **execution:** Early bulk **easy** at true conversational effort—**stops** for fluid/fuel/bathroom on the easy bulk are fine (same philosophy as **`long_easy_aerobic_staple`**). Final **~15–25%** of the run: **gradual** shift toward **moderate/steady**; **no** kick or sprint. If the top feels like **threshold**, the progression was too aggressive or started too early. Post-run: judge effort and pace with **terrain, weather, and fatigue** context.
- **primary_adaptations:** Aerobic base + late neuromuscular engagement; pacing discipline.
- **systems_stressed:** Slightly higher late-load than pure easy long; still lower than MP/HMP blocks.
- **benefits:** Bridges toward race-specific longs; useful when athletes start too hot or need a **controlled** late pick-up without MP/HMP stress.
- **risks:** **Easy** miles too fast; late segment drifts into **threshold** by mistake; **single-session spike** if total duration or late-quality jump far beyond recent longest or typical quality load.
- **when_to_avoid:** **`injury_return`** until easy longs (and easy bulk discipline) are consistently tolerated; acute flare patterns with late-hard running.
- **n1_selection_notes:** Strong fit **`base_building`** → early **`race_specific`**; **`peak_fitness`** / **`full_featured_healthy`** when programming calls for **moderate** finish only. Distinct from **`long_hmp_finish_half_marathon`** and **`long_fast_finish_race_pace_touch`** (those carry **race-pace** intent—this one does **not**).
- **typical_build_context_tags:** `base_building`, `race_specific`, `full_featured_healthy`, `peak_fitness`
- **typical_placement:** Mid-base through early specific; occasional use later when **easy** long + **light** rhythm work is indicated.
- **pairs_poorly_with:** Standalone **threshold**-dense day **next morning** for low-tolerance athletes without explicit plan intent.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer), aligned with easy-long / session-load principles; internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## `long_fast_finish_race_pace_touch`

- **stem:** `long`
- **display_name:** Fast-finish long (race-pace touch)
- **sme_status:** `draft`
- **volume_family:** `composite`
- **definition:** **Large easy bulk** with a **short** finish at **goal race pace for the target event** (from **Training Pace Calculator** / goal race anchor)—a **touch** of specificity, **not** a second race inside the long run. **Not** a continuous **MP block** (see **`long_mp_continuous_marathon`**) and **not** **threshold**.
- **execution:** Keep the **majority** truly easy—**stops** for fuel/fluid on the easy bulk are compatible with the intent. Final **~2–4 mi** (or **~10–15 min**) at **goal pace** only when tolerance and weekly structure support it; **±5 s/mi** band around calculator pace when the product surfaces numbers—**conditions** still explain splits. Requires **early** discipline so the finish is the **only** hard segment.
- **primary_adaptations:** Late-race neuromuscular and metabolic specificity; confidence closing on tired legs.
- **systems_stressed:** Eccentric and metabolic **spike** in the final segment; glycogen demand.
- **benefits:** Time-efficient **race-pace rehearsal** without full MP/HMP long architecture.
- **risks:** Scheduling **every** week; easy miles too fast; morphing into **full MP long** or **threshold** by accident; **spike injury risk** if total long or finish segment jumps abruptly vs recent longest / recent quality.
- **when_to_avoid:** **`injury_return`**; low durability; extreme heat without adjusted expectations; novice athletes without easy-long discipline.
- **n1_selection_notes:** Reserve for **`race_specific`** / **`peak_fitness`**; **low frequency** vs **`long_easy_aerobic_staple`**. Match **pace** to the **goal distance** (e.g. marathon goal vs half goal)—do not use **threshold** as a proxy.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Late base / specific; **not** the weekly default.
- **pairs_poorly_with:** **`long_mp_continuous_marathon`**, **`long_mp_intervals_in_long`**, or **`long_hmp_finish_half_marathon`** in the same microcycle without explicit volume/tolerance rationale.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer); internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## `medium_long_aerobic_staple`

- **stem:** `medium_long`
- **display_name:** Medium-long run (aerobic)
- **sme_status:** `draft`
- **volume_family:** `long` (stem family **`medium_long`**; aerobic accounting often `E`)
- **definition:** Mid-week **endurance layer**—**longer than** a typical **single** easy day, **shorter than** the **peak** weekly long; **all easy** unless another variant is explicitly selected. Same **stop tolerance** as **`long_easy_aerobic_staple`** (fluid, fuel, bathroom, brief regrouping).
- **execution:** True **conversational** easy (or **aerobic**—**easy** but not necessarily **recovery**—when that’s the chosen flavor for the day). The engine may use **~70–75%** of the **athlete’s peak weekly long distance** as a **conceptual** scaler anchor—**shorthand only**; **every runner is different** (weekly shape, tolerance, doubles vs singles, and race block all change the right MLR). **Founder exemplar (one N=1, not a rule):** a **15 mi** mid-long often landed near **~75%** of **that** build’s weekend long in **that** athlete’s week math—**do not** treat **15** or **75%** as targets for all users. **No** embedded quality in **this** variant unless explicitly programmed elsewhere. Avoid **pace creep** into steady moderate when the day is supposed to stay **true easy / aerobic**.
- **primary_adaptations:** Aerobic volume with **lower** peak musculoskeletal dose than the longest run.
- **systems_stressed:** Moderate time on feet; recovery cost typically **below** peak long.
- **benefits:** Spreads weekly load; supports durability and mileage **without** always stacking duration on one day.
- **risks:** Scheduling **too close** to hard sessions for fragile athletes; **spike** if MLR duration jumps far above recent mid-week norms; pace creep.
- **when_to_avoid:** When **maximum** simplicity is needed (fold into plain easy days); acute injury patterns where **any** extra duration mid-week hurts.
- **n1_selection_notes:** **`base_building`**, **`full_featured_healthy`**, **`race_specific`** (volume support without weekend-only architecture). **`durability_rebuild`**: use **shorter** MLR. For **newer** athletes, “medium-long” still scales off **typical** easy-day length—see principles (e.g. **> ~2×** daily easy when daily volume is small; **not** linear at high daily mileage). **Marathon / half blocks:** mid-long is often a **staple**—**distance and % of long are N=1**; the **75%** idea is **illustrative** for one founder build, **not** “everyone’s mid-long must be 75% of long.”
- **typical_build_context_tags:** `base_building`, `full_featured_healthy`, `race_specific`, `durability_rebuild` (shorter MLR)
- **typical_placement:** Mid-week.
- **pairs_poorly_with:** **Threshold intervals** or **VO2** **same day**; **`long_mp`** or heavy quality **next day** without recovery rationale.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer), consistent with easy-long / distributed-load framing; internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## `long_mp_continuous_marathon`

- **stem:** `long_mp`
- **display_name:** Long run with continuous marathon-pace block
- **sme_status:** `draft`
- **volume_family:** `composite`
- **definition:** Long run with a **continuous** block at **marathon goal pace** after an **easy** warm-up—**marathon-specific endurance**. **MP** comes from **Training Pace Calculator** / marathon goal anchor—**not** **threshold** pace and **not** “tempo” language (§4.2).
- **execution:** Easy warm-up (stops for fuel/fluid **before** MP block are fine). **MP** segment: use **±5 s/mi** band around calculator MP when numeric ranges are shown—**effort + context** over split-chasing on rolling terrain / heat / wind. Easy cool-down. Total run and **MP minutes/miles** capped by **peak long** rules and engine **MP volume limits**; progression should respect **recent longest run** and **recent MP exposure** (avoid **single-session** and **single-block** spikes vs what the athlete has tolerated).
- **primary_adaptations:** Marathon-specific metabolic and musculoskeletal durability at **goal** marathon rhythm.
- **systems_stressed:** High glycogen demand; eccentric load **especially** if hilly or if form degrades late.
- **benefits:** Direct rehearsal of **race rhythm** at goal MP; efficient specificity per mile at the target event pace.
- **risks:** **Too frequent** MP longs; MP set **too fast** vs current fitness; ignoring **heat, hills, dehydration** in post-run review; stacking with other dense quality without recovery.
- **when_to_avoid:** **Half-marathon–primary** athletes unless explicitly repurposed; **`injury_return`**; early base before **easy** longs and **easy** discipline are solid; low durability / low data confidence on appropriate MP.
- **n1_selection_notes:** **`race_specific`**, **`peak_fitness`** for **marathon** focus; alternate with **`long_easy_aerobic_staple`** and cutback weeks. Often **one** primary MP-long architecture in a microcycle unless volume/tolerance clearly support more.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Marathon **specific** phase; progression aligned with engine **mp_week**-style sequencing where applicable.
- **pairs_poorly_with:** Dense **`long_hmp_finish_half_marathon`** week; **`long_mp_intervals_in_long`** **plus** this variant without volume rationale; **threshold**-heavy adjacent days for fragile athletes without intent.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer); scaler alignment (`workout_scaler`); internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## `long_mp_intervals_in_long`

- **stem:** `long_mp` (engine may surface structured option as `long_mp_intervals` in option payloads—treat as same family)
- **display_name:** Long run with MP intervals (easy between)
- **sme_status:** `draft`
- **volume_family:** `composite`
- **definition:** Same **marathon specificity** as **`long_mp_continuous_marathon`**, but **broken** into reps with **easy** running between—e.g. **2 × 3 mi @ MP** with **~1 mi easy** between (illustrative). Reduces **continuous** MP musculoskeletal and metabolic stress; useful when introducing MP in-long or when athletes struggle to hold **one** long MP segment.
- **execution:** Warm up easy. **MP** reps at calculator MP (**±5 s/mi** when surfaced); **honest** easy **jog** between—**not** a steady moderate “float.” Brief **stop** for fuel between reps is acceptable if it preserves **true** easy between. Cool down easy. **Total MP** miles/minutes still capped by weekly / session rules; watch **transitions** (they add **mechanical** load).
- **primary_adaptations:** MP rhythm with **partial** recovery; neuromuscular practice at goal pace in **repeat** form.
- **systems_stressed:** Transitions + **accelerations** add load; still **high** metabolic demand.
- **benefits:** **Chunked** psychology; for some athletes, **lower** risk than the first **long continuous** MP exposure.
- **risks:** “Easy” between becomes **moderate**; **total MP** volume **creep** across the week; **spike** if combined MP time jumps vs recent history.
- **when_to_avoid:** Same family contraindications as **`long_mp_continuous_marathon`**; **novices** without easy-long foundation; **`injury_return`** unless explicitly progressed.
- **n1_selection_notes:** Often **`race_specific`** **before** the longest **continuous** MP weeks; bridge in **`peak_fitness`** / **`full_featured_healthy`** marathon blocks.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Early **specific** → mid **specific**.
- **pairs_poorly_with:** **`long_mp_continuous_marathon`** **plus** this pattern in the same week without volume support; stacked **MP** elsewhere without rationale.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer); maps to scaler structured MP pattern; internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## `long_hmp_finish_half_marathon`

- **stem:** `long_hmp`
- **display_name:** Long run with half-marathon pace finish
- **sme_status:** `draft`
- **volume_family:** `composite`
- **definition:** Long run with a **late** segment at **half-marathon goal pace**—**harder** than **MP** work and **distinct** from **threshold** prescription (do **not** derive HMP from **threshold** pace; §4.2—no “tempo” vocabulary).
- **execution:** Early miles **easy**—**stops** on the easy bulk OK. **HMP** finish: pace from **Training Pace Calculator** / HM goal (**±5 s/mi** when surfaced). Engine may progress **~3 → 4 → 6 → 8 mi** style caps **vs** total long—treat as **illustrative**; **N=1** tolerance governs. Cool down easy after the HMP segment when programmed.
- **primary_adaptations:** HM-specific **durability** and **rhythm** at race effort; lactate handling at **HM** intensity (not generic “hard”).
- **systems_stressed:** **High** late-run load—typically **greater** stress than **MP**-quality at comparable **duration** at quality.
- **benefits:** Strong **HM / 10-mile–oriented** race-prep stimulus; teaches **closing** at **HM** rhythm after volume.
- **risks:** Confusing **HMP** with **threshold** or **10K** pace; programming **too often** on tired legs; **spike** if HMP-mileage jumps vs recent history.
- **when_to_avoid:** **Marathon-primary** athletes unless explicitly repurposed; **`injury_return`**; early base; athletes without **easy** bulk discipline.
- **n1_selection_notes:** **`race_specific`**, **`peak_fitness`** for **half** focus; ensure the **week** tolerates **late** quality. Not the default for marathon blocks.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Late base / **specific** for **HM**.
- **pairs_poorly_with:** Dense **`long_mp_continuous_marathon`** / **`long_mp_intervals_in_long`** in the same week for **single-distance** focus athletes without explicit rationale.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer); aligns with scaler `_scale_hmp_long_run`; internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## `long_cutdown_aerobic_to_steady`

- **stem:** `long`
- **display_name:** Cutdown long (segments pick up pace)
- **sme_status:** `draft`
- **volume_family:** `composite`
- **definition:** **Several** segments in **one** long run, each **a bit faster** than the last—starts **very easy**, ends **steady hard** but **controlled**. **Not** an interval session and **not** **threshold** reps; **not** a race-pace **MP/HMP** variant unless explicitly **re-labeled** to that family. **No** all-out sprint finish here.
- **execution:** Example: **4–6** segments with **small** pace steps; early segments must stay **truly easy**. **Stops** between segments for fuel/fluid are acceptable if they don’t turn the run into **interval** training psychologically. **Top** end stays **steady hard / aerobic-steady**—if it becomes **threshold**, steps were too large or easy baseline was too fast. Requires **strong** pacing literacy and conservative **first** segment.
- **primary_adaptations:** Pacing skill; progressive recruitment; engagement on long days without **race-pace** load.
- **systems_stressed:** **Cumulative** fatigue across steps; high misuse risk—**easy** to bleed into **threshold**.
- **benefits:** Variety; teaches **discipline** on **small** gear changes without MP/HMP stress.
- **risks:** Athletes **hammer** each rep; **coach/system** must **cap** top intensity and **step size**; **spike** risk if total **quality-equivalent** load jumps vs recent long runs.
- **when_to_avoid:** **`injury_return`**; athletes who **cannot** hold **easy** early; low self-regulation / always-overpace profiles until basics improve.
- **n1_selection_notes:** **`full_featured_healthy`**, **`race_specific`**, **`peak_fitness`** for **advanced** athletes—**not** a default population long. **`base_building`**: only **mild** cutdown with explicit SME intent.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`, `base_building` (mild cutdown only + SME)
- **typical_placement:** Mid–late season segments for athletes who tolerate **complex** long-run structure.
- **pairs_poorly_with:** Dense **`alternating_threshold_on_minutes`** or other **threshold**-heavy weeks for fragile athletes without rationale.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer); format family varies widely in the wild—this row is **StrideIQ’s controlled** definition; internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## Summary table

| `id` | `stem` | `volume_family` | `sme_status` |
|------|--------|-----------------|--------------|
| `long_easy_aerobic_staple` | long | long | approved |
| `long_progressive_moderate_finish` | long | composite | draft |
| `long_fast_finish_race_pace_touch` | long | composite | draft |
| `medium_long_aerobic_staple` | medium_long | long | draft |
| `long_mp_continuous_marathon` | long_mp | composite | draft |
| `long_mp_intervals_in_long` | long_mp | composite | draft |
| `long_hmp_finish_half_marathon` | long_hmp | composite | draft |
| `long_cutdown_aerobic_to_steady` | long | composite | draft |

**Rollup:** **`approved`** = **1** (`long_easy_aerobic_staple`). **`draft`** = **7** (all other ids in this table).

---

*Pilot v1 — 8 long-family variants. **`sme_status` per row** (header + table + rollup above); runtime wiring still §2 / P0.*
