"""
Strava Webhook Router

Handles Strava webhook events for automatic activity sync.
"""

from typing import Optional
import json
from fastapi import APIRouter, Request, HTTPException, status, Header, Query, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from models import Athlete, Activity
from services.strava_webhook import verify_webhook_signature, subscribe_to_webhooks, list_webhook_subscriptions, delete_webhook_subscription
from tasks.strava_tasks import sync_strava_activities_task
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/strava/webhook", tags=["strava-webhook"])


@router.get("/verify")
def verify_webhook(
    hub_mode: str = Query(..., description="Hub mode (should be 'subscribe')"),
    hub_verify_token: str = Query(..., description="Verification token"),
    hub_challenge: str = Query(..., description="Challenge string from Strava"),
):
    """
    Verify webhook subscription with Strava.
    
    Strava calls this endpoint during webhook subscription to verify ownership.
    Must return hub_challenge if verify_token matches.
    """
    from core.config import settings
    
    expected_token = getattr(settings, 'STRAVA_WEBHOOK_VERIFY_TOKEN', 'verify_token')
    
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("Webhook verification successful")
        return {"hub.challenge": hub_challenge}
    else:
        logger.warning(f"Webhook verification failed: mode={hub_mode}, token={hub_verify_token}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification failed"
        )


@router.post("/events")
async def handle_webhook_event(
    request: Request,
    x_strava_signature: Optional[str] = Header(None, alias="X-Strava-Signature"),
    db: Session = Depends(get_db),
):
    """
    Handle Strava webhook events.
    
    Processes activity.create and activity.update events to automatically sync activities.
    """
    try:
        # Get raw body for signature verification
        body_bytes = await request.body()
        body_str = body_bytes.decode('utf-8')
        
        # SECURITY: Signature is MANDATORY - reject unsigned requests
        if not x_strava_signature:
            logger.warning("Webhook request missing signature header - rejecting")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing signature"
            )
        
        # Strava sends signature as "sha256=<hash>"
        signature = x_strava_signature.replace("sha256=", "")
        if not verify_webhook_signature(body_str, signature):
            logger.warning("Invalid webhook signature - rejecting")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
        
        # Parse event data
        event_data = json.loads(body_str)
        
        event_type = event_data.get("object_type")
        aspect_type = event_data.get("aspect_type")
        object_id = event_data.get("object_id")
        owner_id = event_data.get("owner_id")
        
        logger.info(f"Webhook event: type={event_type}, aspect={aspect_type}, object_id={object_id}, owner_id={owner_id}")
        
        # Only process activity events
        if event_type != "activity":
            logger.info(f"Ignoring non-activity event: {event_type}")
            return {"status": "ignored"}
        
        # Find athlete by Strava ID
        athlete = db.query(Athlete).filter(
            Athlete.strava_athlete_id == owner_id
        ).first()
        
        if not athlete:
            logger.warning(f"No athlete found for Strava ID: {owner_id}")
            return {"status": "athlete_not_found"}
        
        # Enqueue sync task for this athlete
        if aspect_type in ["create", "update"]:
            logger.info(f"Enqueuing sync task for athlete {athlete.id} (Strava ID: {owner_id})")
            sync_strava_activities_task.delay(str(athlete.id))
            return {
                "status": "queued",
                "athlete_id": str(athlete.id),
                "activity_id": object_id
            }
        else:
            logger.info(f"Ignoring aspect type: {aspect_type}")
            return {"status": "ignored", "aspect_type": aspect_type}
            
    except HTTPException:
        # Let HTTPException propagate (auth failures, etc.)
        raise
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON"
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        )


@router.post("/subscribe")
def subscribe_webhook(
    callback_url: str = Query(..., description="Public URL for webhook callbacks"),
):
    """
    Subscribe to Strava webhooks.
    
    This endpoint can be called manually or via admin dashboard to set up webhooks.
    Requires public callback URL accessible by Strava.
    """
    try:
        result = subscribe_to_webhooks(callback_url)
        logger.info(f"Webhook subscription created: {result}")
        return result
    except Exception as e:
        logger.error(f"Error subscribing to webhooks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error subscribing: {str(e)}"
        )


@router.get("/subscriptions")
def get_webhook_subscriptions():
    """
    List current webhook subscriptions.
    """
    try:
        result = list_webhook_subscriptions()
        return result
    except Exception as e:
        logger.error(f"Error listing subscriptions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing subscriptions: {str(e)}"
        )

