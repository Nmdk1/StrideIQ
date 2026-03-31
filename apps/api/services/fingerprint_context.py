"""
Shared helper for formatting confirmed CorrelationFinding rows with
layer intelligence (thresholds, asymmetry, decay) for prompt injection.

Used by both the morning voice (_build_rich_intelligence_context) and
the coach brief (build_athlete_brief). Single source of truth for
formatting, limits, and ordering.

Phase 4 additions:
  - COACHING_LANGUAGE dictionary for DB field → coaching language translation
  - Lifecycle-state-aware labeling in format_finding_line
  - Closed findings grouped into a single summary line
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


COACHING_LANGUAGE: Dict[str, str] = {
    "long_run_ratio": "long runs",
    "weekly_volume_km": "weekly mileage",
    "ctl": "chronic training load",
    "tsb": "freshness (training stress balance)",
    "daily_session_stress": "session intensity",
    "atl": "recent training load",
    "consecutive_run_days": "consecutive running days",
    "garmin_body_battery_end": "body battery / recovery",
    "sleep_hours": "sleep duration",
    "days_since_quality": "days since last quality session",
    "days_since_rest": "days since rest",
    "cadence": "running cadence",
    "elevation_gain": "elevation gain",
    "heart_rate_avg": "average heart rate",
    "pace_threshold": "threshold pace",
    "pace_easy": "easy pace",
    "efficiency": "running efficiency",
    "vo2_estimate": "VO2 estimate",
    "distance_km": "run distance",
}


def _translate(field_name: str) -> str:
    """Translate a DB field name to coaching language.

    Falls back to a cleaned version of the field name if not in the dictionary.
    """
    if field_name in COACHING_LANGUAGE:
        return COACHING_LANGUAGE[field_name]
    return field_name.replace("_", " ")


def get_confirmed_findings(
    athlete_id: UUID,
    db: Session,
    min_confirmed: int = 1,
    limit: int = 12,
):
    """Return active CorrelationFinding rows ordered by evidence weight.

    Includes both confirmed (3+) and emerging (1-2) findings so the LLM
    has the full picture the Progress page shows.
    """
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
    """Format a single CorrelationFinding into a prompt-ready string.

    Lifecycle-aware: uses lifecycle_state when available for labeling.
    All field names go through the COACHING_LANGUAGE translator.
    """
    lifecycle = getattr(f, "lifecycle_state", None)

    if lifecycle == "emerging":
        tier = "EMERGING — ask athlete"
    elif lifecycle == "resolving":
        tier = "RESOLVING"
    elif lifecycle in ("structural", "structural_monitored"):
        tier = "STRUCTURAL"
    elif lifecycle == "active_fixed":
        tier = "ACTIVE (race-specific)"
    elif lifecycle == "active":
        tier = "ACTIVE"
    elif lifecycle == "closed":
        tier = "CLOSED"
    elif f.times_confirmed >= 6:
        tier = "STRONG"
    elif f.times_confirmed >= 3:
        tier = "CONFIRMED"
    else:
        tier = "EMERGING"

    inp = _translate(f.input_name)
    out = _translate(f.output_metric)

    entry = (
        f"[{tier} {f.times_confirmed}x] {inp} → {out}: "
        f"{f.insight_text or f.direction} "
        f"(r={f.correlation_coefficient:.2f}, strength: {f.strength})"
    )

    if lifecycle == "resolving" and getattr(f, "resolving_context", None):
        entry += f" — Attribution: {f.resolving_context}"

    details = []
    if f.threshold_value is not None:
        if verbose:
            details.append(
                f"Personal threshold: {inp} cliff at "
                f"{f.threshold_value:.1f} ({f.threshold_direction}). "
                f"Below: r={f.r_below_threshold:.2f} (n={f.n_below_threshold}), "
                f"Above: r={f.r_above_threshold:.2f} (n={f.n_above_threshold})"
            )
        else:
            details.append(f"Threshold: {inp} cliff at {f.threshold_value:.1f}")

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


def _format_closed_summary(closed_findings: list) -> str:
    """Format closed findings as a single grouped summary line.

    Instead of listing each closed finding individually (wasting prompt space),
    produce: "Previously solved: long runs (closed 8mo ago), sleep duration (closed 3mo ago)"
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    parts = []
    for f in closed_findings:
        inp = _translate(f.input_name)
        updated = getattr(f, "lifecycle_state_updated_at", None)
        if updated:
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            months = max(1, (now - updated).days // 30)
            parts.append(f"{inp} (closed {months}mo ago)")
        else:
            parts.append(f"{inp} (closed)")
    return "  Previously solved: " + ", ".join(parts)


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

    Phase 4: findings are grouped by lifecycle state. Closed findings are
    compressed to a single summary line. Emerging findings get an explicit
    "ask athlete" label so the coach knows to probe.

    Returns None if no confirmed findings exist.
    """
    findings = get_confirmed_findings(athlete_id, db, limit=max_findings)
    if not findings:
        return None

    active: List = []
    emerging: List = []
    resolving: List = []
    structural: List = []
    closed: List = []

    for f in findings:
        ls = getattr(f, "lifecycle_state", None)
        if ls == "closed":
            closed.append(f)
        elif ls == "emerging":
            emerging.append(f)
        elif ls == "resolving":
            resolving.append(f)
        elif ls in ("structural", "structural_monitored"):
            structural.append(f)
        else:
            active.append(f)

    if emerging:
        emerging.sort(
            key=lambda f: (
                getattr(f, "lifecycle_state_updated_at", None)
                or getattr(f, "first_detected_at", None)
                or datetime.min
            ),
            reverse=True,
        )
        emerging = emerging[:1]

    sections = []

    if verbose:
        header = (
            "--- Personal Fingerprint (data-proven patterns) ---\n"
            "ACTIVE = proven — state as fact in coaching language.\n"
            "EMERGING = pattern forming — ask the athlete about it.\n"
            "RESOLVING = improving — attribute to the athlete's work.\n"
            "STRUCTURAL = physiological trait — adjust delivery, do not try to fix.\n"
            "Translate to coaching language; do not expose statistical internals to the athlete.\n"
            "Use threshold/decay data for specific advice.\n"
        )
    else:
        n_active = len(active)
        n_emerging = len(emerging)
        header = (
            f"({n_active} active, {n_emerging} emerging, "
            f"{len(resolving)} resolving, {len(structural)} structural, "
            f"{len(closed)} closed patterns. "
            "Treat ACTIVE as fact. Hedge EMERGING as 'your data suggests'. "
            "Attribute RESOLVING to the athlete's work.)"
        )
    sections.append(header)

    for group in (active, structural, resolving, emerging):
        for f in group:
            sections.append(format_finding_line(f, verbose=verbose))

    if closed:
        sections.append(_format_closed_summary(closed))

    return "\n".join(sections)
