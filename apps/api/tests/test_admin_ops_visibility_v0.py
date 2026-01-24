import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, AthleteIngestionState


client = TestClient(app)


@pytest.fixture
def admin_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"admin_ops_{uuid4()}@example.com",
        display_name="Admin",
        subscription_tier="elite",
        role="admin",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()
    return athlete


@pytest.fixture
def admin_headers(admin_user):
    token = create_access_token({"sub": str(admin_user.id)})
    return {"Authorization": f"Bearer {token}"}


def test_ops_queue_snapshot_is_best_effort(admin_headers, monkeypatch):
    # Force celery inspect to "fail" to prove endpoint returns available=false.
    from tasks import celery_app

    class _BadInspect:
        def active(self):
            raise RuntimeError("nope")

    monkeypatch.setattr(celery_app.control, "inspect", lambda timeout=1.0: _BadInspect())

    resp = client.get("/v1/admin/ops/queue", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["active_count"] == 0


def test_ops_ingestion_stuck_and_errors(admin_headers):
    db = SessionLocal()
    try:
        user_ok = Athlete(email=f"ok_{uuid4()}@example.com", display_name="OK", role="athlete", subscription_tier="free")
        user_stuck = Athlete(email=f"stuck_{uuid4()}@example.com", display_name="Stuck", role="athlete", subscription_tier="free")
        db.add_all([user_ok, user_stuck])
        db.commit()
        db.refresh(user_ok)
        db.refresh(user_stuck)

        now = datetime.now(timezone.utc)

        st_ok = AthleteIngestionState(
            athlete_id=user_ok.id,
            provider="strava",
            last_index_status="running",
            last_index_started_at=now - timedelta(minutes=2),
        )
        st_stuck = AthleteIngestionState(
            athlete_id=user_stuck.id,
            provider="strava",
            last_index_status="running",
            last_index_started_at=now - timedelta(minutes=120),
            last_index_error="rate limit",
        )
        db.add_all([st_ok, st_stuck])
        db.commit()
    finally:
        db.close()

    stuck = client.get("/v1/admin/ops/ingestion/stuck?minutes=30", headers=admin_headers)
    assert stuck.status_code == 200
    stuck_data = stuck.json()
    assert stuck_data["count"] == 1
    assert stuck_data["items"][0]["email"] == user_stuck.email

    errs = client.get("/v1/admin/ops/ingestion/errors?days=30", headers=admin_headers)
    assert errs.status_code == 200
    err_data = errs.json()
    assert err_data["count"] >= 1
    assert any(x["email"] == user_stuck.email for x in err_data["items"])

    # Cleanup (non-transactional tests)
    db = SessionLocal()
    try:
        db.query(AthleteIngestionState).filter(AthleteIngestionState.athlete_id.in_([user_ok.id, user_stuck.id])).delete(synchronize_session=False)
        db.query(Athlete).filter(Athlete.id.in_([user_ok.id, user_stuck.id])).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

