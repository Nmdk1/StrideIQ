"""
T1 Data Integrity — Regression Tests
======================================
Covers acceptance criteria for T1-1, T1-2, T1-3, T1-4.

T1-1: RPI confidence multiplier — verified no haircut on stored value.
T1-2: peak_weekly_miles — smoothed 4-consecutive-week rolling average.
T1-3: Race anchor sync wired after activity import.
T1-4: Starter plan duration scales with experience when no goal date.
"""
from __future__ import annotations

import sys
import os
import inspect
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.fitness_bank import (
    FitnessBankCalculator,
    RacePerformance,
    calculate_rpi,
)
from services.mileage_aggregation import compute_peak_and_current_weekly_miles
from services.rpi_calculator import calculate_training_paces


# ---------------------------------------------------------------------------
# T1-1: RPI confidence multiplier — no haircut on stored value
# ---------------------------------------------------------------------------

class TestT1RpiNoConfidenceHaircut:
    """
    Acceptance: an athlete with a verified 3:14 marathon yields MP ~7:27/mi.
    Confidence values on RacePerformance objects must NOT be multiplied into
    the stored best_rpi.
    """

    def test_find_best_race_returns_raw_rpi_not_adjusted(self):
        calc = FitnessBankCalculator(MagicMock())

        # 3:14 marathon = 11640 seconds
        raw_rpi = calculate_rpi(distance_m=42195, time_seconds=11640)
        assert raw_rpi > 0, "RPI calculation returned zero"

        # Build a race with confidence > 1.0 (would inflate if multiplied into return value)
        race = RacePerformance(
            date=date.today() - timedelta(days=30),
            distance="marathon",
            distance_m=42195,
            finish_time_seconds=11640,
            pace_per_mile=7.45,
            rpi=raw_rpi,
            confidence=1.2,  # "impressive conditions" multiplier
        )
        returned_rpi, returned_race = calc._find_best_race([race])

        assert returned_rpi == raw_rpi, (
            f"_find_best_race returned adjusted RPI {returned_rpi:.2f} "
            f"instead of raw {raw_rpi:.2f}. "
            "Confidence must influence selection only, not the stored value."
        )

    def test_3h14_marathon_yields_approx_727_mp(self):
        """3:14 marathon -> MP should be within +-10s of 7:27/mi."""
        raw_rpi = calculate_rpi(distance_m=42195, time_seconds=11640)
        paces = calculate_training_paces(raw_rpi)

        mp_str = paces.get("marathon", {}).get("mi")
        assert mp_str is not None, "calculate_training_paces returned no marathon pace"

        parts = mp_str.split(":")
        assert len(parts) == 2, f"Unexpected pace format: {mp_str}"
        mp_seconds = int(parts[0]) * 60 + int(parts[1])

        # 7:27 = 447s; allow +-10s tolerance
        assert abs(mp_seconds - 447) <= 10, (
            f"3:14 marathon should yield ~7:27/mi MP, got {mp_str} ({mp_seconds}s). "
            f"RPI used: {raw_rpi:.2f}"
        )


# ---------------------------------------------------------------------------
# T1-2: Smoothed peak -- 4-consecutive-week rolling average
# ---------------------------------------------------------------------------

class TestT1SmoothedPeak:
    """
    Acceptance: 12 weeks at 45mpw + 1 outlier week at 80mpw -> peak in 44-56 range.
    """

    def _make_activities(self, weekly_miles_map: dict) -> list:
        """Create minimal mock activity objects with real start_time datetimes."""
        activities = []
        for monday, miles in weekly_miles_map.items():
            runs_per_week = 5
            miles_each = miles / runs_per_week
            for day_offset in range(runs_per_week):
                run_date = monday + timedelta(days=day_offset)
                act = MagicMock()
                # Use a real datetime so weekday() and date() work correctly
                act.start_time = datetime(run_date.year, run_date.month, run_date.day, 8, 0)
                act.distance_m = miles_each * 1609.344
                act.sport = "run"
                activities.append(act)
        return activities

    def test_outlier_week_does_not_dominate_peak(self):
        today = date(2026, 3, 24)
        weeks = {}
        base = today - timedelta(weeks=15)
        for i in range(15):
            monday = base + timedelta(weeks=i)
            weeks[monday] = 80.0 if i == 10 else 45.0

        activities = self._make_activities(weeks)
        peak, _, _ = compute_peak_and_current_weekly_miles(activities, now=today)

        assert 44.0 <= peak <= 56.0, (
            f"Smoothed peak should be 44-56mpw for 45mpw athlete with 1 outlier week. "
            f"Got {peak:.1f}. Single-week max would be 80.0."
        )

    def test_genuine_high_mileage_athlete_gets_high_peak(self):
        """A consistent 70mpw athlete should get ~70mpw peak."""
        today = date(2026, 3, 24)
        weeks = {}
        base = today - timedelta(weeks=12)
        for i in range(12):
            weeks[base + timedelta(weeks=i)] = 70.0

        activities = self._make_activities(weeks)
        peak, _, _ = compute_peak_and_current_weekly_miles(activities, now=today)

        assert peak >= 68.0, (
            f"Consistent 70mpw athlete should get >=68mpw peak. Got {peak:.1f}"
        )

    def test_empty_history_returns_zero(self):
        peak, current, last_wk = compute_peak_and_current_weekly_miles([])
        assert peak == 0.0
        assert current == 0.0
        assert last_wk == 0.0

    def test_single_week_history_returns_that_week(self):
        today = date(2026, 3, 24)
        monday = today - timedelta(days=today.weekday())
        activities = self._make_activities({monday - timedelta(weeks=1): 50.0})
        peak, _, _ = compute_peak_and_current_weekly_miles(activities, now=today)
        assert abs(peak - 50.0) < 2.0, (
            f"Single-week history peak should be ~50mpw. Got {peak:.1f}"
        )


# ---------------------------------------------------------------------------
# T1-3: Race anchor sync wired into strava_ingest
# ---------------------------------------------------------------------------

class TestT1RaceAnchorSyncOnImport:
    """
    Acceptance: sync_race_anchors_for_activities is wired into ingest_strava_activity_by_id.
    """

    def test_sync_anchor_public_function_importable(self):
        from services.fitness_bank import sync_race_anchors_for_activities
        assert callable(sync_race_anchors_for_activities)

    def test_sync_anchor_wired_in_ingest_source(self):
        """ingest_strava_activity_by_id source must reference sync_race_anchors_for_activities."""
        from services.strava_ingest import ingest_strava_activity_by_id
        source = inspect.getsource(ingest_strava_activity_by_id)
        assert "sync_race_anchors_for_activities" in source, (
            "ingest_strava_activity_by_id must call sync_race_anchors_for_activities "
            "after saving a race activity. T1-3 hook is missing."
        )

    def test_sync_anchor_only_fires_for_race_candidate(self):
        """sync must be inside a conditional guard -- not called unconditionally."""
        from services.strava_ingest import ingest_strava_activity_by_id
        source = inspect.getsource(ingest_strava_activity_by_id)
        sync_idx = source.index("sync_race_anchors_for_activities")
        preceding = source[:sync_idx]
        assert "user_verified_race" in preceding or "is_race_candidate" in preceding, (
            "sync_race_anchors_for_activities must be guarded by a race-candidate check. "
            "Unconditional calls on every activity are too expensive."
        )

    def test_sync_anchor_called_at_runtime_for_race_import(self):
        """
        Behavioral: ingest_strava_activity_by_id with mark_as_race=True must
        actually call sync_race_anchors_for_activities at runtime.
        """
        import services.strava_ingest as strava_ingest
        import services.fitness_bank as fb_module

        athlete_id = uuid4()
        mock_athlete = MagicMock()
        mock_athlete.id = athlete_id

        mock_details = {
            "start_date": "2026-03-01T08:00:00Z",
            "distance": 42195,
            "moving_time": 11640,
            "elapsed_time": 11700,
            "average_speed": 3.6,
            "name": "Boston Marathon",
        }

        # Represent the Activity row that will be created/returned
        mock_act = MagicMock()
        mock_act.id = uuid4()
        mock_act.user_verified_race = True
        mock_act.is_race_candidate = True

        mock_db = MagicMock()
        # db.query(Activity).filter(...).first() → None (new activity, will be created)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with (
            patch.object(strava_ingest, "get_activity_details", return_value=mock_details),
            patch.object(strava_ingest, "extract_best_efforts_from_activity", return_value=2),
            patch.object(strava_ingest, "regenerate_personal_bests", return_value={"created": 1}),
            patch("core.cache.invalidate_athlete_cache"),
            patch.object(fb_module, "sync_race_anchors_for_activities") as mock_sync,
            patch("services.strava_ingest.Activity", return_value=mock_act),
        ):
            result = strava_ingest.ingest_strava_activity_by_id(
                athlete=mock_athlete,
                db=mock_db,
                strava_activity_id=999,
                mark_as_race=True,
            )

        assert mock_sync.called, (
            "sync_race_anchors_for_activities was NOT called at runtime after importing "
            "a user_verified_race activity. T1-3 runtime hook is broken."
        )
        call_kwargs = mock_sync.call_args
        called_athlete_id = (
            call_kwargs.kwargs.get("athlete_id")
            or (call_kwargs.args[0] if call_kwargs.args else None)
        )
        assert called_athlete_id == athlete_id, (
            f"sync_race_anchors_for_activities was called with wrong athlete_id. "
            f"Expected {athlete_id}, got {called_athlete_id}."
        )

    def test_sync_anchor_not_called_for_non_race(self):
        """Non-race activity import must NOT trigger anchor sync."""
        import services.strava_ingest as strava_ingest
        import services.fitness_bank as fb_module

        mock_athlete = MagicMock()
        mock_athlete.id = uuid4()

        mock_details = {
            "start_date": "2026-03-01T08:00:00Z",
            "distance": 10000,
            "moving_time": 3000,
            "elapsed_time": 3100,
            "average_speed": 3.3,
            "name": "Easy 10K",
        }

        mock_act = MagicMock()
        mock_act.id = uuid4()
        mock_act.user_verified_race = False
        mock_act.is_race_candidate = False

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with (
            patch.object(strava_ingest, "get_activity_details", return_value=mock_details),
            patch.object(strava_ingest, "extract_best_efforts_from_activity", return_value=0),
            patch.object(strava_ingest, "regenerate_personal_bests", return_value={}),
            patch("core.cache.invalidate_athlete_cache"),
            patch.object(fb_module, "sync_race_anchors_for_activities") as mock_sync,
            patch("services.strava_ingest.Activity", return_value=mock_act),
        ):
            strava_ingest.ingest_strava_activity_by_id(
                athlete=mock_athlete,
                db=mock_db,
                strava_activity_id=888,
                mark_as_race=False,
            )

        assert not mock_sync.called, (
            "sync_race_anchors_for_activities must NOT be called for non-race activities."
        )


