"""Finding Persistence — Living Fingerprint Spec.

Stores, updates, and supersedes AthleteFinding records.

Supersession logic: one active finding per (investigation_name, finding_type).
When an investigation runs again:
  - Same type found: update sentence/receipts/confidence, bump last_confirmed_at
  - Type no longer found: mark superseded_at, set is_active=False
  - New type found: create new active finding
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from models import AthleteFinding
from services.race_input_analysis import RaceInputFinding

logger = logging.getLogger(__name__)


def store_findings(
    athlete_id: UUID,
    investigation_name: str,
    findings: List[RaceInputFinding],
    db: Session,
) -> Tuple[int, int, int]:
    """Persist findings for a single investigation with supersession logic.

    Returns (created, updated, superseded) counts.
    """
    now = datetime.now(timezone.utc)

    existing = db.query(AthleteFinding).filter(
        AthleteFinding.athlete_id == athlete_id,
        AthleteFinding.investigation_name == investigation_name,
        AthleteFinding.is_active == True,  # noqa: E712
    ).all()

    existing_by_type = {f.finding_type: f for f in existing}
    new_types = {f.finding_type for f in findings}

    created = 0
    updated = 0
    superseded = 0

    for f in findings:
        if f.finding_type in existing_by_type:
            record = existing_by_type[f.finding_type]
            record.sentence = f.sentence
            record.receipts = f.receipts
            record.confidence = f.confidence
            record.last_confirmed_at = now
            updated += 1
        else:
            record = AthleteFinding(
                athlete_id=athlete_id,
                investigation_name=investigation_name,
                finding_type=f.finding_type,
                layer=getattr(f, 'layer', 'B') or 'B',
                sentence=f.sentence,
                receipts=f.receipts,
                confidence=f.confidence,
                first_detected_at=now,
                last_confirmed_at=now,
                is_active=True,
            )
            db.add(record)
            created += 1

    # Supersede findings that no longer emerge
    for ftype, record in existing_by_type.items():
        if ftype not in new_types:
            record.is_active = False
            record.superseded_at = now
            superseded += 1

    db.flush()
    return created, updated, superseded


def store_all_findings(
    athlete_id: UUID,
    findings: List[RaceInputFinding],
    db: Session,
) -> dict:
    """Persist all findings from mine_race_inputs, grouped by investigation.

    Uses the finding_type prefix to infer investigation name where
    the investigation name isn't explicitly carried on the finding.
    """
    by_investigation = {}
    for f in findings:
        inv_name = _infer_investigation_name(f)
        by_investigation.setdefault(inv_name, []).append(f)

    totals = {'created': 0, 'updated': 0, 'superseded': 0}

    for inv_name, inv_findings in by_investigation.items():
        c, u, s = store_findings(athlete_id, inv_name, inv_findings, db)
        totals['created'] += c
        totals['updated'] += u
        totals['superseded'] += s

    return totals


def _infer_investigation_name(f: RaceInputFinding) -> str:
    """Infer investigation name from finding_type."""
    type_to_inv = {
        'back_to_back_durability': 'investigate_back_to_back_durability',
        'race_execution': 'investigate_race_execution',
        'recovery_cost': 'investigate_recovery_cost',
        'training_recipe': 'investigate_training_recipe',
        'heat_resilience': 'investigate_heat_tax',
        'heat_tax': 'investigate_heat_tax',
        'post_injury_resilience': 'investigate_post_injury_resilience',
        'stride_economy': 'investigate_stride_economy',
        'long_run_durability': 'investigate_long_run_durability',
        'weekly_pattern': 'detect_weekly_patterns',
        'stride_progression': 'investigate_stride_progression',
        'cruise_interval_quality': 'investigate_cruise_interval_quality',
        'interval_recovery_trend': 'investigate_interval_recovery_trend',
        'workout_variety_effect': 'investigate_workout_variety_effect',
        'progressive_run_execution': 'investigate_progressive_run_execution',
    }

    for prefix, inv in type_to_inv.items():
        if f.finding_type.startswith(prefix):
            return inv

    if f.finding_type.startswith('adaptation_'):
        return 'detect_adaptation_curves'
    if f.finding_type.startswith('pace_at_hr_'):
        return 'investigate_pace_at_hr_adaptation'
    if f.finding_type.startswith('workout_progression_'):
        return 'investigate_workout_progression'

    return f'unknown_{f.finding_type}'


def get_active_findings(
    athlete_id: UUID,
    db: Session,
) -> List[AthleteFinding]:
    """Get all active findings for an athlete."""
    return db.query(AthleteFinding).filter(
        AthleteFinding.athlete_id == athlete_id,
        AthleteFinding.is_active == True,  # noqa: E712
    ).order_by(AthleteFinding.first_detected_at).all()
