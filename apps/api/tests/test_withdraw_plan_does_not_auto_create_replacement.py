from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete, IntakeQuestionnaire, TrainingPlan


client = TestClient(app)


def test_withdrawn_plan_stays_withdrawn_on_calendar_reload():
    db = SessionLocal()
    athlete = None
    try:
        athlete = Athlete(
            email=f"withdraw_{uuid4()}@example.com",
            display_name="Withdraw Test",
            subscription_tier="free",
            role="athlete",
            onboarding_stage="complete",
            onboarding_completed=True,
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        db.add(
            IntakeQuestionnaire(
                athlete_id=athlete.id,
                stage="goals",
                responses={
                    "goal_event_type": "10k",
                    "goal_event_date": (date.today() + timedelta(weeks=8)).isoformat(),
                    "days_per_week": 5,
                    "weekly_mileage_target": 25,
                },
            )
        )

        plan = TrainingPlan(
            athlete_id=athlete.id,
            name="Existing Plan",
            status="active",
            goal_race_date=date.today() + timedelta(weeks=8),
            goal_race_distance_m=10000,
            plan_start_date=date.today(),
            plan_end_date=date.today() + timedelta(weeks=8),
            total_weeks=8,
            plan_type="10k",
            generation_method="framework_v2",
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)

        token = create_access_token({"sub": str(athlete.id), "email": athlete.email, "role": athlete.role})
        headers = {"Authorization": f"Bearer {token}"}

        withdraw = client.post(f"/v2/plans/{plan.id}/withdraw", headers=headers)
        assert withdraw.status_code == 200, withdraw.text

        db.refresh(plan)
        assert plan.status == "archived"

        calendar = client.get("/v1/calendar", headers=headers)
        assert calendar.status_code == 200, calendar.text
        body = calendar.json()
        assert body.get("active_plan") is None

        active = db.query(TrainingPlan).filter(
            TrainingPlan.athlete_id == athlete.id,
            TrainingPlan.status == "active",
        ).all()
        assert active == []
    finally:
        try:
            if athlete is not None:
                for p in db.query(TrainingPlan).filter(TrainingPlan.athlete_id == athlete.id).all():
                    db.delete(p)
                for iq in db.query(IntakeQuestionnaire).filter(IntakeQuestionnaire.athlete_id == athlete.id).all():
                    db.delete(iq)
                athlete = db.query(Athlete).filter(Athlete.id == athlete.id).first()
                if athlete:
                    db.delete(athlete)
                db.commit()
        except Exception:
            db.rollback()
        db.close()
