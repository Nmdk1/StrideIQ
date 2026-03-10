from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from core.database import SessionLocal
from main import app
from models import Athlete


client = TestClient(app)


def test_onboarding_full_flow_register_stage_progression_and_intake_persists():
    """
    End-to-end-ish flow (no UI):
    - Register (should return token + athlete)
    - Progress onboarding stages via PUT /v1/athletes/me
    - Save goals intake via /v1/onboarding/intake
    - Verify /v1/auth/me reflects onboarding stage/completion at each step
    """

    email = f"onboarding_flow_{uuid4()}@example.com"
    password = "SecureP@ss123"
    token = None
    db = SessionLocal()
    try:
        # Register (public signup)
        resp = client.post(
            "/v1/auth/register",
            json={"email": email, "password": password, "display_name": "Flow Tester"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        token = body.get("access_token")
        athlete_id = body.get("athlete", {}).get("id")
        assert token
        assert athlete_id

        headers = {"Authorization": f"Bearer {token}"}

        # Helper: assert auth/me mirrors onboarding fields
        def _assert_me(stage: str | None, completed: bool):
            me = client.get("/v1/auth/me", headers=headers)
            assert me.status_code == 200, me.text
            meb = me.json()
            assert meb.get("onboarding_stage") == stage
            assert bool(meb.get("onboarding_completed")) is bool(completed)

        _assert_me(None, False)

        # Advance stages
        for st in ["basic_profile", "goals"]:
            r = client.put("/v1/athletes/me", json={"onboarding_stage": st}, headers=headers)
            assert r.status_code == 200, r.text
            _assert_me(st, False)

        # Save goals intake (marks completed + seeds intent snapshot)
        responses = {
            "goal_event_type": "5k",
            "goal_event_date": "2026-03-01",
            "policy_stance": "durability_first",
            "pain_flag": "none",
            "time_available_min": 45,
            "weekly_mileage_target": 30,
            "limiter_primary": "consistency",
            "output_metric_priorities": ["race_time", "efficiency_pace_hr"],
        }
        r = client.post(
            "/v1/onboarding/intake",
            json={"stage": "goals", "responses": responses, "completed": True},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        # Readback
        r = client.get("/v1/onboarding/intake?stage=goals", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json().get("responses") == responses

        # Move past Strava stage without connecting (skip)
        for st in ["connect_strava", "nutrition_setup", "work_setup"]:
            r = client.put("/v1/athletes/me", json={"onboarding_stage": st}, headers=headers)
            assert r.status_code == 200, r.text
            _assert_me(st, False)

        # Complete
        r = client.put(
            "/v1/athletes/me",
            json={"onboarding_stage": "complete", "onboarding_completed": True},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        _assert_me("complete", True)

    finally:
        # Best-effort cleanup (suite runs against persistent DB in some envs)
        try:
            if email:
                athlete = db.query(Athlete).filter(Athlete.email == email.lower()).first()
                if athlete:
                    db.delete(athlete)
                db.commit()
        except Exception:
            db.rollback()
        db.close()

