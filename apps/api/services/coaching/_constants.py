"""
AI Coach Service

Gemini 3 Flash handles bulk coaching queries.
High-stakes queries route to Claude Sonnet for maximum reasoning quality.

Features:
- Persistent conversation sessions per athlete (PostgreSQL-backed)
- Context injection from athlete's actual data
- Knowledge of training methodology
- Tiered context (7-day, 30-day, 120-day)
- Hybrid model routing (Gemini Flash + Claude Sonnet) per ADR-061
- Hard cost caps per athlete
"""

import os
import json
import re
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
import logging
from datetime import timezone

logger = logging.getLogger(__name__)
from core.date_utils import calculate_age  # noqa: E402

# =============================================================================
# ADR-061: HYBRID MODEL ARCHITECTURE WITH COST CAPS
# =============================================================================

# High-stakes signals that trigger Opus routing
class HighStakesSignal(Enum):
    """Signals that trigger Sonnet routing for premium reasoning quality."""
    INJURY = "injury"
    PAIN = "pain"
    OVERTRAINING = "overtraining"
    FATIGUE = "fatigue"
    SKIP_DECISION = "skip"
    LOAD_ADJUSTMENT = "load"
    RETURN_FROM_BREAK = "return"
    ILLNESS = "illness"


# Patterns that trigger high-stakes routing to Sonnet
HIGH_STAKES_PATTERNS = [
    # Injury/pain signals (liability risk)
    "injury", "injured", "pain", "painful", "hurt", "hurting",
    "sore", "soreness", "ache", "aching", "sharp", "stabbing",
    "tender", "swollen", "swelling", "inflammation",
    "strain", "sprain", "tear", "stress fracture",
    "knee", "shin", "achilles", "plantar", "it band", "hip",
    "calf", "hamstring", "quad", "groin", "ankle", "foot",
    
    # Recovery concerns
    "overtrain", "overtraining", "burnout", "exhausted",
    "can't recover", "not recovering", "always tired",
    "resting heart rate", "hrv dropping", "hrv crashed",
    "legs feel dead", "no energy",
    
    # Return-from-break (high error risk)
    "coming back", "returning from", "time off", "break",
    "haven't run", "first run back", "starting again",
    "after illness", "after sick", "after covid",
    "after surgery", "post-op", "back from",
    
    # Load decisions (requires careful reasoning)
    "should i run", "safe to run", "okay to run",
    "skip", "should i skip", "take a day off",
    "reduce mileage", "cut back", "too much",
    "push through", "run through",
]

# Cost cap constants (ADR-061)
# Canonical cap reference + builder addendum block: docs/COACH_RUNTIME_CAP_CONFIG.md
#
# Apr 2026: Universal Kimi K2.5 routing — every request is "premium lane."
# Kimi pricing ($0.38/M input, $1.72/M output) is ~13x cheaper than Sonnet.
# Caps set high enough that no athlete should ever hit them during normal use.
# At Kimi rates, 2M tokens/month ≈ $2.10/user. 5M tokens ≈ $5.25/user.
# Capping an engaged athlete is a product-killer — keep guardrails for abuse
# only, not for normal conversation volume.
COACH_MAX_REQUESTS_PER_DAY = int(os.getenv("COACH_MAX_REQUESTS_PER_DAY", "100"))
COACH_MAX_OPUS_REQUESTS_PER_DAY = int(os.getenv("COACH_MAX_OPUS_REQUESTS_PER_DAY", "50"))
COACH_MONTHLY_TOKEN_BUDGET = int(os.getenv("COACH_MONTHLY_TOKEN_BUDGET", "5000000"))
COACH_MONTHLY_OPUS_TOKEN_BUDGET = int(os.getenv("COACH_MONTHLY_OPUS_TOKEN_BUDGET", "5000000"))
# VIP premium-lane caps (founder bypass still uncapped).
COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP = int(
    os.getenv("COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP", "100")
)
COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP = int(
    os.getenv("COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP", "5000000")
)
COACH_MAX_INPUT_TOKENS = int(os.getenv("COACH_MAX_INPUT_TOKENS", "4000"))
# 500 tokens was causing every response to get cut off mid-sentence.
# 3000 tokens (~1200 words) allows complete, well-structured coaching responses
# 1500 tokens (~600 words) is generous for any conversational response.
# Acts as a hard ceiling preventing essays even when soft prompt instructions are ignored.
COACH_MAX_OUTPUT_TOKENS = int(os.getenv("COACH_MAX_OUTPUT_TOKENS", "1500"))

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\uFE0F"
    "\u200D"
    "]+",
    flags=re.UNICODE,
)


def _strip_emojis(text: str) -> str:
    """Remove emoji glyphs while preserving plain text punctuation."""
    if not text:
        return text
    return _EMOJI_RE.sub("", text)


_KB_VIOLATION_PATTERNS: List[tuple[str, str]] = [
    (r"\bzone\s*[1-5]\b", "HR_ZONE_NUMBER"),
    (r"\bzone\s+(?:one|two|three|four|five)\b", "HR_ZONE_NAME"),
    (r"keep\s+(?:your\s+)?(?:heart\s+rate|hr)\s+(?:below|under|above|at|around)\s+\d+", "HR_TARGET"),
    (r"stay\s+in\s+(?:the\s+)?(?:zone|hr\s+zone)", "HR_ZONE_PRESCRIPTION"),
    (r"\b(?:220|two\s*twenty)\s*[-–]\s*(?:age|your\s+age)", "POPULATION_FORMULA"),
    (r"(?:max\s+hr|maximum\s+heart\s+rate)\s+(?:formula|calculation|is\s+\d{3})", "POPULATION_HR_CALC"),
]

_HEDGE_PHRASES = [
    "still aggressive",
    "that's aggressive",
    "it's worth noting",
    "that said",
    "it's possible that",
    "i would suggest considering",
    "it may be worth",
    "just something to keep in mind",
    "i should mention",
    "to be fair",
    "i want to be careful",
    "proceed with caution",
    "worth considering",
    "something to think about",
    "you might want to consider",
    "it's important to remember",
    "i'd recommend being cautious",
    "on the other hand",
]


def count_hedge_phrases(text: str) -> int:
    lower = (text or "").lower()
    return sum(1 for phrase in _HEDGE_PHRASES if phrase in lower)


def _check_kb_violations(response_text: str, model: str, athlete_id: str) -> Optional[str]:
    """
    Check coach response for KB philosophy violations.

    Returns a violation tag if found (for logging/metrics), None if clean.
    This is a safety net — architectural enforcement (removing HR zones from
    tool outputs) is the primary defense. This catches LLM leakage.
    """
    text_lower = response_text.lower()
    for pattern, tag in _KB_VIOLATION_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            logger.warning(
                "KB VIOLATION [%s] in coach response [model=%s athlete=%s]: %s",
                tag, model, athlete_id, match.group(0),
            )
            return tag
    return None


def _check_response_quality(response_text: str, model: str, athlete_id: str) -> None:
    """Log warnings for responses that violate format/length contracts. Never blocks."""
    warnings = []
    if "##" in response_text or "###" in response_text:
        warnings.append("contains markdown headers")
    if "|" in response_text and "---" in response_text:
        warnings.append("contains markdown table")
    if any(ch in response_text for ch in ["🎯", "💪", "🏃", "✅", "🔥", "😊", "👍", "🏅"]):
        warnings.append("contains emoji")
    word_count = len(response_text.split())
    if word_count > 300:
        warnings.append(f"response is {word_count} words (>300)")
    hedge_count = count_hedge_phrases(response_text)
    if hedge_count >= 3:
        warnings.append(f"hedge_overload:{hedge_count}")
    if warnings:
        logger.warning(
            "Coach response quality check [model=%s athlete=%s]: %s",
            model, athlete_id, "; ".join(warnings),
        )
    _check_kb_violations(response_text, model, athlete_id)


def is_high_stakes_query(message: str) -> bool:
    """
    Determine if query requires Sonnet for premium reasoning quality.
    
    Returns True for:
    - Injury/pain mentions
    - Return-from-break queries
    - Load adjustment decisions
    - Overtraining concerns
    
    See ADR-061 for rationale.
    """
    if not message:
        return False
    message_lower = message.lower()
    return any(pattern in message_lower for pattern in HIGH_STAKES_PATTERNS)

# Check if Anthropic is available (for Opus high-stakes routing)
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.info("Anthropic not installed - high-stakes queries will use GPT-4o fallback")

# Check if Google GenAI is available (for Gemini 3 Flash coaching queries)
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    genai_types = None
    logger.info("Google GenAI not installed - bulk queries will use GPT-4o-mini fallback")

from models import (  # noqa: E402
    Athlete,
    Activity,
    TrainingPlan,
    PlannedWorkout,
    DailyCheckin,
    GarminDay,
    PersonalBest,
    IntakeQuestionnaire,
    CoachUsage,
    CoachChat,
)
from services import coach_tools  # noqa: E402
from core.config import settings  # noqa: E402

# Phase 4/5 Modular Coach Components
from services.coach_modules import (  # noqa: E402
    MessageRouter,
    MessageType,
    ContextBuilder,
    ConversationQualityManager,
)




def _build_cross_training_context(athlete_id: str, db: Session) -> Optional[str]:
    """Build cross-training context for coach prompt.

    Returns a formatted string section if the athlete has cross-training data
    in the last 7 days, or None if no relevant data exists.
    """
    from datetime import timezone
    from collections import defaultdict

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    strength_activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "strength",
            Activity.start_time >= week_ago,
            Activity.start_time <= now,
        )
        .order_by(Activity.start_time)
        .all()
    )

    cycling_activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "cycling",
            Activity.start_time >= week_ago,
            Activity.start_time <= now,
        )
        .order_by(Activity.start_time)
        .all()
    )

    flex_activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "flexibility",
            Activity.start_time >= week_ago,
            Activity.start_time <= now,
        )
        .order_by(Activity.start_time)
        .all()
    )

    if not strength_activities and not cycling_activities and not flex_activities:
        return None

    lines = ["\n\nCROSS-TRAINING CONTEXT (Last 7 Days):"]

    if strength_activities:
        from models import StrengthExerciseSet
        days_str = ", ".join(
            sorted(set(a.start_time.strftime("%a") for a in strength_activities))
        )
        lines.append(f"Strength: {len(strength_activities)} session(s) ({days_str})")

        all_sets = (
            db.query(StrengthExerciseSet)
            .filter(
                StrengthExerciseSet.activity_id.in_([a.id for a in strength_activities]),
                StrengthExerciseSet.set_type == "active",
            )
            .order_by(StrengthExerciseSet.set_order)
            .all()
        )

        if all_sets:
            pattern_counts = defaultdict(int)
            total_volume = 0.0
            for s in all_sets:
                pattern_counts[s.movement_pattern] += 1
                if s.weight_kg and s.reps:
                    total_volume += s.weight_kg * s.reps

            pattern_summary = ", ".join(
                f"{p} ({c} sets)" for p, c in
                sorted(pattern_counts.items(), key=lambda x: -x[1])[:4]
            )
            lines.append(f"  Movement patterns: {pattern_summary}")

            if total_volume > 0:
                lines.append(f"  Total volume: {total_volume:,.0f} kg")

        for act in strength_activities:
            if act.strength_session_type:
                lines.append(
                    f"  {act.start_time.strftime('%a')}: {act.strength_session_type} session"
                    f" ({int((act.duration_s or 0) / 60)} min)"
                )

        last_strength = strength_activities[-1]
        hours_since = (now - last_strength.start_time).total_seconds() / 3600
        lines.append(f"  Last strength session: {hours_since:.0f} hours ago")

    if cycling_activities:
        total_min = sum((a.duration_s or 0) for a in cycling_activities) / 60
        lines.append(
            f"Cycling: {len(cycling_activities)} session(s) — {total_min:.0f} min total"
        )

    if flex_activities:
        total_min = sum((a.duration_s or 0) for a in flex_activities) / 60
        lines.append(
            f"Flexibility: {len(flex_activities)} session(s) — {total_min:.0f} min total"
        )

    lines.append("")
    lines.append(
        "The coach does NOT prescribe strength programming. "
        "Observe what the athlete does, surface what the data shows about "
        "timing and recovery, and answer questions in context."
    )

    return "\n".join(lines)
