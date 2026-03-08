from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from core.database import SessionLocal
from main import app
from models import Athlete, IntakeQuestionnaire, TrainingPlan


client = TestClient(app)


def test_marking_onboarding_complete_does_not_create_starter_plan():
    """
    Regression guard: onboarding completion alone must never create a plan.
    """
    email = f"auto_plan_{uuid4()}@example.com"
    password = "SecureP@ss123"

    # Register
    reg = client.post("/v1/auth/register", json={"email": email, "password": password, "display_name": "Auto Plan"})
    assert reg.status_code == 201, reg.text
    token = reg.json().get("access_token")
    assert token
    headers = {"Authorization": f"Bearer {token}"}

    db = SessionLocal()
    try:
        athlete = db.query(Athlete).filter(Athlete.email == email.lower()).first()
        assert athlete is not None

        # Create goals intake row directly (mirrors onboarding flow where intake was saved earlier).
        db.add(
            IntakeQuestionnaire(
                athlete_id=athlete.id,
                stage="goals",
                responses={
                    "goal_event_type": "5k",
                    "goal_event_date": "2026-03-01",
                    "days_per_week": 6,
                    "weekly_mileage_target": 30,
                },
            )
        )
        db.commit()

        # Mark onboarding complete via API. This must not create a plan.
        r = client.put("/v1/athletes/me", json={"onboarding_stage": "complete", "onboarding_completed": True}, headers=headers)
        assert r.status_code == 200, r.text

        # DB: no plan should be created by side effect.
        plan = db.query(TrainingPlan).filter(TrainingPlan.athlete_id == athlete.id).first()
        assert plan is None
    finally:
        try:
            # Cleanup best-effort
            athlete = db.query(Athlete).filter(Athlete.email == email.lower()).first()
            if athlete:
                for p in db.query(TrainingPlan).filter(TrainingPlan.athlete_id == athlete.id).all():
                    db.delete(p)
                for iq in db.query(IntakeQuestionnaire).filter(IntakeQuestionnaire.athlete_id == athlete.id).all():
                    db.delete(iq)
                db.delete(athlete)
                db.commit()
        except Exception:
            db.rollback()
        db.close()

