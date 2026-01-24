from __future__ import annotations

from uuid import uuid4

from core.database import SessionLocal
from models import Athlete, TrainingPlan, AthleteRaceResultAnchor, IntakeQuestionnaire
from services.starter_plan import ensure_starter_plan


def test_existing_effort_starter_plan_is_upgraded_to_paced_when_race_anchor_exists():
    db = SessionLocal()
    athlete = None
    try:
        athlete = Athlete(
            email=f"upgrade_{uuid4()}@example.com",
            display_name="Upgrade Starter",
            subscription_tier="free",
            role="athlete",
            onboarding_completed=True,
            onboarding_stage="complete",
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
                    "goal_event_type": "5k",
                    "goal_event_date": "2026-03-01",
                    "days_per_week": 6,
                    "weekly_mileage_target": 30,
                },
            )
        )
        # Existing old starter plan (effort-based)
        db.add(
            TrainingPlan(
                athlete_id=athlete.id,
                name="Old Starter",
                status="active",
                goal_race_date="2026-03-01",
                goal_race_distance_m=5000,
                plan_start_date="2026-01-01",
                plan_end_date="2026-03-01",
                total_weeks=8,
                plan_type="5k",
                generation_method="starter_v1",
            )
        )
        # Race anchor exists now
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

        created = ensure_starter_plan(db, athlete=athlete)
        assert created is not None

        active = db.query(TrainingPlan).filter(TrainingPlan.athlete_id == athlete.id, TrainingPlan.status == "active").all()
        assert len(active) == 1
        assert active[0].generation_method == "starter_v1_paced"

        archived = db.query(TrainingPlan).filter(TrainingPlan.athlete_id == athlete.id, TrainingPlan.status == "archived").all()
        assert len(archived) == 1
        assert archived[0].generation_method == "starter_v1"
    finally:
        try:
            if athlete is not None:
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

