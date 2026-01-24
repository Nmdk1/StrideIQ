from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete, AthleteRaceResultAnchor, AthleteTrainingPaceProfile
from services.training_pace_profile import RaceAnchor, compute_training_pace_profile


client = TestClient(app)


def test_get_my_training_pace_profile_returns_missing_when_absent():
    db = SessionLocal()
    athlete = None
    try:
        athlete = Athlete(
            email=f"profile_missing_{uuid4()}@example.com",
            display_name="Profile Missing",
            subscription_tier="free",
            role="athlete",
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        token = create_access_token({"sub": str(athlete.id), "email": athlete.email, "role": athlete.role})
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/v1/athletes/me/training-pace-profile", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("status") == "missing"
        assert body.get("pace_profile") is None
    finally:
        try:
            if athlete is not None:
                athlete = db.query(Athlete).filter(Athlete.id == athlete.id).first()
                if athlete:
                    db.delete(athlete)
                db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_get_my_training_pace_profile_returns_computed_profile():
    db = SessionLocal()
    athlete = None
    try:
        athlete = Athlete(
            email=f"profile_{uuid4()}@example.com",
            display_name="Profile Tester",
            subscription_tier="free",
            role="athlete",
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        # Persist anchor + profile directly (unit-level setup)
        anchor = AthleteRaceResultAnchor(
            athlete_id=athlete.id,
            distance_key="5k",
            distance_meters=5000,
            time_seconds=20 * 60,
            source="user",
        )
        db.add(anchor)
        db.flush()

        payload, err = compute_training_pace_profile(RaceAnchor(distance_key="5k", time_seconds=20 * 60))
        assert err is None
        assert payload is not None

        prof = AthleteTrainingPaceProfile(
            athlete_id=athlete.id,
            race_anchor_id=anchor.id,
            fitness_score=float(payload.get("fitness_score")),
            paces=payload,
        )
        db.add(prof)
        db.commit()

        token = create_access_token({"sub": str(athlete.id), "email": athlete.email, "role": athlete.role})
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/v1/athletes/me/training-pace-profile", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("status") == "computed"
        assert (body.get("pace_profile") or {}).get("anchor", {}).get("distance_key") == "5k"
        assert (body.get("pace_profile") or {}).get("paces", {}).get("threshold") is not None
    finally:
        try:
            if athlete is not None:
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

