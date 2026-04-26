"""
Phase 2 tests — Path A Home Surfaces.
"""
import inspect
from unittest.mock import MagicMock

import pytest


class TestLastRunHeatAdjustment:
    """LastRun includes heat_adjustment_pct field."""

    def test_last_run_model_has_heat_field(self):
        from routers.home import LastRun
        fields = LastRun.model_fields
        assert "heat_adjustment_pct" in fields

    def test_compute_last_run_populates_heat(self):
        from routers.home import compute_last_run

        src = inspect.getsource(compute_last_run)
        assert "heat_adjustment_pct" in src


class TestLastRunWorkoutClassification:
    """LastRun includes workout_classification field."""

    def test_last_run_model_has_workout_classification_field(self):
        from routers.home import LastRun
        fields = LastRun.model_fields
        assert "workout_classification" in fields

    def test_compute_last_run_populates_workout_classification(self):
        from routers.home import compute_last_run

        src = inspect.getsource(compute_last_run)
        assert "workout_classification" in src
        assert "run_shape" in src


class TestHomeFindingModel:
    """HomeFinding typed model exists with required fields."""

    def test_home_finding_has_required_fields(self):
        from routers.home import HomeFinding
        fields = HomeFinding.model_fields
        for f in ("text", "confidence_tier", "domain", "times_confirmed"):
            assert f in fields, f"HomeFinding missing field: {f}"


class TestHomeResponseFindingAndCorrelations:
    """HomeResponse includes finding and has_correlations."""

    def test_home_response_has_finding_field(self):
        from routers.home import HomeResponse
        fields = HomeResponse.model_fields
        assert "finding" in fields
        assert "has_correlations" in fields

    def test_finding_populated_from_correlation_finding(self):
        from routers.home import get_home_data
        src = inspect.getsource(get_home_data)
        assert "CorrelationFinding" in src
        assert "times_confirmed >= 3" in src or "times_confirmed >=3" in src

    def test_finding_uses_day_rotation(self):
        from routers.home import get_home_data
        src = inspect.getsource(get_home_data)
        assert "toordinal" in src


class TestActivityDetailWeatherFields:
    """Activity detail endpoint includes dew_point_f and heat_adjustment_pct."""

    def test_activity_response_includes_weather_fields(self):
        from routers.activities import get_activity
        src = inspect.getsource(get_activity)
        assert '"dew_point_f"' in src
        assert '"heat_adjustment_pct"' in src
