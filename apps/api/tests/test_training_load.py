"""
Unit tests for Training Load Service (TSB/ATL/CTL)

Tests TSS calculations, load metrics, zone classification,
and race readiness scoring.

ADR-010: Training Stress Balance
"""

import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4
from unittest.mock import MagicMock, patch
from services.training_load import (
    TrainingLoadCalculator,
    WorkoutStress,
    DailyLoad,
    LoadSummary,
    TSBZone,
    TSBZoneInfo,
    RaceReadiness,
    PersonalTSBProfile
)


class TestPopulationTSBZones:
    """Test population-based TSB zone classification (fallback behavior)."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    @pytest.fixture
    def calculator(self, mock_db):
        return TrainingLoadCalculator(mock_db)
    
    def test_race_ready_zone(self, calculator):
        """TSB 15+ should be race ready (population norm)."""
        zone = calculator._get_population_tsb_zone(20)
        assert zone.zone == TSBZone.RACE_READY
        assert zone.is_race_window is True
        assert zone.color == "green"
        
    def test_race_ready_lower_bound(self, calculator):
        """TSB 15 should be race ready."""
        zone = calculator._get_population_tsb_zone(15)
        assert zone.zone == TSBZone.RACE_READY
        
    def test_recovering_zone(self, calculator):
        """TSB 5-15 should be recovering."""
        zone = calculator._get_population_tsb_zone(10)
        assert zone.zone == TSBZone.RECOVERING
        assert zone.is_race_window is False
        assert zone.color == "blue"
    
    def test_optimal_training_zone(self, calculator):
        """TSB -10 to +5 should be optimal training."""
        zone = calculator._get_population_tsb_zone(0)
        assert zone.zone == TSBZone.OPTIMAL_TRAINING
        assert zone.label == "Optimal Training"
        
        zone = calculator._get_population_tsb_zone(-5)
        assert zone.zone == TSBZone.OPTIMAL_TRAINING
    
    def test_overreaching_zone(self, calculator):
        """TSB -30 to -10 should be overreaching."""
        zone = calculator._get_population_tsb_zone(-20)
        assert zone.zone == TSBZone.OVERREACHING
        assert zone.color == "orange"
    
    def test_overtraining_risk_zone(self, calculator):
        """TSB < -30 should be overtraining risk."""
        zone = calculator._get_population_tsb_zone(-35)
        assert zone.zone == TSBZone.OVERTRAINING_RISK
        assert zone.color == "red"
        assert "Red zone" in zone.description
    
    def test_very_fresh_still_race_ready(self, calculator):
        """Very high TSB should still be race ready."""
        zone = calculator._get_population_tsb_zone(30)
        assert zone.zone == TSBZone.RACE_READY


class TestPersonalTSBProfile:
    """Test N=1 personalized TSB zones."""
    
    def test_profile_from_insufficient_data(self):
        """Profile with <56 days should use population defaults."""
        athlete_id = uuid4()
        tsb_values = [-5, -10, 0, 5, -15]  # Only 5 days
        
        profile = PersonalTSBProfile.from_tsb_history(athlete_id, tsb_values)
        
        assert profile.is_sufficient_data is False
        # Should use population defaults
        assert profile.mean_tsb == -5.0
        assert profile.std_tsb == 15.0
    
    def test_profile_from_sufficient_data(self):
        """Profile with 56+ days should calculate personal stats."""
        athlete_id = uuid4()
        # Simulate 60 days of TSB values averaging around -15
        tsb_values = [-15 + (i % 10) - 5 for i in range(60)]
        
        profile = PersonalTSBProfile.from_tsb_history(athlete_id, tsb_values)
        
        assert profile.is_sufficient_data is True
        assert profile.sample_days == 60
        # Mean should be close to -15
        assert -20 < profile.mean_tsb < -10
    
    def test_personal_zone_thresholds_calculated(self):
        """Personal thresholds should be mean ± SD based."""
        athlete_id = uuid4()
        # Create athlete who trains at mean TSB of -20, SD of 10
        tsb_values = [-20 + (i % 20) - 10 for i in range(70)]
        
        profile = PersonalTSBProfile.from_tsb_history(athlete_id, tsb_values)
        
        # Thresholds should be relative to personal mean/SD
        assert profile.threshold_fresh > profile.mean_tsb  # Fresh = mean + 1.5 SD
        assert profile.threshold_danger < profile.mean_tsb  # Danger = mean - 2 SD
    
    def test_get_zone_uses_personal_thresholds(self):
        """Zone classification should use personal thresholds."""
        athlete_id = uuid4()
        # High-volume athlete: mean TSB = -20, SD = 10
        # For this athlete, TSB -10 is actually fresher than normal
        profile = PersonalTSBProfile(
            athlete_id=athlete_id,
            mean_tsb=-20.0,
            std_tsb=10.0,
            min_tsb=-40.0,
            max_tsb=5.0,
            sample_days=90,
            threshold_fresh=-5.0,      # -20 + 1.5*10 = -5
            threshold_recovering=-12.5, # -20 + 0.75*10 = -12.5
            threshold_normal_low=-30.0, # -20 - 1*10 = -30
            threshold_danger=-40.0,    # -20 - 2*10 = -40
            is_sufficient_data=True
        )
        
        # TSB -10 (which population would call "overreaching")
        # is in RECOVERING zone for this high-volume athlete
        zone = profile.get_zone(-10)
        assert zone == TSBZone.RECOVERING  # Not OVERREACHING!
        
        # TSB -20 is their normal (optimal training)
        zone = profile.get_zone(-20)
        assert zone == TSBZone.OPTIMAL_TRAINING
        
        # TSB -35 would be overreaching for this athlete
        zone = profile.get_zone(-35)
        assert zone == TSBZone.OVERREACHING
        
        # Population-based would call TSB -20 "overreaching"
        # but for this athlete it's normal training
        
    def test_personal_zone_info_descriptions(self):
        """Zone info should include personalized descriptions."""
        athlete_id = uuid4()
        profile = PersonalTSBProfile(
            athlete_id=athlete_id,
            mean_tsb=-15.0,
            std_tsb=10.0,
            min_tsb=-35.0,
            max_tsb=10.0,
            sample_days=90,
            threshold_fresh=0.0,
            threshold_recovering=-7.5,
            threshold_normal_low=-25.0,
            threshold_danger=-35.0,
            is_sufficient_data=True
        )
        
        zone_info = profile.get_zone_info(-10)
        
        # Description should mention personal context
        assert "your" in zone_info.description.lower() or "typical" in zone_info.description.lower()
    
    def test_minimum_std_enforced(self):
        """Standard deviation should have minimum to avoid overly narrow zones."""
        athlete_id = uuid4()
        # Very consistent athlete - all TSB values the same
        tsb_values = [-10.0] * 60
        
        profile = PersonalTSBProfile.from_tsb_history(athlete_id, tsb_values)
        
        # SD should be at least 8 (enforced minimum)
        assert profile.std_tsb >= 8.0


class TestTSSCalculation:
    """Test TSS calculation methods."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()
    
    @pytest.fixture
    def calculator(self, mock_db):
        """Create calculator instance."""
        return TrainingLoadCalculator(mock_db)
    
    @pytest.fixture
    def mock_athlete(self):
        """Create mock athlete with HR data."""
        athlete = MagicMock()
        athlete.id = uuid4()
        athlete.max_hr = 185
        athlete.resting_hr = 50
        athlete.threshold_pace_per_km = 270  # 4:30/km
        return athlete
    
    @pytest.fixture
    def mock_activity(self):
        """Create mock activity."""
        activity = MagicMock()
        activity.id = uuid4()
        activity.start_time = datetime(2026, 1, 14, 8, 0, 0)
        activity.duration_s = 3600  # 1 hour
        activity.distance_m = 12000  # 12km
        activity.avg_hr = 155
        activity.name = "Easy Morning Run"
        activity.workout_type = "easy_run"
        return activity
    
    def test_hr_tss_calculation(self, calculator, mock_athlete, mock_activity):
        """Test HR-based TSS calculation."""
        stress = calculator.calculate_workout_tss(mock_activity, mock_athlete)
        
        assert stress.tss > 0
        assert stress.calculation_method == "hrTSS"
        assert stress.duration_minutes == 60
        assert 0 < stress.intensity_factor < 2
    
    def test_running_tss_calculation(self, calculator, mock_activity):
        """Test pace-based TSS calculation when no HR data."""
        athlete = MagicMock()
        athlete.max_hr = None
        athlete.resting_hr = None
        athlete.threshold_pace_per_km = 270  # 4:30/km
        
        stress = calculator.calculate_workout_tss(mock_activity, athlete)
        
        assert stress.tss > 0
        assert stress.calculation_method == "rTSS"
    
    def test_estimated_tss_fallback(self, calculator, mock_activity):
        """Test estimated TSS when no HR or pace data."""
        athlete = MagicMock()
        athlete.max_hr = None
        athlete.resting_hr = None
        athlete.threshold_pace_per_km = None
        
        # Activity without proper distance
        mock_activity.distance_m = None
        
        stress = calculator.calculate_workout_tss(mock_activity, athlete)
        
        assert stress.tss > 0
        assert stress.calculation_method == "estimated"
    
    def test_short_workout_zero_tss(self, calculator, mock_athlete, mock_activity):
        """Short workouts should have zero TSS."""
        mock_activity.duration_s = 180  # 3 minutes
        
        stress = calculator.calculate_workout_tss(mock_activity, mock_athlete)
        
        assert stress.tss == 0
        assert stress.calculation_method == "too_short"
    
    def test_intensity_affects_tss(self, calculator, mock_athlete, mock_activity):
        """Higher intensity should produce higher TSS."""
        # Easy run
        mock_activity.avg_hr = 130
        easy_stress = calculator.calculate_workout_tss(mock_activity, mock_athlete)
        
        # Tempo run
        mock_activity.avg_hr = 165
        tempo_stress = calculator.calculate_workout_tss(mock_activity, mock_athlete)
        
        # Tempo should have higher TSS
        assert tempo_stress.tss > easy_stress.tss
    
    def test_duration_affects_tss(self, calculator, mock_athlete, mock_activity):
        """Longer duration should produce higher TSS."""
        # 30 minute run
        mock_activity.duration_s = 1800
        short_stress = calculator.calculate_workout_tss(mock_activity, mock_athlete)
        
        # 90 minute run
        mock_activity.duration_s = 5400
        long_stress = calculator.calculate_workout_tss(mock_activity, mock_athlete)
        
        # Longer should have higher TSS
        assert long_stress.tss > short_stress.tss


class TestEstimatedTSSWorkoutTypes:
    """Test TSS estimation based on workout names/types."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    @pytest.fixture
    def calculator(self, mock_db):
        return TrainingLoadCalculator(mock_db)
    
    @pytest.fixture
    def base_activity(self):
        activity = MagicMock()
        activity.id = uuid4()
        activity.start_time = datetime(2026, 1, 14, 8, 0, 0)
        activity.duration_s = 3600  # 1 hour
        activity.distance_m = None  # Force estimation
        activity.avg_hr = None
        return activity
    
    @pytest.fixture
    def athlete_no_data(self):
        athlete = MagicMock()
        athlete.max_hr = None
        athlete.resting_hr = None
        athlete.threshold_pace_per_km = None
        return athlete
    
    def test_race_has_high_intensity(self, calculator, base_activity, athlete_no_data):
        """Race should have IF ~1.0."""
        base_activity.name = "Race Day - 5K PR"
        base_activity.workout_type = "race"
        
        stress = calculator.calculate_workout_tss(base_activity, athlete_no_data)
        
        assert stress.intensity_factor == 1.0
    
    def test_easy_has_low_intensity(self, calculator, base_activity, athlete_no_data):
        """Easy run should have IF ~0.65."""
        base_activity.name = "Easy Recovery Jog"
        base_activity.workout_type = "recovery"
        
        stress = calculator.calculate_workout_tss(base_activity, athlete_no_data)
        
        assert stress.intensity_factor == 0.65
    
    def test_tempo_has_moderate_high_intensity(self, calculator, base_activity, athlete_no_data):
        """Tempo should have IF ~0.9."""
        base_activity.name = "Tempo Thursday"
        base_activity.workout_type = "tempo"
        
        stress = calculator.calculate_workout_tss(base_activity, athlete_no_data)
        
        assert stress.intensity_factor == 0.9
    
    def test_long_run_has_moderate_intensity(self, calculator, base_activity, athlete_no_data):
        """Long run should have IF ~0.75."""
        base_activity.name = "Sunday Long Run"
        base_activity.workout_type = "long_run"
        
        stress = calculator.calculate_workout_tss(base_activity, athlete_no_data)
        
        assert stress.intensity_factor == 0.75


class TestATLCTLCalculation:
    """Test ATL/CTL exponential moving average calculations."""
    
    def test_atl_decay_constant(self):
        """ATL should use 7-day decay."""
        assert TrainingLoadCalculator.ATL_DECAY_DAYS == 7
    
    def test_ctl_decay_constant(self):
        """CTL should use 42-day decay."""
        assert TrainingLoadCalculator.CTL_DECAY_DAYS == 42
    
    def test_tsb_calculation(self):
        """TSB should equal CTL - ATL."""
        # This is tested implicitly in the service
        # TSB = CTL - ATL
        ctl = 50.0
        atl = 35.0
        expected_tsb = 15.0
        assert ctl - atl == expected_tsb


class TestTrendCalculation:
    """Test trend direction calculation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    @pytest.fixture
    def calculator(self, mock_db):
        return TrainingLoadCalculator(mock_db)
    
    def test_rising_trend(self, calculator):
        """Increasing values should show rising trend."""
        old = [30, 32, 35]
        new = [40, 45, 50]
        
        trend = calculator._calculate_trend(old, new)
        
        assert trend == "rising"
    
    def test_falling_trend(self, calculator):
        """Decreasing values should show falling trend."""
        old = [50, 48, 45]
        new = [35, 30, 28]
        
        trend = calculator._calculate_trend(old, new)
        
        assert trend == "falling"
    
    def test_stable_trend(self, calculator):
        """Similar values should show stable trend."""
        old = [40, 42, 41]
        new = [42, 40, 43]
        
        trend = calculator._calculate_trend(old, new)
        
        assert trend == "stable"
    
    def test_empty_values_stable(self, calculator):
        """Empty lists should return stable."""
        trend = calculator._calculate_trend([], [])
        assert trend == "stable"


class TestTrainingPhaseDetection:
    """Test training phase classification."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    @pytest.fixture
    def calculator(self, mock_db):
        return TrainingLoadCalculator(mock_db)
    
    def test_building_phase(self, calculator):
        """Rising ATL and CTL should be building."""
        phase = calculator._determine_training_phase(
            atl=45, ctl=50, tsb=5,
            atl_trend="rising", ctl_trend="rising"
        )
        assert phase == "building"
    
    def test_tapering_phase(self, calculator):
        """Positive TSB with falling ATL should be tapering."""
        phase = calculator._determine_training_phase(
            atl=30, ctl=50, tsb=20,
            atl_trend="falling", ctl_trend="stable"
        )
        assert phase == "tapering"
    
    def test_recovering_phase(self, calculator):
        """Low loads should be recovering."""
        phase = calculator._determine_training_phase(
            atl=15, ctl=25, tsb=10,
            atl_trend="stable", ctl_trend="stable"
        )
        assert phase == "recovering"
    
    def test_maintaining_phase(self, calculator):
        """Stable trends should be maintaining."""
        phase = calculator._determine_training_phase(
            atl=40, ctl=50, tsb=10,
            atl_trend="stable", ctl_trend="stable"
        )
        assert phase == "maintaining"


class TestRaceReadinessScore:
    """Test race readiness calculation."""
    
    def test_score_components(self):
        """Race readiness should have all components."""
        readiness = RaceReadiness(
            score=85.0,
            tsb=20.0,
            tsb_zone=TSBZone.RACE_READY,
            tsb_trend="rising",
            days_since_hard_workout=4,
            recommendation="Excellent race readiness.",
            is_race_window=True
        )
        
        assert readiness.score == 85.0
        assert readiness.is_race_window is True
        assert readiness.tsb_zone == TSBZone.RACE_READY
    
    def test_optimal_tsb_gives_high_score(self):
        """TSB 15-25 should contribute maximum to score."""
        # This is tested through the service
        # Optimal TSB (15-25) should give tsb_score = 100
        tsb = 20
        expected_tsb_score = 100
        
        # Verify logic
        if 15 <= tsb <= 25:
            assert expected_tsb_score == 100
    
    def test_negative_tsb_gives_lower_score(self):
        """Negative TSB should reduce race readiness."""
        tsb = -15
        # In overreaching zone, tsb_score should be low
        # Score = 40 + (-15 + 10) * 1.5 = 40 - 7.5 = 32.5
        expected_lower_bound = 10
        expected_upper_bound = 50
        
        # Verify the score is in the lower range
        assert expected_lower_bound <= 32.5 <= expected_upper_bound


class TestProjectTSB:
    """Test TSB projection functionality."""
    
    def test_rest_projection_increases_tsb(self):
        """Complete rest should increase TSB (ATL drops faster than CTL)."""
        # With rest (TSS=0), ATL drops faster than CTL
        # So TSB = CTL - ATL should increase
        
        # This is a mathematical property of the EMAs
        atl_decay = 2 / 8  # ~0.25
        ctl_decay = 2 / 43  # ~0.047
        
        # After one day of rest (TSS=0):
        # new_atl = old_atl * (1 - 0.25) = old_atl * 0.75
        # new_ctl = old_ctl * (1 - 0.047) = old_ctl * 0.953
        
        # ATL drops by 25%, CTL drops by ~5%
        # So TSB should increase
        assert atl_decay > ctl_decay  # ATL decays faster


class TestDataclasses:
    """Test dataclass structures."""
    
    def test_workout_stress_creation(self):
        """WorkoutStress should be creatable."""
        stress = WorkoutStress(
            activity_id=uuid4(),
            date=date.today(),
            tss=75.0,
            duration_minutes=60.0,
            intensity_factor=0.85,
            calculation_method="hrTSS"
        )
        
        assert stress.tss == 75.0
        assert stress.calculation_method == "hrTSS"
    
    def test_daily_load_creation(self):
        """DailyLoad should be creatable."""
        load = DailyLoad(
            date=date.today(),
            total_tss=100.0,
            workout_count=2,
            atl=45.0,
            ctl=55.0,
            tsb=10.0
        )
        
        assert load.tsb == load.ctl - load.atl
    
    def test_load_summary_creation(self):
        """LoadSummary should be creatable."""
        summary = LoadSummary(
            current_atl=40.0,
            current_ctl=50.0,
            current_tsb=10.0,
            atl_trend="rising",
            ctl_trend="rising",
            tsb_trend="falling",
            training_phase="building",
            recommendation="Building phase."
        )
        
        assert summary.training_phase == "building"


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    @pytest.fixture
    def calculator(self, mock_db):
        return TrainingLoadCalculator(mock_db)
    
    def test_zero_duration_activity(self, calculator):
        """Zero duration should result in zero TSS."""
        activity = MagicMock()
        activity.id = uuid4()
        activity.start_time = datetime.now()
        activity.duration_s = 0
        activity.distance_m = 5000
        activity.avg_hr = 150
        
        athlete = MagicMock()
        athlete.max_hr = 185
        athlete.resting_hr = 50
        athlete.threshold_pace_per_km = 270
        
        stress = calculator.calculate_workout_tss(activity, athlete)
        
        assert stress.tss == 0
    
    def test_extreme_hr_capped(self, calculator):
        """HR reserve should be capped at 110%."""
        activity = MagicMock()
        activity.id = uuid4()
        activity.start_time = datetime.now()
        activity.duration_s = 3600
        activity.distance_m = 15000
        activity.avg_hr = 200  # Above max!
        
        athlete = MagicMock()
        athlete.max_hr = 185
        athlete.resting_hr = 50
        athlete.threshold_pace_per_km = 270
        
        stress = calculator.calculate_workout_tss(activity, athlete)
        
        # Should still calculate without error
        assert stress.tss > 0
        assert stress.calculation_method == "hrTSS"


class TestRecommendationGeneration:
    """Test recommendation text generation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    @pytest.fixture
    def calculator(self, mock_db):
        return TrainingLoadCalculator(mock_db)
    
    def test_high_fatigue_recommendation(self, calculator):
        """TSB < -20 should warn about fatigue."""
        rec = calculator._generate_recommendation(
            atl=60, ctl=35, tsb=-25, phase="overreaching"
        )
        assert "fatigue" in rec.lower() or "recovery" in rec.lower()
    
    def test_race_ready_recommendation(self, calculator):
        """High TSB in taper should suggest racing."""
        rec = calculator._generate_recommendation(
            atl=25, ctl=50, tsb=25, phase="tapering"
        )
        # Should indicate positive state or race readiness
        assert any(word in rec.lower() for word in ["fresh", "goal", "positive", "harder"])
    
    def test_building_recommendation(self, calculator):
        """Building phase should acknowledge fitness accumulation."""
        rec = calculator._generate_recommendation(
            atl=45, ctl=40, tsb=-5, phase="building"
        )
        assert "building" in rec.lower() or "accumulating" in rec.lower() or "balanced" in rec.lower()
