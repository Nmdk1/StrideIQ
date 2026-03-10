"""Tests for heat_adjustment.py — cross-validated against HeatAdjustedPace.tsx."""
import math
import pytest
from services.heat_adjustment import (
    calculate_dew_point_f,
    calculate_heat_adjustment_pct,
    heat_adjusted_pace,
    compute_activity_heat_fields,
)


class TestDewPoint:
    def test_moderate_conditions(self):
        dp = calculate_dew_point_f(temp_f=85, humidity_pct=60)
        dp_c = (dp - 32) * 5 / 9
        assert 17 < dp_c < 22, f"85°F/60% → dew point {dp_c:.1f}°C, expected ~19°C"

    def test_hot_humid(self):
        dp = calculate_dew_point_f(temp_f=95, humidity_pct=80)
        assert dp > 85, f"95°F/80% → dew point {dp:.1f}°F, expected > 85°F"

    def test_cold_dry(self):
        dp = calculate_dew_point_f(temp_f=40, humidity_pct=30)
        assert dp < 20, f"40°F/30% → dew point {dp:.1f}°F, expected < 20°F"

    def test_100_percent_humidity(self):
        dp = calculate_dew_point_f(temp_f=70, humidity_pct=100)
        assert abs(dp - 70) < 1.0, "At 100% humidity, dew point ≈ temperature"

    def test_very_low_humidity_clamped(self):
        dp = calculate_dew_point_f(temp_f=70, humidity_pct=0)
        assert isinstance(dp, float)

    def test_above_100_humidity_clamped(self):
        dp = calculate_dew_point_f(temp_f=70, humidity_pct=105)
        dp_100 = calculate_dew_point_f(temp_f=70, humidity_pct=100)
        assert abs(dp - dp_100) < 0.1


class TestHeatAdjustmentPct:
    def test_cool_conditions_no_adjustment(self):
        assert calculate_heat_adjustment_pct(50, 40) == 0.0
        assert calculate_heat_adjustment_pct(55, 45) == 0.0

    def test_combined_119_no_adjustment(self):
        assert calculate_heat_adjustment_pct(65, 54) == 0.0

    def test_combined_120_mild(self):
        adj = calculate_heat_adjustment_pct(65, 55)
        assert 0.004 < adj < 0.006, f"Combined 120 → {adj}, expected ~0.005"

    def test_combined_130_moderate(self):
        adj = calculate_heat_adjustment_pct(75, 55)
        assert 0.014 < adj < 0.016, f"Combined 130 → {adj}, expected ~0.015"

    def test_combined_140_warm(self):
        adj = calculate_heat_adjustment_pct(80, 60)
        assert 0.029 < adj < 0.031, f"Combined 140 → {adj}, expected ~0.03"

    def test_combined_150_hot(self):
        adj = calculate_heat_adjustment_pct(85, 65)
        assert 0.044 < adj < 0.046, f"Combined 150 → {adj}, expected ~0.045"

    def test_combined_160_very_hot(self):
        adj = calculate_heat_adjustment_pct(90, 70)
        assert 0.064 < adj < 0.066, f"Combined 160 → {adj}, expected ~0.065"

    def test_combined_170_extreme(self):
        adj = calculate_heat_adjustment_pct(95, 75)
        assert 0.089 < adj < 0.091, f"Combined 170 → {adj}, expected ~0.09"

    def test_combined_180_beyond_extreme(self):
        adj = calculate_heat_adjustment_pct(100, 80)
        assert 0.099 < adj < 0.101, f"Combined 180 → {adj}, expected ~0.10"

    def test_interpolation_within_band(self):
        adj_125 = calculate_heat_adjustment_pct(70, 55)
        adj_120 = calculate_heat_adjustment_pct(65, 55)
        adj_130 = calculate_heat_adjustment_pct(75, 55)
        assert adj_120 < adj_125 < adj_130

    def test_founder_august_17(self):
        """93°F, 52% humidity — founder's hottest August day."""
        dp = calculate_dew_point_f(93, 52)
        adj = calculate_heat_adjustment_pct(93, dp)
        combined = 93 + dp
        assert combined > 150, f"Combined {combined:.0f}, expected > 150"
        assert adj > 0.04, f"Adjustment {adj:.3f}, expected > 4%"

    def test_founder_august_14(self):
        """75°F, 92% humidity — humidity-dominant day."""
        dp = calculate_dew_point_f(75, 92)
        adj = calculate_heat_adjustment_pct(75, dp)
        combined = 75 + dp
        assert combined > 140, f"Combined {combined:.0f}, expected > 140"
        assert adj > 0.02, f"Adjustment {adj:.3f}, expected > 2%"


class TestHeatAdjustedPace:
    def test_cool_no_change(self):
        adjusted = heat_adjusted_pace(480, temp_f=55, humidity_pct=50)
        assert adjusted == 480

    def test_hot_faster_adjusted(self):
        raw_pace = 480  # 8:00/mi
        adjusted = heat_adjusted_pace(raw_pace, temp_f=90, humidity_pct=70)
        assert adjusted < raw_pace, "Heat-adjusted should be faster than raw"
        assert adjusted > 440, "Adjustment shouldn't be more than ~10%"

    def test_explicit_dew_point(self):
        adj_auto = heat_adjusted_pace(480, temp_f=85, humidity_pct=60)
        dp = calculate_dew_point_f(85, 60)
        adj_explicit = heat_adjusted_pace(480, temp_f=85, humidity_pct=60, dew_point_f=dp)
        assert abs(adj_auto - adj_explicit) < 0.01

    def test_returns_float(self):
        result = heat_adjusted_pace(480, temp_f=85, humidity_pct=60)
        assert isinstance(result, float)


class TestComputeActivityHeatFields:
    def test_both_present(self):
        result = compute_activity_heat_fields(85, 60)
        assert result['dew_point_f'] is not None
        assert result['heat_adjustment_pct'] is not None
        assert result['heat_adjustment_pct'] > 0

    def test_temp_none(self):
        result = compute_activity_heat_fields(None, 60)
        assert result['dew_point_f'] is None
        assert result['heat_adjustment_pct'] is None

    def test_humidity_none(self):
        result = compute_activity_heat_fields(85, None)
        assert result['dew_point_f'] is None
        assert result['heat_adjustment_pct'] is None

    def test_both_none(self):
        result = compute_activity_heat_fields(None, None)
        assert result['dew_point_f'] is None
        assert result['heat_adjustment_pct'] is None

    def test_cool_zero_adjustment(self):
        result = compute_activity_heat_fields(50, 40)
        assert result['heat_adjustment_pct'] == 0.0
