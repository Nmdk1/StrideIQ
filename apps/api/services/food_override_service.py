"""
Per-athlete food override service.

When an athlete corrects the macros on a scanned/branded food, we remember
the correction keyed on (athlete, identifier) and replay it the next time
the same food is scanned. This solves the "David's protein bar always
shows wrong calories" class of bug — the system learns from corrections
instead of forgetting them.

Identifier precedence (most-specific wins):
    UPC > FuelingProduct.id > USDA fdc_id

The override schema enforces "exactly one identifier set" via a CHECK
constraint, so callers must pass exactly one of the three.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import AthleteFoodOverride


@dataclass(frozen=True)
class OverrideIdentifier:
    """Exactly one of the three fields is set; the others are None."""

    upc: Optional[str] = None
    fdc_id: Optional[int] = None
    fueling_product_id: Optional[int] = None

    def __post_init__(self) -> None:
        set_count = sum(
            1
            for v in (self.upc, self.fdc_id, self.fueling_product_id)
            if v is not None
        )
        if set_count != 1:
            raise ValueError(
                "OverrideIdentifier requires exactly one of "
                "(upc, fdc_id, fueling_product_id) to be set."
            )


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def find_override(
    db: Session,
    athlete_id: UUID | str,
    *,
    upc: Optional[str] = None,
    fdc_id: Optional[int] = None,
    fueling_product_id: Optional[int] = None,
) -> Optional[AthleteFoodOverride]:
    """Return the athlete's override for the most-specific identifier given.

    Precedence: UPC > fueling_product_id > fdc_id. Callers may pass any
    subset of identifiers; we'll try them in priority order so a UPC scan
    that also resolved to an fdc_id will still find a UPC override first.

    Returns None if no override is registered for any provided identifier.
    """
    if upc:
        hit = (
            db.query(AthleteFoodOverride)
            .filter(
                AthleteFoodOverride.athlete_id == athlete_id,
                AthleteFoodOverride.upc == upc,
            )
            .first()
        )
        if hit:
            return hit

    if fueling_product_id is not None:
        hit = (
            db.query(AthleteFoodOverride)
            .filter(
                AthleteFoodOverride.athlete_id == athlete_id,
                AthleteFoodOverride.fueling_product_id == fueling_product_id,
            )
            .first()
        )
        if hit:
            return hit

    if fdc_id is not None:
        hit = (
            db.query(AthleteFoodOverride)
            .filter(
                AthleteFoodOverride.athlete_id == athlete_id,
                AthleteFoodOverride.fdc_id == fdc_id,
            )
            .first()
        )
        if hit:
            return hit

    return None


def list_overrides_for_athlete(
    db: Session, athlete_id: UUID | str
) -> list[AthleteFoodOverride]:
    """Return all overrides for an athlete, most-recently-applied first."""
    return (
        db.query(AthleteFoodOverride)
        .filter(AthleteFoodOverride.athlete_id == athlete_id)
        .order_by(
            AthleteFoodOverride.last_applied_at.desc().nullslast(),
            AthleteFoodOverride.created_at.desc(),
        )
        .all()
    )


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


def upsert_override(
    db: Session,
    athlete_id: UUID | str,
    identifier: OverrideIdentifier,
    *,
    food_name: Optional[str] = None,
    serving_size_g: Optional[float] = None,
    calories: Optional[float] = None,
    protein_g: Optional[float] = None,
    carbs_g: Optional[float] = None,
    fat_g: Optional[float] = None,
    fiber_g: Optional[float] = None,
    caffeine_mg: Optional[float] = None,
    sodium_mg: Optional[float] = None,
) -> AthleteFoodOverride:
    """Create or update the athlete's override for the given identifier.

    All macro fields are optional — None means "do not override this field"
    on a fresh insert, or "leave the existing override value alone" on
    update. (To clear a field on update, write a new override instead.)
    """
    existing = find_override(
        db,
        athlete_id,
        upc=identifier.upc,
        fdc_id=identifier.fdc_id,
        fueling_product_id=identifier.fueling_product_id,
    )

    now = datetime.now(timezone.utc)

    if existing:
        if food_name is not None:
            existing.food_name = food_name
        if serving_size_g is not None:
            existing.serving_size_g = serving_size_g
        if calories is not None:
            existing.calories = calories
        if protein_g is not None:
            existing.protein_g = protein_g
        if carbs_g is not None:
            existing.carbs_g = carbs_g
        if fat_g is not None:
            existing.fat_g = fat_g
        if fiber_g is not None:
            existing.fiber_g = fiber_g
        if caffeine_mg is not None:
            existing.caffeine_mg = caffeine_mg
        if sodium_mg is not None:
            existing.sodium_mg = sodium_mg
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return existing

    override = AthleteFoodOverride(
        athlete_id=athlete_id,
        upc=identifier.upc,
        fdc_id=identifier.fdc_id,
        fueling_product_id=identifier.fueling_product_id,
        food_name=food_name,
        serving_size_g=serving_size_g,
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        fiber_g=fiber_g,
        caffeine_mg=caffeine_mg,
        sodium_mg=sodium_mg,
        times_applied=0,
    )
    db.add(override)
    db.commit()
    db.refresh(override)
    return override


def record_override_applied(
    db: Session, override: AthleteFoodOverride
) -> None:
    """Increment times_applied + bump last_applied_at when an override is served.

    Best-effort: failures are swallowed — the response to the user is more
    important than the analytics counter.
    """
    try:
        override.times_applied = (override.times_applied or 0) + 1
        override.last_applied_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()


# ---------------------------------------------------------------------------
# Application helpers
# ---------------------------------------------------------------------------


def apply_override_to_barcode_response(
    response_dict: dict,
    override: AthleteFoodOverride,
) -> dict:
    """Replace catalog values in a BarcodeScanResponse-shaped dict with override.

    Caller is responsible for serialising back to the response model. Any
    macro field that the override does not set keeps the catalog value.
    """
    out = dict(response_dict)
    if override.food_name is not None:
        out["food_name"] = override.food_name
    if override.serving_size_g is not None:
        out["serving_size_g"] = override.serving_size_g
    if override.calories is not None:
        out["calories"] = override.calories
    if override.protein_g is not None:
        out["protein_g"] = override.protein_g
    if override.carbs_g is not None:
        out["carbs_g"] = override.carbs_g
    if override.fat_g is not None:
        out["fat_g"] = override.fat_g
    if override.fiber_g is not None:
        out["fiber_g"] = override.fiber_g
    out["is_athlete_override"] = True
    out["override_id"] = override.id
    return out
