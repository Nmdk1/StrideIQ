"""
AutoDiscovery Nightly Task — Phase 0B (founder-only, shadow mode).

Scheduled at 04:00 UTC (before morning intelligence).
Gated by feature flag `auto_discovery.enabled`.
Runs only for athletes in the flag's `allowed_athlete_ids` list.

WS1 fix: loop-family enablement is evaluated per athlete, not once
globally from the first eligible athlete.
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
    time_limit=60 * 60,
    soft_time_limit=50 * 60,
)
def run_auto_discovery_nightly(self, athlete_ids: Optional[List[str]] = None):
    """
    Founder-only nightly AutoDiscovery shadow pass.

    Loop-family enablement is resolved per-athlete so that future partial
    rollouts (e.g. enable interaction scan for athlete A only) work without
    architecture changes.
    """
    db = SessionLocal()
    try:
        from services.auto_discovery.feature_flags import (
            FLAG_SYSTEM_ENABLED,
            is_auto_discovery_enabled,
            is_rescan_enabled,
            is_interaction_enabled,
            is_tuning_enabled,
        )
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete
        from services.plan_framework.feature_flags import FeatureFlagService

        flag_svc = FeatureFlagService(db)

        if athlete_ids:
            target_ids = [UUID(a) for a in athlete_ids]
        else:
            flag = flag_svc._get_flag(FLAG_SYSTEM_ENABLED)
            allowed = flag.get("allowed_athlete_ids", []) if flag else []
            target_ids = [UUID(str(a)) for a in allowed]

        if not target_ids:
            logger.info("AutoDiscovery: no eligible athletes; skipping run")
            return

        logger.info("AutoDiscovery Phase 0B: %d athletes", len(target_ids))

        for athlete_id in target_ids:
            athlete_id_str = str(athlete_id)
            if not is_auto_discovery_enabled(athlete_id_str, db):
                logger.info("AutoDiscovery: athlete=%s not enabled; skipping", athlete_id_str)
                continue

            # WS1: per-athlete loop resolution — not task-wide inference.
            enabled_loops: List[str] = []
            if is_rescan_enabled(athlete_id_str, db):
                enabled_loops.append("correlation_rescan")
            if is_interaction_enabled(athlete_id_str, db):
                enabled_loops.append("interaction_scan")
            if is_tuning_enabled(athlete_id_str, db):
                enabled_loops.append("registry_tuning")

            if not enabled_loops:
                logger.info(
                    "AutoDiscovery: athlete=%s no loops enabled; skipping", athlete_id_str
                )
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

        from tasks.beat_startup_dispatch import record_task_run
        record_task_run("beat:last_run:auto_discovery_nightly")

    finally:
        db.close()
