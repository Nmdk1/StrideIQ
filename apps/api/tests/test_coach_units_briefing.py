"""
Unit-awareness regression tests for the home briefing pipeline.

Two layers of coverage:

1. CoachUnits formatter — the small helper that the briefing builder, the
   deterministic fallback, and any future coach-text generator share.
   Pure functions; cheap to assert exhaustively.

2. Briefing prompt assembly — confirms that for a metric athlete the LLM
   prompt does not carry the imperial defaults that previously caused
   morning_voice to read "7-mile run at 7:39 pace" while the rest of the
   page rendered "11.2 km · 4:45/km".

The regression we're guarding against is real and was visible in
production for Dejan Kadunc on Apr 17, 2026: every other surface
respected his metric preference, but the LLM-generated narrative did not
because the prompt fed it `distance_mi`, `pace` ending in `/mi`, and
explicit text instructions saying "distances in miles, pace in min/mi".
"""

from __future__ import annotations

from services.coach_units import CoachUnits, coach_units


# ---------------------------------------------------------------------------
# CoachUnits formatter
# ---------------------------------------------------------------------------


class TestCoachUnitsLabels:
    def test_metric_labels(self):
        u = coach_units("metric")
        assert u.is_metric is True
        assert u.pace_unit == "min/km"
        assert u.pace_unit_short == "/km"
        assert u.distance_unit_short == "km"
        assert u.distance_unit_long == "kilometers"
        assert u.elevation_unit == "m"
        assert u.temperature_unit == "°C"

    def test_imperial_labels(self):
        u = coach_units("imperial")
        assert u.is_metric is False
        assert u.pace_unit == "min/mi"
        assert u.pace_unit_short == "/mi"
        assert u.distance_unit_short == "mi"
        assert u.distance_unit_long == "miles"
        assert u.elevation_unit == "ft"
        assert u.temperature_unit == "°F"

    def test_unknown_value_defaults_to_imperial(self):
        # Defensive: legacy rows or test fixtures may pass odd values; we
        # don't want a silent crash, and imperial matches the historical
        # baseline.
        for value in (None, "", "Imperial ", "garbage", "METRIC "):
            u = coach_units(value)
            if value and value.strip().lower() == "metric":
                assert u.is_metric is True
            else:
                assert u.is_metric is False


class TestCoachUnitsFormatters:
    def test_format_distance_metric(self):
        u = coach_units("metric")
        assert u.format_distance(11_200) == "11.2 km"
        assert u.format_distance(0) == "0.0 km"
        assert u.format_distance(None) is None

    def test_format_distance_imperial(self):
        u = coach_units("imperial")
        # 11.2 km ~= 6.96 mi
        assert u.format_distance(11_200) == "7.0 mi"
        assert u.format_distance(None) is None

    def test_format_pace_metric(self):
        u = coach_units("metric")
        # 11.2 km in 53:06 -> 4:44.46/km
        assert u.format_pace_from_distance_duration(11_200, 53 * 60 + 6) == "4:44/km"

    def test_format_pace_imperial(self):
        u = coach_units("imperial")
        # 7 mi in 54:23 -> 7:46.1/mi
        assert u.format_pace_from_distance_duration(7 * 1609.344, 7 * 466) == "7:46/mi"

    def test_format_pace_handles_zero_inputs(self):
        u = coach_units("metric")
        assert u.format_pace_from_distance_duration(0, 100) is None
        assert u.format_pace_from_distance_duration(1000, 0) is None
        assert u.format_pace_from_distance_duration(None, 100) is None

    def test_format_pace_carries_seconds_into_minutes(self):
        # 1000 m in 359.6 s -> 5:59.6 -> rounds to 6:00, not 5:60.
        u = coach_units("metric")
        assert u.format_pace_from_distance_duration(1000, 359.6) == "6:00/km"

    def test_format_elevation_metric(self):
        u = coach_units("metric")
        assert u.format_elevation(330.4) == "+330 m"
        assert u.format_elevation(None) is None

    def test_format_elevation_imperial(self):
        u = coach_units("imperial")
        # 330 m -> 1083 ft
        assert u.format_elevation(330) == "+1083 ft"

    def test_format_temperature_metric(self):
        u = coach_units("metric")
        assert u.format_temperature_from_f(68.0) == "20.0°C"
        assert u.format_temperature_from_f(None) is None

    def test_format_temperature_imperial(self):
        u = coach_units("imperial")
        assert u.format_temperature_from_f(72.5) == "72.5°F"


# ---------------------------------------------------------------------------
# Briefing prompt assembly — does the metric athlete's prompt actually carry
# metric units through to the LLM?
# ---------------------------------------------------------------------------


class _FakeQuery:
    """Minimal SQLAlchemy `db.query()` stand-in for the unit-aware path."""

    def __init__(self, rows: list):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def scalar(self):
        return self._rows[0] if self._rows else None


class _FakeDb:
    def __init__(self, athlete_units: str):
        self.athlete_units = athlete_units

    def query(self, *args, **kwargs):
        # Only the units lookup runs through this fake; the rest of the
        # prompt builder is monkey-patched away in the integration test.
        return _FakeQuery([self.athlete_units])


def _stub_full_prompt_path(monkeypatch, units_value: str):
    """Bypass every external dependency in generate_coach_home_briefing
    so the test can assert on the prompt string in isolation."""
    import routers.home as home

    from datetime import date, timezone

    monkeypatch.setattr(
        home, "get_athlete_timezone_from_db", lambda *a, **k: timezone.utc
    )
    monkeypatch.setattr(home, "athlete_local_today", lambda tz: date(2026, 4, 17))

    # build_athlete_brief is imported lazily inside the function — patch
    # the module import target.
    import services.coach_tools as coach_tools_mod
    monkeypatch.setattr(
        coach_tools_mod, "build_athlete_brief", lambda db, aid: "(stub brief)"
    )

    # compute_coach_noticed and rich-intelligence are non-blocking; the
    # fall-throughs cover both empty paths.
    monkeypatch.setattr(home, "compute_coach_noticed", lambda *a, **k: None)
    monkeypatch.setattr(home, "_build_rich_intelligence_context", lambda *a, **k: "")
    monkeypatch.setattr(
        home, "_get_garmin_sleep_h_for_last_night", lambda *a, **k: (None, None, False)
    )
    monkeypatch.setattr(home, "_build_sleep_baseline_guidance", lambda *a, **k: "")

    # Models access during athlete-fact + cross-training queries — return
    # nothing so the loops are empty.
    class _EmptyQuery:
        def __init__(self, *a, **k):
            self._payload = []

        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def offset(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def first(self):
            return None

        def all(self):
            return []

        def scalar(self):
            return 0

    class _Db:
        def __init__(self):
            self._units = units_value

        def query(self, *args, **kwargs):
            target = args[0] if args else None
            target_name = getattr(target, "__name__", str(target))
            if "preferred_units" in str(target):
                return _FakeQuery([self._units])
            if "Athlete.preferred_units" in target_name:
                return _FakeQuery([self._units])
            return _EmptyQuery()

    return _Db()


def _generate(monkeypatch, units_value: str, **overrides):
    from routers.home import generate_coach_home_briefing

    db = _stub_full_prompt_path(monkeypatch, units_value)
    return generate_coach_home_briefing(
        athlete_id="00000000-0000-0000-0000-000000000001",
        db=db,
        today_completed=overrides.get(
            "today_completed",
            {
                "name": "Cerklje na Gorenjskem Running",
                "distance_mi": 6.96,
                "distance_text": "11.2 km",
                "pace": "4:44/km",
                "avg_hr": 142,
                "duration_min": 53,
                "elevation_gain_ft": 1083,
                "elevation_text": "+330 m",
                "temperature_f": 50.0,
                "temperature_text": "10.0°C",
                "humidity_pct": 60,
                "heat_adjustment_pct": 0,
            },
        ),
        planned_workout=overrides.get("planned_workout"),
        checkin_data=overrides.get("checkin_data"),
        race_data=overrides.get("race_data"),
        skip_cache=True,
        upcoming_plan=overrides.get("upcoming_plan"),
        preferred_units=units_value,
    )


class TestBriefingPromptUnitsAwareness:
    """The prompt fed to the LLM must speak the athlete's units everywhere."""

    def test_metric_prompt_uses_km_and_excludes_imperial_keywords(self, monkeypatch):
        result = _generate(monkeypatch, "metric")
        assert result is not None and len(result) > 1, "Expected (None, prompt, ...) tuple"
        prompt = result[1]

        # Athlete-facing instructions converted to metric.
        assert "distances in kilometers" in prompt
        assert "pace in min/km" in prompt or "Pace as min/km" in prompt
        assert "distances in miles" not in prompt
        assert "Pace as min/mi" not in prompt

        # The today line must show the metric values, not the legacy mi number.
        assert "11.2 km" in prompt
        assert "+330 m" in prompt
        assert "10.0°C" in prompt

        # Heat-comparison example must use the metric flavour so the LLM
        # doesn't see "85°F/80%rh" and parrot it back to a Slovenian athlete.
        assert "29°C/80%rh" in prompt
        assert "85°F/80%rh" not in prompt

    def test_imperial_prompt_keeps_existing_phrasing(self, monkeypatch):
        result = _generate(
            monkeypatch,
            "imperial",
            today_completed={
                "name": "Morning Run",
                "distance_mi": 7.0,
                "distance_text": "7.0 mi",
                "pace": "7:39/mi",
                "avg_hr": 142,
                "duration_min": 54,
                "elevation_gain_ft": 250,
                "elevation_text": "+250 ft",
                "temperature_f": 65.0,
                "temperature_text": "65.0°F",
                "humidity_pct": 50,
                "heat_adjustment_pct": 0,
            },
        )
        prompt = result[1]
        assert "distances in miles" in prompt
        assert "Pace as min/mi" in prompt
        assert "7.0 mi" in prompt
        assert "+250 ft" in prompt
        assert "65.0°F" in prompt
        assert "85°F/80%rh" in prompt  # canonical imperial example survives

    def test_metric_prompt_handles_planned_only_path(self, monkeypatch):
        result = _generate(
            monkeypatch,
            "metric",
            today_completed=None,
            planned_workout={
                "has_workout": True,
                "workout_type": "easy",
                "title": "Easy 8 km",
                "distance_mi": 4.97,
                "distance_text": "8.0 km",
            },
        )
        prompt = result[1]
        assert "8.0 km" in prompt
        # Must not silently emit "4.97mi" alongside the metric value.
        assert "4.97mi" not in prompt
        assert "4.97 mi" not in prompt

    def test_metric_prompt_handles_upcoming_plan(self, monkeypatch):
        result = _generate(
            monkeypatch,
            "metric",
            upcoming_plan=[
                {
                    "date": "2026-04-18",
                    "day_name": "Saturday",
                    "workout_type": "long",
                    "title": "Long run",
                    "distance_mi": 12.43,
                    "distance_text": "20.0 km",
                    "description": "Easy effort",
                }
            ],
        )
        prompt = result[1]
        assert "20.0 km" in prompt
        assert "12.43mi" not in prompt
        assert "12.43 mi" not in prompt
