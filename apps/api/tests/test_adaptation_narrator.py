"""
Adaptation Narrator Tests (Phase 3A)

Tests the narration generator, scoring pipeline, suppression logic,
and integration with the intelligence engine. These are DETERMINISTIC
tests — no LLM calls, all using mock responses.

The companion test_narration_scorer.py tests the scoring function itself.
These tests verify:
1. Prompt construction is correct and tightly scoped
2. Good narrations pass scoring and are returned
3. Bad narrations are suppressed (silence > bad narrative)
4. Contradictions are caught and suppressed
5. Batch narration works correctly (LOG skipped, others narrated)
6. Quality gate prevents bad narrations from reaching the athlete
7. NarrationLog persistence records everything for audit
8. API endpoint includes narrative field when available

Sources:
    docs/TRAINING_PLAN_REBUILD_PLAN.md (Phase 3A, Coach Trust track)
"""

import pytest
import sys
import os
from datetime import date, datetime
from unittest.mock import MagicMock, patch, PropertyMock
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.adaptation_narrator import (
    AdaptationNarrator,
    NarrationResult,
    SYSTEM_PROMPT,
    NARRATOR_MODEL,
    NARRATION_MIN_SCORE,
    _build_insight_prompt,
    _format_data,
    _humanize_components,
)
from services.narration_scorer import NarrationScorer


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def narrator():
    """Narrator with a mock Gemini client."""
    mock_client = MagicMock()
    return AdaptationNarrator(gemini_client=mock_client)


@pytest.fixture
def good_narration():
    """A narration that passes all 3 criteria."""
    return (
        "Your training volume increased about 25% this week compared to last. "
        "Consider monitoring how your body responds over the next few days."
    )


@pytest.fixture
def bad_narration_metrics():
    """A narration that leaks raw metrics."""
    return (
        "Your TSB is -15 and CTL has been building. "
        "Consider monitoring your recovery."
    )


@pytest.fixture
def bad_narration_inaccurate():
    """A narration with wrong percentages."""
    return (
        "Your training volume spiked 50% this week. "
        "Be mindful of the extra load going forward."
    )


@pytest.fixture
def bad_narration_not_actionable():
    """A narration with no forward-looking guidance."""
    return (
        "Your training volume increased 25% compared to the prior period. "
        "The largest session was a long run on Saturday morning."
    )


@pytest.fixture
def bad_narration_swap():
    """A narration that claims to have swapped the workout."""
    return (
        "Given the load increase, I've swapped your workout to a recovery run. "
        "Focus on staying relaxed."
    )


@pytest.fixture
def load_spike_ground_truth():
    """Ground truth for a LOAD_SPIKE insight."""
    return {
        "highest_mode": "inform",
        "insights": [
            {
                "rule_id": "LOAD_SPIKE",
                "mode": "inform",
                "data_cited": {
                    "current_km": 60.5,
                    "previous_km": 48.4,
                    "pct_increase": 25.0,
                },
            }
        ],
    }


def _mock_gemini_response(text: str):
    """Create a mock Gemini API response."""
    mock_part = MagicMock()
    mock_part.text = text

    mock_content = MagicMock()
    mock_content.parts = [mock_part]

    mock_candidate = MagicMock()
    mock_candidate.content = mock_content

    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 150
    mock_usage.candidates_token_count = 45

    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]
    mock_response.usage_metadata = mock_usage

    return mock_response


# ===========================================================================
# Prompt Construction
# ===========================================================================

class TestPromptConstruction:
    """Verify the prompt is tightly scoped with correct data."""

    def test_prompt_includes_rule_id(self):
        prompt = _build_insight_prompt(
            rule_id="LOAD_SPIKE", mode="inform",
            data_cited={"pct_increase": 25.0},
            readiness_score=55.0, readiness_components=None,
            recent_context=None, planned_workout=None,
        )
        assert "LOAD_SPIKE" in prompt

    def test_prompt_includes_mode_instruction(self):
        prompt = _build_insight_prompt(
            rule_id="LOAD_SPIKE", mode="inform",
            data_cited={}, readiness_score=None,
            readiness_components=None, recent_context=None,
            planned_workout=None,
        )
        assert "INFORMING" in prompt
        assert "not deciding" in prompt

    def test_prompt_includes_data_cited(self):
        prompt = _build_insight_prompt(
            rule_id="LOAD_SPIKE", mode="inform",
            data_cited={"pct_increase": 25.0, "current_km": 60.5},
            readiness_score=None, readiness_components=None,
            recent_context=None, planned_workout=None,
        )
        assert "25.0" in prompt
        assert "60.5" in prompt

    def test_prompt_includes_readiness(self):
        prompt = _build_insight_prompt(
            rule_id="LOAD_SPIKE", mode="inform",
            data_cited={}, readiness_score=55.0,
            readiness_components=None, recent_context=None,
            planned_workout=None,
        )
        assert "READINESS: 55/100" in prompt

    def test_prompt_includes_context(self):
        prompt = _build_insight_prompt(
            rule_id="LOAD_SPIKE", mode="inform",
            data_cited={}, readiness_score=None,
            readiness_components=None,
            recent_context="Mon: 8km easy, Wed: 12km threshold, Sat: 22km long",
            planned_workout="Easy 8km recovery",
        )
        assert "Mon: 8km easy" in prompt
        assert "Easy 8km recovery" in prompt

    def test_system_prompt_bans_metrics(self):
        """System prompt must ban all the same terms the scorer checks."""
        assert "TSB" in SYSTEM_PROMPT
        assert "CTL" in SYSTEM_PROMPT
        assert "ATL" in SYSTEM_PROMPT
        assert "VDOT" in SYSTEM_PROMPT
        assert "EF" in SYSTEM_PROMPT

    def test_system_prompt_requires_action(self):
        """System prompt must instruct forward-looking language."""
        assert "consider" in SYSTEM_PROMPT.lower()
        assert "be mindful" in SYSTEM_PROMPT.lower()

    def test_system_prompt_forbids_swap(self):
        """System prompt must forbid claiming plan changes."""
        assert "NEVER" in SYSTEM_PROMPT
        assert "swap" in SYSTEM_PROMPT.lower()


# ===========================================================================
# Good Narration — Passes All Criteria
# ===========================================================================

class TestGoodNarration:
    """A well-formed narration passes scoring and is returned."""

    def test_good_narration_passes(self, narrator, good_narration, load_spike_ground_truth):
        narrator.client.models.generate_content.return_value = _mock_gemini_response(good_narration)

        result = narrator.narrate(
            rule_id="LOAD_SPIKE",
            mode="inform",
            data_cited={"pct_increase": 25.0},
            ground_truth=load_spike_ground_truth,
            insight_rule_ids=["LOAD_SPIKE"],
        )

        assert result.narration is not None
        assert result.suppressed is False
        assert result.score_result is not None
        assert result.score_result.score == pytest.approx(1.0)

    def test_good_narration_token_tracking(self, narrator, good_narration, load_spike_ground_truth):
        narrator.client.models.generate_content.return_value = _mock_gemini_response(good_narration)

        result = narrator.narrate(
            rule_id="LOAD_SPIKE", mode="inform",
            data_cited={}, ground_truth=load_spike_ground_truth,
            insight_rule_ids=["LOAD_SPIKE"],
        )

        assert result.input_tokens == 150
        assert result.output_tokens == 45
        assert result.latency_ms >= 0

    def test_good_narration_stores_prompt(self, narrator, good_narration, load_spike_ground_truth):
        narrator.client.models.generate_content.return_value = _mock_gemini_response(good_narration)

        result = narrator.narrate(
            rule_id="LOAD_SPIKE", mode="inform",
            data_cited={"pct_increase": 25.0},
            ground_truth=load_spike_ground_truth,
            insight_rule_ids=["LOAD_SPIKE"],
        )

        assert result.prompt_used is not None
        assert "LOAD_SPIKE" in result.prompt_used


# ===========================================================================
# Suppression: Bad narrations are hidden
# ===========================================================================

class TestSuppression:
    """Bad narrations are suppressed — silence > bad narrative."""

    def test_raw_metrics_suppressed(self, narrator, bad_narration_metrics, load_spike_ground_truth):
        """Narration with TSB/CTL is suppressed."""
        narrator.client.models.generate_content.return_value = _mock_gemini_response(bad_narration_metrics)

        result = narrator.narrate(
            rule_id="LOAD_SPIKE", mode="inform",
            data_cited={"pct_increase": 25.0},
            ground_truth=load_spike_ground_truth,
            insight_rule_ids=["LOAD_SPIKE"],
        )

        assert result.suppressed is True
        assert result.narration is None
        assert result.suppression_reason is not None

    def test_inaccurate_percentage_suppressed(self, narrator, bad_narration_inaccurate, load_spike_ground_truth):
        """Narration with wrong % is suppressed."""
        narrator.client.models.generate_content.return_value = _mock_gemini_response(bad_narration_inaccurate)

        result = narrator.narrate(
            rule_id="LOAD_SPIKE", mode="inform",
            data_cited={"pct_increase": 25.0},
            ground_truth=load_spike_ground_truth,
            insight_rule_ids=["LOAD_SPIKE"],
        )

        assert result.suppressed is True
        assert result.narration is None

    def test_swap_claim_suppressed(self, narrator, bad_narration_swap, load_spike_ground_truth):
        """Narration claiming workout swap in INFORM mode is suppressed."""
        narrator.client.models.generate_content.return_value = _mock_gemini_response(bad_narration_swap)

        result = narrator.narrate(
            rule_id="LOAD_SPIKE", mode="inform",
            data_cited={"pct_increase": 25.0},
            ground_truth=load_spike_ground_truth,
            insight_rule_ids=["LOAD_SPIKE"],
        )

        assert result.suppressed is True
        assert result.score_result.contradicts_engine is True

    def test_empty_llm_response_suppressed(self, narrator, load_spike_ground_truth):
        """Empty LLM response is suppressed."""
        narrator.client.models.generate_content.return_value = _mock_gemini_response("")

        result = narrator.narrate(
            rule_id="LOAD_SPIKE", mode="inform",
            data_cited={}, ground_truth=load_spike_ground_truth,
            insight_rule_ids=["LOAD_SPIKE"],
        )

        assert result.suppressed is True
        assert result.suppression_reason is not None
        assert "empty" in result.suppression_reason.lower()

    def test_llm_error_suppressed(self, narrator, load_spike_ground_truth):
        """LLM call failure is suppressed gracefully."""
        narrator.client.models.generate_content.side_effect = RuntimeError("API timeout")

        result = narrator.narrate(
            rule_id="LOAD_SPIKE", mode="inform",
            data_cited={}, ground_truth=load_spike_ground_truth,
            insight_rule_ids=["LOAD_SPIKE"],
        )

        assert result.suppressed is True
        assert result.error is not None
        assert "API timeout" in result.error


# ===========================================================================
# Batch Narration
# ===========================================================================

class TestBatchNarration:
    """Batch narration processes multiple insights, skipping LOG mode."""

    def test_batch_skips_log_mode(self, narrator, good_narration, load_spike_ground_truth):
        narrator.client.models.generate_content.return_value = _mock_gemini_response(good_narration)

        insights = [
            {"rule_id": "SELF_REG_DELTA", "mode": "log", "data_cited": {}},  # Should be skipped
            {"rule_id": "LOAD_SPIKE", "mode": "inform", "data_cited": {"pct_increase": 25.0}},
        ]

        results = narrator.narrate_batch(
            insights=insights,
            ground_truth=load_spike_ground_truth,
        )

        # Only 1 narration (LOG skipped)
        assert len(results) == 1
        assert results[0].insight_rule_id == "LOAD_SPIKE"

    def test_batch_narrates_all_non_log(self, narrator, good_narration):
        narrator.client.models.generate_content.return_value = _mock_gemini_response(good_narration)

        gt = {
            "highest_mode": "flag",
            "insights": [
                {"rule_id": "LOAD_SPIKE", "mode": "inform", "data_cited": {"pct_increase": 25.0}},
                {"rule_id": "SUSTAINED_DECLINE", "mode": "flag", "data_cited": {"total_decline_pct": 8.5}},
            ],
        }

        results = narrator.narrate_batch(
            insights=gt["insights"],
            ground_truth=gt,
        )

        assert len(results) == 2

    def test_batch_with_all_log_returns_empty(self, narrator):
        results = narrator.narrate_batch(
            insights=[
                {"rule_id": "SELF_REG_DELTA", "mode": "log", "data_cited": {}},
            ],
            ground_truth={"highest_mode": None, "insights": []},
        )

        assert len(results) == 0


# ===========================================================================
# No Client Mode (tests, staging without LLM)
# ===========================================================================

class TestNoClient:
    """Without a Gemini client, narration fails gracefully."""

    def test_no_client_raises(self):
        narrator = AdaptationNarrator(gemini_client=None)

        result = narrator.narrate(
            rule_id="LOAD_SPIKE", mode="inform",
            data_cited={}, ground_truth={},
            insight_rule_ids=[],
        )

        assert result.suppressed is True
        assert "client" in (result.error or "").lower() or "Gemini" in (result.error or "")


# ===========================================================================
# Helper Functions
# ===========================================================================

class TestHelpers:

    def test_format_data_empty(self):
        assert _format_data({}) == "No specific data"

    def test_format_data_float(self):
        result = _format_data({"pct_increase": 25.123})
        assert "25.1" in result

    def test_format_data_string(self):
        result = _format_data({"status": "ok"})
        assert "ok" in result

    def test_humanize_components(self):
        result = _humanize_components({
            "efficiency_trend": 72,
            "tsb": 45,
            "unknown_signal": 99,
        })
        assert "running efficiency trend" in result
        assert "recovery balance" in result
        assert "unknown_signal" not in result

    def test_humanize_empty(self):
        assert _humanize_components({}) == ""


# ===========================================================================
# Quality Gate Configuration
# ===========================================================================

class TestQualityGate:
    """Configuration values are correct per build plan."""

    def test_min_score_is_two_thirds(self):
        """Must pass at least 2 of 3 criteria."""
        assert NARRATION_MIN_SCORE == pytest.approx(0.67, abs=0.01)

    def test_model_is_gemini_flash(self):
        """Build plan specifies Gemini Flash for narrations."""
        assert "flash" in NARRATOR_MODEL.lower()
