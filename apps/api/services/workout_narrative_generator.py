"""Phase 3B: Contextual workout narrative generator.

Generates a fresh, contextual narrative for today's planned workout.
Never the same twice.  Aware of plan phase, progression position,
last session performance, readiness, and what's coming next.

Non-negotiable rules:
- If insufficient context → return None (suppress, don't fabricate).
- >50% phrasing overlap with recently shown narratives → suppress/regenerate.
- No intensity encouragement after very long run / taper / pre-race shakeout.
- Global kill switch + per-narrative suppression respected.
- Premium-only exposure.
"""
from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session
from core.config import settings
from core.llm_client import call_llm

try:
    from google import genai  # module-level so tests can patch services.workout_narrative_generator.genai
except ImportError:
    genai = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NARRATIVE_MODEL = "gemini-2.5-flash"
NARRATIVE_TEMPERATURE = 0.6  # slightly higher than adaptation narration for variety
NARRATIVE_MAX_TOKENS = 250
SIMILARITY_THRESHOLD = 0.50  # suppress if >50% token overlap with recent
RECENT_NARRATIVE_WINDOW = 7  # days to look back for similarity check

# Kill switch env var — generator checks this directly so it is enforced even
# when called outside the eligibility→router path.
KILL_SWITCH_3B_ENV = "STRIDEIQ_3B_KILL_SWITCH"

# Phases / workout types where intensity encouragement is inappropriate
NO_INTENSITY_PHASES = {"taper", "recovery"}
NO_INTENSITY_AFTER = {"long", "long_run", "long_mp", "long_hmp"}


def _resolved_workout_narrative_model() -> str:
    """Resolve workout narrative model via config/env."""
    return settings.WORKOUT_NARRATIVE_MODEL or NARRATIVE_MODEL

# ---------------------------------------------------------------------------
# System prompt for Gemini
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert running coach writing a short, contextual note for today's workout.

RULES:
1. Reference specific data: recent performance, plan phase, progression position.
2. Be forward-looking: what to focus on TODAY, not a history lesson.
3. NEVER use generic coaching platitudes or template language.
4. NEVER mention internal metrics: TSB, CTL, ATL, VDOT, rMSSD, SDNN, EF, TRIMP.
5. NEVER encourage intensity when the athlete is in taper, recovery, or the day after a very long run.
6. Keep it 2-3 sentences maximum.
7. If you don't have enough context to say something genuinely useful, say nothing.
8. Use second person ("you", "your").
9. Be warm but direct. No exclamation marks. No emoji."""


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

@dataclass
class WorkoutNarrativeResult:
    narrative: Optional[str] = None
    suppressed: bool = False
    suppression_reason: Optional[str] = None
    prompt_used: Optional[str] = None
    model_used: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    # 4-criterion quality score (populated after generation, None when suppressed)
    quality_score: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Similarity guard
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Simple whitespace + punctuation tokenizer."""
    return re.findall(r"\w+", text.lower())


def _token_overlap(a: str, b: str) -> float:
    """Jaccard-like overlap between two texts, measured by token frequency."""
    tokens_a = Counter(_tokenize(a))
    tokens_b = Counter(_tokenize(b))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = sum((tokens_a & tokens_b).values())
    union = sum((tokens_a | tokens_b).values())
    return intersection / union if union else 0.0


def _is_too_similar(
    candidate: str,
    recent_narratives: List[str],
    threshold: float = SIMILARITY_THRESHOLD,
) -> bool:
    """Check if candidate is >threshold overlap with any recent narrative."""
    for prev in recent_narratives:
        if _token_overlap(candidate, prev) > threshold:
            return True
    return False


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_context(
    athlete_id: UUID,
    target_date: date,
    db: Session,
) -> Optional[Dict[str, Any]]:
    """Assemble workout + training context for the prompt.

    Returns None if there isn't enough context for a meaningful narrative.
    """
    from models import PlannedWorkout, Activity

    # Today's planned workout
    workout = (
        db.query(PlannedWorkout)
        .filter(
            PlannedWorkout.athlete_id == athlete_id,
            PlannedWorkout.scheduled_date == target_date,
        )
        .first()
    )
    if workout is None:
        return None

    # Recent activities (last 7 days)
    week_ago = target_date - timedelta(days=7)
    recent = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= week_ago,
            Activity.sport == "run",
        )
        .order_by(desc(Activity.start_time))
        .limit(5)
        .all()
    )

    # Yesterday's workout (for the no-intensity-after-long guard)
    yesterday = target_date - timedelta(days=1)
    yesterday_workout = (
        db.query(PlannedWorkout)
        .filter(
            PlannedWorkout.athlete_id == athlete_id,
            PlannedWorkout.scheduled_date == yesterday,
        )
        .first()
    )

    # Next upcoming key session (next 3 days)
    upcoming = (
        db.query(PlannedWorkout)
        .filter(
            PlannedWorkout.athlete_id == athlete_id,
            PlannedWorkout.scheduled_date > target_date,
            PlannedWorkout.scheduled_date <= target_date + timedelta(days=3),
        )
        .order_by(PlannedWorkout.scheduled_date)
        .limit(3)
        .all()
    )

    # Readiness (best-effort)
    readiness_score = None
    try:
        from models import DailyReadiness
        dr = (
            db.query(DailyReadiness)
            .filter(
                DailyReadiness.athlete_id == athlete_id,
                DailyReadiness.date == target_date,
            )
            .first()
        )
        if dr:
            readiness_score = dr.score
    except Exception:
        pass

    # Intensity guard
    suppress_intensity = False
    if workout.phase in NO_INTENSITY_PHASES:
        suppress_intensity = True
    if yesterday_workout and yesterday_workout.workout_type in NO_INTENSITY_AFTER:
        suppress_intensity = True

    return {
        "workout": {
            "type": workout.workout_type,
            "subtype": workout.workout_subtype,
            "title": workout.title,
            "description": workout.description,
            "phase": workout.phase,
            "phase_week": workout.phase_week,
            "week_number": workout.week_number,
            "distance_km": workout.target_distance_km,
            "duration_min": workout.target_duration_minutes,
            "segments": workout.segments,
        },
        "recent_activities": [
            {
                "name": a.name,
                "type": a.workout_type,
                "distance_km": round(a.distance_m / 1000, 1) if a.distance_m else None,
                "duration_min": round(a.duration_s / 60, 1) if a.duration_s else None,
                "avg_hr": a.avg_hr,
            }
            for a in recent
        ],
        "upcoming": [
            {"type": u.workout_type, "title": u.title, "date": u.scheduled_date.isoformat()}
            for u in upcoming
        ],
        "readiness_score": readiness_score,
        "suppress_intensity": suppress_intensity,
        "yesterday_type": yesterday_workout.workout_type if yesterday_workout else None,
    }


def _build_prompt(ctx: Dict[str, Any]) -> str:
    """Build the user prompt from assembled context."""
    w = ctx["workout"]
    lines = [
        f"Today's workout: {w['title']} ({w['type']}, {w['phase']} phase, week {w['week_number']}).",
    ]
    if w.get("description"):
        lines.append(f"Details: {w['description'][:200]}")
    if w.get("distance_km"):
        lines.append(f"Target: {w['distance_km']:.1f} km")

    if ctx["recent_activities"]:
        recent_summary = "; ".join(
            f"{a['name'] or a['type']} ({a['distance_km']} km)"
            for a in ctx["recent_activities"][:3]
        )
        lines.append(f"Recent sessions: {recent_summary}")

    if ctx["readiness_score"] is not None:
        lines.append(f"Readiness: {ctx['readiness_score']:.0f}/100")

    if ctx["upcoming"]:
        next_key = ctx["upcoming"][0]
        lines.append(f"Coming up: {next_key['title']} on {next_key['date']}")

    if ctx["suppress_intensity"]:
        lines.append("IMPORTANT: Do NOT encourage pushing intensity today.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Recent narrative fetch (for similarity check)
# ---------------------------------------------------------------------------

def _get_recent_narratives(
    athlete_id: UUID,
    db: Session,
    window_days: int = RECENT_NARRATIVE_WINDOW,
) -> List[str]:
    """Fetch recently shown workout narratives for similarity check."""
    from models import NarrationLog
    cutoff = date.today() - timedelta(days=window_days)
    rows = (
        db.query(NarrationLog.narration_text)
        .filter(
            NarrationLog.athlete_id == athlete_id,
            NarrationLog.trigger_date >= cutoff,
            NarrationLog.narration_text.isnot(None),
            NarrationLog.suppressed.is_(False),
            NarrationLog.rule_id == "WORKOUT_NARRATIVE",
        )
        .order_by(desc(NarrationLog.trigger_date))
        .limit(10)
        .all()
    )
    return [r.narration_text for r in rows if r.narration_text]


# ---------------------------------------------------------------------------
# LLM call (mirrors adaptation_narrator.py pattern)
# ---------------------------------------------------------------------------

def _call_llm(
    client: Any,
    user_prompt: str,
) -> Tuple[str, int, int, int]:
    """Call configured narrative model. Returns (text, input_tokens, output_tokens, latency_ms)."""
    model_name = _resolved_workout_narrative_model()

    if not model_name.startswith("gemini"):
        result = call_llm(
            model=model_name,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=NARRATIVE_MAX_TOKENS,
            temperature=NARRATIVE_TEMPERATURE,
            response_mode="text",
            timeout_s=60,
        )
        return (
            result["text"],
            int(result["input_tokens"]),
            int(result["output_tokens"]),
            int(result["latency_ms"]),
        )

    if client is None:
        raise RuntimeError("No Gemini client provided.")

    start = time.monotonic()

    try:
        import google.genai.types as genai_types
        contents = [
            genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=user_prompt)],
            ),
        ]
        config = genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=NARRATIVE_MAX_TOKENS,
            temperature=NARRATIVE_TEMPERATURE,
        )
    except Exception:
        contents = [{"role": "user", "parts": [{"text": user_prompt}]}]
        config = {
            "system_instruction": SYSTEM_PROMPT,
            "max_output_tokens": NARRATIVE_MAX_TOKENS,
            "temperature": NARRATIVE_TEMPERATURE,
        }

    response = client.models.generate_content(
        model=model_name,
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
# Banned metric check (reuse from narration_scorer)
# ---------------------------------------------------------------------------

_BANNED_RE = re.compile(
    r"\b(?:TSB|CTL|ATL|VDOT|rMSSD|SDNN|TRIMP)\b"
    r"|(?:EF\s*[:=]\s*\d)"
    r"|(?:efficiency\s+factor\s*[:=]\s*\d)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# 4-criterion quality scorer (WS3)
# ---------------------------------------------------------------------------

# Prescriptive language patterns that fail the tone criterion
_PRESCRIPTIVE_RE = re.compile(
    r"\b(you\s+should|you\s+must|you\s+need\s+to|make\s+sure\s+you|don't\s+forget\s+to)\b",
    re.IGNORECASE,
)

# Intensity phrases that fail physiological soundness in wrong contexts
_INTENSITY_RE = re.compile(
    r"push\s+(hard|yourself|it|the\s+pace)|go\s+(hard|fast|all.?out)|"
    r"\battack\b|\bhammer\b|max\s+effort",
    re.IGNORECASE,
)

# Generic coaching sludge patterns (vague, template-like) that fail contextual check
_GENERIC_SLUDGE_RE = re.compile(
    r"\b(stay\s+focused|give\s+it\s+your\s+all|trust\s+the\s+process|"
    r"you've\s+got\s+this|believe\s+in\s+yourself|listen\s+to\s+your\s+body)\b",
    re.IGNORECASE,
)

# Context signals that indicate the narrative IS contextual
_CONTEXT_SIGNALS = [
    r"\b(week\s+\d|week\s+[a-z]+)\b",       # week references
    r"\b(phase|build|taper|recover)\b",       # plan phase
    r"\b(yesterday|last\s+week|recent|last\s+(run|session|workout))\b",
    r"\b(coming\s+up|ahead|saturday|sunday|monday|tuesday|wednesday|thursday|friday)\b",
    r"\b(progression|building|increasing)\b",
    r"\b(readiness|ready|fresh|tired|fatigue)\b",
]


def score_narrative_quality(
    text: str,
    ctx: Optional[Dict[str, Any]],
    recent_narratives: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Score a workout narrative on the 4-criterion 3B rubric.

    Returns a dict with per-criterion pass/fail + failure reasons.
    Persisted into NarrationLog.ground_truth['quality_score'] at generation time.

    Criteria:
    1. contextual   — references specific workout/phase/recent/upcoming data
    2. non_repetitive — not >50% token overlap with recent narratives
    3. physiologically_sound — no unsafe intensity in taper/post-long contexts
    4. tone_rules_ok — no banned metrics, no prescriptive drift, no generic sludge
    """
    if not text:
        return {
            "contextual": False, "contextual_fail_reason": "empty_narrative",
            "non_repetitive": True, "non_repetitive_fail_reason": None,
            "physiologically_sound": True, "physiologically_sound_fail_reason": None,
            "tone_rules_ok": False, "tone_rules_fail_reason": "empty_narrative",
            "criteria_passed": 0, "score": 0.0,
        }

    failures: Dict[str, Optional[str]] = {
        "contextual_fail_reason": None,
        "non_repetitive_fail_reason": None,
        "physiologically_sound_fail_reason": None,
        "tone_rules_fail_reason": None,
    }

    # 1. Contextual: must contain at least one context signal
    contextual = any(
        re.search(pat, text, re.IGNORECASE) for pat in _CONTEXT_SIGNALS
    )
    if not contextual:
        # Also pass if LLM included a specific number (distance, pace, etc.)
        contextual = bool(re.search(r"\b\d+(\.\d+)?\s*(km|mi|min|sec|:)\b", text))
    if not contextual:
        failures["contextual_fail_reason"] = "no_specific_context_signal"

    # 2. Non-repetitive: not too similar to recent narratives
    non_repetitive = True
    if recent_narratives:
        if _is_too_similar(text, recent_narratives):
            non_repetitive = False
            failures["non_repetitive_fail_reason"] = "token_overlap_exceeds_threshold"

    # 3. Physiologically sound: no intensity encouragement in wrong context
    physiologically_sound = True
    if ctx and ctx.get("suppress_intensity"):
        if _INTENSITY_RE.search(text):
            physiologically_sound = False
            failures["physiologically_sound_fail_reason"] = "intensity_encouragement_in_wrong_context"

    # 4. Tone rules: no banned metrics, no prescriptive drift, no generic sludge
    tone_rules_ok = True
    if _BANNED_RE.search(text):
        tone_rules_ok = False
        failures["tone_rules_fail_reason"] = "banned_metric_acronym"
    elif _PRESCRIPTIVE_RE.search(text):
        tone_rules_ok = False
        failures["tone_rules_fail_reason"] = "prescriptive_language"
    elif _GENERIC_SLUDGE_RE.search(text):
        tone_rules_ok = False
        failures["tone_rules_fail_reason"] = "generic_sludge"

    criteria_passed = sum([contextual, non_repetitive, physiologically_sound, tone_rules_ok])

    return {
        "contextual": contextual,
        "contextual_fail_reason": failures["contextual_fail_reason"],
        "non_repetitive": non_repetitive,
        "non_repetitive_fail_reason": failures["non_repetitive_fail_reason"],
        "physiologically_sound": physiologically_sound,
        "physiologically_sound_fail_reason": failures["physiologically_sound_fail_reason"],
        "tone_rules_ok": tone_rules_ok,
        "tone_rules_fail_reason": failures["tone_rules_fail_reason"],
        "criteria_passed": criteria_passed,
        "score": round(criteria_passed / 4, 3),
    }


# ---------------------------------------------------------------------------
# Kill switch helper (module-level so tests can patch it cleanly)
# ---------------------------------------------------------------------------

def _is_3b_kill_switched(db: Session) -> bool:
    """Check env var AND FeatureFlag table for 3B kill switch.

    Logic:
    - env "1"/"true"/"yes" → immediate hard kill (no DB query needed).
    - Any other env value (including explicit "false" or unset) → check DB
      FeatureFlag.  A disabled flag always kills, even if env is "false".
    """
    import os
    _ks_env = os.getenv(KILL_SWITCH_3B_ENV, "").lower()
    if _ks_env in ("1", "true", "yes"):
        return True
    try:
        from models import FeatureFlag
        flag = db.query(FeatureFlag).filter(FeatureFlag.key == KILL_SWITCH_3B_ENV).first()
        if flag and not flag.enabled:
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_workout_narrative(
    athlete_id: UUID,
    target_date: date,
    db: Session,
    gemini_client: Any = None,
) -> WorkoutNarrativeResult:
    """Generate a contextual workout narrative for the target date.

    Returns WorkoutNarrativeResult.  `narrative` is None when suppressed.
    """
    if _is_3b_kill_switched(db):
        return WorkoutNarrativeResult(
            suppressed=True,
            suppression_reason="3B workout narratives globally disabled (kill_switch).",
        )

    # Build context
    ctx = _build_context(athlete_id, target_date, db)
    if ctx is None:
        return WorkoutNarrativeResult(
            suppressed=True,
            suppression_reason="No planned workout or insufficient context.",
        )

    user_prompt = _build_prompt(ctx)

    # Call LLM
    try:
        text, in_tok, out_tok, lat = _call_llm(gemini_client, user_prompt)
    except Exception as exc:
        return WorkoutNarrativeResult(
            suppressed=True,
            suppression_reason=f"LLM error: {exc}",
            prompt_used=user_prompt,
        )

    if not text or not text.strip():
        return WorkoutNarrativeResult(
            suppressed=True,
            suppression_reason="LLM returned empty response.",
            prompt_used=user_prompt,
            model_used=NARRATIVE_MODEL,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=lat,
        )

    text = text.strip()

    # Safety: banned metrics
    if _BANNED_RE.search(text):
        return WorkoutNarrativeResult(
            suppressed=True,
            suppression_reason="Narrative contained banned metric acronyms.",
            prompt_used=user_prompt,
            model_used=NARRATIVE_MODEL,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=lat,
        )

    # Physiological guard: intensity encouragement in wrong context
    if ctx["suppress_intensity"]:
        intensity_phrases = [
            r"push\s+(hard|yourself|it|the pace)",
            r"go\s+(hard|fast|all.?out)",
            r"attack",
            r"hammer",
            r"max\s+effort",
        ]
        for pat in intensity_phrases:
            if re.search(pat, text, re.IGNORECASE):
                return WorkoutNarrativeResult(
                    suppressed=True,
                    suppression_reason="Narrative encouraged intensity in taper/post-long context.",
                    prompt_used=user_prompt,
                    model_used=NARRATIVE_MODEL,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    latency_ms=lat,
                )

    # Similarity check
    recent = _get_recent_narratives(athlete_id, db)
    if _is_too_similar(text, recent):
        return WorkoutNarrativeResult(
            suppressed=True,
            suppression_reason="Narrative too similar to recent workout notes (>50% overlap).",
            prompt_used=user_prompt,
            model_used=NARRATIVE_MODEL,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=lat,
        )

    # 4-criterion quality score — persisted into audit log for founder review
    quality_score = score_narrative_quality(text, ctx, recent_narratives=recent)

    return WorkoutNarrativeResult(
        narrative=text,
        suppressed=False,
        prompt_used=user_prompt,
        model_used=NARRATIVE_MODEL,
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=lat,
        quality_score=quality_score,
    )


# ---------------------------------------------------------------------------
# P1-D: Consent-aware class wrapper
# ---------------------------------------------------------------------------

class WorkoutNarrativeGenerator:
    """
    Consent-aware wrapper for workout narrative LLM calls.

    Provides a stable class-based API so consent gating can be tested
    and extended without modifying the module-level generate_workout_narrative
    function used by existing call sites.
    """

    def _call_llm(
        self,
        athlete_id: Any = None,
        prompt: str = "",
        db: Any = None,
        client: Any = None,
    ) -> Optional[Tuple[str, int, int, int]]:
        """
        Check consent then dispatch LLM.

        Returns the _call_llm tuple (text, in_tok, out_tok, lat_ms) or None
        if consent is not granted.
        """
        if athlete_id is not None:
            _db = db
            _close = False
            if _db is None:
                from core.database import SessionLocal
                _db = SessionLocal()
                _close = True
            try:
                from services.consent import has_ai_consent as _has_consent
                if not _has_consent(athlete_id=athlete_id, db=_db):
                    return None
            finally:
                if _close:
                    _db.close()

        return _call_llm(client, prompt)
