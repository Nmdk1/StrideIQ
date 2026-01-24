from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete, IntakeQuestionnaire, CoachIntentSnapshot, AthleteRaceResultAnchor, AthleteTrainingPaceProfile


client = TestClient(app)


def test_goals_intake_with_recent_race_computes_and_persists_pace_profile_without_mutating_athlete_columns():
    db = SessionLocal()
    athlete = None
    try:
        athlete = Athlete(
            email=f"pace_{uuid4()}@example.com",
            display_name="Pace Tester",
            subscription_tier="free",
            role="athlete",
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        token = create_access_token({"sub": str(athlete.id), "email": athlete.email, "role": athlete.role})
        headers = {"Authorization": f"Bearer {token}"}

        responses = {
            "goal_event_type": "5k",
            "goal_event_date": "2026-03-01",
            "policy_stance": "durability_first",
            "pain_flag": "none",
            "time_available_min": 55,
            "weekly_mileage_target": 35,
            "limiter_primary": "consistency",
            "output_metric_priorities": ["race_time"],
            # Pace calibration anchor (race result only)
            "recent_race_distance": "5k",
            "recent_race_time": "20:00",
            "recent_race_date": "2026-01-10",
        }

        resp = client.post(
            "/v1/onboarding/intake",
            json={"stage": "goals", "responses": responses, "completed": True},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("ok") is True
        assert body.get("status") == "computed"
        assert body.get("pace_profile") is not None
        assert (body.get("pace_profile") or {}).get("paces", {}).get("threshold") is not None

        # DB: anchor persisted
        anchor = db.query(AthleteRaceResultAnchor).filter(AthleteRaceResultAnchor.athlete_id == athlete.id).first()
        assert anchor is not None
        assert anchor.distance_key == "5k"
        assert anchor.time_seconds == 20 * 60

        # DB: pace profile persisted
        prof = db.query(AthleteTrainingPaceProfile).filter(AthleteTrainingPaceProfile.athlete_id == athlete.id).first()
        assert prof is not None
        assert prof.race_anchor_id == anchor.id
        assert prof.paces.get("anchor", {}).get("distance_key") == "5k"
        assert prof.paces.get("paces", {}).get("threshold") is not None

        # Safety: we did NOT mutate Athlete.vdot or Athlete.threshold_pace_per_km in this feature
        db.refresh(athlete)
        assert athlete.vdot is None
        assert athlete.threshold_pace_per_km is None

    finally:
        try:
            if athlete is not None:
                # Best-effort cleanup
                for row in db.query(IntakeQuestionnaire).filter(IntakeQuestionnaire.athlete_id == athlete.id).all():
                    db.delete(row)
                snap = db.query(CoachIntentSnapshot).filter(CoachIntentSnapshot.athlete_id == athlete.id).first()
                if snap:
                    db.delete(snap)
                prof = db.query(AthleteTrainingPaceProfile).filter(AthleteTrainingPaceProfile.athlete_id == athlete.id).first()
                if prof:
                    db.delete(prof)
                anchor = db.query(AthleteRaceResultAnchor).filter(AthleteRaceResultAnchor.athlete_id == athlete.id).first()
                if anchor:
                    db.delete(anchor)
                athlete = db.query(Athlete).filter(Athlete.id == athlete.id).first()
                if athlete:
                    db.delete(athlete)
                db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_goals_intake_without_recent_race_returns_missing_anchor_status():
    db = SessionLocal()
    athlete = None
    try:
        athlete = Athlete(
            email=f"pace_missing_{uuid4()}@example.com",
            display_name="Pace Missing Tester",
            subscription_tier="free",
            role="athlete",
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        token = create_access_token({"sub": str(athlete.id), "email": athlete.email, "role": athlete.role})
        headers = {"Authorization": f"Bearer {token}"}

        responses = {
            "goal_event_type": "5k",
            "goal_event_date": "2026-03-01",
            "policy_stance": "durability_first",
            "pain_flag": "none",
            "time_available_min": 55,
            "weekly_mileage_target": 35,
            "limiter_primary": "consistency",
            "output_metric_priorities": ["race_time"],
        }

        resp = client.post(
            "/v1/onboarding/intake",
            json={"stage": "goals", "responses": responses, "completed": True},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("ok") is True
        assert body.get("status") == "missing_anchor"

        # DB: no anchor/profile rows created
        anchor = db.query(AthleteRaceResultAnchor).filter(AthleteRaceResultAnchor.athlete_id == athlete.id).first()
        prof = db.query(AthleteTrainingPaceProfile).filter(AthleteTrainingPaceProfile.athlete_id == athlete.id).first()
        assert anchor is None
        assert prof is None
    finally:
        try:
            if athlete is not None:
                for row in db.query(IntakeQuestionnaire).filter(IntakeQuestionnaire.athlete_id == athlete.id).all():
                    db.delete(row)
                snap = db.query(CoachIntentSnapshot).filter(CoachIntentSnapshot.athlete_id == athlete.id).first()
                if snap:
                    db.delete(snap)
                athlete = db.query(Athlete).filter(Athlete.id == athlete.id).first()
                if athlete:
                    db.delete(athlete)
                db.commit()
        except Exception:
            db.rollback()
        db.close()

