# Intervals / VO2 pilot — variant definitions (v1)

**Spec:** `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md` v0.2.18  
**Stems covered:** `intervals` (engine aliases: `interval`, `vo2max` — same dispatch in `workout_scaler.scale_workout`)

**Engine reference:** `apps/api/services/plan_framework/workout_scaler.py` — `_scale_intervals` routes by **goal distance** (`5k`, `10k`, marathon default) and **phase** / **plan_week** / **athlete_ctx** (e.g. high-volume marathon base). Rep lengths **400m → 800m → 1000m** (5K/10K progressions); **1200m @ ~10K race rhythm** in late **10K** paths. **~8%** of weekly volume cap applies to interval prescription in scaler—treat as **engineering guardrail** until registry wiring; N=1 may need stricter caps.

**Ledger link:** A scheduled **intervals** session is a **heavy** line item on the **weekly stimulus ledger** (see `easy_pilot_v1.md` **Deterministic selection logic**). It **feeds** end-of-easy **stride gear** choices the same week—avoid redundant “same system twice” without intent.

**SME approval:** **All rows below are `sme_status: draft`** until the founder promotes each `id` explicitly. Runtime wiring remains gated per spec §2.

---

## StrideIQ VO2 session intent (SME — product)

**Not threshold, not strides**

- **VO2 / intervals** days are **structured quality**: repeated work bouts with **defined** recovery—not a continuous threshold block, not 15–30 s neuromuscular touches at the end of easy.
- **Pace:** derive from the **Training Pace Calculator** (or equivalent product anchor) for **interval / VO2** zone; prescribed as a **band** where the product supports it, with **conditions** (heat, hills, cumulative fatigue) affecting **realization** like threshold (see **`threshold_pilot_v1.md`** environment themes).
- **Controlled hardness:** “Hard but controlled”—**not** all-out sprinting rep 1 and collapsing; mechanics stay **smooth**; last rep **quality**, not desperation, unless SME-intended peaking context.

**Volume discipline**

- Scaler enforces an **interval volume fraction** of weekly miles—selection matrix must still ask whether **total** quality density (threshold + VO2 + MP + long quality) fits **this** athlete **this** week.

---

## Cross-cutting selection (all variants below)

- **One primary VO2 day** is common for many non-elite weeks; **two** requires **tolerance + ledger** justification.
- After **heavy threshold** loading, prefer **shorter rep** VO2 touches or **spacing** before stacking another dense day—see variant **`vo2_light_touch_after_threshold_week`**.
- **Injury_return** / **minimal_sharpen**: fewer reps, shorter reps, or **suppress** VO2 entirely—variants **`vo2_conservative_low_dose`** and **`vo2_minimal_sharpen_micro_touch`** lean here; **veto** when pain or illness dictates.
- **5K vs 10K vs marathon goal:** engine already branches; variants below **name** those intents for the **matrix** even when segment shapes overlap.

---

## `vo2_400m_short_reps_development`

- **stem:** `intervals`
- **display_name:** VO2 — short repeats (400m)
- **sme_status:** `draft`
- **volume_family:** `I`
- **definition:** **Short repeats** at **interval pace** with **brief** jog recovery—**VO2 ceiling** plus **neuromuscular** turnover demand; typical **early build** or **high-mileage marathon** “speed touch” before longer reps.
- **execution:** Warm-up easy **~2 mi**. Main set: **8–16×400m** (volume-capped) with **~200m** jog or **~1 min** easy between—**hard but controlled**, not sprinting. Cool-down easy **~1 mi**. Matches `_scale_10k_intervals` early weeks, `_scale_5k_intervals` early weeks, and marathon **base_speed** branch for **experienced_high_volume**.
- **primary_adaptations:** VO2max / aerobic power ceiling; neuromuscular coordination at speed.
- **systems_stressed:** CNS + musculoskeletal **repeat** loading; higher stride rate stress than long reps.
- **benefits:** **High-quality stimulus per mile** of hard running; useful when **longer** reps are not yet tolerated or when weekly ledger already has **sustained** threshold.
- **risks:** **Spikes** if rep count jumps too fast; **kicking** into sprint mechanics; ignoring heat/terrain on rep quality.
- **when_to_avoid:** Acute hamstring/calf flare; **no** warm-up discipline; same week as **maximal** neuromuscular load without taper intent.
- **n1_selection_notes:** Strong when **ledger** shows **little short-speed** work but athlete can handle **density**; for **marathon** high-volume **base**, aligns with scaler “safer VO2 touch” branch. Down-rank if **5K-style** density already high from **repetitions** or other work (when **`repetitions`** stem ships).
- **typical_build_context_tags:** `base_building`, `full_featured_healthy`, `race_specific`, `peak_fitness`, `durability_rebuild` (SME-reduced reps), `minimal_sharpen` (micro dose), `injury_return` (rare—SME only)
- **typical_placement:** Mid-week; **not** automatically adjacent to **long with quality** without tolerance check.
- **pairs_poorly_with:** **Second** VO2-density day for low-tolerance athletes; **race week** full dose except experienced profiles.
- **source_notes:** Tier B — short-interval VO2 development patterns; align copy with engine 400m branches.

---

## `vo2_800m_reps_development`

- **stem:** `intervals`
- **display_name:** VO2 — 800m repeats
- **sme_status:** `draft`
- **volume_family:** `I`
- **definition:** **Mid-length** repeats—bridge from **short** reps toward **sustained** VO2 power; **hard** rhythm, **controlled** mechanics.
- **execution:** Warm-up easy **~2 mi**. Main set: **5–8×800m** at interval pace with **~2 min** jog recovery (engine typical). Cool-down easy **~1 mi**. From `_scale_10k_intervals` mid build and `_scale_5k_intervals` mid block.
- **primary_adaptations:** VO2 power; **sustained** hard rhythm; lactate flux tolerance at **sub-1K** rep length.
- **systems_stressed:** Cardiovascular **repeat** peaks; legs under **longer** hard segments than 400m.
- **benefits:** Progression step toward **1K** reps without jumping straight to longest reps.
- **risks:** **Rep 1 too fast**; **degrading** form rep-to-rep; under-fueling on **hot** days.
- **when_to_avoid:** Athlete cannot hold **even** splits; returning from layoff—prefer **400** variant or **threshold** first.
- **n1_selection_notes:** Fits **base_building → race_specific** handoff for **5K/10K** paths; marathon athletes may use **sparingly** depending on ledger.
- **typical_build_context_tags:** `base_building`, `full_featured_healthy`, `race_specific`, `peak_fitness`, `minimal_sharpen` (reduced reps)
- **typical_placement:** Mid-week; spacing vs **threshold** day per tolerance.
- **pairs_poorly_with:** Dense **threshold_intervals** same week without recovery narrative.
- **source_notes:** Tier B — 800m VO2 progression patterns.

---

## `vo2_1000m_reps_classic`

- **stem:** `intervals`
- **display_name:** VO2 — kilometer repeats
- **sme_status:** `draft`
- **volume_family:** `I`
- **definition:** **Classic** kilometer repeats at **interval** pace—**staple** sustained VO2 stimulus for many distance runners.
- **execution:** Warm-up **~2 mi**. Main set: **4–6×1000m** with **~2–3 min** jog (engine default marathon path and late 5K/10K progressions). Cool-down **~1 mi**. **Hard, controlled**, even effort.
- **primary_adaptations:** VO2max; **rhythm** at **sustained** high aerobic power.
- **systems_stressed:** **Repeated** 3–4 min peaks; mental discipline for **even** pacing.
- **benefits:** **Dense** VO2 time; **clear** progression metric (reps × pace stability).
- **risks:** **Overreach** if weekly quality already high; **first rep** suicide pace.
- **when_to_avoid:** **Injury_return** default—prefer shorter reps or omit; **minimal_sharpen** unless SME micro-dose.
- **n1_selection_notes:** Default **marathon** engine path when not in short-rep branches; strong **peak_fitness** / **race_specific** for appropriate goals. **Ledger:** if **threshold** already **dominant**, consider **shorter** rep variant instead.
- **typical_build_context_tags:** `full_featured_healthy`, `race_specific`, `peak_fitness`, `base_building` (late), `durability_rebuild` (SME-reduced)
- **typical_placement:** Mid-week anchor quality session.
- **pairs_poorly_with:** **Same-day** long MP blocks; **back-to-back** hard quality without easy between.
- **source_notes:** Tier B — classic 1K interval corpus.

---

## `vo2_1200m_10k_race_rhythm`

- **stem:** `intervals`
- **display_name:** VO2 — 1200m at 10K rhythm
- **sme_status:** `draft`
- **volume_family:** `I`
- **definition:** **Longer** repeats at **~10K race rhythm** (engine `10K_pace` label)—**race-specific** VO2 / rhythm work for **10K** goals, **not** generic “interval pace” copy in narrative when this variant is selected.
- **execution:** Warm-up **~2 mi**. Main set: **4–6×1200m** with **~90 s** jog recovery (late **10K** progression / race_specific in `_scale_10k_intervals`). Cool-down **~1 mi**. **Sustainable** hard—reps should **match** ability to **complete** set with quality.
- **primary_adaptations:** **10K** specificity; sustained power; **rhythm** at race-relevant durations.
- **systems_stressed:** High aerobic power **per rep**; **pacing** discipline.
- **benefits:** Bridges **VO2** work to **race cadence** for **10K** athletes.
- **risks:** **Mislabeled** as “interval day” for **marathon-only** athletes—selection must respect **goal distance**.
- **when_to_avoid:** **Marathon-primary** plans without SME cross-goal reason; early build before **short** rep foundation.
- **n1_selection_notes:** **10K** path **late build / race_specific**; ledger should show **progression** through shorter reps first unless athlete history skips safely.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Mid–late mesocycle for **10K**.
- **pairs_poorly_with:** **Redundant** long **tempo-like** work same week—ledger check (threshold saturation).
- **source_notes:** Tier B — race-pace repeat patterns internalized as StrideIQ **10K rhythm** language.

---

## `vo2_5k_peak_1000_development`

- **stem:** `intervals`
- **display_name:** VO2 — 5K peak block (1000m)
- **sme_status:** `draft`
- **volume_family:** `I`
- **definition:** **5K** progression **peak**: **1000m** repeats at **interval** pace—**ceiling** development for **5K** goals (engine late **5K** branch); **not** 10K race-rhythm variant.
- **execution:** Same **segment shape** as **`vo2_1000m_reps_classic`**; **selection** differs by **goal distance = 5K** and **plan phase / week** toward peak. Warm-up **~2 mi**; **4–6×1000m**; **2–3 min** jog; cool-down **~1 mi**.
- **primary_adaptations:** VO2max for **5K**; sustained power at **slightly faster** intent than marathon-default 1K week.
- **systems_stressed:** Same family as classic 1K—**psychological** demand of **5K** peaking.
- **benefits:** **Peak block** density for **5K** athletes hitting top VO2 progression.
- **risks:** Confusion with **marathon** 1K default—matrix must key off **athlete goal distance**, not title alone.
- **when_to_avoid:** Wrong goal distance; **too early** in 5K progression (prefer **400/800** variants first).
- **n1_selection_notes:** Use when **`distance == 5k`** and scaler would select **late** progression; **ledger** coordinates with **threshold** and **easy stride gear**.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Late **5K** build.
- **pairs_poorly_with:** **Duplicate** 1K-heavy weeks without progression intent.
- **source_notes:** Tier B — 5K VO2 peak patterns; **intent** separation from **`vo2_1000m_reps_classic`** for matrix eligibility.

---

## `vo2_conservative_low_dose`

- **stem:** `intervals`
- **display_name:** VO2 — conservative dose
- **sme_status:** `draft`
- **volume_family:** `I`
- **definition:** **Same rep families** as 400/800 variants but **explicitly capped** rep count and **conservative** progression—**return-to-work**, **durability_rebuild**, or **first** VO2 exposure after disruption.
- **execution:** Prefer **400m** or **800m**; **fewer** reps than standard scaler max; generous easy between; **stop** quality if form degrades—narrative must permit **incomplete** set without shame. Exact numbers still **N=1**; engine may need **parameter** override when wired.
- **primary_adaptations:** Reintroduce **VO2** stimulus without **spiking** injury risk.
- **systems_stressed:** Lower **total** hard volume than staple variants.
- **benefits:** **Bridge** back to full VO2 menus.
- **risks:** Athlete **races** the reduced session—still overruns.
- **when_to_avoid:** Acute pain; **illness**; when **complete** omission of VO2 is smarter.
- **n1_selection_notes:** **`injury_return`**, **`durability_rebuild`**, early return from **travel / illness**; pair with **easy stride** rules so end-of-easy touches **don’t** stack redundant **5K gear** same week.
- **typical_build_context_tags:** `injury_return`, `durability_rebuild`, `minimal_sharpen`, `full_featured_healthy`
- **typical_placement:** **Not** adjacent to **race** or **long quality** without SME.
- **pairs_poorly_with:** **Full** **`vo2_peak_fitness_sustained_reps`** same week.
- **source_notes:** Tier A — founder direction (stimulus + recovery consolidation); Tier B — return-to-interval patterns.

---

## `vo2_minimal_sharpen_micro_touch`

- **stem:** `intervals`
- **display_name:** VO2 — minimal sharpen touch
- **sme_status:** `draft`
- **volume_family:** `I`
- **definition:** **Very small** VO2 **dose**—**taper**, **time-crunched**, or **post-illness** window: keep **sharpness** without **meaningful** recovery debt.
- **execution:** Often **400m** or **short** 800m set with **low** rep count; **full** recovery; **optional** skip final rep if legs flat—product truthfulness over completionism.
- **primary_adaptations:** **Maintain** neuromuscular **sharpness**; **touch** VO2 without deep fatigue.
- **systems_stressed:** **Minimal** relative to staple VO2.
- **benefits:** **Compliance** and **confidence** in **compressed** weeks.
- **risks:** Athlete turns micro touch into **hidden** hard day—narrative must stay **honest**.
- **when_to_avoid:** **Peak** week **overload** mistake—this variant is **not** “main load.”
- **n1_selection_notes:** **`minimal_sharpen`**, late taper segments; **ledger** should show **reduced** total quality elsewhere.
- **typical_build_context_tags:** `minimal_sharpen`, `race_specific`, `full_featured_healthy`
- **typical_placement:** **Far** from **A** race or as **last** touch before short goal race—SME-dependent.
- **pairs_poorly_with:** **Heavy** threshold + **heavy** long quality same week.
- **source_notes:** Tier B — low-dose speed maintenance patterns.

---

## `vo2_light_touch_after_threshold_week`

- **stem:** `intervals`
- **display_name:** VO2 — light touch (heavy threshold week)
- **sme_status:** `draft`
- **volume_family:** `I`
- **definition:** When the **weekly ledger** shows **strong threshold / cruise** density, VO2 **presents** as **short reps** (typically **400m**) or **reduced** total **hard time**—**complement**, don’t **duplicate** sustained **threshold-like** stress.
- **execution:** **400m**-biased or **trimmed** rep counts at true **interval** pace; **spacing** from threshold session **≥** easy day unless athlete history supports tighter coupling.
- **primary_adaptations:** **Ceiling** touch without **second** long sustained **moderate-hard** day feel.
- **systems_stressed:** **Lower** per-rep duration than **1K** staples when threshold already loaded.
- **benefits:** Keeps **speed** in the program when **threshold** did the **sustained** work.
- **risks:** Planner **forgets** ledger and ships **1K** stack—**regression** mode.
- **n1_selection_notes:** **Founder example family:** heavy **threshold** week → prefer **short** VO2 or **omit**; pairs with **`easy_pilot_v1.md`** stride **gear** to hit **missing** systems lightly.
- **typical_build_context_tags:** `full_featured_healthy`, `base_building`, `race_specific`, `peak_fitness`
- **typical_placement:** **After** easy day following threshold, not **sandwiched** blind.
- **pairs_poorly_with:** **Unmodified** **`vo2_1000m_reps_classic`** when ledger **threshold-saturated**.
- **source_notes:** Tier A — complementarity with weekly ledger; Tier B — classic coaching load management.

---

## `vo2_peak_fitness_sustained_reps`

- **stem:** `intervals`
- **display_name:** VO2 — sustained reps (peak)
- **sme_status:** `draft`
- **volume_family:** `I`
- **definition:** **Full-expression** VO2 session for **high-tolerance** athletes in **peak_fitness**: **1000m** staples and/or **1200m** **10K** rhythm when goal-appropriate—**not** for **low-tolerance** or **return** windows.
- **execution:** Use **`vo2_1000m_reps_classic`**, **`vo2_5k_peak_1000_development`**, or **`vo2_1200m_10k_race_rhythm`** shapes at **full** allowed rep counts per volume rules; **warm-up / cool-down** non-negotiable.
- **primary_adaptations:** **Maximal** appropriate VO2 **dose** for phase.
- **systems_stressed:** **Highest** interval variant load class in this pilot.
- **benefits:** **Performance** expression when **recovery** supports it.
- **risks:** **Overreach**; **misapplied** to wrong **build_context**—this is a **privilege** variant, not default.
- **when_to_avoid:** **`injury_return`**, **`durability_rebuild`**, **`minimal_sharpen`** (except SME), low sleep / illness flags.
- **n1_selection_notes:** **`peak_fitness`** + strong **fingerprint** tolerance; **ledger** clear of **conflicting** dense quality.
- **typical_build_context_tags:** `peak_fitness`, `race_specific`, `full_featured_healthy`
- **typical_placement:** **Peak** mesocycle blocks.
- **pairs_poorly_with:** **Stacked** unknown-density weeks; **duplicate** VO2 **without** intent.
- **source_notes:** Tier B — peak-interval expression patterns.

---

## Rollup (authoritative `sme_status`)

| `id` | `stem` | `volume_family` | `sme_status` |
|------|--------|-----------------|--------------|
| `vo2_400m_short_reps_development` | `intervals` | `I` | `draft` |
| `vo2_800m_reps_development` | `intervals` | `I` | `draft` |
| `vo2_1000m_reps_classic` | `intervals` | `I` | `draft` |
| `vo2_1200m_10k_race_rhythm` | `intervals` | `I` | `draft` |
| `vo2_5k_peak_1000_development` | `intervals` | `I` | `draft` |
| `vo2_conservative_low_dose` | `intervals` | `I` | `draft` |
| `vo2_minimal_sharpen_micro_touch` | `intervals` | `I` | `draft` |
| `vo2_light_touch_after_threshold_week` | `intervals` | `I` | `draft` |
| `vo2_peak_fitness_sustained_reps` | `intervals` | `I` | `draft` |

**Counts:** 0 approved / 9 draft.

---

*Note: Row count is **9** (one more than the spec’s illustrative “≥8”) to separate **5K peak 1K intent** from **marathon-default 1K** and add **ledger-aware** light-touch variant.*
