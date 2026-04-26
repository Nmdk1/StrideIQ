"""
Findings Regression Test

Prevents the recurring bug where code changes silently kill correlation
findings. These are behavioral tests — they call the actual persistence
and task code, not hand-derived booleans on mocks.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from models import CorrelationFinding
from services.correlation_persistence import (
    persist_correlation_findings,
    SURFACING_THRESHOLD,
)
from tasks import intelligence_tasks, strava_tasks


# ---------------------------------------------------------------------------
# Constant guard
# ---------------------------------------------------------------------------

def test_surfacing_threshold_is_3():
    """The surfacing threshold should be 3 — not higher, not lower."""
    assert SURFACING_THRESHOLD == 3


# ---------------------------------------------------------------------------
# Behavioral persistence test (real DB)
# ---------------------------------------------------------------------------

def test_mature_finding_survives_single_miss_sweep(db_session, test_athlete):
    """
    A mature finding (times_confirmed >= 3) must NOT be deactivated
    when it is absent from a single sweep.
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
        first_detected_at=datetime.now(timezone.utc) - timedelta(days=30),
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


# ---------------------------------------------------------------------------
# Behavioral wiring guard — refresh path
# ---------------------------------------------------------------------------

def test_refresh_living_fingerprint_runs_campaign_detection(monkeypatch):
    """
    Campaign detection functions are actually called during the daily
    fingerprint refresh, and persistence is attempted.
    """
    athlete_id = uuid.uuid4()

    fake_db = MagicMock()

    # Query chain: 1) active athlete IDs, 2) confirmed events for campaign
    q_active = MagicMock()
    q_active.filter.return_value = q_active
    q_active.distinct.return_value = q_active
    q_active.all.return_value = [(athlete_id,)]

    q_events = MagicMock()
    q_events.filter.return_value = q_events
    q_events.all.return_value = [MagicMock()]

    fake_db.query.side_effect = [q_active, q_events]

    def _fake_get_db_sync():
        return fake_db

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


# ---------------------------------------------------------------------------
# Behavioral resilience guard — post-sync path
# ---------------------------------------------------------------------------

def test_post_sync_campaign_detection_failure_is_non_blocking(monkeypatch):
    """
    If campaign detection blows up during post-sync, the task still returns
    success and downstream work (briefing refresh) still runs.
    """
    athlete_id = str(uuid.uuid4())
    athlete_obj = MagicMock()
    athlete_obj.id = uuid.UUID(athlete_id)
    athlete_obj.preferred_units = "imperial"

    fake_db = MagicMock()
    fake_db.get.return_value = athlete_obj

    # post_sync_processing_task queries:
    # 1) most_recent activity  2) heat-adjustment  3) shape extraction
    # 4) PerformanceEvent for campaign  — each via db.query().filter()...
    class _Q:
        def __init__(self, first=None, all_=None):
            self._first = first
            self._all = all_ or []
        def filter(self, *a, **kw): return self
        def order_by(self, *a, **kw): return self
        def first(self): return self._first
        def all(self): return self._all

    fake_db.query.return_value = _Q()

    monkeypatch.setattr(strava_tasks, "get_db_sync", lambda: fake_db)
    monkeypatch.setattr(strava_tasks, "calculate_athlete_derived_signals", lambda *a, **k: None)
    monkeypatch.setattr(strava_tasks, "sync_strava_best_efforts", lambda *a, **k: {})
    monkeypatch.setattr(strava_tasks, "generate_insights_for_athlete", lambda *a, **k: [])
    monkeypatch.setattr("services.race_input_analysis.mine_race_inputs", lambda *a, **k: ([], []))
    monkeypatch.setattr(
        "services.campaign_detection.detect_inflection_points",
        MagicMock(side_effect=RuntimeError("boom")),
    )
    mark_dirty = MagicMock()
    enqueue_refresh = MagicMock()
    monkeypatch.setattr("services.home_briefing_cache.mark_briefing_dirty", mark_dirty)
    monkeypatch.setattr("tasks.home_briefing_tasks.enqueue_briefing_refresh", enqueue_refresh)

    result = strava_tasks.post_sync_processing_task.run(athlete_id)

    assert result["status"] == "success"
    mark_dirty.assert_called_once_with(athlete_id)
    enqueue_refresh.assert_called_once()
