"""
Unit tests for Home API Router

Tests the Glance layer data:
- Today's workout with context (correlation-based when available)
- Yesterday's insight (from InsightAggregator when available)
- Week progress with trajectory and TSB context

ADR-020: Home Experience Phase 1 Enhancement
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from routers.home import (
    generate_why_context,
    generate_yesterday_insight,
    generate_trajectory_sentence,
    format_phase,
    format_pace,
    get_correlation_context,
    get_tsb_context,
    compute_coach_noticed,
    compute_race_countdown,
    CoachNoticed,
    RaceCountdown,
)


class TestFormatPhase:
    """Tests for phase display name formatting."""
    
    def test_base_phase(self):
        assert format_phase("base") == "Base"
    
    def test_threshold_phase(self):
        assert format_phase("threshold") == "Threshold"
    
    def test_marathon_specific_phase(self):
        assert format_phase("marathon_specific") == "Marathon Specific"
    
    def test_unknown_phase_formats_nicely(self):
        assert format_phase("custom_phase") == "Custom Phase"
    
    def test_none_returns_none(self):
        assert format_phase(None) is None


class TestFormatPace:
    """Tests for pace formatting."""
    
    def test_format_7_minute_pace(self):
        assert format_pace(420) == "7:00/mi"
    
    def test_format_8_30_pace(self):
        assert format_pace(510) == "8:30/mi"
    
    def test_format_sub_6_pace(self):
        assert format_pace(350) == "5:50/mi"


class TestGenerateTrajectory:
    """Tests for trajectory sentence generation (ADR-020)."""
    
    def test_ahead_status(self):
        result = generate_trajectory_sentence("ahead", 30, 40)
        assert "Ahead of schedule" in result
        assert "30 mi done" in result
        assert "40 mi planned" in result
    
    def test_on_track_status(self):
        result = generate_trajectory_sentence("on_track", 20, 40)
        assert "On track" in result
        assert "20 mi remaining" in result
    
    def test_behind_status(self):
        result = generate_trajectory_sentence("behind", 10, 40)
        assert "Behind schedule" in result
        assert "30 mi to go" in result
    
    def test_no_plan_returns_none(self):
        result = generate_trajectory_sentence("no_plan", 0, 0)
        assert result is None
    
    def test_no_plan_with_activities_includes_tsb(self):
        """No plan but has activities can include TSB context."""
        result = generate_trajectory_sentence(
            "no_plan", 20, 0, 
            activities_this_week=3, 
            tsb_context="TSB +15. Good window."
        )
        assert "20 mi across 3 runs" in result
        assert "TSB +15" in result


class TestGenerateWhyContext:
    """Tests for 'Why This Workout' context generation (ADR-020)."""
    
    def test_threshold_workout_context(self):
        """Plan-based context for threshold workout."""
        workout = MagicMock()
        workout.workout_type = "threshold"
        
        plan = MagicMock()
        plan.total_weeks = 12
        
        # Without db/athlete_id, falls back to plan-based
        result, source = generate_why_context(workout, plan, 5, "threshold")
        
        assert "Week 5 of 12" in result
        assert "Threshold phase" in result
        assert "Builds lactate clearance" in result
        assert source == "plan"
    
    def test_long_run_context(self):
        """Plan-based context for long run."""
        workout = MagicMock()
        workout.workout_type = "long"
        
        plan = MagicMock()
        plan.total_weeks = 16
        
        result, source = generate_why_context(workout, plan, 8, "base")
        
        assert "Week 8 of 16" in result
        assert "Builds endurance and fat metabolism" in result
        assert source == "plan"
    
    def test_easy_run_context(self):
        """Plan-based context for easy run."""
        workout = MagicMock()
        workout.workout_type = "easy"
        
        plan = MagicMock()
        plan.total_weeks = 12
        
        result, source = generate_why_context(workout, plan, 3, "base")
        
        assert "Active recovery day" in result
        assert source == "plan"
    
    def test_early_build_context(self):
        """Plan-based context for week 1."""
        workout = MagicMock()
        workout.workout_type = "easy"
        
        plan = MagicMock()
        plan.total_weeks = 12
        
        result, source = generate_why_context(workout, plan, 1, "base")
        
        assert "Week 1" in result
        assert "Building foundation" in result
        assert source == "plan"
    
    def test_final_weeks_context(self):
        """Plan-based context for final week."""
        workout = MagicMock()
        workout.workout_type = "tempo"
        
        plan = MagicMock()
        plan.total_weeks = 12
        
        result, source = generate_why_context(workout, plan, 12, "taper")
        
        assert "Final push" in result
        assert source == "plan"


class TestGetCorrelationContext:
    """Tests for correlation-based context (ADR-020)."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_returns_none_on_no_correlations(self, mock_db):
        """Returns None when no correlations exist."""
        with patch('services.correlation_engine.analyze_correlations') as mock_analyze:
            mock_analyze.return_value = {'error': 'Insufficient data'}
            
            context, source = get_correlation_context("test-id", "easy", mock_db)
            
            assert context is None
            assert source is None
    
    def test_returns_none_on_exception(self, mock_db):
        """Returns None gracefully on exception."""
        with patch('services.correlation_engine.analyze_correlations') as mock_analyze:
            mock_analyze.side_effect = Exception("DB error")
            
            context, source = get_correlation_context("test-id", "easy", mock_db)
            
            assert context is None
            assert source is None
    
    def test_returns_sleep_correlation_context(self, mock_db):
        """Returns context for significant sleep correlation."""
        with patch('services.correlation_engine.analyze_correlations') as mock_analyze:
            mock_analyze.return_value = {
                'correlations': [{
                    'input_name': 'sleep_hours',
                    'correlation_coefficient': 0.6,
                    'is_significant': True,
                    'p_value': 0.02
                }]
            }
            
            context, source = get_correlation_context("test-id", "easy", mock_db)
            
            assert context is not None
            assert "sleep" in context.lower() or "efficiency" in context.lower()
            assert source == "correlation"


class TestGetTSBContext:
    """Tests for TSB-based context (ADR-020)."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_returns_none_on_insufficient_ctl(self, mock_db):
        """Returns None when CTL is too low (< 20)."""
        with patch('services.training_load.TrainingLoadCalculator') as MockCalc:
            mock_instance = MockCalc.return_value
            mock_load = MagicMock()
            mock_load.current_ctl = 15  # Below threshold of 20
            mock_load.current_tsb = 5
            mock_load.current_atl = 15
            mock_instance.calculate_training_load.return_value = mock_load
            
            tsb_label, load_trend, context = get_tsb_context("test-id", mock_db)
            
            assert tsb_label is None
            assert load_trend is None
            assert context is None
    
    def test_returns_none_on_exception(self, mock_db):
        """Returns None gracefully on exception."""
        with patch('services.training_load.TrainingLoadCalculator') as MockCalc:
            MockCalc.side_effect = Exception("DB error")
            
            tsb_label, load_trend, context = get_tsb_context("test-id", mock_db)
            
            assert tsb_label is None
            assert load_trend is None
            assert context is None
    
    def test_returns_none_for_normal_training(self, mock_db):
        """Returns None for normal training states (no noise)."""
        with patch('services.training_load.TrainingLoadCalculator') as MockCalc:
            from services.training_load import TSBZone
            
            mock_instance = MockCalc.return_value
            mock_load = MagicMock()
            mock_load.current_ctl = 40
            mock_load.current_tsb = 0  # Normal range
            mock_load.current_atl = 40
            mock_instance.calculate_training_load.return_value = mock_load
            
            mock_zone = MagicMock()
            mock_zone.zone = TSBZone.OPTIMAL_TRAINING
            mock_instance.get_tsb_zone.return_value = mock_zone
            
            tsb_label, load_trend, context = get_tsb_context("test-id", mock_db)
            
            # Normal training = no context shown (not actionable)
            assert context is None


class TestGenerateYesterdayInsight:
    """Tests for yesterday's insight generation."""
    
    def test_efficiency_insight_positive(self):
        activity = MagicMock()
        activity.efficiency_score = 3.5
        activity.avg_hr = 145
        activity.distance_m = 10000
        activity.duration_s = 3600
        activity.pace_variability = None  # Avoid MagicMock comparison issue
        
        result = generate_yesterday_insight(activity)
        
        assert "Efficiency +3.5% vs baseline" in result
    
    def test_efficiency_insight_negative(self):
        activity = MagicMock()
        activity.efficiency_score = -2.1
        activity.avg_hr = 160
        activity.distance_m = 10000
        activity.duration_s = 3600
        activity.pace_variability = None  # Avoid MagicMock comparison issue
        
        result = generate_yesterday_insight(activity)
        
        assert "Efficiency -2.1% vs baseline" in result
    
    def test_low_hr_insight(self):
        activity = MagicMock()
        activity.efficiency_score = None
        activity.avg_hr = 135
        activity.distance_m = 10000
        activity.duration_s = 3600
        activity.pace_variability = None  # Avoid MagicMock comparison issue
        
        result = generate_yesterday_insight(activity)
        
        assert "HR stayed low" in result
        assert "135 avg" in result
    
    def test_high_hr_insight(self):
        activity = MagicMock()
        activity.efficiency_score = None
        activity.avg_hr = 170
        activity.distance_m = 10000
        activity.duration_s = 3600
        activity.pace_variability = None  # Avoid MagicMock comparison issue
        
        result = generate_yesterday_insight(activity)
        
        assert "HR ran high" in result
    
    def test_fallback_to_distance_pace(self):
        activity = MagicMock()
        activity.efficiency_score = None
        activity.avg_hr = 150  # Neither low nor high
        activity.distance_m = 8046.72  # 5 miles
        activity.duration_s = 2400  # 40 minutes
        activity.pace_variability = None  # Avoid MagicMock comparison issue
        
        result = generate_yesterday_insight(activity)
        
        assert "mi at" in result
        assert "/mi" in result


class TestWeekDayModel:
    """Tests for WeekDay model fields (clickable cards feature)."""
    
    def test_weekday_includes_activity_id_field(self):
        """WeekDay model has activity_id for linking to completed activities."""
        from routers.home import WeekDay
        
        day = WeekDay(
            date="2026-01-30",
            day_abbrev="T",
            workout_type="easy",
            distance_mi=5.0,
            planned_distance_mi=5.0,
            completed=True,
            is_today=False,
            activity_id="abc-123",
            workout_id="workout-456"
        )
        
        assert day.activity_id == "abc-123"
        assert day.workout_id == "workout-456"
        assert day.planned_distance_mi == 5.0
    
    def test_weekday_allows_none_ids(self):
        """WeekDay model allows None for optional ID fields."""
        from routers.home import WeekDay
        
        day = WeekDay(
            date="2026-01-30",
            day_abbrev="T",
            completed=False,
            is_today=True
        )
        
        assert day.activity_id is None
        assert day.workout_id is None
        assert day.planned_distance_mi is None
    
    def test_weekday_completed_day_has_both_distances(self):
        """Completed day can have both actual and planned distances."""
        from routers.home import WeekDay
        
        day = WeekDay(
            date="2026-01-30",
            day_abbrev="T",
            workout_type="easy",
            distance_mi=5.2,  # Actual ran slightly more
            planned_distance_mi=5.0,  # Originally planned
            completed=True,
            is_today=False,
            activity_id="abc-123"
        )
        
        assert day.distance_mi == 5.2
        assert day.planned_distance_mi == 5.0
        assert day.distance_mi != day.planned_distance_mi  # Shows difference


# ── ADR-17 Phase 2: Coach Noticed ───────────────────────────────────


class TestComputeCoachNoticed:
    """Tests for ADR-17 Phase 2 coach_noticed waterfall."""

    @patch("services.correlation_engine.analyze_correlations")
    def test_coach_noticed_picks_strong_correlation(self, mock_corr):
        """Priority 1: strong correlation (|r| >= 0.5, n >= 15)."""
        mock_corr.return_value = {
            "correlations": [
                {
                    "is_significant": True,
                    "correlation_coefficient": 0.65,
                    "sample_size": 20,
                    "input_name": "sleep_hours",
                }
            ]
        }
        db = MagicMock()
        result = compute_coach_noticed("athlete-1", db)
        assert result is not None
        assert result.source == "correlation"
        assert "Sleep Hours" in result.text
        assert result.ask_coach_query

    @patch("services.home_signals.aggregate_signals", side_effect=Exception("disabled"))
    @patch("services.insight_feed.build_insight_feed_cards", side_effect=Exception("disabled"))
    @patch("services.correlation_engine.analyze_correlations")
    def test_coach_noticed_skips_weak_correlation(self, mock_corr, _mock_feed, _mock_sig):
        """Weak correlations (|r| < 0.5) don't qualify for Priority 1."""
        mock_corr.return_value = {
            "correlations": [
                {
                    "is_significant": True,
                    "correlation_coefficient": 0.3,
                    "sample_size": 25,
                    "input_name": "sleep_hours",
                }
            ]
        }
        db = MagicMock()
        result = compute_coach_noticed("athlete-1", db, hero_narrative=None)
        assert result is None

    @patch("services.insight_feed.build_insight_feed_cards", side_effect=Exception("nope"))
    @patch("services.home_signals.aggregate_signals", side_effect=Exception("nope"))
    @patch("services.correlation_engine.analyze_correlations", side_effect=Exception("nope"))
    def test_coach_noticed_fallback_to_narrative(self, _c, _s, _f):
        """Priority 4: hero_narrative fallback when nothing else available."""
        db = MagicMock()
        result = compute_coach_noticed(
            "athlete-1", db, hero_narrative="Your fitness is building steadily."
        )
        assert result is not None
        assert result.source == "narrative"
        assert result.text == "Your fitness is building steadily."

    @patch("services.insight_feed.build_insight_feed_cards", side_effect=Exception("nope"))
    @patch("services.home_signals.aggregate_signals", side_effect=Exception("nope"))
    @patch("services.correlation_engine.analyze_correlations", side_effect=Exception("nope"))
    def test_coach_noticed_returns_none_when_nothing(self, _c, _s, _f):
        """No data at all → None."""
        db = MagicMock()
        result = compute_coach_noticed("athlete-1", db, hero_narrative=None)
        assert result is None

    @patch("services.home_signals.aggregate_signals")
    @patch("services.correlation_engine.analyze_correlations")
    def test_coach_noticed_picks_signal_when_no_correlation(self, mock_corr, mock_signals):
        """Priority 2: top signal when no strong correlation exists."""
        mock_corr.return_value = {"correlations": []}
        mock_signal = MagicMock()
        mock_signal.title = "Efficiency trending up"
        mock_signal.subtitle = "3 week improvement"
        mock_signals.return_value = MagicMock(signals=[mock_signal])
        db = MagicMock()
        result = compute_coach_noticed("athlete-1", db)
        assert result is not None
        assert result.source == "signal"
        assert "Efficiency trending up" in result.text


# ── ADR-17 Phase 2: Race Countdown ──────────────────────────────────


class TestComputeRaceCountdown:
    """Tests for ADR-17 Phase 2 race_countdown computation."""

    def test_race_countdown_with_plan(self):
        """Returns countdown with all fields when plan has race data."""
        plan = MagicMock()
        plan.goal_race_name = "Boston Marathon"
        plan.goal_race_date = date.today() + timedelta(days=30)
        plan.goal_time_seconds = 11400  # 3:10:00
        plan.goal_race_distance_m = 42195.0
        db = MagicMock()
        with patch("services.race_predictor.predict_race_time", return_value=None):
            result = compute_race_countdown(plan, "athlete-1", db)
        assert result is not None
        assert result.days_remaining == 30
        assert result.race_name == "Boston Marathon"
        assert result.goal_time == "3:10:00"
        assert result.goal_pace is not None  # derived from goal_time / distance

    def test_race_countdown_no_plan(self):
        """Returns None when no active plan."""
        result = compute_race_countdown(None, "athlete-1", MagicMock())
        assert result is None

    def test_race_countdown_past_race(self):
        """Returns None when race date has passed."""
        plan = MagicMock()
        plan.goal_race_date = date.today() - timedelta(days=5)
        plan.goal_race_name = "Old Race"
        db = MagicMock()
        result = compute_race_countdown(plan, "athlete-1", db)
        assert result is None

    def test_race_countdown_no_race_date(self):
        """Returns None when plan has no race date."""
        plan = MagicMock()
        plan.goal_race_date = None
        db = MagicMock()
        result = compute_race_countdown(plan, "athlete-1", db)
        assert result is None

    def test_race_countdown_no_goal_time(self):
        """Countdown still works without goal_time — pace and time are None."""
        plan = MagicMock()
        plan.goal_race_name = "Local 10K"
        plan.goal_race_date = date.today() + timedelta(days=14)
        plan.goal_time_seconds = None
        plan.goal_race_distance_m = None
        db = MagicMock()
        with patch("services.race_predictor.predict_race_time", return_value=None):
            result = compute_race_countdown(plan, "athlete-1", db)
        assert result is not None
        assert result.goal_time is None
        assert result.goal_pace is None
        assert result.days_remaining == 14
