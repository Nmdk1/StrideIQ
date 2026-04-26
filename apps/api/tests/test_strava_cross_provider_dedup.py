"""
Cross-provider dedup — Strava sync must not create Activity rows when a
matching Garmin activity already exists in the DB.

Root cause (SEV-1, Feb 23 2026):
  strava_tasks.py was checking for existing activities using provider=strava
  only, so it never saw Garmin-sourced rows and created duplicates.

Regression (SEV-2, Mar 08 2026):
  The dedup used .first() to find a single Garmin candidate. When an athlete
  had a 1-mile warmup AND a 10-mile race within the ±1h window, .first()
  could return the warmup, the distance check would fail (90% diff), and a
  duplicate Strava activity was created. Fixed by using .all() + iterating
  with match_activities() — mirroring the Garmin webhook pattern.

Fix location:
  apps/api/tasks/strava_tasks.py — cross-provider dedup block uses .all()
  and services.activity_deduplication.match_activities().

See: docs/BUILDER_NOTE_2026-02-23_STRAVA_DEDUP_FIX.md
     docs/BUILDER_INSTRUCTIONS_2026-03-08_WORKER_AND_DEDUP.md
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch
from uuid import uuid4

import pytest

from models import Activity
from services.activity_deduplication import match_activities


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _garmin_activity(athlete_id, start_time: datetime, distance_m: float, avg_hr=None) -> Activity:
    """Return a minimal Activity mock representing a Garmin-sourced run."""
    a = MagicMock(spec=Activity)
    a.id = uuid4()
    a.athlete_id = athlete_id
    a.provider = "garmin"
    a.start_time = start_time
    a.distance_m = distance_m
    a.avg_hr = avg_hr
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
# Unit: cross-provider dedup logic using match_activities
# ---------------------------------------------------------------------------

class TestCrossProviderDedupLogic:
    """
    Test the dedup logic using match_activities() — the shared dedup service
    that strava_tasks.py now delegates to.
    """

    def test_skip_when_garmin_match_within_time_window_and_distance_tolerance(self):
        garmin_act = _garmin_activity(ATHLETE_ID, RUN_START, 8054.0)
        strava_dict = {
            "start_time": RUN_START,
            "distance_m": 8054.0 * 1.02,
            "avg_hr": None,
        }
        garmin_dict = {
            "start_time": garmin_act.start_time,
            "distance_m": float(garmin_act.distance_m),
            "avg_hr": garmin_act.avg_hr,
        }
        assert match_activities(strava_dict, garmin_dict), (
            "2% distance diff within 1h window must match"
        )

    def test_do_not_skip_when_distance_exceeds_tolerance(self):
        garmin_act = _garmin_activity(ATHLETE_ID, RUN_START, 8054.0)
        strava_dict = {
            "start_time": RUN_START,
            "distance_m": 8054.0 * 1.10,
            "avg_hr": None,
        }
        garmin_dict = {
            "start_time": garmin_act.start_time,
            "distance_m": float(garmin_act.distance_m),
            "avg_hr": garmin_act.avg_hr,
        }
        assert not match_activities(strava_dict, garmin_dict), (
            "10% distance diff must NOT match"
        )

    def test_do_not_skip_when_no_garmin_candidates(self):
        candidates = []
        strava_dict = {
            "start_time": RUN_START,
            "distance_m": 8054.0,
            "avg_hr": None,
        }
        skip = any(
            match_activities(strava_dict, {
                "start_time": c.start_time,
                "distance_m": float(c.distance_m) if c.distance_m else None,
                "avg_hr": c.avg_hr,
            })
            for c in candidates
        )
        assert not skip, "empty candidate list must not trigger dedup"

    def test_do_not_skip_when_garmin_distance_is_zero(self):
        strava_dict = {
            "start_time": RUN_START,
            "distance_m": 8054.0,
            "avg_hr": None,
        }
        garmin_dict = {
            "start_time": RUN_START,
            "distance_m": 0.0,
            "avg_hr": None,
        }
        assert not match_activities(strava_dict, garmin_dict), (
            "zero-distance Garmin must not match"
        )

    def test_warmup_plus_race_matches_correct_activity(self):
        """
        The critical bug: two Garmin activities in the window — a 1-mile
        warmup and a 10-mile race. The Strava 10-mile race must match the
        Garmin race, not the warmup.
        """
        warmup_start = RUN_START - timedelta(minutes=26)
        race_start = RUN_START

        warmup = _garmin_activity(ATHLETE_ID, warmup_start, 1609.0)
        race = _garmin_activity(ATHLETE_ID, race_start, 16093.0)
        candidates = [warmup, race]

        strava_dict = {
            "start_time": race_start,
            "distance_m": 16093.0 * 1.01,
            "avg_hr": 165,
        }

        matched = None
        for c in candidates:
            c_dict = {
                "start_time": c.start_time,
                "distance_m": float(c.distance_m) if c.distance_m is not None else None,
                "avg_hr": c.avg_hr,
            }
            if match_activities(strava_dict, c_dict):
                matched = c
                break

        assert matched is race, (
            "Strava 10mi race must match the Garmin 10mi race, not the 1mi warmup"
        )

    def test_warmup_does_not_match_race(self):
        """The warmup (1mi) must NOT match the race (10mi)."""
        strava_dict = {
            "start_time": RUN_START,
            "distance_m": 16093.0,
            "avg_hr": None,
        }
        warmup_dict = {
            "start_time": RUN_START - timedelta(minutes=26),
            "distance_m": 1609.0,
            "avg_hr": None,
        }
        assert not match_activities(strava_dict, warmup_dict), (
            "10mi Strava race must not match 1mi Garmin warmup"
        )

    def test_time_window_boundary_exactly_eight_hours_apart(self):
        """Activity exactly TIME_WINDOW_S apart must still match."""
        from services.activity_deduplication import TIME_WINDOW_S
        garmin_dict = {"start_time": RUN_START, "distance_m": 8054.0, "avg_hr": None}
        strava_dict = {
            "start_time": RUN_START + timedelta(seconds=TIME_WINDOW_S),
            "distance_m": 8054.0 * 1.02,
            "avg_hr": None,
        }
        assert match_activities(garmin_dict, strava_dict), (
            "Activity at exactly TIME_WINDOW_S boundary must match"
        )

    def test_time_window_outside_does_not_match(self):
        """Activity one second beyond TIME_WINDOW_S must not match."""
        from services.activity_deduplication import TIME_WINDOW_S
        garmin_dict = {"start_time": RUN_START, "distance_m": 8054.0, "avg_hr": None}
        strava_dict = {
            "start_time": RUN_START + timedelta(seconds=TIME_WINDOW_S + 1),
            "distance_m": 8054.0 * 1.02,
            "avg_hr": None,
        }
        assert not match_activities(garmin_dict, strava_dict), (
            "Activity one second beyond TIME_WINDOW_S must NOT match"
        )

    def test_five_hour_garmin_strava_sync_delay_matches(self):
        """
        Garmin records at run-end; Strava receives the upload ~5h later.
        This is the real-world pattern that the original 1-hour window missed.
        """
        garmin_dict = {
            "start_time": RUN_START,
            "distance_m": 16093.0,   # 10 miles
            "avg_hr": 148,
        }
        strava_dict = {
            "start_time": RUN_START + timedelta(hours=5),
            "distance_m": 16093.0 * 1.01,
            "avg_hr": 150,
        }
        assert match_activities(garmin_dict, strava_dict), (
            "5-hour Garmin→Strava sync delay must be recognised as a duplicate"
        )


# ---------------------------------------------------------------------------
# Integration: dedup block in strava_tasks.py (real import, mocked I/O)
# ---------------------------------------------------------------------------

class TestStravaTasksCrossProviderDedup:
    """
    Verify the dedup block structure in strava_tasks.py.
    """

    def test_dedup_block_is_present_in_strava_tasks(self):
        import inspect
        import tasks.strava_tasks as mod
        source = inspect.getsource(mod)
        assert "Cross-provider dedup" in source
        assert "provider == 'garmin'" in source or 'provider == "garmin"' in source

    def test_uses_all_not_first(self):
        """The dedup must use .all() to find ALL Garmin candidates, not .first()."""
        import inspect
        import tasks.strava_tasks as mod
        source = inspect.getsource(mod)
        dedup_start = source.index("Cross-provider dedup")
        dedup_block = source[dedup_start:dedup_start + 1200]
        assert ".all()" in dedup_block, (
            "Dedup block must use .all() to find all Garmin candidates"
        )
        assert ".first()" not in dedup_block, (
            "Dedup block must NOT use .first() — causes warmup/race bug"
        )

    def test_uses_match_activities(self):
        """The dedup must delegate to match_activities(), not inline distance checks."""
        import inspect
        import tasks.strava_tasks as mod
        source = inspect.getsource(mod)
        dedup_start = source.index("Cross-provider dedup")
        dedup_block = source[dedup_start:dedup_start + 1200]
        assert "match_activities" in dedup_block

    def test_time_window_constant_matches_deduplication_service(self):
        from services.activity_deduplication import TIME_WINDOW_S
        assert TIME_WINDOW_S == 28800, (
            "TIME_WINDOW_S must be 28800 (8h) to cover Garmin→Strava sync delay"
        )

    def test_dedup_logs_skip_with_correct_format(self):
        import inspect
        import tasks.strava_tasks as mod
        source = inspect.getsource(mod)
        assert "Strava dedup: skipping" in source
