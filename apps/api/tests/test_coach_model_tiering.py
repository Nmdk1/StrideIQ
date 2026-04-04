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
    """Test get_model_for_query() — universal Kimi K2.5 routing (Apr 2026)."""

    def test_all_queries_route_to_premium(self, coach):
        """Every query routes to MODEL_HIGH_STAKES (Kimi K2.5 path)."""
        for qt in ("low", "medium", "high", "simple", "standard"):
            model, is_premium = coach.get_model_for_query(qt)
            assert model == coach.MODEL_HIGH_STAKES, f"query_type={qt}"
            assert is_premium is True, f"query_type={qt}"

    def test_founder_routes_to_premium(self, mock_db):
        """Founder always routes to premium."""
        owner_id = uuid4()
        with patch.dict('os.environ', {
            'OWNER_ATHLETE_ID': str(owner_id),
            'COACH_MODEL_ROUTING': 'on',
        }):
            coach = AICoach(mock_db)
            model, is_premium = coach.get_model_for_query("low", athlete_id=owner_id)
            assert model == coach.MODEL_HIGH_STAKES
            assert is_premium is True


class TestVIPLoading:
    """Test VIP athlete loading from environment."""
    
    def test_loads_vip_from_env(self, mock_db):
        """VIP IDs should be loaded from COACH_VIP_ATHLETE_IDS env."""
        vip1 = str(uuid4())
        vip2 = str(uuid4())
        
        with patch.dict('os.environ', {
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
            'COACH_VIP_ATHLETE_IDS': '',
            'OWNER_ATHLETE_ID': owner_id,
        }):
            coach = AICoach(mock_db)
            assert owner_id in coach.VIP_ATHLETE_IDS
    
    def test_empty_vip_env_is_handled(self, mock_db):
        """Empty VIP env should result in empty set."""
        with patch.dict('os.environ', {
            'COACH_VIP_ATHLETE_IDS': '',
            'OWNER_ATHLETE_ID': '',
        }):
            coach = AICoach(mock_db)
            assert len(coach.VIP_ATHLETE_IDS) == 0


class TestEndToEndClassification:
    """Integration tests for the full classification + routing flow."""

    def test_all_complexities_route_to_kimi(self, coach):
        """Every complexity level now routes to premium (Kimi K2.5)."""
        for msg, expected_complexity in [
            ("What was my long run last week?", "low"),
            ("What pace for my tempo run?", "medium"),
            ("Why am I getting slower despite increasing my mileage?", "high"),
        ]:
            complexity = coach.classify_query_complexity(msg)
            model, is_premium = coach.get_model_for_query(complexity, athlete_id=uuid4())
            assert complexity == expected_complexity
            assert model == coach.MODEL_HIGH_STAKES
            assert is_premium is True

    def test_vip_routes_to_premium(self, mock_db):
        """VIP always routes to premium (Kimi K2.5)."""
        vip_id = uuid4()
        with patch.dict('os.environ', {
            'COACH_VIP_ATHLETE_IDS': str(vip_id),
            'COACH_MODEL_ROUTING': 'on',
            'OWNER_ATHLETE_ID': '',
        }):
            coach = AICoach(mock_db)
            model, is_premium = coach.get_model_for_query("high", athlete_id=vip_id)
            assert model == coach.MODEL_HIGH_STAKES
            assert is_premium is True


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
            'COACH_VIP_ATHLETE_IDS': f'  {vip_id}  ,  ',  # Whitespace and trailing comma
            'OWNER_ATHLETE_ID': '',
        }):
            coach = AICoach(mock_db)
            assert vip_id in coach.VIP_ATHLETE_IDS
            assert '' not in coach.VIP_ATHLETE_IDS  # Empty strings filtered
    
    def test_vip_id_as_string_vs_uuid(self, mock_db):
        """VIP check should work with both UUID objects and strings."""
        vip_id = uuid4()
        with patch.dict('os.environ', {
            'COACH_VIP_ATHLETE_IDS': str(vip_id),
            'COACH_MODEL_ROUTING': 'on',
            'OWNER_ATHLETE_ID': '',
        }):
            coach = AICoach(mock_db)
            model, is_premium = coach.get_model_for_query("high", athlete_id=vip_id)
            assert model == coach.MODEL_HIGH_STAKES
    
    def test_non_vip_still_routes_to_kimi(self, coach):
        """Non-VIP routes to Kimi (universal routing)."""
        non_vip_id = uuid4()
        model, is_premium = coach.get_model_for_query("high", athlete_id=non_vip_id)
        assert model == coach.MODEL_HIGH_STAKES

    def test_none_athlete_id_routes_to_kimi(self, coach):
        """None athlete_id routes to Kimi (universal routing)."""
        model, is_premium = coach.get_model_for_query("high", athlete_id=None)
        assert model == coach.MODEL_HIGH_STAKES
    
    def test_vip_always_routes_opus_regardless_of_complexity(self, mock_db):
        """VIP athletes get Opus for ALL queries, not just high-stakes."""
        vip_id = uuid4()
        with patch.dict('os.environ', {
            'COACH_VIP_ATHLETE_IDS': str(vip_id),
            'COACH_MODEL_ROUTING': 'on',
            'OWNER_ATHLETE_ID': '',
        }):
            coach = AICoach(mock_db)
            coach.anthropic_client = MagicMock()

            model, is_opus = coach.get_model_for_query("low", athlete_id=vip_id, message="how was my week?")
            assert is_opus is True
            assert model == coach.MODEL_HIGH_STAKES

    def test_founder_always_routes_opus(self, mock_db):
        """Founder gets Opus for ALL queries, not just high-stakes."""
        founder_id = uuid4()
        with patch.dict('os.environ', {
            'OWNER_ATHLETE_ID': str(founder_id),
            'COACH_MODEL_ROUTING': 'on',
        }):
            coach = AICoach(mock_db)
            coach.anthropic_client = MagicMock()

            model, is_opus = coach.get_model_for_query("low", athlete_id=founder_id, message="how was my week?")
            assert is_opus is True
            assert model == coach.MODEL_HIGH_STAKES

    def test_standard_user_routes_to_kimi(self, mock_db):
        """Non-founder, non-VIP users also route to Kimi (universal routing)."""
        random_id = uuid4()
        with patch.dict('os.environ', {
            'OWNER_ATHLETE_ID': '',
            'COACH_VIP_ATHLETE_IDS': '',
            'COACH_MODEL_ROUTING': 'on',
        }):
            coach = AICoach(mock_db)
            model, is_premium = coach.get_model_for_query("low", athlete_id=random_id, message="how was my week?")
            assert is_premium is True
            assert model == coach.MODEL_HIGH_STAKES
