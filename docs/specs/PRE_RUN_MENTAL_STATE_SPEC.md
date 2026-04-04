# Pre-Run Mental State Check-In Spec

**Date:** March 10, 2026  
**Priority:** P1 — ship after correlation engine wiring + backfill  
**Research basis:** Sports psychology literature review (Marcora 2009, Van Cutsem systematic review, Moritz self-efficacy meta-analysis r=0.31), Jon Greene coaching philosophy ("two gas tanks"), athlete monitoring best practices  
**Principle:** Capture what the device can't measure, at the moment it matters, with enough variance to produce real correlations.

---

## The Problem

The correlation engine has zero signal about the athlete's mental state at the time of a run. Morning check-in readiness produces near-constant values (founder reports 4/5 ninety-nine percent of the time). Post-run feedback is always "depleted." The moment with real variance is pre-run — when the day's accumulated stress, energy, and motivation are all present and differentiated.

Research confirms: mental fatigue reduced endurance performance 15% with zero physiological change (Marcora 2009). The mechanism is RPE inflation — the run *feels* harder, so the athlete self-selects a slower pace. This pathway is invisible to every wearable.

---

## What to Build

Three pre-run mental state fields on the Activity model, a pre-run check-in UI triggered before/during a run, and correlation engine wiring.

---

## Backend

### 1. New columns on Activity model

**File:** `apps/api/models.py`, Activity class (after the `garmin_body_battery_impact` line, ~510)

```python
# --- PRE-RUN MENTAL STATE (Marcora pathway) ---
pre_run_mental_drain_1_5 = Column(Integer, nullable=True)  # 1=sharp/fresh, 5=completely spent
pre_run_drive_1_5 = Column(Integer, nullable=True)          # 1=forcing myself, 5=can't wait
pre_run_life_load_1_5 = Column(Integer, nullable=True)      # 1=light/clear, 5=heavy/overwhelmed
```

### 2. Migration

```
alembic revision --autogenerate -m "add pre_run mental state columns to activity"
```

Three nullable integer columns. No data migration needed.

### 3. API endpoint to submit pre-run state

**File:** `apps/api/routers/activities.py` (or wherever activity updates live)

New endpoint or extend existing activity update:

```
PATCH /v1/activities/{activity_id}/pre-run-state
```

Body:
```json
{
  "mental_drain": 3,
  "drive": 4,
  "life_load": 2
}
```

All three fields optional. Validates 1-5 range. Updates the Activity row.
Returns 200 with updated fields.

Auth: requires athlete ownership of the activity.

Alternative: if the check-in happens before the activity exists (pre-run
prompt before Garmin syncs), store in a temporary `PreRunState` row keyed
by `(athlete_id, date)` and link it to the activity when the activity
arrives. This handles the timing gap between "athlete taps check-in"
and "Garmin webhook delivers the activity."

### 4. Link unmatched pre-run states to activities

When a new activity is ingested (Garmin webhook or Strava sync), check
for an unmatched `PreRunState` row for the same athlete on the same date.
If found, copy the three fields to the Activity and mark the pre-run
state as linked.

**Timing heuristic:** If the athlete submitted the pre-run state within
2 hours before the activity start_time, link it. Otherwise leave
unlinked (it was for a different session or a stale submission).

### 5. Correlation engine wiring

**File:** `apps/api/services/correlation_engine.py`

Add to `aggregate_activity_level_inputs()` (the function created in the
wiring spec):

```python
# Pre-run mental state
("pre_run_mental_drain", "pre_run_mental_drain_1_5"),
("pre_run_drive", "pre_run_drive_1_5"),
("pre_run_life_load", "pre_run_life_load_1_5"),
```

Add to the `_ACTIVITY_SIGNALS` list in the same function. These follow
the identical pattern as cadence, elevation, etc.

### 6. FRIENDLY_NAMES

**File:** `apps/api/services/n1_insight_generator.py`

```python
"pre_run_mental_drain": "pre-run mental fatigue",
"pre_run_drive": "drive to run",
"pre_run_life_load": "life stress load",
```

### 7. DIRECTION_EXPECTATIONS

**File:** `apps/api/services/correlation_engine.py`

```python
("pre_run_mental_drain", "efficiency"): "negative",
("pre_run_mental_drain", "pace_easy"): "negative",
("pre_run_drive", "efficiency"): "positive",
("pre_run_drive", "pace_easy"): "positive",
("pre_run_life_load", "efficiency"): "negative",
```

### 8. CONFOUNDER_MAP

```python
("pre_run_mental_drain", "efficiency"): "daily_session_stress",
("pre_run_drive", "efficiency"): "daily_session_stress",
("pre_run_life_load", "efficiency"): "daily_session_stress",
```

### 9. Lag configuration

These are acute pre-session states. The correlation engine tests lags
0-7 days by default. For pre-run mental state, the primary effect is
same-session (lag 0) with a possible next-day residual (lag 1). The
existing lag range handles this — no change needed. The engine will
naturally find the strongest correlation at lag 0.

---

## Frontend

### 10. Pre-Run Check-In Component

**New component:** `apps/web/components/prerun/PreRunCheckIn.tsx`

Three horizontal slider taps. Same visual style as the existing check-in
page sliders. Total interaction: under 8 seconds.

| # | Label | Anchors | Scale |
|---|-------|---------|-------|
| 1 | How mentally drained are you? | Sharp/Fresh ← → Completely spent | 1-5 |
| 2 | How strong is your drive to run? | Forcing myself ← → Can't wait | 1-5 |
| 3 | How much is life weighing on you? | Light/clear ← → Heavy | 1-5 |

**Design:**
- Compact card, not a full page
- Each dimension is a single row with label, anchor text, and 5 tappable circles
- Skip button always visible ("Skip" or just X to dismiss)
- Submit button at bottom ("Got it" or "Let's go")
- No explanatory text, no tooltips, no onboarding — just the three rows

### 11. Trigger

**When to show:**

Option A (simplest): Show as a dismissable card on the home page when
the athlete has a scheduled workout today that hasn't been completed yet.
The card appears in the morning or whenever they open the app on a run day.

Option B (ideal): Show as an interstitial when the athlete navigates to
their scheduled workout or taps "start" on any pre-run action. This
captures state closest to the run.

Option C (passive): Show as a persistent but unobtrusive element on the
activity detail page for the most recent activity, if no pre-run state
was captured. "How were you feeling before this run?" — retrospective
but still useful. Less ideal timing but captures data from athletes
who don't interact pre-run.

**Recommendation:** Start with Option A. It's the simplest to build and
doesn't require detecting run-start events. The home page already has
contextual cards. Add a pre-run state card when there's a scheduled
workout today. If the athlete submits, the card disappears. If they
skip, it disappears for the day.

### 12. Skip behavior

- Always skippable, never blocks anything
- If skipped 3 times in a row, reduce to every other run day for 2 weeks
- Track skip count in localStorage (not worth a DB field)
- Never explain why you're asking — just ask

### 13. Storage flow

1. Athlete taps values and submits
2. Frontend calls `POST /v1/pre-run-state` with `{ date, mental_drain, drive, life_load }`
3. Backend stores in `PreRunState` table (or directly on today's Activity if one exists)
4. When activity arrives via webhook, backend links the pre-run state
5. Correlation engine picks it up on next sweep

---

## Data Model: PreRunState (temporary holding table)

If using the linking approach:

```python
class PreRunState(Base):
    __tablename__ = "pre_run_state"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    mental_drain_1_5 = Column(Integer, nullable=True)
    drive_1_5 = Column(Integer, nullable=True)
    life_load_1_5 = Column(Integer, nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=True)
    linked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("athlete_id", "date", name="uq_pre_run_state_athlete_date"),
    )
```

One row per athlete per day. When the activity arrives and gets linked,
`activity_id` and `linked_at` are populated. The correlation engine
reads from the Activity columns (populated during linking), not from
this table directly.

---

## Tests

### Backend

1. `test_pre_run_state_stored` — POST pre-run state → row created
2. `test_pre_run_state_validation` — values outside 1-5 rejected
3. `test_pre_run_state_linked_to_activity` — activity arrives within 2h → fields copied to Activity
4. `test_pre_run_state_not_linked_stale` — activity arrives 4h later → not linked
5. `test_pre_run_state_upsert` — second submission same day overwrites
6. `test_pre_run_inputs_in_correlation` — Activity with pre-run fields → appear in `aggregate_activity_level_inputs()`
7. `test_pre_run_friendly_names` — all three keys in FRIENDLY_NAMES
8. `test_pre_run_direction_expectations` — mental_drain negative, drive positive, life_load negative

### Frontend

9. `test_pre_run_card_shows_on_run_day` — scheduled workout today → card visible
10. `test_pre_run_card_hidden_after_submit` — submit → card disappears
11. `test_pre_run_card_skippable` — skip → card disappears for day
12. `test_pre_run_slider_values` — each slider produces 1-5 integer

---

## What This Enables

Once an athlete has 30+ pre-run state entries (roughly 1 month of running),
the engine can discover:

- "When your mental drain is 4-5, your efficiency drops 11% — but only on days
  when life load is also above 3" (combination correlation)
- "Your drive to run is the strongest predictor of your pace selection —
  stronger than sleep, HRV, or training load" (competitive signal ranking)
- "Mental drain has a threshold at 3 — below 3 no effect, above 3 steep
  decline" (Layer 1 threshold detection)
- "The life load → efficiency pathway runs through mental drain, not directly"
  (Layer 3 mediation detection)

These are findings about the athlete's psychology that no wearable and no
other running app can produce. Jon Greene gets this through daily phone calls.
StrideIQ gets it through three taps before a run.

---

## What This Does NOT Do

- Does not replace morning check-in (that captures different signals)
- Does not add a journaling/notes feature
- Does not require natural language processing
- Does not send notifications to prompt check-in
- Does not change any existing check-in behavior
- Does not require coach/LLM involvement

---

## Acceptance Criteria

1. Athlete can submit pre-run state in under 8 seconds
2. State is linked to the correct activity when it arrives
3. All three fields appear in correlation engine inputs
4. All three have FRIENDLY_NAMES and DIRECTION_EXPECTATIONS
5. Skip behavior works without degrading experience
6. No pre-run state is ever required to start a run
7. 12 tests pass
