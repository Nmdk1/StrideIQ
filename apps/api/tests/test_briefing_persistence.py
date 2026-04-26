"""
Tests for services.intelligence.briefing_persistence.persist_briefing.

These tests exercise the real DB (transactional-rollback fixture) so we
verify the ORM mapping, the unique-index collision behavior, and the
"never raises" promise all at once.

The single most important test here is test_persistence_failure_does_not_raise:
the hot path (/v1/home briefing generation) cannot be allowed to break
because of a logging/audit table.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from models import CoachBriefing, CoachBriefingInput
from services.intelligence.briefing_persistence import persist_briefing


def _sample_payload() -> dict:
    return {
        "coach_noticed": "Your easy pace slows with elevation gain across 41 runs.",
        "today_context": "4x10min threshold scheduled — 40 minutes at 6:31/mi.",
        "week_assessment": "25 miles through Thursday with two quality sessions remaining.",
        "checkin_reaction": "Glad you're feeling strong with high readiness.",
        "race_assessment": "With 16 days to the Coke 10K, sub-40 is supported.",
        "morning_voice": "Your overnight HRV tracked against your output metric.",
        "workout_why": "This threshold session builds sustained aerobic power.",
    }


def _sample_prompt() -> str:
    return "SYSTEM: you are a coach.\nATHLETE STATE: ...\nTASK: write the briefing."


_DEFAULT_CHECKIN = {"garmin_sleep_h": 7.5, "sleep_h": 7.0, "readiness": "high"}
_DEFAULT_FINDINGS = [{"input_name": "elevation_gain_m", "output_metric": "easy_pace"}]
_SENTINEL = object()


def _call(
    db_session,
    athlete_id,
    *,
    briefing_source: str = "llm",
    source_model: str = "claude-sonnet-4-6",
    data_fingerprint: str = "fp_aaaaaaaa",
    generated_at: datetime | None = None,
    payload: dict | None = None,
    validation_flags: dict | None = None,
    prompt_text: str | None = None,
    checkin_data=_SENTINEL,
    findings_injected=_SENTINEL,
) -> bool:
    return persist_briefing(
        db=db_session,
        athlete_id=str(athlete_id),
        athlete_local_date=date(2026, 4, 16),
        payload=payload if payload is not None else _sample_payload(),
        source_model=source_model,
        briefing_source=briefing_source,
        briefing_is_interim=False,
        data_fingerprint=data_fingerprint,
        schema_version=2,
        prompt_text=prompt_text if prompt_text is not None else _sample_prompt(),
        today_completed={"name": "Morning run", "distance_mi": 10.0, "pace": "8:25/mi"},
        planned_workout={"has_workout": True, "workout_type": "cruise_intervals"},
        checkin_data=_DEFAULT_CHECKIN if checkin_data is _SENTINEL else checkin_data,
        race_data={"race_name": "Coke 10K", "days_remaining": 16, "goal_time": "0:39:30"},
        upcoming_plan=[{"date": "2026-04-17", "workout_type": "easy"}],
        findings_injected=(
            _DEFAULT_FINDINGS if findings_injected is _SENTINEL else findings_injected
        ),
        validation_flags=validation_flags or {"contract_valid": True, "voice_valid": True},
        generated_at=generated_at,
    )


def test_persists_llm_briefing_and_input(db_session, test_athlete):
    ok = _call(db_session, test_athlete.id)
    assert ok is True

    briefings = (
        db_session.query(CoachBriefing)
        .filter(CoachBriefing.athlete_id == test_athlete.id)
        .all()
    )
    assert len(briefings) == 1
    b = briefings[0]
    assert b.athlete_local_date == date(2026, 4, 16)
    assert b.source_model == "claude-sonnet-4-6"
    assert b.briefing_source == "llm"
    assert b.briefing_is_interim is False
    assert b.schema_version == 2
    assert b.data_fingerprint == "fp_aaaaaaaa"
    assert b.coach_noticed.startswith("Your easy pace")
    assert b.validation_flags == {"contract_valid": True, "voice_valid": True}

    inputs = (
        db_session.query(CoachBriefingInput)
        .filter(CoachBriefingInput.briefing_id == b.id)
        .all()
    )
    assert len(inputs) == 1
    i = inputs[0]
    assert i.athlete_id == test_athlete.id
    assert i.today_completed["name"] == "Morning run"
    assert i.planned_workout["workout_type"] == "cruise_intervals"
    assert i.race_data["race_name"] == "Coke 10K"
    assert i.prompt_text == _sample_prompt()
    # garmin_sleep_h is a Numeric — compare as float.
    assert float(i.garmin_sleep_h) == 7.5


def test_skips_deterministic_fallback_by_default(db_session, test_athlete, monkeypatch):
    monkeypatch.delenv("PERSIST_DETERMINISTIC_BRIEFS", raising=False)

    ok = _call(
        db_session,
        test_athlete.id,
        briefing_source="deterministic_fallback",
        source_model="deterministic-fallback",
    )
    assert ok is False

    count = (
        db_session.query(CoachBriefing)
        .filter(CoachBriefing.athlete_id == test_athlete.id)
        .count()
    )
    assert count == 0


def test_deterministic_fallback_opt_in_via_env(db_session, test_athlete, monkeypatch):
    monkeypatch.setenv("PERSIST_DETERMINISTIC_BRIEFS", "1")

    ok = _call(
        db_session,
        test_athlete.id,
        briefing_source="deterministic_fallback",
        source_model="deterministic-fallback",
    )
    assert ok is True

    count = (
        db_session.query(CoachBriefing)
        .filter(CoachBriefing.athlete_id == test_athlete.id)
        .count()
    )
    assert count == 1


def test_idempotent_on_same_fingerprint_and_minute(db_session, test_athlete):
    now = datetime(2026, 4, 16, 12, 30, 15, tzinfo=timezone.utc)
    assert _call(db_session, test_athlete.id, generated_at=now) is True
    # Same athlete + fingerprint + minute → collapsed by unique index.
    same_minute = datetime(2026, 4, 16, 12, 30, 45, tzinfo=timezone.utc)
    assert _call(db_session, test_athlete.id, generated_at=same_minute) is True

    rows = (
        db_session.query(CoachBriefing)
        .filter(CoachBriefing.athlete_id == test_athlete.id)
        .all()
    )
    assert len(rows) == 1, (
        "Same (athlete, fingerprint, minute) must collapse to exactly one row — "
        "otherwise the corpus fills with duplicates every beat cycle."
    )


def test_different_fingerprint_produces_new_row(db_session, test_athlete):
    now = datetime(2026, 4, 16, 12, 30, 15, tzinfo=timezone.utc)
    assert _call(db_session, test_athlete.id, data_fingerprint="fp_aaaaaaaa", generated_at=now) is True
    assert _call(db_session, test_athlete.id, data_fingerprint="fp_bbbbbbbb", generated_at=now) is True

    rows = (
        db_session.query(CoachBriefing)
        .filter(CoachBriefing.athlete_id == test_athlete.id)
        .all()
    )
    assert len(rows) == 2


def test_different_minute_same_fingerprint_produces_new_row(db_session, test_athlete):
    assert _call(
        db_session,
        test_athlete.id,
        generated_at=datetime(2026, 4, 16, 12, 30, 0, tzinfo=timezone.utc),
    ) is True
    assert _call(
        db_session,
        test_athlete.id,
        generated_at=datetime(2026, 4, 16, 12, 31, 0, tzinfo=timezone.utc),
    ) is True

    rows = (
        db_session.query(CoachBriefing)
        .filter(CoachBriefing.athlete_id == test_athlete.id)
        .all()
    )
    assert len(rows) == 2


def test_persistence_failure_does_not_raise(db_session, test_athlete, monkeypatch):
    """
    If anything inside persist_briefing blows up (DB down, bad type,
    migration skew), the function MUST return False and MUST NOT raise.
    /v1/home cannot be allowed to break because of a logging table.
    """
    def _boom(*_a, **_kw):
        raise RuntimeError("simulated DB outage")

    monkeypatch.setattr(db_session, "add", _boom)

    # Any unexpected exception path must be swallowed.
    result = _call(db_session, test_athlete.id)
    assert result is False


def test_prompt_text_captured_verbatim(db_session, test_athlete):
    prompt = (
        "SYSTEM: you are a running coach.\n"
        "ATHLETE STATE:\n  - RPI 53.2\n  - sleep 7.5h\n"
        "RECENT RUNS:\n  - 10mi @ 8:25/mi\n"
        "TASK: produce JSON with 7 fields.\n"
        "  Include every character exactly — quotes \"like these\" and newlines.\n"
    )
    assert _call(db_session, test_athlete.id, prompt_text=prompt) is True

    inp = db_session.query(CoachBriefingInput).filter(
        CoachBriefingInput.athlete_id == test_athlete.id
    ).one()
    assert inp.prompt_text == prompt, (
        "prompt_text must be byte-identical to what was sent to the LLM — "
        "this is the guarantee that makes the corpus usable for retros."
    )


def test_validation_flags_reflect_pipeline(db_session, test_athlete):
    flags = {
        "contract_valid": True,
        "voice_valid": True,
        "sleep_valid": False,
        "sleep_stripped": True,
        "coach_noticed_cleared": False,
        "workout_why_cleared": True,
        "canary_retried": True,
    }
    assert _call(db_session, test_athlete.id, validation_flags=flags) is True

    b = (
        db_session.query(CoachBriefing)
        .filter(CoachBriefing.athlete_id == test_athlete.id)
        .one()
    )
    assert b.validation_flags == flags


def test_rejects_invalid_athlete_id(db_session):
    ok = persist_briefing(
        db=db_session,
        athlete_id="not-a-uuid",
        athlete_local_date=date(2026, 4, 16),
        payload=_sample_payload(),
        source_model="claude-sonnet-4-6",
        briefing_source="llm",
        briefing_is_interim=False,
        data_fingerprint="fp_aaaaaaaa",
        schema_version=2,
        prompt_text=_sample_prompt(),
        today_completed=None,
        planned_workout=None,
        checkin_data=None,
        race_data=None,
        upcoming_plan=None,
        findings_injected=None,
    )
    assert ok is False


def test_rejects_empty_prompt_text(db_session, test_athlete):
    ok = _call(db_session, test_athlete.id, prompt_text="")
    assert ok is False


# ---------------------------------------------------------------------------
# Wire-up contract tests: ensure the Celery task actually calls persist_briefing
# with the full set of arguments, and that validation_flags is tracked.
# These are source-level contract tests, not mock-heavy integration runs —
# they guard against silent regressions where someone refactors the task
# and forgets to thread the new call through.
# ---------------------------------------------------------------------------

def test_task_module_wires_persist_briefing_with_full_args():
    """The home briefing task must call persist_briefing with every input
    the corpus is supposed to capture. If this breaks, the brief persistence
    corpus silently starts missing fields."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "tasks" / "home_briefing_tasks.py"
    ).read_text(encoding="utf-8")

    assert (
        "from services.intelligence.briefing_persistence import persist_briefing"
        in src
    ), "task must import persist_briefing"

    required_kwargs = [
        "athlete_id=athlete_id",
        "athlete_local_date=",
        "payload=result",
        "source_model=source_model",
        "briefing_source=\"llm\"",
        "briefing_is_interim=False",
        "data_fingerprint=fingerprint",
        "prompt_text=prompt",
        "today_completed=today_completed",
        "planned_workout=planned_workout_snapshot",
        "checkin_data=checkin_data",
        "race_data=race_data",
        "upcoming_plan=upcoming_plan_snapshot",
        "findings_injected=",
        "validation_flags=validation_flags",
    ]
    for kw in required_kwargs:
        assert kw in src, f"persist_briefing call missing required kwarg: {kw}"


def test_task_module_tracks_validation_flags():
    """validation_flags must be updated at each validator branch so the
    persisted row carries a truthful audit of what the pipeline did to
    the LLM output."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "tasks" / "home_briefing_tasks.py"
    ).read_text(encoding="utf-8")

    required_flag_writes = [
        'validation_flags["canary_retried"] = True',
        'validation_flags["voice_valid"] = False',
        'validation_flags["sleep_valid"] = False',
        'validation_flags["sleep_stripped"] = True',
        'validation_flags["coach_noticed_cleared"] = True',
        'validation_flags["workout_why_cleared"] = True',
    ]
    for flag in required_flag_writes:
        assert flag in src, (
            f"validation_flags audit trail missing branch: {flag}. "
            "If a validator fires without a corresponding flag, the persisted "
            "row will misrepresent what happened."
        )


def test_task_module_persist_call_is_non_blocking():
    """Persistence must sit inside a try/except so /v1/home never breaks."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "tasks" / "home_briefing_tasks.py"
    ).read_text(encoding="utf-8")

    # Anchor: find the persist_briefing call site and check it's wrapped.
    idx = src.find("persist_briefing(")
    assert idx != -1
    # Look backwards for a try: before the call.
    window = src[max(0, idx - 400):idx]
    assert "try:" in window, (
        "persist_briefing call must be inside a try/except so a DB failure "
        "cannot break the /v1/home hot path."
    )
    # And a matching except afterward.
    tail = src[idx:idx + 1200]
    assert "except" in tail, "persist_briefing call must have an except clause"


@pytest.mark.parametrize("checkin_data,expected", [
    ({"garmin_sleep_h": 7.25, "sleep_h": 6.5}, 7.25),
    ({"garmin_sleep_h": None, "sleep_h": 8.0}, 8.0),
    ({}, None),
    (None, None),
    ({"sleep_h": "not-a-number"}, None),
])
def test_sleep_h_coercion(db_session, test_athlete, checkin_data, expected):
    assert _call(db_session, test_athlete.id, checkin_data=checkin_data) is True
    inp = (
        db_session.query(CoachBriefingInput)
        .filter(CoachBriefingInput.athlete_id == test_athlete.id)
        .one()
    )
    if expected is None:
        assert inp.garmin_sleep_h is None
    else:
        assert float(inp.garmin_sleep_h) == pytest.approx(expected)
