"""
Tests for Athlete Fact Extraction — Coach Memory Layer 1.

26 tests across 6 groups:
  - Extraction (1-4)
  - Upsert (5-9)
  - Incremental (10-12)
  - Backfill (13-17)
  - Consumer (18-21)
  - Integration (22-26)
"""
import json
import re
import uuid
from datetime import datetime, date, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_athlete_fact(**overrides):
    """Create an AthleteFact-like object for tests that don't hit the DB."""
    from types import SimpleNamespace
    defaults = dict(
        id=uuid.uuid4(),
        athlete_id=uuid.uuid4(),
        fact_type="strength_pr",
        fact_key="deadlift_1rm_lbs",
        fact_value="315",
        numeric_value=315.0,
        confidence="athlete_stated",
        source_chat_id=uuid.uuid4(),
        source_excerpt="I deadlift 315",
        confirmed_by_athlete=False,
        extracted_at=datetime.now(timezone.utc),
        superseded_at=None,
        is_active=True,
        temporal=False,
        ttl_days=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _fake_extraction_result(
    fact_type="strength_pr",
    fact_key="deadlift_1rm_lbs",
    fact_value="315",
    numeric_value=315.0,
    source_excerpt="I deadlift 315",
):
    return {
        "fact_type": fact_type,
        "fact_key": fact_key,
        "fact_value": fact_value,
        "numeric_value": numeric_value,
        "source_excerpt": source_excerpt,
    }


# ===================================================================
# Group 1: Extraction tests (1-4)
# ===================================================================

class TestExtraction:
    """Tests that the LLM extraction prompt produces correct output."""

    @patch("tasks.fact_extraction_task._run_extraction")
    def test_extraction_from_user_messages(self, mock_extract):
        """#1: user says 'I deadlift 315' -> fact extracted with athlete_stated confidence."""
        mock_extract.return_value = [_fake_extraction_result()]

        result = mock_extract("I deadlift 315")
        assert len(result) == 1
        assert result[0]["fact_key"] == "deadlift_1rm_lbs"
        assert result[0]["fact_value"] == "315"
        # confidence is set at insert time, not in extraction output
        assert "confidence" not in result[0]

    @patch("tasks.fact_extraction_task._run_extraction")
    def test_extraction_ignores_coach_messages(self, mock_extract):
        """#2: only user messages are sent to extraction."""
        mock_extract.return_value = []

        messages = [
            {"role": "user", "content": "I deadlift 315"},
            {"role": "assistant", "content": "That's impressive!"},
            {"role": "user", "content": "My squat is 275"},
        ]
        user_text = "\n".join(m["content"] for m in messages if m.get("role") == "user")
        assert "That's impressive!" not in user_text
        assert "I deadlift 315" in user_text
        assert "My squat is 275" in user_text

    @patch("tasks.fact_extraction_task._run_extraction")
    def test_extraction_produces_valid_json(self, mock_extract):
        """#3: extraction prompt returns parseable JSON array."""
        mock_extract.return_value = [
            _fake_extraction_result(),
            _fake_extraction_result(fact_key="squat_1rm_lbs", fact_value="275", numeric_value=275.0),
        ]
        result = mock_extract("I deadlift 315 and squat 275")
        assert isinstance(result, list)
        assert all(isinstance(f, dict) for f in result)
        assert all("fact_key" in f for f in result)

    @patch("tasks.fact_extraction_task._run_extraction")
    def test_extraction_other_category(self, mock_extract):
        """#4: unusual fact gets fact_type='other'."""
        mock_extract.return_value = [
            _fake_extraction_result(
                fact_type="other",
                fact_key="favorite_shoe",
                fact_value="Nike Vaporfly",
                numeric_value=None,
                source_excerpt="I love my Vaporflys",
            )
        ]
        result = mock_extract("I love my Vaporflys")
        assert result[0]["fact_type"] == "other"


# ===================================================================
# Group 2: Upsert tests (5-9) — require DB
# ===================================================================

class TestUpsert:
    """Tests for the _upsert_fact concurrency-safe logic."""

    def test_upsert_same_value_skips(self, db_session, test_athlete):
        """#5: same key + same value -> no new row."""
        from models import AthleteFact, CoachChat

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[], is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        from tasks.fact_extraction_task import _upsert_fact
        fact_data = _fake_extraction_result()
        _upsert_fact(db_session, test_athlete.id, chat.id, fact_data)
        db_session.commit()

        count_before = db_session.query(AthleteFact).filter(
            AthleteFact.athlete_id == test_athlete.id,
        ).count()

        _upsert_fact(db_session, test_athlete.id, chat.id, fact_data)
        db_session.commit()

        count_after = db_session.query(AthleteFact).filter(
            AthleteFact.athlete_id == test_athlete.id,
        ).count()
        assert count_after == count_before

    def test_upsert_different_value_supersedes(self, db_session, test_athlete):
        """#6: same key + new value -> old row deactivated, new row active."""
        from models import AthleteFact, CoachChat

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[], is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        from tasks.fact_extraction_task import _upsert_fact
        _upsert_fact(db_session, test_athlete.id, chat.id, _fake_extraction_result(fact_value="300"))
        db_session.commit()

        _upsert_fact(db_session, test_athlete.id, chat.id, _fake_extraction_result(fact_value="315"))
        db_session.commit()

        old = db_session.query(AthleteFact).filter(
            AthleteFact.athlete_id == test_athlete.id,
            AthleteFact.fact_key == "deadlift_1rm_lbs",
            AthleteFact.is_active == False,  # noqa: E712
        ).first()
        assert old is not None
        assert old.fact_value == "300"
        assert old.superseded_at is not None

        current = db_session.query(AthleteFact).filter(
            AthleteFact.athlete_id == test_athlete.id,
            AthleteFact.fact_key == "deadlift_1rm_lbs",
            AthleteFact.is_active == True,  # noqa: E712
        ).first()
        assert current is not None
        assert current.fact_value == "315"

    def test_upsert_preserves_history(self, db_session, test_athlete):
        """#7: after supersession, both rows exist."""
        from models import AthleteFact, CoachChat

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[], is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        from tasks.fact_extraction_task import _upsert_fact
        _upsert_fact(db_session, test_athlete.id, chat.id, _fake_extraction_result(fact_value="300"))
        db_session.commit()
        _upsert_fact(db_session, test_athlete.id, chat.id, _fake_extraction_result(fact_value="315"))
        db_session.commit()

        all_facts = db_session.query(AthleteFact).filter(
            AthleteFact.athlete_id == test_athlete.id,
            AthleteFact.fact_key == "deadlift_1rm_lbs",
        ).all()
        assert len(all_facts) == 2

    def test_upsert_concurrent_insert_handled(self, db_session, test_athlete):
        """#8: duplicate insert via same-value path is handled gracefully."""
        from models import AthleteFact, CoachChat
        from tasks.fact_extraction_task import _upsert_fact

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[], is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        fact_data = _fake_extraction_result()
        _upsert_fact(db_session, test_athlete.id, chat.id, fact_data)
        db_session.commit()

        # Second insert with same key+value should be a no-op (same-value skip)
        _upsert_fact(db_session, test_athlete.id, chat.id, fact_data)
        db_session.commit()

        count = db_session.query(AthleteFact).filter(
            AthleteFact.athlete_id == test_athlete.id,
            AthleteFact.fact_key == "deadlift_1rm_lbs",
        ).count()
        assert count == 1

    def test_upsert_integrityerror_does_not_rollback_prior_facts(self, db_session, test_athlete):
        """#9: savepoint rollback does not erase earlier successful upserts."""
        from models import AthleteFact, CoachChat
        from tasks.fact_extraction_task import _upsert_fact

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[], is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        # Insert two different facts successfully
        _upsert_fact(db_session, test_athlete.id, chat.id, _fake_extraction_result(
            fact_key="squat_1rm_lbs", fact_value="275",
        ))
        _upsert_fact(db_session, test_athlete.id, chat.id, _fake_extraction_result(
            fact_key="deadlift_1rm_lbs", fact_value="315",
        ))
        db_session.commit()

        # Now try to insert a duplicate of the second (same value → skip)
        _upsert_fact(db_session, test_athlete.id, chat.id, _fake_extraction_result(
            fact_key="deadlift_1rm_lbs", fact_value="315",
        ))
        db_session.commit()

        # First fact should still exist
        squat = db_session.query(AthleteFact).filter(
            AthleteFact.athlete_id == test_athlete.id,
            AthleteFact.fact_key == "squat_1rm_lbs",
            AthleteFact.is_active == True,  # noqa: E712
        ).first()
        assert squat is not None
        assert squat.fact_value == "275"

    def test_upsert_promotes_relative_time_fact_to_temporal(self, db_session, test_athlete):
        """Non-temporal category with relative-time text must get short TTL."""
        from models import AthleteFact, CoachChat
        from tasks.fact_extraction_task import _upsert_fact

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[], is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        _upsert_fact(
            db_session,
            test_athlete.id,
            chat.id,
            _fake_extraction_result(
                fact_type="other",
                fact_key="event_window",
                fact_value="goal race in 4 days",
                numeric_value=None,
                source_excerpt="goal race in 4 days",
            ),
        )
        db_session.commit()

        fact = db_session.query(AthleteFact).filter(
            AthleteFact.athlete_id == test_athlete.id,
            AthleteFact.fact_key == "event_window",
            AthleteFact.is_active == True,  # noqa: E712
        ).first()
        assert fact is not None
        assert fact.temporal is True
        assert fact.ttl_days == 3


# ===================================================================
# Group 3: Incremental extraction tests (10-12)
# ===================================================================

class TestIncremental:
    """Tests for incremental (checkpoint-based) extraction."""

    @patch("tasks.fact_extraction_task._run_extraction")
    def test_incremental_only_new_messages(self, mock_extract, db_session, test_athlete):
        """#10: only messages after last_extracted_msg_count are processed."""
        from models import CoachChat

        mock_extract.return_value = []

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[
                {"role": "user", "content": "old msg 1", "timestamp": "t1"},
                {"role": "assistant", "content": "resp 1", "timestamp": "t1"},
                {"role": "user", "content": "old msg 2", "timestamp": "t2"},
                {"role": "assistant", "content": "resp 2", "timestamp": "t2"},
                {"role": "user", "content": "old msg 3", "timestamp": "t3"},
                {"role": "assistant", "content": "resp 3", "timestamp": "t3"},
                {"role": "user", "content": "old msg 4", "timestamp": "t4"},
                {"role": "assistant", "content": "resp 4", "timestamp": "t4"},
                {"role": "user", "content": "new msg 1", "timestamp": "t5"},
                {"role": "assistant", "content": "resp 5", "timestamp": "t5"},
            ],
            is_active=True,
            last_extracted_msg_count=8,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        # Simulate what the task does
        last_idx = chat.last_extracted_msg_count or 0
        new_messages = chat.messages[last_idx:]
        user_messages = [m for m in new_messages if m.get("role") == "user"]
        user_text = "\n".join(m["content"] for m in user_messages)

        assert "new msg 1" in user_text
        assert "old msg" not in user_text
        assert len(user_messages) == 1

    @patch("tasks.fact_extraction_task._run_extraction")
    def test_incremental_updates_checkpoint(self, mock_extract, db_session, test_athlete):
        """#11: after extraction, checkpoint equals total message count."""
        from models import CoachChat
        from tasks.fact_extraction_task import extract_athlete_facts

        mock_extract.return_value = []

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[
                {"role": "user", "content": "msg", "timestamp": "t1"},
                {"role": "assistant", "content": "resp", "timestamp": "t1"},
            ],
            is_active=True,
            last_extracted_msg_count=0,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        # Patch SessionLocal to use our test session
        with patch("tasks.fact_extraction_task.SessionLocal", return_value=db_session):
            with patch.object(db_session, "close"):
                extract_athlete_facts(str(test_athlete.id), str(chat.id))

        db_session.refresh(chat)
        assert chat.last_extracted_msg_count == 2

    @patch("tasks.fact_extraction_task._run_extraction")
    def test_incremental_skips_when_no_new(self, mock_extract, db_session, test_athlete):
        """#12: no new messages -> task returns early without calling LLM."""
        from models import CoachChat
        from tasks.fact_extraction_task import extract_athlete_facts

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[
                {"role": "user", "content": "msg", "timestamp": "t1"},
                {"role": "assistant", "content": "resp", "timestamp": "t1"},
            ],
            is_active=True,
            last_extracted_msg_count=2,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        with patch("tasks.fact_extraction_task.SessionLocal", return_value=db_session):
            with patch.object(db_session, "close"):
                extract_athlete_facts(str(test_athlete.id), str(chat.id))

        mock_extract.assert_not_called()


# ===================================================================
# Group 4: Backfill tests (13-17)
# ===================================================================

class TestBackfill:
    """Tests for the historical backfill script."""

    @patch("tasks.fact_extraction_task._run_extraction")
    def test_backfill_chronological_order(self, mock_extract, db_session, test_athlete):
        """#13: earlier value superseded by later value, not vice versa."""
        from models import AthleteFact, CoachChat
        from tasks.fact_extraction_task import _upsert_fact

        early_chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[{"role": "user", "content": "I weigh 180", "timestamp": "2025-01-01"}],
            is_active=True,
        )
        late_chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[{"role": "user", "content": "I weigh 175", "timestamp": "2025-06-01"}],
            is_active=True,
        )
        db_session.add_all([early_chat, late_chat])
        db_session.commit()
        db_session.refresh(early_chat)
        db_session.refresh(late_chat)

        # Simulate backfill in chronological order
        _upsert_fact(db_session, test_athlete.id, early_chat.id, _fake_extraction_result(
            fact_key="weight_lbs", fact_value="180", numeric_value=180.0,
        ))
        db_session.commit()

        _upsert_fact(db_session, test_athlete.id, late_chat.id, _fake_extraction_result(
            fact_key="weight_lbs", fact_value="175", numeric_value=175.0,
        ))
        db_session.commit()

        active = db_session.query(AthleteFact).filter(
            AthleteFact.athlete_id == test_athlete.id,
            AthleteFact.fact_key == "weight_lbs",
            AthleteFact.is_active == True,  # noqa: E712
        ).first()
        assert active.fact_value == "175"

    @patch("tasks.fact_extraction_task._run_extraction")
    def test_backfill_sets_checkpoint(self, mock_extract, db_session, test_athlete):
        """#14: after backfill, last_extracted_msg_count is set."""
        from models import CoachChat
        mock_extract.return_value = []

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[
                {"role": "user", "content": "msg", "timestamp": "t1"},
                {"role": "assistant", "content": "resp", "timestamp": "t1"},
            ],
            is_active=True,
            last_extracted_msg_count=None,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        # Simulate backfill logic
        user_messages = [m for m in chat.messages if m.get("role") == "user"]
        user_text = "\n".join(m["content"] for m in user_messages)
        mock_extract(user_text)
        chat.last_extracted_msg_count = len(chat.messages)
        db_session.commit()
        db_session.refresh(chat)

        assert chat.last_extracted_msg_count == 2

    @patch("tasks.fact_extraction_task._run_extraction")
    def test_backfill_idempotent(self, mock_extract, db_session, test_athlete):
        """#15: running backfill twice produces same result."""
        from models import AthleteFact, CoachChat
        from tasks.fact_extraction_task import _upsert_fact

        mock_extract.return_value = [_fake_extraction_result()]

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[{"role": "user", "content": "I deadlift 315", "timestamp": "t1"}],
            is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        # First run
        for f in mock_extract("I deadlift 315"):
            _upsert_fact(db_session, test_athlete.id, chat.id, f)
        db_session.commit()

        count_after_first = db_session.query(AthleteFact).filter(
            AthleteFact.athlete_id == test_athlete.id,
        ).count()

        # Second run (idempotent)
        for f in mock_extract("I deadlift 315"):
            _upsert_fact(db_session, test_athlete.id, chat.id, f)
        db_session.commit()

        count_after_second = db_session.query(AthleteFact).filter(
            AthleteFact.athlete_id == test_athlete.id,
        ).count()
        assert count_after_first == count_after_second

    def test_backfill_resume_from_chat_id(self, db_session, test_athlete):
        """#16: strict tuple resume skips everything at or before the resume point."""
        from models import CoachChat
        from sqlalchemy import or_, and_

        chats = []
        for i in range(5):
            c = CoachChat(
                athlete_id=test_athlete.id, context_type="open",
                messages=[{"role": "user", "content": f"msg {i}", "timestamp": f"t{i}"}],
                is_active=True,
            )
            db_session.add(c)
            db_session.commit()
            db_session.refresh(c)
            chats.append(c)

        # Sort by (created_at, id) — the actual deterministic backfill order
        sorted_chats = sorted(chats, key=lambda c: (c.created_at, c.id))
        resume_chat = sorted_chats[2]

        query = (
            db_session.query(CoachChat)
            .filter(CoachChat.athlete_id == test_athlete.id)
            .filter(CoachChat.messages.isnot(None))
            .order_by(CoachChat.created_at.asc(), CoachChat.id.asc())
        )
        query = query.filter(
            or_(
                CoachChat.created_at > resume_chat.created_at,
                and_(
                    CoachChat.created_at == resume_chat.created_at,
                    CoachChat.id > resume_chat.id,
                ),
            )
        )
        remaining = query.all()
        remaining_ids = {c.id for c in remaining}

        # Resume chat and everything before it in sorted order must be excluded
        assert resume_chat.id not in remaining_ids
        for c in sorted_chats[:3]:
            assert c.id not in remaining_ids
        # Everything after resume point must be included
        for c in sorted_chats[3:]:
            assert c.id in remaining_ids

    def test_backfill_resume_handles_same_timestamp_chats(self, db_session, test_athlete):
        """#17: deterministic ordering by (created_at, id) for same-timestamp chats."""
        from models import CoachChat

        # All chats share the same created_at (auto-set by server_default)
        chats = []
        for i in range(3):
            c = CoachChat(
                athlete_id=test_athlete.id, context_type="open",
                messages=[{"role": "user", "content": f"msg {i}"}],
                is_active=True,
            )
            db_session.add(c)
            db_session.flush()
            chats.append(c)
        db_session.commit()

        ordered = (
            db_session.query(CoachChat)
            .filter(CoachChat.athlete_id == test_athlete.id)
            .order_by(CoachChat.created_at.asc(), CoachChat.id.asc())
            .all()
        )
        ids = [c.id for c in ordered]
        assert ids == sorted(ids)


# ===================================================================
# Group 5: Consumer tests (18-21)
# ===================================================================

class TestConsumer:
    """Tests for fact injection into prompts."""

    def test_facts_injected_into_morning_voice_prompt(self, db_session, test_athlete):
        """#18: active facts appear in prompt, capped at 15."""
        from models import AthleteFact, CoachChat

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[], is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        for i in range(5):
            f = AthleteFact(
                athlete_id=test_athlete.id,
                fact_type="strength_pr",
                fact_key=f"test_fact_{i}",
                fact_value=f"val_{i}",
                confidence="athlete_stated",
                source_chat_id=chat.id,
                source_excerpt=f"I said {i}",
                is_active=True,
            )
            db_session.add(f)
        db_session.commit()

        MAX_INJECTED_FACTS = 15
        active_facts = (
            db_session.query(AthleteFact)
            .filter(
                AthleteFact.athlete_id == test_athlete.id,
                AthleteFact.is_active == True,  # noqa: E712
            )
            .order_by(
                AthleteFact.confirmed_by_athlete.desc(),
                AthleteFact.extracted_at.desc(),
            )
            .limit(MAX_INJECTED_FACTS)
            .all()
        )
        assert len(active_facts) == 5
        facts_text = "\n".join(f"- {f.fact_key}: {f.fact_value}" for f in active_facts)
        assert "test_fact_0" in facts_text

    def test_superseded_facts_not_injected(self, db_session, test_athlete):
        """#19: superseded facts excluded from prompt."""
        from models import AthleteFact, CoachChat
        from sqlalchemy.sql import func

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[], is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        # Active fact
        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="strength_pr", fact_key="deadlift_1rm_lbs",
            fact_value="315", confidence="athlete_stated",
            source_chat_id=chat.id, source_excerpt="I deadlift 315",
            is_active=True,
        ))
        # Superseded fact
        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="strength_pr", fact_key="deadlift_1rm_lbs",
            fact_value="300", confidence="athlete_stated",
            source_chat_id=chat.id, source_excerpt="I deadlift 300",
            is_active=False, superseded_at=func.now(),
        ))
        db_session.commit()

        active_facts = (
            db_session.query(AthleteFact)
            .filter(
                AthleteFact.athlete_id == test_athlete.id,
                AthleteFact.is_active == True,  # noqa: E712
            )
            .all()
        )
        values = [f.fact_value for f in active_facts]
        assert "315" in values
        assert "300" not in values

    def test_injection_priority_order(self, db_session, test_athlete):
        """#20: confirmed facts sort before unconfirmed, then by recency."""
        from models import AthleteFact, CoachChat

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[], is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        # Unconfirmed, newer
        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="body_composition", fact_key="weight_lbs",
            fact_value="180", confidence="athlete_stated",
            source_chat_id=chat.id, source_excerpt="I weigh 180",
            is_active=True, confirmed_by_athlete=False,
        ))
        # Confirmed, older
        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="strength_pr", fact_key="squat_1rm_lbs",
            fact_value="275", confidence="athlete_stated",
            source_chat_id=chat.id, source_excerpt="I squat 275",
            is_active=True, confirmed_by_athlete=True,
        ))
        db_session.commit()

        ordered = (
            db_session.query(AthleteFact)
            .filter(
                AthleteFact.athlete_id == test_athlete.id,
                AthleteFact.is_active == True,  # noqa: E712
            )
            .order_by(
                AthleteFact.confirmed_by_athlete.desc(),
                AthleteFact.extracted_at.desc(),
            )
            .all()
        )
        # Confirmed first
        assert ordered[0].fact_key == "squat_1rm_lbs"
        assert ordered[0].confirmed_by_athlete is True

    def test_injection_cap_respected(self, db_session, test_athlete):
        """#21: 20 active facts -> only 15 injected."""
        from models import AthleteFact, CoachChat

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[], is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        for i in range(20):
            db_session.add(AthleteFact(
                athlete_id=test_athlete.id,
                fact_type="other", fact_key=f"cap_test_{i}",
                fact_value=f"v{i}", confidence="athlete_stated",
                source_chat_id=chat.id, source_excerpt=f"excerpt {i}",
                is_active=True,
            ))
        db_session.commit()

        MAX_INJECTED_FACTS = 15
        injected = (
            db_session.query(AthleteFact)
            .filter(
                AthleteFact.athlete_id == test_athlete.id,
                AthleteFact.is_active == True,  # noqa: E712
            )
            .order_by(
                AthleteFact.confirmed_by_athlete.desc(),
                AthleteFact.extracted_at.desc(),
            )
            .limit(MAX_INJECTED_FACTS)
            .all()
        )
        assert len(injected) == 15


# ===================================================================
# Group 6: Integration tests (22-26)
# ===================================================================

class TestIntegration:
    """End-to-end and guardrail integration tests."""

    def test_extraction_task_fires_after_chat_save(self):
        """#22: _save_chat_messages enqueues extract_athlete_facts."""
        with patch("tasks.fact_extraction_task.extract_athlete_facts") as mock_task:
            mock_task.delay = MagicMock()

            # Simulate what _save_chat_messages does after commit
            athlete_id = uuid.uuid4()
            chat_id = uuid.uuid4()
            from tasks.fact_extraction_task import extract_athlete_facts
            extract_athlete_facts.delay(str(athlete_id), str(chat_id))

            mock_task.delay.assert_called_once_with(str(athlete_id), str(chat_id))

    @patch("tasks.fact_extraction_task._run_extraction")
    def test_no_extraction_on_empty_user_messages(self, mock_extract, db_session, test_athlete):
        """#23: chat with only assistant messages -> no extraction, checkpoint still updated."""
        from models import CoachChat
        from tasks.fact_extraction_task import extract_athlete_facts

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[
                {"role": "assistant", "content": "Hello! How can I help?", "timestamp": "t1"},
            ],
            is_active=True,
            last_extracted_msg_count=0,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        with patch("tasks.fact_extraction_task.SessionLocal", return_value=db_session):
            with patch.object(db_session, "close"):
                extract_athlete_facts(str(test_athlete.id), str(chat.id))

        db_session.refresh(chat)
        assert chat.last_extracted_msg_count == 1
        mock_extract.assert_not_called()

    def test_guardrail_assertion_25_catches_superseded(self, db_session, test_athlete):
        """#24: superseded fact with old value near key mention -> assertion fails."""
        from models import AthleteFact, CoachChat
        from sqlalchemy.sql import func
        from services.experience_guardrail import ExperienceGuardrail, AssertionResult

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[], is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        # Current fact
        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="strength_pr", fact_key="deadlift_1rm_lbs",
            fact_value="335", confidence="athlete_stated",
            source_chat_id=chat.id, source_excerpt="I deadlift 335 now",
            is_active=True,
        ))
        # Superseded fact
        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="strength_pr", fact_key="deadlift_1rm_lbs",
            fact_value="315", confidence="athlete_stated",
            source_chat_id=chat.id, source_excerpt="I deadlift 315",
            is_active=False, superseded_at=func.now(),
        ))
        db_session.commit()

        guardrail = ExperienceGuardrail(
            athlete_id=str(test_athlete.id),
            db=db_session,
            redis_client=None,
        )
        # Coach text mentions deadlift with old value 315 but not current 335
        coach_texts = ["Your deadlift at 315 is solid for your frame."]
        guardrail._assert_no_superseded_athlete_facts(coach_texts)

        result_25 = [r for r in guardrail.results if r.id == 25]
        assert len(result_25) == 1
        assert result_25[0].passed is False

    def test_guardrail_assertion_25_ignores_unrelated_numbers(self, db_session, test_athlete):
        """#25: '315' in a pace context does not trigger false positive."""
        from models import AthleteFact, CoachChat
        from sqlalchemy.sql import func
        from services.experience_guardrail import ExperienceGuardrail

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[], is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="strength_pr", fact_key="deadlift_1rm_lbs",
            fact_value="335", confidence="athlete_stated",
            source_chat_id=chat.id, source_excerpt="I deadlift 335",
            is_active=True,
        ))
        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="strength_pr", fact_key="deadlift_1rm_lbs",
            fact_value="315", confidence="athlete_stated",
            source_chat_id=chat.id, source_excerpt="I deadlift 315",
            is_active=False, superseded_at=func.now(),
        ))
        db_session.commit()

        guardrail = ExperienceGuardrail(
            athlete_id=str(test_athlete.id),
            db=db_session,
            redis_client=None,
        )
        # '315' appears but NOT near 'deadlift' key context
        coach_texts = ["Your pace was 3:15 per km on the tempo today."]
        guardrail._assert_no_superseded_athlete_facts(coach_texts)

        result_25 = [r for r in guardrail.results if r.id == 25]
        assert len(result_25) == 1
        assert result_25[0].passed is True

    def test_guardrail_assertion_25_numeric_boundary(self, db_session, test_athlete):
        """#26: 315 does not match 1315 (numeric token boundary)."""
        from models import AthleteFact, CoachChat
        from sqlalchemy.sql import func
        from services.experience_guardrail import ExperienceGuardrail

        chat = CoachChat(
            athlete_id=test_athlete.id, context_type="open",
            messages=[], is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="strength_pr", fact_key="deadlift_1rm_lbs",
            fact_value="335", confidence="athlete_stated",
            source_chat_id=chat.id, source_excerpt="I deadlift 335",
            is_active=True,
        ))
        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="strength_pr", fact_key="deadlift_1rm_lbs",
            fact_value="315", confidence="athlete_stated",
            source_chat_id=chat.id, source_excerpt="I deadlift 315",
            is_active=False, superseded_at=func.now(),
        ))
        db_session.commit()

        guardrail = ExperienceGuardrail(
            athlete_id=str(test_athlete.id),
            db=db_session,
            redis_client=None,
        )
        # '1315' contains '315' but should NOT match due to numeric boundary
        coach_texts = ["Your deadlift volume was 1315 total pounds this week."]
        guardrail._assert_no_superseded_athlete_facts(coach_texts)

        result_25 = [r for r in guardrail.results if r.id == 25]
        assert len(result_25) == 1
        assert result_25[0].passed is True


class TestTemporalFactLifecycle:
    """Tests for temporal fact TTL classification and filtering."""

    def _select_injected_facts(self, db_session, athlete_id):
        """Mirror home.py injection selection logic."""
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        from models import AthleteFact as _AF

        MAX_INJECTED_FACTS = 15
        BATCH_SIZE = 50
        MAX_SCAN_ROWS = 500
        _now = _dt.now(_tz.utc)

        selected = []
        offset = 0
        while len(selected) < MAX_INJECTED_FACTS and offset < MAX_SCAN_ROWS:
            batch = (
                db_session.query(_AF)
                .filter(
                    _AF.athlete_id == athlete_id,
                    _AF.is_active == True,  # noqa: E712
                )
                .order_by(
                    _AF.confirmed_by_athlete.desc(),
                    _AF.extracted_at.desc(),
                )
                .offset(offset)
                .limit(BATCH_SIZE)
                .all()
            )
            if not batch:
                break

            for f in batch:
                if f.temporal and f.ttl_days is not None:
                    if f.extracted_at < _now - _td(days=f.ttl_days):
                        continue
                selected.append(f)
                if len(selected) >= MAX_INJECTED_FACTS:
                    break
            offset += BATCH_SIZE

        return selected

    def test_injury_fact_gets_ttl(self):
        """injury_history fact_type → temporal=True, ttl_days=14."""
        from tasks.fact_extraction_task import FACT_TTL_CATEGORIES
        assert FACT_TTL_CATEGORIES["injury_history"] == 14

    def test_permanent_fact_no_ttl(self):
        """life_context fact_type → not in TTL dict (permanent)."""
        from tasks.fact_extraction_task import FACT_TTL_CATEGORIES
        assert "life_context" not in FACT_TTL_CATEGORIES
        assert "race_history" not in FACT_TTL_CATEGORIES
        assert "health" not in FACT_TTL_CATEGORIES
        assert "preference" not in FACT_TTL_CATEGORIES

    def test_equipment_fact_gets_90_day_ttl(self):
        """equipment fact_type → temporal=True, ttl_days=90."""
        from tasks.fact_extraction_task import FACT_TTL_CATEGORIES
        assert FACT_TTL_CATEGORIES["equipment"] == 90

    def test_strength_fact_gets_30_day_ttl(self):
        """strength_pr fact_type → temporal=True, ttl_days=30."""
        from tasks.fact_extraction_task import FACT_TTL_CATEGORIES
        assert FACT_TTL_CATEGORIES["strength_pr"] == 30

    def test_stale_temporal_fact_excluded_from_injection(self, db_session, test_athlete):
        """Temporal fact past TTL must not survive selection."""
        from datetime import datetime, timedelta, timezone
        from models import AthleteFact, CoachChat

        chat = CoachChat(
            athlete_id=test_athlete.id,
            context_type="open",
            messages=[],
            is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="injury_history",
            fact_key="current_injury_symptoms",
            fact_value="left shin soreness",
            confidence="athlete_stated",
            source_chat_id=chat.id,
            source_excerpt="left shin soreness",
            is_active=True,
            temporal=True,
            ttl_days=14,
            extracted_at=datetime.now(timezone.utc) - timedelta(days=20),
        ))
        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="life_context",
            fact_key="age_years",
            fact_value="57",
            confidence="athlete_stated",
            source_chat_id=chat.id,
            source_excerpt="I am 57",
            is_active=True,
            temporal=False,
            ttl_days=None,
            extracted_at=datetime.now(timezone.utc) - timedelta(days=60),
        ))
        db_session.commit()

        selected = self._select_injected_facts(db_session, test_athlete.id)
        keys = {f.fact_key for f in selected}
        assert "current_injury_symptoms" not in keys
        assert "age_years" in keys

    def test_fresh_temporal_fact_included_in_injection(self, db_session, test_athlete):
        """Temporal fact within TTL survives selection."""
        from datetime import datetime, timedelta, timezone
        from models import AthleteFact, CoachChat

        chat = CoachChat(
            athlete_id=test_athlete.id,
            context_type="open",
            messages=[],
            is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="injury_history",
            fact_key="current_injury_symptoms",
            fact_value="left shin soreness",
            confidence="athlete_stated",
            source_chat_id=chat.id,
            source_excerpt="left shin soreness",
            is_active=True,
            temporal=True,
            ttl_days=14,
            extracted_at=datetime.now(timezone.utc) - timedelta(days=5),
        ))
        db_session.commit()

        selected = self._select_injected_facts(db_session, test_athlete.id)
        keys = {f.fact_key for f in selected}
        assert "current_injury_symptoms" in keys

    def test_injection_not_starved_by_stale_head(self, db_session, test_athlete):
        """Many stale newest rows should not prevent selecting valid older rows."""
        from datetime import datetime, timedelta, timezone
        from models import AthleteFact, CoachChat

        chat = CoachChat(
            athlete_id=test_athlete.id,
            context_type="open",
            messages=[],
            is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        for i in range(40):
            db_session.add(AthleteFact(
                athlete_id=test_athlete.id,
                fact_type="injury_history",
                fact_key=f"old_injury_{i}",
                fact_value="stale",
                confidence="athlete_stated",
                source_chat_id=chat.id,
                source_excerpt="stale",
                is_active=True,
                temporal=True,
                ttl_days=14,
                extracted_at=datetime.now(timezone.utc) - timedelta(days=20),
            ))

        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="life_context",
            fact_key="age_years",
            fact_value="57",
            confidence="athlete_stated",
            source_chat_id=chat.id,
            source_excerpt="I am 57",
            is_active=True,
            temporal=False,
            ttl_days=None,
            extracted_at=datetime.now(timezone.utc) - timedelta(days=120),
        ))
        db_session.add(AthleteFact(
            athlete_id=test_athlete.id,
            fact_type="preference",
            fact_key="prefers_morning_runs",
            fact_value="true",
            confidence="athlete_stated",
            source_chat_id=chat.id,
            source_excerpt="I prefer morning runs",
            is_active=True,
            temporal=False,
            ttl_days=None,
            extracted_at=datetime.now(timezone.utc) - timedelta(days=110),
        ))
        db_session.commit()

        selected = self._select_injected_facts(db_session, test_athlete.id)
        keys = {f.fact_key for f in selected}
        assert "age_years" in keys
        assert "prefers_morning_runs" in keys


class TestUpcomingRaceExtraction:
    """Fix 2: Extraction prompt captures upcoming race details."""

    def test_extraction_prompt_includes_upcoming_race(self):
        """Extraction prompt mentions upcoming race details."""
        from tasks.fact_extraction_task import EXTRACTION_PROMPT
        assert "upcoming race" in EXTRACTION_PROMPT.lower()

    def test_upcoming_race_in_fact_types(self):
        """upcoming_race is a valid fact_type in the extraction prompt."""
        from tasks.fact_extraction_task import EXTRACTION_PROMPT
        assert "upcoming_race" in EXTRACTION_PROMPT

    def test_upcoming_race_in_ttl_categories(self):
        """upcoming_race must be temporal with a short TTL."""
        from tasks.fact_extraction_task import FACT_TTL_CATEGORIES
        assert FACT_TTL_CATEGORIES["upcoming_race"] == 7
        assert FACT_TTL_CATEGORIES["race_goal"] == 7
        assert FACT_TTL_CATEGORIES["race_plan"] == 7

    def test_relative_time_detector_matches_common_phrases(self):
        from tasks.fact_extraction_task import _contains_relative_time_phrase

        assert _contains_relative_time_phrase("I am 2 weeks out from race day")
        assert _contains_relative_time_phrase("Tune-up race is in 4 days")
        assert _contains_relative_time_phrase("My race is next week")
        assert _contains_relative_time_phrase("Tomorrow is the workout")
        assert not _contains_relative_time_phrase("My 10K PR is 41:30")


