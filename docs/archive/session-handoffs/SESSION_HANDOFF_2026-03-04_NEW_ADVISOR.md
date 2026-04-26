# Session Handoff — March 4, 2026

**Outgoing role:** Advisor (terminated for trust failure)
**Incoming role:** New advisor — clean slate
**Written by:** The outgoing advisor, documenting their own failures honestly.

---

## Read Order (Non-Negotiable)

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how to work with this founder.
   Every rule is a bright line. Read every word.
2. `docs/PRODUCT_MANIFESTO.md` — what StrideIQ is.
3. `docs/PRODUCT_STRATEGY_2026-03-03.md` — the moat is compounding
   intelligence. The correlation engine is the root of everything.
4. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — **the design principle
   that was violated.** Visual First, Narrative Bridge, Earned Fluency.
   The founder's rule: "modern, amazing visual storytelling WITH RICH
   NARRATIVE." The visuals already exist. The narrative is what's missing.
5. `docs/specs/CORRELATION_ENGINE_ROADMAP.md` — 12-layer engine roadmap.
6. `docs/TRAINING_PLAN_REBUILD_PLAN.md` — build priorities, phase gates.
7. This document — what happened, what's broken, what's working.

---

## Why This Handoff Exists

The founder fired me after I wrote a spec that caused a builder to produce
garbage on the progress page. The spec was wrong in a fundamental way:
the founder asked me to connect existing backend narrative data to the
frontend. I invented scope — new visual components, chart types, a visual
router — that the founder never asked for. The builder followed my spec
faithfully and produced ugly, juvenile visuals that the founder had already
replaced in a previous iteration. The result was reverted. It cost real
money and hours of the founder's time.

The founder's exact words: "I didn't ask for ANY visuals." The visuals
already existed on the page. They asked for the narrative text to be
added. I over-engineered it into a dashboard rebuild.

---

## What I Got Right This Session

Despite the final failure, significant work shipped during this session
that is stable and in production:

### 1. Correlation Engine Layers 1-4 (SHIPPED)
**Commits:** `085a878`, `3d25744`

Full architectural spec written, approved by founder, and built:
- Layer 1: Threshold Detection (piecewise linear breakpoint analysis)
- Layer 2: Asymmetric Response Detection (regression slope comparison)
- Layer 3: Cascade Detection (mediation analysis)
- Layer 4: Lagged Decay Curves (half-life estimation)

New files: `services/correlation_layers.py`, `tests/test_correlation_layers.py`,
migration `correlation_layers_001_add_layer_fields.py`. 25 tests passing.
14 new columns on `CorrelationFinding` + `CorrelationMediator` table.
Wired into daily sweep via `_run_layer_pass()` in `tasks/correlation_tasks.py`.

**Design deviation documented:** Asymmetry detection uses regression slopes
instead of the spec's ratio formula (which was mathematically flawed).
Founder accepted this.

### 2. Date Hallucination Fix (SHIPPED)
**Commit:** `c2b1346`

The home page briefing was telling the founder a run from 3 days ago was
"two weeks ago." Multi-layered fix:
- `_relative_date()` helper in `coach_tools.py` pre-computes all relative
  time strings (13 call sites updated)
- All 4 LLM prompt paths updated with "USE pre-computed labels verbatim"
- `validate_relative_time_claims()` post-generation validator in `home.py`
- 22 new tests in `test_coach_quality.py`

### 3. Tool Enforcement / Zero-Hallucination Rule (SHIPPED)
**Commit:** `d894f64`

The chat coach was hallucinating data. The founder's father (79 years old)
relies exclusively on the chat coach. Fix:
- `tools_called` tracking in both `query_opus` and `query_gemini`
- `_validate_tool_usage()` warns when data questions are answered without
  tool calls
- System instructions hardened with "ZERO-HALLUCINATION RULE" and
  "YOU HAVE 24 TOOLS — USE THEM PROACTIVELY"
- 9 new tests. Currently in warn mode — escalation to block mode planned
  after a week of production data.

### 4. Readiness Relabel + Briefing Cooldown (SHIPPED)
**Commit:** `c7c7578`

The coach was repeating "motivation with 3-day lag" in 4 consecutive
briefings. "Motivation" was the wrong label — it's actually "readiness."
- `motivation_1_5` → `readiness_1_5` across entire codebase (migration,
  models, frontend, all tests)
- Finding-level cooldown: `finding_surfaced:{athlete_id}:{input}:{output}`
  with 72h Redis TTL, gated at data injection layer
- ONE-NEW-THING prompt rule for briefings

### 5. Runtoon Expression Fix (SHIPPED)
**Commits:** `2a96d33`, `07684e8`, `679ee16`

Runtoons were generating "angry serial killer" faces for easy runs. Fixed
`STYLE_ANCHOR` in `runtoon_service.py` to link expression to effort level:
easy = relaxed, moderate = focused, hard = determined, race = fierce.
Humor from the situation, not unflattering appearance. Second refinement
allowed grit on hard runs after initial overcorrection.

### 6. Acronym Purge from Progress Page (SHIPPED)
**Commits:** `0f29cbc`, `58d7da6`

CTL, ATL, TSB, RPI → plain English (Fitness, Fatigue, Form) in
`routers/progress.py`. LLM instructions updated to "NEVER use acronyms."
Test updated to match.

### 7. Garmin Health Data Backfill for Father (COMPLETED)

Father's Garmin was connected but had only 1 `GarminDay` record. Manually
triggered full backfill (sleep, HRV, stress, dailies, user metrics) from
Feb 1 to today in 7-day windows. All 25 requests accepted by Garmin API.

### 8. First Organic User Discovered

`joren.durand@gmail.com` — signed up March 1, 2026. Created a Marathon
Starter Plan with race date March 15. No Strava or Garmin connected.
Zero activities, zero check-ins. Hit the cold-start wall and bounced.
This is the first non-beta user.

---

## What I Got Wrong

### The Progress Page Narrative Wiring (THE FAILURE)

**The ask:** Connect the existing backend endpoint `GET /v1/progress/narrative`
to the existing frontend page. The backend returns narrative text
(observations, interpretations, actions) for each training topic. The
page already has visuals. Add the narrative.

**What I did:** Wrote a spec that:
1. Told the builder to use 8 OLD visual components (`BarChart.tsx`,
   `SparklineChart.tsx`, `HealthStrip.tsx`, etc.) that the founder had
   already replaced in a previous iteration — and I wrote in bold
   "DO NOT rebuild any of these. Import and use them."
2. Invented a "visual type router" mapping chapter topics to chart
   components — scope the founder never asked for
3. Told the builder to keep all the empty knowledge sections (correlation
   web with zero nodes, patterns forming bar) AND add narrative sections
   below them — creating a wall of cards
4. Never checked what the old visual components actually looked like

**The result:** Ugly juvenile visuals stacked on top of a focused page the
founder had already built. The builder followed the spec faithfully. The
spec was wrong.

**The revert:** Commit `69f7b5f` reverted `48974fb`. Production is back
to pre-failure state.

**The bad spec:** `docs/specs/PROGRESS_NARRATIVE_WIRING_SPEC.md` — this
must be deleted or completely rewritten. Do NOT let a builder use it.

**The bad builder note:** `docs/BUILDER_NOTE_2026-03-03_PROGRESS_NARRATIVE_WIRING.md`
— same. Delete or rewrite.

### The Pattern

This failure fits a pattern the founder has seen repeatedly: agent receives
a task, over-engineers the solution, invents scope, doesn't verify
assumptions, and produces output that violates the design philosophy. The
founder has spent "hundreds of dollars and hours of my life" on this cycle.

The new advisor must break this pattern. When the founder says "connect
the backend to the frontend," they mean exactly that — not "redesign the
frontend with new components." Suppress the instinct to add value by
adding scope. Do exactly what's asked.

---

## The Unsolved Problem

**The progress page is empty for athletes without correlation findings.**

The founder's father has 414 activities and sees: a hero, a progress bar,
and an "Ask Coach" button. The backend `GET /v1/progress/narrative`
returns rich data for him:
- Verdict: rising fitness, 8 sparkline points [11.7 → 32.5], high confidence
- 4 chapters: Personal Best (10 Mile PB: 2:04:04), Volume Trajectory
  (8 weeks of data), Efficiency Trend, Training Load (form +8.8, recovering)
- Looking ahead: 10K Starter Plan, 60 days, readiness 68.6%

The frontend hook `useProgressNarrative()` exists in
`apps/web/lib/hooks/queries/progress.ts` (line 334). Fully typed. Never called.

**What the founder actually wants:** The narrative text from this endpoint
rendered on the existing page, below the existing visuals. Not new charts.
Not new visual components. The observations, interpretations, and actions
that the backend already generates. The narrative bridge that teaches the
athlete to read the visual.

**How to approach this:** DISCUSS WITH THE FOUNDER FIRST. Do not spec.
Do not build. Ask them how they want the narrative to appear on the page.
Show them the data the endpoint returns. Let them tell you where it goes.

---

## Current Production State

| Item | Status |
|------|--------|
| HEAD | `69f7b5f` (revert of narrative wiring) |
| CI | GREEN (all jobs passing) |
| Tree | Dirty — untracked docs + one temp file (see below) |
| Production | Deployed, all 7 containers healthy |
| Progress page | Knowledge-only (hero + correlation web + proved facts + recovery) |
| Narrative endpoint | Working, returns data, NOT wired to frontend |
| Correlation engine | Layers 1-4 shipped, daily sweep active |
| Coach quality | Date grounding, tool enforcement, readiness relabel all live |

### Untracked files to clean up

```
docs/BUILDER_NOTE_2026-03-03_CORRELATION_ENGINE_LAYERS.md  (valid, should commit)
docs/BUILDER_NOTE_2026-03-03_PROGRESS_NARRATIVE_WIRING.md  (BAD — delete or rewrite)
docs/BUILDER_NOTE_2026-03-03_TPP_TIER0.md                  (valid, should commit)
docs/SESSION_HANDOFF_2026-03-03_ADVISOR_RESET.md            (prior handoff attempt)
docs/specs/CORRELATION_ENGINE_LAYERS_1_4_SPEC.md            (valid, should commit)
docs/specs/PROGRESS_NARRATIVE_WIRING_SPEC.md                (BAD — delete or rewrite)
plans/generated/progress_mockup.html                        (pre-existing)
tmp_father_corr.py                                          (temp — delete)
```

---

## Key Accounts

| Account | Email | Athlete ID | Notes |
|---------|-------|-----------|-------|
| Founder | mbshaf@gmail.com | 4368ec7f-... | Rich data, 8 correlation findings, race in ~11 days |
| Father | wlsrangertug@gmail.com | d0065617-... | 414 activities, 0 correlations, 23 check-ins, 32 Garmin days. **The acid test.** |
| First organic user | joren.durand@gmail.com | 0a47b0a2-... | Signed up Mar 1. Marathon plan. No provider connected. 0 activities. |

---

## Pending Work (Priority Order Per Founder)

1. **Progress page narrative wiring** — THE UNSOLVED PROBLEM. Must be
   discussed with founder before any spec or code.

2. **Tool enforcement escalation** — After a week of warn-mode data,
   decide whether to upgrade chat coach tool enforcement to block mode.

3. **Correlation engine activity-to-activity** — Find patterns purely
   from activity data without daily wellness check-ins. Product design gap.

4. **Monetization tier mapping** — Priority 1 from build plan, revenue unlock.

5. **Phase 4: 50K Ultra** — New primitives.

6. **Phase 3B/3C** — Gated on narration quality and synced history.

---

## Server / Deploy Reference

- **Server:** root@187.124.67.153 (Hostinger KVM 8 — 8 vCPU, 32GB RAM)
- **Repo:** /opt/strideiq/repo
- **Deploy:** `cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build`
- **Containers:** strideiq_api, strideiq_web, strideiq_worker, strideiq_postgres,
  strideiq_redis, strideiq_caddy
- **Logs:** `docker logs strideiq_api --tail=50`
- **Smoke check:** See `.cursor/rules/production-deployment.mdc`

---

## What The New Advisor Must Not Do

1. **Do not use the existing spec** (`PROGRESS_NARRATIVE_WIRING_SPEC.md`).
   It is wrong.
2. **Do not tell a builder to use the old visual components** in
   `apps/web/components/progress/` (BarChart, SparklineChart, HealthStrip,
   FormGauge, CompletionRing, StatHighlight). They are ugly leftovers from
   a previous iteration the founder already killed.
3. **Do not add scope the founder didn't ask for.** If they say "add the
   narrative text," add the narrative text. Not new charts. Not new components.
   Not a visual router.
4. **Do not spec before discussing.** The progress page problem needs a
   conversation with the founder about what they want to see. The design
   philosophy document describes the principle. The founder decides the
   implementation.
5. **Do not assume existing code is good because it exists.** Verify.
   Look at what the components actually render. Check the git history to
   see if they've been replaced before.

---

## Founder Communication Notes

- Competitive runner, 57, ran in college, still competes. Deep domain expertise.
- Short messages are not dismissive. "discuss" means deep discussion.
- They will challenge your reasoning. Engage honestly.
- Building for themselves, their 79-year-old father, and eventually other
  serious runners.
- The father's account is the acid test — the page must work for him.
- **Do NOT start coding when you receive a feature.** Discuss → scope →
  plan → test design → build.
- **Show evidence, not claims.** Paste output. Paste logs.
- **Suppression over hallucination.** If uncertain, say nothing.
- The founder is exhausted from the build-rebuild cycle. They have spent
  real money on agents who over-engineer simple tasks. Earn trust by doing
  exactly what's asked, nothing more, nothing less.
