# Intervals / VO2 pilot — variant definitions (v1)

**Spec:** `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md` v0.2.21 · **Sequence:** `docs/specs/WORKOUT_FLUENCY_BUILD_SEQUENCE.md`  
**Stems covered:** `intervals` (engine aliases: `interval`, `vo2max` — same dispatch in `workout_scaler.scale_workout`)

**Engine reference:** `apps/api/services/plan_framework/workout_scaler.py` — `_scale_intervals` routes by **goal distance** (`5k`, `10k`, marathon default) and **phase** / **plan_week** / **athlete_ctx** (e.g. high-volume marathon base). Rep lengths **400m → 800m → 1000m** (5K/10K progressions); **1200m @ ~10K race rhythm** in late **10K** paths. **~8%** of weekly volume cap applies to interval prescription in scaler—treat as **engineering guardrail** until registry wiring; N=1 may need stricter caps.

**Engine gaps (founder-supplied, KB ahead of code):** **Pyramid/ladder** sessions, **mile repeats**, and **3×2 mi** (and similar **long-rep**) structures are **not** emitted by `_scale_intervals` today. Rows below capture **intent + selection hooks**; Phase 2 registry + scaler/segment builder must **implement or map** before runtime wiring. Do **not** treat these as live `GeneratedWorkout` shapes until contract tests exist.

**Ledger link:** A scheduled **intervals** session is a **heavy** line item on the **weekly stimulus ledger** (see `easy_pilot_v1.md` **Deterministic selection logic**). It **feeds** end-of-easy **stride gear** choices the same week—avoid redundant “same system twice” without intent.

**SME approval:** **Nine** variant ids are **`sme_status: approved`** — founder SME session **2026-03-20** (pace, complementarity, recovery philosophy) plus **intervals-only / dual-quality / 10K–threshold split** **2026-03-22** (chat, condensed below). **Three** ids (**`vo2_pyramid_ladder_float_recovery`**, **`vo2_mile_repeats`**, **`vo2_3x2mi_long_reps`**) remain **`draft`** — advanced patterns, KB-forward or founder N-of-1 chassis; **explicit promotion** required before shipping slice. Runtime wiring remains gated per spec §2.

**Authoritative status:** Rollup table at file end is **source of truth** for counts (**9** approved / **3** draft).

---

## StrideIQ intervals & weekly structure (SME — product intent, 2026-03-22)

**Threshold vs intervals — complementary, not duplicate**

- **Threshold** (see **`threshold_pilot_v1.md`**) is where much **lactate resistance** and **sustained hard running** live: cruise intervals, continuous T, density with **incomplete** recovery between work bouts. For **10K** and longer goals, threshold is **vital** for **late-race durability** when the race stops feeling “easy.”
- **Intervals / VO2** (this pilot) primarily **raise the ceiling** — turnover, rhythm under discomfort, **5K-class** (calculator **interval**) work so race pace feels **under** the edge of mechanics. **None of it exists in isolation:** long runs (including **progressive** or **fast-finish** when appropriate) carry **specific endurance** and fueling reality that intervals and threshold do not replace.

**Dual-quality week (intervals + threshold + long in the same week)**

- When the week already includes a **threshold** session, **threshold is handling much of the “10K-ish” sustained-hard / lactate rhythm load.** The **interval day** should **not** default to **duplicating** that with **long reps at 10K race rhythm** unless the matrix explicitly selects a **sparse race-rhythm touch** (see **`vo2_1200m_10k_race_rhythm`** — **n1_selection_notes**).
- **Default bias for interval day in dual-quality weeks:** **5K-anchor / calculator interval pace** for **800m–1000m** (and shorter) work — **ceiling** focus while threshold carries **durability**.

**Single-quality week (one structured hard day + long, no threshold)**

- **Default interval anchor:** **calculator interval / VO2** (5K-class stimulus). Do **not** spend the **only** hard day primarily on **10K race-pace long reps** pretending to cover both ceiling and sustained-hard — that is a **different** coaching choice and should be **explicit**, not silent scaler default.

**Intervals-only spine (selector / copy contract — not a single workout id)**

- **One** structured **intervals** quality day **+ long**; athlete may add **strides** or **hill sprints** **1–2×** on other days as **neuromuscular** touch (**`easy_pilot_v1.md`**) — **not** a second VO2 day.
- **Half marathon and longer goals:** if **not** running **two** qualities + long, the **long run** should include **some** specific quality **at least every third week** (progressive, fast finish, MP/HMP blocks per **`long_run_pilot_v1.md`** — exact variant from matrix).
- **Rep distances:** prefer **multiples of 400 m** for **track legibility** (facility + communication) unless a goal-specific exception is SME-intended (e.g. **1K** as standard staple).
- **Build vs routine:** In a **build**, segment shapes should trend **progressive** (shorter → longer reps over time, subject to caps). In **routine / no race on calendar**, **A/B/C/D-style rotation** across weeks is valid for **mental stimulation** while still respecting progression and ledger.
- **Weeks-to-race compression:** **no fixed founder table** — **data + athlete tolerance + ledger** should constrain variant eligibility; until signals are strong, prefer **conservative** choices + **honest disclosure** in copy.
- **Feel over formula:** Schedules **break** (heat, illness, life). Narrative and adaptation paths must allow **skip, shorten, or push** without shame — **honesty** beats completionism.

**Recovery modality (between reps)**

- **N-of-1:** Some athletes **always** walk, **always** jog, or **adapt** (e.g. **jog until you can’t**, then walk — **heat/humidity** often **lengthens** recoveries as a season progresses). The registry should eventually carry **`rest_modality`** (or equivalent) for prescription truth; until wired, copy may describe **“easy jog or easy walk as needed”** when variant is agnostic.
- **Float recovery** (easy jog between ladder pieces) is **not** the same session class as **full** walk recovery — **ledger** and **fatigue cost** differ; do not silently equate.

**Prescribing faster than calculator “interval” pace**

- If the product prescribes **faster than** the calculator **interval** output, the **context** should be **5K race goal** (or explicit short-race block) — **not** the default reading for **10K-primary** athletes. **Copy:** encourage athletes **not to race workouts**; acknowledge many still will — **trust-preserving** tone.

---

## StrideIQ VO2 session intent (SME — product)

**Not threshold, not strides**

- **VO2 / intervals** days are **structured quality**: repeated work bouts with **defined** recovery—not a continuous threshold block, not 15–30 s neuromuscular touches at the end of easy.
- **Controlled hardness:** “Hard but controlled”—**not** all-out sprinting rep 1 and collapsing; mechanics stay **smooth**; last rep **quality**, not desperation, unless SME-intended peaking context.

### Pace from the Training Pace Calculator (same anchor weighting as threshold)

- **Single anchor chain for prescription:** Interval / VO2 paces come from the **Training Pace Calculator** using the **same recent-race anchor rules and priority** as **threshold** (see **`threshold_pilot_v1.md`** — *StrideIQ pace & environment*): best **recent race** within the **last 6 months** — **5K PR** when it qualifies; if not, **1 mile or 10K** (when more than one qualifies, prefer the **shorter** race as calculator input). From that anchor, use the calculator’s **interval / VO2** outputs for session prescription—**do not** silently use a different anchor for intervals than for threshold unless the product defines an explicit, athlete-visible override.
- **Bands:** where the product shows numeric ranges, treat **interval** prescription with the same **±5 seconds per mile** band **philosophy** as threshold (effort + context over split-chasing)—exact UX is product-owned; the **intent** is **banded tolerance**, not a single nail-every-split number.
- **Execution reality:** heat, hills, wind, surface, cumulative fatigue — same **post-hoc and during-run** honesty as threshold pilot themes; naive “you missed pace” without context erodes trust.

**Founder conviction (product why):** Intervals, **chosen intelligently** and **recovered from**, build a **large aerobic engine** and speed **ceiling**; they are **complementary** to **threshold** work, not a substitute. Neglecting threshold can leave **sustained-hard** ability undertrained; addressing threshold alongside intervals is how many athletes **break the next plateau**. (Founder lived experience: a **late-start** return to training with **intervals as a centerpiece** drove a massive jump in fitness; **national-level** results at **masters** age; **threshold** emphasis added later to open **new** ceilings—**N-of-1** illustration, not a promise for every athlete.)

**Volume discipline**

- Scaler enforces an **interval volume fraction** of weekly miles—selection matrix must still ask whether **total** quality density (threshold + VO2 + MP + long quality) fits **this** athlete **this** week.

---

## Cross-cutting selection (all variants below)

- **One primary VO2 day** is common for many non-elite weeks; **two** requires **tolerance + ledger** justification.
- **Dual-quality weeks:** after **threshold** loading, prefer **5K-anchor** interval variants (**800m–1000m**, **`vo2_400m`**) over **default** long **10K-rhythm** reps unless **`vo2_1200m_10k_race_rhythm`** is **explicitly** selected for a **sparse** touch — see **`vo2_light_touch_after_threshold_week`** and **StrideIQ intervals & weekly structure** above.
- After **heavy threshold** loading, prefer **shorter rep** VO2 touches or **spacing** before stacking another dense day—see variant **`vo2_light_touch_after_threshold_week`**.
- **Injury_return** / **minimal_sharpen**: fewer reps, shorter reps, or **suppress** VO2 entirely—variants **`vo2_conservative_low_dose`** and **`vo2_minimal_sharpen_micro_touch`** lean here; **veto** when pain or illness dictates.
- **5K vs 10K vs marathon goal:** engine already branches; variants below **name** those intents for the **matrix** even when segment shapes overlap.
- **Ladders / mile / 2 mi:** when selected, **ledger** must account for **high** neuromuscular + metabolic load—often **replace or trim** other VO2 that week unless tolerance is proven. **Founder personal progression** (e.g. very high-volume **400 → 800 → K → 1200 → mile** ladders with tight rest progression) is **illustrative** and **not** the default population prescription — see **`vo2_mile_repeats`** / advanced **`draft`** rows.

---

## `vo2_400m_short_reps_development`

- **stem:** `intervals`
- **display_name:** VO2 — short repeats (400m)
- **sme_status:** `approved`
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
- **sme_status:** `approved`
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
- **sme_status:** `approved`
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
- **sme_status:** `approved`
- **volume_family:** `I`
- **definition:** **Longer** repeats at **~10K race rhythm** (engine `10K_pace` label)—**race-specific** VO2 / rhythm work for **10K** goals, **not** generic “interval pace” copy in narrative when this variant is selected. **Occasional / sparse** use is appropriate to **feel** race rhythm; it is **not** the automatic default end state for every **10K** athlete every late week—especially when **threshold** already carries sustained-hard load (**StrideIQ intervals & weekly structure**).
- **execution:** Warm-up **~2 mi**. Main set: **4–6×1200m** with **~90 s** jog recovery (late **10K** progression / race_specific in `_scale_10k_intervals`). Cool-down **~1 mi**. **Sustainable** hard—reps should **match** ability to **complete** set with quality.
- **primary_adaptations:** **10K** specificity; sustained power; **rhythm** at race-relevant durations.
- **systems_stressed:** High aerobic power **per rep**; **pacing** discipline.
- **benefits:** Bridges **VO2** work to **race cadence** for **10K** athletes.
- **risks:** **Mislabeled** as “interval day” for **marathon-only** athletes—selection must respect **goal distance**. **Duplicate stimulus** with **dense threshold** same week if selected **by rote** without ledger.
- **when_to_avoid:** **Marathon-primary** plans without SME cross-goal reason; early build before **short** rep foundation. **Single-quality weeks** where **interval day** should prioritize **ceiling** (**5K-anchor** reps) unless athlete explicitly wants race-rhythm emphasis.
- **n1_selection_notes:** **10K** path **late build / race_specific**; ledger should show **progression** through shorter reps first unless athlete history skips safely. **If weekly ledger includes a full threshold session**, **down-rank** this variant vs **`vo2_800m_reps_development`** / **`vo2_1000m_reps_classic`** at **interval** pace unless SME or athlete intent requests a **race-rhythm touch**.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`
- **typical_placement:** Mid–late mesocycle for **10K**.
- **pairs_poorly_with:** **Redundant** long **tempo-like** work same week—ledger check (threshold saturation).
- **source_notes:** Tier B — race-pace repeat patterns internalized as StrideIQ **10K rhythm** language.

---

## `vo2_5k_peak_1000_development`

- **stem:** `intervals`
- **display_name:** VO2 — 5K peak block (1000m)
- **sme_status:** `approved`
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
- **sme_status:** `approved`
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
- **sme_status:** `approved`
- **volume_family:** `I`
- **definition:** **Very small** VO2 **dose**—**taper**, **time-crunched**, or **post-illness** window: keep **sharpness** without **meaningful** recovery debt.
- **execution:** Often **400m** or **short** 800m set with **low** rep count; **full** recovery; **optional** skip final rep if legs flat—product truthfulness over completionism. **Taper alternatives (SME):** some athletes prefer **strides only** in race week; others **2–3 × ~400m at ~5K feel** on the **roads** (fartlek-style) to **touch the system** and stay **fresh**—matrix may substitute **neuromuscular** touch (**`easy_pilot_v1.md`**) when a full interval variant is too heavy.
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
- **sme_status:** `approved`
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
- **sme_status:** `approved`
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

## `vo2_pyramid_ladder_float_recovery`

- **stem:** `intervals`
- **display_name:** VO2 — pyramid ladder (float recovery)
- **sme_status:** `draft` *(promotion pending — complex session; engine not implemented)*
- **volume_family:** `I`
- **definition:** **Pyramid ladder** at **interval / VO2** effort: rep distances **ascend then descend** with **easy float** recovery between pieces—founder exemplar **400m → 800m → 1200m → 1 mile → 1200m → 800m → 400m**, **~400m float** (easy jog) between each work piece. **Not** threshold cruise intervals; **not** a single continuous tempo.
- **execution:** Full warm-up easy; ladder as prescribed; **floats** stay **true easy**—if floats become “moderate,” the session is mis-executed. Cool-down easy. **Rep paces** from calculator **interval** zone (banded); last reps **quality**, not sprint-collapse. **Engine:** *not implemented* in `workout_scaler` — requires **ordered multi-segment** prescription in a future builder.
- **primary_adaptations:** VO2 **touch** across **multiple** rep lengths in one session; rhythm and **gear-change** literacy; neuromuscular variety.
- **systems_stressed:** **High** session load—psychological + metabolic; cumulative fatigue **late** in pyramid.
- **benefits:** **One session** samples **several** time-at-intensity boxes; engaging for athletes who tolerate complexity.
- **risks:** **Overreach** vs weekly ledger; **racing** early reps; floats too fast; **inappropriate** for low-tolerance or **injury_return** without SME strip-down.
- **when_to_avoid:** **`injury_return`**, **`minimal_sharpen`** (full ladder), early relationship with VO2 unless shortened ladder; weeks already **dense** in **reps** or **threshold_intervals**.
- **n1_selection_notes:** **Ledger-heavy**—often **the** VO2 anchor that week; pair with **easy stride gear** that **does not** duplicate **5K rep** stimulus if ladder already **fast-short** heavy.
- **typical_build_context_tags:** `peak_fitness`, `race_specific`, `full_featured_healthy`, `base_building` (shortened ladder + SME)
- **typical_placement:** Mid-week quality; **spacing** from long-run **MP** quality.
- **pairs_poorly_with:** Second **complex** VO2 or **dense threshold** without recovery narrative.
- **source_notes:** Tier A — founder pattern **2026-03-20** session family; Tier B — pyramid ladder exists widely in coaching practice—StrideIQ id is **this** structure + float rule.

---

## `vo2_mile_repeats`

- **stem:** `intervals`
- **display_name:** VO2 — mile repeats
- **sme_status:** `draft` *(promotion pending — advanced density; **not** default for most; founder personal high-volume progressions use similar shapes but are **N-of-1**)*
- **volume_family:** `I`
- **definition:** **Repeated miles** at **interval / VO2** (or goal-appropriate **hard aerobic power**) with **defined** jog or time recovery—classic **density** session for athletes who tolerate **longer** reps than 400–800m work. **Psychological alternatives** (e.g. **2×2 mi** or **3×1 mi** vs **4×1 mi**) are **N-of-1** coaching choices, not universal scaler rules.
- **execution:** Warm-up easy; **N × 1 mile** at prescribed pace band (calculator **interval** or SME-prescribed surrogate); recovery **easy jog** or **standing / walk** per protocol—**full enough** that **last** rep matches intent. Cool-down easy. **Rep count** N-of-1 (often **3–6** range illustrative). **Engine:** *not implemented* as explicit **mile** prescription in `_scale_intervals` (nearest shapes are **1000m / 1200m**)—future scaler or segment template should emit **1609m** (or mile) explicitly.
- **primary_adaptations:** Sustained VO2 **per rep**; **pacing** discipline at **race-relevant** duration for some goals.
- **systems_stressed:** **High** per-rep cardiovascular load; eccentric / mechanical if **downhill** bias.
- **benefits:** **Clear** progression metric (reps @ stability); bridges toward **10K–half** specificity when pace is appropriate.
- **risks:** **First rep** suicide; **under-recovery** between miles; masking **threshold** mislabeled as VO2.
- **when_to_avoid:** **`injury_return`**; athletes without **even-split** discipline; same week as **1200m race-rhythm** overload for **10K** without rationale.
- **n1_selection_notes:** **Ledger** coordinates with **`vo2_1000m_reps_classic`**—avoid **redundant** “long rep” days; **marathon-primary** athletes may use **sparingly** vs **MP** long work.
- **typical_build_context_tags:** `race_specific`, `peak_fitness`, `full_featured_healthy`, `base_building` (reduced N + SME)
- **typical_placement:** Mid-week anchor.
- **pairs_poorly_with:** **`vo2_peak_fitness_sustained_reps`** **stacked** blindly same week.
- **source_notes:** Tier B — mile repeat session family; StrideIQ **numeric** surfaces should prefer **calculator bands** over single split targets.

---

## `vo2_3x2mi_long_reps`

- **stem:** `intervals`
- **display_name:** VO2 — 3 × 2 mile (long reps)
- **sme_status:** `draft` *(promotion pending — **very** high load; founder-mentioned pattern; engine not implemented)*
- **volume_family:** `I`
- **definition:** **Three** work segments of **2 miles** each at **prescribed** quality pace—**sustained power** session. Pace may sit **between** classic **threshold** and **VO2** depending on athlete and phase (selector must **not** silently call it “easy”); this row is **interval stem** for **registry / matrix** when the **main set** is **repeated long reps** with **recovery** between.
- **execution:** Warm-up easy; **3 × 2 mi** with **recovery** (e.g. **800m–1 mi** easy jog or **3–5 min**) between—exact recovery **N=1**. Cool-down easy. **Engine:** *not implemented* in `workout_scaler`; requires **custom segments** and **strict** cap vs weekly volume + **threshold** ledger.
- **primary_adaptations:** **Sustained** aerobic power; **mental** durability for **long** hard segments.
- **systems_stressed:** **Very high** session load—glycogen, mechanical fatigue.
- **benefits:** **Race-specific** strength for **half / marathon** athletes in **specific** blocks when SME-intended—not a default **5K** tool.
- **risks:** **Massive** overload if combined with **MP long** or **dense threshold**; **pace drift** rep-to-rep.
- **when_to_avoid:** **`injury_return`**, **`minimal_sharpen`**, low-mileage athletes without **long rep** history.
- **n1_selection_notes:** **`peak_fitness`**, **`race_specific`** for **high-tolerance** profiles; **one** such session may **dominate** the week’s **quality** budget.
- **typical_build_context_tags:** `peak_fitness`, `race_specific`, `full_featured_healthy`
- **typical_placement:** **Specific** mesocycle; **never** adjacent to **unplanned** second **long quality** day.
- **pairs_poorly_with:** **`long_mp_over_under_alternating_miles`** same week without explicit SME (both are **heavy MP-adjacent** stress families).
- **source_notes:** Tier A — founder “**3 × 2 mile**” mention **2026-03-20** family; Tier B — pace labeling must stay honest vs **threshold** pilot variants.

---

## Rollup (authoritative `sme_status`)

| `id` | `stem` | `volume_family` | `sme_status` |
|------|--------|-----------------|--------------|
| `vo2_400m_short_reps_development` | `intervals` | `I` | `approved` |
| `vo2_800m_reps_development` | `intervals` | `I` | `approved` |
| `vo2_1000m_reps_classic` | `intervals` | `I` | `approved` |
| `vo2_1200m_10k_race_rhythm` | `intervals` | `I` | `approved` |
| `vo2_5k_peak_1000_development` | `intervals` | `I` | `approved` |
| `vo2_conservative_low_dose` | `intervals` | `I` | `approved` |
| `vo2_minimal_sharpen_micro_touch` | `intervals` | `I` | `approved` |
| `vo2_light_touch_after_threshold_week` | `intervals` | `I` | `approved` |
| `vo2_peak_fitness_sustained_reps` | `intervals` | `I` | `approved` |
| `vo2_pyramid_ladder_float_recovery` | `intervals` | `I` | `draft` |
| `vo2_mile_repeats` | `intervals` | `I` | `draft` |
| `vo2_3x2mi_long_reps` | `intervals` | `I` | `draft` |

**Counts:** **9** approved / **3** draft.

---

*Notes: **9** approved rows align with current `_scale_intervals` shapes (plus matrix intent). **3** **`draft`** rows (ladder, mile repeats, 3×2 mi) are **KB-forward** or **advanced N-of-1** until scaler/segments exist and founder promotes. **2026-03-22:** intervals pilot brought to parity with threshold / long / easy pilots for **weekly complementarity**, **intervals-only spine**, **recovery modality philosophy**, and **taper touch options**.*
