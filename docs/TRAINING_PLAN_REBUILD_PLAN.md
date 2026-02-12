# Training Plan & Daily Adaptation — Phased Build Plan

**Date:** February 12, 2026
**Status:** APPROVED — Ready to build
**Decision:** A-level rigor at every distance + Daily Adaptation Engine + Coach Trust as parallel track

---

## Guiding Principles (Non-Negotiable)

1. **N=1 over population norms.** Every default is overridable by athlete data. Long run distances, periodization models, VO2max placement, intensity distribution — all parameterized, all learned from the individual. Population norms are cold-start heuristics, not rules.

2. **No template narratives. Ever.** A template gets stale the second time you read it. The only narrative worth showing is contextual — aware of where you are in the plan, what happened last week, how you responded, and what's coming next. That requires the adaptation engine and proven coach intelligence. Until then, clean prescriptions with calculated paces. Silence is better than fake wisdom.

3. **Daily adaptation is the monetization moat.** Static plans are one-time purchases. Daily intelligence is the subscription value — it's what makes the product irreplaceable and compounds over time.

4. **The system INFORMS, the athlete DECIDES.** The default behavior is surfacing data and patterns, NOT swapping workouts or overriding the athlete. Fatigue is a stimulus, not an enemy — supercompensation requires overreach. The system must never prevent a breakthrough by "protecting" the athlete from productive stress. Intervention is reserved for extreme, sustained, unmistakable negative trajectories — and even then it's a flag, not an override.

5. **Coach trust is earned, not assumed.** The rules engine surfaces information. The coach NARRATES first, ADVISES second, acts AUTONOMOUSLY only when trust is proven. Coach improvement is a continuous parallel track — not a deferred phase.

6. **No metric is assumed directional. No threshold is assumed universal.** HRV, TSB, resting HR — discover the individual relationship before acting on it. The correlation engine compiles data and reports until evidence is conclusive for THAT athlete. Adaptation thresholds are per-athlete parameters that start conservative and calibrate from outcome data. Hardcoded thresholds from textbooks or coaching opinion are cold-start heuristics only.

7. **Self-regulation is a signal, not a problem.** When the athlete modifies a workout (planned 15 easy, did 10 at MP), that is first-class data. Log the delta, log the outcome, study the pattern. An experienced athlete who overrides "rest" and gets a breakthrough is not non-compliant — they are self-regulating. The system learns from these overrides to refine its model of the individual.

8. **Paid tier = N=1 intelligence + daily insight.** Free/one-time plans give you the "what." Subscription gives you the "why this works for YOU" — your supercompensation patterns, your recovery timelines, your load-response relationship.

9. **The system doesn't coach you on running. It coaches you on YOU.** The value is being the data analyst of your body — surfacing patterns, correlations, and insights from your own data that you can't hold in your head across 2+ years of training. 150+ tools and growing.

---

## Resolved Decisions

These are decided. No revisiting during the build.

1. **Standard tier pace injection:** YES — show paces on free plans if the athlete has RPI from signup or Strava. Paces are expected, not a differentiator. N=1 intelligence and daily adaptation are the paid differentiators.

2. **50K timeline:** Deferred until after 5K is complete (Phase 1 scope ends at 5K). 50K requires new primitives (back-to-back long runs, time-on-feet, RPE, nutrition, strength) that shouldn't block the core distances.

3. **Adaptation notification:** In-app first. Push notification as fast follow. Email weekly digest only (not per-adaptation).

4. **Nightly replan timing:** 5 AM athlete local time. Not configurable in v1 — simplicity over flexibility.

5. **Coach narration model:** Gemini Flash for adaptation narrations (fast, cheap, tightly scoped). Route through existing tiering only for conversational/advisory interactions.

6. **Dead code:** `plan_generator_v2.py` is deleted in Phase 1. No ceremony.

---

## Parallel Track: Coach Trust (Runs Through All Phases)

Coach trust is NOT a phase. It is a continuous investment that improves at every stage.

### What runs from Day 1:

**Coach Evaluation Suite** (`test_coach_evaluation.py`)
- Every failure the founder has found manually ($1000+ in tokens) becomes a regression test
- Contract tests (deterministic, no API calls): prompt construction, tone rules in system prompt, normalization pipeline, tool definitions present
- LLM evaluation tests (tagged `@pytest.mark.coach_integration`, costs tokens, run nightly/pre-deploy):
  - No raw metric dumping (TSB, CTL, ATL never appear as raw numbers)
  - No VDOT (trademark regression)
  - Validates athlete feelings before contradicting
  - Uses tools when data is needed (calls get_training_paces, not guessing)
  - Tone rules followed (lead with positives, forward-looking actions)
  - Citation contract holds (no uncited numeric claims)
  - Normalization works (no fact capsule labels, no contract echoes)
  - No physiologically unsound recommendations (no intervals day after 20-miler)
- Curated scenario tests from the founder's training history
- "Here's what happened this week. What should the plan do?" → Compare coach answer to founder's actual decision
- Score accuracy. Track over time. Identify failure patterns.
- This is the acceptance test for coach quality — when it consistently matches or exceeds founder judgment on a class of decisions, that class is eligible for advisory/autonomy.

**Key files:**
- New: `apps/api/tests/test_coach_evaluation.py` (LLM evaluation, tagged coach_integration)
- New: `apps/api/tests/test_coach_contract.py` (deterministic contract tests, every commit)
- Modified: existing coach tests updated to cover new scenarios

**HRV Correlation Study (Background)**
- Start data collection immediately — HRV (rMSSD, SDNN) vs next-day efficiency, key workout quality, race performance
- Time-shifted analysis (0-14 day lags) already supported by `correlation_engine.py`
- Monthly per-athlete reports: "HRV relationship: [positive / negative / no signal / insufficient data]"
- Do NOT act on HRV in readiness score until individual relationship is statistically significant
- Fix: remove HRV from hardcoded `good_high_inputs` in `correlation_engine.py` line 1319

### What unlocks at milestones:

| Milestone | Gate | Scoring Function | What Unlocks |
|-----------|------|-----------------|-------------|
| Phase 2 live (intelligence engine) | Coach narrates intelligence insights | Each narration scored on 3 binary criteria: (1) factually correct vs intelligence engine data, (2) no raw metrics leaked, (3) actionable language. Score = % of criteria passed across all narrations in the window. | Every narration is a scored test |
| Narration score > 90% for 4 weeks | Automated scoring against ground truth + founder spot-check of 10% sample | Score function must be defined and tested BEFORE Phase 3 begins. Founder reviews the scoring function itself, not just the results. | Coach begins generating contextual workout narratives (Phase 3B) |
| Contextual narrative quality sustained | Founder review of weekly sample (5-10 narratives) + regression suite green + no new failure modes | Rubric: (1) contextual (references specific data), (2) non-repetitive (no two narratives share >50% of phrasing), (3) physiologically sound, (4) follows tone rules | Coach advisory mode — proposes adjustments, athlete approves/rejects, acceptance rate tracked |
| Advisory acceptance rate > 80% for 8 weeks | Acceptance = athlete approves or completes the suggested modification. Rejection = athlete dismisses or does something different. Measured weekly. | Rate = accepted / (accepted + rejected). Ignored = excluded (athlete didn't see it). | Coach conditional autonomy — adjusts within bounds without approval |

---

## Phase 1: World-Class Plans by Distance

**Goal:** Build plans so good the prescription itself earns trust. Clean, correct, paces injected. No narrative filler.
**Dependencies:** None — start immediately.

### 1-PRE. Plan Validation Framework (BUILD THIS FIRST)

Before writing a single line of plan generation code, build the automated test framework that encodes what "world-class" means. The KB's Part 4 checklist becomes executable assertions. Plans are generated and validated against every coaching rule.

**The validation engine checks:**
- Volume distribution: easy running = 65-80% of weekly volume (every week)
- Source B limits: long ≤30%, T ≤10%, I ≤8%, MP ≤20% (every session)
- Phase rules: no threshold in base, no intervals mid-build (unless N=1 override)
- Alternation: T-week = easy long, MP-long week = no T. Never 3 quality days.
- Hard-easy: quality day always followed by easy/rest
- Progression: long run jumps ≤2mi/week, volume jumps ≤15%/week (except cutback)
- Cutback: every Nth week, correct reduction percentage
- Taper: volume reduces, intensity maintained (strides/sharpening present)
- MP total: ≥40mi for marathon (distance-specific targets)
- Paces: every non-rest workout has calculated paces when RPI exists

**Parametrized test matrix:**
- Every distance × every volume tier × every duration variant
- N=1 override variants: experienced athlete (70mpw, 18mi long runs) vs beginner (25mpw)
- Each variant must pass ALL coaching rules

**Distance-specific assertions:**
- Marathon: MP total ≥40mi, T-block is primary quality, long run peaks ≥20mi for mid+ tiers
- Half: threshold dominant (more T sessions than I sessions), HMP long runs only in build/peak
- 10K: VO2max + threshold co-dominant, interval volume increases through build
- 5K: VO2max dominant (more I sessions than T), repetition work present, long runs NOT capped below athlete's practice

**Scope guardrail (prevents scope creep):**
- 1-PRE delivers the FRAMEWORK + validation functions + marathon variants passing against current generator
- Half/10K/5K tests: written as `@pytest.mark.xfail(reason="generator not yet implemented")` — they exist, they document the contract, they do NOT block progress
- Each distance task (1E, 1F, 1G) removes xfail for that distance as part of ITS acceptance criteria
- The builder must NOT try to make the full matrix green in 1-PRE. That's the whole point of the phased plan.

**Acceptance Criteria:**
- [ ] `test_plan_validation_matrix.py` exists with parametrized tests across all distance/tier/duration combinations
- [ ] Marathon variants: expected to PASS against current generator (or expose real gaps to fix in 1B)
- [ ] Half/10K/5K variants: marked xfail, document the contract, do not block 1-PRE completion
- [ ] Validation functions cover ALL Part 4 checklist items
- [ ] Distance-specific assertions for each distance (written, not necessarily passing)
- [ ] N=1 override scenarios included in matrix
- [ ] Framework is reusable — adding a new distance means adding parameters + removing xfail, not new test infrastructure

**Key files:**
- New: `apps/api/tests/test_plan_validation_matrix.py`
- New: `apps/api/tests/plan_validation_helpers.py` (shared assertion functions)

**KB sources for validation rules (builder MUST read these before writing assertions):**
- `_AI_CONTEXT_/KNOWLEDGE_BASE/PLAN_GENERATION_FRAMEWORK.md` — Part 4 checklist, volume limits, phase rules
- `_AI_CONTEXT_/KNOWLEDGE_BASE/coaches/verde_tc/PHILOSOPHY.md` — **PRIMARY philosophical alignment.** Jon Green / Verde Track Club. Volume over intensity, conservative by default, athlete autonomy, "my job is to eliminate my own job." Founder's preferred coaching style. Contains specific workout examples and periodization approach.
- `_AI_CONTEXT_/KNOWLEDGE_BASE/coaches/source_B/PHILOSOPHY.md` — Source B volume limits (long ≤30%, T ≤10%, I ≤8%)
- `_AI_CONTEXT_/KNOWLEDGE_BASE/coaches/source_B/WORKOUT_DEFINITIONS.md` — Workout type definitions and progressions
- `_AI_CONTEXT_/KNOWLEDGE_BASE/coaches/source_A/PLANS.md` — Plan structure and periodization
- `_AI_CONTEXT_/KNOWLEDGE_BASE/02_PERIODIZATION.md` — Phase rules, alternation, cutback patterns
- `_AI_CONTEXT_/KNOWLEDGE_BASE/TRAINING_METHODOLOGY.md` — Distance-specific emphasis rules
- `_AI_CONTEXT_/KNOWLEDGE_BASE/00_GOVERNING_PRINCIPLE.md` — N=1 philosophy that constrains ALL assertions

---

### 1A. Pace Injection Audit & Fix

**What:** Verify paces inject on ALL tiers where RPI exists. Fix standard tier (`paces=None` on line 260 of `generator.py`).

**Acceptance Criteria:**
- [ ] Every plan tier (standard, semi-custom, custom, model-driven, constraint-aware) shows calculated paces when the athlete has RPI
- [ ] Standard tier generates paces from RPI when available, falls back to effort descriptions only when no RPI exists
- [ ] Paces display in both per-mile and per-km formats
- [ ] Existing tests pass, new tests cover pace injection across all tiers

**Key files:**
- `apps/api/services/plan_framework/generator.py` (line 260)
- `apps/api/services/plan_framework/pace_engine.py`
- `apps/api/routers/plan_generation.py`

### 1B. Marathon — A-Level Quality

**What:** Polish the showcase distance. Verify every aspect against the KB framework.

**Acceptance Criteria:**
- [ ] T-block progression matches `PLAN_GENERATION_FRAMEWORK.md` (5×5min → 30min continuous, scaled by tier)
- [ ] MP progression totals 40-50+ miles pre-race (verified against archetype)
- [ ] Long run progression uses athlete's established practice when Strava data exists (not population cap)
- [ ] Cutback weeks validate against Part 4 checklist (every 4th week standard, every 3rd for masters override)
- [ ] Weekly structure respects alternation rule (T-week = easy long, MP-long week = no T)
- [ ] No workout exceeds Source B volume limits (long ≤30%, T ≤10%, I ≤8%)
- [ ] Clean workout cards: calculated paces, structured segments, zero filler text
- [ ] `plan_generator_v2.py` deleted (dead code)

**Key files:**
- `plans/archetypes/marathon_mid_6d_18w.json`
- `apps/api/services/plan_generator.py`
- `apps/api/services/plan_framework/generator.py`

### 1C. N=1 Override System

**What:** Athlete data overrides plan defaults. This is what makes plans individual.

**⚠️ REQUIRES ADR BEFORE IMPLEMENTATION** — This is the highest-risk new service. The ADR must address:
1. **What counts as a "long run"?** Longest run of each week? % of weekly volume? How are trail runs with high elevation but moderate distance handled? What about athletes who don't have a clear long run pattern?
2. **What is the minimum data threshold?** How many weeks of Strava data are needed before the system considers itself "informed" vs "guessing"? Below that threshold, what does the system tell the athlete?
3. **Is the fallback genuinely N=1 or secretly a template?** If the fallback is tier defaults from `constants.py`, that IS a template. The system must be transparent: "I'm using estimated defaults based on limited data. This will improve as I learn your patterns."
4. **Edge cases:** Inconsistent loggers (runs every day one week, nothing for two weeks). Athletes who log walks and runs in the same account. Athletes returning from injury with 2 years of pre-injury data that no longer reflects their current state.

**Acceptance Criteria:**
- [ ] ADR written and approved before any implementation
- [ ] `athlete_plan_profile.py` service derives: long run baseline, volume tier, recovery speed, quality session tolerance — all from Strava data
- [ ] Long run distance: uses athlete's established pattern (median of last 8 long runs) when available, falls back to tier default WITH EXPLICIT DISCLOSURE
- [ ] Volume tier: auto-detected from last 8-12 weeks of Strava, not questionnaire
- [ ] Cutback frequency: parameterized (3/4/5 week cycle), default 4, overridable
- [ ] Periodization: both early-VO2max and late-VO2max approaches supported. Default to KB Rule M2 (early). Intelligence Bank override when data exists.
- [ ] All constants in `constants.py` accept override from `athlete_plan_profile`
- [ ] Plans generated with overrides are validated against Part 4 checklist

**Key files:**
- New: `apps/api/services/athlete_plan_profile.py`
- Modified: `apps/api/services/plan_framework/constants.py`
- Modified: `apps/api/services/plan_framework/generator.py`

### 1D. Taper Democratization

**What:** Bring τ1-aware taper to all subscription tiers.

**Acceptance Criteria:**
- [ ] Athletes with calibrated τ1: taper uses individual_performance_model calculation
- [ ] Athletes without τ1: taper estimated from efficiency rebound speed after cutback weeks (proxy for adaptation rate)
- [ ] Taper maintains intensity (strides, light sharpening) while reducing volume — not blanket reduction
- [ ] Pre-race fingerprinting data available to subscription tier athletes
- [ ] Taper structure validated: fast adapters get shorter taper, slow adapters get longer

**Key files:**
- `apps/api/services/individual_performance_model.py`
- `apps/api/services/pre_race_fingerprinting.py`
- `apps/api/services/plan_framework/phase_builder.py`

### 1E. Half Marathon — A-Level Quality

**Acceptance Criteria:**
- [ ] Threshold is PRIMARY quality emphasis (cruise intervals → continuous → race-pace)
- [ ] HMP long runs: introduced in late build (last 3-4mi @ HMP), progressing to 6-8mi @ HMP
- [ ] VO2max: secondary (1000m/1200m intervals for economy, not primary development)
- [ ] Long run distances: N=1 first, tier defaults as cold-start only
- [ ] Taper: 2 weeks, maintains threshold intensity
- [ ] Phase builder `_build_half_marathon_phases()` fully implemented with appropriate phase allocation
- [ ] Workout scaler produces half-specific sessions
- [ ] All volume limits respected per Source B

### 1F. 10K — A-Level Quality

**Acceptance Criteria:**
- [ ] VO2max + threshold co-primary emphasis
- [ ] VO2max progression: 400m → 800m → 1000m → 1200m (volume at I-pace increases through build)
- [ ] Threshold: supporting role (cruise intervals, tempo runs)
- [ ] Race-pace: 10K-paced intervals with short rest in peak phase
- [ ] Long run distances: N=1 first, tier defaults as cold-start only
- [ ] Taper: 1-2 weeks, short crisp sessions
- [ ] Phase builder `_build_10k_phases()` fully implemented
- [ ] Workout scaler produces 10K-specific sessions

### 1G. 5K — A-Level Quality

**Acceptance Criteria:**
- [ ] VO2max PRIMARY emphasis. Fast-twitch recruitment addressed.
- [ ] VO2max intervals: 400m → 800m → 1000m (highest intensity quality sessions)
- [ ] Repetitions: 200m, 300m at faster-than-5K pace (neuromuscular + economy)
- [ ] Threshold: supporting role only (cruise intervals for aerobic support)
- [ ] Long run: N=1 critical. Population defaults are MINIMUMS, not caps. 70mpw runner doing 18mi long runs for a 5K is correct — the system must not interfere.
- [ ] Taper: 1 week, maintain neuromuscular sharpness
- [ ] Phase builder `_build_5k_phases()` fully implemented
- [ ] Workout scaler produces 5K-specific sessions

---

## Phase 2: Daily Adaptation Engine

**Goal:** The plan adjusts every day based on what the athlete actually does. This is the subscription moat.
**Dependencies:** Phase 1 must be substantially complete (plans must be correct before adapting them). Architecture can start in parallel with Phase 1.

### 2-PRE. Training Logic Scenario Framework (BUILD THIS FIRST)

Before writing intelligence code, build the scenario test framework. Construct training states, trigger the system, assert the intelligence output is correct.

**The Golden Scenario (must pass — this is the litmus test):**
Founder's real training week: 51→60 miles, 20mi/2300ft Sunday, every metric says "deeply fatigued." Tuesday: planned 15 easy. System MUST NOT swap the workout. System MUST surface load data (inform mode). Athlete does 10 at MP instead (self-regulation). System MUST log the override and track the outcome. Wednesday: athlete does 8 slow (self-regulation). System MUST log this too. End of week: efficiency breakthrough. System MUST detect and surface it. System MUST correlate the breakthrough with the load spike. **At no point does the system override the athlete.**

**Scenario categories:**
- Readiness computation: declining efficiency → lower score, high completion → higher score, missing signals → graceful degradation
- Intelligence rules: each of the 7 rules tested. Verify mode (inform vs suggest vs flag) is correct for each scenario.
- The golden scenario: load spike + athlete feels great → system INFORMS but does NOT intervene
- Self-regulation logging: planned ≠ actual → delta logged, outcome tracked, pattern learned
- Sustained negative trend: 3+ weeks declining → system FLAGS (not before 3 weeks)
- False positive prevention: post-load-spike efficiency dip (normal) vs sustained decline (concerning)
- Override behavior: N=1 data correctly influences readiness thresholds
- Edge cases: athlete with 2 activities (not 200), athlete with no plan, athlete mid-taper, athlete returning from injury

**Acceptance Criteria:**
- [ ] `test_training_logic_scenarios.py` exists with 25+ scenarios covering all intelligence rules
- [ ] The golden scenario (founder's 51→60 week) is test #1 and must pass
- [ ] Scenarios built from founder's actual training history where possible
- [ ] Each scenario has: setup (athlete state), trigger (system action), expected output (insight type + mode)
- [ ] Framework verifies the system NEVER swaps a workout in default inform mode
- [ ] Framework verifies FLAG mode fires only on sustained (3+ week) negative trends
- [ ] Self-regulation tracking scenarios: planned ≠ actual → correct logging verified
- [ ] Framework supports adding scenarios without new infrastructure

**Key files:**
- New: `apps/api/tests/test_training_logic_scenarios.py`
- New: `apps/api/tests/training_scenario_helpers.py`

---

### 2A. Readiness Score (Signal, Not Rule)

**What:** Composite signal from existing data, computed daily. The score is a SIGNAL — what fires from it is governed by per-athlete thresholds, not hardcoded constants.

**Architecture:**
```
Readiness Score (0-100) = signal aggregation
         ↓
Per-Athlete Thresholds (parameters, not constants)
         ↓
Adaptation Rules Engine (reads thresholds from athlete profile)
         ↓
Threshold Calibration (background, continuous)
  - Logs: readiness=X, scheduled=quality, outcome=[strong/neutral/poor]
  - Over time: discovers where THIS athlete's real threshold lives
  - Until data: conservative defaults (err on side of NOT adapting)
```

| Signal | Source | Cold-Start Weight | Notes |
|--------|--------|-------------------|-------|
| TSB (Training Stress Balance) | `training_load.py` | 0.25 | Distance from target TSB for current phase |
| Efficiency trend (7-day) | `coach_tools.py` | 0.30 | The manifesto's "master signal" — highest cold-start weight |
| Completion rate (7-day) | `PlannedWorkout.completed` | 0.20 | % of planned workouts completed |
| Days since last quality session | `PlannedWorkout` query | 0.15 | Recovery adequacy |
| Recovery half-life | `coach_tools.py` | 0.10 | Personal recovery speed |
| HRV trend | `DailyCheckin.hrv_rmssd` | **0.00** | Excluded until correlation engine proves individual direction (p < 0.05) |
| Sleep trend | `DailyCheckin.sleep_h` | **0.00** | Excluded until correlation engine proves individual relationship |

**⚠️ Cold-start weights are hypotheses, not ground truth.** The builder must:
1. Propose weights with rationale (why efficiency at 0.30 and not 0.20?)
2. Run sensitivity analysis against founder's historical training data
3. Validate: does the composite score correlate with known good/bad training periods?
4. Weights become per-athlete parameters over time (same calibration pattern as thresholds)
5. This is NOT a rubber-stamp exercise — the founder will review the sensitivity analysis output

**Per-Athlete Adaptation Thresholds:**
| Threshold | Cold-Start Default | Meaning |
|-----------|-------------------|---------|
| `swap_quality_threshold` | 35 (conservative) | Below this, swap quality → easy. Default is very low so system rarely intervenes early on. |
| `reduce_volume_threshold` | 25 | Below this, reduce next week's volume. |
| `skip_day_threshold` | 15 | Below this, recommend rest day. |
| `increase_volume_threshold` | 80 | Above this consistently, modest volume increase eligible. |

**Threshold Calibration (background process):**
- Every time the athlete does (or skips) a workout, log: readiness score at decision point, workout type scheduled, outcome (completion, efficiency delta, subjective feel next day)
- Weekly batch: compute correlation between readiness score and workout outcome quality
- When N ≥ 30 data points: estimate per-athlete thresholds using outcome data
- Report: "Your quality sessions performed best when readiness was above [X]. Sessions below [Y] had negative efficiency impact." — but only report when statistically significant
- This is the same pattern as HRV correlation engine: collect, study, report, then act

**Why conservative defaults matter:** If the cold-start default is 35, the system almost never swaps a workout for a new athlete. It watches. It logs. It learns. When it finally does intervene, the signal is screaming, not crossing an arbitrary textbook line. An athlete who crushes workouts at readiness 30 will have their threshold calibrated down. An athlete who struggles at readiness 50 will have theirs calibrated up.

**Acceptance Criteria:**
- [ ] `readiness_score.py` computes a 0-100 score from available signals (pure signal, no judgment)
- [ ] HRV excluded from score by default; only included when correlation engine has established individual direction with p < 0.05
- [ ] Sleep weight determined by correlation engine, not assumed
- [ ] `DailyReadiness` model stores: date, athlete_id, score, component breakdown (JSONB)
- [ ] `AthleteAdaptationThresholds` model stores per-athlete thresholds with cold-start defaults
- [ ] Thresholds are parameters read from athlete profile, NOT constants in code
- [ ] Celery task computes readiness nightly for all athletes with active plans
- [ ] Score components are individually inspectable (not just a black-box number)
- [ ] Threshold calibration logs every readiness-at-decision + outcome pair
- [ ] Score tested against founder's historical data to verify it produces sensible output
- [ ] No threshold fires an adaptation until explicitly calibrated OR signal is extreme (below conservative default)

### 2B. Workout State Machine + Self-Regulation Tracking

**What:** `PlannedWorkout` gains lifecycle states and self-regulation tracking. When planned ≠ actual, the delta is first-class data.

**Acceptance Criteria:**
- [ ] New fields on PlannedWorkout: `actual_workout_type` (what they actually did), `planned_vs_actual_delta` (JSONB: distance delta, pace delta, intensity delta), `readiness_at_execution` (score when they did the workout)
- [ ] `SelfRegulationLog` model: timestamp, athlete_id, workout_id, planned_type, actual_type, planned_distance, actual_distance, planned_intensity, actual_intensity, outcome_efficiency_delta (computed next day), outcome_subjective (from check-in if available)
- [ ] Migration adds fields without breaking existing plans
- [ ] State transitions: SCHEDULED → COMPLETED, SCHEDULED → SKIPPED, SCHEDULED → MODIFIED_BY_ATHLETE (planned easy, did quality)
- [ ] `InsightLog` model records every intelligence insight: timestamp, athlete_id, rule_id, mode (inform/suggest/flag), message, data_cited, athlete_response (if any)
- [ ] When Strava sync detects a completed workout that differs from the plan (different type, different pace zone, different distance), automatically populate self-regulation fields

### 2C. Daily Intelligence Engine

**What:** NOT a rules engine that swaps workouts. An intelligence engine that surfaces information, learns from outcomes, and intervenes ONLY at extremes. The athlete decides. The system learns.

**Design Principle (from founder's real training):**
The founder jumped from 51→60 miles, ran 20mi/2300ft Sunday, every metric said "deeply fatigued." Tuesday: planned 15 easy, felt amazing, ran 10 at MP. Wednesday: sore, self-regulated to 8 slow. Result: massive efficiency and neuromuscular breakthroughs. The old rules engine would have swapped Tuesday's quality session and prevented the breakthrough. **Fatigue is the stimulus. Supercompensation requires overreach. The system must never prevent a breakthrough by "protecting" the athlete from productive stress.**

**Three operating modes:**

**Mode 1: INFORM (default for all athletes)**
Surface data the athlete can't easily hold in their head. No workout swapping.
- "Your load is up 18% this week. Sunday's 20-miler was your biggest session in 8 weeks."
- "Readiness signal is low. Efficiency trend over last 3 sessions: [X]."
- "Your last 3 post-load-spike weeks produced efficiency gains of [Y]."
- The athlete sees this and makes their own call.

**Mode 2: SUGGEST (earned, when the system has studied the individual)**
The system has enough outcome data to surface PERSONAL patterns.
- "Last time you had a load spike like this (Week 12, Oct), you responded well to quality on day 3 followed by 2 easy days."
- "When you've overridden easy → quality after big load weeks, the outcome has been positive 7 of 9 times. You self-regulate well here."
- Still no swapping. Context from the athlete's own history.

**Mode 3: INTERVENE (extreme, sustained, unmistakable)**
Flags — NOT overrides. Fires only on sustained trajectories, not single-day signals:
- Efficiency declining for 3+ WEEKS (not days)
- Completion rate dropping (athlete is missing sessions, not choosing to modify them)
- Subjective feel consistently negative (sustained pattern, not one sore day)
- AND the athlete hasn't acknowledged it
- Even then: "I'm seeing a 3-week declining trend. This looks different from your normal loading patterns. Worth reviewing?"

**Intelligence rules (inform/suggest/flag — NOT swap):**

1. **Load spike detected** → INFORM: "Volume up X% this week. Your [biggest/most intense] session was [Y]."
2. **Post-workout delta** → LOG + LEARN: Athlete planned easy, did quality. Log the override. Track outcome. Over time: learn self-regulation patterns.
3. **Efficiency breakthrough detected** → INFORM: "Your efficiency jumped X% — [context: post-load-spike, post-recovery, etc.]"
4. **Workout faster than target + lower HR** → INFORM: "You ran 15s/mi faster than target with lower HR. Pace zones may need updating." → Offer one-tap pace recalculation.
5. **Sustained negative efficiency trend (3+ weeks)** → FLAG: "Efficiency has been declining for [N] weeks. This is longer than your typical post-load dips."
6. **Sustained missed sessions (pattern, not one-off)** → ASK: "I noticed 3 missed sessions in 2 weeks — injury, life, or strategic? This helps me learn your patterns."
7. **Readiness consistently high + athlete not increasing** → SUGGEST: "Your readiness has been high for 2 weeks. Your body may be ready for more. [Context from athlete's history if available.]"

**Supercompensation Study (background, same pattern as HRV correlation):**
- Collect: every load spike, fatigue signal, athlete override, outcome
- Study: what precedes breakthroughs for THIS athlete? What precedes injuries/plateaus?
- Report: "Your breakthroughs tend to follow 2-3 weeks of progressive overload. Your injury risk increases when overload extends beyond 4 weeks without recovery."
- Act (eventually): only when the system can distinguish "productive overreach" from "injury trajectory" for THIS individual

**Self-regulation tracking:**
- Every time planned ≠ actual, log the delta (planned workout type, actual workout type, actual pace, actual distance)
- Log the outcome (efficiency delta next day, subjective feel next day if available)
- Over time: "When you override easy → quality after a load spike, outcomes are positive X% of the time"
- This IS the N=1 intelligence. This is what makes the subscription irreplaceable.

**Acceptance Criteria:**
- [ ] `daily_intelligence.py` implements all 7 intelligence rules
- [ ] Default mode is INFORM — no workout swapping without explicit athlete opt-in
- [ ] INTERVENE mode fires only on sustained (3+ week) negative trends, never single-day signals
- [ ] Each rule produces a structured `IntelligenceInsight`: rule_id, mode (inform/suggest/flag), message, data_cited
- [ ] Self-regulation tracking: logs every planned-vs-actual delta with outcome
- [ ] Supercompensation study: background process analyzing load-spike → outcome patterns per athlete
- [ ] Rules tested against founder's real training scenario (the 51→60 week MUST NOT produce a workout swap)
- [ ] Scenario tests include: load spike + athlete feels great (system should NOT intervene), sustained decline (system SHOULD flag), athlete self-regulating competently (system should learn, not override)
- [ ] All insights logged in `InsightLog` with full audit trail
- [ ] Feature flags for each rule and each mode transition
- [ ] **Rollback capability:** Each intelligence rule has an independent feature flag (on/off per rule, per mode). If a rule produces bad insights overnight, it can be killed without affecting other rules. `InsightLog` allows post-hoc review of all insights generated by a rule before it was disabled. No "undo" needed because INFORM mode doesn't modify plans — but FLAG mode insights that triggered athlete notifications need a "correction" notification path.

### 2D. Morning Intelligence & Notification

**What:** Celery beat task runs at 5 AM athlete local time. Computes readiness, runs intelligence rules, surfaces insights. Does NOT modify the plan by default.

**⚠️ Timezone implementation note:** "5 AM athlete local time" means the Celery beat task runs frequently (e.g., every 15 minutes) and checks which athletes are at their 5 AM window. NOT one global run. Athlete timezone stored in profile (derived from Strava timezone or explicit setting). Builder must handle DST transitions gracefully.

**Acceptance Criteria:**
- [ ] `daily_intelligence_task` runs on schedule for all athletes with active plans
- [ ] Computes readiness → runs intelligence rules → generates insights → logs everything
- [ ] Insight visible on today's calendar card: "Load up 18% this week. Your biggest session was Sunday's 20-miler."
- [ ] No insight = no noise (don't notify "everything is fine" every day)
- [ ] FLAG-level insights (sustained negative trends) get prominent display + optional push notification
- [ ] INFORM-level insights are visible but not intrusive
- [ ] Plan is NOT modified — athlete sees their planned workout + today's intelligence alongside it
- [ ] Athlete can choose to modify their workout based on the insight (logged as self-regulation data)
- [ ] Push notification support for FLAG-level only (not blocking launch)
- [ ] Task handles errors gracefully (one athlete's failure doesn't block others)

### 2E. No-Race-Planned Modes

**What:** Two rule-driven modes for athletes between race cycles.

**Maintenance Mode:**
- Consistent volume at ~80% of last build's peak
- Easy runs + strides + 1 modest quality session per week
- Readiness monitoring (flag if efficiency drops)

**Base Building Mode:**
- Progressive volume increase (10% / 3-4 weeks, cutback)
- Strides + hills for neuromuscular activation
- No hard threshold/interval work

**Acceptance Criteria:**
- [ ] Athlete can select mode when no race is scheduled
- [ ] Each mode generates a rolling 4-week plan that refreshes weekly
- [ ] Volume, quality sessions, and structure match mode definition
- [ ] Adaptation engine (2C) applies to these plans identically
- [ ] Transition from no-race mode to race plan is seamless (base building feeds into race plan Phase 1)

---

## Phase 3: Contextual Coach Narratives

**Goal:** The coach explains adaptation decisions and eventually provides genuinely contextual workout notes — never templates, never repeated.
**Dependencies:** Phase 2 running and creating context. Coach narration accuracy gated by parallel trust track.

### 3A. Adaptation Narration

**What:** After the rules engine applies an adaptation, the coach generates a contextual explanation.

**Acceptance Criteria:**
- [ ] Every adaptation gets a 2-3 sentence narration citing specific data (efficiency %, TSB, completion rate)
- [ ] Narration stored in `AdaptationLog.narrative` and `PlannedWorkout.coach_notes`
- [ ] Uses Gemini Flash with tightly scoped prompt (adaptation rule + readiness components + recent data)
- [ ] Coach does NOT decide the adaptation — only explains the deterministic decision
- [ ] Narration accuracy scored against rules engine ground truth (parallel trust track)
- [ ] Narrations that contradict the rules engine decision are flagged and logged for review
- [ ] If narration quality is below threshold, show only the structured reason (no AI text)

### 3B. Contextual Workout Narratives

**Gate:** Narration accuracy > 90% sustained for 4 weeks (measured in parallel trust track).

**What:** Each workout gets a contextual note that is never the same twice. Aware of plan phase, progression position, last session performance, readiness, what's coming next.

**Acceptance Criteria:**
- [ ] Generated fresh each day, not cached or templated
- [ ] References specific recent data: "You crushed last week's 3x10" not "Threshold builds lactate clearance"
- [ ] If the coach can't generate something genuinely contextual, show nothing
- [ ] Founder review of first 50 narratives before general rollout
- [ ] Kill switch: if quality degrades, narratives are suppressed (silence > bad narrative)

### 3C. N=1 Personalized Insights

**Gate:** Intelligence Bank has 3+ months of data for the athlete AND correlation engine has statistically significant findings.

**What:** Insights derived from the athlete's own data patterns.

**Acceptance Criteria:**
- [ ] Only surfaced when backed by statistical significance (p < 0.05, |r| >= 0.3, n >= 10)
- [ ] Examples: "YOUR threshold sessions produce efficiency spikes 48hrs later" / "YOUR efficiency peaks in weeks above 18mi long runs"
- [ ] Clearly labeled as data-derived, not opinion
- [ ] Founder review before rollout

---

## Phase 4: 50K Ultra (New Primitives)

**Goal:** Extend the system to 50K with genuinely new training concepts.
**Dependencies:** Phases 1-2 complete.

### New Concepts Required

- **Back-to-back long runs** — new workout type, new scheduling logic
- **Time-on-feet metric** — `target_duration_hours` field on `PlannedWorkout`
- **RPE-based intensity** — training zones by RPE, not pace
- **Nutrition as training** — `nutrition_plan` JSONB field on `PlannedWorkout`
- **Strength training integration** — `strength` workout type

**Acceptance Criteria:**
- [ ] All new model fields added with migration
- [ ] Back-to-back long runs scheduled correctly (Saturday + Sunday)
- [ ] 50K plan uses time-on-feet as primary progression metric
- [ ] RPE zones replace pace zones for appropriate workouts
- [ ] Nutrition prescriptions attached to long runs
- [ ] Strength sessions integrated into weekly structure
- [ ] Adaptation engine handles 50K-specific workout types
- [ ] N=1 overrides apply (experienced ultra runners have established patterns)

---

## Phase Summary

| Phase | What | Gate to Start |
|-------|------|---------------|
| **1** | World-class plans: marathon → half → 10K → 5K. N=1 overrides. Paces everywhere. Taper democratization. | None — start immediately |
| **2** | Daily adaptation engine: readiness score, rules engine, workout state machine, nightly replan, no-race modes. | Phase 1 substantially complete |
| **3** | Contextual coach narratives: adaptation narration → workout notes → N=1 insights. | Phase 2 running + coach trust milestones met |
| **4** | 50K ultra: new primitives. | Phases 1-2 complete |
| **Parallel** | Coach trust: test harness, HRV study, narration scoring, advisory mode, autonomy. | Starts Day 1, milestones gated by measured accuracy |

---

## Monetization Mapping

| Tier | What They Get | Plan Features | Adaptation |
|------|--------------|---------------|------------|
| **Free** | RPI calculator, basic plan outline | Phase structure, effort descriptions, general guidance | None |
| **One-time ($5)** | Complete race plan | Calculated paces, proper periodization, workout structure | None (static) |
| **Guided Self-Coaching ($15/mo)** | The coached experience | N=1 plan parameters, daily adaptation, readiness score, completion tracking, intelligence bank | Full daily adaptation |
| **Premium ($25/mo)** | Everything + conversational coach | All above + contextual narratives, coach advisory mode, multi-race planning, recovery integration, pre-race fingerprinting, Intelligence Bank dashboard | Adaptation + coach proposals |

---

*This plan represents the shared vision.*
*No code should be written that contradicts the principles at the top of this document.*
*Acceptance criteria are pass/fail. If a criterion is not met, the phase is not complete.*
