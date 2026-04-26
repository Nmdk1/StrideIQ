"""
Phase 2 — per-athlete food override service.

The contract:
  - find_override picks the most-specific identifier (UPC > fpid > fdc_id)
  - upsert_override creates on first call, updates on subsequent calls
  - records_override_applied bumps the analytics counter without exploding
  - apply_override_to_barcode_response replaces catalog values
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from core.database import SessionLocal
from models import Athlete, AthleteFoodOverride, FuelingProduct
from services.food_override_service import (
    OverrideIdentifier,
    apply_override_to_barcode_response,
    find_override,
    list_overrides_for_athlete,
    record_override_applied,
    upsert_override,
)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def athlete(db):
    a = Athlete(
        email=f"override_{uuid4().hex[:8]}@example.com",
        display_name="Override Tester",
        subscription_tier="free",
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    yield a
    db.query(AthleteFoodOverride).filter(
        AthleteFoodOverride.athlete_id == a.id
    ).delete()
    db.delete(a)
    db.commit()


@pytest.fixture
def fueling_product(db):
    p = FuelingProduct(
        brand="TestBrand",
        product_name="TestBar",
        category="bar",
        serving_size_g=60,
        calories=210,
        protein_g=20,
        carbs_g=22,
        fat_g=7,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    yield p
    db.delete(p)
    db.commit()


# ---------------------------------------------------------------------------
# OverrideIdentifier guard
# ---------------------------------------------------------------------------


class TestOverrideIdentifierGuard:
    def test_requires_at_least_one_identifier(self):
        with pytest.raises(ValueError):
            OverrideIdentifier()

    def test_rejects_two_identifiers(self):
        with pytest.raises(ValueError):
            OverrideIdentifier(upc="123", fdc_id=456)

    def test_accepts_single_upc(self):
        OverrideIdentifier(upc="123")

    def test_accepts_single_fdc(self):
        OverrideIdentifier(fdc_id=456)

    def test_accepts_single_fpid(self):
        OverrideIdentifier(fueling_product_id=789)


# ---------------------------------------------------------------------------
# upsert + find round-trip
# ---------------------------------------------------------------------------


class TestUpsertAndFindRoundTrip:
    def test_create_returns_persisted_row(self, db, athlete):
        ov = upsert_override(
            db,
            athlete.id,
            OverrideIdentifier(upc="0123456789012"),
            food_name="David's Bar",
            calories=240,
            protein_g=25,
            carbs_g=20,
            fat_g=8,
        )
        assert ov.id is not None
        assert ov.athlete_id == athlete.id
        assert ov.upc == "0123456789012"
        assert ov.calories == 240
        assert ov.protein_g == 25

    def test_create_then_find_by_upc(self, db, athlete):
        upsert_override(
            db,
            athlete.id,
            OverrideIdentifier(upc="9991112223334"),
            calories=180,
        )
        hit = find_override(db, athlete.id, upc="9991112223334")
        assert hit is not None
        assert hit.calories == 180

    def test_find_returns_none_for_unknown_upc(self, db, athlete):
        upsert_override(
            db, athlete.id, OverrideIdentifier(upc="A"), calories=100
        )
        assert find_override(db, athlete.id, upc="B") is None

    def test_second_upsert_updates_existing_row(self, db, athlete):
        first = upsert_override(
            db,
            athlete.id,
            OverrideIdentifier(upc="X"),
            calories=200,
            protein_g=10,
        )
        second = upsert_override(
            db,
            athlete.id,
            OverrideIdentifier(upc="X"),
            calories=250,
        )
        assert first.id == second.id
        assert second.calories == 250
        assert second.protein_g == 10  # untouched, no clobber

    def test_per_athlete_isolation(self, db, athlete):
        other = Athlete(
            email=f"other_{uuid4().hex[:8]}@example.com",
            display_name="Other",
            subscription_tier="free",
        )
        db.add(other)
        db.commit()

        try:
            upsert_override(
                db, athlete.id, OverrideIdentifier(upc="ISOL"), calories=100
            )
            upsert_override(
                db, other.id, OverrideIdentifier(upc="ISOL"), calories=999
            )
            mine = find_override(db, athlete.id, upc="ISOL")
            theirs = find_override(db, other.id, upc="ISOL")
            assert mine.calories == 100
            assert theirs.calories == 999
        finally:
            db.query(AthleteFoodOverride).filter(
                AthleteFoodOverride.athlete_id == other.id
            ).delete()
            db.delete(other)
            db.commit()


# ---------------------------------------------------------------------------
# Identifier precedence: UPC > fueling_product_id > fdc_id
# ---------------------------------------------------------------------------


class TestIdentifierPrecedence:
    def test_upc_override_wins_over_fdc_when_both_passed(
        self, db, athlete
    ):
        upsert_override(
            db, athlete.id, OverrideIdentifier(upc="UPC1"), calories=111
        )
        upsert_override(
            db, athlete.id, OverrideIdentifier(fdc_id=222), calories=222
        )
        # When the same scan resolves both, UPC wins
        hit = find_override(db, athlete.id, upc="UPC1", fdc_id=222)
        assert hit.calories == 111

    def test_fpid_falls_through_when_no_upc_override_exists(
        self, db, athlete, fueling_product
    ):
        upsert_override(
            db,
            athlete.id,
            OverrideIdentifier(fueling_product_id=fueling_product.id),
            calories=333,
        )
        hit = find_override(
            db,
            athlete.id,
            upc="UNREGISTERED",
            fueling_product_id=fueling_product.id,
        )
        assert hit is not None
        assert hit.calories == 333

    def test_fdc_falls_through_when_no_upc_or_fpid_override(
        self, db, athlete
    ):
        upsert_override(
            db, athlete.id, OverrideIdentifier(fdc_id=999), calories=444
        )
        hit = find_override(db, athlete.id, fdc_id=999)
        assert hit.calories == 444


# ---------------------------------------------------------------------------
# Listing + counter
# ---------------------------------------------------------------------------


class TestListingAndCounter:
    def test_list_returns_only_athletes_overrides(self, db, athlete):
        upsert_override(
            db, athlete.id, OverrideIdentifier(upc="L1"), calories=100
        )
        upsert_override(
            db, athlete.id, OverrideIdentifier(upc="L2"), calories=200
        )
        rows = list_overrides_for_athlete(db, athlete.id)
        assert len(rows) >= 2
        upcs = {r.upc for r in rows}
        assert {"L1", "L2"}.issubset(upcs)

    def test_record_applied_bumps_counter_and_timestamp(self, db, athlete):
        ov = upsert_override(
            db, athlete.id, OverrideIdentifier(upc="C1"), calories=100
        )
        before = ov.times_applied
        record_override_applied(db, ov)
        db.refresh(ov)
        assert ov.times_applied == (before or 0) + 1
        assert ov.last_applied_at is not None


# ---------------------------------------------------------------------------
# apply_override_to_barcode_response
# ---------------------------------------------------------------------------


class TestApplyOverrideToBarcodeResponse:
    def test_replaces_set_fields_only(self, db, athlete):
        ov = upsert_override(
            db,
            athlete.id,
            OverrideIdentifier(upc="A1"),
            calories=240,
            protein_g=25,
        )
        catalog = {
            "found": True,
            "food_name": "Generic Bar",
            "serving_size_g": 100,
            "calories": 200,
            "protein_g": 18,
            "carbs_g": 24,
            "fat_g": 6,
            "fiber_g": 2,
        }
        merged = apply_override_to_barcode_response(catalog, ov)
        assert merged["calories"] == 240  # overridden
        assert merged["protein_g"] == 25  # overridden
        assert merged["carbs_g"] == 24  # untouched
        assert merged["fat_g"] == 6  # untouched
        assert merged["is_athlete_override"] is True
        assert merged["override_id"] == ov.id

    def test_overrides_food_name_when_set(self, db, athlete):
        ov = upsert_override(
            db,
            athlete.id,
            OverrideIdentifier(upc="A2"),
            food_name="My Custom Name",
        )
        catalog = {"food_name": "Generic", "calories": 100}
        merged = apply_override_to_barcode_response(catalog, ov)
        assert merged["food_name"] == "My Custom Name"
