"""
Garmin Webhook Celery Tasks (D4 stubs — implemented in D5/D6)

These task stubs are registered with Celery so that webhook route handlers
can dispatch them immediately (fire-and-forget) and return 200 to Garmin.

Implementation status:
  process_garmin_activity_task      — stub (D5 implements ingestion logic)
  process_garmin_activity_detail_task — stub (D5 implements stream ingestion)
  process_garmin_health_task        — stub (D6 implements GarminDay upsert)
  process_garmin_deregistration_task — stub (calls existing disconnect logic)
  process_garmin_permissions_task   — stub (handles permission change events)

When D5/D6 are implemented, the stubs below are replaced with real logic.
The task names and signatures must NOT change — they are keyed in by the
webhook router and any queued tasks must be processable after a deploy.

See docs/PHASE2_GARMIN_INTEGRATION_AC.md §D5, §D6
"""

import logging
from typing import Any, Dict

from tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="process_garmin_activity_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_garmin_activity_task(
    self,
    athlete_id: str,
    payload: Dict[str, Any],
) -> None:
    """
    Ingest a Garmin activity summary from a push webhook.

    D5 implements this fully:
      1. ensure_fresh_garmin_token
      2. adapt_activity_summary (via garmin_adapter)
      3. Filter: sport="run" only
      4. Deduplication against existing Strava/Garmin activities
      5. Create/update Activity row with provider="garmin"
      6. Enqueue activity detail task if details available

    Args:
        athlete_id: Internal athlete UUID.
        payload: Raw Garmin push webhook payload dict.
    """
    logger.info(
        "[D4 STUB] process_garmin_activity_task — D5 not yet implemented",
        extra={"athlete_id": athlete_id, "summary_id": payload.get("summaryId")},
    )


@celery_app.task(
    name="process_garmin_activity_detail_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_garmin_activity_detail_task(
    self,
    athlete_id: str,
    payload: Dict[str, Any],
) -> None:
    """
    Ingest a Garmin activity detail (GPS samples, laps) from a push webhook.

    D5 implements this: parses stream samples, extracts powerInWatts,
    stores in ActivityStream table.

    Args:
        athlete_id: Internal athlete UUID.
        payload: Raw Garmin ClientActivityDetail payload dict.
    """
    logger.info(
        "[D4 STUB] process_garmin_activity_detail_task — D5 not yet implemented",
        extra={"athlete_id": athlete_id, "summary_id": payload.get("summaryId")},
    )


@celery_app.task(
    name="process_garmin_health_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_garmin_health_task(
    self,
    athlete_id: str,
    data_type: str,
    payload: Dict[str, Any],
) -> None:
    """
    Upsert a Garmin health/wellness payload into GarminDay.

    D6 implements this:
      - data_type: "sleeps" | "hrv" | "stress" | "dailies" | "user-metrics"
      - Calls the appropriate adapt_*() function from garmin_adapter
      - Upserts into GarminDay on (athlete_id, calendar_date)
      - Stress samples stored as-is JSONB; negatives stored, filtered at query time

    Args:
        athlete_id: Internal athlete UUID.
        data_type: Webhook data type string matching the route path segment.
        payload: Raw Garmin health payload dict.
    """
    logger.info(
        "[D4 STUB] process_garmin_health_task — D6 not yet implemented",
        extra={
            "athlete_id": athlete_id,
            "data_type": data_type,
            "summary_id": payload.get("summaryId"),
        },
    )


@celery_app.task(
    name="process_garmin_deregistration_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_garmin_deregistration_task(
    self,
    athlete_id: str,
    payload: Dict[str, Any],
) -> None:
    """
    Handle a Garmin deregistration ping.

    Garmin sends this when a user disconnects from StrideIQ via the Garmin
    Connect app (not via StrideIQ's disconnect flow). Triggers the same
    soft-disconnect logic as POST /v1/garmin/disconnect but initiated by Garmin.

    Implementation: call the existing disconnect endpoint logic:
      - Clear OAuth tokens
      - Set garmin_connected=False
      - Write consent_audit_log entry (source="garmin_initiated")
      - Do NOT delete GarminDay or activities (soft disconnect)
    """
    logger.info(
        "[D4 STUB] process_garmin_deregistration_task",
        extra={"athlete_id": athlete_id},
    )


@celery_app.task(
    name="process_garmin_permissions_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_garmin_permissions_task(
    self,
    athlete_id: str,
    payload: Dict[str, Any],
) -> None:
    """
    Handle a Garmin user permissions change ping.

    Garmin sends this when an athlete changes their data sharing permissions
    in the Garmin Connect app (e.g., revokes ACTIVITY_EXPORT). Triggers a
    permission re-check and adjusts sync scope accordingly.

    Implementation:
      - Call GET /rest/user/permissions via garmin_oauth.get_user_permissions()
      - If ACTIVITY_EXPORT or HEALTH_EXPORT revoked: log warning, adjust sync
      - Write a note to the athlete's account (non-blocking)
    """
    logger.info(
        "[D4 STUB] process_garmin_permissions_task",
        extra={"athlete_id": athlete_id},
    )
