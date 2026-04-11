"""Tests for V2 plan saver and router adapter mapping."""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from services.plan_engine_v2.models import (
    V2DayPlan,
    V2PlanPreview,
    V2WeekPlan,
    WorkoutSegment,
    FuelingPlan,
)
from services.plan_engine_v2.plan_saver import (
    _estimate_day_distance_km,
    _estimate_day_duration_min,
    _build_segments_json,
    _build_coach_notes,
)
from services.plan_engine_v2.router_adapter import (
    _map_tune_up_races,
    _compute_plan_start,
    _EVENT_MAP,
)


class TestEstimateDayDistanceKm:
    def test_from_target_distance(self):
        day = V2DayPlan(
            day_of_week=0, workout_type="easy", title="Easy",
            description="Easy run", phase="general",
            target_distance_km=10.0,
        )
        assert _estimate_day_distance_km(day) == 10.0

    def test_from_segments_with_distance(self):
        day = V2DayPlan(
            day_of_week=0, workout_type="threshold_cruise",
            title="Threshold", description="", phase="general",
            segments=[
                WorkoutSegment(type="warmup", pace_pct_mp=80, pace_sec_per_km=350,
                               description="warmup", distance_km=2.0),
                WorkoutSegment(type="work", pace_pct_mp=100, pace_sec_per_km=280,
                               description="work", distance_km=5.0),
                WorkoutSegment(type="cooldown", pace_pct_mp=80, pace_sec_per_km=350,
                               description="cooldown", distance_km=2.0),
            ],
        )
        assert _estimate_day_distance_km(day) == 9.0

    def test_from_segments_with_duration(self):
        day = V2DayPlan(
            day_of_week=0, workout_type="vo2max",
            title="VO2max", description="", phase="general",
            segments=[
                WorkoutSegment(type="warmup", pace_pct_mp=80, pace_sec_per_km=350,
                               description="warmup", distance_km=2.0),
                WorkoutSegment(type="work", pace_pct_mp=115, pace_sec_per_km=240,
                               description="work", duration_min=3.0),
                WorkoutSegment(type="cooldown", pace_pct_mp=80, pace_sec_per_km=350,
                               description="cooldown", distance_km=2.0),
            ],
        )
        result = _estimate_day_distance_km(day)
        assert result is not None
        assert result > 4.0

    def test_from_distance_range(self):
        day = V2DayPlan(
            day_of_week=0, workout_type="easy", title="Easy",
            description="", phase="general",
            distance_range_km=(8.0, 10.0),
        )
        assert _estimate_day_distance_km(day) == 9.0

    def test_rest_day_returns_none(self):
        day = V2DayPlan(
            day_of_week=0, workout_type="rest", title="Rest",
            description="", phase="general",
        )
        assert _estimate_day_distance_km(day) is None


class TestEstimateDayDurationMin:
    def test_from_distance_and_pace(self):
        day = V2DayPlan(
            day_of_week=0, workout_type="easy", title="Easy",
            description="", phase="general",
            target_distance_km=10.0,
        )
        result = _estimate_day_duration_min(day, easy_pace_sec_km=350.0)
        assert result is not None
        assert 55 <= result <= 60

    def test_from_segments(self):
        day = V2DayPlan(
            day_of_week=0, workout_type="workout", title="W",
            description="", phase="general",
            segments=[
                WorkoutSegment(type="warmup", pace_pct_mp=80, pace_sec_per_km=350,
                               description="warmup", duration_min=10.0),
                WorkoutSegment(type="work", pace_pct_mp=100, pace_sec_per_km=280,
                               description="work", duration_min=20.0),
            ],
        )
        result = _estimate_day_duration_min(day, easy_pace_sec_km=350.0)
        assert result is not None
        assert result >= 25


class TestBuildCoachNotes:
    def test_with_segments_and_fueling(self):
        day = V2DayPlan(
            day_of_week=0, workout_type="long_easy", title="Long",
            description="", phase="general",
            segments=[
                WorkoutSegment(type="easy", pace_pct_mp=80, pace_sec_per_km=350,
                               description="Easy pace", distance_km=20.0),
            ],
            fueling=FuelingPlan(during_run_carbs_g_per_hr=60, notes="Gel every 45min"),
        )
        notes = _build_coach_notes(day)
        assert "Easy pace" in notes
        assert "60g carbs/hr" in notes
        assert "Gel every 45min" in notes

    def test_no_segments_no_fueling(self):
        day = V2DayPlan(
            day_of_week=0, workout_type="easy", title="Easy",
            description="", phase="general",
            distance_range_km=(8.0, 10.0),
        )
        assert _build_coach_notes(day) is None


class TestBuildSegmentsJson:
    def test_returns_list_of_dicts(self):
        day = V2DayPlan(
            day_of_week=0, workout_type="threshold", title="T",
            description="", phase="general",
            segments=[
                WorkoutSegment(type="warmup", pace_pct_mp=80, pace_sec_per_km=350,
                               description="warmup", distance_km=2.0),
            ],
        )
        result = _build_segments_json(day)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "warmup"

    def test_none_when_no_segments(self):
        day = V2DayPlan(
            day_of_week=0, workout_type="easy", title="E",
            description="", phase="general",
        )
        assert _build_segments_json(day) is None


class TestMapTuneUpRaces:
    def test_maps_pydantic_models(self):
        class MockTuneUp:
            race_date = date(2026, 6, 15)
            distance = "half_marathon"
            name = "Brooklyn Half"
            purpose = "threshold"

        result = _map_tune_up_races([MockTuneUp()])
        assert len(result) == 1
        assert result[0].distance == "half_marathon"
        assert result[0].name == "Brooklyn Half"

    def test_maps_dicts(self):
        raw = [{"date": date(2026, 6, 15), "distance": "10k", "name": "Local 10K", "purpose": "sharpening"}]
        result = _map_tune_up_races(raw)
        assert len(result) == 1
        assert result[0].distance == "10K"

    def test_returns_none_for_empty(self):
        assert _map_tune_up_races(None) is None
        assert _map_tune_up_races([]) is None


class TestComputePlanStart:
    def test_aligns_to_monday(self):
        race = date(2026, 7, 25)  # Saturday
        start = _compute_plan_start(race, 16)
        assert start.weekday() == 0  # Monday

    def test_correct_weeks_before_race(self):
        race = date(2026, 7, 25)
        start = _compute_plan_start(race, 16)
        weeks_diff = (race - start).days / 7
        assert 15 <= weeks_diff <= 17


class TestEventMap:
    def test_all_distances_mapped(self):
        for dist in ["5k", "10k", "half_marathon", "half", "marathon"]:
            assert dist in _EVENT_MAP
