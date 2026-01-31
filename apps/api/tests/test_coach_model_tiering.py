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
    """Mock database session."""
    return MagicMock()


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
        """Standard coaching questions should be MEDIUM."""
        medium_queries = [
            "What pace for my tempo run?",
            "Can I move my long run to Saturday?",
            "Should I skip today's workout?",
            "How should I ramp back after 2 weeks off?",
            "What's the best way to train for a marathon?",
            "How many miles should I run this week?",
            "Is my heart rate too high on easy runs?",
        ]
        for query in medium_queries:
            assert coach.classify_query_complexity(query) == "medium", f"Expected MEDIUM for: {query}"
    
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
    
    def test_causal_without_ambiguity_is_medium(self, coach):
        """Causal questions without ambiguity signals should be MEDIUM (Sonnet handles)."""
        medium_causal = [
            "Why am I tired?",  # Simple causal, no ambiguity
            "What's causing my calf pain?",  # Single factor
        ]
        for query in medium_causal:
            assert coach.classify_query_complexity(query) == "medium", f"Expected MEDIUM for: {query}"
    
    def test_empty_and_none_queries(self, coach):
        """Empty or None queries should default to MEDIUM."""
        assert coach.classify_query_complexity("") == "medium"
        assert coach.classify_query_complexity(None) == "medium"


class TestModelRouting:
    """Test get_model_for_query() method."""
    
    def test_low_complexity_uses_nano(self, coach):
        """LOW complexity should use gpt-5-nano."""
        model = coach.get_model_for_query("low")
        assert model == "gpt-5-nano"
    
    def test_medium_complexity_uses_mini(self, coach):
        """MEDIUM complexity should use gpt-5-mini."""
        model = coach.get_model_for_query("medium")
        assert model == "gpt-5-mini"
    
    def test_high_complexity_non_vip_uses_5_1(self, coach):
        """HIGH complexity for non-VIP should use gpt-5.1."""
        athlete_id = uuid4()
        model = coach.get_model_for_query("high", athlete_id=athlete_id)
        assert model == "gpt-5.1"
    
    def test_high_complexity_vip_uses_5_2(self, coach):
        """HIGH complexity for VIP should use gpt-5.2."""
        vip_id = uuid4()
        coach.VIP_ATHLETE_IDS = {str(vip_id)}
        
        model = coach.get_model_for_query("high", athlete_id=vip_id)
        assert model == "gpt-5.2"
    
    def test_legacy_simple_maps_to_low(self, coach):
        """Legacy 'simple' query type should use MODEL_LOW."""
        model = coach.get_model_for_query("simple")
        assert model == "gpt-5-nano"
    
    def test_legacy_standard_reclassifies(self, coach):
        """Legacy 'standard' should reclassify based on message."""
        # Without message, defaults to MEDIUM
        model = coach.get_model_for_query("standard")
        assert model == "gpt-5-mini"
        
        # With high-complexity message
        model = coach.get_model_for_query(
            "standard", 
            message="Why am I getting slower despite running more?"
        )
        assert model == "gpt-5.1"


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
    
    def test_lookup_query_gets_nano(self, coach):
        """A lookup query should route to gpt-5-nano."""
        message = "What was my long run last week?"
        complexity = coach.classify_query_complexity(message)
        model = coach.get_model_for_query(complexity)
        
        assert complexity == "low"
        assert model == "gpt-5-nano"
    
    def test_coaching_query_gets_mini(self, coach):
        """A standard coaching query should route to gpt-5-mini."""
        message = "What pace should I run my tempo at?"
        complexity = coach.classify_query_complexity(message)
        model = coach.get_model_for_query(complexity)
        
        assert complexity == "medium"
        assert model == "gpt-5-mini"
    
    def test_complex_query_gets_5_1(self, coach):
        """A complex query should route to gpt-5.1."""
        message = "Why am I getting slower despite increasing my mileage?"
        complexity = coach.classify_query_complexity(message)
        model = coach.get_model_for_query(complexity, athlete_id=uuid4())
        
        assert complexity == "high"
        assert model == "gpt-5.1"
    
    def test_complex_query_vip_gets_5_2(self, coach):
        """A complex query from VIP should route to gpt-5.2."""
        vip_id = uuid4()
        coach.VIP_ATHLETE_IDS = {str(vip_id)}
        
        message = "Why am I getting slower despite increasing my mileage?"
        complexity = coach.classify_query_complexity(message)
        model = coach.get_model_for_query(complexity, athlete_id=vip_id)
        
        assert complexity == "high"
        assert model == "gpt-5.2"
