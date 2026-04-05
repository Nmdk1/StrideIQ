"""Tests for weather enrichment pipeline (enrich_activity_weather + fetch_weather_for_date)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.weather_backfill import (
    enrich_activity_weather,
    extract_weather_at_hour,
    fetch_weather_for_date,
    _try_api,
    HISTORICAL_FORECAST_URL,
    ARCHIVE_URL,
)


class TestTryApi:
    """Unit tests for _try_api."""

    def test_returns_data_on_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "hourly": {"temperature_2m": [20.0, 21.0]}
        }
        with patch("services.weather_backfill.httpx.get", return_value=mock_resp):
            result = _try_api("https://example.com", 34.0, -86.0, datetime(2026, 4, 1).date())
        assert result is not None
        assert result["hourly"]["temperature_2m"] == [20.0, 21.0]

    def test_returns_none_on_empty_temps(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"hourly": {"temperature_2m": []}}
        with patch("services.weather_backfill.httpx.get", return_value=mock_resp):
            result = _try_api("https://example.com", 34.0, -86.0, datetime(2026, 4, 1).date())
        assert result is None

    def test_returns_none_on_http_error(self):
        with patch("services.weather_backfill.httpx.get", side_effect=Exception("timeout")):
            result = _try_api("https://example.com", 34.0, -86.0, datetime(2026, 4, 1).date())
        assert result is None


class TestFetchWeatherForDate:
    """Tests for fetch_weather_for_date with dual-API fallback."""

    def test_uses_historical_forecast_first(self):
        forecast_data = {"hourly": {"temperature_2m": [25.0]}}
        with patch("services.weather_backfill._try_api") as mock_try:
            mock_try.return_value = forecast_data
            result = fetch_weather_for_date(34.0, -86.0, datetime(2026, 4, 1).date())
        assert result == forecast_data
        mock_try.assert_called_once_with(HISTORICAL_FORECAST_URL, 34.0, -86.0, datetime(2026, 4, 1).date())

    def test_falls_back_to_archive(self):
        archive_data = {"hourly": {"temperature_2m": [22.0]}}
        with patch("services.weather_backfill._try_api") as mock_try:
            mock_try.side_effect = [None, archive_data]
            result = fetch_weather_for_date(34.0, -86.0, datetime(2026, 4, 1).date())
        assert result == archive_data
        assert mock_try.call_count == 2
        mock_try.assert_any_call(ARCHIVE_URL, 34.0, -86.0, datetime(2026, 4, 1).date())

    def test_returns_none_when_both_fail(self):
        with patch("services.weather_backfill._try_api", return_value=None):
            result = fetch_weather_for_date(34.0, -86.0, datetime(2026, 4, 1).date())
        assert result is None


class TestExtractWeatherAtHour:
    """Tests for extract_weather_at_hour."""

    def _sample_data(self):
        return {
            "hourly": {
                "temperature_2m": [15.0, 18.0, 20.5],
                "relative_humidity_2m": [80, 70, 65],
                "dew_point_2m": [11.0, 12.5, 13.5],
                "wind_speed_10m": [10.0, 15.0, 8.0],
                "wind_direction_10m": [180, 200, 170],
                "weather_code": [0, 3, 61],
            }
        }

    def test_extracts_correct_hour(self):
        result = extract_weather_at_hour(self._sample_data(), 1)
        assert result is not None
        assert result["temperature_f"] == pytest.approx(64.4, abs=0.1)
        assert result["humidity_pct"] == 70
        assert result["weather_condition"] == "overcast"

    def test_hour_zero(self):
        result = extract_weather_at_hour(self._sample_data(), 0)
        assert result is not None
        assert result["temperature_f"] == pytest.approx(59.0, abs=0.1)
        assert result["weather_condition"] == "clear"

    def test_out_of_range_hour(self):
        result = extract_weather_at_hour(self._sample_data(), 25)
        assert result is None

    def test_none_temperature(self):
        data = {"hourly": {"temperature_2m": [None]}}
        result = extract_weather_at_hour(data, 0)
        assert result is None


class TestEnrichActivityWeather:
    """Tests for enrich_activity_weather — the live pipeline function."""

    def _make_activity(self, sport="run", lat=34.73, lng=-86.58, start=None):
        act = MagicMock()
        act.id = "test-activity-id"
        act.sport = sport
        act.start_lat = lat
        act.start_lng = lng
        act.start_time = start or datetime(2026, 4, 1, 14, 30, tzinfo=timezone.utc)
        act.temperature_f = None
        act.humidity_pct = None
        act.dew_point_f = None
        act.heat_adjustment_pct = None
        act.weather_condition = None
        return act

    def test_enriches_outdoor_activity(self):
        act = self._make_activity()
        weather_data = {
            "hourly": {
                "temperature_2m": [None] * 14 + [20.5],
                "relative_humidity_2m": [None] * 14 + [65],
                "dew_point_2m": [None] * 14 + [13.5],
                "wind_speed_10m": [None] * 14 + [8.0],
                "wind_direction_10m": [None] * 14 + [170],
                "weather_code": [None] * 14 + [0],
            }
        }
        with patch("services.weather_backfill.fetch_weather_for_date", return_value=weather_data):
            result = enrich_activity_weather(act, MagicMock())
        assert result is True
        assert act.temperature_f == pytest.approx(68.9, abs=0.1)
        assert act.humidity_pct == 65
        assert act.weather_condition == "clear"
        assert act.dew_point_f is not None

    def test_skips_indoor_sport(self):
        act = self._make_activity(sport="strength")
        result = enrich_activity_weather(act, MagicMock())
        assert result is False

    def test_skips_no_gps(self):
        act = self._make_activity(lat=None, lng=None)
        result = enrich_activity_weather(act, MagicMock())
        assert result is False

    def test_skips_no_start_time(self):
        act = self._make_activity()
        act.start_time = None
        result = enrich_activity_weather(act, MagicMock())
        assert result is False

    def test_handles_api_failure_gracefully(self):
        act = self._make_activity()
        with patch("services.weather_backfill.fetch_weather_for_date", return_value=None):
            result = enrich_activity_weather(act, MagicMock())
        assert result is False
        assert act.temperature_f is None

    def test_handles_exception_gracefully(self):
        act = self._make_activity()
        with patch("services.weather_backfill.fetch_weather_for_date", side_effect=RuntimeError("boom")):
            result = enrich_activity_weather(act, MagicMock())
        assert result is False

    def test_flexibility_skipped(self):
        act = self._make_activity(sport="flexibility")
        result = enrich_activity_weather(act, MagicMock())
        assert result is False

    def test_cycling_enriched(self):
        act = self._make_activity(sport="cycling")
        weather_data = {
            "hourly": {
                "temperature_2m": [None] * 14 + [25.0],
                "relative_humidity_2m": [None] * 14 + [50],
                "dew_point_2m": [None] * 14 + [14.0],
                "wind_speed_10m": [None] * 14 + [12.0],
                "wind_direction_10m": [None] * 14 + [90],
                "weather_code": [None] * 14 + [3],
            }
        }
        with patch("services.weather_backfill.fetch_weather_for_date", return_value=weather_data):
            result = enrich_activity_weather(act, MagicMock())
        assert result is True
        assert act.temperature_f == pytest.approx(77.0, abs=0.1)
