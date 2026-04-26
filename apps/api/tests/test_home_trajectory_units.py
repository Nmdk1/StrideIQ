"""Regression tests: home trajectory sentence respects athlete preferred_units.

Imperial athletes get miles, metric athletes get kilometres. No mixed units.

All distance inputs are in meters (canonical). The function formats output
using the athlete's preferred_units.
"""

import pytest

from routers.home import generate_trajectory_sentence


class TestTrajectorySentenceImperial:
    def test_no_plan_single_run_miles(self):
        out = generate_trajectory_sentence(
            status="no_plan",
            completed_m=12875,
            planned_m=0,
            activities_this_week=1,
            preferred_units="imperial",
        )
        assert out == "8 mi logged this week. Consistency compounds."

    def test_no_plan_multi_run_miles(self):
        out = generate_trajectory_sentence(
            status="no_plan",
            completed_m=82076,
            planned_m=0,
            activities_this_week=5,
            preferred_units="imperial",
        )
        assert out == "51 mi across 5 runs this week."

    def test_ahead_status_miles(self):
        out = generate_trajectory_sentence(
            status="ahead",
            completed_m=32187,
            planned_m=24140,
            preferred_units="imperial",
        )
        assert "20 mi" in out
        assert "15 mi" in out
        assert "km" not in out

    def test_default_units_when_none_is_imperial(self):
        out = generate_trajectory_sentence(
            status="no_plan",
            completed_m=16093,
            planned_m=0,
            activities_this_week=2,
            preferred_units=None,
        )
        assert "mi" in out
        assert "km" not in out


class TestTrajectorySentenceMetric:
    def test_no_plan_single_run_km(self):
        out = generate_trajectory_sentence(
            status="no_plan",
            completed_m=13000,
            planned_m=0,
            activities_this_week=1,
            preferred_units="metric",
        )
        assert out == "13 km logged this week. Consistency compounds."
        assert "mi" not in out.replace("compounds", "")

    def test_no_plan_multi_run_km(self):
        out = generate_trajectory_sentence(
            status="no_plan",
            completed_m=82000,
            planned_m=0,
            activities_this_week=5,
            preferred_units="metric",
        )
        assert out == "82 km across 5 runs this week."

    def test_ahead_status_km(self):
        out = generate_trajectory_sentence(
            status="ahead",
            completed_m=32000,
            planned_m=24000,
            preferred_units="metric",
        )
        assert "32 km" in out
        assert "24 km" in out
        assert " mi" not in out

    def test_behind_status_km(self):
        out = generate_trajectory_sentence(
            status="behind",
            completed_m=5000,
            planned_m=20000,
            remaining_m=15000,
            preferred_units="metric",
        )
        assert "15 km" in out
        assert "Behind schedule" in out
        assert " mi" not in out
