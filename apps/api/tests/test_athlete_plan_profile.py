"""
Tests for AthletePlanProfileService — N=1 override system (Phase 1C).

Tests are organized by derivation domain:
1. Long run identification (duration-gated at 105 min)
2. Volume derivation (tier, trend, confidence)
3. Recovery derivation (half-life, cutback frequency)
4. Quality tolerance (sessions/week, back-to-back)
5. Data sufficiency classification
6. Edge cases (gaps, inconsistent logging, taper pollution)
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from services.athlete_plan_profile import (
    AthletePlanProfileService,
    AthleteProfile,
    LONG_RUN_DURATION_THRESHOLD_MIN,
)


def _make_activity(
    distance_miles: float,
    duration_minutes: float,
    days_ago: int = 0,
    sport: str = "run",
    workout_type: str = None,
    is_race: bool = False,
):
    """Create a mock Activity object for testing."""
    act = MagicMock()
    act.distance_m = int(distance_miles * 1609.344)
    act.duration_s = int(duration_minutes * 60)
    act.sport = sport
    act.start_time = datetime.now(timezone.utc) - timedelta(days=days_ago)
    act.workout_type = workout_type
    act.is_race_candidate = is_race
    act.user_verified_race = is_race
    act.avg_hr = 140
    act.max_hr = 170
    act.intensity_score = 50
    return act


def _make_week_of_runs(
    days_ago_start: int,
    easy_miles: float = 6.0,
    easy_pace_min_per_mile: float = 9.0,
    long_miles: float = None,
    long_pace_min_per_mile: float = 9.5,
    quality_miles: float = None,
    quality_type: str = "tempo_run",
    runs_per_week: int = 5,
):
    """Create a synthetic week of training."""
    activities = []
    # Easy runs
    easy_count = runs_per_week - (1 if long_miles else 0) - (1 if quality_miles else 0)
    for i in range(easy_count):
        activities.append(_make_activity(
            distance_miles=easy_miles,
            duration_minutes=easy_miles * easy_pace_min_per_mile,
            days_ago=days_ago_start + i,
            workout_type="easy_run",
        ))
    # Long run (Saturday)
    if long_miles:
        activities.append(_make_activity(
            distance_miles=long_miles,
            duration_minutes=long_miles * long_pace_min_per_mile,
            days_ago=days_ago_start + 5,
            workout_type="long_run",
        ))
    # Quality session
    if quality_miles:
        activities.append(_make_activity(
            distance_miles=quality_miles,
            duration_minutes=quality_miles * 8.0,  # faster pace
            days_ago=days_ago_start + 3,
            workout_type=quality_type,
        ))
    return activities


# ---------------------------------------------------------------------------
# Fixtures: standard athlete histories
# ---------------------------------------------------------------------------

def _experienced_70mpw_history():
    """12 weeks of a ~70 mpw runner with 16-18mi long runs.

    Weekly breakdown (6 runs):
      4 easy * 11mi = 44 + 1 long * ~17mi + 1 quality * 8mi = ~69mi
    """
    activities = []
    for week in range(12):
        days_ago = week * 7
        activities.extend(_make_week_of_runs(
            days_ago_start=days_ago,
            easy_miles=11.0,
            easy_pace_min_per_mile=7.5,
            long_miles=16.0 + (week % 3),  # 16, 17, 18 rotation
            long_pace_min_per_mile=8.0,    # 16mi * 8.0 = 128min > 105
            quality_miles=8.0,
            quality_type="tempo_run" if week % 2 == 0 else "vo2max_intervals",
            runs_per_week=6,
        ))
    return activities


def _beginner_25mpw_history():
    """8 weeks of a ~25 mpw runner with short runs.

    Weekly breakdown (4 runs):
      3 easy * 5mi = 15 + 1 long * 8mi = 23mi
    Long run: 8mi * 11.5 min/mi = 92min < 105 (NOT a long run by duration gate)
    """
    activities = []
    for week in range(8):
        days_ago = week * 7
        activities.extend(_make_week_of_runs(
            days_ago_start=days_ago,
            easy_miles=5.0,
            easy_pace_min_per_mile=11.0,
            long_miles=8.0,                # 8mi * 11.5 = 92min < 105
            long_pace_min_per_mile=11.5,
            quality_miles=None,
            runs_per_week=4,
        ))
    return activities


def _masters_55mpw_history():
    """10 weeks of a 55 mpw masters runner."""
    activities = []
    for week in range(10):
        days_ago = week * 7
        activities.extend(_make_week_of_runs(
            days_ago_start=days_ago,
            easy_miles=7.0,
            easy_pace_min_per_mile=8.5,
            long_miles=14.0,               # 14mi * 9.0 = 126min > 105
            long_pace_min_per_mile=9.0,
            quality_miles=7.0,
            quality_type="tempo_run",
            runs_per_week=6,
        ))
    return activities


# ===================================================================
# Test Group 1: Long Run Identification (Duration-Gated)
# ===================================================================

class TestLongRunIdentification:
    """Long runs are identified by duration (>= 105 min), not distance."""

    def test_fast_10_miler_not_long_run(self):
        """A 10mi run at 7:00/mi (70 min) is NOT a long run."""
        svc = AthletePlanProfileService()
        activities = [_make_activity(10.0, 70, days_ago=1)]
        long_runs = svc._identify_long_runs(activities)
        assert len(long_runs) == 0

    def test_slow_10_miler_is_long_run(self):
        """A 10mi run at 11:00/mi (110 min) IS a long run."""
        svc = AthletePlanProfileService()
        activities = [_make_activity(10.0, 110, days_ago=1)]
        long_runs = svc._identify_long_runs(activities)
        assert len(long_runs) == 1

    def test_trail_8_miler_is_long_run(self):
        """An 8mi trail run at 2:15 (135 min) IS a long run."""
        svc = AthletePlanProfileService()
        activities = [_make_activity(8.0, 135, days_ago=1)]
        long_runs = svc._identify_long_runs(activities)
        assert len(long_runs) == 1

    def test_105_min_threshold_boundary(self):
        """Exactly 105 min is a long run; 104 min is not."""
        svc = AthletePlanProfileService()
        at_threshold = [_make_activity(11.0, 105, days_ago=1)]
        below_threshold = [_make_activity(11.0, 104, days_ago=2)]
        assert len(svc._identify_long_runs(at_threshold)) == 1
        assert len(svc._identify_long_runs(below_threshold)) == 0

    def test_multiple_long_runs_identified(self):
        """Multiple runs over 105 min are all identified."""
        svc = AthletePlanProfileService()
        activities = _experienced_70mpw_history()
        long_runs = svc._identify_long_runs(activities)
        # 12 weeks, each with a 16-18mi long run at 8:00/mi = 128-144 min
        assert len(long_runs) >= 10  # At least 10 of 12 should qualify

    def test_beginner_no_long_runs(self):
        """A beginner with 7mi runs at 11:30 (80 min) has no long runs."""
        svc = AthletePlanProfileService()
        activities = _beginner_25mpw_history()
        long_runs = svc._identify_long_runs(activities)
        assert len(long_runs) == 0

    def test_non_runs_excluded(self):
        """Activities with sport != 'run' are excluded."""
        svc = AthletePlanProfileService()
        activities = [_make_activity(10.0, 120, days_ago=1, sport="ride")]
        long_runs = svc._identify_long_runs(activities)
        assert len(long_runs) == 0


# ===================================================================
# Test Group 2: Long Run Baseline Calculation
# ===================================================================

class TestLongRunBaseline:
    """Baseline uses median of last 8 identified long runs."""

    def test_baseline_from_experienced_runner(self):
        """70 mpw runner: baseline should reflect 16-18mi long runs."""
        svc = AthletePlanProfileService()
        activities = _experienced_70mpw_history()
        profile = svc._derive_long_run(activities, weeks_of_data=12)
        # Median of 16, 17, 18 rotation = ~17mi
        assert 15.0 <= profile["baseline_miles"] <= 19.0
        # Duration: ~8:00/mi * 17mi = ~136 min
        assert profile["baseline_minutes"] >= 105
        assert profile["confidence"] >= 0.7
        assert profile["source"] == "history"

    def test_baseline_cold_start_beginner(self):
        """Beginner with no long runs: falls back to tier default."""
        svc = AthletePlanProfileService()
        activities = _beginner_25mpw_history()
        profile = svc._derive_long_run(activities, weeks_of_data=8)
        assert profile["confidence"] == 0.0
        assert profile["source"] == "tier_default"
        assert profile["frequency"] == 0.0

    def test_baseline_uses_last_8(self):
        """Uses only the most recent 8 long runs, not all of them."""
        svc = AthletePlanProfileService()
        # Create 15 long runs: old ones at 12mi, recent ones at 18mi
        old_longs = [_make_activity(12.0, 120, days_ago=100 + i * 7) for i in range(7)]
        recent_longs = [_make_activity(18.0, 144, days_ago=i * 7) for i in range(8)]
        activities = old_longs + recent_longs
        profile = svc._derive_long_run(activities, weeks_of_data=15)
        # Should be based on the recent 18mi runs, not the old 12mi runs
        assert profile["baseline_miles"] >= 17.0

    def test_typical_pace_calculated(self):
        """Typical pace is median(duration / distance) of identified long runs."""
        svc = AthletePlanProfileService()
        activities = _experienced_70mpw_history()
        profile = svc._derive_long_run(activities, weeks_of_data=12)
        # ~8:00/mi pace
        assert 7.5 <= profile["typical_pace"] <= 8.5


# ===================================================================
# Test Group 3: Volume Derivation
# ===================================================================

class TestVolumeDerivation:
    """Volume tier, current, peak, trend from activity history."""

    def test_experienced_runner_volume(self):
        """70 mpw runner classified as HIGH tier."""
        svc = AthletePlanProfileService()
        activities = _experienced_70mpw_history()
        vol = svc._derive_volume(activities, goal_distance="marathon")
        assert vol["tier"].value in ("high", "elite")
        assert 60 <= vol["current_weekly_miles"] <= 80
        assert vol["confidence"] >= 0.8

    def test_beginner_volume(self):
        """25 mpw runner classified as BUILDER or LOW tier."""
        svc = AthletePlanProfileService()
        activities = _beginner_25mpw_history()
        vol = svc._derive_volume(activities, goal_distance="marathon")
        assert vol["tier"].value in ("builder", "low")
        assert 20 <= vol["current_weekly_miles"] <= 30

    def test_volume_trend_stable(self):
        """Consistent volume → 'maintaining' trend."""
        svc = AthletePlanProfileService()
        activities = _experienced_70mpw_history()
        vol = svc._derive_volume(activities, goal_distance="marathon")
        assert vol["trend"] == "maintaining"

    def test_empty_history(self):
        """No activities → zero volume, cold start confidence."""
        svc = AthletePlanProfileService()
        vol = svc._derive_volume([], goal_distance="marathon")
        assert vol["current_weekly_miles"] == 0
        assert vol["confidence"] == 0.0

    def test_volume_trend_building(self):
        """Ascending volume → 'building' trend."""
        svc = AthletePlanProfileService()
        # 8 weeks: volume ramps from ~30 to ~55 mpw
        activities = []
        for week in range(8):
            days_ago = (7 - week) * 7  # oldest first
            miles_per_run = 5.0 + week * 0.8  # 5.0 → 10.6
            activities.extend(_make_week_of_runs(
                days_ago_start=days_ago,
                easy_miles=miles_per_run,
                runs_per_week=5,
            ))
        vol = svc._derive_volume(activities, goal_distance="marathon")
        assert vol["trend"] == "building"

    def test_volume_trend_declining(self):
        """Descending volume → 'declining' trend."""
        svc = AthletePlanProfileService()
        # 8 weeks: volume drops from ~55 to ~25 mpw
        activities = []
        for week in range(8):
            days_ago = (7 - week) * 7
            miles_per_run = 11.0 - week * 1.0  # 11 → 4
            activities.extend(_make_week_of_runs(
                days_ago_start=days_ago,
                easy_miles=miles_per_run,
                runs_per_week=5,
            ))
        vol = svc._derive_volume(activities, goal_distance="marathon")
        assert vol["trend"] == "declining"


# ===================================================================
# Test Group 4: Recovery Derivation
# ===================================================================

class TestRecoveryDerivation:
    """Recovery half-life and cutback frequency from history."""

    def test_default_cutback_frequency(self):
        """Without strong signal, cutback defaults to 4."""
        svc = AthletePlanProfileService()
        activities = _experienced_70mpw_history()
        rec = svc._derive_recovery(activities)
        assert rec["cutback_frequency"] in (3, 4, 5)

    def test_insufficient_data_low_confidence(self):
        """Few activities → low recovery confidence."""
        svc = AthletePlanProfileService()
        activities = [_make_activity(5.0, 45, days_ago=i) for i in range(3)]
        rec = svc._derive_recovery(activities)
        assert rec["confidence"] <= 0.3

    def test_half_life_to_cutback_mapping_fast(self):
        """Fast recoverer (half-life ≤ 36h) → cutback every 5 weeks."""
        svc = AthletePlanProfileService()
        # The recovery derivation tries to import calculate_recovery_half_life.
        # When it can't compute a real value (mock env), it falls back to
        # default 48h → freq 4. We test the mapping logic directly.
        # Half-life ≤ 36 → freq 5
        assert svc._map_half_life_to_cutback(30.0) == 5
        assert svc._map_half_life_to_cutback(36.0) == 5

    def test_half_life_to_cutback_mapping_normal(self):
        """Normal recoverer (36h < half-life ≤ 60h) → cutback every 4 weeks."""
        svc = AthletePlanProfileService()
        assert svc._map_half_life_to_cutback(48.0) == 4
        assert svc._map_half_life_to_cutback(60.0) == 4

    def test_half_life_to_cutback_mapping_slow(self):
        """Slow recoverer (half-life > 60h) → cutback every 3 weeks."""
        svc = AthletePlanProfileService()
        assert svc._map_half_life_to_cutback(72.0) == 3
        assert svc._map_half_life_to_cutback(96.0) == 3


# ===================================================================
# Test Group 5: Quality Tolerance
# ===================================================================

class TestQualityTolerance:
    """How many quality sessions the athlete handles per week."""

    def test_experienced_runner_quality(self):
        """70 mpw runner with regular quality sessions."""
        svc = AthletePlanProfileService()
        activities = _experienced_70mpw_history()
        qt = svc._derive_quality_tolerance(activities, weeks_of_data=12)
        assert qt["sessions_per_week"] >= 1.0
        assert qt["confidence"] >= 0.5

    def test_beginner_no_quality(self):
        """Beginner with no quality sessions."""
        svc = AthletePlanProfileService()
        activities = _beginner_25mpw_history()
        qt = svc._derive_quality_tolerance(activities, weeks_of_data=8)
        assert qt["sessions_per_week"] < 0.5

    def test_back_to_back_quality_detected(self):
        """Consecutive-day quality sessions are detected."""
        svc = AthletePlanProfileService()
        activities = [
            _make_activity(7.0, 56, days_ago=3, workout_type="tempo_run"),
            _make_activity(6.0, 42, days_ago=2, workout_type="vo2max_intervals"),
            _make_activity(5.0, 45, days_ago=1, workout_type="easy_run"),
        ]
        qt = svc._derive_quality_tolerance(activities, weeks_of_data=1)
        assert qt["back_to_back"] is True

    def test_no_back_to_back_when_separated(self):
        """Quality sessions 3+ days apart → back_to_back is False."""
        svc = AthletePlanProfileService()
        activities = [
            _make_activity(7.0, 56, days_ago=7, workout_type="tempo_run"),
            _make_activity(6.0, 42, days_ago=3, workout_type="vo2max_intervals"),
            _make_activity(5.0, 45, days_ago=1, workout_type="easy_run"),
        ]
        qt = svc._derive_quality_tolerance(activities, weeks_of_data=2)
        assert qt["back_to_back"] is False


# ===================================================================
# Test Group 6: Data Sufficiency
# ===================================================================

class TestDataSufficiency:
    """Classification: rich, adequate, thin, cold_start."""

    def test_rich_data(self):
        """12 weeks, 70+ runs → rich."""
        svc = AthletePlanProfileService()
        activities = _experienced_70mpw_history()
        assert svc._classify_sufficiency(activities) == "rich"

    def test_adequate_data(self):
        """10 weeks, ~60 runs → adequate."""
        svc = AthletePlanProfileService()
        activities = _masters_55mpw_history()
        assert svc._classify_sufficiency(activities) == "adequate"

    def test_thin_data(self):
        """4-7 weeks, 12-24 runs → thin."""
        svc = AthletePlanProfileService()
        # 5 weeks * 4 runs = 20 runs
        activities = []
        for week in range(5):
            activities.extend(_make_week_of_runs(
                days_ago_start=week * 7,
                easy_miles=5.0,
                runs_per_week=4,
            ))
        assert svc._classify_sufficiency(activities) == "thin"

    def test_cold_start(self):
        """< 4 weeks or < 12 runs → cold_start."""
        svc = AthletePlanProfileService()
        activities = [_make_activity(5.0, 45, days_ago=i) for i in range(5)]
        assert svc._classify_sufficiency(activities) == "cold_start"

    def test_empty_cold_start(self):
        """No activities → cold_start."""
        svc = AthletePlanProfileService()
        assert svc._classify_sufficiency([]) == "cold_start"


# ===================================================================
# Test Group 7: Edge Cases
# ===================================================================

class TestEdgeCases:
    """Gaps, inconsistent logging, taper pollution."""

    def test_gap_detection_28_days(self):
        """28+ day gap triggers post-gap window."""
        svc = AthletePlanProfileService()
        # Pre-gap: 60mpw, 8 weeks ago to 5 weeks ago
        pre_gap = []
        for week in range(3):
            pre_gap.extend(_make_week_of_runs(
                days_ago_start=56 + week * 7,
                easy_miles=8.0,
                long_miles=16.0,
                long_pace_min_per_mile=8.0,
                runs_per_week=6,
            ))
        # 30-day gap (no activities)
        # Post-gap: 20mpw, last 3 weeks
        post_gap = []
        for week in range(3):
            post_gap.extend(_make_week_of_runs(
                days_ago_start=week * 7,
                easy_miles=4.0,
                runs_per_week=4,
            ))
        all_activities = pre_gap + post_gap
        window, disclosures = svc._get_analysis_window(all_activities)
        # Should use post-gap only
        assert any("break" in d.lower() or "returning" in d.lower() for d in disclosures)

    def test_no_gap_under_28_days(self):
        """< 28 day gap does NOT trigger gap handling."""
        svc = AthletePlanProfileService()
        # 20-day gap between two training blocks
        block1 = [_make_activity(6.0, 54, days_ago=30 + i) for i in range(5)]
        block2 = [_make_activity(6.0, 54, days_ago=i) for i in range(5)]
        all_activities = block1 + block2
        window, disclosures = svc._get_analysis_window(all_activities)
        # No gap disclosure
        assert not any("break" in d.lower() or "returning" in d.lower() for d in disclosures)

    def test_race_taper_detection(self):
        """Recent race extends analysis window past taper."""
        svc = AthletePlanProfileService()
        # Normal training 3-11 weeks ago (continuous, no 28-day gap)
        pre_taper = []
        for week in range(8):
            pre_taper.extend(_make_week_of_runs(
                days_ago_start=21 + week * 7,
                easy_miles=7.0,
                long_miles=14.0,
                long_pace_min_per_mile=8.5,
                runs_per_week=5,
            ))
        # Taper: last 2 weeks (reduced volume, no long run)
        taper = [_make_activity(4.0, 36, days_ago=i) for i in range(14)]
        # Race 3 days ago
        race = _make_activity(26.2, 210, days_ago=3, is_race=True)
        all_activities = pre_taper + taper + [race]
        window, disclosures = svc._get_analysis_window(all_activities)
        assert any("taper" in d.lower() or "race" in d.lower() for d in disclosures)

    def test_non_run_activities_filtered(self):
        """Cycling and other sports are excluded from profile derivation."""
        svc = AthletePlanProfileService()
        runs = [_make_activity(6.0, 54, days_ago=i, sport="run") for i in range(10)]
        bikes = [_make_activity(20.0, 120, days_ago=i, sport="ride") for i in range(10)]
        all_activities = runs + bikes
        run_only = svc._filter_runs(all_activities)
        assert len(run_only) == 10
        assert all(a.sport == "run" for a in run_only)

    def test_staleness_days(self):
        """Staleness reflects days since most recent activity."""
        svc = AthletePlanProfileService()
        # Most recent run was 5 days ago
        activities = [_make_activity(6.0, 54, days_ago=5 + i) for i in range(20)]
        profile = svc.derive_profile_from_activities(activities, "marathon")
        assert 4 <= profile.staleness_days <= 6  # allow 1-day tolerance


# ===================================================================
# Test Group 8: Full Profile Derivation (Integration)
# ===================================================================

class TestFullProfile:
    """End-to-end profile derivation from activity history."""

    def test_experienced_70mpw_profile(self):
        """Experienced runner gets rich, high-confidence profile."""
        svc = AthletePlanProfileService()
        activities = _experienced_70mpw_history()
        profile = svc.derive_profile_from_activities(
            activities=activities,
            goal_distance="marathon",
        )
        assert isinstance(profile, AthleteProfile)
        assert profile.data_sufficiency == "rich"
        assert profile.volume_tier.value in ("high", "elite")
        assert profile.long_run_confidence >= 0.6
        assert profile.long_run_source == "history"
        assert profile.long_run_baseline_minutes >= 105
        assert 15.0 <= profile.long_run_baseline_miles <= 19.0

    def test_beginner_25mpw_profile(self):
        """Beginner gets thin data, tier defaults for long run."""
        svc = AthletePlanProfileService()
        activities = _beginner_25mpw_history()
        profile = svc.derive_profile_from_activities(
            activities=activities,
            goal_distance="marathon",
        )
        assert profile.data_sufficiency in ("thin", "adequate")
        assert profile.volume_tier.value in ("builder", "low")
        assert profile.long_run_confidence == 0.0
        assert profile.long_run_source == "tier_default"
        assert len(profile.disclosures) > 0  # Should have transparency notes

    def test_masters_55mpw_profile(self):
        """Masters runner gets adequate data, reasonable profile."""
        svc = AthletePlanProfileService()
        activities = _masters_55mpw_history()
        profile = svc.derive_profile_from_activities(
            activities=activities,
            goal_distance="half_marathon",
        )
        assert profile.data_sufficiency in ("adequate", "rich")
        assert profile.volume_tier.value in ("mid", "high")
        assert profile.long_run_confidence >= 0.4

    def test_cold_start_profile(self):
        """No history → cold start with all defaults and disclosures."""
        svc = AthletePlanProfileService()
        profile = svc.derive_profile_from_activities(
            activities=[],
            goal_distance="marathon",
        )
        assert profile.data_sufficiency == "cold_start"
        assert profile.volume_confidence == 0.0
        assert profile.long_run_confidence == 0.0
        assert profile.long_run_source == "tier_default"
        assert len(profile.disclosures) >= 1
