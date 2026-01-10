"""
Strava Webhook Service

Handles Strava webhook subscriptions and event processing.
Enables automatic activity sync when activities are created/updated.
"""

import hmac
import hashlib
import requests
from typing import Dict, Optional
from core.config import settings
import logging

logger = logging.getLogger(__name__)

STRAVA_CLIENT_ID = getattr(settings, 'STRAVA_CLIENT_ID', None)
STRAVA_CLIENT_SECRET = getattr(settings, 'STRAVA_CLIENT_SECRET', None)
STRAVA_WEBHOOK_VERIFY_TOKEN = getattr(settings, 'STRAVA_WEBHOOK_VERIFY_TOKEN', None)


def verify_webhook_signature(payload: str, signature: str) -> bool:
    """
    Verify Strava webhook signature.
    
    Strava signs webhook payloads with SHA256 HMAC using client secret.
    """
    if not STRAVA_CLIENT_SECRET:
        logger.warning("STRAVA_CLIENT_SECRET not set, cannot verify webhook signature")
        return False
    
    expected_signature = hmac.new(
        STRAVA_CLIENT_SECRET.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


def subscribe_to_webhooks(callback_url: str) -> Dict:
    """
    Subscribe to Strava webhooks.
    
    Requires:
    - callback_url: Public URL where Strava will send webhook events
    - verify_token: Token for webhook verification (set in Strava app settings)
    
    Returns subscription response from Strava.
    """
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET:
        raise ValueError("Strava credentials not configured")
    
    url = "https://www.strava.com/api/v3/push_subscriptions"
    
    params = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "callback_url": callback_url,
        "verify_token": STRAVA_WEBHOOK_VERIFY_TOKEN or "verify_token",
    }
    
    response = requests.post(url, params=params)
    response.raise_for_status()
    
    return response.json()


def list_webhook_subscriptions() -> Dict:
    """
    List current webhook subscriptions.
    """
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET:
        raise ValueError("Strava credentials not configured")
    
    url = "https://www.strava.com/api/v3/push_subscriptions"
    
    params = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    
    return response.json()


def delete_webhook_subscription(subscription_id: int) -> bool:
    """
    Delete a webhook subscription.
    """
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET:
        raise ValueError("Strava credentials not configured")
    
    url = f"https://www.strava.com/api/v3/push_subscriptions/{subscription_id}"
    
    params = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
    }
    
    response = requests.delete(url, params=params)
    return response.status_code == 204


