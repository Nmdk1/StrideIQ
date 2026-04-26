from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from models import Athlete, CoachChat, CoachThreadSummary
from services.ai_coach import AICoach
from services.coaching.runtime_v2 import (
    RUNTIME_MODE_OFF,
    RUNTIME_VERSION_V1,
    CoachRuntimeV2State,
)
from services.coaching.ledger import get_ledger
from services.coaching.thread_lifecycle import (
    close_thread,
    generate_thread_summary_payload,
    recent_threads_block,
    should_close_for_idle,
)


def _thread(**overrides):
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    data = {
        "id": uuid4(),
        "athlete_id": uuid4(),
        "is_active": True,
        "updated_at": now - timedelta(hours=25),
        "messages": [
            {
                "role": "user",
                "content": "I'm a 60mpw runner and I'm 57. My plan is to race a sub 18 5k in fall. Should I keep speed?",
            },
            {"role": "assistant", "content": "ok"},
        ],
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_idle_timeout_closes_after_24_hours():
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)

    assert should_close_for_idle(_thread(updated_at=now - timedelta(hours=24))) is True
    assert (
        should_close_for_idle(
            _thread(updated_at=now - timedelta(hours=23, minutes=59)),
            now_utc=now,
        )
        is False
    )
    assert should_close_for_idle(_thread(is_active=False), now_utc=now) is False


def test_generate_thread_summary_extracts_facts_decisions_questions_and_tags():
    payload = generate_thread_summary_payload(
        _thread(),
        generated_at=datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc),
    )

    fields = {fact["field"] for fact in payload["stated_facts"]}
    assert {"weekly_volume_mpw", "age", "target_event"} <= fields
    assert payload["decisions"] == [
        "My plan is to race a sub 18 5k in fall. Should I keep speed?"
    ]
    assert payload["open_questions"] == [
        "I'm a 60mpw runner and I'm 57. My plan is to race a sub 18 5k in fall. Should I keep speed?"
    ]
    assert "race" in payload["topic_tags"]


def test_close_thread_writes_summary_and_facts_to_ledger(db_session):
    athlete = Athlete(
        email=f"thread_lifecycle_{uuid4()}@example.com",
        display_name="Thread Lifecycle Athlete",
        subscription_tier="guided",
        ai_consent=True,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    thread = CoachChat(
        athlete_id=athlete.id,
        context_type="open",
        messages=[
            {
                "role": "user",
                "content": "I'm a 60mpw runner and I'm 57.",
            }
        ],
        is_active=True,
        updated_at=datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc),
    )
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    summary = close_thread(
        db_session,
        thread,
        now_utc=datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    ledger = get_ledger(db_session, athlete.id)
    assert summary.thread_id == thread.id
    assert summary.stated_facts
    assert thread.is_active is False
    assert ledger.payload["weekly_volume_mpw"]["value"] == 60.0
    assert ledger.payload["age"]["value"] == 57


def test_thread_summary_cascades_when_athlete_deleted(db_session):
    athlete = Athlete(
        email=f"thread_summary_cascade_{uuid4()}@example.com",
        display_name="Thread Summary Cascade Athlete",
        subscription_tier="guided",
        ai_consent=True,
    )
    thread_owner = Athlete(
        email=f"thread_summary_owner_{uuid4()}@example.com",
        display_name="Thread Summary Owner",
        subscription_tier="guided",
        ai_consent=True,
    )
    db_session.add_all([athlete, thread_owner])
    db_session.commit()
    db_session.refresh(athlete)
    db_session.refresh(thread_owner)

    # Isolate the coach_thread_summary.athlete_id FK. coach_chat.athlete_id
    # is intentionally not part of this migration and does not cascade.
    thread = CoachChat(
        athlete_id=thread_owner.id,
        context_type="open",
        messages=[{"role": "user", "content": "Thread for FK target."}],
        is_active=False,
    )
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    summary = CoachThreadSummary(
        athlete_id=athlete.id,
        thread_id=thread.id,
        topic_tags=["race"],
        decisions=[],
        open_questions=[],
        stated_facts=[],
    )
    db_session.add(summary)
    db_session.commit()

    db_session.delete(athlete)
    db_session.commit()

    assert (
        db_session.query(CoachThreadSummary)
        .filter(CoachThreadSummary.athlete_id == athlete.id)
        .count()
        == 0
    )


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, value):
        self.rows = self.rows[:value]
        return self

    def all(self):
        return self.rows


class FakeDb:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return FakeQuery(self.rows if model.__name__ == "CoachThreadSummary" else [])


def test_recent_threads_block_limits_to_five_and_caps_tokens():
    athlete_id = uuid4()
    summaries = [
        SimpleNamespace(
            athlete_id=athlete_id,
            thread_id=uuid4(),
            generated_at=datetime(2026, 4, 26 - index, 12, 0, tzinfo=timezone.utc),
            topic_tags=["race"],
            decisions=["decision " + ("x" * 1000)],
            open_questions=[],
            stated_facts=[{"field": "age", "value": 57}],
        )
        for index in range(8)
    ]

    result = recent_threads_block(FakeDb(summaries), athlete_id)

    assert len(result["recent_threads"]) <= 5
    assert result["token_budget"]["estimated_tokens"] <= 2000
    assert result["recent_threads"][0]["date"] == "2026-04-26"


@pytest.mark.asyncio
async def test_chat_invokes_close_idle_threads(monkeypatch):
    import services.consent as consent_module
    from services.coaching import core as coach_core

    athlete_id = uuid4()
    db = MagicMock()
    closed_summary = SimpleNamespace(thread_id=uuid4())
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(coach_core.settings, "KIMI_API_KEY", "", raising=False)
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: CoachRuntimeV2State(
            runtime_mode=RUNTIME_MODE_OFF,
            runtime_version=RUNTIME_VERSION_V1,
            shadow_enabled=False,
            visible_enabled=False,
        ),
    )
    close_spy = MagicMock(return_value=[closed_summary])
    monkeypatch.setattr(coach_core, "close_idle_threads", close_spy)

    coach = AICoach.__new__(AICoach)
    coach.db = db
    coach.anthropic_client = None
    coach.gemini_client = None

    result = await coach.chat(athlete_id, "New thread starts now.")

    close_spy.assert_called_once_with(db, athlete_id)
    db.commit.assert_called_once()
    assert result["error"] is True
    assert result["runtime_mode"] == RUNTIME_MODE_OFF


@pytest.mark.asyncio
async def test_chat_invokes_close_idle_threads_persists_summary(
    db_session, monkeypatch
):
    import services.consent as consent_module
    from services.coaching import core as coach_core

    athlete = Athlete(
        email=f"chat_idle_close_{uuid4()}@example.com",
        display_name="Chat Idle Close Athlete",
        subscription_tier="guided",
        ai_consent=True,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    idle_thread = CoachChat(
        athlete_id=athlete.id,
        context_type="open",
        messages=[
            {
                "role": "user",
                "content": "I'm a 60mpw runner and I'm 57.",
                "timestamp": "2026-04-25T10:00:00+00:00",
            }
        ],
        is_active=True,
        updated_at=datetime.now(timezone.utc) - timedelta(hours=25),
    )
    db_session.add(idle_thread)
    db_session.commit()
    db_session.refresh(idle_thread)

    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(coach_core.settings, "KIMI_API_KEY", "", raising=False)
    monkeypatch.setattr(coach_core.settings, "ANTHROPIC_API_KEY", "", raising=False)
    monkeypatch.setattr(coach_core.settings, "GOOGLE_AI_API_KEY", "", raising=False)

    coach = AICoach(db_session)
    coach.anthropic_client = None
    coach.gemini_client = None

    result = await coach.chat(athlete.id, "New thread starts now.")

    db_session.refresh(idle_thread)
    summary = (
        db_session.query(CoachThreadSummary)
        .filter(CoachThreadSummary.thread_id == idle_thread.id)
        .one_or_none()
    )
    assert result["error"] is True
    assert idle_thread.is_active is False
    assert summary is not None
    assert summary.stated_facts
