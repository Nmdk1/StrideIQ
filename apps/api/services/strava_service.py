import os
import time
import requests
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


def get_auth_url(state: str | None = None) -> str:
    if not STRAVA_CLIENT_ID:
        raise ValueError("STRAVA_CLIENT_ID is not set")

    params = {
        "client_id": STRAVA_CLIENT_ID,
        "redirect_uri": STRAVA_REDIRECT_URI,
        "response_type": "code",
        "scope": "activity:read_all,read_all",
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
    r.raise_for_status()
    return r.json()


def refresh_access_token(refresh_token: str) -> Dict:
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
        try:
            r = requests.get(url, headers=headers, params=params)
            print(f"DEBUG: poll_activities - response status: {r.status_code}")

            # Handle rate limiting (429 Too Many Requests)
            if r.status_code == 429:
                retry_after = int(r.headers.get('Retry-After', 60 * (2 ** attempt)))  # Default: 60s, 120s, 240s
                if not allow_rate_limit_sleep:
                    raise RuntimeError(f"429 Rate limited for poll_activities_page (Retry-After {retry_after}s)")
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


def poll_activities(athlete, after_timestamp: Optional[int] = None, max_retries: int = 3) -> List[Dict]:
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
        allow_rate_limit_sleep=True,
    )


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
            try:
                r = requests.get(url, headers=headers, params=params)
            
                # Handle rate limiting (429 Too Many Requests)
                if r.status_code == 429:
                    retry_after = int(r.headers.get("Retry-After", 60 * (2**attempt)))
                    if not allow_rate_limit_sleep:
                        # Let callers decide how to handle rate limiting (e.g. stop early
                        # in HTTP requests, retry later in background jobs).
                        raise RuntimeError(f"429 Rate limited for activity details {activity_id} (Retry-After {retry_after}s)")
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


def get_activity_laps(athlete, activity_id: int, max_retries: int = 3) -> List[Dict]:
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
        try:
            r = requests.get(url, headers=headers)
            
            # Handle rate limiting (429 Too Many Requests)
            if r.status_code == 429:
                # Get retry-after header if available, otherwise use exponential backoff
                retry_after = int(r.headers.get('Retry-After', 60 * (2 ** attempt)))  # Default: 60s, 120s, 240s
                print(f"DEBUG: Rate limited (429) for activity {activity_id}, waiting {retry_after}s before retry {attempt + 1}/{max_retries}")
                time.sleep(retry_after)
                continue
            
            # Handle token refresh (401 Unauthorized)
            if r.status_code == 401 and athlete.strava_refresh_token:
                print(f"DEBUG: Token expired, refreshing for activity {activity_id}")
                token = refresh_access_token(athlete.strava_refresh_token)
                athlete.strava_access_token = token["access_token"]
                headers["Authorization"] = f"Bearer {athlete.strava_access_token}"
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
