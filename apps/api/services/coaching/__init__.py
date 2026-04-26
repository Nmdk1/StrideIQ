"""Coaching package - split from monolithic ai_coach.py."""

from services import coach_tools  # noqa: F401
from core.config import settings  # noqa: F401
from .core import AICoach, get_ai_coach  # noqa: F401
from ._constants import (  # noqa: F401
    HighStakesSignal,
    HIGH_STAKES_PATTERNS,
    COACH_MAX_REQUESTS_PER_DAY,
    COACH_MAX_OPUS_REQUESTS_PER_DAY,
    COACH_MONTHLY_TOKEN_BUDGET,
    COACH_MONTHLY_OPUS_TOKEN_BUDGET,
    COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP,
    COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP,
    COACH_MAX_INPUT_TOKENS,
    COACH_MAX_OUTPUT_TOKENS,
    _strip_emojis,
    _check_kb_violations,
    _check_response_quality,
    is_high_stakes_query,
    _build_cross_training_context,
)
