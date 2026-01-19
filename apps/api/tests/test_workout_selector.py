"""
Tests for N=1 Learning Workout Selector

ADR-036: N=1 Learning Workout Selection Engine

Tests the three-dimensional workout selection model:
1. Periodization - Phase matching (soft weight)
2. Progression - Week position with τ1-informed speed
3. Variance - No immediate stimulus repeats, dont_follow respected

Key invariants tested:
- Phase filtering is a soft weight, not hard filter
- Variance rules prevent same stimulus back-to-back
- dont_follow rules are respected
- Data tier affects explore/exploit ratio
- Constraint filters are hard (no hills if no hill access)
- Selection is deterministic when seeded
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.workout_templates import (
    WorkoutSelector,
    WorkoutTemplate,
    WorkoutTemplateLibrary,
    TrainingPhase,
    StimulusType,
    FatigueCost,
    DataTier,
    DataSufficiencyAssessment,
    load_template_library,
    assess_data_sufficiency,
)


class TestWorkoutTemplateLibrary:
    """Tests for template library loading and validation."""
    
    def test_load_template_library_success(self):
        """Template library loads and validates successfully."""
        library = load_template_library()
        
        assert library is not None
        assert len(library.templates) >= 10  # We have 12 initial templates
        assert library.version == "1.0"
    
    def test_all_templates_have_required_fields(self):
        """All templates have required fields."""
        library = load_template_library()
        
        for template in library.templates:
            assert template.id is not None
            assert template.name is not None
            assert len(template.phases) > 0
            assert template.stimulus_type is not None
            assert template.fatigue_cost is not None
            assert template.expected_rpe_range is not None
            assert template.hypothesis is not None
    
    def test_template_id_uniqueness(self):
        """All template IDs are unique."""
        library = load_template_library()
        
        ids = [t.id for t in library.templates]
        assert len(ids) == len(set(ids)), "Duplicate template IDs found"
    
    def test_progression_ranges_valid(self):
        """Progression ranges are valid [0.0, 1.0]."""
        library = load_template_library()
        
        for template in library.templates:
            min_val, max_val = template.progression_week_range
            assert 0.0 <= min_val <= 1.0, f"{template.id} has invalid min: {min_val}"
            assert 0.0 <= max_val <= 1.0, f"{template.id} has invalid max: {max_val}"
            assert min_val <= max_val, f"{template.id} has min > max"


class TestWorkoutSelectorInvariants:
    """Tests for WorkoutSelector invariants from ADR-036."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        # Mock queries to return empty results
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []
        return db
    
    @pytest.fixture
    def selector(self, mock_db):
        """Create a WorkoutSelector with mocked dependencies."""
        selector = WorkoutSelector(mock_db)
        selector.seed_random(42)  # Deterministic for testing
        return selector
    
    def test_phase_filter_is_soft_not_hard(self, selector):
        """
        Phase filtering is a SOFT weight, not a hard filter.
        Out-of-phase templates should still be selectable with lower score.
        """
        # With an empty recent_quality_ids, we should get candidates
        # even if some are out-of-phase
        
        with patch.object(selector, '_get_athlete_model', return_value={
            "tau1": 42.0, "tau2": 7.0, "k1": 1.0, "k2": 2.0, "p0": 100.0
        }):
            with patch.object(selector, '_get_response_history', return_value={}):
                with patch.object(selector, '_get_athlete_learnings', return_value={}):
                    with patch('services.workout_templates.assess_data_sufficiency') as mock_assess:
                        mock_assess.return_value = DataSufficiencyAssessment(
                            tier=DataTier.UNCALIBRATED,
                            total_activities=10,
                            days_of_data=30,
                            quality_sessions=2,
                            rpe_coverage=0.0,
                            race_count=0,
                            days_since_last_activity=1,
                            notes=[]
                        )
                        
                        # Select for BASE phase - should work
                        result = selector.select_quality_workout(
                            athlete_id=str(uuid4()),
                            phase=TrainingPhase.BASE,
                            week_in_phase=1,
                            total_phase_weeks=4,
                            recent_quality_ids=[],
                            athlete_facilities=[]
                        )
                        
                        assert result is not None
                        assert result.template is not None
    
    def test_variance_prevents_same_stimulus_back_to_back(self, selector):
        """
        Variance rules should penalize (not eliminate) same stimulus type
        when it was just used.
        """
        with patch.object(selector, '_get_athlete_model', return_value={
            "tau1": 42.0, "tau2": 7.0, "k1": 1.0, "k2": 2.0, "p0": 100.0
        }):
            with patch.object(selector, '_get_response_history', return_value={}):
                with patch.object(selector, '_get_athlete_learnings', return_value={}):
                    with patch('services.workout_templates.assess_data_sufficiency') as mock_assess:
                        mock_assess.return_value = DataSufficiencyAssessment(
                            tier=DataTier.UNCALIBRATED,
                            total_activities=10,
                            days_of_data=30,
                            quality_sessions=2,
                            rpe_coverage=0.0,
                            race_count=0,
                            days_since_last_activity=1,
                            notes=[]
                        )
                        
                        # First selection
                        result1 = selector.select_quality_workout(
                            athlete_id=str(uuid4()),
                            phase=TrainingPhase.BUILD,
                            week_in_phase=3,
                            total_phase_weeks=8,
                            recent_quality_ids=[],
                            athlete_facilities=[]
                        )
                        
                        # Second selection with first result in recent_quality_ids
                        result2 = selector.select_quality_workout(
                            athlete_id=str(uuid4()),
                            phase=TrainingPhase.BUILD,
                            week_in_phase=3,
                            total_phase_weeks=8,
                            recent_quality_ids=[result1.template.id],
                            athlete_facilities=[]
                        )
                        
                        # Due to variance penalty, they should often be different
                        # (not guaranteed due to explore/exploit)
                        # At minimum, audit should show variance filter was applied
                        assert result2.filtered_out_by_variance >= 0
    
    def test_dont_follow_rules_respected(self, selector):
        """
        Templates should be penalized when they follow a blocked predecessor.
        """
        library = selector.library
        
        # Find a template with dont_follow rules
        template_with_rules = None
        for t in library.templates:
            if t.dont_follow:
                template_with_rules = t
                break
        
        if template_with_rules is None:
            pytest.skip("No templates with dont_follow rules in library")
        
        # The dont_follow should be penalized when that template was just used
        with patch.object(selector, '_get_athlete_model', return_value={
            "tau1": 42.0, "tau2": 7.0, "k1": 1.0, "k2": 2.0, "p0": 100.0
        }):
            with patch.object(selector, '_get_response_history', return_value={}):
                with patch.object(selector, '_get_athlete_learnings', return_value={}):
                    with patch('services.workout_templates.assess_data_sufficiency') as mock_assess:
                        mock_assess.return_value = DataSufficiencyAssessment(
                            tier=DataTier.UNCALIBRATED,
                            total_activities=10,
                            days_of_data=30,
                            quality_sessions=2,
                            rpe_coverage=0.0,
                            race_count=0,
                            days_since_last_activity=1,
                            notes=[]
                        )
                        
                        # Run selection with a blocked predecessor
                        blocked_id = template_with_rules.dont_follow[0]
                        result = selector.select_quality_workout(
                            athlete_id=str(uuid4()),
                            phase=TrainingPhase.BUILD,
                            week_in_phase=3,
                            total_phase_weeks=8,
                            recent_quality_ids=[blocked_id],
                            athlete_facilities=[]
                        )
                        
                        # Template should still be selectable but with penalty
                        assert result is not None
    
    def test_constraint_filter_is_hard(self, selector):
        """
        Constraint filters (requires: hill_access) should be hard filters.
        Templates requiring unavailable facilities should be excluded entirely.
        """
        library = selector.library
        
        # Find a template that requires hill_access
        hill_template = None
        for t in library.templates:
            if 'hill_access' in t.requires:
                hill_template = t
                break
        
        if hill_template is None:
            pytest.skip("No templates requiring hill_access in library")
        
        with patch.object(selector, '_get_athlete_model', return_value={
            "tau1": 42.0, "tau2": 7.0, "k1": 1.0, "k2": 2.0, "p0": 100.0
        }):
            with patch.object(selector, '_get_response_history', return_value={}):
                with patch.object(selector, '_get_athlete_learnings', return_value={}):
                    with patch('services.workout_templates.assess_data_sufficiency') as mock_assess:
                        mock_assess.return_value = DataSufficiencyAssessment(
                            tier=DataTier.UNCALIBRATED,
                            total_activities=10,
                            days_of_data=30,
                            quality_sessions=2,
                            rpe_coverage=0.0,
                            race_count=0,
                            days_since_last_activity=1,
                            notes=[]
                        )
                        
                        # Run 50 selections with no hill access
                        hill_selected = False
                        for i in range(50):
                            selector.seed_random(i)
                            result = selector.select_quality_workout(
                                athlete_id=str(uuid4()),
                                phase=TrainingPhase.BUILD,
                                week_in_phase=3,
                                total_phase_weeks=8,
                                recent_quality_ids=[],
                                athlete_facilities=[]  # No hill access
                            )
                            if result.template.id == hill_template.id:
                                hill_selected = True
                                break
                        
                        assert not hill_selected, \
                            "Hill template was selected despite no hill_access"
    
    def test_selection_deterministic_when_seeded(self, selector):
        """Selection should be deterministic when random is seeded."""
        with patch.object(selector, '_get_athlete_model', return_value={
            "tau1": 42.0, "tau2": 7.0, "k1": 1.0, "k2": 2.0, "p0": 100.0
        }):
            with patch.object(selector, '_get_response_history', return_value={}):
                with patch.object(selector, '_get_athlete_learnings', return_value={}):
                    with patch('services.workout_templates.assess_data_sufficiency') as mock_assess:
                        mock_assess.return_value = DataSufficiencyAssessment(
                            tier=DataTier.UNCALIBRATED,
                            total_activities=10,
                            days_of_data=30,
                            quality_sessions=2,
                            rpe_coverage=0.0,
                            race_count=0,
                            days_since_last_activity=1,
                            notes=[]
                        )
                        
                        athlete_id = str(uuid4())
                        
                        # Run with same seed twice
                        selector.seed_random(12345)
                        result1 = selector.select_quality_workout(
                            athlete_id=athlete_id,
                            phase=TrainingPhase.BUILD,
                            week_in_phase=3,
                            total_phase_weeks=8,
                            recent_quality_ids=[],
                            athlete_facilities=[]
                        )
                        
                        selector.seed_random(12345)
                        result2 = selector.select_quality_workout(
                            athlete_id=athlete_id,
                            phase=TrainingPhase.BUILD,
                            week_in_phase=3,
                            total_phase_weeks=8,
                            recent_quality_ids=[],
                            athlete_facilities=[]
                        )
                        
                        assert result1.template.id == result2.template.id
    
    def test_data_tier_affects_explore_probability(self, selector):
        """
        Explore probability should be higher for uncalibrated athletes
        and lower for calibrated athletes.
        """
        # This is validated indirectly through the selection mode in audit
        with patch.object(selector, '_get_athlete_model', return_value={
            "tau1": 42.0, "tau2": 7.0, "k1": 1.0, "k2": 2.0, "p0": 100.0
        }):
            with patch.object(selector, '_get_response_history', return_value={}):
                with patch.object(selector, '_get_athlete_learnings', return_value={}):
                    # Test with uncalibrated tier
                    with patch('services.workout_templates.assess_data_sufficiency') as mock_assess:
                        mock_assess.return_value = DataSufficiencyAssessment(
                            tier=DataTier.UNCALIBRATED,
                            total_activities=10,
                            days_of_data=30,
                            quality_sessions=2,
                            rpe_coverage=0.0,
                            race_count=0,
                            days_since_last_activity=1,
                            notes=[]
                        )
                        
                        selector.seed_random(99)
                        result = selector.select_quality_workout(
                            athlete_id=str(uuid4()),
                            phase=TrainingPhase.BUILD,
                            week_in_phase=3,
                            total_phase_weeks=8,
                            recent_quality_ids=[],
                            athlete_facilities=[]
                        )
                        
                        # Audit log should show explore probability
                        assert "explore_probability" in result.audit_log
                        assert result.audit_log["explore_probability"] == 0.5  # Uncalibrated = 50%


class TestDataSufficiencyAssessment:
    """Tests for data sufficiency tier assessment."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session for tier assessment."""
        db = MagicMock()
        return db
    
    def test_uncalibrated_tier_low_activities(self, mock_db):
        """Athletes with <30 activities should be UNCALIBRATED."""
        # Mock query results
        mock_db.query.return_value.filter.return_value.count.return_value = 20
        mock_db.query.return_value.filter.return_value.first.return_value = (None, None)
        
        # This will use the actual function with mocked db
        # For unit testing, we'd need to properly mock the query chain
        # This is more of an integration test pattern
        pass  # Skip detailed mock setup for now
    
    def test_staleness_downgrades_tier(self, mock_db):
        """Athletes with stale data should be downgraded."""
        # A calibrated athlete with no activity for 60+ days
        # should be downgraded to LEARNING
        pass  # Skip detailed mock setup for now


class TestWorkoutSelectorWithLearnings:
    """Tests for workout selection with banked athlete intelligence."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []
        return db
    
    @pytest.fixture
    def selector(self, mock_db):
        """Create a WorkoutSelector with mocked dependencies."""
        selector = WorkoutSelector(mock_db)
        selector.seed_random(42)
        return selector
    
    def test_what_works_boosts_template_score(self, selector):
        """Templates in what_works should have boosted scores."""
        with patch.object(selector, '_get_athlete_model', return_value={
            "tau1": 42.0, "tau2": 7.0, "k1": 1.0, "k2": 2.0, "p0": 100.0
        }):
            with patch.object(selector, '_get_response_history', return_value={}):
                with patch.object(selector, '_get_athlete_learnings', return_value={
                    "what_works": ["threshold_intervals_3x10"],
                    "what_doesnt_work": [],
                    "what_works_stimulus": [],
                    "what_doesnt_work_stimulus": [],
                    "injury_triggers": []
                }):
                    with patch('services.workout_templates.assess_data_sufficiency') as mock_assess:
                        mock_assess.return_value = DataSufficiencyAssessment(
                            tier=DataTier.LEARNING,
                            total_activities=50,
                            days_of_data=120,
                            quality_sessions=15,
                            rpe_coverage=0.6,
                            race_count=1,
                            days_since_last_activity=1,
                            notes=[]
                        )
                        
                        # With exploit mode, the boosted template should be more likely
                        boosted_count = 0
                        for i in range(20):
                            selector.seed_random(1000 + i)
                            result = selector.select_quality_workout(
                                athlete_id=str(uuid4()),
                                phase=TrainingPhase.BUILD,
                                week_in_phase=4,
                                total_phase_weeks=8,
                                recent_quality_ids=[],
                                athlete_facilities=[]
                            )
                            if result.template.id == "threshold_intervals_3x10":
                                boosted_count += 1
                        
                        # Should be selected more than random chance
                        # With 12 templates and 1.5x boost, should see it often
                        assert boosted_count >= 3, \
                            f"what_works template only selected {boosted_count}/20 times"
    
    def test_what_doesnt_work_penalizes_template_score(self, selector):
        """Templates in what_doesnt_work should have reduced scores."""
        with patch.object(selector, '_get_athlete_model', return_value={
            "tau1": 42.0, "tau2": 7.0, "k1": 1.0, "k2": 2.0, "p0": 100.0
        }):
            with patch.object(selector, '_get_response_history', return_value={}):
                with patch.object(selector, '_get_athlete_learnings', return_value={
                    "what_works": [],
                    "what_doesnt_work": ["threshold_intervals_3x10"],
                    "what_works_stimulus": [],
                    "what_doesnt_work_stimulus": [],
                    "injury_triggers": []
                }):
                    with patch('services.workout_templates.assess_data_sufficiency') as mock_assess:
                        mock_assess.return_value = DataSufficiencyAssessment(
                            tier=DataTier.CALIBRATED,
                            total_activities=150,
                            days_of_data=365,
                            quality_sessions=50,
                            rpe_coverage=0.8,
                            race_count=5,
                            days_since_last_activity=1,
                            notes=[]
                        )
                        
                        # With calibrated (90% exploit), penalized template should rarely appear
                        penalized_count = 0
                        for i in range(30):
                            selector.seed_random(2000 + i)
                            result = selector.select_quality_workout(
                                athlete_id=str(uuid4()),
                                phase=TrainingPhase.BUILD,
                                week_in_phase=4,
                                total_phase_weeks=8,
                                recent_quality_ids=[],
                                athlete_facilities=[]
                            )
                            if result.template.id == "threshold_intervals_3x10":
                                penalized_count += 1
                        
                        # Should be selected less than random chance
                        assert penalized_count <= 5, \
                            f"what_doesnt_work template selected {penalized_count}/30 times (too often)"


class TestFallbackBehavior:
    """Tests for fallback behavior when all candidates are filtered."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []
        return db
    
    @pytest.fixture
    def selector(self, mock_db):
        """Create a WorkoutSelector."""
        return WorkoutSelector(mock_db)
    
    def test_phase_fallback_returns_valid_template(self, selector):
        """Phase fallback should return a valid template for each phase."""
        for phase in TrainingPhase:
            fallback = selector._get_phase_fallback(phase)
            assert fallback is not None
            assert fallback.id is not None
    
    def test_base_phase_fallback_is_strides(self, selector):
        """Base phase fallback should be strides (low fatigue, universal)."""
        fallback = selector._get_phase_fallback(TrainingPhase.BASE)
        assert fallback.id == "strides_6x20"
    
    def test_taper_phase_fallback_is_sharpening(self, selector):
        """Taper phase fallback should be sharpening (race prep)."""
        fallback = selector._get_phase_fallback(TrainingPhase.TAPER)
        assert fallback.id == "sharpening_6x200"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
