"""Tests for expanded race detection (Racing Fingerprint Pre-Work P4)."""

import pytest
from services.performance_engine import (
    RACE_DISTANCES,
    _name_race_score,
    detect_race_candidate,
)


def _splits_consistent(n: int, pace_min_per_mile: float = 8.0, hr: int = 170):
    """Build n consistent splits (low CV)."""
    dist_per_split = 1609.34
    time_per_split = pace_min_per_mile * 60
    return [
        {
            "distance": dist_per_split,
            "moving_time": time_per_split,
            "average_heartrate": hr,
        }
        for _ in range(n)
    ]


class TestRaceDistances:
    def test_has_eight_distances(self):
        assert len(RACE_DISTANCES) == 8

    def test_mile_range(self):
        lo, hi = RACE_DISTANCES['mile']
        assert lo <= 1609 <= hi

    def test_50k_range(self):
        lo, hi = RACE_DISTANCES['50k']
        assert lo <= 50000 <= hi


class TestExpandedRaceDetection:
    def test_detects_mile_race(self):
        is_race, conf = detect_race_candidate(
            activity_pace=5.5, max_hr=190, avg_hr=180,
            splits=_splits_consistent(1, pace_min_per_mile=5.5),
            distance_meters=1609, duration_seconds=540,
            activity_name="Track Mile Race",
        )
        assert conf > 0

    def test_detects_15k_race(self):
        is_race, conf = detect_race_candidate(
            activity_pace=7.5, max_hr=185, avg_hr=172,
            splits=_splits_consistent(9),
            distance_meters=15000, duration_seconds=4200,
            activity_name="Spring 15K Classic",
        )
        assert is_race is True

    def test_detects_25k_race(self):
        is_race, conf = detect_race_candidate(
            activity_pace=8.0, max_hr=185, avg_hr=172,
            splits=_splits_consistent(15),
            distance_meters=25100, duration_seconds=7500,
            activity_name="Trail 25K Race",
        )
        assert is_race is True

    def test_detects_50k_race(self):
        is_race, conf = detect_race_candidate(
            activity_pace=9.0, max_hr=180, avg_hr=155,
            splits=_splits_consistent(31),
            distance_meters=50200, duration_seconds=16000,
        )
        assert conf > 0

    def test_detects_race_without_hr(self):
        """Distance match + name + consistent splits → detected without HR."""
        is_race, conf = detect_race_candidate(
            activity_pace=7.5, max_hr=None, avg_hr=None,
            splits=_splits_consistent(6, hr=0),
            distance_meters=10000, duration_seconds=2800,
            activity_name="Gulf Coast Classic 10K Race",
        )
        assert is_race is True
        assert conf >= 0.50

    def test_name_boosts_confidence(self):
        name_score = _name_race_score("Charity 5K - 1st Overall Finish")
        assert name_score >= 0.8

    def test_name_alone_insufficient(self):
        """Race-like name at non-standard distance → not detected."""
        is_race, conf = detect_race_candidate(
            activity_pace=8.0, max_hr=180, avg_hr=165,
            splits=_splits_consistent(5),
            distance_meters=7000,
            duration_seconds=2400,
            activity_name="Race prep run",
        )
        assert is_race is False
        assert conf == 0.0

    def test_non_race_distance_returns_zero(self):
        is_race, conf = detect_race_candidate(
            activity_pace=8.0, max_hr=190, avg_hr=180,
            splits=_splits_consistent(4),
            distance_meters=8000, duration_seconds=2400,
        )
        assert is_race is False
        assert conf == 0.0

    def test_5k_with_low_hr_not_race(self):
        """5K at easy HR should not be flagged as race."""
        is_race, conf = detect_race_candidate(
            activity_pace=9.0, max_hr=190, avg_hr=140,
            splits=_splits_consistent(3),
            distance_meters=5000, duration_seconds=1680,
        )
        assert is_race is False

    def test_original_4_distances_still_work(self):
        """5K, 10K, half, marathon all still detect with strong signals."""
        for dist, n_splits in [(5000, 4), (10000, 6), (21097, 13), (42195, 26)]:
            is_race, conf = detect_race_candidate(
                activity_pace=7.0, max_hr=190, avg_hr=178,
                splits=_splits_consistent(n_splits),
                distance_meters=dist, duration_seconds=n_splits * 450,
                activity_name="Spring Race",
            )
            assert is_race is True, f"Failed for {dist}m (conf={conf})"


class TestNameRaceScore:
    def test_no_name(self):
        assert _name_race_score(None) == 0.0

    def test_empty_name(self):
        assert _name_race_score("") == 0.0

    def test_single_keyword(self):
        assert _name_race_score("Morning Race") == 0.5

    def test_two_keywords(self):
        assert _name_race_score("Charity Race") == 0.8

    def test_three_keywords(self):
        assert _name_race_score("5K Race 1st Overall") == 1.0

    def test_no_keywords(self):
        assert _name_race_score("Easy morning jog") == 0.0
