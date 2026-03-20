from uuid import uuid4
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete


client = TestClient(app)


def _auth_headers(user_id: str) -> dict:
    token = create_access_token({"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


def test_backfill_progress_endpoint_empty_returns_safe_zero():
    db = SessionLocal()
    athlete = Athlete(
        email=f"progress_empty_{uuid4()}@example.com",
        display_name="Progress Empty",
        subscription_tier="free",
        role="athlete",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()

    redis_client = MagicMock()
    redis_client.hgetall.return_value = {}
    with patch("routers.garmin.get_redis_client", return_value=redis_client):
        resp = client.get("/v1/garmin/backfill-progress", headers=_auth_headers(str(athlete.id)))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "in_progress": False,
        "activities_ingested": 0,
        "health_records_ingested": 0,
        "sweep_complete": False,
        "findings_count": 0,
    }


def test_backfill_progress_endpoint_with_data():
    db = SessionLocal()
    athlete = Athlete(
        email=f"progress_data_{uuid4()}@example.com",
        display_name="Progress Data",
        subscription_tier="free",
        role="athlete",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()

    redis_client = MagicMock()
    redis_client.hgetall.return_value = {
        "activities_ingested": "12",
        "health_records_ingested": "8",
        "sweep_complete": "true",
        "findings_count": "4",
    }
    with patch("routers.garmin.get_redis_client", return_value=redis_client):
        resp = client.get("/v1/garmin/backfill-progress", headers=_auth_headers(str(athlete.id)))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "in_progress": False,
        "activities_ingested": 12,
        "health_records_ingested": 8,
        "sweep_complete": True,
        "findings_count": 4,
    }
