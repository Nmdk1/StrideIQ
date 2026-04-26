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
            rpi=50.0,
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


class TestStructuredIntervalNameParsing:
    """REGRESSION GUARD: structured intervals named 'N x DISTANCE' or
    'N x DURATION' must classify by SEGMENT shape, not as fartlek.

    The founder's actual workout names from a real beta-tester screenshot
    were getting dumped into FARTLEK because:
      1. The keyword list didn't recognize 'N x DIST' patterns at all.
      2. The structural classifier bucketed by overall avg intensity,
         which is wrecked by warmup + recoveries + cooldown.

    Both paths must be defended -- if either silently regresses, athletes
    once again can't trust the system to know what kind of workout they
    just did, and the Compare tab compounds that distrust by grouping
    on the wrong workout_type."""

    @pytest.fixture
    def classifier(self):
        return WorkoutClassifierService(MagicMock())

    def _mock_activity(self, name: str, duration_s: int = 4185, distance_m: int = 12700):
        """Defaults match the founder's '3 mile wu, 16 x 400 w 90 sec rest'
        run from the screenshot (7.89 mi in 1:09:45)."""
        activity = MagicMock()
        activity.name = name
        activity.duration_s = duration_s
        activity.distance_m = distance_m
        activity.avg_hr = 133
        activity.max_hr = 175
        activity.average_speed = Decimal("3.03")
        activity.athlete_id = "test-athlete-id"
        activity.start_time = datetime.now()
        activity.total_elevation_gain = 50
        activity.is_race_candidate = False
        activity.user_verified_race = False
        activity.splits = []
        return activity

    def _thresholds(self):
        from services.workout_classifier import AthleteThresholds
        return AthleteThresholds(
            max_hr=180,
            resting_hr=50,
            threshold_hr=160,
            threshold_pace_per_km=270.0,
            rpi=50.0,
            marathon_pace_per_km=300.0,
            easy_pace_per_km=360.0,
        )

    def test_short_metric_repeats_classify_as_vo2max_not_fartlek(self, classifier):
        """'3 mile wu, 16 x 400 w 90 sec rest' is the textbook shape of a
        VO2max session.  Before the fix this was being classified as
        FARTLEK because overall avg HR (133) and avg pace (8:51/mi) sit in
        moderate territory.  The name tells us the structure -- listen to it."""
        a = self._mock_activity("3 mile wu, 16 x 400 w 90 sec rest")
        c = classifier.classify_activity(a, self._thresholds())
        assert c.workout_type == WorkoutType.VO2MAX_INTERVALS, c.reasoning
        assert c.workout_type != WorkoutType.FARTLEK
        assert c.detected_intervals is True

    def test_minute_based_threshold_intervals_not_fartlek(self, classifier):
        """'Lauderdale County - 6 x 5 minutes' is a classic cruise-interval
        workout.  Five-minute work bouts at threshold pace, jog recoveries.
        Pre-fix this was FARTLEK; post-fix it must be CRUISE_INTERVALS."""
        a = self._mock_activity("Lauderdale County - 6 x 5 minutes")
        c = classifier.classify_activity(a, self._thresholds())
        assert c.workout_type == WorkoutType.CRUISE_INTERVALS, c.reasoning
        assert c.workout_type != WorkoutType.FARTLEK

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("8 x 400m repeats", WorkoutType.VO2MAX_INTERVALS),
            ("12 x 200 strides on track", WorkoutType.VO2MAX_INTERVALS),
            ("6x800m at 5k pace", WorkoutType.VO2MAX_INTERVALS),
            ("4 x 1000 with 2 min jog", WorkoutType.VO2MAX_INTERVALS),
            ("3 x 1600m hard", WorkoutType.VO2MAX_INTERVALS),
            ("4 x 1 mile hard", WorkoutType.VO2MAX_INTERVALS),
            # Explicit threshold/cruise keywords correctly win precedence
            # and route to CRUISE_INTERVALS regardless of segment shape.
            ("3 x 2 mile threshold", WorkoutType.CRUISE_INTERVALS),
            ("4 x 1 mile cruise", WorkoutType.CRUISE_INTERVALS),
            ("8 x 30 sec hill sprints", WorkoutType.VO2MAX_INTERVALS),
            ("10 x 1 minute hard", WorkoutType.VO2MAX_INTERVALS),
            ("4 x 8 min at LT", WorkoutType.CRUISE_INTERVALS),
            ("3 x 15 min hard blocks", WorkoutType.THRESHOLD_RUN),
        ],
    )
    def test_structured_interval_patterns_classify_by_shape(
        self, classifier, name, expected
    ):
        a = self._mock_activity(name)
        c = classifier.classify_activity(a, self._thresholds())
        assert c.workout_type == expected, (
            f"name='{name}' expected {expected.value} got "
            f"{c.workout_type.value} -- reasoning: {c.reasoning}"
        )
        assert c.workout_type != WorkoutType.FARTLEK

    def test_random_phrases_with_x_do_not_falsely_match(self, classifier):
        """The 'N x DIST' regex must not fire on dates, times, or unrelated
        phrases that happen to contain a digit-x-digit substring."""
        from services.workout_classifier import _parse_structured_interval

        for benign in [
            "easy run on March 5",
            "ran past mile 4",
            "5k race",
            "9 mile easy",
        ]:
            assert _parse_structured_interval(benign) is None, benign


class TestStructuralIntervalBucketing:
    """REGRESSION GUARD: when intervals are detected from splits but the
    name gives no structure, the classifier must STILL prefer segment
    shape over diluted overall intensity.  This is the second half of
    the fix -- without it, every athlete who imports a Garmin workout
    with a generic name would still get FARTLEK on 16 x 400 because the
    avg intensity sits below the old > 70 cutoff."""

    @pytest.fixture
    def classifier(self):
        return WorkoutClassifierService(MagicMock())

    def _activity(self):
        a = MagicMock()
        a.name = "Run Activity"
        a.duration_s = 4000
        a.distance_m = 12000
        a.avg_hr = 140
        a.max_hr = 175
        a.is_race_candidate = False
        a.user_verified_race = False
        a.splits = []
        return a

    def _thresholds(self):
        from services.workout_classifier import AthleteThresholds
        return AthleteThresholds(
            max_hr=180,
            resting_hr=50,
            threshold_hr=160,
            threshold_pace_per_km=270.0,
            rpi=50.0,
            marathon_pace_per_km=300.0,
            easy_pace_per_km=360.0,
        )

    def test_short_segments_at_moderate_overall_intensity_are_vo2max(self, classifier):
        """16 x 400m repeats: each segment is ~75 seconds.  Overall avg
        intensity is moderate because of warmup + recoveries.  The
        classifier MUST pick VO2MAX_INTERVALS from segment shape, not
        FARTLEK from the diluted average."""
        c = classifier._classify_interval_workout(
            self._activity(),
            self._thresholds(),
            hr_zone=3,
            intensity_score=60.0,
            num_intervals=16,
            avg_interval_duration=1.25,
        )
        assert c.workout_type == WorkoutType.VO2MAX_INTERVALS, c.reasoning

    def test_five_minute_segments_classify_as_cruise_intervals(self, classifier):
        """6 x 5 min at threshold: textbook cruise intervals."""
        c = classifier._classify_interval_workout(
            self._activity(),
            self._thresholds(),
            hr_zone=4,
            intensity_score=55.0,
            num_intervals=6,
            avg_interval_duration=5.0,
        )
        assert c.workout_type == WorkoutType.CRUISE_INTERVALS, c.reasoning

    def test_unstructured_low_intensity_with_no_segment_data_remains_fartlek(
        self, classifier
    ):
        """The ONLY path to FARTLEK should be: intervals detected from
        pace variance, but no usable segment structure AND moderate
        intensity.  This is true unstructured speed play."""
        c = classifier._classify_interval_workout(
            self._activity(),
            self._thresholds(),
            hr_zone=3,
            intensity_score=55.0,
            num_intervals=0,
            avg_interval_duration=0.0,
        )
        assert c.workout_type == WorkoutType.FARTLEK
