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
        return {
            "response": """{
  "assessment": "Strong controlled run execution today.",
  "implication": "This supports stable build progression for this phase.",
  "action": ["Keep tomorrow easy and protect recovery before the next quality day."],
  "athlete_alignment_note": "Aligned with reported effort.",
  "evidence": ["2026-02-10: run paced slower by 0:09/mi vs marathon reference"],
  "safety_status": "ok"
}""",
            "error": False,
        }

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
    assert "Return JSON with keys: assessment, implication, action" in msg
    assert "Next step:" in resp.response
    assert "Strong controlled run execution today." in resp.response
    assert "Recorded pace vs marathon pace" not in resp.response


@pytest.mark.asyncio
async def test_calendar_router_strips_internal_labels_and_enforces_action(monkeypatch, db_session, test_athlete):
    def _fake_day_context(*_args, **_kwargs):
        return {
            "ok": True,
            "data": {
                "date": "2026-02-10",
                "weekday": "Tuesday",
                "marathon_pace_per_mile": "6:57/mi",
                "planned_workout": {"title": "Hill Strides", "workout_type": "easy"},
                "activities": [
                    {
                        "name": "Run",
                        "pace_per_mile": "7:06/mi",
                        "distance_mi": 10.0,
                        "pace_vs_marathon_label": "slower by 0:09/mi",
                    }
                ],
            },
        }

    async def _fake_chat(self, athlete_id, message, include_context=True):
        return {
            "response": "**Date: 2026-02-10 (Tuesday)**\nRecorded pace vs marathon pace: slower by 0:09/mi.\nYou ran 10 miles at 7:06/mi.",
            "error": False,
        }

    monkeypatch.setattr(calendar_router.coach_tools, "get_calendar_day_context", _fake_day_context)
    monkeypatch.setattr(calendar_router.AICoach, "chat", _fake_chat)

    req = calendar_router.CoachMessageRequest(
        message="How was run today?",
        context_type="day",
        context_date=date(2026, 2, 10),
    )
    resp = await calendar_router.send_coach_message(req, current_user=test_athlete, db=db_session)
    lower = resp.response.lower()
    assert "recorded pace vs marathon pace" not in lower
    assert "next step:" in lower
    assert "-" in resp.response


def test_ai_coach_registers_compute_running_math_tool():
    from services.ai_coach import AICoach

    mock_db = MagicMock()
    with patch.object(AICoach, "__init__", lambda self, db: None):
        coach = AICoach(mock_db)

    opus_tools = coach._opus_tools()
    opus_names = [t["name"] for t in opus_tools]
    assert "compute_running_math" in opus_names


def test_no_openai_references_in_ai_coach():
    """Regression guard: ai_coach.py must not reference OpenAI runtime paths.

    OpenAI Assistants were removed as a legacy fallback.  If someone
    re-introduces them without discussion, this test will catch it.

    Scoped to code lines only (strips # comments) to avoid false positives
    from historical notes while still catching real re-introductions.
    """
    import pathlib
    source = pathlib.Path(__file__).resolve().parent.parent / "services" / "ai_coach.py"
    raw = source.read_text(encoding="utf-8")
    # Strip single-line comments and docstrings aren't an issue — the
    # forbidden terms are import/attribute patterns that only matter in code.
    code_lines = [
        line for line in raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    code_text = "\n".join(code_lines)
    forbidden = [
        "from openai",          # import
        "import OpenAI",        # import
        "OPENAI_AVAILABLE",     # flag
        "self.client.beta",     # OpenAI Assistants API calls
        "self.assistant_id",    # OpenAI assistant ID attribute
        "fallback_to_assistants",  # fallback signal key
    ]
    for term in forbidden:
        assert term not in code_text, (
            f"Forbidden OpenAI reference found in ai_coach.py: '{term}'. "
            "OpenAI Assistants were removed — do not re-introduce without ADR approval."
        )
