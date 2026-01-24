import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import date, datetime, timezone

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, IntakeQuestionnaire, AthleteIngestionState, TrainingPlan


client = TestClient(app)


@pytest.fixture
def admin_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"admin_god_{uuid4()}@example.com",
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


@pytest.fixture
def normal_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"user_god_{uuid4()}@example.com",
        display_name="User",
        subscription_tier="free",
        role="athlete",
        strava_athlete_id=123456,
        last_strava_sync=datetime.now(timezone.utc),
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()
    return athlete


def test_admin_user_detail_includes_god_mode_fields(admin_headers, admin_user, normal_user):
    db = SessionLocal()
    try:
        # Add intake row
        intake = IntakeQuestionnaire(
            athlete_id=normal_user.id,
            stage="goals",
            responses={"time_available_min": 45, "primary_goal": "5k"},
            completed_at=datetime.now(timezone.utc),
        )
        db.add(intake)

        # Add ingestion state row
        ingestion = AthleteIngestionState(
            athlete_id=normal_user.id,
            provider="strava",
            last_index_status="running",
        )
        db.add(ingestion)

        # Add active plan
        plan = TrainingPlan(
            athlete_id=normal_user.id,
            name="Test Plan",
            status="active",
            goal_race_name="Test 5K",
            goal_race_date=date.today(),
            goal_race_distance_m=5000,
            goal_time_seconds=None,
            plan_start_date=date.today(),
            plan_end_date=date.today(),
            total_weeks=1,
            plan_type="5k",
            generation_method="ai",
        )
        db.add(plan)
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/v1/admin/users/{normal_user.id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["id"] == str(normal_user.id)
    assert data["is_blocked"] is False
    assert "integrations" in data
    assert data["integrations"]["strava_athlete_id"] == 123456
    assert "ingestion_state" in data
    assert data["ingestion_state"]["provider"] == "strava"
    assert data["ingestion_state"]["last_index_status"] == "running"
    assert "intake_history" in data
    assert isinstance(data["intake_history"], list)
    assert data["intake_history"][0]["stage"] == "goals"
    assert data["intake_history"][0]["responses"]["primary_goal"] == "5k"
    assert "active_plan" in data
    assert data["active_plan"]["name"] == "Test Plan"

    # Cleanup (non-transactional tests)
    db = SessionLocal()
    try:
        db.query(TrainingPlan).filter(TrainingPlan.athlete_id == normal_user.id).delete()
        db.query(AthleteIngestionState).filter(AthleteIngestionState.athlete_id == normal_user.id).delete()
        db.query(IntakeQuestionnaire).filter(IntakeQuestionnaire.athlete_id == normal_user.id).delete()
        db.query(Athlete).filter(Athlete.id.in_([normal_user.id, admin_user.id])).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

