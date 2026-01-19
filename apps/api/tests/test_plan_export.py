"""
Tests for Plan Export Service

Tests the training plan export functionality:
- CSV export (Google Sheets compatible)
- JSON export (full backup)
- Unit conversions
- Filename sanitization
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import date, datetime
import json
import csv
import io

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.plan_export import (
    export_plan_to_csv,
    export_plan_to_json,
    export_active_plan_to_csv,
    _format_time,
    _format_pace,
    _clean_description,
    _sanitize_filename,
    ExportResult,
)


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_format_time_hours(self):
        """Should format time with hours correctly."""
        assert _format_time(3661) == "1:01:01"
        assert _format_time(7200) == "2:00:00"
        assert _format_time(3723) == "1:02:03"
    
    def test_format_time_minutes_only(self):
        """Should format time without hours correctly."""
        assert _format_time(125) == "2:05"
        assert _format_time(600) == "10:00"
        assert _format_time(59) == "0:59"
    
    def test_format_pace(self):
        """Should format pace as M:SS."""
        assert _format_pace(360) == "6:00"
        assert _format_pace(420) == "7:00"
        assert _format_pace(385) == "6:25"
        assert _format_pace(330) == "5:30"
    
    def test_clean_description_newlines(self):
        """Should replace newlines with spaces."""
        result = _clean_description("Line 1\nLine 2\rLine 3")
        assert "\n" not in result
        assert "\r" not in result
        assert "Line 1" in result
        assert "Line 2" in result
    
    def test_clean_description_multiple_spaces(self):
        """Should collapse multiple spaces."""
        result = _clean_description("Word1    Word2   Word3")
        assert "    " not in result
        assert "   " not in result
    
    def test_clean_description_none(self):
        """Should handle None gracefully."""
        assert _clean_description(None) == ""
    
    def test_sanitize_filename_invalid_chars(self):
        """Should remove invalid filename characters."""
        result = _sanitize_filename("Plan: My/Test\\Plan?")
        assert ":" not in result
        assert "/" not in result
        assert "\\" not in result
        assert "?" not in result
    
    def test_sanitize_filename_spaces(self):
        """Should replace spaces with underscores."""
        result = _sanitize_filename("My Training Plan")
        assert " " not in result
        assert "_" in result
    
    def test_sanitize_filename_length(self):
        """Should limit filename length."""
        long_name = "A" * 100
        result = _sanitize_filename(long_name)
        assert len(result) <= 50


class TestCSVExport:
    """Tests for CSV export functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()
    
    @pytest.fixture
    def mock_plan(self):
        """Create a mock training plan."""
        plan = MagicMock()
        plan.id = uuid4()
        plan.athlete_id = uuid4()
        plan.name = "Boston Marathon 2026"
        plan.goal_race_name = "Boston Marathon"
        plan.goal_race_date = date(2026, 4, 20)
        plan.goal_time_seconds = 10800  # 3:00:00
        plan.total_weeks = 16
        return plan
    
    @pytest.fixture
    def mock_workouts(self, mock_plan):
        """Create mock workouts."""
        workouts = []
        for i in range(7):
            w = MagicMock()
            w.id = uuid4()
            w.plan_id = mock_plan.id
            w.scheduled_date = date(2026, 1, 6 + i)
            w.week_number = 1
            w.day_of_week = i  # 0=Sun to 6=Sat
            w.phase = "base"
            w.workout_type = "easy" if i < 3 else "threshold"
            w.title = f"Workout {i+1}"
            w.description = f"Description for workout {i+1}"
            w.target_distance_km = 8.0 if i < 3 else 10.0
            w.target_duration_minutes = 50 if i < 3 else 60
            w.target_pace_per_km_seconds = 330 if i < 3 else 300  # 5:30/km, 5:00/km
            w.target_pace_per_km_seconds_max = None
            w.completed = False
            w.skipped = False
            w.coach_notes = "Stay relaxed"
            w.athlete_notes = None
            workouts.append(w)
        return workouts
    
    def test_export_csv_plan_not_found(self, mock_db):
        """Should return error when plan not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = export_plan_to_csv(
            plan_id=uuid4(),
            athlete_id=uuid4(),
            db=mock_db
        )
        
        assert not result.success
        assert "not found" in result.error.lower()
    
    def test_export_csv_no_workouts(self, mock_db, mock_plan):
        """Should return error when no workouts found."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        result = export_plan_to_csv(
            plan_id=mock_plan.id,
            athlete_id=mock_plan.athlete_id,
            db=mock_db
        )
        
        assert not result.success
        assert "no workouts" in result.error.lower()
    
    def test_export_csv_success(self, mock_db, mock_plan, mock_workouts):
        """Should successfully export plan to CSV."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_workouts
        
        result = export_plan_to_csv(
            plan_id=mock_plan.id,
            athlete_id=mock_plan.athlete_id,
            db=mock_db,
            units="imperial"
        )
        
        assert result.success
        assert result.format == "csv"
        assert result.row_count == 7
        assert "Boston" in result.filename
        assert ".csv" in result.filename
    
    def test_export_csv_content_has_headers(self, mock_db, mock_plan, mock_workouts):
        """CSV content should have proper headers."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_workouts
        
        result = export_plan_to_csv(
            plan_id=mock_plan.id,
            athlete_id=mock_plan.athlete_id,
            db=mock_db,
            units="imperial"
        )
        
        assert "Week" in result.content
        assert "Date" in result.content
        assert "Phase" in result.content
        assert "Distance (mi)" in result.content
    
    def test_export_csv_metric_units(self, mock_db, mock_plan, mock_workouts):
        """CSV should use metric units when specified."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_workouts
        
        result = export_plan_to_csv(
            plan_id=mock_plan.id,
            athlete_id=mock_plan.athlete_id,
            db=mock_db,
            units="metric"
        )
        
        assert "Distance (km)" in result.content
        assert "Pace (min/km)" in result.content
    
    def test_export_csv_valid_csv_format(self, mock_db, mock_plan, mock_workouts):
        """Exported content should be valid CSV."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_workouts
        
        result = export_plan_to_csv(
            plan_id=mock_plan.id,
            athlete_id=mock_plan.athlete_id,
            db=mock_db
        )
        
        # Should be parseable as CSV
        reader = csv.reader(io.StringIO(result.content))
        rows = list(reader)
        
        # Should have metadata rows + header + data rows
        assert len(rows) >= 8  # 4 metadata + 1 blank + 1 header + 7 workouts


class TestJSONExport:
    """Tests for JSON export functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()
    
    @pytest.fixture
    def mock_plan(self):
        """Create a mock training plan."""
        plan = MagicMock()
        plan.id = uuid4()
        plan.athlete_id = uuid4()
        plan.name = "Boston Marathon 2026"
        plan.status = "active"
        plan.goal_race_name = "Boston Marathon"
        plan.goal_race_date = date(2026, 4, 20)
        plan.goal_race_distance_m = 42195
        plan.goal_time_seconds = 10800
        plan.plan_start_date = date(2026, 1, 1)
        plan.plan_end_date = date(2026, 4, 20)
        plan.total_weeks = 16
        plan.baseline_vdot = 55.0
        plan.plan_type = "marathon"
        plan.generation_method = "ai"
        return plan
    
    @pytest.fixture
    def mock_workouts(self, mock_plan):
        """Create mock workouts."""
        workouts = []
        for i in range(3):
            w = MagicMock()
            w.id = uuid4()
            w.plan_id = mock_plan.id
            w.scheduled_date = date(2026, 1, 6 + i)
            w.week_number = 1
            w.day_of_week = i
            w.workout_type = "easy"
            w.workout_subtype = None
            w.title = f"Workout {i+1}"
            w.description = f"Description {i+1}"
            w.phase = "base"
            w.phase_week = 1
            w.target_duration_minutes = 50
            w.target_distance_km = 8.0
            w.target_pace_per_km_seconds = 330
            w.target_hr_min = 120
            w.target_hr_max = 140
            w.segments = [{"type": "steady", "duration_min": 50}]
            w.completed = False
            w.skipped = False
            w.skip_reason = None
            w.coach_notes = "Stay relaxed"
            w.athlete_notes = None
            workouts.append(w)
        return workouts
    
    def test_export_json_success(self, mock_db, mock_plan, mock_workouts):
        """Should successfully export plan to JSON."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_workouts
        
        result = export_plan_to_json(
            plan_id=mock_plan.id,
            athlete_id=mock_plan.athlete_id,
            db=mock_db
        )
        
        assert result.success
        assert result.format == "json"
        assert result.row_count == 3
        assert ".json" in result.filename
    
    def test_export_json_valid_format(self, mock_db, mock_plan, mock_workouts):
        """Exported content should be valid JSON."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_workouts
        
        result = export_plan_to_json(
            plan_id=mock_plan.id,
            athlete_id=mock_plan.athlete_id,
            db=mock_db
        )
        
        # Should be parseable as JSON
        data = json.loads(result.content)
        
        assert "export_version" in data
        assert "plan" in data
        assert "workouts" in data
        assert len(data["workouts"]) == 3
    
    def test_export_json_includes_segments(self, mock_db, mock_plan, mock_workouts):
        """Should include workout segments when requested."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_workouts
        
        result = export_plan_to_json(
            plan_id=mock_plan.id,
            athlete_id=mock_plan.athlete_id,
            db=mock_db,
            include_segments=True
        )
        
        data = json.loads(result.content)
        
        # First workout should have segments
        assert "segments" in data["workouts"][0]


class TestActivePlanExport:
    """Tests for active plan export."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()
    
    def test_export_no_active_plan(self, mock_db):
        """Should return error when no active plan exists."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        
        result = export_active_plan_to_csv(
            athlete_id=uuid4(),
            db=mock_db
        )
        
        assert not result.success
        assert "no active plan" in result.error.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
