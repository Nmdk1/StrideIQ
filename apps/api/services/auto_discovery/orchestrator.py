"""
AutoDiscovery Orchestrator — Phase 1 (live mutation + safety + observability).

Phase 0C shadow pass is preserved and always runs.  When live mutation is
enabled (``auto_discovery.mutation.live`` flag), Phase 1 adds:
  - Deep-window CorrelationFinding promotion
  - Stability annotation on existing findings
  - Interaction finding promotion (after 3+ nightly runs)
  - Per-athlete investigation tuning apply (after 2+ consecutive kept runs)
  - Typed durable change ledger (auto_discovery_change_log)
  - Per-athlete transaction boundary with auto-disable thresholds
  - Scan coverage persistence

Safety contracts:
- Global kill switch: ``auto_discovery.mutation.live`` off → shadow only.
- Per-loop kill switches: auto_promote.findings, auto_promote.stability,
  auto_promote.tuning independently disableable.
- If error rate for a loop exceeds threshold, promotion auto-disables for run.
- Per-athlete transaction boundary: all mutations or none commit.
- All mutations write to change_log for audit and revert.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import AutoDiscoveryRun, AutoDiscoveryExperiment, AutoDiscoveryCandidate
from services.auto_discovery.rescan_loop import (
    run_multiwindow_rescan,
    summarize_window_stability,
    promote_deep_window_findings,
    annotate_finding_stability,
)
from services.auto_discovery.fqs_adapters import CorrelationFindingFQSAdapter
from services.auto_discovery.interaction_loop import (
    run_pairwise_interaction_scan,
    INTERACTION_KEEP_THRESHOLD,
    promote_interaction_findings,
)
from services.auto_discovery.tuning_loop import (
    run_pilot_tuning_loop,
    summarize_tuning_results,
    apply_tuning_improvement,
    count_consecutive_kept_runs,
)
from services.auto_discovery.feature_flags import (
    is_live_mutation_enabled,
    is_auto_promote_findings_enabled,
    is_auto_promote_stability_enabled,
    is_auto_promote_tuning_enabled,
)

logger = logging.getLogger(__name__)

_PHASE = "1"
_SCHEMA_VERSION = 4

# ── Phase 1 auto-disable thresholds ─────────────────────────────────────────
# Stop promotion for a loop if error rate exceeds this fraction in one run
_MAX_LOOP_ERROR_RATE = 0.20
# Hard caps on mutations per athlete per run
_MAX_MUTATIONS_PER_ATHLETE = 20
_MAX_TOTAL_MUTATIONS_PER_RUN = 50
# Consecutive runs required before a tuning improvement can be applied
_TUNING_CONSECUTIVE_RUNS = 2


def run_auto_discovery_for_athlete(
    athlete_id: UUID,
    db: Session,
    enabled_loops: Optional[List[str]] = None,
) -> AutoDiscoveryRun:
    """
    Execute one full AutoDiscovery pass for the athlete.

    Phase 0C shadow pass always runs first (experiment ledger, candidate memory).
    Phase 1 live mutation runs only when ``auto_discovery.mutation.live`` is
    enabled for the athlete.

    Per-athlete transaction contract: if live mutation is enabled, all mutations
    for this athlete either commit together or are rolled back entirely.
    The change ledger captures every applied mutation for audit and revert.

    Parameters
    ----------
    athlete_id:
        UUID of the athlete.  Must be in the feature-flag allowlist.
    db:
        Live SQLAlchemy session.  Caller must NOT commit before calling
        this function; this function owns the final commit.
    enabled_loops:
        Loop families to run.  Default: ["correlation_rescan"].
        Phase 0B/1 adds: "interaction_scan", "registry_tuning".

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

    # ── WS2: Upsert durable cross-run candidates ────────────────────────────
    _upsert_candidates(
        athlete_id=athlete_id,
        run=run,
        report=report,
        db=db,
    )

    # ── Phase 1: Live mutation block ─────────────────────────────────────────
    # Runs only when auto_discovery.mutation.live is enabled for this athlete.
    # Per-athlete transaction contract: all mutations commit together or
    # the entire mutation block is rolled back (shadow data is preserved).
    phase1_summary = _run_phase1_mutations(
        athlete_id=athlete_id,
        run=run,
        all_rescan_results=all_rescan_results,
        experiment_rows=experiment_rows,
        db=db,
    )
    if phase1_summary:
        report["phase1_mutations"] = phase1_summary

    db.commit()
    logger.info(
        "AutoDiscovery Phase 1: athlete=%s status=%s experiments=%d duration_s=%.1f",
        athlete_id_str,
        run.status,
        run.experiment_count,
        (finished_at - started_at).total_seconds(),
    )
    return run


# ── Phase 1: Live mutation executor ────────────────────────────────────────

def _run_phase1_mutations(
    athlete_id: UUID,
    run: AutoDiscoveryRun,
    all_rescan_results: List[Dict[str, Any]],
    experiment_rows: List[AutoDiscoveryExperiment],
    db: Session,
) -> Optional[Dict[str, Any]]:
    """Execute Phase 1 live mutations for the athlete.

    Returns a summary dict to embed in the run report, or None if mutation
    is not enabled for this athlete.

    Per-athlete transaction contract: if any step raises an unexpected error,
    the entire mutation block is rolled back and an error record is returned
    instead of propagating the exception.
    """
    athlete_id_str = str(athlete_id)

    if not is_live_mutation_enabled(athlete_id_str, db):
        return None

    summary: Dict[str, Any] = {
        "mutation_live": True,
        "findings_promoted": [],
        "stability_annotated": 0,
        "interactions_promoted": [],
        "tuning_applied": [],
        "change_log_ids": [],
        "auto_disabled_loops": [],
        "error": None,
    }

    mutation_count = 0

    try:
        # ── 1: Deep-window finding promotion ──────────────────────────────
        if is_auto_promote_findings_enabled(athlete_id_str, db):
            rescan_experiments = [
                e for e in experiment_rows if e.loop_type == "correlation_rescan"
            ]
            error_count = sum(1 for e in rescan_experiments if e.failure_reason)
            total = len(rescan_experiments)
            error_rate = (error_count / total) if total else 0.0

            if error_rate > _MAX_LOOP_ERROR_RATE:
                summary["auto_disabled_loops"].append({
                    "loop": "rescan_promotion",
                    "reason": f"error_rate {error_rate:.2f} > threshold {_MAX_LOOP_ERROR_RATE}",
                    "error_count": error_count,
                    "total": total,
                })
                logger.warning(
                    "Phase 1: auto-disabled rescan promotion for athlete=%s (error_rate=%.2f)",
                    athlete_id_str, error_rate,
                )
            elif mutation_count < _MAX_MUTATIONS_PER_ATHLETE:
                promoted, count = promote_deep_window_findings(
                    athlete_id=athlete_id,
                    rescan_results=all_rescan_results,
                    db=db,
                )
                for p in promoted:
                    change_log_id = _write_change_log(
                        athlete_id=athlete_id,
                        run_id=run.id,
                        change_type="new_correlation_finding",
                        change_key=_finding_change_key(athlete_id_str, p),
                        before_state=None,
                        after_state=p,
                        db=db,
                    )
                    if change_log_id:
                        summary["change_log_ids"].append(str(change_log_id))
                    mutation_count += 1
                summary["findings_promoted"] = promoted

        # ── 2: Stability annotation ────────────────────────────────────────
        if is_auto_promote_stability_enabled(athlete_id_str, db):
            count = annotate_finding_stability(
                athlete_id=athlete_id,
                rescan_results=all_rescan_results,
                db=db,
            )
            summary["stability_annotated"] = count
            if count > 0:
                _write_change_log(
                    athlete_id=athlete_id,
                    run_id=run.id,
                    change_type="stability_annotation",
                    change_key=f"stability:{athlete_id_str}:{run.id}",
                    before_state=None,
                    after_state={"count": count},
                    db=db,
                )
                mutation_count += count

        # ── 3: Interaction finding promotion ──────────────────────────────
        if is_auto_promote_findings_enabled(athlete_id_str, db):
            interaction_experiments = [
                e for e in experiment_rows if e.loop_type == "interaction_scan"
            ]
            error_count = sum(1 for e in interaction_experiments if e.failure_reason)
            total = len(interaction_experiments)
            error_rate = (error_count / total) if total else 0.0

            if error_rate > _MAX_LOOP_ERROR_RATE:
                summary["auto_disabled_loops"].append({
                    "loop": "interaction_promotion",
                    "reason": f"error_rate {error_rate:.2f} > threshold {_MAX_LOOP_ERROR_RATE}",
                })
            elif mutation_count < _MAX_MUTATIONS_PER_ATHLETE:
                promoted = promote_interaction_findings(athlete_id=athlete_id, db=db)
                for p in promoted:
                    change_log_id = _write_change_log(
                        athlete_id=athlete_id,
                        run_id=run.id,
                        change_type="new_interaction_finding",
                        change_key=p.get("finding_key", ""),
                        before_state=None,
                        after_state=p,
                        db=db,
                    )
                    if change_log_id:
                        summary["change_log_ids"].append(str(change_log_id))
                    mutation_count += 1
                summary["interactions_promoted"] = promoted

        # ── 4: Tuning apply ────────────────────────────────────────────────
        if is_auto_promote_tuning_enabled(athlete_id_str, db):
            tuning_experiments = [
                e for e in experiment_rows
                if e.loop_type == "registry_tuning" and e.kept
            ]
            error_count = sum(1 for e in [
                x for x in experiment_rows if x.loop_type == "registry_tuning"
            ] if e.failure_reason)
            total_tuning = len([x for x in experiment_rows if x.loop_type == "registry_tuning"])
            tuning_error_rate = (error_count / total_tuning) if total_tuning else 0.0

            if tuning_error_rate > _MAX_LOOP_ERROR_RATE:
                summary["auto_disabled_loops"].append({
                    "loop": "tuning_apply",
                    "reason": f"error_rate {tuning_error_rate:.2f} > threshold {_MAX_LOOP_ERROR_RATE}",
                })
            else:
                applied = _apply_proven_tuning(
                    athlete_id=athlete_id,
                    tuning_experiments=tuning_experiments,
                    run=run,
                    db=db,
                )
                summary["tuning_applied"] = applied
                for a in applied:
                    mutation_count += 1

    except Exception as exc:
        logger.error(
            "Phase 1 mutation error for athlete=%s: %s — rolling back phase1 mutations",
            athlete_id_str, exc,
        )
        # Roll back only the Phase 1 mutations; shadow data (experiments, candidates)
        # was already flushed — we re-add the run after rollback.
        try:
            db.rollback()
            db.add(run)
            db.flush()
        except Exception:
            pass
        summary["error"] = str(exc)
        summary["mutation_live"] = False

    return summary


def _apply_proven_tuning(
    athlete_id: UUID,
    tuning_experiments: List[AutoDiscoveryExperiment],
    run: AutoDiscoveryRun,
    db: Session,
) -> List[Dict[str, Any]]:
    """Apply tuning experiments that have been kept for enough consecutive runs."""
    applied: List[Dict[str, Any]] = []

    seen_investigations: Dict[str, Dict[str, Any]] = {}
    for exp in tuning_experiments:
        target_name = exp.target_name or ""
        parts = target_name.split(":")
        if len(parts) < 2:
            continue
        inv_name = parts[1]
        if inv_name not in seen_investigations or (exp.score_delta or 0) > (seen_investigations[inv_name].get("score_delta") or 0):
            seen_investigations[inv_name] = {
                "experiment": exp,
                "score_delta": exp.score_delta,
                "candidate_config": exp.candidate_config,
                "result_summary": exp.result_summary,
            }

    for inv_name, best in seen_investigations.items():
        exp = best["experiment"]
        consecutive = count_consecutive_kept_runs(athlete_id, inv_name, db, _TUNING_CONSECUTIVE_RUNS)
        if consecutive < _TUNING_CONSECUTIVE_RUNS:
            logger.info(
                "Tuning Phase 1: skipping %s — only %d/%d consecutive kept runs",
                inv_name, consecutive, _TUNING_CONSECUTIVE_RUNS,
            )
            continue

        param_overrides = (exp.candidate_config or {}).get("changed_delta") or {}
        if not param_overrides:
            param_overrides = exp.candidate_config or {}

        # First write the change log so we have an ID for the config FK
        before_state = (exp.result_summary or {}).get("baseline_config")
        after_state = {
            "investigation_name": inv_name,
            "param_overrides": param_overrides,
            "score_delta": exp.score_delta,
        }
        change_log_id = _write_change_log(
            athlete_id=athlete_id,
            run_id=run.id,
            change_type="tuning_override_applied",
            change_key=_tuning_change_key(str(athlete_id), inv_name, param_overrides),
            before_state=before_state,
            after_state=after_state,
            db=db,
        )

        was_applied = apply_tuning_improvement(
            athlete_id=athlete_id,
            investigation_name=inv_name,
            param_overrides=param_overrides,
            run_id=run.id,
            change_log_id=change_log_id,
            db=db,
        )

        if was_applied:
            applied.append({
                "investigation_name": inv_name,
                "param_overrides": param_overrides,
                "score_delta": exp.score_delta,
                "change_log_id": str(change_log_id) if change_log_id else None,
            })

    return applied


def _write_change_log(
    athlete_id: UUID,
    run_id: UUID,
    change_type: str,
    change_key: str,
    before_state: Optional[Any],
    after_state: Optional[Any],
    db: Session,
) -> Optional[UUID]:
    """Write one row to auto_discovery_change_log.

    Returns the new row id, or None if the row already exists (idempotent).
    """
    from models import AutoDiscoveryChangeLog
    from sqlalchemy.exc import IntegrityError

    row_id = _uuid.uuid4()
    row = AutoDiscoveryChangeLog(
        id=row_id,
        run_id=run_id,
        athlete_id=athlete_id,
        change_type=change_type,
        change_key=change_key,
        before_state=before_state,
        after_state=after_state,
        reverted=False,
    )
    try:
        db.add(row)
        db.flush()
        return row_id
    except IntegrityError:
        db.rollback()
        return None


def _finding_change_key(athlete_id_str: str, finding_dict: Dict[str, Any]) -> str:
    import hashlib
    import json
    parts = {
        "athlete": athlete_id_str,
        "input": finding_dict.get("input_name"),
        "output": finding_dict.get("output_metric"),
        "direction": finding_dict.get("direction"),
        "lag": finding_dict.get("lag_days", 0),
        "source": "auto_discovery",
    }
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:32]


def _tuning_change_key(athlete_id_str: str, inv_name: str, param_overrides: Dict[str, Any]) -> str:
    import hashlib
    import json
    parts = {
        "athlete": athlete_id_str,
        "investigation": inv_name,
        "params": json.dumps(param_overrides, sort_keys=True),
    }
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:32]


# ── FQS rescan scoring ─────────────────────────────────────────────────────

def _score_rescan_window(
    result_summary: Dict[str, Any],
    adapter: CorrelationFindingFQSAdapter,
) -> Dict[str, Any]:
    """
    Compute aggregate FQS scores for a single window's correlation dicts.

    Returns a dict with per-finding scores, aggregate stats, and a compact
    score_provenance block (WS1-1B) for founder-review output.
    """
    findings_by_metric = result_summary.get("findings_by_metric", {})
    all_scores: List[float] = []
    scored_per_metric: Dict[str, List[float]] = {}
    # Collect component values across all scored findings for provenance.
    all_component_values: List[Dict[str, float]] = []

    for metric, correlations in findings_by_metric.items():
        metric_scores: List[float] = []
        for c in correlations:
            fqs = adapter.score_shadow_dict(c)
            metric_scores.append(fqs["final_score"])
            all_component_values.append(fqs.get("components", {}))
        scored_per_metric[metric] = metric_scores
        all_scores.extend(metric_scores)

    total = len(all_scores)
    aggregate = round(sum(all_scores) / total, 4) if total else 0.0

    # Build compact provenance block (WS1-1B).
    score_provenance = _build_rescan_provenance(
        adapter=adapter, all_component_values=all_component_values
    )

    return {
        "total_scored": total,
        "aggregate_final_score": aggregate,
        "per_metric_avg": {
            m: round(sum(s) / len(s), 4) if s else 0.0
            for m, s in scored_per_metric.items()
        },
        "score_provenance": score_provenance,
    }


def _build_rescan_provenance(
    adapter: CorrelationFindingFQSAdapter,
    all_component_values: List[Dict[str, float]],
) -> Dict[str, Any]:
    """
    Build the compact score_provenance block for a rescan window.

    Shape:
        component_values: average of each component across all scored findings
        component_quality: labels from adapter (exact/inferred/registry_default)
        has_inferred_components: True if any component is not 'exact'
    """
    quality = adapter.COMPONENT_QUALITY
    has_inferred = any(v != "exact" for v in quality.values())

    if not all_component_values:
        return {
            "component_values": {},
            "component_quality": quality,
            "has_inferred_components": has_inferred,
        }

    component_keys = list(all_component_values[0].keys())
    avg_components = {
        k: round(
            sum(cv.get(k, 0.0) for cv in all_component_values) / len(all_component_values),
            4,
        )
        for k in component_keys
    }
    return {
        "component_values": avg_components,
        "component_quality": quality,
        "has_inferred_components": has_inferred,
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
        # WS1-1A: aggregate real interaction scores from kept experiments.
        # The pairwise loop is discovery-only (no A/B candidate variant), so
        # aggregate_candidate_score and aggregate_delta are structurally absent —
        # this is not a placeholder; it reflects the loop's single-arm design.
        # We report aggregate_interaction_score (mean kept interaction_score) so
        # the summary is value-bearing when kept candidates exist.
        kept_scores_int = [
            e.baseline_score for e in kept_interaction
            if e.baseline_score is not None
        ]
        all_scores_int = [
            e.baseline_score for e in interaction_exps
            if e.baseline_score is not None
        ]
        agg_kept = (
            round(sum(kept_scores_int) / len(kept_scores_int), 4)
            if kept_scores_int else None
        )
        agg_all = (
            round(sum(all_scores_int) / len(all_scores_int), 4)
            if all_scores_int else None
        )
        summary["interaction_scan"] = {
            "experiments_run": len(interaction_exps),
            "kept": len(kept_interaction),
            # Mean interaction_score of kept candidates (null only when nothing kept).
            "aggregate_baseline_score": agg_kept,
            # Mean interaction_score across all tested experiments (value-bearing).
            "aggregate_all_score": agg_all,
            # Pairwise loop is single-arm (discovery only); no candidate variant exists.
            "aggregate_candidate_score": None,
            "aggregate_delta": None,
            "loop_design": "single_arm_discovery",
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


# ── WS2: Durable candidate memory ─────────────────────────────────────────

def _make_candidate_key(candidate_type: str, payload: Dict[str, Any]) -> str:
    """
    Build a deterministic stable key for a candidate.

    Key scheme:
      stable_finding / strengthened_finding:
        "input_name:output_name:direction"
      interaction:
        "factor1:factor2:output_metric:direction_label"  (factors sorted for stability)
      registry_tuning:
        "investigation:param_name:delta_repr"
    """
    if candidate_type in ("stable_finding", "strengthened_finding"):
        input_name = str(payload.get("input_name", "")).lower()
        output_name = str(payload.get("output_name", "")).lower()
        direction = str(payload.get("direction", "")).lower()
        return f"{input_name}:{output_name}:{direction}"

    if candidate_type == "interaction":
        factors = sorted(str(f).lower() for f in (payload.get("factors") or []))
        output = str(payload.get("output_metric", "")).lower()
        direction = str(payload.get("direction_label", "")).lower()
        return ":".join(factors) + f":{output}:{direction}"

    if candidate_type == "registry_tuning":
        inv = str(payload.get("investigation", "")).lower()
        param = str(payload.get("parameter_change") or payload.get("changed_param") or "").lower()
        # Represent the delta as sorted key=value pairs for determinism.
        delta = payload.get("parameter_change") or payload.get("changed_delta") or {}
        if isinstance(delta, dict):
            delta_repr = ",".join(f"{k}={v}" for k, v in sorted(delta.items()))
        else:
            delta_repr = str(delta).lower()
        return f"{inv}:{param}:{delta_repr}"

    # Fallback for unknown types.
    import hashlib
    import json
    return hashlib.md5(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _upsert_candidates(
    athlete_id: UUID,
    run: AutoDiscoveryRun,
    report: Dict[str, Any],
    db: Session,
) -> None:
    """
    Upsert durable cross-run candidates from the nightly report.

    For each candidate extracted from the report:
    - If new: insert with current_status='open', times_seen=1
    - If existing: increment times_seen, update last_seen_run_id, latest_summary,
      latest_score, latest_score_delta, provenance_snapshot.

    Critical: existing review state (approved/rejected/deferred) is NEVER
    overwritten by a re-appearance.  Only the above update fields change.

    No athlete-facing tables are touched.
    """
    from sqlalchemy.exc import IntegrityError

    now = datetime.now(timezone.utc)
    athlete_id_uuid = athlete_id if isinstance(athlete_id, _uuid.UUID) else _uuid.UUID(str(athlete_id))
    run_id = run.id

    # Gather candidate payloads from the report.
    candidates_to_upsert: List[Dict[str, Any]] = []

    # Stable findings → candidate_type "stable_finding"
    for f in report.get("stable_findings", []):
        candidates_to_upsert.append({
            "candidate_type": "stable_finding",
            "payload": f,
            "score": f.get("avg_score"),
            "score_delta": None,
            "provenance": f.get("score_provenance"),
        })

    # Strengthened findings → candidate_type "strengthened_finding"
    for f in report.get("strengthened_findings", []):
        candidates_to_upsert.append({
            "candidate_type": "strengthened_finding",
            "payload": f,
            "score": f.get("avg_score"),
            "score_delta": None,
            "provenance": f.get("score_provenance"),
        })

    # Interaction candidates
    interaction_section = report.get("candidate_interactions", {})
    if interaction_section.get("cleared_threshold"):
        for cand in interaction_section.get("candidates", []):
            # Build interaction provenance from score_components already on the candidate.
            sc = cand.get("score_components") or {}
            interaction_provenance = {
                "component_values": sc,
                "component_quality": {
                    "effect_size_norm": "exact",
                    "sample_support": "exact",
                },
                "has_inferred_components": False,
            } if sc else None
            candidates_to_upsert.append({
                "candidate_type": "interaction",
                "payload": cand,
                "score": cand.get("interaction_score"),
                "score_delta": None,
                "provenance": interaction_provenance,
            })

    # Registry tuning candidates
    tuning_section = report.get("registry_tuning_candidates", {})
    if tuning_section.get("cleared_threshold"):
        for cand in tuning_section.get("candidates", []):
            candidates_to_upsert.append({
                "candidate_type": "registry_tuning",
                "payload": cand,
                "score": cand.get("candidate_score"),
                "score_delta": cand.get("score_delta"),
                # score_provenance is the key added by summarize_tuning_results.
                "provenance": cand.get("score_provenance"),
            })

    for item in candidates_to_upsert:
        ctype = item["candidate_type"]
        payload = item["payload"]
        ckey = _make_candidate_key(ctype, payload)

        try:
            existing = (
                db.query(AutoDiscoveryCandidate)
                .filter_by(
                    athlete_id=athlete_id_uuid,
                    candidate_type=ctype,
                    candidate_key=ckey,
                )
                .first()
            )

            if existing is None:
                candidate = AutoDiscoveryCandidate(
                    id=_uuid.uuid4(),
                    athlete_id=athlete_id_uuid,
                    candidate_type=ctype,
                    candidate_key=ckey,
                    first_seen_run_id=run_id,
                    last_seen_run_id=run_id,
                    times_seen=1,
                    current_status="open",
                    latest_summary=payload,
                    latest_score=item["score"],
                    latest_score_delta=item["score_delta"],
                    provenance_snapshot=item["provenance"],
                    created_at=now,
                    updated_at=now,
                )
                db.add(candidate)
            else:
                # Update mutable tracking fields; preserve review state.
                existing.last_seen_run_id = run_id
                existing.times_seen = (existing.times_seen or 0) + 1
                existing.latest_summary = payload
                if item["score"] is not None:
                    existing.latest_score = item["score"]
                if item["score_delta"] is not None:
                    existing.latest_score_delta = item["score_delta"]
                if item["provenance"] is not None:
                    existing.provenance_snapshot = item["provenance"]
                existing.updated_at = now

            db.flush()

        except IntegrityError:
            db.rollback()
            logger.warning(
                "AutoDiscovery candidate upsert: race condition on (%s, %s, %s); skipping",
                athlete_id_uuid, ctype, ckey,
            )


# ── WS3: Founder review state machine ─────────────────────────────────────

def review_candidate(
    candidate_id: _uuid.UUID,
    action: str,
    db: Session,
    note: Optional[str] = None,
    promotion_target: Optional[str] = None,
) -> AutoDiscoveryCandidate:
    """
    Apply a founder review action to an AutoDiscoveryCandidate.

    Valid actions:
        "approve"  → current_status = "approved"
        "reject"   → current_status = "rejected"
        "defer"    → current_status = "deferred"
        "stage"    → current_status = "approved", promotion_target = <target>
                     (candidate must already be approved or action is "stage")

    Persists an AutoDiscoveryReviewLog row for full auditability.

    Raises ValueError for invalid action or unknown candidate.
    Safety: no athlete-facing tables are touched.
    """
    from models import AutoDiscoveryReviewLog

    valid_actions = {"approve", "reject", "defer", "stage"}
    if action not in valid_actions:
        raise ValueError(f"Invalid action '{action}'. Must be one of: {sorted(valid_actions)}")

    candidate = db.query(AutoDiscoveryCandidate).filter_by(id=candidate_id).first()
    if candidate is None:
        raise ValueError(f"AutoDiscoveryCandidate {candidate_id} not found")

    previous_status = candidate.current_status

    if action == "approve":
        new_status = "approved"
    elif action == "reject":
        new_status = "rejected"
    elif action == "defer":
        new_status = "deferred"
    elif action == "stage":
        if promotion_target is None:
            raise ValueError(
                "promotion_target is required for action='stage'. "
                "Valid values: surface_candidate, registry_change_candidate, "
                "investigation_upgrade_candidate, manual_research_candidate"
            )
        # Staging requires an already-approved candidate — explicit discipline.
        if candidate.current_status != "approved":
            raise ValueError(
                f"Cannot stage candidate with status='{candidate.current_status}'. "
                "Candidate must be approved first (action='approve') before staging."
            )
        valid_targets = {
            "surface_candidate",
            "registry_change_candidate",
            "investigation_upgrade_candidate",
            "manual_research_candidate",
        }
        if promotion_target not in valid_targets:
            raise ValueError(
                f"Invalid promotion_target '{promotion_target}'. "
                f"Must be one of: {sorted(valid_targets)}"
            )
        new_status = "approved"  # status unchanged; only promotion_target is set
        candidate.promotion_target = promotion_target
        if note:
            candidate.promotion_note = note
    else:
        raise ValueError(f"Unknown action: {action}")

    now = datetime.now(timezone.utc)
    candidate.current_status = new_status
    candidate.reviewed_at = now
    candidate.updated_at = now
    if note and action != "stage":
        candidate.promotion_note = note

    log = AutoDiscoveryReviewLog(
        id=_uuid.uuid4(),
        candidate_id=candidate.id,
        athlete_id=candidate.athlete_id,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        promotion_target=promotion_target,
        note=note,
        created_at=now,
    )
    db.add(log)
    db.commit()

    logger.info(
        "AutoDiscovery review: candidate=%s action=%s %s→%s",
        candidate_id, action, previous_status, new_status,
    )
    return candidate


# ── WS5: Founder review query ──────────────────────────────────────────────

def get_founder_review_summary(
    athlete_id: UUID,
    db: Session,
) -> Dict[str, Any]:
    """
    Return a structured founder-review summary for a single athlete.

    Sections:
      open_by_value       — open candidates sorted by latest_score desc
      seen_multiple_times — candidates with times_seen >= 2
      approved            — approved candidates (staged ones last)
      rejected            — rejected candidates
      deferred            — deferred candidates
    """
    athlete_id_uuid = athlete_id if isinstance(athlete_id, _uuid.UUID) else _uuid.UUID(str(athlete_id))

    all_candidates = (
        db.query(AutoDiscoveryCandidate)
        .filter_by(athlete_id=athlete_id_uuid)
        .all()
    )

    open_candidates = [c for c in all_candidates if c.current_status == "open"]
    approved = [c for c in all_candidates if c.current_status == "approved"]
    rejected = [c for c in all_candidates if c.current_status == "rejected"]
    deferred = [c for c in all_candidates if c.current_status == "deferred"]

    def _serialize(c: AutoDiscoveryCandidate) -> Dict[str, Any]:
        return {
            "id": str(c.id),
            "candidate_type": c.candidate_type,
            "candidate_key": c.candidate_key,
            "current_status": c.current_status,
            "times_seen": c.times_seen,
            "latest_score": c.latest_score,
            "latest_score_delta": c.latest_score_delta,
            "first_seen_run_id": str(c.first_seen_run_id),
            "last_seen_run_id": str(c.last_seen_run_id),
            "promotion_target": c.promotion_target,
            "promotion_note": c.promotion_note,
            "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
            "latest_summary": c.latest_summary,
            "provenance_snapshot": c.provenance_snapshot,
        }

    # Sort open by value (latest_score desc, times_seen desc for ties).
    open_sorted = sorted(
        open_candidates,
        key=lambda c: (-(c.latest_score or 0.0), -(c.times_seen or 0)),
    )

    recurring = [c for c in open_sorted if (c.times_seen or 0) >= 2]

    return {
        "athlete_id": str(athlete_id_uuid),
        "total_candidates": len(all_candidates),
        "open_by_value": [_serialize(c) for c in open_sorted],
        "seen_multiple_times": [_serialize(c) for c in recurring],
        "approved": [_serialize(c) for c in approved],
        "rejected": [_serialize(c) for c in rejected],
        "deferred": [_serialize(c) for c in deferred],
    }
