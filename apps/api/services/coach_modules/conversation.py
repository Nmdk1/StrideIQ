"""
AI Coach Conversation Quality Module (Phase 5)

Handles conversation quality improvements:
1. Confidence-gated responses
2. Question tracking (avoid repetition)
3. Progressive detail levels

Extracted as part of Phase 4/5 refactor for maintainability.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ConfidenceLevel(Enum):
    """Confidence levels for AI Coach responses."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DetailLevel(Enum):
    """Response detail levels based on conversation depth."""
    FULL = "full"           # First response: full context
    MODERATE = "moderate"   # Follow-up: briefer, assumes context
    BRIEF = "brief"         # Third+: very brief


# Patterns for detecting already-answered questions
ANSWER_PATTERNS: Dict[str, str] = {
    "return_date": (
        r"(returned|came back|started again|back from|started running).{0,30}"
        r"(january|february|march|april|may|june|july|august|september|october|november|december"
        r"|\d{1,2}[/-]\d{1,2}|\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        r"|last\s+(week|month)|(\d+)\s+(days?|weeks?|months?)\s+ago)"
    ),
    "pain_level": (
        r"(no pain|no niggles|pain[- ]?free|feeling\s+(good|great|fine|okay|ok|better)"
        r"|injury[- ]?free|fully\s+recovered|100\s*%|back\s+to\s+normal)"
    ),
    "weekly_mileage": (
        r"(\d{2,3})\s*(miles?|mpw|mi|km|kilometers?)\s*(per\s+week|weekly|/\s*w(ee)?k)?"
    ),
    "goal_race": (
        r"(marathon|half[- ]?marathon|10k|5k|ultra)\s*(on|in|race|goal)"
        r"|(race|goal).{0,20}(marathon|half|10k|5k)"
    ),
    "goal_time": (
        r"(goal|target|aiming|shooting)\s*(for|time|of)?\s*[:\s]?\s*\d{1,2}:\d{2}"
        r"|\d{1,2}:\d{2}:\d{2}\s*(goal|target)"
    ),
}

# Clarification question types and their detection patterns
CLARIFICATION_PATTERNS: Dict[str, str] = {
    "return_date": r"when did you (return|come back|start again)|return date|injury.*when",
    "pain_level": r"(any|current) (pain|niggles|issues)|how.*feel",
    "weekly_mileage": r"(current|weekly|recent) (mileage|miles|volume)",
    "goal_race": r"(goal|target|upcoming) race|which race",
    "goal_time": r"(goal|target) time|what time",
}


class ConversationQualityManager:
    """
    Manages conversation quality improvements.
    
    Tracks:
    - What clarification questions have been asked
    - What information the athlete has already provided
    - Conversation depth for progressive detail levels
    """
    
    def __init__(self):
        self.answer_patterns = ANSWER_PATTERNS
        self.clarification_patterns = CLARIFICATION_PATTERNS
    
    def already_answered_in_thread(
        self, 
        messages: List[Dict[str, str]], 
        question_type: str
    ) -> bool:
        """
        Check if a clarification question was already answered in the thread.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            question_type: Type of question (e.g., 'return_date', 'pain_level')
            
        Returns:
            True if the question has already been answered.
        """
        if question_type not in self.answer_patterns:
            return False
        
        pattern = self.answer_patterns[question_type]
        
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if re.search(pattern, content, re.IGNORECASE):
                    return True
        
        return False
    
    def already_asked_clarification(
        self,
        messages: List[Dict[str, str]],
        question_type: str
    ) -> bool:
        """
        Check if we already asked a specific clarification question.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            question_type: Type of clarification (e.g., 'return_date')
            
        Returns:
            True if we already asked this clarification.
        """
        if question_type not in self.clarification_patterns:
            return False
        
        pattern = self.clarification_patterns[question_type]
        
        for msg in messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if re.search(pattern, content, re.IGNORECASE):
                    return True
        
        return False
    
    def should_ask_clarification(
        self,
        messages: List[Dict[str, str]],
        question_type: str
    ) -> bool:
        """
        Determine if we should ask a clarification question.
        
        Returns True only if:
        - The question hasn't been answered
        - We haven't already asked this clarification
        
        Args:
            messages: List of message dicts
            question_type: Type of clarification needed
            
        Returns:
            True if we should ask the clarification.
        """
        # Don't ask if already answered
        if self.already_answered_in_thread(messages, question_type):
            return False
        
        # Don't ask if we already asked
        if self.already_asked_clarification(messages, question_type):
            return False
        
        return True
    
    def get_detail_level(self, user_message_count: int) -> DetailLevel:
        """
        Determine appropriate response detail level based on conversation depth.
        
        Args:
            user_message_count: Number of user messages in current thread
            
        Returns:
            DetailLevel enum value.
        """
        if user_message_count <= 1:
            return DetailLevel.FULL
        elif user_message_count <= 3:
            return DetailLevel.MODERATE
        else:
            return DetailLevel.BRIEF
    
    def build_detail_instruction(self, detail_level: DetailLevel) -> str:
        """
        Build instruction string for response detail level.
        
        Args:
            detail_level: The target detail level
            
        Returns:
            Instruction string for the AI.
        """
        if detail_level == DetailLevel.FULL:
            return (
                "RESPONSE DEPTH: FULL. This is a new conversation. "
                "Provide complete context, explain your reasoning thoroughly, "
                "and include relevant background information."
            )
        elif detail_level == DetailLevel.MODERATE:
            return (
                "RESPONSE DEPTH: MODERATE. This is a follow-up in an ongoing conversation. "
                "Assume the athlete remembers context from earlier messages. "
                "Be concise but still provide key evidence and reasoning."
            )
        else:  # BRIEF
            return (
                "RESPONSE DEPTH: BRIEF. This is a continuation of a longer conversation. "
                "The athlete knows the context. Give direct, concise answers. "
                "Only expand if they ask for more detail."
            )
    
    def build_confidence_instruction(self) -> str:
        """
        Build the confidence-gated response instruction.
        
        Returns:
            Instruction string requiring confidence levels.
        """
        return """CONFIDENCE-GATED RESPONSES (REQUIRED for judgment/opinion questions):

For ALL judgment/opinion/timeline questions, you MUST:
1. State your answer DIRECTLY first (yes/no/maybe/likely/unlikely)
2. State your confidence level in parentheses: (High confidence), (Medium confidence), or (Low confidence)
3. Explain your reasoning with specific evidence from their data
4. List 2-3 key risks or caveats

Confidence level guidelines:
- HIGH: Strong data support, clear trend, >80% certainty
- MEDIUM: Good data but some uncertainty, 50-80% certainty
- LOW: Limited data, conflicting signals, <50% certainty

Example format:
"**Yes, I think you can hit your goal** (Medium confidence).

Your efficiency is trending positive with [specific evidence]. However, [key uncertainty].

Risks:
1. [Risk 1]
2. [Risk 2]

Recommendation: [Actionable next step]"

NEVER give a judgment answer without stating confidence level."""


# Singleton instance
conversation_manager = ConversationQualityManager()
