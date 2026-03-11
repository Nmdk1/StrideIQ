"""
AutoDiscovery Nightly Task — Phase 0A (founder-only, shadow mode).

Scheduled at 04:00 UTC (before morning intelligence).
Gated by feature flag `auto_discovery.enabled`.
Runs only for athletes in the flag's `allowed_athlete_ids` list.

This task owns no athlete-facing output, no registry mutations,
and no live commits other than the run + experiment ledger rows.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from tasks import celery_app
from core.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    name="tasks.run_auto_discovery_nightly",
    bind=True,
    max_retries=0,
    time_limit=60 * 60,       # 1-hour hard cap
    soft_time_limit=50 * 60,
)
def run_auto_discovery_nightly(self, athlete_ids: Optional[List[str]] = None):
    """
    Founder-only nightly AutoDiscovery shadow pass.

    If `athlete_ids` is provided, runs only for those athletes (manual
    trigger).  Otherwise discovers athletes enabled via feature flag.

    Parameters
    ----------
    athlete_ids:
        Optional explicit list of athlete UUID strings.  When absent,
        the task queries the feature-flag allowlist.
    """
    db = SessionLocal()
    try:
        from services.auto_discovery.feature_flags import (
            FLAG_SYSTEM_ENABLED,
            FLAG_LOOP_RESCAN,
            is_auto_discovery_enabled,
            is_rescan_enabled,
        )
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete
        from services.plan_framework.feature_flags import FeatureFlagService
        from models import Athlete

        flag_svc = FeatureFlagService(db)

        if athlete_ids:
            target_ids = [UUID(a) for a in athlete_ids]
        else:
            # Discover from feature-flag allowlist (data-driven, no hardcoding).
            flag = flag_svc._get_flag(FLAG_SYSTEM_ENABLED)
            allowed = flag.get("allowed_athlete_ids", []) if flag else []
            target_ids = [UUID(str(a)) for a in allowed]

        if not target_ids:
            logger.info("AutoDiscovery: no eligible athletes; skipping run")
            return

        enabled_loops: List[str] = []
        if is_rescan_enabled(str(target_ids[0]) if target_ids else None, db):
            enabled_loops.append("correlation_rescan")

        if not enabled_loops:
            logger.info("AutoDiscovery: no loops enabled; skipping run")
            return

        logger.info(
            "AutoDiscovery Phase 0A: %d athletes, loops=%s",
            len(target_ids), enabled_loops,
        )

        for athlete_id in target_ids:
            athlete_id_str = str(athlete_id)
            if not is_auto_discovery_enabled(athlete_id_str, db):
                logger.info("AutoDiscovery: athlete=%s not enabled; skipping", athlete_id_str)
                continue
            try:
                run = run_auto_discovery_for_athlete(
                    athlete_id=athlete_id,
                    db=db,
                    enabled_loops=enabled_loops,
                )
                logger.info(
                    "AutoDiscovery: athlete=%s run_id=%s status=%s experiments=%d",
                    athlete_id_str, run.id, run.status, run.experiment_count,
                )
            except Exception as exc:
                logger.error(
                    "AutoDiscovery: athlete=%s failed: %s",
                    athlete_id_str, exc,
                )
                db.rollback()

    finally:
        db.close()
