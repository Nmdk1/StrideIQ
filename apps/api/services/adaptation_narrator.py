"""
Adaptation Narrator (Phase 3A)

Generates contextual coach narrations for intelligence insights.
The coach EXPLAINS the deterministic decision — it does NOT decide.

Uses Gemini Flash with a tightly scoped prompt:
    - The insight rule that fired (rule_id, mode, data_cited)
    - The readiness score and its components
    - Recent training context (last 7 days of activities)
    - What the planned workout is

The narration must:
    1. Cite specific data ("25% volume increase" not "you ran more")
    2. Never expose raw metrics (TSB, CTL, ATL, EF, VDOT)
    3. Contain actionable language ("consider", "be mindful", "going forward")
    4. Never claim to have changed the plan (INFORM mode = no swaps)
    5. Be 2-3 sentences, conversational coaching tone

Every narration is scored by the NarrationScorer against the engine's
ground truth. If the score is below threshold, the narration is suppressed
and only the structured insight is shown. Silence > bad narrative.

Sources:
    docs/TRAINING_PLAN_REBUILD_PLAN.md (Phase 3A spec + Coach Trust track)
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from services.narration_scorer import NarrationScorer, NarrationScoreResult

# Check if Google GenAI is available
try:
    from google import genai as _genai_module
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    _genai_module = None
    genai_types = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NARRATOR_MODEL = "gemini-2.5-flash"
NARRATOR_TEMPERATURE = 0.3          # Low temp for factual accuracy
NARRATOR_MAX_TOKENS = 200           # 2-3 sentences max
NARRATION_MIN_SCORE = 0.67          # Below this → suppress (at least 2/3 criteria pass)
NARRATION_CONTRADICTION_THRESHOLD = True  # Any contradiction → suppress


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a running coach providing a brief contextual explanation of a training insight.

CRITICAL RULES:
- You are EXPLAINING a decision that has already been made. You did NOT make the decision.
- NEVER say you changed, swapped, modified, or adjusted the athlete's plan.
- NEVER use these acronyms or raw metrics: TSB, CTL, ATL, VDOT, rMSSD, SDNN, EF, TRIMP
- Use human-friendly language: "training load" not "CTL", "recovery balance" not "TSB"
- Include at least one forward-looking action word: "consider", "be mindful of", "going forward", "listen to your body", etc.
- Be specific: cite the actual percentages and numbers from the data provided.
- Keep it to 2-3 sentences maximum. Conversational. Like a knowledgeable friend who runs.
- Lead with what's happening, end with what to consider."""


def _build_insight_prompt(
    rule_id: str,
    mode: str,
    data_cited: Dict[str, Any],
    readiness_score: Optional[float],
    readiness_components: Optional[Dict[str, Any]],
    recent_context: Optional[str],
    planned_workout: Optional[str],
) -> str:
    """Build the user prompt with structured insight data."""
    parts = [
        f"INSIGHT RULE: {rule_id}",
        f"MODE: {mode} (you are INFORMING, not deciding)",
        f"DATA: {_format_data(data_cited)}",
    ]

    if readiness_score is not None:
        parts.append(f"READINESS: {readiness_score:.0f}/100")

    if readiness_components:
        # Only include human-friendly component names
        friendly = _humanize_components(readiness_components)
        if friendly:
            parts.append(f"READINESS SIGNALS: {friendly}")

    if recent_context:
        parts.append(f"RECENT TRAINING: {recent_context}")

    if planned_workout:
        parts.append(f"TODAY'S PLAN: {planned_workout}")

    parts.append(
        "\nWrite a 2-3 sentence coaching explanation. "
        "Cite the specific numbers. End with what to consider."
    )

    return "\n".join(parts)


def _format_data(data_cited: Dict[str, Any]) -> str:
    """Format data_cited dict into a human-readable string for the prompt."""
    if not data_cited:
        return "No specific data"

    parts = []
    for key, value in data_cited.items():
        friendly_key = key.replace("_", " ").replace("pct", "%").replace("km", "km")
        if isinstance(value, float):
            parts.append(f"{friendly_key}: {value:.1f}")
        else:
            parts.append(f"{friendly_key}: {value}")
    return ", ".join(parts)


def _humanize_components(components: Dict[str, Any]) -> str:
    """Convert readiness components to human-friendly descriptions."""
    human_map = {
        "efficiency_trend": "running efficiency trend",
        "tsb": "recovery balance",
        "completion_rate": "training consistency",
        "recovery_days": "time since last hard session",
        "half_life": "recovery trajectory",
    }

    parts = []
    for key, value in components.items():
        if key in human_map:
            if isinstance(value, (int, float)):
                parts.append(f"{human_map[key]}: {value:.0f}")
            else:
                parts.append(f"{human_map[key]}: {value}")
    return ", ".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class NarrationResult:
    """Result of generating and scoring a narration."""
    insight_rule_id: str
    narration: Optional[str] = None     # The generated text (None if suppressed)
    score_result: Optional[NarrationScoreResult] = None
    suppressed: bool = False
    suppression_reason: Optional[str] = None

    # LLM metadata
    model_used: str = NARRATOR_MODEL
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0

    # Raw response (for debugging)
    raw_response: Optional[str] = None
    prompt_used: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Narrator service
# ---------------------------------------------------------------------------

class AdaptationNarrator:
    """
    Generate and score contextual narrations for intelligence insights.

    The narrator:
    1. Builds a tightly scoped prompt from the insight + context
    2. Calls Gemini Flash for the narration
    3. Scores the narration against engine ground truth
    4. Suppresses narrations that fail scoring criteria

    Usage:
        narrator = AdaptationNarrator(gemini_client=client)
        result = narrator.narrate(
            rule_id="LOAD_SPIKE",
            mode="inform",
            data_cited={"pct_increase": 25.0, ...},
            ground_truth={...},
            insight_rule_ids=["LOAD_SPIKE"],
        )
        if not result.suppressed:
            # Use result.narration
    """

    def __init__(self, gemini_client=None):
        """
        Initialize the narrator.

        Args:
            gemini_client: google.genai.Client instance (None = dry run mode)
        """
        self.client = gemini_client
        self.scorer = NarrationScorer()

    def narrate(
        self,
        rule_id: str,
        mode: str,
        data_cited: Dict[str, Any],
        ground_truth: Dict[str, Any],
        insight_rule_ids: List[str],
        readiness_score: Optional[float] = None,
        readiness_components: Optional[Dict[str, Any]] = None,
        recent_context: Optional[str] = None,
        planned_workout: Optional[str] = None,
    ) -> NarrationResult:
        """
        Generate and score a narration for an intelligence insight.

        Returns NarrationResult with narration text (or suppressed).
        """
        result = NarrationResult(insight_rule_id=rule_id)

        # Build prompt
        user_prompt = _build_insight_prompt(
            rule_id=rule_id,
            mode=mode,
            data_cited=data_cited,
            readiness_score=readiness_score,
            readiness_components=readiness_components,
            recent_context=recent_context,
            planned_workout=planned_workout,
        )
        result.prompt_used = user_prompt

        # Call LLM
        try:
            raw_text, input_tok, output_tok, latency = self._call_llm(user_prompt)
            result.raw_response = raw_text
            result.input_tokens = input_tok
            result.output_tokens = output_tok
            result.latency_ms = latency
        except Exception as e:
            logger.error(f"Narration LLM call failed for {rule_id}: {e}")
            result.error = str(e)
            result.suppressed = True
            result.suppression_reason = f"LLM call failed: {e}"
            return result

        if not raw_text or not raw_text.strip():
            result.suppressed = True
            result.suppression_reason = "LLM returned empty response"
            return result

        # Score against ground truth
        score_result = self.scorer.score(
            narration=raw_text,
            ground_truth=ground_truth,
            insight_rule_ids=insight_rule_ids,
        )
        result.score_result = score_result

        # Quality gate
        if score_result.score < NARRATION_MIN_SCORE:
            result.suppressed = True
            result.suppression_reason = (
                f"Score {score_result.score:.2f} below threshold {NARRATION_MIN_SCORE}. "
                f"Errors: {score_result.factual_errors}"
            )
            logger.warning(
                f"Narration suppressed for {rule_id}: score={score_result.score:.2f}, "
                f"errors={score_result.factual_errors}"
            )

        # Contradiction gate
        if NARRATION_CONTRADICTION_THRESHOLD and score_result.contradicts_engine:
            result.suppressed = True
            result.suppression_reason = (
                f"Contradiction detected: {score_result.contradiction_detail}"
            )
            logger.warning(
                f"Narration suppressed for {rule_id}: contradiction — "
                f"{score_result.contradiction_detail}"
            )

        # Set narration only if not suppressed
        if not result.suppressed:
            result.narration = raw_text.strip()

        return result

    def narrate_batch(
        self,
        insights: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        readiness_score: Optional[float] = None,
        readiness_components: Optional[Dict[str, Any]] = None,
        recent_context: Optional[str] = None,
        planned_workout: Optional[str] = None,
    ) -> List[NarrationResult]:
        """
        Generate narrations for all insights in an intelligence result.

        Each insight is narrated independently. LOG-mode insights are skipped
        (they're internal tracking, not user-facing).
        """
        results = []
        insight_rule_ids = [i.get("rule_id", "") for i in insights]

        for insight in insights:
            mode = insight.get("mode", "log")

            # Skip LOG mode — not user-facing
            if mode == "log":
                continue

            result = self.narrate(
                rule_id=insight.get("rule_id", "UNKNOWN"),
                mode=mode,
                data_cited=insight.get("data_cited", {}),
                ground_truth=ground_truth,
                insight_rule_ids=insight_rule_ids,
                readiness_score=readiness_score,
                readiness_components=readiness_components,
                recent_context=recent_context,
                planned_workout=planned_workout,
            )
            results.append(result)

        return results

    # ==================================================================
    # LLM call
    # ==================================================================

    def _call_llm(self, user_prompt: str) -> Tuple[str, int, int, int]:
        """
        Call Gemini Flash and return (text, input_tokens, output_tokens, latency_ms).

        If no client is available (test/dry-run mode), raises RuntimeError.
        Supports both real Gemini clients and mock clients (for testing).
        """
        if self.client is None:
            raise RuntimeError(
                "No Gemini client available. "
                "Set GOOGLE_API_KEY or pass gemini_client to AdaptationNarrator."
            )

        start = time.monotonic()

        # Build the call arguments — if genai_types is available, use typed objects.
        # If not (mock client in tests), pass raw dicts that the mock can handle.
        if GENAI_AVAILABLE and genai_types is not None:
            contents = [
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=user_prompt)],
                ),
            ]
            config = genai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=NARRATOR_MAX_TOKENS,
                temperature=NARRATOR_TEMPERATURE,
            )
        else:
            # Mock/test mode — pass raw data the mock client will ignore anyway
            contents = [{"role": "user", "parts": [{"text": user_prompt}]}]
            config = {
                "system_instruction": SYSTEM_PROMPT,
                "max_output_tokens": NARRATOR_MAX_TOKENS,
                "temperature": NARRATOR_TEMPERATURE,
            }

        response = self.client.models.generate_content(
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

        # Token usage
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        return text, input_tokens, output_tokens, latency_ms
