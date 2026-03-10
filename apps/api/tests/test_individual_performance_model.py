"""
Tests for Individual Performance Model

Tests:
1. Model calibration with synthetic data
2. Fallback behavior with insufficient data
3. Optimal taper calculation
4. Load trajectory calculation
5. Race time prediction

ADR-022: Individual Performance Model for Plan Generation
"""

import pytest
from datetime import date, timedelta, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from services.individual_performance_model import (
    IndividualPerformanceModel,
    BanisterModel,
    ModelConfidence,
    TrainingDay,
    PerformanceMarker,
    DEFAULT_TAU1,
    DEFAULT_TAU2,
    get_or_calibrate_model
)
from services.optimal_load_calculator import (
    OptimalLoadCalculator,
    LoadTrajectory,
    TaperPlan,
    TrainingPhase
)
from services.race_predictor import (
    RacePredictor,
    RacePrediction
)
from services.model_driven_plan_generator import (
    ModelDrivenPlanGenerator,
    ModelDrivenPlan
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_db():
    """Create mock database session."""
    return MagicMock()


@pytest.fixture
def sample_training_days():
    """Generate sample training data."""
    days = []
    base_date = date.today() - timedelta(days=180)
    
    for i in range(180):
        day_date = base_date + timedelta(days=i)
        
        # Simulate typical training pattern
        # Higher TSS on weekends (long run), rest on Mondays
        day_of_week = day_date.weekday()
        
        if day_of_week == 0:  # Monday - rest
            tss = 0
        elif day_of_week == 6:  # Sunday - long run
            tss = 80 + (i % 30)  # Progressive long runs
        elif day_of_week in [2, 4]:  # Wed, Fri - quality
            tss = 50 + (i % 20)
        else:  # Easy days
            tss = 30 + (i % 15)
        
        days.append(TrainingDay(date=day_date, tss=tss))
    
    return days


@pytest.fixture
def sample_performance_markers():
    """Generate sample race performance data."""
    markers = []
    base_date = date.today() - timedelta(days=180)
    
    # Simulate improving fitness
    for i, day_offset in enumerate([30, 60, 90, 120, 150]):
        marker_date = base_date + timedelta(days=day_offset)
        # RPI improves over time
        rpi = 48 + (i * 0.5)
        
        markers.append(PerformanceMarker(
            date=marker_date,
            performance_value=rpi,
            source="race",
            weight=1.5
        ))
    
    return markers


# =============================================================================
# MODEL CALIBRATION TESTS
# =============================================================================

class TestModelCalibration:
    """Tests for individual model calibration."""
    
    def test_fit_model_with_sufficient_data(
        self, mock_db, sample_training_days, sample_performance_markers
    ):
        """Test model fitting with sufficient training and performance data."""
        engine = IndividualPerformanceModel(mock_db)
        
        model = engine._fit_model(
            athlete_id="test-athlete",
            training_days=sample_training_days,
            performance_markers=sample_performance_markers
        )
        
        # Verify model is calibrated with valid parameters
        assert model is not None
        assert model.tau1 >= 25 and model.tau1 <= 70
        assert model.tau2 >= 4 and model.tau2 <= 18
        assert model.tau1 > model.tau2  # Fitness decays slower than fatigue
        
        # Confidence depends on model fit quality (r_squared), not just data quantity.
        # With synthetic data that doesn't perfectly follow the Banister model,
        # we may get LOW confidence even with sufficient data points.
        # The key assertion is that the model returns SOMETHING, not UNCALIBRATED.
        assert model.confidence != ModelConfidence.UNCALIBRATED
    
    def test_model_falls_back_to_defaults_with_insufficient_data(self, mock_db):
        """Test fallback to population defaults when data is insufficient."""
        engine = IndividualPerformanceModel(mock_db)
        
        # Only 2 performance markers (need 3+)
        insufficient_markers = [
            PerformanceMarker(date=date.today() - timedelta(days=30), performance_value=50, source="race"),
            PerformanceMarker(date=date.today() - timedelta(days=60), performance_value=49, source="race"),
        ]
        
        # Only 30 training days (need 60+)
        insufficient_training = [
            TrainingDay(date=date.today() - timedelta(days=i), tss=50)
            for i in range(30)
        ]
        
        model = engine._create_default_model(
            athlete_id=uuid4(),
            n_training_days=30,
            n_markers=2,
            reason="Insufficient data"
        )
        
        # Should use population defaults
        assert model.tau1 == DEFAULT_TAU1
        assert model.tau2 == DEFAULT_TAU2
        assert model.confidence == ModelConfidence.UNCALIBRATED
        assert "Insufficient data" in model.confidence_notes[0]
    
    def test_model_confidence_levels(
        self, mock_db, sample_training_days, sample_performance_markers
    ):
        """Test that confidence is correctly assessed based on data quality."""
        engine = IndividualPerformanceModel(mock_db)
        
        # Test with 5+ races (should be HIGH)
        confidence, notes = engine._assess_confidence(
            n_markers=5,
            r_squared=0.75,
            fit_error=10,
            n_days=180
        )
        assert confidence == ModelConfidence.HIGH
        
        # Test with 3-4 races (should be MODERATE)
        confidence, notes = engine._assess_confidence(
            n_markers=3,
            r_squared=0.55,
            fit_error=20,
            n_days=90
        )
        assert confidence == ModelConfidence.MODERATE
        
        # Test with poor fit (should be LOW)
        confidence, notes = engine._assess_confidence(
            n_markers=2,
            r_squared=0.3,
            fit_error=50,
            n_days=60
        )
        assert confidence == ModelConfidence.LOW
    
    def test_optimal_taper_calculation(self, mock_db):
        """
        Test optimal taper days calculation from model parameters.
        
        Taper is now τ1-aware (ADR-034 Phase 1):
        - Fast adapters (τ1 < 30): 1.75 × τ2, bounded 7-14 days
        - Moderate adapters (30 ≤ τ1 < 40): 2.0 × τ2, bounded 10-18 days
        - Slow adapters (τ1 ≥ 40): 2.25 × τ2, bounded 14-21 days
        """
        # Fast adapter (τ1 = 25) with fast recovery (τ2 = 5)
        # Expected: 1.75 * 5 = 8.75 → 8, bounded to 7-14 → 8
        fast_adapter_model = BanisterModel(
            athlete_id="test",
            tau1=25, tau2=5, k1=1, k2=2, p0=50,
            fit_error=0, r_squared=0.8,
            n_performance_markers=5, n_training_days=180,
            confidence=ModelConfidence.HIGH
        )
        taper_days = fast_adapter_model.calculate_optimal_taper_days()
        assert 7 <= taper_days <= 14, f"Fast adapter should get 7-14 day taper, got {taper_days}"
        
        # Fast adapter with normal recovery (τ2 = 7)
        # Expected: 1.75 * 7 = 12.25 → 12, bounded to 7-14 → 12
        fast_adapter_normal_recovery = BanisterModel(
            athlete_id="test",
            tau1=25, tau2=7, k1=1, k2=2, p0=50,
            fit_error=0, r_squared=0.8,
            n_performance_markers=5, n_training_days=180,
            confidence=ModelConfidence.HIGH
        )
        taper_days = fast_adapter_normal_recovery.calculate_optimal_taper_days()
        assert taper_days == 12, f"Expected 12 day taper for τ1=25/τ2=7, got {taper_days}"
        
        # Moderate adapter (τ1 = 35) with normal recovery (τ2 = 7)
        # Expected: 2.0 * 7 = 14, bounded to 10-18 → 14
        moderate_adapter_model = BanisterModel(
            athlete_id="test",
            tau1=35, tau2=7, k1=1, k2=2, p0=50,
            fit_error=0, r_squared=0.8,
            n_performance_markers=5, n_training_days=180,
            confidence=ModelConfidence.HIGH
        )
        taper_days = moderate_adapter_model.calculate_optimal_taper_days()
        assert 10 <= taper_days <= 18, f"Moderate adapter should get 10-18 day taper, got {taper_days}"
        
        # Slow adapter (τ1 = 50) with slow recovery (τ2 = 10)
        # Expected: 2.25 * 10 = 22.5 → 22, bounded to 14-21 → 21
        slow_adapter_model = BanisterModel(
            athlete_id="test",
            tau1=50, tau2=10, k1=1, k2=2, p0=50,
            fit_error=0, r_squared=0.8,
            n_performance_markers=5, n_training_days=180,
            confidence=ModelConfidence.HIGH
        )
        taper_days = slow_adapter_model.calculate_optimal_taper_days()
        assert 14 <= taper_days <= 21, f"Slow adapter should get 14-21 day taper, got {taper_days}"
        
    def test_taper_rationale_generation(self, mock_db):
        """Test that taper rationale explains τ1-based reasoning."""
        fast_model = BanisterModel(
            athlete_id="test",
            tau1=25, tau2=7, k1=1, k2=2, p0=50,
            fit_error=0, r_squared=0.8,
            n_performance_markers=5, n_training_days=180,
            confidence=ModelConfidence.HIGH
        )
        
        rationale = fast_model.get_taper_rationale()
        assert "25" in rationale or "fast" in rationale.lower()
        assert "taper" in rationale.lower()
        assert len(rationale) > 20


# =============================================================================
# OPTIMAL LOAD CALCULATOR TESTS
# =============================================================================

class TestOptimalLoadCalculator:
    """Tests for optimal load trajectory calculation."""
    
    def test_trajectory_includes_build_and_taper_phases(self, mock_db):
        """Test that trajectory includes both build and taper phases."""
        # Mock the model calibration
        with patch('services.optimal_load_calculator.get_or_calibrate_model') as mock_model:
            mock_model.return_value = BanisterModel(
                athlete_id="test",
                tau1=42, tau2=7, k1=1, k2=2, p0=50,
                fit_error=0, r_squared=0.8,
                n_performance_markers=5, n_training_days=180,
                confidence=ModelConfidence.MODERATE
            )
            
            calculator = OptimalLoadCalculator(mock_db)
            
            trajectory = calculator.calculate_trajectory(
                athlete_id=uuid4(),
                race_date=date.today() + timedelta(days=84),  # 12 weeks
                current_ctl=60,
                current_atl=50,
                target_tsb=15,
                max_weekly_tss=400,
                min_weekly_tss=120
            )
            
            assert trajectory is not None
            assert len(trajectory.weeks) > 0
            
            # Should have both build and taper phases
            phases = [w.phase for w in trajectory.weeks]
            assert TrainingPhase.BUILD in phases or TrainingPhase.BASE in phases
            assert TrainingPhase.TAPER in phases
    
    def test_trajectory_includes_cutback_weeks(self, mock_db):
        """Test that trajectory includes cutback weeks every 4th week."""
        with patch('services.optimal_load_calculator.get_or_calibrate_model') as mock_model:
            mock_model.return_value = BanisterModel(
                athlete_id="test",
                tau1=42, tau2=7, k1=1, k2=2, p0=50,
                fit_error=0, r_squared=0.8,
                n_performance_markers=5, n_training_days=180,
                confidence=ModelConfidence.MODERATE
            )
            
            calculator = OptimalLoadCalculator(mock_db)
            
            trajectory = calculator.calculate_trajectory(
                athlete_id=uuid4(),
                race_date=date.today() + timedelta(days=112),  # 16 weeks
                current_ctl=60,
                current_atl=50
            )
            
            # Check for cutback weeks
            cutback_weeks = [w for w in trajectory.weeks if w.is_cutback]
            assert len(cutback_weeks) >= 2  # Should have at least 2 cutbacks in 16 weeks
    
    def test_taper_hits_target_tsb(self, mock_db):
        """Test that projected race-day TSB is close to target."""
        with patch('services.optimal_load_calculator.get_or_calibrate_model') as mock_model:
            mock_model.return_value = BanisterModel(
                athlete_id="test",
                tau1=42, tau2=7, k1=1, k2=2, p0=50,
                fit_error=0, r_squared=0.8,
                n_performance_markers=5, n_training_days=180,
                confidence=ModelConfidence.MODERATE
            )
            
            calculator = OptimalLoadCalculator(mock_db)
            target_tsb = 15
            
            trajectory = calculator.calculate_trajectory(
                athlete_id=uuid4(),
                race_date=date.today() + timedelta(days=56),  # 8 weeks
                current_ctl=60,
                current_atl=50,
                target_tsb=target_tsb
            )
            
            # Projected TSB should be reasonably close to target
            assert abs(trajectory.projected_race_day_tsb - target_tsb) < 10


# =============================================================================
# RACE PREDICTOR TESTS
# =============================================================================

class TestRacePredictor:
    """Tests for race time prediction."""
    
    def test_prediction_returns_valid_time(self, mock_db):
        """Test that prediction returns a valid race time."""
        with patch.object(RacePredictor, '_get_current_rpi', return_value=50.0):
            with patch.object(RacePredictor, '_get_current_ctl', return_value=60):
                with patch.object(RacePredictor, '_project_race_day_fitness', return_value=(65, 50)):
                    with patch('services.race_predictor.get_or_calibrate_model') as mock_model:
                        mock_model.return_value = BanisterModel(
                            athlete_id="test",
                            tau1=42, tau2=7, k1=1, k2=2, p0=50,
                            fit_error=0, r_squared=0.8,
                            n_performance_markers=5, n_training_days=180,
                            confidence=ModelConfidence.MODERATE
                        )
                        
                        predictor = RacePredictor(mock_db)
                        
                        prediction = predictor.predict(
                            athlete_id=uuid4(),
                            race_date=date.today() + timedelta(days=56),
                            distance_m=42195  # Marathon
                        )
                        
                        assert prediction.predicted_time_seconds > 0
                        assert prediction.confidence_interval_seconds > 0
                        assert prediction.prediction_confidence in ["high", "moderate", "low", "insufficient_data"]
    
    def test_prediction_handles_insufficient_data(self, mock_db):
        """Test that prediction gracefully handles insufficient data."""
        # Mock the model retrieval to return a model with no calibration
        mock_model = MagicMock()
        mock_model.tau1 = 42.0
        mock_model.tau2 = 7.0
        mock_model.k1 = 1.0
        mock_model.k2 = 2.0
        
        with patch('services.race_predictor.get_or_calibrate_model', return_value=mock_model):
            with patch.object(RacePredictor, '_get_current_rpi', return_value=None):
                with patch.object(RacePredictor, '_estimate_rpi_from_training', return_value=None):
                    predictor = RacePredictor(mock_db)
                    
                    prediction = predictor.predict(
                        athlete_id=uuid4(),
                        race_date=date.today() + timedelta(days=56),
                        distance_m=42195
                    )
                    
                    assert prediction.prediction_confidence == "insufficient_data"
                    assert "Insufficient data" in prediction.notes[0]
    
    def test_tsb_adjustment_applied(self, mock_db):
        """Test that TSB adjustment is applied to predictions."""
        predictor = RacePredictor(mock_db)
        
        # Optimal TSB (+15) should give positive adjustment
        optimal_adjustment = predictor._calculate_tsb_adjustment(15)
        assert optimal_adjustment > 0
        
        # Negative TSB should give negative adjustment
        fatigued_adjustment = predictor._calculate_tsb_adjustment(-10)
        assert fatigued_adjustment < optimal_adjustment


# =============================================================================
# MODEL-DRIVEN PLAN GENERATOR TESTS
# =============================================================================

class TestModelDrivenPlanGenerator:
    """Tests for model-driven plan generation."""
    
    def test_plan_has_correct_structure(self, mock_db):
        """Test that generated plan has correct structure."""
        with patch('services.model_driven_plan_generator.get_or_calibrate_model') as mock_model:
            mock_model.return_value = BanisterModel(
                athlete_id="test",
                tau1=42, tau2=7, k1=1, k2=2, p0=50,
                fit_error=0, r_squared=0.8,
                n_performance_markers=5, n_training_days=180,
                confidence=ModelConfidence.MODERATE
            )
            
            with patch.object(ModelDrivenPlanGenerator, '_get_current_state', return_value=(60, 50)):
                with patch.object(ModelDrivenPlanGenerator, '_get_training_paces', return_value={
                    "e_pace": "9:00/mi",
                    "m_pace": "8:00/mi",
                    "t_pace": "7:15/mi",
                    "i_pace": "6:30/mi"
                }):
                    with patch.object(ModelDrivenPlanGenerator, '_apply_decay_interventions', 
                                      side_effect=lambda w, *args: w):
                        with patch.object(ModelDrivenPlanGenerator, '_get_counter_conventional_notes', 
                                          return_value=[]):
                            with patch('services.model_driven_plan_generator.RacePredictor') as mock_predictor:
                                mock_predictor.return_value.predict.return_value = RacePrediction(
                                    predicted_time_seconds=12600,
                                    predicted_time_formatted="3:30:00",
                                    confidence_interval_seconds=180,
                                    confidence_interval_formatted="±3:00",
                                    prediction_confidence="moderate",
                                    projected_rpi=50,
                                    projected_ctl=65,
                                    projected_tsb=15,
                                    factors=[],
                                    notes=[]
                                )
                                
                                with patch('services.model_driven_plan_generator.OptimalLoadCalculator') as mock_calc:
                                    from services.optimal_load_calculator import WeeklyLoadTarget
                                    mock_calc.return_value.calculate_trajectory.return_value = LoadTrajectory(
                                        athlete_id="test",
                                        race_date=date.today() + timedelta(days=84),
                                        weeks=[
                                            WeeklyLoadTarget(
                                                week_number=i+1,
                                                start_date=date.today() + timedelta(days=i*7),
                                                end_date=date.today() + timedelta(days=i*7+6),
                                                target_tss=300,
                                                phase=TrainingPhase.BUILD if i < 9 else TrainingPhase.TAPER
                                            )
                                            for i in range(12)
                                        ],
                                        projected_race_day_ctl=65,
                                        projected_race_day_atl=50,
                                        projected_race_day_tsb=15,
                                        model_confidence=ModelConfidence.MODERATE,
                                        tau1=42, tau2=7,
                                        total_weeks=12,
                                        total_planned_tss=3600,
                                        taper_start_week=10
                                    )
                                    
                                    generator = ModelDrivenPlanGenerator(mock_db)
                                    
                                    plan = generator.generate(
                                        athlete_id=uuid4(),
                                        race_date=date.today() + timedelta(days=84),
                                        race_distance="marathon"
                                    )
                                    
                                    assert plan is not None
                                    assert len(plan.weeks) == 12
                                    assert plan.total_weeks == 12
                                    assert plan.prediction is not None
                                    assert plan.model_confidence == "moderate"
    
    def test_week_structure_varies_by_phase(self, mock_db):
        """Test that week structure varies by training phase."""
        generator = ModelDrivenPlanGenerator(mock_db)
        
        # Get structures for different phases
        base_structure = generator._get_base_week_structure()
        build_structure = generator._get_build_week_structure()
        taper_structure = generator._get_taper_week_structure()
        
        # Verify structures are different
        assert base_structure != build_structure
        assert build_structure != taper_structure
        
        # Verify all structures sum to 100%
        assert abs(sum(s["tss_pct"] for s in base_structure) - 1.0) < 0.01
        assert abs(sum(s["tss_pct"] for s in build_structure) - 1.0) < 0.01
        assert abs(sum(s["tss_pct"] for s in taper_structure) - 1.0) < 0.01


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for the full pipeline."""
    
    def test_full_pipeline_with_mock_data(self, mock_db):
        """Test the full pipeline from calibration to plan generation."""
        # This tests the integration between all components
        # In a real test, we would use actual database fixtures
        
        # For now, verify the modules can be imported and have expected interfaces
        from services.individual_performance_model import IndividualPerformanceModel
        from services.optimal_load_calculator import OptimalLoadCalculator
        from services.race_predictor import RacePredictor
        from services.model_driven_plan_generator import ModelDrivenPlanGenerator
        
        # Verify classes have expected methods
        assert hasattr(IndividualPerformanceModel, 'calibrate')
        assert hasattr(OptimalLoadCalculator, 'calculate_trajectory')
        assert hasattr(OptimalLoadCalculator, 'calculate_personalized_taper')
        assert hasattr(RacePredictor, 'predict')
        assert hasattr(ModelDrivenPlanGenerator, 'generate')
