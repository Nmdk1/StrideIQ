"""
Tests for services.effort_resolver.

Founder rule (binding): the athlete's own RPE always wins. Garmin is a
low-confidence fallback. We never blend the two.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.effort_resolver import (
    ResolvedEffort,
    resolve_effort,
    to_dict,
)


def _activity(
    *,
    garmin_perceived_effort: int | None = None,
    garmin_feel: str | None = None,
):
    return SimpleNamespace(
        garmin_perceived_effort=garmin_perceived_effort,
        garmin_feel=garmin_feel,
    )


def _feedback(*, perceived_effort: int | None, leg_feel: str | None = None):
    return SimpleNamespace(
        perceived_effort=perceived_effort,
        leg_feel=leg_feel,
    )


class TestAthleteWins:
    """Athlete's own RPE always wins outright — never blended with Garmin."""

    def test_athlete_rpe_wins_over_garmin_rpe(self):
        a = _activity(garmin_perceived_effort=9, garmin_feel="weak")
        fb = _feedback(perceived_effort=4, leg_feel="normal")

        result = resolve_effort(a, fb)

        assert result.rpe == 4
        assert result.source == "athlete_feedback"
        assert result.feel_label == "normal"
        assert result.confidence == "high"

    def test_athlete_rpe_wins_when_no_leg_feel(self):
        a = _activity(garmin_perceived_effort=8, garmin_feel="weak")
        fb = _feedback(perceived_effort=6, leg_feel=None)

        result = resolve_effort(a, fb)

        assert result.rpe == 6
        assert result.source == "athlete_feedback"
        assert result.feel_label is None
        assert result.confidence == "high"

    def test_athlete_rpe_at_boundaries(self):
        a = _activity(garmin_perceived_effort=5)

        for rpe in (1, 10):
            result = resolve_effort(a, _feedback(perceived_effort=rpe))
            assert result.rpe == rpe
            assert result.source == "athlete_feedback"


class TestGarminFallback:
    """Garmin self-eval is used only when no athlete RPE is recorded."""

    def test_garmin_rpe_used_when_no_feedback_row(self):
        a = _activity(garmin_perceived_effort=7, garmin_feel="normal")

        result = resolve_effort(a, None)

        assert result.rpe == 7
        assert result.source == "garmin_self_eval"
        assert result.feel_label == "normal"
        assert result.confidence == "low"

    def test_garmin_rpe_used_when_feedback_has_no_rpe(self):
        a = _activity(garmin_perceived_effort=5, garmin_feel="normal")
        fb = _feedback(perceived_effort=None, leg_feel="tired")

        result = resolve_effort(a, fb)

        assert result.rpe == 5
        assert result.source == "garmin_self_eval"
        # Garmin feel wins for the label too — feedback has no numeric RPE.
        assert result.feel_label == "normal"
        assert result.confidence == "low"

    def test_garmin_feel_only_derives_bucketed_rpe(self):
        a = _activity(garmin_perceived_effort=None, garmin_feel="strong")

        result = resolve_effort(a, None)

        # "strong" buckets to 4 per the FIT SDK 5-point mapping.
        assert result.rpe == 4
        assert result.source == "garmin_self_eval"
        assert result.feel_label == "strong"
        assert result.confidence == "low"

    def test_garmin_feel_unknown_label_keeps_label_no_rpe(self):
        a = _activity(garmin_perceived_effort=None, garmin_feel="bonkers")

        result = resolve_effort(a, None)

        assert result.rpe is None
        assert result.source == "garmin_self_eval"
        assert result.feel_label == "bonkers"
        assert result.confidence == "low"


class TestEmpty:
    """No data at all -> a stable empty record."""

    def test_no_activity_data_no_feedback(self):
        a = _activity()

        result = resolve_effort(a, None)

        assert result.rpe is None
        assert result.source is None
        assert result.feel_label is None
        assert result.confidence == "none"

    def test_invalid_garmin_rpe_out_of_range_ignored(self):
        a = _activity(garmin_perceived_effort=42)

        result = resolve_effort(a, None)

        assert result.rpe is None
        assert result.source is None
        assert result.confidence == "none"

    def test_invalid_athlete_rpe_falls_through_to_garmin(self):
        a = _activity(garmin_perceived_effort=6, garmin_feel="normal")
        fb = _feedback(perceived_effort=0)  # outside 1-10 range

        result = resolve_effort(a, fb)

        assert result.source == "garmin_self_eval"
        assert result.rpe == 6


class TestSerialization:
    def test_to_dict_shape(self):
        resolved = ResolvedEffort(rpe=5, source="athlete_feedback", feel_label="normal", confidence="high")

        d = to_dict(resolved)

        assert d == {
            "rpe": 5,
            "source": "athlete_feedback",
            "feel_label": "normal",
            "confidence": "high",
        }

    def test_to_dict_empty(self):
        resolved = ResolvedEffort(rpe=None, source=None, feel_label=None, confidence="none")

        d = to_dict(resolved)

        assert d == {
            "rpe": None,
            "source": None,
            "feel_label": None,
            "confidence": "none",
        }
