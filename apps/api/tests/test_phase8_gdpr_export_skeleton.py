import json
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from core.security import create_access_token
from core.database import SessionLocal
from main import app
from models import Athlete, TrainingPlan, AthleteDataImportJob


client = TestClient(app)


def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def test_gdpr_export_requires_auth():
    resp = client.get("/v1/gdpr/export")
    assert resp.status_code == 401


def test_gdpr_export_shape_and_no_secrets_leak():
    sentinel = f"SENTINEL_SECRET_{uuid4()}"
    db = SessionLocal()
    user = None
    try:
        user = Athlete(
            email=f"gdpr_{uuid4()}@example.com",
            display_name="GDPR User",
            subscription_tier="free",
            role="athlete",
            strava_access_token=sentinel,
            strava_refresh_token=sentinel,
            garmin_password_encrypted=sentinel,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        resp = client.get("/v1/gdpr/export", headers=_headers(user))
        assert resp.status_code == 200, resp.text
        body = resp.json()

        # Shape
        assert set(body.keys()) == {"metadata", "profile", "counts", "plans_recent", "import_jobs_recent"}
        assert body["metadata"]["athlete_id"] == str(user.id)
        assert body["metadata"]["version"] == "v1_skeleton"
        assert isinstance(body["plans_recent"], list)
        assert isinstance(body["import_jobs_recent"], list)

        # No token/secret keys or values leaked
        blob = json.dumps(body)
        assert sentinel not in blob
        for forbidden_key in (
            "strava_access_token",
            "strava_refresh_token",
            "garmin_password_encrypted",
            "stored_path",
            "file_sha256",
            "password_hash",
        ):
            assert forbidden_key not in blob
    finally:
        try:
            if user is not None:
                db.query(Athlete).filter(Athlete.id == user.id).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_gdpr_export_is_bounded_and_counts_are_total():
    db = SessionLocal()
    user = None
    plan_ids = []
    job_ids = []
    try:
        user = Athlete(
            email=f"gdpr_bounds_{uuid4()}@example.com",
            display_name="GDPR Bounds User",
            subscription_tier="free",
            role="athlete",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Create >25 plans and jobs to validate bounding.
        today = date.today()
        for i in range(30):
            p = TrainingPlan(
                athlete_id=user.id,
                name=f"Plan {i}",
                status="active",
                goal_race_name="Test Race",
                goal_race_date=today + timedelta(days=90),
                goal_race_distance_m=42195,
                plan_start_date=today,
                plan_end_date=today + timedelta(days=90),
                total_weeks=12,
                plan_type="marathon",
                generation_method="template",
            )
            db.add(p)
            db.flush()
            plan_ids.append(p.id)

            j = AthleteDataImportJob(
                athlete_id=user.id,
                provider="garmin",
                status="success",
                original_filename=f"file_{i}.zip",
                stats={
                    "activities_parsed": 2,
                    "activities_inserted": 1,
                    "error_codes": [],
                    # Should never leak from export stats_summary:
                    "raw_file_contents": f"SHOULD_NOT_LEAK_{uuid4()}",
                },
                error=f"SHOULD_NOT_LEAK_{uuid4()}",
            )
            db.add(j)
            db.flush()
            job_ids.append(j.id)

        db.commit()

        resp = client.get("/v1/gdpr/export", headers=_headers(user))
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["counts"]["plans_total"] == 30
        assert body["counts"]["imports_jobs_total"] == 30

        assert len(body["plans_recent"]) == 25
        assert len(body["import_jobs_recent"]) == 25

        # Ensure stats_summary is bounded and doesn't leak raw keys/values.
        blob = json.dumps(body)
        assert "raw_file_contents" not in blob
        assert "SHOULD_NOT_LEAK_" not in blob
        assert '"error"' not in blob  # job.error must not be exposed
    finally:
        try:
            if job_ids:
                db.query(AthleteDataImportJob).filter(AthleteDataImportJob.id.in_(job_ids)).delete(
                    synchronize_session=False
                )
            if plan_ids:
                db.query(TrainingPlan).filter(TrainingPlan.id.in_(plan_ids)).delete(synchronize_session=False)
            if user is not None:
                db.query(Athlete).filter(Athlete.id == user.id).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        db.close()

