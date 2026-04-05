# Workstream 3 Spec: Home Page Cross-Training Acknowledgment

**Date:** April 5, 2026
**Author:** Builder
**Status:** Awaiting advisor review

---

## Problem

The founder does a walk, the home page acts like nothing happened.
`LastRunHero` only shows runs. Weekly chips show cross-training icons,
but there's no acknowledgment card for the actual activity. The athlete
has to navigate to the activity list to confirm it was captured.

---

## 1. API Response Shape

Add `recent_cross_training` to `HomeResponse` in `routers/home.py`:

```python
class RecentCrossTraining(BaseModel):
    id: str
    sport: str
    name: Optional[str] = None
    distance_m: Optional[float] = None
    duration_s: Optional[int] = None
    avg_hr: Optional[int] = None
    steps: Optional[int] = None
    active_kcal: Optional[int] = None
    start_time: str  # ISO datetime
    additional_count: int = 0  # how many MORE non-run activities in last 24h
```

On `HomeResponse`, add:
```python
recent_cross_training: Optional[RecentCrossTraining] = None
```

**Query logic** (inside `get_home_data`, after the existing timezone setup):

```python
# Recent cross-training: most recent non-run activity in last 24h (athlete local)
_ct_cutoff_utc = _today_start_utc - timedelta(hours=24)
_ct_activities = (
    db.query(Activity)
    .filter(
        Activity.athlete_id == current_user.id,
        Activity.sport != "run",
        Activity.is_duplicate == False,
        Activity.start_time >= _ct_cutoff_utc,
    )
    .order_by(desc(Activity.start_time))
    .all()
)

recent_cross_training = None
if _ct_activities:
    latest_ct = _ct_activities[0]
    recent_cross_training = RecentCrossTraining(
        id=str(latest_ct.id),
        sport=latest_ct.sport,
        name=latest_ct.name,
        distance_m=latest_ct.distance_m,
        duration_s=latest_ct.duration_s or latest_ct.moving_time_s,
        avg_hr=latest_ct.avg_hr,
        steps=latest_ct.steps,
        active_kcal=latest_ct.active_kcal,
        start_time=latest_ct.start_time.isoformat(),
        additional_count=len(_ct_activities) - 1,
    )
```

- **24-hour window** from the start of today (athlete local), not a rolling
  24h from now. This means a walk at 2 PM yesterday appears until midnight
  tonight, then disappears. Matches the daily rhythm.
- `additional_count` is the number of OTHER non-run activities in the same
  window. If the founder walks AND does strength, the card shows the walk
  (most recent) with "+1 more" linking to the activity list.

---

## 2. Component Design

### Placement

Between `LastRunHero` and `CompactPMC`. This is the natural visual hierarchy:
the run is the hero, cross-training is acknowledged beneath it, training
load context follows.

```
┌─────────────────────────────────────────────┐
│  LastRunHero (existing — full-bleed canvas)  │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│  🚶 Walking · 1.1 mi · 28 min · 92 bpm     │  ← NEW
│  Lauderdale County · 2:08 PM    +1 more →   │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│  CompactPMC (existing)                      │
└─────────────────────────────────────────────┘
```

### Component: `RecentCrossTrainingCard`

Single-row compact card. Not a hero — smaller visual weight than LastRunHero.

```
┌───────────────────────────────────────────────┐
│ [icon]  Walking · 1.1 mi · 28 min · 92 bpm   │
│         Lauderdale County · 2:08 PM           │
└───────────────────────────────────────────────┘
```

**Content rules per sport:**

| Sport | Primary metrics shown |
|-------|----------------------|
| Walking | distance, duration, steps (headline if no distance), avg HR |
| Hiking | distance, duration, elevation, avg HR |
| Cycling | distance, duration, avg speed, avg HR |
| Strength | duration, session type badge, avg HR |
| Flexibility | duration, avg HR |

**Interaction:**
- Tap anywhere → navigates to `/activities/{id}`
- If `additional_count > 0`: "+N more" text at the right edge, tapping it
  navigates to `/activities` (list page)

**Styling:**
- `bg-slate-800/30 border border-slate-700/30 rounded-lg` — matches the
  existing card style on the home page
- Sport icon from `SPORT_CONFIG` with the sport's color
- Metric text in `text-sm text-slate-300`, secondary text (name, time) in
  `text-xs text-slate-500`
- No animation, no gradient, no special effects — quiet acknowledgment

### When the card does NOT render:
- No non-run activities in the last 24 hours → component returns `null`
- The section simply doesn't exist on the page — no gap, no placeholder

---

## 3. No Recent Run + Recent Walk

**The walk does NOT get promoted to the hero position.**

The home page is a running command center. `LastRunHero` shows runs, period.
When there's no recent run (96h window expired) but there IS a recent walk:

- `LastRunHero` renders nothing (existing behavior — `last_run` is null)
- `RecentCrossTrainingCard` renders the walk in its normal secondary position
- The athlete sees the walk acknowledged but the running hero stays absent

This correctly communicates: "You haven't run in 4 days. You walked today."
Promoting the walk to hero would falsely imply it's equivalent to a run in
the training context. That's not what the athlete wants to see.

If the athlete hasn't run in a week but has been cycling and doing strength,
the card still shows the most recent non-run activity. The weekly chips
(which already show all sports) provide the full picture of the training week.

---

## 4. Frontend Type Addition

In `apps/web/lib/api/services/home.ts`, add to `HomeData`:

```typescript
recent_cross_training: {
  id: string;
  sport: string;
  name: string | null;
  distance_m: number | null;
  duration_s: number | null;
  avg_hr: number | null;
  steps: number | null;
  active_kcal: number | null;
  start_time: string;
  additional_count: number;
} | null;
```

---

## Build Sequence

1. Add `RecentCrossTraining` model + query to `routers/home.py`
2. Add field to `HomeResponse` and wire into the return statement
3. Add TypeScript type to `home.ts`
4. Create `RecentCrossTrainingCard` component
5. Insert into `app/home/page.tsx` between LastRunHero and CompactPMC

One commit. CI green.

---

## What NOT to change

- `LastRunHero` — unchanged, still run-only
- `CompactPMC` — unchanged
- Weekly chips — already show cross-training, not touched
- Morning briefing — already has cross-training awareness (Phase 4)
- No new API endpoint — extends existing `/v1/home` response
