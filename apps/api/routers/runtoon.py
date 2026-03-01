"""
Runtoon API Router

Endpoints:
    Photo management:
        POST   /v1/runtoon/photos           — Upload athlete reference photo
        GET    /v1/runtoon/photos           — List athlete photos (signed URLs)
        DELETE /v1/runtoon/photos/{id}      — Remove a photo (DB + R2)

    Runtoon operations:
        GET    /v1/activities/{id}/runtoon          — Get Runtoon for activity
        POST   /v1/activities/{id}/runtoon/generate — Manual regeneration
        GET    /v1/runtoon/download/{id}            — Signed download URL (1:1 or 9:16)

Privacy invariant: storage keys are NEVER returned in API responses.
All image access is via signed URLs with 15-minute TTL.
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.tier_utils import tier_satisfies
from models import Athlete, AthletePhoto, RuntoonImage, Activity, FeatureFlag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/runtoon", tags=["runtoon"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PHOTO_MAX_BYTES = 7 * 1024 * 1024          # 7 MB
PHOTO_ACCEPTED_TYPES = {"image/jpeg", "image/png", "image/webp"}
PHOTO_MIN = 3
PHOTO_MAX = 10
RUNTOON_PER_ACTIVITY_CAP = 3
SIGNED_URL_TTL = 900  # 15 minutes
DOWNLOAD_SIGNED_URL_TTL = 900


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class PhotoResponse(BaseModel):
    id: UUID
    photo_type: str
    mime_type: str
    size_bytes: int
    signed_url: str
    created_at: datetime

    class Config:
        from_attributes = True


class RuntoonResponse(BaseModel):
    id: UUID
    activity_id: UUID
    signed_url: str
    attempt_number: int
    generation_time_ms: Optional[int]
    cost_usd: Optional[float]
    created_at: datetime
    has_nine_sixteen: bool = True   # Always available if Runtoon exists

    class Config:
        from_attributes = True


class DownloadResponse(BaseModel):
    signed_url: str
    format: str     # "1:1" or "9:16"
    expires_in: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_feature_flag(db: Session, athlete_id) -> bool:
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == "runtoon.enabled").first()
    if not flag or not flag.enabled:
        return False
    if flag.allowed_athlete_ids is None:
        return True
    allowed = flag.allowed_athlete_ids or []
    return str(athlete_id) in [str(a) for a in allowed]


def _require_feature_flag(db: Session, athlete_id) -> None:
    if not _check_feature_flag(db, athlete_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Runtoon is not enabled for your account.",
        )


def _get_storage() -> "storage_service":  # type: ignore[return]
    from services import storage_service
    return storage_service


# ---------------------------------------------------------------------------
# Photo management endpoints
# ---------------------------------------------------------------------------

@router.post("/photos", response_model=PhotoResponse, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    file: UploadFile = File(...),
    photo_type: str = Form(..., description="face | running | full_body | additional"),
    consent_given: bool = Form(..., description="Athlete has agreed to photo use policy"),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload an athlete reference photo for Runtoon generation.

    Consent is required before the upload is accepted.
    Photos are stored in a private R2 bucket under a server-controlled key.
    The response contains a signed URL for preview only (15-min TTL).

    Constraints:
    - Minimum 3, maximum 10 active photos per athlete
    - Max 7 MB per photo
    - Accepted: JPEG, PNG, WebP
    - photo_type: face | running | full_body | additional
    """
    _require_feature_flag(db, current_user.id)

    # Consent gate — required by the data model contract
    if not consent_given:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent is required to upload photos. Set consent_given=true.",
        )

    # Validate photo_type
    valid_types = {"face", "running", "full_body", "additional"}
    if photo_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid photo_type. Must be one of: {', '.join(sorted(valid_types))}",
        )

    # Check format
    content_type = file.content_type or ""
    if content_type not in PHOTO_ACCEPTED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{content_type}'. Accepted: JPEG, PNG, WebP.",
        )

    # Read and size-check
    data = await file.read()
    if len(data) > PHOTO_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({len(data) / 1024 / 1024:.1f} MB). Maximum is 7 MB.",
        )

    # Slot check
    active_count = (
        db.query(sa_func.count(AthletePhoto.id))
        .filter(AthletePhoto.athlete_id == current_user.id, AthletePhoto.is_active == True)
        .scalar()
    ) or 0
    if active_count >= PHOTO_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {PHOTO_MAX} active photos allowed. Delete an existing photo first.",
        )

    # Determine file extension
    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
    ext = ext_map.get(content_type, "jpg")

    # Upload to R2
    photo_id = uuid.uuid4()
    storage_key = f"photos/{current_user.id}/{photo_id}.{ext}"
    storage = _get_storage()
    try:
        storage.upload_file(storage_key, data, content_type)
    except Exception as e:
        logger.error("Photo upload to R2 failed for athlete %s: %s", current_user.id, e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage temporarily unavailable. Please try again.",
        )

    # Write DB record
    photo = AthletePhoto(
        id=photo_id,
        athlete_id=current_user.id,
        storage_key=storage_key,
        photo_type=photo_type,
        mime_type=content_type,
        size_bytes=len(data),
        is_active=True,
        consent_at=datetime.now(tz=timezone.utc),
        consent_version="1.0",
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)

    # Generate signed URL for response preview
    signed_url = storage.generate_signed_url(storage_key, expires_in=SIGNED_URL_TTL)

    logger.info("Photo uploaded: athlete=%s photo_id=%s type=%s", current_user.id, photo_id, photo_type)

    return PhotoResponse(
        id=photo.id,
        photo_type=photo.photo_type,
        mime_type=photo.mime_type,
        size_bytes=photo.size_bytes,
        signed_url=signed_url,
        created_at=photo.created_at,
    )


@router.get("/photos", response_model=List[PhotoResponse])
def list_photos(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the athlete's active reference photos with signed preview URLs."""
    _require_feature_flag(db, current_user.id)

    photos = (
        db.query(AthletePhoto)
        .filter(AthletePhoto.athlete_id == current_user.id, AthletePhoto.is_active == True)
        .order_by(AthletePhoto.created_at)
        .all()
    )

    storage = _get_storage()
    result = []
    for p in photos:
        try:
            signed_url = storage.generate_signed_url(p.storage_key, expires_in=SIGNED_URL_TTL)
        except Exception:
            signed_url = ""
        result.append(
            PhotoResponse(
                id=p.id,
                photo_type=p.photo_type,
                mime_type=p.mime_type,
                size_bytes=p.size_bytes,
                signed_url=signed_url,
                created_at=p.created_at,
            )
        )
    return result


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(
    photo_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a reference photo.
    Marks the DB record is_active=False AND deletes the R2 object.
    Both operations run synchronously to ensure consistency.
    """
    _require_feature_flag(db, current_user.id)

    photo = db.get(AthletePhoto, photo_id)
    if not photo or str(photo.athlete_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found.")
    if not photo.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found.")

    storage_key = photo.storage_key
    photo.is_active = False
    db.commit()

    # Delete from R2 — best-effort (photo is already de-activated in DB)
    try:
        storage = _get_storage()
        storage.delete_file(storage_key)
    except Exception as e:
        logger.warning("R2 delete failed for photo %s: %s (DB already updated)", photo_id, e)

    logger.info("Photo deleted: athlete=%s photo_id=%s", current_user.id, photo_id)


# ---------------------------------------------------------------------------
# Runtoon retrieval endpoints (mounted under /v1/activities/{id}/runtoon)
# These use a separate router prefix to match the activity-centric URL shape.
# ---------------------------------------------------------------------------

activity_router = APIRouter(prefix="/v1/activities", tags=["runtoon"])


@activity_router.get("/{activity_id}/runtoon", response_model=Optional[RuntoonResponse])
def get_runtoon(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the most recent visible Runtoon for an activity.

    Returns null (204-style None) if none exists yet — the frontend polls
    until the image appears or a 90s timeout is hit.

    States the frontend must handle:
    - null → Generating (poll every 5s, timeout 90s) or No photos uploaded
    - RuntoonResponse → Ready
    """
    # Verify activity belongs to this athlete
    activity = db.get(Activity, activity_id)
    if not activity or str(activity.athlete_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")

    runtoon = (
        db.query(RuntoonImage)
        .filter(
            RuntoonImage.activity_id == activity_id,
            RuntoonImage.athlete_id == current_user.id,
            RuntoonImage.is_visible == True,
        )
        .order_by(RuntoonImage.attempt_number.desc())
        .first()
    )

    if not runtoon:
        return None

    storage = _get_storage()
    try:
        signed_url = storage.generate_signed_url(runtoon.storage_key, expires_in=SIGNED_URL_TTL)
    except Exception as e:
        logger.warning("Could not generate signed URL for runtoon %s: %s", runtoon.id, e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Image temporarily unavailable.")

    return RuntoonResponse(
        id=runtoon.id,
        activity_id=runtoon.activity_id,
        signed_url=signed_url,
        attempt_number=runtoon.attempt_number,
        generation_time_ms=runtoon.generation_time_ms,
        cost_usd=float(runtoon.cost_usd) if runtoon.cost_usd else None,
        created_at=runtoon.created_at,
    )


@activity_router.post("/{activity_id}/runtoon/generate", status_code=status.HTTP_202_ACCEPTED)
def trigger_regeneration(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Queue a manual Runtoon regeneration for an activity.

    Rate limits:
    - Max 3 total per activity (1 auto + 2 manual)
    - Max 5/day per athlete
    - Free tier: blocked (regeneration requires Guided+)
    - Entitlement: must be Guided or Premium
    """
    _require_feature_flag(db, current_user.id)

    # Regeneration requires at minimum Guided tier
    if not tier_satisfies(current_user.subscription_tier, "guided"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Runtoon regeneration requires the Guided plan.",
        )

    activity = db.get(Activity, activity_id)
    if not activity or str(activity.athlete_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")

    # Per-activity cap check
    existing_count = (
        db.query(sa_func.count(RuntoonImage.id))
        .filter(
            RuntoonImage.activity_id == activity_id,
            RuntoonImage.athlete_id == current_user.id,
        )
        .scalar()
    ) or 0
    if existing_count >= RUNTOON_PER_ACTIVITY_CAP:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maximum {RUNTOON_PER_ACTIVITY_CAP} Runtoons per activity reached.",
        )

    # Daily cap check
    today_count = (
        db.query(sa_func.count(RuntoonImage.id))
        .filter(
            RuntoonImage.athlete_id == current_user.id,
            RuntoonImage.created_at >= datetime.now(tz=timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
        )
        .scalar()
    ) or 0
    if today_count >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily Runtoon limit (5) reached. Try again tomorrow.",
        )

    # Enqueue
    try:
        from tasks.runtoon_tasks import generate_runtoon_for_activity
        generate_runtoon_for_activity.delay(str(current_user.id), str(activity_id))
        logger.info("Runtoon regen queued: athlete=%s activity=%s", current_user.id, activity_id)
    except Exception as e:
        logger.warning("Failed to queue Runtoon regen: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not queue regeneration. Please try again.",
        )

    return {"queued": True, "message": "Runtoon generation started."}


# ---------------------------------------------------------------------------
# Download endpoint
# ---------------------------------------------------------------------------

@router.get("/download/{runtoon_id}", response_model=DownloadResponse)
def download_runtoon(
    runtoon_id: UUID,
    format: str = Query(default="1:1", description="1:1 (square) or 9:16 (Stories)"),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a fresh signed download URL for a Runtoon image.

    For 9:16 (Stories) format: server-side Pillow recompose using stored
    caption_text + stats_text. No second API call. Recomposed image is
    returned as a signed URL for a freshly-uploaded 9:16 key.

    URL expires in 15 minutes.
    """
    _require_feature_flag(db, current_user.id)

    if format not in ("1:1", "9:16"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="format must be '1:1' or '9:16'",
        )

    runtoon = db.get(RuntoonImage, runtoon_id)
    if not runtoon or str(runtoon.athlete_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Runtoon not found.")

    storage = _get_storage()

    if format == "1:1":
        # Fresh signed URL for the existing 1:1 image
        signed_url = storage.generate_signed_url(runtoon.storage_key, expires_in=DOWNLOAD_SIGNED_URL_TTL)

        # Log download event
        logger.info(
            "ANALYTICS event=runtoon.downloaded athlete=%s runtoon=%s format=1:1",
            current_user.id, runtoon_id,
        )

        return DownloadResponse(signed_url=signed_url, format="1:1", expires_in=DOWNLOAD_SIGNED_URL_TTL)

    # 9:16 recompose
    try:
        # Load 1:1 bytes from R2 via signed URL
        one_by_one_url = storage.generate_signed_url(runtoon.storage_key, expires_in=60)
        import urllib.request
        with urllib.request.urlopen(one_by_one_url, timeout=15) as resp:
            source_bytes = resp.read()

        from services.runtoon_service import recompose_stories
        stories_bytes = recompose_stories(
            source_image_bytes=source_bytes,
            stats_text=runtoon.stats_text or "",
            caption_text=runtoon.caption_text or "",
        )

        # Upload 9:16 version to R2 (ephemeral — keyed by hash so idempotent)
        stories_key = f"runtoons/{runtoon.athlete_id}/{runtoon_id}_916.png"
        storage.upload_file(stories_key, stories_bytes, "image/png")
        signed_url = storage.generate_signed_url(stories_key, expires_in=DOWNLOAD_SIGNED_URL_TTL)

        logger.info(
            "ANALYTICS event=runtoon.downloaded athlete=%s runtoon=%s format=9:16",
            current_user.id, runtoon_id,
        )

        return DownloadResponse(signed_url=signed_url, format="9:16", expires_in=DOWNLOAD_SIGNED_URL_TTL)

    except Exception as e:
        logger.error("9:16 recompose failed for runtoon %s: %s", runtoon_id, e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="9:16 format temporarily unavailable. Use 1:1 instead.",
        )
