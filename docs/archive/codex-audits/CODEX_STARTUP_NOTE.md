# Codex Startup Note — Larry Coverage Diagnostic

**Date:** March 8, 2026

## Your Role

You are the technical advisor and builder. The founder (Michael) directs
you through Codex. He has a separate thinking partner (Opus in Cursor)
for product discussions. Your job is to investigate, build, and show
evidence. Not to advise on product direction unless asked.

## Required Reading (in order)

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how to work with this founder.
   Non-negotiable. Read it first.
2. `docs/specs/SHAPE_SENTENCE_SPEC.md` — the shape sentence system.
   Parts 5-6 are explicitly GATED. Do not build anything in those sections.
3. `docs/BUILDER_INSTRUCTIONS_COVERAGE_FIXES.md` — what was just built
   and shipped. Context for where we are now.
4. `apps/api/services/shape_extractor.py` — the extractor pipeline.
   This is the code you'll be investigating.

## What Just Happened

Shape sentence coverage went from 3% to 71% (real athletes only).
Three fixes shipped: anti-oscillation merge, hybrid anomaly detection,
acceleration-based hill repeats. All deployed and verified on production.

Per-athlete coverage now:
- Michael: 28/34 (82%)
- BHL: 7/9 (77%)
- Larry: 11/22 (50%) ← **the problem**

Larry's 11 suppressed activities break down as:
- `phases>8`: 6 — investigated, these are honest suppression. The
  anti-oscillation merge runs and correctly absorbs nothing. Gray
  segments are 193-2618 seconds long, not GPS noise.
- `cls_none`: 4 — **this is your investigation target**
- `anomaly`: 1 — 266 impossible velocity points, correctly flagged

The anti-oscillation merge is NOT the remaining bottleneck. Do not
spend time on it.

## Your Immediate Task

**Deep dive the 3 Larry `cls_none` easy/gray runs.**

Three of the four `cls_none` runs share the same pattern — the fourth
(Feb 06, 1.89 mi) is a different messy-workout problem. Focus on:

- **2026-02-26** — 2.0 mi, 4 effort phases, `easy→gray→easy→gray`,
  0 accelerations, `pace_progression=variable`
- **2026-02-13** — 2.0 mi, 6 effort phases, `easy→gray→easy→gray→easy→gray`,
  0 accelerations, `pace_progression=steady`
- **2026-02-12** — 5.0 mi, 7 effort phases, mostly easy/gray + one
  short threshold (70s), 1 acceleration, `pace_progression=variable`

These fail `easy_run` because `len(effort_phases) > 3`. They fail
`gray_zone_run` because gray duration isn't >50% of total.

**For each run, report:**
1. Exact effort phase zones, durations, and average paces
2. Gray duration as percentage of total effort duration
3. How close the gray phases' paces are to Larry's easy ceiling
4. Whether calling these `easy_run` would be factually wrong

**Then answer:**
Is there a narrow classifier rule that catches these three without
false-positiving on genuine gray-zone work? What would that rule
look like?

## Larry's Pace Profile (from production)

- easy: 12:30/mi (750 sec)
- marathon: 10:12/mi (612 sec)
- threshold: 9:37/mi (577 sec)
- interval: 8:18/mi (498 sec)
- repetition: 7:36/mi (456 sec)

Easy ceiling (with ±10s zone half-width): ~740 sec/mi = 12:20/mi.
Gray zone is anything between 12:20 and the marathon ceiling.

## What NOT To Do

- Do not propose fixes before completing the diagnostic
- Do not touch title authorship, identity model, or Parts 5-6 of
  the shape sentence spec
- Do not work on anti-oscillation merge improvements
- Do not try to rescue the `phases>8` runs
- Do not discuss product strategy — just investigate and report
- Show evidence, not claims

## How to Access Production Data

You can query production via SSH. Scripts go to local `.py` files,
`scp` to the server, `docker cp` into the container, `docker exec`
to run them. The API container is `strideiq_api`. The database
session is available via:

```python
from database import SessionLocal
from models import Athlete, Activity
db = SessionLocal()
larry = db.query(Athlete).filter(Athlete.display_name.ilike('%larry%')).first()
```

Activity stream data is in `Activity.streams` (JSON dict with keys
like `time`, `velocity_smooth`, `cadence`, `grade_smooth`, etc.).

The shape extractor can be called directly:

```python
from services.shape_extractor import extract_shape, PaceProfile
shape = extract_shape(activity.streams, pace_profile=pace_profile)
```
