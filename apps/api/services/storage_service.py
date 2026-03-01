"""
Cloudflare R2 Object Storage — private bucket for Runtoon photos and images.

Privacy invariant (platform-wide, non-negotiable):
    ALL athlete data is private by default. Every R2 bucket is private.
    Storage keys (object paths) are NEVER returned directly to clients.
    All client access is via signed URLs with a 15-minute TTL generated
    server-side for the authenticated athlete's own data only.

Three operations:
    upload_file(key, data, content_type)  → None
    generate_signed_url(key, expires_in)  → str   (15-min TTL default)
    delete_file(key)                      → None

Key structure:
    photos/{athlete_id}/{photo_id}.{ext}       — athlete reference photos
    runtoons/{athlete_id}/{runtoon_id}.png     — generated Runtoon images

Dependencies:
    boto3 — S3-compatible client (Cloudflare R2 uses S3 API)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Guard import so the module can be imported in environments without boto3
# (e.g., unit tests that mock the storage interface).
try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment,misc]
    BotoCoreError = Exception  # type: ignore[assignment]
    BOTO3_AVAILABLE = False

_client = None  # module-level singleton; created lazily


def _get_client():
    """Return (or create) the boto3 S3 client for Cloudflare R2."""
    global _client
    if _client is not None:
        return _client

    if not BOTO3_AVAILABLE:
        raise RuntimeError(
            "boto3 is not installed. Add it to requirements.txt and rebuild."
        )

    from core.config import settings

    if not all([settings.R2_ACCESS_KEY_ID, settings.R2_SECRET_ACCESS_KEY, settings.R2_ENDPOINT_URL]):
        raise RuntimeError(
            "R2 credentials not configured. "
            "Set R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL in env."
        )

    _client = boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",  # R2 uses "auto" for region
    )
    logger.info("R2 storage client initialised (endpoint=%s)", settings.R2_ENDPOINT_URL)
    return _client


def get_bucket_name() -> str:
    from core.config import settings
    return settings.R2_BUCKET_NAME


def upload_file(key: str, data: bytes, content_type: str) -> None:
    """
    Upload bytes to R2 under the given key.

    Args:
        key:          R2 object key (e.g., "photos/{athlete_id}/{photo_id}.jpg")
        data:         Raw bytes to store
        content_type: MIME type (e.g., "image/jpeg", "image/png")

    Raises:
        RuntimeError: If R2 credentials are missing.
        ClientError:  If the upload fails at the storage layer.
    """
    client = _get_client()
    bucket = get_bucket_name()
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        logger.info("R2 upload: key=%s size=%d", key, len(data))
    except (ClientError, BotoCoreError) as exc:
        logger.error("R2 upload failed: key=%s error=%s", key, exc)
        raise


def generate_signed_url(key: str, expires_in: int = 900) -> str:
    """
    Generate a pre-signed GET URL for a private R2 object.

    The URL expires after ``expires_in`` seconds (default 900 = 15 minutes).
    This is the ONLY way client code should access R2 objects — never return
    the raw storage key or construct bucket URLs directly.

    Args:
        key:        R2 object key
        expires_in: TTL in seconds (default 900 = 15 min)

    Returns:
        Pre-signed HTTPS URL valid for ``expires_in`` seconds.

    Raises:
        RuntimeError: If R2 credentials are missing.
        ClientError:  If URL generation fails.
    """
    client = _get_client()
    bucket = get_bucket_name()
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        logger.debug("R2 signed URL generated: key=%s ttl=%ds", key, expires_in)
        return url
    except (ClientError, BotoCoreError) as exc:
        logger.error("R2 signed URL failed: key=%s error=%s", key, exc)
        raise


def delete_file(key: str) -> None:
    """
    Delete an object from R2.

    Used when:
    - Athlete deletes a photo (DELETE /v1/runtoon/photos/{id})
    - Athlete deletes their account (cascade via GDPR/account deletion task)

    Silently succeeds if the object does not exist (idempotent).

    Args:
        key: R2 object key to delete.

    Raises:
        RuntimeError: If R2 credentials are missing.
        ClientError:  If deletion fails at the storage layer (not 404).
    """
    client = _get_client()
    bucket = get_bucket_name()
    try:
        client.delete_object(Bucket=bucket, Key=key)
        logger.info("R2 delete: key=%s", key)
    except (ClientError, BotoCoreError) as exc:
        # 404 / NoSuchKey is not an error — object was already gone.
        error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if error_code == "NoSuchKey":
            logger.debug("R2 delete: key=%s already absent (NoSuchKey)", key)
            return
        logger.error("R2 delete failed: key=%s error=%s", key, exc)
        raise
