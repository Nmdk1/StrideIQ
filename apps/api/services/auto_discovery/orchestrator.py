"""
AutoDiscovery Orchestrator — Phase 0A (shadow mode only).

Executes one founder-only nightly research pass for a single athlete:

1. Creates an `auto_discovery_run` row.
2. Runs the correlation multi-window rescan loop (shadow).
3. Rolls back any un-committed correlation_finding flushes from the
   rescan (shadow contract).
4. Writes one `auto_discovery_experiment` row per window result.
5. Assembles a structured nightly report and finalises the run row.

Safety guarantees (Phase 0A):
- No `correlation_finding`, `fingerprint_finding`, or any
  athlete-facing table is mutated and committed.
- No production registry values are written.
- Exactly one `db.commit()` call at the very end, which writes
  only the `auto_discovery_run` and `auto_discovery_experiment` rows.
"""

from __future__ import annotations

import logging
import time
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import AutoDiscoveryRun, AutoDiscoveryExperiment
from services.auto_discovery.rescan_loop import (
    run_multiwindow_rescan,
    summarize_window_stability,
)

logger = logging.getLogger(__name__)

_PHASE = "0A"
_SCHEMA_VERSION = 1


def run_auto_discovery_for_athlete(
    athlete_id: UUID,
    db: Session,
    enabled_loops: Optional[List[str]] = None,
) -> AutoDiscoveryRun:
    """
    Execute one full AutoDiscovery shadow pass for the athlete.

    Parameters
    ----------
    athlete_id:
        UUID of the athlete.  Must be in the feature-flag allowlist.
    db:
        Live SQLAlchemy session.  Caller must NOT commit before calling
        this function; this function owns the final commit.
    enabled_loops:
        Loop families to run.  Defaults to ["correlation_rescan"].
        In Phase 0A only "correlation_rescan" is wired.

    Returns
    -------
    AutoDiscoveryRun
        The persisted run row (committed).
    """
    if enabled_loops is None:
        enabled_loops = ["correlation_rescan"]

    athlete_id_str = str(athlete_id)
    started_at = datetime.now(timezone.utc)

    run = AutoDiscoveryRun(
        id=_uuid.uuid4(),
        athlete_id=athlete_id,
        started_at=started_at,
        status="running",
        loop_types=enabled_loops,
    )
    db.add(run)
    db.flush()

    experiment_rows: List[AutoDiscoveryExperiment] = []
    all_rescan_results: List[Dict[str, Any]] = []
    partial = False

    # ── Correlation multi-window rescan ────────────────────────────────────
    if "correlation_rescan" in enabled_loops:
        logger.info("AutoDiscovery Phase 0A: starting rescan for athlete=%s", athlete_id_str)
        try:
            # analyze_correlations() internally flushes to correlation_finding.
            # We collect the result dicts then roll back those flushes so no
            # correlation_finding rows are committed.
            rescan_results = run_multiwindow_rescan(athlete_id=athlete_id, db=db)

            # Roll back any correlation_finding flushes — shadow contract.
            # We keep the run + experiment rows by re-adding them after rollback.
            db.rollback()
            db.add(run)
            db.flush()

            all_rescan_results = rescan_results

            for result in rescan_results:
                baseline_score = _count_findings(result.get("result_summary", {}))
                exp = AutoDiscoveryExperiment(
                    id=_uuid.uuid4(),
                    run_id=run.id,
                    athlete_id=athlete_id,
                    loop_type=result["loop_type"],
                    target_name=result["target_name"],
                    baseline_config=result["baseline_config"],
                    candidate_config=result["candidate_config"],
                    baseline_score=float(baseline_score),
                    candidate_score=None,
                    score_delta=None,
                    kept=result.get("failure_reason") is None,
                    runtime_ms=result.get("runtime_ms"),
                    result_summary=result.get("result_summary"),
                    failure_reason=result.get("failure_reason"),
                )
                db.add(exp)
                experiment_rows.append(exp)

        except Exception as exc:
            partial = True
            logger.error("AutoDiscovery rescan failed for athlete=%s: %s", athlete_id_str, exc)
            # Don't re-raise — we still write the partial run row.

    db.flush()

    # ── Assemble structured nightly report ─────────────────────────────────
    report = _build_report(
        athlete_id=athlete_id_str,
        rescan_results=all_rescan_results,
        experiment_rows=experiment_rows,
        partial=partial,
    )

    finished_at = datetime.now(timezone.utc)
    run.finished_at = finished_at
    run.status = "partial" if partial else "completed"
    run.experiment_count = len(experiment_rows)
    run.kept_count = sum(1 for e in experiment_rows if e.kept)
    run.discarded_count = sum(1 for e in experiment_rows if not e.kept)
    run.report = report

    db.commit()
    logger.info(
        "AutoDiscovery Phase 0A: athlete=%s status=%s experiments=%d duration_s=%.1f",
        athlete_id_str,
        run.status,
        run.experiment_count,
        (finished_at - started_at).total_seconds(),
    )
    return run


# ── Report assembly ────────────────────────────────────────────────────────

def _count_findings(result_summary: Dict[str, Any]) -> int:
    return result_summary.get("total_findings", 0)


def _build_report(
    athlete_id: str,
    rescan_results: List[Dict[str, Any]],
    experiment_rows: List[AutoDiscoveryExperiment],
    partial: bool,
) -> Dict[str, Any]:
    """
    Assemble the structured nightly report.  All seven required sections
    must be present even when empty; absence of a section means Phase 0
    is incomplete (spec acceptance rule).
    """
    stability = summarize_window_stability(rescan_results) if rescan_results else {
        "stable": [], "recent_only": [], "strengthening": [], "unstable": []
    }

    # Section 1: Stable findings — present across all windows.
    stable_findings = stability["stable"]

    # Section 2: Strengthened findings — stronger in longer windows.
    strengthened_findings = stability["strengthening"]

    # Section 3: Candidate interactions — Phase 0B; empty in 0A.
    candidate_interactions: List[Dict] = []

    # Section 4: Registry tuning candidates — Phase 0B; empty in 0A.
    registry_tuning_candidates: List[Dict] = []

    # Section 5: Discarded experiments — failed or error windows.
    discarded = [
        {
            "target_name": e.target_name,
            "failure_reason": e.failure_reason,
            "runtime_ms": e.runtime_ms,
        }
        for e in experiment_rows
        if not e.kept
    ]

    # Section 6: Score summary by loop family.
    kept = [e for e in experiment_rows if e.kept]
    score_summary = {
        "correlation_rescan": {
            "experiments_run": sum(1 for e in experiment_rows if e.loop_type == "correlation_rescan"),
            "kept": sum(1 for e in kept if e.loop_type == "correlation_rescan"),
            "total_findings_across_windows": sum(
                _count_findings(r.get("result_summary", {}))
                for r in rescan_results
                if not r.get("failure_reason")
            ),
            "stable_finding_count": len(stable_findings),
            "strengthening_finding_count": len(strengthened_findings),
            "recent_only_count": len(stability.get("recent_only", [])),
            "unstable_count": len(stability.get("unstable", [])),
        }
    }

    # Section 7: No-surface guarantee (explicit, required by spec).
    no_surface_guarantee = {
        "athlete_facing_surfaces_mutated": False,
        "production_registry_values_mutated": False,
        "live_mutation_enabled": False,
        "phase": _PHASE,
        "guarantee_schema_version": _SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "schema_version": _SCHEMA_VERSION,
        "phase": _PHASE,
        "athlete_id": athlete_id,
        "partial": partial,
        # ── Required sections ──────────────────────────────────────────────
        "stable_findings": stable_findings,
        "strengthened_findings": strengthened_findings,
        "candidate_interactions": candidate_interactions,
        "registry_tuning_candidates": registry_tuning_candidates,
        "discarded_experiments": discarded,
        "score_summary": score_summary,
        "no_surface_guarantee": no_surface_guarantee,
        # ── Window stability detail (additional context) ───────────────────
        "window_stability_detail": stability,
    }
