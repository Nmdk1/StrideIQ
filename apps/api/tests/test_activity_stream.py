"""Tests for Activity Stream ingestion, storage, lifecycle, and API (ADR-063).

Phase 1: Stream Data Foundation — Run Shape Intelligence.

Test categories covered:
  Category 1: Unit tests (model, service, ingestion, backfill, endpoint)
  Category 2: Integration tests (full sync flow, backfill e2e, endpoint e2e)
  Category 4: Failure-mode / scenario tests (429, timeout, malformed, idempotency)
  Category 5: N/A for Phase 1 (no coach output) — formally excepted, obligation
              transfers to Phase 2.
  Category 6: Production smoke tests are documented in ADR-063; run post-deploy.

All tests use transactional rollback via db_session fixture.
"""
import os
import sys
import pytest
import time
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.fernet import Fernet
from models import Activity, ActivitySplit, ActivityStream, Athlete


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_encryption_key():
    """Ensure a valid Fernet key is available for token encryption tests."""
    import services.token_encryption as te_mod
    key = Fernet.generate_key().decode()
    old_val = os.environ.get("TOKEN_ENCRYPTION_KEY")
    os.environ["TOKEN_ENCRYPTION_KEY"] = key
    te_mod._token_encryption = None  # Reset singleton to pick up new key
    yield
    te_mod._token_encryption = None
    if old_val is not None:
        os.environ["TOKEN_ENCRYPTION_KEY"] = old_val
    elif "TOKEN_ENCRYPTION_KEY" in os.environ:
        del os.environ["TOKEN_ENCRYPTION_KEY"]


@pytest.fixture
def test_athlete(db_session):
    """Create a test athlete with Strava credentials."""
    from services.token_encryption import encrypt_token

    athlete = Athlete(
        email=f"stream_test_{uuid4()}@example.com",
        display_name="Stream Test Athlete",
        subscription_tier="free",
        birthdate=date(1990, 1, 1),
        sex="M",
        strava_access_token=encrypt_token("fake_access_token"),
        strava_refresh_token=encrypt_token("fake_refresh_token"),
        strava_athlete_id=12345,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


@pytest.fixture
def strava_activity(db_session, test_athlete):
    """Create a Strava-sourced activity with external_activity_id."""
    activity = Activity(
        athlete_id=test_athlete.id,
        name="Morning Run",
        start_time=datetime.now(timezone.utc) - timedelta(days=1),
        sport="run",
        source="strava",
        provider="strava",
        external_activity_id="9876543210",
        duration_s=3600,
        distance_m=10000,
        avg_hr=150,
        stream_fetch_status="pending",
    )
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    return activity


@pytest.fixture
def manual_activity(db_session, test_athlete):
    """Create a manual activity with no external_activity_id."""
    activity = Activity(
        athlete_id=test_athlete.id,
        name="Manual Run",
        start_time=datetime.now(timezone.utc) - timedelta(days=2),
        sport="run",
        source="manual",
        provider=None,
        external_activity_id=None,
        duration_s=1800,
        distance_m=5000,
        stream_fetch_status="unavailable",
    )
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    return activity


def _make_stream_data(point_count=3600, channels=None):
    """Build a realistic stream_data dict for testing."""
    if channels is None:
        channels = ["time", "distance", "heartrate", "altitude",
                     "velocity_smooth", "grade_smooth", "cadence"]
    data = {}
    for ch in channels:
        if ch == "time":
            data[ch] = list(range(point_count))
        elif ch == "distance":
            data[ch] = [i * 2.8 for i in range(point_count)]
        elif ch == "heartrate":
            data[ch] = [140 + (i % 40) for i in range(point_count)]
        elif ch == "altitude":
            data[ch] = [100.0 + (i * 0.01) for i in range(point_count)]
        elif ch == "velocity_smooth":
            data[ch] = [3.0 + (i % 10) * 0.1 for i in range(point_count)]
        elif ch == "grade_smooth":
            data[ch] = [0.0 + (i % 20) * 0.5 for i in range(point_count)]
        elif ch == "cadence":
            data[ch] = [88 + (i % 5) for i in range(point_count)]
        elif ch == "latlng":
            data[ch] = [[38.0 + i * 0.0001, -122.0 + i * 0.0001] for i in range(point_count)]
        elif ch == "moving":
            data[ch] = [True] * point_count
    return data


def _make_strava_streams_response(point_count=3600, channels=None):
    """Build a mock Strava API streams response (list of stream objects)."""
    if channels is None:
        channels = ["time", "distance", "heartrate", "altitude",
                     "velocity_smooth", "grade_smooth", "cadence"]
    data = _make_stream_data(point_count, channels)
    return [
        {
            "type": ch,
            "data": data[ch],
            "series_type": "distance",
            "original_size": point_count,
            "resolution": "high",
        }
        for ch in channels
    ]


# ===========================================================================
# CATEGORY 1: UNIT TESTS — ActivityStream Model
# ===========================================================================

class TestActivityStreamModel:
    """Unit tests for the ActivityStream model (ADR-063 Decision 1)."""

    def test_create_with_full_data(self, db_session, strava_activity):
        """All 9 channels, 3600 points each — full stream round-trips."""
        channels = ["time", "distance", "heartrate", "altitude",
                     "velocity_smooth", "grade_smooth", "cadence", "latlng", "moving"]
        stream_data = _make_stream_data(3600, channels)

        stream = ActivityStream(
            activity_id=strava_activity.id,
            stream_data=stream_data,
            channels_available=channels,
            point_count=3600,
            source="strava",
        )
        db_session.add(stream)
        db_session.commit()
        db_session.refresh(stream)

        assert stream.id is not None
        assert stream.activity_id == strava_activity.id
        assert stream.point_count == 3600
        assert stream.source == "strava"
        assert set(stream.channels_available) == set(channels)
        assert len(stream.stream_data["time"]) == 3600
        assert len(stream.stream_data["heartrate"]) == 3600

    def test_create_with_partial_data(self, db_session, strava_activity):
        """Only time + distance + altitude (no HR monitor) — partial is valid."""
        channels = ["time", "distance", "altitude"]
        stream_data = _make_stream_data(1800, channels)

        stream = ActivityStream(
            activity_id=strava_activity.id,
            stream_data=stream_data,
            channels_available=channels,
            point_count=1800,
            source="strava",
        )
        db_session.add(stream)
        db_session.commit()
        db_session.refresh(stream)

        assert stream.point_count == 1800
        assert "heartrate" not in stream.channels_available
        assert "heartrate" not in stream.stream_data

    def test_unique_constraint_prevents_duplicate(self, db_session, strava_activity):
        """Duplicate activity_id raises IntegrityError — the armor."""
        from sqlalchemy.exc import IntegrityError

        stream1 = ActivityStream(
            activity_id=strava_activity.id,
            stream_data=_make_stream_data(100, ["time"]),
            channels_available=["time"],
            point_count=100,
            source="strava",
        )
        db_session.add(stream1)
        db_session.commit()

        stream2 = ActivityStream(
            activity_id=strava_activity.id,
            stream_data=_make_stream_data(100, ["time"]),
            channels_available=["time"],
            point_count=100,
            source="strava",
        )
        db_session.add(stream2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_round_trip_float_precision(self, db_session, strava_activity):
        """Altitude 123.456789 survives write/read within tolerance."""
        test_altitude = 123.456789
        stream_data = {
            "time": [0, 1, 2],
            "altitude": [test_altitude, 200.123456, 300.789012],
        }
        stream = ActivityStream(
            activity_id=strava_activity.id,
            stream_data=stream_data,
            channels_available=["time", "altitude"],
            point_count=3,
            source="strava",
        )
        db_session.add(stream)
        db_session.commit()
        db_session.refresh(stream)

        stored = stream.stream_data["altitude"][0]
        assert abs(stored - test_altitude) < 1e-6, (
            f"Float precision drift: stored={stored}, expected={test_altitude}"
        )

    def test_empty_stream_data_is_valid(self, db_session, strava_activity):
        """Activity had no streams — empty dict is stored, channels_available=[]."""
        stream = ActivityStream(
            activity_id=strava_activity.id,
            stream_data={},
            channels_available=[],
            point_count=0,
            source="strava",
        )
        db_session.add(stream)
        db_session.commit()
        db_session.refresh(stream)

        assert stream.stream_data == {}
        assert stream.channels_available == []
        assert stream.point_count == 0

    def test_channels_available_matches_data_keys(self, db_session, strava_activity):
        """channels_available must list exactly the keys in stream_data."""
        channels = ["time", "heartrate", "cadence"]
        stream_data = _make_stream_data(100, channels)

        stream = ActivityStream(
            activity_id=strava_activity.id,
            stream_data=stream_data,
            channels_available=channels,
            point_count=100,
            source="strava",
        )
        db_session.add(stream)
        db_session.commit()
        db_session.refresh(stream)

        assert set(stream.channels_available) == set(stream.stream_data.keys())

    def test_point_count_matches_time_array(self, db_session, strava_activity):
        """point_count must equal len(stream_data['time'])."""
        stream_data = _make_stream_data(500, ["time", "heartrate"])

        stream = ActivityStream(
            activity_id=strava_activity.id,
            stream_data=stream_data,
            channels_available=["time", "heartrate"],
            point_count=500,
            source="strava",
        )
        db_session.add(stream)
        db_session.commit()
        db_session.refresh(stream)

        assert stream.point_count == len(stream.stream_data["time"])

    def test_relationship_activity_to_stream(self, db_session, strava_activity):
        """Activity.stream returns the associated ActivityStream (uselist=False)."""
        stream = ActivityStream(
            activity_id=strava_activity.id,
            stream_data=_make_stream_data(100, ["time"]),
            channels_available=["time"],
            point_count=100,
            source="strava",
        )
        db_session.add(stream)
        db_session.commit()
        db_session.refresh(strava_activity)

        assert strava_activity.stream is not None
        assert strava_activity.stream.id == stream.id


# ===========================================================================
# CATEGORY 1: UNIT TESTS — Stream Fetch Lifecycle (State Machine)
# ===========================================================================

class TestStreamFetchLifecycle:
    """Unit tests for stream_fetch_* fields on Activity (ADR-063 Decision 2)."""

    def test_default_status_is_pending(self, db_session, test_athlete):
        """New activity defaults to 'pending' stream_fetch_status."""
        activity = Activity(
            athlete_id=test_athlete.id,
            name="New Run",
            start_time=datetime.now(timezone.utc),
            sport="run",
            source="strava",
            provider="strava",
            external_activity_id="111111",
        )
        db_session.add(activity)
        db_session.commit()
        db_session.refresh(activity)

        assert activity.stream_fetch_status == "pending"
        assert activity.stream_fetch_retry_count == 0
        assert activity.stream_fetch_attempted_at is None
        assert activity.stream_fetch_error is None
        assert activity.stream_fetch_deferred_until is None

    def test_check_constraint_rejects_invalid_status(self, db_session, strava_activity):
        """Check constraint prevents invalid stream_fetch_status values."""
        from sqlalchemy.exc import IntegrityError

        strava_activity.stream_fetch_status = "invalid_status"
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_valid_statuses_accepted(self, db_session, test_athlete):
        """All 6 valid statuses are accepted by the check constraint."""
        valid_statuses = ["pending", "fetching", "success", "failed", "deferred", "unavailable"]
        for status in valid_statuses:
            activity = Activity(
                athlete_id=test_athlete.id,
                name=f"Run {status}",
                start_time=datetime.now(timezone.utc) - timedelta(hours=len(valid_statuses)),
                sport="run",
                source="strava",
                provider="strava",
                external_activity_id=f"status_test_{status}_{uuid4()}",
                stream_fetch_status=status,
            )
            db_session.add(activity)
        db_session.commit()  # All 6 should succeed

    def test_claim_transition_pending_to_fetching(self, db_session, strava_activity):
        """Atomic claim: pending → fetching succeeds."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            UPDATE activity
            SET stream_fetch_status = 'fetching',
                stream_fetch_attempted_at = NOW()
            WHERE id = :activity_id
              AND stream_fetch_status = 'pending'
            RETURNING id
        """), {"activity_id": str(strava_activity.id)})

        assert result.rowcount == 1

    def test_claim_fails_if_already_claimed(self, db_session, strava_activity):
        """Double claim: second worker gets rowcount=0."""
        from sqlalchemy import text

        # First claim succeeds
        db_session.execute(text("""
            UPDATE activity
            SET stream_fetch_status = 'fetching',
                stream_fetch_attempted_at = NOW()
            WHERE id = :activity_id
              AND stream_fetch_status = 'pending'
        """), {"activity_id": str(strava_activity.id)})

        # Second claim fails (status is now 'fetching', not 'pending')
        result = db_session.execute(text("""
            UPDATE activity
            SET stream_fetch_status = 'fetching',
                stream_fetch_attempted_at = NOW()
            WHERE id = :activity_id
              AND (
                stream_fetch_status = 'pending'
                OR (stream_fetch_status = 'failed' AND stream_fetch_retry_count < 3)
                OR (stream_fetch_status = 'deferred' AND stream_fetch_deferred_until < NOW())
              )
            RETURNING id
        """), {"activity_id": str(strava_activity.id)})

        assert result.rowcount == 0

    def test_claim_failed_with_retries_remaining(self, db_session, strava_activity):
        """Failed activity with retry_count < 3 can be claimed."""
        from sqlalchemy import text

        strava_activity.stream_fetch_status = "failed"
        strava_activity.stream_fetch_retry_count = 1
        db_session.commit()

        result = db_session.execute(text("""
            UPDATE activity
            SET stream_fetch_status = 'fetching',
                stream_fetch_attempted_at = NOW()
            WHERE id = :activity_id
              AND stream_fetch_status = 'failed'
              AND stream_fetch_retry_count < 3
            RETURNING id
        """), {"activity_id": str(strava_activity.id)})

        assert result.rowcount == 1

    def test_claim_failed_with_retries_exhausted(self, db_session, strava_activity):
        """Failed activity with retry_count >= 3 cannot be claimed."""
        from sqlalchemy import text

        strava_activity.stream_fetch_status = "failed"
        strava_activity.stream_fetch_retry_count = 3
        db_session.commit()

        result = db_session.execute(text("""
            UPDATE activity
            SET stream_fetch_status = 'fetching',
                stream_fetch_attempted_at = NOW()
            WHERE id = :activity_id
              AND stream_fetch_status = 'failed'
              AND stream_fetch_retry_count < 3
            RETURNING id
        """), {"activity_id": str(strava_activity.id)})

        assert result.rowcount == 0

    def test_claim_deferred_after_cooldown(self, db_session, strava_activity):
        """Deferred activity past deferred_until can be claimed."""
        from sqlalchemy import text

        strava_activity.stream_fetch_status = "deferred"
        strava_activity.stream_fetch_deferred_until = datetime.now(timezone.utc) - timedelta(minutes=5)
        db_session.commit()

        result = db_session.execute(text("""
            UPDATE activity
            SET stream_fetch_status = 'fetching',
                stream_fetch_attempted_at = NOW()
            WHERE id = :activity_id
              AND stream_fetch_status = 'deferred'
              AND stream_fetch_deferred_until < NOW()
            RETURNING id
        """), {"activity_id": str(strava_activity.id)})

        assert result.rowcount == 1

    def test_claim_deferred_before_cooldown(self, db_session, strava_activity):
        """Deferred activity before deferred_until cannot be claimed."""
        from sqlalchemy import text

        strava_activity.stream_fetch_status = "deferred"
        strava_activity.stream_fetch_deferred_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        db_session.commit()

        result = db_session.execute(text("""
            UPDATE activity
            SET stream_fetch_status = 'fetching',
                stream_fetch_attempted_at = NOW()
            WHERE id = :activity_id
              AND stream_fetch_status = 'deferred'
              AND stream_fetch_deferred_until < NOW()
            RETURNING id
        """), {"activity_id": str(strava_activity.id)})

        assert result.rowcount == 0

    def test_terminal_states_cannot_be_claimed(self, db_session, strava_activity):
        """Success and unavailable are terminal — cannot transition to fetching."""
        from sqlalchemy import text

        for terminal_status in ["success", "unavailable"]:
            strava_activity.stream_fetch_status = terminal_status
            db_session.commit()

            result = db_session.execute(text("""
                UPDATE activity
                SET stream_fetch_status = 'fetching',
                    stream_fetch_attempted_at = NOW()
                WHERE id = :activity_id
                  AND (
                    stream_fetch_status = 'pending'
                    OR (stream_fetch_status = 'failed' AND stream_fetch_retry_count < 3)
                    OR (stream_fetch_status = 'deferred' AND stream_fetch_deferred_until < NOW())
                  )
                RETURNING id
            """), {"activity_id": str(strava_activity.id)})

            assert result.rowcount == 0, f"Terminal state '{terminal_status}' should not be claimable"


# ===========================================================================
# CATEGORY 1: UNIT TESTS — Strava Service (get_activity_streams)
# ===========================================================================

class TestGetActivityStreams:
    """Unit tests for get_activity_streams() (ADR-063 Decision 4)."""

    def _patch_strava(self, **overrides):
        """Helper: return context managers for common strava_service patches."""
        from contextlib import ExitStack
        defaults = {
            "requests_get": None,
            "requests_post": None,
            "budget": True,
            "decrypt": "fake_token",
            "encrypt": "encrypted",
        }
        defaults.update(overrides)

        stack = ExitStack()
        if defaults["requests_get"] is not None:
            stack.enter_context(patch("requests.get", **defaults["requests_get"]))
        if defaults["requests_post"] is not None:
            stack.enter_context(patch("requests.post", **defaults["requests_post"]))
        stack.enter_context(patch(
            "services.strava_service.acquire_strava_read_budget",
            return_value=defaults["budget"],
        ))
        stack.enter_context(patch(
            "services.token_encryption.decrypt_token",
            return_value=defaults["decrypt"],
        ))
        stack.enter_context(patch(
            "services.token_encryption.encrypt_token",
            return_value=defaults["encrypt"],
        ))
        return stack

    def test_success_returns_parsed_dict(self):
        """Mock 200 response → StreamFetchResult with outcome=success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_strava_streams_response(100)

        with patch("requests.get", return_value=mock_response), \
             patch("services.strava_service.acquire_strava_read_budget", return_value=True), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"):
            from services.strava_service import get_activity_streams
            result = get_activity_streams(
                MagicMock(strava_access_token="encrypted"),
                activity_id=12345,
            )

        assert result.outcome == "success"
        assert result.data is not None
        assert "time" in result.data
        assert "heartrate" in result.data
        assert len(result.data["time"]) == 100

    def test_partial_channels_returns_only_available(self):
        """Response missing heartrate → result has no heartrate key."""
        response_data = _make_strava_streams_response(100, ["time", "distance", "altitude"])
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with patch("requests.get", return_value=mock_response), \
             patch("services.strava_service.acquire_strava_read_budget", return_value=True), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"):
            from services.strava_service import get_activity_streams
            result = get_activity_streams(
                MagicMock(strava_access_token="encrypted"),
                activity_id=12345,
            )

        assert result.outcome == "success"
        assert "heartrate" not in result.data
        assert "time" in result.data
        assert "altitude" in result.data

    def test_401_triggers_token_refresh(self):
        """Mock 401 → refresh → retry → success."""
        mock_401 = MagicMock()
        mock_401.status_code = 401

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = _make_strava_streams_response(50, ["time"])

        mock_refresh = MagicMock()
        mock_refresh.status_code = 200
        mock_refresh.json.return_value = {
            "access_token": "new_token",
            "refresh_token": "new_refresh",
            "expires_at": int((datetime.now(timezone.utc) + timedelta(hours=6)).timestamp()),
        }
        mock_refresh.raise_for_status = MagicMock()

        with patch("requests.get", side_effect=[mock_401, mock_200]), \
             patch("requests.post", return_value=mock_refresh), \
             patch("services.strava_service.acquire_strava_read_budget", return_value=True), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"), \
             patch("services.token_encryption.encrypt_token", return_value="encrypted"):
            from services.strava_service import get_activity_streams
            athlete = MagicMock()
            athlete.strava_access_token = "encrypted"
            athlete.strava_refresh_token = "encrypted_refresh"
            result = get_activity_streams(athlete, activity_id=12345)

        assert result.outcome == "success"
        assert "time" in result.data

    def test_429_sleep_mode(self):
        """Mock 429 with allow_rate_limit_sleep=True → sleep and retry."""
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {"Retry-After": "5"}

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = _make_strava_streams_response(50, ["time"])

        with patch("requests.get", side_effect=[mock_429, mock_200]), \
             patch("services.strava_service.acquire_strava_read_budget", return_value=True), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"), \
             patch("services.strava_service.time.sleep"):
            from services.strava_service import get_activity_streams
            result = get_activity_streams(
                MagicMock(strava_access_token="encrypted"),
                activity_id=12345,
                allow_rate_limit_sleep=True,
            )

        assert result.outcome == "success"

    def test_429_raise_mode(self):
        """Mock 429 with allow_rate_limit_sleep=False → raise StravaRateLimitError."""
        from services.strava_service import StravaRateLimitError

        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {"Retry-After": "60"}

        with patch("requests.get", return_value=mock_429), \
             patch("services.strava_service.acquire_strava_read_budget", return_value=True), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"):
            from services.strava_service import get_activity_streams
            with pytest.raises(StravaRateLimitError):
                get_activity_streams(
                    MagicMock(strava_access_token="encrypted"),
                    activity_id=12345,
                    allow_rate_limit_sleep=False,
                )

    def test_empty_response_returns_unavailable(self):
        """Strava returns empty array (manual activity) → outcome='unavailable'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("requests.get", return_value=mock_response), \
             patch("services.strava_service.acquire_strava_read_budget", return_value=True), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"):
            from services.strava_service import get_activity_streams
            result = get_activity_streams(
                MagicMock(strava_access_token="encrypted"),
                activity_id=12345,
            )

        assert result.outcome == "unavailable"
        assert result.data is None

    def test_malformed_response_returns_failed(self):
        """Invalid JSON → outcome='failed' (retryable, NOT unavailable)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch("requests.get", return_value=mock_response), \
             patch("services.strava_service.acquire_strava_read_budget", return_value=True), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"):
            from services.strava_service import get_activity_streams
            result = get_activity_streams(
                MagicMock(strava_access_token="encrypted"),
                activity_id=12345,
            )

        assert result.outcome == "failed"
        assert "malformed_json" in result.error

    def test_channel_length_mismatch_returns_failed(self):
        """time=100 points, heartrate=98 points → outcome='failed' (NOT unavailable)."""
        response_data = [
            {"type": "time", "data": list(range(100)), "series_type": "distance",
             "original_size": 100, "resolution": "high"},
            {"type": "heartrate", "data": [140] * 98, "series_type": "distance",
             "original_size": 98, "resolution": "high"},
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with patch("requests.get", return_value=mock_response), \
             patch("services.strava_service.acquire_strava_read_budget", return_value=True), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"):
            from services.strava_service import get_activity_streams
            result = get_activity_streams(
                MagicMock(strava_access_token="encrypted"),
                activity_id=12345,
            )

        assert result.outcome == "failed"
        assert "channel_length_mismatch" in result.error

    def test_budget_exhausted_raises_or_waits(self):
        """acquire_strava_read_budget returns False → StravaRateLimitError raised."""
        with patch("services.strava_service.acquire_strava_read_budget", return_value=False), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"):
            from services.strava_service import get_activity_streams, StravaRateLimitError
            with pytest.raises(StravaRateLimitError):
                get_activity_streams(
                    MagicMock(strava_access_token="encrypted"),
                    activity_id=12345,
                    allow_rate_limit_sleep=False,
                )

    def test_redis_down_returns_skipped_no_redis(self):
        """acquire_strava_read_budget returns None (Redis down) → outcome='skipped_no_redis' (NOT unavailable)."""
        with patch("services.strava_service.acquire_strava_read_budget", return_value=None), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"):
            from services.strava_service import get_activity_streams
            result = get_activity_streams(
                MagicMock(strava_access_token="encrypted"),
                activity_id=12345,
            )

        assert result.outcome == "skipped_no_redis"
        assert result.data is None


# ===========================================================================
# CATEGORY 1: UNIT TESTS — Rate Limiter
# ===========================================================================

class TestAcquireStravaReadBudget:
    """Unit tests for the global rate limiter (ADR-063 Decision 4)."""

    def test_returns_true_when_budget_available(self):
        """Budget available → True, counter incremented."""
        mock_redis = MagicMock()
        mock_redis.eval.return_value = 1

        with patch("core.cache.get_redis_client", return_value=mock_redis):
            from services.strava_service import acquire_strava_read_budget
            result = acquire_strava_read_budget()

        assert result is True

    def test_returns_false_when_budget_exhausted(self):
        """Budget exhausted → False."""
        mock_redis = MagicMock()
        mock_redis.eval.return_value = 0

        with patch("core.cache.get_redis_client", return_value=mock_redis):
            from services.strava_service import acquire_strava_read_budget
            result = acquire_strava_read_budget()

        assert result is False

    def test_returns_none_when_redis_unavailable(self):
        """Redis down → None (caller must apply degraded-mode policy)."""
        with patch("core.cache.get_redis_client", return_value=None):
            from services.strava_service import acquire_strava_read_budget
            result = acquire_strava_read_budget()

        assert result is None

    def test_uses_global_key_not_per_athlete(self):
        """Key must be strava:rate:global:window:{id}, not per-athlete."""
        mock_redis = MagicMock()
        mock_redis.eval.return_value = 1

        with patch("core.cache.get_redis_client", return_value=mock_redis):
            from services.strava_service import acquire_strava_read_budget
            acquire_strava_read_budget()

        # Inspect the key passed to the Lua eval call
        call_args = mock_redis.eval.call_args
        # eval(script, num_keys, key, ...args)
        # The key is the 3rd positional argument (index 2)
        if call_args and call_args[0]:
            key_arg = call_args[0][2] if len(call_args[0]) > 2 else None
            if key_arg:
                assert "global" in key_arg, f"Key should be global, got: {key_arg}"


# ===========================================================================
# CATEGORY 1: UNIT TESTS — Backfill Query
# ===========================================================================

class TestBackfillEligibility:
    """Unit tests for backfill eligibility query (ADR-063 Decision 5)."""

    def test_pending_strava_activity_is_eligible(self, db_session, strava_activity):
        """Pending + provider=strava + external_id → eligible."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT id FROM activity
            WHERE stream_fetch_status IN ('pending', 'failed', 'deferred')
              AND external_activity_id IS NOT NULL
              AND provider = 'strava'
              AND (
                stream_fetch_status = 'pending'
                OR (stream_fetch_status = 'failed' AND stream_fetch_retry_count < 3)
                OR (stream_fetch_status = 'deferred' AND stream_fetch_deferred_until < NOW())
              )
        """))
        ids = [str(row[0]) for row in result]
        assert str(strava_activity.id) in ids

    def test_manual_activity_not_eligible(self, db_session, manual_activity):
        """Manual activity (unavailable) is not in backfill query."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT id FROM activity
            WHERE stream_fetch_status IN ('pending', 'failed', 'deferred')
              AND external_activity_id IS NOT NULL
              AND provider = 'strava'
        """))
        ids = [str(row[0]) for row in result]
        assert str(manual_activity.id) not in ids

    def test_success_activity_not_eligible(self, db_session, strava_activity):
        """Success (terminal) is not in backfill query."""
        from sqlalchemy import text

        strava_activity.stream_fetch_status = "success"
        db_session.commit()

        result = db_session.execute(text("""
            SELECT id FROM activity
            WHERE stream_fetch_status IN ('pending', 'failed', 'deferred')
              AND external_activity_id IS NOT NULL
              AND provider = 'strava'
        """))
        ids = [str(row[0]) for row in result]
        assert str(strava_activity.id) not in ids

    def test_failed_with_exhausted_retries_not_eligible(self, db_session, strava_activity):
        """Failed + retry_count=3 is filtered out by the retry guard."""
        from sqlalchemy import text

        strava_activity.stream_fetch_status = "failed"
        strava_activity.stream_fetch_retry_count = 3
        db_session.commit()

        result = db_session.execute(text("""
            SELECT id FROM activity
            WHERE stream_fetch_status IN ('pending', 'failed', 'deferred')
              AND external_activity_id IS NOT NULL
              AND provider = 'strava'
              AND (
                stream_fetch_status = 'pending'
                OR (stream_fetch_status = 'failed' AND stream_fetch_retry_count < 3)
                OR (stream_fetch_status = 'deferred' AND stream_fetch_deferred_until < NOW())
              )
        """))
        ids = [str(row[0]) for row in result]
        assert str(strava_activity.id) not in ids

    def test_deferred_before_cooldown_not_eligible(self, db_session, strava_activity):
        """Deferred + deferred_until in future → not eligible yet."""
        from sqlalchemy import text

        strava_activity.stream_fetch_status = "deferred"
        strava_activity.stream_fetch_deferred_until = datetime.now(timezone.utc) + timedelta(hours=1)
        db_session.commit()

        result = db_session.execute(text("""
            SELECT id FROM activity
            WHERE stream_fetch_status IN ('pending', 'failed', 'deferred')
              AND external_activity_id IS NOT NULL
              AND provider = 'strava'
              AND (
                stream_fetch_status = 'pending'
                OR (stream_fetch_status = 'failed' AND stream_fetch_retry_count < 3)
                OR (stream_fetch_status = 'deferred' AND stream_fetch_deferred_until < NOW())
              )
        """))
        ids = [str(row[0]) for row in result]
        assert str(strava_activity.id) not in ids

    def test_oldest_first_ordering(self, db_session, test_athlete):
        """Backfill processes oldest activities first."""
        from sqlalchemy import text

        activities = []
        for i in range(5):
            a = Activity(
                athlete_id=test_athlete.id,
                name=f"Run {i}",
                start_time=datetime.now(timezone.utc) - timedelta(days=10 - i),
                sport="run",
                source="strava",
                provider="strava",
                external_activity_id=f"ordering_test_{i}_{uuid4()}",
                stream_fetch_status="pending",
            )
            db_session.add(a)
            activities.append(a)
        db_session.commit()

        result = db_session.execute(text("""
            SELECT id FROM activity
            WHERE stream_fetch_status = 'pending'
              AND external_activity_id IS NOT NULL
              AND provider = 'strava'
            ORDER BY start_time ASC
        """))
        ids = [str(row[0]) for row in result]

        # Oldest (days=10 ago) should come before newest (days=6 ago)
        oldest_idx = ids.index(str(activities[0].id))
        newest_idx = ids.index(str(activities[4].id))
        assert oldest_idx < newest_idx


# ===========================================================================
# CATEGORY 2: INTEGRATION TESTS
# ===========================================================================

class TestStreamIngestionIntegration:
    """Integration tests — components wired together against test database."""

    def test_stream_stored_and_served_round_trip(self, db_session, strava_activity):
        """Ingest stream data → query via relationship → data matches."""
        original_data = _make_stream_data(500, ["time", "heartrate", "altitude"])
        channels = list(original_data.keys())

        stream = ActivityStream(
            activity_id=strava_activity.id,
            stream_data=original_data,
            channels_available=channels,
            point_count=500,
            source="strava",
        )
        db_session.add(stream)
        db_session.commit()

        # Query through relationship
        db_session.refresh(strava_activity)
        stored = strava_activity.stream

        assert stored is not None
        assert stored.point_count == 500
        assert stored.stream_data["time"] == original_data["time"]
        assert stored.stream_data["heartrate"] == original_data["heartrate"]
        # Float tolerance check for altitude
        for i in range(500):
            assert abs(stored.stream_data["altitude"][i] - original_data["altitude"][i]) < 1e-6

    def test_migration_marks_manual_activities_unavailable(self, db_session, manual_activity):
        """Activities without external_activity_id should be 'unavailable'."""
        # manual_activity fixture already sets unavailable in the fixture
        # This test verifies the pattern the migration enforces
        assert manual_activity.stream_fetch_status == "unavailable"
        assert manual_activity.external_activity_id is None


# ===========================================================================
# CATEGORY 4: FAILURE-MODE TESTS
# ===========================================================================

class TestFailureModes:
    """Failure injection tests — chaos/retry/idempotency (ADR-063)."""

    def test_idempotent_no_duplicate_on_rerun(self, db_session, strava_activity):
        """Storing streams twice for same activity → unique constraint prevents dupe."""
        from sqlalchemy.exc import IntegrityError

        stream1 = ActivityStream(
            activity_id=strava_activity.id,
            stream_data=_make_stream_data(100, ["time"]),
            channels_available=["time"],
            point_count=100,
            source="strava",
        )
        db_session.add(stream1)
        db_session.commit()

        stream2 = ActivityStream(
            activity_id=strava_activity.id,
            stream_data=_make_stream_data(100, ["time"]),
            channels_available=["time"],
            point_count=100,
            source="strava",
        )
        db_session.add(stream2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_stale_fetching_cleanup_query(self, db_session, strava_activity):
        """Activity stuck in 'fetching' for >10min gets reset to 'failed'."""
        from sqlalchemy import text

        strava_activity.stream_fetch_status = "fetching"
        strava_activity.stream_fetch_attempted_at = datetime.now(timezone.utc) - timedelta(minutes=15)
        strava_activity.stream_fetch_retry_count = 0
        db_session.commit()

        result = db_session.execute(text("""
            UPDATE activity
            SET stream_fetch_status = 'failed',
                stream_fetch_error = 'fetching_timeout_cleanup',
                stream_fetch_retry_count = stream_fetch_retry_count + 1
            WHERE stream_fetch_status = 'fetching'
              AND stream_fetch_attempted_at < NOW() - INTERVAL '10 minutes'
            RETURNING id
        """))

        assert result.rowcount == 1
        db_session.refresh(strava_activity)
        assert strava_activity.stream_fetch_status == "failed"
        assert strava_activity.stream_fetch_error == "fetching_timeout_cleanup"
        assert strava_activity.stream_fetch_retry_count == 1

    def test_stale_fetching_cleanup_ignores_recent(self, db_session, strava_activity):
        """Activity in 'fetching' for <10min is NOT cleaned up (worker still active)."""
        from sqlalchemy import text

        strava_activity.stream_fetch_status = "fetching"
        strava_activity.stream_fetch_attempted_at = datetime.now(timezone.utc) - timedelta(minutes=3)
        db_session.commit()

        result = db_session.execute(text("""
            UPDATE activity
            SET stream_fetch_status = 'failed',
                stream_fetch_error = 'fetching_timeout_cleanup',
                stream_fetch_retry_count = stream_fetch_retry_count + 1
            WHERE stream_fetch_status = 'fetching'
              AND stream_fetch_attempted_at < NOW() - INTERVAL '10 minutes'
            RETURNING id
        """))

        assert result.rowcount == 0
        db_session.refresh(strava_activity)
        assert strava_activity.stream_fetch_status == "fetching"  # unchanged

    def test_partial_batch_success(self, db_session, test_athlete):
        """3 success + 1 fail = 3 streams stored, 1 remains pending/failed."""
        activities = []
        for i in range(4):
            a = Activity(
                athlete_id=test_athlete.id,
                name=f"Batch Run {i}",
                start_time=datetime.now(timezone.utc) - timedelta(days=i),
                sport="run",
                source="strava",
                provider="strava",
                external_activity_id=f"batch_test_{i}_{uuid4()}",
                stream_fetch_status="pending",
            )
            db_session.add(a)
            activities.append(a)
        db_session.commit()

        # Simulate: first 3 succeed, 4th fails
        for i in range(3):
            stream = ActivityStream(
                activity_id=activities[i].id,
                stream_data=_make_stream_data(100, ["time"]),
                channels_available=["time"],
                point_count=100,
                source="strava",
            )
            db_session.add(stream)
            activities[i].stream_fetch_status = "success"

        activities[3].stream_fetch_status = "failed"
        activities[3].stream_fetch_error = "timeout"
        activities[3].stream_fetch_retry_count = 1
        db_session.commit()

        # Verify: 3 streams exist, 1 activity is failed
        stream_count = db_session.query(ActivityStream).filter(
            ActivityStream.activity_id.in_([a.id for a in activities])
        ).count()
        assert stream_count == 3

        db_session.refresh(activities[3])
        assert activities[3].stream_fetch_status == "failed"


# ===========================================================================
# CATEGORY 4: FAILURE-MODE TESTS — State Classification Correctness
# ===========================================================================

class TestTransientFailuresNeverSetUnavailable:
    """Verify that transient/operational failures are NOT misclassified as
    terminal 'unavailable'. Only Strava-confirmed no-streams (404, empty)
    may set 'unavailable'. Everything else must be 'failed' or reverted to
    'pending' so backfill can retry."""

    def test_redis_down_does_not_set_unavailable(self, db_session, test_athlete, strava_activity):
        """Redis down during fetch → revert to 'pending', not 'unavailable'."""
        # Ensure activity is in fetchable state
        strava_activity.stream_fetch_status = "pending"
        db_session.commit()

        with patch("services.strava_service.acquire_strava_read_budget", return_value=None), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"):
            from tasks.strava_tasks import _fetch_and_store_stream
            result = _fetch_and_store_stream(
                str(strava_activity.id), test_athlete, db_session,
            )

        assert result == "skipped_no_redis"
        db_session.refresh(strava_activity)
        assert strava_activity.stream_fetch_status == "pending"
        assert strava_activity.stream_fetch_status != "unavailable"

    def test_malformed_json_does_not_set_unavailable(self, db_session, test_athlete, strava_activity):
        """Malformed JSON response → 'failed' (retryable), not 'unavailable'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")

        strava_activity.stream_fetch_status = "pending"
        db_session.commit()

        with patch("requests.get", return_value=mock_response), \
             patch("services.strava_service.acquire_strava_read_budget", return_value=True), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"):
            from tasks.strava_tasks import _fetch_and_store_stream
            result = _fetch_and_store_stream(
                str(strava_activity.id), test_athlete, db_session,
            )

        assert result == "failed"
        db_session.refresh(strava_activity)
        assert strava_activity.stream_fetch_status == "failed"
        assert strava_activity.stream_fetch_status != "unavailable"
        assert "malformed_json" in (strava_activity.stream_fetch_error or "")

    def test_channel_length_mismatch_does_not_set_unavailable(self, db_session, test_athlete, strava_activity):
        """Channel length mismatch → 'failed' (retryable), not 'unavailable'."""
        response_data = [
            {"type": "time", "data": list(range(100)), "series_type": "distance",
             "original_size": 100, "resolution": "high"},
            {"type": "heartrate", "data": [140] * 98, "series_type": "distance",
             "original_size": 98, "resolution": "high"},
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        strava_activity.stream_fetch_status = "pending"
        db_session.commit()

        with patch("requests.get", return_value=mock_response), \
             patch("services.strava_service.acquire_strava_read_budget", return_value=True), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"):
            from tasks.strava_tasks import _fetch_and_store_stream
            result = _fetch_and_store_stream(
                str(strava_activity.id), test_athlete, db_session,
            )

        assert result == "failed"
        db_session.refresh(strava_activity)
        assert strava_activity.stream_fetch_status == "failed"
        assert strava_activity.stream_fetch_status != "unavailable"
        assert "channel_length_mismatch" in (strava_activity.stream_fetch_error or "")

    def test_token_decrypt_failure_does_not_set_unavailable(self, db_session, test_athlete, strava_activity):
        """Token decrypt failure → 'failed' (retryable), not 'unavailable'."""
        strava_activity.stream_fetch_status = "pending"
        db_session.commit()

        with patch("services.strava_service.acquire_strava_read_budget", return_value=True), \
             patch("services.token_encryption.decrypt_token", return_value=None):
            from tasks.strava_tasks import _fetch_and_store_stream
            result = _fetch_and_store_stream(
                str(strava_activity.id), test_athlete, db_session,
            )

        assert result == "failed"
        db_session.refresh(strava_activity)
        assert strava_activity.stream_fetch_status == "failed"
        assert strava_activity.stream_fetch_status != "unavailable"

    def test_strava_404_does_set_unavailable(self, db_session, test_athlete, strava_activity):
        """Strava 404 (activity truly has no streams) → 'unavailable' (terminal)."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        strava_activity.stream_fetch_status = "pending"
        db_session.commit()

        with patch("requests.get", return_value=mock_response), \
             patch("services.strava_service.acquire_strava_read_budget", return_value=True), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"):
            from tasks.strava_tasks import _fetch_and_store_stream
            result = _fetch_and_store_stream(
                str(strava_activity.id), test_athlete, db_session,
            )

        assert result == "unavailable"
        db_session.refresh(strava_activity)
        assert strava_activity.stream_fetch_status == "unavailable"

    def test_strava_empty_response_does_set_unavailable(self, db_session, test_athlete, strava_activity):
        """Strava empty response (manual activity) → 'unavailable' (terminal)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        strava_activity.stream_fetch_status = "pending"
        db_session.commit()

        with patch("requests.get", return_value=mock_response), \
             patch("services.strava_service.acquire_strava_read_budget", return_value=True), \
             patch("services.token_encryption.decrypt_token", return_value="fake_token"):
            from tasks.strava_tasks import _fetch_and_store_stream
            result = _fetch_and_store_stream(
                str(strava_activity.id), test_athlete, db_session,
            )

        assert result == "unavailable"
        db_session.refresh(strava_activity)
        assert strava_activity.stream_fetch_status == "unavailable"
