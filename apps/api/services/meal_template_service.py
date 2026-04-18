"""
Meal template learning, naming, and reuse.

Two ways a template gets created:

1. **Implicit learning** — when an athlete confirms a multi-item meal
   (currently photo-parsed), we upsert a signature row.  Once the same
   signature has been confirmed >= ``NAME_PROMPT_THRESHOLD`` times we
   set ``name_prompted_at`` and the frontend offers "Name this meal".

2. **Explicit save** — the athlete taps "Save as meal" on a logged
   entry or builds a meal in the picker.  ``is_user_named=True`` and
   ``name`` is required so it shows up in the named-meals picker.

Logging a saved meal copies the items into a fresh ``NutritionEntry``
on a chosen date — see :func:`log_template_for_athlete`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date as date_type, datetime, timezone
from decimal import Decimal
from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import MealTemplate, NutritionEntry

logger = logging.getLogger(__name__)


# Surface a "name this meal" prompt only once the athlete has clearly
# repeated the meal — three is the same threshold the photo-parse path
# already uses for surfacing template_match.
NAME_PROMPT_THRESHOLD = 3


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------


def compute_signature(food_names: Iterable[str]) -> str:
    """Deterministic signature from sorted, normalized food names."""
    normalized = sorted({
        name.strip().lower().replace(" ", "_") for name in food_names if name
    })
    return "+".join(normalized)


# ---------------------------------------------------------------------------
# Implicit-learner read path
# ---------------------------------------------------------------------------


def find_template(
    athlete_id, food_names: list[str], db: Session
) -> Optional[dict]:
    """
    Find a matching implicit-learner template with >= 3 confirmations.

    Used by the photo parser to suggest "you've logged this meal before".
    Uses 80% item overlap so a missing or extra single item still matches.
    """
    sig = compute_signature(food_names)
    if not sig:
        return None
    exact = db.query(MealTemplate).filter(
        MealTemplate.athlete_id == athlete_id,
        MealTemplate.meal_signature == sig,
        MealTemplate.times_confirmed >= NAME_PROMPT_THRESHOLD,
    ).first()

    if exact:
        return _template_to_dict(exact)

    templates = db.query(MealTemplate).filter(
        MealTemplate.athlete_id == athlete_id,
        MealTemplate.times_confirmed >= NAME_PROMPT_THRESHOLD,
    ).all()

    input_items = set(sig.split("+"))
    for t in templates:
        template_items = set(t.meal_signature.split("+"))
        if not template_items:
            continue
        overlap = len(input_items & template_items) / max(len(template_items), 1)
        if overlap >= 0.8:
            return _template_to_dict(t)

    return None


def _template_to_dict(t: MealTemplate) -> dict:
    return {
        "template_id": t.id,
        "meal_signature": t.meal_signature,
        "items": t.items,
        "times_confirmed": t.times_confirmed,
        "name": t.name,
        "is_user_named": bool(t.is_user_named),
        "should_prompt_name": (
            (t.times_confirmed or 0) >= NAME_PROMPT_THRESHOLD
            and not t.is_user_named
            and t.name_prompted_at is None
        ),
    }


# ---------------------------------------------------------------------------
# Implicit-learner write path
# ---------------------------------------------------------------------------


def upsert_template(
    athlete_id,
    food_names: list[str],
    confirmed_items: list[dict],
    db: Session,
) -> Optional[MealTemplate]:
    """Create or update an implicit-learner template from a confirmed meal.

    Returns the upserted row (or ``None`` if the inputs were unusable).
    Only meaningful for multi-item meals — single-item entries (e.g. a
    barcode-scanned bar) will not be upserted because they're noise.
    """
    if len(food_names) < 2:
        # Single-item logs are not "meals" and just pollute the templates
        # table.  This is the implicit-learner fix referenced in Phase 3.
        return None

    sig = compute_signature(food_names)
    if not sig:
        return None

    existing = db.query(MealTemplate).filter(
        MealTemplate.athlete_id == athlete_id,
        MealTemplate.meal_signature == sig,
    ).first()

    if existing:
        existing.items = confirmed_items
        existing.times_confirmed = (existing.times_confirmed or 0) + 1
        existing.last_used = datetime.now(timezone.utc)
        row = existing
    else:
        row = MealTemplate(
            athlete_id=athlete_id,
            meal_signature=sig,
            items=confirmed_items,
            times_confirmed=1,
            last_used=datetime.now(timezone.utc),
            is_user_named=False,
        )
        db.add(row)

    try:
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        logger.warning(
            "Failed to upsert meal template for %s", athlete_id, exc_info=True
        )
        return None


# ---------------------------------------------------------------------------
# Explicit save / named-meal CRUD
# ---------------------------------------------------------------------------


@dataclass
class TemplateItem:
    food: str
    grams: Optional[float] = None
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    source_upc: Optional[str] = None
    source_fdc_id: Optional[int] = None

    def to_jsonable(self) -> dict:
        d = {"food": self.food}
        for f in (
            "grams",
            "calories",
            "protein_g",
            "carbs_g",
            "fat_g",
            "fiber_g",
            "source_upc",
            "source_fdc_id",
        ):
            v = getattr(self, f)
            if v is not None:
                d[f] = v
        return d


def save_named_template(
    athlete_id,
    name: str,
    items: List[TemplateItem],
    db: Session,
) -> MealTemplate:
    """Explicitly save a meal under a user-given name.

    If a row with the same signature already exists (e.g. it was learned
    implicitly first), we promote it to ``is_user_named=True`` and apply
    the name; otherwise we create a fresh row.
    """
    if not name or not name.strip():
        raise ValueError("name is required")
    if not items:
        raise ValueError("at least one item is required")

    name = name.strip()
    food_names = [it.food for it in items if it.food]
    sig = compute_signature(food_names)
    if not sig:
        raise ValueError("items must include at least one food name")

    items_json = [it.to_jsonable() for it in items]

    existing = db.query(MealTemplate).filter(
        MealTemplate.athlete_id == athlete_id,
        MealTemplate.meal_signature == sig,
    ).first()

    if existing:
        existing.name = name
        existing.is_user_named = True
        existing.items = items_json
        existing.last_used = datetime.now(timezone.utc)
        # Don't reset times_confirmed — preserve learned signal.
        row = existing
    else:
        row = MealTemplate(
            athlete_id=athlete_id,
            meal_signature=sig,
            items=items_json,
            times_confirmed=1,
            last_used=datetime.now(timezone.utc),
            name=name,
            is_user_named=True,
        )
        db.add(row)

    db.commit()
    db.refresh(row)
    return row


def list_named_templates(athlete_id, db: Session) -> List[MealTemplate]:
    """Return the athlete's saved/named meals, most-recently-used first."""
    return (
        db.query(MealTemplate)
        .filter(
            MealTemplate.athlete_id == athlete_id,
            MealTemplate.is_user_named.is_(True),
        )
        .order_by(MealTemplate.last_used.desc().nullslast(), MealTemplate.id.desc())
        .all()
    )


def get_template(template_id: int, athlete_id, db: Session) -> Optional[MealTemplate]:
    return (
        db.query(MealTemplate)
        .filter(
            MealTemplate.id == template_id,
            MealTemplate.athlete_id == athlete_id,
        )
        .first()
    )


def update_template(
    template_id: int,
    athlete_id,
    db: Session,
    *,
    name: Optional[str] = None,
    items: Optional[List[TemplateItem]] = None,
) -> Optional[MealTemplate]:
    row = get_template(template_id, athlete_id, db)
    if not row:
        return None

    if name is not None:
        new_name = name.strip()
        if not new_name:
            raise ValueError("name cannot be empty")
        row.name = new_name
        row.is_user_named = True

    if items is not None:
        if not items:
            raise ValueError("items cannot be empty")
        food_names = [it.food for it in items if it.food]
        sig = compute_signature(food_names)
        if not sig:
            raise ValueError("items must include at least one food name")
        row.items = [it.to_jsonable() for it in items]
        # Re-compute signature since items changed; relax uniqueness if it
        # collides by appending the existing pk (rare, but possible).
        if sig != row.meal_signature:
            collision = (
                db.query(MealTemplate)
                .filter(
                    MealTemplate.athlete_id == athlete_id,
                    MealTemplate.meal_signature == sig,
                    MealTemplate.id != row.id,
                )
                .first()
            )
            if collision is None:
                row.meal_signature = sig
            else:
                # Keep the original signature to avoid the unique conflict;
                # items are still updated.
                pass

    db.commit()
    db.refresh(row)
    return row


def delete_template(template_id: int, athlete_id, db: Session) -> bool:
    row = get_template(template_id, athlete_id, db)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def mark_name_prompt_shown(template_id: int, athlete_id, db: Session) -> None:
    """Idempotently record that we've offered the name-this-meal prompt."""
    row = get_template(template_id, athlete_id, db)
    if not row or row.name_prompted_at is not None:
        return
    row.name_prompted_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except Exception:
        db.rollback()


# ---------------------------------------------------------------------------
# Logging a template -> NutritionEntry
# ---------------------------------------------------------------------------


def _sum_items(items: list[dict]) -> dict:
    total = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "fiber_g": 0.0}
    for it in items or []:
        for k in total:
            v = it.get(k)
            if isinstance(v, (int, float, Decimal)):
                total[k] += float(v)
    return total


def log_template_for_athlete(
    template_id: int,
    athlete_id: UUID,
    log_date: date_type,
    entry_type: str,
    db: Session,
    *,
    activity_id: Optional[UUID] = None,
    notes_override: Optional[str] = None,
) -> Optional[NutritionEntry]:
    """Log a saved meal as a NutritionEntry on the given date.

    The caller is responsible for date-window validation and activity_id
    consistency — this function only assembles the entry.  Returns the
    persisted entry, or None if the template could not be found.
    """
    template = get_template(template_id, athlete_id, db)
    if not template:
        return None

    totals = _sum_items(template.items or [])
    notes = notes_override or template.name or "Saved meal"

    entry = NutritionEntry(
        athlete_id=athlete_id,
        date=log_date,
        entry_type=entry_type,
        activity_id=activity_id,
        calories=Decimal(str(totals["calories"])) if totals["calories"] else None,
        protein_g=Decimal(str(totals["protein_g"])) if totals["protein_g"] else None,
        carbs_g=Decimal(str(totals["carbs_g"])) if totals["carbs_g"] else None,
        fat_g=Decimal(str(totals["fat_g"])) if totals["fat_g"] else None,
        fiber_g=Decimal(str(totals["fiber_g"])) if totals["fiber_g"] else None,
        notes=notes,
        macro_source="meal_template",
    )
    db.add(entry)

    template.last_used = datetime.now(timezone.utc)

    db.commit()
    db.refresh(entry)
    return entry
