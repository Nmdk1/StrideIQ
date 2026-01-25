"""
Phase 7: Provider file import endpoints (Garmin/Coros).

This is the athlete-facing seam for uploading provider exports and tracking import jobs.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.auth import get_current_user
from models import Athlete, AthleteDataImportJob
from schemas import AthleteDataImportJobResponse, AthleteDataImportJobListResponse
from services.plan_framework.feature_flags import FeatureFlagService
from tasks import celery_app


router = APIRouter(prefix="/v1/imports", tags=["imports"])


def _ensure_enabled(db: Session, athlete_id: UUID, flag_key: str) -> None:
    svc = FeatureFlagService(db)
    if not svc.is_enabled(flag_key, athlete_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="feature_disabled")


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "")
    if not base:
        return "upload.zip"
    keep = []
    for ch in base:
        if ch.isalnum() or ch in (".", "_", "-", "@"):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep)[:180]


@router.post("/garmin/upload", response_model=AthleteDataImportJobResponse)
async def upload_garmin_export(
    file: UploadFile = File(...),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a Garmin export zip (extracted and processed asynchronously).
    """
    _ensure_enabled(db, current_user.id, "integrations.garmin_file_import_v1")

    original_filename = _safe_filename(file.filename or "garmin_export.zip")
    if not original_filename.lower().endswith(".zip"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="expected_zip_file")

    job = AthleteDataImportJob(
        athlete_id=current_user.id,
        provider="garmin",
        status="queued",
        original_filename=original_filename,
        stored_path=None,
        file_size_bytes=None,
        file_sha256=None,
        stats={},
        error=None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Store under /uploads/imports/<job_id>/
    job_dir = Path(settings.UPLOADS_DIR) / "imports" / str(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)
    stored_path = job_dir / original_filename

    sha256 = hashlib.sha256()
    total = 0
    try:
        with stored_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.IMPORT_MAX_FILE_BYTES:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file_too_large")
                sha256.update(chunk)
                out.write(chunk)
    finally:
        try:
            await file.close()
        except Exception:
            pass

    job.stored_path = str(stored_path)
    job.file_size_bytes = total
    job.file_sha256 = sha256.hexdigest()
    db.add(job)
    db.commit()
    db.refresh(job)

    # Enqueue async processing
    celery_app.send_task("imports.process_athlete_data_import_job", args=[str(job.id)])

    return job


@router.get("/jobs", response_model=AthleteDataImportJobListResponse)
def list_my_import_jobs(
    provider: Optional[str] = None,
    limit: int = 25,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(AthleteDataImportJob).filter(AthleteDataImportJob.athlete_id == current_user.id)
    if provider:
        q = q.filter(AthleteDataImportJob.provider == provider)
    jobs = q.order_by(AthleteDataImportJob.created_at.desc()).limit(min(max(limit, 1), 200)).all()
    return {"jobs": jobs}


@router.get("/jobs/{job_id}", response_model=AthleteDataImportJobResponse)
def get_my_import_job(
    job_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = (
        db.query(AthleteDataImportJob)
        .filter(AthleteDataImportJob.id == job_id, AthleteDataImportJob.athlete_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    return job

