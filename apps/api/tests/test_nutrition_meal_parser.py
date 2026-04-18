"""
Service tests for parse_meal_items.

Covers the new meal-parser path that powers the meal builder's
"paste your meal" textarea: free text in, list of structured items
out. Mocks the LLM call directly so tests are deterministic and
don't require any API keys.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from services import nutrition_parser


class _FakeUsdaMatch:
    """Stand-in for services.usda_food_lookup.lookup_food return value."""

    def __init__(
        self,
        *,
        calories_per_100g: float = 100.0,
        protein_per_100g: float = 5.0,
        carbs_per_100g: float = 15.0,
        fat_per_100g: float = 2.0,
        fiber_per_100g: float = 1.0,
        source: str = "usda_local",
    ) -> None:
        self.calories_per_100g = calories_per_100g
        self.protein_per_100g = protein_per_100g
        self.carbs_per_100g = carbs_per_100g
        self.fat_per_100g = fat_per_100g
        self.fiber_per_100g = fiber_per_100g
        self.source = source


class TestParseMealItemsHappyPath:
    def test_returns_list_of_items_with_macros(self):
        with patch.object(nutrition_parser, "_call_llm_meal") as mock_llm:
            mock_llm.return_value = {
                "items": [
                    {
                        "food": "2 eggs scrambled",
                        "calories": 180,
                        "protein_g": 12,
                        "carbs_g": 1,
                        "fat_g": 14,
                        "fiber_g": 0,
                    },
                    {
                        "food": "1 slice whole wheat toast",
                        "calories": 80,
                        "protein_g": 4,
                        "carbs_g": 14,
                        "fat_g": 1,
                        "fiber_g": 2,
                    },
                    {
                        "food": "1 tbsp peanut butter",
                        "calories": 95,
                        "protein_g": 4,
                        "carbs_g": 3,
                        "fat_g": 8,
                        "fiber_g": 1,
                    },
                ]
            }
            items = nutrition_parser.parse_meal_items(
                "2 eggs scrambled, 1 slice whole wheat toast, 1 tbsp peanut butter"
            )

        assert isinstance(items, list)
        assert len(items) == 3
        assert items[0]["food"] == "2 eggs scrambled"
        assert items[0]["calories"] == 180.0
        assert items[1]["food"] == "1 slice whole wheat toast"
        assert items[2]["food"] == "1 tbsp peanut butter"
        for item in items:
            assert item["macro_source"] == "llm_estimated"

    def test_single_item_still_returns_list(self):
        with patch.object(nutrition_parser, "_call_llm_meal") as mock_llm:
            mock_llm.return_value = {
                "items": [
                    {
                        "food": "1 banana",
                        "calories": 105,
                        "protein_g": 1,
                        "carbs_g": 27,
                        "fat_g": 0,
                        "fiber_g": 3,
                    }
                ]
            }
            items = nutrition_parser.parse_meal_items("1 banana")

        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0]["food"] == "1 banana"


class TestParseMealItemsValidation:
    def test_empty_text_raises_value_error(self):
        with pytest.raises(ValueError):
            nutrition_parser.parse_meal_items("")

    def test_whitespace_only_text_raises_value_error(self):
        with pytest.raises(ValueError):
            nutrition_parser.parse_meal_items("   \n   ")

    def test_llm_failure_raises_runtime_error(self):
        with patch.object(nutrition_parser, "_call_kimi_meal") as mock_kimi, \
             patch.object(nutrition_parser, "_call_openai_meal") as mock_openai:
            mock_kimi.return_value = None
            mock_openai.return_value = None
            with pytest.raises(RuntimeError):
                nutrition_parser.parse_meal_items("anything")

    def test_llm_returns_no_items_returns_empty_list(self):
        with patch.object(nutrition_parser, "_call_llm_meal") as mock_llm:
            mock_llm.return_value = {"items": []}
            items = nutrition_parser.parse_meal_items("nothing recognizable")
        assert items == []

    def test_llm_returns_non_list_items_returns_empty_list(self):
        # Defensive: if the model returns something weird, we don't blow up.
        with patch.object(nutrition_parser, "_call_llm_meal") as mock_llm:
            mock_llm.return_value = {"items": "not a list"}
            items = nutrition_parser.parse_meal_items("breakfast")
        assert items == []

    def test_items_with_blank_food_are_dropped(self):
        with patch.object(nutrition_parser, "_call_llm_meal") as mock_llm:
            mock_llm.return_value = {
                "items": [
                    {"food": "1 apple", "calories": 95},
                    {"food": "", "calories": 0},
                    {"food": "   ", "calories": 0},
                    {"food": "1 orange", "calories": 62},
                ]
            }
            items = nutrition_parser.parse_meal_items("apple and orange")

        assert len(items) == 2
        assert items[0]["food"] == "1 apple"
        assert items[1]["food"] == "1 orange"


class TestParseMealItemsUsdaEnrichment:
    def test_usda_fills_in_missing_macros_per_item(self):
        # LLM gave us a food string but no macros; USDA fills them in.
        with patch.object(nutrition_parser, "_call_llm_meal") as mock_llm, \
             patch("services.usda_food_lookup.lookup_food") as mock_lookup:
            mock_llm.return_value = {
                "items": [
                    {"food": "1 medium banana"},
                    {"food": "8 oz chicken breast"},
                ]
            }
            mock_lookup.side_effect = [
                _FakeUsdaMatch(
                    calories_per_100g=89,
                    protein_per_100g=1.1,
                    carbs_per_100g=23,
                    fat_per_100g=0.3,
                    fiber_per_100g=2.6,
                    source="usda_local",
                ),
                _FakeUsdaMatch(
                    calories_per_100g=165,
                    protein_per_100g=31,
                    carbs_per_100g=0,
                    fat_per_100g=3.6,
                    fiber_per_100g=0,
                    source="usda_local",
                ),
            ]

            items = nutrition_parser.parse_meal_items(
                "1 medium banana, 8 oz chicken breast",
                db=object(),
            )

        assert len(items) == 2
        assert items[0]["calories"] == 89.0
        assert items[0]["macro_source"] == "usda_local"
        assert items[1]["calories"] == 165.0
        assert items[1]["protein_g"] == 31.0
        assert items[1]["macro_source"] == "usda_local"

    def test_usda_does_not_overwrite_llm_macros(self):
        with patch.object(nutrition_parser, "_call_llm_meal") as mock_llm, \
             patch("services.usda_food_lookup.lookup_food") as mock_lookup:
            mock_llm.return_value = {
                "items": [
                    {
                        "food": "2 eggs",
                        "calories": 180,
                        "protein_g": 12,
                        "carbs_g": 1,
                        "fat_g": 14,
                        "fiber_g": 0,
                    },
                ]
            }
            mock_lookup.return_value = _FakeUsdaMatch(
                calories_per_100g=999,
                protein_per_100g=999,
                carbs_per_100g=999,
                fat_per_100g=999,
                fiber_per_100g=999,
                source="usda_local",
            )
            items = nutrition_parser.parse_meal_items("2 eggs", db=object())

        assert items[0]["calories"] == 180.0
        assert items[0]["protein_g"] == 12.0
        # The LLM already filled these in -- USDA must not stomp them.
        assert items[0]["macro_source"] == "llm_estimated"

    def test_usda_failure_does_not_break_parse(self):
        with patch.object(nutrition_parser, "_call_llm_meal") as mock_llm, \
             patch("services.usda_food_lookup.lookup_food") as mock_lookup:
            mock_llm.return_value = {
                "items": [{"food": "1 banana", "calories": 105}]
            }
            mock_lookup.side_effect = RuntimeError("usda offline")

            items = nutrition_parser.parse_meal_items("1 banana", db=object())

        assert len(items) == 1
        assert items[0]["calories"] == 105.0
        assert items[0]["macro_source"] == "llm_estimated"
