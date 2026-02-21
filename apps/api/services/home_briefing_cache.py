"""
Home Briefing Cache Service (ADR-065 / Lane 2A)

Manages the async briefing cache contract:
- Read: fresh / stale / missing / refreshing
- Write: structured payload with metadata
- Dedupe: enqueue cooldown + in-flight lock
- Circuit breaker: stop requeueing after repeated failures

The /v1/home endpoint calls read_briefing_cache() and never blocks on LLM.
The Celery task calls write_briefing_cache() after generating a briefing.
"""

import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from core.cache import get_redis_client

logger = logging.getLogger(__name__)

FRESH_THRESHOLD_S = 15 * 60       # 15 minutes
STALE_MAX_S = 60 * 60             # 60 minutes
CACHE_TTL_S = 3600                # Redis hard expiry
ENQUEUE_COOLDOWN_S = 60           # Min seconds between enqueues per athlete
LOCK_TTL_S = 120                  # In-flight task lock
CIRCUIT_FAILURE_THRESHOLD = 3     # Consecutive failures before circuit opens
CIRCUIT_OPEN_DURATION_S = 15 * 60 # 15 minutes


class BriefingState(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"
    REFRESHING = "refreshing"
    CONSENT_REQUIRED = "consent_required"


def _cache_key(athlete_id: str) -> str:
    return f"home_briefing:{athlete_id}"


def _lock_key(athlete_id: str) -> str:
    return f"home_briefing_lock:{athlete_id}"


def _cooldown_key(athlete_id: str) -> str:
    return f"home_briefing_cooldown:{athlete_id}"


def _circuit_key(athlete_id: str) -> str:
    return f"home_briefing_circuit:{athlete_id}"


def read_briefing_cache(athlete_id: str) -> Tuple[Optional[Dict], BriefingState]:
    """
    Read briefing from Redis cache with staleness semantics.

    Returns (payload_or_none, state).
    Never blocks. Never calls LLM.
    """
    r = get_redis_client()
    if not r:
        return None, BriefingState.MISSING

    try:
        raw = r.get(_cache_key(athlete_id))
    except Exception as e:
        logger.warning(f"Redis read error for home briefing {athlete_id}: {e}")
        return None, BriefingState.MISSING

    if not raw:
        lock_exists = _lock_exists(r, athlete_id)
        state = BriefingState.REFRESHING if lock_exists else BriefingState.MISSING
        return None, state

    try:
        entry = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None, BriefingState.MISSING

    generated_at_str = entry.get("generated_at")
    if not generated_at_str:
        return None, BriefingState.MISSING

    try:
        generated_at = datetime.fromisoformat(generated_at_str)
    except (ValueError, TypeError):
        return None, BriefingState.MISSING

    age_s = (datetime.now(timezone.utc) - generated_at).total_seconds()

    payload = entry.get("payload")

    if age_s < FRESH_THRESHOLD_S:
        return payload, BriefingState.FRESH
    elif age_s < STALE_MAX_S:
        return payload, BriefingState.STALE
    else:
        lock_exists = _lock_exists(r, athlete_id)
        state = BriefingState.REFRESHING if lock_exists else BriefingState.MISSING
        return None, state


def write_briefing_cache(
    athlete_id: str,
    payload: Dict[str, Any],
    source_model: str,
    data_fingerprint: str,
    version: int = 1,
) -> bool:
    """
    Write a generated briefing to Redis cache.
    Called by the Celery task after successful LLM generation.
    """
    r = get_redis_client()
    if not r:
        return False

    from datetime import timedelta

    now = datetime.now(timezone.utc)
    entry = {
        "payload": payload,
        "generated_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=STALE_MAX_S)).isoformat(),
        "source_model": source_model,
        "version": version,
        "data_fingerprint": data_fingerprint,
    }

    key = _cache_key(athlete_id)
    serialized = json.dumps(entry, default=str)
    try:
        r.setex(key, CACHE_TTL_S, serialized)
    except Exception as e:
        logger.error(
            f"Redis setex FAILED for home briefing {athlete_id}: {e}",
            exc_info=True,
        )
        raise RuntimeError(f"Cache write failed for {athlete_id}: {e}") from e

    # Verification read — confirm the key landed in Redis before declaring success.
    # This catches silent write failures (wrong DB, eviction, replication lag).
    try:
        written = r.exists(key)
    except Exception as e:
        logger.error(
            f"Redis verification read FAILED for home briefing {athlete_id}: {e}",
            exc_info=True,
        )
        raise RuntimeError(f"Cache verification failed for {athlete_id}: {e}") from e

    if not written:
        logger.error(
            f"Cache write verification FAILED: key {key} does not exist after setex. "
            f"Possible Redis eviction, wrong DB, or silent failure."
        )
        raise RuntimeError(f"Cache write verification failed for {athlete_id}: key absent after setex")

    logger.info(
        f"Home briefing cached and verified for {athlete_id} "
        f"(model={source_model}, fingerprint={data_fingerprint[:8]}, "
        f"bytes={len(serialized)})"
    )
    return True


def should_enqueue_refresh(athlete_id: str) -> bool:
    """
    Check cooldown + circuit breaker before enqueueing a refresh.
    Returns True if a task should be enqueued.
    """
    r = get_redis_client()
    if not r:
        return False

    try:
        if r.exists(_cooldown_key(athlete_id)):
            logger.debug(f"Home briefing refresh skipped (cooldown): {athlete_id}")
            return False

        if _circuit_is_open(r, athlete_id):
            logger.debug(f"Home briefing refresh skipped (circuit open): {athlete_id}")
            return False

        return True
    except Exception as e:
        logger.warning(f"Enqueue check error for {athlete_id}: {e}")
        return True  # fail open


def set_enqueue_cooldown(athlete_id: str) -> None:
    """Mark that a task was enqueued for this athlete. Prevents rapid re-enqueue."""
    r = get_redis_client()
    if not r:
        return
    try:
        r.setex(_cooldown_key(athlete_id), ENQUEUE_COOLDOWN_S, "1")
    except Exception:
        pass


def acquire_task_lock(athlete_id: str) -> bool:
    """
    Acquire an in-flight lock for this athlete's briefing task.
    Returns True if lock acquired, False if another task is already running.
    """
    r = get_redis_client()
    if not r:
        return True  # fail open

    try:
        acquired = r.set(_lock_key(athlete_id), "1", nx=True, ex=LOCK_TTL_S)
        return bool(acquired)
    except Exception:
        return True  # fail open


def release_task_lock(athlete_id: str) -> None:
    """Release the in-flight lock after task completes."""
    r = get_redis_client()
    if not r:
        return
    try:
        r.delete(_lock_key(athlete_id))
    except Exception:
        pass


def record_task_failure(athlete_id: str) -> None:
    """Record a provider failure. Opens circuit after CIRCUIT_FAILURE_THRESHOLD."""
    r = get_redis_client()
    if not r:
        return
    try:
        key = _circuit_key(athlete_id)
        count = r.incr(key)
        r.expire(key, CIRCUIT_OPEN_DURATION_S)
        if count >= CIRCUIT_FAILURE_THRESHOLD:
            logger.warning(
                f"Home briefing circuit OPEN for {athlete_id} "
                f"after {count} consecutive failures"
            )
    except Exception:
        pass


def reset_circuit(athlete_id: str) -> None:
    """Reset the circuit breaker on successful generation."""
    r = get_redis_client()
    if not r:
        return
    try:
        r.delete(_circuit_key(athlete_id))
    except Exception:
        pass


def _lock_exists(r, athlete_id: str) -> bool:
    try:
        return bool(r.exists(_lock_key(athlete_id)))
    except Exception:
        return False


def _circuit_is_open(r, athlete_id: str) -> bool:
    try:
        count = r.get(_circuit_key(athlete_id))
        return count is not None and int(count) >= CIRCUIT_FAILURE_THRESHOLD
    except Exception:
        return False
