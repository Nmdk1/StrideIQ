"""
Photo-based nutrition parser.

Kimi K2.5 identifies food items from a photo, USDA provides verified macros.
Fallback to GPT-5.4 Mini if Kimi fails.
"""
from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.orm import Session

from services.usda_food_lookup import FoodMatch, lookup_food

logger = logging.getLogger(__name__)

_VISION_PROMPT = """Analyze this food photo. For each food item visible:
1. Identify the food item specifically
2. Estimate its dimensions/volume relative to the plate/container
3. Estimate weight in grams based on the estimated volume
4. Provide a standardized search name for USDA FoodData Central lookup

Return ONLY a JSON object with this exact structure:
{
  "items": [
    {"food": "grilled chicken breast", "grams": 180, "usda_search": "chicken breast meat cooked grilled"},
    {"food": "brown rice", "grams": 150, "usda_search": "rice brown cooked"}
  ]
}

Rules:
- Include every distinct food item visible
- Estimate weight in grams (not ounces)
- usda_search should use generic USDA terminology (avoid brand names)
- Return valid JSON only, no markdown fences"""


@dataclass
class ParsedFoodItem:
    food: str
    grams: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    macro_source: str
    fdc_id: Optional[int] = None


@dataclass
class PhotoParseResult:
    items: List[ParsedFoodItem] = field(default_factory=list)
    total_calories: float = 0
    total_protein_g: float = 0
    total_carbs_g: float = 0
    total_fat_g: float = 0
    total_fiber_g: float = 0


def parse_food_photo(image_bytes: bytes, db: Session) -> PhotoParseResult:
    """Parse a food photo into structured nutrition data."""
    t0 = time.monotonic()
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    raw_items = _call_vision_model(b64_image)
    if not raw_items:
        logger.warning("Vision model returned no items")
        return PhotoParseResult()

    result = PhotoParseResult()
    for item in raw_items:
        food_name = item.get("food", "unknown")
        grams = float(item.get("grams", 100))
        usda_search = item.get("usda_search", food_name)

        match = lookup_food(usda_search, db)
        if match:
            parsed = _compute_macros_from_match(food_name, grams, match)
        else:
            parsed = ParsedFoodItem(
                food=food_name, grams=grams,
                calories=0, protein_g=0, carbs_g=0, fat_g=0, fiber_g=0,
                macro_source="llm_estimated",
            )

        result.items.append(parsed)
        result.total_calories += parsed.calories
        result.total_protein_g += parsed.protein_g
        result.total_carbs_g += parsed.carbs_g
        result.total_fat_g += parsed.fat_g
        result.total_fiber_g += parsed.fiber_g

    latency_ms = (time.monotonic() - t0) * 1000
    logger.info("photo_parse_latency_ms=%.0f items=%d", latency_ms, len(result.items))
    return result


def _compute_macros_from_match(food_name: str, grams: float, match: FoodMatch) -> ParsedFoodItem:
    factor = grams / 100.0
    source = "usda_local" if match.source in ("sr_legacy", "foundation", "usda_local") else "usda_api"
    return ParsedFoodItem(
        food=food_name,
        grams=grams,
        calories=round(match.calories_per_100g * factor, 1),
        protein_g=round(match.protein_per_100g * factor, 1),
        carbs_g=round(match.carbs_per_100g * factor, 1),
        fat_g=round(match.fat_per_100g * factor, 1),
        fiber_g=round(match.fiber_per_100g * factor, 1),
        macro_source=source,
        fdc_id=match.fdc_id,
    )


def _call_vision_model(b64_image: str) -> list:
    """Call Kimi K2.5, fallback to GPT-5.4 Mini."""
    items = _call_kimi_vision(b64_image)
    if items is not None:
        return items

    logger.warning("Kimi vision failed, falling back to GPT-5.4 Mini")
    items = _call_openai_vision(b64_image)
    if items is not None:
        return items

    return []


def _build_messages(b64_image: str) -> list:
    return [{
        "role": "user",
        "content": [
            {"type": "text", "text": _VISION_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
        ],
    }]


def _parse_vision_response(text: str) -> Optional[list]:
    if not text:
        return None
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()

    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        start = clean.find("{")
        end = clean.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(clean[start:end + 1])
        except json.JSONDecodeError:
            return None

    if isinstance(data, dict):
        return data.get("items", [])
    if isinstance(data, list):
        return data
    return None


def _call_kimi_vision(b64_image: str) -> Optional[list]:
    try:
        from core.config import settings
        from openai import OpenAI

        api_key = settings.KIMI_API_KEY
        if not api_key:
            return None

        client = OpenAI(
            api_key=api_key,
            base_url=settings.KIMI_BASE_URL,
            timeout=30,
        )
        response = client.chat.completions.create(
            model="kimi-k2.6",
            messages=_build_messages(b64_image),
            max_tokens=1000,
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "disabled"}},
        )
        text = response.choices[0].message.content if response.choices else ""
        return _parse_vision_response(text)
    except Exception:
        logger.warning("Kimi vision call failed", exc_info=True)
        return None


def _call_openai_vision(b64_image: str) -> Optional[list]:
    try:
        import os
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        client = OpenAI(api_key=api_key, timeout=30)
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=_build_messages(b64_image),
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content if response.choices else ""
        return _parse_vision_response(text)
    except Exception:
        logger.warning("OpenAI vision fallback failed", exc_info=True)
        return None
