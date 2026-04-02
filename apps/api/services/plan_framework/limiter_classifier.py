"""Limiter Lifecycle Classifier (Phase 3 + Phase 4 coach integration)

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
  3. Fact-aware promotion (Phase 4): limiter_context facts promote emerging
  4. Standard lifecycle: active/emerging/resolving/closed

Resolution paths:
  active_fixed → closed: triggered by race date passing (not correlation fade)
  structural_monitored → active: if acute training cause identified
  emerging → active: athlete-confirmed via limiter_context fact (Phase 4)
  emerging → closed: athlete explains pattern as historical via fact
  active → resolving: resolving_context captured for coach attribution

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

LSPEC_INPUT_NAME = "lspec_rule_based"
LSPEC_OUTPUT_METRIC = "race_readiness"

ADVANCED_PEAK_MILES_FLOOR = 30.0
LSPEC_WEEKS_TO_RACE = 6
STRUCTURAL_STABILITY_DAYS = 90
SOLVABLE_EMERGENCE_DAYS = 60

INPUT_TO_LIMITER_TYPE: Dict[str, str] = {
    "long_run_ratio": "L-VOL",
    "weekly_volume_km": "L-VOL",
    "ctl": "L-VOL",
    "tsb": "L-REC",
    "daily_session_stress": "L-REC",
    "atl": "L-REC",
    "consecutive_run_days": "L-REC",
    "garmin_body_battery_end": "L-REC",
    "sleep_hours": "L-REC",
    "days_since_quality": "L-THRESH",
    "days_since_rest": "L-CON",
}


def _get_limiter_type_for_finding(finding) -> Optional[str]:
    """Map a finding's input_name to its limiter category."""
    return INPUT_TO_LIMITER_TYPE.get(finding.input_name)


def classify_lifecycle_states(
    athlete_id: UUID,
    db: Session,
) -> Dict[int, str]:
    """Classify lifecycle state for all active correlation findings.

    L-SPEC (priority 0): If the athlete meets L-SPEC conditions (≤6w to
    race + advanced + intervals/threshold in L30), a synthetic finding
    with lifecycle_state=active_fixed is created or maintained. This does
    NOT override other findings — they keep their correct lifecycle states.

    Phase 4 additions:
      - Loads active limiter_context facts for the athlete.
      - Uses structured limiter_type matching to promote emerging → active
        (confirming) or emerging → closed (athlete explains as historical).
      - Captures resolving_context when a finding transitions to resolving.

    Returns a dict of {finding.id: lifecycle_state} for every finding
    that was classified or reclassified.
    """
    from models import CorrelationFinding

    now = datetime.now(timezone.utc)
    results: Dict[int, str] = {}

    profile = _get_profile(athlete_id, db)
    half_life = profile.recovery_half_life_hours if profile else None
    peak_miles = profile.peak_weekly_miles if profile else 0.0

    lspec_active = _check_lspec_gate(
        athlete_id, db, now, peak_miles,
    )
    lspec_finding = _manage_lspec_finding(athlete_id, db, now, lspec_active)
    if lspec_finding:
        results[lspec_finding.id] = lspec_finding.lifecycle_state

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

    limiter_facts = _load_limiter_context_facts(athlete_id, db, now)
    expired_fact_types = _detect_expired_fact_types(athlete_id, db, now)

    for finding in findings:
        if finding.input_name == LSPEC_INPUT_NAME:
            if finding.id not in results:
                results[finding.id] = finding.lifecycle_state
            continue

        old_state = finding.lifecycle_state

        if old_state == "active_fixed":
            state = "closed"
            logger.info(
                "limiter_classifier: active_fixed → closed for finding %s "
                "(non-synthetic active_fixed cleaned up)",
                finding.id,
            )
        else:
            state = _classify_single(
                finding, half_life, now,
            )

        state = _apply_fact_promotion(finding, state, limiter_facts)

        finding_limiter = _get_limiter_type_for_finding(finding)
        if (
            old_state == "active"
            and state != "active"
            and finding_limiter in expired_fact_types
        ):
            logger.info(
                "limiter_classifier: active → %s for finding %s "
                "(limiter_context fact expired, forced re-evaluation)",
                state, finding.id,
            )

        if old_state == "active" and state == "resolving":
            finding.resolving_context = _build_resolving_context(
                finding, limiter_facts, db, athlete_id,
            )

        results[finding.id] = state

        if old_state != state:
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


def _manage_lspec_finding(
    athlete_id: UUID,
    db: Session,
    now: datetime,
    lspec_active: bool,
):
    """Create, maintain, or deactivate the synthetic L-SPEC finding.

    When CG-12 gate fires: creates or reactivates a synthetic finding
    with lifecycle_state=active_fixed and input_name=lspec_rule_based.

    When CG-12 stops firing: deactivates the synthetic finding (closed).

    Returns the finding (or None if L-SPEC never existed).
    """
    import uuid as uuid_mod
    from models import CorrelationFinding

    existing = (
        db.query(CorrelationFinding)
        .filter(
            CorrelationFinding.athlete_id == athlete_id,
            CorrelationFinding.input_name == LSPEC_INPUT_NAME,
            CorrelationFinding.output_metric == LSPEC_OUTPUT_METRIC,
        )
        .first()
    )

    if lspec_active:
        if existing:
            if existing.lifecycle_state != "active_fixed":
                logger.info(
                    "limiter_classifier: L-SPEC reactivated for athlete %s",
                    athlete_id,
                )
                existing.lifecycle_state = "active_fixed"
                existing.lifecycle_state_updated_at = now
                existing.is_active = True
            existing.last_confirmed_at = now
            return existing

        finding = CorrelationFinding(
            id=uuid_mod.uuid4(),
            athlete_id=athlete_id,
            input_name=LSPEC_INPUT_NAME,
            output_metric=LSPEC_OUTPUT_METRIC,
            direction="positive",
            time_lag_days=0,
            correlation_coefficient=1.0,
            p_value=0.0,
            sample_size=1,
            strength="strong",
            times_confirmed=3,
            first_detected_at=now,
            last_confirmed_at=now,
            category="pattern",
            confidence=1.0,
            is_active=True,
            lifecycle_state="active_fixed",
            lifecycle_state_updated_at=now,
            discovery_source="lspec_rule",
        )
        db.add(finding)
        logger.info(
            "limiter_classifier: L-SPEC synthetic finding created for athlete %s",
            athlete_id,
        )
        return finding

    if existing and existing.lifecycle_state == "active_fixed":
        existing.lifecycle_state = "closed"
        existing.lifecycle_state_updated_at = now
        existing.is_active = False
        logger.info(
            "limiter_classifier: L-SPEC deactivated for athlete %s "
            "(gate no longer fires)",
            athlete_id,
        )
        return existing

    return existing


LSPEC_PACE_TOLERANCE = 1.03
LSPEC_THRESHOLD_MIN_SECONDS = 600

def _check_lspec_gate(
    athlete_id: UUID,
    db: Session,
    now: datetime,
    peak_miles: float,
) -> bool:
    """CG-12: L-SPEC context gate (pace-verified).

    Fires when ALL conditions are met:
      1. ≤6 weeks to active goal race
      2. Advanced athlete (peak miles ≥ 30)
      3. Any L30 split at interval pace (from RPI)
      4. Any L30 activity with ≥10 min total at threshold pace (from RPI)

    Pace data is the truth — workout_type labels are ignored.
    A fartlek at interval pace IS an interval session.
    A progression run with 12 min at threshold pace IS threshold work.
    """
    from models import TrainingPlan, Athlete

    if peak_miles < ADVANCED_PEAK_MILES_FLOOR:
        return False

    cutoff = (now + timedelta(weeks=LSPEC_WEEKS_TO_RACE)).date()
    upcoming_plan = (
        db.query(TrainingPlan)
        .filter(
            TrainingPlan.athlete_id == athlete_id,
            TrainingPlan.status == "active",
            TrainingPlan.goal_race_date <= cutoff,
            TrainingPlan.goal_race_date >= now.date(),
        )
        .order_by(TrainingPlan.goal_race_date.asc())
        .first()
    )

    if not upcoming_plan:
        return False

    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete or not athlete.rpi:
        return False

    pace_thresholds = _get_pace_thresholds(athlete.rpi)
    if not pace_thresholds:
        return False

    interval_pace, threshold_pace = pace_thresholds
    l30_start = now - timedelta(days=30)

    has_intervals = _any_split_at_pace(
        athlete_id, db, l30_start, interval_pace,
    )
    if not has_intervals:
        return False

    has_threshold = _any_session_sustained_pace(
        athlete_id, db, l30_start, threshold_pace, LSPEC_THRESHOLD_MIN_SECONDS,
    )

    return has_threshold


def _get_pace_thresholds(rpi: float) -> Optional[tuple]:
    """Derive interval and threshold pace thresholds (seconds/mile) from RPI."""
    try:
        from services.rpi_calculator import calculate_training_paces
        paces = calculate_training_paces(rpi)
        interval_pace = paces.get("interval_pace")
        threshold_pace = paces.get("threshold_pace")
        if interval_pace and threshold_pace:
            return (interval_pace, threshold_pace)
    except Exception as ex:
        logger.warning("limiter_classifier: pace threshold derivation failed: %s", ex)
    return None


def _any_split_at_pace(
    athlete_id: UUID,
    db: Session,
    since: datetime,
    target_pace_sec_per_mile: int,
) -> bool:
    """Check if any L30 split hit interval pace (with tolerance)."""
    from models import Activity, ActivitySplit

    max_pace = target_pace_sec_per_mile * LSPEC_PACE_TOLERANCE

    splits = (
        db.query(
            ActivitySplit.distance,
            ActivitySplit.moving_time,
            ActivitySplit.elapsed_time,
        )
        .join(Activity, ActivitySplit.activity_id == Activity.id)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
            Activity.start_time >= since,
            ActivitySplit.distance > 50,
        )
        .all()
    )

    for s in splits:
        dist_m = float(s.distance) if s.distance else 0
        time_s = s.moving_time or s.elapsed_time or 0
        if dist_m < 50 or time_s < 10:
            continue
        pace = time_s / (dist_m / 1609.34)
        if pace <= max_pace:
            return True

    return False


def _any_session_sustained_pace(
    athlete_id: UUID,
    db: Session,
    since: datetime,
    target_pace_sec_per_mile: int,
    min_duration_seconds: int,
) -> bool:
    """Check if any L30 activity has >= min_duration at threshold pace."""
    from models import Activity, ActivitySplit

    max_pace = target_pace_sec_per_mile * LSPEC_PACE_TOLERANCE

    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
            Activity.start_time >= since,
        )
        .all()
    )

    for act in activities:
        splits = (
            db.query(
                ActivitySplit.distance,
                ActivitySplit.moving_time,
                ActivitySplit.elapsed_time,
            )
            .filter(ActivitySplit.activity_id == act.id)
            .all()
        )
        total_at_pace = 0
        for s in splits:
            dist_m = float(s.distance) if s.distance else 0
            time_s = s.moving_time or s.elapsed_time or 0
            if dist_m < 50 or time_s < 10:
                continue
            pace = time_s / (dist_m / 1609.34)
            if pace <= max_pace:
                total_at_pace += time_s
        if total_at_pace >= min_duration_seconds:
            return True

    return False


def _classify_single(
    finding,
    half_life: Optional[float],
    now: datetime,
) -> str:
    """Classify a single CorrelationFinding into a lifecycle state.

    L-SPEC is handled separately by _manage_lspec_finding — this function
    classifies correlation-derived findings only.
    """
    inp = finding.input_name

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


# ---------------------------------------------------------------------------
# Phase 4: Fact-aware promotion and resolving context
# ---------------------------------------------------------------------------

def _load_limiter_context_facts(
    athlete_id: UUID,
    db: Session,
    now: datetime,
) -> list:
    """Load active (non-expired) limiter_context facts for the athlete."""
    from models import AthleteFact

    facts = (
        db.query(AthleteFact)
        .filter(
            AthleteFact.athlete_id == athlete_id,
            AthleteFact.fact_type == "limiter_context",
            AthleteFact.is_active == True,  # noqa: E712
        )
        .all()
    )

    active_facts = []
    for f in facts:
        if _is_fact_expired(f, now):
            continue
        active_facts.append(f)
    return active_facts


def _is_fact_expired(fact, now: datetime) -> bool:
    """Check if a temporal fact has expired based on extracted_at + ttl_days."""
    try:
        if not fact.temporal or not fact.ttl_days:
            return False
        extracted = fact.extracted_at
        if extracted is None:
            return False
        if not isinstance(extracted, datetime):
            return False
        if extracted.tzinfo is None:
            extracted = extracted.replace(tzinfo=timezone.utc)
        return (extracted + timedelta(days=int(fact.ttl_days))) < now
    except (TypeError, ValueError):
        return False


def _detect_expired_fact_types(
    athlete_id: UUID,
    db: Session,
    now: datetime,
) -> frozenset:
    """Find limiter_type values whose limiter_context facts have expired.

    Used to log forced re-evaluation when a supporting fact lapses.
    """
    from models import AthleteFact

    expired_types: set = set()
    facts = (
        db.query(AthleteFact)
        .filter(
            AthleteFact.athlete_id == athlete_id,
            AthleteFact.fact_type == "limiter_context",
            AthleteFact.is_active == True,  # noqa: E712
        )
        .all()
    )
    for f in facts:
        if _is_fact_expired(f, now):
            lt = _extract_limiter_type_from_fact(f)
            if lt:
                expired_types.add(lt)
    return frozenset(expired_types)


def _apply_fact_promotion(
    finding,
    proposed_state: str,
    limiter_facts: list,
) -> str:
    """Check if a limiter_context fact should override the proposed state.

    Matching: the fact's fact_key must contain a structured limiter_type
    that matches the finding's input_name → limiter category mapping.

    Promotion rules:
      - emerging + confirming fact → active
      - emerging + historical-context fact → closed
    Only fires for emerging findings with a matching fact.
    """
    if proposed_state != "emerging":
        return proposed_state

    finding_limiter = _get_limiter_type_for_finding(finding)
    if not finding_limiter:
        return proposed_state

    for fact in limiter_facts:
        fact_limiter = _extract_limiter_type_from_fact(fact)
        if fact_limiter != finding_limiter:
            continue

        disposition = (fact.fact_value or "").strip().lower()
        if disposition in ("historical", "resolved", "past", "closed"):
            logger.info(
                "limiter_classifier: emerging → closed for finding %s "
                "(athlete explained as historical via fact %s)",
                finding.id, fact.id,
            )
            return "closed"

        logger.info(
            "limiter_classifier: emerging → active for finding %s "
            "(athlete confirmed via limiter_context fact %s)",
            finding.id, fact.id,
        )
        return "active"

    return proposed_state


def _extract_limiter_type_from_fact(fact) -> Optional[str]:
    """Extract the structured limiter_type from a limiter_context fact.

    fact_key format: "limiter_type:L-VOL" or just "L-VOL".
    """
    key = (fact.fact_key or "").strip()
    if key.startswith("limiter_type:"):
        return key.split(":", 1)[1].strip()
    if key.startswith("L-"):
        return key
    return None


def _build_resolving_context(
    finding,
    limiter_facts: list,
    db: Session,
    athlete_id: UUID,
) -> Optional[str]:
    """Build attribution string at active → resolving transition.

    Combines limiter_context fact values and current plan phase
    to explain what the athlete did that caused the shift.
    """
    parts = []

    finding_limiter = _get_limiter_type_for_finding(finding)
    for fact in limiter_facts:
        fact_limiter = _extract_limiter_type_from_fact(fact)
        if fact_limiter == finding_limiter and fact.fact_value:
            parts.append(fact.fact_value.strip())

    try:
        from models import TrainingPlan
        plan = (
            db.query(TrainingPlan)
            .filter(
                TrainingPlan.athlete_id == athlete_id,
                TrainingPlan.status == "active",
            )
            .order_by(TrainingPlan.created_at.desc())
            .first()
        )
        if plan and plan.name:
            parts.append(f"during {plan.name}")
    except Exception:
        pass

    if not parts:
        return None
    return "; ".join(parts)
