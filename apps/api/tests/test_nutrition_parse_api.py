"""
Integration tests for Nutrition Parse endpoint (Phase 1)

POST /v1/nutrition/parse
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from uuid import uuid4
from unittest.mock import patch

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete


client = TestClient(app)


@pytest.fixture
def test_athlete():
    """Create a test athlete (unique per run)."""
    db = SessionLocal()
    try:
        athlete = Athlete(
            email=f"test_nutrition_parse_{uuid4()}@example.com",
            display_name="Test Athlete Nutrition Parse",
            subscription_tier="free",
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        yield athlete
        db.delete(athlete)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def auth_headers(test_athlete):
    token = create_access_token({"sub": str(test_athlete.id)})
    return {"Authorization": f"Bearer {token}"}


class TestNutritionParse:
    def test_parse_returns_prefilled_entry(self, test_athlete, auth_headers):
        with patch("services.nutrition_parser.parse_nutrition_text") as mock_parse:
            mock_parse.return_value = {
                "calories": 150.0,
                "protein_g": 5.0,
                "carbs_g": 27.0,
                "fat_g": 3.0,
                "fiber_g": 4.0,
                "notes": "oatmeal, black coffee",
            }

            resp = client.post(
                "/v1/nutrition/parse",
                json={"text": "oatmeal and black coffee"},
                headers=auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["athlete_id"] == str(test_athlete.id)
            assert data["date"] == date.today().isoformat()
            assert data["entry_type"] == "daily"
            assert data["activity_id"] is None
            assert data["calories"] == 150.0
            assert data["carbs_g"] == 27.0
            assert data["notes"] == "oatmeal, black coffee"

    def test_parse_requires_text(self, auth_headers):
        resp = client.post("/v1/nutrition/parse", json={"text": ""}, headers=auth_headers)
        assert resp.status_code == 422

    def test_parse_returns_503_on_parser_failure(self, auth_headers):
        with patch("services.nutrition_parser.parse_nutrition_text") as mock_parse:
            mock_parse.side_effect = RuntimeError("boom")
            resp = client.post(
                "/v1/nutrition/parse",
                json={"text": "banana"},
                headers=auth_headers,
            )
            assert resp.status_code == 503


class TestNutritionParseAvailable:
    def test_available_false_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        resp = client.get("/v1/nutrition/parse/available")
        assert resp.status_code == 200
        assert resp.json() == {"available": False}

    def test_available_true_when_key_set(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        resp = client.get("/v1/nutrition/parse/available")
        assert resp.status_code == 200
        assert resp.json() == {"available": True}

