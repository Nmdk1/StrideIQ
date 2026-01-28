"""
AI Coach Routing Module (Phase 4 Refactor)

Handles message classification and routing logic.
Extracted from ai_coach.py for maintainability and testability.

Message Types:
- JUDGMENT: Opinion/timeline questions that require LLM reasoning
- PRESCRIPTION: Workout prescription requests  
- COMPARISON: Comparison questions with return context
- GENERAL: All other messages
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Tuple, Optional
from uuid import UUID


class MessageType(Enum):
    """Classification of incoming coach messages."""
    JUDGMENT = "judgment"
    PRESCRIPTION = "prescription"
    COMPARISON = "comparison"
    CLARIFICATION_NEEDED = "clarification_needed"
    GENERAL = "general"


# Return context phrases (Phase 1 expanded)
RETURN_CONTEXT_PHRASES = (
    # Original phrases
    "since coming back",
    "since i came back",
    "since coming back from",
    "coming back from",
    "back from injury",
    "after injury",
    "after my injury",
    "since injury",
    "since my injury",
    "after a break",
    "after my break",
    "after time off",
    "since a break",
    "since my break",
    "since time off",
    "since returning",
    "since i returned",
    "recently returned",
    "returning from injury",
    "returning from a break",
    # Phase 1 additions - expanded coverage
    "post-injury",
    "post injury",
    "post-break",
    "post break",
    "recovery phase",
    "in recovery",
    "since i started running again",
    "since starting again",
    "first week back",
    "first run back",
    "first time back",
    "just started back",
    "just came back",
    "just got back",
    "getting back into",
    "easing back into",
    "building back",
    "ramping back up",
    "after surgery",
    "after my surgery",
    "since surgery",
    "after rehab",
    "since rehab",
    "after physical therapy",
    "since physical therapy",
    "physical therapy ended",
    "since pt",
    "after being injured",
    "after being sick",
    "after illness",
    "since being sick",
    # Phase 2 additions
    "back from a break",
    "back from break",
    "i'm back from",
    "im back from",
)


# Comparison keywords
COMPARISON_KEYWORDS = (
    "longest",
    "furthest",
    "fastest",
    "slowest",
    "best",
    "worst",
    "most",
    "least",
    "hardest",
    "toughest",
    "easiest",
    "biggest",
    "smallest",
)


class MessageRouter:
    """
    Routes incoming messages to appropriate handlers based on classification.
    
    Extracted from AICoach for testability and maintainability.
    """
    
    def __init__(self):
        self.return_context_phrases = RETURN_CONTEXT_PHRASES
        self.comparison_keywords = COMPARISON_KEYWORDS
    
    def classify(self, message: str, has_prior_return_context: bool = False) -> Tuple[MessageType, bool]:
        """
        Classify a message and determine routing.
        
        Args:
            message: The user's message
            has_prior_return_context: Whether return context was mentioned earlier in thread
            
        Returns:
            Tuple of (MessageType, should_skip_shortcuts)
        """
        ml = (message or "").lower()
        
        # Judgment questions always bypass shortcuts
        if self.is_judgment_question(message):
            return MessageType.JUDGMENT, True
        
        # Check for return context needing clarification
        if self.needs_return_clarification(message, has_prior_return_context):
            return MessageType.CLARIFICATION_NEEDED, True
        
        # Prescription requests (but not if it's really a judgment question)
        if self.is_prescription_request(message):
            return MessageType.PRESCRIPTION, False
        
        # Comparison with return context
        if self.has_return_context(ml) and self._has_comparison_language(ml):
            return MessageType.COMPARISON, False
        
        return MessageType.GENERAL, False
    
    def is_judgment_question(self, message: str) -> bool:
        """
        Detect opinion/judgment/timeline questions that MUST go to the LLM.
        
        These questions require nuanced reasoning, not hardcoded shortcuts:
        - "Would it be reasonable to think I'll hit 3:08 by March?"
        - "Do you think I can get back to my old pace?"
        - "Am I on track for my goal?"
        - "Is it realistic to run a marathon in 8 weeks?"
        
        Returns True if this should bypass all deterministic shortcuts.
        """
        ml = (message or "").lower()
        
        # Opinion-seeking patterns (require LLM reasoning)
        opinion_patterns = (
            "would it be reasonable",
            "do you think",
            "what do you think",
            "is it realistic",
            "is it reasonable",
            "is it possible",
            "can i",
            "will i",
            "am i on track",
            "am i ready",
            "will i be ready",
            "will i be fit",
            "will i make it",
            "can i make it",
            "should i be worried",
            "should i be concerned",
            "how likely",
            "what's your take",
            "what are my chances",
            "what's the probability",
            "is this achievable",
            "is this doable",
            "is this feasible",
            "your opinion",
            "your assessment",
        )
        
        has_opinion = any(p in ml for p in opinion_patterns)
        if has_opinion:
            return True
        
        # Benchmark + timeline combinations also require judgment
        benchmark_indicators = (
            "marathon shape",
            "race shape",
            "pb shape",
            "pr shape",
            "peak form",
            "was in",
            "used to run",
            "i ran a",
            "my best",
            "when i was",
            "at my peak",
            "my pb",
            "my pr",
            "3:0",  # Marathon time references
            "sub-3",
            "sub 3",
            "bq",
            "boston qualify",
        )
        
        goal_timeline_patterns = (
            "by march",
            "by april",
            "by may",
            "by june",
            "by july",
            "by august",
            "by september",
            "by october",
            "by november",
            "by december",
            "by january",
            "by february",
            "by the marathon",
            "by race day",
            "by the race",
            "in time",
            "on time",
            "ready for",
            "before the",
        )
        
        has_benchmark = any(p in ml for p in benchmark_indicators)
        has_timeline = any(p in ml for p in goal_timeline_patterns)
        
        if has_benchmark and has_timeline:
            return True
        
        # Benchmark + return context also triggers judgment routing
        if has_benchmark and self.has_return_context(ml):
            return True
        
        return False
    
    def is_prescription_request(self, message: str) -> bool:
        """Detect explicit workout prescription requests."""
        ml = (message or "").lower()
        
        explicit = any(
            k in ml
            for k in (
                "what should i do",
                "what do i do",
                "what should i run",
                "give me a workout",
                "plan my week",
                "this week",
                "next week",
            )
        )
        if explicit:
            return True

        # "today/tomorrow" only counts as a prescription request if paired with decision verb
        if ("today" in ml or "tomorrow" in ml) and any(
            k in ml for k in ("what should", "should i", "workout", "do today", "do tomorrow", "prescribe")
        ):
            return True

        return False
    
    def has_return_context(self, lower_message: str) -> bool:
        """Check if message mentions return-from-injury/break context."""
        ml = (lower_message or "").lower()
        return any(p in ml for p in self.return_context_phrases)
    
    def needs_return_clarification(
        self, 
        message: str, 
        has_prior_return_context: bool = False,
    ) -> bool:
        """
        Check if we need to ask for clarification about return timeline.
        
        Returns True if:
        - Return context is detected (in message or prior)
        - Comparison language is present
        - No specific date/timeframe is provided
        """
        ml = (message or "").lower()
        
        has_return = self.has_return_context(ml) or has_prior_return_context
        if not has_return:
            return False
        
        if not self._has_comparison_language(ml):
            return False
        
        # Check for explicit date/timeframe
        has_iso_date = bool(re.search(r"\b20\d{2}-\d{2}-\d{2}\b", ml))
        has_relative = bool(re.search(r"\b(\d{1,3})\s*(day|days|d|week|weeks|wk|wks|month|months|mo)\b", ml))
        has_month_name = bool(re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|may|june|july|august|september|october|november|december)\b", ml))
        
        # If they provided a date, no clarification needed
        if has_iso_date or has_relative or has_month_name:
            return False
        
        return True
    
    def _has_comparison_language(self, lower_message: str) -> bool:
        """Check for comparison/superlative language."""
        return any(k in lower_message for k in self.comparison_keywords)
    
    def needs_return_scope_clarification(self, lower_message: str) -> bool:
        """
        Legacy method for return scope clarification.
        
        True when:
        - The athlete uses return-context language
        - AND also uses comparison/superlative language
        - BUT does not provide any concrete return window
        """
        lower = (lower_message or "").lower()
        if not lower:
            return False
        if not self.has_return_context(lower):
            return False

        # Check for comparison tokens
        comparison_tokens = (
            "longest", "furthest", "fastest", "slowest",
            "best", "worst", "most", "least",
            "hardest", "toughest", "easiest",
            "slow", "fast",
        )
        if not any(t in lower for t in comparison_tokens):
            return False

        has_iso_date = bool(re.search(r"\b20\d{2}-\d{2}-\d{2}\b", lower))
        has_relative = bool(re.search(r"\b(\d{1,3})\s*(day|days|d|week|weeks|wk|wks|month|months|mo)\b", lower))
        has_month_name = bool(re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b", lower))
        
        return not (has_iso_date or has_relative or has_month_name)


# Singleton instance for easy import
router = MessageRouter()
