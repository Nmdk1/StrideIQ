"""Regression tests: home trajectory sentence respects athlete preferred_units.

Imperial athletes get miles, metric athletes get kilometres. No mixed units.
"""

import pytest

from routers.home import generate_trajectory_sentence


class TestTrajectorySentenceImperial:
    def test_no_plan_single_run_miles(self):
        out = generate_trajectory_sentence(
            status="no_plan",
            completed_mi=8.0,
            planned_mi=0.0,
            activities_this_week=1,
            preferred_units="imperial",
        )
        assert out == "8 mi logged this week. Consistency compounds."

    def test_no_plan_multi_run_miles(self):
        out = generate_trajectory_sentence(
            status="no_plan",
            completed_mi=51.0,
            planned_mi=0.0,
            activities_this_week=5,
            preferred_units="imperial",
        )
        assert out == "51 mi across 5 runs this week."

    def test_ahead_status_miles(self):
        out = generate_trajectory_sentence(
            status="ahead",
            completed_mi=20.0,
            planned_mi=15.0,
            preferred_units="imperial",
        )
        assert "20 mi" in out
        assert "15 mi" in out
        assert "km" not in out

    def test_default_units_when_none_is_imperial(self):
        out = generate_trajectory_sentence(
            status="no_plan",
            completed_mi=10.0,
            planned_mi=0.0,
            activities_this_week=2,
            preferred_units=None,
        )
        assert "mi" in out
        assert "km" not in out


class TestTrajectorySentenceMetric:
    def test_no_plan_single_run_km(self):
        out = generate_trajectory_sentence(
            status="no_plan",
            completed_mi=8.0,
            planned_mi=0.0,
            activities_this_week=1,
            preferred_units="metric",
        )
        # 8 mi * 1.60934 = 12.87 km -> rounded to "13 km"
        assert out == "13 km logged this week. Consistency compounds."
        assert "mi" not in out.replace("compounds", "")

    def test_no_plan_multi_run_km(self):
        out = generate_trajectory_sentence(
            status="no_plan",
            completed_mi=51.0,
            planned_mi=0.0,
            activities_this_week=5,
            preferred_units="metric",
        )
        # 51 mi * 1.60934 = 82.08 km -> rounded to "82 km"
        assert out == "82 km across 5 runs this week."

    def test_ahead_status_km(self):
        out = generate_trajectory_sentence(
            status="ahead",
            completed_mi=20.0,
            planned_mi=15.0,
            preferred_units="metric",
        )
        # 20 mi -> 32 km, 15 mi -> 24 km
        assert "32 km" in out
        assert "24 km" in out
        assert " mi" not in out

    def test_behind_status_km(self):
        out = generate_trajectory_sentence(
            status="behind",
            completed_mi=5.0,
            planned_mi=20.0,
            remaining_mi=15.0,
            preferred_units="metric",
        )
        assert "24 km" in out
        assert "Behind schedule" in out
        assert " mi" not in out
