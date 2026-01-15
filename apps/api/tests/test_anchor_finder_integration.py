"""
Integration tests for AnchorFinder (ADR-033)

These tests use REAL database fixtures to verify anchor finding logic.
No mocks - actual queries against test data.

Tests cover:
- Empty history edge cases
- Injury rebound detection
- Similar workout matching
- Efficiency outlier detection
- Milestone comparison
"""

import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4
from decimal import Decimal

from models import Activity, Athlete
from services.anchor_finder import (
    AnchorFinder,
    InjuryReboundAnchor,
    WorkoutAnchor,
    EfficiencyAnchor,
    LoadStateAnchor,
    MilestoneAnchor,
    format_date_relative,
    format_pace
)


# =============================================================================
# FIXTURES - Create realistic training data
# =============================================================================

@pytest.fixture
def athlete_with_activities(db_session, test_athlete):
    """
    Create an athlete with 3 months of realistic training data.
    
    Pattern:
    - Weeks 1-4: Normal training (50-60 mi/week)
    - Week 5-6: Injury drop (10-20 mi/week)
    - Weeks 7-10: Rebuild (30-50 mi/week)
    - Week 11-12: Back to normal
    """
    activities = []
    base_date = date.today() - timedelta(days=84)  # 12 weeks ago
    
    # Helper to create activities
    def create_run(day_offset, distance_m, duration_s, workout_type, hr=145):
        activity = Activity(
            id=uuid4(),
            athlete_id=test_athlete.id,
            provider="strava",
            external_activity_id=str(uuid4())[:10],
            sport="run",
            name=f"{workout_type.replace('_', ' ').title()} Run",
            start_time=datetime.combine(base_date + timedelta(days=day_offset), datetime.min.time()),
            distance_m=distance_m,
            duration_s=duration_s,
            average_speed=Decimal(str(distance_m / duration_s)) if duration_s > 0 else None,
            avg_hr=hr,
            max_hr=hr + 20,
            workout_type=workout_type,
            total_elevation_gain=Decimal("50")
        )
        return activity
    
    # Week 1-4: Normal training
    for week in range(4):
        week_start = week * 7
        # Easy run Mon
        activities.append(create_run(week_start, 8000, 2400, "easy", 140))
        # Threshold Tue
        activities.append(create_run(week_start + 1, 10000, 2700, "threshold", 165))
        # Easy Wed
        activities.append(create_run(week_start + 2, 8000, 2400, "easy", 138))
        # Easy Thu
        activities.append(create_run(week_start + 3, 6000, 1800, "easy", 142))
        # Rest Fri
        # Long run Sat
        activities.append(create_run(week_start + 5, 25000, 7500, "long", 145))
        # Easy Sun
        activities.append(create_run(week_start + 6, 8000, 2400, "easy", 140))
    
    # Week 5-6: Injury (sharp drop)
    for week in range(4, 6):
        week_start = week * 7
        # Only 1-2 short easy runs
        activities.append(create_run(week_start + 2, 3000, 1200, "easy", 135))
        if week == 5:
            activities.append(create_run(week_start + 5, 5000, 1800, "easy", 138))
    
    # Week 7-10: Rebuild
    for week in range(6, 10):
        week_start = week * 7
        rebuild_factor = (week - 5) / 5  # 0.2 to 0.8
        base_distance = int(8000 * rebuild_factor + 3000)
        
        activities.append(create_run(week_start, base_distance, int(base_distance / 3.3), "easy", 142))
        activities.append(create_run(week_start + 2, base_distance, int(base_distance / 3.3), "easy", 140))
        activities.append(create_run(week_start + 4, int(base_distance * 1.5), int(base_distance * 1.5 / 3.3), "easy", 143))
        activities.append(create_run(week_start + 6, int(base_distance * 2), int(base_distance * 2 / 3.3), "long", 145))
    
    # Week 11-12: Back to normal
    for week in range(10, 12):
        week_start = week * 7
        activities.append(create_run(week_start, 8000, 2400, "easy", 140))
        activities.append(create_run(week_start + 1, 10000, 2700, "threshold", 165))
        activities.append(create_run(week_start + 3, 6000, 1800, "easy", 142))
        activities.append(create_run(week_start + 5, 22000, 6600, "long", 145))
    
    # Add all activities to DB
    for activity in activities:
        db_session.add(activity)
    db_session.commit()
    
    yield test_athlete, activities
    
    # Cleanup happens via test_athlete fixture


@pytest.fixture
def athlete_with_race(db_session, test_athlete):
    """Create athlete with threshold workout followed by race."""
    activities = []
    base_date = date.today() - timedelta(days=30)
    
    # Threshold workout 2 weeks before race
    threshold = Activity(
        id=uuid4(),
        athlete_id=test_athlete.id,
        provider="strava",
        external_activity_id=str(uuid4())[:10],
        sport="run",
        name="Tempo Tuesday",
        start_time=datetime.combine(base_date, datetime.min.time()),
        distance_m=10000,
        duration_s=2700,
        average_speed=Decimal("3.7"),
        avg_hr=165,
        max_hr=175,
        workout_type="threshold"
    )
    activities.append(threshold)
    
    # Race 2 weeks later
    race = Activity(
        id=uuid4(),
        athlete_id=test_athlete.id,
        provider="strava",
        external_activity_id=str(uuid4())[:10],
        sport="run",
        name="Spring Half Marathon",
        start_time=datetime.combine(base_date + timedelta(days=14), datetime.min.time()),
        distance_m=21097,
        duration_s=5400,
        average_speed=Decimal("3.9"),
        avg_hr=170,
        max_hr=185,
        workout_type="race",
        is_race_candidate=True
    )
    activities.append(race)
    
    for a in activities:
        db_session.add(a)
    db_session.commit()
    
    yield test_athlete, activities


@pytest.fixture
def athlete_with_efficiency_variance(db_session, test_athlete):
    """Create athlete with varied efficiency (pace:HR ratio)."""
    activities = []
    base_date = date.today() - timedelta(days=30)
    
    # Normal efficiency runs
    for i in range(5):
        a = Activity(
            id=uuid4(),
            athlete_id=test_athlete.id,
            provider="strava",
            external_activity_id=str(uuid4())[:10],
            sport="run",
            name=f"Easy Run {i+1}",
            start_time=datetime.combine(base_date + timedelta(days=i*2), datetime.min.time()),
            distance_m=8000,
            duration_s=2400,
            average_speed=Decimal("3.33"),  # 8:00/mi pace
            avg_hr=145,
            max_hr=160
        )
        activities.append(a)
    
    # Outlier: Much better efficiency (faster at lower HR)
    outlier = Activity(
        id=uuid4(),
        athlete_id=test_athlete.id,
        provider="strava",
        external_activity_id=str(uuid4())[:10],
        sport="run",
        name="Magic Run",
        start_time=datetime.combine(base_date + timedelta(days=15), datetime.min.time()),
        distance_m=10000,
        duration_s=2700,
        average_speed=Decimal("3.7"),  # 7:15/mi pace
        avg_hr=138,  # Lower HR than normal
        max_hr=150
    )
    activities.append(outlier)
    
    for a in activities:
        db_session.add(a)
    db_session.commit()
    
    yield test_athlete, activities, outlier


@pytest.fixture
def athlete_empty_history(db_session, test_athlete):
    """Athlete with no activities."""
    yield test_athlete


# =============================================================================
# TESTS - Empty History Edge Cases
# =============================================================================

class TestEmptyHistoryEdgeCases:
    """Test anchor finder behavior with no data."""
    
    def test_injury_rebound_no_activities(self, db_session, athlete_empty_history):
        """Should return None when no activities exist."""
        finder = AnchorFinder(db_session, athlete_empty_history.id)
        
        result = finder.find_previous_injury_rebound()
        
        assert result is None
    
    def test_similar_workout_no_activities(self, db_session, athlete_empty_history):
        """Should return None when no activities exist."""
        finder = AnchorFinder(db_session, athlete_empty_history.id)
        
        result = finder.find_similar_workout("threshold")
        
        assert result is None
    
    def test_efficiency_outlier_no_activities(self, db_session, athlete_empty_history):
        """Should return None when no activities exist."""
        finder = AnchorFinder(db_session, athlete_empty_history.id)
        
        result = finder.find_efficiency_outlier("high")
        
        assert result is None
    
    def test_similar_milestone_no_activities(self, db_session, athlete_empty_history):
        """Should return None when no activities exist."""
        finder = AnchorFinder(db_session, athlete_empty_history.id)
        
        result = finder.find_similar_milestone(50.0)
        
        assert result is None


# =============================================================================
# TESTS - Injury Rebound Detection
# =============================================================================

class TestInjuryReboundDetection:
    """Test injury pattern detection from real data."""
    
    def test_detects_injury_pattern(self, db_session, athlete_with_activities):
        """Should detect the injury drop and rebound pattern."""
        athlete, activities = athlete_with_activities
        finder = AnchorFinder(db_session, athlete.id)
        
        result = finder.find_previous_injury_rebound(lookback_days=100)
        
        # Should find the injury pattern from weeks 5-6
        assert result is not None
        assert isinstance(result, InjuryReboundAnchor)
        assert result.weeks_to_recover > 0
        assert result.recovery_pct > 0
    
    def test_no_injury_in_consistent_training(self, db_session, athlete_with_race):
        """Should return None when no injury pattern exists."""
        athlete, activities = athlete_with_race
        finder = AnchorFinder(db_session, athlete.id)
        
        result = finder.find_previous_injury_rebound(lookback_days=60)
        
        # No sharp volume drop in this data
        assert result is None


# =============================================================================
# TESTS - Similar Workout Matching
# =============================================================================

class TestSimilarWorkoutMatching:
    """Test workout comparison logic."""
    
    def test_finds_similar_threshold_workout(self, db_session, athlete_with_race):
        """Should find prior threshold workout."""
        athlete, activities = athlete_with_race
        finder = AnchorFinder(db_session, athlete.id)
        
        result = finder.find_similar_workout("threshold", lookback_days=60)
        
        assert result is not None
        assert isinstance(result, WorkoutAnchor)
        assert result.workout_type == "threshold"
    
    def test_finds_workout_with_following_race(self, db_session, athlete_with_race):
        """Should identify race that followed the workout."""
        athlete, activities = athlete_with_race
        finder = AnchorFinder(db_session, athlete.id)
        
        result = finder.find_similar_workout("threshold", lookback_days=60)
        
        assert result is not None
        assert result.following_race is not None
        assert "Half Marathon" in result.following_race or "race" in result.following_race.lower()
        assert result.days_to_race == 14
    
    def test_no_match_for_nonexistent_type(self, db_session, athlete_with_race):
        """Should return None for workout types that don't exist."""
        athlete, activities = athlete_with_race
        finder = AnchorFinder(db_session, athlete.id)
        
        result = finder.find_similar_workout("vo2max", lookback_days=60)
        
        assert result is None


# =============================================================================
# TESTS - Efficiency Outlier Detection
# =============================================================================

class TestEfficiencyOutlierDetection:
    """Test efficiency comparison logic."""
    
    def test_finds_high_efficiency_outlier(self, db_session, athlete_with_efficiency_variance):
        """Should find the run with best efficiency."""
        athlete, activities, outlier = athlete_with_efficiency_variance
        finder = AnchorFinder(db_session, athlete.id)
        
        result = finder.find_efficiency_outlier("high", lookback_days=60)
        
        assert result is not None
        assert isinstance(result, EfficiencyAnchor)
        assert result.direction == "high"
        # The outlier should have the best efficiency
        assert result.activity_id == outlier.id
    
    def test_efficiency_requires_minimum_activities(self, db_session, test_athlete):
        """Should return None with fewer than 5 activities."""
        # Create only 3 activities
        for i in range(3):
            a = Activity(
                id=uuid4(),
                athlete_id=test_athlete.id,
                provider="strava",
                external_activity_id=str(uuid4())[:10],
                sport="run",
                name=f"Run {i}",
                start_time=datetime.now() - timedelta(days=i),
                distance_m=8000,
                duration_s=2400,
                average_speed=Decimal("3.33"),
                avg_hr=145,
                max_hr=160
            )
            db_session.add(a)
        db_session.commit()
        
        finder = AnchorFinder(db_session, test_athlete.id)
        result = finder.find_efficiency_outlier("high", lookback_days=30)
        
        assert result is None


# =============================================================================
# TESTS - Milestone Comparison
# =============================================================================

class TestMilestoneComparison:
    """Test milestone matching logic."""
    
    def test_finds_similar_volume_week(self, db_session, athlete_with_activities):
        """Should find prior week with similar volume."""
        athlete, activities = athlete_with_activities
        finder = AnchorFinder(db_session, athlete.id)
        
        # Look for a week around 50 miles (the normal training weeks)
        result = finder.find_similar_milestone(50.0, tolerance_pct=0.2)
        
        # Should find a comparable week from the training history
        assert result is not None
        assert isinstance(result, MilestoneAnchor)
        assert 40 <= result.weekly_miles <= 60


# =============================================================================
# TESTS - Date Formatting
# =============================================================================

class TestDateFormatting:
    """Test date formatting utilities."""
    
    def test_format_today(self):
        assert format_date_relative(date.today()) == "today"
    
    def test_format_yesterday(self):
        assert format_date_relative(date.today() - timedelta(days=1)) == "yesterday"
    
    def test_format_this_week(self):
        # 3 days ago should return day name
        d = date.today() - timedelta(days=3)
        result = format_date_relative(d)
        assert result in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    def test_format_pace(self):
        assert format_pace(6.5) == "6:30"
        assert format_pace(7.0) == "7:00"
        assert format_pace(5.25) == "5:15"


# =============================================================================
# TESTS - Cross-User Isolation
# =============================================================================

class TestCrossUserIsolation:
    """Verify anchor finder only sees current user's data."""
    
    def test_only_finds_own_activities(self, db_session, test_athlete):
        """Should not find activities from other athletes."""
        # Create another athlete with activities
        other_athlete = Athlete(
            email=f"other_{uuid4()}@example.com",
            display_name="Other Athlete",
            subscription_tier="free"
        )
        db_session.add(other_athlete)
        db_session.commit()
        
        # Add activity for other athlete
        other_activity = Activity(
            id=uuid4(),
            athlete_id=other_athlete.id,
            provider="strava",
            external_activity_id=str(uuid4())[:10],
            sport="run",
            name="Other's Threshold",
            start_time=datetime.now() - timedelta(days=10),
            distance_m=10000,
            duration_s=2700,
            average_speed=Decimal("3.7"),
            avg_hr=165,
            max_hr=175,
            workout_type="threshold"
        )
        db_session.add(other_activity)
        db_session.commit()
        
        # Query for test_athlete
        finder = AnchorFinder(db_session, test_athlete.id)
        result = finder.find_similar_workout("threshold", lookback_days=60)
        
        # Should not find other athlete's activity
        assert result is None
        
        # Cleanup
        db_session.delete(other_activity)
        db_session.delete(other_athlete)
        db_session.commit()
