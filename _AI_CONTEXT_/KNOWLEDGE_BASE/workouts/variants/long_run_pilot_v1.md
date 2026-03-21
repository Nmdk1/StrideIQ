# Long-run pilot — variant definitions (v1)

**Spec:** `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md` v0.2.23 · **Sequence:** `docs/specs/WORKOUT_FLUENCY_BUILD_SEQUENCE.md`  
**Stems covered:** `long`, `medium_long`, `long_mp`, `long_hmp` (aliases per `workout_scaler.py`: `long_run`, `marathon_pace_long`, etc.)

**Engine reference:** `apps/api/services/plan_framework/workout_scaler.py` — `_scale_long_run`, `_scale_medium_long`, `_scale_mp_long_run`, `_scale_hmp_long_run`.

**Primary consumer:** **Deterministic planning pipelines** (selection matrix → plan constants → **CI**). This file is **SME-grounded machine-ingestible spec**: a **toolbox** of blocks mapped by tags, athlete signals, caps, and `pairs_poorly_with` / `when_to_avoid`. Prose must stay **extractable**—stable **`id`**, closed **`typical_build_context_tags`**, explicit constraints—so Phase 2 can compile Markdown → validated registry without reinterpretation drift. **Human-readable narrative is secondary** to that goal, except **`display_name`** and other **athlete-facing** strings derived from these rows (product copy).

**SME approval:** **All nine** Pilot 2 long-family variant ids **`approved`** — eight **2026-03-20** / **2026-03-22** as prior header; **`long_mp_over_under_alternating_miles`** **2026-03-22** (finishing Phase 1 fluency KB). Runtime wiring remains gated per `WORKOUT_FLUENCY_REGISTRY_SPEC.md` §2.

**Authoritative status (this file + summary table):** **Truth:** **9** rows **`approved`** (rollup below). This table is the **source of truth** for Pilot 2 counts.

**`draft` / `approved` (general):** **`approved`** means SME-cleared for KB / registry **shipping slice** (Phase 2+)—not permission to bypass §2 for runtime wiring. New rows in **any** pilot file stay **`draft`** until explicit founder promotion (e.g. deferred tracks, future extensions).

**Cross-reference:** Embedded **threshold** quality in the **last** portion of a long day is also described in `threshold_pilot_v1.md` (`progressive_threshold_25_40`). Prefer **one** canonical variant for “quality in the long run” unless SME splits long-stem vs threshold-stem dispatch.

---

## StrideIQ long-run principles (founder Q&A incorporated; **9** rows **`approved`** — see rollup)

- **Easy long** is the **weekly structural anchor** for most athletes—time on feet, aerobic load, durability. Pace is **easy conversational**; use **Training Pace Calculator** (goal race or best recent race anchor) and RPE as context, not race effort on the easy bulk.
- **Most runners should have a long run** in the week; what counts as “long” **scales with the athlete**. For **newer** runners, a pragmatic floor is **more than double** a typical **single** easy day (when daily volume is small). For **high-mileage** athletes, “double daily” stops being meaningful—long is **no longer linear** off daily miles; use **time on feet**, recent longest session, and plan caps instead.
- **Stops are normal:** brief stops for **fluid, fuel, bathroom, or regrouping** (including short walking) do not invalidate an easy long—the session is defined by **easy effort and duration**, not uninterrupted clock continuity.
- **Total distance** scales with weekly volume and race distance; internal scaler uses ~**28–30%** of weekly volume toward long-run target with **tier/distance peaks**—variants describe **structure**, not replace safety caps.
- **Post-run analysis:** same as threshold pilot—**elevation, temperature, wind, sun, surface, fatigue** affect realized pace; judgment needs context.
- **Injury return and tolerance** are **N=1**; do not treat any exemplar below as a universal rule.
- **Fueling and hydration (marathon readiness):** details vary by athlete, but **successful marathon racing** requires both **practicing** fluid and fuel on **long runs** and **executing** the plan in the race. Stopping briefly to get hydration or fuel down is **valid**—a few seconds lost beats under-fueling.

---

## StrideIQ prescription & environment (long-family)

**Cross-cutting (SME session):** MP/HMP from **Training Pace Calculator** / goal race—not threshold. **±5 s/mi** band when numeric ranges are shown. **All nine** **`approved`** rows incorporate **2026-03-20** founder Q&A plus **2026-03-22** promotions, including **`long_mp_over_under_alternating_miles`** (**2026-03-20** pattern, **high-bar** — not a first-build default).

**Marathon-pace (MP) and half-marathon-pace (HMP) segments in long runs:**

- Prescribe **MP** and **HMP** from the **Training Pace Calculator** using the athlete’s **goal race** (or best defensible race anchor the product already uses for those distances)—not from threshold pace. **MP ≠ threshold** in copy or logic.
- **Band (per mile, when the product surfaces a numeric range):** treat **±5 seconds per mile** around calculator MP or HMP as the same **execution tolerance** philosophy as threshold sessions unless SME narrows or widens for a specific variant—effort + context still beat split-chasing.
- **MP over-under miles (alternating):** **advanced** marathoners—typically **2nd / 3rd+** marathon **build**, many long runs **already** in the legs—may use alternating **mile** segments **faster** then **slower** than goal **MP** by a **small fixed offset** (founder exemplar **~15–20 s/mi** each way)—see **`long_mp_over_under_alternating_miles`**. **Plateau / engagement** tool, **not** a first-build default. **Structured MP rhythm**, not threshold reps and not an easy long mislabeled.

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
- **execution:** Ease into conversational pace; hold easy for the run as a whole. **Practice** fluid and fuel strategy on long runs as you would on race day (exact products and timing **N=1**). **Stop as needed** for hydration and fuel—especially heat or high sweat loss—without treating the session as “broken.” Cap distance/time per weekly volume, peak rules, and **recent longest-run progression** (avoid abrupt single-session spikes vs what the athlete has tolerated in the prior few weeks). Narrative: prioritize **effort + context**, not uninterrupted clock purity.
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
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** **Why this exists:** for athletes who are **adding mileage and long-run base** but show **durability drift** on long easy days—e.g. **loss of efficiency** late, **pace falling** in the final third when effort should still be easy, or **cardiac drift** that is **outsized** for the context. This session teaches a **controlled late pick-up to steady moderate** without jumping to **marathon/half race pace** and without **threshold** work (no “tempo” vocabulary—§4.2). **What it is:** mostly **easy** long run; final **~15–25%** of the run **smoothly** progresses to **moderate/steady**—**not** a race-pace finish variant.
- **execution:** Early bulk **easy** at true conversational effort—**stops** for fluid/fuel/bathroom on the easy bulk are fine (same philosophy as **`long_easy_aerobic_staple`**). Final **~15–25%** of the run (**distance- or time-based, pick one consistent method for the athlete**): **gradual** shift toward **moderate/steady**; **no** kick or sprint. If the top feels like **threshold**, the progression was too aggressive or started too early. Post-run: judge effort and pace with **terrain, weather, and fatigue** context.
- **primary_adaptations:** Aerobic base + late neuromuscular engagement; **durability of pacing** on tired legs without race-pace load.
- **systems_stressed:** Slightly higher late-load than pure easy long; still lower than MP/HMP blocks.
- **benefits:** Addresses **late-run breakdown patterns** on easy longs while staying below race-pace stress; bridges toward later race-specific longs when the athlete is ready.
- **risks:** **Easy** miles too fast; late segment drifts into **threshold** by mistake; **single-session spike** if total duration or late-quality jump far beyond recent longest or typical quality load.
- **when_to_avoid:** **`injury_return`** until easy longs (and easy bulk discipline) are consistently tolerated; acute flare patterns with late-hard running.
- **n1_selection_notes:** Choose this when **signal** suggests **durability/form** on long runs needs work **before** assigning **`long_fast_finish_race_pace_touch`** or **`long_mp_*`**. Strong fit **`base_building`** → early **`race_specific`**; **`peak_fitness`** / **`full_featured_healthy`** when the **purpose** is **moderate** finish only—not race-pace rehearsal. Distinct from **`long_hmp_finish_half_marathon`** and **`long_fast_finish_race_pace_touch`** (**race-pace** intent—this one does **not**).
- **typical_build_context_tags:** `base_building`, `race_specific`, `full_featured_healthy`, `peak_fitness`
- **typical_placement:** Mid-base through early specific; occasional use later when **easy** long + **light** rhythm work is indicated.
- **pairs_poorly_with:** Standalone **threshold**-dense day **next morning** for low-tolerance athletes without explicit plan intent.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer), aligned with easy-long / session-load principles; internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## `long_fast_finish_race_pace_touch`

- **stem:** `long`
- **display_name:** Fast-finish long (marathon — final ~2 mi)
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** **Marathon-specific** long run: **large easy bulk**, then **~2 miles** at **marathon goal pace or slightly faster** (from **Training Pace Calculator** / marathon goal)—to rehearse **pushing hard on tired legs** and the **feel of late-race marathon** (e.g. miles **~24–26.2**), **not** to run a second marathon inside the workout. **Not** a continuous **MP long** (see **`long_mp_continuous_marathon`**) and **not** **threshold**. **Why:** for athletes who have **already built durability** and are sharpening **race-day characteristics**—**not** the default for a **first-time** marathon breakthrough (e.g. “break 4 for the first time”) or athletes still earning easy-long discipline.
- **execution:** Keep the **majority** truly easy—**stops** for fuel/fluid on the easy bulk are compatible (brief stops to **get hydration down** are **smart**, not a failure). Final **~2 mi** at **MP or faster** when tolerance and week structure support it—**two miles is enough** for this purpose; **±5 s/mi** band around calculator MP when numbers are shown—**conditions** still explain splits. Requires **early** discipline so the finish is the **only** hard segment. **Practice** marathon fueling/hydration on the easy bulk as for race day (**N=1** products/timing).
- **primary_adaptations:** Late-marathon neuromuscular and metabolic specificity; **confidence and skill** closing when already loaded.
- **systems_stressed:** Eccentric and metabolic **spike** in the final segment; glycogen demand.
- **benefits:** **Time-efficient** rehearsal of **late-marathon** demand without full MP-in-long architecture.
- **risks:** Scheduling **every** week; easy miles too fast; morphing into **full MP long** or **threshold** by accident; **spike injury risk** if total long or finish segment jumps abruptly vs recent longest / recent quality.
- **when_to_avoid:** **`injury_return`**; low durability; extreme heat without adjusted expectations; **novice / first-marathon** athletes still building base—prefer **`long_progressive_moderate_finish`** or pure easy longs first.
- **n1_selection_notes:** Reserve for **`race_specific`** / **`peak_fitness`** in **marathon** blocks; **low frequency** vs **`long_easy_aerobic_staple`**. **Half-marathon** or **10K** “fast finish” is **not** this row’s primary intent—use goal-specific programming elsewhere unless SME explicitly maps. Pace from **marathon goal**, not **threshold**.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Late base / marathon **specific**; **not** the weekly default.
- **pairs_poorly_with:** **`long_mp_continuous_marathon`**, **`long_mp_intervals_in_long`**, or **`long_hmp_finish_half_marathon`** in the same microcycle without explicit volume/tolerance rationale.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer); internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## `medium_long_aerobic_staple`

- **stem:** `medium_long`
- **display_name:** Medium-long run (aerobic)
- **sme_status:** `approved`
- **volume_family:** `long` (stem family **`medium_long`**; aerobic accounting often `E`)
- **definition:** Mid-week **endurance layer**—**longer than** a typical **single** easy day, **shorter than** the **peak** weekly long. In **marathon and half** blocks this is often a **staple** day. Default flavor: **all easy / aerobic** unless another variant is explicitly selected. Same **stop tolerance** as **`long_easy_aerobic_staple`** (fluid, fuel, bathroom, brief regrouping).
- **execution:** **Aerobic** running—**easy** but **not necessarily recovery-easy** when that’s the intent for the day. The engine may use **~70–75%** of the **athlete’s peak weekly long distance** as a **conceptual** scaler anchor—**shorthand only**; **every runner is different**. **Founder exemplar (one N=1, not a rule):** mid-long often **~15 mi** and ~**75%** of **that** week’s long in **that** build; weekend longs in the same period might land **~18–22 mi** while key longs included **MP** work—**do not** copy those numbers as universal. **Optional progression (SME):** a **few** times per build, the same mid-long architecture can be run **~20 s/mi slower than marathon goal pace**—**high durability benefit** and **relatively lower injury risk** vs race-pace longs, but it **loads cumulative fatigue** and needs **time to adapt**; not for early in a relationship with mid-long volume. **Strides:** **not** on day one—after the athlete **has adapted** to the mid-long, **occasional** strides at the end are fine; **not every time**—**vary** the stimulus so the runner doesn’t dread or stale the day. **Practice** fuel/hydration on longer MLRs as for race prep (**N=1**). Avoid **pace creep** when the day is supposed to stay **true easy / aerobic**.
- **primary_adaptations:** Aerobic volume with **lower** peak musculoskeletal dose than the longest run; **durability** when **steady aerobic** or **MP-minus** variants are used intentionally.
- **systems_stressed:** Moderate time on feet; recovery cost typically **below** peak long; **MP-minus** versions add **fatigue debt** over the mesocycle.
- **benefits:** Spreads weekly load; supports mileage and **durability** without always stacking all duration on one day; **MP-minus** mid-long (when used) can build **race-specific strength** with controlled risk.
- **risks:** Scheduling **too close** to hard sessions for fragile athletes; **spike** if MLR duration jumps far above recent mid-week norms; pace creep; **under-recovery** if **MP-minus** or long MLR is stacked without easy days around it.
- **when_to_avoid:** When **maximum** simplicity is needed (fold into plain easy days); acute injury patterns where **any** extra duration mid-week hurts.
- **n1_selection_notes:** **`base_building`**, **`full_featured_healthy`**, **`race_specific`** (volume support). **`durability_rebuild`**: use **shorter** MLR. **Marathon / half blocks:** often a **weekly staple**; **distance and % of long are N=1** (75% is **illustrative**, not law). **MP on mid-long** a **couple** of times per build is a **valid** programming pattern (may be expressed via scaler / alternate variant—coordinate with engine); **big MP weeks** should **protect** the athlete with **easy** days **before and after** heavy sessions.
- **typical_build_context_tags:** `base_building`, `full_featured_healthy`, `race_specific`, `durability_rebuild` (shorter MLR)
- **typical_placement:** Mid-week.
- **pairs_poorly_with:** **Threshold intervals** or **VO2** **same day**; **`long_mp`** or heavy quality **next day** without recovery rationale.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer), consistent with easy-long / distributed-load framing; internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## `long_mp_continuous_marathon`

- **stem:** `long_mp`
- **display_name:** Long run with continuous marathon-pace block
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** Long run with a **continuous** block at **marathon goal pace** after an **easy** warm-up—**marathon-specific endurance**. **MP** comes from **Training Pace Calculator** / marathon goal anchor—**not** **threshold** pace and **not** “tempo” language (§4.2).
- **execution:** Easy warm-up—**brief stops** to get **fluid/fuel down** before or during MP are **acceptable** (execution quality beats stopwatch purity). **MP** segment: **±5 s/mi** band around calculator MP when numeric ranges are shown—**effort + context** over split-chasing. **Practice** race fueling and hydration on **every** long run that includes meaningful MP (**N=1** plan). Easy cool-down. Total run and **MP minutes/miles** capped by **peak long** rules and engine **MP volume limits**; progression should respect **recent longest run** and **recent MP exposure** (avoid **single-session** and **single-block** spikes vs what the athlete has tolerated).
- **primary_adaptations:** Marathon-specific metabolic and musculoskeletal durability at **goal** marathon rhythm.
- **systems_stressed:** High glycogen demand; eccentric load **especially** if hilly or if form degrades late.
- **benefits:** Direct rehearsal of **race rhythm** at goal MP; efficient specificity per mile at the target event pace.
- **risks:** **Too frequent** MP longs; MP set **too fast** vs current fitness; ignoring **heat, hills, dehydration** in post-run review; stacking with other dense quality without recovery.
- **when_to_avoid:** **Half-marathon–primary** athletes unless explicitly repurposed; **`injury_return`**; early base before **easy** longs and **easy** discipline are solid; low durability / low data confidence on appropriate MP.
- **n1_selection_notes:** **`race_specific`**, **`peak_fitness`** for **marathon** focus; alternate with **`long_easy_aerobic_staple`** and cutback weeks. **Cadence (founder exemplar, N=1):** often **every 2–3 weeks** depending on **block structure**—not necessarily every week. **Big MP days** (e.g. **~20 mi** with **~16 mi** at MP) are a **major** stressor: structure the **week** around them—**several easy days before** so the athlete is **fresh going in**, and **easy days after** to **consolidate**; do not bury them in dense quality without intent. **MP on mid-long** a **couple** times per build can pair with this family when programmed—watch **weekly** load. **Founder pattern:** tolerance for **long continuous MP** segments; many athletes may use **`long_mp_intervals_in_long`** as a **bridge** first (see that row).
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Marathon **specific** phase; progression aligned with engine **mp_week**-style sequencing where applicable.
- **pairs_poorly_with:** Dense **`long_hmp_finish_half_marathon`** week; **`long_mp_intervals_in_long`** **plus** this variant without volume rationale; **threshold**-heavy adjacent days for fragile athletes without intent.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer); scaler alignment (`workout_scaler`); internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## `long_mp_intervals_in_long`

- **stem:** `long_mp` (engine may surface structured option as `long_mp_intervals` in option payloads—treat as same family)
- **display_name:** Long run with MP intervals (easy between)
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** Same **marathon specificity** as **`long_mp_continuous_marathon`**, but **broken** into reps with **easy** running between—e.g. **2 × 3 mi @ MP** with **~1 mi easy** between (illustrative). Reduces **continuous** MP musculoskeletal and metabolic stress; common **bridge** when introducing MP in-long or when an athlete does **not** tolerate **one long continuous** MP segment well.
- **execution:** Warm up easy. **MP** reps at calculator MP (**±5 s/mi** when surfaced); **honest** easy **jog** between—**not** a steady moderate “float.” **Stops** for fuel, fluid, or safety between reps are **fine** if **easy** running between stays **honest**—forcing “no stopping” is **counterproductive** for real-world execution. Cool down easy. **Total MP** miles/minutes still capped by weekly / session rules; watch **transitions** (they add **mechanical** load). **Practice** fueling/hydration as for race day (**N=1**).
- **primary_adaptations:** MP rhythm with **partial** recovery; neuromuscular practice at goal pace in **repeat** form.
- **systems_stressed:** Transitions + **accelerations** add load; still **high** metabolic demand.
- **benefits:** **Chunked** psychology; for some athletes, **lower** risk than the first **long continuous** MP exposure.
- **risks:** “Easy” between becomes **moderate**; **total MP** volume **creep** across the week; **spike** if combined MP time jumps vs recent history.
- **when_to_avoid:** Same family contraindications as **`long_mp_continuous_marathon`**; **novices** without easy-long foundation; **`injury_return`** unless explicitly progressed.
- **n1_selection_notes:** Often **`race_specific`** **before** the longest **continuous** MP weeks; bridge in **`peak_fitness`** / **`full_featured_healthy`** marathon blocks. **Population note:** many plans use **fractionated** MP in long runs as a **progression** tool; **founder SME** often preferred **long continuous MP** in personal training—**both** patterns are valid; selection is **N=1** tolerance and psychology, not dogma.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Early **specific** → mid **specific**.
- **pairs_poorly_with:** **`long_mp_continuous_marathon`** **plus** this pattern in the same week without volume support; stacked **MP** elsewhere without rationale.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer); maps to scaler structured MP pattern; internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## `long_hmp_finish_half_marathon`

- **stem:** `long_hmp`
- **display_name:** Long run with half-marathon pace finish
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** Long run with a **late** segment at **half-marathon goal pace**—**harder** than **MP** work and **distinct** from **threshold** prescription (do **not** derive HMP from **threshold** pace; §4.2—no “tempo” vocabulary).
- **execution:** Early miles **easy**—**stops** on the easy bulk OK. **HMP** finish: pace from **Training Pace Calculator** / HM goal (**±5 s/mi** when surfaced). **Brief stops** for fluid/fuel during the quality portion are **acceptable** if execution quality is preserved. Engine may progress **~3 → 4 → 6 → 8 mi** style caps **vs** total long—treat as **illustrative**; **N=1** tolerance governs. Cool down easy after the HMP segment when programmed. **Practice** fueling/hydration as for race prep (**N=1**).
- **primary_adaptations:** HM-specific **durability** and **rhythm** at race effort; lactate handling at **HM** intensity (not generic “hard”).
- **systems_stressed:** **High** late-run load—typically **greater** stress than **MP**-quality at comparable **duration** at quality.
- **benefits:** Strong **HM / 10-mile–oriented** race-prep stimulus; teaches **closing** at **HM** rhythm after volume.
- **risks:** Confusing **HMP** with **threshold** or **10K** pace; programming **too often** on tired legs; **spike** if HMP-mileage jumps vs recent history.
- **when_to_avoid:** **Marathon-primary** athletes unless explicitly repurposed; **`injury_return`**; early base; athletes without **easy** bulk discipline.
- **n1_selection_notes:** **`race_specific`**, **`peak_fitness`** for **half** focus; ensure the **week** tolerates **late** quality. Not the default for **marathon-primary** blocks. **Founder note:** fastest **half-marathon** performances have sometimes come **off marathon training**—standalone **HM** peaking and **10K-primary** use of this variant are **less certain**; treat as **N=1 trial** with SME judgment (**HMP caps** for non-marathon-background HM racers remain **illustrative** in execution text).
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Late base / **specific** for **HM**.
- **pairs_poorly_with:** Dense **`long_mp_continuous_marathon`** / **`long_mp_intervals_in_long`** in the same week for **single-distance** focus athletes without explicit rationale.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer); aligns with scaler `_scale_hmp_long_run`; internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## `long_cutdown_aerobic_to_steady`

- **stem:** `long`
- **display_name:** Cutdown long (segments pick up pace)
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** **Several** segments in **one** long run, each **a bit faster** than the last—starts **very easy**, ends **steady hard** but **controlled**. **Not** an interval session and **not** **threshold** reps; **not** the **`long_hmp_finish_half_marathon`** or **`long_fast_finish_race_pace_touch`** variant unless explicitly **re-labeled**. **No** all-out sprint finish here. **Scope (SME):** for athletes typically **>** **~65 mpw** with **durability already built**, **many** long runs under their belt, **time goals** in the **BQ-class** conversation (illustrative—not a gate on who “deserves” the workout), and **plateau-busting** phases—**not** a default for low-mileage or early-base runners.
- **execution:** Example: **4–6** segments with **small** pace steps; early segments must stay **truly easy**. **Stops** between segments for fuel/fluid are acceptable if they don’t turn the run into **interval** training psychologically. **“Steady hard” (SME anchor):** **below threshold**, **above marathon goal pace** when both are known from the calculator—**not** threshold. **Founder exemplar (one N=1):** when **threshold** was **~6:30/mi**, **steady hard** was **~6:45/mi**—faster than **MP** in that cycle, **not** threshold; perceived “**~10–15%**” offset is an **effort/pace shorthand**, not a universal formula—**N=1** calibration. If the top becomes **threshold**, steps were too large or easy baseline was too fast. Requires **strong** pacing literacy and conservative **first** segment.
- **primary_adaptations:** Pacing skill; progressive recruitment; engagement on long days without **race-pace** load.
- **systems_stressed:** **Cumulative** fatigue across steps; high misuse risk—**easy** to bleed into **threshold**.
- **benefits:** **Variety** and **plateau disruption** for **high-mileage**, **durability-rich** athletes; teaches **discipline** on **small** gear changes without MP/HMP stress.
- **risks:** Athletes **hammer** each rep; **coach/system** must **cap** top intensity and **step size**; **spike** risk if total **quality-equivalent** load jumps vs recent long runs.
- **when_to_avoid:** **`injury_return`**; athletes who **cannot** hold **easy** early; low self-regulation / always-overpace profiles until basics improve; **low weekly mileage** or **few** long-run exposures—use simpler long-run variants first.
- **n1_selection_notes:** **`full_featured_healthy`**, **`race_specific`**, **`peak_fitness`** for **advanced**, **high-volume** athletes—**not** a default population long. **`base_building`**: only **mild** cutdown with explicit SME intent.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`, `base_building` (mild cutdown only + SME)
- **typical_placement:** Mid–late season segments for athletes who tolerate **complex** long-run structure.
- **pairs_poorly_with:** Dense **`alternating_threshold_on_minutes`** or other **threshold**-heavy weeks for fragile athletes without rationale.
- **source_notes:** Tier A — founder SME primary (Michael Shaffer); format family varies widely in the wild—this row is **StrideIQ’s controlled** definition; internal ref: [`forget-the-10-rule`](https://mbshaf.substack.com/p/forget-the-10-rule) — spec §4.4.

---

## `long_mp_over_under_alternating_miles`

- **stem:** `long_mp`
- **display_name:** Long run — MP over-under miles
- **sme_status:** `approved`
- **volume_family:** `composite`
- **definition:** For **advanced** marathoners in **their second, third, or later marathon build** who already have **many long runs** behind them—**plateau-breaking** and **interest** on **MP** long days, not a **first-marathon** tool. Within a **long run** with **easy** warm-up and cool-down, the **main set** alternates **full mile** segments: one mile **~15–20 s/mi faster** than calculator **goal MP**, the next mile **~15–20 s/mi slower** than **MP**—repeat for **8–18 miles** of **over-under** work (founder range; **N=1** adjusts **offset**, **mile count**, and **total long** distance). Teaches **MP rhythm**, **discipline**, and **fueling** under **oscillating** pace—**not** cruise **threshold** intervals and **not** a progressive **cutdown** (`long_cutdown_aerobic_to_steady`).
- **execution:** Easy warm-up (distance **N=1**); then **mile A** (MP **minus** offset), **mile B** (MP **plus** offset), alternating; easy cool-down. **±5 s/mi** band philosophy around **each** target mile still applies where the product shows bands—**conditions** change realized splits. **Stops** for fuel/fluid allowed per long-run principles. **Engine:** *not implemented* in `_scale_mp_long_run` today—requires **segmented** long prescription in a future builder.
- **primary_adaptations:** **Marathon** pace ** literacy**; **glycogen** management across **rolling** effort; mental **rhythm** under **small** pace oscillation.
- **systems_stressed:** **Sustained** load with **pace changes** each mile—mechanical and metabolic; **higher** error rate than **steady MP** blocks if athlete **chases** splits without context.
- **benefits:** **Race-specific** **rhythm** practice for athletes who **flatline** or **drift** on steady MP; **mental engagement** and **novelty** for veterans who “already know” steady MP longs; **plateau disruption** when tolerance and history support it.
- **risks:** **Too large** offset → **threshold** / **easy** drift; **too many** miles for current tolerance; **stacking** with **`vo2_3x2mi_long_reps`** or dense **MP** volume same week.
- **when_to_avoid:** **First marathon build** or **few** lifetime long runs; **`injury_return`**; athletes who **cannot** hold **two** distinct **gears**; **minimal_sharpen** full dose; **no** recent **steady MP** foundation; **novice** or **low-mileage** profiles defaulting to simpler **`long_mp_continuous_marathon`** or **`long_easy_aerobic_staple`** first.
- **n1_selection_notes:** **`race_specific`**, **`peak_fitness`** for **marathon-primary** athletes with **multiple** marathon **cycles** and **deep** long-run history—**selection matrix** should require **evidence** of tolerance (e.g. successful **steady MP** longs, volume, no red injury flags), not age alone. **Ledger** must **count** this as **major** **long** quality—not “just easy miles.” **Founder exemplar:** appropriate for a **Boston** (or similar) **build** when the athlete is **not** new to marathon-specific long work.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`, `base_building` (shortened over-under segment + SME)
- **typical_placement:** **Specific** phase **long**; **not** every week.
- **pairs_poorly_with:** **`vo2_3x2mi_long_reps`** same week without SME; **`long_mp_continuous_marathon`** **dress-rehearsal** week overload without rationale.
- **source_notes:** Tier A — founder pattern **2026-03-20** (15–20 s/mi, 8–18 mi alternating block); founder **population gate** **2026-03-20** (advanced, **2nd+** marathon build, long-run **mileage**, plateau / engagement—including founder **Boston** build intent); Tier B — over-under / wave long formats exist widely—this id is **StrideIQ’s MP-centered** definition.

---

## Summary table

| `id` | `stem` | `volume_family` | `sme_status` |
|------|--------|-----------------|--------------|
| `long_easy_aerobic_staple` | long | long | approved |
| `long_progressive_moderate_finish` | long | composite | approved |
| `long_fast_finish_race_pace_touch` | long | composite | approved |
| `medium_long_aerobic_staple` | medium_long | long | approved |
| `long_mp_continuous_marathon` | long_mp | composite | approved |
| `long_mp_intervals_in_long` | long_mp | composite | approved |
| `long_hmp_finish_half_marathon` | long_hmp | composite | approved |
| `long_cutdown_aerobic_to_steady` | long | composite | approved |
| `long_mp_over_under_alternating_miles` | long_mp | composite | approved |

**Rollup:** **`approved`** = **9**. **`draft`** = **0**.

---

*Pilot v1 — **9** long-family variants **`approved`**. **`sme_status` per row** (header + table + rollup above); runtime wiring still §2 / P0.*
