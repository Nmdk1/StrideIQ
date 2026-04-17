"""Phase 3 — auto display_name + dominant_workout_type for routes."""

from __future__ import annotations

import uuid

from models import AthleteRoute
from routers.routes import _auto_display_name


class _R:
    """Lightweight stand-in for AthleteRoute when we only test the namer."""

    def __init__(self, distance_p50_m=None, name=None):
        self.distance_p50_m = distance_p50_m
        self.name = name


class TestAutoDisplayName:
    def test_zero_distance_returns_untitled(self):
        assert _auto_display_name(_R(distance_p50_m=0)) == "Untitled route"
        assert _auto_display_name(_R(distance_p50_m=None)) == "Untitled route"

    def test_short_loop_under_8km(self):
        # 5.0 km should land in "loop"
        assert _auto_display_name(_R(distance_p50_m=5000)) == "5.0 km loop"

    def test_mid_distance_route_8_to_16(self):
        # 11.7 km is the founder's most-run route; this is the canonical case
        assert _auto_display_name(_R(distance_p50_m=11700)) == "11.7 km route"

    def test_long_run_label_16_to_26(self):
        assert _auto_display_name(_R(distance_p50_m=18800)) == "18.8 km long-run route"

    def test_marathon_distance_26_to_36(self):
        assert (
            _auto_display_name(_R(distance_p50_m=27900))
            == "27.9 km marathon-distance route"
        )

    def test_ultra_distance_above_36(self):
        assert (
            _auto_display_name(_R(distance_p50_m=42500))
            == "42.5 km ultra-distance route"
        )

    def test_track_workout_prefix_on_short_loop(self):
        # Track workout type → "track loop"
        assert (
            _auto_display_name(_R(distance_p50_m=4000), dominant_type="track_workout")
            == "4.0 km track loop"
        )

    def test_threshold_prefix_on_mid_route(self):
        assert (
            _auto_display_name(_R(distance_p50_m=10000), dominant_type="threshold_run")
            == "10.0 km tempo route"
        )

    def test_long_run_does_not_double_label(self):
        # 18.8 km long-run + dominant_type=long_run should NOT be
        # "long-run long-run route"; the descriptor already says it.
        assert (
            _auto_display_name(_R(distance_p50_m=18800), dominant_type="long_run")
            == "18.8 km long-run route"
        )

    def test_unknown_workout_type_no_prefix(self):
        # recovery_run isn't track/threshold/long → no prefix added
        assert (
            _auto_display_name(_R(distance_p50_m=10000), dominant_type="recovery_run")
            == "10.0 km route"
        )
