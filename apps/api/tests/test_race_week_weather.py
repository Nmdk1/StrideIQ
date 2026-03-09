"""Tests for P0 Race-Week Weather feature.

Covers: race key mismatch fix, admin forecast endpoint, personal heat adjustment,
weather context builder, race-week conditional injection, graceful fallbacks.
"""
import json
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from pydantic import ValidationError


class TestRaceDataDictKeysMatchPrompt(unittest.TestCase):
    """Test 1: race_data_dict keys match what race_summary reads."""

    def test_race_data_dict_keys_match_prompt(self):
        from routers.home import get_home_data, generate_coach_home_briefing
        import inspect

        builder_source = inspect.getsource(get_home_data)
        assert "\"name\": race_countdown.race_name" in builder_source
        assert "\"date\": race_countdown.race_date" in builder_source
        assert "\"distance\": _format_race_distance" in builder_source
        assert "\"days_remaining\":" in builder_source

        consumer_source = inspect.getsource(generate_coach_home_briefing)
        assert "race_data.get('name'" in consumer_source
        assert "race_data.get('date'" in consumer_source
        assert "race_data.get('distance'" in consumer_source


class TestFormatRaceDistance(unittest.TestCase):
    """Tests 2-4: _format_race_distance output for standard and custom distances."""

    def test_format_race_distance_marathon(self):
        from routers.home import _format_race_distance

        plan = MagicMock()
        plan.goal_race_distance_m = 42195
        assert _format_race_distance(plan) == "marathon"

    def test_format_race_distance_half(self):
        from routers.home import _format_race_distance

        plan = MagicMock()
        plan.goal_race_distance_m = 21097
        assert _format_race_distance(plan) == "half marathon"

    def test_format_race_distance_custom(self):
        from routers.home import _format_race_distance

        plan = MagicMock()
        plan.goal_race_distance_m = 80467  # ~50 miles
        result = _format_race_distance(plan)
        assert "50.0" in result
        assert "miles" in result

    def test_format_race_distance_none(self):
        from routers.home import _format_race_distance

        plan = MagicMock(spec=[])
        result = _format_race_distance(plan)
        assert result == "unknown distance"

    def test_format_race_distance_5k(self):
        from routers.home import _format_race_distance

        plan = MagicMock()
        plan.goal_race_distance_m = 5000
        assert _format_race_distance(plan) == "5K"

    def test_format_race_distance_10k(self):
        from routers.home import _format_race_distance

        plan = MagicMock()
        plan.goal_race_distance_m = 10000
        assert _format_race_distance(plan) == "10K"


class TestGetRaceForecast(unittest.TestCase):
    """Tests 5-6: forecast retrieval from Redis."""

    @patch("core.cache.get_redis_client")
    def test_get_race_forecast_returns_none_when_empty(self, mock_redis):
        from routers.home import _get_race_forecast

        client = MagicMock()
        client.get.return_value = None
        mock_redis.return_value = client

        result = _get_race_forecast("some-athlete-id")
        assert result is None

    @patch("core.cache.get_redis_client")
    def test_get_race_forecast_returns_none_on_malformed_json(self, mock_redis):
        from routers.home import _get_race_forecast

        client = MagicMock()
        client.get.return_value = "not-valid-json{{"
        mock_redis.return_value = client

        result = _get_race_forecast("some-athlete-id")
        assert result is None

    @patch("core.cache.get_redis_client")
    def test_get_race_forecast_returns_none_when_redis_unavailable(self, mock_redis):
        from routers.home import _get_race_forecast

        mock_redis.return_value = None
        result = _get_race_forecast("some-athlete-id")
        assert result is None


class TestPersonalMultiplier(unittest.TestCase):
    """Tests 7-8: personal heat multiplier from AthleteFinding."""

    def test_personal_multiplier_from_resilience_ratio_bounded(self):
        from routers.home import _get_personal_heat_multiplier

        db = MagicMock()
        finding = MagicMock()
        finding.receipts = {"resilience_ratio": 1.5, "classification": "resilient"}
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = finding

        result = _get_personal_heat_multiplier(str(uuid4()), db)
        # 1.0 / 1.5 = 0.667, bounded to 0.70
        assert result == 0.70

    def test_personal_multiplier_from_classification_defaults(self):
        from routers.home import _get_personal_heat_multiplier

        db = MagicMock()
        finding = MagicMock()
        finding.receipts = {"classification": "sensitive"}
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = finding

        result = _get_personal_heat_multiplier(str(uuid4()), db)
        assert result == 1.15

    def test_personal_multiplier_no_finding(self):
        from routers.home import _get_personal_heat_multiplier

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = _get_personal_heat_multiplier(str(uuid4()), db)
        assert result == 1.0

    def test_personal_multiplier_upper_bound(self):
        from routers.home import _get_personal_heat_multiplier

        db = MagicMock()
        finding = MagicMock()
        finding.receipts = {"resilience_ratio": 0.3}
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = finding

        result = _get_personal_heat_multiplier(str(uuid4()), db)
        # 1.0 / 0.5 (clamped to 0.5) = 2.0, bounded to 1.30
        assert result == 1.30


class TestBuildRaceWeatherContext(unittest.TestCase):
    """Tests 9-10: weather context builder."""

    def test_build_race_weather_context_includes_forecast(self):
        from routers.home import _build_race_weather_context

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []

        forecast = {"temp_f": 82.0, "dew_point_f": 68.0, "humidity_pct": 65}
        race_data = {"name": "Boston Marathon", "days_remaining": 5}

        result = _build_race_weather_context(str(uuid4()), db, forecast, race_data)
        assert result is not None
        assert "RACE WEEK WEATHER" in result
        assert "82°F" in result
        assert "Boston Marathon" in result
        assert "5 days" in result
        assert "COACHING RULE" in result

    def test_build_race_weather_context_filters_to_real_runs_non_duplicates(self):
        from routers.home import _build_race_weather_context
        import inspect

        source = inspect.getsource(_build_race_weather_context)
        assert "is_duplicate == False" in source
        assert "sport.ilike" in source
        assert "distance_m >= 5000" in source

    def test_build_race_weather_context_returns_none_missing_data(self):
        from routers.home import _build_race_weather_context

        db = MagicMock()
        result = _build_race_weather_context(
            str(uuid4()), db, {"temp_f": 80}, {"name": "Race"}
        )
        assert result is None


class TestRaceWeatherInjectionTiming(unittest.TestCase):
    """Tests 11-12: weather context injection only within 7 days."""

    def test_race_weather_only_injected_within_7_days(self):
        import inspect
        from routers.home import generate_coach_home_briefing

        source = inspect.getsource(generate_coach_home_briefing)
        assert "days_remaining\", 99) <= 7" in source

    def test_race_weather_injected_at_7_days(self):
        import inspect
        from routers.home import generate_coach_home_briefing

        source = inspect.getsource(generate_coach_home_briefing)
        assert "<= 7" in source
        assert "_get_race_forecast" in source
        assert "_build_race_weather_context" in source


class TestAdminForecastValidation(unittest.TestCase):
    """Test 13: admin forecast endpoint validates bounds."""

    def test_admin_forecast_validation_bounds_reject_invalid_values(self):
        from routers.admin import RaceForecastRequest

        with self.assertRaises(ValidationError):
            RaceForecastRequest(
                athlete_id=uuid4(), temp_f=150, humidity_pct=50
            )

        with self.assertRaises(ValidationError):
            RaceForecastRequest(
                athlete_id=uuid4(), temp_f=80, humidity_pct=110
            )

        with self.assertRaises(ValidationError):
            RaceForecastRequest(
                athlete_id=uuid4(), temp_f=-30, humidity_pct=50
            )

        valid = RaceForecastRequest(
            athlete_id=uuid4(), temp_f=80, humidity_pct=50
        )
        assert valid.temp_f == 80
        assert valid.humidity_pct == 50

    def test_admin_forecast_description_max_length(self):
        from routers.admin import RaceForecastRequest

        with self.assertRaises(ValidationError):
            RaceForecastRequest(
                athlete_id=uuid4(), temp_f=80, humidity_pct=50,
                description="x" * 241,
            )


class TestIntegrationHomeEndpoint(unittest.TestCase):
    """Tests 14-15: integration-level checks for race data in briefing path."""

    def test_home_endpoint_race_assessment_has_real_race_fields_when_plan_exists(self):
        import inspect
        from routers.home import generate_coach_home_briefing

        source = inspect.getsource(generate_coach_home_briefing)
        assert "race_data.get('name'" in source
        assert "race_data.get('date'" in source
        assert "race_data.get('distance'" in source
        assert "race_data.get('days_remaining'" in source

        assert "race_data.get('race_name'" not in source

    def test_home_endpoint_graceful_when_forecast_absent_or_cache_unavailable(self):
        from routers.home import _get_race_forecast

        with patch("core.cache.get_redis_client", return_value=None):
            result = _get_race_forecast("any-id")
            assert result is None

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("connection refused")
        with patch("core.cache.get_redis_client", return_value=mock_client):
            result = _get_race_forecast("any-id")
            assert result is None
