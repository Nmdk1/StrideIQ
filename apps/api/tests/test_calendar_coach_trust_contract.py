from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from models import Activity
from routers import calendar as calendar_router
from services.coach_tools import get_calendar_day_context


def _parse_pace_seconds(pace_text: str) -> int:
    cleaned = pace_text.split("/", 1)[0]
    mins, secs = cleaned.split(":")
    return int(mins) * 60 + int(secs)


def test_calendar_day_context_includes_weekday_and_pace_comparison(db_session, test_athlete):
    test_athlete.rpi = 55.0
    test_athlete.preferred_units = "imperial"
    db_session.commit()

    db_session.add(
        Activity(
            athlete_id=test_athlete.id,
            name="Quality Tuesday",
            start_time=datetime(2026, 2, 10, 12, 0, 0),
            sport="run",
            source="manual",
            duration_s=4260,  # 7:06/mi for 10 miles
            distance_m=16093,
            avg_hr=152,
        )
    )
    db_session.commit()

    result = get_calendar_day_context(db_session, test_athlete.id, "2026-02-10")
    data = result["data"]
    first = data["activities"][0]

    assert result["ok"] is True
    assert data["date"] == "2026-02-10"
    assert data["weekday"] == "Tuesday"
    assert data["marathon_pace_per_mile"] is not None
    assert first["pace_vs_marathon_label"] is not None
    assert first["pace_vs_marathon_direction"] in ("faster", "slower", "equal")


def test_calendar_day_context_pace_relation_is_math_consistent(db_session, test_athlete):
    test_athlete.rpi = 55.0
    test_athlete.preferred_units = "imperial"
    db_session.commit()

    db_session.add(
        Activity(
            athlete_id=test_athlete.id,
            name="Pace Relation Check",
            start_time=datetime(2026, 2, 10, 12, 0, 0),
            sport="run",
            source="manual",
            duration_s=4260,
            distance_m=16093,
            avg_hr=152,
        )
    )
    db_session.commit()

    result = get_calendar_day_context(db_session, test_athlete.id, "2026-02-10")
    data = result["data"]
    first = data["activities"][0]

    activity_pace_s = _parse_pace_seconds(first["pace_per_mile"])
    marathon_pace_s = _parse_pace_seconds(data["marathon_pace_per_mile"])
    expected_delta = activity_pace_s - marathon_pace_s
    actual_delta = first["pace_vs_marathon_seconds_per_mile"]

    assert actual_delta == expected_delta
    if actual_delta < 0:
        assert first["pace_vs_marathon_label"].startswith("faster by")
        assert first["pace_vs_marathon_direction"] == "faster"
    elif actual_delta > 0:
        assert first["pace_vs_marathon_label"].startswith("slower by")
        assert first["pace_vs_marathon_direction"] == "slower"
    else:
        assert first["pace_vs_marathon_label"] == "on marathon pace"
        assert first["pace_vs_marathon_direction"] == "equal"


@pytest.mark.asyncio
async def test_calendar_router_fails_closed_when_day_context_missing(monkeypatch, db_session, test_athlete):
    def _fake_day_context(*_args, **_kwargs):
        return {"ok": False, "data": {}}

    async def _should_not_call_chat(*_args, **_kwargs):
        raise AssertionError("AICoach.chat should not run when day context preflight fails")

    monkeypatch.setattr(calendar_router.coach_tools, "get_calendar_day_context", _fake_day_context)
    monkeypatch.setattr(calendar_router.AICoach, "chat", _should_not_call_chat)

    req = calendar_router.CoachMessageRequest(
        message="How was run today?",
        context_type="day",
        context_date=date(2026, 2, 10),
    )
    resp = await calendar_router.send_coach_message(req, current_user=test_athlete, db=db_session)
    assert "cannot answer this safely" in resp.response.lower()


@pytest.mark.asyncio
async def test_calendar_router_injects_authoritative_fact_capsule(monkeypatch, db_session, test_athlete):
    captured: dict = {}

    def _fake_day_context(*_args, **_kwargs):
        return {
            "ok": True,
            "data": {
                "date": "2026-02-10",
                "weekday": "Tuesday",
                "marathon_pace_per_mile": "6:57/mi",
                "activities": [
                    {
                        "pace_vs_marathon_label": "slower by 0:09/mi",
                    }
                ],
            },
        }

    async def _fake_chat(self, athlete_id, message, include_context=True):
        captured["message"] = message
        return {"response": "ok", "error": False}

    monkeypatch.setattr(calendar_router.coach_tools, "get_calendar_day_context", _fake_day_context)
    monkeypatch.setattr(calendar_router.AICoach, "chat", _fake_chat)

    req = calendar_router.CoachMessageRequest(
        message="How was run today?",
        context_type="day",
        context_date=date(2026, 2, 10),
    )
    resp = await calendar_router.send_coach_message(req, current_user=test_athlete, db=db_session)

    msg = captured.get("message", "")
    assert "AUTHORITATIVE FACT CAPSULE (MUST USE EXACTLY):" in msg
    assert "RESPONSE CONTRACT (MANDATORY):" in msg
    assert "Date: 2026-02-10" in msg
    assert "Weekday: Tuesday" in msg
    assert "Recorded pace vs marathon pace: slower by 0:09/mi" in msg
    assert "do not recompute pace relation" in msg
    assert resp.response == "ok"


def test_ai_coach_registers_compute_running_math_tool():
    from services.ai_coach import AICoach

    mock_db = MagicMock()
    with patch.object(AICoach, "__init__", lambda self, db: None):
        coach = AICoach(mock_db)

    assistant_tools = coach._assistant_tools()
    assistant_names = [t["function"]["name"] for t in assistant_tools]
    assert "compute_running_math" in assistant_names

    opus_tools = coach._opus_tools()
    opus_names = [t["name"] for t in opus_tools]
    assert "compute_running_math" in opus_names
