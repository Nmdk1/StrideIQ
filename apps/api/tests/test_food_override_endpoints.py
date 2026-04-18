"""
Phase 2 — endpoint integration for per-athlete food overrides.

Verifies the full loop:
  1. First scan returns generic catalog values
  2. Athlete edits the entry to correct values
  3. Next scan returns the corrected values + is_athlete_override flag
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, AthleteFoodOverride, NutritionEntry, USDAFood
from services.usda_food_lookup import FoodMatch

client = TestClient(app)


def _auth_headers(athlete: Athlete) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token({'sub': str(athlete.id)})}"
    }


@pytest.fixture
def athlete():
    db = SessionLocal()
    try:
        a = Athlete(
            email=f"override_ep_{uuid4().hex[:8]}@example.com",
            display_name="Override Endpoint Tester",
            subscription_tier="free",
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        yield a

        # Clean up
        db.query(NutritionEntry).filter(
            NutritionEntry.athlete_id == a.id
        ).delete()
        db.query(AthleteFoodOverride).filter(
            AthleteFoodOverride.athlete_id == a.id
        ).delete()
        db.delete(a)
        db.commit()
    finally:
        db.close()


def _generic_match() -> FoodMatch:
    return FoodMatch(
        fdc_id=42424242,
        description="Generic Protein Bar",
        calories_per_100g=200.0,
        protein_per_100g=18.0,
        carbs_per_100g=24.0,
        fat_per_100g=6.0,
        fiber_per_100g=2.0,
        source="usda_local",
    )


# ---------------------------------------------------------------------------
# scan-barcode: catalog hit, no override
# ---------------------------------------------------------------------------


class TestScanBarcodeWithoutOverride:
    def test_returns_catalog_values_with_override_flag_false(self, athlete):
        with patch(
            "services.barcode_lookup.lookup_barcode",
            return_value=_generic_match(),
        ):
            r = client.post(
                "/v1/nutrition/scan-barcode",
                json={"upc": "0000000111111"},
                headers=_auth_headers(athlete),
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["found"] is True
        assert body["calories"] == 200
        assert body["protein_g"] == 18
        assert body.get("is_athlete_override") is False
        assert body.get("override_id") is None

    def test_returns_found_false_when_no_match_and_no_override(self, athlete):
        with patch("services.barcode_lookup.lookup_barcode", return_value=None):
            r = client.post(
                "/v1/nutrition/scan-barcode",
                json={"upc": "0000000222222"},
                headers=_auth_headers(athlete),
            )
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is False
        assert body.get("is_athlete_override") is False
        assert body.get("override_id") is None
        assert body.get("calories") is None


# ---------------------------------------------------------------------------
# Edit -> auto-learn -> next-scan flow
# ---------------------------------------------------------------------------


class TestEditAutoLearnsOverride:
    def test_full_loop_create_edit_rescan_returns_corrected_values(self, athlete):
        upc = "0000999888777"

        # 1. First scan — generic catalog
        with patch(
            "services.barcode_lookup.lookup_barcode",
            return_value=_generic_match(),
        ):
            r1 = client.post(
                "/v1/nutrition/scan-barcode",
                json={"upc": upc},
                headers=_auth_headers(athlete),
            )
        assert r1.status_code == 200
        scan = r1.json()
        assert scan["calories"] == 200
        assert scan.get("is_athlete_override") is False

        # 2. Athlete logs the entry, including source identifiers
        r2 = client.post(
            "/v1/nutrition",
            json={
                "athlete_id": str(uuid4()),
                "date": date.today().isoformat(),
                "entry_type": "daily",
                "calories": 200,
                "protein_g": 18,
                "carbs_g": 24,
                "fat_g": 6,
                "notes": "David's Protein Bar",
                "macro_source": "branded_barcode",
                "source_upc": upc,
                "source_fdc_id": 42424242,
            },
            headers=_auth_headers(athlete),
        )
        assert r2.status_code == 201, r2.text
        entry = r2.json()
        assert entry["source_upc"] == upc
        assert entry["source_fdc_id"] == 42424242

        # 3. Athlete edits — corrects calories from 200 -> 240
        r3 = client.put(
            f"/v1/nutrition/{entry['id']}",
            json={
                "athlete_id": str(uuid4()),
                "date": date.today().isoformat(),
                "entry_type": "daily",
                "calories": 240,
                "protein_g": 25,
                "carbs_g": 22,
                "fat_g": 8,
                "notes": "David's Protein Bar",
                "macro_source": "branded_barcode",
                "source_upc": upc,
                "source_fdc_id": 42424242,
            },
            headers=_auth_headers(athlete),
        )
        assert r3.status_code == 200, r3.text

        # 4. Override should now be persisted
        db = SessionLocal()
        try:
            ov = (
                db.query(AthleteFoodOverride)
                .filter(
                    AthleteFoodOverride.athlete_id == athlete.id,
                    AthleteFoodOverride.upc == upc,
                )
                .first()
            )
            assert ov is not None, "edit did not auto-learn an override"
            assert ov.calories == 240
            assert ov.protein_g == 25
            assert ov.carbs_g == 22
            assert ov.fat_g == 8
            assert ov.food_name == "David's Protein Bar"
        finally:
            db.close()

        # 5. Next scan returns the override values
        with patch(
            "services.barcode_lookup.lookup_barcode",
            return_value=_generic_match(),
        ):
            r5 = client.post(
                "/v1/nutrition/scan-barcode",
                json={"upc": upc},
                headers=_auth_headers(athlete),
            )
        assert r5.status_code == 200
        scan2 = r5.json()
        assert scan2["calories"] == 240
        assert scan2["protein_g"] == 25
        assert scan2["carbs_g"] == 22
        assert scan2["fat_g"] == 8
        assert scan2["food_name"] == "David's Protein Bar"
        assert scan2["is_athlete_override"] is True
        assert scan2["override_id"] is not None

    def test_patch_macro_change_also_auto_learns(self, athlete):
        upc = "0000111222333"
        # Create entry with source identifiers via POST
        r = client.post(
            "/v1/nutrition",
            json={
                "athlete_id": str(uuid4()),
                "date": date.today().isoformat(),
                "entry_type": "daily",
                "calories": 200,
                "protein_g": 18,
                "notes": "Bar",
                "macro_source": "branded_barcode",
                "source_upc": upc,
            },
            headers=_auth_headers(athlete),
        )
        assert r.status_code == 201
        entry_id = r.json()["id"]

        # PATCH calories
        rp = client.patch(
            f"/v1/nutrition/{entry_id}",
            json={"calories": 260},
            headers=_auth_headers(athlete),
        )
        assert rp.status_code == 200, rp.text

        # Override should exist
        db = SessionLocal()
        try:
            ov = (
                db.query(AthleteFoodOverride)
                .filter(
                    AthleteFoodOverride.athlete_id == athlete.id,
                    AthleteFoodOverride.upc == upc,
                )
                .first()
            )
            assert ov is not None
            assert ov.calories == 260
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Per-athlete isolation at the endpoint layer
# ---------------------------------------------------------------------------


class TestPerAthleteIsolationAtEndpoint:
    def test_one_athletes_override_does_not_leak_to_another(self, athlete):
        upc = "0000444555666"

        # Athlete A registers an override
        from services.food_override_service import (
            OverrideIdentifier,
            upsert_override,
        )

        db = SessionLocal()
        try:
            upsert_override(
                db,
                athlete.id,
                OverrideIdentifier(upc=upc),
                calories=350,
            )
        finally:
            db.close()

        # Athlete B scans the same UPC
        other = Athlete(
            email=f"isolation_{uuid4().hex[:8]}@example.com",
            display_name="Other Tester",
            subscription_tier="free",
        )
        db = SessionLocal()
        try:
            db.add(other)
            db.commit()
            db.refresh(other)
        finally:
            db.close()

        try:
            with patch(
                "services.barcode_lookup.lookup_barcode",
                return_value=_generic_match(),
            ):
                r = client.post(
                    "/v1/nutrition/scan-barcode",
                    json={"upc": upc},
                    headers=_auth_headers(other),
                )
            assert r.status_code == 200
            body = r.json()
            assert body["calories"] == 200, "Other athlete should see catalog values"
            assert body.get("is_athlete_override") is False
        finally:
            db = SessionLocal()
            try:
                db.delete(db.query(Athlete).filter(Athlete.id == other.id).first())
                db.commit()
            finally:
                db.close()
