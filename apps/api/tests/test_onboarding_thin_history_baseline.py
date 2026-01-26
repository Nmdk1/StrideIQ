from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete, IntakeQuestionnaire


client = TestClient(app)


def test_onboarding_status_marks_baseline_needed_when_history_is_thin_and_no_baseline_saved():
    db = SessionLocal()
    athlete = None
    try:
        athlete = Athlete(
            email=f"thin_{uuid4()}@example.com",
            display_name="Thin History",
            subscription_tier="free",
            role="athlete",
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        token = create_access_token({"sub": str(athlete.id), "email": athlete.email, "role": athlete.role})
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/v1/onboarding/status", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("history", {}).get("is_thin") is True
        assert body.get("baseline", {}).get("needed") is True

    finally:
        try:
            if athlete is not None:
                for row in db.query(IntakeQuestionnaire).filter(IntakeQuestionnaire.athlete_id == athlete.id).all():
                    db.delete(row)
                athlete = db.query(Athlete).filter(Athlete.id == athlete.id).first()
                if athlete:
                    db.delete(athlete)
                db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_onboarding_status_clears_baseline_needed_after_baseline_intake_saved():
    db = SessionLocal()
    athlete = None
    try:
        athlete = Athlete(
            email=f"baseline_{uuid4()}@example.com",
            display_name="Baseline User",
            subscription_tier="free",
            role="athlete",
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        token = create_access_token({"sub": str(athlete.id), "email": athlete.email, "role": athlete.role})
        headers = {"Authorization": f"Bearer {token}"}

        # Save baseline intake (completed)
        payload = {
            "stage": "baseline",
            "responses": {
                "runs_per_week_4w": 3,
                "weekly_volume_value": 15,
                "weekly_volume_unit": "miles",
                "longest_run_last_month": 4,
                "longest_run_unit": "miles",
                "returning_from_break": True,
                "return_date_approx": "2026-01-01",
            },
            "completed": True,
        }
        r2 = client.post("/v1/onboarding/intake", json=payload, headers=headers)
        assert r2.status_code == 200, r2.text

        resp = client.get("/v1/onboarding/status", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("history", {}).get("is_thin") is True
        assert body.get("baseline", {}).get("completed") is True
        assert body.get("baseline", {}).get("needed") is False

    finally:
        try:
            if athlete is not None:
                for row in db.query(IntakeQuestionnaire).filter(IntakeQuestionnaire.athlete_id == athlete.id).all():
                    db.delete(row)
                athlete = db.query(Athlete).filter(Athlete.id == athlete.id).first()
                if athlete:
                    db.delete(athlete)
                db.commit()
        except Exception:
            db.rollback()
        db.close()

