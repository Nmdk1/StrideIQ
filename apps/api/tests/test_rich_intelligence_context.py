"""
Tests for _build_rich_intelligence_context() in routers/home.py.

Covers:
1. N=1 insights appear in output
2. Function survives N=1 failure (non-blocking)
3. Daily intelligence rules (non-LOG) appear in output
4. All sources empty → returns ""
5. Opus is tried first when ANTHROPIC_API_KEY is set
"""
import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch
from uuid import UUID


# ---------------------------------------------------------------------------
# Shared helpers / minimal stubs
# ---------------------------------------------------------------------------

def _make_db():
    return MagicMock()


def _athlete_id():
    return "4368ec7f-c30d-45ff-a6ee-58db7716be24"


# ---------------------------------------------------------------------------
# 1. N=1 insights appear in output
# ---------------------------------------------------------------------------

class TestRichContextN1Insights:
    def test_rich_context_includes_n1_insights(self):
        """N=1 insight text and confidence appear under Personal Patterns header."""
        from routers.home import _build_rich_intelligence_context
        from services.n1_insight_generator import N1Insight

        insights = [
            N1Insight(text="Sleep > 7h correlates with faster pacing next day", confidence=0.82),
            N1Insight(text="Higher easy-run volume precedes efficiency gains", confidence=0.71),
            N1Insight(text="Midweek rest improves weekend long run HR", confidence=0.65),
        ]

        with patch("services.n1_insight_generator.generate_n1_insights", return_value=insights), \
             patch("services.daily_intelligence.DailyIntelligenceEngine") as mock_engine, \
             patch("services.coach_tools.get_wellness_trends", return_value={"narrative": ""}), \
             patch("services.coach_tools.get_pb_patterns", return_value={"narrative": ""}), \
             patch("services.coach_tools.compare_training_periods", return_value={"narrative": ""}):

            mock_engine.return_value.evaluate.return_value = MagicMock(insights=[])
            result = _build_rich_intelligence_context(_athlete_id(), _make_db())

        assert "Personal Patterns" in result
        assert "Sleep > 7h correlates with faster pacing next day" in result
        assert "Higher easy-run volume precedes efficiency gains" in result
        assert "Midweek rest improves weekend long run HR" in result
        assert "0.82" in result
        assert "0.71" in result
        assert "0.65" in result
        assert "DEEP INTELLIGENCE" in result


# ---------------------------------------------------------------------------
# 2. Function survives N=1 failure (non-blocking)
# ---------------------------------------------------------------------------

class TestRichContextN1Failure:
    def test_rich_context_survives_n1_failure(self):
        """If generate_n1_insights raises, function continues and returns other data."""
        from routers.home import _build_rich_intelligence_context
        from services.daily_intelligence import InsightMode

        mock_insight = MagicMock()
        mock_insight.rule_id = "LOAD_SPIKE"
        mock_insight.mode = InsightMode.INFORM
        mock_insight.message = "Weekly load jumped 32% — keep today easy."

        mock_result = MagicMock()
        mock_result.insights = [mock_insight]

        with patch("services.n1_insight_generator.generate_n1_insights", side_effect=Exception("DB timeout")), \
             patch("services.daily_intelligence.DailyIntelligenceEngine") as mock_engine, \
             patch("services.coach_tools.get_wellness_trends", return_value={"narrative": "Sleep avg 6.8h (trend: stable)."}), \
             patch("services.coach_tools.get_pb_patterns", return_value={"narrative": ""}), \
             patch("services.coach_tools.compare_training_periods", return_value={"narrative": ""}):

            mock_engine.return_value.evaluate.return_value = mock_result
            result = _build_rich_intelligence_context(_athlete_id(), _make_db())

        # Must not raise; must return a string
        assert isinstance(result, str)
        # Other sources should still appear
        assert "LOAD_SPIKE" in result or "Sleep avg 6.8h" in result


# ---------------------------------------------------------------------------
# 3. Daily intelligence rules appear in output
# ---------------------------------------------------------------------------

class TestRichContextDailyIntelligence:
    def test_rich_context_includes_daily_intelligence(self):
        """INFORM-mode rules appear under Today's Intelligence Rules header."""
        from routers.home import _build_rich_intelligence_context
        from services.daily_intelligence import InsightMode

        def _mock_insight(rule_id, mode, message):
            m = MagicMock()
            m.rule_id = rule_id
            m.mode = mode
            m.message = message
            return m

        inform1 = _mock_insight("PACE_IMPROVEMENT", InsightMode.INFORM, "Pace at effort improved 4% vs 4-week avg.")
        inform2 = _mock_insight("LOAD_SPIKE", InsightMode.INFORM, "Weekly load jumped 28% — consider recovery priority.")
        log_insight = _mock_insight("ACTIVITY_LOGGED", InsightMode.LOG, "Activity recorded.")

        mock_result = MagicMock()
        mock_result.insights = [inform1, inform2, log_insight]

        with patch("services.n1_insight_generator.generate_n1_insights", return_value=[]), \
             patch("services.daily_intelligence.DailyIntelligenceEngine") as mock_engine, \
             patch("services.coach_tools.get_wellness_trends", return_value={"narrative": ""}), \
             patch("services.coach_tools.get_pb_patterns", return_value={"narrative": ""}), \
             patch("services.coach_tools.compare_training_periods", return_value={"narrative": ""}):

            mock_engine.return_value.evaluate.return_value = mock_result
            result = _build_rich_intelligence_context(_athlete_id(), _make_db())

        assert "Today's Intelligence Rules" in result
        assert "PACE_IMPROVEMENT" in result
        assert "Pace at effort improved 4% vs 4-week avg." in result
        assert "LOAD_SPIKE" in result
        assert "Weekly load jumped 28% — consider recovery priority." in result
        # LOG insights must NOT appear
        assert "ACTIVITY_LOGGED" not in result
        assert "Activity recorded." not in result


# ---------------------------------------------------------------------------
# 4. All sources empty → returns ""
# ---------------------------------------------------------------------------

class TestRichContextAllEmpty:
    def test_rich_context_all_sources_empty(self):
        """When all five sources return empty data, function returns empty string."""
        from routers.home import _build_rich_intelligence_context

        mock_result = MagicMock()
        mock_result.insights = []

        with patch("services.n1_insight_generator.generate_n1_insights", return_value=[]), \
             patch("services.daily_intelligence.DailyIntelligenceEngine") as mock_engine, \
             patch("services.coach_tools.get_wellness_trends", return_value={"narrative": "No wellness data available."}), \
             patch("services.coach_tools.get_pb_patterns", return_value={"narrative": ""}), \
             patch("services.coach_tools.compare_training_periods", return_value={"narrative": ""}):

            mock_engine.return_value.evaluate.return_value = mock_result
            result = _build_rich_intelligence_context(_athlete_id(), _make_db())

        assert result == ""


# ---------------------------------------------------------------------------
# 5. Opus is primary model when ANTHROPIC_API_KEY is set
# ---------------------------------------------------------------------------

class TestOpusPrimaryModel:
    def test_opus_is_primary_model_when_key_set(self):
        """_call_llm_for_briefing tries Opus first when ANTHROPIC_API_KEY is set."""
        import os
        from tasks.home_briefing_tasks import _call_llm_for_briefing

        dummy_result = {"morning_voice": "Test output", "coach_noticed": "Test noticed"}

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-abc"}), \
             patch("tasks.home_briefing_tasks._call_opus_briefing", return_value=dummy_result) as mock_opus, \
             patch("tasks.home_briefing_tasks._call_gemini_briefing") as mock_gemini:

            result = _call_llm_for_briefing("prompt", {}, [])

        # Opus must have been called
        mock_opus.assert_called_once()
        # Gemini must NOT have been called (Opus succeeded)
        mock_gemini.assert_not_called()
        assert result == dummy_result

    def test_gemini_fallback_when_opus_fails(self):
        """_call_llm_for_briefing falls back to Gemini if Opus returns None."""
        import os
        from tasks.home_briefing_tasks import _call_llm_for_briefing

        gemini_result = {"morning_voice": "Gemini output", "coach_noticed": "Gemini noticed"}

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-abc"}), \
             patch("tasks.home_briefing_tasks._call_opus_briefing", return_value=None), \
             patch("tasks.home_briefing_tasks._call_gemini_briefing", return_value=gemini_result) as mock_gemini:

            result = _call_llm_for_briefing("prompt", {}, [])

        mock_gemini.assert_called_once()
        assert result == gemini_result
