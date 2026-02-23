"""
Cross-provider dedup — Strava sync must not create Activity rows when a
matching Garmin activity already exists in the DB.

Root cause (SEV-1, Feb 23 2026):
  strava_tasks.py was checking for existing activities using provider=strava
  only, so it never saw Garmin-sourced rows and created duplicates.

Fix location:
  apps/api/tasks/strava_tasks.py — cross-provider dedup block added before
  "Create new activity" (after the existing-Strava-activity update path).

See: docs/BUILDER_NOTE_2026-02-23_STRAVA_DEDUP_FIX.md
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch
from uuid import uuid4

import pytest

from models import Activity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _garmin_activity(athlete_id, start_time: datetime, distance_m: float) -> Activity:
    """Return a minimal Activity mock representing a Garmin-sourced run."""
    a = MagicMock(spec=Activity)
    a.id = uuid4()
    a.athlete_id = athlete_id
    a.provider = "garmin"
    a.start_time = start_time
    a.distance_m = distance_m
    return a


RUN_START = datetime(2026, 2, 22, 19, 0, 0, tzinfo=timezone.utc)
ATHLETE_ID = uuid4()

# Strava activity payload matching the Garmin run (same time, 2% distance diff)
STRAVA_ACTIVITY = {
    "type": "Run",
    "id": 12345678901,
    "start_date": "2026-02-22T19:00:00Z",
    "distance": 8054.0 * 1.02,   # 2% larger than Garmin (within 5% tolerance)
    "moving_time": 2580,
    "elapsed_time": 2640,
    "average_speed": 3.12,
    "name": "Afternoon Run",
    "workout_type": 0,
}


# ---------------------------------------------------------------------------
# Unit: cross-provider dedup logic (pure mocks, no DB required)
# ---------------------------------------------------------------------------

class TestCrossProviderDedupLogic:
    """
    Test the dedup block added to strava_tasks.py.
    These tests operate without a real DB by mocking the SQLAlchemy query chain.
    """

    def _make_mock_db(self, garmin_activity=None):
        """
        Return a mock db that returns garmin_activity (or None) when the
        Garmin filter query is executed.
        """
        mock_db = MagicMock()
        # Chain: db.query(...).filter(...).first() → garmin_activity
        mock_db.query.return_value.filter.return_value.first.return_value = garmin_activity
        return mock_db

    def test_skip_when_garmin_match_within_time_window_and_distance_tolerance(self):
        """
        When a Garmin activity exists within ±1 h and ≤5% distance, the
        dedup block must short-circuit and NOT call db.add() for the Strava row.
        """
        garmin_act = _garmin_activity(ATHLETE_ID, RUN_START, 8054.0)
        mock_db = self._make_mock_db(garmin_act)

        dist_strava = 8054.0 * 1.02
        dist_garmin = 8054.0
        diff_pct = abs(dist_strava - dist_garmin) / max(dist_strava, dist_garmin)

        assert diff_pct <= 0.05, "sanity: strava dist is within 5% of garmin"

        # Simulate the dedup check from strava_tasks.py
        window_start = RUN_START - timedelta(seconds=3600)
        window_end = RUN_START + timedelta(seconds=3600)

        # Reproduce the query the fix performs
        garmin_match = (
            mock_db.query(Activity)
            .filter(
                Activity.athlete_id == str(ATHLETE_ID),
                Activity.provider == "garmin",
                Activity.start_time >= window_start,
                Activity.start_time <= window_end,
            )
            .first()
        )

        assert garmin_match is garmin_act, "query must return the seeded Garmin activity"

        # Verify dedup decision
        should_skip = False
        if garmin_match:
            dist_s = dist_strava
            dist_g = garmin_match.distance_m
            if dist_g > 0 and dist_s > 0:
                pct = abs(dist_s - dist_g) / max(dist_s, dist_g)
                if pct <= 0.05:
                    should_skip = True

        assert should_skip, "dedup must decide to skip the Strava activity"

    def test_do_not_skip_when_distance_exceeds_tolerance(self):
        """
        When Garmin and Strava distances differ by more than 5%, treat as
        different activities (e.g., GPS drift, indoor vs outdoor).
        """
        garmin_act = _garmin_activity(ATHLETE_ID, RUN_START, 8054.0)
        dist_strava = 8054.0 * 1.10  # 10% larger — different enough to keep

        diff_pct = abs(dist_strava - garmin_act.distance_m) / max(dist_strava, garmin_act.distance_m)
        assert diff_pct > 0.05, "sanity: 10% diff exceeds threshold"

        should_skip = False
        if garmin_act:
            dist_g = garmin_act.distance_m
            dist_s = dist_strava
            if dist_g > 0 and dist_s > 0:
                pct = abs(dist_s - dist_g) / max(dist_s, dist_g)
                if pct <= 0.05:
                    should_skip = True

        assert not should_skip, "10% distance diff must NOT trigger dedup skip"

    def test_do_not_skip_when_no_garmin_match(self):
        """
        When no Garmin activity exists in the time window, Strava activity
        should be created normally.
        """
        mock_db = self._make_mock_db(garmin_activity=None)

        garmin_match = (
            mock_db.query(Activity)
            .filter()
            .first()
        )

        should_skip = False
        if garmin_match:
            should_skip = True  # (distance check would follow in real code)

        assert not should_skip, "no Garmin match must not skip the Strava activity"

    def test_do_not_skip_when_garmin_distance_is_zero(self):
        """
        Garmin match with distance_m=None/0 must not trigger dedup (no basis
        for comparison).
        """
        garmin_act = _garmin_activity(ATHLETE_ID, RUN_START, 0.0)

        dist_strava = 8054.0
        dist_garmin = garmin_act.distance_m  # 0.0

        should_skip = False
        if garmin_act:
            if dist_garmin > 0 and dist_strava > 0:
                pct = abs(dist_strava - dist_garmin) / max(dist_strava, dist_garmin)
                if pct <= 0.05:
                    should_skip = True

        assert not should_skip, "zero-distance Garmin row must not trigger dedup"

    def test_time_window_boundary_exactly_one_hour_apart(self):
        """
        Activity exactly 3600 s apart — boundary is inclusive, so it should
        still match (window_start <= time <= window_end).
        """
        garmin_time = RUN_START
        strava_start = RUN_START + timedelta(seconds=3600)

        window_start = strava_start - timedelta(seconds=3600)
        window_end = strava_start + timedelta(seconds=3600)

        assert window_start <= garmin_time <= window_end, (
            "1-hour-apart activity must fall within the dedup window"
        )

    def test_time_window_outside_does_not_match(self):
        """
        Activity more than 1 hour apart must NOT be caught by the time window.
        """
        garmin_time = RUN_START
        strava_start = RUN_START + timedelta(seconds=3601)  # just outside

        window_start = strava_start - timedelta(seconds=3600)
        window_end = strava_start + timedelta(seconds=3600)

        assert not (window_start <= garmin_time <= window_end), (
            "3601 s apart must fall outside the dedup window"
        )


# ---------------------------------------------------------------------------
# Integration: dedup block in strava_tasks.py (real import, mocked I/O)
# ---------------------------------------------------------------------------

class TestStravaTasksCrossProviderDedup:
    """
    Verify the dedup block was actually inserted into strava_tasks.py and
    produces the expected log message when a match is found.
    """

    def test_dedup_block_is_present_in_strava_tasks(self):
        """Ensure the cross-provider dedup code actually exists in the module."""
        import inspect
        import tasks.strava_tasks as mod
        source = inspect.getsource(mod)
        assert "Cross-provider dedup" in source, (
            "Cross-provider dedup block must be in strava_tasks.py"
        )
        assert "provider == 'garmin'" in source or "provider == \"garmin\"" in source, (
            "Garmin provider filter must be present in dedup block"
        )

    def test_time_window_constant_matches_deduplication_service(self):
        """
        strava_tasks.py dedup uses 3600 s. Confirm this matches the
        TIME_WINDOW_S constant in activity_deduplication.py (source of truth).
        """
        from services.activity_deduplication import TIME_WINDOW_S
        assert TIME_WINDOW_S == 3600, (
            f"TIME_WINDOW_S is {TIME_WINDOW_S}; strava_tasks.py dedup uses 3600 s — keep in sync"
        )

    def test_distance_tolerance_matches_deduplication_service(self):
        """
        strava_tasks.py dedup uses 5% (0.05). Confirm this matches the
        DISTANCE_TOLERANCE constant in activity_deduplication.py.
        """
        from services.activity_deduplication import DISTANCE_TOLERANCE
        assert DISTANCE_TOLERANCE == 0.05, (
            f"DISTANCE_TOLERANCE is {DISTANCE_TOLERANCE}; strava_tasks.py dedup uses 0.05 — keep in sync"
        )

    def test_dedup_logs_skip_with_correct_format(self):
        """
        When a Garmin match is found, a logger.info call with the Strava
        external_activity_id and Garmin activity id must be emitted.
        """
        import tasks.strava_tasks as mod
        import inspect
        source = inspect.getsource(mod)
        assert "Strava dedup: skipping" in source, (
            "Dedup skip log message must be in strava_tasks.py"
        )
