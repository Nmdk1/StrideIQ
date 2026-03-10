"""
Correlation Engine Layers 1–4

Second-pass analyses that run on confirmed correlation findings
(times_confirmed >= 3) during the daily sweep.  Each layer answers a
different question about a confirmed relationship:

  Layer 1 — Threshold:  "At what value does the effect change?"
  Layer 2 — Asymmetry:  "Does a bad input hurt more than a good one helps?"
  Layer 4 — Decay:      "How long does the effect last?"
  Layer 3 — Cascade:    "Does A affect C directly or through B?"

All four run AFTER findings are persisted — they never modify the
existing correlation engine logic.  Failures are fire-and-forget with
logged warnings.
"""

import logging
import math
from datetime import timedelta
from statistics import median, mean
from typing import Dict, List, Optional, Tuple

from datetime import datetime

from scipy.stats import ttest_ind

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _align_with_lag(
    input_data: List[Tuple[datetime, float]],
    output_data: List[Tuple[datetime, float]],
    lag_days: int,
) -> List[Tuple[float, float]]:
    """Align two time-series at a given lag, returning (input_val, output_val) pairs."""
    shifted = [(d + timedelta(days=lag_days), v) for d, v in input_data]
    lookup = {d: v for d, v in shifted}
    out_lookup = {d: v for d, v in output_data}
    common = sorted(set(lookup) & set(out_lookup))
    return [(lookup[d], out_lookup[d]) for d in common]


def _pearson(x: List[float], y: List[float]) -> Tuple[float, float]:
    """Pearson r and p-value.  Returns (0, 1) on degenerate input."""
    n = len(x)
    if n < 5 or len(y) != n:
        return 0.0, 1.0
    mx, my = mean(x), mean(y)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    sx = sum((xi - mx) ** 2 for xi in x)
    sy = sum((yi - my) ** 2 for yi in y)
    if sx == 0 or sy == 0:
        return 0.0, 1.0
    r = num / math.sqrt(sx * sy)
    if abs(r) >= 1.0:
        return r, 0.0
    t_stat = r * math.sqrt((n - 2) / (1 - r ** 2))
    from scipy.stats import t as t_dist
    p = 2 * t_dist.sf(abs(t_stat), n - 2)
    return r, p


# ---------------------------------------------------------------------------
# Layer 1 — Threshold Detection
# ---------------------------------------------------------------------------

def detect_threshold(
    input_data: List[Tuple[datetime, float]],
    output_data: List[Tuple[datetime, float]],
    lag_days: int = 0,
    min_segment_size: int = 5,
    min_r_difference: float = 0.2,
) -> Optional[Dict]:
    """
    Find the input value where the correlation changes character.

    Returns None if no threshold detected (linear relationship).
    Returns dict with threshold_value, threshold_direction,
    r_below, r_above, n_below, n_above.
    """
    aligned = _align_with_lag(input_data, output_data, lag_days)
    if len(aligned) < 2 * min_segment_size:
        return None

    aligned.sort(key=lambda p: p[0])
    inputs = [p[0] for p in aligned]
    outputs = [p[1] for p in aligned]

    best_split = None
    best_diff = 0.0

    unique_inputs = sorted(set(inputs))
    for candidate in unique_inputs:
        below_x = [outputs[i] for i in range(len(inputs)) if inputs[i] < candidate]
        above_x = [outputs[i] for i in range(len(inputs)) if inputs[i] >= candidate]
        below_in = [inputs[i] for i in range(len(inputs)) if inputs[i] < candidate]
        above_in = [inputs[i] for i in range(len(inputs)) if inputs[i] >= candidate]

        if len(below_x) < min_segment_size or len(above_x) < min_segment_size:
            continue

        r_below, _ = _pearson(below_in, below_x)
        r_above, _ = _pearson(above_in, above_x)

        diff = abs(abs(r_below) - abs(r_above))
        if diff < min_r_difference:
            continue
        if abs(r_below) < 0.3 and abs(r_above) < 0.3:
            continue

        if diff > best_diff:
            best_diff = diff
            direction = "below_matters" if abs(r_below) > abs(r_above) else "above_matters"
            best_split = {
                "threshold_value": round(candidate, 4),
                "threshold_direction": direction,
                "r_below": round(r_below, 4),
                "r_above": round(r_above, 4),
                "n_below": len(below_x),
                "n_above": len(above_x),
            }

    return best_split


# ---------------------------------------------------------------------------
# Layer 2 — Asymmetric Response Detection
# ---------------------------------------------------------------------------

def detect_asymmetry(
    input_data: List[Tuple[datetime, float]],
    output_data: List[Tuple[datetime, float]],
    lag_days: int = 0,
    min_segment_size: int = 5,
) -> Optional[Dict]:
    """
    Detect whether the negative effect of an input is larger than the
    positive effect.

    Returns None if insufficient data.
    Returns dict with asymmetry_ratio, asymmetry_direction,
    effect_below_baseline, effect_above_baseline, baseline_value.
    """
    aligned = _align_with_lag(input_data, output_data, lag_days)
    if len(aligned) < 2 * min_segment_size:
        return None

    input_vals = [p[0] for p in aligned]
    output_vals = [p[1] for p in aligned]

    baseline = median(input_vals)

    below_inputs = [input_vals[i] for i in range(len(input_vals)) if input_vals[i] < baseline]
    below_outputs = [output_vals[i] for i in range(len(input_vals)) if input_vals[i] < baseline]
    above_inputs = [input_vals[i] for i in range(len(input_vals)) if input_vals[i] >= baseline]
    above_outputs = [output_vals[i] for i in range(len(input_vals)) if input_vals[i] >= baseline]

    if len(below_outputs) < min_segment_size or len(above_outputs) < min_segment_size:
        return None

    # Regression slope on each side captures output change per unit input
    # change — the true measure of response sensitivity.
    def _slope(x, y):
        mx, my = mean(x), mean(y)
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        denom = sum((xi - mx) ** 2 for xi in x)
        return num / denom if denom > 1e-12 else 0.0

    effect_below = _slope(below_inputs, below_outputs)
    effect_above = _slope(above_inputs, above_outputs)

    _, p_val = ttest_ind(below_outputs, above_outputs, equal_var=False)
    if p_val >= 0.1:
        return {
            "asymmetry_ratio": 1.0,
            "asymmetry_direction": "symmetric",
            "effect_below_baseline": round(effect_below, 6),
            "effect_above_baseline": round(effect_above, 6),
            "baseline_value": round(baseline, 4),
        }

    if abs(effect_above) < 1e-12:
        ratio = float("inf") if abs(effect_below) > 1e-12 else 1.0
    else:
        ratio = abs(effect_below) / abs(effect_above)

    if ratio > 2.0:
        direction = "negative_dominant"
    elif ratio < 0.67:
        direction = "positive_dominant"
    else:
        direction = "symmetric"

    return {
        "asymmetry_ratio": round(ratio, 4),
        "asymmetry_direction": direction,
        "effect_below_baseline": round(effect_below, 6),
        "effect_above_baseline": round(effect_above, 6),
        "baseline_value": round(baseline, 4),
    }


# ---------------------------------------------------------------------------
# Layer 4 — Lagged Decay Curves
# ---------------------------------------------------------------------------

MIN_CORRELATION_STRENGTH = 0.3


def compute_decay_curve(
    input_data: List[Tuple[datetime, float]],
    output_data: List[Tuple[datetime, float]],
    peak_lag: int,
    max_lag: int = 7,
    min_samples: int = 10,
) -> Optional[Dict]:
    """
    Compute the full lag profile and fit a decay curve.

    Returns None if insufficient data.
    Returns dict with lag_profile, decay_half_life_days, decay_type.
    """
    lag_profile: List[Optional[float]] = []

    for lag in range(max_lag + 1):
        aligned = _align_with_lag(input_data, output_data, lag)
        if len(aligned) < min_samples:
            lag_profile.append(None)
            continue
        x = [p[0] for p in aligned]
        y = [p[1] for p in aligned]
        r, p = _pearson(x, y)
        lag_profile.append(round(r, 4) if p < 0.05 else None)

    significant_count = sum(1 for r in lag_profile if r is not None and abs(r) >= MIN_CORRELATION_STRENGTH)
    if significant_count == 0:
        return None

    # Classify decay type
    peak_r = lag_profile[peak_lag] if peak_lag <= max_lag and lag_profile[peak_lag] is not None else None
    if peak_r is None:
        non_none = [(i, r) for i, r in enumerate(lag_profile) if r is not None]
        if not non_none:
            return None
        peak_lag, peak_r = max(non_none, key=lambda t: abs(t[1]))

    # Sustained: significant across 4+ lags
    if significant_count >= 4:
        return {
            "lag_profile": lag_profile,
            "decay_half_life_days": None,
            "decay_type": "sustained",
        }

    # Check monotonic decay from peak
    post_peak = [(i, lag_profile[i]) for i in range(peak_lag, max_lag + 1) if lag_profile[i] is not None]
    is_monotonic = True
    if len(post_peak) >= 2:
        for j in range(1, len(post_peak)):
            if abs(post_peak[j][1]) > abs(post_peak[j - 1][1]) + 0.01:
                is_monotonic = False
                break

    if not is_monotonic:
        return {
            "lag_profile": lag_profile,
            "decay_half_life_days": None,
            "decay_type": "complex",
        }

    # Exponential decay — compute half-life
    half_target = abs(peak_r) / 2.0
    half_life = None
    for lag_idx, r_val in post_peak:
        if r_val is not None and abs(r_val) <= half_target:
            half_life = round(lag_idx - peak_lag, 1)
            break

    if half_life is None and len(post_peak) >= 2:
        last_lag, last_r = post_peak[-1]
        if last_r is not None and abs(last_r) < abs(peak_r):
            decay_rate = (abs(peak_r) - abs(last_r)) / (last_lag - peak_lag) if last_lag > peak_lag else 0
            if decay_rate > 0:
                half_life = round(half_target / decay_rate, 1)

    return {
        "lag_profile": lag_profile,
        "decay_half_life_days": half_life,
        "decay_type": "exponential",
    }


# ---------------------------------------------------------------------------
# Layer 3 — Cascade Detection (Mediation Analysis)
# ---------------------------------------------------------------------------

def detect_mediators(
    finding_input_name: str,
    finding_output_metric: str,
    finding_r: float,
    finding_lag: int,
    all_inputs: Dict[str, List[Tuple[datetime, float]]],
    output_data: List[Tuple[datetime, float]],
) -> List[Dict]:
    """
    For a confirmed finding (A → C), identify variables that mediate
    the relationship.

    Uses the standard partial correlation formula.

    Returns list of mediator dicts:
      mediator_variable, direct_effect, indirect_effect,
      mediation_ratio, is_full_mediation
    """
    from services.correlation_engine import compute_partial_correlation

    A = finding_input_name
    r_ac = finding_r
    mediators: List[Dict] = []

    for candidate_name, candidate_data in all_inputs.items():
        if candidate_name == A:
            continue
        if len(candidate_data) < 10:
            continue

        # Candidate B must correlate with A
        aligned_ab = _align_with_lag(
            [(d, v) for d, v in all_inputs[A]],
            candidate_data,
            lag_days=0,
        )
        if len(aligned_ab) < 10:
            continue
        r_ab, p_ab = _pearson([p[0] for p in aligned_ab], [p[1] for p in aligned_ab])
        if abs(r_ab) < MIN_CORRELATION_STRENGTH:
            continue

        # Candidate B must correlate with C (the output)
        aligned_bc = _align_with_lag(candidate_data, output_data, lag_days=finding_lag)
        if len(aligned_bc) < 10:
            continue
        r_bc, p_bc = _pearson([p[0] for p in aligned_bc], [p[1] for p in aligned_bc])
        if abs(r_bc) < MIN_CORRELATION_STRENGTH:
            continue

        # Compute partial correlation: r(A, C | B)
        partial_r = compute_partial_correlation(
            all_inputs[A], output_data, candidate_data,
            lag_days=finding_lag,
        )
        if partial_r is None:
            continue

        indirect = abs(r_ac) - abs(partial_r)
        total = abs(r_ac)
        if total < 1e-12:
            continue
        mediation_ratio = indirect / total

        if mediation_ratio < 0.4:
            continue

        is_full = abs(partial_r) < MIN_CORRELATION_STRENGTH

        mediators.append({
            "mediator_variable": candidate_name,
            "direct_effect": round(partial_r, 4),
            "indirect_effect": round(indirect, 4),
            "mediation_ratio": round(mediation_ratio, 4),
            "is_full_mediation": is_full,
        })

    mediators.sort(key=lambda m: m["mediation_ratio"], reverse=True)
    return mediators


# ---------------------------------------------------------------------------
# Second-pass entry point
# ---------------------------------------------------------------------------

def run_layer_analysis(
    finding,
    input_data: List[Tuple[datetime, float]],
    output_data: List[Tuple[datetime, float]],
    all_inputs: Dict[str, List[Tuple[datetime, float]]],
    db,
):
    """
    Run all four layers on a single confirmed finding.
    Updates the finding object in-place.  Caller must commit.

    Failures are logged and swallowed — never breaks the sweep.
    """
    # Layer 1: Threshold
    try:
        result = detect_threshold(input_data, output_data, finding.time_lag_days)
        if result:
            finding.threshold_value = result["threshold_value"]
            finding.threshold_direction = result["threshold_direction"]
            finding.r_below_threshold = result["r_below"]
            finding.r_above_threshold = result["r_above"]
            finding.n_below_threshold = result["n_below"]
            finding.n_above_threshold = result["n_above"]
    except Exception as exc:
        logger.warning("Layer 1 (threshold) failed for finding %s: %s", finding.id, exc)

    # Layer 2: Asymmetry
    try:
        result = detect_asymmetry(input_data, output_data, finding.time_lag_days)
        if result:
            finding.asymmetry_ratio = result["asymmetry_ratio"]
            finding.asymmetry_direction = result["asymmetry_direction"]
            finding.effect_below_baseline = result["effect_below_baseline"]
            finding.effect_above_baseline = result["effect_above_baseline"]
            finding.baseline_value = result["baseline_value"]
    except Exception as exc:
        logger.warning("Layer 2 (asymmetry) failed for finding %s: %s", finding.id, exc)

    # Layer 4: Decay
    try:
        result = compute_decay_curve(input_data, output_data, finding.time_lag_days)
        if result:
            finding.lag_profile = result["lag_profile"]
            finding.decay_half_life_days = result["decay_half_life_days"]
            finding.decay_type = result["decay_type"]
    except Exception as exc:
        logger.warning("Layer 4 (decay) failed for finding %s: %s", finding.id, exc)

    # Layer 3: Cascade (mediators)
    try:
        mediator_results = detect_mediators(
            finding_input_name=finding.input_name,
            finding_output_metric=finding.output_metric,
            finding_r=finding.correlation_coefficient,
            finding_lag=finding.time_lag_days,
            all_inputs=all_inputs,
            output_data=output_data,
        )
        if mediator_results:
            _persist_mediators(finding, mediator_results, db)
    except Exception as exc:
        logger.warning("Layer 3 (cascade) failed for finding %s: %s", finding.id, exc)


def _persist_mediators(finding, mediator_results: List[Dict], db):
    """Upsert mediator rows for a finding."""
    from models import CorrelationMediator

    existing = db.query(CorrelationMediator).filter(
        CorrelationMediator.finding_id == finding.id,
    ).all()
    existing_by_var = {m.mediator_variable: m for m in existing}

    for med in mediator_results:
        if med["mediator_variable"] in existing_by_var:
            row = existing_by_var[med["mediator_variable"]]
            row.direct_effect = med["direct_effect"]
            row.indirect_effect = med["indirect_effect"]
            row.mediation_ratio = med["mediation_ratio"]
            row.is_full_mediation = med["is_full_mediation"]
        else:
            import uuid as _uuid
            row = CorrelationMediator(
                id=_uuid.uuid4(),
                finding_id=finding.id,
                mediator_variable=med["mediator_variable"],
                direct_effect=med["direct_effect"],
                indirect_effect=med["indirect_effect"],
                mediation_ratio=med["mediation_ratio"],
                is_full_mediation=med["is_full_mediation"],
            )
            db.add(row)
