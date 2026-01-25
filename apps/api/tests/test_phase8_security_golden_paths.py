from __future__ import annotations

import io
import logging
import os
import zipfile
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from core.config import settings
from core.security import create_access_token
from core.database import SessionLocal
from main import app
from models import Athlete, AthleteDataImportJob


client = TestClient(app)


def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def test_admin_endpoints_forbidden_for_non_admin():
    """
    Phase 8 Golden Path 1: Auth boundary.

    As a normal athlete, admin endpoints and legacy Garmin password-connect endpoints
    must not be reachable (403/401/404 depending on gate).
    """
    db = SessionLocal()
    user = None
    try:
        user = Athlete(
            email=f"phase8_user_{uuid4()}@example.com",
            display_name="Phase8 User",
            subscription_tier="free",
            role="athlete",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        headers = _headers(user)

        # Admin endpoints must be blocked.
        resp = client.get("/v1/admin/invites", headers=headers)
        assert resp.status_code in (401, 403)

        resp = client.get("/v1/admin/feature-flags", headers=headers)
        assert resp.status_code in (401, 403)

        resp = client.get("/v1/admin/users", headers=headers)
        assert resp.status_code in (401, 403)

        # Legacy Garmin username/password connect endpoints are admin-only (and also feature-flag gated).
        # Even if the legacy flag is enabled/disabled, a non-admin must not pass the role check.
        resp = client.post(
            "/v1/garmin/connect",
            headers=headers,
            json={"username": "u", "password": "p", "athlete_id": str(user.id)},
        )
        assert resp.status_code in (401, 403, 404)
    finally:
        try:
            if user is not None:
                db.query(Athlete).filter(Athlete.id == user.id).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_no_idor_on_import_jobs():
    """
    Phase 8 Golden Path 2: IDOR boundary.

    Athlete A must not be able to access Athlete B's import job by guessing UUID.
    """
    db = SessionLocal()
    a = None
    b = None
    job = None
    try:
        a = Athlete(email=f"a_{uuid4()}@example.com", display_name="A", subscription_tier="free", role="athlete")
        b = Athlete(email=f"b_{uuid4()}@example.com", display_name="B", subscription_tier="free", role="athlete")
        db.add(a)
        db.add(b)
        db.commit()
        db.refresh(a)
        db.refresh(b)

        job = AthleteDataImportJob(
            athlete_id=b.id,
            provider="garmin",
            status="queued",
            original_filename="garmin_export.zip",
            stored_path="/uploads/imports/placeholder.zip",
            file_size_bytes=1,
            file_sha256="0" * 64,
            stats={},
            error=None,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Owner can fetch.
        resp_ok = client.get(f"/v1/imports/jobs/{job.id}", headers=_headers(b))
        assert resp_ok.status_code == 200, resp_ok.text
        assert resp_ok.json().get("id") == str(job.id)

        # Non-owner must not learn the job exists.
        resp = client.get(f"/v1/imports/jobs/{job.id}", headers=_headers(a))
        assert resp.status_code == 404, resp.text

        # Non-owner must also not see it in the list endpoint.
        resp_list = client.get("/v1/imports/jobs?provider=garmin", headers=_headers(a))
        assert resp_list.status_code == 200, resp_list.text
        jobs = resp_list.json().get("jobs") or []
        assert all(j.get("id") != str(job.id) for j in jobs)
    finally:
        try:
            if job is not None:
                db.query(AthleteDataImportJob).filter(AthleteDataImportJob.id == job.id).delete(synchronize_session=False)
            if a is not None:
                db.query(Athlete).filter(Athlete.id == a.id).delete(synchronize_session=False)
            if b is not None:
                db.query(Athlete).filter(Athlete.id == b.id).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_import_error_no_raw_log_leak(caplog, tmp_path, monkeypatch):
    """
    Phase 8 Golden Path 3: Sensitive logging boundary.

    Force a Garmin DI_CONNECT parse error where the ZIP contains a sentinel string.
    Assert the sentinel does NOT appear in:
    - captured logs
    - AthleteDataImportJob.error (bounded metadata only)
    """
    sentinel = f"SENTINEL_DO_NOT_LEAK_{uuid4()}"

    db = SessionLocal()
    user = None
    job = None
    zip_path = None
    try:
        # Keep this test hermetic: force uploads to a temp dir so we don't rely on /uploads
        # (and so we can clean up easily).
        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(settings, "UPLOADS_DIR", str(uploads_dir))

        user = Athlete(
            email=f"phase8_import_{uuid4()}@example.com",
            display_name="Phase8 Import User",
            subscription_tier="free",
            role="athlete",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Create job first so we can write to its uploads directory.
        job = AthleteDataImportJob(
            athlete_id=user.id,
            provider="garmin",
            status="queued",
            original_filename="garmin_export.zip",
            stored_path=None,
            file_size_bytes=None,
            file_sha256=None,
            stats={},
            error=None,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Write a ZIP containing an invalid summarizedActivities file with sentinel embedded.
        # This should fail JSON parsing without ever logging file contents.
        job_dir = os.path.join(settings.UPLOADS_DIR, "imports", str(job.id))
        os.makedirs(job_dir, exist_ok=True)
        zip_path = os.path.join(job_dir, "garmin_export.zip")

        bad_json = f'{{"this_is_invalid_json": "{sentinel}"'  # missing closing braces
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("DI_CONNECT/DI-Connect-Fitness/bad_summarizedActivities.json", bad_json)

        with open(zip_path, "wb") as f:
            f.write(buf.getvalue())

        job.stored_path = zip_path
        job.file_size_bytes = os.path.getsize(zip_path)
        db.add(job)
        db.commit()

        caplog.set_level(logging.DEBUG)

        from tasks.import_tasks import process_athlete_data_import_job

        with pytest.raises(Exception) as excinfo:
            process_athlete_data_import_job(str(job.id))

        # The exception itself must not include raw uploaded content.
        assert sentinel not in str(excinfo.value)

        # Refresh job and verify bounded error text doesn't include sentinel content.
        db.refresh(job)
        assert job.status == "error"
        assert job.error is not None
        assert sentinel not in (job.error or "")

        # Logs must also not contain sentinel.
        assert sentinel not in caplog.text
    finally:
        try:
            # No explicit FS cleanup needed: uploads_dir is under tmp_path.
            if job is not None:
                db.query(AthleteDataImportJob).filter(AthleteDataImportJob.id == job.id).delete(synchronize_session=False)
            if user is not None:
                db.query(Athlete).filter(Athlete.id == user.id).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        db.close()

