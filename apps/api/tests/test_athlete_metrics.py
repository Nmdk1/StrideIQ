"""
Unit tests for Athlete Metrics Service

Tests auto-estimation of max_hr and VDOT.
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import MagicMock, patch
from services.athlete_metrics import (
    estimate_max_hr,
    estimate_vdot,
    auto_estimate_athlete_thresholds
)


class TestEstimateMaxHR:
    """Test max_hr estimation logic."""
    
    def test_respects_user_set_value(self):
        """Test that user-set max_hr is not overwritten."""
        athlete = MagicMock()
        athlete.max_hr = 185  # User-set value
        db = MagicMock()
        
        result = estimate_max_hr(athlete, db, force_update=False)
        
        assert result == 185
        # Should not query database
        db.query.assert_not_called()
    
    def test_force_update_overrides_user_value(self):
        """Test that force_update recalculates even with user value."""
        athlete = MagicMock()
        athlete.id = uuid4()
        athlete.max_hr = 185
        athlete.birthdate = date(1980, 1, 1)  # ~44 years old
        
        db = MagicMock()
        # Mock no activities with HR data
        mock_query = MagicMock()
        mock_query.scalar.return_value = None
        db.query.return_value.filter.return_value = mock_query
        
        with patch('services.performance_engine.calculate_age_at_date', return_value=44):
            result = estimate_max_hr(athlete, db, force_update=True)
        
        # Should calculate from age formula: 220 - 44 = 176
        assert result == 176
    
    def test_age_formula_fallback(self):
        """Test fallback to 220-age formula."""
        athlete = MagicMock()
        athlete.id = uuid4()
        athlete.max_hr = None
        athlete.birthdate = date(1990, 1, 1)  # ~34 years old
        
        db = MagicMock()
        # Mock no activities with HR data
        mock_query = MagicMock()
        mock_query.scalar.return_value = None
        db.query.return_value.filter.return_value = mock_query
        
        with patch('services.performance_engine.calculate_age_at_date', return_value=34):
            result = estimate_max_hr(athlete, db, force_update=False)
        
        # 220 - 34 = 186
        assert result == 186


class TestEstimateVDOT:
    """Test VDOT estimation logic."""
    
    def test_respects_user_set_value(self):
        """Test that user-set VDOT is not overwritten."""
        athlete = MagicMock()
        athlete.vdot = 50.0  # User-set value
        db = MagicMock()
        
        result = estimate_vdot(athlete, db, force_update=False)
        
        assert result == 50.0
        # Should not query database
        db.query.assert_not_called()
    
    def test_calculates_from_personal_best(self):
        """Test VDOT calculation from PersonalBest."""
        athlete = MagicMock()
        athlete.id = uuid4()
        athlete.vdot = None
        
        # Mock a 5K PB of 20:00 (VDOT ~49)
        mock_pb = MagicMock()
        mock_pb.distance_meters = 5000
        mock_pb.time_seconds = 1200  # 20:00
        mock_pb.is_race = True
        
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_pb
        
        with patch('services.vdot_calculator.calculate_vdot_from_race_time', return_value=49.5):
            result = estimate_vdot(athlete, db, force_update=False)
        
        assert result == 49.5
        assert athlete.vdot == 49.5


class TestAutoEstimateThresholds:
    """Test combined threshold estimation."""
    
    def test_returns_both_values(self):
        """Test that both max_hr and vdot are returned."""
        athlete = MagicMock()
        athlete.id = uuid4()
        athlete.max_hr = 185
        athlete.vdot = 50.0
        athlete.birthdate = date(1980, 1, 1)
        
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 1
        
        with patch('services.performance_engine.calculate_age_at_date', return_value=44):
            result = auto_estimate_athlete_thresholds(athlete, db)
        
        assert 'max_hr' in result
        assert 'vdot' in result
        assert 'max_hr_source' in result
        assert 'vdot_source' in result
