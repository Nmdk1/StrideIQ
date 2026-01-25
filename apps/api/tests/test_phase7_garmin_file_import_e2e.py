from __future__ import annotations

import io
import json
import os
import zipfile
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app
from core.config import settings
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, AthleteDataImportJob, Activity


client = TestClient(app)


def _ensure_flag_enabled(db) -> None:
    """
    Phase 7 E2E requires the import endpoints to be enabled.
    """
    from services.plan_framework.feature_flags import FeatureFlagService

    key = "integrations.garmin_file_import_v1"
    svc = FeatureFlagService(db)
    if not svc.get_flag(key):
        svc.create_flag(
            key=key,
            name="Garmin file import (v1)",
            enabled=True,
            description="Test flag for Phase 7 E2E",
        )
    else:
        svc.set_flag(key, {"enabled": True})


def _build_minimal_garmin_export_zip_bytes(*, run_activity_id: int, non_run_activity_id: int) -> bytes:
    """
    Build a minimal DI_CONNECT export ZIP with one run + one non-run.
    """
    run_start_gmt_ms = 1700000000000.0  # epoch ms
    payload = [
        {
            "activityId": int(run_activity_id),
            "activityType": "running",
            # Garmin DI_CONNECT key casing
            "startTimeGmt": run_start_gmt_ms,
            "distance": 160934.4,  # cm == 1609.344m
            "duration": 420000.0,  # ms == 420s
        },
        {
            "activityId": int(non_run_activity_id),
            "activityType": "cycling",
            "startTimeGmt": run_start_gmt_ms + 86400000.0,
            "distance": 100000.0,
            "duration": 100000.0,
        },
    ]

    summarized = [{"summarizedActivitiesExport": payload}]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "DI_CONNECT/DI-Connect-Fitness/test_summarizedActivities.json",
            json.dumps(summarized),
        )
    return buf.getvalue()


def test_phase7_e2e_garmin_upload_job_worker_and_idempotent_reimport(monkeypatch):
    """
    Phase 7 E2E Golden Path (API + storage + worker task):

    - enable feature flag
    - create athlete + auth token
    - upload a minimal Garmin export ZIP via /v1/imports/garmin/upload
    - run the worker task synchronously
    - verify job transitions to success and activity is inserted
    - upload the same ZIP again and verify no duplicates / no crash
    """

    db = SessionLocal()
    athlete = None
    created_job_ids: list[str] = []
    try:
        # Ensure uploads directory exists in-container.
        os.makedirs(settings.UPLOADS_DIR, exist_ok=True)

        # Prevent the live celery worker (if running) from racing this test by
        # picking up the queued job. We want a deterministic API->job->worker flow.
        send_calls: list[tuple[tuple, dict]] = []

        def _no_op_send_task(*args, **kwargs):
            send_calls.append((args, kwargs))
            return None

        monkeypatch.setattr("routers.imports.celery_app.send_task", _no_op_send_task)

        _ensure_flag_enabled(db)

        athlete = Athlete(
            email=f"phase7_import_{uuid4()}@example.com",
            display_name="Phase7 Import Athlete",
            subscription_tier="free",
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        headers = {"Authorization": f"Bearer {create_access_token({'sub': str(athlete.id)})}"}

        # Ensure globally-unique external ids so repeat test runs don't collide with the DB-wide
        # unique constraint on (provider, external_activity_id).
        run_id = (uuid4().int % 10**12) + 10**12
        non_run_id = (uuid4().int % 10**12) + 2 * 10**12
        zip_bytes = _build_minimal_garmin_export_zip_bytes(run_activity_id=run_id, non_run_activity_id=non_run_id)

        # --- Upload (job 1) ---
        resp = client.post(
            "/v1/imports/garmin/upload",
            headers=headers,
            files={"file": ("garmin_export.zip", zip_bytes, "application/zip")},
        )
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["id"]
        created_job_ids.append(job_id)

        job = db.query(AthleteDataImportJob).filter(AthleteDataImportJob.id == job_id).first()
        assert job is not None
        assert job.status in ("queued", "running")
        assert job.stored_path and job.stored_path.endswith(".zip")

        # --- Run worker task synchronously ---
        from tasks.import_tasks import process_athlete_data_import_job

        # Call the task function directly (no Celery broker dependency).
        stats = process_athlete_data_import_job(str(job.id))
        assert stats.get("status") == "success"

        db.refresh(job)
        assert job.status == "success"
        assert (job.stats or {}).get("activities_inserted") == 1
        assert (job.stats or {}).get("activities_parsed") == 2

        count = (
            db.query(Activity)
            .filter(Activity.athlete_id == athlete.id, Activity.provider == "garmin")
            .count()
        )
        assert count == 1

        # --- Upload same file again (job 2) ---
        resp2 = client.post(
            "/v1/imports/garmin/upload",
            headers=headers,
            files={"file": ("garmin_export.zip", zip_bytes, "application/zip")},
        )
        assert resp2.status_code == 200, resp2.text
        job2_id = resp2.json()["id"]
        created_job_ids.append(job2_id)

        job2 = db.query(AthleteDataImportJob).filter(AthleteDataImportJob.id == job2_id).first()
        assert job2 is not None
        assert job2.status == "queued"

        stats2 = process_athlete_data_import_job(str(job2.id))
        assert stats2.get("status") == "success"

        db.refresh(job2)
        assert job2.status == "success"
        # Should not create a duplicate.
        assert (job2.stats or {}).get("activities_inserted") == 0
        assert (job2.stats or {}).get("activities_skipped_duplicate") >= 1

        count2 = (
            db.query(Activity)
            .filter(Activity.athlete_id == athlete.id, Activity.provider == "garmin")
            .count()
        )
        assert count2 == 1

    finally:
        # Best-effort cleanup (this test uses SessionLocal and would otherwise leave rows behind).
        try:
            if athlete is not None:
                # Remove activities inserted for this athlete.
                db.query(Activity).filter(Activity.athlete_id == athlete.id).delete(synchronize_session=False)
                # Remove jobs for this athlete (or those we explicitly recorded).
                if created_job_ids:
                    db.query(AthleteDataImportJob).filter(AthleteDataImportJob.id.in_(created_job_ids)).delete(
                        synchronize_session=False
                    )
                db.query(AthleteDataImportJob).filter(AthleteDataImportJob.athlete_id == athlete.id).delete(
                    synchronize_session=False
                )
                # Remove athlete row.
                db.query(Athlete).filter(Athlete.id == athlete.id).delete(synchronize_session=False)
                db.commit()
        except Exception:
            db.rollback()
        db.close()

