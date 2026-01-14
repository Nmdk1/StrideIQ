"""
Unit tests for Home Signals Aggregation Service

Tests signal aggregation, filtering, and prioritization.

ADR-013: Home Glance Signals Integration
"""

import pytest
from datetime import datetime, date
from unittest.mock import MagicMock, patch
from services.home_signals import (
    Signal,
    SignalType,
    SignalConfidence,
    SignalIcon,
    SignalsResponse,
    aggregate_signals,
    signals_to_dict,
    get_tsb_signal,
    get_efficiency_signal,
    # get_critical_speed_signal removed - archived
    get_fingerprint_signal,
    get_pace_decay_signal,
    MAX_SIGNALS,
    PRIORITY_TSB_RACE_READY,
    PRIORITY_EFFICIENCY_TREND,
    # PRIORITY_CRITICAL_SPEED removed - archived
    PRIORITY_FINGERPRINT_MATCH,
    PRIORITY_PACE_DECAY
)


class TestSignalDataclass:
    """Test Signal dataclass creation."""
    
    def test_create_signal(self):
        """Can create a Signal."""
        signal = Signal(
            id="test_signal",
            type=SignalType.TSB,
            priority=1,
            confidence=SignalConfidence.HIGH,
            icon=SignalIcon.BATTERY_FULL,
            color="green",
            title="Test Title",
            subtitle="Test subtitle",
            detail="Some detail",
            action_url="/analytics"
        )
        
        assert signal.id == "test_signal"
        assert signal.type == SignalType.TSB
        assert signal.confidence == SignalConfidence.HIGH
    
    def test_signal_optional_fields(self):
        """Signal can have None for optional fields."""
        signal = Signal(
            id="minimal",
            type=SignalType.EFFICIENCY,
            priority=3,
            confidence=SignalConfidence.MODERATE,
            icon=SignalIcon.TRENDING_UP,
            color="emerald",
            title="Efficiency up",
            subtitle="Last 4 weeks"
        )
        
        assert signal.detail is None
        assert signal.action_url is None


class TestSignalsResponse:
    """Test SignalsResponse creation and serialization."""
    
    def test_create_response(self):
        """Can create SignalsResponse."""
        signals = [
            Signal(
                id="s1",
                type=SignalType.TSB,
                priority=1,
                confidence=SignalConfidence.HIGH,
                icon=SignalIcon.BATTERY_FULL,
                color="green",
                title="Fresh",
                subtitle="Good window"
            )
        ]
        
        response = SignalsResponse(
            signals=signals,
            suppressed_count=2,
            last_updated=datetime(2026, 1, 14, 10, 30, 0)
        )
        
        assert len(response.signals) == 1
        assert response.suppressed_count == 2
    
    def test_signals_to_dict(self):
        """SignalsResponse serializes correctly."""
        signals = [
            Signal(
                id="test_id",
                type=SignalType.EFFICIENCY,
                priority=3,
                confidence=SignalConfidence.HIGH,
                icon=SignalIcon.TRENDING_UP,
                color="emerald",
                title="Efficiency up 4.2%",
                subtitle="Last 4 weeks",
                detail="p=0.02",
                action_url="/analytics"
            )
        ]
        
        response = SignalsResponse(
            signals=signals,
            suppressed_count=1,
            last_updated=datetime(2026, 1, 14, 10, 30, 0)
        )
        
        result = signals_to_dict(response)
        
        assert "signals" in result
        assert len(result["signals"]) == 1
        assert result["signals"][0]["id"] == "test_id"
        assert result["signals"][0]["type"] == "efficiency"
        assert result["signals"][0]["confidence"] == "high"
        assert result["signals"][0]["icon"] == "trending_up"
        assert result["suppressed_count"] == 1


class TestSignalTypes:
    """Test signal type enums."""
    
    def test_signal_types(self):
        """All signal types exist."""
        assert SignalType.TSB.value == "tsb"
        assert SignalType.EFFICIENCY.value == "efficiency"
        assert SignalType.FINGERPRINT.value == "fingerprint"
        # CRITICAL_SPEED removed - archived
        assert SignalType.PACE_DECAY.value == "pace_decay"
    
    def test_confidence_levels(self):
        """All confidence levels exist."""
        assert SignalConfidence.HIGH.value == "high"
        assert SignalConfidence.MODERATE.value == "moderate"
        assert SignalConfidence.LOW.value == "low"
    
    def test_icons(self):
        """Common icons exist."""
        assert SignalIcon.TRENDING_UP.value == "trending_up"
        assert SignalIcon.BATTERY_FULL.value == "battery_full"
        assert SignalIcon.TARGET.value == "target"


class TestPriorityConstants:
    """Test priority constants."""
    
    def test_priority_order(self):
        """Priorities are in correct order (lower = more important)."""
        assert PRIORITY_TSB_RACE_READY < PRIORITY_FINGERPRINT_MATCH
        assert PRIORITY_FINGERPRINT_MATCH < PRIORITY_EFFICIENCY_TREND
        assert PRIORITY_EFFICIENCY_TREND < PRIORITY_PACE_DECAY
        # PRIORITY_CRITICAL_SPEED removed - archived
    
    def test_max_signals_reasonable(self):
        """Max signals is a reasonable number."""
        assert MAX_SIGNALS >= 2
        assert MAX_SIGNALS <= 6


class TestAggregateSignals:
    """Test signal aggregation logic."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_aggregate_returns_response(self, mock_db):
        """Aggregate returns SignalsResponse."""
        with patch('services.home_signals.get_tsb_signal', return_value=None), \
             patch('services.home_signals.get_efficiency_signal', return_value=None), \
             patch('services.home_signals.get_fingerprint_signal', return_value=None), \
             patch('services.home_signals.get_pace_decay_signal', return_value=None):
            
            response = aggregate_signals("test-athlete", mock_db)
            
            assert isinstance(response, SignalsResponse)
            assert isinstance(response.signals, list)
            assert isinstance(response.suppressed_count, int)
    
    def test_aggregate_limits_signals(self, mock_db):
        """Aggregate limits to MAX_SIGNALS."""
        # Create more signals than MAX_SIGNALS
        signals = [
            Signal(id=f"s{i}", type=SignalType.TSB, priority=i,
                   confidence=SignalConfidence.HIGH, icon=SignalIcon.CHECKMARK,
                   color="green", title=f"Signal {i}", subtitle="Test")
            for i in range(MAX_SIGNALS + 3)
        ]
        
        with patch('services.home_signals.get_tsb_signal', return_value=signals[0]), \
             patch('services.home_signals.get_efficiency_signal', return_value=signals[1]), \
             patch('services.home_signals.get_fingerprint_signal', return_value=signals[2]), \
             patch('services.home_signals.get_pace_decay_signal', return_value=signals[3] if len(signals) > 3 else None):
            
            response = aggregate_signals("test-athlete", mock_db)
            
            assert len(response.signals) <= MAX_SIGNALS
    
    def test_aggregate_sorts_by_priority(self, mock_db):
        """Signals are sorted by priority."""
        low_priority = Signal(
            id="low", type=SignalType.PACE_DECAY, priority=10,
            confidence=SignalConfidence.HIGH, icon=SignalIcon.TIMER,
            color="orange", title="Low Priority", subtitle="Test"
        )
        high_priority = Signal(
            id="high", type=SignalType.TSB, priority=1,
            confidence=SignalConfidence.HIGH, icon=SignalIcon.BATTERY_FULL,
            color="green", title="High Priority", subtitle="Test"
        )
        
        with patch('services.home_signals.get_tsb_signal', return_value=high_priority), \
             patch('services.home_signals.get_efficiency_signal', return_value=None), \
             patch('services.home_signals.get_fingerprint_signal', return_value=None), \
             patch('services.home_signals.get_pace_decay_signal', return_value=low_priority):
            
            response = aggregate_signals("test-athlete", mock_db)
            
            if len(response.signals) >= 2:
                assert response.signals[0].priority <= response.signals[1].priority
    
    def test_aggregate_filters_low_confidence(self, mock_db):
        """Low confidence signals are filtered out."""
        low_conf = Signal(
            id="low_conf", type=SignalType.EFFICIENCY, priority=3,
            confidence=SignalConfidence.LOW, icon=SignalIcon.TRENDING_UP,
            color="blue", title="Low Confidence", subtitle="Test"
        )
        high_conf = Signal(
            id="high_conf", type=SignalType.TSB, priority=1,
            confidence=SignalConfidence.HIGH, icon=SignalIcon.BATTERY_FULL,
            color="green", title="High Confidence", subtitle="Test"
        )
        
        with patch('services.home_signals.get_tsb_signal', return_value=high_conf), \
             patch('services.home_signals.get_efficiency_signal', return_value=low_conf), \
             patch('services.home_signals.get_fingerprint_signal', return_value=None), \
             patch('services.home_signals.get_pace_decay_signal', return_value=None):
            
            response = aggregate_signals("test-athlete", mock_db)
            
            # Low confidence should be filtered
            ids = [s.id for s in response.signals]
            assert "high_conf" in ids
            # Low confidence should NOT be in the list
            assert "low_conf" not in ids


class TestTSBSignal:
    """Test TSB signal generation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_tsb_signal_returns_none_on_error(self, mock_db):
        """Returns None when training load calculation fails."""
        with patch('services.training_load.TrainingLoadCalculator') as mock_calc:
            mock_instance = mock_calc.return_value
            mock_instance.calculate_training_load.side_effect = Exception("DB error")
            
            result = get_tsb_signal("test-id", mock_db)
            
            # With the mock failing, it should return None
            assert result is None


class TestEfficiencySignal:
    """Test efficiency signal generation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_efficiency_signal_returns_none_on_error(self, mock_db):
        """Returns None when analytics fails."""
        with patch('services.efficiency_analytics.get_efficiency_trends') as mock_trends:
            mock_trends.side_effect = Exception("Error")
            
            result = get_efficiency_signal("test-id", mock_db)
            
            assert result is None


# TestCriticalSpeedSignal removed - archived to branch archive/cs-model-2026-01


class TestFingerprintSignal:
    """Test fingerprint signal generation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_fingerprint_signal_returns_none_on_error(self, mock_db):
        """Returns None when fingerprinting fails."""
        with patch('services.pre_race_fingerprinting.generate_readiness_profile') as mock_fp:
            mock_fp.side_effect = Exception("Error")
            
            result = get_fingerprint_signal("test-id", mock_db)
            
            assert result is None


class TestPaceDecaySignal:
    """Test pace decay signal generation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_decay_signal_returns_none_on_error(self, mock_db):
        """Returns None when decay analysis fails."""
        with patch('services.pace_decay.get_athlete_decay_profile') as mock_decay:
            mock_decay.side_effect = Exception("Error")
            
            result = get_pace_decay_signal("test-id", mock_db)
            
            assert result is None


class TestEdgeCases:
    """Test edge cases."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_no_signals_returns_empty(self, mock_db):
        """No signals returns empty list."""
        with patch('services.home_signals.get_tsb_signal', return_value=None), \
             patch('services.home_signals.get_efficiency_signal', return_value=None), \
             patch('services.home_signals.get_fingerprint_signal', return_value=None), \
             patch('services.home_signals.get_pace_decay_signal', return_value=None):
            
            response = aggregate_signals("test-athlete", mock_db)
            
            assert len(response.signals) == 0
            assert response.suppressed_count == 0
    
    def test_empty_athlete_id(self, mock_db):
        """Empty athlete ID handled gracefully."""
        with patch('services.home_signals.get_tsb_signal', return_value=None), \
             patch('services.home_signals.get_efficiency_signal', return_value=None), \
             patch('services.home_signals.get_fingerprint_signal', return_value=None), \
             patch('services.home_signals.get_pace_decay_signal', return_value=None):
            
            response = aggregate_signals("", mock_db)
            
            assert isinstance(response, SignalsResponse)


class TestSignalColors:
    """Test signal color assignments."""
    
    def test_valid_tailwind_colors(self):
        """Colors should be valid Tailwind color names."""
        valid_colors = {"green", "emerald", "blue", "orange", "red", "purple", "yellow", "pink"}
        
        # Create sample signals and verify colors
        signals = [
            Signal(id="s1", type=SignalType.TSB, priority=1,
                   confidence=SignalConfidence.HIGH, icon=SignalIcon.BATTERY_FULL,
                   color="green", title="Test", subtitle="Test"),
            Signal(id="s2", type=SignalType.EFFICIENCY, priority=2,
                   confidence=SignalConfidence.HIGH, icon=SignalIcon.TRENDING_UP,
                   color="emerald", title="Test", subtitle="Test"),
        ]
        
        for s in signals:
            assert s.color in valid_colors
