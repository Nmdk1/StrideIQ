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


def get_auth_url() -> str:
    if not STRAVA_CLIENT_ID:
        raise ValueError("STRAVA_CLIENT_ID is not set")

    params = {
        "client_id": STRAVA_CLIENT_ID,
        "redirect_uri": STRAVA_REDIRECT_URI,
        "response_type": "code",
        "scope": "activity:read_all,read_all",
        "approval_prompt": "force",
    }

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


def poll_activities(athlete, after_timestamp: Optional[int] = None, max_retries: int = 3) -> List[Dict]:
    """
    Poll activities from Strava with rate limiting and retry logic.
    """
    from services.token_encryption import decrypt_token
    
    # Decrypt access token
    access_token = decrypt_token(athlete.strava_access_token)
    if not access_token:
        raise ValueError("Failed to decrypt Strava access token")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"per_page": 200}

    # Only add "after" parameter if we have a valid timestamp > 0
    # If after_timestamp is 0 or None, omit the parameter to fetch all activities
    if after_timestamp is not None and after_timestamp > 0:
        params["after"] = int(after_timestamp)
        print(f"DEBUG: poll_activities - adding 'after' param: {params['after']}")
    elif after_timestamp is None and athlete.last_strava_sync:
        # Fallback: use athlete's last sync if no timestamp provided
        params["after"] = int(athlete.last_strava_sync.timestamp())
        print(f"DEBUG: poll_activities - using athlete.last_strava_sync: {params['after']}")
    else:
        print(f"DEBUG: poll_activities - no 'after' param (fetching all activities)")

    print(f"DEBUG: poll_activities - request params: {params}")
    url = f"{STRAVA_API_BASE}/athlete/activities"
    
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=headers, params=params)
            print(f"DEBUG: poll_activities - response status: {r.status_code}")

            # Handle rate limiting (429 Too Many Requests)
            if r.status_code == 429:
                retry_after = int(r.headers.get('Retry-After', 60 * (2 ** attempt)))  # Default: 60s, 120s, 240s
                print(f"DEBUG: Rate limited (429) on poll_activities, waiting {retry_after}s before retry {attempt + 1}/{max_retries}")
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
            print(f"DEBUG: poll_activities - raw response count: {len(activities) if isinstance(activities, list) else 'not a list'}")
            return activities
            
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


def get_activity_details(athlete, activity_id: int, max_retries: int = 3) -> Optional[Dict]:
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
    
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=headers)
            
            # Handle rate limiting (429 Too Many Requests)
            if r.status_code == 429:
                retry_after = int(r.headers.get('Retry-After', 60 * (2 ** attempt)))
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
