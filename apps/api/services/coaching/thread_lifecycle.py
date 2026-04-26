from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from models import CoachChat, CoachThreadSummary
from services.coaching.ledger import set_fact
from services.coaching.ledger_extraction import (
    extract_facts_from_turn,
)

IDLE_THREAD_CLOSE_AFTER = timedelta(hours=24)
RECENT_THREAD_LIMIT = 5
RECENT_THREADS_TOKEN_CAP = 2000


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _estimated_tokens(value: Any) -> int:
    text = json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)
    return max(1, len(text) // 4)


def should_close_for_idle(
    thread: CoachChat, *, now_utc: datetime | None = None
) -> bool:
    if not getattr(thread, "is_active", False):
        return False
    updated_at = getattr(thread, "updated_at", None)
    if updated_at is None:
        return False
    now = now_utc or _now()
    return _ensure_aware(updated_at) <= _ensure_aware(now) - IDLE_THREAD_CLOSE_AFTER


def _user_messages(thread: CoachChat) -> list[str]:
    rows = []
    for message in getattr(thread, "messages", None) or []:
        if (message.get("role") or "").lower() in {"user", "athlete"}:
            content = (message.get("content") or "").strip()
            if content:
                rows.append(content)
    return rows


def _topic_tags(text: str) -> list[str]:
    lower = text.lower()
    tags = []
    mapping = {
        "race": ("race", "5k", "10k", "half marathon", "marathon"),
        "weight_loss": ("weight", "pounds", "cut", "mass reduction"),
        "strength": ("deadlift", "strength", "lifting", "gym"),
        "injury": ("injury", "injured", "post injury", "calf", "knee", "achilles"),
        "nutrition": ("fueling", "breakfast", "gel", "nutrition"),
        "recovery": ("recovery", "sleep", "fatigue", "tired"),
    }
    for tag, terms in mapping.items():
        if any(term in lower for term in terms):
            tags.append(tag)
    return tags[:5] or ["general"]


def _open_questions(messages: list[str]) -> list[str]:
    questions = []
    for message in messages:
        if "?" in message:
            questions.append(message[:240])
    return questions[-5:]


def _decisions(messages: list[str]) -> list[str]:
    decisions = []
    decision_patterns = (
        r"\bmy plan is to\b(.+)",
        r"\bi'?ll\b(.+)",
        r"\bi will\b(.+)",
        r"\bi'm planning\b(.+)",
        r"\bi am planning\b(.+)",
    )
    for message in messages:
        for pattern in decision_patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                decisions.append(match.group(0).strip()[:240])
                break
    return decisions[-5:]


def generate_thread_summary_payload(
    thread: CoachChat,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated = generated_at or _now()
    messages = _user_messages(thread)
    text = "\n".join(messages)
    facts = []
    for message in messages:
        for fact in extract_facts_from_turn(
            thread.athlete_id,
            message,
            source=f"thread_close:{thread.id}",
            asserted_at=generated,
        ):
            facts.append(
                {
                    "field": fact.field,
                    "value": fact.value,
                    "confidence": fact.confidence,
                    "source": fact.source,
                    "asserted_at": (fact.asserted_at or generated).isoformat(),
                }
            )
    return {
        "topic_tags": _topic_tags(text),
        "decisions": _decisions(messages),
        "open_questions": _open_questions(messages),
        "stated_facts": facts,
    }


def close_thread(
    db: Session,
    thread: CoachChat,
    *,
    reason: str = "idle_timeout",
    now_utc: datetime | None = None,
) -> CoachThreadSummary:
    del reason
    generated = now_utc or _now()
    existing = (
        db.query(CoachThreadSummary)
        .filter(CoachThreadSummary.thread_id == thread.id)
        .one_or_none()
    )
    if existing is not None:
        thread.is_active = False
        db.flush()
        return existing

    payload = generate_thread_summary_payload(thread, generated_at=generated)
    summary = CoachThreadSummary(
        athlete_id=thread.athlete_id,
        thread_id=thread.id,
        generated_at=generated,
        topic_tags=payload["topic_tags"],
        decisions=payload["decisions"],
        open_questions=payload["open_questions"],
        stated_facts=payload["stated_facts"],
    )
    db.add(summary)
    thread.is_active = False
    for fact in payload["stated_facts"]:
        set_fact(
            db,
            thread.athlete_id,
            fact["field"],
            fact["value"],
            source=f"thread_close:{thread.id}",
            confidence="athlete_stated",
            asserted_at=generated,
        )
    db.flush()
    return summary


def close_idle_threads(
    db: Session,
    athlete_id: UUID,
    *,
    now_utc: datetime | None = None,
) -> list[CoachThreadSummary]:
    now = now_utc or _now()
    threads = (
        db.query(CoachChat)
        .filter(CoachChat.athlete_id == athlete_id, CoachChat.is_active.is_(True))
        .all()
    )
    summaries = []
    for thread in threads:
        if should_close_for_idle(thread, now_utc=now):
            summaries.append(close_thread(db, thread, now_utc=now))
    return summaries


def recent_threads_block(
    db: Session,
    athlete_id: UUID,
    *,
    limit: int = RECENT_THREAD_LIMIT,
) -> dict[str, Any]:
    summaries = (
        db.query(CoachThreadSummary)
        .filter(CoachThreadSummary.athlete_id == athlete_id)
        .order_by(CoachThreadSummary.generated_at.desc())
        .limit(limit)
        .all()
    )
    entries = [
        {
            "date": summary.generated_at.date().isoformat(),
            "topic_tags": summary.topic_tags or [],
            "decisions": summary.decisions or [],
            "open_questions": summary.open_questions or [],
            "stated_facts_summary": summary.stated_facts or [],
            "thread_id": str(summary.thread_id),
        }
        for summary in summaries
    ]
    while entries and _estimated_tokens(entries) > RECENT_THREADS_TOKEN_CAP:
        entries.pop()
    return {
        "schema_version": "coach_runtime_v2.recent_threads.v1",
        "status": "complete",
        "recent_threads": entries,
        "token_budget": {
            "max_tokens": RECENT_THREADS_TOKEN_CAP,
            "estimated_tokens": _estimated_tokens(entries),
        },
    }
