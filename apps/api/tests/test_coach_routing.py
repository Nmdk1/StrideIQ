"""
Phase 1 Routing Fix Tests (ADR-compliant)

Tests for:
1. Judgment question detection (_is_judgment_question)
2. Return context detection (_has_return_context)
3. Return clarification gate (_needs_return_clarification)
4. Routing priority (judgment questions bypass shortcuts)
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4


class TestJudgmentQuestionDetection:
    """Test _is_judgment_question method for opinion/timeline questions."""

    @pytest.fixture
    def coach(self):
        """Create a minimal AICoach instance for testing detection methods."""
        from services.ai_coach import AICoach
        
        mock_db = MagicMock()
        with patch.object(AICoach, '__init__', lambda self, db: None):
            coach = AICoach(mock_db)
            coach.db = mock_db
            # Copy the detection methods we need
            coach._RETURN_CONTEXT_PHRASES = AICoach._RETURN_CONTEXT_PHRASES
            coach._has_return_context = AICoach._has_return_context.__get__(coach, AICoach)
            coach._is_judgment_question = AICoach._is_judgment_question.__get__(coach, AICoach)
            return coach

    def test_opinion_patterns_detected(self, coach):
        """Opinion-seeking patterns should be detected as judgment questions."""
        opinion_questions = [
            "Would it be reasonable to think I'll hit 3:08 by March?",
            "Do you think I can get back to my old pace?",
            "What do you think about my training?",
            "Is it realistic to run a marathon in 8 weeks?",
            "Am I on track for my goal?",
            "Will I be ready for the race?",
            "Can I make it to sub-3?",
            "Should I be worried about my pace?",
            "Is it possible to improve that much?",
            "What's your take on my progress?",
            "How likely am I to hit my goal?",
            "Will I be fit enough by race day?",
        ]
        
        for q in opinion_questions:
            assert coach._is_judgment_question(q), f"Should detect as judgment: {q}"

    def test_benchmark_plus_timeline_detected(self, coach):
        """Benchmark + timeline combinations should be detected."""
        benchmark_timeline_questions = [
            "Since I was in 3:08 marathon shape, will I be ready by March?",
            "I was in great race shape last year, can I get there by the marathon?",
            "My pb shape was amazing, is it realistic to return by June?",
            "I used to run 7:00/mi pace, can I get back to that by the race?",
            "At my peak I ran a 3:05, am I on track for the marathon?",
        ]
        
        for q in benchmark_timeline_questions:
            assert coach._is_judgment_question(q), f"Should detect as judgment: {q}"

    def test_prescription_requests_not_judgment(self, coach):
        """Pure prescription requests should NOT be judgment questions."""
        prescription_requests = [
            "What should I do today?",
            "Plan my week for me",
            "Give me a workout",
            "What should I run tomorrow?",
            "What's my workout this week?",
        ]
        
        for q in prescription_requests:
            assert not coach._is_judgment_question(q), f"Should NOT be judgment: {q}"

    def test_simple_data_questions_not_judgment(self, coach):
        """Simple data lookup questions should NOT be judgment questions."""
        data_questions = [
            "What was my longest run?",
            "Show me my fastest 5k",
            "What's my current mileage?",
            "How many miles did I run last week?",
        ]
        
        for q in data_questions:
            assert not coach._is_judgment_question(q), f"Should NOT be judgment: {q}"


class TestReturnContextDetection:
    """Test _has_return_context method for injury/break context."""

    @pytest.fixture
    def coach(self):
        """Create a minimal AICoach instance for testing detection methods."""
        from services.ai_coach import AICoach
        
        mock_db = MagicMock()
        with patch.object(AICoach, '__init__', lambda self, db: None):
            coach = AICoach(mock_db)
            coach.db = mock_db
            coach._RETURN_CONTEXT_PHRASES = AICoach._RETURN_CONTEXT_PHRASES
            coach._has_return_context = AICoach._has_return_context.__get__(coach, AICoach)
            return coach

    def test_original_return_phrases_detected(self, coach):
        """Original return context phrases should be detected."""
        return_messages = [
            "since coming back from injury",
            "after my injury I've been slow",
            "since returning to running",
            "I recently returned from a break",
            "back from injury now",
        ]
        
        for msg in return_messages:
            assert coach._has_return_context(msg.lower()), f"Should detect return context: {msg}"

    def test_expanded_return_phrases_detected(self, coach):
        """Phase 1 expanded return context phrases should be detected."""
        expanded_messages = [
            "in my post-injury recovery",
            "I'm in recovery phase",
            "first week back running",
            "just started back after surgery",
            "building back up after being sick",
            "ramping back up slowly",
            "easing back into training",
            "after rehab I'm getting stronger",
            "since physical therapy ended",
        ]
        
        for msg in expanded_messages:
            assert coach._has_return_context(msg.lower()), f"Should detect return context: {msg}"

    def test_non_return_messages_not_detected(self, coach):
        """Messages without return context should not be detected."""
        normal_messages = [
            "what should I run today?",
            "my longest run was 10 miles",
            "I want to run a marathon",
            "how's my fitness looking?",
            "plan my week",
        ]
        
        for msg in normal_messages:
            assert not coach._has_return_context(msg.lower()), f"Should NOT detect return context: {msg}"


class TestReturnClarificationGate:
    """Test _needs_return_clarification method."""

    @pytest.fixture
    def coach(self):
        """Create a minimal AICoach instance for testing."""
        from services.ai_coach import AICoach
        
        mock_db = MagicMock()
        with patch.object(AICoach, '__init__', lambda self, db: None):
            coach = AICoach(mock_db)
            coach.db = mock_db
            coach._RETURN_CONTEXT_PHRASES = AICoach._RETURN_CONTEXT_PHRASES
            coach._has_return_context = AICoach._has_return_context.__get__(coach, AICoach)
            coach._thread_mentions_return_context = MagicMock(return_value=False)
            coach._needs_return_clarification = AICoach._needs_return_clarification.__get__(coach, AICoach)
            return coach

    def test_return_plus_comparison_needs_clarification(self, coach):
        """Return context + comparison language should trigger clarification."""
        athlete_id = uuid4()
        
        messages_needing_clarification = [
            "since coming back, what's my longest run?",
            "after my injury, was that my fastest pace?",
            "I'm back from a break, is that my best run?",
            "since returning, how does that compare to my slowest?",
        ]
        
        for msg in messages_needing_clarification:
            assert coach._needs_return_clarification(msg, athlete_id), f"Should need clarification: {msg}"

    def test_return_with_date_no_clarification(self, coach):
        """Return context with a date provided should NOT need clarification."""
        athlete_id = uuid4()
        
        messages_with_dates = [
            "since coming back in January, what's my longest run?",
            "after my injury about 6 weeks ago, how am I doing?",
            "since returning on 2026-01-15, what's my progress?",
            "I came back in December, is that my best run?",
        ]
        
        for msg in messages_with_dates:
            assert not coach._needs_return_clarification(msg, athlete_id), f"Should NOT need clarification (has date): {msg}"

    def test_no_return_context_no_clarification(self, coach):
        """Messages without return context should not need clarification."""
        athlete_id = uuid4()
        
        normal_messages = [
            "what's my longest run?",
            "show me my fastest 5k",
            "what's my best pace?",
        ]
        
        for msg in normal_messages:
            assert not coach._needs_return_clarification(msg, athlete_id), f"Should NOT need clarification: {msg}"

    def test_return_without_comparison_no_clarification(self, coach):
        """Return context without comparison language should not need clarification."""
        athlete_id = uuid4()
        
        messages = [
            "since coming back, what should I do today?",
            "after my injury, plan my week",
            "I'm back from a break, give me a workout",
        ]
        
        for msg in messages:
            assert not coach._needs_return_clarification(msg, athlete_id), f"Should NOT need clarification (no comparison): {msg}"


class TestRoutingPriority:
    """Test that judgment questions bypass deterministic shortcuts."""

    @pytest.fixture
    def coach(self):
        """Create a minimal AICoach instance for testing routing."""
        from services.ai_coach import AICoach
        
        mock_db = MagicMock()
        with patch.object(AICoach, '__init__', lambda self, db: None):
            coach = AICoach(mock_db)
            coach.db = mock_db
            coach._RETURN_CONTEXT_PHRASES = AICoach._RETURN_CONTEXT_PHRASES
            coach._has_return_context = AICoach._has_return_context.__get__(coach, AICoach)
            coach._is_judgment_question = AICoach._is_judgment_question.__get__(coach, AICoach)
            coach._is_prescription_request = AICoach._is_prescription_request.__get__(coach, AICoach)
            return coach

    def test_judgment_bypasses_prescription_trigger(self, coach):
        """Judgment questions with 'this week' should NOT trigger prescription routing."""
        # This message contains "this week" which normally triggers prescription
        # BUT it's a judgment question, so it should bypass
        message = "This week I move up to 55 miles. Would it be reasonable to think I'll hit my goal?"
        
        is_judgment = coach._is_judgment_question(message)
        is_prescription = coach._is_prescription_request(message)
        
        assert is_judgment, "Should detect as judgment question"
        assert is_prescription, "'this week' does trigger prescription detection"
        # The key is that judgment check happens FIRST, so prescription is skipped
        # This is tested by the _skip_deterministic_shortcuts flag in chat()

    def test_judgment_with_benchmark_detected(self, coach):
        """The problematic user message should be detected as judgment."""
        # This is the exact message that was causing issues
        message = (
            "Last week was my first week running 6 days since injury. "
            "This week I move up to 55 miles, next week 65 then 3 weeks at 70 "
            "before taper week into tune up 10 mile race and taper week to marathon on March 15th. "
            "Since i was in 3:08 marathon shape in December (probably much faster) "
            "would it be reasonable to think that if I can hit my mileage I will be there in time?"
        )
        
        assert coach._is_judgment_question(message), "Should detect the problematic message as judgment"

    def test_pure_prescription_not_judgment(self, coach):
        """Pure prescription requests should not be judgment questions."""
        message = "This week I want to hit 55 miles. What should I run today?"
        
        is_judgment = coach._is_judgment_question(message)
        is_prescription = coach._is_prescription_request(message)
        
        assert not is_judgment, "Pure prescription should NOT be judgment"
        assert is_prescription, "Should still be prescription request"


class TestComparisonKeywordExpansion:
    """Test that comparison keywords are properly detected."""

    @pytest.fixture
    def coach(self):
        """Create a minimal AICoach instance."""
        from services.ai_coach import AICoach
        
        mock_db = MagicMock()
        with patch.object(AICoach, '__init__', lambda self, db: None):
            coach = AICoach(mock_db)
            coach._COMPARISON_KEYWORDS = AICoach._COMPARISON_KEYWORDS
            return coach

    def test_all_comparison_keywords_present(self, coach):
        """Verify all expected comparison keywords are in the list."""
        expected_keywords = (
            "longest", "furthest", "fastest", "slowest",
            "best", "worst", "most", "least",
            "hardest", "toughest", "easiest",
            "biggest", "smallest",
        )
        
        for keyword in expected_keywords:
            assert keyword in coach._COMPARISON_KEYWORDS, f"Missing keyword: {keyword}"


# =============================================================================
# PHASE 2 TESTS: Context Architecture (additional_instructions)
# =============================================================================

class TestRunInstructionsBuilder:
    """Test _build_run_instructions method for dynamic per-run context."""

    @pytest.fixture
    def coach(self):
        """Create a minimal AICoach instance with mocked dependencies."""
        from services.ai_coach import AICoach
        
        mock_db = MagicMock()
        with patch.object(AICoach, '__init__', lambda self, db: None):
            coach = AICoach(mock_db)
            coach.db = mock_db
            coach._RETURN_CONTEXT_PHRASES = AICoach._RETURN_CONTEXT_PHRASES
            coach._COMPARISON_KEYWORDS = AICoach._COMPARISON_KEYWORDS
            coach._has_return_context = AICoach._has_return_context.__get__(coach, AICoach)
            coach._is_judgment_question = AICoach._is_judgment_question.__get__(coach, AICoach)
            coach._is_prescription_request = AICoach._is_prescription_request.__get__(coach, AICoach)
            coach._build_context_injection_for_message = MagicMock(return_value=None)
            coach._build_run_instructions = AICoach._build_run_instructions.__get__(coach, AICoach)
            return coach

    def test_judgment_question_includes_critical_instruction(self, coach):
        """Judgment questions should include CRITICAL JUDGMENT INSTRUCTION."""
        athlete_id = uuid4()
        message = "Would it be reasonable to think I'll hit 3:08 by March?"
        
        with patch('services.ai_coach.coach_tools.get_training_load', return_value={"atl": 50, "ctl": 60, "tsb": 10}):
            instructions = coach._build_run_instructions(athlete_id, message)
        
        assert "CRITICAL JUDGMENT INSTRUCTION" in instructions
        assert "answer directly first" in instructions.lower()
        assert "do not deflect" in instructions.lower()

    def test_return_context_includes_post_return_guidance(self, coach):
        """Return-from-injury context should include appropriate guidance."""
        athlete_id = uuid4()
        message = "Since coming back from injury, how am I doing?"
        
        with patch('services.ai_coach.coach_tools.get_training_load', return_value={"atl": 30, "ctl": 35, "tsb": 5}):
            instructions = coach._build_run_instructions(athlete_id, message)
        
        assert "RETURN-FROM-INJURY CONTEXT" in instructions
        assert "post-return period" in instructions.lower()
        assert "conservative" in instructions.lower()

    def test_benchmark_reference_includes_comparison_guidance(self, coach):
        """Benchmark references should include comparison guidance."""
        athlete_id = uuid4()
        message = "I was in 3:08 marathon shape in December, can I get back there?"
        
        with patch('services.ai_coach.coach_tools.get_training_load', return_value={"atl": 45, "ctl": 50, "tsb": 5}):
            instructions = coach._build_run_instructions(athlete_id, message)
        
        assert "BENCHMARK REFERENCE DETECTED" in instructions
        assert "current metrics" in instructions.lower()

    def test_prescription_request_includes_conservative_bounds(self, coach):
        """Prescription requests should include conservative bounds."""
        athlete_id = uuid4()
        message = "What should I run this week?"
        
        with patch('services.ai_coach.coach_tools.get_training_load', return_value={"atl": 55, "ctl": 60, "tsb": 5}):
            instructions = coach._build_run_instructions(athlete_id, message)
        
        assert "PRESCRIPTION REQUEST" in instructions
        assert "conservative bounds" in instructions.lower()
        assert "20%" in instructions

    def test_training_state_always_included(self, coach):
        """Training state should always be included (using plain English, not acronyms)."""
        athlete_id = uuid4()
        message = "How am I doing?"
        
        with patch('services.ai_coach.coach_tools.get_training_load', return_value={"atl": 50.5, "ctl": 60.2, "tsb": 9.7}):
            instructions = coach._build_run_instructions(athlete_id, message)
        
        # Implementation uses plain English per communication style guidelines
        assert "fatigue level" in instructions
        assert "fitness level" in instructions
        assert "form" in instructions
        assert "CURRENT TRAINING STATE" in instructions

    def test_fatigued_state_labeled_correctly(self, coach):
        """Low TSB should be labeled as 'fatigued'."""
        athlete_id = uuid4()
        message = "How am I doing?"
        
        with patch('services.ai_coach.coach_tools.get_training_load', return_value={"atl": 70, "ctl": 55, "tsb": -15}):
            instructions = coach._build_run_instructions(athlete_id, message)
        
        assert "fatigued" in instructions.lower()

    def test_fresh_state_labeled_correctly(self, coach):
        """High TSB should be labeled as 'fresh'."""
        athlete_id = uuid4()
        message = "How am I doing?"
        
        with patch('services.ai_coach.coach_tools.get_training_load', return_value={"atl": 40, "ctl": 55, "tsb": 15}):
            instructions = coach._build_run_instructions(athlete_id, message)
        
        assert "fresh" in instructions.lower()


class TestThreadHistoryLimits:
    """Test that thread history limits are correctly increased (Phase 2)."""

    @pytest.fixture
    def coach(self):
        """Create a minimal AICoach instance."""
        from services.ai_coach import AICoach
        
        mock_db = MagicMock()
        with patch.object(AICoach, '__init__', lambda self, db: None):
            coach = AICoach(mock_db)
            coach.db = mock_db
            coach.client = MagicMock()
            coach.get_thread_history = AICoach.get_thread_history.__get__(coach, AICoach)
            return coach

    def test_default_limit_is_100(self, coach):
        """Default limit should be 100 (up from 50)."""
        # Check the function signature default
        import inspect
        sig = inspect.signature(coach.get_thread_history)
        default_limit = sig.parameters['limit'].default
        assert default_limit == 100, f"Expected default limit 100, got {default_limit}"

    def test_max_limit_is_500(self, coach):
        """Max limit should be 500 (up from 200)."""
        # Mock the athlete lookup to return a thread_id
        mock_athlete = MagicMock()
        mock_athlete.coach_thread_id = "thread_123"
        coach.db.query.return_value.filter.return_value.first.return_value = mock_athlete
        
        # Mock the OpenAI client
        coach.client.beta.threads.messages.list.return_value = MagicMock(data=[])
        
        # Call with limit > 500, should be capped
        coach.get_thread_history(uuid4(), limit=1000)
        
        # Verify the API was called with limit=500
        coach.client.beta.threads.messages.list.assert_called_once()
        call_kwargs = coach.client.beta.threads.messages.list.call_args[1]
        assert call_kwargs['limit'] == 500, f"Expected limit 500, got {call_kwargs['limit']}"


class TestContextInjectionPriorMessages:
    """Test that context injection uses more prior messages (Phase 2)."""

    @pytest.fixture
    def coach(self):
        """Create a minimal AICoach instance."""
        from services.ai_coach import AICoach
        
        mock_db = MagicMock()
        with patch.object(AICoach, '__init__', lambda self, db: None):
            coach = AICoach(mock_db)
            coach.db = mock_db
            coach._RETURN_CONTEXT_PHRASES = AICoach._RETURN_CONTEXT_PHRASES
            coach._COMPARISON_KEYWORDS = AICoach._COMPARISON_KEYWORDS
            coach._has_return_context = AICoach._has_return_context.__get__(coach, AICoach)
            coach._build_context_injection_pure = AICoach._build_context_injection_pure.__get__(coach, AICoach)
            coach._build_context_injection_for_message = AICoach._build_context_injection_for_message.__get__(coach, AICoach)
            coach.get_thread_history = MagicMock()
            return coach

    def test_fetches_40_messages_for_context(self, coach):
        """Should fetch 40 messages to get up to 20 user messages."""
        athlete_id = uuid4()
        message = "What was my longest run since coming back?"
        
        # Mock history with mixed roles
        coach.get_thread_history.return_value = {
            "messages": [
                {"role": "user", "content": f"Message {i}"}
                for i in range(25)
            ]
        }
        
        coach._build_context_injection_for_message(athlete_id=athlete_id, message=message)
        
        # Verify we requested 40 messages
        coach.get_thread_history.assert_called_once_with(athlete_id, limit=40)

    def test_caps_prior_messages_at_20(self, coach):
        """Should only use up to 20 prior user messages."""
        athlete_id = uuid4()
        message = "What was my longest run since coming back?"
        
        # Mock history with 30 user messages
        coach.get_thread_history.return_value = {
            "messages": [
                {"role": "user", "content": f"Message {i}"}
                for i in range(30)
            ]
        }
        
        # Spy on _build_context_injection_pure to see what gets passed
        with patch.object(coach, '_build_context_injection_pure', wraps=coach._build_context_injection_pure) as spy:
            coach._build_context_injection_for_message(athlete_id=athlete_id, message=message)
            
            # Check that at most 20 prior messages were passed
            call_args = spy.call_args
            prior_msgs = call_args[1]['prior_user_messages']
            assert len(prior_msgs) <= 20, f"Expected at most 20 prior messages, got {len(prior_msgs)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
