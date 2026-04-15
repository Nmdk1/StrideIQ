from __future__ import annotations

import os
import json
import re
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from models import CoachChat  # noqa: E402


class ThreadMixin:
    """Mixin extracted from AICoach - thread methods."""

    def get_or_create_thread(self, athlete_id: UUID) -> Optional[str]:
        """
        Get or create a conversation thread for an athlete.
        
        Thread IDs are persisted on the Athlete record so conversation
        context survives across requests and page refreshes.
        """
        thread_id, _created = self.get_or_create_thread_with_state(athlete_id)
        return thread_id



    def get_or_create_thread_with_state(self, athlete_id: UUID) -> Tuple[Optional[str], bool]:
        """
        Get or create a conversation session for an athlete using PostgreSQL (CoachChat).

        Returns:
            (chat_id_str, created_new)
        """
        try:
            # Find the most recent active open chat session
            chat = (
                self.db.query(CoachChat)
                .filter(
                    CoachChat.athlete_id == athlete_id,
                    CoachChat.context_type == "open",
                    CoachChat.is_active == True,  # noqa: E712
                )
                .order_by(CoachChat.updated_at.desc())
                .first()
            )
            if chat:
                return str(chat.id), False

            # Create a new chat session
            chat = CoachChat(
                athlete_id=athlete_id,
                context_type="open",
                messages=[],
                is_active=True,
            )
            self.db.add(chat)
            self.db.commit()
            return str(chat.id), True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to get/create coach chat session: {e}")
            return None, False



    def get_thread_history(self, athlete_id: UUID, limit: int = 100) -> Dict[str, Any]:
        """
        Fetch persisted coach conversation messages from PostgreSQL (CoachChat).

        Returns:
            {"thread_id": str|None, "messages": [{"role","content","created_at"}]}
        """
        limit = max(1, min(int(limit), 500))

        try:
            chat = (
                self.db.query(CoachChat)
                .filter(
                    CoachChat.athlete_id == athlete_id,
                    CoachChat.context_type == "open",
                    CoachChat.is_active == True,  # noqa: E712
                )
                .order_by(CoachChat.updated_at.desc())
                .first()
            )
            if not chat or not chat.messages:
                return {"thread_id": str(chat.id) if chat else None, "messages": []}

            # Messages are stored chronologically in the JSONB array.
            # Return the last `limit` messages.
            all_msgs = chat.messages or []
            recent = all_msgs[-limit:] if len(all_msgs) > limit else all_msgs

            out: List[Dict[str, Any]] = []
            for m in recent:
                content = m.get("content", "")
                # Production-beta: hide internal context injections from UI/history.
                if (content or "").startswith("INTERNAL COACH CONTEXT"):
                    continue
                out.append({
                    "role": m.get("role", "assistant"),
                    "content": content,
                    "created_at": m.get("timestamp") or m.get("created_at"),
                })

            return {"thread_id": str(chat.id), "messages": out}
        except Exception as e:
            logger.warning(f"Failed to read coach chat history: {e}")
            return {"thread_id": None, "messages": []}



    def _save_chat_messages(
        self,
        athlete_id: UUID,
        user_message: str,
        assistant_response: str,
        model: Optional[str] = None,
    ) -> None:
        """Save user message and assistant response to PostgreSQL CoachChat."""
        try:
            chat = (
                self.db.query(CoachChat)
                .filter(
                    CoachChat.athlete_id == athlete_id,
                    CoachChat.context_type == "open",
                    CoachChat.is_active == True,  # noqa: E712
                )
                .order_by(CoachChat.updated_at.desc())
                .first()
            )
            if not chat:
                chat = CoachChat(
                    athlete_id=athlete_id,
                    context_type="open",
                    messages=[],
                    is_active=True,
                )
                self.db.add(chat)

            now_iso = datetime.utcnow().replace(microsecond=0).isoformat()
            msgs = list(chat.messages or [])
            msgs.append({"role": "user", "content": user_message, "timestamp": now_iso})
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": assistant_response,
                "timestamp": now_iso,
            }
            if model:
                assistant_msg["model"] = model
            msgs.append(assistant_msg)
            chat.messages = msgs
            # Force SQLAlchemy to detect the JSONB change
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(chat, "messages")
            self.db.commit()

            # Fire-and-forget fact extraction (async, non-blocking)
            try:
                from tasks.fact_extraction_task import extract_athlete_facts
                extract_athlete_facts.delay(str(athlete_id), str(chat.id))
            except Exception as fe:
                logger.warning(f"Failed to enqueue fact extraction: {fe}")
        except Exception as e:
            self.db.rollback()
            logger.warning(f"Failed to save coach chat messages: {e}")
    


