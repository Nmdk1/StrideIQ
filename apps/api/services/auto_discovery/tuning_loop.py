"""
Pilot Registry Tuning Loop — Phase 0B (founder-only, shadow mode).

Turns pilot InvestigationParamSpec metadata into actual shadow tuning
experiments.  For each pilot investigation, generates bounded candidate
parameter sets and evaluates them against the athlete's historical corpus.

Scope (Phase 0B):
- Pilot subset of 6 investigations only.
- Bounded mechanical candidate generation: step up/down for numeric params.
- No LLM proposals.  No broad random search.
- Keep/discard rule is explicit and test-covered.

Safety guarantees:
- No writes to AthleteFinding, CorrelationFinding, or any athlete-facing table.
- No production registry values are changed.
- Results are returned as dicts; orchestrator owns persistence.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Keep threshold: candidate must score this much better than baseline.
TUNING_KEEP_THRESHOLD = 0.03  # 3 FQS points improvement

# Pilot investigation names (must match INVESTIGATION_REGISTRY).
PILOT_INVESTIGATIONS = [
    "investigate_pace_at_hr_adaptation",
    "investigate_heat_tax",
    "investigate_long_run_durability",
    "investigate_interval_recovery_trend",
    "investigate_workout_variety_effect",
    "investigate_stride_progression",
]

# Step sizes for bounded numeric candidate generation (as fraction of range).
_STEP_FRACTION = 0.2  # 20% of param range per step


def run_pilot_tuning_loop(
    athlete_id: UUID,
    db: Session,
) -> List[Dict[str, Any]]:
    """
    Run shadow registry tuning for all enabled pilot investigations.

    Returns experiment-result dicts (one per investigation × candidate config)
    suitable for writing to `auto_discovery_experiment`.

    No production tables are mutated.
    """
    from services.race_input_analysis import (
        INVESTIGATION_REGISTRY,
        InvestigationSpec,
    )
    from services.auto_discovery.fqs_adapters import AthleteFindingFQSAdapter

    athlete_id_str = str(athlete_id)
    adapter = AthleteFindingFQSAdapter()

    # Index pilot specs by name.
    pilot_specs: Dict[str, InvestigationSpec] = {
        spec.name: spec
        for spec in INVESTIGATION_REGISTRY
        if spec.name in PILOT_INVESTIGATIONS and spec.shadow_enabled
    }

    experiment_results: List[Dict[str, Any]] = []

    for inv_name in PILOT_INVESTIGATIONS:
        spec = pilot_specs.get(inv_name)
        if spec is None:
            logger.debug("Tuning: investigation %s not in shadow-enabled pilot; skipping", inv_name)
            continue
        if not spec.tunable_params:
            logger.debug("Tuning: investigation %s has no tunable params; skipping", inv_name)
            continue

        # Run baseline once.
        baseline_config = {p.name: p.default for p in spec.tunable_params}
        baseline_findings, baseline_error = _run_with_config(
            inv_name=inv_name,
            params=baseline_config,
            athlete_id=athlete_id,
            db=db,
        )
        baseline_score = adapter.score_finding_list(baseline_findings)

        # Generate bounded candidates from each tunable param.
        for param_spec in spec.tunable_params:
            candidates = _generate_candidates(param_spec)
            for candidate_config_delta in candidates:
                candidate_params = {**baseline_config, **candidate_config_delta}
                # Skip if identical to baseline.
                if candidate_params == baseline_config:
                    continue

                t0 = time.monotonic()
                candidate_findings, candidate_error = _run_with_config(
                    inv_name=inv_name,
                    params=candidate_params,
                    athlete_id=athlete_id,
                    db=db,
                )
                runtime_ms = int((time.monotonic() - t0) * 1000)

                candidate_score = adapter.score_finding_list(candidate_findings)
                score_delta = round(candidate_score - baseline_score, 4)
                kept, rationale = _apply_keep_rule(
                    score_delta=score_delta,
                    baseline_score=baseline_score,
                    candidate_score=candidate_score,
                    baseline_findings=baseline_findings,
                    candidate_findings=candidate_findings,
                )

                experiment_results.append({
                    "loop_type": "registry_tuning",
                    "target_name": f"tuning:{inv_name}:{param_spec.name}",
                    "baseline_config": {
                        "investigation": inv_name,
                        "params": baseline_config,
                    },
                    "candidate_config": {
                        "investigation": inv_name,
                        "params": candidate_params,
                        "changed_param": param_spec.name,
                        "changed_delta": candidate_config_delta,
                    },
                    "baseline_score": round(baseline_score, 4),
                    "candidate_score": round(candidate_score, 4),
                    "score_delta": score_delta,
                    "kept": kept,
                    "result_summary": {
                        "investigation": inv_name,
                        "param_name": param_spec.name,
                        "baseline_findings_count": len(baseline_findings),
                        "candidate_findings_count": len(candidate_findings),
                        "kept": kept,
                        "rationale": rationale,
                        "baseline_error": baseline_error,
                        "candidate_error": candidate_error,
                        # WS1-1B: FQS provenance for founder review.
                        "score_provenance": _build_tuning_provenance(adapter),
                    },
                    "failure_reason": candidate_error,
                    "runtime_ms": runtime_ms,
                })
                logger.info(
                    "Tuning: athlete=%s inv=%s param=%s baseline=%.4f candidate=%.4f delta=%.4f kept=%s",
                    athlete_id_str, inv_name, param_spec.name,
                    baseline_score, candidate_score, score_delta, kept,
                )

    return experiment_results


def _generate_candidates(param_spec: Any) -> List[Dict[str, Any]]:
    """
    Generate bounded step up/down candidates from a single InvestigationParamSpec.

    Returns a list of {param_name: value} dicts (one per candidate).
    """
    candidates: List[Dict[str, Any]] = []
    name = param_spec.name

    if param_spec.param_type == "int":
        lo: int = param_spec.min_value
        hi: int = param_spec.max_value
        default: int = param_spec.default
        step = max(1, int((hi - lo) * _STEP_FRACTION))
        # Step down.
        if default - step >= lo:
            candidates.append({name: default - step})
        # Step up.
        if default + step <= hi:
            candidates.append({name: default + step})
    elif param_spec.param_type == "float":
        lo_f: float = param_spec.min_value
        hi_f: float = param_spec.max_value
        default_f: float = param_spec.default
        step_f = (hi_f - lo_f) * _STEP_FRACTION
        if default_f - step_f >= lo_f:
            candidates.append({name: round(default_f - step_f, 4)})
        if default_f + step_f <= hi_f:
            candidates.append({name: round(default_f + step_f, 4)})
    elif param_spec.param_type == "bool":
        # Only flip if explicitly safe_to_flip (default True if not specified).
        safe = getattr(param_spec, "safe_to_flip", True)
        if safe:
            candidates.append({name: not param_spec.default})

    return candidates


def _run_with_config(
    inv_name: str,
    params: Dict[str, Any],
    athlete_id: UUID,
    db: Session,
) -> Tuple[list, Optional[str]]:
    """
    Run an investigation under shadow parameter overrides.

    Shadow override approach: patch InvestigationSpec.min_activities and
    min_data_weeks for the duration of the call, then restore originals.
    This keeps the change local to the pilot subset and does not rewrite
    the investigation functions themselves.

    Returns (findings_list, error_string_or_None).
    """
    from services.race_input_analysis import (
        INVESTIGATION_REGISTRY,
        load_training_zones,
    )
    from models import PerformanceEvent

    spec = next((s for s in INVESTIGATION_REGISTRY if s.name == inv_name), None)
    if spec is None:
        return [], f"investigation {inv_name} not found in registry"

    # Load context required by pilot investigations.
    try:
        zones = load_training_zones(athlete_id, db)
        if not zones:
            return [], "no training zones available"

        events = db.query(PerformanceEvent).filter(
            PerformanceEvent.athlete_id == athlete_id,
            PerformanceEvent.user_confirmed == True,  # noqa: E712
        ).order_by(PerformanceEvent.event_date).all()
    except Exception as exc:
        return [], f"context load error: {exc}"

    # Temporarily override spec thresholds with shadow params.
    saved_min_activities = spec.min_activities
    saved_min_data_weeks = spec.min_data_weeks
    try:
        if "min_activities" in params:
            spec.min_activities = int(params["min_activities"])
        if "min_data_weeks" in params:
            spec.min_data_weeks = int(params["min_data_weeks"])

        result = spec.fn(athlete_id, db, zones, events)
    except Exception as exc:
        return [], str(exc)
    finally:
        # Always restore originals — shadow mode must leave registry unchanged.
        spec.min_activities = saved_min_activities
        spec.min_data_weeks = saved_min_data_weeks

    if result is None:
        return [], None
    if isinstance(result, list):
        return result, None
    return [result], None


def _apply_keep_rule(
    score_delta: float,
    baseline_score: float,
    candidate_score: float,
    baseline_findings: list,
    candidate_findings: list,
) -> Tuple[bool, str]:
    """
    Simple explicit keep rule for Phase 0B.

    Keep when:
    1. score_delta > TUNING_KEEP_THRESHOLD (3 FQS points improvement), AND
    2. candidate produces at least as many findings as baseline
       (no stability regression — losing findings is suspicious)

    Returns (kept: bool, rationale: str).
    """
    if score_delta <= TUNING_KEEP_THRESHOLD:
        return False, (
            f"score_delta {score_delta:.4f} does not exceed keep threshold "
            f"{TUNING_KEEP_THRESHOLD} (baseline={baseline_score:.4f}, "
            f"candidate={candidate_score:.4f})"
        )

    n_base = len(baseline_findings)
    n_cand = len(candidate_findings)
    if n_cand < n_base:
        return False, (
            f"stability regression: candidate produced {n_cand} findings "
            f"vs baseline {n_base}; discarded despite positive delta {score_delta:.4f}"
        )

    return True, (
        f"kept: score_delta {score_delta:.4f} > {TUNING_KEEP_THRESHOLD} "
        f"and finding count stable ({n_base} → {n_cand})"
    )


def summarize_tuning_results(
    experiment_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Produce a ranked summary of tuning candidates for the nightly report.

    Returns either ranked candidates or an explicit threshold-cleared statement.
    """
    kept_exps = [e for e in experiment_results if e.get("kept")]
    discarded_exps = [e for e in experiment_results if not e.get("kept")]

    if not experiment_results:
        return {
            "cleared_threshold": False,
            "candidates": [],
            "reason": "no pilot investigations were run in this session",
        }

    if not kept_exps:
        return {
            "cleared_threshold": False,
            "candidates": [],
            "reason": (
                f"{len(experiment_results)} experiments run across pilot investigations; "
                f"none exceeded keep threshold (delta > {TUNING_KEEP_THRESHOLD})"
            ),
            "top_discarded": [
                {
                    "investigation": e["result_summary"].get("investigation"),
                    "param": e["result_summary"].get("param_name"),
                    "score_delta": e.get("score_delta"),
                    "rationale": e["result_summary"].get("rationale"),
                }
                for e in sorted(discarded_exps, key=lambda x: -(x.get("score_delta") or 0))[:3]
            ],
        }

    ranked = sorted(kept_exps, key=lambda x: -(x.get("score_delta") or 0))
    return {
        "cleared_threshold": True,
        "candidates": [
            {
                "investigation": e["result_summary"].get("investigation"),
                "parameter_change": e["candidate_config"].get("changed_delta"),
                "baseline_score": e.get("baseline_score"),
                "candidate_score": e.get("candidate_score"),
                "score_delta": e.get("score_delta"),
                "kept": True,
                "rationale": e["result_summary"].get("rationale"),
            }
            for e in ranked
        ],
    }


def _build_tuning_provenance(adapter: Any) -> Dict[str, Any]:
    """
    Build compact FQS provenance block for tuning experiments (WS1-1B).

    Tuning uses AthleteFindingFQSAdapter, which scores AthleteFinding objects.
    The provenance captures the adapter's static component quality labels
    (per-finding component values would require re-scoring at report time,
    so we report the quality labels and flag any inferred components).

    Shape matches the spec:
        component_values: empty dict (individual findings not re-scored here)
        component_quality: labels from adapter
        has_inferred_components: True if any component is not 'exact'
    """
    quality = adapter.COMPONENT_QUALITY
    has_inferred = any(v != "exact" for v in quality.values())
    return {
        "component_values": {},
        "component_quality": quality,
        "has_inferred_components": has_inferred,
    }
