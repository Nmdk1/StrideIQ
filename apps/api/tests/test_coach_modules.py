"""
Phase 4 Code Architecture Tests

Tests for refactored ai_coach modules:
1. routing.py - MessageRouter classification
2. context.py - ContextBuilder instructions
"""

import pytest
from uuid import uuid4


class TestMessageRouterClassify:
    """Test MessageRouter.classify() for message type detection."""

    @pytest.fixture
    def router(self):
        from services.coach_modules.routing import MessageRouter
        return MessageRouter()

    def test_judgment_question_returns_judgment_type(self, router):
        """Judgment questions should be classified as JUDGMENT."""
        from services.coach_modules.routing import MessageType
        
        judgment_questions = [
            "Would it be reasonable to think I'll hit 3:08 by March?",
            "Do you think I can get back to my old pace?",
            "Am I on track for my goal?",
            "Is it realistic to run a marathon in 8 weeks?",
        ]
        
        for q in judgment_questions:
            msg_type, skip_shortcuts = router.classify(q)
            assert msg_type == MessageType.JUDGMENT, f"Failed: {q}"
            assert skip_shortcuts is True, f"Should skip shortcuts for: {q}"

    def test_prescription_returns_prescription_type(self, router):
        """Prescription requests should be classified as PRESCRIPTION."""
        from services.coach_modules.routing import MessageType
        
        prescription_requests = [
            "What should I run today?",
            "Plan my week for me",
            "Give me a workout",
        ]
        
        for q in prescription_requests:
            msg_type, skip_shortcuts = router.classify(q)
            assert msg_type == MessageType.PRESCRIPTION, f"Failed: {q}"
            assert skip_shortcuts is False, f"Should NOT skip shortcuts for: {q}"

    def test_judgment_takes_priority_over_prescription(self, router):
        """Judgment questions with 'this week' should be JUDGMENT, not PRESCRIPTION."""
        from services.coach_modules.routing import MessageType
        
        # This message has "this week" (prescription trigger) but is a judgment question
        message = "This week I move up to 55 miles. Would it be reasonable to think I'll hit my goal?"
        
        msg_type, skip_shortcuts = router.classify(message)
        assert msg_type == MessageType.JUDGMENT
        assert skip_shortcuts is True

    def test_return_clarification_detected(self, router):
        """Return context + comparison without date should need clarification."""
        from services.coach_modules.routing import MessageType
        
        message = "Since coming back, what's my longest run?"
        
        msg_type, skip_shortcuts = router.classify(message)
        assert msg_type == MessageType.CLARIFICATION_NEEDED
        assert skip_shortcuts is True

    def test_return_with_date_no_clarification(self, router):
        """Return context with a date should NOT need clarification."""
        from services.coach_modules.routing import MessageType
        
        message = "Since coming back in January, what's my longest run?"
        
        msg_type, skip_shortcuts = router.classify(message)
        # Should be COMPARISON or GENERAL, not CLARIFICATION_NEEDED
        assert msg_type != MessageType.CLARIFICATION_NEEDED

    def test_general_message(self, router):
        """General messages should be classified as GENERAL."""
        from services.coach_modules.routing import MessageType
        
        general_messages = [
            "How's my fitness looking?",
            "Tell me about my recent runs",
            "What's my VDOT?",
        ]
        
        for q in general_messages:
            msg_type, skip_shortcuts = router.classify(q)
            assert msg_type == MessageType.GENERAL, f"Failed: {q}"


class TestMessageRouterDetection:
    """Test individual detection methods in MessageRouter."""

    @pytest.fixture
    def router(self):
        from services.coach_modules.routing import MessageRouter
        return MessageRouter()

    def test_is_judgment_question_opinion_patterns(self, router):
        """Opinion patterns should be detected."""
        opinion_questions = [
            "Do you think I can do it?",
            "Is it realistic to expect that?",
            "What's your take on my progress?",
        ]
        
        for q in opinion_questions:
            assert router.is_judgment_question(q), f"Should detect: {q}"

    def test_is_judgment_question_benchmark_timeline(self, router):
        """Benchmark + timeline should be detected as judgment."""
        message = "Since I was in 3:08 marathon shape, will I be ready by March?"
        assert router.is_judgment_question(message)

    def test_is_prescription_request(self, router):
        """Prescription requests should be detected."""
        prescription_messages = [
            "What should I do today?",
            "Plan my week",
            "Give me a workout",
        ]
        
        for msg in prescription_messages:
            assert router.is_prescription_request(msg), f"Should detect: {msg}"

    def test_has_return_context(self, router):
        """Return context phrases should be detected."""
        return_messages = [
            "since coming back from injury",
            "after my break",
            "I'm back from a break",
            "post-injury recovery",
            "first week back",
        ]
        
        for msg in return_messages:
            assert router.has_return_context(msg.lower()), f"Should detect: {msg}"

    def test_no_return_context(self, router):
        """Normal messages should not trigger return context."""
        normal_messages = [
            "what should I run today?",
            "my longest run was 10 miles",
            "how's my fitness?",
        ]
        
        for msg in normal_messages:
            assert not router.has_return_context(msg.lower()), f"Should NOT detect: {msg}"


class TestContextBuilder:
    """Test ContextBuilder for instruction generation."""

    @pytest.fixture
    def builder(self):
        from services.coach_modules.context import ContextBuilder
        return ContextBuilder()

    def test_build_run_instructions_with_training_load(self, builder):
        """Should include training state when provided."""
        instructions = builder.build_run_instructions(
            message="How am I doing?",
            training_load={"atl": 50.0, "ctl": 60.0, "tsb": 10.0},
        )
        
        assert "CURRENT TRAINING STATE" in instructions
        assert "ATL=50.0" in instructions
        assert "CTL=60.0" in instructions
        assert "TSB=10.0" in instructions

    def test_build_run_instructions_judgment(self, builder):
        """Should include judgment instruction when flagged."""
        instructions = builder.build_run_instructions(
            message="Do you think I can hit my goal?",
            is_judgment=True,
        )
        
        assert "CRITICAL JUDGMENT INSTRUCTION" in instructions
        assert "answer DIRECTLY first" in instructions

    def test_build_run_instructions_return_context(self, builder):
        """Should include return-from-injury context when flagged."""
        instructions = builder.build_run_instructions(
            message="Since coming back, how am I doing?",
            has_return_context=True,
        )
        
        assert "RETURN-FROM-INJURY CONTEXT" in instructions
        assert "post-return period" in instructions

    def test_build_run_instructions_benchmark(self, builder):
        """Should include benchmark guidance when flagged."""
        instructions = builder.build_run_instructions(
            message="I was in 3:08 marathon shape",
            has_benchmark=True,
        )
        
        assert "BENCHMARK REFERENCE DETECTED" in instructions

    def test_build_run_instructions_prescription(self, builder):
        """Should include prescription bounds when flagged."""
        instructions = builder.build_run_instructions(
            message="What should I run this week?",
            is_prescription=True,
        )
        
        assert "PRESCRIPTION REQUEST" in instructions
        assert "conservative bounds" in instructions

    def test_build_run_instructions_empty_when_no_flags(self, builder):
        """Should return empty when no flags or training load."""
        instructions = builder.build_run_instructions(
            message="Hello",
        )
        
        assert instructions == ""

    def test_build_context_injection_return_context(self, builder):
        """Should inject context for return-context messages."""
        result = builder.build_context_injection(
            message="Since coming back, what's my longest run?",
        )
        
        assert result is not None
        assert "return_context_detected" in result
        assert "comparison_language_detected" in result

    def test_build_context_injection_none_for_normal(self, builder):
        """Should return None for normal messages."""
        result = builder.build_context_injection(
            message="Hello, how are you?",
        )
        
        assert result is None

    def test_detect_benchmark_reference(self, builder):
        """Should detect benchmark references."""
        benchmark_messages = [
            "I was in 3:08 marathon shape",
            "At my peak I ran a 3:05",
            "My PR was much faster",
        ]
        
        for msg in benchmark_messages:
            assert builder.detect_benchmark_reference(msg), f"Should detect: {msg}"


class TestModuleImports:
    """Test that module imports work correctly."""

    def test_import_from_package(self):
        """Should be able to import from package."""
        from services.coach_modules import MessageRouter, MessageType, ContextBuilder
        
        assert MessageRouter is not None
        assert MessageType is not None
        assert ContextBuilder is not None

    def test_import_singletons(self):
        """Should be able to import singleton instances."""
        from services.coach_modules import router, context_builder
        
        assert router is not None
        assert context_builder is not None

    def test_import_constants(self):
        """Should be able to import constants."""
        from services.coach_modules import RETURN_CONTEXT_PHRASES, COMPARISON_KEYWORDS
        
        assert len(RETURN_CONTEXT_PHRASES) > 30
        assert len(COMPARISON_KEYWORDS) > 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
