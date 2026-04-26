# Builder Note — Progress Page Phase 2

**Date:** March 3, 2026
**Spec:** `docs/specs/PROGRESS_NARRATIVE_SPEC_V1.md`
**Design targets:**
- `docs/references/progress_page_mockup_v2_2026-03-02.html` (primary)
- `docs/references/SUPERSEDED_progress_page_mockup_v1_2026-03-02.html` (Recovery Fingerprint reference)
**Depends on:** Phase 1 (shipped), Correlation Engine Quality Fix (shipped)

---

## Before Your First Tool Call

Read these in order:

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how you work (non-negotiable)
2. `docs/PRODUCT_MANIFESTO.md` — the soul
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — visual doctrine
4. `docs/specs/PROGRESS_NARRATIVE_SPEC_V1.md` — full spec
5. `docs/BUILDER_NOTE_2026-03-03_CORRELATION_ENGINE_QUALITY.md` — what was just fixed and why
6. Both mockup files listed above — open in browser
7. This builder note

---

## Context

Phase 1 shipped three sections: Hero, Correlation Web, What the Data Proved.
The correlation engine quality fix shipped immediately after.

**Three problems remain:**

1. **The page is sparse.** Only 3 sections out of a 7-section vision.
2. **The Correlation Web only shows 1 finding.** The engine only runs for
   `output_metric="efficiency"` on demand. Two years of data, one edge.
   The full correlation space is unexplored.
3. **The CorrelationWeb component has desktop UX issues.** Force simulation
   is unstable with few nodes, edges are hard to select on desktop.

---

## Scope — Four Work Items

### Item 1: Correlation Engine Full Sweep (highest priority)

**Problem:** `analyze_correlations()` defaults to `output_metric="efficiency"`
and only runs on-demand. The founder has ~2 years of data and sees 1 edge.

**Fix:**

1. **New Celery task: `tasks.run_daily_correlation_sweep`**
   - For each athlete with new data in the last 24h:
   - Run `analyze_correlations()` for ALL output metrics:
     `efficiency`, `pace_easy`, `pace_threshold`, `completion`,
     `efficiency_threshold`, `efficiency_race`, `efficiency_trend`,
     `pb_events`, `race_pace`
   - This is 9 calls per athlete, each exploring ~20 input variables
     across lags 0-7.
   - Runs daily, after morning intelligence.

2. **Add to `celerybeat_schedule.py`:**

```python
'daily-correlation-sweep': {
    'task': 'tasks.run_daily_correlation_sweep',
    'schedule': crontab(hour=8, minute=0),  # After morning intelligence
},
```

3. **Immediate backfill:** After deploy, manually trigger the sweep for
   the founder account across all output metrics to populate findings
   from existing data.

**Files:**
- `apps/api/tasks/correlation_tasks.py` — **New** — Celery task
- `apps/api/celerybeat_schedule.py` — Add new schedule entry
- `apps/api/services/correlation_engine.py` — No changes needed (already
  supports all output metrics via parameter)

### Item 2: CorrelationWeb Desktop Fixes

**Problems identified by founder:**
- Force simulation oscillates with few nodes (2-3), nodes drift visibly
- Edges hard to select on desktop — 20px invisible hit target too narrow
  on curved paths
- `alphaDecay(0.04)` too slow — simulation takes seconds to settle

**Fixes in `apps/web/components/progress/CorrelationWeb.tsx`:**

1. **Increase `alphaDecay` to 0.08-0.1** — simulation settles in ~1 second
   instead of 3-4 seconds.

2. **For ≤ 5 nodes: skip force simulation, use fixed positions.** Inputs
   evenly spaced on the left, outputs evenly spaced on the right. No
   drift, no oscillation. Force simulation only adds value when there are
   enough nodes for interesting spatial relationships (6+).

3. **Batch position updates.** Instead of `setPos()` on every tick, use
   `requestAnimationFrame` and only update React state when positions change
   by > 1px. Stops unnecessary re-renders.

4. **Wider edge hit target on desktop.** Increase invisible stroke from
   20px to 40px. On mobile keep 20px (finger target is already large).
   Use `@media (pointer: fine)` or a `window.matchMedia` check.

5. **Add `sim.on('end', ...)` handler** — when simulation settles, do one
   final `setPos()` and stop. No more ongoing ticks after convergence.

### Item 3: Acronym Rule Enforcement (global, applied here)

**Project rule (from `BUILD_SPEC_HOME_AND_ACTIVITY.md` and home PMC):**
No raw acronyms in athlete-facing surfaces. The established pattern is:
`"Fitness (CTL)"`, `"Fatigue (ATL)"`, `"Form (TSB)"`.

**Apply to Progress page:**

| Current | Correct |
|---------|---------|
| "CTL then" | "Fitness then" |
| "CTL now" | "Fitness now" |
| Any raw "TSB" | "Form (TSB)" |
| Any raw "ATL" | "Fatigue (ATL)" |
| Any raw "HRV" | "Heart Rate Variability (HRV)" (first use) then "HRV" |
| Any raw "TSS" | "Training Stress" |

**Backend:** Update `GET /v1/progress/knowledge` hero stat labels to use
human-readable names. The label field should say "Fitness then" not
"CTL then".

**Frontend:** Update `CorrelationWeb` and `WhatDataProved` node labels
and fact headlines. The `_humanize_metric()` function in `progress.py`
must produce athlete-friendly names, not developer names.

**Check:** `_humanize_metric()` in `correlation_engine.py` — update the
mapping to ensure ALL metric names that appear on the Progress page use
plain language first, acronym in parentheses only when helpful.

### Item 4: Recovery Fingerprint

**Founder's favorite from the mockup.** An animated canvas showing how the
athlete's body recovers from hard weeks — now vs 90 days ago.

**What it shows:**
- X-axis: days after a hard week (Day 0 through Day 7)
- Y-axis: efficiency as % of baseline (60-100%)
- Two curves: "90 days ago" (dashed, muted) and "Now" (solid, green, animated)
- The "Now" curve recovers faster — the gap IS the adaptation
- Hover any point → tooltip with both values + coach interpretation

**Data source:** `services/recovery_metrics.py` already has:
- `calculate_recovery_half_life()` — computes hours to baseline
- Hard/easy session classification by HR threshold
- Activity sequence analysis

**What's needed:**

1. **Remove the max_hr gate from `recovery_metrics.py` (CRITICAL)**
   - `compute_recovery_curve()` (line 380) returns `None` if `athlete.max_hr`
     is not set. This uses a population metric as a gate for an N=1 feature.
     Max HR is not used by the founder, is poorly understood, rarely reached
     in real training, and contradicts the product manifesto.
   - **Do NOT derive max_hr from data. Remove the dependency entirely.**
   - **Replace hard session classification** with one of these N=1 approaches
     (choose the most practical, can combine):
     a. **Athlete's own HR percentile:** Query all activities with avg_hr,
        compute P80. Sessions with avg_hr >= P80 = hard. No max HR needed.
        This is purely derived from their own distribution.
     b. **Daily session stress:** `distance_m × avg_hr` already exists in
        `aggregate_daily_session_stress()`. Top quartile = hard session.
     c. **Workout type:** Activity.workout_type already classifies runs as
        `tempo_run`, `race`, `interval`, `threshold_run`, `long_run`,
        `easy_run`. Use the classification directly. Any of
        `race|interval|tempo_run|threshold_run` = hard.
     d. **RPE from check-ins:** `DailyCheckin.rpe_1_10 >= 7` = hard.
   - Apply the same fix to `calculate_recovery_half_life()` (line 77
     comment: "In a full implementation, you'd compare to athlete's max HR"
     — wrong approach, use percentile or workout type instead).
   - Also fix `HARD_SESSION_HR_THRESHOLD` and `EASY_SESSION_HR_THRESHOLD`
     constants (lines 26-27) — replace with percentile-based thresholds.

2. **`compute_recovery_curve()` already exists (lines 359-496)**
   - The builder who shipped the correlation work already added this function.
   - The logic after the hard-session classification is correct (collect
     efficiency on days 0-7, average across instances, normalize as % of
     baseline). Only the hard-session classification needs to change.
   - After fixing the classification, verify it returns real data for the
     founder — they have ~2 years of data with dozens of races, intervals,
     and threshold runs.

2. **New endpoint or extend existing:**
   - Add `recovery_curve` to the `GET /v1/progress/knowledge` response
   - Or new `GET /v1/progress/recovery-curve` if response is getting large

3. **Frontend: `RecoveryFingerprint.tsx`**
   - Canvas 2D component (not SVG — performance for animation)
   - Animated curve drawing using `requestAnimationFrame`
   - "Before" curve draws first (dashed, muted)
   - "Now" curve animates in (solid green, with gradient fill and glow dot)
   - Hover shows tooltip with both values + day label
   - Legend: "90 days ago" / "Now"
   - Use the v1 mockup as the direct reference for the canvas implementation

**Fallback:** If insufficient hard sessions (< 3 in either window), show
a message: "Need more hard sessions to compute your recovery curve.
Currently {N} hard sessions in the last 90 days."

---

## Build Contracts

1. **Acronym rule is global and non-negotiable.** First use on any
   athlete-facing surface must be the full term with acronym in
   parentheses: "Fitness (CTL)", "Heart Rate Variability (HRV)".
   Subsequent uses on the same page may use the acronym alone.

2. **Correlation sweep must not block API requests.** It runs as a
   background Celery task, not inline.

3. **CorrelationWeb must be stable before adding more nodes.** The desktop
   fixes must land before the sweep populates more findings, or the graph
   will be even worse with 10+ oscillating nodes.

4. **Recovery Fingerprint uses Canvas 2D, not SVG.** The animated curve
   drawing requires frame-by-frame control that Canvas provides.

5. **All new data on the Progress page follows the design principle:**
   visual first, narrative bridge below. No data without interpretation.

---

## Recommended Build Order

| Order | Item | Why |
|-------|------|-----|
| 1 | CorrelationWeb desktop fixes | Must stabilize before sweep adds nodes |
| 2 | Acronym rule enforcement | Quick, global trust improvement |
| 3 | Correlation sweep + backfill | Populates the page with real findings |
| 4 | Recovery Fingerprint | Largest new section, founder's favorite |

Items 1-2 can be done in one commit. Item 3 in a second commit. Item 4
is a standalone feature.

---

## Files to Change

| File | Change |
|------|--------|
| `apps/web/components/progress/CorrelationWeb.tsx` | Desktop fixes: alphaDecay, fixed positions for ≤5 nodes, wider hit target, batched updates |
| `apps/api/routers/progress.py` | Update hero stat labels to human-readable; add recovery_curve to response |
| `apps/api/services/correlation_engine.py` | Update `_humanize_metric()` for athlete-friendly names |
| `apps/api/tasks/correlation_tasks.py` | **New** — daily correlation sweep task |
| `apps/api/celerybeat_schedule.py` | Add daily-correlation-sweep schedule |
| `apps/api/services/recovery_metrics.py` | Add `compute_recovery_curve()` |
| `apps/web/components/progress/RecoveryFingerprint.tsx` | **New** — canvas recovery curve |
| `apps/web/components/progress/ProgressHero.tsx` | Update stat labels |
| `apps/web/components/progress/WhatDataProved.tsx` | Ensure metric names use human language |
| `apps/web/components/progress/index.ts` | Export RecoveryFingerprint |
| `apps/web/app/progress/page.tsx` | Add RecoveryFingerprint section |
| `docs/SITE_AUDIT_LIVING.md` | Update post-deploy |

---

## Required Tests

1. `run_daily_correlation_sweep` task runs for all 9 output metrics
2. Sweep only processes athletes with activity in last 24h
3. Sweep respects existing confounder + direction quality gates
4. `_humanize_metric()` returns human-readable names for all known metrics
5. Hero stat labels contain no raw acronyms
6. CorrelationWeb: ≤ 5 nodes uses fixed positions (no force simulation)
7. CorrelationWeb: > 5 nodes uses force simulation with `alphaDecay >= 0.08`
8. `compute_recovery_curve()` returns correct shape with before/now arrays
9. `compute_recovery_curve()` returns fallback when < 3 hard sessions
10. Recovery Fingerprint renders on mobile and desktop
11. No regressions: all existing progress tests still pass

---

## Production Smoke Checks (post-deploy)

```bash
# 1. Correlation sweep task exists and runs
docker exec strideiq_worker python -c "
from tasks.correlation_tasks import run_daily_correlation_sweep
print('Task imported successfully')
"

# 2. Manual sweep for founder — populates findings across all metrics
docker exec strideiq_api python -c "
from database import SessionLocal
from services.correlation_engine import analyze_correlations
from models import Athlete, CorrelationFinding
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
metrics = ['efficiency','pace_easy','pace_threshold','completion',
           'efficiency_threshold','efficiency_race','efficiency_trend',
           'pb_events','race_pace']
for m in metrics:
    try:
        r = analyze_correlations(str(user.id), days=90, db=db, output_metric=m)
        c = len(r.get('correlations', []))
        print(f'{m}: {c} correlations found')
    except Exception as e:
        print(f'{m}: ERROR {e}')
count = db.query(CorrelationFinding).filter(
    CorrelationFinding.athlete_id == user.id,
    CorrelationFinding.is_active == True
).count()
print(f'Total active findings: {count}')
db.close()
"

# 3. Progress page shows more than 1 edge
TOKEN=$(...generate token...)
curl -s -H "Authorization: Bearer $TOKEN" \
  https://strideiq.run/v1/progress/knowledge | python3 -c "
import sys, json
d = json.load(sys.stdin)
nodes = d['correlation_web']['nodes']
edges = d['correlation_web']['edges']
facts = d['proved_facts']
print(f'Nodes: {len(nodes)}, Edges: {len(edges)}, Facts: {len(facts)}')
for s in d['hero']['stats']:
    assert 'CTL' not in s['label'], f'Raw acronym in hero: {s[\"label\"]}'
    assert 'TSB' not in s['label'], f'Raw acronym in hero: {s[\"label\"]}'
    print(f'  Stat: {s[\"label\"]} = {s[\"value\"]}')
print('PASS: no raw acronyms, multiple findings')
"

# 4. Recovery curve endpoint returns data
curl -s -H "Authorization: Bearer $TOKEN" \
  https://strideiq.run/v1/progress/knowledge | python3 -c "
import sys, json
d = json.load(sys.stdin)
rc = d.get('recovery_curve')
if rc:
    print(f'Before points: {len(rc[\"before\"])}')
    print(f'Now points: {len(rc[\"now\"])}')
    print('PASS: recovery curve present')
else:
    print('INFO: recovery curve not present (may need more hard sessions)')
"
```

---

## Evidence Required in Handoff

1. **Commit hash(es)** — scoped commits only
2. **Files changed table** — file + one-line description
3. **Test output** — full pytest output, 0 failures
4. **Production smoke check output** — paste results of all 4 checks
5. **Before/after for correlation count** — "1 active finding" → "{N} active findings"
6. **Desktop screenshot** — CorrelationWeb with multiple nodes, stable, edges selectable
7. **Mobile screenshot** — same page, responsive
8. **Recovery Fingerprint screenshot** — canvas rendering with both curves
9. **Acronym check** — no raw CTL/ATL/TSB/HRV anywhere on the page

---

## Mandatory: Site Audit Update

After deploy, update `docs/SITE_AUDIT_LIVING.md`:
- New entry under "Delta Since Last Audit"
- Note: "Daily correlation sweep across 9 output metrics. CorrelationWeb
  desktop stability fix. Recovery Fingerprint (canvas). Acronym rule
  enforced on Progress page."
- Update `last_updated` date
