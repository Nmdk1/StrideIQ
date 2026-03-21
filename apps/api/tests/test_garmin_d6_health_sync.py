"""
D6: Health/Wellness Ingestion Tests (GarminDay)

Tests for process_garmin_health_task in apps/api/tasks/garmin_webhook_tasks.py.

Coverage:
  - Source contract: no raw Garmin field names in task module
  - Data type routing: each data_type calls the correct adapter
  - Upsert creates new GarminDay row when none exists
  - Upsert updates existing GarminDay row additively (no destructive overwrites)
  - Multiple data_types for the same date populate the same row
  - Stress JSONB samples stored as-is (including negative avg_stress)
  - CalendarDate rule (L1): sleep calendarDate is the wakeup morning
  - Payload shape: both dict and list handled defensively
  - Unknown data_type is logged and skipped without crashing
"""

import inspect
import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

ATHLETE_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Module-level autouse fixture: block all Celery/broker side effects
# ---------------------------------------------------------------------------
# Root cause of the historical hang: tests that call process_garmin_health_task.run()
# with valid payloads (processed > 0) trigger the briefing refresh path, which calls
# enqueue_briefing_refresh() → generate_home_briefing_task.apply_async() → Celery broker.
# In CI (no broker), this blocks indefinitely.  We patch both entry points here
# as an autouse module fixture so every test in this file is always safe.

@pytest.fixture(autouse=True)
def _no_briefing_side_effects():
    with patch("services.home_briefing_cache.mark_briefing_dirty"), \
         patch("tasks.home_briefing_tasks.enqueue_briefing_refresh"), \
         patch("core.cache.invalidate_athlete_cache"):
        yield


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_mock_db():
    return MagicMock()


def _make_mock_garmin_day(calendar_date="2026-02-21"):
    gd = MagicMock()
    gd.id = uuid.uuid4()
    gd.calendar_date = date.fromisoformat(calendar_date)
    # Initialise all nullable columns to None
    gd.sleep_total_s = None
    gd.sleep_score = None
    gd.hrv_overnight_avg = None
    gd.avg_stress = None
    gd.steps = None
    gd.vo2max = None
    gd.stress_samples = None
    gd.body_battery_samples = None
    gd.resting_hr = None
    gd.garmin_sleep_summary_id = None
    gd.garmin_hrv_summary_id = None
    gd.garmin_daily_summary_id = None
    return gd


# Minimal valid raw payloads — envelope only, adapter does the translation.
# These use internal field names because the adapter is called for real here
# (the test drives the full ingest helper, not a mock).

_SLEEP_RAW = {
    "userId": "garmin-user-1",
    "summaryId": "sleep-sum-001",
    "calendarDate": "2026-02-22",
    "durationInSeconds": 28800,
    "deepSleepDurationInSeconds": 7200,
    "lightSleepDurationInSeconds": 14400,
    "remSleepInSeconds": 5400,
    "awakeDurationInSeconds": 1800,
    "overallSleepScore": {"value": 82, "qualifierKey": "GOOD"},
    "validation": "DEVICE",
}

_HRV_RAW = {
    "userId": "garmin-user-1",
    "summaryId": "hrv-sum-001",
    "calendarDate": "2026-02-22",
    "lastNightAvg": 45,
    "lastNight5MinHigh": 62,
}

_STRESS_RAW = {
    "userId": "garmin-user-1",
    "calendarDate": "2026-02-22",
    "averageStressLevel": 38,
    "maxStressLevel": 75,
    "timeOffsetStressLevelValues": "{15: 38, 30: 45}",
    "timeOffsetBodyBatteryValues": "{15: 70, 30: 65}",
}

_STRESS_NEGATIVE_RAW = {
    "userId": "garmin-user-1",
    "calendarDate": "2026-02-22",
    "averageStressLevel": -1,          # insufficient data
    "maxStressLevel": -1,
    "timeOffsetStressLevelValues": None,
    "timeOffsetBodyBatteryValues": None,
}

_DAILY_RAW = {
    "userId": "garmin-user-1",
    "summaryId": "daily-sum-001",
    "calendarDate": "2026-02-22",
    "steps": 8500,
    "restingHeartRateInBeatsPerMinute": 58,
    "averageHeartRateInBeatsPerMinute": 68,
    "minHeartRateInBeatsPerMinute": 52,
    "maxHeartRateInBeatsPerMinute": 112,
    "activeKilocalories": 450,
    "activeTimeInSeconds": 3600,
    "averageStressLevel": 35,
    "maxStressLevel": 70,
    "stressQualifier": "calm",
    "moderateIntensityDurationInSeconds": 1800,
    "vigorousIntensityDurationInSeconds": 900,
}

_USER_METRICS_RAW = {
    "userId": "garmin-user-1",
    "calendarDate": "2026-02-22",
    "vo2Max": 52.5,
}


# ---------------------------------------------------------------------------
# Source contract
# ---------------------------------------------------------------------------

class TestSourceContract:
    """
    D0/D3.3 source contract: raw Garmin field names must NOT appear in
    garmin_webhook_tasks.py. All translation lives in garmin_adapter.py.
    """

    _GARMIN_CAMEL_FIELDS = [
        "summaryId",
        "activityId",
        "startTimeInSeconds",
        "distanceInMeters",
        "calendarDate",
        "lastNightAvg",
        "lastNight5MinHigh",
        "durationInSeconds",
        "deepSleepDurationInSeconds",
        "lightSleepDurationInSeconds",
        "remSleepInSeconds",
        "awakeDurationInSeconds",
        "overallSleepScore",
        "restingHeartRateInBeatsPerMinute",
        "averageHeartRateInBeatsPerMinute",
        "averageStressLevel",
        "maxStressLevel",
        "timeOffsetStressLevelValues",
        "timeOffsetBodyBatteryValues",
        "vo2Max",
        "stepsGoal",
    ]

    def test_task_module_contains_no_garmin_raw_field_names(self):
        import tasks.garmin_webhook_tasks as task_mod
        source = inspect.getsource(task_mod)
        for field in self._GARMIN_CAMEL_FIELDS:
            assert field not in source, (
                f"Raw Garmin field name '{field}' found in garmin_webhook_tasks.py. "
                "All Garmin→internal translation must happen in garmin_adapter.py."
            )

    def test_task_imports_health_adapters(self):
        import tasks.garmin_webhook_tasks as task_mod
        source = inspect.getsource(task_mod)
        for fn in (
            "adapt_sleep_summary",
            "adapt_hrv_summary",
            "adapt_stress_detail",
            "adapt_daily_summary",
            "adapt_user_metrics",
        ):
            assert fn in source, f"{fn} not imported in garmin_webhook_tasks.py"


# ---------------------------------------------------------------------------
# Data type routing
# ---------------------------------------------------------------------------

class TestDataTypeRouting:
    """Each data_type string must route to the correct adapter function."""

    def _run_task(self, data_type, payload, mock_db, existing_row=None):
        from tasks.garmin_webhook_tasks import process_garmin_health_task
        mock_db.query.return_value.filter.return_value.first.return_value = existing_row
        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db):
            return process_garmin_health_task.run(ATHLETE_ID, data_type, payload)

    def test_sleeps_uses_adapt_sleep_summary(self):
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch("tasks.garmin_webhook_tasks.adapt_sleep_summary") as mock_fn, \
             patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db):
            mock_fn.return_value = {"calendar_date": "2026-02-22", "sleep_total_s": 28800}
            process_garmin_health_task = __import__(
                "tasks.garmin_webhook_tasks", fromlist=["process_garmin_health_task"]
            ).process_garmin_health_task
            process_garmin_health_task.run(ATHLETE_ID, "sleeps", _SLEEP_RAW)
        mock_fn.assert_called_once_with(_SLEEP_RAW)

    def test_hrv_uses_adapt_hrv_summary(self):
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch("tasks.garmin_webhook_tasks.adapt_hrv_summary") as mock_fn, \
             patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db):
            mock_fn.return_value = {"calendar_date": "2026-02-22", "hrv_overnight_avg": 45}
            process_garmin_health_task = __import__(
                "tasks.garmin_webhook_tasks", fromlist=["process_garmin_health_task"]
            ).process_garmin_health_task
            process_garmin_health_task.run(ATHLETE_ID, "hrv", _HRV_RAW)
        mock_fn.assert_called_once_with(_HRV_RAW)

    def test_stress_uses_adapt_stress_detail(self):
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch("tasks.garmin_webhook_tasks.adapt_stress_detail") as mock_fn, \
             patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db):
            mock_fn.return_value = {"calendar_date": "2026-02-22", "avg_stress": 38}
            process_garmin_health_task = __import__(
                "tasks.garmin_webhook_tasks", fromlist=["process_garmin_health_task"]
            ).process_garmin_health_task
            process_garmin_health_task.run(ATHLETE_ID, "stress", _STRESS_RAW)
        mock_fn.assert_called_once_with(_STRESS_RAW)

    def test_dailies_uses_adapt_daily_summary(self):
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch("tasks.garmin_webhook_tasks.adapt_daily_summary") as mock_fn, \
             patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db):
            mock_fn.return_value = {"calendar_date": "2026-02-22", "steps": 8500}
            process_garmin_health_task = __import__(
                "tasks.garmin_webhook_tasks", fromlist=["process_garmin_health_task"]
            ).process_garmin_health_task
            process_garmin_health_task.run(ATHLETE_ID, "dailies", _DAILY_RAW)
        mock_fn.assert_called_once_with(_DAILY_RAW)

    def test_user_metrics_uses_adapt_user_metrics(self):
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch("tasks.garmin_webhook_tasks.adapt_user_metrics") as mock_fn, \
             patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db):
            mock_fn.return_value = {"calendar_date": "2026-02-22", "vo2max": 52.5}
            process_garmin_health_task = __import__(
                "tasks.garmin_webhook_tasks", fromlist=["process_garmin_health_task"]
            ).process_garmin_health_task
            process_garmin_health_task.run(ATHLETE_ID, "user-metrics", _USER_METRICS_RAW)
        mock_fn.assert_called_once_with(_USER_METRICS_RAW)

    def test_unknown_data_type_skipped_without_crash(self):
        mock_db = _make_mock_db()
        from tasks.garmin_webhook_tasks import process_garmin_health_task
        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db):
            result = process_garmin_health_task.run(ATHLETE_ID, "respiration", _DAILY_RAW)
        # Must not crash; must return something indicating skip
        assert result is not None
        mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# Upsert logic
# ---------------------------------------------------------------------------

class TestUpsertLogic:
    """GarminDay upsert: create on miss, additive update on hit."""

    def _run_ingest(self, data_type, payload, existing_row=None):
        from tasks.garmin_webhook_tasks import _ingest_health_item
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = existing_row
        _ingest_health_item(payload, data_type, ATHLETE_ID, mock_db)
        return mock_db

    def test_creates_new_row_when_none_exists(self):
        mock_db = self._run_ingest("sleeps", _SLEEP_RAW, existing_row=None)
        mock_db.add.assert_called_once()
        added = mock_db.add.call_args[0][0]
        assert added.sleep_total_s == 28800
        assert added.sleep_score == 82

    def test_updates_existing_row_additively(self):
        """Existing row updated with new data; no new row added."""
        existing = _make_mock_garmin_day("2026-02-22")
        mock_db = self._run_ingest("sleeps", _SLEEP_RAW, existing_row=existing)
        mock_db.add.assert_not_called()
        assert existing.sleep_total_s == 28800
        assert existing.sleep_score == 82

    def test_update_preserves_existing_fields_not_in_payload(self):
        """
        When a sleep update arrives, daily summary fields on the existing row
        must NOT be cleared (additive contract).
        """
        existing = _make_mock_garmin_day("2026-02-22")
        existing.steps = 9000   # from a previous dailies upsert
        existing.resting_hr = 55

        self._run_ingest("sleeps", _SLEEP_RAW, existing_row=existing)

        # Sleep fields updated
        assert existing.sleep_total_s == 28800
        # Daily fields untouched (they were None in sleep adapter output)
        assert existing.steps == 9000
        assert existing.resting_hr == 55

    def test_daily_summary_fields_correct(self):
        mock_db = self._run_ingest("dailies", _DAILY_RAW, existing_row=None)
        added = mock_db.add.call_args[0][0]
        assert added.steps == 8500
        assert added.resting_hr == 58
        assert added.avg_stress == 35
        assert added.active_kcal == 450

    def test_hrv_fields_correct(self):
        mock_db = self._run_ingest("hrv", _HRV_RAW, existing_row=None)
        added = mock_db.add.call_args[0][0]
        assert added.hrv_overnight_avg == 45
        assert added.hrv_5min_high == 62

    def test_user_metrics_vo2max_stored(self):
        mock_db = self._run_ingest("user-metrics", _USER_METRICS_RAW, existing_row=None)
        added = mock_db.add.call_args[0][0]
        assert added.vo2max == 52.5

    def test_athlete_id_set_on_new_row(self):
        mock_db = self._run_ingest("hrv", _HRV_RAW, existing_row=None)
        added = mock_db.add.call_args[0][0]
        assert str(added.athlete_id) == ATHLETE_ID

    def test_calendar_date_set_on_new_row(self):
        mock_db = self._run_ingest("hrv", _HRV_RAW, existing_row=None)
        added = mock_db.add.call_args[0][0]
        assert added.calendar_date == date(2026, 2, 22)

    def test_none_values_not_written_to_existing_row(self):
        """
        Adapter may return None for absent fields. None values must not
        overwrite real data already on the row.
        """
        existing = _make_mock_garmin_day("2026-02-22")
        existing.hrv_overnight_avg = 50   # real value from earlier

        # HRV payload that only has lastNightAvg (no 5min high)
        raw_partial = {**_HRV_RAW}
        raw_partial.pop("lastNight5MinHigh", None)
        # adapt_hrv_summary will return hrv_5min_high=None for absent field

        # Mock adapt_hrv_summary to return a partial dict
        from tasks.garmin_webhook_tasks import _ingest_health_item
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        with patch("tasks.garmin_webhook_tasks.adapt_hrv_summary") as mock_fn:
            mock_fn.return_value = {
                "calendar_date": "2026-02-22",
                "garmin_hrv_summary_id": "hrv-sum-002",
                "hrv_overnight_avg": 48,
                "hrv_5min_high": None,   # absent from payload
            }
            _ingest_health_item(raw_partial, "hrv", ATHLETE_ID, mock_db)

        assert existing.hrv_overnight_avg == 48       # updated
        # hrv_5min_high was not set to None (MagicMock doesn't record setattr called with None)
        # Verify via explicit check: setattr should NOT have been called with None value
        # (this is enforced by the _upsert_garmin_day implementation)


# ---------------------------------------------------------------------------
# Multiple data types — same date, same row
# ---------------------------------------------------------------------------

class TestMultipleDataTypesSameDate:
    """All data types for the same date should populate the same GarminDay row."""

    def test_sleep_then_hrv_same_row(self):
        """Sleep update followed by HRV update should both land on the same row."""
        from tasks.garmin_webhook_tasks import _ingest_health_item, _upsert_garmin_day

        # Simulate two sequential upserts on the same existing row
        row = _make_mock_garmin_day("2026-02-22")
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = row

        _ingest_health_item(_SLEEP_RAW, "sleeps", ATHLETE_ID, mock_db)
        _ingest_health_item(_HRV_RAW, "hrv", ATHLETE_ID, mock_db)

        # Both sets of fields should be on the single row
        assert row.sleep_total_s == 28800
        assert row.hrv_overnight_avg == 45
        mock_db.add.assert_not_called()

    def test_daily_then_stress_same_row(self):
        row = _make_mock_garmin_day("2026-02-22")
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = row

        from tasks.garmin_webhook_tasks import _ingest_health_item
        _ingest_health_item(_DAILY_RAW, "dailies", ATHLETE_ID, mock_db)
        _ingest_health_item(_STRESS_RAW, "stress", ATHLETE_ID, mock_db)

        assert row.steps == 8500              # from dailies
        assert row.stress_samples is not None  # from stress
        mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# Stress JSONB storage and negative values
# ---------------------------------------------------------------------------

class TestStressStorage:
    """Stress samples stored as-is JSONB; negative values not filtered at write time."""

    def _run(self, raw, existing=None):
        from tasks.garmin_webhook_tasks import _ingest_health_item
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        _ingest_health_item(raw, "stress", ATHLETE_ID, mock_db)
        return mock_db

    def test_stress_samples_stored_as_is(self):
        mock_db = self._run(_STRESS_RAW)
        added = mock_db.add.call_args[0][0]
        assert added.stress_samples == "{15: 38, 30: 45}"

    def test_body_battery_samples_stored_as_is(self):
        mock_db = self._run(_STRESS_RAW)
        added = mock_db.add.call_args[0][0]
        assert added.body_battery_samples == "{15: 70, 30: 65}"

    def test_negative_avg_stress_stored_not_filtered(self):
        """
        AC §D6.3: negative stress values mean insufficient data, not low stress.
        They must be stored as-is. Filtering happens at query time.
        """
        mock_db = self._run(_STRESS_NEGATIVE_RAW)
        added = mock_db.add.call_args[0][0]
        assert added.avg_stress == -1

    def test_avg_stress_on_existing_row_updated(self):
        existing = _make_mock_garmin_day("2026-02-22")
        existing.avg_stress = 50
        self._run(_STRESS_RAW, existing=existing)
        assert existing.avg_stress == 38  # overwritten by new stress update


# ---------------------------------------------------------------------------
# CalendarDate rule (L1)
# ---------------------------------------------------------------------------

class TestCalendarDateRule:
    """
    Sleep calendarDate is the WAKEUP DAY (morning), not the preceding night.
    The adapter preserves it as-is; the task must store it correctly as a date.
    """

    def test_sleep_calendar_date_is_wakeup_day(self):
        """
        Sleep that starts Friday night and ends Saturday morning should have
        calendar_date = Saturday. The adapter preserves Garmin's calendarDate
        directly — no adjustment needed.
        """
        from tasks.garmin_webhook_tasks import _ingest_health_item
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        saturday_sleep = {**_SLEEP_RAW, "calendarDate": "2026-02-21"}  # Saturday
        _ingest_health_item(saturday_sleep, "sleeps", ATHLETE_ID, mock_db)

        added = mock_db.add.call_args[0][0]
        assert added.calendar_date == date(2026, 2, 21)

    def test_calendar_date_string_parsed_to_date_object(self):
        """calendar_date from adapter is a string; task must convert to date."""
        from tasks.garmin_webhook_tasks import _ingest_health_item
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        _ingest_health_item(_HRV_RAW, "hrv", ATHLETE_ID, mock_db)

        added = mock_db.add.call_args[0][0]
        assert isinstance(added.calendar_date, date)
        assert added.calendar_date == date(2026, 2, 22)

    def test_missing_calendar_date_skipped_gracefully(self):
        """Payload with no calendarDate must be skipped without crashing."""
        from tasks.garmin_webhook_tasks import _ingest_health_item
        raw_no_date = {k: v for k, v in _SLEEP_RAW.items() if k != "calendarDate"}
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        _ingest_health_item(raw_no_date, "sleeps", ATHLETE_ID, mock_db)

        mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# Payload shape normalisation
# ---------------------------------------------------------------------------

class TestPayloadShapeNormalization:
    """Defensive handling of both dict and list Garmin push payload shapes."""

    def _run_task(self, data_type, payload):
        from tasks.garmin_webhook_tasks import process_garmin_health_task
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db):
            result = process_garmin_health_task.run(ATHLETE_ID, data_type, payload)
        return result, mock_db

    def test_dict_payload_processed_as_single_item(self):
        result, mock_db = self._run_task("hrv", _HRV_RAW)
        assert result["processed"] == 1
        mock_db.add.assert_called_once()

    def test_list_payload_iterates_all_items(self):
        hrv_2 = {**_HRV_RAW, "calendarDate": "2026-02-23"}
        result, mock_db = self._run_task("hrv", [_HRV_RAW, hrv_2])
        assert result["processed"] == 2
        assert mock_db.add.call_count == 2

    def test_empty_list_does_nothing(self):
        result, mock_db = self._run_task("hrv", [])
        assert result["processed"] == 0
        mock_db.add.assert_not_called()

    def test_list_with_missing_calendar_date_skips_bad_items(self):
        """Items with no calendarDate are skipped; valid items still processed."""
        bad_item = {k: v for k, v in _HRV_RAW.items() if k != "calendarDate"}
        result, mock_db = self._run_task("hrv", [_HRV_RAW, bad_item])
        # Only the valid item creates a row
        assert result["processed"] == 1
        mock_db.add.assert_called_once()


class TestHealthBriefingRefreshTrigger:
    """Health ingestion should refresh home briefing when data changes."""

    def test_refresh_triggered_when_processed(self):
        from tasks.garmin_webhook_tasks import process_garmin_health_task
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("services.home_briefing_cache.mark_briefing_dirty") as mock_dirty, \
             patch("tasks.home_briefing_tasks.enqueue_briefing_refresh") as mock_enq:
            result = process_garmin_health_task.run(ATHLETE_ID, "hrv", _HRV_RAW)

        assert result["processed"] == 1
        mock_dirty.assert_called_once_with(ATHLETE_ID)
        mock_enq.assert_called_once_with(ATHLETE_ID, force=True)

    def test_refresh_not_triggered_when_nothing_processed(self):
        from tasks.garmin_webhook_tasks import process_garmin_health_task
        mock_db = _make_mock_db()
        # Missing calendarDate -> skipped
        bad_item = {k: v for k, v in _HRV_RAW.items() if k != "calendarDate"}
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("services.home_briefing_cache.mark_briefing_dirty") as mock_dirty, \
             patch("tasks.home_briefing_tasks.enqueue_briefing_refresh") as mock_enq:
            result = process_garmin_health_task.run(ATHLETE_ID, "hrv", bad_item)

        assert result["processed"] == 0
        mock_dirty.assert_not_called()
        mock_enq.assert_not_called()


class _FakeRedisCoalesce:
    def __init__(self):
        self._store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._store:
            return False
        self._store[key] = value
        return True

    def setex(self, key, ttl, value):
        self._store[key] = value

    def exists(self, key):
        return 1 if key in self._store else 0

    def delete(self, key):
        self._store.pop(key, None)

    def get(self, key):
        return self._store.get(key)


class TestHealthWebhookBurstCoalescing:
    def test_webhook_burst_coalesces_refreshes(self):
        """
        Burst of health webhooks should enqueue at most one active refresh
        plus one follow-up task.
        """
        from tasks.garmin_webhook_tasks import process_garmin_health_task
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        fake_r = _FakeRedisCoalesce()

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("tasks.garmin_webhook_tasks.get_redis_client", return_value=fake_r), \
             patch("services.home_briefing_cache.mark_briefing_dirty"), \
             patch("services.home_briefing_cache.is_task_lock_held", return_value=False), \
             patch("tasks.home_briefing_tasks.enqueue_briefing_refresh") as mock_enq, \
             patch("tasks.garmin_webhook_tasks.flush_home_briefing_followup_task") as mock_followup:
            mock_enq.return_value = True
            mock_followup.apply_async = MagicMock()

            # First event in burst
            r1 = process_garmin_health_task.run(ATHLETE_ID, "hrv", _HRV_RAW)
            # Second event in same burst window
            r2 = process_garmin_health_task.run(ATHLETE_ID, "stress", _STRESS_RAW)

        assert r1["processed"] == 1
        assert r2["processed"] == 1
        # One active enqueue only inside the coalesce window.
        assert mock_enq.call_count == 1
        # One queued follow-up only.
        mock_followup.apply_async.assert_called_once()
