"""
Meal template learning and matching.

Learns recurring meals from confirmed photo parses. After 3+ confirmations,
suggests the template's portions instead of re-estimating.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from models import MealTemplate

logger = logging.getLogger(__name__)


def compute_signature(food_names: list[str]) -> str:
    """Deterministic signature from sorted, normalized food names."""
    normalized = sorted(set(
        name.strip().lower().replace(" ", "_") for name in food_names if name
    ))
    return "+".join(normalized)


def find_template(
    athlete_id: str, food_names: list[str], db: Session
) -> Optional[dict]:
    """
    Find a matching template with >= 3 confirmations.
    Uses 80% item overlap for generous matching.
    """
    sig = compute_signature(food_names)
    exact = db.query(MealTemplate).filter(
        MealTemplate.athlete_id == athlete_id,
        MealTemplate.meal_signature == sig,
        MealTemplate.times_confirmed >= 3,
    ).first()

    if exact:
        return {
            "template_id": exact.id,
            "meal_signature": exact.meal_signature,
            "items": exact.items,
            "times_confirmed": exact.times_confirmed,
        }

    templates = db.query(MealTemplate).filter(
        MealTemplate.athlete_id == athlete_id,
        MealTemplate.times_confirmed >= 3,
    ).all()

    input_items = set(sig.split("+"))
    for t in templates:
        template_items = set(t.meal_signature.split("+"))
        if not template_items:
            continue
        overlap = len(input_items & template_items) / max(len(template_items), 1)
        if overlap >= 0.8:
            return {
                "template_id": t.id,
                "meal_signature": t.meal_signature,
                "items": t.items,
                "times_confirmed": t.times_confirmed,
            }

    return None


def upsert_template(
    athlete_id: str,
    food_names: list[str],
    confirmed_items: list[dict],
    db: Session,
) -> None:
    """Create or update a meal template from a confirmed meal."""
    sig = compute_signature(food_names)
    if not sig:
        return

    existing = db.query(MealTemplate).filter(
        MealTemplate.athlete_id == athlete_id,
        MealTemplate.meal_signature == sig,
    ).first()

    if existing:
        existing.items = confirmed_items
        existing.times_confirmed = (existing.times_confirmed or 0) + 1
        existing.last_used = datetime.now(timezone.utc)
    else:
        db.add(MealTemplate(
            athlete_id=athlete_id,
            meal_signature=sig,
            items=confirmed_items,
            times_confirmed=1,
            last_used=datetime.now(timezone.utc),
        ))

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to upsert meal template for %s", athlete_id, exc_info=True)
