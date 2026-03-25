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
from services.starter_plan import _goal_date_from_intake


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
        peak, _ = compute_peak_and_current_weekly_miles(activities, now=today)

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
        peak, _ = compute_peak_and_current_weekly_miles(activities, now=today)

        assert peak >= 68.0, (
            f"Consistent 70mpw athlete should get >=68mpw peak. Got {peak:.1f}"
        )

    def test_empty_history_returns_zero(self):
        peak, current = compute_peak_and_current_weekly_miles([])
        assert peak == 0.0
        assert current == 0.0

    def test_single_week_history_returns_that_week(self):
        today = date(2026, 3, 24)
        monday = today - timedelta(days=today.weekday())
        activities = self._make_activities({monday - timedelta(weeks=1): 50.0})
        peak, _ = compute_peak_and_current_weekly_miles(activities, now=today)
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


# ---------------------------------------------------------------------------
# T1-4: Starter plan duration scales with experience, no semi-custom without race
# ---------------------------------------------------------------------------

class TestT1StarterPlanNullGoalDate:
    """
    Acceptance: goal_event_date absent -> experience-scaled duration, no semi-custom.
    """

    def test_goal_date_helper_returns_none_when_key_absent(self):
        assert _goal_date_from_intake({}) is None
        assert _goal_date_from_intake({"goal_event_date": ""}) is None
        assert _goal_date_from_intake({"goal_event_date": None}) is None

    def test_no_goal_date_in_source_defaults_to_experience_block(self):
        """ensure_starter_plan source must NOT contain raw +8-week default."""
        import services.starter_plan as sp
        source = inspect.getsource(sp.ensure_starter_plan)
        assert "weeks=8" not in source, (
            "ensure_starter_plan must not hard-code 8-week default. "
            "Duration must scale with athlete experience level."
        )

    def test_base_building_block_durations_in_source(self):
        """Source must encode the three experience-scaled durations (12, 16, 18)."""
        import services.starter_plan as sp
        source = inspect.getsource(sp.ensure_starter_plan)
        assert "base_weeks = 18" in source, "Missing 18w block for experienced athletes"
        assert "base_weeks = 16" in source, "Missing 16w block for intermediate athletes"
        assert "base_weeks = 12" in source, "Missing 12w block for beginner athletes"

    def test_semi_custom_skipped_when_base_building(self):
        """Source guard ensures _is_base_building suppresses semi-custom path."""
        import services.starter_plan as sp
        source = inspect.getsource(sp.ensure_starter_plan)
        assert "_is_base_building" in source, (
            "_is_base_building flag must exist in ensure_starter_plan"
        )
        semi_custom_idx = source.index("generate_semi_custom")
        preceding = source[:semi_custom_idx]
        assert "_is_base_building" in preceding, (
            "generate_semi_custom call must be guarded by _is_base_building check"
        )

    @pytest.mark.parametrize("weekly_miles,expected_min_weeks,expected_max_weeks", [
        (15.0, 11, 13),   # beginner -> 12w base block
        (35.0, 15, 17),   # intermediate -> 16w base block
        (55.0, 17, 19),   # experienced -> 18w base block
    ])
    def test_no_goal_date_produces_experience_scaled_duration_at_runtime(
        self, weekly_miles, expected_min_weeks, expected_max_weeks
    ):
        """
        Behavioral: ensure_starter_plan with no goal_event_date in intake must
        call generate_standard with duration_weeks in the experience-scaled range.
        Exercises the runtime code path, not just source inspection.
        """
        import services.starter_plan as sp
        from models import TrainingPlan, IntakeQuestionnaire, AthleteRaceResultAnchor

        mock_athlete = MagicMock()
        mock_athlete.id = uuid4()
        mock_athlete.onboarding_completed = True

        # Intake responses with no goal_event_date key
        mock_intake = MagicMock()
        mock_intake.responses = {
            "goal_distance": "half_marathon",
            "weekly_mileage_target": weekly_miles,
            "days_per_week": 5,
        }

        mock_plan = MagicMock()
        mock_plan.workouts = []
        mock_plan.id = uuid4()

        # Track the duration_weeks argument passed to generate_standard
        captured_duration = []

        def fake_generate_standard(**kwargs):
            captured_duration.append(kwargs.get("duration_weeks"))
            return mock_plan

        mock_db = MagicMock()

        def db_query_side_effect(model):
            q = MagicMock()
            if model is TrainingPlan:
                # No existing active plan
                q.filter.return_value.first.return_value = None
            elif model is IntakeQuestionnaire:
                q.filter.return_value.order_by.return_value.first.return_value = mock_intake
            elif model is AthleteRaceResultAnchor:
                # No anchor — avoids semi-custom path
                q.filter.return_value.first.return_value = None
            else:
                from models import Activity
                if model is Activity:
                    q.filter.return_value.count.return_value = 0
                    q.filter.return_value.first.return_value = None
                else:
                    q.filter.return_value.first.return_value = None
                    q.filter.return_value.count.return_value = 0
            return q

        mock_db.query.side_effect = db_query_side_effect

        with patch("services.plan_framework.generator.PlanGenerator") as MockGen:
            mock_gen = MockGen.return_value
            mock_gen.generate_standard.side_effect = fake_generate_standard
            mock_gen.generate_semi_custom.return_value = mock_plan
            mock_gen.tier_classifier.classify.return_value = MagicMock(value="mid")

            try:
                sp.ensure_starter_plan(db=mock_db, athlete=mock_athlete)
            except Exception:
                pass  # We only need the captured call args

        assert len(captured_duration) > 0, (
            f"generate_standard was never called for {weekly_miles}mpw no-goal-date athlete."
        )
        duration = captured_duration[0]
        assert duration is not None, "generate_standard called with duration_weeks=None"
        assert expected_min_weeks <= duration <= expected_max_weeks, (
            f"{weekly_miles}mpw athlete with no goal date should get "
            f"{expected_min_weeks}-{expected_max_weeks}w plan. Got {duration}w."
        )

    def test_semi_custom_not_called_at_runtime_without_race_date(self):
        """
        Behavioral: even with a valid anchor, ensure_starter_plan must NOT call
        generate_semi_custom when no goal_event_date is present.
        """
        import services.starter_plan as sp
        from models import TrainingPlan, IntakeQuestionnaire, AthleteRaceResultAnchor, Activity

        mock_athlete = MagicMock()
        mock_athlete.id = uuid4()
        mock_athlete.onboarding_completed = True

        mock_intake = MagicMock()
        mock_intake.responses = {
            "goal_distance": "marathon",
            "weekly_mileage_target": 50.0,
            "days_per_week": 6,
            # Intentionally no goal_event_date
        }

        mock_anchor = MagicMock()
        mock_anchor.distance_key = "marathon"
        mock_anchor.time_seconds = 11640

        mock_plan = MagicMock()
        mock_plan.workouts = []
        mock_plan.id = uuid4()

        mock_db = MagicMock()

        def db_query_side_effect(model):
            q = MagicMock()
            if model is TrainingPlan:
                q.filter.return_value.first.return_value = None
            elif model is IntakeQuestionnaire:
                q.filter.return_value.order_by.return_value.first.return_value = mock_intake
            elif model is AthleteRaceResultAnchor:
                q.filter.return_value.first.return_value = mock_anchor
            elif model is Activity:
                q.filter.return_value.count.return_value = 10
                q.filter.return_value.first.return_value = None
            else:
                q.filter.return_value.first.return_value = None
                q.filter.return_value.count.return_value = 0
            return q

        mock_db.query.side_effect = db_query_side_effect

        with patch("services.plan_framework.generator.PlanGenerator") as MockGen:
            mock_gen = MockGen.return_value
            mock_gen.generate_standard.return_value = mock_plan
            mock_gen.generate_semi_custom.return_value = mock_plan
            mock_gen.tier_classifier.classify.return_value = MagicMock(value="high")

            try:
                sp.ensure_starter_plan(db=mock_db, athlete=mock_athlete)
            except Exception:
                pass

        assert not mock_gen.generate_semi_custom.called, (
            "generate_semi_custom must NOT be called when no goal_event_date is present, "
            "even if the athlete has a valid race anchor. "
            "Semi-custom generates taper phases which are wrong for base-building plans."
        )
