# Session Handoff — February 12, 2026

## Read First
1. `docs/SESSION_HANDOFF_2026-02-08.md` — Full project context, architecture, deploy procedures
2. `docs/SESSION_HANDOFF_2026-02-11.md` — Previous session fixes and current state

The first half was planning (design, philosophy, test strategy). The second half was **building Phase 1-PRE** — the plan validation framework and coach contract test suite.

---

## Session Summary

Deep collaborative design session with the founder. Built the complete phased plan for the Training Plan & Daily Intelligence rebuild. No code — all design, philosophy, and test strategy.

---

## Current State

- **HEAD:** Uncommitted changes on `main` (awaiting founder review before commit)
- **New test files:** `plan_validation_helpers.py`, `test_plan_validation_matrix.py`, `test_coach_contract.py`
- **Deleted:** `apps/api/services/plan_generator_v2.py` (dead code, zero imports)
- **Repo:** Now public
- **Droplet:** Unchanged from Feb 11
- **CI:** Same status as Feb 11 (new tests not yet committed)

### Definitive Test Counts (full suite, Feb 12)

| Suite | Collected | Passed | Failed | xfailed | Skipped |
|-------|-----------|--------|--------|---------|---------|
| Existing tests | 1486 | 1479 | 0 | 0 | 7 |
| Plan validation (new) | 89 | 52 | 22 | 15 | 0 |
| Coach contract (new) | 22 | 22 | 0 | 0 | 0 |
| **Total** | **1597** | **1553** | **22** | **15** | **7** |

- **Zero regressions** in existing 1486 tests
- 22 failures = legitimate generator gaps (Phase 1B fix targets)
- 15 xfails = scope guardrails (12 half/10K/5K + 3 N=1 overrides)
- 7 skips = pre-existing (Stripe webhook + security markers)

---

## Documents Created/Updated This Session

### `docs/TRAINING_PLAN_REBUILD_PLAN.md` (THE BUILD PLAN)
Complete phased plan for the training plan and daily intelligence rebuild. **Read this first when building starts.** Contains:
- 9 guiding principles (non-negotiable)
- Resolved decisions (no revisiting during build)
- Parallel coach trust track with milestones
- Phase 1: World-class plans by distance (1-PRE through 1G)
- Phase 2: Daily Intelligence Engine (2-PRE through 2E)
- Phase 3: Contextual Coach Narratives
- Phase 4: 50K and beyond

### `docs/AGENT_WORKFLOW.md` (HOW TO BUILD)
The build loop, testing pyramid, validation commands, and founder working style. **Read this before writing any code.** Contains:
- 7-step build loop (Research → Test Plan → Tests → Implement → Validate → Commit → CI)
- 6-category testing pyramid (Unit, Integration, Plan Validation, Training Logic, Coach Evaluation, Production Smoke)
- Exact validation commands for backend, frontend, and production
- Task mapping (which tests apply to which phase)
- 12 founder working style rules

---

## Key Design Decisions Made This Session

### 1. "The system INFORMS, the athlete DECIDES" (Principle 4)
Biggest philosophical shift. The daily engine surfaces data and patterns but does NOT swap workouts or override the athlete. Fatigue is a stimulus for adaptation, not a problem to solve. Intervention only on sustained 3+ week negative trajectories.

**Origin:** Founder's real training — jumped from 51→60 miles, 20mi/2300ft Sunday, every metric said "deeply fatigued." Ran 10 at MP Tuesday (felt amazing), 8 slow Wednesday (self-regulated). Result: massive efficiency breakthroughs. The old rules-engine design would have swapped Tuesday's quality session and prevented the breakthrough.

### 2. Self-regulation is first-class data (Principle 7)
When planned ≠ actual (planned 15 easy, did 10 at MP), the delta is logged, the outcome is tracked, and the pattern is studied. Over time: "When you override easy → quality after load spikes, outcomes are positive X% of the time."

### 3. No threshold is assumed universal (Principle 6)
Readiness thresholds are per-athlete parameters with conservative cold-start defaults. The system logs readiness-at-decision + outcome pairs and calibrates to the individual over time. Same pattern as HRV correlation engine.

### 4. Three operating modes: INFORM → SUGGEST → INTERVENE
- INFORM (default): surface data, athlete decides
- SUGGEST (earned): surface personal patterns from athlete's own history
- INTERVENE (extreme only): flag sustained 3+ week negative trends, still not an override

### 5. Plan Validation Framework before plan code (Phase 1-PRE)
The coaching rules from the KB become executable test assertions. Parametrized matrix across every distance × tier × duration. Plans must pass before shipping.

### 6. The Golden Scenario (test #1)
Founder's 51→60 week is the litmus test for the intelligence engine. System must NOT swap a workout. Must inform, log self-regulation, detect breakthrough, correlate with load spike.

### 7. 6-category testing pyramid
Unit → Integration → Plan Validation → Training Logic → Coach LLM Evaluation → Production Smoke. Every task gets a full test plan with founder sign-off before writing tests.

### 8. Mission statement
**"Empowering the athlete to be their own AI-assisted super coach."** N=1. The system is the data analyst of your body — surfacing patterns, correlations, and insights from your own data that you can't hold in your head across 2+ years of training.

---

## Advisor Review (Feb 12, end of session)

An independent advisor agent reviewed all three documents. Key findings incorporated:
1. **Phase 1-PRE scope creep guardrail added** — marathon variants expected to pass, half/10K/5K marked xfail until their tasks deliver
2. **`athlete_plan_profile.py` (1C) flagged as highest-risk** — ADR now mandatory before implementation, with specific questions the ADR must answer
3. **Readiness score cold-start weights specified** — 0.30 efficiency, 0.25 TSB, 0.20 completion, 0.15 recovery days, 0.10 half-life, 0.00 HRV/sleep until proven. Sensitivity analysis required.
4. **5 AM timezone implementation note added** — Celery runs every 15min, checks athlete timezone windows
5. **Coach trust milestone scoring functions defined** — concrete rubrics for narration accuracy, narrative quality, advisory acceptance rate
6. **Rollback strategy added** — per-rule feature flags + correction notification path for bad FLAG-mode insights
7. **KB source references added** — builder must read specific KB documents before writing plan validation assertions

---

## Build Progress (Phase 1-PRE: Plan Validation Framework)

**Status: COMPLETE** — Framework built, tests running, gaps documented.

### Files Created
- `apps/api/tests/plan_validation_helpers.py` — 13 assertion functions encoding KB coaching rules, strict/relaxed threshold modes
- `apps/api/tests/test_plan_validation_matrix.py` — 89 parametrized tests across 21 variants (18 distance/tier/duration + 3 N=1 overrides)

### Test Results (89 tests)
- **22 FAILED** — Marathon variants failing on real coaching logic gaps (exactly what we want)
- **52 PASSED** — Rules the current generator satisfies
- **15 XFAILED** — 12 half/10K/5K + 3 N=1 override variants (scope guardrails)
- **0 regressions** — All 1486 existing tests still pass

### 22 Failures Breakdown (Phase 1B fix targets)
| Test Class | Count | Failing Variants | Root Cause |
|------------|-------|------------------|------------|
| TestPlanValidationMatrix (full validation) | 6 | All 6 marathon variants | Aggregated failures from below |
| TestSourceBLimits | 6 | All 6 marathon variants | T sessions 14-16% (limit 10%), MP exceeds volume %, easy too low |
| TestQualityDayLimit | 3 | mid-6d, mid-12w-6d, high-6d | Secondary quality converts medium_long→threshold, creating 3 quality days |
| TestAlternationRule | 6 | All 6 marathon variants | Now enforced as failure (was warning pre-Issue 2 fix) |
| TestVolumeProgression | 1 | builder-18w-5d | Cutback timing gap in builder tier |

### Rules PASSING (generator gets these right)
- Hard-easy pattern (6/6 pass) — no back-to-back hard days
- Phase rules (6/6 pass) — no threshold in base phase
- Volume progression (5/6 pass) — reasonable week-over-week (builder only gap)
- Taper structure (6/6 pass) — volume reduces properly
- Plan structure (18/18 pass) — all distances have valid structure
- Distance emphasis (6/6 pass) — marathon correctly threshold-dominant

## Coach Contract Test Suite (Parallel Track: Coach Trust)

**Status: COMPLETE** — 22/22 tests passing.

### File Created
- `apps/api/tests/test_coach_contract.py` — Deterministic coach contract tests (zero LLM cost)

### What It Tests (22 tests)
| Category | Tests | Status |
|----------|-------|--------|
| Tone Rules in Prompt | 6 | All pass — acronym ban (tsb/atl/ctl), no fabrication, no internal labels, tool usage, plain English, concise |
| Normalization Pipeline | 6 | All pass — strips fact capsule, response contract, date labels; preserves content; collapses newlines; renames Receipts→Evidence |
| Tool Definitions | 3 | All pass — 23 required tools exist, callable, and count enforced |
| Model Tiering | 3 | All pass — high-stakes detection, injury routing (skip if no classify method), simple query routing (skip if no classify method) |
| Known Regressions | 4 | All pass — no VDOT in prompt, normalization called in chat path, prompt not empty, coaching approach present |

---

## Dead Code Cleanup

- **Deleted:** `apps/api/services/plan_generator_v2.py` (567 lines, zero imports anywhere in codebase)
- Per build plan Phase 1 cleanup task

---

## What's Next (When Founder Returns)

### Immediate (Phase 1A-1B)
1. **Review and commit** the 1-PRE validation framework + coach contract tests + dead code deletion
2. **Phase 1A: Pace injection for standard plans** — `generate_standard()` currently passes `paces=None`. When athlete has race data, inject paces. Quick scoped change.
3. **Phase 1B: Marathon A-Level Quality** — Fix the 5 coaching logic gaps found by validation tests:
   - Cap threshold sessions to ≤10% of weekly volume (workout scaler fix)
   - Enforce alternation rule: MP long weeks have NO threshold
   - Limit quality sessions to max 2 per week (secondary quality logic)
   - Scale MP long runs proportionally to weekly volume
   - Fix builder tier cutback pattern

### Build Order
1-PRE (DONE) → 1A → 1B → 1C (ADR first!) → 1D → 1E/1F/1G

### Follow the Loop
Research → Full Test Plan (founder sign-off) → Tests → Implement → Validate → Commit → CI

---

## Untracked/Modified Files

Same as Feb 11, plus:
- `docs/TRAINING_PLAN_REBUILD_PLAN.md` (new — the build plan)
- `docs/AGENT_WORKFLOW.md` (new — the workflow)
- `docs/SESSION_HANDOFF_2026-02-12.md` (this file)
- `apps/api/tests/plan_validation_helpers.py` (new — 13 validation assertion functions, strict/relaxed modes)
- `apps/api/tests/test_plan_validation_matrix.py` (new — 89 parametrized plan tests incl. 3 N=1 xfails)
- `apps/api/tests/test_coach_contract.py` (new — 22 coach contract tests incl. 23-tool count enforcement)
- `apps/api/services/plan_generator_v2.py` (deleted — dead code)
