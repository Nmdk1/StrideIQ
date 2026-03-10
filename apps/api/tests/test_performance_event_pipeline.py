"""Tests for PerformanceEvent pipeline and curation API (Phase 1A)."""

import uuid
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from services.performance_event_pipeline import (
    populate_performance_events,
    compute_block_signature,
    classify_race_role,
    _mark_personal_bests,
    LOOKBACK_WEEKS,
)


def _mock_activity(
    provider="strava", distance_m=10000, duration_s=3600,
    avg_hr=150, max_hr=185, name=None, start_date=None,
    is_race_candidate=False, strava_workout_type_raw=None,
    user_verified_race=None, is_dup=False,
):
    act = MagicMock()
    act.id = uuid.uuid4()
    act.athlete_id = uuid.uuid4()
    act.provider = provider
    act.distance_m = distance_m
    act.duration_s = duration_s
    act.avg_hr = avg_hr
    act.max_hr = max_hr
    act.name = name
    act.start_time = datetime.combine(start_date or date(2025, 6, 15), datetime.min.time())
    act.is_duplicate = is_dup
    act.is_race_candidate = is_race_candidate
    act.strava_workout_type_raw = strava_workout_type_raw
    act.user_verified_race = user_verified_race
    act.performance_percentage = None
    act.birthdate = date(1968, 1, 1)
    act.sex = "M"
    type(act).pace_per_mile = PropertyMock(
        return_value=26.8224 / (distance_m / duration_s) if duration_s and distance_m else None
    )
    return act


def _mock_athlete():
    a = MagicMock()
    a.id = uuid.uuid4()
    a.birthdate = date(1968, 1, 1)
    a.sex = "M"
    a.max_hr = None
    a.resting_hr = 55
    a.threshold_pace = None
    return a


def _mock_event(event_date, distance_category, time_seconds, event_id=None):
    ev = MagicMock()
    ev.id = event_id or uuid.uuid4()
    ev.event_date = event_date
    ev.distance_category = distance_category
    ev.time_seconds = time_seconds
    ev.user_classified_role = None
    ev.race_role = None
    ev.is_personal_best = False
    ev.user_confirmed = True
    return ev


class TestPopulatePerformanceEvents:
    @patch("services.performance_event_pipeline.compute_block_signature", return_value={})
    @patch("services.performance_event_pipeline.TrainingLoadCalculator")
    @patch("services.performance_event_pipeline.calculate_rpi_from_race_time", return_value=45.0)
    @patch("services.performance_event_pipeline.calculate_age_graded_performance", return_value=65.0)
    @patch("services.performance_event_pipeline.calculate_age_at_date", return_value=57)
    def test_creates_event_from_strava_tag(self, mock_age, mock_perf, mock_rpi, mock_load_cls, mock_block):
        athlete = _mock_athlete()
        act = _mock_activity(
            distance_m=10000, duration_s=2800,
            strava_workout_type_raw=3, start_date=date(2025, 3, 15),
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = athlete
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [act]
        db.query.return_value.filter.return_value.all.side_effect = [
            [],  # existing events query
            [],  # _mark_personal_bests
            [],  # _classify_race_roles
        ]

        mock_load_inst = MagicMock()
        mock_load_inst.compute_training_state_history.return_value = {}
        mock_load_cls.return_value = mock_load_inst

        result = populate_performance_events(athlete.id, db)
        assert result["events_created"] == 1
        assert db.add.called

    @patch("services.performance_event_pipeline.compute_block_signature", return_value={})
    @patch("services.performance_event_pipeline.TrainingLoadCalculator")
    @patch("services.performance_event_pipeline.calculate_rpi_from_race_time", return_value=40.0)
    def test_skips_non_race_distance(self, mock_rpi, mock_load_cls, mock_block):
        athlete = _mock_athlete()
        act = _mock_activity(distance_m=7000, duration_s=2400)

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = athlete
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [act]
        db.query.return_value.filter.return_value.all.side_effect = [[], [], []]

        mock_load_inst = MagicMock()
        mock_load_cls.return_value = mock_load_inst

        result = populate_performance_events(athlete.id, db)
        assert result["events_created"] == 0

    @patch("services.performance_event_pipeline.compute_block_signature", return_value={})
    @patch("services.performance_event_pipeline.TrainingLoadCalculator")
    @patch("services.performance_event_pipeline.calculate_rpi_from_race_time", return_value=50.0)
    @patch("services.performance_event_pipeline.calculate_age_graded_performance", return_value=70.0)
    @patch("services.performance_event_pipeline.calculate_age_at_date", return_value=57)
    def test_creates_event_from_user_verified(self, mock_age, mock_perf, mock_rpi, mock_load_cls, mock_block):
        athlete = _mock_athlete()
        act = _mock_activity(
            distance_m=21097, duration_s=5600,
            user_verified_race=True, start_date=date(2025, 11, 30),
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = athlete
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [act]
        db.query.return_value.filter.return_value.all.side_effect = [[], [], []]

        mock_load_inst = MagicMock()
        mock_load_inst.compute_training_state_history.return_value = {}
        mock_load_cls.return_value = mock_load_inst

        result = populate_performance_events(athlete.id, db)
        assert result["events_created"] == 1


class TestClassifyRaceRole:
    def test_solo_race_is_a_race(self):
        ev = _mock_event(date(2025, 6, 15), "10k", 2800)
        assert classify_race_role(ev, [ev]) == "a_race"

    def test_tune_up_before_longer_race(self):
        ev1 = _mock_event(date(2025, 6, 1), "5k", 1200)
        ev2 = _mock_event(date(2025, 6, 29), "half_marathon", 5600)
        assert classify_race_role(ev1, [ev1, ev2]) == "tune_up"

    def test_a_race_when_far_apart(self):
        ev1 = _mock_event(date(2025, 3, 1), "10k", 2800)
        ev2 = _mock_event(date(2025, 9, 1), "half_marathon", 5600)
        assert classify_race_role(ev1, [ev1, ev2]) == "a_race"


class TestComputeBlockSignature:
    def test_empty_block(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        sig = compute_block_signature(
            activity_id=uuid.uuid4(),
            event_date=date(2025, 6, 15),
            distance_category="10k",
            athlete_id=uuid.uuid4(),
            db=db,
        )
        assert sig["total_activities"] == 0
        assert sig["lookback_weeks"] == 12

    @patch("services.performance_event_pipeline.classify_effort_bulk")
    def test_with_activities(self, mock_classify):
        aid = uuid.uuid4()
        base = date(2025, 6, 15)
        acts = [
            _mock_activity(distance_m=10000, duration_s=3600, start_date=base - timedelta(weeks=w))
            for w in range(1, 9)
        ]

        effort_map = {a.id: "easy" if i % 3 == 0 else "moderate" for i, a in enumerate(acts)}
        mock_classify.return_value = effort_map

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = acts

        sig = compute_block_signature(
            activity_id=uuid.uuid4(),
            event_date=base,
            distance_category="10k",
            athlete_id=aid,
            db=db,
        )
        assert sig["total_activities"] == 8
        assert sig["lookback_weeks"] == 12
        assert len(sig["weekly_volumes_km"]) == 12
        assert sig["long_run_max_km"] > 0


class TestLookbackWeeks:
    def test_mile_is_8(self):
        assert LOOKBACK_WEEKS["mile"] == 8

    def test_marathon_is_18(self):
        assert LOOKBACK_WEEKS["marathon"] == 18

    def test_50k_is_20(self):
        assert LOOKBACK_WEEKS["50k"] == 20
