"""
Coach Modules Package (Phase 4/5 Refactor)

Modular architecture for the AI Coach service.

Modules:
- routing: Message classification and routing logic
- context: Context building for run instructions
- conversation: Conversation quality improvements (Phase 5)

Usage:
    from services.coach_modules import MessageRouter, MessageType, ContextBuilder
    from services.coach_modules.routing import router
    from services.coach_modules.context import context_builder
    from services.coach_modules.conversation import conversation_manager
"""

from .routing import (
    MessageRouter,
    MessageType,
    RETURN_CONTEXT_PHRASES,
    COMPARISON_KEYWORDS,
    router,
)
from .context import (
    ContextBuilder,
    context_builder,
)
from .conversation import (
    ConversationQualityManager,
    ConfidenceLevel,
    DetailLevel,
    conversation_manager,
    ANSWER_PATTERNS,
    CLARIFICATION_PATTERNS,
)

__all__ = [
    # Routing
    "MessageRouter",
    "MessageType",
    "RETURN_CONTEXT_PHRASES",
    "COMPARISON_KEYWORDS",
    "router",
    # Context
    "ContextBuilder",
    "context_builder",
    # Conversation Quality (Phase 5)
    "ConversationQualityManager",
    "ConfidenceLevel",
    "DetailLevel",
    "conversation_manager",
    "ANSWER_PATTERNS",
    "CLARIFICATION_PATTERNS",
]
