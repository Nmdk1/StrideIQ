"""N=1 personalized insight generator (Phase 3C).

Transforms statistically significant per-athlete correlations into
human-readable, data-derived insights.  All insights:
- Pass Bonferroni-corrected significance + effect size + sample gates.
- Use "YOUR …" phrasing — observation, not prescription.
- Never leak internal metric acronyms (TSB, CTL, ATL, EF, VDOT, etc.).
- Scale confidence with data volume + effect strength.
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
    """Build a single human-readable insight sentence."""
    friendly_input = _friendly(input_name)
    friendly_output = _friendly(output_metric)

    # Direction phrasing
    if direction == "positive":
        relationship = "tends to improve"
        anti = "tends to decline"
    else:
        relationship = "tends to decline"
        anti = "tends to improve"

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

    text = (
        f"Based on your data: YOUR {friendly_output} {qual} {relationship}"
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


def _categorize(direction: str) -> str:
    """Map correlation direction to insight category."""
    if direction == "positive":
        return "what_works"
    return "what_doesnt"


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
            category=_categorize(direction),
        ))

    # Sort by confidence descending, cap at max_insights
    insights.sort(key=lambda i: i.confidence, reverse=True)
    return insights[:max_insights]
