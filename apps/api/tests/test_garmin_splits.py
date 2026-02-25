"""
Tests for Garmin ActivitySplit creation (builder note: BUILDER_NOTE_2026-02-25_GARMIN_SPLITS_GAP.md)

9 required contracts:
  1. adapt_activity_detail_laps returns correct split count
  2. adapt_activity_detail_laps computes avg HR from samples (when no per-lap aggregate)
  3. adapt_activity_detail_laps falls back to sample-derived splits when laps missing
  4. adapt_activity_detail_laps returns [] when laps is missing and samples insufficient
  5. _ingest_activity_detail_item creates ActivitySplit rows
  6. _ingest_activity_detail_item is idempotent (re-ingest replaces splits, not appends)
  7. _ingest_activity_detail_item creates splits from samples when no laps in payload
  8. Source contract: no raw Garmin field names in garmin_webhook_tasks.py
"""

import sys
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch, call

import pytest

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)


# ---------------------------------------------------------------------------
# Fixtures — raw payload builders
# ---------------------------------------------------------------------------

def _make_samples(lap_boundaries: List[int]) -> List[Dict[str, Any]]:
    """Build sample dicts across multiple lap windows for testing."""
    samples = []
    for i, lap_start in enumerate(lap_boundaries):
        next_start = lap_boundaries[i + 1] if i + 1 < len(lap_boundaries) else lap_start + 300
        # 3 samples per lap, evenly spaced
        for j in range(3):
            ts = lap_start + j * ((next_start - lap_start) // 3)
            samples.append({
                "startTimeInSeconds": ts,
                "heartRate": 140 + i * 10 + j,   # lap 0: 140-142, lap 1: 150-152
                "stepsPerMinute": 160 + i * 4,
                "speedMetersPerSecond": 3.5 + i * 0.2,
                "elevationInMeters": 100.0,
            })
    return samples


def _make_laps_raw(
    start_times: List[int],
    with_aggregates: bool = False,
) -> List[Dict[str, Any]]:
    """Build raw Garmin lap dicts."""
    laps = []
    for i, ts in enumerate(start_times):
        lap: Dict[str, Any] = {"startTimeInSeconds": ts}
        if with_aggregates:
            lap["totalDistanceInMeters"] = 1609.34
            lap["clockDurationInSeconds"] = 420
            lap["timerDurationInSeconds"] = 418
            lap["averageHeartRateInBeatsPerMinute"] = 145 + i * 5
            lap["maxHeartRateInBeatsPerMinute"] = 165 + i * 5
            lap["averageRunCadenceInStepsPerMinute"] = 168.0
        laps.append(lap)
    return laps


def _make_raw_detail(laps=None, samples=None) -> Dict[str, Any]:
    return {
        "activityId": 12345678,
        "summaryId": "summary-abc",
        "laps": laps,
        "samples": samples or [],
    }


# ===========================================================================
# Test 1 — correct split count
# ===========================================================================
class TestAdaptLapsCount:

    def test_returns_one_split_per_lap(self):
        """2 laps → 2 splits returned."""
        from services.garmin_adapter import adapt_activity_detail_laps

        laps = _make_laps_raw([1000, 2000], with_aggregates=True)
        raw_detail = _make_raw_detail(laps=laps)
        result = adapt_activity_detail_laps(raw_detail, [])

        assert len(result) == 2

    def test_split_numbers_are_1_indexed(self):
        """split_number is 1-indexed (matches Strava convention)."""
        from services.garmin_adapter import adapt_activity_detail_laps

        laps = _make_laps_raw([1000, 2000, 3000], with_aggregates=True)
        raw_detail = _make_raw_detail(laps=laps)
        result = adapt_activity_detail_laps(raw_detail, [])

        assert [s["split_number"] for s in result] == [1, 2, 3]

    def test_laps_sorted_by_start_time(self):
        """Out-of-order laps are sorted before numbering."""
        from services.garmin_adapter import adapt_activity_detail_laps

        # Deliberately reversed order
        laps = _make_laps_raw([2000, 1000], with_aggregates=True)
        raw_detail = _make_raw_detail(laps=laps)
        result = adapt_activity_detail_laps(raw_detail, [])

        # split 1 should correspond to earlier start time (1000)
        assert result[0]["split_number"] == 1
        assert result[1]["split_number"] == 2


# ===========================================================================
# Test 2 — avg HR computed from samples when no per-lap aggregate
# ===========================================================================
class TestAdaptLapsHRFromSamples:

    def test_avg_hr_computed_from_samples_in_lap_window(self):
        """When lap has no averageHeartRateInBeatsPerMinute, computes from samples."""
        from services.garmin_adapter import adapt_activity_detail_laps

        # Lap 1: samples at t=1000, 1100, 1200 with HR 140, 145, 150
        # Lap 2: samples at t=2000, 2100, 2200 with HR 160, 165, 170
        lap1_start, lap2_start = 1000, 2000
        samples = [
            {"startTimeInSeconds": 1000, "heartRate": 140, "stepsPerMinute": 165},
            {"startTimeInSeconds": 1100, "heartRate": 145, "stepsPerMinute": 166},
            {"startTimeInSeconds": 1200, "heartRate": 150, "stepsPerMinute": 167},
            {"startTimeInSeconds": 2000, "heartRate": 160, "stepsPerMinute": 170},
            {"startTimeInSeconds": 2100, "heartRate": 165, "stepsPerMinute": 171},
            {"startTimeInSeconds": 2200, "heartRate": 170, "stepsPerMinute": 172},
        ]
        laps = _make_laps_raw([lap1_start, lap2_start], with_aggregates=False)
        raw_detail = _make_raw_detail(laps=laps, samples=samples)
        result = adapt_activity_detail_laps(raw_detail, samples)

        assert result[0]["average_heartrate"] == round((140 + 145 + 150) / 3)
        assert result[1]["average_heartrate"] == round((160 + 165 + 170) / 3)

    def test_max_hr_computed_from_samples_in_lap_window(self):
        """max_heartrate is the sample maximum within the lap window."""
        from services.garmin_adapter import adapt_activity_detail_laps

        samples = [
            {"startTimeInSeconds": 1000, "heartRate": 140},
            {"startTimeInSeconds": 1100, "heartRate": 175},  # peak in lap 1
            {"startTimeInSeconds": 2000, "heartRate": 160},
        ]
        laps = _make_laps_raw([1000, 2000], with_aggregates=False)
        raw_detail = _make_raw_detail(laps=laps, samples=samples)
        result = adapt_activity_detail_laps(raw_detail, samples)

        assert result[0]["max_heartrate"] == 175

    def test_per_lap_aggregate_hr_takes_precedence_over_samples(self):
        """Per-lap averageHeartRateInBeatsPerMinute overrides sample computation."""
        from services.garmin_adapter import adapt_activity_detail_laps

        samples = [
            {"startTimeInSeconds": 1000, "heartRate": 140},
            {"startTimeInSeconds": 1100, "heartRate": 145},
        ]
        laps = _make_laps_raw([1000], with_aggregates=True)
        laps[0]["averageHeartRateInBeatsPerMinute"] = 999  # explicit per-lap value
        raw_detail = _make_raw_detail(laps=laps, samples=samples)
        result = adapt_activity_detail_laps(raw_detail, samples)

        assert result[0]["average_heartrate"] == 999

    def test_avg_cadence_computed_from_samples_when_no_aggregate(self):
        """average_cadence computed from stepsPerMinute samples when absent from lap."""
        from services.garmin_adapter import adapt_activity_detail_laps

        samples = [
            {"startTimeInSeconds": 1000, "stepsPerMinute": 164},
            {"startTimeInSeconds": 1100, "stepsPerMinute": 168},
            {"startTimeInSeconds": 1200, "stepsPerMinute": 172},
        ]
        laps = _make_laps_raw([1000], with_aggregates=False)
        raw_detail = _make_raw_detail(laps=laps, samples=samples)
        result = adapt_activity_detail_laps(raw_detail, samples)

        expected = round((164 + 168 + 172) / 3, 1)
        assert result[0]["average_cadence"] == pytest.approx(expected, abs=0.5)

    def test_per_lap_aggregate_fields_mapped_correctly(self):
        """When per-lap aggregates are present, all fields are mapped correctly."""
        from services.garmin_adapter import adapt_activity_detail_laps

        laps = _make_laps_raw([1000], with_aggregates=True)
        raw_detail = _make_raw_detail(laps=laps)
        result = adapt_activity_detail_laps(raw_detail, [])

        split = result[0]
        assert split["distance"] == pytest.approx(1609.34, abs=0.01)
        assert split["elapsed_time"] == 420
        assert split["moving_time"] == 418
        assert split["average_heartrate"] == 145
        assert split["max_heartrate"] == 165
        assert split["average_cadence"] == 168.0
        assert split["gap_seconds_per_mile"] is None  # Not in Garmin JSON API


# ===========================================================================
# Test 3 — fallback when laps missing
# ===========================================================================
class TestAdaptLapsFallbackWhenNoLaps:

    def test_derives_splits_from_samples_when_laps_key_absent(self):
        """No laps + rich samples -> derive distance-based splits."""
        from services.garmin_adapter import adapt_activity_detail_laps

        # 4 x 600s at 3.0 m/s = 7200m total (~4.47mi): expect >= 4 splits.
        samples = [
            {"startTimeInSeconds": 1000, "speedMetersPerSecond": 3.0, "heartRate": 140, "stepsPerMinute": 165},
            {"startTimeInSeconds": 1600, "speedMetersPerSecond": 3.0, "heartRate": 142, "stepsPerMinute": 166},
            {"startTimeInSeconds": 2200, "speedMetersPerSecond": 3.0, "heartRate": 145, "stepsPerMinute": 167},
            {"startTimeInSeconds": 2800, "speedMetersPerSecond": 3.0, "heartRate": 148, "stepsPerMinute": 168},
            {"startTimeInSeconds": 3400, "speedMetersPerSecond": 3.0, "heartRate": 150, "stepsPerMinute": 169},
        ]
        raw_detail = {"activityId": 123, "samples": samples}  # no laps key
        result = adapt_activity_detail_laps(raw_detail, samples)

        assert len(result) >= 4
        assert result[0]["split_number"] == 1
        assert result[0]["distance"] == pytest.approx(1609.34, abs=5.0)
        assert result[0]["gap_seconds_per_mile"] is None

    def test_derives_splits_when_laps_is_none(self):
        """laps=None + rich samples -> derive distance-based splits."""
        from services.garmin_adapter import adapt_activity_detail_laps

        samples = _make_samples([1000, 1300, 1600, 1900, 2200, 2500])
        # Ensure speed exists for integration
        for s in samples:
            s["speedMetersPerSecond"] = s.get("speedMetersPerSecond", 3.2)
        raw_detail = _make_raw_detail(laps=None, samples=samples)
        result = adapt_activity_detail_laps(raw_detail, samples)

        assert len(result) >= 1
        assert all(split["split_number"] >= 1 for split in result)


# ===========================================================================
# Test 4 — empty when laps missing and samples insufficient
# ===========================================================================
class TestAdaptLapsEmptyWhenInsufficientSamples:

    def test_returns_empty_list_when_laps_key_absent(self):
        """No laps and no samples -> returns []."""
        from services.garmin_adapter import adapt_activity_detail_laps

        raw_detail = {"activityId": 123, "samples": []}
        result = adapt_activity_detail_laps(raw_detail, [])

        assert result == []

    def test_returns_empty_list_when_laps_is_none(self):
        """laps=None and no samples -> returns []."""
        from services.garmin_adapter import adapt_activity_detail_laps

        raw_detail = _make_raw_detail(laps=None)
        result = adapt_activity_detail_laps(raw_detail, [])

        assert result == []


    def test_returns_empty_list_when_laps_empty(self):
        """laps=[] and no samples -> returns []."""
        from services.garmin_adapter import adapt_activity_detail_laps

        raw_detail = _make_raw_detail(laps=[])
        result = adapt_activity_detail_laps(raw_detail, [])

        assert result == []

    def test_skips_laps_missing_start_time(self):
        """Laps without startTimeInSeconds are silently skipped."""
        from services.garmin_adapter import adapt_activity_detail_laps

        laps = [
            {"totalDistanceInMeters": 500},           # no startTimeInSeconds
            {"startTimeInSeconds": 2000, "totalDistanceInMeters": 1609.34},
        ]
        raw_detail = _make_raw_detail(laps=laps)
        result = adapt_activity_detail_laps(raw_detail, [])

        assert len(result) == 1
        assert result[0]["split_number"] == 1


# ===========================================================================
# Test 5 — integration: ActivitySplit rows created
# ===========================================================================
class TestIngestActivityDetailCreatesSplits:

    def test_creates_activity_splits_when_laps_present(self):
        """_ingest_activity_detail_item creates ActivitySplit rows for each lap."""
        from tasks.garmin_webhook_tasks import _ingest_activity_detail_item
        from models import ActivitySplit

        mock_activity = MagicMock()
        mock_activity.id = uuid.uuid4()
        mock_activity.start_time = datetime(2026, 2, 25, 8, 0, 0, tzinfo=timezone.utc)
        mock_activity.stream_fetch_status = None
        mock_activity.garmin_activity_id = 12345678

        mock_db = MagicMock()

        def query_side(model):
            q = MagicMock()
            if model is __import__('models', fromlist=['Activity']).Activity:
                q.filter.return_value.first.return_value = mock_activity
            elif model is __import__('models', fromlist=['ActivityStream']).ActivityStream:
                q.filter.return_value.first.return_value = None
            elif model is ActivitySplit:
                q.filter.return_value.delete.return_value = 0
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side

        laps = _make_laps_raw([1000, 2000], with_aggregates=True)
        raw_item = _make_raw_detail(laps=laps, samples=[])

        added_objects = []
        mock_db.add.side_effect = added_objects.append

        result = _ingest_activity_detail_item(raw_item, "athlete-id", mock_db)

        assert result is True
        split_adds = [o for o in added_objects if isinstance(o, ActivitySplit)]
        assert len(split_adds) == 2
        assert split_adds[0].split_number == 1
        assert split_adds[1].split_number == 2


# ===========================================================================
# Test 6 — idempotency
# ===========================================================================
class TestIngestActivityDetailIdempotentSplits:

    def test_existing_splits_deleted_before_recreating(self):
        """Re-ingestion deletes old ActivitySplit rows then creates new ones."""
        from tasks.garmin_webhook_tasks import _ingest_activity_detail_item
        from models import ActivitySplit

        mock_activity = MagicMock()
        mock_activity.id = uuid.uuid4()
        mock_activity.start_time = datetime(2026, 2, 25, 8, 0, 0, tzinfo=timezone.utc)
        mock_activity.stream_fetch_status = None
        mock_activity.garmin_activity_id = 12345678

        delete_called = {"n": 0}
        mock_db = MagicMock()

        def query_side(model):
            q = MagicMock()
            if model is __import__('models', fromlist=['Activity']).Activity:
                q.filter.return_value.first.return_value = mock_activity
            elif model is __import__('models', fromlist=['ActivityStream']).ActivityStream:
                q.filter.return_value.first.return_value = None
            elif model is ActivitySplit:
                def _delete(**kwargs):
                    delete_called["n"] += 1
                    return 2  # pretend 2 old splits deleted
                q.filter.return_value.delete.side_effect = _delete
            return q

        mock_db.query.side_effect = query_side

        laps = _make_laps_raw([1000, 2000], with_aggregates=True)
        raw_item = _make_raw_detail(laps=laps, samples=[])
        mock_db.add = MagicMock()

        _ingest_activity_detail_item(raw_item, "athlete-id", mock_db)

        # Delete must be called once (for the ActivitySplit query)
        assert delete_called["n"] == 1


# ===========================================================================
# Test 7 — sample fallback when no laps
# ===========================================================================
class TestIngestActivityDetailSampleFallbackWhenNoLaps:

    def test_splits_created_from_samples_when_payload_has_no_laps(self):
        """When payload has no laps but has samples, ActivitySplit rows are created."""
        from tasks.garmin_webhook_tasks import _ingest_activity_detail_item
        from models import ActivitySplit

        mock_activity = MagicMock()
        mock_activity.id = uuid.uuid4()
        mock_activity.start_time = datetime(2026, 2, 25, 8, 0, 0, tzinfo=timezone.utc)
        mock_activity.stream_fetch_status = None
        mock_activity.garmin_activity_id = 12345678

        mock_db = MagicMock()

        def query_side(model):
            q = MagicMock()
            if model is __import__('models', fromlist=['Activity']).Activity:
                q.filter.return_value.first.return_value = mock_activity
            elif model is __import__('models', fromlist=['ActivityStream']).ActivityStream:
                q.filter.return_value.first.return_value = None
            elif model is ActivitySplit:
                q.filter.return_value.delete.return_value = 0
            return q

        mock_db.query.side_effect = query_side

        samples = [
            {"startTimeInSeconds": 1000, "speedMetersPerSecond": 3.0, "heartRate": 140, "stepsPerMinute": 165},
            {"startTimeInSeconds": 1600, "speedMetersPerSecond": 3.0, "heartRate": 142, "stepsPerMinute": 166},
            {"startTimeInSeconds": 2200, "speedMetersPerSecond": 3.0, "heartRate": 145, "stepsPerMinute": 167},
            {"startTimeInSeconds": 2800, "speedMetersPerSecond": 3.0, "heartRate": 148, "stepsPerMinute": 168},
            {"startTimeInSeconds": 3400, "speedMetersPerSecond": 3.0, "heartRate": 150, "stepsPerMinute": 169},
        ]
        raw_item = _make_raw_detail(laps=None, samples=samples)  # no laps, but rich samples
        added_objects = []
        mock_db.add.side_effect = added_objects.append

        result = _ingest_activity_detail_item(raw_item, "athlete-id", mock_db)

        split_adds = [o for o in added_objects if isinstance(o, ActivitySplit)]
        assert result is True
        assert len(split_adds) >= 1

    def test_no_error_raised_when_laps_absent(self):
        """No exception raised when 'laps' key is absent from payload."""
        from tasks.garmin_webhook_tasks import _ingest_activity_detail_item

        mock_activity = MagicMock()
        mock_activity.id = uuid.uuid4()
        mock_activity.start_time = datetime(2026, 2, 25, 8, 0, 0, tzinfo=timezone.utc)
        mock_activity.stream_fetch_status = None
        mock_activity.garmin_activity_id = 99999

        mock_db = MagicMock()

        def query_side(model):
            q = MagicMock()
            if model is __import__('models', fromlist=['Activity']).Activity:
                q.filter.return_value.first.return_value = mock_activity
            elif model is __import__('models', fromlist=['ActivityStream']).ActivityStream:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = query_side
        mock_db.add = MagicMock()

        # No laps key — should not raise
        raw_item = {"activityId": 99999, "summaryId": "s1", "samples": []}
        result = _ingest_activity_detail_item(raw_item, "athlete-id", mock_db)
        assert result is True


# ===========================================================================
# Test 8 — source contract: no raw Garmin field names in task module
# ===========================================================================
class TestGarminSourceContract:

    GARMIN_RAW_FIELDS = [
        "startTimeInSeconds",
        "totalDistanceInMeters",
        "clockDurationInSeconds",
        "timerDurationInSeconds",
        "averageHeartRateInBeatsPerMinute",
        "maxHeartRateInBeatsPerMinute",
        "averageRunCadenceInStepsPerMinute",
        "stepsPerMinute",
        "heartRate",
    ]

    def test_garmin_field_names_not_in_webhook_tasks_module(self):
        """
        Raw Garmin field names must not appear in garmin_webhook_tasks.py.
        All field translation belongs in garmin_adapter.py (source contract).
        """
        task_module_path = os.path.join(
            _API_ROOT, "tasks", "garmin_webhook_tasks.py"
        )
        with open(task_module_path, "r") as f:
            source = f.read()

        violations = [
            field for field in self.GARMIN_RAW_FIELDS
            if field in source
        ]
        assert violations == [], (
            f"Raw Garmin field names found in garmin_webhook_tasks.py "
            f"(source contract violation): {violations}"
        )
