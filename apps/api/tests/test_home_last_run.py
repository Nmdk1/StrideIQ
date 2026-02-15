"""RSI Layer 1 — Home Page Last Run Hero Tests

AC coverage:
    L1-1: /v1/home returns last_run with effort_intensity when streams available
    L1-2: /v1/home returns last_run with stream_status:'pending' and effort_intensity:null when streams not yet fetched
    L1-3: /v1/home returns last_run: null when athlete has no activities
    L1-extra: last_run is null when latest activity is >24h old
"""
import sys
import os
import pytest
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from sqlalchemy import event
from sqlalchemy.orm import Session

from main import app
from core.database import engine, get_db
from core.security import create_access_token
from models import Activity, ActivityStream, Athlete
from fixtures.stream_fixtures import make_easy_run_stream


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_encryption_key():
    """Ensure valid Fernet key for token encryption."""
    import services.token_encryption as te_mod
    key = Fernet.generate_key().decode()
    old_val = os.environ.get("TOKEN_ENCRYPTION_KEY")
    os.environ["TOKEN_ENCRYPTION_KEY"] = key
    te_mod._token_encryption = None
    yield
    te_mod._token_encryption = None
    if old_val is not None:
        os.environ["TOKEN_ENCRYPTION_KEY"] = old_val
    elif "TOKEN_ENCRYPTION_KEY" in os.environ:
        del os.environ["TOKEN_ENCRYPTION_KEY"]


@pytest.fixture
def db_session():
    """DB session shared between test fixtures and the app via dependency override."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        nonlocal nested
        if trans.nested and not trans._parent.nested:
            nested = connection.begin_nested()

    def _override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    yield session
    app.dependency_overrides.pop(get_db, None)
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    return TestClient(app)


@pytest.fixture
def test_athlete(db_session):
    """Authenticated athlete with Tier 1 physiology."""
    from services.token_encryption import encrypt_token
    athlete = Athlete(
        email=f"home_l1_{uuid4()}@example.com",
        display_name="Layer 1 Test",
        subscription_tier="premium",
        birthdate=date(1990, 1, 1),
        sex="M",
        strava_access_token=encrypt_token("fake_token"),
        strava_refresh_token=encrypt_token("fake_refresh"),
        strava_athlete_id=77001,
        max_hr=186,
        resting_hr=48,
        threshold_hr=165,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def _auth(athlete):
    token = create_access_token(data={"sub": str(athlete.id)})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# L1-1: last_run with effort_intensity when streams available
# ---------------------------------------------------------------------------

class TestLastRunWithStreams:
    """L1-1: /v1/home returns last_run with effort_intensity when streams are available."""

    def test_last_run_present_with_effort_when_stream_success(
        self, client, test_athlete, db_session
    ):
        """When latest activity (within 24h) has stream_fetch_status='success',
        last_run includes effort_intensity, tier_used, confidence, segments."""
        activity = Activity(
            athlete_id=test_athlete.id,
            name="Morning Easy Run",
            start_time=datetime.now(timezone.utc) - timedelta(hours=2),
            sport="run",
            source="strava",
            provider="strava",
            external_activity_id=f"home_l1_{uuid4().hex[:8]}",
            duration_s=3600,
            distance_m=10000,
            avg_hr=145,
            stream_fetch_status="success",
        )
        db_session.add(activity)
        db_session.commit()

        stream_data = make_easy_run_stream(duration_s=3600)
        stream = ActivityStream(
            activity_id=activity.id,
            stream_data=stream_data,
            channels_available=list(stream_data.keys()),
            point_count=3600,
            source="strava",
        )
        db_session.add(stream)
        db_session.commit()

        resp = client.get("/v1/home", headers=_auth(test_athlete))
        assert resp.status_code == 200
        data = resp.json()

        lr = data.get("last_run")
        assert lr is not None, "last_run should be present"
        assert lr["activity_id"] == str(activity.id)
        assert lr["name"] == "Morning Easy Run"
        assert lr["stream_status"] == "success"

        # L1-1: effort_intensity populated
        assert lr["effort_intensity"] is not None
        assert isinstance(lr["effort_intensity"], list)
        assert len(lr["effort_intensity"]) > 0
        assert len(lr["effort_intensity"]) <= 500, "Should be LTTB capped to ≤500"

        # Analysis metadata present
        assert lr["tier_used"] is not None
        assert lr["confidence"] is not None
        assert 0.0 <= lr["confidence"] <= 1.0

        # Segments present
        assert lr["segments"] is not None
        assert isinstance(lr["segments"], list)
        assert len(lr["segments"]) > 0
        seg = lr["segments"][0]
        assert "type" in seg
        assert "start_time_s" in seg
        assert "end_time_s" in seg

        # H1: pace_stream and elevation_stream populated from velocity_smooth/altitude
        assert lr["pace_stream"] is not None, "pace_stream should be populated when velocity_smooth exists"
        assert isinstance(lr["pace_stream"], list)
        assert len(lr["pace_stream"]) > 0
        assert len(lr["pace_stream"]) <= 500, "Should be LTTB capped to ≤500"
        # Pace values should be reasonable (s/km)
        for p in lr["pace_stream"]:
            assert 120 <= p <= 1200, f"Pace {p} s/km out of reasonable range"

        assert lr["elevation_stream"] is not None, "elevation_stream should be populated when altitude exists"
        assert isinstance(lr["elevation_stream"], list)
        assert len(lr["elevation_stream"]) > 0
        assert len(lr["elevation_stream"]) <= 500, "Should be LTTB capped to ≤500"

        # Derived metrics
        assert lr["distance_m"] == 10000
        assert lr["moving_time_s"] == 3600
        assert lr["average_hr"] == 145
        assert lr["pace_per_km"] is not None
        assert lr["pace_per_km"] > 0

    def test_effort_values_are_valid_floats(
        self, client, test_athlete, db_session
    ):
        """All effort_intensity values are floats in [0, 1]."""
        activity = Activity(
            athlete_id=test_athlete.id,
            name="Validation Run",
            start_time=datetime.now(timezone.utc) - timedelta(hours=1),
            sport="run",
            source="strava",
            provider="strava",
            external_activity_id=f"home_val_{uuid4().hex[:8]}",
            duration_s=1800,
            distance_m=5000,
            avg_hr=150,
            stream_fetch_status="success",
        )
        db_session.add(activity)
        db_session.commit()

        stream_data = make_easy_run_stream(duration_s=1800)
        stream = ActivityStream(
            activity_id=activity.id,
            stream_data=stream_data,
            channels_available=list(stream_data.keys()),
            point_count=1800,
            source="strava",
        )
        db_session.add(stream)
        db_session.commit()

        resp = client.get("/v1/home", headers=_auth(test_athlete))
        lr = resp.json()["last_run"]
        assert lr is not None

        for val in lr["effort_intensity"]:
            assert isinstance(val, (int, float)), f"Expected float, got {type(val)}"
            assert 0.0 <= val <= 1.0, f"Effort value {val} out of [0, 1] range"


# ---------------------------------------------------------------------------
# L1-2: last_run with pending stream_status
# ---------------------------------------------------------------------------

class TestLastRunPendingStream:
    """L1-2: /v1/home returns last_run with stream_status='pending' and effort_intensity=null."""

    def test_last_run_present_but_no_effort_when_stream_pending(
        self, client, test_athlete, db_session
    ):
        """When stream_fetch_status='pending', last_run exists but effort_intensity is null."""
        activity = Activity(
            athlete_id=test_athlete.id,
            name="Pending Stream Run",
            start_time=datetime.now(timezone.utc) - timedelta(hours=3),
            sport="run",
            source="strava",
            provider="strava",
            external_activity_id=f"home_pend_{uuid4().hex[:8]}",
            duration_s=2700,
            distance_m=8000,
            avg_hr=140,
            stream_fetch_status="pending",
        )
        db_session.add(activity)
        db_session.commit()

        resp = client.get("/v1/home", headers=_auth(test_athlete))
        assert resp.status_code == 200
        lr = resp.json()["last_run"]

        assert lr is not None
        assert lr["stream_status"] == "pending"
        assert lr["effort_intensity"] is None
        assert lr["pace_stream"] is None
        assert lr["elevation_stream"] is None
        assert lr["tier_used"] is None
        assert lr["confidence"] is None
        assert lr["segments"] is None

        # Metrics still available
        assert lr["distance_m"] == 8000
        assert lr["name"] == "Pending Stream Run"

    def test_last_run_fetching_also_shows_metrics_only(
        self, client, test_athlete, db_session
    ):
        """stream_fetch_status='fetching' treated same as pending."""
        activity = Activity(
            athlete_id=test_athlete.id,
            name="Fetching Run",
            start_time=datetime.now(timezone.utc) - timedelta(hours=1),
            sport="run",
            source="strava",
            provider="strava",
            external_activity_id=f"home_fetch_{uuid4().hex[:8]}",
            duration_s=1800,
            distance_m=5000,
            stream_fetch_status="fetching",
        )
        db_session.add(activity)
        db_session.commit()

        resp = client.get("/v1/home", headers=_auth(test_athlete))
        lr = resp.json()["last_run"]

        assert lr is not None
        assert lr["stream_status"] == "fetching"
        assert lr["effort_intensity"] is None


# ---------------------------------------------------------------------------
# L1-3: last_run null when no activities
# ---------------------------------------------------------------------------

class TestLastRunNoActivities:
    """L1-3: /v1/home returns last_run: null when athlete has no activities."""

    def test_last_run_null_when_no_activities(
        self, client, test_athlete
    ):
        """Brand new athlete with no activities → last_run is null."""
        resp = client.get("/v1/home", headers=_auth(test_athlete))
        assert resp.status_code == 200
        assert resp.json()["last_run"] is None


# ---------------------------------------------------------------------------
# L1-extra: 24h decay
# ---------------------------------------------------------------------------

class TestLastRun24hDecay:
    """Layer 1 spec: last_run is null when latest activity is >24h old."""

    def test_last_run_null_when_activity_older_than_24h(
        self, client, test_athlete, db_session
    ):
        """Activity from 25 hours ago → last_run is null."""
        activity = Activity(
            athlete_id=test_athlete.id,
            name="Old Run",
            start_time=datetime.now(timezone.utc) - timedelta(hours=25),
            sport="run",
            source="strava",
            provider="strava",
            external_activity_id=f"home_old_{uuid4().hex[:8]}",
            duration_s=3600,
            distance_m=10000,
            stream_fetch_status="success",
        )
        db_session.add(activity)
        db_session.commit()

        resp = client.get("/v1/home", headers=_auth(test_athlete))
        assert resp.status_code == 200
        assert resp.json()["last_run"] is None

    def test_last_run_present_when_activity_within_24h(
        self, client, test_athlete, db_session
    ):
        """Activity from 23 hours ago → last_run is present."""
        activity = Activity(
            athlete_id=test_athlete.id,
            name="Recent Run",
            start_time=datetime.now(timezone.utc) - timedelta(hours=23),
            sport="run",
            source="strava",
            provider="strava",
            external_activity_id=f"home_recent_{uuid4().hex[:8]}",
            duration_s=2400,
            distance_m=7000,
            stream_fetch_status="pending",
        )
        db_session.add(activity)
        db_session.commit()

        resp = client.get("/v1/home", headers=_auth(test_athlete))
        lr = resp.json()["last_run"]
        assert lr is not None
        assert lr["name"] == "Recent Run"
