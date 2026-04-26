"""
Tests for Activity Workout Type — Fix 1 race classification sync.

All tests call the real PUT endpoint through TestClient, asserting DB state
after the request. No business logic is duplicated in test code.
"""
import os
import uuid
from datetime import datetime, timezone, date
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import event
from sqlalchemy.orm import Session

from fastapi.testclient import TestClient
from main import app
from core.database import engine, get_db
from core.security import create_access_token
from models import Activity, Athlete


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_encryption_key():
    """Ensure valid Fernet key for token encryption (required by app startup)."""
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
    """TestClient wired to the overridden DB session."""
    return TestClient(app)


@pytest.fixture
def test_athlete(db_session):
    """Create a test athlete with an auth token."""
    from services.token_encryption import encrypt_token
    athlete = Athlete(
        email=f"workout_type_test_{uuid.uuid4()}@example.com",
        display_name="Workout Type Test Athlete",
        subscription_tier="free",
        birthdate=date(1990, 1, 1),
        sex="M",
        strava_access_token=encrypt_token("fake_token"),
        strava_refresh_token=encrypt_token("fake_refresh"),
        strava_athlete_id=int(str(uuid.uuid4().int)[:8]),
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


@pytest.fixture
def auth_headers(test_athlete):
    """JWT auth headers for the test athlete."""
    token = create_access_token(data={
        "sub": str(test_athlete.id),
        "email": test_athlete.email,
        "role": "athlete",
    })
    return {"Authorization": f"Bearer {token}"}


def _make_activity(db_session, athlete, **overrides):
    """Create an Activity row with minimal required fields."""
    defaults = dict(
        athlete_id=athlete.id,
        provider="strava",
        external_activity_id=str(uuid.uuid4()),
        name="Test Run",
        start_time=datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc),
        distance_m=8000,
        duration_s=3600,
        workout_type="easy_run",
        workout_zone="endurance",
        workout_confidence=0.8,
        is_race_candidate=False,
        user_verified_race=False,
    )
    defaults.update(overrides)
    activity = Activity(**defaults)
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    return activity


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

class TestRaceClassificationSyncEndpoint:
    """Fix 1: PUT endpoint must sync user_verified_race and is_race_candidate."""

    def test_put_race_sets_both_flags_true(self, client, db_session, test_athlete, auth_headers):
        """PUT workout_type=race sets user_verified_race=True and is_race_candidate=True."""
        activity = _make_activity(
            db_session, test_athlete,
            workout_type="easy_run",
            is_race_candidate=False,
            user_verified_race=False,
        )

        resp = client.put(
            f"/v1/activities/{activity.id}/workout-type",
            json={"workout_type": "race"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        db_session.refresh(activity)
        assert activity.workout_type == "race"
        assert activity.workout_confidence == 1.0
        assert activity.user_verified_race is True
        assert activity.is_race_candidate is True

    def test_put_tune_up_race_sets_both_flags_true(self, client, db_session, test_athlete, auth_headers):
        """PUT workout_type=tune_up_race sets both race flags True."""
        activity = _make_activity(
            db_session, test_athlete,
            workout_type="easy_run",
            is_race_candidate=False,
            user_verified_race=False,
        )

        resp = client.put(
            f"/v1/activities/{activity.id}/workout-type",
            json={"workout_type": "tune_up_race"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        db_session.refresh(activity)
        assert activity.workout_type == "tune_up_race"
        assert activity.workout_confidence == 1.0
        assert activity.user_verified_race is True
        assert activity.is_race_candidate is True

    def test_put_nonrace_clears_both_flags(self, client, db_session, test_athlete, auth_headers):
        """Changing from race to easy_run clears both user_verified_race and is_race_candidate."""
        activity = _make_activity(
            db_session, test_athlete,
            workout_type="race",
            is_race_candidate=True,
            user_verified_race=True,
        )

        resp = client.put(
            f"/v1/activities/{activity.id}/workout-type",
            json={"workout_type": "easy_run"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        db_session.refresh(activity)
        assert activity.workout_type == "easy_run"
        assert activity.workout_confidence == 1.0
        assert activity.user_verified_race is False
        assert activity.is_race_candidate is False

    def test_put_invalid_workout_type_returns_400(self, client, db_session, test_athlete, auth_headers):
        """PUT with an invalid workout_type returns 400 and does not mutate the DB."""
        activity = _make_activity(
            db_session, test_athlete,
            workout_type="easy_run",
            is_race_candidate=False,
            user_verified_race=False,
        )

        resp = client.put(
            f"/v1/activities/{activity.id}/workout-type",
            json={"workout_type": "not_a_real_type"},
            headers=auth_headers,
        )

        assert resp.status_code == 400
        db_session.refresh(activity)
        # DB state must be unchanged
        assert activity.workout_type == "easy_run"
        assert activity.user_verified_race is False
        assert activity.is_race_candidate is False
