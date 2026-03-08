"""
Shared helper for formatting confirmed CorrelationFinding rows with
layer intelligence (thresholds, asymmetry, decay) for prompt injection.

Used by both the morning voice (_build_rich_intelligence_context) and
the coach brief (build_athlete_brief). Single source of truth for
formatting, limits, and ordering.
"""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def get_confirmed_findings(
    athlete_id: UUID,
    db: Session,
    min_confirmed: int = 3,
    limit: int = 8,
):
    """Return confirmed, active CorrelationFinding rows ordered by evidence weight."""
    from models import CorrelationFinding as CF

    return (
        db.query(CF)
        .filter(
            CF.athlete_id == athlete_id,
            CF.is_active == True,  # noqa: E712
            CF.times_confirmed >= min_confirmed,
        )
        .order_by(CF.times_confirmed.desc())
        .limit(limit)
        .all()
    )


def format_finding_line(f, verbose: bool = False) -> str:
    """Format a single CorrelationFinding into a prompt-ready string."""
    entry = (
        f"{f.input_name} → {f.output_metric}: "
        f"{f.insight_text or f.direction} "
        f"(confirmed {f.times_confirmed}x, r={f.correlation_coefficient:.2f}, "
        f"strength: {f.strength})"
    )

    details = []
    if f.threshold_value is not None:
        if verbose:
            details.append(
                f"Personal threshold: {f.input_name} cliff at "
                f"{f.threshold_value:.1f} ({f.threshold_direction}). "
                f"Below: r={f.r_below_threshold:.2f} (n={f.n_below_threshold}), "
                f"Above: r={f.r_above_threshold:.2f} (n={f.n_above_threshold})"
            )
        else:
            details.append(f"Threshold: {f.input_name} cliff at {f.threshold_value:.1f}")

    if f.asymmetry_ratio is not None:
        if verbose:
            details.append(
                f"Asymmetry: {f.asymmetry_ratio:.1f}x "
                f"({f.asymmetry_direction}). "
                f"Below baseline: effect={f.effect_below_baseline:.2f}, "
                f"Above baseline: effect={f.effect_above_baseline:.2f}"
            )
        else:
            details.append(f"Asymmetry: {f.asymmetry_ratio:.1f}x ({f.asymmetry_direction})")

    if f.decay_half_life_days is not None:
        details.append(
            f"Timing: half-life {f.decay_half_life_days:.1f} days ({f.decay_type})"
        )

    if f.time_lag_days and f.time_lag_days > 0:
        details.append(f"Lag: {f.time_lag_days} day(s)")

    if details:
        if verbose:
            return "- " + entry + "\n" + "\n".join(f"    {d}" for d in details)
        return "  " + entry + " — " + ", ".join(details)

    return ("- " if verbose else "  ") + entry


def build_fingerprint_prompt_section(
    athlete_id: UUID,
    db: Session,
    verbose: bool = False,
    max_findings: int = 8,
) -> Optional[str]:
    """
    Build the full fingerprint prompt section for injection.

    verbose=True: used by morning voice (full layer detail with newlines).
    verbose=False: used by coach brief (compact single-line per finding).

    Returns None if no confirmed findings exist.
    """
    findings = get_confirmed_findings(athlete_id, db, limit=max_findings)
    if not findings:
        return None

    lines = [format_finding_line(f, verbose=verbose) for f in findings]

    if verbose:
        header = (
            "--- Personal Fingerprint (confirmed patterns with evidence counts) ---\n"
            "IMPORTANT: When referencing these patterns, cite the confirmation count. "
            "Use threshold values for specific recommendations. "
            "Use decay timing for forward-looking advice.\n"
        )
    else:
        header = (
            "(These are confirmed personal patterns — cite evidence counts when referencing them. "
            "Use layer data for specific, grounded recommendations.)"
        )

    return header + "\n" + "\n".join(lines)
