"""
Centralized LLM client abstraction.

All non-tool-call LLM completions go through call_llm().
Provider routing is based on model name prefix:
  - "claude-*"  → Anthropic SDK
  - "kimi-*"    → OpenAI-compatible SDK (Moonshot base URL)
  - "gemini-*"  → Google GenAI SDK

Tool-call loops (ai_coach.py query_opus / query_gemini) remain on their
native SDKs until offline tool-parity validation passes — they do NOT
route through this module.

Fallback chain for Kimi-selected calls:
  kimi-k2.5 → claude-sonnet-4-6 → gemini-2.5-flash

Usage:
    from core.llm_client import call_llm, resolve_briefing_model

    model = resolve_briefing_model(athlete_id=str(current_user.id))
    result = call_llm(
        model=model,
        system="You are ...",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.3,
        response_mode="json",
        timeout_s=45,
    )
    text = result["text"]
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import List, Literal, Optional, TypedDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Normalized response type
# ---------------------------------------------------------------------------

class LLMResponse(TypedDict):
    text: str
    model: str
    provider: str          # "anthropic" | "kimi" | "gemini"
    input_tokens: int
    output_tokens: int
    latency_ms: float
    finish_reason: Optional[str]


def _is_kimi_reasoning_model(model: str) -> bool:
    """Kimi reasoning models require temperature omission."""
    m = (model or "").strip().lower()
    return m == "kimi-k2.5" or m.startswith("kimi-k2.5-")


# ---------------------------------------------------------------------------
# Internal helpers — lazy imports to avoid hard deps at module load
# ---------------------------------------------------------------------------

def _get_settings():
    from core.config import settings
    return settings


def _call_anthropic(
    model: str,
    system: str,
    messages: List[dict],
    max_tokens: int,
    temperature: float,
    response_mode: Literal["text", "json"],
    timeout_s: int,
) -> LLMResponse:
    """Anthropic Messages API adapter (text + JSON modes)."""
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package not installed") from exc

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = Anthropic(api_key=api_key, timeout=timeout_s)

    t0 = time.monotonic()
    response = client.messages.create(
        model=model,
        system=system,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    latency_ms = (time.monotonic() - t0) * 1000

    raw_text = response.content[0].text if response.content else ""
    return LLMResponse(
        text=raw_text,
        model=model,
        provider="anthropic",
        input_tokens=response.usage.input_tokens if response.usage else 0,
        output_tokens=response.usage.output_tokens if response.usage else 0,
        latency_ms=latency_ms,
        finish_reason=response.stop_reason,
    )


def _call_kimi(
    model: str,
    system: str,
    messages: List[dict],
    max_tokens: int,
    temperature: float,
    response_mode: Literal["text", "json"],
    timeout_s: int,
) -> LLMResponse:
    """
    Kimi (Moonshot) via OpenAI-compatible SDK.

    Supports both kimi-k2-turbo-preview and kimi-k2.5. For k2.5 in JSON
    mode, thinking is disabled so output goes to `content` normally.
    K2.5 uses fixed temperature (1.0 thinking, 0.6 non-thinking).
    """
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package not installed") from exc

    settings = _get_settings()
    api_key = settings.KIMI_API_KEY or os.getenv("KIMI_API_KEY")
    base_url = settings.KIMI_BASE_URL

    if not api_key:
        raise RuntimeError("KIMI_API_KEY not set")

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s)

    oai_messages = [{"role": "system", "content": system}] + list(messages)

    extra_kwargs: dict = {}
    extra_body: dict = {}
    is_reasoning = _is_kimi_reasoning_model(model)
    if response_mode == "json":
        extra_kwargs["response_format"] = {"type": "json_object"}
        if is_reasoning:
            extra_body["thinking"] = {"type": "disabled"}
    if not is_reasoning:
        extra_kwargs["temperature"] = temperature

    t0 = time.monotonic()
    response = client.chat.completions.create(
        model=model,
        messages=oai_messages,
        max_tokens=max_tokens,
        extra_body=extra_body if extra_body else None,
        **extra_kwargs,
    )
    latency_ms = (time.monotonic() - t0) * 1000

    choice = response.choices[0] if response.choices else None
    raw_text = choice.message.content if choice and choice.message else ""
    usage = response.usage

    return LLMResponse(
        text=raw_text or "",
        model=model,
        provider="kimi",
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        latency_ms=latency_ms,
        finish_reason=choice.finish_reason if choice else None,
    )


def _call_gemini(
    model: str,
    system: str,
    messages: List[dict],
    max_tokens: int,
    temperature: float,
    response_mode: Literal["text", "json"],
    timeout_s: int,
) -> LLMResponse:
    """Google GenAI adapter (text + JSON modes via response_mime_type)."""
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError as exc:
        raise RuntimeError("google-genai package not installed") from exc

    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_AI_API_KEY not set")

    client = genai.Client(
        api_key=api_key,
        http_options={"timeout": timeout_s * 1000},
    )

    # Build contents from messages (flatten to single prompt string for
    # simple text/JSON completions — not tool-call loops)
    system_part = f"{system}\n\n" if system else ""
    user_content = "\n".join(
        m.get("content", "") for m in messages if m.get("role") == "user"
    )
    contents = system_part + user_content

    config_kwargs: dict = {
        "max_output_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_mode == "json":
        config_kwargs["response_mime_type"] = "application/json"

    t0 = time.monotonic()
    resp = client.models.generate_content(
        model=model,
        contents=contents,
        config=genai_types.GenerateContentConfig(**config_kwargs),
    )
    latency_ms = (time.monotonic() - t0) * 1000

    raw_text = resp.text if resp.text else ""
    # Token counts — available via usage_metadata if present
    usage = getattr(resp, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", 0) or 0
    output_tokens = getattr(usage, "candidates_token_count", 0) or 0

    return LLMResponse(
        text=raw_text,
        model=model,
        provider="gemini",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        finish_reason=None,
    )


# ---------------------------------------------------------------------------
# Fallback chain
# ---------------------------------------------------------------------------

_FALLBACK_CHAIN = {
    "kimi": ("anthropic", "gemini"),
    "anthropic": ("gemini",),
    "gemini": (),
}

_GEMINI_FALLBACK_MODEL = "gemini-2.5-flash"
_ANTHROPIC_FALLBACK_MODEL = "claude-sonnet-4-6"

def _provider_for_model(model: str) -> str:
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("kimi"):
        return "kimi"
    if model.startswith("gemini"):
        return "gemini"
    raise ValueError(f"Unknown model family for model '{model}'. "
                     "Expected prefix: claude-, kimi-, or gemini-")


_ADAPTER_MAP = {
    "anthropic": _call_anthropic,
    "kimi": _call_kimi,
    "gemini": _call_gemini,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call_llm(
    *,
    model: str,
    system: str,
    messages: List[dict],
    max_tokens: int,
    temperature: float,
    response_mode: Literal["text", "json"] = "text",
    timeout_s: int = 45,
) -> LLMResponse:
    """
    Route an LLM completion to the correct provider with automatic fallback.

    For Kimi-selected calls the fallback chain is:
        kimi-k2-turbo-preview → claude-sonnet-4-6 → gemini-2.5-flash

    For Anthropic-selected calls:
        claude-sonnet-4-6 → gemini-2.5-flash

    Never raises to the caller if any fallback succeeds. Raises RuntimeError
    only if all providers in the chain fail.
    """
    primary_provider = _provider_for_model(model)
    chain = [primary_provider] + list(_FALLBACK_CHAIN.get(primary_provider, ()))

    last_exc: Optional[Exception] = None
    for i, provider in enumerate(chain):
        # Use the requested model for the first attempt, canonical fallback model otherwise
        if i == 0:
            attempt_model = model
        elif provider == "anthropic":
            attempt_model = _ANTHROPIC_FALLBACK_MODEL
        elif provider == "gemini":
            attempt_model = _GEMINI_FALLBACK_MODEL
        else:
            attempt_model = model

        try:
            result = _ADAPTER_MAP[provider](
                model=attempt_model,
                system=system,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                response_mode=response_mode,
                timeout_s=timeout_s,
            )
            if i > 0:
                logger.warning(
                    "LLM fallback: primary provider %s failed, used %s (%s)",
                    chain[0], provider, attempt_model,
                )
            logger.info(
                "LLM call: model=%s provider=%s in=%.0f out=%.0f lat=%.0fms",
                attempt_model, provider,
                result["input_tokens"], result["output_tokens"], result["latency_ms"],
            )
            return result
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "LLM provider %s failed (attempt %d/%d): %s: %s",
                provider, i + 1, len(chain), type(exc).__name__, exc,
            )

    raise RuntimeError(
        f"All LLM providers failed for model '{model}'. Last error: {last_exc}"
    ) from last_exc


def call_llm_with_json_parse(
    *,
    model: str,
    system: str,
    messages: List[dict],
    max_tokens: int,
    temperature: float,
    timeout_s: int = 45,
) -> Optional[dict]:
    """
    Call LLM in JSON mode and parse the result.

    Returns the parsed dict on success, or None if:
    - All providers fail
    - JSON parse fails after stripping markdown fences

    Never raises — safe to use in briefing paths where silence > crash.
    """
    try:
        result = call_llm(
            model=model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_mode="json",
            timeout_s=timeout_s,
        )
    except RuntimeError as exc:
        logger.error("call_llm_with_json_parse: all providers failed: %s", exc)
        return None

    text = (result["text"] or "").strip()
    # Strip markdown fences that some models emit despite being told not to
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning(
            "call_llm_with_json_parse: JSON parse failed for model %s: %s",
            result["model"], exc,
        )
        return None


# ---------------------------------------------------------------------------
# Canary routing helpers
# ---------------------------------------------------------------------------

def _canary_athlete_ids() -> set:
    """Return the set of athlete IDs routed to the Kimi canary."""
    settings = _get_settings()
    raw = settings.KIMI_CANARY_ATHLETE_IDS or ""
    return {aid.strip() for aid in raw.split(",") if aid.strip()}


def _canary_enabled() -> bool:
    settings = _get_settings()
    if not settings.KIMI_CANARY_ENABLED:
        return False
    if not (settings.KIMI_API_KEY or os.getenv("KIMI_API_KEY")):
        logger.critical(
            "KIMI_CANARY_ENABLED=true but KIMI_API_KEY is not set — "
            "canary routing is DISABLED to prevent silent failures."
        )
        return False
    return True


def resolve_briefing_model(athlete_id: Optional[str] = None) -> str:
    """
    Return the model to use for briefing generation.

    If KIMI_CANARY_ENABLED and the athlete is in KIMI_CANARY_ATHLETE_IDS,
    returns KIMI_CANARY_MODEL (default: kimi-k2.5).
    Otherwise returns BRIEFING_PRIMARY_MODEL.

    K2.5 is used with thinking disabled (via _call_kimi adapter) so it
    outputs JSON to `content` like a standard model.
    """
    if athlete_id and _canary_enabled():
        if athlete_id in _canary_athlete_ids():
            settings = _get_settings()
            model = settings.KIMI_CANARY_MODEL
            logger.info("Canary: routing briefing for athlete %s to %s", athlete_id, model)
            return model
    settings = _get_settings()
    return settings.BRIEFING_PRIMARY_MODEL


def resolve_knowledge_model() -> str:
    """Return the model for knowledge extraction."""
    settings = _get_settings()
    return settings.KNOWLEDGE_PRIMARY_MODEL


def is_canary_athlete(athlete_id: str) -> bool:
    """Return True if this athlete is in the Kimi canary cohort."""
    return _canary_enabled() and athlete_id in _canary_athlete_ids()
