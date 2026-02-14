"""N=1 personalized insight generator (Phase 3C).

Transforms statistically significant per-athlete correlations into
human-readable, data-derived insights.  All insights:
- Pass Bonferroni-corrected significance + effect size + sample gates.
- Use "YOUR …" phrasing — observation, not prescription.
- Never leak internal metric acronyms (TSB, CTL, ATL, EF, VDOT, etc.).
- Scale confidence with data volume + effect strength.

=============================================================================
ATHLETE TRUST SAFETY CONTRACT — Efficiency Interpretation (Phase 3C Scope)
=============================================================================

1. DIRECTIONAL CLAIMS REQUIRE EXPLICIT POLARITY METADATA.
   Athlete-facing "improving / declining / better / worse" is allowed only
   when the output metric's OutputMetricMeta defines unambiguous polarity.

2. TWO-TIER FAIL-CLOSED BEHAVIOR.
   • Tier 1 — Ambiguous polarity (polarity_ambiguous == True):
     Show neutral observation text only; classify as "pattern".
   • Tier 2 — Missing / invalid / conflicting metadata:
     Suppress directional interpretation entirely.  Return structured
     evidence data only, or suppress the insight.

3. NO SIGN-ONLY INFERENCE.
   Correlation sign alone (r > 0 / r < 0) must never determine
   "beneficial" or "harmful" without polarity metadata from the registry.

4. APPROVED DIRECTIONAL OUTPUT WHITELIST (Phase 3C).
   Directional athlete-facing language is permitted ONLY for metrics
   listed in DIRECTIONAL_SAFE_METRICS:
     pace_easy, pace_threshold, race_pace   (lower is better)
     completion_rate, completion, pb_events  (higher is better)
   Any new metric requires OutputMetricMeta registration with explicit
   polarity before directional language is permitted.

5. SINGLE REGISTRY AUTHORITY FOR 3C.
   OutputMetricMeta + OUTPUT_METRIC_REGISTRY is the sole source of truth
   for metric definition, polarity, and interpretation in the 3C pipeline.
   No local overrides, no inline sign-flipping.

6. TRUST OVER VERBOSITY.
   When interpretation certainty is low, prefer short neutral language
   over explanatory directional certainty.

7. REGRESSION PROTECTIONS (REQUIRED).
   Tests must cover: mixed-scenario (same pace / lower HR AND same HR /
   faster pace), ambiguity-neutral wording, and missing-metadata
   suppression.

8. CURRENT SCOPE + DEBT NOTE.
   This contract is enforced now in the 3C insight layer
   (n1_insight_generator → _build_insight_text → _categorize path).
   Legacy services with local polarity logic (load_response_explain,
   causal_attribution, coach_tools, home_signals, calendar_signals,
   pattern_recognition, run_analysis_engine, ai_coach) are tracked as
   migration debt.  See comments referencing OutputMetricMeta in those
   files.
=============================================================================
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Banned acronym / internal-label check
# ---------------------------------------------------------------------------

BANNED_LABELS = {
    "TSB", "CTL", "ATL", "VDOT", "rMSSD", "SDNN", "EF", "TRIMP",
}

BANNED_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(b) for b in BANNED_LABELS) + r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Human-friendly name mapping for correlation inputs
# ---------------------------------------------------------------------------

FRIENDLY_NAMES: Dict[str, str] = {
    "weekly_volume_km": "weekly running volume",
    "weekly_volume_mi": "weekly mileage",
    "long_run_distance_km": "long run distance",
    "long_run_distance_mi": "long run distance",
    "avg_hr": "average heart rate",
    "max_hr": "max heart rate",
    "duration_s": "run duration",
    "intensity_score": "session intensity",
    "sleep_hours": "sleep duration",
    "sleep_h": "sleep duration",
    "daily_protein_g": "daily protein intake",
    "daily_carbs_g": "daily carb intake",
    "hrv_rmssd": "heart-rate variability",
    "resting_hr": "resting heart rate",
    "elevation_gain": "elevation gain",
    "recovery_days": "recovery days between quality sessions",
    "threshold_volume": "threshold training volume",
    "interval_volume": "interval training volume",
    "easy_volume": "easy running volume",
    "efficiency": "running efficiency",
    "pace_easy": "easy pace",
    "completion_rate": "workout completion rate",
}


def _friendly(raw_name: str) -> str:
    """Convert internal metric name to human-friendly label."""
    return FRIENDLY_NAMES.get(raw_name, raw_name.replace("_", " "))


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

@dataclass
class N1Insight:
    text: str
    source: str = "n1"
    confidence: float = 0.0
    evidence: Dict[str, Any] = field(default_factory=dict)
    category: str = "pattern"  # "what_works", "what_doesnt", "pattern"


# ---------------------------------------------------------------------------
# Canonical output-metric contract
# ---------------------------------------------------------------------------
# Each output metric carries explicit metadata so that downstream consumers
# (insight text, categorisation, coach tools) never guess polarity from sign.
#
# DESIGN RULE: raw `efficiency` (pace_sec_km / avg_hr, uncontrolled) is
# directionally ambiguous — its ratio rises when HR drops at fixed pace
# (good) but falls when pace improves at fixed HR (also good).  We therefore
# mark it `polarity_ambiguous=True` and refuse to emit directional claims
# ("what works / doesn't") from it.  Unambiguous alternatives exist:
#   - pace_at_effort  (zone-filtered pace; lower = faster = better)
#   - hr_at_fixed_pace (lower = better)
#   - speed_at_fixed_hr (higher = better)
#   - completion / completion_rate (higher = better)

@dataclass
class OutputMetricMeta:
    """Contract describing how to interpret an output metric's direction."""
    metric_key: str
    metric_definition: str
    higher_is_better: Optional[bool]       # None → ambiguous
    polarity_ambiguous: bool               # True → no directional claims allowed
    direction_interpretation: str          # human-readable note for audit


OUTPUT_METRIC_REGISTRY: Dict[str, OutputMetricMeta] = {
    "efficiency": OutputMetricMeta(
        metric_key="efficiency",
        metric_definition="pace(sec/km) / avg_hr(bpm) — uncontrolled ratio",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation=(
            "Ambiguous: ratio rises when HR drops (good) but falls when "
            "pace improves (also good). Do not infer direction from sign."
        ),
    ),
    "efficiency_threshold": OutputMetricMeta(
        metric_key="efficiency_threshold",
        metric_definition="pace(sec/km) / avg_hr within threshold HR zone (80-88% max HR)",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation=(
            "Zone-filtered but still a ratio of two co-moving variables. "
            "Safer than raw efficiency but not fully unambiguous."
        ),
    ),
    "efficiency_easy": OutputMetricMeta(
        metric_key="efficiency_easy",
        metric_definition="pace(sec/km) / avg_hr within easy HR zone (<75% max HR)",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation="Zone-filtered efficiency ratio — still ambiguous.",
    ),
    "efficiency_race": OutputMetricMeta(
        metric_key="efficiency_race",
        metric_definition="pace(sec/km) / avg_hr within race HR zone (>88% max HR)",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation="Zone-filtered efficiency ratio — still ambiguous.",
    ),
    "efficiency_trend": OutputMetricMeta(
        metric_key="efficiency_trend",
        metric_definition="Rolling % change in zone-filtered efficiency vs baseline",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation="Trend of ambiguous base metric — inherits ambiguity.",
    ),
    "pace_easy": OutputMetricMeta(
        metric_key="pace_easy",
        metric_definition="pace(sec/km) at easy effort — single controlled variable",
        higher_is_better=False,
        polarity_ambiguous=False,
        direction_interpretation="Lower pace = faster at easy effort = unambiguously better.",
    ),
    "pace_threshold": OutputMetricMeta(
        metric_key="pace_threshold",
        metric_definition="pace(sec/km) at threshold effort — single controlled variable",
        higher_is_better=False,
        polarity_ambiguous=False,
        direction_interpretation="Lower pace = faster at threshold effort = unambiguously better.",
    ),
    "completion_rate": OutputMetricMeta(
        metric_key="completion_rate",
        metric_definition="Fraction of planned workout completed",
        higher_is_better=True,
        polarity_ambiguous=False,
        direction_interpretation="Higher = more of the plan completed = unambiguously better.",
    ),
    "completion": OutputMetricMeta(
        metric_key="completion",
        metric_definition="Binary/fractional workout completion",
        higher_is_better=True,
        polarity_ambiguous=False,
        direction_interpretation="Higher = completed more = unambiguously better.",
    ),
    "pb_events": OutputMetricMeta(
        metric_key="pb_events",
        metric_definition="Personal best event occurrences",
        higher_is_better=True,
        polarity_ambiguous=False,
        direction_interpretation="More PB events = unambiguously better.",
    ),
    "race_pace": OutputMetricMeta(
        metric_key="race_pace",
        metric_definition="pace(sec/km) in race activities",
        higher_is_better=False,
        polarity_ambiguous=False,
        direction_interpretation="Lower pace = faster race = unambiguously better.",
    ),
    # --- Phase 2: Run Stream Analysis metrics ---
    "cardiac_drift_pct": OutputMetricMeta(
        metric_key="cardiac_drift_pct",
        metric_definition="Percentage HR rise from first-half to second-half of work/steady segments",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation=(
            "Ambiguous: drift rises with fatigue (expected in long runs) but also "
            "with dehydration or heat. Context-dependent — do not infer directional quality."
        ),
    ),
    "pace_drift_pct": OutputMetricMeta(
        metric_key="pace_drift_pct",
        metric_definition="Percentage velocity change from first-half to second-half of work segments",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation=(
            "Ambiguous: positive = got faster (negative split, often good) but also "
            "could mean started too slow. Negative = slowed (normal in long runs). "
            "Do not infer direction without workout context."
        ),
    ),
    "cadence_trend_bpm_per_km": OutputMetricMeta(
        metric_key="cadence_trend_bpm_per_km",
        metric_definition="Linear cadence change (steps/min) per km over work segments",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation=(
            "Ambiguous: cadence changes interact with pace, fatigue, and terrain. "
            "Dropping cadence may indicate fatigue or intentional lengthening. "
            "Do not infer directional quality."
        ),
    ),
    "plan_execution_variance": OutputMetricMeta(
        metric_key="plan_execution_variance",
        metric_definition="Summary-level delta between planned and actual workout metrics",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation=(
            "Ambiguous: over-executing a plan may be harmful (injury risk), "
            "under-executing may be adaptive (recovery). Do not infer direction."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Directional-safe whitelist (Contract §4)
# ---------------------------------------------------------------------------
# Only these metrics may produce "what_works" / "what_doesnt" categories
# or "tends to improve / decline" athlete-facing text.  All others are
# observation-only.  Adding a metric here requires a registered
# OutputMetricMeta with polarity_ambiguous=False.

DIRECTIONAL_SAFE_METRICS: frozenset = frozenset({
    "pace_easy",
    "pace_threshold",
    "race_pace",
    "completion_rate",
    "completion",
    "pb_events",
})


def get_metric_meta(output_metric: str) -> OutputMetricMeta:
    """Look up metric metadata.  Unknown metrics are treated as ambiguous."""
    return OUTPUT_METRIC_REGISTRY.get(
        output_metric,
        OutputMetricMeta(
            metric_key=output_metric,
            metric_definition=f"Unknown metric: {output_metric}",
            higher_is_better=None,
            polarity_ambiguous=True,
            direction_interpretation="Unknown metric — polarity not registered.",
        ),
    )


def _validate_metric_meta(meta: OutputMetricMeta) -> bool:
    """Check whether metric metadata is valid and internally consistent.

    Returns False (→ tier-2 suppression) when:
    - polarity_ambiguous is False but higher_is_better is None (conflicting)
    - polarity_ambiguous is True but higher_is_better is not None (conflicting)
    - metric_definition is empty
    """
    if not meta.metric_definition:
        return False
    if meta.polarity_ambiguous and meta.higher_is_better is not None:
        return False  # Conflicting: claims ambiguous but also declares polarity
    if not meta.polarity_ambiguous and meta.higher_is_better is None:
        return False  # Conflicting: claims unambiguous but has no polarity
    return True


def _is_beneficial(direction: str, output_metric: str) -> Optional[bool]:
    """Determine if the correlation direction is beneficial for the athlete.

    Implements the two-tier fail-closed contract:
      - Tier 1 (ambiguous polarity): returns None → neutral text
      - Tier 2 (invalid/missing metadata OR not in whitelist): returns None
      - Unambiguous + whitelisted: returns True/False

    Returns:
        True  — beneficial (what_works)  — only for whitelisted unambiguous metrics
        False — harmful   (what_doesnt) — only for whitelisted unambiguous metrics
        None  — neutral   (pattern)     — ambiguous, invalid, or not whitelisted
    """
    meta = get_metric_meta(output_metric)

    # Tier 2: invalid / conflicting metadata → suppress directional output
    if not _validate_metric_meta(meta):
        return None

    # Tier 1: ambiguous polarity → neutral observation only
    if meta.polarity_ambiguous:
        return None

    # Whitelist gate (Contract §4): even if metadata says unambiguous,
    # directional language requires explicit whitelist membership
    if output_metric not in DIRECTIONAL_SAFE_METRICS:
        return None

    raw_positive = direction == "positive"
    return raw_positive == meta.higher_is_better


# ---------------------------------------------------------------------------
# Insight text generation
# ---------------------------------------------------------------------------

def _build_insight_text(
    input_name: str,
    direction: str,
    strength: str,
    r: float,
    lag_days: int,
    output_metric: str = "efficiency",
) -> str:
    """Build a single human-readable insight sentence.

    For AMBIGUOUS metrics (raw efficiency, zone-filtered efficiency):
      → neutral phrasing: "associated with changes in …"
      → no "improves/declines" claim.

    For UNAMBIGUOUS metrics (pace_easy, completion, etc.):
      → directional phrasing: "tends to improve/decline …"
    """
    friendly_input = _friendly(input_name)
    friendly_output = _friendly(output_metric)

    # Lag phrasing
    if lag_days == 0:
        timing = ""
    elif lag_days == 1:
        timing = " the following day"
    else:
        timing = f" within {lag_days} days"

    # Strength qualifier
    if abs(r) >= 0.7:
        qual = "strongly"
    elif abs(r) >= 0.5:
        qual = "noticeably"
    else:
        qual = "moderately"

    # Polarity-aware direction
    beneficial = _is_beneficial(direction, output_metric)

    if beneficial is None:
        # AMBIGUOUS metric — neutral language, no directional claim
        text = (
            f"Based on your data: YOUR {friendly_output} is {qual} "
            f"associated with changes{timing} when your {friendly_input} is higher."
        )
    elif beneficial:
        text = (
            f"Based on your data: YOUR {friendly_output} {qual} tends to improve"
            f"{timing} when your {friendly_input} is higher."
        )
    else:
        text = (
            f"Based on your data: YOUR {friendly_output} {qual} tends to decline"
            f"{timing} when your {friendly_input} is higher."
        )
    return text


def _compute_confidence(r: float, p_adj: float, n: int) -> float:
    """Scale confidence with effect strength + data volume."""
    # Effect component: |r| scaled 0-1
    effect = min(abs(r), 1.0)
    # Volume component: logarithmic scaling, caps at ~100 samples
    import math
    volume = min(math.log(max(n, 1)) / math.log(100), 1.0)
    # Significance component: inverse p, capped
    sig = max(1.0 - p_adj, 0.0)
    # Weighted average
    return round(0.4 * effect + 0.3 * volume + 0.3 * sig, 3)


def _categorize(direction: str, output_metric: str = "efficiency") -> str:
    """Map correlation to insight category using polarity-aware logic.

    Returns "pattern" (neutral) when the output metric is ambiguous,
    preventing false "what works / what doesn't" claims.
    """
    beneficial = _is_beneficial(direction, output_metric)
    if beneficial is None:
        return "pattern"  # Ambiguous — no directional claim
    return "what_works" if beneficial else "what_doesnt"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_n1_insights(
    athlete_id: UUID,
    db: Session,
    days_window: Optional[int] = None,
    output_metric: str = "efficiency",
    max_insights: int = 10,
) -> List[N1Insight]:
    """Generate N=1 insights for an athlete from correlation engine output.

    Args:
        athlete_id: Athlete UUID.
        db: Database session.
        days_window: Analysis window (auto-selects up to 365 if None).
        output_metric: Target output metric for correlations.
        max_insights: Maximum insights to return.

    Returns:
        List of N1Insight objects, sorted by confidence descending.
        Only includes findings that survive Bonferroni correction.
    """
    # Determine window from history if not specified
    if days_window is None:
        from services.phase3_eligibility import _history_stats
        stats = _history_stats(athlete_id, db)
        days_window = min(stats.get("history_span_days", 90), 365)
        days_window = max(days_window, 30)  # floor

    # Run correlation engine
    try:
        from services.correlation_engine import analyze_correlations
        result = analyze_correlations(
            athlete_id=str(athlete_id),
            days=days_window,
            db=db,
            output_metric=output_metric,
        )
    except Exception:
        return []

    raw = result.get("correlations", [])
    if not raw:
        return []

    # Bonferroni correction
    n_tests = max(len(raw), 1)
    insights: List[N1Insight] = []

    for c in raw:
        p_adj = min(c["p_value"] * n_tests, 1.0)
        r_val = c["correlation_coefficient"]
        n_val = c["sample_size"]

        # Gate: corrected significance + effect size + sample size
        if p_adj >= 0.05 or abs(r_val) < 0.3 or n_val < 10:
            continue

        input_name = c.get("input_name", "unknown")
        direction = c.get("direction", "positive")
        strength = c.get("strength", "moderate")
        lag = c.get("time_lag_days", 0)

        text = _build_insight_text(
            input_name=input_name,
            direction=direction,
            strength=strength,
            r=r_val,
            lag_days=lag,
            output_metric=output_metric,
        )

        # Safety: reject if banned acronyms leak through friendly-name mapping
        if BANNED_PATTERN.search(text):
            continue

        confidence = _compute_confidence(r_val, p_adj, n_val)
        evidence = {
            "r": round(r_val, 4),
            "p": round(c["p_value"], 6),
            "p_adjusted": round(p_adj, 6),
            "n": n_val,
            "lag_days": lag,
            "input_name": input_name,
        }

        insights.append(N1Insight(
            text=text,
            source="n1",
            confidence=confidence,
            evidence=evidence,
            category=_categorize(direction, output_metric),
        ))

    # Sort by confidence descending, cap at max_insights
    insights.sort(key=lambda i: i.confidence, reverse=True)
    return insights[:max_insights]
