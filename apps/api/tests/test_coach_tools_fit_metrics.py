"""
Phase 3 (fit_run_001) — get_recent_runs surfaces FIT-derived metrics + the
resolved perceived effort to the coach / LLM.

Founder rule (binding): the athlete's own RPE always wins. Garmin self-eval
is a low-confidence fallback. This file is the snapshot test that proves the
LLM gets that envelope.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4


def _activity_with_full_fit(activity_id, athlete_id):
    """A run activity carrying every FIT-derived field a coach can consume."""
    a = MagicMock()
    a.id = activity_id
    a.athlete_id = athlete_id
    a.start_time = datetime.utcnow()
    a.name = "Tempo Run"
    a.distance_m = 12000
    a.duration_s = 3000
    a.moving_time_s = 2950
    a.avg_hr = 162
    a.max_hr = 178
    a.workout_type = "tempo_run"
    a.intensity_score = 75
    a.total_elevation_gain = Decimal("85.0")
    a.total_descent_m = Decimal("82.0")
    a.temperature_f = 58
    a.humidity_pct = 70
    a.weather_condition = "clear"
    a.shape_sentence = None
    a.user_verified_race = False
    a.is_race_candidate = False
    # FIT activity-level metrics
    a.avg_power_w = 282
    a.max_power_w = 410
    a.avg_stride_length_m = Decimal("1.42")
    a.avg_ground_contact_ms = Decimal("245")
    a.avg_ground_contact_balance_pct = Decimal("50.4")
    a.avg_vertical_oscillation_cm = Decimal("8.1")
    a.avg_vertical_ratio_pct = Decimal("5.7")
    # Garmin self-eval (should be ignored when athlete RPE present below)
    a.garmin_perceived_effort = 8
    a.garmin_feel = "weak"
    return a


def _wire_db(mock_db, activities, feedback_rows):
    """Wire the chained query mocks for both Activity and ActivityFeedback."""
    from models import Activity, ActivityFeedback

    def query_side_effect(model):
        chain = MagicMock()
        if model is Activity:
            chain.filter.return_value.order_by.return_value.limit.return_value.all.return_value = activities
        elif model is ActivityFeedback:
            chain.filter.return_value.all.return_value = feedback_rows
        else:
            # Athlete lookup for preferred_units lives behind .filter().first().
            chain.filter.return_value.first.return_value = SimpleNamespace(preferred_units="imperial")
        return chain

    mock_db.query.side_effect = query_side_effect


class TestRecentRunsSurfacesFitMetrics:
    def test_athlete_rpe_wins_and_fit_fields_present(self):
        from services.coach_tools import get_recent_runs

        athlete_id = uuid4()
        activity_id = uuid4()
        activity = _activity_with_full_fit(activity_id, athlete_id)
        feedback = MagicMock()
        feedback.activity_id = activity_id
        feedback.perceived_effort = 6  # athlete logged it
        feedback.leg_feel = "normal"

        mock_db = MagicMock()
        _wire_db(mock_db, [activity], [feedback])

        result = get_recent_runs(mock_db, athlete_id, days=7)

        assert result["ok"] is True
        run = result["data"]["runs"][0]

        # FIT activity-level metrics surfaced verbatim (rounded for display).
        assert run["avg_power_w"] == 282
        assert run["max_power_w"] == 410
        assert run["avg_stride_length_m"] == 1.42
        assert run["avg_ground_contact_ms"] == 245
        assert run["avg_ground_contact_balance_pct"] == 50.4
        assert run["avg_vertical_oscillation_cm"] == 8.1
        assert run["avg_vertical_ratio_pct"] == 5.7
        assert run["total_descent_m"] == 82.0
        assert run["moving_time_s"] == 2950

        # Athlete RPE wins outright over Garmin's 8 / weak.
        assert run["perceived_effort"] == {
            "rpe": 6,
            "source": "athlete_feedback",
            "feel_label": "normal",
            "confidence": "high",
        }

    def test_garmin_fallback_when_no_feedback(self):
        from services.coach_tools import get_recent_runs

        athlete_id = uuid4()
        activity_id = uuid4()
        activity = _activity_with_full_fit(activity_id, athlete_id)

        mock_db = MagicMock()
        _wire_db(mock_db, [activity], [])  # no feedback row at all

        result = get_recent_runs(mock_db, athlete_id, days=7)

        run = result["data"]["runs"][0]
        # Falls back to Garmin self-eval, attributed.
        assert run["perceived_effort"] == {
            "rpe": 8,
            "source": "garmin_self_eval",
            "feel_label": "weak",
            "confidence": "low",
        }

    def test_no_fit_no_effort_is_clean(self):
        """Older Strava-only run: no FIT, no Garmin self-eval, no feedback."""
        from services.coach_tools import get_recent_runs

        athlete_id = uuid4()
        activity_id = uuid4()
        a = _activity_with_full_fit(activity_id, athlete_id)
        # Strip all the FIT + Garmin fallback data.
        a.avg_power_w = None
        a.max_power_w = None
        a.avg_stride_length_m = None
        a.avg_ground_contact_ms = None
        a.avg_ground_contact_balance_pct = None
        a.avg_vertical_oscillation_cm = None
        a.avg_vertical_ratio_pct = None
        a.total_descent_m = None
        a.moving_time_s = None
        a.garmin_perceived_effort = None
        a.garmin_feel = None

        mock_db = MagicMock()
        _wire_db(mock_db, [a], [])

        result = get_recent_runs(mock_db, athlete_id, days=7)

        run = result["data"]["runs"][0]
        for k in (
            "avg_power_w",
            "max_power_w",
            "avg_stride_length_m",
            "avg_ground_contact_ms",
            "avg_ground_contact_balance_pct",
            "avg_vertical_oscillation_cm",
            "avg_vertical_ratio_pct",
            "total_descent_m",
            "moving_time_s",
        ):
            assert run[k] is None, f"{k} should be None when FIT absent"

        assert run["perceived_effort"] == {
            "rpe": None,
            "source": None,
            "feel_label": None,
            "confidence": "none",
        }
