"""
Phase 7: Provider file import tasks (Garmin/Coros).

This module runs in the Celery worker.
"""

from __future__ import annotations

import hashlib
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from core.config import settings
from core.database import get_db_sync
from tasks import celery_app
from models import AthleteDataImportJob
from services.ingestion_state import mark_index_error, mark_index_finished, mark_index_started
from services.provider_import.garmin_di_connect import import_garmin_di_connect_summaries


IMPORTS_DIRNAME = "imports"
# Extraction cap (independent from upload byte cap) to protect worker from zip bombs.
MAX_EXTRACTED_BYTES = max(settings.IMPORT_MAX_FILE_BYTES * 20, 250 * 1024 * 1024)  # min 250MB, default ~1.5GB


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_extract_zip(zip_path: Path, dest_dir: Path) -> Dict[str, Any]:
    """
    Extract zip safely:
    - prevent zip-slip
    - cap total uncompressed size
    """
    zip_path = Path(zip_path)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    total_uncompressed = 0
    extracted_files = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        infos = zf.infolist()
        for info in infos:
            # Directory entries are fine.
            if info.is_dir():
                continue
            total_uncompressed += int(info.file_size or 0)
            if total_uncompressed > MAX_EXTRACTED_BYTES:
                raise ValueError("zip_extraction_exceeds_limit")

        for info in infos:
            name = info.filename
            # Zip paths use '/' separators.
            if not name or name.endswith("/"):
                continue
            out_path = (dest_dir / name).resolve()
            if not str(out_path).startswith(str(dest_dir.resolve())):
                raise ValueError("zip_slip_detected")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, out_path.open("wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
            extracted_files += 1

    return {"extracted_files": extracted_files, "extracted_bytes": total_uncompressed}


@celery_app.task(name="imports.process_athlete_data_import_job")
def process_athlete_data_import_job(job_id: str) -> Dict[str, Any]:
    """
    Process a single AthleteDataImportJob.

    This task is intentionally deterministic and bounded. It should never log raw file data.
    """
    db = get_db_sync()
    try:
        job_uuid = UUID(job_id)
        job: Optional[AthleteDataImportJob] = db.query(AthleteDataImportJob).filter_by(id=job_uuid).first()
        if not job:
            return {"status": "error", "error": "job_not_found"}

        # Mark running
        job.status = "running"
        job.started_at = _utcnow()
        job.finished_at = None
        job.error = None
        db.add(job)
        db.commit()

        # Durable ingestion state (ops surface)
        try:
            mark_index_started(db, job.athlete_id, provider=job.provider, task_id=str(process_athlete_data_import_job.request.id))
            db.commit()
        except Exception:
            db.rollback()

        stored = Path(job.stored_path or "")
        if not stored.exists():
            raise FileNotFoundError("stored_file_missing")

        extracted_root = stored
        extraction_stats: Dict[str, Any] = {}

        if stored.suffix.lower() == ".zip":
            extract_dir = Path(settings.UPLOADS_DIR) / IMPORTS_DIRNAME / str(job.id) / "extracted"
            extraction_stats = _safe_extract_zip(stored, extract_dir)
            extracted_root = extract_dir

        if job.provider == "garmin":
            stats = import_garmin_di_connect_summaries(db, athlete_id=job.athlete_id, extracted_root_dir=extracted_root)
        else:
            raise ValueError("unsupported_provider")

        # Merge extraction stats + import stats (bounded)
        merged_stats = dict(stats or {})
        if extraction_stats:
            merged_stats["extraction"] = extraction_stats

        job.status = "success"
        job.finished_at = _utcnow()
        job.stats = merged_stats
        db.add(job)
        db.commit()

        try:
            mark_index_finished(db, job.athlete_id, provider=job.provider, result=merged_stats)
            db.commit()
        except Exception:
            db.rollback()

        return merged_stats
    except Exception as e:
        # Best-effort write job error
        try:
            job_uuid = UUID(job_id)
            job = db.query(AthleteDataImportJob).filter_by(id=job_uuid).first()
            if job:
                job.status = "error"
                job.finished_at = _utcnow()
                job.error = str(e)[:4000]
                db.add(job)
                db.commit()
        except Exception:
            db.rollback()

        try:
            if "job" in locals() and job:
                mark_index_error(db, job.athlete_id, provider=job.provider, error=str(e)[:4000])
                db.commit()
        except Exception:
            db.rollback()
        raise
    finally:
        db.close()

