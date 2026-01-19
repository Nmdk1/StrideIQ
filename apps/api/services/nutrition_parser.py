"""
Nutrition Natural-Language Parsing (Phase 1)

Converts free-form food text into approximate macros.

Design goals:
- Keep the endpoint lightweight and resilient
- Return a best-effort structured estimate (not medical-grade accuracy)
- Fail gracefully so manual entry remains the fallback
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


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
    """
    Extract first JSON object from model output.
    We keep this deliberately simple and robust.
    """
    if not text:
        raise ValueError("Empty model response")

    # Fast path: direct JSON
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Fallback: find first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")

    candidate = text[start : end + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON is not an object")
    return parsed


def parse_nutrition_text(text: str) -> Dict[str, Optional[float] | str]:
    """
    Parse nutrition free text using OpenAI.

    Returns:
      dict with keys: calories, protein_g, carbs_g, fat_g, fiber_g, notes
    """
    if not text or not text.strip():
        raise ValueError("text is required")

    if not OPENAI_AVAILABLE:
        raise RuntimeError("OpenAI client not installed")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")

    client = OpenAI(api_key=api_key)

    system = (
        "You are a nutrition logging helper. "
        "Given a short text describing food/drink, estimate macros. "
        "Return ONLY valid JSON. No markdown, no commentary."
    )

    user = f"""Text: {text}

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

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=400,
        )
        content = response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"OpenAI nutrition parse failed: {e}")
        raise RuntimeError("OpenAI request failed")

    data = _extract_json_object(content)

    calories = _coerce_float(data.get("calories"))
    protein_g = _coerce_float(data.get("protein_g"))
    carbs_g = _coerce_float(data.get("carbs_g"))
    fat_g = _coerce_float(data.get("fat_g"))
    fiber_g = _coerce_float(data.get("fiber_g"))
    notes = data.get("notes")
    if not isinstance(notes, str) or not notes.strip():
        notes = text.strip()

    return {
        "calories": calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "fiber_g": fiber_g,
        "notes": notes.strip(),
    }

