import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import date, timedelta

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, AdminAuditEvent, TrainingPlan, PlannedWorkout, IntakeQuestionnaire, AthleteRaceResultAnchor


client = TestClient(app)


@pytest.fixture
def admin_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"admin_planregen_{uuid4()}@example.com",
        display_name="Admin",
        subscription_tier="pro",
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


def test_admin_can_regenerate_starter_plan_and_audits(admin_headers, admin_user):
    db = SessionLocal()
    athlete = None
    old_plan = None
    try:
        athlete = Athlete(
            email=f"user_planregen_{uuid4()}@example.com",
            display_name="User",
            subscription_tier="free",
            role="athlete",
            onboarding_stage="complete",
            onboarding_completed=True,
            birthdate=date(1985, 1, 1),
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        # Goals intake so ensure_starter_plan can work.
        db.add(
            IntakeQuestionnaire(
                athlete_id=athlete.id,
                stage="goals",
                responses={
                    "goal_event_type": "half_marathon",
                    "goal_event_date": (date.today() + timedelta(weeks=12)).isoformat(),
                    "days_per_week": 6,
                    "weekly_mileage_target": 70,
                },
            )
        )
        # Race anchor so we get paced plan.
        db.add(
            AthleteRaceResultAnchor(
                athlete_id=athlete.id,
                distance_key="5k",
                distance_meters=5000,
                time_seconds=20 * 60,
                source="user",
            )
        )
        db.commit()

        # Seed an existing active plan to prove we archive it.
        old_plan = TrainingPlan(
            athlete_id=athlete.id,
            name="Old Plan",
            status="active",
            goal_race_date=date.today() + timedelta(weeks=12),
            goal_race_distance_m=21097,
            plan_start_date=date.today(),
            plan_end_date=date.today() + timedelta(weeks=12),
            total_weeks=12,
            plan_type="half_marathon",
            generation_method="starter_v1_paced",
        )
        db.add(old_plan)
        db.commit()
        db.refresh(old_plan)
        db.add(
            PlannedWorkout(
                plan_id=old_plan.id,
                athlete_id=athlete.id,
                scheduled_date=date.today() + timedelta(days=1),
                week_number=1,
                day_of_week=1,
                workout_type="easy",
                title="Easy",
                description="",
                phase="base",
            )
        )
        db.commit()

    finally:
        db.close()

    reason = "beta support"
    resp = client.post(
        f"/v1/admin/users/{athlete.id}/plans/starter/regenerate",
        json={"reason": reason},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert str(old_plan.id) in body["archived_plan_ids"]
    assert body["new_plan_id"]

    db = SessionLocal()
    try:
        # Old plan is archived
        old = db.query(TrainingPlan).filter(TrainingPlan.id == old_plan.id).first()
        assert old is not None
        assert old.status == "archived"

        # New plan is active
        new = db.query(TrainingPlan).filter(TrainingPlan.id == body["new_plan_id"]).first()
        assert new is not None
        assert new.status == "active"

        # Audit exists
        ev = (
            db.query(AdminAuditEvent)
            .filter(
                AdminAuditEvent.actor_athlete_id == admin_user.id,
                AdminAuditEvent.target_athlete_id == athlete.id,
                AdminAuditEvent.action == "plan.starter.regenerate",
            )
            .order_by(AdminAuditEvent.created_at.desc())
            .first()
        )
        assert ev is not None
        assert ev.reason == reason
        assert ev.payload["after"]["new_plan_id"] == body["new_plan_id"]
    finally:
        db.close()

