"""
Pairwise Interaction Loop — Phase 0B (founder-only, shadow mode).

Turns the existing combination-correlation helper into a persisted,
scored shadow discovery loop.

Scope: pairwise only.  Three-way and higher-order interactions are
explicitly out of scope for Phase 0B.

Output metrics supported: efficiency, pace_easy, pace_threshold, completion.

Safety guarantees:
- No writes to athlete-facing tables.
- No writes to correlation_finding or fingerprint_finding.
- Returns experiment dicts; the orchestrator owns persistence.
"""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Minimum samples per group for an interaction to be reportable.
_MIN_GROUP_SIZE = 5
# Minimum Cohen's d to be considered a meaningful interaction effect.
_MIN_EFFECT_SIZE = 0.5
# Maximum interactions returned per metric.
_TOP_N = 10
# Keep threshold: interaction score must exceed this to be "kept".
INTERACTION_KEEP_THRESHOLD = 0.35

# Output metrics with their aggregation keys and polarity
# (lower is better for pace, higher for completion/efficiency).
_INTERACTION_METRICS: Dict[str, str] = {
    "efficiency": "efficiency",
    "pace_easy": "pace_easy",
    "pace_threshold": "pace_threshold",
    "completion": "completion",
}


def run_pairwise_interaction_scan(
    athlete_id: UUID,
    db: Session,
    days: int = 180,
) -> List[Dict[str, Any]]:
    """
    Run pairwise interaction discovery for the athlete in shadow mode.

    Returns a list of experiment-result dicts (one per output metric)
    suitable for writing to `auto_discovery_experiment`.

    No production DB tables are mutated.  The caller must roll back
    any pending writes after this function returns.
    """
    from services.correlation_engine import (
        aggregate_daily_inputs,
        aggregate_training_load_inputs,
        aggregate_activity_level_inputs,
        aggregate_feedback_inputs,
        aggregate_training_pattern_inputs,
        aggregate_efficiency_outputs,
        MIN_SAMPLE_SIZE,
    )

    def _get_output_for_metric(metric_name, athlete_id_str, start_date, end_date, db):
        from tasks.correlation_tasks import _aggregate_output_for_metric
        return _aggregate_output_for_metric(metric_name, athlete_id_str, start_date, end_date, db)

    athlete_id_str = str(athlete_id)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    experiment_results: List[Dict[str, Any]] = []

    # Aggregate all inputs once.
    try:
        all_inputs = aggregate_daily_inputs(athlete_id_str, start_date, end_date, db)
        load_inputs = aggregate_training_load_inputs(athlete_id_str, start_date, end_date, db)
        all_inputs.update(load_inputs)
        activity_inputs = aggregate_activity_level_inputs(athlete_id_str, start_date, end_date, db)
        all_inputs.update(activity_inputs)
        feedback_inputs = aggregate_feedback_inputs(athlete_id_str, start_date, end_date, db)
        all_inputs.update(feedback_inputs)
        pattern_inputs = aggregate_training_pattern_inputs(athlete_id_str, start_date, end_date, db)
        all_inputs.update(pattern_inputs)
    except Exception as exc:
        logger.error("Interaction scan: input aggregation failed for athlete=%s: %s", athlete_id_str, exc)
        return []

    for metric_name in _INTERACTION_METRICS:
        t0 = time.monotonic()
        error: Optional[str] = None
        interactions: List[Dict[str, Any]] = []
        tested_pairs: List[tuple] = []

        try:
            output_data = _get_output_for_metric(metric_name, athlete_id_str, start_date, end_date, db)
            if len(output_data) < MIN_SAMPLE_SIZE:
                error = f"Insufficient output data: {len(output_data)} < {MIN_SAMPLE_SIZE}"
            else:
                output_dict = {d: v for d, v in output_data}
                scan_result = _find_pairwise_interactions(
                    all_inputs=all_inputs,
                    output_dict=output_dict,
                    output_metric=metric_name,
                    min_group=_MIN_GROUP_SIZE,
                    min_effect=_MIN_EFFECT_SIZE,
                    top_n=_TOP_N,
                )
                interactions = scan_result["top_interactions"]
                tested_pairs = scan_result["tested_pairs"]
        except Exception as exc:
            error = str(exc)
            logger.warning("Interaction scan: metric=%s failed: %s", metric_name, exc)

        runtime_ms = int((time.monotonic() - t0) * 1000)
        scored_interactions = [_score_interaction(i) for i in interactions]
        scored_interactions.sort(key=lambda x: x["interaction_score"], reverse=True)

        # Threshold statement if no interactions cleared the bar.
        threshold_statement = None
        kept = [i for i in scored_interactions if i["interaction_score"] >= INTERACTION_KEEP_THRESHOLD]
        if not interactions:
            threshold_statement = {
                "cleared_threshold": False,
                "reason": error or "no interactions above minimum effect size",
                "threshold": INTERACTION_KEEP_THRESHOLD,
            }
        elif not kept:
            threshold_statement = {
                "cleared_threshold": False,
                "reason": f"{len(interactions)} candidates tested, none exceeded score threshold {INTERACTION_KEEP_THRESHOLD}",
                "threshold": INTERACTION_KEEP_THRESHOLD,
            }

        experiment_results.append({
            "loop_type": "interaction_scan",
            "target_name": f"pairwise:{metric_name}",
            "baseline_config": {
                "output_metric": metric_name,
                "days": days,
                "min_effect_size": _MIN_EFFECT_SIZE,
            },
            "candidate_config": {},
            "result_summary": {
                "output_metric": metric_name,
                "interactions_tested": len(interactions),
                "interactions_kept": len(kept),
                "top_interactions": kept or interactions[:3],  # top 3 even if below threshold
                "threshold_statement": threshold_statement,
                "error": error,
                # WS1-1B: FQS provenance block preserved for founder review.
                "score_provenance": _build_interaction_provenance(kept or scored_interactions[:3]),
            },
            # WS1-1A: real aggregate score from kept candidates (not count-based).
            "baseline_score": _aggregate_interaction_score(kept),
            "candidate_score": None,
            "score_delta": None,
            "failure_reason": error,
            "runtime_ms": runtime_ms,
        })

        # Persist coverage for every tested pair-metric combination so the
        # scheduler knows what has been explored (and what hasn't).
        top_pair_set = set()
        for interaction in (kept or interactions[:3]):
            factors = interaction.get("factors", [])
            if len(factors) == 2:
                top_pair_set.add(tuple(sorted(factors)))
        for pair in tested_pairs:
            input_a, input_b = pair[0], pair[1]
            pair_key = tuple(sorted([input_a, input_b]))
            result_label = "signal" if pair_key in top_pair_set else "no_signal"
            try:
                upsert_scan_coverage(
                    athlete_id=athlete_id,
                    input_a=input_a,
                    input_b=input_b,
                    output_metric=metric_name,
                    window_days=days,
                    result=result_label,
                    db=db,
                )
            except Exception as exc:
                logger.warning(
                    "Interaction scan: coverage upsert failed pair=(%s,%s) metric=%s: %s",
                    input_a, input_b, metric_name, exc,
                )

        logger.info(
            "Interaction scan: athlete=%s metric=%s candidates=%d kept=%d runtime_ms=%d",
            athlete_id_str, metric_name, len(interactions), len(kept), runtime_ms,
        )

    return experiment_results


def _find_pairwise_interactions(
    all_inputs: Dict[str, Any],
    output_dict: Dict[Any, float],
    output_metric: str,
    min_group: int,
    min_effect: float,
    top_n: int,
) -> List[Dict[str, Any]]:
    """Core median-split pairwise test loop."""
    # Build binary splits.
    splits: Dict[str, Dict] = {}
    for input_name, data in all_inputs.items():
        if len(data) < min_group * 2:
            continue
        values = [v for _, v in data]
        median_val = sorted(values)[len(values) // 2]
        splits[input_name] = {
            "high": {d for d, v in data if v >= median_val},
            "low": {d for d, v in data if v < median_val},
            "median": median_val,
        }

    input_names = list(splits.keys())
    results: List[Dict[str, Any]] = []
    tested: List[tuple] = []

    for i in range(len(input_names)):
        for j in range(i + 1, len(input_names)):
            n1, n2 = input_names[i], input_names[j]
            s1, s2 = splits[n1], splits[n2]

            both_high = s1["high"] & s2["high"]
            both_low = s1["low"] & s2["low"]

            eff_high = [output_dict[d] for d in both_high if d in output_dict]
            eff_low = [output_dict[d] for d in both_low if d in output_dict]

            if len(eff_high) < min_group or len(eff_low) < min_group:
                continue

            tested.append((n1, n2))

            m_high = mean(eff_high)
            m_low = mean(eff_low)
            if len(eff_high) > 1 and len(eff_low) > 1:
                pooled = math.sqrt((stdev(eff_high) ** 2 + stdev(eff_low) ** 2) / 2)
            else:
                pooled = 1.0
            effect = (m_high - m_low) / pooled if pooled > 0 else 0.0

            if abs(effect) < min_effect:
                continue

            # Lower output = better for pace metrics; higher = better for completion/efficiency-style.
            lower_is_better = "pace" in output_metric
            high_is_better = (effect < 0) if lower_is_better else (effect > 0)

            results.append({
                "factors": [n1, n2],
                "output_metric": output_metric,
                "condition": "both_high",
                "effect_size": round(effect, 3),
                "mean_high": round(m_high, 4),
                "mean_low": round(m_low, 4),
                "n_high": len(eff_high),
                "n_low": len(eff_low),
                "high_group_better": high_is_better,
                "direction_label": (
                    f"{'lower' if lower_is_better else 'higher'} {output_metric} when both {n1} and {n2} are high"
                ),
            })

    results.sort(key=lambda x: abs(x["effect_size"]), reverse=True)
    return {
        "top_interactions": results[:top_n],
        "tested_pairs": tested,
    }


def _score_interaction(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute a transparent founder-reviewable score for a pairwise candidate.

    Score components:
        effect_size_norm  — normalized |Cohen's d|, capped at 1.5 → score [0, 1]
        sample_support    — log-scaled combined sample size
    """
    abs_effect = abs(candidate.get("effect_size") or 0.0)
    n_total = (candidate.get("n_high") or 0) + (candidate.get("n_low") or 0)

    effect_score = min(1.0, abs_effect / 1.5)
    sample_score = min(1.0, math.log1p(max(0, n_total - 10)) / math.log1p(90))

    interaction_score = round(0.6 * effect_score + 0.4 * sample_score, 4)

    return {
        **candidate,
        "interaction_score": interaction_score,
        "score_components": {
            "effect_size_norm": round(effect_score, 4),
            "sample_support": round(sample_score, 4),
        },
    }


def _aggregate_interaction_score(candidates: List[Dict[str, Any]]) -> Optional[float]:
    """
    Aggregate interaction scores from kept/scored candidates.

    Returns the mean `interaction_score` of the candidates, or None if the
    list is empty (no candidates cleared threshold).

    Used by the orchestrator to populate a real numeric `baseline_score` on
    the interaction experiment row instead of the count-based proxy.
    """
    if not candidates:
        return None
    scores = [c.get("interaction_score") or 0.0 for c in candidates]
    return round(sum(scores) / len(scores), 4)


def _build_interaction_provenance(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a compact FQS provenance block for interaction results.

    Interaction candidates do not go through the full FQS adapter pipeline
    (no correlation_finding row), so provenance reflects the two transparent
    score components used in _score_interaction().

    Shape matches the spec:
        score_provenance.component_values
        score_provenance.component_quality
        score_provenance.has_inferred_components
    """
    if not candidates:
        return {
            "component_values": {},
            "component_quality": {
                "effect_size_norm": "exact",
                "sample_support": "exact",
            },
            "has_inferred_components": False,
        }

    # Average component values across candidates.
    effect_scores = [c.get("score_components", {}).get("effect_size_norm", 0.0) for c in candidates]
    sample_scores = [c.get("score_components", {}).get("sample_support", 0.0) for c in candidates]

    avg_effect = round(sum(effect_scores) / len(effect_scores), 4) if effect_scores else 0.0
    avg_sample = round(sum(sample_scores) / len(sample_scores), 4) if sample_scores else 0.0

    return {
        "component_values": {
            "effect_size_norm": avg_effect,
            "sample_support": avg_sample,
        },
        "component_quality": {
            "effect_size_norm": "exact",
            "sample_support": "exact",
        },
        "has_inferred_components": False,
    }


# ---------------------------------------------------------------------------
# Phase 1: Interaction finding promotion
# ---------------------------------------------------------------------------

# How many times a candidate must be seen across nightly runs before promoting
_INTERACTION_PROMOTION_TIMES_SEEN = 3


def promote_interaction_findings(
    athlete_id: UUID,
    db: Session,
) -> List[Dict[str, Any]]:
    """Phase 1 mutation: promote interaction candidates that have been seen
    in 3+ consecutive nightly runs into real AthleteFinding rows.

    Uses upsert semantics: identity key is
    `interaction_discovery:{sorted_inputs}:{output_metric}`.

    Returns list of promoted finding dicts.  Caller owns commit.
    """
    from models import AutoDiscoveryCandidate, AthleteFinding
    from services.n1_insight_generator import friendly_signal_name
    import uuid as _uuid

    now = datetime.utcnow()
    promoted: List[Dict[str, Any]] = []

    eligible_candidates = (
        db.query(AutoDiscoveryCandidate)
        .filter(
            AutoDiscoveryCandidate.athlete_id == athlete_id,
            AutoDiscoveryCandidate.candidate_type == "interaction",
            AutoDiscoveryCandidate.times_seen >= _INTERACTION_PROMOTION_TIMES_SEEN,
            AutoDiscoveryCandidate.current_status.in_(["open", "approved"]),
        )
        .all()
    )

    for candidate in eligible_candidates:
        summary = candidate.latest_summary or {}

        factors = summary.get("factors") or []
        input_a = summary.get("input_a") or (factors[0] if len(factors) > 0 else "")
        input_b = summary.get("input_b") or (factors[1] if len(factors) > 1 else "")
        output_metric = summary.get("output_metric") or ""

        if not (input_a and output_metric):
            continue

        inputs_sorted = sorted([input_a, input_b]) if input_b else [input_a]
        finding_key = f"interaction_discovery:{'_x_'.join(inputs_sorted)}:{output_metric}"

        existing = (
            db.query(AthleteFinding)
            .filter(
                AthleteFinding.athlete_id == athlete_id,
                AthleteFinding.finding_type == "pairwise_interaction",
                AthleteFinding.investigation_name == finding_key,
                AthleteFinding.is_active == True,  # noqa: E712
            )
            .first()
        )

        label_a = friendly_signal_name(input_a)
        label_b = friendly_signal_name(input_b) if input_b else ""
        label_out = friendly_signal_name(output_metric)

        if input_b:
            sentence = (
                f"When {label_a} is high together with {label_b}, "
                f"your {label_out} changes significantly."
            )
        else:
            sentence = f"Your {label_a} has an interaction effect on {label_out}."

        receipts = {
            "input_a": input_a,
            "input_b": input_b,
            "output_metric": output_metric,
            "effect_size": summary.get("effect_size"),
            "interaction_score": summary.get("interaction_score"),
            "times_seen": candidate.times_seen,
            "discovery_candidate_id": str(candidate.id),
        }

        if existing:
            # Update times_seen tracking and receipts
            existing_receipts = existing.receipts or {}
            existing_receipts["times_seen"] = candidate.times_seen
            existing_receipts["last_confirmed_at"] = now.isoformat()
            existing.receipts = existing_receipts
            existing.last_confirmed_at = now
            db.flush()
            state = "updated"
        else:
            new_finding = AthleteFinding(
                id=_uuid.uuid4(),
                athlete_id=athlete_id,
                investigation_name=finding_key,
                finding_type="pairwise_interaction",
                sentence=sentence,
                receipts=receipts,
                confidence="suggestive",
                first_detected_at=now,
                last_confirmed_at=now,
                is_active=True,
            )
            db.add(new_finding)
            db.flush()
            state = "created"

        # Mark candidate as promoted
        candidate.current_status = "promoted"
        candidate.updated_at = now
        db.flush()

        promoted.append({
            "finding_key": finding_key,
            "input_a": input_a,
            "input_b": input_b,
            "output_metric": output_metric,
            "state": state,
            "times_seen": candidate.times_seen,
        })
        logger.info(
            "Interaction Phase 1: %s finding athlete=%s key=%s",
            state, str(athlete_id), finding_key,
        )

    return promoted


def upsert_scan_coverage(
    athlete_id: UUID,
    input_a: str,
    input_b: Optional[str],
    output_metric: str,
    window_days: Optional[int],
    result: str,
    db: Session,
) -> None:
    """Upsert a scan coverage record for one (athlete, input pair, metric, window).

    `result` must be 'signal', 'no_signal', or 'error'.
    """
    from models import AutoDiscoveryScanCoverage
    import uuid as _uuid

    now = datetime.utcnow()
    test_key = _make_coverage_key(input_a, input_b, output_metric, window_days)

    existing = (
        db.query(AutoDiscoveryScanCoverage)
        .filter(
            AutoDiscoveryScanCoverage.athlete_id == athlete_id,
            AutoDiscoveryScanCoverage.loop_type == "interaction_scan",
            AutoDiscoveryScanCoverage.test_key == test_key,
        )
        .first()
    )

    if existing:
        existing.last_scanned_at = now
        existing.result = result
        existing.scan_count = (existing.scan_count or 0) + 1
    else:
        db.add(AutoDiscoveryScanCoverage(
            id=_uuid.uuid4(),
            athlete_id=athlete_id,
            loop_type="interaction_scan",
            test_key=test_key,
            input_a=input_a,
            input_b=input_b,
            output_metric=output_metric,
            window_days=window_days,
            last_scanned_at=now,
            result=result,
            scan_count=1,
        ))
    db.flush()


def _make_coverage_key(
    input_a: str,
    input_b: Optional[str],
    output_metric: str,
    window_days: Optional[int],
) -> str:
    import hashlib, json
    parts = sorted([input_a, input_b or ""]) + [output_metric, str(window_days or "full")]
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:32]

