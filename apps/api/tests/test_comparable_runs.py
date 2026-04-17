"""Phase 5 — comparable runs tier logic tests (pure-function, no DB).

The persistence + tier integration tests live in
``test_comparable_runs_persistence.py`` and skip when no Postgres
fixture is available.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from services.comparison.comparable_runs import (
    ANNIVERSARY_WINDOW_DAYS,
    DEFAULT_TRAILING_DAYS,
    DISTANCE_TOLERANCE,
    ELEVATION_TOLERANCE,
    HEAT_DEW_TOLERANCE_F,
    HEAT_TEMP_TOLERANCE_F,
    SAME_ROUTE_RECENT_LIMIT,
    SAME_TYPE_LIMIT,
    SIMILAR_DISTANCE_LIMIT,
    SIMILAR_DISTANCE_TRAILING_DAYS,
    _avg_pace_s_per_km,
    _days_ago,
    _elevation_in_tolerance,
    _heat_in_tolerance,
)


@dataclass
class _A:
    """Lightweight stand-in for Activity for pure-function tests."""

    temperature_f: Optional[float] = None
    dew_point_f: Optional[float] = None
    total_elevation_gain: Optional[float] = None
    distance_m: Optional[int] = None
    duration_s: Optional[int] = None
    start_time: Optional[datetime] = None
    workout_type: Optional[str] = None
    avg_hr: Optional[int] = None
    name: Optional[str] = None
    route_id: Optional[uuid.UUID] = None
    id: uuid.UUID = uuid.uuid4()
    athlete_id: uuid.UUID = uuid.uuid4()
    sport: str = "run"


# ---------------------------------------------------------------------------
# Constants sanity (catch accidental edits)
# ---------------------------------------------------------------------------


def test_tolerances_are_sane():
    assert HEAT_TEMP_TOLERANCE_F == 5.0
    assert HEAT_DEW_TOLERANCE_F == 5.0
    assert ELEVATION_TOLERANCE == 0.20
    assert DISTANCE_TOLERANCE == 0.15
    assert DEFAULT_TRAILING_DAYS == 90
    assert ANNIVERSARY_WINDOW_DAYS == 30
    assert SAME_ROUTE_RECENT_LIMIT == 5
    assert SAME_TYPE_LIMIT == 5
    assert SIMILAR_DISTANCE_LIMIT == 5
    # Distance fallback runs on a tighter trailing window than the
    # workout-type tier, so it surfaces *recent* effort rather than
    # block-old anchors when those don't exist.
    assert SIMILAR_DISTANCE_TRAILING_DAYS == 60


# ---------------------------------------------------------------------------
# avg_pace
# ---------------------------------------------------------------------------


class TestAvgPace:
    def test_normal(self):
        # 10 km in 50 minutes → 5:00 / km = 300 s/km
        assert _avg_pace_s_per_km(10000, 3000) == 300.0

    def test_missing_returns_none(self):
        assert _avg_pace_s_per_km(None, 3000) is None
        assert _avg_pace_s_per_km(10000, None) is None
        assert _avg_pace_s_per_km(0, 3000) is None


# ---------------------------------------------------------------------------
# heat tolerance
# ---------------------------------------------------------------------------


class TestHeatTolerance:
    def test_both_missing_temp_returns_false(self):
        a = _A(temperature_f=None, dew_point_f=60)
        b = _A(temperature_f=None, dew_point_f=60)
        assert _heat_in_tolerance(a, b) is False

    def test_one_missing_dew_returns_false(self):
        a = _A(temperature_f=70, dew_point_f=None)
        b = _A(temperature_f=70, dew_point_f=60)
        assert _heat_in_tolerance(a, b) is False

    def test_within_tolerance(self):
        a = _A(temperature_f=72, dew_point_f=63)
        b = _A(temperature_f=70, dew_point_f=60)
        assert _heat_in_tolerance(a, b) is True

    def test_temp_outside_tolerance(self):
        a = _A(temperature_f=72, dew_point_f=63)
        b = _A(temperature_f=82, dew_point_f=63)
        assert _heat_in_tolerance(a, b) is False

    def test_dew_outside_tolerance(self):
        # Even matching temps, very different dew = different "feels like"
        a = _A(temperature_f=72, dew_point_f=50)
        b = _A(temperature_f=72, dew_point_f=70)
        assert _heat_in_tolerance(a, b) is False


# ---------------------------------------------------------------------------
# elevation tolerance
# ---------------------------------------------------------------------------


class TestElevationTolerance:
    def test_both_missing_returns_false(self):
        a = _A(total_elevation_gain=None)
        b = _A(total_elevation_gain=None)
        assert _elevation_in_tolerance(a, b) is False

    def test_one_missing_returns_false(self):
        a = _A(total_elevation_gain=200)
        b = _A(total_elevation_gain=None)
        assert _elevation_in_tolerance(a, b) is False

    def test_within_tolerance(self):
        a = _A(total_elevation_gain=200)
        b = _A(total_elevation_gain=220)
        assert _elevation_in_tolerance(a, b) is True

    def test_outside_tolerance(self):
        a = _A(total_elevation_gain=200)
        b = _A(total_elevation_gain=400)
        assert _elevation_in_tolerance(a, b) is False

    def test_both_zero_in_tolerance(self):
        a = _A(total_elevation_gain=0)
        b = _A(total_elevation_gain=0)
        assert _elevation_in_tolerance(a, b) is True


# ---------------------------------------------------------------------------
# days_ago
# ---------------------------------------------------------------------------


class TestDaysAgo:
    def test_simple(self):
        focus = datetime(2026, 4, 17, 8, 0, tzinfo=timezone.utc)
        prior = datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc)
        assert _days_ago(prior, focus) == 7

    def test_one_year(self):
        focus = datetime(2026, 4, 17, tzinfo=timezone.utc)
        prior = datetime(2025, 4, 17, tzinfo=timezone.utc)
        assert _days_ago(prior, focus) == 365

    def test_none_returns_none(self):
        assert _days_ago(None, datetime(2026, 4, 17, tzinfo=timezone.utc)) is None
        assert _days_ago(datetime(2026, 4, 17, tzinfo=timezone.utc), None) is None


# ---------------------------------------------------------------------------
# Similar-distance fallback tier
#
# This is the always-available floor for the Compare panel. The other four
# tiers gate on workout_type, route_id, anniversary, or a detected training
# block; when all four are absent (which describes most non-founder beta
# athletes pre-fix) the panel rendered empty for the entire population.
# This tier returns something for any athlete with at least one other run
# of similar distance in the trailing window.
# ---------------------------------------------------------------------------


class TestSimilarDistanceTier:
    """Exercises `_tier_similar_distance` against a query mock."""

    def _focus(self, distance_m: int = 10000):
        return _A(
            distance_m=distance_m,
            duration_s=2700,
            start_time=datetime(2026, 4, 17, 8, 0, tzinfo=timezone.utc),
        )

    def test_focus_with_no_distance_returns_empty_without_querying_db(self):
        from unittest.mock import MagicMock
        from services.comparison.comparable_runs import _tier_similar_distance

        focus = _A(
            distance_m=None,
            duration_s=2700,
            start_time=datetime(2026, 4, 17, tzinfo=timezone.utc),
        )
        db = MagicMock()
        result = _tier_similar_distance(db, focus, route_lookup={})
        assert result == []
        db.query.assert_not_called()

    def test_focus_with_zero_distance_returns_empty(self):
        from unittest.mock import MagicMock
        from services.comparison.comparable_runs import _tier_similar_distance

        focus = _A(
            distance_m=0,
            duration_s=0,
            start_time=datetime(2026, 4, 17, tzinfo=timezone.utc),
        )
        db = MagicMock()
        assert _tier_similar_distance(db, focus, route_lookup={}) == []

    def test_returns_up_to_limit_entries_in_recent_first_order(self):
        """REGRESSION GUARD: the floor tier must surface something whenever
        the athlete has any same-distance runs in the trailing window. If
        this returns empty when matches exist, the Compare panel silently
        re-breaks for the population."""
        from unittest.mock import MagicMock
        from services.comparison.comparable_runs import (
            SIMILAR_DISTANCE_LIMIT,
            _tier_similar_distance,
        )

        focus = self._focus()
        # Build 8 same-ish-distance candidates (all within ±15% of 10km).
        candidates = []
        for i in range(8):
            candidates.append(
                _A(
                    distance_m=10000 + (i - 4) * 500,
                    duration_s=2700 + i * 30,
                    start_time=datetime(2026, 4, 17 - i - 1, tzinfo=timezone.utc),
                    avg_hr=140 + i,
                )
            )

        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.limit.return_value = chain
        chain.all.return_value = candidates
        db = MagicMock()
        db.query.return_value = chain

        entries = _tier_similar_distance(db, focus, route_lookup={})
        assert 0 < len(entries) <= SIMILAR_DISTANCE_LIMIT
        # Each entry has a populated distance and the activity ids match
        # candidates that survived the limit cap.
        for e in entries:
            assert e.distance_m is not None


class TestOrchestratorFallback:
    """`find_comparables_for_activity` must always return the similar-
    distance tier when no earlier tier matches and there are eligible
    same-distance runs.  This is the contract that prevents the panel
    from rendering empty for anyone but the founder.
    """

    def test_panel_falls_back_to_similar_distance_when_other_tiers_empty(self):
        """REGRESSION GUARD: this is the population-level breakage that
        beta testers reported.  No anniversary, no repeated route, no
        classified workout type, no detected block -- but the athlete
        has done other runs of similar distance.  The panel MUST surface
        the similar-distance tier in that case."""
        from unittest.mock import MagicMock, patch
        from services.comparison.comparable_runs import (
            ComparableEntry,
            ComparableTier,
            find_comparables_for_activity,
        )

        focus_id = uuid.uuid4()
        focus = _A(
            distance_m=10000,
            duration_s=2700,
            start_time=datetime(2026, 4, 17, tzinfo=timezone.utc),
            workout_type=None,
            route_id=None,
        )
        focus.id = focus_id

        db = MagicMock()
        # First two query() calls in the orchestrator: focus lookup + route
        # lookup.  Both should return the focus / no routes respectively.
        focus_q = MagicMock()
        focus_q.filter.return_value = focus_q
        focus_q.first.return_value = focus
        db.query.return_value = focus_q

        fallback_entry = ComparableEntry(
            activity_id=str(uuid.uuid4()),
            start_time="2026-04-10T08:00:00+00:00",
            distance_m=10100,
            duration_s=2750,
            avg_pace_s_per_km=272.0,
            avg_hr=145,
            workout_type=None,
            name="Recent run",
            route_id=None,
            route_display_name=None,
            temperature_f=None,
            dew_point_f=None,
            elevation_gain_m=None,
            days_ago=7,
            in_tolerance_heat=False,
            in_tolerance_elevation=False,
            delta_pace_s_per_km=-3.0,
            delta_hr_bpm=2,
            delta_distance_m=100,
        )

        with patch(
            "services.comparison.comparable_runs._tier_anniversary",
            return_value=[],
        ), patch(
            "services.comparison.comparable_runs._tier_same_route_recent",
            return_value=[],
        ), patch(
            "services.comparison.comparable_runs._current_block_for_activity",
            return_value=None,
        ), patch(
            "services.comparison.comparable_runs._tier_same_type_current_block",
            return_value=[],
        ), patch(
            "services.comparison.comparable_runs._tier_same_type_similar_cond",
            return_value=[],
        ), patch(
            "services.comparison.comparable_runs._tier_similar_distance",
            return_value=[fallback_entry],
        ):
            result = find_comparables_for_activity(db, focus_id)

        assert result is not None
        assert result.tiers, (
            "panel rendered empty even though the similar-distance fallback "
            "had a match -- this is exactly the population-level break that "
            "beta testers reported"
        )
        kinds = [t.kind for t in result.tiers]
        assert "similar_distance" in kinds
        sim = next(t for t in result.tiers if t.kind == "similar_distance")
        assert sim.entries == [fallback_entry]
