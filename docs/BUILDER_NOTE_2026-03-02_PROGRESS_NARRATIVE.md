# Builder Note — Progress Page Redesign

**Date:** March 2, 2026
**Spec:** `docs/specs/PROGRESS_NARRATIVE_SPEC_V1.md`
**Design principle:** `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` Part 1
**Priority:** High — this page converts free users to subscribers

---

## Objective

Replace the current progress page (12 disjointed text cards) with a visual
story told by a coach. Every section follows the design principle: visual
anchor catches the eye, narrative bridge below teaches the athlete to read
the visual.

---

## Scope

### In scope

1. **New endpoint:** `GET /v1/progress/narrative`
   - Phase 1: deterministic data assembly (sparklines, bar data, gauges, correlation series)
   - Phase 2: LLM narrative synthesis (coach voice for each section)
   - Redis caching (30min TTL narrative, longer for visual data)
   - Graceful fallback: visuals + deterministic labels when LLM fails

2. **Frontend visual components:**
   - Sparkline (fitness arc, efficiency trend)
   - Bar chart (weekly volume)
   - Health strip (sleep, HRV, RHR, stress indicators)
   - Gauge (readiness, form position)
   - Paired sparkline (N=1 correlation visual)
   - Capability bars (race time projections, no-race variant)
   - Completion ring (consistency %)
   - Stat highlight (PB callout)

3. **Frontend narrative layout:**
   - Flowing document with visual → narrative rhythm
   - Not cards. Not a grid.
   - Interactive visuals (hover/tap for values)

4. **Looking Ahead — two variants:**
   - Race on calendar: readiness gauge + scenario framing
   - No race: capability trajectory bars + trend narrative

5. **Athlete feedback:** 3-button footer logged to `NarrativeFeedback` table

6. **New Alembic migration:** `progress_narrative_001`

### Out of scope

- Full PMC chart (lives on Training Load page)
- Full efficiency chart (lives on Analytics page)
- PB table as standalone section (woven into chapters if relevant)
- Runner profile section (belongs on settings/profile)

---

## Data Sources (all existing — no new services)

| Source | What it provides | Visual it feeds |
|--------|-----------------|-----------------|
| `TrainingLoadCalculator` | CTL history, ATL, TSB, zone | Verdict sparkline, form gauge |
| `get_efficiency_trends()` | Efficiency time series | Efficiency sparkline chapter |
| `get_confirmed_correlations()` | N=1 patterns with time series | Paired sparkline |
| `get_weekly_volume()` | Weekly mileage over 8 weeks | Volume bar chart chapter |
| `get_wellness_trends()` | Sleep, HRV, RHR, stress, motivation | Health strip chapter, dot plot |
| `get_recovery_status()` | Durability, injury risk, readiness | Readiness gauge |
| `get_race_predictions()` | Finish time estimates by distance | Capability bars |
| `TrainingPlan` | Race info, phase | Looking Ahead variant selection |
| `GarminDay` | Device health metrics | Health strip data |
| `DailyCheckin` | Checkin count, wellness scores | Dot plot, patterns_forming indicator |
| `calculate_consistency_index()` | Completion % | Completion ring |
| `PersonalBest` | Recent PBs | Stat highlight chapter |
| `Activity` | Recent runs | Evidence in narratives |

---

## Files to change

| File | Change |
|------|--------|
| `apps/api/routers/progress.py` | New `get_progress_narrative()` endpoint + response models |
| `apps/api/models.py` | `NarrativeFeedback` model |
| `apps/api/alembic/versions/progress_narrative_001_*.py` | Migration |
| `apps/web/app/progress/page.tsx` | Replace card grid with visual + narrative layout |
| `apps/web/lib/hooks/queries/progress.ts` | New `useProgressNarrative()` hook + types |
| `apps/web/components/progress/` | New visual components (sparkline, bar chart, gauge, etc.) |
| `docs/SITE_AUDIT_LIVING.md` | Update |

---

## Build Contracts (non-negotiable — from spec)

Read the full "Build Contracts" section in the spec. Summary:

1. **Render independence.** Single endpoint `GET /v1/progress/narrative`.
   Visual data is assembled deterministically (< 500ms), then LLM narrative
   is generated (< 5s total). If LLM fails, response still contains all
   visual data + deterministic fallback text. No two-call split. The frontend
   shows a visual-first skeleton while the call completes.

2. **Latency budget.** Deterministic visuals < 500ms. LLM narrative < 5s.
   Cache hit < 100ms.

3. **Per-act fallback copy.** Every act has a deterministic text fallback
   defined in the spec. When LLM fails, visuals render with factual labels.
   No coaching language, no invented text.

4. **No-race capability grounding.** Trajectory variant uses ONLY times from
   `get_race_predictions()`. No invented projections. If no prediction exists
   for a distance, that bar doesn't render.

5. **N=1 confidence gating.** `emerging` (1-2 confirmations) = "signal to
   watch." `confirmed` (3-5) = "becoming reliable." `strong` (6+) = "your body
   consistently shows." Emerging patterns are NEVER presented as causal claims.
   Validation rejects LLM output that violates this.

## Additional Rules

6. **Every section needs both visual and narrative.** A section without a
   visual anchor is a text wall. A visual without narrative is a pretty chart.

7. **Within narrative: interpretation leads, metrics follow.** The coach voice
   arrives first. Numbers are evidence for what the coach said.

8. **N=1 uniqueness test.** If the pattern callout could appear on a different
   athlete's page, reject it.

9. **Looking Ahead never vanishes.** Race variant or trajectory variant —
   every runner gets a forward-looking section.

10. **All distances in miles.**

---

## Required Tests

1. Endpoint returns valid JSON with all required visual_data + narrative fields
2. Visual data is present even when LLM fails (deterministic fallback)
3. Chapters are suppressed when no interpretation is generated
4. N=1 section suppressed when no confirmed correlations; patterns_forming shown
5. Looking Ahead selects race variant when TrainingPlan has goal_race_date
6. Looking Ahead selects trajectory variant when no race on calendar
7. Feedback endpoint logs to NarrativeFeedback
8. Redis cache hit on second call within TTL
9. Cache invalidated on new activity or checkin
10. All distances in miles
11. Empty states render honest messaging with partial visuals
12. Mobile responsive — visuals scale correctly

---

## Production Smoke Checks (post-deploy)

Run these on the server after deploy. All must pass.

```bash
# 1. Endpoint returns valid response with visual_data + narrative fields
TOKEN=$(...generate token...)
curl -s -H "Authorization: Bearer $TOKEN" \
  https://strideiq.run/v1/progress/narrative | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert 'verdict' in d and d['verdict']['sparkline_data'], 'Missing verdict sparkline'
assert 'chapters' in d and len(d['chapters']) >= 2, 'Too few chapters'
for c in d['chapters']:
    assert c.get('visual_type') and c.get('visual_data'), f'Chapter {c[\"topic\"]} missing visual'
    assert c.get('observation') and c.get('interpretation'), f'Chapter {c[\"topic\"]} missing narrative'
assert 'looking_ahead' in d and d['looking_ahead']['variant'] in ('race','trajectory'), 'Bad looking_ahead'
print('PASS: response shape valid')
"

# 2. Fallback path — LLM failure still returns visual data
# (Temporarily break LLM key or mock failure, then verify)
# visual_data fields must be present, narrative fields contain fallback text
# Restore LLM key after test

# 3. Race vs no-race variant
# Verify looking_ahead.variant matches whether founder has active TrainingPlan
curl -s -H "Authorization: Bearer $TOKEN" \
  https://strideiq.run/v1/progress/narrative | python3 -c "
import sys, json
d = json.load(sys.stdin)
la = d['looking_ahead']
print(f'Variant: {la[\"variant\"]}')
if la['variant'] == 'race':
    assert la['race']['race_name'] and la['race']['days_remaining'] >= 0
    assert len(la['race']['scenarios']) >= 2, 'Need 2+ scenarios'
    print(f'Race: {la[\"race\"][\"race_name\"]} in {la[\"race\"][\"days_remaining\"]}d')
else:
    assert la['trajectory']['capabilities'] and len(la['trajectory']['capabilities']) > 0
    print(f'Trajectory: {len(la[\"trajectory\"][\"capabilities\"])} distances')
print('PASS: looking_ahead variant correct')
"

# 4. Mobile rendering — open on phone browser, verify:
#    - Sparklines visible and not clipped
#    - Bar charts scale to viewport
#    - Touch on visual shows tooltip/value
#    - Narrative text readable line height
#    - No horizontal scroll
```

---

## Evidence Required in Handoff

The builder must provide ALL of the following in the delivery message:

1. **Commit hash(es)** — scoped commits only
2. **Files changed table** — file + one-line description of change
3. **Test output** — full pytest output, total count, 0 failures
4. **Production smoke check output** — paste results of all 4 checks above
5. **Screenshot or recording** — desktop + mobile showing the full page with
   visuals rendering and narrative below
6. **Fallback evidence** — screenshot or log showing visual-only render when
   LLM is unavailable
7. **AC checklist** — every AC from the spec marked with evidence

---

## Mandatory: Site Audit Update

After deploy, update `docs/SITE_AUDIT_LIVING.md`:
- New entry under "Delta Since Last Audit"
- Update "Progress" page description to reflect visual + narrative redesign
- Update `last_updated` date
- Document any new endpoints, models, or migrations added

---

## Acceptance Criteria

See `docs/specs/PROGRESS_NARRATIVE_SPEC_V1.md` AC1-AC14.

**Key gates:**
- Single endpoint, single call (AC1)
- Every section has visual + narrative (AC2)
- Visuals load first, narrative fills in (AC3)
- N=1 is athlete-specific (AC6)
- Looking Ahead adapts to race/no-race (AC7)
- LLM failure = visuals + deterministic labels, not blank page (AC10)
- Visuals are interactive (AC11)
- Page feels like a visual story, not a dashboard or text wall (AC12)
- Tree clean, tests green, production healthy (AC14)
