from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from models import Athlete, CoachChat, CoachThreadSummary
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
