# Builder Instructions: Fix Duplicate Campaign Detectors + Findings Regression Test

**Priority:** URGENT — two separate campaign detectors exist, the wrong one is feeding the home page
**Scope:** 3 tasks
**Risk:** Medium — replacing narrative source for home page campaign context

---

## Context

There are TWO separate campaign detectors. The wrong one is feeding the home page. The result: the founder's home page says "27-week campaign" when the reality is a 6-month build that ended with a femur fracture, followed by 8 weeks of cautious comeback.

### The two detectors:

1. **`apps/api/services/campaign_detection.py`** (600 lines) — the GOOD one. Uses volume inflection points, disruption detection (instant cliffs + progressive declines), phase classification (base_building, escalation, taper, disrupted), disruption severity analysis, recovery pattern detection. Understands that a femur fracture creates two separate campaigns. Just wired into the fingerprint refresh and Strava post-sync. Output goes to `PerformanceEvent.campaign_data` JSONB.

2. **`apps/api/services/training_story_engine.py` → `detect_campaign()`** (line ~882) — the BROKEN one. Takes `min(all_adaptation_starts)` to `max(all_adaptation_ends)` and calls it one campaign. Zero disruption awareness. Zero injury detection. This is what feeds the home page via `synthesize_training_story()` → `to_coach_context()` → `_build_rich_intelligence_context()`. This is what produced the false "27-week campaign" narrative.

### Additional finding:

Correlation findings have regressed multiple times. Each regression costs real debugging time and money. There is no CI test that catches "founder went from 8 findings to 2."

---

## Task 0: Remove the Broken Campaign Detector from Training Story Engine

**Priority: HIGHEST — this is producing wrong narratives on the home page right now.**

**File:** `apps/api/services/training_story_engine.py`

### 0a: Replace `detect_campaign()` with a call to the real campaign detector's stored output

The function `detect_campaign()` (line ~882) takes adaptation date ranges and computes `min(start)` to `max(end)` as one campaign. It has no disruption awareness. Delete this function entirely and replace the call at line ~1047 with a lookup of `PerformanceEvent.campaign_data` (which the real campaign detector populates).

**In `synthesize_training_story()`** (line ~1044), replace:

```python
campaign = detect_campaign(findings, date_ranges, connections, race_stories)
```

With a function that reads from the real campaign detector's output:

```python
campaign = _get_campaign_from_events(race_stories, events)
```

New helper (add to the same file):

```python
def _get_campaign_from_events(
    race_stories: List[RaceStory],
    events: List["PerformanceEvent"],
) -> Optional[Dict]:
    """
    Read campaign data from PerformanceEvent.campaign_data (populated by
    the real campaign detector in campaign_detection.py).
    
    Returns the most recent campaign that has linked races, or None.
    """
    campaigns_seen = {}
    for ev in events:
        if ev.campaign_data and isinstance(ev.campaign_data, dict):
            start = ev.campaign_data.get('start_date')
            end = ev.campaign_data.get('end_date')
            if not start or not end:
                continue
            key = (start, end)
            record = campaigns_seen.get(key)
            if record is None:
                campaigns_seen[key] = {
                    'campaign': ev.campaign_data,
                    'latest_linked_race_date': ev.event_date,
                }
            else:
                if ev.event_date and (
                    record['latest_linked_race_date'] is None
                    or ev.event_date > record['latest_linked_race_date']
                ):
                    record['latest_linked_race_date'] = ev.event_date

    if not campaigns_seen:
        return None

    # Return the campaign tied to the most recent linked race event date
    latest_record = max(
        campaigns_seen.values(),
        key=lambda r: r.get('latest_linked_race_date') or date.min,
    )
    latest = latest_record['campaign']
    
    span_weeks = latest.get('total_weeks', 0)
    end_reason = latest.get('end_reason', 'unknown')
    
    summary = f"{span_weeks}-week training arc"
    if end_reason == 'disruption':
        summary += " (ended by disruption)"
    elif end_reason == 'ongoing':
        summary += " (ongoing)"
    
    return {
        'start_date': latest.get('start_date'),
        'end_date': latest.get('end_date'),
        'span_weeks': span_weeks,
        'end_reason': end_reason,
        'phases': latest.get('phases', []),
        'summary': summary,
    }
```

### 0b: Update `synthesize_training_story` signature

The `events` parameter is already passed to this function (line ~1033 in home.py passes it). Verify the function signature accepts it and passes it through to `_get_campaign_from_events`.

### 0c: Delete the old `detect_campaign()` function

Remove the entire function (lines ~882-961) and its section header. It is replaced by `_get_campaign_from_events`.

### 0d: If no campaign_data exists yet on PerformanceEvent

The real campaign detector was just wired and may not have run yet for all athletes. If `_get_campaign_from_events` returns None, the campaign narrative should be None (silence). Do NOT fall back to the old broken logic. Silence is better than a wrong 27-week arc.

### 0e: Add a hard regression test for "silence over wrong campaign"

Add a unit test in `apps/api/tests/test_training_story_engine.py`:

```python
def test_campaign_narrative_is_none_without_campaign_data():
    findings = []  # or minimal valid findings fixture
    events = []    # no campaign_data available yet
    story = synthesize_training_story(findings, events)
    assert story.campaign_narrative is None
```

This test enforces the no-fallback contract permanently.

---

## Task 1: Wire Campaign Detection into the Daily Fingerprint Refresh (ALREADY DONE — VERIFY ONLY)

**This was already wired by the builder.** Verify it exists in both:
- `apps/api/tasks/intelligence_tasks.py` → `refresh_living_fingerprint` (after `store_all_findings` + `db.commit()`)
- `apps/api/tasks/strava_tasks.py` → post-sync block (after finding persistence + `db.commit()`)

If already present in both locations, skip to Task 2. If missing from either, add:

```python
# Campaign detection — find training arcs and link to races
try:
    from services.campaign_detection import (
        detect_inflection_points,
        build_campaigns,
        store_campaign_data_on_events,
    )
    from models import PerformanceEvent

    inflection_points = detect_inflection_points(aid, db)
    if inflection_points:
        confirmed_events = (
            db.query(PerformanceEvent)
            .filter(
                PerformanceEvent.athlete_id == aid,
                PerformanceEvent.user_confirmed == True,  # noqa: E712
            )
            .all()
        )
        campaigns = build_campaigns(aid, inflection_points, confirmed_events, db)
        if campaigns:
            updated = store_campaign_data_on_events(aid, campaigns, db)
            db.commit()
            logger.info(
                "Campaign detection for %s: %d inflections, %d campaigns, %d events updated",
                aid, len(inflection_points), len(campaigns), updated,
            )
except Exception as e:
    db.rollback()
    logger.error("Campaign detection failed for %s: %s", aid, e)
```

This runs campaign detection for every athlete with recent activity during the daily 06:00 UTC fingerprint refresh. It's fire-and-forget — if it fails, the rest of the fingerprint refresh continues. The output goes to `PerformanceEvent.campaign_data` (JSONB column that already exists).

**Also wire into the Strava/Garmin post-sync path.** Search for where `mine_race_inputs` is called inline after sync. Add the same campaign detection block after it. This ensures campaigns update when new activities arrive, not just on the daily sweep.

Search for calls to `mine_race_inputs` outside of `intelligence_tasks.py`:

```
grep -r "mine_race_inputs" apps/api/ --include="*.py" -l
```

For each callsite, add the campaign detection block after the findings persistence.

---

## Task 2: Findings Regression Test

**New file:** `apps/api/tests/test_findings_regression.py`

Replace the current brittle mock/source-inspection checks with 3 behavioral tests that execute real logic paths.

```python
"""
Findings Regression Test

Prevents the recurring bug where code changes silently kill correlation
findings. If the founder's finding count drops below the established
baseline, CI goes red before it reaches production.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from models import CorrelationFinding
from services.correlation_persistence import persist_correlation_findings
from tasks import intelligence_tasks, strava_tasks


def test_mature_finding_survives_single_miss_sweep(db_session, test_athlete):
    """
    Behavioral guard:
    Mature findings (times_confirmed >= 3) are not deactivated when absent
    from one sweep.
    """
    finding = CorrelationFinding(
        athlete_id=test_athlete.id,
        input_name="sleep_hours",
        output_metric="efficiency",
        direction="positive",
        time_lag_days=1,
        correlation_coefficient=0.42,
        p_value=0.01,
        sample_size=40,
        strength="moderate",
        times_confirmed=5,
        category="pattern",
        confidence=0.8,
        is_active=True,
        last_confirmed_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(finding)
    db_session.commit()

    stats = persist_correlation_findings(
        athlete_id=test_athlete.id,
        analysis_result={"correlations": []},
        db=db_session,
        output_metric="efficiency",
    )
    db_session.refresh(finding)

    assert stats["deactivated"] == 0
    assert finding.is_active is True


def test_refresh_fingerprint_runs_campaign_detection_and_persists(monkeypatch):
    """
    Behavioral wiring guard for daily refresh path.
    """
    athlete_id = uuid.uuid4()

    q_active = MagicMock()
    q_active.filter.return_value = q_active
    q_active.distinct.return_value = q_active
    q_active.all.return_value = [(athlete_id,)]

    q_events = MagicMock()
    q_events.filter.return_value = q_events
    q_events.all.return_value = [MagicMock()]

    fake_db = MagicMock()
    fake_db.query.side_effect = [q_active, q_events]

    def _fake_get_db_sync():
        yield fake_db

    detect_mock = MagicMock(return_value=[{"t": "inflection"}])
    build_mock = MagicMock(return_value=[{"id": "campaign"}])
    store_mock = MagicMock(return_value=1)

    monkeypatch.setattr(intelligence_tasks, "get_db_sync", _fake_get_db_sync)
    monkeypatch.setattr("services.race_input_analysis.mine_race_inputs", lambda aid, db: ([], []))
    monkeypatch.setattr("services.campaign_detection.detect_inflection_points", detect_mock)
    monkeypatch.setattr("services.campaign_detection.build_campaigns", build_mock)
    monkeypatch.setattr("services.campaign_detection.store_campaign_data_on_events", store_mock)

    result = intelligence_tasks.refresh_living_fingerprint.run()

    assert result["refreshed"] == 1
    detect_mock.assert_called_once()
    build_mock.assert_called_once()
    store_mock.assert_called_once()
    assert fake_db.commit.call_count >= 1


def test_post_sync_campaign_detection_failure_is_non_blocking(monkeypatch):
    """
    Behavioral resilience guard for post-sync path.
    """
    athlete_id = str(uuid.uuid4())
    athlete_obj = MagicMock()
    athlete_obj.id = uuid.UUID(athlete_id)
    athlete_obj.preferred_units = "imperial"

    class _Q:
        def __init__(self, first=None, all_=None):
            self._first = first
            self._all = all_ or []
        def filter(self, *args, **kwargs): return self
        def order_by(self, *args, **kwargs): return self
        def first(self): return self._first
        def all(self): return self._all

    fake_db = MagicMock()
    fake_db.get.return_value = athlete_obj
    fake_db.query.side_effect = [
        _Q(first=None),
        _Q(all_=[]),
        _Q(all_=[]),
    ]

    def _fake_get_db_sync():
        return fake_db

    monkeypatch.setattr(strava_tasks, "get_db_sync", _fake_get_db_sync)
    monkeypatch.setattr(strava_tasks, "calculate_athlete_derived_signals", lambda *a, **k: None)
    monkeypatch.setattr(strava_tasks, "sync_strava_best_efforts", lambda *a, **k: {})
    monkeypatch.setattr(strava_tasks, "generate_insights_for_athlete", lambda *a, **k: [])
    monkeypatch.setattr("services.race_input_analysis.mine_race_inputs", lambda *a, **k: ([], []))
    monkeypatch.setattr("services.campaign_detection.detect_inflection_points", MagicMock(side_effect=RuntimeError("boom")))
    mark_dirty = MagicMock()
    enqueue_refresh = MagicMock()
    monkeypatch.setattr("services.home_briefing_cache.mark_briefing_dirty", mark_dirty)
    monkeypatch.setattr("tasks.home_briefing_tasks.enqueue_briefing_refresh", enqueue_refresh)

    result = strava_tasks.post_sync_processing_task.run(athlete_id)

    assert result["status"] == "success"
    mark_dirty.assert_called_once_with(athlete_id)
    enqueue_refresh.assert_called_once()
```

---

## Task 3: Verify on Production

After deploy, trigger a manual fingerprint refresh for the founder:

```bash
docker exec strideiq_api python -c "
from core.database import SessionLocal
from models import Athlete, PerformanceEvent
db = SessionLocal()

# Check campaign detection output
founder = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
events_with_campaigns = db.query(PerformanceEvent).filter(
    PerformanceEvent.athlete_id == founder.id,
    PerformanceEvent.campaign_data.isnot(None),
).all()

print(f'Events with campaign data: {len(events_with_campaigns)}')
for ev in events_with_campaigns:
    print(f'  {ev.event_date}: {ev.campaign_data.get(\"total_weeks\", \"?\")} weeks, '
          f'end_reason={ev.campaign_data.get(\"end_reason\", \"?\")}')

# Check correlation findings
from models import CorrelationFinding
active = db.query(CorrelationFinding).filter(
    CorrelationFinding.athlete_id == founder.id,
    CorrelationFinding.is_active == True,
).all()
print(f'\\nActive correlation findings: {len(active)}')
for f in sorted(active, key=lambda x: x.times_confirmed, reverse=True):
    print(f'  {f.input_name} -> {f.output_metric} (lag={f.time_lag_days}d, confirmed={f.times_confirmed}x, confounded={f.is_confounded})')

db.close()
"
```

**Expected:** The founder should have campaign data on their confirmed race events (especially the Nov 29 half and Dec 13 10K, which were part of the 6-month long run campaign). Active correlation findings should be >= 8.

---

## What this does NOT change

- Correlation engine logic (unchanged)
- Persistence/deactivation logic (unchanged)
- Surfacing threshold (stays at 3)
- Frontend (no visual changes)
- This is purely wiring + safety net
