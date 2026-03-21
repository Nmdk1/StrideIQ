# Workout Fluency Registry — Specification v0.2.16

**Status:** Draft — **builder-safe for pilot KB work**; production wiring remains gated (see §2).  
**Date:** 2026-03-20  
**Purpose:** Define a **shared vocabulary** of run types and variants (what they are, how they’re used, when they’re inappropriate) so plan generation can eventually apply **N=1 history and fingerprint** without inventing physiology or relying on opaque code-only logic.

**Companion (recovery / gates):** `docs/specs/PLAN_GENERATION_VISION_ALIGNMENT_RECOVERY_SPEC.md` — P0 plan acceptability and athlete-truth continuity. **This spec** addresses **definitions + intent of workout tools**; together they reduce “safe but wrong-for-athlete” plans.

---

## 1. Roles

| Role | Responsibility |
|------|----------------|
| **Founder (SME)** | Coaching truth, source boundaries, veto on claims, exemplar narratives, final approval of closed enums (`build_context_tag`, `sme_status`). |
| **Builder agents** | Schema, file locations, registry format, linkage to `plan_framework`, tests, phased rollout, evidence. |

The founder does **not** need to choose YAML vs Markdown tables; agents recommend. The founder **does** approve whether a **claim** belongs in the product KB.

**Process note:** Specs and completion reports are expected to pass **technical advisor review** (and often additional advisors). Agents should treat advisor deltas as **required edits** unless the founder explicitly overrides.

---

## 2. Execution gate (dependency on P0 plan reliability)

**P0 plan acceptability** is defined by `docs/specs/PLAN_GENERATION_VISION_ALIGNMENT_RECOVERY_SPEC.md` (recovery contracts, athlete-truth continuity, endpoint-level invariants). Until that spec’s **pass/fail acceptance** is green for the relevant generation paths (at minimum: constraint-aware plan generation and starter flows referenced there), the following **must not** ship to production:

- Machine registry loaders, scaler/phase dispatch keyed on `workout_variant_id`, or any new **runtime** branch that selects workouts from this registry.

**Allowed before P0 is green (does not relax P0 itself):**

- SME-reviewed **KB-only** variant prose under `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/` (threshold pilot first — §8).
- Spec, indexes, and **offline** contract tests that **do not** change production generation behavior.

**Hard rule:** No **broad ontology expansion into runtime** (new consumer paths, automatic variant selection in `workout_scaler` / `phase_builder`) unless the **P0 plan acceptability gate** for those paths is green or the founder documents an **explicit, scoped waiver** for a single PR.

### 2.1 Enforcement (CI + PR template)

**Operational checklist:** `docs/specs/WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md` — copy/paste PR body tokens, `sme_status` promotion rules, reviewer expectations.

**CI guard:** On pull requests, if the diff touches `apps/api/services/plan_framework/**` or `apps/api/routers/plan_generation.py`, workflow job **`p0-plan-registry-gate`** runs `.github/scripts/ci_p0_registry_gate.py` and **fails** unless the PR description includes `P0-GATE: GREEN` or `P0-GATE: WAIVER` with a non-empty `P0-WAIVER-REF:` line. This does not replace human review; it prevents silent runtime changes without attestation.

**CI scope (critical):** The script checks **only that the attestation tokens are present** in the PR body. It does **not** verify that `GREEN` is factually justified, that recovery-spec acceptance is met, or that a `WAIVER` is legitimate — that remains **author + reviewer + founder** responsibility. Do not treat CI green on this job as substantive P0 validation.

**SME promotion:** Who may set `sme_status: approved` and how PRs must record it — **same** checklist doc (§3).

---

## 3. Problem statement

StrideIQ already encodes **volume limits**, **phase shapes**, and **much taxonomy** in the knowledge base and in `plan_validation_helpers.py`. What is still weak:

1. **Per-variant depth** — Same string `workout_type` can mean different prescriptions; **continuous threshold** vs **cruise intervals** vs **progressive threshold** need **explicit** execution, intent, and contraindicates. (Colloquial **“tempo”** is **not** StrideIQ vocabulary—see §4.2.)
2. **“Why here, why now”** — Sequencing is partly in `PhaseBuilder` / `WorkoutScaler` but **not** surfaced as a portable, inspectable rationale layer tied to named variants.
3. **Distance-as-weak-axis** — Race distance must **not** be the primary selector for volume or long-run architecture; **athlete state** (durability rebuild, injury return, high-volume 5K/10K racer, etc.) must drive eligible variants within safety caps.

**Wiring** into generation is a **separate phase** with its own acceptance tests and **§2 gate**.

---

## 4. Design principles (non-negotiable)

1. **Athlete decides; system informs.** The registry describes tools and typical use; it does not override the athlete.
2. **N=1 over population templates.** Population norms are cold-start or disclosure-labeled defaults only.
3. **Suppression over hallucination.** If the registry (or history) doesn’t support a claim, the system does not fabricate “why.”
4. **Information over celebrity.** Provenance is for **audit**; the bar for inclusion is **accurate, usable definition** vetted by SME—not fame alone.
5. **Distance is not a straitjacket.** Within physiological reason and individual tolerance, the same race distance may pair with **very different** weekly architectures. The registry encodes **variant eligibility signals** via **`build_context_tag`** (closed enum + precedence — §6.3), not “10K = never long.”
6. **Corpus, not cult — synthesis owns the product.** Licensed extracts, published endurance literature, and internal research are **raw material**. What ships in StrideIQ is **so transformed** (N=1, engine, safety, voice) that **third-party programs do not merit public credit**—like citing who explained breathing every time a runner inhales. **N=1 history, injury constraints, and athlete intent outrank population templates** when they conflict. SME veto still applies to any claim.

### 4.1 Source admissibility (agent-executable)

**Ranked tiers (highest admissibility first):** Tiers judge **evidence quality for internal QA**, not **marketing attribution**.

| Tier | Admissible as | Examples / notes |
|------|----------------|------------------|
| **A** | Primary physiological or prescription claim | SME-written text; or SME-approved paraphrase **tracked internally** (corpus / license record)—**not** surfaced to athletes as “from [person/book].” |
| **B** | Primary claim when backed | Established endurance-training literature, licensed internal extracts, or structured coaching corpus **referenced by internal catalog / tier in builder docs only**—see §4.4. |
| **C** | Supporting context only (not sole basis for a claim) | Peer-reviewed physiology or consensus exercise science, cited **without** turning product copy into a bibliography. |

**Explicit disallow (must not be sole or primary support for a claim):**

- Anonymous or unverifiable blogs, social posts, and forum threads.
- “Copy-template” plans scraped from the web without SME review.
- LLM-generated definitions or citations **without** SME `sme_status: approved`.
- Vague attributions (“coaches say…”) with no checkable basis.
- **Public** name-drops of coaches, books, or commercial programs in athlete-facing strings (§4.4).

**SME veto remains final** for any external claim at any tier.

### 4.4 No public attribution (coaches, books, brands)

- **Athlete-facing copy, registry `display_name`, plan narratives, and API fields intended for the user** must **not** credit or name third-party coaches, books, trademarks, or training “systems.” StrideIQ presents **its own** coaching voice and logic.
- **`source_notes` in KB markdown** should record **Tier** (A/B/C) and, when needed for compliance, **internal corpus reference ids**—**not** proper-name attribution (e.g. “Tier B — licensed endurance corpus; ref internal KB catalog”).
- **Legal / licensing** records live **outside** user-visible surfaces (e.g. internal acquisition logs, contracts)—not in workout titles or push notifications.
- **§5 artifacts** under `coaches/source_*` remain **builder inputs**; they are not an instruction to **quote** those labels to athletes.

### 4.2 Product vocabulary — threshold family (SME)

- **Do not use “tempo”** as a defined pace, session label, or athlete-facing term. It is not a single physiological anchor; treat it as absent from product copy and registry **display names**.
- **Threshold** vs **critical velocity / steady-state** (and related labels in historical vs modern texts) are **distinct** constructs—do not conflate. Examples here illustrate **lineage** for disambiguation, not an exclusive list of authorities (principle **#6**, §4.3).
- **Implementation note:** Legacy code may still accept a historical `tempo` string as an alias for continuous threshold work; that is **backward compatibility only**, not permission to emit “tempo” in UX or KB. Canonical stems remain **`threshold`** and **`threshold_intervals`**.

### 4.3 N=1 vs population coaching systems (product stance)

- **StrideIQ default is N=1:** history, fingerprints, constraints, and athlete choice—not “this week because a book’s template says so.”
- **Published systems** (classic or modern) supply **language, typical progressions, and starting caps** for cold start and disclosure; they are **not** the only correct mapping for a real athlete.
- **Deep research** (internal or routed external agent) should **broaden** evidence to **current** coaching practice and physiology—then **SME** decides what enters the registry.
- **Founder SME** is **veto and product boundary**, not the **sole** source of training wisdom.

---

## 5. Relationship to existing artifacts

| Artifact | Role |
|----------|------|
| `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/WORKOUT_LIBRARY.md` | Breadth taxonomy — **input** to stem/variant IDs. |
| `_AI_CONTEXT_/KNOWLEDGE_BASE/coaches/source_B/WORKOUT_DEFINITIONS.md` | E/M/T/I/R families — **input** for physiology and caps language. |
| `_AI_CONTEXT_/KNOWLEDGE_BASE/PLAN_GENERATION_FRAMEWORK.md` | Phase and weekly structure rules — **sequencing context** for variants. |
| `_AI_CONTEXT_/KNOWLEDGE_BASE/00_GOVERNING_PRINCIPLE.md` | Athlete-first — **overrides** generic book text when they conflict. |
| `apps/api/services/plan_framework/workout_scaler.py` | Today’s **prescription** logic — must **map** to registry IDs when wired (see §10). |
| `apps/api/services/plan_framework/phase_builder.py` | Phase eligibility — must **align** with variant fields when wired. |
| `apps/api/services/athlete_plan_profile.py` | N=1 volume/long-run/cutback — **future consumer** of variant eligibility when wired. |
| `apps/api/tests/plan_validation_helpers.py` | Structural validation — **complements** registry (does not replace deep definitions). |

**Note:** `02_PERIODIZATION.md` is largely stubbed; until filled, **do not** treat it as authoritative for variant placement—use `PLAN_GENERATION_FRAMEWORK.md` + this registry + SME.

---

## 6. Core concepts

### 6.1 Stem (`workout_stem`)

A **stable** canonical name aligned with existing engine types where possible (e.g. `easy`, `long`, `threshold_intervals`, `long_mp`, `intervals`, `repetitions`, `strides`, `hills`). Stems may map 1:many to **variants**.

### 6.2 Variant (`workout_variant_id`)

A **specific** prescription pattern: same stem, different structure or intent.

Examples (illustrative, not exhaustive):

| `workout_variant_id` | Stem | Distinction |
|---------------------|------|-------------|
| `threshold_continuous_progressive` | threshold | Staple continuous threshold, periodized |
| `cruise_intervals_classic` | threshold_intervals | Repeats at T with short jog |
| `progressive_threshold_25_40` | threshold | Within-run progression toward T |
| `long_easy_aerobic` | long | Easy aerobic long |
| `long_progression_finish` | long | Easy bulk + moderate finish |
| `mp_blocks_in_long` | long_mp | MP segments inside long run |
| `vo2_short_reps_200_400` | intervals | Short reps, neuromuscular + VO2 touch |
| `vo2_long_reps_1k_2mi` | intervals | Longer reps at ~5K–10K effort |

### 6.3 Build context (`build_context_tag`) — **closed enum**

This field drives **athlete-state-first** variant eligibility. **Only** the following values are valid in variant docs and (later) the machine registry. **Do not** invent new tags in pilot files; propose additions via spec revision + SME sign-off.

| Tag | Meaning (selection intent) |
|-----|----------------------------|
| `injury_return` | Return-to-structure after layoff or injury-cautious window; minimal sharp density; transparency over ambition. |
| `durability_rebuild` | Rebuilding tissue/tolerance; conservative intensity density; easy volume and long runs within tolerance. |
| `minimal_sharpen` | Deliberately **low** density of quality (taper, time-crunched sharp block, or post-illness limited window)—not synonymous with full race-specific blocks. |
| `base_building` | Aerobic engine emphasis; race-specific work secondary. |
| `race_specific` | Goal-pace rhythm, specificity, or race-pace-adjacent work appropriate to the mesocycle. |
| `peak_fitness` | High-tolerance athlete in a **peak** block; full intensity menu available within caps. |
| `full_featured_healthy` | Default **healthy, balanced** week: mix of easy, long, threshold/intervals appropriate to phase—no special conservative or peak override. |

**Deprecated informal labels (v0.1 draft text — do not use in new files):**

| Old label | Replace with |
|-----------|----------------|
| `aerobic_engine` | `base_building` |
| `race_specific_sharpen` | `race_specific` |
| `injury_return_minimal` | `injury_return` (severity lives in athlete profile / constraints, not a second tag) |
| `balanced_all_systems` | `full_featured_healthy` |

#### 6.3.1 Precedence and conflicts

At selection time the engine (when wired) resolves **at most one primary `build_context_tag`** per decision point from athlete profile + phase + explicit constraints. **Multiple signals** may be true; **precedence picks the primary** so implementation does not diverge by agent.

**Rule — conservative wins:** Evaluate conditions in the order below; **first match** becomes the primary tag.

| Order | Tag | Typical winning condition (illustrative — exact signals TBD at wiring) |
|-------|-----|------------------------------------------------------------------------|
| 1 | `injury_return` | Injury-return or medically cautious constraint active |
| 2 | `durability_rebuild` | Explicit rebuild / low-tolerance durability emphasis (and not superseded by 1 — 1 always wins) |
| 3 | `minimal_sharpen` | Taper or explicit minimal-quality-density window |
| 4 | `race_specific` | Race-specific mesocycle **and** none of 1–3 apply |
| 5 | `peak_fitness` | Peak block with high tolerance **and** none of 1–4 apply |
| 6 | `base_building` | General aerobic build **and** none of 1–5 apply |
| 7 | `full_featured_healthy` | Fallback healthy default |

**Non-primary tags:** Variant docs may list **multiple** tags in `typical_placement` / eligibility to mean “commonly used in these contexts.” **Primary resolution** for generation uses the table above only. If a variant lists `race_specific` but primary is `injury_return`, that variant is **ineligible** unless the variant explicitly allows override (future field — not in threshold Pilot 1 KB).

### 6.4 Founder exemplars (documentation only)

The following **illustrate** constraint diversity for **one** athlete; they are **not** universal rules:

- **High-volume 10K-oriented block:** Peak **70+ mpw**; long runs **15–18 mi**; sometimes **multiple** long-ish days in a week when rebuilding durability post-injury; primary quality may be **intervals** from short reps through **~2 mi** at ~5K effort, plus **threshold** progressions (~25–40 min), strides, hills—**when healthy and tolerating load**.
- **Minimal marathon sharpen post-injury:** Mostly **easy** miles; **one** ~10 mi day faster than marathon pace; **one** ~63 mi week; **one** ~20 mi long run; **~2 weeks** pain-free before race—still executed competitively (e.g. AG result, BQ).
- **Long structured build (high adherence to a fixed template):** High compliance with a rigid published schedule can yield strong performances **or** contribute to injury risk depending on individual response—registry should describe **risk factors** (sudden jumps, monolithic templates) without treating any template as law.

Agents must **not** copy these as defaults for all users; they inform **tags** and **SME review** of risk fields.

---

## 7. Schema: required fields per variant (v0.2.16)

### 7.0 Consumption model (deterministic plan construction)

Pilot markdown in `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/` is an **interim carrier**. The **canonical consumer** is **code**: eligibility rules, phase/scaler dispatch, and **contract tests** that pin outputs for fixture athletes. Founders and SMEs **author** truth here; they are **not** the runtime audience. Edit guidance:

- Prefer **stable, enumerable signals** (`typical_build_context_tags`, explicit **`when_to_avoid`** / **`pairs_poorly_with`** hints, clear **`stem`**) over essay-only nuance that cannot become registry fields.
- **`display_name`** and athlete-visible strings are **human product copy**; other fields should read as **machine-ingestible spec** (still plain language—no obfuscation—just **unambiguous** for compilation).
- Phase 2 **compiles** this content into a validated artifact (§8); Phase 3 **wires** consumers—§2 gate unchanged.

Each `workout_variant_id` MUST have the following (prose in KB; structured row in machine registry when introduced).

**Advisor shorthand → schema column (same content):**

| Advisor / doc shorthand | Schema field in this spec |
|-------------------------|---------------------------|
| `what` | `definition` |
| `how` | `execution` |
| `benefits` | `benefits` |
| `risks` | `risks` |
| `systems` | `systems_stressed` |
| `when_not` | `when_to_avoid` |
| `n1_selection` | `n1_selection_notes` (when to prefer / avoid for N=1 — pilot may use bullet list) |
| `build_context_tag` | Declared via `typical_build_context_tags` (list of **enum** values from §6.3) |
| `sources` | `source_notes` (and tier per §4.1) |
| `sme_status` | `sme_status` (enum below) |

| Field | Description |
|-------|-------------|
| `id` | Stable snake_case identifier; **globally unique** in registry. |
| `stem` | Parent stem. |
| `display_name` | Athlete-facing short name. |
| `definition` | What the session **is** in one tight paragraph—**selection / eligibility context** for the matrix as well as human summary. |
| `execution` | How to run it (warmup, main set, cooldown, terrain notes)—**dispatch and validation** hooks as Phase 2+ harden. |
| `primary_adaptations` | Physiological targets (aerobic, lactate clearance, VO2, neuromuscular, economy, durability). |
| `systems_stressed` | Cardiovascular, musculoskeletal, CNS load, metabolic—plain language. |
| `benefits` | Why a coach might assign it—**conditional** on appropriate load. |
| `risks` | Overuse, spike injury, glycogen depletion, masters recovery, etc. |
| `when_to_avoid` | Fatigue markers, injury flags, low data confidence, heat, return-to-run—**signals**, not diagnoses. |
| `n1_selection_notes` | Plain-language **when this variant is a strong vs weak fit** for N=1 (optional in very early drafts, required before `sme_status: approved`). |
| `typical_build_context_tags` | Non-empty list of tags from **§6.3 only** where this variant is appropriate. |
| `typical_placement` | Phases / week roles (prose) — complements tags. |
| `pairs_poorly_with` | e.g. heavy VO2 day after maximal long; same-day race; etc. |
| `volume_family` | **Enum:** `E`, `M`, `T`, `I`, `R`, `long`, `composite` (Source B–aligned). |
| `source_notes` | Tier + internal reference per §4.1 / §4.4; **no** third-party **names** in user-surfaced strings. Empty only if SME-original. |
| `sme_status` | **Enum:** `draft` \| `approved` \| `vetoed`. Optional later: `deprecated` for registry rows. **Only `approved` variants may be consumed by production wiring or shipping contract tests.** |

### 7.1 Validation contract (machine registry and CI — when introduced)

Registry artifacts MUST be validated by automated checks (tests or schema):

- Every `id` is **unique**; `stem` + `id` pairing stable across versions (deprecate, don’t reuse IDs).
- For any row with `sme_status: approved`: **no empty** `definition`, `execution`, `benefits`, `risks`, `systems_stressed`, `when_to_avoid`, `typical_build_context_tags`, `volume_family`.
- `typical_build_context_tags` ⊆ allowed set in §6.3.
- `volume_family` ∈ allowed enum above.
- **Integrity:** each `stem` maps to a known engine stem used in `workout_scaler.py` dispatch (or documented exception list).

**Optional v0.3+**

- `n1_signals` — Structured fingerprint hints for up/down-rank.
- `pace_reference` — Tie to `PaceEngine` zones when wired.

---

## 8. Machine registry (phase 2 — format TBD)

**v0.2.16 KB pilot delivers:** Threshold variant markdown **SME-approved**; long-family **`long_run_pilot_v1.md`**: **8**× **`approved`**. **Pilot 3** **`easy_pilot_v1.md`**: **4** variants (`easy`, `recovery`, `easy_strides`, `rest`) — **all** **`sme_status: approved`** (founder SME **2026-03-20**; see file rollup). **§7.0** — KB prose is input to **deterministic** plan construction. **Remaining v1 stems** (VO2 / intervals primary track, deferred reps-strides-hills per build sequence) — **not** complete until those pilots exist and SME-**approve** per founder scope **before** Phase 3 wiring.

**v0.3+ delivers:** Single validated artifact (`workout_registry.yaml` or JSON) with schema version, consumed by tests first, then optionally by Python loader — **subject to §2**.

**Rule:** No production dependency on the registry until **contract tests** pin a subset of variants to expected `GeneratedWorkout` shapes (or explicit “suppressed” outcomes).

---

## 9. Pilot scope (**default: threshold first**)

**Pilot 1 (default, highest leverage):** **Threshold** stems and variants — **`threshold`**, **`threshold_intervals`**. Legacy code may still map a historical **`tempo`** input string to continuous threshold work (**§4.2**); product language does **not** use “tempo.” Target **≥8** approved variant rows (can span multiple markdown files).

**Pilot 2 (second):** **Long run** variants (easy, progression, MP-embedded)—after Pilot 1 SME-approved baseline. **KB:** `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/long_run_pilot_v1.md` (**8** variants, **all** **`sme_status: approved`** founder SME **2026-03-20** / **2026-03-22**). Future edits: **do not** infer promotion—explicit founder sign-off per `id`.

**Pilot 3 (third):** **Easy family** — **`easy`** (incl. legacy **`easy_run`** alias), **`recovery`**, **`easy_strides`**, **`rest`**. **KB:** `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/easy_pilot_v1.md` (**4** variants, **all** **`sme_status: approved`** founder SME **2026-03-20**). Future edits: **do not** infer promotion—explicit founder sign-off per `id`.

**Build sequencing:** `docs/specs/WORKOUT_FLUENCY_BUILD_SEQUENCE.md` — **define all (in scope) → build tools (registry, validators, tests) → wire runtime** (§2 / P0).

**Defer:** Full **R** and **hill** microvariants until Pilot 1–2 stable.

---

## 10. Acceptance criteria (v0.2.16 doc + KB pilot)

- [x] Founder confirms **`build_context_tag` enum** (§6.3) as used in Pilot 1 — **2026-03-22** (implicit in approval of tagged pilot content).
- [x] Founder confirms **`sme_status` enum** and rule: only **`approved`** in any shipping wiring path — **2026-03-22**.
- [x] Founder confirms **source policy** (§4.1) as applied in Pilot 1 — **2026-03-22**.
- [x] Agents add **Pilot 1** threshold variant docs (≥8 variants), each tagged with §6.3 values and `sme_status` on every variant — see `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/threshold_pilot_v1.md` (**9** variants, **`approved`** founder SME **2026-03-22**).
- [x] Agents maintain **Pilot 2** long-family variant docs (8 variants), each tagged with §6.3 values and `sme_status` on every variant — see `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/long_run_pilot_v1.md` (**all 8** **`approved`** — **`long_easy_aerobic_staple`** **2026-03-20**; remaining **seven** **2026-03-22**; rollup in that file).
- [x] Founder SME **explicitly approves** all Pilot 2 rows — **2026-03-22** (batch promotion of seven ids; do not infer for **other** pilots).
- [x] Agents add **Pilot 3** easy-family variant docs — `easy_pilot_v1.md` (**4** variants: `easy`, `recovery`, `easy_strides`, `rest`; each with `sme_status` on every variant).
- [x] Founder SME **approves** all Pilot 3 rows — **2026-03-20** (batch approval of four ids; do not infer for **other** pilots).
- [x] Cross-links from `WORKOUT_LIBRARY.md` to variant docs (index + authority note—no mass rewrite).
- [x] **§2 execution gate** operationalized: PR checklist (`WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md`) + CI job `p0-plan-registry-gate` (see §2.1).
- [ ] Authors of **runtime** PRs still must paste **`P0-GATE:`** attestation in the PR body when CI applies (human process; CI enforces presence only).

---

## 11. Acceptance criteria (wiring phase — beyond v0.2.16 KB)

- [ ] **Mapping table** checked in: registry `id` → current `workout_type` strings (and aliases) as accepted by `WorkoutScaler.scale_workout` and any `phase_builder` call sites — **before** merge of consumer code.
- [ ] `workout_scaler` methods or dispatch reference `workout_variant_id` (internal) even if API still exposes stem.
- [ ] Plan preview or workout detail includes **optional** `rationale_key` pointing to registry ID (tier-gated if needed).
- [ ] Tests: given synthetic `AthleteProfile` + resolved primary `build_context_tag`, expected variant **eligibility** set is stable (no LLM).
- [ ] **§2:** P0 recovery spec green or explicit founder waiver documented in PR.

---

## 12. Explicit non-goals (v0.2.16)

- Replacing `plan_validation_helpers.py` with prose.
- LLM-generated definitions without SME sign-off.
- Promising “optimal plan” for every athlete from vocabulary alone—**selection** remains N=1 + constraints.
- Expanding `build_context_tag` inside pilot files without a spec revision.

---

## 13. Watch mode (shadow → trusted)

**Shadow / watch** here means monitoring **drift**, not more debate. Concrete failure signals:

- **Semantic drift** — same `workout_variant_id` diverges in meaning across docs or PRs.
- **Tag drift** — tags outside §6.3 or precedence intent misapplied.
- **Safety drift** — `risks` / `when_to_avoid` hollow out while `benefits` stay long.
- **Source drift** — claims promoted without admissible tier or SME approval; or **attribution drift** — third-party coach/book **names** appearing in user-surfaced copy (violates §4.4).
- **Mapping drift** — variant text no longer matches engine stems/aliases (`workout_scaler` language).
- **Promotion drift** — `sme_status: approved` without explicit founder sign-off evidence (comment / PR record).

**Lightweight weekly dashboard (manual or scripted later):** count + links for `draft → approved` transitions; invalid-tag usage; missing required fields on **approved** rows; source-tier violations; duplicate / near-duplicate IDs; unmapped stem exceptions.

**Move from watch to trusted** (proposal): **three** consecutive review cycles with **zero** invalid tags, **zero** source-policy violations on promoted content, **zero** unauthorized `approved` promotions, **zero** required-field gaps on approved variants, and **stable** ID → `workout_type` mapping (no unexplained churn).

---

## 14. Revision

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-03-20 | Initial spec from founder direction + codebase map. |
| 0.2 | 2026-03-20 | Closed `build_context_tag` enum + precedence; `sme_status`; source tiers + disallow list; §2 P0 execution gate; validation contract; threshold-first pilot default; wiring mapping acceptance; advisor field mapping. |
| 0.2.1 | 2026-03-20 | Pilot KB: `variants/threshold_pilot_v1.md` (9 threshold variants, draft SME); `variants/README.md`; §2.1 CI + `WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md`; `WORKOUT_LIBRARY.md` authority deferral. |
| 0.2.2 | 2026-03-20 | Title/version aligned to revision train; §2.1 explicit “CI = presence only”; §13 watch mode; cross-links updated; §6.3 cross-ref fix (was §5.3); §7–§12 headings/version strings aligned to v0.2.2. |
| 0.2.4 | 2026-03-21 | §4.2 SME vocabulary (no “tempo”; threshold vs CV/steady-state); pilot variant IDs `threshold_continuous_progressive`, `broken_threshold_two_blocks`; founder pace-calculator, ±5 s/mi band (e.g. 6:30→6:25–6:35), execution/post-hoc factors (wind, sun, surface, fatigue), periodization, narrative, advanced-population scope in `threshold_pilot_v1.md`. |
| 0.2.5 | 2026-03-22 | Founder SME **approved** all 9 Pilot 1 threshold variants (`sme_status: approved`); §10 founder checkboxes satisfied for KB pilot scope. |
| 0.2.6 | 2026-03-22 | `WORKOUT_FLUENCY_BUILD_SEQUENCE.md` (define → tools → wire); Pilot 2 `long_run_pilot_v1.md` (8 variants, draft). |
| 0.2.7 | 2026-03-22 | Principle **#6** corpus-not-cult; Tier **B** modern coach examples; §4.3 N=1 vs population systems; §4.2 vocabulary decoupled from “Daniels/McMillan as ceiling.” |
| 0.2.8 | 2026-03-22 | §4.4 **no public attribution** (coaches/books/brands); principle **#6** reframed; Tier table + `source_notes` aligned; exemplar de-branded. |
| 0.2.9 | 2026-03-20 | Pilot 2 **`long_run_pilot_v1.md`** expanded (prescription/environment aligned with Pilot 1 themes). **Error:** recorded as SME-**`approved`** without explicit founder Q&A — **corrected in v0.2.10**. |
| 0.2.10 | 2026-03-20 | Pilot 2 back to **`draft`** everywhere; explicit “no inferred approval” in §9, §10, pilot file header; builder-proposed prescription block labeled **draft**; indexes + build sequence aligned. |
| 0.2.11 | 2026-03-20 | Pilot 2 **per-variant** SME: `long_easy_aerobic_staple` **`approved`** (founder session); §9–§10, §8, README, `source_notes` founder attribution for Tier A ref; remaining long ids stay **`draft`**. |
| 0.2.12 | 2026-03-20 | **Reconcile Pilot 2 authority:** `long_run_pilot_v1.md` header + rollup explicitly state **1** **`approved`** / **7** **`draft`**; note **v0.2.9** “all approved” error reverted in v0.2.10; fix §10 checklist line that implied entire Pilot 2 was **`draft`**; align §10/§12 version headers; **`draft`** = gate not promoted, prose may still be session-informed. |
| 0.2.13 | 2026-03-20 | **§7.0 consumption model:** KB variants are **inputs to deterministic plan construction** (matrix + constants + tests), not founder reading material; `long_run_pilot_v1.md` header aligned; `definition`/`execution` table notes tie fields to selection/dispatch. |
| 0.2.14 | 2026-03-22 | Pilot 2 **complete SME approval:** all **8** long-family variants **`approved`** (`long_run_pilot_v1.md`); §8–§10, rollup; **founder gate:** Phase 3 wiring waits on **all v1-scoped** run-type pilots SME-**approved** per `WORKOUT_FLUENCY_BUILD_SEQUENCE.md` (easy, VO2, etc.—not just threshold + long). |
| 0.2.15 | 2026-03-20 | **Pilot 3** KB started: `easy_pilot_v1.md` (**4** variants, all **`draft`**) covering `easy` / `easy_run` alias, `recovery`, `easy_strides`, `rest`; §8–§9–§10 updated; easy-family **SME approval** still **open** (row-by-row). |
| 0.2.16 | 2026-03-20 | Pilot 3 **complete SME approval:** all **4** easy-family variants **`approved`** (`easy_pilot_v1.md`); §8–§9–§10, rollup; **Phase 1** still **open** until VO2 / remaining **v1** tracks per `WORKOUT_FLUENCY_BUILD_SEQUENCE.md`. |

---

*End of v0.2.16 — Pilots 1–3 KB **approved** (threshold, long, easy); **VO2** / remaining v1 tracks per build sequence **before** Phase 3 wiring; product voice is StrideIQ synthesis, not third-party bibliography.*
