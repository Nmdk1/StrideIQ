"""
Tests for ADR-061: Hybrid Model Architecture with Cost Caps

Tests the high-stakes classifier and budget checking logic.
"""
import pytest
from datetime import date
from uuid import uuid4

# Import the classifier function directly (doesn't need DB)
import sys
sys.path.insert(0, '..')


class TestHighStakesClassifier:
    """Test the is_high_stakes_query function."""
    
    def test_injury_patterns_detected(self):
        """Injury-related queries should be high-stakes."""
        from services.ai_coach import is_high_stakes_query
        
        assert is_high_stakes_query("my knee hurts") is True
        assert is_high_stakes_query("I have pain in my shin") is True
        assert is_high_stakes_query("feeling some soreness in my calf") is True
        assert is_high_stakes_query("I think I have a stress fracture") is True
        assert is_high_stakes_query("my achilles is tender") is True
    
    def test_return_from_break_patterns_detected(self):
        """Return-from-break queries should be high-stakes."""
        from services.ai_coach import is_high_stakes_query
        
        assert is_high_stakes_query("I'm coming back from injury") is True
        assert is_high_stakes_query("this is my first run back") is True
        assert is_high_stakes_query("returning from time off") is True
        assert is_high_stakes_query("after illness, should I run?") is True
    
    def test_load_decision_patterns_detected(self):
        """Load adjustment queries should be high-stakes."""
        from services.ai_coach import is_high_stakes_query
        
        assert is_high_stakes_query("should I skip my run today?") is True
        assert is_high_stakes_query("is it safe to run?") is True
        assert is_high_stakes_query("should I reduce mileage?") is True
        assert is_high_stakes_query("can I push through this?") is True
    
    def test_normal_queries_not_high_stakes(self):
        """Normal coaching queries should NOT be high-stakes."""
        from services.ai_coach import is_high_stakes_query
        
        assert is_high_stakes_query("what was my pace yesterday?") is False
        assert is_high_stakes_query("show me my weekly mileage") is False
        assert is_high_stakes_query("how is my fitness trending?") is False
        assert is_high_stakes_query("what should my long run be this week?") is False
        assert is_high_stakes_query("tell me about tempo runs") is False
    
    def test_empty_and_none_handling(self):
        """Empty or None messages should not be high-stakes."""
        from services.ai_coach import is_high_stakes_query
        
        assert is_high_stakes_query("") is False
        assert is_high_stakes_query(None) is False


class TestHighStakesPatterns:
    """Test the HIGH_STAKES_PATTERNS list."""
    
    def test_patterns_exist(self):
        """Should have a comprehensive list of patterns."""
        from services.ai_coach import HIGH_STAKES_PATTERNS
        
        assert len(HIGH_STAKES_PATTERNS) > 30  # Should have many patterns
        assert "injury" in HIGH_STAKES_PATTERNS
        assert "pain" in HIGH_STAKES_PATTERNS
        assert "skip" in HIGH_STAKES_PATTERNS
    
    def test_body_parts_included(self):
        """Should include common running injury body parts."""
        from services.ai_coach import HIGH_STAKES_PATTERNS
        
        body_parts = ["knee", "shin", "achilles", "plantar", "hip", "calf", "hamstring"]
        for part in body_parts:
            assert part in HIGH_STAKES_PATTERNS, f"Missing body part: {part}"


class TestCostCapConstants:
    """Test the cost cap constants are properly defined."""
    
    def test_constants_exist(self):
        """Cost cap constants should be defined."""
        from services.ai_coach import (
            COACH_MAX_REQUESTS_PER_DAY,
            COACH_MAX_OPUS_REQUESTS_PER_DAY,
            COACH_MONTHLY_TOKEN_BUDGET,
            COACH_MONTHLY_OPUS_TOKEN_BUDGET,
            COACH_MAX_INPUT_TOKENS,
            COACH_MAX_OUTPUT_TOKENS,
        )
        
        assert COACH_MAX_REQUESTS_PER_DAY == 50
        assert COACH_MAX_OPUS_REQUESTS_PER_DAY == 3
        assert COACH_MONTHLY_TOKEN_BUDGET == 1_000_000
        assert COACH_MONTHLY_OPUS_TOKEN_BUDGET == 50_000
        assert COACH_MAX_INPUT_TOKENS == 4000
        assert COACH_MAX_OUTPUT_TOKENS == 1500


class TestHighStakesSignalEnum:
    """Test the HighStakesSignal enum."""
    
    def test_enum_values(self):
        """Enum should have all expected signal types."""
        from services.ai_coach import HighStakesSignal
        
        assert HighStakesSignal.INJURY.value == "injury"
        assert HighStakesSignal.PAIN.value == "pain"
        assert HighStakesSignal.SKIP_DECISION.value == "skip"
        assert HighStakesSignal.RETURN_FROM_BREAK.value == "return"
        assert HighStakesSignal.ILLNESS.value == "illness"
