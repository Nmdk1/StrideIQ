"""
Activity detail endpoint must surface FIT-derived activity-level metrics
when they are populated, and must omit them (null) when they aren't —
without regressing the rest of the response shape.

This is the contract the new RunDetailsGrid + GarminEffortFallback
components rely on. If this test starts failing, the activity page will
silently lose all running-dynamics / power / Garmin-self-eval cards.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import event
from sqlalchemy.orm import Session

from fastapi.testclient import TestClient

from main import app
from core.database import engine, get_db
from core.security import create_access_token
from models import Activity, Athlete


@pytest.fixture(autouse=True)
def _ensure_encryption_key():
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
    from services.token_encryption import encrypt_token
    athlete = Athlete(
        email=f"fit_detail_{uuid.uuid4()}@example.com",
        display_name="FIT Detail Athlete",
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
    token = create_access_token(data={
        "sub": str(test_athlete.id),
        "email": test_athlete.email,
        "role": "athlete",
    })
    return {"Authorization": f"Bearer {token}"}


def _make_activity(db_session, athlete, **overrides):
    defaults = dict(
        athlete_id=athlete.id,
        provider="garmin",
        external_activity_id=str(uuid.uuid4()),
        name="FIT Run",
        sport="run",
        start_time=datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc),
        distance_m=10000,
        duration_s=3000,
    )
    defaults.update(overrides)
    activity = Activity(**defaults)
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    return activity


class TestActivityDetailFitFields:
    """The activity detail endpoint must expose FIT-derived columns."""

    def test_endpoint_surfaces_all_fit_fields_when_populated(
        self, client, db_session, test_athlete, auth_headers
    ):
        activity = _make_activity(
            db_session,
            test_athlete,
            moving_time_s=2940,
            total_descent_m=152.4,
            avg_power_w=245,
            max_power_w=310,
            avg_stride_length_m=1.18,
            avg_ground_contact_ms=228.0,
            avg_ground_contact_balance_pct=50.4,
            avg_vertical_oscillation_cm=8.6,
            avg_vertical_ratio_pct=7.3,
            garmin_feel="strong",
            garmin_perceived_effort=7,
        )

        resp = client.get(f"/v1/activities/{activity.id}", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        # FIT-derived running dynamics + power.
        assert body["avg_power_w"] == 245
        assert body["max_power_w"] == 310
        assert body["avg_stride_length_m"] == pytest.approx(1.18)
        assert body["avg_ground_contact_ms"] == pytest.approx(228.0)
        assert body["avg_ground_contact_balance_pct"] == pytest.approx(50.4)
        assert body["avg_vertical_oscillation_cm"] == pytest.approx(8.6)
        assert body["avg_vertical_ratio_pct"] == pytest.approx(7.3)
        assert body["total_descent_m"] == pytest.approx(152.4)

        # Garmin self-evaluation (low-confidence fallback only).
        assert body["garmin_feel"] == "strong"
        assert body["garmin_perceived_effort"] == 7

        # Moving time (FIT) must override duration when populated.
        assert body["moving_time_s"] == 2940

    def test_endpoint_returns_nulls_when_fit_fields_missing(
        self, client, db_session, test_athlete, auth_headers
    ):
        """Watch-only / Strava-only activities must return nulls, not 500."""
        activity = _make_activity(db_session, test_athlete)

        resp = client.get(f"/v1/activities/{activity.id}", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        for key in (
            "avg_power_w",
            "max_power_w",
            "avg_stride_length_m",
            "avg_ground_contact_ms",
            "avg_ground_contact_balance_pct",
            "avg_vertical_oscillation_cm",
            "avg_vertical_ratio_pct",
            "total_descent_m",
            "garmin_feel",
            "garmin_perceived_effort",
        ):
            assert key in body, f"missing key {key} in response"
            assert body[key] is None, f"{key} should be null when no FIT data"

        # When moving_time_s isn't populated the API falls back to elapsed
        # time so the UI never displays a blank moving-time card.
        assert body["moving_time_s"] == 3000

    def test_endpoint_falls_back_to_duration_when_moving_time_absent(
        self, client, db_session, test_athlete, auth_headers
    ):
        activity = _make_activity(
            db_session,
            test_athlete,
            duration_s=3600,
            moving_time_s=None,
        )
        resp = client.get(f"/v1/activities/{activity.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["moving_time_s"] == 3600
