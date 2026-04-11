# Plan Engine V2 — Master Plan

**Date:** April 10, 2026
**Status:** Comprehensive build plan — START HERE
**Author:** Advisor session with founder

This is the single document that ties everything together. Read this
first. It tells you what to build, what to reuse, what to read, and
in what order.

---

## What We're Building

A next-generation plan generator that produces training plans informed
by modern coaching science (Davis, Green, Roche, Coe), using the
athlete's individual data to determine dosage. It replaces V1's
generation logic while preserving V1's intelligence infrastructure.

**What changes:** How plans are structured, how workouts are described,
what modes are available (Build/Maintain/Custom), how progression
works, how fueling is integrated.

**What does NOT change:** How athlete data is gathered, how paces are
calculated, how findings are discovered, how the plan talks to the
coach/briefing/replanner. V2 is a better brain using the same eyes
and ears.

---

## The Existing System (DO NOT REBUILD)

V2 consumes these existing components. They are battle-tested,
production-hardened, and connected to the intelligence engine. Treat
them as read-only APIs.

### 1. Fitness Bank (`services/fitness_bank.py`)

**What it gives you:** The athlete's complete capability profile.

| Field | What it means |
|-------|--------------|
| `best_rpi` | Individual performance index — the anchor for ALL paces |
| `experience_level` | Tier (beginner → elite) |
| `constraint` | `injury` / `time` / `detrained` / `none` |
| `current_weekly_miles` / `peak_weekly_miles` | Volume history |
| `current_long_run_miles` | Recent long run capability |
| `recent_quality_sessions_28d` | Quality session frequency |
| `ctl` / `atl` | Chronic/acute training load |
| `weeks_to_race_ready` / `sustainable_peak_weekly` | Projections |
| `peak_confidence` | How much to trust stale peaks |
| `race_list` | All race results with RPI |

**V2 usage:** Call `get_fitness_bank(athlete_id, db)` at plan start.
This is your athlete profile. Every volume decision, every quality
density decision, every pace decision flows from this.

### 2. Pace Calculator (`services/workout_prescription.py`)

**Sacred function:** `calculate_paces_from_rpi(rpi) → dict`

Returns named Daniels zones in min/mi: `easy`, `long`, `marathon`,
`threshold`, `interval`, `repetition`, `recovery`.

**V2 usage:** Call this FIRST. These are the anchors. V2 extends them
with the percentage ladder (filling gaps between named zones) but
never overrides them. If Daniels says threshold is 6:45, that's what
threshold is.

Also available: `format_pace()`, `format_pace_range()` for
athlete-facing text.

### 3. Fingerprint Bridge (`plan_framework/fingerprint_bridge.py`)

**What it gives you:** The athlete's N=1 intelligence translated into
plan parameters.

| Parameter | What it means | How V2 uses it |
|-----------|--------------|----------------|
| `cutback_frequency` | How often to schedule down weeks | Phase structure |
| `quality_spacing_min_hours` | Min gap between quality sessions | Weekly layout |
| `limiter` | Dominant bottleneck: `volume`, `recovery`, `ceiling`, `threshold`, `race_specific` | Where the plan's energy goes |
| `primary_quality_emphasis` | `long`, `threshold`, `intervals`, or conservative spacing | Which quality sessions dominate |
| `tss_sensitivity` | `moderate` or `high` | Volume caps |
| `consecutive_day_preference` | Whether athlete tolerates back-to-back quality | Weekly layout |
| `training_context` | From AthleteFacts (injuries, preferences) | Constraints |
| `disclosures` | What the system told the athlete | Coach/UI copy |

**V2 usage:** Call `build_fingerprint_params(athlete_id, db)` at plan
start. This is the intelligence layer speaking. V1 only consumed
`cutback_frequency` and `quality_spacing_min_hours`. V2 MUST consume
ALL parameters — especially `limiter` and `primary_quality_emphasis`,
which directly map to the sliding bottleneck concept.

**The `limiter` field IS the sliding bottleneck.** If the correlation
engine says this athlete is volume-limited, the plan emphasizes easy
volume. If threshold-limited, the plan emphasizes threshold work.
This is where the intelligence engine meets the plan generator.

### 4. Load Context (`plan_framework/load_context.py`)

**What it gives you:** Recent training reality for volume seeding.

| Field | What it means |
|-------|--------------|
| `l30_max_easy_long_mi` | Max easy/long run in last 30 days |
| `observed_recent_weekly_miles` | 4-week average volume |
| `history_override_easy_long` | Has enough 15+ and 18+ mi history |
| `count_long_15plus` / `count_long_18plus` | Long run depth |

**V2 usage:** Call `build_load_context(athlete_id, db, reference_date)`
to seed starting volumes. Don't prescribe a 20-mile long run for
someone whose L30 max is 12. Don't start at 50 mpw for someone
averaging 30.

### 5. Quality Gate (`services/plan_quality_gate.py`)

**What it gives you:** Pass/fail validation against proven invariants.

Key function: `evaluate_constraint_aware_plan(plan) → QualityGateResult`

Also: `compute_athlete_long_run_floor(...)` — the unified floor
calculation that protects athletes from under-prescription.

**V2 usage:** Run the existing gate on V2 output. If V2 plans fail
the existing gate, V2 has regressed. V2 adds its OWN additional
checks (fueling, effort language, progression, distance ranges) on
top of the existing gate.

### 6. Limiter Classifier (`plan_framework/limiter_classifier.py`)

**What it gives you:** Lifecycle state management for correlation
findings. Determines which findings are `active`, `emerging`,
`resolving`, `structural`.

**V2 usage:** Run BEFORE plan generation so the fingerprint bridge
reads consistent finding states. V2 doesn't call this directly —
the bridge calls it internally. But V2 should understand that the
`limiter` parameter it receives is grounded in real finding lifecycle
data, not a guess.

### 7. Adaptive Replanner (`plan_framework/adaptive_replanner.py`)

**What it gives you:** Mid-plan adaptation when the athlete diverges.

Triggers: missed long run, 3+ consecutive missed days, sustained
low readiness. Generates a 2-week micro-plan replacement.

**V2 usage:** The replanner calls the plan engine to generate the
micro-plan. When V2 is active, the replanner should call V2 instead
of V1. V2 must produce plans that are compatible with the replanner's
diff and acceptance flow (same `PlannedWorkout` fields, same
`PlanModificationLog` contract).

### 8. Models (`models.py`)

**`TrainingPlan`:** V2 writes to the same table. New fields needed:
`block_number`, `peak_workout_state` (for build-over-build). Make
race fields nullable (Build/Maintain have no race).

**`PlannedWorkout`:** V2 writes to the same table. Key fields:
`scheduled_date`, `workout_type`, `title`, `description`, `phase`,
`target_distance_km`, `segments` (JSONB), pace columns, `week_number`.

**Day-of-week convention:** Model documents Sunday=0. Prescription
code uses Monday=0. V2 must map explicitly.

---

## What V2 Adds (the new capabilities)

### A. Three Plan Modes
- **Race:** Preparing for a specific race (M, HM, 5K, 10K, Ultra)
- **Build:** General fitness without a race (Onramp, Volume, Intensity)
- **Maintain:** Hold fitness between goals

All modes use the SAME engine — same segments schema, same pace
ladder, same effort language. The difference is periodization
structure and quality density.

### B. Extension-Based Progression
Pace stays constant within a block. Duration/distance grows.
400m → 800m → 1200m → mile at the same pace. Three types:
extension (marathon/HM/ultra/build), variety (5K/10K), hybrid
alternating (champion ultra).

### C. Build-Over-Build Memory
`peak_workout_state` on TrainingPlan stores the peak from the
final week. Next block seeds from previous peak. Ensures continuous
adaptation across cycles.

### D. Effort-Based Descriptions
Athlete-facing text uses effort language (10K effort, threshold,
easy/mod) with pace as secondary. Internal `pace_pct_mp` is never
shown to the athlete.

### E. Distance Ranges
Easy and long runs prescribed as ranges (e.g., "8-16 mi") for
athlete self-selection. Embodies "plans written in pencil."

### F. Fueling Integration
Every workout ≥90 min includes `fueling_target_g_per_hr` and a
fueling reminder in the description. Targets scale with training age.

### G. Three Rotating Long Run Types
A (easy progressive), B (threshold segments), C (fatigue resistance).
No two consecutive weeks get the same type.

### H. Auto-Renewal
Build and Maintain plans auto-generate the next block before the
current one ends, seeded from peak_workout_state.

---

## Document Map (what to read and when)

### Tier 1: Read Before Writing Any Code

| Order | Document | What it tells you |
|-------|----------|-------------------|
| 1 | **This document** | What to build, what to reuse, milestones |
| 2 | `docs/wiki/index.md` → `docs/wiki/plan-engine.md` | The full product: what's built, how the intelligence engine works, where V2 fits in the system. Also read `docs/wiki/product-vision.md` for strategic priorities. |
| 3 | `docs/BUILDER_INSTRUCTIONS_2026-04-10_PLAN_ENGINE_V2_SANDBOX.md` | How to build safely (sandbox, preview, cutover) |
| 4 | `docs/specs/PLAN_GENERATOR_ALGORITHM_SPEC.md` | The algorithm (periodization, segments, progression, quality bar) |

### Tier 2: Read Before Implementing Specific Modules

| Document | Read when implementing... |
|----------|--------------------------|
| `docs/references/GREEN_COACHING_PHILOSOPHY_EXPANDED_2026-04-10.md` | Workout descriptions, coaching voice, any athlete-facing text |
| `docs/references/DAVIS_FULL_SPECTRUM_10K_PLAN_CONSTRUCTION_2026-04-10.md` | 5K/10K mode periodization, percentage ladder, plan construction process |
| `docs/references/DAVIS_MARATHON_EXCELLENCE_AND_TRAINING_LOAD_2026-04-10.md` | Marathon mode, plan tiering by volume, three-load framework |
| `docs/references/ROCHE_SWAP_EFFORT_DICTIONARY_2026-04-10.md` | effort_mapper.py (effort terminology) |
| `docs/references/ROCHE_SWAP_WORKOUT_EXECUTION_GUIDE_2026-04-10.md` | workout_library.py (execution protocols) |

### Tier 3: Reference As Needed

| Document | Use when... |
|----------|-------------|
| `ROCHE_SWAP_TRAINING_PHILOSOPHY_UNIFIED_2026-04-10.md` | Understanding the hierarchy and sliding bottleneck |
| `DAVIS_MODERN_MARATHON_APPROACH_REFERENCE_NOTE_2026-04-10.md` | Marathon three-phase periodization |
| `DAVIS_FIVE_PRINCIPLES_MARATHON_TRAINING_2026-04-10.md` | Four components of marathon fitness |
| `ROCHE_SWAP_COACHING_PHILOSOPHY_2026-04-10.md` | Plan structure examples (ultra, base, 5K/10K) |
| `ROCHE_SWAP_12WK_MARATHON_PLAN_2026-04-10.md` | Quality bar for marathon plans |
| `ROCHE_SWAP_PLANS_SUPPLEMENTARY_2026-04-10.md` | Quality bar for HM/track/100mi plans |
| `ROCHE_SWAP_FUELING_REFERENCE_2026-04-10.md` | Fueling targets and protocols |
| All other `docs/references/*.md` | Deep dives on specific topics |

---

## Phased Milestones

### Phase 1: Foundation — ✅ COMPLETE (April 9, 2026)

**Goal:** V2 generates valid plans for easy cases with correct paces,
effort language, and segments.

**Delivered:**
- [x] `pace_ladder.py` — percentage ladder from RPI, consuming
      `calculate_paces_from_rpi()`
- [x] `effort_mapper.py` — internal % → athlete-facing effort text
- [x] `models.py` (V2 dataclasses) — PaceLadder, WorkoutSegment, V2DayPlan, V2WeekPlan, V2PlanPreview
- [x] `engine.py` — loads fitness bank, computes ladder, builds phases, produces full plans

### Phase 2: Workout Library + Long Runs — ✅ COMPLETE (April 9, 2026)

**Goal:** V2 produces complete weeks with correct workout types,
long run rotation, and distance ranges.

**Delivered:**
- [x] `workout_library.py` — 22+ workout types with concrete segments
- [x] Three rotating long run types (easy progressive, threshold segments, fatigue resistance)
- [x] Distance ranges on all easy/long runs
- [x] Fueling on all workouts ≥90 minutes
- [x] Weekly assembly in `engine.py` with schedule_week()

### Phase 3: Periodization + Progression — ✅ COMPLETE (April 10, 2026)

**Goal:** V2 produces full multi-week plans with correct phase
structure and extension-based progression.

**Delivered:**
- [x] `periodizer.py` — phase structures for race/build/maintain modes
- [x] Extension-based progression (pace constant, duration grows)
- [x] Full plan assembly in `engine.py` — multi-week plans
- [x] Integration with fingerprint bridge — consumes `limiter`,
      `primary_quality_emphasis`, `cutback_frequency`,
      `quality_spacing_min_hours`
- [x] Integration with load context — volume seeding from L30
- [x] Tune-up race integration with preserved midweek quality

### Phase 4: All Modes + Build-Over-Build — ✅ COMPLETE (April 10, 2026)

**Goal:** V2 handles all plan modes including Build and Maintain, with
build-over-build seeding.

**Delivered:**
- [x] Build-Onramp (8 weeks, no threshold, 4 runs/week)
- [x] Build-Volume (6 weeks repeatable)
- [x] Build-Intensity (4 weeks, 2 quality days)
- [x] Maintain (4 weeks repeatable)
- [x] Build-over-build seeding (peak_workout_state → next block)
- [x] `plan_preview` migration (`plan_engine_v2_001`)

### Phase 5: Quality Gate + Evaluation — ✅ COMPLETE (April 10, 2026)

**Goal:** V2 passes all validation criteria and produces founder-reviewed
plans.

**Delivered:**
- [x] V2-specific quality gate (integrated in engine.py)
- [x] Evaluation harness — all real athlete profiles + synthetic profiles
- [x] Test matrix runner with full reports
- [x] Founder coaching review of all generated plans
- [x] Tune-up plans reviewed and validated by founder

**Founder review (April 10, 2026):** "The long run staircase on the
16-week marathon is what it should be — 14 → 16 → 18 → cutback → 20
→ 21 → cutback → 18 → tune-up → 21 → cutback → 19 → 18 → taper.
Visit the peak, drop, visit again, taper down. The tune-up week
preserving quality (threshold Wed, pre-race Fri, race Sat, recovery
LR Sun) is correct handling."

### Phase 6: Cutover — 🔄 IN PROGRESS

**Goal:** V2 goes live, starting with founder account.

- [x] `engine=v2` query parameter on `POST /v2/plans/constraint-aware`
- [x] `router_adapter.py` — request mapping, FitnessBank/FingerprintParams/LoadContext loading, response stitching
- [x] `plan_saver.py` — V2WeekPlan → TrainingPlan + PlannedWorkout DB rows
- [x] Admin/owner gate (V2 only available to admin/owner roles)
- [x] V2 deployed to production (April 11, 2026)
- [x] Smoke test: V2 dry-run generates correctly on production
- [x] V1 default path verified unaffected
- [ ] Founder account switched to V2 for live plan generation
- [ ] 7 days monitoring
- [ ] Beta athlete rollout
- [ ] 14 days monitoring
- [ ] Global default flip
- [ ] V1 archived after 4 weeks stable

---

## Non-Negotiable Constraints

1. **V1 stays untouched** until V2 is proven in production.
2. **`calculate_paces_from_rpi()` is sacred.** V2 extends, never
   overrides.
3. **Intelligence engine outputs are consumed, not ignored.** The
   fingerprint bridge, limiter, and load context exist for a reason.
   V2 that ignores them is DUMBER than V1.
4. **No "% MP" in athlete-facing text.** Ever. Effort terms only.
5. **Fueling on every workout ≥90 min.** Non-negotiable.
6. **Distance ranges on every easy/long run.** Non-negotiable.
7. **Extension-based progression within blocks.** Pace constant,
   duration grows. Not "same workout faster."
8. **Workout descriptions teach the WHY.** Not just the WHAT.
   Green's principle: "My job is to eliminate my own job."
9. **The athlete decides.** Distance ranges, effort-based language,
   and the replanner give the athlete agency. The system informs.
10. **Same species, same hierarchy, same science.** Dosage varies by
    training age. Architecture doesn't.

---

## Sources (the full KB)

### Primary Influences (ordered by founder priority)

**Jon Green (philosophy — founder's #1):**
- `GREEN_COACHING_PHILOSOPHY_EXPANDED_2026-04-10.md` — seven principles
- `GREEN_COACHING_PHILOSOPHY_REFERENCE_NOTE_2026-04-10.md` — doubles, N=1

**John Davis (science — primary road/track):**
- `DAVIS_MODERN_MARATHON_APPROACH_REFERENCE_NOTE_2026-04-10.md`
- `DAVIS_FIVE_PRINCIPLES_MARATHON_TRAINING_2026-04-10.md`
- `DAVIS_MARATHON_EXCELLENCE_AND_TRAINING_LOAD_2026-04-10.md`
- `DAVIS_FULL_SPECTRUM_10K_PLAN_CONSTRUCTION_2026-04-10.md`
- `DAVIS_MARATHON_BUILD_SAMPLE_2026-04-10.md`
- `SSMAX_STEADY_STATE_MAX_REFERENCE_NOTE_2026-04-10.md`
- `COE_STYLE_TRAINING_REFERENCE_NOTE_2026-04-10.md`

**David & Megan Roche (practical structures — trail/ultra):**
- `ROCHE_SWAP_COACHING_PHILOSOPHY_2026-04-10.md`
- `ROCHE_SWAP_TRAINING_PHILOSOPHY_UNIFIED_2026-04-10.md`
- `ROCHE_SWAP_EFFORT_DICTIONARY_2026-04-10.md`
- `ROCHE_SWAP_WORKOUT_EXECUTION_GUIDE_2026-04-10.md`
- `ROCHE_SWAP_12WK_MARATHON_PLAN_2026-04-10.md`
- `ROCHE_SWAP_PLANS_SUPPLEMENTARY_2026-04-10.md`
- `ROCHE_SWAP_FUELING_REFERENCE_2026-04-10.md`

**Physiological foundation:**
- `ADVANCED_EXERCISE_PHYSIOLOGY_SYNTHESIS_2026-04-10.md`

**The founder:** The quality bar. Physicist, coach, competitive runner.
If the plan wouldn't pass the napkin test, it's not good enough.

### Existing System Documentation
- `docs/specs/PLAN_GENERATOR_ALGORITHM_SPEC.md` — V2 algorithm
- `docs/BUILDER_INSTRUCTIONS_2026-04-10_PLAN_ENGINE_V2_SANDBOX.md` — sandbox
- `docs/BUILDER_INSTRUCTIONS_2026-04-10_TRAINING_LIFECYCLE.md` — lifecycle modes
- `docs/specs/N1_ENGINE_ADR_V2.md` — V1 requirements (for regression checking)
- `docs/specs/KB_RULE_REGISTRY_ANNOTATED.md` — 76 existing KB rules
- `docs/wiki/plan-engine.md` — wiki overview
