"""Limiter Lifecycle Classifier (Phase 3)

Assigns lifecycle states to CorrelationFinding records:
  emerging            — correlation strengthening in L90, candidate frontier
  active              — current frontier, drives plan session type + dosing
  active_fixed        — L-SPEC only: pre-race integration, resolves at race day
  resolving           — intervention underway, correlation weakening
  closed              — historical signal, athlete solved it
  structural          — confirmed physiological trait, delivery modifications only
  structural_monitored — trait in 36-48h half-life range, stable but may shift
                         if acute cause is identified. Coach layer surfaces
                         differently from confirmed structural.

Classification priority (from LIMITER_TAXONOMY_ANNOTATED.md):
  0. CG-12: L-SPEC context gate (rule-based, overrides all)
  1. CG-11: L-REC structural discriminator (three-tier half-life)
  2. CG-10: CS-6/CS-7 interaction gate (fast recoverers)
  3. Standard lifecycle: active/emerging/resolving/closed

Resolution paths:
  active_fixed → closed: triggered by race date passing (not correlation fade)
  structural_monitored → active: if acute training cause identified

Notes:
  - ADVANCED_PEAK_MILES_FLOOR (30 mpw) is a conservative first-pass proxy
    for the CG-12 advanced tier check. The KB defines advanced by adaptation
    state and training history, not mileage alone. A 25 mpw athlete with 2
    years of consistent training could qualify. This threshold will be refined
    when the development ladder is implemented (Phase 5+).

See: docs/specs/LIMITER_TAXONOMY_ANNOTATED.md
     docs/specs/LIMITER_ENGINE_BRIEF.md
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

LREC_INPUT_NAMES = frozenset({
    "tsb", "daily_session_stress", "atl", "consecutive_run_days",
    "garmin_body_battery_end", "sleep_hours",
})

LREC_STRONG_INPUTS = frozenset({"daily_session_stress", "atl"})

LVOL_INPUT_NAMES = frozenset({
    "long_run_ratio", "weekly_volume_km", "ctl",
})

LTHRESH_INPUT_NAMES = frozenset({"days_since_quality"})

TSB_INPUTS = frozenset({"tsb"})

ADVANCED_PEAK_MILES_FLOOR = 30.0
LSPEC_WEEKS_TO_RACE = 6
STRUCTURAL_STABILITY_DAYS = 90
SOLVABLE_EMERGENCE_DAYS = 60


def classify_lifecycle_states(
    athlete_id: UUID,
    db: Session,
) -> Dict[int, str]:
    """Classify lifecycle state for all active correlation findings.

    Returns a dict of {finding.id: lifecycle_state} for every finding
    that was classified or reclassified.
    """
    from models import CorrelationFinding

    now = datetime.now(timezone.utc)
    results: Dict[int, str] = {}

    from sqlalchemy import or_

    findings = (
        db.query(CorrelationFinding)
        .filter(
            CorrelationFinding.athlete_id == athlete_id,
            CorrelationFinding.times_confirmed >= 3,
            or_(
                CorrelationFinding.is_active == True,  # noqa: E712
                CorrelationFinding.lifecycle_state == "active_fixed",
            ),
        )
        .all()
    )

    if not findings:
        return results

    profile = _get_profile(athlete_id, db)
    half_life = profile.recovery_half_life_hours if profile else None
    peak_miles = profile.peak_weekly_miles if profile else 0.0

    lspec_active = _check_lspec_gate(
        athlete_id, db, now, peak_miles,
    )

    for finding in findings:
        if finding.lifecycle_state == "active_fixed" and not lspec_active:
            state = "closed"
            logger.info(
                "limiter_classifier: active_fixed → closed for finding %s "
                "(L-SPEC gate no longer fires — race passed or conditions changed)",
                finding.id,
            )
        else:
            state = _classify_single(
                finding, half_life, lspec_active, now,
            )

        results[finding.id] = state

        if finding.lifecycle_state != state:
            finding.lifecycle_state = state
            finding.lifecycle_state_updated_at = now

    try:
        db.flush()
    except Exception as ex:
        logger.warning("limiter_classifier: flush failed: %s", ex)

    return results


def _get_profile(athlete_id: UUID, db: Session):
    """Derive athlete plan profile, returning None on failure."""
    try:
        from services.athlete_plan_profile import AthletePlanProfileService
        svc = AthletePlanProfileService()
        return svc.derive_profile(athlete_id, db, goal_distance="marathon")
    except Exception as ex:
        logger.warning("limiter_classifier: profile derivation failed: %s", ex)
        return None


def _check_lspec_gate(
    athlete_id: UUID,
    db: Session,
    now: datetime,
    peak_miles: float,
) -> bool:
    """CG-12: L-SPEC context gate.

    Fires when ALL conditions are met:
      - ≤6 weeks to goal race
      - Advanced athlete (peak miles ≥ 30)
      - Intervals AND threshold present in L30 activities
    """
    from models import TrainingPlan, Activity

    if peak_miles < ADVANCED_PEAK_MILES_FLOOR:
        return False

    cutoff = (now + timedelta(weeks=LSPEC_WEEKS_TO_RACE)).date()
    upcoming_plan = (
        db.query(TrainingPlan)
        .filter(
            TrainingPlan.athlete_id == athlete_id,
            TrainingPlan.goal_race_date <= cutoff,
            TrainingPlan.goal_race_date >= now.date(),
        )
        .order_by(TrainingPlan.goal_race_date.asc())
        .first()
    )

    if not upcoming_plan:
        return False

    l30_start = now - timedelta(days=30)
    recent_types = set(
        row[0] for row in
        db.query(Activity.workout_type)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= l30_start,
            Activity.workout_type.isnot(None),
        )
        .distinct()
        .all()
    )

    has_intervals = bool(
        recent_types & {"intervals", "interval", "vo2", "speed", "repetitions", "repeats"}
    )
    has_threshold = bool(
        recent_types & {"threshold", "tempo", "tempo_run", "threshold_intervals", "cruise_intervals"}
    )

    return has_intervals and has_threshold


def _classify_single(
    finding,
    half_life: Optional[float],
    lspec_active: bool,
    now: datetime,
) -> str:
    """Classify a single CorrelationFinding into a lifecycle state."""

    inp = finding.input_name

    if lspec_active:
        return "active_fixed"

    if inp in LREC_INPUT_NAMES:
        state = _classify_lrec(finding, half_life, now)
        if state:
            return state

    return _classify_standard(finding, now)


def _classify_lrec(
    finding,
    half_life: Optional[float],
    now: datetime,
) -> Optional[str]:
    """CG-11 + CG-10: L-REC classification.

    CG-10: CS-6/CS-7 interaction — TSB correlations with |r| > 0.45
    only flag L-REC when half-life > 36h. Fast recoverers get a timing
    signal, not an L-REC assignment.

    CG-11 three-tier discriminator:
      half-life >48h + stable 90+ days → structural
      half-life 36-48h + stable        → structural (monitored)
      half-life <36h + recent <60 days → active (solvable)
      half-life 36-48h + recent        → active (solvable)
    """
    inp = finding.input_name
    r = abs(finding.correlation_coefficient)

    if inp in TSB_INPUTS and r > 0.45:
        if half_life is not None and half_life <= 36.0:
            return None

    if half_life is None:
        return "active" if _is_recent(finding, now) else None

    stable = _is_stable(finding, now)

    if half_life > 48.0 and stable:
        return "structural"

    if 36.0 <= half_life <= 48.0:
        if stable:
            return "structural_monitored"
        else:
            return "active"

    if half_life < 36.0:
        if _is_recent(finding, now):
            return "active"
        return None

    return None


def _classify_standard(
    finding,
    now: datetime,
) -> str:
    """Standard lifecycle classification for non-L-REC findings.

    Uses temporal signals from the finding's confirmation history:
      - Recently strengthening → active or emerging
      - Stable and long-standing → active
      - Weakening (was strong, now fading) → resolving
      - Not confirmed recently → closed
    """
    r = abs(finding.correlation_coefficient)
    confirmed = finding.times_confirmed
    last_confirmed = finding.last_confirmed_at
    first_detected = finding.first_detected_at

    if last_confirmed is None:
        return "active" if r >= 0.30 else "closed"

    if last_confirmed.tzinfo is None:
        last_confirmed = last_confirmed.replace(tzinfo=timezone.utc)
    if first_detected and first_detected.tzinfo is None:
        first_detected = first_detected.replace(tzinfo=timezone.utc)

    days_since_confirmed = (now - last_confirmed).days

    if days_since_confirmed > 90:
        return "closed"

    if days_since_confirmed > 60 and r < 0.40:
        return "resolving"

    if first_detected:
        age_days = (now - first_detected).days
        if age_days < 60 and confirmed < 5:
            return "emerging"

    return "active"


def _is_recent(finding, now: datetime) -> bool:
    """Check if the finding emerged recently (< SOLVABLE_EMERGENCE_DAYS)."""
    first = finding.first_detected_at
    if first is None:
        return True
    if first.tzinfo is None:
        first = first.replace(tzinfo=timezone.utc)
    return (now - first).days < SOLVABLE_EMERGENCE_DAYS


def _is_stable(finding, now: datetime) -> bool:
    """Check if the finding has been stable for STRUCTURAL_STABILITY_DAYS."""
    first = finding.first_detected_at
    if first is None:
        return False
    if first.tzinfo is None:
        first = first.replace(tzinfo=timezone.utc)
    age = (now - first).days
    return age >= STRUCTURAL_STABILITY_DAYS and finding.times_confirmed >= 5
