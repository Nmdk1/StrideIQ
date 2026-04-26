import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from routers import ai_coach


class _FakeCoach:
    def __init__(self, db):
        self.db = db

    async def chat(self, **kwargs):
        return {
            "response": "I checked your training log.",
            "thread_id": "thread-1",
            "error": False,
            "tools_called": ["get_recent_runs", "get_recent_runs", "get_training_load"],
            "tool_count": 2,
            "conversation_contract": "decision_point",
        }


@pytest.mark.asyncio
async def test_chat_response_exposes_trust_metadata(monkeypatch):
    monkeypatch.setattr(ai_coach, "AICoach", _FakeCoach)

    response = await ai_coach.chat_with_coach(
        request=ai_coach.ChatRequest(message="Should I move tomorrow's threshold?"),
        athlete=SimpleNamespace(id=uuid4()),
        db=object(),
    )

    assert response.tools_used == [
        "get_recent_runs",
        "get_recent_runs",
        "get_training_load",
    ]
    assert response.tool_count == 2
    assert response.conversation_contract == "decision_point"


@pytest.mark.asyncio
async def test_stream_done_event_exposes_trust_metadata(monkeypatch):
    monkeypatch.setattr(ai_coach, "AICoach", _FakeCoach)

    response = await ai_coach.chat_with_coach_stream(
        request=ai_coach.ChatRequest(message="Should I move tomorrow's threshold?"),
        athlete=SimpleNamespace(id=uuid4()),
        db=object(),
    )

    body = b""
    async for chunk in response.body_iterator:
        body += chunk

    done_payload = None
    for packet in body.decode("utf-8").split("\n\n"):
        if "event: done" not in packet:
            continue
        data_line = next(line for line in packet.splitlines() if line.startswith("data: "))
        done_payload = json.loads(data_line.removeprefix("data: "))

    assert done_payload is not None
    assert done_payload["tools_used"] == [
        "get_recent_runs",
        "get_recent_runs",
        "get_training_load",
    ]
    assert done_payload["tool_count"] == 2
    assert done_payload["conversation_contract"] == "decision_point"
