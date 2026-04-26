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


class TestNutritionParseMeal:
    """POST /v1/nutrition/parse-meal -- powers the meal builder textarea.

    Returns a list of structured items so the user can edit each one
    individually, instead of one merged macro total like /parse does.
    """

    def test_parse_meal_returns_items_list(self, test_athlete, auth_headers):
        with patch("services.nutrition_parser.parse_meal_items") as mock_parse:
            mock_parse.return_value = [
                {
                    "food": "2 eggs scrambled",
                    "calories": 180.0,
                    "protein_g": 12.0,
                    "carbs_g": 1.0,
                    "fat_g": 14.0,
                    "fiber_g": 0.0,
                    "macro_source": "llm_estimated",
                },
                {
                    "food": "1 slice whole wheat toast",
                    "calories": 80.0,
                    "protein_g": 4.0,
                    "carbs_g": 14.0,
                    "fat_g": 1.0,
                    "fiber_g": 2.0,
                    "macro_source": "usda_local",
                },
            ]

            resp = client.post(
                "/v1/nutrition/parse-meal",
                json={"text": "2 eggs scrambled and 1 slice whole wheat toast"},
                headers=auth_headers,
            )

            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert len(data["items"]) == 2
            assert data["items"][0]["food"] == "2 eggs scrambled"
            assert data["items"][0]["calories"] == 180.0
            assert data["items"][1]["macro_source"] == "usda_local"

    def test_parse_meal_requires_text(self, auth_headers):
        resp = client.post(
            "/v1/nutrition/parse-meal", json={"text": ""}, headers=auth_headers
        )
        assert resp.status_code == 422

    def test_parse_meal_returns_503_on_parser_failure(self, auth_headers):
        with patch("services.nutrition_parser.parse_meal_items") as mock_parse:
            mock_parse.side_effect = RuntimeError("boom")
            resp = client.post(
                "/v1/nutrition/parse-meal",
                json={"text": "anything"},
                headers=auth_headers,
            )
            assert resp.status_code == 503

    def test_parse_meal_returns_empty_list_when_nothing_recognized(
        self, test_athlete, auth_headers
    ):
        with patch("services.nutrition_parser.parse_meal_items") as mock_parse:
            mock_parse.return_value = []
            resp = client.post(
                "/v1/nutrition/parse-meal",
                json={"text": "asdf qwer"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert resp.json() == {"items": []}


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

