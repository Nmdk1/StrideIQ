from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete, IntakeQuestionnaire, TrainingPlan, AthleteRaceResultAnchor


client = TestClient(app)


def test_calendar_does_not_auto_provision_plan_when_onboarding_complete_and_no_active_plan():
    db = SessionLocal()
    athlete = None
    try:
        athlete = Athlete(
            email=f"cal_starter_{uuid4()}@example.com",
            display_name="Calendar Starter",
            subscription_tier="free",
            role="athlete",
            onboarding_stage="complete",
            onboarding_completed=True,
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        # Goals intake exists
        db.add(
            IntakeQuestionnaire(
                athlete_id=athlete.id,
                stage="goals",
                responses={
                    "goal_event_type": "half_marathon",
                    "goal_event_date": "2026-04-11",
                    "days_per_week": 6,
                    "weekly_mileage_target": 40,
                },
            )
        )
        # Race anchor exists -> should yield pace-integrated plan
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

        token = create_access_token({"sub": str(athlete.id), "email": athlete.email, "role": athlete.role})
        headers = {"Authorization": f"Bearer {token}"}

        # Calendar should stay honest: no active plan means no active plan.
        resp = client.get("/v1/calendar", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("active_plan") is None

        # DB: no plan should be created as a side effect of loading calendar.
        plan = db.query(TrainingPlan).filter(TrainingPlan.athlete_id == athlete.id, TrainingPlan.status == "active").first()
        assert plan is None
    finally:
        try:
            if athlete is not None:
                # best-effort cleanup
                for p in db.query(TrainingPlan).filter(TrainingPlan.athlete_id == athlete.id).all():
                    db.delete(p)
                for iq in db.query(IntakeQuestionnaire).filter(IntakeQuestionnaire.athlete_id == athlete.id).all():
                    db.delete(iq)
                for a in db.query(AthleteRaceResultAnchor).filter(AthleteRaceResultAnchor.athlete_id == athlete.id).all():
                    db.delete(a)
                athlete = db.query(Athlete).filter(Athlete.id == athlete.id).first()
                if athlete:
                    db.delete(athlete)
                db.commit()
        except Exception:
            db.rollback()
        db.close()

