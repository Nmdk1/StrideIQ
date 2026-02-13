# Session Handoff — February 12, 2026

## Read First: `docs/SESSION_HANDOFF_2026-02-11.md`
That file has deploy procedures, founder principles, and project context. This note covers only what happened today.

---

## Session Summary

Completed Phase 1 of the Training Plan Rebuild. The session had two parts:

1. **Bug fixes** (mechanical): Pace engine didn't recognize `"repetitions"` (plural) or `"long_hmp"`. 7-week plans overflowed because race-specific phase forced to 1 week even when 0 weeks remained. Both fixed and shipped.

2. **Coaching philosophy rework** (the real work): Read all 31 KB files. Discovered the 5K and 10K generators were copying Daniels' periodization (VO2max in build, threshold as support) instead of synthesizing the KB's inverted intensity model (threshold builds the floor, VO2max sharpens on top). Formulated 5 coaching questions, got founder answers establishing a consistent periodization model across all distances, then applied the inverted model in one pass across all four distances.

---

## Current State

- **HEAD:** `0dd0035` on `main`, pushed
- **CI:** Needs verification (repo must be set public temporarily)
- **Tests:** 158 passed, 3 xfailed (pre-existing builder tier limitation), 0 failures
- **Coach contract tests:** 22 passed

---

## Commits This Session (all on `main`)

| Commit | What | Files |
|--------|------|-------|
| `03160bf` | fix: pace engine `"repetitions"` + `"long_hmp"` recognition, 7-week phase overflow guard | `pace_engine.py`, `phase_builder.py` |
| `0dd0035` | refactor: apply inverted intensity model across all 4 distances | `generator.py`, `phase_builder.py`, `plan_validation_helpers.py` |

---

## What Changed (the coaching rework)

### The Inverted Intensity Model (KB Synthesis)

The knowledge base's governing principle — confirmed by founder answers to 5 specific questions:

| Phase | Marathon | Half Marathon | 10K | 5K |
|-------|---------|--------------|-----|-----|
| Base | Strides, hills | Strides, hills | Strides, hills, reps | Strides, hills, reps |
| Build | Threshold + MP intro | Threshold dominant | Threshold dominant | Threshold dominant |
| Race-Specific | MP long runs, T maintenance | HMP long runs, T maintenance, VO2 secondary | VO2max intervals, T maintenance | 5K-pace intervals, goal-pace reps |
| Taper | Maintain intensity, reduce volume | Same | Same | Same |

**Key principle:** LT is the limiting factor for most runners at all distances (Source A). Building the threshold floor first means athletes clear lactate faster between race-specific intervals, making the VO2max phase more productive. This is the opposite of Daniels (who puts intervals early).

### Files Changed

**`phase_builder.py`:**
- 5K Phase 2: "VO2max + Speed" → "Threshold Development", quality_sessions 2→1
- 10K Phase 2: "VO2max + Threshold" → "Threshold Development", quality_sessions 2→1
- Both base phases: added `"repetitions"` to allowed_workouts
- Half marathon and marathon: untouched

**`generator.py`:**
- Base phase (5K/10K): now rotates strides, hills, AND reps (speed on fresh legs)
- Build/threshold phase: unified T-block progression for ALL distances
- Race-specific (5K/10K): both return `"intervals"` (VO2max arrives late)
- 10K secondary quality: `"threshold"` maintenance (not co-dominant complement)
- 10K cutback: simplified to `"strides"`

**`plan_validation_helpers.py`:**
- 5K: removed "I > T" (VO2max dominant), added "T >= I" (threshold dominant)
- 10K: removed "co-dominant ratio < 3.0", added "T >= I" (threshold dominant)

**`workout_scaler.py`:** No changes needed — the architecture was right, only the coaching decisions (when each workout type is called) were wrong.

### The 5 Coaching Questions (Founder Answers)

1. **Does the inverted model apply to 5K and 10K?** Yes. Even at 5K, LT is the limiting factor for most runners. Speed in base, threshold in build, race-specific late.

2. **Is Verde TC/Green the default for all distances?** Green sets the philosophy (conservative, volume-over-intensity). Distance-specific sources govern workout content within that structure.

3. **Where do reps belong in 5K?** Both base (neuromuscular tool-building on fresh legs) and race-specific (practicing the effort pattern under fatigue). Build phase is threshold-only.

4. **Phase 1 defaults reflect KB synthesis, Phase 2 personalizes.** Correct. Phase 1 produces the best possible plan from distance/duration/tier. Phase 2 adds N=1 intelligence.

5. **Threshold primary for 10K?** Yes. 10K structure is closer to half marathon than 5K. Threshold dominant in build, VO2max sharpening in race-specific.

---

## Phase 1 — COMPLETE

All acceptance criteria met for 1A through 1G:
- Validation framework (1A, 1-PRE)
- Pace injection from race data or Strava (1B)
- N=1 athlete plan profile from Strava history (1C)
- Personalized taper from Banister model / observed history (1D)
- Half marathon distance-specific generator (1E)
- 10K distance-specific generator (1F)
- 5K distance-specific generator (1G)
- Coaching philosophy rework: inverted intensity model from KB synthesis

**Note:** The acceptance criteria in `TRAINING_PLAN_REBUILD_PLAN.md` for 1F and 1G still say "co-dominant" and "VO2max dominant" respectively. These are now superseded by the inverted model. The founder approved the change explicitly. The doc should be updated to reflect the new model, but the code and tests are already correct.

---

## NEXT SESSION: Phase 2 — Daily Adaptation Engine

**Read:** `docs/TRAINING_PLAN_REBUILD_PLAN.md` sections starting at "Phase 2: Daily Adaptation Engine"

**Start with:** 2-PRE (Training Logic Scenario Framework). Build the test framework BEFORE writing intelligence code. The golden scenario (founder's 51→60 mile week) is test #1 and must pass.

**Phase 2 subphases:**
- 2-PRE: Scenario test framework (25+ scenarios)
- 2A: Readiness score (composite signal, not rule)
- 2B: Adaptation rules engine (7 intelligence rules)
- 2C: Self-regulation logging (planned ≠ actual → track outcomes)
- 2D: Nightly replan task (5 AM local time)
- 2E: Coach narration of adaptations (Gemini Flash)

**Key architecture decisions for Phase 2:**
- The system INFORMS, the athlete DECIDES (default mode)
- Per-athlete thresholds, not hardcoded constants
- HRV and sleep excluded from readiness until correlation engine proves individual direction
- Conservative cold-start defaults (system almost never intervenes for new athletes)
- Self-regulation is first-class data, not non-compliance

---

## Untracked Files (not committed, intentional)
```
 M docs/SESSION_HANDOFF_2026-02-08.md
?? .github/scripts/
?? apps/api/coverage.xml
?? docs/P0_1_PRE_MERGE_PACKAGE.md
?? docs/SESSION_HANDOFF_2026-02-11.md
?? docs/SESSION_HANDOFF_2026-02-12.md
```
