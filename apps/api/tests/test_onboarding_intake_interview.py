from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete, IntakeQuestionnaire, CoachIntentSnapshot


client = TestClient(app)


def test_onboarding_intake_upsert_and_readback_seeds_coach_intent_snapshot():
    db = SessionLocal()
    athlete = None
    try:
        athlete = Athlete(
            email=f"intake_{uuid4()}@example.com",
            display_name="Intake Tester",
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
            "pain_flag": "niggle",
            "time_available_min": 55,
            "weekly_mileage_target": 35,
            "limiter_primary": "consistency",
            "output_metric_priorities": ["race_time", "efficiency_pace_hr", "durability"],
        }

        # Save
        resp = client.post("/v1/onboarding/intake", json={"stage": "goals", "responses": responses, "completed": True}, headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json().get("ok") is True

        # Read back
        resp = client.get("/v1/onboarding/intake?stage=goals", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["stage"] == "goals"
        assert body["responses"] == responses

        # DB: intake persisted (single row per stage after upsert cleanup)
        rows = db.query(IntakeQuestionnaire).filter(
            IntakeQuestionnaire.athlete_id == athlete.id,
            IntakeQuestionnaire.stage == "goals",
        ).all()
        assert len(rows) == 1

        # DB: coach intent snapshot seeded with athlete-led priors
        snap = db.query(CoachIntentSnapshot).filter(CoachIntentSnapshot.athlete_id == athlete.id).first()
        assert snap is not None
        assert snap.next_event_type == "5k"
        assert snap.pain_flag == "niggle"
        assert snap.time_available_min == 55
        assert float(snap.weekly_mileage_target) == 35.0
        assert snap.what_feels_off == "consistency"
        assert (snap.extra or {}).get("policy_stance") == "durability_first"
        assert (snap.extra or {}).get("output_metric_priorities") == ["race_time", "efficiency_pace_hr", "durability"]
    finally:
        try:
            if athlete is not None:
                # Best-effort cleanup (some suites run against persistent DB)
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

