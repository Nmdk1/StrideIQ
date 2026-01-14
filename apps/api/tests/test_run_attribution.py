"""
Unit tests for Run Attribution Service

Tests attribution calculation for individual runs.

ADR-015: Why This Run? Activity Attribution
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch
from services.run_attribution import (
    AttributionSource,
    AttributionConfidence,
    RunAttribution,
    RunAttributionResult,
    get_run_attribution,
    run_attribution_to_dict,
    get_pace_decay_attribution,
    get_tsb_attribution,
    get_pre_state_attribution,
    get_efficiency_attribution,
    # get_cs_attribution removed - archived
    generate_summary,
    PRIORITY_PACE_DECAY,
    PRIORITY_TSB,
    PRIORITY_PRE_STATE,
    PRIORITY_EFFICIENCY,
    # PRIORITY_CRITICAL_SPEED removed - archived
    MAX_ATTRIBUTIONS,
)


class TestAttributionSource:
    """Test AttributionSource enum."""
    
    def test_source_values(self):
        """All source types exist."""
        assert AttributionSource.PACE_DECAY.value == "pace_decay"
        assert AttributionSource.TSB.value == "tsb"
        assert AttributionSource.PRE_STATE.value == "pre_state"
        assert AttributionSource.EFFICIENCY.value == "efficiency"
        # CRITICAL_SPEED removed - archived


class TestAttributionConfidence:
    """Test AttributionConfidence enum."""
    
    def test_confidence_values(self):
        """All confidence levels exist."""
        assert AttributionConfidence.HIGH.value == "high"
        assert AttributionConfidence.MODERATE.value == "moderate"
        assert AttributionConfidence.LOW.value == "low"


class TestRunAttribution:
    """Test RunAttribution dataclass."""
    
    def test_create_attribution(self):
        """Can create RunAttribution."""
        attr = RunAttribution(
            source="pace_decay",
            priority=1,
            confidence="high",
            title="Even Pacing",
            insight="Decay 3% — controlled execution.",
            icon="timer",
            color="green",
            data={"decay_percent": 3.0}
        )
        
        assert attr.source == "pace_decay"
        assert attr.priority == 1
        assert attr.title == "Even Pacing"


class TestRunAttributionResult:
    """Test RunAttributionResult dataclass."""
    
    def test_create_result(self):
        """Can create RunAttributionResult."""
        attrs = [
            RunAttribution(
                source="pace_decay",
                priority=1,
                confidence="high",
                title="Even Pacing",
                insight="Good pacing.",
                icon="timer",
                color="green",
                data={}
            )
        ]
        
        result = RunAttributionResult(
            activity_id="test-id",
            activity_name="Morning Run",
            attributions=attrs,
            summary="Good execution.",
            generated_at=datetime(2026, 1, 14, 10, 30)
        )
        
        assert result.activity_id == "test-id"
        assert len(result.attributions) == 1


class TestRunAttributionToDict:
    """Test serialization."""
    
    def test_serialization(self):
        """Serializes correctly."""
        attrs = [
            RunAttribution(
                source="pace_decay",
                priority=1,
                confidence="high",
                title="Even Pacing",
                insight="Decay 3% — controlled.",
                icon="timer",
                color="green",
                data={"decay_percent": 3.0}
            )
        ]
        
        result = RunAttributionResult(
            activity_id="test-id",
            activity_name="Morning Run",
            attributions=attrs,
            summary="Good execution.",
            generated_at=datetime(2026, 1, 14, 10, 30)
        )
        
        d = run_attribution_to_dict(result)
        
        assert "activity_id" in d
        assert "activity_name" in d
        assert "attributions" in d
        assert "summary" in d
        assert "generated_at" in d
        
        assert len(d["attributions"]) == 1
        assert d["attributions"][0]["source"] == "pace_decay"
        assert d["attributions"][0]["title"] == "Even Pacing"


class TestPriorityConstants:
    """Test priority constants."""
    
    def test_priority_order(self):
        """Priorities are in correct order."""
        assert PRIORITY_PACE_DECAY < PRIORITY_TSB
        assert PRIORITY_TSB < PRIORITY_PRE_STATE
        assert PRIORITY_PRE_STATE < PRIORITY_EFFICIENCY
        # PRIORITY_CRITICAL_SPEED removed - archived
    
    def test_max_attributions_reasonable(self):
        """Max attributions is reasonable."""
        assert MAX_ATTRIBUTIONS >= 3
        assert MAX_ATTRIBUTIONS <= 10


class TestGenerateSummary:
    """Test summary generation."""
    
    def test_summary_from_pace_decay(self):
        """Summary generated from pace decay."""
        attrs = [
            RunAttribution(
                source="pace_decay",
                priority=1,
                confidence="high",
                title="Even Pacing",
                insight="Good pacing.",
                icon="timer",
                color="green",
                data={"pattern": "even"}
            )
        ]
        
        summary = generate_summary(attrs)
        
        assert summary is not None
        assert len(summary) > 0
    
    def test_summary_from_tsb(self):
        """Summary generated from TSB."""
        attrs = [
            RunAttribution(
                source="tsb",
                priority=2,
                confidence="high",
                title="Peak Form",
                insight="Good freshness.",
                icon="battery",
                color="green",
                data={"zone": "race_ready"}
            )
        ]
        
        summary = generate_summary(attrs)
        
        assert summary is not None
    
    def test_empty_attributions(self):
        """Empty attributions returns None."""
        summary = generate_summary([])
        assert summary is None


class TestGetPaceDecayAttribution:
    """Test pace decay attribution."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    @pytest.fixture
    def mock_activity(self):
        activity = MagicMock()
        activity.id = "test-id"
        activity.athlete_id = "athlete-id"
        activity.name = "Test Run"
        return activity
    
    def test_returns_none_insufficient_splits(self, mock_db, mock_activity):
        """Returns None if < 3 splits."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        result = get_pace_decay_attribution(mock_activity, mock_db)
        
        assert result is None


class TestGetTSBAttribution:
    """Test TSB attribution."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_returns_none_on_error(self, mock_db):
        """Returns None when calculation fails."""
        with patch('services.training_load.TrainingLoadCalculator') as mock_calc:
            mock_instance = mock_calc.return_value
            mock_instance.calculate_training_load.side_effect = Exception("Error")
            
            result = get_tsb_attribution("athlete-id", date.today(), mock_db)
            
            # With the mock failing, should return None
            assert result is None


class TestGetPreStateAttribution:
    """Test pre-state attribution."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_returns_none_no_checkin(self, mock_db):
        """Returns None if no check-in."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = get_pre_state_attribution("athlete-id", date.today(), mock_db)
        
        assert result is None


class TestGetEfficiencyAttribution:
    """Test efficiency attribution."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    @pytest.fixture
    def mock_activity(self):
        activity = MagicMock()
        activity.id = "test-id"
        activity.athlete_id = "athlete-id"
        activity.avg_hr = 150
        activity.distance_m = 10000
        activity.duration_s = 3600
        activity.start_time = datetime.now()
        return activity
    
    def test_returns_none_no_hr(self, mock_db):
        """Returns None if no HR data."""
        activity = MagicMock()
        activity.avg_hr = None
        activity.distance_m = 10000
        activity.duration_s = 3600
        
        result = get_efficiency_attribution(activity, mock_db)
        
        assert result is None
    
    def test_returns_none_short_run(self, mock_db):
        """Returns None for very short runs."""
        activity = MagicMock()
        activity.avg_hr = 150
        activity.distance_m = 500
        activity.duration_s = 300
        
        result = get_efficiency_attribution(activity, mock_db)
        
        assert result is None


# TestGetCSAttribution removed - archived to branch archive/cs-model-2026-01


class TestGetRunAttribution:
    """Test main attribution function."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_returns_none_activity_not_found(self, mock_db):
        """Returns None if activity not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = get_run_attribution("activity-id", "athlete-id", mock_db)
        
        assert result is None
    
    def test_returns_result_with_activity(self, mock_db):
        """Returns result when activity exists."""
        # Mock activity
        activity = MagicMock()
        activity.id = "activity-id"
        activity.athlete_id = "athlete-id"
        activity.name = "Morning Run"
        activity.start_time = datetime.now()
        activity.distance_m = 10000
        activity.duration_s = 3600
        activity.avg_hr = None
        
        mock_db.query.return_value.filter.return_value.first.return_value = activity
        
        # Mock splits query to return empty (no pace decay)
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        with patch('services.run_attribution.get_tsb_attribution', return_value=None), \
             patch('services.run_attribution.get_pre_state_attribution', return_value=None), \
             patch('services.run_attribution.get_efficiency_attribution', return_value=None):
            
            result = get_run_attribution("activity-id", "athlete-id", mock_db)
            
            assert result is not None
            assert result.activity_id == "activity-id"


class TestEdgeCases:
    """Test edge cases."""
    
    def test_empty_data_dict(self):
        """Attribution with empty data."""
        attr = RunAttribution(
            source="tsb",
            priority=2,
            confidence="high",
            title="Fresh",
            insight="Good form.",
            icon="battery",
            color="green",
            data={}
        )
        
        assert attr.data == {}
    
    def test_all_colors_valid(self):
        """Colors are valid Tailwind colors."""
        valid_colors = {"green", "emerald", "blue", "orange", "yellow", "slate", "red"}
        
        attrs = [
            RunAttribution(
                source="test",
                priority=1,
                confidence="high",
                title="Test",
                insight="Test",
                icon="test",
                color="green",
                data={}
            ),
            RunAttribution(
                source="test2",
                priority=2,
                confidence="moderate",
                title="Test2",
                insight="Test2",
                icon="test",
                color="yellow",
                data={}
            ),
        ]
        
        for attr in attrs:
            assert attr.color in valid_colors


class TestAttributionIcons:
    """Test icon assignments."""
    
    def test_pace_decay_icon(self):
        """Pace decay uses timer icon."""
        attr = RunAttribution(
            source="pace_decay",
            priority=1,
            confidence="high",
            title="Even",
            insight="Good",
            icon="timer",
            color="green",
            data={}
        )
        assert attr.icon == "timer"
    
    def test_tsb_icon(self):
        """TSB uses battery icon."""
        attr = RunAttribution(
            source="tsb",
            priority=2,
            confidence="high",
            title="Fresh",
            insight="Good",
            icon="battery",
            color="green",
            data={}
        )
        assert attr.icon == "battery"
