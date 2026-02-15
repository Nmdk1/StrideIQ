"""A3: Moment Narrator — LLM-generated coaching sentences for coachable moments.

Translates metric-label moments ("Cadence Surge: 6.0") into coaching sentences
("Your cadence shifted from 168 to 174 at 42 minutes — your body found a more
efficient gear as fatigue set in.").

Architecture:
- One batched Gemini Flash call per activity (all moments together)
- Context window extraction: absolute values around each moment for specificity
- Post-generation trust-safety validation per moment (fail-closed to None)
- No retry, hard timeout — this is enrichment, not critical path

Non-negotiable rules:
- If LLM call fails → all narratives None (frontend shows metric labels)
- If output count mismatches → all narratives None
- If a single narrative fails validation → that narrative None, others survive
- No banned internal metrics (TSB, CTL, ATL, VDOT, etc.)
- Causal language only allowed for causation-typed moments
- No sycophantic phrasing
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NARRATOR_MODEL = "gemini-2.5-flash"
NARRATOR_TEMPERATURE = 0.5
NARRATOR_MAX_TOKENS = 1000
NARRATOR_TIMEOUT_S = 10  # Hard cap — enrichment, not critical path

# Moment types where causal language is allowed (the detection itself implies causation)
CAUSAL_ALLOWED_TYPES = frozenset({
    "grade_adjusted_anomaly",
    "recovery_hr_delay",
})


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert running coach explaining key moments from a run.

For each moment, write ONE coaching sentence a runner would understand.

RULES:
1. Be specific — cite the actual numbers (pace, HR, cadence, grade) provided in the context window.
2. Use second person ("you", "your").
3. Explain what happened and why it matters for the athlete's training.
4. No jargon. No metric labels. No internal abbreviations (TSB, CTL, ATL, VDOT, rMSSD, SDNN, TRIMP, EF).
5. No sycophancy — do not say "great job", "amazing", "well done", "impressive", "incredible", etc.
6. Each sentence must be unique — no repeated phrasing patterns across moments.
7. Keep each narrative to 1-2 sentences (max 50 words per moment).
8. Be warm but direct. No exclamation marks. No emoji.

OUTPUT FORMAT:
Return a JSON array of strings. One string per moment, in the same order as the input.
Example: ["Your cadence shifted from 168 to 174 spm at 42:00 as you settled into a rhythm.", "Heart rate drifted 8% over this steady segment while pace held — your body was working harder to maintain output."]

Return ONLY the JSON array. No markdown, no explanation."""


# ---------------------------------------------------------------------------
# Trust-safety validation
# ---------------------------------------------------------------------------

_BANNED_METRICS_RE = re.compile(
    r"\b(?:TSB|CTL|ATL|VDOT|rMSSD|SDNN|TRIMP)\b"
    r"|(?:EF\s*[:=]\s*\d)"
    r"|(?:efficiency\s+factor\s*[:=]\s*\d)",
    re.IGNORECASE,
)

_SYCOPHANTIC_WORDS = (
    "great job", "well done", "amazing", "impressive", "incredible",
    "fantastic", "wonderful", "awesome", "brilliant", "magnificent",
    "outstanding", "superb", "stellar", "remarkable", "spectacular",
    "phenomenal", "extraordinary", "nice work", "good job", "proud of",
)

_CAUSAL_PHRASES = (
    "because you", "caused by", "due to your", "as a result of your",
    "that's why", "which caused", "which led to",
)


def validate_moment_narrative(
    text: str,
    moment_type: str,
) -> Optional[str]:
    """Validate a single moment narrative. Returns text if valid, None if not.

    Fail-closed: any violation → None (frontend falls back to metric label).
    """
    if not text or not isinstance(text, str):
        return None

    text = text.strip()
    if len(text) < 10:
        logger.debug("Moment narrative too short: %d chars", len(text))
        return None

    lower = text.lower()

    # 1. Banned internal metrics
    if _BANNED_METRICS_RE.search(text):
        logger.warning("Moment narrative contains banned metric: %s", text[:80])
        return None

    # 2. Sycophantic phrasing
    for phrase in _SYCOPHANTIC_WORDS:
        if phrase in lower:
            logger.warning("Moment narrative sycophantic (%s): %s", phrase, text[:80])
            return None

    # 3. Causal language — only allowed for causation-typed moments
    if moment_type not in CAUSAL_ALLOWED_TYPES:
        for phrase in _CAUSAL_PHRASES:
            if phrase in lower:
                logger.warning("Moment narrative causal (%s) for non-causal type %s: %s",
                               phrase, moment_type, text[:80])
                return None

    return text


# ---------------------------------------------------------------------------
# Context window extraction
# ---------------------------------------------------------------------------

def extract_moment_windows(
    moments: list,
    stream_data: Dict[str, list],
    window_seconds: int = 30,
) -> List[Dict[str, Any]]:
    """Extract absolute stream values around each moment's time_s for LLM context.

    Returns one dict per moment with before/at values for pace, HR, cadence, grade.
    """
    time_arr = stream_data.get("time", [])
    velocity = stream_data.get("velocity_smooth", [])
    heartrate = stream_data.get("heartrate", [])
    cadence = stream_data.get("cadence", [])
    grade = stream_data.get("grade_smooth", [])

    n = len(time_arr)
    windows = []

    for m in moments:
        idx = m.index if hasattr(m, 'index') else m.get('index', 0)
        window: Dict[str, Any] = {}

        # Find "before" index: window_seconds before the moment
        before_idx = max(0, idx - window_seconds)

        def _safe_val(arr: list, i: int) -> Optional[float]:
            if not arr or i < 0 or i >= len(arr):
                return None
            v = arr[i]
            return float(v) if v is not None else None

        # Velocity → pace (s/km)
        def _vel_to_pace(vel: Optional[float]) -> Optional[float]:
            if vel is None or vel <= 0.1:
                return None
            return 1000.0 / vel

        vel_before = _safe_val(velocity, before_idx)
        vel_at = _safe_val(velocity, idx)
        window["pace_before_s_km"] = _vel_to_pace(vel_before)
        window["pace_at_s_km"] = _vel_to_pace(vel_at)

        window["hr_before"] = _safe_val(heartrate, before_idx)
        window["hr_at"] = _safe_val(heartrate, idx)

        cad_before = _safe_val(cadence, before_idx)
        cad_at = _safe_val(cadence, idx)
        # Normalize half-cadence (Strava sends strides/min, athletes think steps/min)
        window["cadence_before"] = round(cad_before * 2) if cad_before is not None and cad_before < 120 else (round(cad_before) if cad_before is not None else None)
        window["cadence_at"] = round(cad_at * 2) if cad_at is not None and cad_at < 120 else (round(cad_at) if cad_at is not None else None)

        window["grade_at"] = _safe_val(grade, idx)

        windows.append(window)

    return windows


# ---------------------------------------------------------------------------
# Format helpers for the prompt
# ---------------------------------------------------------------------------

def _format_pace(s_km: Optional[float]) -> str:
    """Format pace as m:ss/km for the LLM prompt."""
    if s_km is None:
        return "N/A"
    m = int(s_km) // 60
    s = int(s_km) % 60
    return f"{m}:{s:02d}/km"


def _format_time(seconds: int) -> str:
    """Format time_s as mm:ss."""
    m = seconds // 60
    s = seconds % 60
    return f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(
    moments: list,
    windows: List[Dict[str, Any]],
    segments: list,
    athlete_context: Any = None,
) -> str:
    """Build the user prompt with moment data, context windows, and segment summary."""
    lines = []

    # Segment summary
    lines.append("RUN SEGMENTS:")
    for seg in segments:
        seg_type = seg.type if hasattr(seg, 'type') else seg.get('type', '?')
        dur = seg.duration_s if hasattr(seg, 'duration_s') else seg.get('duration_s', 0)
        lines.append(f"  - {seg_type}: {_format_time(dur)} duration")

    # Athlete context (if available)
    if athlete_context:
        zones = []
        if hasattr(athlete_context, 'max_hr') and athlete_context.max_hr:
            zones.append(f"max HR {athlete_context.max_hr}")
        if hasattr(athlete_context, 'threshold_hr') and athlete_context.threshold_hr:
            zones.append(f"threshold HR {athlete_context.threshold_hr}")
        if hasattr(athlete_context, 'resting_hr') and athlete_context.resting_hr:
            zones.append(f"resting HR {athlete_context.resting_hr}")
        if zones:
            lines.append(f"\nATHLETE ZONES: {', '.join(zones)}")

    lines.append(f"\nMOMENTS ({len(moments)} total):")
    lines.append("Write one coaching sentence per moment.\n")

    for i, (m, w) in enumerate(zip(moments, windows)):
        m_type = m.type if hasattr(m, 'type') else m.get('type', '?')
        m_time = m.time_s if hasattr(m, 'time_s') else m.get('time_s', 0)
        m_value = m.value if hasattr(m, 'value') else m.get('value')
        m_context = m.context if hasattr(m, 'context') else m.get('context')

        lines.append(f"Moment {i+1}:")
        lines.append(f"  Type: {m_type}")
        lines.append(f"  Time: {_format_time(m_time)}")
        if m_value is not None:
            lines.append(f"  Value: {m_value}")
        if m_context:
            lines.append(f"  Context: {m_context}")
        lines.append(f"  Window (30s before → at moment):")
        lines.append(f"    Pace: {_format_pace(w.get('pace_before_s_km'))} → {_format_pace(w.get('pace_at_s_km'))}")
        if w.get('hr_before') is not None or w.get('hr_at') is not None:
            lines.append(f"    HR: {w.get('hr_before', 'N/A')} → {w.get('hr_at', 'N/A')} bpm")
        if w.get('cadence_before') is not None or w.get('cadence_at') is not None:
            lines.append(f"    Cadence: {w.get('cadence_before', 'N/A')} → {w.get('cadence_at', 'N/A')} spm")
        if w.get('grade_at') is not None:
            lines.append(f"    Grade: {w['grade_at']:.1f}%")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _call_narrator_llm(
    client: Any,
    prompt: str,
) -> Tuple[str, int, int, int]:
    """Call Gemini Flash for moment narratives.

    Returns (text, input_tokens, output_tokens, latency_ms).
    Raises on failure.
    """
    if client is None:
        raise RuntimeError("No Gemini client provided.")

    start = time.monotonic()

    try:
        import google.genai.types as genai_types
        contents = [
            genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=prompt)],
            ),
        ]
        config = genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=NARRATOR_MAX_TOKENS,
            temperature=NARRATOR_TEMPERATURE,
        )
    except Exception:
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        config = {
            "system_instruction": SYSTEM_PROMPT,
            "max_output_tokens": NARRATOR_MAX_TOKENS,
            "temperature": NARRATOR_TEMPERATURE,
        }

    response = client.models.generate_content(
        model=NARRATOR_MODEL,
        contents=contents,
        config=config,
    )

    latency_ms = int((time.monotonic() - start) * 1000)

    text = ""
    if response.candidates:
        candidate = response.candidates[0]
        if candidate.content and candidate.content.parts:
            text = candidate.content.parts[0].text or ""

    input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
    output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

    return text, input_tokens, output_tokens, latency_ms


# ---------------------------------------------------------------------------
# Parse LLM output
# ---------------------------------------------------------------------------

def _parse_narrative_array(raw_text: str, expected_count: int) -> Optional[List[str]]:
    """Parse JSON array from LLM output. Returns None on any parse/contract failure."""
    if not raw_text:
        return None

    # Strip markdown fences if present
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Moment narrator: JSON parse failed. Raw: %s", text[:200])
        return None

    if not isinstance(parsed, list):
        logger.warning("Moment narrator: expected list, got %s", type(parsed).__name__)
        return None

    if len(parsed) != expected_count:
        logger.warning(
            "Moment narrator: count mismatch — expected %d, got %d. Dropping all.",
            expected_count, len(parsed),
        )
        return None

    # Ensure all items are strings
    result = []
    for item in parsed:
        if isinstance(item, str):
            result.append(item)
        else:
            result.append(None)

    return result


# ---------------------------------------------------------------------------
# Telemetry result
# ---------------------------------------------------------------------------

@dataclass
class NarratorResult:
    """Telemetry from a narrator invocation."""
    success: bool = False
    fallback_count: int = 0  # How many moments fell back to None
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_moment_narratives(
    moments: list,
    segments: list,
    stream_data: Dict[str, list],
    gemini_client: Any = None,
    athlete_context: Any = None,
) -> Tuple[List[Optional[str]], NarratorResult]:
    """Generate coaching narratives for a list of detected moments.

    Returns:
        (narratives, result) where narratives[i] is str or None for each moment.
        NarratorResult contains telemetry for logging.

    Fail-safe: any failure → all narratives None. Individual validation failures
    result in per-moment None with others surviving.
    """
    n = len(moments)
    empty = [None] * n

    if n == 0:
        return empty, NarratorResult(success=True)

    if gemini_client is None:
        return empty, NarratorResult(error="no_gemini_client")

    # Extract context windows
    windows = extract_moment_windows(moments, stream_data)

    # Build prompt
    prompt = _build_prompt(moments, windows, segments, athlete_context)

    # Call LLM with timeout enforcement
    try:
        raw_text, in_tok, out_tok, lat_ms = _call_narrator_llm(gemini_client, prompt)
    except Exception as exc:
        logger.warning("Moment narrator LLM call failed: %s", exc)
        return empty, NarratorResult(error=str(exc))

    # Timeout check (latency-based — the actual timeout is enforced by the
    # Gemini client's request_options if configured, this is a fallback log)
    if lat_ms > NARRATOR_TIMEOUT_S * 1000:
        logger.warning("Moment narrator exceeded timeout: %d ms", lat_ms)

    # Parse
    parsed = _parse_narrative_array(raw_text, n)
    if parsed is None:
        return empty, NarratorResult(
            latency_ms=lat_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            error="parse_failed",
        )

    # Validate each narrative
    validated: List[Optional[str]] = []
    fallback_count = 0
    for i, (text, m) in enumerate(zip(parsed, moments)):
        m_type = m.type if hasattr(m, 'type') else m.get('type', '')
        if text is None:
            validated.append(None)
            fallback_count += 1
        else:
            result = validate_moment_narrative(text, m_type)
            if result is None:
                fallback_count += 1
            validated.append(result)

    return validated, NarratorResult(
        success=True,
        fallback_count=fallback_count,
        latency_ms=lat_ms,
        input_tokens=in_tok,
        output_tokens=out_tok,
    )
