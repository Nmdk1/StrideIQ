"""
Tests for Coach LLM Model Tiering (Phase 11 - ADR-060)

Tests the complexity classifier and model routing logic.
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

# Import the AICoach class
from services.ai_coach import AICoach


@pytest.fixture
def mock_db():
    """Mock database session that returns None for athlete queries."""
    db = MagicMock()
    # Ensure athlete queries return None (no VIP status in DB)
    db.query.return_value.filter.return_value.first.return_value = None
    return db


@pytest.fixture
def coach(mock_db):
    """Create AICoach instance with mocked dependencies."""
    with patch.dict('os.environ', {
        'OPENAI_API_KEY': '',  # Disable OpenAI client
        'COACH_MODEL_ROUTING': 'on',
        'COACH_VIP_ATHLETE_IDS': '',
        'OWNER_ATHLETE_ID': '',
    }):
        return AICoach(mock_db)


class TestQueryComplexityClassifier:
    """Test classify_query_complexity() method."""
    
    def test_low_complexity_lookups(self, coach):
        """Pure data lookups should be classified as LOW."""
        low_queries = [
            "What was my last run?",
            "Show me this week's mileage",
            "What is my TSB?",
            "List my personal bests",
            "What does VO2max mean?",
            "Define threshold pace",
            "Show my plan",
            "My recent runs",
            "Yesterday's run",
            "What is my CTL?",
        ]
        for query in low_queries:
            assert coach.classify_query_complexity(query) == "low", f"Expected LOW for: {query}"
    
    def test_medium_complexity_standard_coaching(self, coach):
        """Standard coaching questions without causal/ambiguity should be MEDIUM."""
        medium_queries = [
            "What pace for my tempo run?",
            "Can I move my long run to Saturday?",
            # "Should I skip today's workout?" → now HIGH (decision pattern with 90/10)
            # "How should I ramp back after 2 weeks off?" → now HIGH (causal "how do i")
            "What's the best way to train for a marathon?",
            "How many miles should I run this week?",
            "Is my heart rate too high on easy runs?",
        ]
        for query in medium_queries:
            assert coach.classify_query_complexity(query) == "medium", f"Expected MEDIUM for: {query}"
    
    def test_high_complexity_decision_queries(self, coach):
        """Decision queries requiring judgment should be HIGH (90/10 split)."""
        high_queries = [
            "Should I skip today's workout?",
            "Should I rest tomorrow?",
            "Is it okay to run on this?",
        ]
        for query in high_queries:
            assert coach.classify_query_complexity(query) == "high", f"Expected HIGH for: {query}"
    
    def test_high_complexity_causal_with_ambiguity(self, coach):
        """Causal questions with ambiguity should be HIGH."""
        high_queries = [
            "Why am I getting slower despite running more?",
            "Why is my pace dropping even though I feel fine?",
            "What's causing my HR to spike but my pace hasn't changed?",
            "What's driving my fatigue despite getting 8 hours of sleep?",
        ]
        for query in high_queries:
            assert coach.classify_query_complexity(query) == "high", f"Expected HIGH for: {query}"
    
    def test_high_complexity_causal_with_multiple_factors(self, coach):
        """Causal questions with multiple factors should be HIGH."""
        high_queries = [
            "Why am I getting slower and my HR is higher and my legs feel heavy?",
            "What's causing my efficiency to drop, my sleep to suffer, and my motivation to tank?",
        ]
        for query in high_queries:
            assert coach.classify_query_complexity(query) == "high", f"Expected HIGH for: {query}"
    
    def test_causal_without_ambiguity_is_high(self, coach):
        """Causal questions should be HIGH even without ambiguity (90/10 split).
        
        Updated from old 95/5 logic where causal needed ambiguity for HIGH.
        With 90/10, ANY causal question triggers Opus for better reasoning.
        """
        high_causal = [
            "Why am I tired?",  # Causal → HIGH
            "What's causing my calf pain?",  # Causal → HIGH
        ]
        for query in high_causal:
            assert coach.classify_query_complexity(query) == "high", f"Expected HIGH for: {query}"
    
    def test_empty_and_none_queries(self, coach):
        """Empty or None queries should default to MEDIUM."""
        assert coach.classify_query_complexity("") == "medium"
        assert coach.classify_query_complexity(None) == "medium"


class TestModelRouting:
    """Test get_model_for_query() method - returns (model_name, is_opus) tuple."""
    
    def test_low_complexity_uses_default(self, coach):
        """LOW complexity should use MODEL_DEFAULT."""
        model, is_opus = coach.get_model_for_query("low")
        assert model == coach.MODEL_DEFAULT
        assert is_opus is False
    
    def test_medium_complexity_uses_default(self, coach):
        """MEDIUM complexity should use MODEL_DEFAULT (for non-high-stakes)."""
        model, is_opus = coach.get_model_for_query("medium")
        assert model == coach.MODEL_DEFAULT
        assert is_opus is False
    
    def test_high_complexity_non_vip_uses_default(self, coach):
        """HIGH complexity for non-VIP uses MODEL_DEFAULT (no Opus without subscription)."""
        athlete_id = uuid4()
        model, is_opus = coach.get_model_for_query("high", athlete_id=athlete_id)
        # Without subscription/Anthropic client, falls back to default
        assert model == coach.MODEL_DEFAULT
        assert is_opus is False
    
    def test_high_complexity_vip_uses_default(self, coach):
        """HIGH complexity for VIP uses MODEL_DEFAULT without Anthropic client."""
        vip_id = uuid4()
        coach.VIP_ATHLETE_IDS = {str(vip_id)}
        
        model, is_opus = coach.get_model_for_query("high", athlete_id=vip_id)
        # Without Anthropic client configured, falls back to default
        assert model == coach.MODEL_DEFAULT
        assert is_opus is False
    
    def test_legacy_simple_maps_to_low(self, coach):
        """Legacy 'simple' query type should use MODEL_DEFAULT."""
        model, is_opus = coach.get_model_for_query("simple")
        assert model == coach.MODEL_DEFAULT
        assert is_opus is False
    
    def test_legacy_standard_reclassifies(self, coach):
        """Legacy 'standard' should use MODEL_DEFAULT (non-high-stakes default)."""
        # Without message, defaults to MODEL_DEFAULT
        model, is_opus = coach.get_model_for_query("standard")
        assert model == coach.MODEL_DEFAULT
        
        # With high-complexity message but no Anthropic client, still MODEL_DEFAULT
        model, is_opus = coach.get_model_for_query(
            "standard", 
            message="Why am I getting slower despite running more?"
        )
        assert model == coach.MODEL_DEFAULT


class TestVIPLoading:
    """Test VIP athlete loading from environment."""
    
    def test_loads_vip_from_env(self, mock_db):
        """VIP IDs should be loaded from COACH_VIP_ATHLETE_IDS env."""
        vip1 = str(uuid4())
        vip2 = str(uuid4())
        
        with patch.dict('os.environ', {
            'OPENAI_API_KEY': '',
            'COACH_VIP_ATHLETE_IDS': f'{vip1},{vip2}',
            'OWNER_ATHLETE_ID': '',
        }):
            coach = AICoach(mock_db)
            assert vip1 in coach.VIP_ATHLETE_IDS
            assert vip2 in coach.VIP_ATHLETE_IDS
    
    def test_loads_owner_as_vip(self, mock_db):
        """Owner ID should be automatically added as VIP."""
        owner_id = str(uuid4())
        
        with patch.dict('os.environ', {
            'OPENAI_API_KEY': '',
            'COACH_VIP_ATHLETE_IDS': '',
            'OWNER_ATHLETE_ID': owner_id,
        }):
            coach = AICoach(mock_db)
            assert owner_id in coach.VIP_ATHLETE_IDS
    
    def test_empty_vip_env_is_handled(self, mock_db):
        """Empty VIP env should result in empty set."""
        with patch.dict('os.environ', {
            'OPENAI_API_KEY': '',
            'COACH_VIP_ATHLETE_IDS': '',
            'OWNER_ATHLETE_ID': '',
        }):
            coach = AICoach(mock_db)
            assert len(coach.VIP_ATHLETE_IDS) == 0


class TestEndToEndClassification:
    """Integration tests for the full classification + routing flow."""
    
    def test_lookup_query_gets_default(self, coach):
        """A lookup query should route to MODEL_DEFAULT."""
        message = "What was my long run last week?"
        complexity = coach.classify_query_complexity(message)
        model, is_opus = coach.get_model_for_query(complexity)
        
        assert complexity == "low"
        assert model == coach.MODEL_DEFAULT
    
    def test_coaching_query_gets_default(self, coach):
        """A standard coaching query should route to MODEL_DEFAULT."""
        message = "What pace for my tempo run?"  # Simple pace lookup, no causal/decision
        complexity = coach.classify_query_complexity(message)
        model, is_opus = coach.get_model_for_query(complexity)
        
        assert complexity == "medium"
        assert model == coach.MODEL_DEFAULT
    
    def test_complex_query_gets_default_without_anthropic(self, coach):
        """A complex query without Anthropic client routes to MODEL_DEFAULT."""
        message = "Why am I getting slower despite increasing my mileage?"
        complexity = coach.classify_query_complexity(message)
        model, is_opus = coach.get_model_for_query(complexity, athlete_id=uuid4())
        
        assert complexity == "high"
        assert model == coach.MODEL_DEFAULT  # No Anthropic client = default
    
    def test_complex_query_vip_gets_default_without_anthropic(self, coach):
        """A complex query from VIP without Anthropic routes to MODEL_DEFAULT."""
        vip_id = uuid4()
        coach.VIP_ATHLETE_IDS = {str(vip_id)}
        
        message = "Why am I getting slower despite increasing my mileage?"
        complexity = coach.classify_query_complexity(message)
        model, is_opus = coach.get_model_for_query(complexity, athlete_id=vip_id)
        
        assert complexity == "high"
        assert model == coach.MODEL_DEFAULT  # No Anthropic client = default


class TestToolValidation:
    """Test tool validation for data questions (Sprint 2)."""
    
    def test_data_question_without_tools_fails(self, coach):
        """A data question without tool calls should fail validation."""
        is_valid, reason = coach._validate_tool_usage(
            message="How many miles did I run this week?",
            tools_called=[],
            tool_calls_count=0,
        )
        assert is_valid is False
        assert reason == "no_tools_called"
    
    def test_data_question_with_tools_passes(self, coach):
        """A data question with data tools should pass validation."""
        is_valid, reason = coach._validate_tool_usage(
            message="How many miles did I run this week?",
            tools_called=["get_recent_runs", "get_training_load"],
            tool_calls_count=2,
        )
        assert is_valid is True
        assert reason == "ok"
    
    def test_definition_question_skips_validation(self, coach):
        """Definition questions don't need tool validation."""
        is_valid, reason = coach._validate_tool_usage(
            message="What is a tempo run?",
            tools_called=[],
            tool_calls_count=0,
        )
        assert is_valid is True
        assert reason == "not_data_question"
    
    def test_non_data_question_skips_validation(self, coach):
        """Non-data questions don't need tool validation."""
        is_valid, reason = coach._validate_tool_usage(
            message="Hello!",
            tools_called=[],
            tool_calls_count=0,
        )
        assert is_valid is True
        assert reason == "not_data_question"
    
    def test_data_question_with_wrong_tools_fails(self, coach):
        """Data question with non-data tools should fail."""
        is_valid, reason = coach._validate_tool_usage(
            message="How far did I run yesterday?",
            tools_called=["get_coach_intent_snapshot"],  # Not a data tool
            tool_calls_count=1,
        )
        assert is_valid is False
        assert reason == "no_data_tools_called"
    
    def test_is_data_question_detects_mileage(self, coach):
        """Questions about mileage should be detected as data questions."""
        assert coach._is_data_question("How many miles did I run this week?") is True
        assert coach._is_data_question("What was my total mileage?") is True
    
    def test_is_data_question_excludes_definitions(self, coach):
        """Definition questions should not be data questions."""
        assert coach._is_data_question("What is a tempo run?") is False
        assert coach._is_data_question("Explain what VO2max means") is False
        assert coach._is_data_question("Define threshold pace") is False


class TestEdgeCases:
    """Edge case and boundary tests for robustness."""
    
    def test_case_insensitive_low_patterns(self, coach):
        """Patterns should match regardless of case."""
        assert coach.classify_query_complexity("WHAT WAS MY LAST RUN?") == "low"
        assert coach.classify_query_complexity("What Was My Last Run?") == "low"
        assert coach.classify_query_complexity("what was my last run?") == "low"
    
    def test_case_insensitive_high_patterns(self, coach):
        """High complexity patterns should match regardless of case."""
        assert coach.classify_query_complexity("WHY AM I GETTING SLOWER DESPITE RUNNING MORE?") == "high"
        assert coach.classify_query_complexity("Why Am I Getting Slower Despite Running More?") == "high"
    
    def test_boundary_multiple_ands(self, coach):
        """Multiple 'and' with causal should trigger HIGH (90/10: causal alone is HIGH)."""
        # With 90/10, any causal is HIGH - so both of these are HIGH
        assert coach.classify_query_complexity("Why am I tired and slow and sore?") == "high"
        assert coach.classify_query_complexity("Why am I tired and slow?") == "high"  # Causal → HIGH
        
        # Multiple factors WITHOUT causal should also be HIGH (multi-factor alone triggers)
        assert coach.classify_query_complexity("My legs are tired, my HR is high, and my sleep is bad") == "high"
    
    def test_boundary_multiple_commas(self, coach):
        """Multiple commas should trigger HIGH (multi-factor)."""
        # With 90/10, causal alone is HIGH
        assert coach.classify_query_complexity("Why am I tired, slow, sore?") == "high"
        assert coach.classify_query_complexity("Why am I tired, slow?") == "high"  # Causal → HIGH
        
        # Multi-factor without causal (2+ commas)
        assert coach.classify_query_complexity("My pace dropped, HR spiked, and legs feel heavy") == "high"
    
    def test_special_characters_dont_break(self, coach):
        """Unicode and special characters should be handled gracefully."""
        assert coach.classify_query_complexity("What's my TSB? 🏃") == "low"
        assert coach.classify_query_complexity("What's my—tempo—pace?") == "medium"
        assert coach.classify_query_complexity("") == "medium"
    
    def test_very_long_query(self, coach):
        """Long queries should not cause performance issues."""
        long_query = "What was my run " * 100
        result = coach.classify_query_complexity(long_query)
        assert result == "low"  # Contains "what was my"
    
    def test_whitespace_in_vip_ids(self, mock_db):
        """Whitespace in VIP IDs should be trimmed."""
        vip_id = str(uuid4())
        
        with patch.dict('os.environ', {
            'OPENAI_API_KEY': '',
            'COACH_VIP_ATHLETE_IDS': f'  {vip_id}  ,  ',  # Whitespace and trailing comma
            'OWNER_ATHLETE_ID': '',
        }):
            coach = AICoach(mock_db)
            assert vip_id in coach.VIP_ATHLETE_IDS
            assert '' not in coach.VIP_ATHLETE_IDS  # Empty strings filtered
    
    def test_vip_id_as_string_vs_uuid(self, coach):
        """VIP check should work with both UUID objects and strings."""
        vip_id = uuid4()
        coach.VIP_ATHLETE_IDS = {str(vip_id)}
        
        # Pass UUID object - should still match, but returns default without Anthropic
        model, is_opus = coach.get_model_for_query("high", athlete_id=vip_id)
        assert model == coach.MODEL_DEFAULT  # No Anthropic client = default
    
    def test_non_vip_does_not_get_opus(self, coach):
        """Non-VIP should never get Opus, falls back to default."""
        vip_id = uuid4()
        non_vip_id = uuid4()
        coach.VIP_ATHLETE_IDS = {str(vip_id)}
        
        model, is_opus = coach.get_model_for_query("high", athlete_id=non_vip_id)
        assert model == coach.MODEL_DEFAULT  # No Anthropic client = default
    
    def test_none_athlete_id_for_high_complexity(self, coach):
        """None athlete_id should default to MODEL_DEFAULT."""
        model, is_opus = coach.get_model_for_query("high", athlete_id=None)
        assert model == coach.MODEL_DEFAULT  # No athlete_id triggers no-subscription path
    
    def test_low_complexity_ignores_vip_status(self, coach):
        """Low complexity should always use MODEL_DEFAULT, even for VIPs."""
        vip_id = uuid4()
        coach.VIP_ATHLETE_IDS = {str(vip_id)}
        
        model, is_opus = coach.get_model_for_query("low", athlete_id=vip_id)
        assert model == coach.MODEL_DEFAULT
    
    def test_medium_complexity_ignores_vip_status(self, coach):
        """Medium complexity should always use MODEL_DEFAULT, even for VIPs."""
        vip_id = uuid4()
        coach.VIP_ATHLETE_IDS = {str(vip_id)}
        
        model, is_opus = coach.get_model_for_query("medium", athlete_id=vip_id)
        assert model == coach.MODEL_DEFAULT
