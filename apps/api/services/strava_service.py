import os
import time
import requests
from dataclasses import dataclass
from typing import Optional, Dict, List
from dotenv import load_dotenv

load_dotenv()

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REDIRECT_URI = os.getenv(
    "STRAVA_REDIRECT_URI",
    "http://localhost:8000/v1/strava/callback",
)
STRAVA_API_BASE = "https://www.strava.com/api/v3"


class StravaOAuthCapacityError(RuntimeError):
    """
    Raised when the Strava OAuth app has reached its connected-athlete capacity.
    """


def _looks_like_capacity_error(payload: dict | None) -> bool:
    try:
        p = payload or {}
        msg = " ".join(
            [
                str(p.get("message") or ""),
                str(p.get("error") or ""),
                str(p.get("errors") or ""),
            ]
        ).lower()
        # Strava community reports multiple strings for athlete-capacity limits, including:
        # - "Limit of connected athletes exceeded"
        # - "Too many athletes"
        # - "Too many accounts on that key"
        if "too many accounts" in msg and ("key" in msg or "client" in msg):
            return True
        if "connected" in msg and ("athlete" in msg or "athletes" in msg) and ("limit" in msg or "exceeded" in msg):
            return True
        if ("limit" in msg or "exceeded" in msg) and ("athlete" in msg or "athletes" in msg):
            return True
        if "too many" in msg and ("athlete" in msg or "athletes" in msg or "account" in msg or "accounts" in msg):
            return True
        return False
    except Exception:
        return False


def _acquire_strava_detail_slot(timeout_s: int, poll_s: float) -> bool:
    """
    Global throttle for Strava activity detail fetches (viral-safe scaling).

    This caps concurrent calls to `/activities/{id}` across all workers using Redis.
    If Redis is unavailable, we degrade gracefully (no throttle).
    """
    from core.cache import get_redis_client
    from core.config import settings

    client = get_redis_client()
    if not client:
        return True

    key = "throttle:strava:activity_details:inflight"
    limit = max(1, int(settings.STRAVA_DETAIL_FETCH_CONCURRENCY))
    ttl_s = max(30, int(timeout_s) + 30)  # safety TTL in case a worker dies mid-request

    # Lua: increment, enforce limit, set expiry once.
    acquire_lua = """
    local key = KEYS[1]
    local limit = tonumber(ARGV[1])
    local ttl = tonumber(ARGV[2])
    local v = redis.call('INCR', key)
    if v == 1 then
      redis.call('EXPIRE', key, ttl)
    end
    if v > limit then
      redis.call('DECR', key)
      return 0
    end
    return v
    """

    deadline = time.time() + max(1, int(timeout_s))
    while time.time() < deadline:
        try:
            v = client.eval(acquire_lua, 1, key, str(limit), str(ttl_s))
            if int(v) > 0:
                return True
        except Exception:
            # If Redis misbehaves, prefer availability over throttling.
            return True
        time.sleep(max(0.1, float(poll_s)))
    return False


def _release_strava_detail_slot() -> None:
    from core.cache import get_redis_client

    client = get_redis_client()
    if not client:
        return

    key = "throttle:strava:activity_details:inflight"
    release_lua = """
    local key = KEYS[1]
    local v = redis.call('GET', key)
    if not v then
      return 0
    end
    v = tonumber(v)
    if v <= 1 then
      redis.call('DEL', key)
      return 0
    end
    local nv = redis.call('DECR', key)
    if nv <= 0 then
      redis.call('DEL', key)
      return 0
    end
    return nv
    """
    try:
        client.eval(release_lua, 1, key)
    except Exception:
        # Best-effort release only.
        return


# Strava OAuth scopes requested by StrideIQ
# See: https://developers.strava.com/docs/authentication/
#
# Core scopes for training analysis:
#   - read: Read public segments, routes, profile
#   - read_all: Access private activities and full profile
#   - activity:read_all: Access all activities (including private)
#   - profile:read_all: Read detailed athlete profile (zones, FTP, weight)
#
# Optional future scopes (not yet requested):
#   - activity:write: Upload activities (manual entry feature)
#   - profile:write: Update athlete profile
#
STRAVA_SCOPES = "read,read_all,activity:read_all,profile:read_all"


def get_auth_url(state: str | None = None) -> str:
    if not STRAVA_CLIENT_ID:
        raise ValueError("STRAVA_CLIENT_ID is not set")

    params = {
        "client_id": STRAVA_CLIENT_ID,
        "redirect_uri": STRAVA_REDIRECT_URI,
        "response_type": "code",
        "scope": STRAVA_SCOPES,
        "approval_prompt": "force",
    }
    if state:
        params["state"] = state

    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://www.strava.com/oauth/authorize?{query}"


def exchange_code_for_token(code: str) -> Dict:
    url = "https://www.strava.com/oauth/token"
    data = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }

    r = requests.post(url, json=data)
    if r.status_code >= 400:
        try:
            payload = r.json()
        except Exception:
            payload = {"message": r.text}
        if r.status_code == 403 and _looks_like_capacity_error(payload):
            raise StravaOAuthCapacityError(str(payload.get("message") or "Limit of connected athletes exceeded"))
        r.raise_for_status()
    return r.json()


def refresh_access_token(refresh_token: str) -> Dict:
    """
    Exchange a refresh token for a new access token from Strava.
    
    Returns dict with: access_token, refresh_token, expires_at, expires_in, token_type
    Raises requests.HTTPError on failure (e.g. 400 = truly revoked).
    """
    url = "https://www.strava.com/oauth/token"
    data = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    r = requests.post(url, json=data)
    r.raise_for_status()
    return r.json()


def ensure_fresh_token(athlete, db) -> bool:
    """
    Pre-flight check: refresh the Strava access token if it expires within 5 minutes.
    
    Call this before any Strava API request to avoid 401 errors.
    Returns True if token is fresh (or was refreshed), False if refresh failed.
    Commits to DB on success.
    """
    import logging
    from datetime import datetime, timezone as tz, timedelta
    from services.token_encryption import decrypt_token, encrypt_token

    logger = logging.getLogger(__name__)

    if not athlete.strava_access_token or not athlete.strava_refresh_token:
        return False

    # If we don't have expires_at stored, skip pre-flight (will rely on 401 reactive refresh)
    expires_at = getattr(athlete, "strava_token_expires_at", None)
    if expires_at is None:
        return True  # Can't check, assume OK

    now = datetime.now(tz.utc)
    # Refresh if token expires within 5 minutes
    if expires_at > now + timedelta(minutes=5):
        return True  # Token still fresh

    try:
        raw_refresh = decrypt_token(athlete.strava_refresh_token)
        if not raw_refresh:
            return False

        token_data = refresh_access_token(raw_refresh)

        athlete.strava_access_token = encrypt_token(token_data["access_token"])
        if token_data.get("refresh_token"):
            athlete.strava_refresh_token = encrypt_token(token_data["refresh_token"])
        if token_data.get("expires_at"):
            athlete.strava_token_expires_at = datetime.fromtimestamp(
                token_data["expires_at"], tz=tz.utc
            )
        db.commit()
        logger.info(f"Pre-flight token refresh successful for athlete {athlete.id}")
        return True
    except Exception as e:
        logger.warning(f"Pre-flight token refresh failed for athlete {athlete.id}: {e}")
        return False


class StravaRateLimitError(RuntimeError):
    def __init__(self, message: str, *, retry_after_s: int):
        super().__init__(message)
        self.retry_after_s = int(retry_after_s)


@dataclass
class StreamFetchResult:
    """Typed result from get_activity_streams() to distinguish failure modes.

    Outcomes:
        "success"          — data is populated; store and mark success
        "unavailable"      — Strava confirms no streams (404, empty); terminal
        "failed"           — transient/parse error; increment retry, re-eligible
        "skipped_no_redis" — Redis down; revert to pending, leave for backfill
    """
    outcome: str          # "success" | "unavailable" | "failed" | "skipped_no_redis"
    data: Optional[Dict] = None
    error: Optional[str] = None


def poll_activities_page(
    athlete,
    after_timestamp: Optional[int] = None,
    before_timestamp: Optional[int] = None,
    page: int = 1,
    per_page: int = 200,
    max_retries: int = 3,
    allow_rate_limit_sleep: bool = True,
) -> List[Dict]:
    """
    Poll ONE page of activities from Strava with rate limiting and retry logic.
    """
    from services.token_encryption import decrypt_token
    
    # Decrypt access token
    access_token = decrypt_token(athlete.strava_access_token)
    if not access_token:
        raise ValueError("Failed to decrypt Strava access token")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"per_page": int(per_page), "page": int(page)}

    # Optional filters
    if after_timestamp is not None and after_timestamp > 0:
        params["after"] = int(after_timestamp)
        print(f"DEBUG: poll_activities - adding 'after' param: {params['after']}")
    if before_timestamp is not None and before_timestamp > 0:
        params["before"] = int(before_timestamp)

    print(f"DEBUG: poll_activities_page - params: {params}")

    print(f"DEBUG: poll_activities - request params: {params}")
    url = f"{STRAVA_API_BASE}/athlete/activities"
    
    for attempt in range(max_retries):
        # Global rate budget (ADR-063): every HTTP request checks budget
        budget = acquire_strava_read_budget()
        if budget is False:
            if not allow_rate_limit_sleep:
                raise StravaRateLimitError(
                    "Rate budget exhausted for poll_activities_page",
                    retry_after_s=900,
                )
            window_remaining = 900 - (int(time.time()) % 900)
            print(f"DEBUG: poll budget exhausted, sleeping {window_remaining}s")
            time.sleep(window_remaining)
            # Re-check after sleep
            budget = acquire_strava_read_budget()
            if not budget:
                raise StravaRateLimitError(
                    "Rate budget still exhausted after window rollover",
                    retry_after_s=900,
                )
        # budget is None (Redis down): fall through for existing paths (degraded mode)

        try:
            r = requests.get(url, headers=headers, params=params)
            print(f"DEBUG: poll_activities - response status: {r.status_code}")

            # Handle rate limiting (429 Too Many Requests)
            if r.status_code == 429:
                retry_after = int(r.headers.get('Retry-After', 60 * (2 ** attempt)))  # Default: 60s, 120s, 240s
                if not allow_rate_limit_sleep:
                    raise StravaRateLimitError(
                        f"429 Rate limited for poll_activities_page (Retry-After {retry_after}s)",
                        retry_after_s=retry_after,
                    )
                print(f"DEBUG: Rate limited (429) on poll_activities_page, waiting {retry_after}s before retry {attempt + 1}/{max_retries}")
                time.sleep(retry_after)
                continue

            # Handle token refresh (401 Unauthorized)
            if r.status_code == 401 and athlete.strava_refresh_token:
                from services.token_encryption import decrypt_token, encrypt_token
                print(f"DEBUG: Token expired, refreshing for poll_activities")
                refresh_token = decrypt_token(athlete.strava_refresh_token)
                if refresh_token:
                    token = refresh_access_token(refresh_token)
                    # Encrypt new tokens
                    athlete.strava_access_token = encrypt_token(token["access_token"])
                    if token.get("refresh_token"):
                        athlete.strava_refresh_token = encrypt_token(token["refresh_token"])
                    if token.get("expires_at"):
                        from datetime import datetime, timezone as tz
                        athlete.strava_token_expires_at = datetime.fromtimestamp(
                            token["expires_at"], tz=tz.utc
                        )
                    # Update headers with decrypted token
                    access_token = decrypt_token(athlete.strava_access_token)
                    headers["Authorization"] = f"Bearer {access_token}"
                    continue

            r.raise_for_status()
            activities = r.json()
            print(f"DEBUG: poll_activities_page - raw response count: {len(activities) if isinstance(activities, list) else 'not a list'}")
            return activities if isinstance(activities, list) else []
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                # Last attempt failed, raise the exception
                print(f"ERROR: Failed to poll activities after {max_retries} attempts: {e}")
                raise
            # Wait before retrying
            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            print(f"DEBUG: Error polling activities, retrying in {wait_time}s...")
            time.sleep(wait_time)
    
    # Should never reach here, but just in case
    raise Exception("Failed to poll activities after all retries")


def poll_activities(
    athlete,
    after_timestamp: Optional[int] = None,
    max_retries: int = 3,
    allow_rate_limit_sleep: bool = True,
) -> List[Dict]:
    """
    Backwards-compatible wrapper for polling the first page of activities.
    """
    # Preserve the old "use last_strava_sync if not provided" behavior.
    if after_timestamp is None and getattr(athlete, "last_strava_sync", None):
        after_timestamp = int(athlete.last_strava_sync.timestamp())
    return poll_activities_page(
        athlete,
        after_timestamp=after_timestamp,
        before_timestamp=None,
        page=1,
        per_page=200,
        max_retries=max_retries,
        allow_rate_limit_sleep=allow_rate_limit_sleep,
    )


def acquire_strava_read_budget(window_budget: int = 100) -> Optional[bool]:
    """
    Global rate limiter for ALL Strava API reads (ADR-063 Decision 4).

    App-wide sliding window aligned to Strava's 15-min boundaries.
    Every Strava read path (poll, details, laps, streams) MUST call this
    before making an HTTP request — including retries.

    Returns:
        True  — read allowed, budget decremented
        False — budget exhausted for current window, caller must wait or defer
        None  — Redis unavailable, caller must apply degraded-mode policy:
                 - Streams: skip fetch entirely (leave pending for backfill)
                 - Existing paths: fall through (existing behavior)
    """
    from core.cache import get_redis_client

    client = get_redis_client()
    if not client:
        return None  # Redis down — caller applies degraded-mode policy

    window_id = int(time.time()) // 900  # 15-min window aligned to Strava boundaries
    key = f"strava:rate:global:window:{window_id}"
    ttl = 1200  # 20 min (15-min window + 5-min buffer)

    acquire_lua = """
    local key = KEYS[1]
    local limit = tonumber(ARGV[1])
    local ttl = tonumber(ARGV[2])
    local current = tonumber(redis.call("GET", key) or "0")
    if current >= limit then
        return 0
    end
    redis.call("INCR", key)
    if current == 0 then
        redis.call("EXPIRE", key, ttl)
    end
    return 1
    """

    try:
        result = client.eval(acquire_lua, 1, key, str(window_budget), str(ttl))
        return int(result) == 1
    except Exception:
        # Redis misbehaving — treat as unavailable
        return None


def get_strava_read_budget_remaining(window_budget: int = 100) -> Optional[int]:
    """
    Read the number of budget tokens remaining in the current 15-min window.

    Returns:
        int  — tokens remaining (0..window_budget)
        None — Redis unavailable
    """
    from core.cache import get_redis_client

    client = get_redis_client()
    if not client:
        return None

    window_id = int(time.time()) // 900
    key = f"strava:rate:global:window:{window_id}"

    try:
        current = client.get(key)
        used = int(current) if current else 0
        return max(0, window_budget - used)
    except Exception:
        return None


def get_activity_details(
    athlete,
    activity_id: int,
    max_retries: int = 3,
    allow_rate_limit_sleep: bool = True,
) -> Optional[Dict]:
    """
    Get detailed activity information including best efforts.
    Includes retry logic for rate limiting.
    """
    from services.token_encryption import decrypt_token
    
    # Decrypt access token
    access_token = decrypt_token(athlete.strava_access_token)
    if not access_token:
        return None
    
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{STRAVA_API_BASE}/activities/{activity_id}"
    # IMPORTANT: Strava will omit `best_efforts` unless include_all_efforts is enabled.
    # We rely on best_efforts for PB correctness, so request them explicitly.
    params = {"include_all_efforts": "true"}
    
    # Global throttle: cap concurrent detail fetches so viral spikes queue instead of melting.
    from core.config import settings
    acquired = _acquire_strava_detail_slot(
        timeout_s=int(settings.STRAVA_DETAIL_FETCH_ACQUIRE_TIMEOUT_S),
        poll_s=float(settings.STRAVA_DETAIL_FETCH_ACQUIRE_POLL_S),
    )
    if not acquired:
        return None

    try:
        for attempt in range(max_retries):
            # Global rate budget (ADR-063): every HTTP request checks budget
            budget = acquire_strava_read_budget()
            if budget is False:
                if not allow_rate_limit_sleep:
                    raise StravaRateLimitError(
                        f"Rate budget exhausted for activity details {activity_id}",
                        retry_after_s=900,
                    )
                window_remaining = 900 - (int(time.time()) % 900)
                time.sleep(window_remaining)
                budget = acquire_strava_read_budget()
                if not budget:
                    raise StravaRateLimitError(
                        f"Rate budget still exhausted for activity details {activity_id}",
                        retry_after_s=900,
                    )
            # budget is None (Redis down): fall through (existing degraded behavior)

            try:
                r = requests.get(url, headers=headers, params=params)
            
                # Handle rate limiting (429 Too Many Requests)
                if r.status_code == 429:
                    retry_after = int(r.headers.get("Retry-After", 60 * (2**attempt)))
                    if not allow_rate_limit_sleep:
                        raise StravaRateLimitError(
                            f"429 Rate limited for activity details {activity_id} (Retry-After {retry_after}s)",
                            retry_after_s=retry_after,
                        )
                    print(f"DEBUG: Rate limited (429) for activity details {activity_id}, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
            
                # Handle token refresh (401 Unauthorized)
                if r.status_code == 401 and athlete.strava_refresh_token:
                    from services.token_encryption import decrypt_token, encrypt_token
                    print(f"DEBUG: Token expired, refreshing for activity details {activity_id}")
                    refresh_token = decrypt_token(athlete.strava_refresh_token)
                    if refresh_token:
                        token = refresh_access_token(refresh_token)
                        # Encrypt new tokens
                        athlete.strava_access_token = encrypt_token(token["access_token"])
                        if token.get("refresh_token"):
                            athlete.strava_refresh_token = encrypt_token(token["refresh_token"])
                        if token.get("expires_at"):
                            from datetime import datetime, timezone as tz
                            athlete.strava_token_expires_at = datetime.fromtimestamp(
                                token["expires_at"], tz=tz.utc
                            )
                        # Update headers
                        access_token = decrypt_token(athlete.strava_access_token)
                        headers["Authorization"] = f"Bearer {access_token}"
                        continue
            
                r.raise_for_status()
                return r.json()
            
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    print(f"ERROR: Failed to get activity details for {activity_id} after {max_retries} attempts: {e}")
                    return None
                wait_time = 2 ** attempt
                print(f"DEBUG: Error getting activity details for {activity_id}, retrying in {wait_time}s...")
                time.sleep(wait_time)
    
        return None
    finally:
        _release_strava_detail_slot()


def get_activity_laps(
    athlete,
    activity_id: int,
    max_retries: int = 3,
    allow_rate_limit_sleep: bool = True,
) -> List[Dict]:
    """
    Fetch activity laps with rate limiting and retry logic.
    Strava rate limits: 100 requests per 15 minutes, 1000 per day.
    """
    from services.token_encryption import decrypt_token
    
    # Decrypt access token
    access_token = decrypt_token(athlete.strava_access_token)
    if not access_token:
        return []
    
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{STRAVA_API_BASE}/activities/{activity_id}/laps"
    
    for attempt in range(max_retries):
        # Global rate budget (ADR-063): every HTTP request checks budget
        budget = acquire_strava_read_budget()
        if budget is False:
            if not allow_rate_limit_sleep:
                raise StravaRateLimitError(
                    f"Rate budget exhausted for activity laps {activity_id}",
                    retry_after_s=900,
                )
            window_remaining = 900 - (int(time.time()) % 900)
            time.sleep(window_remaining)
            budget = acquire_strava_read_budget()
            if not budget:
                raise StravaRateLimitError(
                    f"Rate budget still exhausted for activity laps {activity_id}",
                    retry_after_s=900,
                )
        # budget is None (Redis down): fall through (existing degraded behavior)

        try:
            r = requests.get(url, headers=headers)
            
            # Handle rate limiting (429 Too Many Requests)
            if r.status_code == 429:
                retry_after = int(r.headers.get('Retry-After', 60 * (2 ** attempt)))
                if not allow_rate_limit_sleep:
                    raise StravaRateLimitError(
                        f"429 Rate limited for activity laps {activity_id} (Retry-After {retry_after}s)",
                        retry_after_s=retry_after,
                    )
                print(f"DEBUG: Rate limited (429) for activity {activity_id}, waiting {retry_after}s before retry {attempt + 1}/{max_retries}")
                time.sleep(retry_after)
                continue
            
            # Handle token refresh (401 Unauthorized)
            if r.status_code == 401 and athlete.strava_refresh_token:
                print(f"DEBUG: Token expired, refreshing for activity {activity_id}")
                from services.token_encryption import decrypt_token, encrypt_token
                refresh_token = decrypt_token(athlete.strava_refresh_token)
                token = refresh_access_token(refresh_token)
                # SECURITY: Encrypt the new tokens before storing
                athlete.strava_access_token = encrypt_token(token["access_token"])
                if token.get("refresh_token"):
                    athlete.strava_refresh_token = encrypt_token(token["refresh_token"])
                if token.get("expires_at"):
                    from datetime import datetime, timezone as tz
                    athlete.strava_token_expires_at = datetime.fromtimestamp(
                        token["expires_at"], tz=tz.utc
                    )
                headers["Authorization"] = f"Bearer {token['access_token']}"
                continue
            
            r.raise_for_status()
            return r.json() or []
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                # Last attempt failed, raise the exception
                print(f"ERROR: Failed to fetch laps for activity {activity_id} after {max_retries} attempts: {e}")
                raise
            # Wait before retrying
            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            print(f"DEBUG: Error fetching laps for activity {activity_id}, retrying in {wait_time}s...")
            time.sleep(wait_time)
    
    return []


# --- Stream types requested from Strava (ADR-063) ---
STRAVA_STREAM_TYPES = [
    "time", "distance", "heartrate", "cadence", "altitude",
    "velocity_smooth", "grade_smooth", "latlng", "moving",
]


def get_activity_streams(
    athlete,
    activity_id: int,
    stream_types: Optional[List[str]] = None,
    max_retries: int = 3,
    allow_rate_limit_sleep: bool = True,
) -> StreamFetchResult:
    """
    Fetch per-second resolution stream data for a Strava activity (ADR-063).

    Returns a StreamFetchResult with typed outcome so callers can distinguish:
        "success"          — data populated; store and mark success
        "unavailable"      — Strava confirms no streams (404, empty); terminal
        "failed"           — transient/parse error; retryable
        "skipped_no_redis" — Redis down; revert to pending for backfill

    StravaRateLimitError is still raised for rate-limit exhaustion
    (allow_rate_limit_sleep=False), handled by callers as "deferred."

    Channel length validation: all channels must have the same length as
    the 'time' channel. Mismatched lengths → reject entire stream set as
    "failed" (ADR-063: reject + log, not silent truncation).
    """
    from services.token_encryption import decrypt_token, encrypt_token

    # --- Rate budget check (ADR-063 Decision 4) ---
    # For streams, Redis-down = disabled entirely (no degraded-mode fallback)
    budget = acquire_strava_read_budget()
    if budget is None:
        # Redis down — leave pending for backfill (NOT unavailable)
        print(f"INFO: stream_fetch_skipped_no_redis activity_id={activity_id}")
        return StreamFetchResult(outcome="skipped_no_redis", error="redis_unavailable")
    if budget is False:
        # Budget exhausted
        if not allow_rate_limit_sleep:
            raise StravaRateLimitError(
                f"Rate budget exhausted for stream fetch {activity_id}",
                retry_after_s=900,
            )
        # Sleep until next window boundary
        window_seconds_remaining = 900 - (int(time.time()) % 900)
        print(f"DEBUG: Stream rate budget exhausted, sleeping {window_seconds_remaining}s until next window")
        time.sleep(window_seconds_remaining)
        # Re-check budget after sleep
        budget = acquire_strava_read_budget()
        if not budget:
            raise StravaRateLimitError(
                f"Rate budget still exhausted after window rollover for {activity_id}",
                retry_after_s=900,
            )

    # --- Decrypt token ---
    access_token = decrypt_token(athlete.strava_access_token)
    if not access_token:
        return StreamFetchResult(outcome="failed", error="token_decrypt_failed")

    headers = {"Authorization": f"Bearer {access_token}"}
    types = stream_types or STRAVA_STREAM_TYPES
    types_str = ",".join(types)
    url = f"{STRAVA_API_BASE}/activities/{activity_id}/streams"
    params = {"keys": types_str, "key_by_type": "true"}

    for attempt in range(max_retries):
        try:
            # Each retry attempt consumes rate budget
            if attempt > 0:
                retry_budget = acquire_strava_read_budget()
                if retry_budget is None:
                    print(f"INFO: stream_fetch_retry_skipped_no_redis activity_id={activity_id}")
                    return StreamFetchResult(outcome="skipped_no_redis", error="redis_unavailable_on_retry")
                if retry_budget is False:
                    if not allow_rate_limit_sleep:
                        raise StravaRateLimitError(
                            f"Rate budget exhausted on retry for {activity_id}",
                            retry_after_s=900,
                        )
                    window_remaining = 900 - (int(time.time()) % 900)
                    time.sleep(window_remaining)

            r = requests.get(url, headers=headers, params=params, timeout=30)

            # --- 429 Rate Limited ---
            if r.status_code == 429:
                retry_after = int(r.headers.get("Retry-After", 60 * (2 ** attempt)))
                if not allow_rate_limit_sleep:
                    raise StravaRateLimitError(
                        f"429 Rate limited for activity streams {activity_id} "
                        f"(Retry-After {retry_after}s)",
                        retry_after_s=retry_after,
                    )
                print(f"DEBUG: Rate limited (429) for streams {activity_id}, waiting {retry_after}s")
                time.sleep(retry_after)
                continue

            # --- 401 Token Expired ---
            if r.status_code == 401 and athlete.strava_refresh_token:
                print(f"DEBUG: Token expired, refreshing for streams {activity_id}")
                refresh_token = decrypt_token(athlete.strava_refresh_token)
                if refresh_token:
                    token = refresh_access_token(refresh_token)
                    athlete.strava_access_token = encrypt_token(token["access_token"])
                    if token.get("refresh_token"):
                        athlete.strava_refresh_token = encrypt_token(token["refresh_token"])
                    if token.get("expires_at"):
                        from datetime import datetime, timezone as tz
                        athlete.strava_token_expires_at = datetime.fromtimestamp(
                            token["expires_at"], tz=tz.utc
                        )
                    access_token = decrypt_token(athlete.strava_access_token)
                    headers["Authorization"] = f"Bearer {access_token}"
                    continue

            # --- 404 → Strava confirms no streams (terminal) ---
            if r.status_code == 404:
                return StreamFetchResult(outcome="unavailable", error="strava_404_no_streams")

            r.raise_for_status()

            # --- Parse response ---
            try:
                data = r.json()
            except (ValueError, TypeError):
                print(f"ERROR: Malformed JSON in streams response for {activity_id}")
                return StreamFetchResult(outcome="failed", error="malformed_json")

            if not data:
                # Empty response — Strava confirms no streams (manual activity, etc.)
                return StreamFetchResult(outcome="unavailable", error="empty_response")

            # Strava returns a list of stream objects or a dict (key_by_type=true)
            result = {}
            if isinstance(data, list):
                for stream_obj in data:
                    stream_type = stream_obj.get("type")
                    stream_data = stream_obj.get("data")
                    if stream_type and stream_data is not None:
                        result[stream_type] = stream_data
            elif isinstance(data, dict):
                for stream_type, stream_obj in data.items():
                    if isinstance(stream_obj, dict) and "data" in stream_obj:
                        result[stream_type] = stream_obj["data"]
                    elif isinstance(stream_obj, list):
                        result[stream_type] = stream_obj

            if not result:
                # Strava returned data but no usable channels — no streams
                return StreamFetchResult(outcome="unavailable", error="no_usable_channels")

            # --- Channel length validation (ADR-063) ---
            # All channels must match the length of 'time'. Mismatch → reject.
            if "time" in result:
                expected_len = len(result["time"])
                for ch_name, ch_data in result.items():
                    if ch_name == "time":
                        continue
                    if len(ch_data) != expected_len:
                        print(
                            f"ERROR: channel_length_mismatch activity_id={activity_id} "
                            f"time={expected_len} {ch_name}={len(ch_data)}"
                        )
                        return StreamFetchResult(
                            outcome="failed",
                            error=f"channel_length_mismatch:{ch_name}={len(ch_data)},time={expected_len}",
                        )

            return StreamFetchResult(outcome="success", data=result)

        except StravaRateLimitError:
            raise  # Let rate limit errors propagate
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                print(f"ERROR: Failed to fetch streams for {activity_id} after {max_retries} attempts: {e}")
                return StreamFetchResult(outcome="failed", error=f"request_error:{e}")
            wait_time = 2 ** attempt
            print(f"DEBUG: Error fetching streams for {activity_id}, retrying in {wait_time}s...")
            time.sleep(wait_time)

    return StreamFetchResult(outcome="failed", error="retries_exhausted")
