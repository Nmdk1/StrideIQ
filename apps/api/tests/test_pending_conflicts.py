from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from services.ai_coach import AICoach
from services.coaching.ledger import PendingConflict
from services.coaching.ledger_extraction import ProposedFact
from services.coaching.runtime_v2 import (
    RUNTIME_MODE_VISIBLE,
    RUNTIME_VERSION_V2,
    CoachRuntimeV2State,
)
from services.coaching.runtime_v2_packet import assemble_v2_packet


def _conflict(field: str = "weekly_volume_mpw") -> PendingConflict:
    return PendingConflict(
        field=field,
        existing={
            "value": 60.0,
            "confidence": "athlete_stated",
            "asserted_at": "2026-04-01T12:00:00+00:00",
        },
        proposed={
            "value": 45.0,
            "confidence": "derived",
            "source": "activity_stream",
            "asserted_at": "2026-04-26T12:00:00+00:00",
        },
        reason="athlete_stated_fact_requires_confirmation_before_overwrite",
    )


def test_pending_conflict_surfaces_in_packet():
    conflict = _conflict()

    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        db=None,
        message="Should I add more volume?",
        conversation_context=[],
        legacy_athlete_state="",
        pending_conflicts=[conflict],
    )

    assert packet["pending_conflicts"] == [
        {
            "field": "weekly_volume_mpw",
            "existing_value": 60.0,
            "existing_confidence": "athlete_stated",
            "existing_asserted_at": "2026-04-01T12:00:00+00:00",
            "proposed_value": 45.0,
            "proposed_confidence": "derived",
            "proposed_source": "activity_stream",
            "suggested_question": "What weekly mileage are you actually averaging right now?",
        }
    ]


def test_pending_conflict_redacts_sensitive_field():
    conflict = PendingConflict(
        field="current_weight_lbs",
        existing={
            "value": 185.0,
            "confidence": "athlete_stated",
            "asserted_at": "2026-04-01T12:00:00+00:00",
        },
        proposed={
            "value": 190.0,
            "confidence": "derived",
            "source": "scale_sync",
            "asserted_at": "2026-04-26T12:00:00+00:00",
        },
        reason="athlete_stated_fact_requires_confirmation_before_overwrite",
    )

    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        db=None,
        message="What should I do about weight loss?",
        conversation_context=[],
        legacy_athlete_state="",
        pending_conflicts=[conflict],
    )

    assert packet["pending_conflicts"][0]["field"] == "current_weight_lbs"
    assert packet["pending_conflicts"][0]["existing_value"] == "[redacted]"
    assert packet["pending_conflicts"][0]["proposed_value"] == "[redacted]"
    assert packet["pending_conflicts"][0]["suggested_question"] == "What is your current weight?"


def test_pending_conflict_priority_over_unknowns(monkeypatch):
    from services.coaching import runtime_v2_packet

    def fake_compute_unknowns(*args, **kwargs):
        return [
            {
                "field": "weekly_volume_mpw",
                "suggested_question": "What weekly mileage are you actually averaging right now?",
            },
            {
                "field": "pace_zones",
                "suggested_question": "What paces are currently true?",
            },
        ]

    monkeypatch.setattr(runtime_v2_packet, "compute_unknowns", fake_compute_unknowns)

    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        db=None,
        message="What pace should I run for intervals?",
        conversation_context=[],
        legacy_athlete_state="",
        pending_conflicts=[_conflict()],
    )

    assert {item["field"] for item in packet["pending_conflicts"]} == {
        "weekly_volume_mpw"
    }
    assert [item["field"] for item in packet["blocks"]["unknowns"]["data"]] == [
        "pace_zones"
    ]


@pytest.mark.asyncio
async def test_chat_threads_pending_conflicts_into_v2_packet(monkeypatch):
    import services.consent as consent_module
    from services.coaching import core as coach_core

    athlete_id = uuid4()
    conflict = _conflict()
    captured: dict[str, object] = {}
    db = MagicMock()
    db.commit = MagicMock()

    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(coach_core.settings, "KIMI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: CoachRuntimeV2State(
            runtime_mode=RUNTIME_MODE_VISIBLE,
            runtime_version=RUNTIME_VERSION_V2,
            shadow_enabled=False,
            visible_enabled=True,
        ),
    )
    monkeypatch.setattr(coach_core, "close_idle_threads", lambda db, athlete_id: [])

    async def fake_extract(*args, **kwargs):
        return [
            ProposedFact(
                field="weekly_volume_mpw",
                value=45.0,
                source="turn_id:test",
                confidence="derived",
                asserted_at=datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc),
            )
        ]

    monkeypatch.setattr(coach_core, "extract_facts_from_turn_with_optional_llm", fake_extract)
    monkeypatch.setattr(
        coach_core,
        "persist_proposed_facts",
        lambda db, athlete_id, facts: [conflict, object()],
    )

    def fake_assemble_v2_packet(**kwargs):
        captured.update(kwargs)
        return {
            "conversation_mode": {"primary": "engage_and_reason", "confidence": "high"},
            "telemetry": {},
        }

    monkeypatch.setattr(coach_core, "assemble_v2_packet", fake_assemble_v2_packet)

    coach = AICoach.__new__(AICoach)
    coach.db = db
    coach.anthropic_client = None
    coach.gemini_client = None
    coach.router = SimpleNamespace(classify=lambda message: (None, True))
    coach.classify_query_complexity = lambda message: "low"
    coach.get_model_for_query = lambda *args, **kwargs: ("kimi-k2.6", True)
    coach.is_athlete_vip = lambda athlete_id: False
    coach.check_budget = lambda *args, **kwargs: (True, None)
    coach._build_athlete_state_for_opus = lambda athlete_id: ""
    coach._build_finding_deep_link_context = lambda *args, **kwargs: None
    coach.get_or_create_thread_with_state = lambda athlete_id: (uuid4(), None)
    coach.get_thread_history = lambda athlete_id, limit=10: {"messages": []}
    coach.query_kimi_v2_packet = AsyncMock(
        return_value={
            "response": (
                "Decision: resolve the weekly-volume conflict before adding interval work. "
                "Tradeoff: you keep the plan grounded, but you delay the workout decision. "
                "Default: answer the mileage question first."
            ),
            "error": False,
            "model": "kimi-k2.6",
            "thinking": "enabled",
            "kimi_latency_ms": 1,
        }
    )
    coach._normalize_response_for_ui = lambda **kwargs: kwargs["assistant_message"]
    coach._record_turn_guard_event = MagicMock()
    coach._save_chat_messages = MagicMock()

    result = await coach.chat(athlete_id, "Should I add interval work?")

    assert result["error"] is False
    assert captured["pending_conflicts"] == [conflict]
    assert result["runtime_mode"] == RUNTIME_MODE_VISIBLE
    assert result["response"].startswith("Decision: resolve the weekly-volume conflict")
    assert (
        coach._record_turn_guard_event.call_args.kwargs["event"]
        == "pass_v2_packet"
    )
