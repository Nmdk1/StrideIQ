"""
Phase 5 Conversation Quality Tests

Tests for:
1. Confidence-gated response instructions
2. Question tracking (avoid repetition)
3. Progressive detail levels
"""

import pytest


class TestQuestionTracking:
    """Test already_answered_in_thread detection."""

    @pytest.fixture
    def manager(self):
        from services.coach_modules.conversation import ConversationQualityManager
        return ConversationQualityManager()

    def test_detects_return_date_with_month(self, manager):
        """Should detect return date when user mentions a month."""
        messages = [
            {"role": "user", "content": "I came back from injury in January"},
        ]
        assert manager.already_answered_in_thread(messages, "return_date")

    def test_detects_return_date_with_relative_time(self, manager):
        """Should detect return date with relative time reference."""
        messages = [
            {"role": "user", "content": "I started running again 3 weeks ago"},
        ]
        assert manager.already_answered_in_thread(messages, "return_date")

    def test_detects_return_date_with_date_format(self, manager):
        """Should detect return date with numeric date."""
        messages = [
            {"role": "user", "content": "I returned on 1/15"},
        ]
        assert manager.already_answered_in_thread(messages, "return_date")

    def test_no_false_positive_for_return_date(self, manager):
        """Should not detect return date when not mentioned."""
        messages = [
            {"role": "user", "content": "What's my longest run this month?"},
        ]
        assert not manager.already_answered_in_thread(messages, "return_date")

    def test_detects_pain_level_no_pain(self, manager):
        """Should detect when user says no pain."""
        messages = [
            {"role": "user", "content": "I'm feeling great, no pain at all"},
        ]
        assert manager.already_answered_in_thread(messages, "pain_level")

    def test_detects_pain_level_recovered(self, manager):
        """Should detect fully recovered statement."""
        messages = [
            {"role": "user", "content": "I'm fully recovered now"},
        ]
        assert manager.already_answered_in_thread(messages, "pain_level")

    def test_detects_weekly_mileage(self, manager):
        """Should detect weekly mileage."""
        messages = [
            {"role": "user", "content": "I'm running about 45 miles per week"},
        ]
        assert manager.already_answered_in_thread(messages, "weekly_mileage")

    def test_detects_weekly_mileage_mpw(self, manager):
        """Should detect MPW format."""
        messages = [
            {"role": "user", "content": "Currently at 50 mpw"},
        ]
        assert manager.already_answered_in_thread(messages, "weekly_mileage")

    def test_ignores_assistant_messages(self, manager):
        """Should only check user messages for answers."""
        messages = [
            {"role": "assistant", "content": "You returned in January"},
        ]
        assert not manager.already_answered_in_thread(messages, "return_date")


class TestClarificationTracking:
    """Test already_asked_clarification detection."""

    @pytest.fixture
    def manager(self):
        from services.coach_modules.conversation import ConversationQualityManager
        return ConversationQualityManager()

    def test_detects_return_date_question(self, manager):
        """Should detect when we asked about return date."""
        messages = [
            {"role": "assistant", "content": "When did you return from your injury?"},
        ]
        assert manager.already_asked_clarification(messages, "return_date")

    def test_detects_pain_level_question(self, manager):
        """Should detect when we asked about pain."""
        messages = [
            {"role": "assistant", "content": "Do you have any current pain or niggles?"},
        ]
        assert manager.already_asked_clarification(messages, "pain_level")

    def test_no_false_positive_for_clarification(self, manager):
        """Should not detect clarification when not asked."""
        messages = [
            {"role": "assistant", "content": "Your longest run was 15 miles."},
        ]
        assert not manager.already_asked_clarification(messages, "return_date")


class TestShouldAskClarification:
    """Test should_ask_clarification logic."""

    @pytest.fixture
    def manager(self):
        from services.coach_modules.conversation import ConversationQualityManager
        return ConversationQualityManager()

    def test_should_ask_if_not_answered(self, manager):
        """Should ask if question not answered and not asked before."""
        messages = [
            {"role": "user", "content": "Since coming back, what's my longest run?"},
        ]
        assert manager.should_ask_clarification(messages, "return_date")

    def test_should_not_ask_if_already_answered(self, manager):
        """Should not ask if user already provided the info."""
        messages = [
            {"role": "user", "content": "I came back in January"},
            {"role": "user", "content": "What's my longest run since then?"},
        ]
        assert not manager.should_ask_clarification(messages, "return_date")

    def test_should_not_ask_if_already_asked(self, manager):
        """Should not repeat clarification question."""
        messages = [
            {"role": "assistant", "content": "When did you return from your injury?"},
            {"role": "user", "content": "What's my longest run?"},
        ]
        assert not manager.should_ask_clarification(messages, "return_date")


class TestDetailLevels:
    """Test progressive detail level calculation."""

    @pytest.fixture
    def manager(self):
        from services.coach_modules.conversation import ConversationQualityManager
        return ConversationQualityManager()

    def test_first_message_is_full(self, manager):
        """First message should get full detail."""
        from services.coach_modules.conversation import DetailLevel
        assert manager.get_detail_level(1) == DetailLevel.FULL

    def test_second_third_message_is_moderate(self, manager):
        """Second and third messages should get moderate detail."""
        from services.coach_modules.conversation import DetailLevel
        assert manager.get_detail_level(2) == DetailLevel.MODERATE
        assert manager.get_detail_level(3) == DetailLevel.MODERATE

    def test_fourth_plus_message_is_brief(self, manager):
        """Fourth+ messages should get brief detail."""
        from services.coach_modules.conversation import DetailLevel
        assert manager.get_detail_level(4) == DetailLevel.BRIEF
        assert manager.get_detail_level(10) == DetailLevel.BRIEF


class TestDetailInstructions:
    """Test detail instruction generation."""

    @pytest.fixture
    def manager(self):
        from services.coach_modules.conversation import ConversationQualityManager
        return ConversationQualityManager()

    def test_full_instruction_mentions_complete(self, manager):
        """Full detail instruction should mention complete context."""
        from services.coach_modules.conversation import DetailLevel
        instruction = manager.build_detail_instruction(DetailLevel.FULL)
        assert "complete context" in instruction.lower() or "FULL" in instruction

    def test_moderate_instruction_mentions_concise(self, manager):
        """Moderate instruction should mention being concise."""
        from services.coach_modules.conversation import DetailLevel
        instruction = manager.build_detail_instruction(DetailLevel.MODERATE)
        assert "concise" in instruction.lower() or "MODERATE" in instruction

    def test_brief_instruction_mentions_direct(self, manager):
        """Brief instruction should mention direct answers."""
        from services.coach_modules.conversation import DetailLevel
        instruction = manager.build_detail_instruction(DetailLevel.BRIEF)
        assert "direct" in instruction.lower() or "BRIEF" in instruction


class TestConfidenceInstruction:
    """Test confidence-gated response instruction."""

    @pytest.fixture
    def manager(self):
        from services.coach_modules.conversation import ConversationQualityManager
        return ConversationQualityManager()

    def test_includes_confidence_levels(self, manager):
        """Instruction should mention all confidence levels."""
        instruction = manager.build_confidence_instruction()
        assert "High" in instruction
        assert "Medium" in instruction
        assert "Low" in instruction

    def test_includes_direct_answer_requirement(self, manager):
        """Instruction should require direct answer first."""
        instruction = manager.build_confidence_instruction()
        assert "DIRECTLY" in instruction or "directly" in instruction

    def test_includes_evidence_requirement(self, manager):
        """Instruction should require evidence."""
        instruction = manager.build_confidence_instruction()
        assert "evidence" in instruction.lower()

    def test_includes_example_format(self, manager):
        """Instruction should include example format."""
        instruction = manager.build_confidence_instruction()
        assert "Example" in instruction or "example" in instruction


class TestModuleImports:
    """Test that Phase 5 module imports work."""

    def test_import_from_package(self):
        """Should be able to import from package."""
        from services.coach_modules import (
            ConversationQualityManager,
            ConfidenceLevel,
            DetailLevel,
        )
        assert ConversationQualityManager is not None
        assert ConfidenceLevel is not None
        assert DetailLevel is not None

    def test_import_singleton(self):
        """Should be able to import singleton."""
        from services.coach_modules import conversation_manager
        assert conversation_manager is not None

    def test_import_patterns(self):
        """Should be able to import pattern constants."""
        from services.coach_modules import ANSWER_PATTERNS, CLARIFICATION_PATTERNS
        assert len(ANSWER_PATTERNS) >= 5
        assert len(CLARIFICATION_PATTERNS) >= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
