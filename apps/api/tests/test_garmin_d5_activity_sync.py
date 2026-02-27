"""
D5: Activity Sync Tests

Tests for:
  - D5.1: process_garmin_activity_task (activity summary ingestion)
  - D5.2: process_garmin_activity_detail_task (stream sample ingestion)

Coverage:
  - Payload shape normalization (dict vs list)
  - Activity type filtering (run only)
  - Deduplication behaviour (new / Garmin idempotent / Strava precedence)
  - Provider precedence: Garmin overwrites Strava duplicate
  - Stream sample extraction via adapt_activity_detail_samples
  - Unknown activityId handling in detail task
  - last_garmin_sync update after ingestion
  - Source contract: no raw Garmin field names in task module
"""

import inspect
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call

import pytest

from services.garmin_adapter import adapt_activity_detail_samples


# ---------------------------------------------------------------------------
# Shared test fixtures / helpers
# ---------------------------------------------------------------------------

ATHLETE_ID = str(uuid.uuid4())

# Minimal raw Garmin running activity (ClientActivity shape)
_RUNNING_RAW = {
    "userId": "garmin-user-1",
    "summaryId": "sum-abc-001",
    "activityId": 5001968355,
    "activityName": "Morning Run",
    "activityType": "RUNNING",
    "startTimeInSeconds": 1740000000,
    "durationInSeconds": 3600,
    "distanceInMeters": 10000.0,
    "averageHeartRateInBeatsPerMinute": 145,
    "maxHeartRateInBeatsPerMinute": 165,
    "averageSpeedInMetersPerSecond": 2.78,
    "totalElevationGainInMeters": 50.0,
}

_CYCLING_RAW = {
    "userId": "garmin-user-1",
    "summaryId": "sum-cycling-001",
    "activityId": 5001968356,
    "activityType": "CYCLING",
    "startTimeInSeconds": 1740000000,
    "durationInSeconds": 3600,
    "distanceInMeters": 30000.0,
}

_TRAIL_RUNNING_RAW = {
    "userId": "garmin-user-1",
    "summaryId": "sum-trail-001",
    "activityId": 5001968357,
    "activityType": "TRAIL_RUNNING",
    "startTimeInSeconds": 1740003600,
    "durationInSeconds": 7200,
    "distanceInMeters": 15000.0,
}


def _make_mock_db():
    """Return a MagicMock SQLAlchemy session."""
    return MagicMock()


def _make_mock_athlete():
    athlete = MagicMock()
    athlete.id = uuid.UUID(ATHLETE_ID)
    athlete.last_garmin_sync = None
    return athlete


def _make_mock_activity(
    provider="garmin",
    external_activity_id="sum-abc-001",
    garmin_activity_id=5001968355,
    distance_m=10000,
    avg_hr=145,
    start_time=None,
):
    """Build a MagicMock Activity row for dedup/idempotency tests."""
    activity = MagicMock()
    activity.id = uuid.uuid4()
    activity.provider = provider
    activity.external_activity_id = external_activity_id
    activity.garmin_activity_id = garmin_activity_id
    activity.distance_m = distance_m
    activity.avg_hr = avg_hr
    activity.start_time = start_time or datetime.fromtimestamp(1740000000, tz=timezone.utc)
    return activity


# ---------------------------------------------------------------------------
# Source contract
# ---------------------------------------------------------------------------

class TestSourceContract:
    """
    Garmin camelCase field names must appear ONLY in garmin_adapter.py.
    The task module must not contain raw Garmin API field names.
    """

    _GARMIN_CAMEL_FIELDS = [
        "summaryId",
        "activityId",
        "activityType",
        "startTimeInSeconds",
        "distanceInMeters",
        "averageHeartRateInBeatsPerMinute",
        "maxHeartRateInBeatsPerMinute",
        "durationInSeconds",
        "averageSpeedInMetersPerSecond",
        "totalElevationGainInMeters",
        "totalElevationLossInMeters",
        "activeKilocalories",
        "averageRunCadenceInStepsPerMinute",
        "maxRunCadenceInStepsPerMinute",
        "averagePaceInMinutesPerKilometer",
        "maxPaceInMinutesPerKilometer",
        "startingLatitudeInDegree",
        "startingLongitudeInDegree",
        # Sample-level fields
        "powerInWatts",
        "heartRate",
        "latitudeInDegree",
        "longitudeInDegree",
        "elevationInMeters",
        "speedMetersPerSecond",
        "stepsPerMinute",
    ]

    def test_task_module_contains_no_garmin_raw_field_names(self):
        """garmin_webhook_tasks.py must not translate raw Garmin field names."""
        import tasks.garmin_webhook_tasks as task_mod
        source = inspect.getsource(task_mod)
        for field in self._GARMIN_CAMEL_FIELDS:
            assert field not in source, (
                f"Raw Garmin field name '{field}' found in garmin_webhook_tasks.py. "
                "All Garmin→internal translation must happen in garmin_adapter.py."
            )

    def test_task_imports_adapt_activity_summary(self):
        """Task module must import adapt_activity_summary from garmin_adapter."""
        import tasks.garmin_webhook_tasks as task_mod
        source = inspect.getsource(task_mod)
        assert "adapt_activity_summary" in source

    def test_task_imports_adapt_activity_detail_samples(self):
        """Detail task must import adapt_activity_detail_samples from garmin_adapter."""
        import tasks.garmin_webhook_tasks as task_mod
        source = inspect.getsource(task_mod)
        assert "adapt_activity_detail_samples" in source

    def test_task_imports_adapt_activity_detail_envelope(self):
        """Detail task must import adapt_activity_detail_envelope (activityId mapping)."""
        import tasks.garmin_webhook_tasks as task_mod
        source = inspect.getsource(task_mod)
        assert "adapt_activity_detail_envelope" in source


# ---------------------------------------------------------------------------
# adapt_activity_detail_samples (pure function — no DB needed)
# ---------------------------------------------------------------------------

class TestAdaptActivityDetailSamples:
    """Tests for the garmin_adapter.adapt_activity_detail_samples function."""

    _SAMPLE_UNIX_START = 1512234126
    _ACTIVITY_START_UNIX = 1512234126

    def _sample(self, **overrides):
        base = {
            "startTimeInSeconds": self._SAMPLE_UNIX_START,
            "latitudeInDegree": 51.0532,
            "longitudeInDegree": -114.0688,
            "elevationInMeters": 1049.4,
            "heartRate": 83,
            "speedMetersPerSecond": 2.5,
            "stepsPerMinute": 180,
            "powerInWatts": 250.0,
        }
        base.update(overrides)
        return base

    def test_time_is_relative_to_activity_start(self):
        samples = [
            self._sample(startTimeInSeconds=self._ACTIVITY_START_UNIX),
            self._sample(startTimeInSeconds=self._ACTIVITY_START_UNIX + 10),
        ]
        result = adapt_activity_detail_samples(samples, self._ACTIVITY_START_UNIX)
        assert result["time"] == [0, 10]

    def test_heartrate_extracted(self):
        samples = [self._sample(heartRate=145), self._sample(heartRate=150)]
        result = adapt_activity_detail_samples(samples, self._ACTIVITY_START_UNIX)
        assert result["heartrate"] == [145, 150]

    def test_power_extracted(self):
        samples = [self._sample(powerInWatts=280.5), self._sample(powerInWatts=310.0)]
        result = adapt_activity_detail_samples(samples, self._ACTIVITY_START_UNIX)
        assert result["watts"] == [280.5, 310.0]

    def test_latlng_extracted_as_pairs(self):
        samples = [
            self._sample(latitudeInDegree=51.0, longitudeInDegree=-114.0),
            self._sample(latitudeInDegree=51.1, longitudeInDegree=-114.1),
        ]
        result = adapt_activity_detail_samples(samples, self._ACTIVITY_START_UNIX)
        assert result["latlng"] == [[51.0, -114.0], [51.1, -114.1]]

    def test_altitude_extracted(self):
        samples = [self._sample(elevationInMeters=1049.4), self._sample(elevationInMeters=1052.0)]
        result = adapt_activity_detail_samples(samples, self._ACTIVITY_START_UNIX)
        assert result["altitude"] == [1049.4, 1052.0]

    def test_velocity_smooth_extracted(self):
        samples = [self._sample(speedMetersPerSecond=2.78), self._sample(speedMetersPerSecond=3.1)]
        result = adapt_activity_detail_samples(samples, self._ACTIVITY_START_UNIX)
        assert result["velocity_smooth"] == [2.78, 3.1]

    def test_cadence_extracted(self):
        samples = [self._sample(stepsPerMinute=180), self._sample(stepsPerMinute=170)]
        result = adapt_activity_detail_samples(samples, self._ACTIVITY_START_UNIX)
        assert result["cadence"] == [180, 170]

    def test_empty_samples_returns_empty_dict(self):
        result = adapt_activity_detail_samples([], 0.0)
        assert result == {}

    def test_channel_excluded_when_all_values_none(self):
        """A channel absent from all samples should not appear in output."""
        samples = [
            # No powerInWatts key in any sample
            {
                "startTimeInSeconds": self._ACTIVITY_START_UNIX,
                "heartRate": 140,
            },
        ]
        result = adapt_activity_detail_samples(samples, self._ACTIVITY_START_UNIX)
        assert "watts" not in result
        assert "heartrate" in result

    def test_partial_sample_channel_included_with_none_placeholder(self):
        """If only some samples have a field, channel is included with None for missing."""
        samples = [
            self._sample(powerInWatts=200.0),
            # second sample missing powerInWatts
            {
                "startTimeInSeconds": self._ACTIVITY_START_UNIX + 1,
                "heartRate": 140,
            },
        ]
        result = adapt_activity_detail_samples(samples, self._ACTIVITY_START_UNIX)
        assert "watts" in result
        assert result["watts"][0] == 200.0
        assert result["watts"][1] is None

    def test_missing_latlng_when_only_one_coordinate_present(self):
        """latlng must be None if only one of lat/lng is present."""
        samples = [
            {
                "startTimeInSeconds": self._ACTIVITY_START_UNIX,
                "latitudeInDegree": 51.0,
                # no longitudeInDegree
            }
        ]
        result = adapt_activity_detail_samples(samples, self._ACTIVITY_START_UNIX)
        # latlng channel excluded entirely (only Nones)
        assert "latlng" not in result


# ---------------------------------------------------------------------------
# D5.1: process_garmin_activity_task — payload shape normalization
# ---------------------------------------------------------------------------

class TestPayloadShapeNormalization:
    """
    The task must handle both dict (single activity) and list (array)
    push payload shapes defensively.

    D4.3 live capture will confirm which Garmin actually sends. D5 handles both.
    """

    def _run_task(self, mock_db, mock_athlete, payload):
        """Helper: patch get_db_sync and call task directly."""
        from tasks.garmin_webhook_tasks import process_garmin_activity_task

        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("tasks.garmin_webhook_tasks._find_athlete_in_db", return_value=mock_athlete):
            return process_garmin_activity_task.run(ATHLETE_ID, payload)

    def test_dict_payload_treated_as_single_item(self):
        """A single dict payload should process exactly one activity."""
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()

        result = self._run_task(mock_db, mock_athlete, _RUNNING_RAW)

        assert result["status"] == "ok"
        # Should have created 1 activity (running) and skipped 0
        assert result["created"] + result["updated"] == 1

    def test_list_payload_processes_all_items(self):
        """A list payload should process each item."""
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()

        payload = [_RUNNING_RAW, _TRAIL_RUNNING_RAW]
        result = self._run_task(mock_db, mock_athlete, payload)

        assert result["status"] == "ok"
        assert result["created"] == 2

    def test_empty_list_does_nothing(self):
        """Empty list payload should result in nothing created/updated."""
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()

        result = self._run_task(mock_db, mock_athlete, [])

        assert result["status"] == "ok"
        assert result["created"] == 0
        assert result["updated"] == 0

    def test_mixed_list_only_runs_processed(self):
        """Mixed list: only running activities created; cycling skipped."""
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()

        payload = [_RUNNING_RAW, _CYCLING_RAW]
        result = self._run_task(mock_db, mock_athlete, payload)

        assert result["created"] == 1
        assert result["skipped"] == 1


# ---------------------------------------------------------------------------
# D5.1: Activity type filtering
# ---------------------------------------------------------------------------

class TestActivityTypeFiltering:
    """Only running activities (sport="run") should be created as Activity rows."""

    def _run_item(self, raw_payload):
        from tasks.garmin_webhook_tasks import _ingest_activity_item
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []
        return _ingest_activity_item(raw_payload, mock_athlete, mock_db)

    def test_running_activity_is_created(self):
        result = self._run_item(_RUNNING_RAW)
        assert result == "created"

    def test_trail_running_is_created(self):
        result = self._run_item(_TRAIL_RUNNING_RAW)
        assert result == "created"

    def test_cycling_activity_is_skipped(self):
        result = self._run_item(_CYCLING_RAW)
        assert result == "skipped"

    def test_treadmill_running_is_created(self):
        raw = {**_RUNNING_RAW, "activityType": "TREADMILL_RUNNING", "summaryId": "sum-treadmill-001"}
        result = self._run_item(raw)
        assert result == "created"

    def test_unknown_sport_is_skipped(self):
        raw = {**_RUNNING_RAW, "activityType": "YOGA", "summaryId": "sum-yoga-001"}
        result = self._run_item(raw)
        assert result == "skipped"

    def test_missing_summary_id_is_skipped(self):
        raw = {k: v for k, v in _RUNNING_RAW.items() if k != "summaryId"}
        result = self._run_item(raw)
        assert result == "skipped"

    def test_missing_start_time_is_skipped(self):
        raw = {k: v for k, v in _RUNNING_RAW.items() if k != "startTimeInSeconds"}
        result = self._run_item(raw)
        assert result == "skipped"


# ---------------------------------------------------------------------------
# D5.1: Deduplication and provider precedence
# ---------------------------------------------------------------------------

class TestDeduplicationAndProviderPrecedence:
    """
    Provider precedence contract [F2]:
    Garmin is primary, Strava is secondary.
    When Garmin+Strava match the same activity:
      - Existing Activity row updated (no new row created)
      - provider set to "garmin"
    """

    def _run_item(self, raw_payload, existing_garmin=None, candidates=None):
        from tasks.garmin_webhook_tasks import _ingest_activity_item
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()

        # First query: idempotency check (garmin+external_id lookup)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_garmin

        # Second query: time-window candidates for dedup
        mock_db.query.return_value.filter.return_value.all.return_value = candidates or []

        return _ingest_activity_item(raw_payload, mock_athlete, mock_db), mock_db

    def test_new_activity_creates_row_with_provider_garmin(self):
        result, mock_db = self._run_item(_RUNNING_RAW)
        assert result == "created"
        mock_db.add.assert_called_once()
        # Verify the added object has provider="garmin"
        added = mock_db.add.call_args[0][0]
        assert added.provider == "garmin"

    def test_idempotent_garmin_reingestion_is_skipped(self):
        """Same Garmin activity arriving twice: second time is skipped."""
        existing = _make_mock_activity(provider="garmin", external_activity_id="sum-abc-001")
        result, mock_db = self._run_item(_RUNNING_RAW, existing_garmin=existing)
        assert result == "skipped"
        mock_db.add.assert_not_called()

    def test_strava_duplicate_garmin_wins(self):
        """
        Strava activity already exists. Matching Garmin activity arrives.
        Garmin wins: existing row updated, provider → "garmin".
        No new row created.
        """
        strava_activity = _make_mock_activity(
            provider="strava",
            external_activity_id="strava-123",
            distance_m=10000,
            avg_hr=145,
            start_time=datetime.fromtimestamp(1740000000, tz=timezone.utc),
        )
        # No prior Garmin idempotency match
        result, mock_db = self._run_item(
            _RUNNING_RAW,
            existing_garmin=None,
            candidates=[strava_activity],
        )
        assert result == "updated"
        # No new row should be added
        mock_db.add.assert_not_called()
        # provider updated to garmin on the strava row
        assert strava_activity.provider == "garmin"

    def test_no_second_row_created_on_strava_duplicate(self):
        """Strava duplicate: only one row exists after ingestion."""
        strava_activity = _make_mock_activity(
            provider="strava",
            external_activity_id="strava-456",
            distance_m=10000,
            avg_hr=145,
            start_time=datetime.fromtimestamp(1740000000, tz=timezone.utc),
        )
        result, mock_db = self._run_item(
            _RUNNING_RAW,
            existing_garmin=None,
            candidates=[strava_activity],
        )
        assert result == "updated"
        mock_db.add.assert_not_called()

    def test_garmin_external_id_set_on_strava_override(self):
        """When Garmin overrides Strava, external_activity_id is set to Garmin's summaryId."""
        strava_activity = _make_mock_activity(
            provider="strava",
            external_activity_id="strava-789",
            distance_m=10000,
            avg_hr=145,
            start_time=datetime.fromtimestamp(1740000000, tz=timezone.utc),
        )
        self._run_item(_RUNNING_RAW, existing_garmin=None, candidates=[strava_activity])
        assert strava_activity.external_activity_id == "sum-abc-001"

    def test_non_matching_candidate_not_overwritten(self):
        """
        A Strava activity that does NOT match (different time/distance)
        must not be overwritten.
        """
        non_match = _make_mock_activity(
            provider="strava",
            external_activity_id="strava-nomatch",
            distance_m=5000,       # different distance
            avg_hr=140,
            start_time=datetime.fromtimestamp(1740000000 + 7200, tz=timezone.utc),  # 2hr later
        )
        result, mock_db = self._run_item(
            _RUNNING_RAW,
            existing_garmin=None,
            candidates=[non_match],
        )
        # Should create a new row, not update the non-matching Strava row
        assert result == "created"
        mock_db.add.assert_called_once()
        assert non_match.provider == "strava"  # unchanged


# ---------------------------------------------------------------------------
# D5.1: Activity field mapping on new Activity creation
# ---------------------------------------------------------------------------

class TestActivityFieldMapping:
    """Verify key fields are correctly mapped from adapted dict to Activity ORM."""

    def test_created_activity_fields(self):
        from tasks.garmin_webhook_tasks import _ingest_activity_item
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        _ingest_activity_item(_RUNNING_RAW, mock_athlete, mock_db)

        added = mock_db.add.call_args[0][0]
        assert added.provider == "garmin"
        assert added.external_activity_id == "sum-abc-001"
        assert added.garmin_activity_id == 5001968355
        assert added.sport == "run"
        assert added.distance_m == 10000  # rounded int
        assert added.avg_hr == 145
        assert added.athlete_id == mock_athlete.id

    def test_distance_stored_as_integer(self):
        """distance_m column is Integer; adapter returns float — task must round."""
        from tasks.garmin_webhook_tasks import _ingest_activity_item
        raw = {**_RUNNING_RAW, "distanceInMeters": 10000.7, "summaryId": "sum-dist-test"}
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        _ingest_activity_item(raw, mock_athlete, mock_db)

        added = mock_db.add.call_args[0][0]
        assert isinstance(added.distance_m, int)
        assert added.distance_m == 10001

    def test_source_set_to_garmin_for_non_manual(self):
        from tasks.garmin_webhook_tasks import _ingest_activity_item
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        _ingest_activity_item(_RUNNING_RAW, mock_athlete, mock_db)

        added = mock_db.add.call_args[0][0]
        assert added.source == "garmin"

    def test_source_set_to_garmin_manual_for_manual_activity(self):
        from tasks.garmin_webhook_tasks import _ingest_activity_item
        raw = {**_RUNNING_RAW, "manual": True, "summaryId": "sum-manual-001"}
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        _ingest_activity_item(raw, mock_athlete, mock_db)

        added = mock_db.add.call_args[0][0]
        assert added.source == "garmin_manual"


# ---------------------------------------------------------------------------
# D5.1: last_garmin_sync update
# ---------------------------------------------------------------------------

class TestLastGarminSyncUpdate:
    """After any successful ingestion run, last_garmin_sync must be set."""

    def test_last_garmin_sync_updated_after_processing(self):
        from tasks.garmin_webhook_tasks import process_garmin_activity_task
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()

        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("tasks.garmin_webhook_tasks._find_athlete_in_db", return_value=mock_athlete):
            process_garmin_activity_task.run(ATHLETE_ID, _RUNNING_RAW)

        # last_garmin_sync must have been assigned a datetime
        assert mock_athlete.last_garmin_sync is not None
        assert isinstance(mock_athlete.last_garmin_sync, datetime)

    def test_last_garmin_sync_updated_even_when_all_skipped(self):
        """Sync timestamp updated even if all items are skipped (e.g. cycling only)."""
        from tasks.garmin_webhook_tasks import process_garmin_activity_task
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()

        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("tasks.garmin_webhook_tasks._find_athlete_in_db", return_value=mock_athlete):
            process_garmin_activity_task.run(ATHLETE_ID, _CYCLING_RAW)

        assert mock_athlete.last_garmin_sync is not None

    def test_unknown_athlete_returns_skipped(self):
        """If athlete not found in DB, task returns skipped (no crash)."""
        from tasks.garmin_webhook_tasks import process_garmin_activity_task
        mock_db = _make_mock_db()

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("tasks.garmin_webhook_tasks._find_athlete_in_db", return_value=None):
            result = process_garmin_activity_task.run(ATHLETE_ID, _RUNNING_RAW)

        assert result["status"] == "skipped"
        assert result["reason"] == "athlete_not_found"

    def test_briefing_refresh_triggered_when_activity_changes(self):
        """Created/updated Garmin activities should dirty + force-refresh home briefing."""
        from tasks.garmin_webhook_tasks import process_garmin_activity_task
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()

        # New activity path: no existing Garmin idempotency hit, no dedup candidates.
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("tasks.garmin_webhook_tasks._find_athlete_in_db", return_value=mock_athlete), \
             patch("services.home_briefing_cache.mark_briefing_dirty") as mock_dirty, \
             patch("tasks.home_briefing_tasks.enqueue_briefing_refresh") as mock_enq:
            process_garmin_activity_task.run(ATHLETE_ID, _RUNNING_RAW)

        mock_dirty.assert_called_once_with(ATHLETE_ID)
        mock_enq.assert_called_once_with(
            ATHLETE_ID,
            force=True,
            allow_circuit_probe=True,
        )

    def test_briefing_refresh_not_triggered_when_all_skipped(self):
        """All-skipped Garmin payloads should not trigger briefing refresh."""
        from tasks.garmin_webhook_tasks import process_garmin_activity_task
        mock_db = _make_mock_db()
        mock_athlete = _make_mock_athlete()

        # CYCLING payload is skipped by _ingest_activity_item
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("tasks.garmin_webhook_tasks._find_athlete_in_db", return_value=mock_athlete), \
             patch("services.home_briefing_cache.mark_briefing_dirty") as mock_dirty, \
             patch("tasks.home_briefing_tasks.enqueue_briefing_refresh") as mock_enq:
            process_garmin_activity_task.run(ATHLETE_ID, _CYCLING_RAW)

        mock_dirty.assert_not_called()
        mock_enq.assert_not_called()


# ---------------------------------------------------------------------------
# D5.2: process_garmin_activity_detail_task — stream ingestion
# ---------------------------------------------------------------------------

_SAMPLE_UNIX = 1512234126

_DETAIL_PAYLOAD = {
    "userId": "garmin-user-1",
    "summaryId": "sum-abc-001",
    "activityId": 5001968355,
    "samples": [
        {
            "startTimeInSeconds": _SAMPLE_UNIX,
            "latitudeInDegree": 51.0532,
            "longitudeInDegree": -114.0688,
            "elevationInMeters": 1049.4,
            "heartRate": 83,
            "speedMetersPerSecond": 2.5,
            "stepsPerMinute": 180,
            "powerInWatts": 250.0,
        },
        {
            "startTimeInSeconds": _SAMPLE_UNIX + 1,
            "latitudeInDegree": 51.0533,
            "longitudeInDegree": -114.0689,
            "elevationInMeters": 1050.0,
            "heartRate": 85,
            "speedMetersPerSecond": 2.6,
            "stepsPerMinute": 182,
            "powerInWatts": 255.0,
        },
    ],
}


class TestStreamIngestionTask:
    """D5.2: process_garmin_activity_detail_task stream ingestion logic."""

    def _make_activity(self):
        activity = MagicMock()
        activity.id = uuid.uuid4()
        activity.garmin_activity_id = 5001968355
        activity.start_time = datetime.fromtimestamp(_SAMPLE_UNIX, tz=timezone.utc)
        activity.stream_fetch_status = "pending"
        return activity

    def _run_task(self, payload, activity=None):
        from tasks.garmin_webhook_tasks import process_garmin_activity_detail_task
        mock_db = _make_mock_db()

        # First query: find Activity by garmin_activity_id
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            activity,  # Activity lookup
            None,      # ActivityStream lookup (no existing stream)
        ]

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db):
            result = process_garmin_activity_detail_task.run(ATHLETE_ID, payload)
        return result, mock_db

    def test_stream_created_for_known_activity(self):
        activity = self._make_activity()
        result, mock_db = self._run_task(_DETAIL_PAYLOAD, activity=activity)

        assert result["status"] == "ok"
        assert result["processed"] == 1
        mock_db.add.assert_called_once()

    def test_stream_data_contains_heartrate(self):
        activity = self._make_activity()
        result, mock_db = self._run_task(_DETAIL_PAYLOAD, activity=activity)

        stream = mock_db.add.call_args[0][0]
        assert "heartrate" in stream.stream_data
        assert stream.stream_data["heartrate"][0] == 83

    def test_stream_data_contains_watts(self):
        activity = self._make_activity()
        result, mock_db = self._run_task(_DETAIL_PAYLOAD, activity=activity)

        stream = mock_db.add.call_args[0][0]
        assert "watts" in stream.stream_data
        assert stream.stream_data["watts"][0] == 250.0

    def test_stream_data_contains_latlng(self):
        activity = self._make_activity()
        result, mock_db = self._run_task(_DETAIL_PAYLOAD, activity=activity)

        stream = mock_db.add.call_args[0][0]
        assert "latlng" in stream.stream_data
        assert stream.stream_data["latlng"][0] == [51.0532, -114.0688]

    def test_stream_source_set_to_garmin(self):
        activity = self._make_activity()
        result, mock_db = self._run_task(_DETAIL_PAYLOAD, activity=activity)

        stream = mock_db.add.call_args[0][0]
        assert stream.source == "garmin"

    def test_stream_fetch_status_set_to_success(self):
        activity = self._make_activity()
        result, mock_db = self._run_task(_DETAIL_PAYLOAD, activity=activity)

        assert activity.stream_fetch_status == "success"

    def test_unknown_garmin_activity_id_is_skipped(self):
        """If no Activity matches the activityId, skip gracefully (no add)."""
        result, mock_db = self._run_task(_DETAIL_PAYLOAD, activity=None)

        assert result["status"] == "ok"
        assert result["processed"] == 0
        mock_db.add.assert_not_called()

    def test_missing_activity_id_in_payload_skipped(self):
        """Payload without activityId is skipped."""
        payload = {k: v for k, v in _DETAIL_PAYLOAD.items() if k != "activityId"}
        result, mock_db = self._run_task(payload, activity=None)

        assert result["processed"] == 0

    def test_list_payload_processes_multiple_detail_items(self):
        """List payload shape: both detail items processed."""
        from tasks.garmin_webhook_tasks import process_garmin_activity_detail_task
        mock_db = _make_mock_db()

        activity_a = self._make_activity()
        activity_b = MagicMock()
        activity_b.id = uuid.uuid4()
        activity_b.garmin_activity_id = 9999000001
        activity_b.start_time = datetime.fromtimestamp(_SAMPLE_UNIX, tz=timezone.utc)
        activity_b.stream_fetch_status = "pending"

        payload_b = {**_DETAIL_PAYLOAD, "activityId": 9999000001}

        # Activity lookups interleaved: a found, no stream; b found, no stream
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            activity_a, None,   # item 1: activity found, no stream
            activity_b, None,   # item 2: activity found, no stream
        ]

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db):
            result = process_garmin_activity_detail_task.run(
                ATHLETE_ID, [_DETAIL_PAYLOAD, payload_b]
            )

        assert result["processed"] == 2
        assert mock_db.add.call_count == 2

    def test_empty_samples_sets_stream_fetch_unavailable(self):
        """No samples in detail → status set to unavailable, no stream row created."""
        activity = self._make_activity()
        payload_no_samples = {**_DETAIL_PAYLOAD, "samples": []}
        result, mock_db = self._run_task(payload_no_samples, activity=activity)

        mock_db.add.assert_not_called()
        assert activity.stream_fetch_status == "unavailable"

    def test_dict_payload_treated_as_single_item(self):
        """Single dict payload processes as one detail item."""
        activity = self._make_activity()
        result, mock_db = self._run_task(_DETAIL_PAYLOAD, activity=activity)

        assert result["processed"] == 1
