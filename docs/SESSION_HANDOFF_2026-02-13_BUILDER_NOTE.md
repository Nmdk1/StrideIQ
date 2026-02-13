# Builder Note — February 13, 2026

## Read First
- `docs/SESSION_HANDOFF_2026-02-13.md` — full session handoff with detailed scope for Run Shape Intelligence and Strava Write-Back
- `docs/TRAINING_PLAN_REBUILD_PLAN.md` — north star build plan (principles, phases, priorities)

---

## Current State

- **HEAD:** `ae12222` on `main`, pushed and deployed to production
- **Production:** All 6 containers healthy on `strideiq.run`
- **Tests:** 1986 passed, 7 skipped, 119 xfail, 0 failures
- **Tree:** Clean, nothing uncommitted

---

## What Just Shipped

Two commits this session:

| Commit | What |
|--------|------|
| `f55059b` | Athlete Trust Safety Contract: OutputMetricMeta registry, directional whitelist, two-tier fail-closed, 65 contract tests, 11 legacy service comment updates, synced-history eligibility, tier alignment, 3B audit logging |
| `ae12222` | Session handoff doc with Run Shape Intelligence and Strava Write-Back scope |

Phase 3 (3A/3B/3C) code is **delivery-complete**. 3B and 3C are gate-accruing in production. The founder has 2 years of synced Strava data — 3C should unlock for them immediately via the founder rule.

---

## Your Assignment: Run Shape Intelligence

This is the next build priority. Full scope is in `docs/SESSION_HANDOFF_2026-02-13.md` under "Feature: Run Shape Intelligence." Read that section carefully before starting.

### The Vision (short version)

Reinvent how athletes see their run data. Not five separate charts like Garmin. Not decade-old panels like Strava. One unified canvas with composable, toggleable layers (pace, HR, cadence, stride length, elevation fill with grade coloring, workout structure markers). Interactive — hover crosshair, zoom/brush, segment comparison, plan overlay. AI-powered coachable moments pinned to specific timestamps on the chart.

The chart is magic on its own. Runners are data geeks — they love beautiful data. The AI coach layer is the moat — coachable moments, drift detection, plan-vs-execution comparison, cross-run context. No competitor has both.

### Implementation Sequence

1. **Stream ingestion + storage** — new `ActivityStream` model, Strava stream fetch (`GET /activities/{id}/streams`), Garmin stream parsing, backfill pipeline with rate limiting
2. **Coach tool** — `analyze_run_streams` with segment detection, drift analysis, coachable moment identification, plan comparison
3. **Unified canvas** — frontend React component, composable layers, all interactions
4. **Coachable moment rendering** — markers on chart linked to coach findings
5. **Comparison** — run-over-run overlay, segment-vs-segment, plan overlay

### Key Technical Context

**What already exists (don't rebuild these):**
- `ActivitySplit` model (10 fields) in `models.py` line 403 — keep for backward compat
- Strava split/lap ingestion in `tasks/strava_tasks.py` — extend, don't replace
- Garmin lap import in `tasks/garmin_tasks.py`
- `GET /v1/activities/{id}/splits` endpoint
- `SplitsChart.tsx` and `SplitsTable.tsx` (Recharts) — likely needs replacement for the unified canvas
- AI coach with extensive tool system in `services/coach_tools.py`

**Stream data details:**
- Strava: `GET /activities/{id}/streams` returns `time`, `distance`, `heartrate`, `cadence`, `altitude`, `velocity_smooth`, `grade_smooth`, `latlng` at ~1 second resolution
- A 60-min run = ~3,600 data points across ~8 channels = ~30-50KB compressed
- Store in database (new `ActivityStream` table), not object storage. Query simplicity matters at current scale.
- Backfill for founder's 2 years of Strava data is the first test case. Use same rate-limiting pattern as existing split backfill.

**Design requirements (from founder):**
- Modern, not 1990s. Dark background option. Think F1 telemetry, not Excel.
- Smooth curves (rolling average), subtle grid, strong data.
- Elevation as shaded fill underneath (context, not competing signal), with grade color-coding (green/yellow/red for flat/moderate/steep).
- Touch-friendly, responsive. Pinch to zoom on mobile.
- Single chart with toggleable layers — NOT multiple panels.

### Use Cases That Must Work Beautifully
1. Interval session (12x400m) — rep consistency, HR per rep, recovery quality
2. Progressive run — pace stepping down, HR response, cadence/stride showing HOW you got faster
3. Hill repeats — elevation fill with grade, pace dips explained by grade, effort consistency
4. Easy long run — cardiac drift detection, decoupling point
5. Race — negative split execution, pacing vs plan

---

## Rules and Contracts You Must Follow

### Athlete Trust Safety Contract
Read the module docstring in `services/n1_insight_generator.py`. It's 8 clauses. The short version: never emit directional language ("improving," "declining") for ambiguous metrics (any pace/HR efficiency ratio). Only metrics in `DIRECTIONAL_SAFE_METRICS` get directional claims. This applies to ANY new coach output, including `analyze_run_streams`.

### Cursor Rules (auto-loaded)
- `.cursor/rules/build-plan-awareness.mdc` — always-on, shows build priorities and open gates
- `.cursor/rules/athlete-trust-efficiency-contract.mdc` — activates when editing efficiency/correlation/insight files

### Build Plan Principles
Top of `docs/TRAINING_PLAN_REBUILD_PLAN.md`. Do not build features that contradict them. Key ones:
- No metric is assumed directional (Principle 6)
- Coach does not decide adaptation — only explains deterministic decisions
- Suppression over hallucination

---

## Deploy Workflow

After committing and pushing to `main`:

```
ssh root@strideiq.run
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
```

Build takes 3-8 minutes. Verify with `docker ps` (6 containers, all healthy).

Full deploy guide: `_AI_CONTEXT_/OPERATIONS/DEPLOYMENT_WORKFLOW.md`

---

## Lower Priority (do not start yet)

- **Strava Write-Back** — scoped in the handoff doc, build after Run Shape produces content worth pushing. Opt-in, append model, founder is first test user.
- **Monetization** — 1-2 weeks out
- **Phase 4 (50K Ultra)** — not pressing
- **Legacy efficiency polarity migration** — 8 services tracked as debt, not blocking

---

## Founder Context

- The founder is a runner with 2 years of Strava data. They will be the first user testing everything.
- They care deeply about data visualization — runners are scientists, doctors, data geeks. The chart itself must be excellent, not just a vehicle for AI.
- They have high standards for UI/UX. "Both Garmin and Strava charts suck" — direct quote. Build something worthy of 2026, not 2015.
- They have an advisor agent they consult for architectural decisions. Major design choices may go through that review.
- They are non-technical for deployment (provide exact commands, not concepts) but highly technical in product vision and coaching domain knowledge.
