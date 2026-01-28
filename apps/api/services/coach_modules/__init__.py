"""
Coach Modules Package (Phase 4 Refactor)

Modular architecture for the AI Coach service.

Modules:
- routing: Message classification and routing logic
- context: Context building for run instructions

Usage:
    from services.coach_modules import MessageRouter, MessageType, ContextBuilder
    from services.coach_modules.routing import router
    from services.coach_modules.context import context_builder
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
]
