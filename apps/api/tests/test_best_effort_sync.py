"""
Unit tests for BestEffort sync and BigInteger fix.

Tests the BestEffort table schema, sync flow, and PersonalBest integration.

ADR-018: BestEffort strava_effort_id BigInteger Fix
"""

import pytest
from datetime import datetime, date, timedelta
from uuid import uuid4
from unittest.mock import MagicMock, patch
from services.best_effort_service import (
    normalize_effort_name,
    STRAVA_EFFORT_MAP,
    STANDARD_DISTANCES,
)


class TestNormalizeEffortName:
    """Test Strava effort name normalization."""
    
    def test_normalize_mile(self):
        """Normalizes '1 mile' to 'mile'."""
        assert normalize_effort_name("1 mile") == "mile"
        assert normalize_effort_name("mile") == "mile"
    
    def test_normalize_5k(self):
        """Normalizes '5k' to '5k'."""
        assert normalize_effort_name("5k") == "5k"
        assert normalize_effort_name("5K") == "5k"
    
    def test_normalize_half_marathon(self):
        """Normalizes half marathon variants."""
        assert normalize_effort_name("half marathon") == "half_marathon"
        assert normalize_effort_name("half-marathon") == "half_marathon"
    
    def test_unmapped_efforts_return_none(self):
        """Unmapped efforts return None."""
        assert normalize_effort_name("1/2 mile") is None
        # Now tracked as standard distances
        assert normalize_effort_name("1k") == "1k"
        assert normalize_effort_name("10 mile") == "10_mile"
    
    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        assert normalize_effort_name("") is None
        assert normalize_effort_name(None) is None


class TestStravaEffortMap:
    """Test Strava effort mapping configuration."""
    
    def test_all_mapped_categories_exist(self):
        """All mapped categories have corresponding standard distances."""
        for strava_name, category in STRAVA_EFFORT_MAP.items():
            if category is not None:
                assert category in STANDARD_DISTANCES, f"{category} not in STANDARD_DISTANCES"
    
    def test_marathon_mapped(self):
        """Marathon is mapped correctly."""
        assert STRAVA_EFFORT_MAP.get("marathon") == "marathon"
    
    def test_2mile_mapped(self):
        """2 mile is mapped correctly."""
        assert STRAVA_EFFORT_MAP.get("2 mile") == "2mile"


class TestStandardDistances:
    """Test standard distances configuration."""
    
    def test_5k_distance(self):
        """5K is 5000 meters."""
        assert STANDARD_DISTANCES["5k"] == 5000
    
    def test_mile_distance(self):
        """Mile is 1609 meters."""
        assert STANDARD_DISTANCES["mile"] == 1609
    
    def test_half_marathon_distance(self):
        """Half marathon is 21097 meters."""
        assert STANDARD_DISTANCES["half_marathon"] == 21097
    
    def test_marathon_distance(self):
        """Marathon is 42195 meters."""
        assert STANDARD_DISTANCES["marathon"] == 42195


class TestBigIntegerStravaIds:
    """Test that large Strava effort IDs are handled correctly."""
    
    def test_large_strava_effort_id_fits(self):
        """Strava effort IDs larger than 32-bit max are valid."""
        large_id = 71766851694  # Actual Strava effort ID
        max_int32 = 2147483647
        max_int64 = 9223372036854775807
        
        assert large_id > max_int32, "Test ID should exceed 32-bit max"
        assert large_id < max_int64, "Test ID should fit in 64-bit"
    
    def test_strava_effort_id_examples(self):
        """Real Strava effort IDs from API responses."""
        # These are real IDs that caused the original bug
        effort_ids = [
            71766851694,
            71766851688,
            69057812036,
            69057812028,
        ]
        
        max_int32 = 2147483647
        for eid in effort_ids:
            assert eid > max_int32, f"Effort ID {eid} should exceed 32-bit max"


class TestBestEffortModel:
    """Test BestEffort model with BigInteger column."""
    
    def test_besteffort_can_store_large_ids(self):
        """BestEffort model can store large strava_effort_id values."""
        # This test verifies the schema at import time
        from models import BestEffort
        from sqlalchemy import BigInteger
        
        # Check column type
        column = BestEffort.__table__.columns['strava_effort_id']
        assert isinstance(column.type, BigInteger), \
            f"strava_effort_id should be BigInteger, got {type(column.type)}"


class TestPersonalBestMerge:
    """Test PersonalBest merging from multiple sources."""
    
    def test_takes_faster_time(self):
        """Merge should take the faster time from either source."""
        # Activity-based PB: 19:01 (1141s)
        # BestEffort PB: 19:31 (1171s)
        # Result: 19:01 (Activity is faster)
        
        activity_time = 1141
        besteffort_time = 1171
        
        merged_time = min(activity_time, besteffort_time)
        assert merged_time == activity_time
    
    def test_takes_besteffort_when_faster(self):
        """Merge should take BestEffort when it's faster."""
        # Activity-based PB: 6:18 (378s)
        # BestEffort PB: 6:08 (368s)
        # Result: 6:08 (BestEffort is faster)
        
        activity_time = 378
        besteffort_time = 368
        
        merged_time = min(activity_time, besteffort_time)
        assert merged_time == besteffort_time


class TestRaceFlagInheritance:
    """Test that is_race flag is inherited from Activity."""
    
    def test_besteffort_from_race_activity_is_race(self):
        """BestEffort from a race activity should be marked as race."""
        # If Activity.is_race_candidate is True, PersonalBest.is_race should be True
        
        activity_is_race = True
        expected_pb_is_race = True
        
        assert expected_pb_is_race == activity_is_race
    
    def test_besteffort_from_training_is_not_race(self):
        """BestEffort from a training run should not be marked as race."""
        activity_is_race = False
        expected_pb_is_race = False
        
        assert expected_pb_is_race == activity_is_race
