"""
Garmin Connect Adapter Layer (D3)

Single point of translation between raw Garmin API payloads and internal
model field names. If Garmin renames a field, only this file changes.

CONTRACT (enforced by tests):
  - In the adapter-to-model/dedup path, Garmin field names (camelCase API
    names such as startTimeInSeconds, distanceInMeters) appear ONLY in this
    file. No other file in that path should translate raw Garmin field names.
  - This contract is scoped to the webhook/API ingestion path. The separate
    DI (takeout file import) path in services/provider_import/garmin_di_connect.py
    also uses Garmin field names — that is a distinct, compliant path and is
    not subject to this constraint.
  - All output dicts use exclusively internal field names.
  - activity_deduplication.py must never receive a raw Garmin payload.
    Call chain: raw payload → adapt_*() → internal dict → deduplication.
  - Fields not in the official schema are NOT mapped in Tier 1.

Portal verification (February 2026):
  - Official schema uses camelCase, e.g. `distanceInMeters` (not PascalCase).
  - Running dynamics (stride length, GCT, vertical oscillation, ratio, GAP)
    are FIT-file-only — absent from the JSON Activity API.
  - Power is available per-sample in activityDetails, not at summary level.
  - Training Effect, self-evaluation, body battery impact are undocumented
    and deferred until the D4.3 live webhook capture provides evidence.

See docs/PHASE2_GARMIN_INTEGRATION_AC.md §D3
See docs/garmin-portal/HEALTH_API.md for official schema definitions
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# --- Activity type → internal sport mapping ---
# Only run types map to "run". All others are skipped by the ingest task.
_ACTIVITY_TYPE_MAP: Dict[str, Optional[str]] = {
    "RUNNING": "run",
    "TRAIL_RUNNING": "run",
    "TREADMILL_RUNNING": "run",
    "INDOOR_RUNNING": "run",
    "VIRTUAL_RUN": "run",
}


# ---------------------------------------------------------------------------
# D3.1 — Activity adapter
# ---------------------------------------------------------------------------

def adapt_activity_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a raw Garmin ClientActivity payload to internal Activity field names.

    Only fields present in the official ClientActivity JSON schema are mapped
    here. FIT-file-only fields (running dynamics), undocumented fields (TE,
    self-eval, body battery at activity level), and per-sample-only fields
    (power) are excluded from Tier 1 mapping.

    Args:
        raw: Raw ClientActivity dict from Garmin push webhook or REST API.

    Returns:
        Dict with internal field names only. All values may be None if the
        corresponding Garmin field is absent from the payload.
    """
    return {
        # --- Identifiers ---
        "external_activity_id": _str_or_none(raw.get("summaryId")),
        "garmin_activity_id": _int_or_none(raw.get("activityId")),
        "provider": "garmin",

        # --- Timing ---
        "start_time": _unix_to_datetime(raw.get("startTimeInSeconds")),
        "duration_s": _int_or_none(raw.get("durationInSeconds")),

        # --- Sport classification ---
        "sport": _map_activity_type(raw.get("activityType")),

        # --- Metadata ---
        "name": _str_or_none(raw.get("activityName")),
        "source": "garmin_manual" if raw.get("manual") else "garmin",
        "device_name": _str_or_none(raw.get("deviceName")),

        # --- Cardiovascular ---
        "avg_hr": _int_or_none(raw.get("averageHeartRateInBeatsPerMinute")),
        "max_hr": _int_or_none(raw.get("maxHeartRateInBeatsPerMinute")),

        # --- Movement ---
        "average_speed": _float_or_none(raw.get("averageSpeedInMetersPerSecond")),
        "max_speed": _float_or_none(raw.get("maxSpeedInMetersPerSecond")),
        "distance_m": _float_or_none(raw.get("distanceInMeters")),
        "total_elevation_gain": _float_or_none(raw.get("totalElevationGainInMeters")),
        "total_descent_m": _float_or_none(raw.get("totalElevationLossInMeters")),

        # --- Cadence ---
        "avg_cadence": _int_or_none(raw.get("averageRunCadenceInStepsPerMinute")),
        "max_cadence": _int_or_none(raw.get("maxRunCadenceInStepsPerMinute")),

        # --- Pace ---
        "avg_pace_min_per_km": _float_or_none(raw.get("averagePaceInMinutesPerKilometer")),
        "max_pace_min_per_km": _float_or_none(raw.get("maxPaceInMinutesPerKilometer")),

        # --- Energy ---
        "active_kcal": _int_or_none(raw.get("activeKilocalories")),

        # --- Steps ---
        "steps": _int_or_none(raw.get("steps")),

        # --- Location ---
        "start_lat": _float_or_none(raw.get("startingLatitudeInDegree")),
        "start_lng": _float_or_none(raw.get("startingLongitudeInDegree")),

        # --- Fields intentionally NOT mapped in Tier 1 ---
        # Running dynamics: stride length, GCT, GCT balance, vert oscillation,
        # vert ratio, GAP — FIT-file only, absent from JSON API.
        # Training Effect: aerobic/anaerobic TE, TE label — undocumented.
        # Self-evaluation: feel, perceived effort — undocumented.
        # Body battery impact at activity level — undocumented.
        # Moving time: not in official schema.
        # Power at summary level: per-sample only (stream samples in Details).
    }


# ---------------------------------------------------------------------------
# D3.2 — Health / wellness adapters
# ---------------------------------------------------------------------------

def adapt_daily_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a raw Garmin ClientDaily payload to GarminDay daily fields.

    Args:
        raw: Raw ClientDaily dict (from push webhook or dailies REST endpoint).

    Returns:
        Dict with GarminDay internal field names.
    """
    return {
        "calendar_date": _str_or_none(raw.get("calendarDate")),  # "YYYY-MM-DD"
        "garmin_daily_summary_id": _str_or_none(raw.get("summaryId")),

        # Cardiovascular
        "resting_hr": _int_or_none(raw.get("restingHeartRateInBeatsPerMinute")),
        "min_hr": _int_or_none(raw.get("minHeartRateInBeatsPerMinute")),
        "max_hr": _int_or_none(raw.get("maxHeartRateInBeatsPerMinute")),

        # Stress — negative values (-1 to -5) indicate data quality issues.
        # Store as-is. Consumers must filter negatives before statistics.
        "avg_stress": _int_or_none(raw.get("averageStressLevel")),
        "max_stress": _int_or_none(raw.get("maxStressLevel")),
        "stress_qualifier": _str_or_none(raw.get("stressQualifier")),

        # Activity
        "steps": _int_or_none(raw.get("steps")),
        "active_time_s": _int_or_none(raw.get("activeTimeInSeconds")),
        "active_kcal": _int_or_none(raw.get("activeKilocalories")),
        "moderate_intensity_s": _int_or_none(raw.get("moderateIntensityDurationInSeconds")),
        "vigorous_intensity_s": _int_or_none(raw.get("vigorousIntensityDurationInSeconds")),
    }


def adapt_sleep_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a raw Garmin ClientSleep payload to GarminDay sleep fields.

    CALENDAR DATE RULE (L1): calendarDate from Garmin is the WAKEUP day
    (morning), not the preceding night. For example, Friday night sleep
    returns calendarDate = Saturday. This is correct as-is — do NOT adjust.
    When joining sleep to activity data, use:
        garmin_day.calendar_date = activity.start_time::date  (wakeup day)

    The adapter preserves the date as Garmin provides it.

    Note on sleep score: Garmin returns a nested `overallSleepScore` object:
        { "value": 87, "qualifierKey": "GOOD" }
    Extract value and qualifierKey separately.

    Note on sleep data quality: Garmin devices may auto-sync during the night
    before sleep is complete, resulting in incomplete summary records. Always
    update with the most recent push notification for a given calendarDate.
    """
    score_obj = raw.get("overallSleepScore") or {}

    return {
        "calendar_date": _str_or_none(raw.get("calendarDate")),
        "garmin_sleep_summary_id": _str_or_none(raw.get("summaryId")),

        "sleep_total_s": _int_or_none(raw.get("durationInSeconds")),
        "sleep_deep_s": _int_or_none(raw.get("deepSleepDurationInSeconds")),
        "sleep_light_s": _int_or_none(raw.get("lightSleepDurationInSeconds")),
        "sleep_rem_s": _int_or_none(raw.get("remSleepInSeconds")),
        "sleep_awake_s": _int_or_none(raw.get("awakeDurationInSeconds")),

        # Nested sleep score object
        "sleep_score": _int_or_none(score_obj.get("value")),
        "sleep_score_qualifier": _str_or_none(score_obj.get("qualifierKey")),
        "sleep_validation": _str_or_none(raw.get("validation")),
    }


def adapt_hrv_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a raw Garmin ClientHRVSummary payload to GarminDay HRV fields.

    Args:
        raw: Raw ClientHRVSummary dict.

    Returns:
        Dict with GarminDay HRV field names.
    """
    return {
        "calendar_date": _str_or_none(raw.get("calendarDate")),
        "garmin_hrv_summary_id": _str_or_none(raw.get("summaryId")),

        "hrv_overnight_avg": _int_or_none(raw.get("lastNightAvg")),
        "hrv_5min_high": _int_or_none(raw.get("lastNight5MinHigh")),
    }


def adapt_stress_detail(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a raw Garmin ClientStress payload to GarminDay JSONB sample fields.

    Stress values: negative values (-1 to -5) indicate data quality issues
    (off-wrist, large motion, etc.). These are stored as-is in the JSONB
    samples. Consumers must filter negatives before computing statistics.
    The `timeOffsetStressLevelValues` field may arrive as a string
    representation of a dict; stored as-is for flexibility.

    Args:
        raw: Raw ClientStress dict.

    Returns:
        Dict with GarminDay stress/body-battery field names.
    """
    return {
        "calendar_date": _str_or_none(raw.get("calendarDate")),

        # Aggregate stress (may also arrive via daily summary — upsert handles this)
        "avg_stress": _int_or_none(raw.get("averageStressLevel")),
        "max_stress": _int_or_none(raw.get("maxStressLevel")),

        # Raw time-offset samples (stored as-is for Tier 2 analysis)
        "stress_samples": raw.get("timeOffsetStressLevelValues"),
        "body_battery_samples": raw.get("timeOffsetBodyBatteryValues"),
    }


def adapt_activity_detail_envelope(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract top-level fields from a raw Garmin ClientActivityDetail payload.

    Separates the envelope fields (identifiers) from the samples array so that
    the ingest task can use internal field names without touching raw Garmin keys.

    Args:
        raw: Raw ClientActivityDetail dict.

    Returns:
        {
            "garmin_activity_id": int | None,
            "external_activity_id": str | None,
            "samples": list,
        }
    """
    return {
        "garmin_activity_id": _int_or_none(raw.get("activityId")),
        "external_activity_id": _str_or_none(raw.get("summaryId")),
        "samples": raw.get("samples") or [],
    }


def adapt_activity_detail_samples(
    samples: list,
    activity_start_unix: float = 0.0,
) -> Dict[str, Any]:
    """
    Extract per-channel arrays from a Garmin ClientActivityDetail samples list.

    Returns a stream_data dict compatible with ActivityStream.stream_data JSONB:
        {
            "time": [relative_seconds, ...],   # seconds since activity start
            "heartrate": [bpm_int, ...],
            "watts": [float, ...],
            "latlng": [[lat, lng], ...],        # None where either coord absent
            "altitude": [meters_float, ...],
            "velocity_smooth": [m/s_float, ...],
            "cadence": [steps_per_min_int, ...],
        }

    Arrays are aligned to sample index. Where a field is absent from a sample
    the value is None (preserves alignment with the time axis). Channels with
    zero non-None values across all samples are excluded from the output.

    Fields intentionally NOT mapped (absent from official Sample schema):
      - strideLength, groundContactTime, verticalOscillation, verticalRatio
      - Running dynamics are FIT-file-only (see docs/garmin-portal/HEALTH_API.md §M2)

    Args:
        samples: List of raw Garmin sample dicts from ClientActivityDetail.
        activity_start_unix: Unix timestamp (seconds) of the parent activity.
                             Used to compute relative time offsets.

    Returns:
        Dict of channel_name → aligned value list. Empty dict if samples is empty.

    See docs/PHASE2_GARMIN_INTEGRATION_AC.md §D5.2
    See docs/garmin-portal/HEALTH_API.md §activityDetails Sample schema
    """
    if not samples:
        return {}

    time_vals: list = []
    heartrate_vals: list = []
    watts_vals: list = []
    latlng_vals: list = []
    altitude_vals: list = []
    velocity_vals: list = []
    cadence_vals: list = []

    activity_start_unix_int = int(activity_start_unix)

    for sample in samples:
        # Time — relative seconds from activity start
        sample_ts = sample.get("startTimeInSeconds")
        time_vals.append(
            int(sample_ts) - activity_start_unix_int if sample_ts is not None else None
        )

        heartrate_vals.append(_int_or_none(sample.get("heartRate")))
        watts_vals.append(_float_or_none(sample.get("powerInWatts")))

        lat = _float_or_none(sample.get("latitudeInDegree"))
        lng = _float_or_none(sample.get("longitudeInDegree"))
        latlng_vals.append([lat, lng] if lat is not None and lng is not None else None)

        altitude_vals.append(_float_or_none(sample.get("elevationInMeters")))
        velocity_vals.append(_float_or_none(sample.get("speedMetersPerSecond")))
        cadence_vals.append(_int_or_none(sample.get("stepsPerMinute")))

    def _keep(vals: list) -> bool:
        return any(v is not None for v in vals)

    channels: Dict[str, Any] = {}
    if _keep(time_vals):
        channels["time"] = time_vals
    if _keep(heartrate_vals):
        channels["heartrate"] = heartrate_vals
    if _keep(watts_vals):
        channels["watts"] = watts_vals
    if _keep(latlng_vals):
        channels["latlng"] = latlng_vals
    if _keep(altitude_vals):
        channels["altitude"] = altitude_vals
    if _keep(velocity_vals):
        channels["velocity_smooth"] = velocity_vals
    if _keep(cadence_vals):
        channels["cadence"] = cadence_vals

    return channels


def adapt_user_metrics(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a raw Garmin User Metrics payload to GarminDay user metrics fields.

    Only `vo2Max` is captured in Tier 1. `vo2MaxCycling` and `fitnessAge`
    are deferred.

    Args:
        raw: Raw user metrics dict.

    Returns:
        Dict with GarminDay user metrics field names.
    """
    return {
        "calendar_date": _str_or_none(raw.get("calendarDate")),
        "vo2max": _float_or_none(raw.get("vo2Max")),
    }


# ---------------------------------------------------------------------------
# Internal type coercion helpers
# ---------------------------------------------------------------------------

def _str_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _int_or_none(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _unix_to_datetime(value: Any) -> Optional[datetime]:
    """Convert a Unix timestamp (int seconds) to a UTC-aware datetime."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _map_activity_type(garmin_type: Any) -> Optional[str]:
    """
    Map Garmin activityType string to internal sport code.

    Returns "run" for known running types, None for everything else.
    The ingest task skips activities where sport is None.
    """
    if garmin_type is None:
        return None
    return _ACTIVITY_TYPE_MAP.get(str(garmin_type).upper())
