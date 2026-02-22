#!/usr/bin/env python3
"""
RETIRED — DO NOT USE

This script was written for the credential-based Garmin integration
(python-garminconnect / username+password auth). That integration was
retired in Phase 2 (Feb 2026) when StrideIQ migrated to OAuth 2.0 PKCE
via the official Garmin Connect API.

The tasks it references (`sync_garmin_activities_task`,
`sync_garmin_recovery_metrics_task`) were defined in
`apps/api/tasks/garmin_tasks.py`, which has been deleted.

Replacement:
  Garmin data now arrives via push webhooks (D4) and is processed by:
    - process_garmin_activity_task  (D5)
    - process_garmin_health_task    (D6)
  No polling/scheduling script is needed — Garmin pushes data to us.

  For 90-day backfill on connect, see D7 (initial backfill task).

See docs/PHASE2_GARMIN_INTEGRATION_AC.md §D5, §D6, §D7
"""

raise SystemExit(
    "schedule_staggered_garmin_syncs.py is retired. "
    "Garmin data arrives via push webhooks. See docs/PHASE2_GARMIN_INTEGRATION_AC.md."
)
