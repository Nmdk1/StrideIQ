"""
D3 Adapter Layer Tests

Tests for services/garmin_adapter.py, garmin_004 migration, and the
D3.3 deduplication contract.

Coverage:
  - Source contract: Garmin field names appear only in garmin_adapter.py
  - Activity adapter: field translation, sport mapping, null handling
  - Daily summary adapter: all GarminDay daily fields
  - Sleep summary adapter: nested overallSleepScore, calendarDate rule
  - HRV adapter: lastNightAvg, lastNight5MinHigh
  - Stress detail adapter: negative value pass-through, JSONB samples
  - User metrics adapter: vo2Max extraction
  - garmin_004 schema: new Activity columns present and nullable
  - Deduplication contract: adapt_activity_summary output → dedup works
"""

import inspect
from datetime import datetime, timezone

import pytest

from services.garmin_adapter import (
    adapt_activity_summary,
    adapt_daily_summary,
    adapt_hrv_summary,
    adapt_stress_detail,
    adapt_user_metrics,
    adapt_sleep_summary,
)


# ===========================================================================
# Source contract
# ===========================================================================

class TestAdapterSourceContract:
    """
    In the adapter-to-model/dedup path, Garmin field names (camelCase API
    names) must appear ONLY in garmin_adapter.py. No other file in that path
    should translate raw Garmin field names.

    Scope: webhook/API ingestion path only. The separate DI takeout import
    path (services/provider_import/garmin_di_connect.py) is excluded from
    this contract — it handles a different ingestion surface and is compliant.

    Tests enforce the D0/D3.3 contract by inspecting source of neighbouring
    services in the ingestion path.
    """

    def test_dedup_service_contains_no_garmin_field_names(self):
        import services.activity_deduplication as dedup_mod

        source = inspect.getsource(dedup_mod)
        # These are the provider-specific names the adapter is responsible for
        banned = [
            "startTimeInSeconds",
            "distanceInMeters",
            "averageHeartRateInBeatsPerMinute",
            "summaryId",
            "activityId",
        ]
        for name in banned:
            assert name not in source, (
                f"activity_deduplication.py must not reference Garmin field "
                f"'{name}'. Move all provider translations to garmin_adapter.py."
            )

    def test_adapter_output_contains_only_internal_keys(self):
        """adapt_activity_summary returns only internal field names."""
        raw = {
            "summaryId": "abc123",
            "activityId": 99,
            "startTimeInSeconds": 1512234126,
            "durationInSeconds": 3600,
            "activityType": "RUNNING",
            "activityName": "Morning run",
            "averageHeartRateInBeatsPerMinute": 145,
            "maxHeartRateInBeatsPerMinute": 170,
            "averageSpeedInMetersPerSecond": 3.0,
            "distanceInMeters": 10000.0,
            "totalElevationGainInMeters": 80.0,
            "totalElevationLossInMeters": 75.0,
            "averageRunCadenceInStepsPerMinute": 170,
            "maxRunCadenceInStepsPerMinute": 185,
            "averagePaceInMinutesPerKilometer": 5.56,
            "maxPaceInMinutesPerKilometer": 4.2,
            "maxSpeedInMetersPerSecond": 4.5,
            "activeKilocalories": 650,
            "steps": 9000,
            "deviceName": "forerunner965",
            "startingLatitudeInDegree": 51.5,
            "startingLongitudeInDegree": -0.12,
            "manual": False,
        }
        adapted = adapt_activity_summary(raw)

        # No Garmin-named keys should appear in the output
        garmin_keys = [k for k in adapted if "InSeconds" in k or "InMeters" in k
                       or "InBeatsPerMinute" in k or "summaryId" in k]
        assert garmin_keys == [], f"Garmin field names leaked into output: {garmin_keys}"


# ===========================================================================
# Activity adapter
# ===========================================================================

class TestAdaptActivitySummary:

    def _sample_raw(self, **overrides):
        base = {
            "summaryId": "x153a9f3-5a9478d4-6",
            "activityId": 5001968355,
            "startTimeInSeconds": 1512234126,
            "startTimeOffsetInSeconds": -25200,
            "durationInSeconds": 1789,
            "activityType": "RUNNING",
            "activityName": "Easy run",
            "averageHeartRateInBeatsPerMinute": 144,
            "maxHeartRateInBeatsPerMinute": 159,
            "averageSpeedInMetersPerSecond": 2.781,
            "maxSpeedInMetersPerSecond": 4.152,
            "distanceInMeters": 1976.83,
            "totalElevationGainInMeters": 16.0,
            "totalElevationLossInMeters": 22.0,
            "averageRunCadenceInStepsPerMinute": 84,
            "maxRunCadenceInStepsPerMinute": 106,
            "averagePaceInMinutesPerKilometer": 15.521924,
            "maxPaceInMinutesPerKilometer": 10.396549,
            "activeKilocalories": 367,
            "steps": 5022,
            "deviceName": "forerunner935",
            "startingLatitudeInDegree": 51.053232522681355,
            "startingLongitudeInDegree": -114.06880217604339,
            "manual": False,
        }
        base.update(overrides)
        return base

    def test_identifiers(self):
        out = adapt_activity_summary(self._sample_raw())
        assert out["external_activity_id"] == "x153a9f3-5a9478d4-6"
        assert out["garmin_activity_id"] == 5001968355
        assert out["provider"] == "garmin"

    def test_start_time_is_utc_aware_datetime(self):
        out = adapt_activity_summary(self._sample_raw())
        assert isinstance(out["start_time"], datetime)
        assert out["start_time"].tzinfo == timezone.utc
        assert out["start_time"].year == 2017  # 1512234126 → Dec 2 2017

    def test_duration_mapped(self):
        out = adapt_activity_summary(self._sample_raw())
        assert out["duration_s"] == 1789

    def test_running_maps_to_run(self):
        for garmin_type in ("RUNNING", "TRAIL_RUNNING", "TREADMILL_RUNNING",
                            "INDOOR_RUNNING", "VIRTUAL_RUN"):
            out = adapt_activity_summary(self._sample_raw(activityType=garmin_type))
            assert out["sport"] == "run", f"Expected 'run' for {garmin_type}"

    def test_cycling_maps_to_cycling(self):
        for garmin_type in ("CYCLING", "ROAD_BIKING", "GRAVEL_CYCLING"):
            out = adapt_activity_summary(self._sample_raw(activityType=garmin_type))
            assert out["sport"] == "cycling", f"Expected 'cycling' for {garmin_type}"
            assert out["garmin_activity_type"] == garmin_type
            assert out["cadence_unit"] == "rpm"

    def test_cross_training_types(self):
        cases = {
            "INDOOR_CYCLING": ("cycling", "rpm"),
            "MOUNTAIN_BIKING": ("cycling", "rpm"),
            "ROAD_BIKING": ("cycling", "rpm"),
            "GRAVEL_CYCLING": ("cycling", "rpm"),
            "VIRTUAL_RIDE": ("cycling", "rpm"),
            "E_BIKE_FITNESS": ("cycling", "rpm"),
            "TRACK_CYCLING": ("cycling", "rpm"),
            "BIKE_COMMUTING": ("cycling", "rpm"),
            "ELLIPTICAL": ("cycling", "rpm"),
            "STAIR_CLIMBING": ("cycling", "rpm"),
            "WALKING": ("walking", "spm"),
            "CASUAL_WALKING": ("walking", "spm"),
            "SPEED_WALKING": ("walking", "spm"),
            "INDOOR_WALKING": ("walking", "spm"),
            "HIKING": ("hiking", "spm"),
            "SWIMMING": ("swimming", None),
            "LAP_SWIMMING": ("swimming", None),
            "OPEN_WATER_SWIMMING": ("swimming", None),
            "STRENGTH_TRAINING": ("strength", None),
            "WEIGHT_TRAINING": ("strength", None),
            "YOGA": ("flexibility", None),
            "PILATES": ("flexibility", None),
            "BREATHWORK": ("flexibility", None),
            "HIIT": ("cardio", None),
            "INDOOR_ROWING": ("rowing", "spm"),
            "CROSS_COUNTRY_SKIING": ("winter_sport", None),
            "STAND_UP_PADDLEBOARDING": ("water_sport", None),
            "MULTI_SPORT": ("multi_sport", None),
            "GOLF": ("other", None),
            "TRACK_RUNNING": ("run", "spm"),
            "ULTRA_RUN": ("run", "spm"),
        }
        for garmin_type, (expected_sport, expected_cadence) in cases.items():
            out = adapt_activity_summary(self._sample_raw(activityType=garmin_type))
            assert out["sport"] == expected_sport, f"{garmin_type} → {out['sport']}"
            assert out["cadence_unit"] == expected_cadence, f"{garmin_type} cadence"
            assert out["garmin_activity_type"] == garmin_type

    def test_unknown_type_maps_to_none(self):
        out = adapt_activity_summary(self._sample_raw(activityType="ZORBING"))
        assert out["sport"] is None
        assert out["garmin_activity_type"] == "ZORBING"
        assert out["cadence_unit"] is None

    def test_missing_type_maps_to_none(self):
        out = adapt_activity_summary(self._sample_raw(activityType=None))
        assert out["sport"] is None

    def test_manual_false_gives_garmin_source(self):
        out = adapt_activity_summary(self._sample_raw(manual=False))
        assert out["source"] == "garmin"

    def test_manual_true_gives_garmin_manual_source(self):
        out = adapt_activity_summary(self._sample_raw(manual=True))
        assert out["source"] == "garmin_manual"

    def test_cardiovascular_fields(self):
        out = adapt_activity_summary(self._sample_raw())
        assert out["avg_hr"] == 144
        assert out["max_hr"] == 159

    def test_movement_fields(self):
        out = adapt_activity_summary(self._sample_raw())
        assert out["distance_m"] == 1976.83
        assert out["average_speed"] == 2.781
        assert out["max_speed"] == 4.152
        assert out["total_elevation_gain"] == 16.0
        assert out["total_descent_m"] == 22.0

    def test_cadence_fields(self):
        out = adapt_activity_summary(self._sample_raw())
        assert out["avg_cadence"] == 84
        assert out["max_cadence"] == 106

    def test_pace_fields(self):
        out = adapt_activity_summary(self._sample_raw())
        assert out["avg_pace_min_per_km"] == pytest.approx(15.521924)
        assert out["max_pace_min_per_km"] == pytest.approx(10.396549)

    def test_energy_and_steps(self):
        out = adapt_activity_summary(self._sample_raw())
        assert out["active_kcal"] == 367
        assert out["steps"] == 5022

    def test_device_and_location(self):
        out = adapt_activity_summary(self._sample_raw())
        assert out["device_name"] == "forerunner935"
        assert out["start_lat"] == pytest.approx(51.053232522681355)
        assert out["start_lng"] == pytest.approx(-114.06880217604339)

    def test_all_optional_fields_none_on_empty_payload(self):
        out = adapt_activity_summary({})
        assert out["external_activity_id"] is None
        assert out["garmin_activity_id"] is None
        assert out["start_time"] is None
        assert out["sport"] is None
        assert out["avg_hr"] is None
        assert out["distance_m"] is None
        assert out["avg_pace_min_per_km"] is None
        assert out["steps"] is None
        assert out["start_lat"] is None
        assert out["provider"] == "garmin"  # always hardcoded

    def test_fit_only_fields_absent_from_output(self):
        """Running dynamics are FIT-file-only and must NOT appear as mapped keys."""
        out = adapt_activity_summary(self._sample_raw())
        fit_only_keys = [
            "avg_stride_length_m", "avg_ground_contact_ms",
            "avg_ground_contact_balance_pct", "avg_vertical_oscillation_cm",
            "avg_vertical_ratio_pct", "avg_gap_min_per_mile",
        ]
        for key in fit_only_keys:
            assert key not in out, (
                f"FIT-file-only field '{key}' must not be set by the Tier 1 adapter"
            )

    def test_undocumented_fields_absent_from_output(self):
        """TE, self-eval, body battery are undocumented and not mapped."""
        out = adapt_activity_summary(self._sample_raw())
        deferred = [
            "garmin_aerobic_te", "garmin_anaerobic_te", "garmin_te_label",
            "garmin_feel", "garmin_perceived_effort",
            "garmin_body_battery_impact", "moving_time_s",
        ]
        for key in deferred:
            assert key not in out, (
                f"Undocumented field '{key}' must not be set by Tier 1 adapter"
            )


# ===========================================================================
# Daily summary adapter
# ===========================================================================

class TestAdaptDailySummary:

    def _sample(self):
        return {
            "userId": "abc",
            "summaryId": "daily-001",
            "calendarDate": "2026-02-15",
            "restingHeartRateInBeatsPerMinute": 52,
            "minHeartRateInBeatsPerMinute": 49,
            "maxHeartRateInBeatsPerMinute": 130,
            "averageStressLevel": 35,
            "maxStressLevel": 70,
            "stressQualifier": "calm",
            "steps": 8400,
            "activeTimeInSeconds": 3600,
            "activeKilocalories": 450,
            "moderateIntensityDurationInSeconds": 1800,
            "vigorousIntensityDurationInSeconds": 900,
        }

    def test_calendar_date_preserved(self):
        out = adapt_daily_summary(self._sample())
        assert out["calendar_date"] == "2026-02-15"

    def test_summary_id_mapped(self):
        out = adapt_daily_summary(self._sample())
        assert out["garmin_daily_summary_id"] == "daily-001"

    def test_hr_fields(self):
        out = adapt_daily_summary(self._sample())
        assert out["resting_hr"] == 52
        assert out["min_hr"] == 49
        assert out["max_hr"] == 130

    def test_stress_fields(self):
        out = adapt_daily_summary(self._sample())
        assert out["avg_stress"] == 35
        assert out["max_stress"] == 70
        assert out["stress_qualifier"] == "calm"

    def test_activity_fields(self):
        out = adapt_daily_summary(self._sample())
        assert out["steps"] == 8400
        assert out["active_time_s"] == 3600
        assert out["active_kcal"] == 450
        assert out["moderate_intensity_s"] == 1800
        assert out["vigorous_intensity_s"] == 900

    def test_negative_stress_passes_through(self):
        """Negative stress values indicate data quality issues — store as-is."""
        raw = self._sample()
        raw["averageStressLevel"] = -1  # off-wrist
        out = adapt_daily_summary(raw)
        assert out["avg_stress"] == -1


# ===========================================================================
# Sleep summary adapter
# ===========================================================================

class TestAdaptSleepSummary:

    def _sample(self):
        return {
            "summaryId": "sleep-001",
            "calendarDate": "2026-02-15",  # wakeup day (Saturday morning)
            "durationInSeconds": 28800,
            "deepSleepDurationInSeconds": 7200,
            "lightSleepDurationInSeconds": 14400,
            "remSleepInSeconds": 5400,
            "awakeDurationInSeconds": 1800,
            "validation": "DEVICE",
            "overallSleepScore": {
                "value": 84,
                "qualifierKey": "GOOD"
            },
        }

    def test_calendar_date_is_wakeup_day(self):
        """calendarDate must be preserved as-is (it IS the wakeup morning)."""
        out = adapt_sleep_summary(self._sample())
        assert out["calendar_date"] == "2026-02-15"

    def test_sleep_stages_mapped(self):
        out = adapt_sleep_summary(self._sample())
        assert out["sleep_total_s"] == 28800
        assert out["sleep_deep_s"] == 7200
        assert out["sleep_light_s"] == 14400
        assert out["sleep_rem_s"] == 5400
        assert out["sleep_awake_s"] == 1800

    def test_nested_sleep_score_unpacked(self):
        out = adapt_sleep_summary(self._sample())
        assert out["sleep_score"] == 84
        assert out["sleep_score_qualifier"] == "GOOD"

    def test_missing_sleep_score_is_none(self):
        raw = self._sample()
        del raw["overallSleepScore"]
        out = adapt_sleep_summary(raw)
        assert out["sleep_score"] is None
        assert out["sleep_score_qualifier"] is None

    def test_null_sleep_score_is_none(self):
        raw = self._sample()
        raw["overallSleepScore"] = None
        out = adapt_sleep_summary(raw)
        assert out["sleep_score"] is None

    def test_validation_mapped(self):
        out = adapt_sleep_summary(self._sample())
        assert out["sleep_validation"] == "DEVICE"

    def test_docstring_documents_calendar_date_rule(self):
        """adapt_sleep_summary docstring must document the L1 calendarDate rule."""
        doc = adapt_sleep_summary.__doc__ or ""
        assert "wakeup" in doc.lower(), (
            "adapt_sleep_summary docstring must state that calendarDate is the wakeup day"
        )


# ===========================================================================
# HRV adapter
# ===========================================================================

class TestAdaptHrvSummary:

    def test_hrv_fields_mapped(self):
        raw = {
            "summaryId": "hrv-001",
            "calendarDate": "2026-02-15",
            "lastNightAvg": 44,
            "lastNight5MinHigh": 72,
            "startTimeInSeconds": 1653976004,
            "durationInSeconds": 3820,
        }
        out = adapt_hrv_summary(raw)
        assert out["calendar_date"] == "2026-02-15"
        assert out["garmin_hrv_summary_id"] == "hrv-001"
        assert out["hrv_overnight_avg"] == 44
        assert out["hrv_5min_high"] == 72

    def test_missing_hrv_values_give_none(self):
        out = adapt_hrv_summary({"calendarDate": "2026-02-15"})
        assert out["hrv_overnight_avg"] is None
        assert out["hrv_5min_high"] is None


# ===========================================================================
# Stress detail adapter
# ===========================================================================

class TestAdaptStressDetail:

    def _sample(self):
        return {
            "summaryId": "stress-001",
            "calendarDate": "2026-02-15",
            "averageStressLevel": 43,
            "maxStressLevel": 51,
            "timeOffsetStressLevelValues": "{0: 18, 180: 51, 360: 28}",
            "timeOffsetBodyBatteryValues": "{0: 55, 180: 56, 360: 59}",
        }

    def test_stress_fields_mapped(self):
        out = adapt_stress_detail(self._sample())
        assert out["calendar_date"] == "2026-02-15"
        assert out["avg_stress"] == 43
        assert out["max_stress"] == 51

    def test_samples_stored_as_is(self):
        """JSONB samples are stored as-is; no parsing or transformation."""
        out = adapt_stress_detail(self._sample())
        assert out["stress_samples"] == "{0: 18, 180: 51, 360: 28}"
        assert out["body_battery_samples"] == "{0: 55, 180: 56, 360: 59}"

    def test_negative_stress_passes_through(self):
        raw = self._sample()
        raw["averageStressLevel"] = -2  # large motion artifact
        out = adapt_stress_detail(raw)
        assert out["avg_stress"] == -2


# ===========================================================================
# User metrics adapter
# ===========================================================================

class TestAdaptUserMetrics:

    def test_vo2max_mapped(self):
        raw = {
            "summaryId": "metrics-001",
            "calendarDate": "2026-02-15",
            "vo2Max": 52,
            "vo2MaxCycling": 48,
            "fitnessAge": 28,
        }
        out = adapt_user_metrics(raw)
        assert out["calendar_date"] == "2026-02-15"
        assert out["vo2max"] == pytest.approx(52.0)

    def test_cycling_vo2max_not_mapped(self):
        """vo2MaxCycling is deferred — must not appear in Tier 1 output."""
        raw = {"calendarDate": "2026-02-15", "vo2Max": 50, "vo2MaxCycling": 45}
        out = adapt_user_metrics(raw)
        assert "vo2max_cycling" not in out

    def test_missing_vo2max_gives_none(self):
        out = adapt_user_metrics({"calendarDate": "2026-02-15"})
        assert out["vo2max"] is None


# ===========================================================================
# D3.3 — Deduplication contract
# ===========================================================================

class TestDeduplicationContract:
    """
    After adapt_activity_summary, the output must be directly usable by
    activity_deduplication.py without any field renaming.
    """

    def test_adapted_output_flows_into_dedup(self):
        """An adapted activity must match itself (same values) via dedup."""
        from services.activity_deduplication import match_activities

        raw = {
            "startTimeInSeconds": 1512234126,
            "distanceInMeters": 10000.0,
            "averageHeartRateInBeatsPerMinute": 145,
            "durationInSeconds": 3600,
            "activityType": "RUNNING",
        }
        adapted = adapt_activity_summary(raw)

        # Build a second internal dict with the same values (as if from a
        # previously stored Garmin activity)
        existing = {
            "start_time": adapted["start_time"],
            "distance_m": adapted["distance_m"],
            "avg_hr": adapted["avg_hr"],
        }
        # match_activities(a, b) → True when values are within thresholds
        result = match_activities(adapted, existing)
        assert result is True, (
            "Adapted Garmin activity should match identical existing record"
        )

    def test_raw_garmin_payload_does_not_match_in_dedup(self):
        """Raw Garmin payloads (not adapted) must not match in dedup.

        The dedup service looks for `start_time` and `distance_m`. A raw
        Garmin payload has `startTimeInSeconds` and `distanceInMeters` instead.
        Without adaptation the keys are absent → dedup returns False (no match).
        """
        from services.activity_deduplication import match_activities

        # Raw Garmin payload — provider-specific field names
        raw_garmin = {
            "startTimeInSeconds": 1512234126,
            "distanceInMeters": 10000.0,
            "averageHeartRateInBeatsPerMinute": 145,
        }
        # Existing properly-adapted internal dict
        existing = {
            "start_time": datetime.fromtimestamp(1512234126, tz=timezone.utc),
            "distance_m": 10000.0,
            "avg_hr": 145,
        }
        # Raw payload lacks `start_time` → dedup sees it as missing → returns False
        result = match_activities(raw_garmin, existing)
        assert result is False, (
            "Raw Garmin payload (not adapted) should not match — "
            "callers must adapt first"
        )


# ===========================================================================
# garmin_004 schema: new Activity columns
# ===========================================================================

class TestGarmin004Schema:
    """Verify the Activity model has all garmin_004 columns."""

    def test_new_columns_present_in_activity_model(self):
        from models import Activity

        expected = [
            "garmin_activity_id",
            "avg_pace_min_per_km",
            "max_pace_min_per_km",
            "steps",
            "device_name",
            "start_lat",
            "start_lng",
        ]
        for col in expected:
            assert hasattr(Activity, col), (
                f"Activity model missing garmin_004 column: {col}"
            )

    def test_garmin_004_migration_file_exists(self):
        import pathlib
        alembic_dir = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"
        migrations = list(alembic_dir.glob("garmin_004_*.py"))
        assert migrations, "garmin_004 migration file not found"

    def test_migration_chains_from_garmin_003(self):
        import pathlib
        alembic_dir = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"
        path = list(alembic_dir.glob("garmin_004_*.py"))[0]
        content = path.read_text()
        assert 'down_revision' in content
        assert '"garmin_003"' in content or "'garmin_003'" in content, (
            "garmin_004 must chain from garmin_003"
        )
