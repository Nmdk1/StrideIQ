"""
Unit tests for Workout Classification Service

Tests the keyword-based and data-based classification logic,
including false positive prevention.
"""

import pytest
from services.workout_classifier import (
    _matches_keyword,
    _has_negation_context,
    WorkoutClassifierService,
    WorkoutType,
    WorkoutZone
)
from unittest.mock import MagicMock
from datetime import datetime
from decimal import Decimal


class TestKeywordMatching:
    """Test keyword matching helper functions."""
    
    def test_matches_keyword_exact_word(self):
        """Test that single words match at word boundaries."""
        assert _matches_keyword('interval', 'interval training') == True
        assert _matches_keyword('interval', '5x1mi intervals') == True
        assert _matches_keyword('tempo', 'tempo run') == True
    
    def test_matches_keyword_rejects_partial(self):
        """Test that partial word matches are rejected."""
        # 'interval' should NOT match in 'intervalometer'
        assert _matches_keyword('interval', 'intervalometer') == False
        # 'tempo' should NOT match in 'contemporary'
        assert _matches_keyword('tempo', 'contemporary') == False
    
    def test_matches_keyword_multi_word(self):
        """Test that multi-word keywords use substring matching."""
        assert _matches_keyword('track workout', 'track workout today') == True
        assert _matches_keyword('speed work', 'did some speed work') == True
        assert _matches_keyword('long run', 'my long run today') == True
    
    def test_negation_context_skipped(self):
        """Test detection of negated context - skipped."""
        assert _has_negation_context('intervals', 'skipped intervals today') == True
        assert _has_negation_context('tempo', 'skipped tempo run') == True
    
    def test_negation_context_cancelled(self):
        """Test detection of negated context - cancelled."""
        assert _has_negation_context('workout', 'cancelled workout') == True
        assert _has_negation_context('track', 'cancelled track session') == True
    
    def test_negation_context_no_negation(self):
        """Test that normal usage is not detected as negation."""
        assert _has_negation_context('intervals', '5x1mi intervals') == False
        assert _has_negation_context('tempo', 'tempo run at lake') == False
        assert _has_negation_context('workout', 'great workout today') == False
    
    def test_negation_context_missed(self):
        """Test detection of missed/didn't do patterns."""
        assert _has_negation_context('tempo', 'missed tempo run') == True
        assert _has_negation_context('intervals', "didn't do intervals") == True
    
    def test_negation_context_instead_of(self):
        """Test detection of 'instead of' negation."""
        assert _has_negation_context('tempo', 'easy run instead of tempo') == True


class TestWorkoutClassifierFromName:
    """Test name-based classification."""
    
    @pytest.fixture
    def classifier(self):
        """Create classifier instance with mock db."""
        return WorkoutClassifierService(MagicMock())
    
    def _mock_activity(self, name: str, duration_s: int = 3600, distance_m: int = 10000):
        """Create a mock activity with given name."""
        activity = MagicMock()
        activity.name = name
        activity.duration_s = duration_s
        activity.distance_m = distance_m
        activity.avg_hr = 150
        activity.max_hr = 170
        activity.average_speed = Decimal('2.78')
        activity.athlete_id = 'test-athlete-id'
        activity.start_time = datetime.now()
        activity.total_elevation_gain = 100
        # Ensure not classified as race
        activity.is_race_candidate = False
        activity.user_verified_race = False
        # Mock splits for interval detection
        activity.splits = []
        return activity
    
    def _mock_athlete_thresholds(self):
        """Create mock athlete thresholds for classification."""
        from services.workout_classifier import AthleteThresholds
        return AthleteThresholds(
            max_hr=190,
            resting_hr=50,
            threshold_hr=165,
            threshold_pace_per_km=270.0,  # 4:30/km
            vdot=50.0,
            marathon_pace_per_km=300.0,  # 5:00/km
            easy_pace_per_km=360.0  # 6:00/km
        )
    
    def test_intervals_positive_match(self, classifier):
        """Test that real interval workouts are classified correctly."""
        activity = self._mock_activity('5x1mi intervals')
        classification = classifier.classify_activity(activity, self._mock_athlete_thresholds())
        
        assert classification.workout_type == WorkoutType.VO2MAX_INTERVALS
        assert classification.workout_zone == WorkoutZone.SPEED
    
    def test_intervals_false_positive_skipped(self, classifier):
        """Test that 'skipped intervals' is NOT classified as intervals."""
        activity = self._mock_activity('skipped intervals - easy run instead')
        classification = classifier.classify_activity(activity, self._mock_athlete_thresholds())
        
        # Should NOT be classified as intervals
        assert classification.workout_type != WorkoutType.VO2MAX_INTERVALS
    
    def test_tempo_positive_match(self, classifier):
        """Test that tempo runs are classified correctly."""
        activity = self._mock_activity('Tempo run 35 minutes')
        classification = classifier.classify_activity(activity, self._mock_athlete_thresholds())
        
        assert classification.workout_type == WorkoutType.THRESHOLD_RUN
        assert classification.workout_zone == WorkoutZone.STAMINA
    
    def test_tempo_false_positive_cancelled(self, classifier):
        """Test that 'cancelled tempo' is NOT classified as tempo."""
        activity = self._mock_activity('cancelled tempo - just easy miles')
        classification = classifier.classify_activity(activity, self._mock_athlete_thresholds())
        
        # Should NOT be classified as threshold
        assert classification.workout_type != WorkoutType.THRESHOLD_RUN
    
    def test_recovery_positive_match(self, classifier):
        """Test that recovery runs are classified correctly."""
        activity = self._mock_activity('Recovery run', duration_s=1800, distance_m=5000)
        classification = classifier.classify_activity(activity, self._mock_athlete_thresholds())
        
        assert classification.workout_type == WorkoutType.EASY_RUN
        assert classification.workout_zone == WorkoutZone.ENDURANCE
    
    def test_track_workout_positive_match(self, classifier):
        """Test that track workouts are classified correctly."""
        activity = self._mock_activity('Track workout - 6x800m')
        classification = classifier.classify_activity(activity, self._mock_athlete_thresholds())
        
        assert classification.workout_type == WorkoutType.VO2MAX_INTERVALS
    
    def test_generic_workout_not_false_positive(self, classifier):
        """Test that 'workout' alone doesn't trigger interval classification."""
        # A general "morning workout" should NOT be classified as intervals
        # This was a previous false positive
        activity = self._mock_activity('Morning workout', duration_s=3600, distance_m=10000)
        classification = classifier.classify_activity(activity, self._mock_athlete_thresholds())
        
        # Should be classified based on data, not as VO2MAX_INTERVALS from 'workout' keyword
        assert classification.workout_type != WorkoutType.VO2MAX_INTERVALS or \
               'interval' not in classification.reasoning.lower()
