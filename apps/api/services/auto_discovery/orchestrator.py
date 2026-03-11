"""
AutoDiscovery Orchestrator — Phase 0B (shadow mode only).

Executes one founder-only nightly research pass for a single athlete.
Phase 0B extends 0A with:
  - correlation_rescan: real FQS-driven scores (not counts)
  - interaction_scan: pairwise interaction discovery loop
  - registry_tuning: pilot investigation parameter tuning loop

Safety guarantees (unchanged from Phase 0A):
- No correlation_finding, fingerprint_finding, or athlete-facing table
  is mutated and committed.
- No production registry values are written.
- No production cache is read or written from shadow paths (WS1 fix).
- Exactly one db.commit() at the very end, writing only auto_discovery_run
  and auto_discovery_experiment rows.
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
from services.auto_discovery.fqs_adapters import CorrelationFindingFQSAdapter
from services.auto_discovery.interaction_loop import (
    run_pairwise_interaction_scan,
    INTERACTION_KEEP_THRESHOLD,
)
from services.auto_discovery.tuning_loop import (
    run_pilot_tuning_loop,
    summarize_tuning_results,
    TUNING_KEEP_THRESHOLD,
)

logger = logging.getLogger(__name__)

_PHASE = "0B"
_SCHEMA_VERSION = 2


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
        Loop families to run.  Default: ["correlation_rescan"].
        Phase 0B adds: "interaction_scan", "registry_tuning".

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
    all_interaction_results: List[Dict[str, Any]] = []
    all_tuning_results: List[Dict[str, Any]] = []
    partial = False

    # ── Correlation multi-window rescan (WS1+WS2) ─────────────────────────
    if "correlation_rescan" in enabled_loops:
        logger.info("AutoDiscovery 0B: starting rescan for athlete=%s", athlete_id_str)
        try:
            rescan_results = run_multiwindow_rescan(athlete_id=athlete_id, db=db)
            # Roll back any correlation_finding flushes — shadow contract.
            db.rollback()
            db.add(run)
            db.flush()

            all_rescan_results = rescan_results
            rescan_adapter = CorrelationFindingFQSAdapter()

            for result in rescan_results:
                result_summary = result.get("result_summary", {})
                # WS2: real FQS-driven scoring using shadow dict adapter.
                fqs_scores = _score_rescan_window(result_summary, rescan_adapter)
                baseline_score = fqs_scores["aggregate_final_score"]

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
                    result_summary={
                        **result_summary,
                        "fqs_scores": fqs_scores,
                    },
                    failure_reason=result.get("failure_reason"),
                )
                db.add(exp)
                experiment_rows.append(exp)

        except Exception as exc:
            partial = True
            logger.error("AutoDiscovery rescan failed for athlete=%s: %s", athlete_id_str, exc)

    # ── Pairwise interaction loop (WS3) ────────────────────────────────────
    if "interaction_scan" in enabled_loops:
        logger.info("AutoDiscovery 0B: starting interaction scan for athlete=%s", athlete_id_str)
        try:
            interaction_results = run_pairwise_interaction_scan(athlete_id=athlete_id, db=db)
            all_interaction_results = interaction_results

            for result in interaction_results:
                exp = AutoDiscoveryExperiment(
                    id=_uuid.uuid4(),
                    run_id=run.id,
                    athlete_id=athlete_id,
                    loop_type=result["loop_type"],
                    target_name=result["target_name"],
                    baseline_config=result["baseline_config"],
                    candidate_config=result["candidate_config"],
                    baseline_score=result.get("baseline_score"),
                    candidate_score=result.get("candidate_score"),
                    score_delta=result.get("score_delta"),
                    kept=result.get("failure_reason") is None and (
                        result["result_summary"].get("interactions_kept", 0) > 0
                    ),
                    runtime_ms=result.get("runtime_ms"),
                    result_summary=result.get("result_summary"),
                    failure_reason=result.get("failure_reason"),
                )
                db.add(exp)
                experiment_rows.append(exp)

        except Exception as exc:
            partial = True
            logger.error("AutoDiscovery interaction scan failed for athlete=%s: %s", athlete_id_str, exc)

    # ── Registry tuning loop (WS4) ─────────────────────────────────────────
    if "registry_tuning" in enabled_loops:
        logger.info("AutoDiscovery 0B: starting tuning loop for athlete=%s", athlete_id_str)
        try:
            tuning_results = run_pilot_tuning_loop(athlete_id=athlete_id, db=db)
            all_tuning_results = tuning_results

            for result in tuning_results:
                exp = AutoDiscoveryExperiment(
                    id=_uuid.uuid4(),
                    run_id=run.id,
                    athlete_id=athlete_id,
                    loop_type=result["loop_type"],
                    target_name=result["target_name"],
                    baseline_config=result["baseline_config"],
                    candidate_config=result["candidate_config"],
                    baseline_score=result.get("baseline_score"),
                    candidate_score=result.get("candidate_score"),
                    score_delta=result.get("score_delta"),
                    kept=result.get("kept", False),
                    runtime_ms=result.get("runtime_ms"),
                    result_summary=result.get("result_summary"),
                    failure_reason=result.get("failure_reason"),
                )
                db.add(exp)
                experiment_rows.append(exp)

        except Exception as exc:
            partial = True
            logger.error("AutoDiscovery tuning loop failed for athlete=%s: %s", athlete_id_str, exc)

    db.flush()

    # ── Assemble structured nightly report ─────────────────────────────────
    report = _build_report(
        athlete_id=athlete_id_str,
        rescan_results=all_rescan_results,
        interaction_results=all_interaction_results,
        tuning_results=all_tuning_results,
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
        "AutoDiscovery Phase 0B: athlete=%s status=%s experiments=%d duration_s=%.1f",
        athlete_id_str,
        run.status,
        run.experiment_count,
        (finished_at - started_at).total_seconds(),
    )
    return run


# ── FQS rescan scoring ─────────────────────────────────────────────────────

def _score_rescan_window(
    result_summary: Dict[str, Any],
    adapter: CorrelationFindingFQSAdapter,
) -> Dict[str, Any]:
    """
    Compute aggregate FQS scores for a single window's correlation dicts.

    Returns a dict with per-finding scores and aggregate stats.
    """
    findings_by_metric = result_summary.get("findings_by_metric", {})
    all_scores: List[float] = []
    scored_per_metric: Dict[str, List[float]] = {}

    for metric, correlations in findings_by_metric.items():
        metric_scores: List[float] = []
        for c in correlations:
            fqs = adapter.score_shadow_dict(c)
            metric_scores.append(fqs["final_score"])
        scored_per_metric[metric] = metric_scores
        all_scores.extend(metric_scores)

    total = len(all_scores)
    aggregate = round(sum(all_scores) / total, 4) if total else 0.0

    return {
        "total_scored": total,
        "aggregate_final_score": aggregate,
        "per_metric_avg": {
            m: round(sum(s) / len(s), 4) if s else 0.0
            for m, s in scored_per_metric.items()
        },
    }


# ── Report assembly (WS5) ──────────────────────────────────────────────────

def _build_report(
    athlete_id: str,
    rescan_results: List[Dict[str, Any]],
    interaction_results: List[Dict[str, Any]],
    tuning_results: List[Dict[str, Any]],
    experiment_rows: List[AutoDiscoveryExperiment],
    partial: bool,
) -> Dict[str, Any]:
    """
    Assemble the structured nightly report.  All seven required sections
    must be present.  Phase 0B: sections 3 and 4 contain real ranked
    content or explicit threshold-cleared statements (not empty lists).
    """
    stability = summarize_window_stability(rescan_results) if rescan_results else {
        "stable": [], "recent_only": [], "strengthening": [], "unstable": []
    }

    # Section 1: Stable findings.
    stable_findings = stability["stable"]

    # Section 2: Strengthened findings.
    strengthened_findings = stability["strengthening"]

    # Section 3: Candidate interactions — real ranked output or threshold statement.
    candidate_interactions = _build_candidate_interactions_section(interaction_results)

    # Section 4: Registry tuning candidates — real ranked output or threshold statement.
    registry_tuning_candidates = _build_tuning_section(tuning_results)

    # Section 5: Discarded experiments.
    discarded = [
        {
            "target_name": e.target_name,
            "loop_type": e.loop_type,
            "failure_reason": e.failure_reason,
            "runtime_ms": e.runtime_ms,
        }
        for e in experiment_rows
        if not e.kept
    ]

    # Section 6: Score summary — WS2 real FQS values per loop family.
    score_summary = _build_score_summary(
        experiment_rows=experiment_rows,
        rescan_results=rescan_results,
        stability=stability,
    )

    # Section 7: No-surface guarantee.
    no_surface_guarantee = {
        "athlete_facing_surfaces_mutated": False,
        "production_registry_values_mutated": False,
        "production_cache_polluted": False,
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
        "stable_findings": stable_findings,
        "strengthened_findings": strengthened_findings,
        "candidate_interactions": candidate_interactions,
        "registry_tuning_candidates": registry_tuning_candidates,
        "discarded_experiments": discarded,
        "score_summary": score_summary,
        "no_surface_guarantee": no_surface_guarantee,
        "window_stability_detail": stability,
    }


def _build_candidate_interactions_section(
    interaction_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build the candidate_interactions report section.

    Returns ranked candidates or an explicit threshold statement.
    """

    if not interaction_results:
        return {
            "cleared_threshold": False,
            "candidates": [],
            "reason": "interaction_scan loop not enabled in this run",
        }

    all_candidates: List[Dict[str, Any]] = []
    for result in interaction_results:
        summary = result.get("result_summary", {})
        top = summary.get("top_interactions", [])
        for cand in top:
            if cand.get("interaction_score", 0) >= INTERACTION_KEEP_THRESHOLD:
                all_candidates.append({
                    "output_metric": summary.get("output_metric"),
                    "factors": cand.get("factors"),
                    "effect_size": cand.get("effect_size"),
                    "interaction_score": cand.get("interaction_score"),
                    "score_components": cand.get("score_components"),
                    "n_high": cand.get("n_high"),
                    "n_low": cand.get("n_low"),
                    "direction_label": cand.get("direction_label"),
                })

    all_candidates.sort(key=lambda x: -(x.get("interaction_score") or 0))

    if not all_candidates:
        # Collect threshold statements from each metric.
        threshold_details = [
            r.get("result_summary", {}).get("threshold_statement")
            for r in interaction_results
            if r.get("result_summary", {}).get("threshold_statement")
        ]
        reason = (
            "interactions were tested across all metrics; "
            f"none exceeded score threshold {INTERACTION_KEEP_THRESHOLD}"
        )
        return {
            "cleared_threshold": False,
            "candidates": [],
            "reason": reason,
            "metric_details": threshold_details,
        }

    return {
        "cleared_threshold": True,
        "candidates": all_candidates[:20],  # top 20 across all metrics
    }


def _build_tuning_section(
    tuning_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the registry_tuning_candidates report section."""
    if not tuning_results:
        return {
            "cleared_threshold": False,
            "candidates": [],
            "reason": "registry_tuning loop not enabled in this run",
        }
    return summarize_tuning_results(tuning_results)


def _build_score_summary(
    experiment_rows: List[AutoDiscoveryExperiment],
    rescan_results: List[Dict[str, Any]],
    stability: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Phase 0B score summary — real FQS values per loop family.
    """
    summary: Dict[str, Any] = {}

    # Correlation rescan.
    rescan_exps = [e for e in experiment_rows if e.loop_type == "correlation_rescan"]
    kept_rescan = [e for e in rescan_exps if e.kept]
    if rescan_exps:
        scores = [e.baseline_score for e in rescan_exps if e.baseline_score is not None]
        agg_baseline = round(sum(scores) / len(scores), 4) if scores else None
        summary["correlation_rescan"] = {
            "experiments_run": len(rescan_exps),
            "kept": len(kept_rescan),
            "aggregate_baseline_score": agg_baseline,
            "aggregate_candidate_score": None,  # no candidate for rescan
            "aggregate_score_delta": None,
            "stable_finding_count": len(stability.get("stable", [])),
            "strengthening_finding_count": len(stability.get("strengthening", [])),
            "recent_only_count": len(stability.get("recent_only", [])),
            "unstable_count": len(stability.get("unstable", [])),
        }

    # Interaction scan.
    interaction_exps = [e for e in experiment_rows if e.loop_type == "interaction_scan"]
    kept_interaction = [e for e in interaction_exps if e.kept]
    if interaction_exps:
        summary["interaction_scan"] = {
            "experiments_run": len(interaction_exps),
            "kept": len(kept_interaction),
            "aggregate_baseline_score": None,  # interaction uses count-based baseline
            "aggregate_candidate_score": None,
            "aggregate_score_delta": None,
        }

    # Registry tuning.
    tuning_exps = [e for e in experiment_rows if e.loop_type == "registry_tuning"]
    kept_tuning = [e for e in tuning_exps if e.kept]
    if tuning_exps:
        b_scores = [e.baseline_score for e in tuning_exps if e.baseline_score is not None]
        c_scores = [e.candidate_score for e in tuning_exps if e.candidate_score is not None]
        d_scores = [e.score_delta for e in tuning_exps if e.score_delta is not None]
        summary["registry_tuning"] = {
            "experiments_run": len(tuning_exps),
            "kept": len(kept_tuning),
            "aggregate_baseline_score": round(sum(b_scores) / len(b_scores), 4) if b_scores else None,
            "aggregate_candidate_score": round(sum(c_scores) / len(c_scores), 4) if c_scores else None,
            "aggregate_score_delta": round(sum(d_scores) / len(d_scores), 4) if d_scores else None,
        }

    return summary
