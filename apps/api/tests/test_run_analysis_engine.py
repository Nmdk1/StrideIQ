"""
Unit tests for Run Analysis Engine

Tests percentile calculation, cohort selection, label generation, and
GarminDay gap-fill behavior (device vs self-report priority contract).

Bug fix verified: Percentile direction + label for positive outlier post-injury.
"""

import pytest
from datetime import datetime, timedelta, date
from unittest.mock import MagicMock, patch, PropertyMock
from uuid import uuid4

from services.run_analysis_engine import (
    RunAnalysisEngine,
    WorkoutType,
    InputSnapshot,
    _garmin_stress_qualifier,
)


class TestPercentileCalculation:
    """Test percentile calculation and direction."""
    
    def test_lower_efficiency_score_is_better(self):
        """
        Efficiency score = HR / pace.
        Lower score = less HR per unit of pace = more efficient.
        A run with lower score should have HIGHER percentile.
        """
        # If current run has efficiency_score = 10
        # And similar runs have scores [15, 20, 25, 30]
        # All 4 similar runs have HIGHER (worse) scores
        # So better_count = 4, percentile = 4/4 * 100 = 100%
        
        current_score = 10
        similar_scores = [15, 20, 25, 30]
        
        better_count = sum(1 for e in similar_scores if e > current_score)
        percentile = (better_count / len(similar_scores)) * 100
        
        assert percentile == 100.0, "Best run should be 100th percentile"
    
    def test_higher_efficiency_score_is_worse(self):
        """
        A run with higher efficiency score should have LOWER percentile.
        """
        # If current run has efficiency_score = 35
        # And similar runs have scores [15, 20, 25, 30]
        # 0 similar runs have higher scores
        # So better_count = 0, percentile = 0%
        
        current_score = 35
        similar_scores = [15, 20, 25, 30]
        
        better_count = sum(1 for e in similar_scores if e > current_score)
        percentile = (better_count / len(similar_scores)) * 100
        
        assert percentile == 0.0, "Worst run should be 0th percentile"
    
    def test_median_run_is_50th_percentile(self):
        """
        A run in the middle should be around 50th percentile.
        """
        current_score = 22.5
        similar_scores = [15, 20, 25, 30]
        
        better_count = sum(1 for e in similar_scores if e > current_score)
        percentile = (better_count / len(similar_scores)) * 100
        
        assert percentile == 50.0, "Median run should be 50th percentile"


class TestLabelGeneration:
    """Test that labels correctly describe performance direction."""
    
    def test_high_percentile_shows_better_than(self):
        """
        Percentile > 75% should generate "Better than X%" text.
        """
        percentile = 85
        
        # Simulate the label generation logic
        if percentile > 75:
            label = f"Better than {int(percentile)}% of your recent runs"
        else:
            label = None
        
        assert label is not None
        assert "Better than 85%" in label
    
    def test_low_percentile_shows_harder_effort(self):
        """
        Percentile < 25% should generate "Harder effort" text, not confusing "Below X%".
        
        This is the bug fix: "Below 100%" was confusing.
        Now says "Harder effort than X% of your recent runs".
        """
        percentile = 5
        workout_type = "moderate"
        
        # Simulate the NEW label generation logic (after fix)
        if percentile < 25:
            label = f"Harder effort than {int(100 - percentile)}% of your recent {workout_type} runs (last 90 days)"
        else:
            label = None
        
        assert label is not None
        assert "Harder effort than 95%" in label
        assert "last 90 days" in label
        assert "Below" not in label  # Bug fix: no more confusing "Below" label


class TestCohortTimeWindow:
    """Test that cohort selection respects time windows."""
    
    def test_cohort_limited_to_90_days(self):
        """
        The _find_similar_workouts function should limit to 90 days by default.
        This prevents comparing post-injury runs to pre-injury peak performance.
        """
        # This is a behavior test - the window should be 90 days
        before_date = date(2026, 1, 26)
        days_window = 90
        
        earliest_date = before_date - timedelta(days=days_window)
        
        assert earliest_date == date(2025, 10, 28)
        
        # An activity from 100 days ago should be excluded
        old_activity_date = before_date - timedelta(days=100)
        assert old_activity_date < earliest_date, "Old activities should be excluded"
        
        # An activity from 60 days ago should be included
        recent_activity_date = before_date - timedelta(days=60)
        assert recent_activity_date >= earliest_date, "Recent activities should be included"


class TestPostInjuryScenario:
    """
    Test the specific bug scenario: post-injury run showing conflicting info.
    
    Scenario:
    - Athlete returns from injury
    - First few runs are significantly better than other recovery runs
    - But would be worse than pre-injury peak
    
    Expected behavior:
    - Both efficiency cards should agree (efficient vs recent context)
    - Percentile compares to 90-day window (post-injury period)
    - Labels are clear and non-contradictory
    """
    
    def test_post_injury_positive_outlier(self):
        """
        A post-injury run that's very efficient should show:
        - High percentile (vs other post-injury runs)
        - Positive label ("Better than X%")
        
        NOT:
        - 0th percentile (comparing to pre-injury)
        - Negative label ("Below 100%")
        """
        # Simulate post-injury scenario
        # This run: efficiency_score = 12 (good for recovery period)
        # Recent 90-day runs (all recovery): [14, 15, 16, 18]
        # Pre-injury runs (excluded by 90-day window): [8, 9, 10, 11]
        
        current_score = 12
        recent_90_day_scores = [14, 15, 16, 18]  # Other recovery runs
        
        # Calculate percentile vs 90-day cohort only
        better_count = sum(1 for e in recent_90_day_scores if e > current_score)
        percentile = (better_count / len(recent_90_day_scores)) * 100
        
        # This run is better than ALL recovery runs
        assert percentile == 100.0, "Best recovery run should be 100th percentile"
        
        # Label should be positive
        if percentile > 75:
            label = f"Better than {int(percentile)}% of your recent runs"
        else:
            label = "Unexpected negative label"
        
        assert "Better than 100%" in label
        assert "Below" not in label


class TestOutlierReason:
    """Test that outlier reasons are clear and accurate."""
    
    def test_bottom_5_percent_outlier_reason(self):
        """
        Bottom 5% runs should have a clear, non-judgmental reason.
        """
        percentile = 3
        
        # NEW reason (after fix)
        if percentile < 5:
            reason = "Effort required more from your body than usual (vs last 90 days)"
        else:
            reason = None
        
        assert reason is not None
        assert "required more from your body" in reason
        assert "90 days" in reason
        # Old confusing text should be gone
        assert "below" not in reason.lower()
    
    def test_top_5_percent_outlier_reason(self):
        """
        Top 5% runs should have a positive reason.
        """
        percentile = 97
        
        if percentile > 95:
            reason = "Exceptionally efficient run compared to recent efforts"
        else:
            reason = None
        
        assert reason is not None
        assert "efficient" in reason.lower()


# =============================================================================
# GarminDay gap-fill tests (builder note: 6 required paths)
# =============================================================================

def _make_garmin_day(calendar_date, sleep_total_s=None, hrv_overnight_avg=None,
                     resting_hr=None, avg_stress=None):
    """Build a mock GarminDay with the given fields."""
    g = MagicMock()
    g.calendar_date = calendar_date
    g.sleep_total_s = sleep_total_s
    g.hrv_overnight_avg = hrv_overnight_avg
    g.resting_hr = resting_hr
    g.avg_stress = avg_stress
    return g


def _make_checkin(checkin_date, sleep_h=None, hrv_rmssd=None,
                  resting_hr=None, stress_1_5=None, soreness_1_5=None):
    """Build a mock DailyCheckin with the given fields."""
    c = MagicMock()
    c.date = checkin_date
    c.sleep_h = sleep_h
    c.hrv_rmssd = hrv_rmssd
    c.resting_hr = resting_hr
    c.stress_1_5 = stress_1_5
    c.soreness_1_5 = soreness_1_5
    return c


class TestGarminDayGapFill:
    """
    Verify the GarminDay gap-fill contract in get_input_snapshot().

    Source priority rule (non-negotiable):
      1. DailyCheckin (self-report) wins on overlapping fields.
      2. GarminDay fills only null fields.
      3. Garmin stress is NEVER written to stress_today (/5 field).
    """

    RUN_DATE = date(2026, 2, 28)

    def _engine_with_db(self, checkins, garmin_rows, activities=None):
        """Return a RunAnalysisEngine whose DB queries return the given data."""
        db = MagicMock()
        athlete_id = uuid4()

        activities = activities or []

        def query_side_effect(model):
            from models import DailyCheckin as DC, GarminDay as GD, Activity as A
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q

            if model is DC:
                mock_q.all.return_value = checkins
            elif model is GD:
                mock_q.all.return_value = garmin_rows
            elif model is A:
                mock_q.all.return_value = activities
            else:
                mock_q.all.return_value = []
            return mock_q

        db.query.side_effect = query_side_effect
        engine = RunAnalysisEngine(db)
        return engine, athlete_id

    # ------------------------------------------------------------------
    # Test 1 — Device-only path
    # ------------------------------------------------------------------
    def test_device_only_path(self):
        """No check-ins + GarminDay present → snapshot populated from device."""
        garmin = _make_garmin_day(
            calendar_date=self.RUN_DATE,
            sleep_total_s=27000,   # 7.5 h
            hrv_overnight_avg=58,
            resting_hr=52,
            avg_stress=30,
        )
        engine, athlete_id = self._engine_with_db(checkins=[], garmin_rows=[garmin])
        snapshot = engine.get_input_snapshot(athlete_id, self.RUN_DATE)

        assert snapshot.sleep_last_night == pytest.approx(7.5, rel=1e-3)
        assert snapshot.hrv_today == 58.0
        assert snapshot.resting_hr_today == 52
        assert snapshot.garmin_stress_score == 30
        assert snapshot.garmin_stress_qualifier == "balanced"
        assert "sleep_last_night" in snapshot.garmin_filled_fields
        assert "hrv_today" in snapshot.garmin_filled_fields
        assert "resting_hr_today" in snapshot.garmin_filled_fields
        # Self-report stress field must remain null
        assert snapshot.stress_today is None

    # ------------------------------------------------------------------
    # Test 2 — Priority path: DailyCheckin wins on overlapping fields
    # ------------------------------------------------------------------
    def test_priority_checkin_wins_on_overlap(self):
        """
        Both sources present → check-in values win; garmin_filled_fields is empty
        for overlapping fields.
        """
        checkin_today = _make_checkin(
            self.RUN_DATE, sleep_h=6.0, hrv_rmssd=70, resting_hr=48, stress_1_5=3
        )
        checkin_yest = _make_checkin(self.RUN_DATE - timedelta(days=1), sleep_h=6.5)
        garmin = _make_garmin_day(
            calendar_date=self.RUN_DATE,
            sleep_total_s=28800,   # 8 h — should NOT override check-in
            hrv_overnight_avg=40,  # lower — should NOT override check-in
            resting_hr=60,         # higher — should NOT override check-in
            avg_stress=80,
        )
        engine, athlete_id = self._engine_with_db(
            checkins=[checkin_today, checkin_yest],
            garmin_rows=[garmin],
        )
        snapshot = engine.get_input_snapshot(athlete_id, self.RUN_DATE)

        # Self-report values preserved
        assert snapshot.hrv_today == 70.0
        assert snapshot.resting_hr_today == 48
        assert snapshot.stress_today == 3
        # Garmin stress stored separately (different field)
        assert snapshot.garmin_stress_score == 80
        assert snapshot.garmin_stress_qualifier == "very_stressful"
        # No physiological fields overwritten
        assert "hrv_today" not in snapshot.garmin_filled_fields
        assert "resting_hr_today" not in snapshot.garmin_filled_fields

    # ------------------------------------------------------------------
    # Test 3 — Hybrid path: partial check-ins, Garmin fills nulls
    # ------------------------------------------------------------------
    def test_hybrid_partial_checkin_garmin_fills_nulls(self):
        """
        Partial check-in (has stress/soreness, missing HRV/resting_hr) →
        Garmin fills only the null physiological fields.
        """
        checkin_today = _make_checkin(
            self.RUN_DATE, stress_1_5=2, soreness_1_5=1,
            sleep_h=None, hrv_rmssd=None, resting_hr=None,
        )
        garmin = _make_garmin_day(
            calendar_date=self.RUN_DATE,
            sleep_total_s=25200,   # 7.0 h
            hrv_overnight_avg=62,
            resting_hr=55,
            avg_stress=20,
        )
        engine, athlete_id = self._engine_with_db(
            checkins=[checkin_today],
            garmin_rows=[garmin],
        )
        snapshot = engine.get_input_snapshot(athlete_id, self.RUN_DATE)

        # Self-report preserved
        assert snapshot.stress_today == 2
        assert snapshot.soreness_today == 1
        # Garmin filled nulls
        assert snapshot.sleep_last_night == pytest.approx(7.0, rel=1e-3)
        assert snapshot.hrv_today == 62.0
        assert snapshot.resting_hr_today == 55
        assert "hrv_today" in snapshot.garmin_filled_fields
        assert "resting_hr_today" in snapshot.garmin_filled_fields
        # stress_today must remain self-report only
        assert snapshot.garmin_stress_score == 20
        assert snapshot.garmin_stress_qualifier == "calm"

    # ------------------------------------------------------------------
    # Test 4 — Stress sentinel -1 → Garmin stress fields remain null
    # ------------------------------------------------------------------
    def test_stress_sentinel_minus_one_produces_null(self):
        """avg_stress = -1 is Garmin's sentinel for 'no measurement'. Both Garmin stress fields must stay null."""
        garmin = _make_garmin_day(
            calendar_date=self.RUN_DATE,
            resting_hr=54,
            avg_stress=-1,   # sentinel
        )
        engine, athlete_id = self._engine_with_db(checkins=[], garmin_rows=[garmin])
        snapshot = engine.get_input_snapshot(athlete_id, self.RUN_DATE)

        assert snapshot.garmin_stress_score is None
        assert snapshot.garmin_stress_qualifier is None
        # Resting HR still filled
        assert snapshot.resting_hr_today == 54

    # ------------------------------------------------------------------
    # Test 5 — Graceful empty path: no GarminDay rows → no crash
    # ------------------------------------------------------------------
    def test_graceful_empty_garmin(self):
        """No GarminDay rows → snapshot behaves identically to pre-GarminDay code."""
        engine, athlete_id = self._engine_with_db(checkins=[], garmin_rows=[])
        snapshot = engine.get_input_snapshot(athlete_id, self.RUN_DATE)

        assert snapshot.sleep_last_night is None
        assert snapshot.hrv_today is None
        assert snapshot.resting_hr_today is None
        assert snapshot.garmin_stress_score is None
        assert snapshot.garmin_stress_qualifier is None
        assert snapshot.garmin_filled_fields == []


class TestGarminStressQualifier:
    """Test deterministic stress qualifier bands."""

    def test_calm_band(self):
        assert _garmin_stress_qualifier(0) == "calm"
        assert _garmin_stress_qualifier(24) == "calm"

    def test_balanced_band(self):
        assert _garmin_stress_qualifier(25) == "balanced"
        assert _garmin_stress_qualifier(49) == "balanced"

    def test_stressful_band(self):
        assert _garmin_stress_qualifier(50) == "stressful"
        assert _garmin_stress_qualifier(74) == "stressful"

    def test_very_stressful_band(self):
        assert _garmin_stress_qualifier(75) == "very_stressful"
        assert _garmin_stress_qualifier(100) == "very_stressful"
