"""Tests for Phase 3B workout narrative generator.

Covers:
- Contextual prompt construction (references phase, recent activity, readiness).
- Suppression for sparse context (no planned workout).
- Kill switch and banned metric suppression.
- Phrasing similarity >50% suppressed.
- Physiological guardrails (no intensity after long run / taper).
- LLM error handling.
"""
import os
import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.workout_narrative_generator import (
    generate_workout_narrative,
    _build_context,
    _build_prompt,
    _token_overlap,
    _is_too_similar,
    WorkoutNarrativeResult,
    SIMILARITY_THRESHOLD,
    KILL_SWITCH_3B_ENV,
)


@pytest.fixture(autouse=True)
def _kill_switch_off(monkeypatch):
    """Ensure kill switch is off for all generator tests.

    Patches the FeatureFlag DB lookup inside the generator to return None,
    preventing a spurious .first() call from consuming DB mock side_effect slots.
    """
    monkeypatch.setenv(KILL_SWITCH_3B_ENV, "false")
    with patch("services.workout_narrative_generator._is_3b_kill_switched", return_value=False):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_workout(
    workout_type="easy",
    phase="build",
    week=5,
    title="Easy Run",
    description="8km easy",
    subtype=None,
    distance_km=8.0,
    duration_min=50,
    segments=None,
    phase_week=3,
):
    w = MagicMock()
    w.athlete_id = uuid4()
    w.workout_type = workout_type
    w.workout_subtype = subtype
    w.phase = phase
    w.phase_week = phase_week
    w.week_number = week
    w.title = title
    w.description = description
    w.target_distance_km = distance_km
    w.target_duration_minutes = duration_min
    w.segments = segments
    w.scheduled_date = date.today()
    return w


def _make_activity(name="Morning Run", wtype="easy_run", dist_m=8000, dur_s=3000, hr=140):
    a = MagicMock()
    a.name = name
    a.workout_type = wtype
    a.distance_m = dist_m
    a.duration_s = dur_s
    a.avg_hr = hr
    a.sport = "run"
    a.start_time = datetime.now(timezone.utc) - timedelta(days=1)
    return a


def _patch_narrative_llm(monkeypatch, text="Great session focus today."):
    """Patch _call_narrative_llm to return the given text without an LLM call."""
    from services import workout_narrative_generator as module
    monkeypatch.setattr(
        module, "_call_narrative_llm",
        lambda athlete_id, prompt: (text, 100, 30, 50),
    )


# ---------------------------------------------------------------------------
# Similarity guard
# ---------------------------------------------------------------------------

class TestSimilarityGuard:

    def test_identical_texts_high_overlap(self):
        assert _token_overlap("hello world foo bar", "hello world foo bar") > 0.99

    def test_completely_different_texts_low_overlap(self):
        assert _token_overlap("the quick brown fox", "alpha beta gamma delta") < 0.1

    def test_partial_overlap(self):
        a = "your threshold session went well today"
        b = "your easy session recovery went smoothly yesterday"
        overlap = _token_overlap(a, b)
        assert 0.0 < overlap < 1.0

    def test_is_too_similar_catches_duplicate(self):
        candidate = "Keep the effort relaxed and steady on this easy run."
        recent = ["Keep the effort relaxed and steady on this easy run."]
        assert _is_too_similar(candidate, recent, threshold=0.5) is True

    def test_is_too_similar_allows_fresh(self):
        candidate = "After yesterday's long run, today is about active recovery and easy movement."
        recent = ["Your threshold session showed real progress in your build phase."]
        assert _is_too_similar(candidate, recent, threshold=0.5) is False


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------

class TestContextBuilding:

    def test_no_workout_returns_none(self):
        """No planned workout → None context → suppressed."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        ctx = _build_context(uuid4(), date.today(), db)
        assert ctx is None

    def test_context_includes_workout_details(self):
        workout = _make_workout(workout_type="threshold", phase="build")
        yesterday = _make_workout(workout_type="easy")

        db = MagicMock()
        # Build a chain of query responses
        db.query.return_value.filter.return_value.first.side_effect = [
            workout,       # today's workout
            yesterday,     # yesterday's workout
            None,          # DailyReadiness
        ]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            [_make_activity()],  # recent activities
            [],                   # upcoming
        ]

        ctx = _build_context(uuid4(), date.today(), db)

        assert ctx is not None
        assert ctx["workout"]["type"] == "threshold"
        assert ctx["workout"]["phase"] == "build"

    def test_suppress_intensity_in_taper(self):
        workout = _make_workout(workout_type="easy", phase="taper")

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            workout,  # today
            None,     # yesterday
            None,     # readiness
        ]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            [],  # recent
            [],  # upcoming
        ]

        ctx = _build_context(uuid4(), date.today(), db)
        assert ctx["suppress_intensity"] is True

    def test_suppress_intensity_after_long_run(self):
        workout = _make_workout(workout_type="easy", phase="build")
        yesterday = _make_workout(workout_type="long")

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            workout,   # today
            yesterday, # yesterday was long
            None,      # readiness
        ]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            [],  # recent
            [],  # upcoming
        ]

        ctx = _build_context(uuid4(), date.today(), db)
        assert ctx["suppress_intensity"] is True


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

class TestPromptConstruction:

    def test_prompt_includes_phase(self):
        ctx = {
            "workout": {
                "type": "threshold", "subtype": None, "title": "Tempo Run",
                "description": "30min tempo", "phase": "build", "phase_week": 3,
                "week_number": 8, "distance_km": 10.0, "duration_min": 50,
                "segments": None,
            },
            "recent_activities": [],
            "upcoming": [],
            "readiness_score": 72.0,
            "suppress_intensity": False,
            "yesterday_type": None,
        }
        prompt = _build_prompt(ctx)
        assert "build" in prompt.lower()
        assert "Tempo Run" in prompt
        assert "72" in prompt

    def test_prompt_includes_suppress_intensity(self):
        ctx = {
            "workout": {
                "type": "easy", "subtype": None, "title": "Recovery Run",
                "description": "easy", "phase": "taper", "phase_week": 1,
                "week_number": 16, "distance_km": 5.0, "duration_min": 30,
                "segments": None,
            },
            "recent_activities": [],
            "upcoming": [],
            "readiness_score": None,
            "suppress_intensity": True,
            "yesterday_type": "long",
        }
        prompt = _build_prompt(ctx)
        assert "NOT encourage" in prompt or "not encourage" in prompt.lower()


# ---------------------------------------------------------------------------
# Full generation
# ---------------------------------------------------------------------------

class TestGenerateWorkoutNarrative:

    def test_good_narrative_returned(self, monkeypatch):
        """Good LLM output → narrative returned, not suppressed."""
        workout = _make_workout()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            workout, None, None,
        ]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            [], [], [],
        ]

        _patch_narrative_llm(monkeypatch, "Focus on keeping your cadence relaxed through the first half.")
        result = generate_workout_narrative(uuid4(), date.today(), db)

        assert result.narrative is not None
        assert result.suppressed is False

    def test_no_workout_suppressed(self):
        """No planned workout → suppressed."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = generate_workout_narrative(uuid4(), date.today(), db)
        assert result.suppressed is True
        assert "context" in result.suppression_reason.lower() or "workout" in result.suppression_reason.lower()

    def test_banned_metrics_suppressed(self, monkeypatch):
        """LLM output containing TSB → suppressed."""
        workout = _make_workout()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            workout, None, None,
        ]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            [], [], [],
        ]

        _patch_narrative_llm(monkeypatch, "Your TSB is -15 so take it easy today.")
        result = generate_workout_narrative(uuid4(), date.today(), db)

        assert result.suppressed is True
        assert "banned" in result.suppression_reason.lower() or "metric" in result.suppression_reason.lower()

    def test_intensity_in_taper_suppressed(self, monkeypatch):
        """Intensity encouragement during taper → suppressed."""
        workout = _make_workout(phase="taper")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            workout, None, None,
        ]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            [], [], [],
        ]

        _patch_narrative_llm(monkeypatch, "Push hard on this one and attack the hills.")
        result = generate_workout_narrative(uuid4(), date.today(), db)

        assert result.suppressed is True
        assert "intensity" in result.suppression_reason.lower()

    def test_similar_narrative_suppressed(self, monkeypatch):
        """Narrative >50% overlap with recent → suppressed."""
        workout = _make_workout()
        recent_text = "Keep the effort relaxed and steady on this easy run today."

        narr_row = MagicMock()
        narr_row.narration_text = recent_text

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            workout, None, None,
        ]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            [], [],  # recent activities, upcoming
            [narr_row],  # recent narratives
        ]

        _patch_narrative_llm(monkeypatch, recent_text)
        result = generate_workout_narrative(uuid4(), date.today(), db)
        assert result.suppressed is True
        assert "similar" in result.suppression_reason.lower()

    def test_llm_error_suppressed(self, monkeypatch):
        """LLM exception → suppressed, not 500."""
        workout = _make_workout()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            workout, None, None,
        ]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            [], [],
        ]

        from services import workout_narrative_generator as module
        def _raise(*a, **kw):
            raise RuntimeError("test error")
        monkeypatch.setattr(module, "_call_narrative_llm", _raise)
        result = generate_workout_narrative(uuid4(), date.today(), db)
        assert result.suppressed is True
        assert "error" in result.suppression_reason.lower()

    def test_empty_llm_response_suppressed(self, monkeypatch):
        """Empty LLM response → suppressed."""
        workout = _make_workout()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            workout, None, None,
        ]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            [], [],
        ]

        _patch_narrative_llm(monkeypatch, "")
        result = generate_workout_narrative(uuid4(), date.today(), db)
        assert result.suppressed is True


class TestModelRouting:
    def test_routes_through_central_llm_client(self, monkeypatch):
        from services import workout_narrative_generator as module

        fake = {
            "text": "Workout narrative from centralized client.",
            "input_tokens": 9,
            "output_tokens": 6,
            "latency_ms": 35,
        }
        monkeypatch.setattr(module, "call_llm", lambda **kwargs: fake)

        text, in_tok, out_tok, lat = module._call_narrative_llm(uuid4(), "prompt")
        assert text == "Workout narrative from centralized client."
        assert in_tok == 9
        assert out_tok == 6
        assert lat == 35
