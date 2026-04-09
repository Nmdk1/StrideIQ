"""
Nutrition Natural-Language Parsing.

Uses Kimi K2.5 to identify foods from text, then looks up USDA for verified macros.
Falls back to OpenAI if Kimi is unavailable.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        v = value.strip()
        if v == "":
            return None
        try:
            return float(v)
        except Exception:
            return None
    return None


def _extract_json_object(text: str) -> Dict[str, Any]:
    if not text:
        raise ValueError("Empty model response")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")

    candidate = text[start : end + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON is not an object")
    return parsed


_NL_SYSTEM = (
    "You are a nutrition logging helper. "
    "Given a short text describing food/drink, estimate macros. "
    "Return ONLY valid JSON. No markdown, no commentary."
)

_NL_USER_TEMPLATE = """Text: {text}

Return a JSON object with these keys:
{{
  "calories": number|null,
  "protein_g": number|null,
  "carbs_g": number|null,
  "fat_g": number|null,
  "fiber_g": number|null,
  "notes": string
}}

Rules:
- Prefer conservative, reasonable estimates if uncertain.
- If the text is too vague, set numbers to null but still return notes.
- notes should be a short canonicalized list of detected items."""


def parse_nutrition_text(text: str, db=None) -> Dict[str, Optional[float] | str]:
    """
    Parse nutrition free text using Kimi K2.5 (primary) or OpenAI (fallback).

    If a db session is provided and USDA foods are seeded, attempts USDA
    lookup for verified macros. Otherwise uses model-estimated values.
    """
    if not text or not text.strip():
        raise ValueError("text is required")

    data = _call_llm(text)

    calories = _coerce_float(data.get("calories"))
    protein_g = _coerce_float(data.get("protein_g"))
    carbs_g = _coerce_float(data.get("carbs_g"))
    fat_g = _coerce_float(data.get("fat_g"))
    fiber_g = _coerce_float(data.get("fiber_g"))
    notes = data.get("notes")
    if not isinstance(notes, str) or not notes.strip():
        notes = text.strip()

    macro_source = "llm_estimated"

    if db is not None and notes:
        try:
            from services.usda_food_lookup import lookup_food
            match = lookup_food(notes, db)
            if match:
                calories = calories or round(match.calories_per_100g, 1)
                protein_g = protein_g or round(match.protein_per_100g, 1)
                carbs_g = carbs_g or round(match.carbs_per_100g, 1)
                fat_g = fat_g or round(match.fat_per_100g, 1)
                fiber_g = fiber_g or round(match.fiber_per_100g, 1)
                macro_source = "usda_local" if "local" in match.source else "usda_api"
        except Exception:
            logger.debug("USDA lookup skipped", exc_info=True)

    return {
        "calories": calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "fiber_g": fiber_g,
        "notes": notes.strip(),
        "macro_source": macro_source,
    }


def _call_llm(text: str) -> dict:
    """Try Kimi K2.5 first, fall back to OpenAI."""
    result = _call_kimi(text)
    if result is not None:
        return result

    result = _call_openai(text)
    if result is not None:
        return result

    raise RuntimeError("All LLM providers failed for nutrition text parsing")


def _call_kimi(text: str) -> Optional[dict]:
    try:
        from core.config import settings
        from openai import OpenAI

        api_key = settings.KIMI_API_KEY
        if not api_key:
            return None

        client = OpenAI(api_key=api_key, base_url=settings.KIMI_BASE_URL, timeout=15)
        response = client.chat.completions.create(
            model="kimi-k2.5",
            messages=[
                {"role": "system", "content": _NL_SYSTEM},
                {"role": "user", "content": _NL_USER_TEMPLATE.format(text=text)},
            ],
            max_tokens=400,
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "disabled"}},
        )
        content = response.choices[0].message.content or ""
        return _extract_json_object(content)
    except Exception:
        logger.warning("Kimi nutrition text parse failed", exc_info=True)
        return None


def _call_openai(text: str) -> Optional[dict]:
    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        client = OpenAI(api_key=api_key, timeout=15)
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": _NL_SYSTEM},
                {"role": "user", "content": _NL_USER_TEMPLATE.format(text=text)},
            ],
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        return _extract_json_object(content)
    except Exception:
        logger.warning("OpenAI nutrition text parse failed", exc_info=True)
        return None
