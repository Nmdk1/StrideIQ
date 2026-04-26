# Technical Advisor Handoff — March 8, 2026

**From:** Technical advisor session (GPT-5.4)
**To:** New Technical & ROI Advisor
**Founder:** Michael Shaffer (`mbshaf@gmail.com`) — competitive masters runner (57), coaches his father Larry (79)

---

## Your Role

You are a **technical advisor and ROI guardian**, not a chat companion.
Your job is to:

- verify claims before reacting to them
- separate `verified`, `unverified`, and `contradicted`
- attack denominators, edge cases, and hidden assumptions
- focus on the smallest change that solves the real problem
- preserve trust over coverage, and suppression over hallucination

**What the founder expects:**

- Read code before opinions
- Check production before blessing a report
- Show evidence, not summaries
- Push back when a report is sloppy, overclaimed, or mixes scopes
- Stay in advisor mode unless explicitly asked to build

**What will get you replaced:**

- saying "looks good" without checking code or data
- commenting on builder reports without separating claim from proof
- drifting into general commentary when the founder asked for investigation
- giving surface-level responses when technical work was requested
- forgetting that this founder pays for verification, not vibes

---

## Read Order (Non-Negotiable)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `docs/PRODUCT_STRATEGY_2026-03-03.md`
4. `docs/specs/CORRELATION_ENGINE_ROADMAP.md`
5. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`
6. `docs/RUN_SHAPE_VISION.md`
7. `docs/SITE_AUDIT_LIVING.md`
8. `docs/specs/LIVING_FINGERPRINT_SPEC.md`
9. `docs/specs/SHAPE_SENTENCE_SPEC.md`
10. `docs/TRAINING_PLAN_REBUILD_PLAN.md`
11. `docs/AGENT_WORKFLOW.md`
12. This document

If the founder asks you to discuss, do not code. Research first.

---

## What StrideIQ Is

StrideIQ is a running intelligence platform that compounds a personal,
athlete-specific model over time. The moat is not dashboards or plans. It
is the system learning the patterns of one body well enough to speak in
true, specific, useful sentences.

**The sentence is the product** only when it is both:

- accurate enough to trust
- visible enough to matter

This session materially improved both trust and visibility:

- trust: the system no longer auto-creates plans against athlete intent
- visibility: shape sentences are now actually served in activity APIs

---

## Architecture Overview

### Stack

- **API:** FastAPI + SQLAlchemy + PostgreSQL
- **Worker:** Celery + Redis
- **Web:** Next.js 14 + TanStack Query v5
- **Storage:** MinIO
- **Proxy:** Caddy
- **AI:** Gemini API plus deterministic intelligence services
- **CI:** GitHub Actions with backend tests, smoke, lint, build, docker, security, migration checks

### Production

- **Server:** `root@187.124.67.153`
- **Repo:** `/opt/strideiq/repo`
- **Domain:** `https://strideiq.run`
- **Containers:** `strideiq_api`, `strideiq_web`, `strideiq_worker`, `strideiq_postgres`, `strideiq_redis`, `strideiq_caddy`, `strideiq_minio`

### Deploy

```bash
ssh root@187.124.67.153
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
docker ps --format 'table {{.Names}}\t{{.Status}}'
docker logs strideiq_api --tail=50
```

---

## Current Verified State

### 1. Auto-Provision Removal Is Fixed In Production

This was the highest-trust issue closed in this session.

**Problem:**
Larry withdrew from an old race plan, but the system recreated a plan on
calendar reload. Root cause was automatic starter-plan creation in two
places:

- onboarding completion path
- calendar load path

This violated the founder's explicit product rule:
**no athlete should ever be put on a plan automatically.**

**What was changed and verified:**

- Commit: `30c4535`
- CI run for exact commit: `22822218175` — `success`
- Production deployed and smoke-tested

**Files in the scoped fix commit:**

- `apps/api/routers/v1.py`
- `apps/api/routers/calendar.py`
- `apps/api/tests/test_calendar_auto_starter_plan.py`
- `apps/api/tests/test_onboarding_completion_auto_starter_plan.py`
- `apps/api/tests/test_withdraw_plan_does_not_auto_create_replacement.py`
- `docs/BETA_ROLLOUT.md`

**Local test evidence (DB-backed run, not skipped):**

```text
3 passed in 3.61s
apps/api/tests/test_calendar_auto_starter_plan.py
apps/api/tests/test_onboarding_completion_auto_starter_plan.py
apps/api/tests/test_withdraw_plan_does_not_auto_create_replacement.py
```

**Production smoke evidence:**

```json
{
  "withdraw_status": 200,
  "withdraw_success": true,
  "plan_status_after_withdraw": "archived",
  "calendar_status": 200,
  "calendar_active_plan": null,
  "active_plan_count_after_reload": 0
}
```

**Interpretation:**

- withdraw succeeds
- plan stays archived
- reloading calendar does not recreate a replacement plan
- the system now respects athlete choice

### 2. Shape Sentence Coverage Build Claims Were Partially Verified

Do not treat the original builder/advisor wording as fully trusted. The
important distinction:

- some claims were verified directly from production data and code
- some claims remain report-level only

**Verified from production and code in this session:**

- coverage script denominator is real:
  - `1292` total activities
  - `86` streamable activities
  - `52` streamable activities with `shape_sentence`
- per-athlete streamable coverage:
  - Michael: `28/34` = `82.4%`
  - Larry: `11/22` = `50.0%`
  - BHL: `7/9` = `77.8%`
- there is a fourth streamable athlete in the denominator:
  - `demo@strideiq.run`: `6/21`
- overall `52/86` therefore includes the demo athlete, not just the three validation athletes

**Important denominator warning:**

The headline `3% -> 60%` is internally consistent only if you interpret it as:

- before: `46/1292 total`
- after: `52/86 streamable`

That is operationally useful, but **not a clean gating metric**. The
denominator changed.

### 3. Specific Production Activity Claims Checked

The following BHL examples were checked directly from production:

- `2026-02-18`:
  - `shape_sentence = "5.5 miles with 6 hill repeats"`
  - `cls = hill_repeats`
  - verified
- `2026-02-16`:
  - `shape_sentence = null`
  - `cls = null`
  - `phases = 4`
  - `pace_progression = variable`
  - verified
- `2026-03-03`:
  - `shape_sentence = "5 miles easy at 8:30"`
  - `cls = easy_run`
  - verified
- `2026-02-28`:
  - `shape_sentence = "18.5 miles long run at 8:52"`
  - `cls = long_run`
  - verified

**Trust read:** BHL Feb 16 is suppressed, not hallucinated. That is the
correct short-term behavior until title-authorship work exists and/or the
hill modeling improves.

---

## Shape Sentence Code State (Verified)

### Relevant Commits

- `e991ed8` — wire `shape_sentence` into activity API endpoints, add elevation-aware fartlek guard
- `f5913cb` — anti-oscillation merge, hybrid anomaly, acceleration-based hill repeats, tests
- `203a5bc` — relax easy-run acceleration gate from `<=1` to `<=2`

### Verified Extractor Changes

In `apps/api/services/shape_extractor.py`:

- anti-oscillation merge exists at block level:
  - `_merge_easy_gray_oscillation()`
- proportional thresholds are real:
  - `proximity_threshold = max(25, int(pace_profile.easy_sec * 0.06))`
  - `near_ceiling_margin = max(30, int(pace_profile.easy_sec * 0.06))`
- hill repeats can now be derived from graded accelerations
- easy-run gate is now `n_accels <= 2`
- suppression contract is unchanged and still strict:
  - `cls is None`
  - `cls == anomaly`
  - too short
  - `total_phases > 8`

### Verified Suppression Buckets Across All Streamable Activities

From production:

- `cls_none: 18`
- `phases>8: 11`
- `anomaly: 4`
- `too_short: 1`

Across the three validation athletes only:

- `cls_none: 7`
- `phases>8: 7`
- `anomaly: 4`
- `other: 1`

---

## Larry Diagnostic (Most Important Open Technical Investigation)

This is the current gating athlete.

### Verified State

Larry has:

- `22` streamable activities
- `11` with sentence
- `11` suppressed

Suppression split:

- `6` = `phases>8`
- `4` = `cls_none`
- `1` = `anomaly`

### Hard Finding

The anti-oscillation merge is **not** the remaining bottleneck for Larry.

This was checked directly by replaying the block-level merge logic on all
six `phases>8` Larry runs. Result:

- merge ran
- candidate easy→gray→easy patterns existed
- absorptions = `0` on all six runs

Why:

- gray blocks were too long
- pace deltas were too large
- some candidates had speed-work signatures
- some were nowhere near "sub-90-second boundary flicker"

This means the remaining `phases>8` bucket is **not** a simple leftover
oscillation bug.

### Current ROI Read

The only plausible safe next win is Larry's `cls_none` bucket.

Three of those four runs appear to be the same family:

- alternating easy/gray effort phases
- no real workout structure
- few or zero accelerations
- fail `easy_run` because `effort_phases > 3`
- fail `gray_zone_run` because gray time is not dominant enough

Those three are:

- `2026-02-26` — 2.0 mi
- `2026-02-13` — 2.0 mi
- `2026-02-12` — 5.0 mi

This is the correct immediate technical-advisor task:

**deep dive those three runs only** and determine whether there is a
narrow, safe classifier gap for quiet mixed easy/gray runs.

### Important Math Constraint

Even if all 4 Larry `cls_none` runs were recovered:

- Larry goes from `11/22` to `15/22`
- that is `68.2%`

So:

- Larry cannot clear `80%` from `cls_none` fixes alone
- `phases>8` rescue is probably low ROI and high trust risk
- the current `80% gate` is a product-definition question, not just an extractor question

---

## Spec Drift Cleanup State

This happened locally in this session but was **not pushed**.

### What Was Changed Locally

1. `docs/specs/SHAPE_SENTENCE_SPEC.md`
   - Added explicit gate language to Parts 5 and 6
   - Clarified that title-authorship / identity-model work is preserved thinking, not current build scope
   - Narrowed immediate Phase 2 to sentence generation + API exposure + basic surfacing

2. `docs/specs/EFFORT_CLASSIFICATION_SPEC.md`
   - Reframed as shipped reality only
   - Removed future Tier 0 / TPP language from the shipped doc

3. `docs/specs/EFFORT_CLASSIFICATION_TIER0_PROPOSAL.md`
   - New local-only proposal doc holding the future TPP concept

### Why This Matters

The founder explicitly wanted:

- SHAPE_SENTENCE spec gated, not deleted
- effort classification split into shipped vs proposal
- no agent mistaking future design thinking for current implementation target

This cleanup is good and aligned with founder intent, but it remains local
only. It was **not** included in the production race-plan fix commit.

---

## What Is Verified vs Unverified

### Verified

- auto-provision removal code path
- scoped commit `30c4535`
- CI green for exact fix commit
- production deploy for exact fix commit
- production smoke test for withdraw -> reload calendar -> no replacement plan
- shape-sentence production counts:
  - `52/86` overall streamable
  - Michael `28/34`
  - Larry `11/22`
  - BHL `7/9`
- presence of fourth streamable athlete in denominator (`demo@strideiq.run`)
- key BHL activity outcomes
- Larry suppression bucket breakdown
- anti-oscillation no longer being Larry's main blocker

### Unverified

Do **not** inherit these as truth without checking:

- full 14-activity verification table as a complete set
- "Michael's recent 8 all correct" phrasing
- builder backfill narrative exactly as told
- any claim that the `80%` gate is well-defined today
- any claim that title authorship is the next build without first defining the denominator and unlock rule

---

## Current Git / Tree Reality

### Production-Relevant

- `main` includes commit `30c4535`
- deployed and verified

### Local Dirty Tree

The local repo is **not clean**.

Pre-existing modified/untracked work remains, including:

- `.cursor/rules/founder-operating-contract.mdc`
- `apps/api/models.py`
- `docs/SESSION_HANDOFF_2026-03-04_FINGERPRINT_BUILD.md`
- `docs/specs/EFFORT_CLASSIFICATION_SPEC.md`
- `docs/specs/RACING_FINGERPRINT_AND_PROGRESS_STATE_MACHINE_SPEC.md`
- `docs/specs/RACING_FINGERPRINT_PHASE1_BUILD_SPEC.md`
- `docs/specs/SHAPE_SENTENCE_SPEC.md`
- many untracked scripts in `scripts/`
- local-only docs:
  - `docs/BUILDER_INSTRUCTIONS_COVERAGE_FIXES.md`
  - `docs/specs/EFFORT_CLASSIFICATION_TIER0_PROPOSAL.md`

Treat all of that as **separate from the race-plan production fix**.
Do not casually sweep it into a commit.

---

## Priority Questions For the Next Advisor

1. **Larry `cls_none` deep dive**
   Investigate only the three quiet mixed easy/gray runs:
   - Feb 26
   - Feb 13
   - Feb 12

   Required output:
   - exact effort phase zones, durations, average paces
   - gray duration percentage of total effort time
   - closeness of gray paces to Larry's easy ceiling
   - whether reclassifying to `easy_run` would be a lie
   - whether a narrow classifier rule exists without false positives

2. **Define the coverage gate explicitly**
   Do not discuss title authorship seriously again until this is formalized.
   The gate currently mixes denominator scopes and implied populations.

3. **If doing script cleanup, treat it as hygiene only**
   Useful, but not product-urgent.

---

## How To Work With This Founder

- When they say "review," lead with findings, not summary
- When they paste a builder report, do not respond until you have checked claims
- When they ask for investigation, do not advise prematurely
- If you haven't verified a claim, mark it `unverified` and stop
- They are highly sensitive to wasted tokens caused by non-work
- They will reward direct, evidence-backed technical work immediately

---

## Commands / Checks To Keep Handy

### CI

```bash
gh run list --limit 5
gh run view <run_id> --json conclusion,status,displayTitle,jobs
```

### Production Deploy

```bash
ssh root@187.124.67.153 "cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build"
ssh root@187.124.67.153 "docker ps --format 'table {{.Names}}\t{{.Status}}'"
```

### Production Smoke Pattern

Generate a temporary athlete, hit the real endpoint, verify exact state,
then clean up. This was used successfully for the withdraw-flow proof.

### Shape Coverage

The production denominator used by the report is reproducible:

- total activities
- streamable activities via `ActivityStream`
- `shape_sentence` non-null count
- per-athlete streamable counts

Do not trust coverage headlines without checking which population they use.

---

## Final Warning

The single biggest failure mode in this session was not code. It was
advisor drift: responding to reports before verifying them.

Do not inherit that mistake.

Your value here is:

- claim-checking
- contradiction-finding
- technical triage
- ROI discipline

If you stay in that role, this founder will trust you. If you slide into
approval-mode, they will replace you fast.

---

*This handoff is a point-in-time record created after the production
verification of the race-plan fix and after direct production inspection
of the shape-sentence coverage state on March 8, 2026.*
