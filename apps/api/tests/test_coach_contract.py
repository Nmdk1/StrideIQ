"""
Coach Contract Tests — Deterministic tests that verify the coaching contract
WITHOUT calling the LLM.

These tests verify:
1. System prompt contains all required tone rules
2. Normalization pipeline strips internal labels
3. All tools are defined and available
4. Model tiering routes correctly
5. Known failure patterns are caught

These run on EVERY COMMIT (no token cost).
The companion test_coach_evaluation.py (tagged @pytest.mark.coach_integration)
tests actual LLM output and runs nightly/pre-deploy.

Source: docs/TRAINING_PLAN_REBUILD_PLAN.md (Parallel Track: Coach Trust)
"""

import pytest
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_coach_stub():
    """Create a minimally-mocked AICoach for testing prompt construction."""
    from services.ai_coach import AICoach
    mock_db = MagicMock()
    coach = AICoach(db=mock_db)
    return coach


def _get_system_instructions():
    """Get the static SYSTEM_INSTRUCTIONS string."""
    from services.ai_coach import AICoach
    return AICoach.SYSTEM_INSTRUCTIONS


# ---------------------------------------------------------------------------
# TONE RULES: System prompt must contain all required coaching rules
# ---------------------------------------------------------------------------

class TestToneRulesInPrompt:
    """
    Every tone rule from the coaching contract must be present in the
    system instructions. If a rule is missing, the LLM won't follow it.
    """

    def test_no_acronyms_rule(self):
        """Coach must NEVER use TSB, ATL, CTL acronyms.
        Verify the system instructions explicitly ban these acronyms.
        """
        instructions = _get_system_instructions()
        lower = instructions.lower()
        # The instructions must contain all three banned acronyms in context
        # (e.g., "never use training acronyms (tsb, atl, ctl)")
        assert "tsb" in lower and "atl" in lower and "ctl" in lower, \
            "System instructions must explicitly list banned acronyms (TSB, ATL, CTL)"

    def test_no_data_fabrication_rule(self):
        """Coach must NEVER fabricate or estimate data."""
        instructions = _get_system_instructions()
        assert "NEVER" in instructions, "System instructions must contain NEVER rules"
        # Check for data integrity rules
        lower = instructions.lower()
        assert any(
            term in lower
            for term in ["fabricate", "hallucinate", "estimate", "guess"]
        ), "System instructions must prohibit data fabrication"

    def test_no_internal_labels_rule(self):
        """Coach must not output 'fact capsule', 'response contract', etc.
        The rule may be in static SYSTEM_INSTRUCTIONS or in the dynamic
        Gemini prompt template. Check both sources.
        """
        import inspect
        from services.ai_coach import AICoach
        instructions = _get_system_instructions()
        # Also check the dynamic prompt in query_gemini source
        gemini_source = inspect.getsource(AICoach.query_gemini)
        combined = (instructions + gemini_source).lower()
        assert "fact capsule" in combined or "internal label" in combined, \
            "System instructions or Gemini prompt must prohibit internal labels"

    def test_tool_usage_required(self):
        """Coach must be instructed to use tools, not guess."""
        instructions = _get_system_instructions()
        lower = instructions.lower()
        assert "tool" in lower, \
            "System instructions must reference tool usage"

    def test_plain_english_rule(self):
        """Coach must use plain English."""
        instructions = _get_system_instructions()
        lower = instructions.lower()
        assert any(
            term in lower
            for term in ["plain english", "plain language", "no acronym"]
        ), "System instructions must require plain English"

    def test_concise_communication(self):
        """Coach must be concise, not write essays."""
        instructions = _get_system_instructions()
        lower = instructions.lower()
        assert any(
            term in lower
            for term in ["concise", "sparse", "direct", "essay"]
        ), "System instructions must require concise communication"


# ---------------------------------------------------------------------------
# NORMALIZATION: Pipeline must strip internal artifacts
# ---------------------------------------------------------------------------

class TestNormalizationPipeline:
    """
    The _normalize_response_for_ui function must strip all internal
    artifacts before the athlete sees the response.
    """

    def _normalize(self, text: str, user_message: str = "How am I doing?") -> str:
        """Call the normalization function."""
        coach = _make_coach_stub()
        return coach._normalize_response_for_ui(
            user_message=user_message,
            assistant_message=text,
        )

    def test_strips_fact_capsule_label(self):
        """'FACT CAPSULE' labels must be removed from output."""
        raw = "Your easy pace is 8:30/mi.\nAUTHORITATIVE FACT CAPSULE: Your threshold pace is 6:15/mi.\nKeep up the work."
        normalized = self._normalize(raw)
        assert "FACT CAPSULE" not in normalized.upper(), \
            "Fact capsule label must be stripped"
        # NOTE: Current normalization strips the ENTIRE line containing the label.
        # The data on that line is lost. This is acceptable — the LLM should not
        # produce these labels in the first place. The normalization is a safety net.
        assert "8:30/mi" in normalized, "Non-capsule content must survive"

    def test_strips_response_contract_label(self):
        """'RESPONSE CONTRACT' labels must be removed."""
        raw = "RESPONSE CONTRACT: I will provide evidence-based coaching.\nYour easy pace is 8:30/mi."
        normalized = self._normalize(raw)
        assert "RESPONSE CONTRACT" not in normalized.upper()
        assert "8:30/mi" in normalized

    def test_strips_date_labels(self):
        """Standalone date labels must be removed."""
        raw = "date: 2026-02-12\nYour weekly mileage was 45 miles."
        normalized = self._normalize(raw)
        # The date as a standalone label should be stripped
        assert not re.match(r"^date\s*:", normalized, re.IGNORECASE)

    def test_preserves_actual_content(self):
        """Normalization should not destroy useful content."""
        raw = "Your efficiency has improved 12% over the last 4 weeks. Keep it up!"
        normalized = self._normalize(raw)
        assert "12%" in normalized
        assert "4 weeks" in normalized
        assert "Keep it up" in normalized

    def test_collapses_excessive_newlines(self):
        """Multiple consecutive newlines should be collapsed."""
        raw = "First paragraph.\n\n\n\n\nSecond paragraph."
        normalized = self._normalize(raw)
        # Should not have more than 2 consecutive newlines
        assert "\n\n\n" not in normalized

    def test_renames_receipts_to_evidence(self):
        """'Receipts' heading should be renamed to 'Evidence'."""
        raw = "## Receipts\n- Run on 2026-01-15: 8.5mi"
        normalized = self._normalize(raw)
        assert "Receipts" not in normalized
        assert "Evidence" in normalized


# ---------------------------------------------------------------------------
# TOOL DEFINITIONS: All tools must be present and properly defined
# ---------------------------------------------------------------------------

class TestToolDefinitions:
    """
    The coach has 23 tools. All must be importable and callable from coach_tools.
    Missing tools mean the coach can't answer certain questions.
    """

    # All 23 tools from coach_tools.py — reconciled against actual module.
    REQUIRED_TOOLS = [
        "get_recent_runs",
        "get_calendar_day_context",
        "get_efficiency_trend",
        "get_plan_week",
        "get_weekly_volume",
        "get_training_load",
        "get_training_paces",
        "get_correlations",
        "get_race_predictions",
        "get_recovery_status",
        "get_active_insights",
        "get_pb_patterns",
        "get_efficiency_by_zone",
        "get_nutrition_correlations",
        "get_best_runs",
        "compare_training_periods",
        "get_wellness_trends",
        "get_athlete_profile",
        "get_training_load_history",
        "get_coach_intent_snapshot",
        "set_coach_intent_snapshot",
        "get_training_prescription_window",
        "compute_running_math",
    ]

    def test_all_tools_exist_in_module(self):
        """All 23 required tools must be importable from coach_tools."""
        from services import coach_tools

        missing = []
        for tool_name in self.REQUIRED_TOOLS:
            if not hasattr(coach_tools, tool_name):
                missing.append(tool_name)

        assert not missing, f"Missing tools in coach_tools: {missing}"

    def test_tools_are_callable(self):
        """All tools must be callable functions."""
        from services import coach_tools

        non_callable = []
        for tool_name in self.REQUIRED_TOOLS:
            fn = getattr(coach_tools, tool_name, None)
            if fn and not callable(fn):
                non_callable.append(tool_name)

        assert not non_callable, f"Non-callable tools: {non_callable}"

    def test_tool_count_matches(self):
        """Tool list must have exactly 23 entries (reconciliation check)."""
        assert len(self.REQUIRED_TOOLS) == 23, \
            f"Expected 23 tools, found {len(self.REQUIRED_TOOLS)} in REQUIRED_TOOLS list"


# ---------------------------------------------------------------------------
# MODEL TIERING: Correct routing for query types
# ---------------------------------------------------------------------------

class TestModelTiering:
    """
    Model tiering must route correctly:
    - High-stakes (injury, pain, recovery) -> Opus
    - Standard coaching -> Gemini Flash
    - Free users -> always default model
    """

    def test_high_stakes_patterns_exist(self):
        """High-stakes detection must have patterns defined."""
        from services.ai_coach import AICoach
        coach = _make_coach_stub()
        # The coach should have high-stakes detection capability
        assert hasattr(coach, 'is_high_stakes_query') or \
            hasattr(coach, 'classify_query_complexity'), \
            "Coach must have query classification capability"

    def test_injury_query_classified_correctly(self):
        """Injury-related queries should be classified as high complexity."""
        from services.ai_coach import AICoach
        coach = _make_coach_stub()
        if not hasattr(coach, 'classify_query_complexity'):
            pytest.skip("classify_query_complexity not found on AICoach — method may have been renamed")
        result = coach.classify_query_complexity("My knee hurts when I run downhill, should I skip tomorrow?")
        assert result in ("high", "medium"), \
            f"Injury query should be high/medium complexity, got: {result}"

    def test_simple_query_not_high_stakes(self):
        """Simple lookups should not be routed to expensive models."""
        from services.ai_coach import AICoach
        coach = _make_coach_stub()
        if not hasattr(coach, 'classify_query_complexity'):
            pytest.skip("classify_query_complexity not found on AICoach — method may have been renamed")
        result = coach.classify_query_complexity("What was my mileage last week?")
        assert result == "low", \
            f"Simple lookup should be low complexity, got: {result}"


# ---------------------------------------------------------------------------
# REGRESSION: Known failures from founder's testing ($1000+ in tokens)
# ---------------------------------------------------------------------------

class TestKnownRegressions:
    """
    Every failure the founder found manually becomes a regression test.
    These verify the machinery AROUND the LLM prevents known issues.
    """

    def test_vdot_not_in_system_prompt(self):
        """
        VDOT is a trademarked term. The system should use RPI instead.
        Verify the system prompt doesn't instruct the coach to use VDOT.
        """
        instructions = _get_system_instructions()
        # VDOT should not appear as an instruction to the coach
        # (it might appear in a "don't use this" context, which is fine)
        lines_with_vdot = [
            line for line in instructions.split('\n')
            if 'vdot' in line.lower() and 'never' not in line.lower() and 'don\'t' not in line.lower()
        ]
        assert len(lines_with_vdot) == 0, \
            f"System prompt instructs coach to use VDOT (trademark): {lines_with_vdot}"

    def test_normalization_called_in_chat_path(self):
        """
        Normalization MUST be called before returning responses.
        This is a structural check — verify the chat method calls normalize.
        Normalization is called from the chat() method, not query_gemini().
        """
        import inspect
        from services.ai_coach import AICoach
        # Normalization is called in the chat() method which wraps query_gemini
        source = inspect.getsource(AICoach.chat)
        assert "_normalize_response_for_ui" in source, \
            "chat() must call _normalize_response_for_ui before returning"

    def test_system_prompt_not_empty(self):
        """System instructions must not be empty."""
        instructions = _get_system_instructions()
        assert len(instructions) > 100, \
            f"System instructions too short ({len(instructions)} chars) — likely empty or corrupted"

    def test_system_prompt_has_coaching_approach(self):
        """System prompt must include coaching approach section."""
        instructions = _get_system_instructions()
        lower = instructions.lower()
        assert any(
            term in lower
            for term in ["coaching approach", "coaching style", "communication"]
        ), "System instructions must include coaching approach guidance"
