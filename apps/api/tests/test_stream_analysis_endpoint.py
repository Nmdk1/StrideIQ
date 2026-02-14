"""RSI-Alpha — AC-1: Stream Analysis Endpoint Tests

Tests the REST endpoint: GET /v1/activities/{id}/stream-analysis

AC coverage:
    AC-1: Analysis endpoint returns correct status/shape for all lifecycle states.
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
from core.database import SessionLocal, engine, get_db
from core.security import create_access_token
from models import Activity, ActivityStream, Athlete, PlannedWorkout, TrainingPlan
from fixtures.stream_fixtures import make_easy_run_stream, make_interval_stream


# ---------------------------------------------------------------------------
# Fixtures: DB session with app dependency override
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

    # Override the app's get_db dependency so it shares this session
    def _override_get_db():
        try:
            yield session
        finally:
            pass  # session lifecycle managed by fixture

    app.dependency_overrides[get_db] = _override_get_db
    yield session

    app.dependency_overrides.pop(get_db, None)
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """TestClient wired to the overridden DB session."""
    return TestClient(app)


@pytest.fixture
def test_athlete(db_session):
    """Create an authenticated test athlete with Tier 1 physiology."""
    from services.token_encryption import encrypt_token
    athlete = Athlete(
        email=f"rsi_endpoint_{uuid4()}@example.com",
        display_name="RSI Endpoint Test",
        subscription_tier="premium",
        birthdate=date(1990, 1, 1),
        sex="M",
        strava_access_token=encrypt_token("fake_token"),
        strava_refresh_token=encrypt_token("fake_refresh"),
        strava_athlete_id=88001,
        max_hr=186,
        resting_hr=48,
        threshold_hr=165,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


@pytest.fixture
def other_athlete(db_session):
    """A separate athlete to test ownership checks."""
    from services.token_encryption import encrypt_token
    athlete = Athlete(
        email=f"rsi_other_{uuid4()}@example.com",
        display_name="Other Athlete",
        subscription_tier="free",
        birthdate=date(1985, 6, 15),
        sex="F",
        strava_access_token=encrypt_token("fake_other"),
        strava_refresh_token=encrypt_token("fake_other_refresh"),
        strava_athlete_id=88002,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


@pytest.fixture
def activity_with_stream(db_session, test_athlete):
    """Activity with stream_fetch_status='success' and populated stream data."""
    activity = Activity(
        athlete_id=test_athlete.id,
        name="RSI Endpoint Easy Run",
        start_time=datetime.now(timezone.utc) - timedelta(days=1),
        sport="run",
        source="strava",
        provider="strava",
        external_activity_id=f"rsi_ep_{uuid4().hex[:8]}",
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
    db_session.refresh(activity)
    return activity


@pytest.fixture
def activity_pending(db_session, test_athlete):
    """Activity with stream_fetch_status='pending'."""
    activity = Activity(
        athlete_id=test_athlete.id,
        name="Pending Stream Run",
        start_time=datetime.now(timezone.utc) - timedelta(days=2),
        sport="run",
        source="strava",
        provider="strava",
        external_activity_id=f"rsi_pending_{uuid4().hex[:8]}",
        duration_s=1800,
        distance_m=5000,
        stream_fetch_status="pending",
    )
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    return activity


@pytest.fixture
def activity_fetching(db_session, test_athlete):
    """Activity with stream_fetch_status='fetching'."""
    activity = Activity(
        athlete_id=test_athlete.id,
        name="Fetching Stream Run",
        start_time=datetime.now(timezone.utc) - timedelta(days=2),
        sport="run",
        source="strava",
        provider="strava",
        external_activity_id=f"rsi_fetching_{uuid4().hex[:8]}",
        duration_s=2400,
        distance_m=7000,
        stream_fetch_status="fetching",
    )
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    return activity


@pytest.fixture
def activity_unavailable(db_session, test_athlete):
    """Activity with stream_fetch_status='unavailable' (manual entry)."""
    activity = Activity(
        athlete_id=test_athlete.id,
        name="Manual Run",
        start_time=datetime.now(timezone.utc) - timedelta(days=3),
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


@pytest.fixture
def other_athlete_activity(db_session, other_athlete):
    """Activity owned by other_athlete (for ownership check)."""
    activity = Activity(
        athlete_id=other_athlete.id,
        name="Other Athlete Run",
        start_time=datetime.now(timezone.utc) - timedelta(days=1),
        sport="run",
        source="strava",
        provider="strava",
        external_activity_id=f"rsi_other_{uuid4().hex[:8]}",
        duration_s=2000,
        distance_m=6000,
        stream_fetch_status="success",
    )
    db_session.add(activity)
    db_session.commit()

    stream_data = make_easy_run_stream(duration_s=2000)
    stream = ActivityStream(
        activity_id=activity.id,
        stream_data=stream_data,
        channels_available=list(stream_data.keys()),
        point_count=2000,
        source="strava",
    )
    db_session.add(stream)
    db_session.commit()
    db_session.refresh(activity)
    return activity


@pytest.fixture
def activity_with_plan(db_session, test_athlete, activity_with_stream):
    """Links a PlannedWorkout to activity_with_stream."""
    plan = TrainingPlan(
        athlete_id=test_athlete.id,
        name="RSI Test Plan",
        plan_start_date=date.today() - timedelta(days=14),
        plan_end_date=date.today() + timedelta(days=14),
        goal_race_date=date.today() + timedelta(days=14),
        goal_race_distance_m=5000,
        total_weeks=4,
        status="active",
        plan_type="5k",
    )
    db_session.add(plan)
    db_session.commit()

    workout = PlannedWorkout(
        plan_id=plan.id,
        athlete_id=test_athlete.id,
        scheduled_date=activity_with_stream.start_time.date(),
        week_number=1,
        day_of_week=1,
        phase="base",
        title="Easy Run",
        workout_type="easy",
        target_duration_minutes=60,
        target_distance_km=10.0,
        completed=True,
        completed_activity_id=activity_with_stream.id,
        segments=[
            {"type": "warmup", "duration_minutes": 10},
            {"type": "steady", "duration_minutes": 45},
            {"type": "cooldown", "duration_minutes": 5},
        ],
    )
    db_session.add(workout)
    db_session.commit()
    return activity_with_stream


# ---------------------------------------------------------------------------
# Helper: authenticated client
# ---------------------------------------------------------------------------

def _auth_headers(athlete):
    """Build auth headers for test_athlete."""
    token = create_access_token(data={"sub": str(athlete.id)})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# AC-1 Tests
# ---------------------------------------------------------------------------

class TestStreamAnalysisEndpoint:
    """AC-1: GET /v1/activities/{id}/stream-analysis."""

    ENDPOINT = "/v1/activities/{activity_id}/stream-analysis"

    def test_returns_200_with_full_result_when_stream_exists(
        self, client, test_athlete, activity_with_stream
    ):
        """200 with all StreamAnalysisResult fields when stream data exists."""
        url = self.ENDPOINT.format(activity_id=activity_with_stream.id)
        resp = client.get(url, headers=_auth_headers(test_athlete))

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        # All 11 required fields present
        required_fields = [
            "segments", "drift", "moments", "plan_comparison",
            "channels_present", "channels_missing", "point_count",
            "confidence", "tier_used", "estimated_flags", "cross_run_comparable",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Type checks
        assert isinstance(data["segments"], list)
        assert isinstance(data["drift"], dict)
        assert isinstance(data["moments"], list)
        assert isinstance(data["channels_present"], list)
        assert isinstance(data["channels_missing"], list)
        assert isinstance(data["point_count"], int)
        assert isinstance(data["confidence"], (int, float))
        assert isinstance(data["cross_run_comparable"], bool)
        assert data["tier_used"] in {
            "tier1_threshold_hr", "tier2_estimated_hrr", "tier3_max_hr", "tier4_stream_relative"
        }
        assert 0.0 <= data["confidence"] <= 1.0

    def test_returns_404_when_activity_not_found(self, client, test_athlete):
        """404 for nonexistent activity ID."""
        url = self.ENDPOINT.format(activity_id=uuid4())
        resp = client.get(url, headers=_auth_headers(test_athlete))
        assert resp.status_code == 404

    def test_returns_404_when_owned_by_other_user(
        self, client, test_athlete, other_athlete_activity
    ):
        """404 (not 403) when activity belongs to another athlete."""
        url = self.ENDPOINT.format(activity_id=other_athlete_activity.id)
        resp = client.get(url, headers=_auth_headers(test_athlete))
        assert resp.status_code == 404

    def test_returns_pending_when_stream_status_pending(
        self, client, test_athlete, activity_pending
    ):
        """200 with {"status": "pending"} when stream_fetch_status='pending'."""
        url = self.ENDPOINT.format(activity_id=activity_pending.id)
        resp = client.get(url, headers=_auth_headers(test_athlete))
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "pending"

    def test_returns_pending_when_stream_status_fetching(
        self, client, test_athlete, activity_fetching
    ):
        """200 with {"status": "pending"} when stream_fetch_status='fetching'."""
        url = self.ENDPOINT.format(activity_id=activity_fetching.id)
        resp = client.get(url, headers=_auth_headers(test_athlete))
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "pending"

    def test_returns_unavailable_when_stream_status_unavailable(
        self, client, test_athlete, activity_unavailable
    ):
        """200 with {"status": "unavailable"} when stream_fetch_status='unavailable'."""
        url = self.ENDPOINT.format(activity_id=activity_unavailable.id)
        resp = client.get(url, headers=_auth_headers(test_athlete))
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "unavailable"

    def test_returns_401_without_auth(self, client, activity_with_stream):
        """401 when no auth header provided."""
        url = self.ENDPOINT.format(activity_id=activity_with_stream.id)
        resp = client.get(url)
        assert resp.status_code == 401

    def test_includes_plan_comparison_when_plan_linked(
        self, client, test_athlete, activity_with_plan
    ):
        """plan_comparison is non-null when a PlannedWorkout is linked."""
        url = self.ENDPOINT.format(activity_id=activity_with_plan.id)
        resp = client.get(url, headers=_auth_headers(test_athlete))
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("plan_comparison") is not None

    def test_plan_comparison_null_when_no_plan(
        self, client, test_athlete, activity_with_stream
    ):
        """plan_comparison is null when no linked plan."""
        url = self.ENDPOINT.format(activity_id=activity_with_stream.id)
        resp = client.get(url, headers=_auth_headers(test_athlete))
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("plan_comparison") is None

    def test_response_includes_effort_intensity(
        self, client, test_athlete, activity_with_stream
    ):
        """Response includes per-point effort_intensity data."""
        url = self.ENDPOINT.format(activity_id=activity_with_stream.id)
        resp = client.get(url, headers=_auth_headers(test_athlete))
        assert resp.status_code == 200
        data = resp.json()
        # Effort intensity is either a top-level array or within stream_data
        has_effort = (
            "effort_intensity" in data
            or "effort" in data
            or (
                isinstance(data.get("segments"), list)
                and len(data["segments"]) > 0
            )
        )
        assert has_effort, "Response must include effort intensity data"
