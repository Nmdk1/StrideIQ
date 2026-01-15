"""
Unit tests for Calendar Signals Service

Tests day badges and week trajectories for calendar visualization.

ADR-016: Calendar Signals - Day Badges + Week Trajectory
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch
from services.calendar_signals import (
    SignalType,
    SignalConfidence,
    TrajectoryTrend,
    DayBadge,
    WeekTrajectory,
    CalendarSignalsResponse,
    get_day_badges,
    get_week_trajectory,
    get_calendar_signals,
    calendar_signals_to_dict,
    get_efficiency_badge,
    get_pace_decay_badge,
    get_tsb_badge,
    get_pr_match_badge,
    MAX_BADGES_PER_DAY,
)


class TestSignalType:
    """Test SignalType enum."""
    
    def test_signal_type_values(self):
        """All signal types exist."""
        assert SignalType.EFFICIENCY_SPIKE.value == "efficiency_spike"
        assert SignalType.EFFICIENCY_DROP.value == "efficiency_drop"
        assert SignalType.DECAY_RISK.value == "decay_risk"
        assert SignalType.EVEN_PACING.value == "even_pacing"
        assert SignalType.PR_MATCH.value == "pr_match"
        assert SignalType.FRESH_FORM.value == "fresh_form"
        assert SignalType.FATIGUED.value == "fatigued"
        assert SignalType.AT_CS.value == "at_cs"


class TestSignalConfidence:
    """Test SignalConfidence enum."""
    
    def test_confidence_values(self):
        """All confidence levels exist."""
        assert SignalConfidence.HIGH.value == "high"
        assert SignalConfidence.MODERATE.value == "moderate"
        assert SignalConfidence.LOW.value == "low"


class TestTrajectoryTrend:
    """Test TrajectoryTrend enum."""
    
    def test_trend_values(self):
        """All trend values exist."""
        assert TrajectoryTrend.POSITIVE.value == "positive"
        assert TrajectoryTrend.CAUTION.value == "caution"
        assert TrajectoryTrend.NEUTRAL.value == "neutral"


class TestDayBadge:
    """Test DayBadge dataclass."""
    
    def test_create_badge(self):
        """Can create DayBadge."""
        badge = DayBadge(
            type="efficiency_spike",
            badge="Eff ↑",
            color="emerald",
            icon="trending_up",
            confidence="high",
            tooltip="Efficiency 8% above average",
            priority=2
        )
        
        assert badge.type == "efficiency_spike"
        assert badge.badge == "Eff ↑"
        assert badge.color == "emerald"
        assert badge.priority == 2
    
    def test_default_priority(self):
        """Default priority is 5."""
        badge = DayBadge(
            type="test",
            badge="T",
            color="slate",
            icon="info",
            confidence="low",
            tooltip="Test"
        )
        
        assert badge.priority == 5


class TestWeekTrajectory:
    """Test WeekTrajectory dataclass."""
    
    def test_create_trajectory(self):
        """Can create WeekTrajectory."""
        trajectory = WeekTrajectory(
            summary="On track — efficiency trending up.",
            trend="positive",
            details={"efficiency_trend": "+4%"}
        )
        
        assert trajectory.summary == "On track — efficiency trending up."
        assert trajectory.trend == "positive"
        assert trajectory.details["efficiency_trend"] == "+4%"
    
    def test_default_details(self):
        """Details defaults to empty dict."""
        trajectory = WeekTrajectory(
            summary="Test",
            trend="neutral"
        )
        
        assert trajectory.details == {}


class TestCalendarSignalsResponse:
    """Test CalendarSignalsResponse dataclass."""
    
    def test_create_response(self):
        """Can create CalendarSignalsResponse."""
        badge = DayBadge(
            type="efficiency_spike",
            badge="Eff ↑",
            color="emerald",
            icon="trending_up",
            confidence="high",
            tooltip="Test"
        )
        
        trajectory = WeekTrajectory(
            summary="On track.",
            trend="positive"
        )
        
        response = CalendarSignalsResponse(
            day_signals={"2026-01-14": [badge]},
            week_trajectories={"2026-W03": trajectory}
        )
        
        assert len(response.day_signals) == 1
        assert len(response.week_trajectories) == 1


class TestCalendarSignalsToDict:
    """Test serialization."""
    
    def test_serialization(self):
        """Serializes correctly."""
        badge = DayBadge(
            type="efficiency_spike",
            badge="Eff ↑",
            color="emerald",
            icon="trending_up",
            confidence="high",
            tooltip="Test tooltip"
        )
        
        trajectory = WeekTrajectory(
            summary="On track.",
            trend="positive",
            details={"eff": "+4%"}
        )
        
        response = CalendarSignalsResponse(
            day_signals={"2026-01-14": [badge]},
            week_trajectories={"2026-W03": trajectory}
        )
        
        d = calendar_signals_to_dict(response)
        
        assert "day_signals" in d
        assert "week_trajectories" in d
        assert "2026-01-14" in d["day_signals"]
        assert len(d["day_signals"]["2026-01-14"]) == 1
        assert d["day_signals"]["2026-01-14"][0]["badge"] == "Eff ↑"
        assert d["week_trajectories"]["2026-W03"]["summary"] == "On track."


class TestMaxBadgesPerDay:
    """Test badge limit constant."""
    
    def test_max_badges_reasonable(self):
        """Max badges is reasonable."""
        assert MAX_BADGES_PER_DAY >= 1
        assert MAX_BADGES_PER_DAY <= 5


class TestGetEfficiencyBadge:
    """Test efficiency badge generation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_returns_none_no_activities(self, mock_db):
        """Returns None when no activities."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = get_efficiency_badge("athlete-id", date.today(), mock_db)
        
        assert result is None


class TestGetPaceDecayBadge:
    """Test pace decay badge generation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_returns_none_no_long_runs(self, mock_db):
        """Returns None when no long runs."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = get_pace_decay_badge("athlete-id", date.today(), mock_db)
        
        assert result is None


class TestGetTSBBadge:
    """Test TSB badge generation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_returns_none_on_error(self, mock_db):
        """Returns None when TSB calc fails."""
        with patch('services.training_load.TrainingLoadCalculator') as mock_calc:
            mock_instance = mock_calc.return_value
            mock_instance.calculate_training_load.side_effect = Exception("Error")
            
            result = get_tsb_badge("athlete-id", date.today(), mock_db)
            
            assert result is None


class TestGetPRMatchBadge:
    """Test PR match badge generation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_returns_none_no_checkin(self, mock_db):
        """Returns None when no check-in."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = get_pr_match_badge("athlete-id", date.today(), mock_db)
        
        assert result is None


class TestGetDayBadges:
    """Test day badge aggregation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_limits_badges(self, mock_db):
        """Limits badges to MAX_BADGES_PER_DAY."""
        # All badge functions will return None with no data
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = get_day_badges("athlete-id", date.today(), mock_db)
        
        assert len(result) <= MAX_BADGES_PER_DAY


class TestGetWeekTrajectory:
    """Test week trajectory generation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_returns_none_no_activities(self, mock_db):
        """Returns None when no activities."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = get_week_trajectory("athlete-id", date.today(), mock_db)
        
        assert result is None


class TestGetCalendarSignals:
    """Test main calendar signals function."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_returns_response(self, mock_db):
        """Returns CalendarSignalsResponse."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = get_calendar_signals(
            "athlete-id",
            date.today(),
            date.today() + timedelta(days=7),
            mock_db
        )
        
        assert isinstance(result, CalendarSignalsResponse)
        assert isinstance(result.day_signals, dict)
        assert isinstance(result.week_trajectories, dict)


class TestBadgeColors:
    """Test badge colors are valid."""
    
    def test_valid_colors(self):
        """Badge colors are valid Tailwind colors."""
        valid_colors = {"emerald", "green", "blue", "orange", "yellow", "purple", "slate"}
        
        # Test efficiency spike
        badge1 = DayBadge(
            type="efficiency_spike",
            badge="Eff ↑",
            color="emerald",
            icon="trending_up",
            confidence="high",
            tooltip="Test"
        )
        
        # Test decay risk
        badge2 = DayBadge(
            type="decay_risk",
            badge="Fade",
            color="orange",
            icon="trending_down",
            confidence="high",
            tooltip="Test"
        )
        
        assert badge1.color in valid_colors
        assert badge2.color in valid_colors


class TestTrajectoryTrendColors:
    """Test trajectory trend mappings."""
    
    def test_positive_trend(self):
        """Positive trend exists."""
        trajectory = WeekTrajectory(
            summary="On track.",
            trend=TrajectoryTrend.POSITIVE.value
        )
        
        assert trajectory.trend == "positive"
    
    def test_caution_trend(self):
        """Caution trend exists."""
        trajectory = WeekTrajectory(
            summary="Watch fatigue.",
            trend=TrajectoryTrend.CAUTION.value
        )
        
        assert trajectory.trend == "caution"
    
    def test_neutral_trend(self):
        """Neutral trend exists."""
        trajectory = WeekTrajectory(
            summary="Building week.",
            trend=TrajectoryTrend.NEUTRAL.value
        )
        
        assert trajectory.trend == "neutral"


class TestBadgeIcons:
    """Test badge icons."""
    
    def test_valid_icons(self):
        """Badge icons are valid."""
        valid_icons = {
            "trending_up", "trending_down", "check", "target",
            "zap", "alert_triangle", "alert_circle", "info"
        }
        
        badge = DayBadge(
            type="efficiency_spike",
            badge="Eff ↑",
            color="emerald",
            icon="trending_up",
            confidence="high",
            tooltip="Test"
        )
        
        assert badge.icon in valid_icons


# =============================================================================
# ADR-021: Calendar Signals Endpoint Routing Tests
# =============================================================================

class TestCalendarSignalsEndpointRouting:
    """
    Test that /calendar/signals endpoint is correctly routed.
    
    ADR-021: Previously, /calendar/signals was matching /{calendar_date}
    route because of FastAPI route ordering. This caused 422 errors.
    """
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    @pytest.fixture
    def mock_user(self):
        """Create mock authenticated user."""
        user = MagicMock()
        user.id = "test-user-id"
        return user
    
    def test_signals_endpoint_exists(self):
        """Verify /signals endpoint is defined in router."""
        from routers.calendar import router
        
        # Check that /signals route exists (with /calendar prefix)
        routes = [route.path for route in router.routes]
        assert any("/signals" in path for path in routes), f"No signals route found in {routes}"
    
    def test_signals_before_date_route(self):
        """Verify /signals is defined before /{calendar_date} in route order."""
        from routers.calendar import router
        
        routes = [route.path for route in router.routes]
        
        # Find indices (routes include /calendar prefix)
        signals_idx = None
        date_idx = None
        
        for i, path in enumerate(routes):
            if "/signals" in path and "{calendar_date}" not in path:
                signals_idx = i
            elif "/{calendar_date}" in path and "/notes" not in path:
                date_idx = i
        
        assert signals_idx is not None, f"/signals route not found in {routes}"
        assert date_idx is not None, f"/{{calendar_date}} route not found in {routes}"
        assert signals_idx < date_idx, f"/signals (idx {signals_idx}) must be before /{{calendar_date}} (idx {date_idx})"
    
    def test_endpoint_returns_empty_on_date_range_too_large(self, mock_db, mock_user):
        """Endpoint returns 200 with empty result for date range > 90 days."""
        from routers.calendar import get_calendar_signals_endpoint
        from datetime import date, timedelta
        
        start = date.today()
        end = start + timedelta(days=100)  # > 90 days
        
        # Mock feature flag
        with patch('routers.calendar.is_feature_enabled') as mock_flag:
            mock_flag.return_value = True
            
            result = get_calendar_signals_endpoint(
                start_date=start,
                end_date=end,
                current_user=mock_user,
                db=mock_db
            )
        
        assert result["day_signals"] == {}
        assert result["week_trajectories"] == {}
        assert "90 days" in result.get("message", "")
    
    def test_endpoint_returns_empty_on_end_before_start(self, mock_db, mock_user):
        """Endpoint returns 200 with empty result when end_date < start_date."""
        from routers.calendar import get_calendar_signals_endpoint
        from datetime import date
        
        start = date(2026, 1, 15)
        end = date(2026, 1, 1)  # Before start
        
        with patch('routers.calendar.is_feature_enabled') as mock_flag:
            mock_flag.return_value = True
            
            result = get_calendar_signals_endpoint(
                start_date=start,
                end_date=end,
                current_user=mock_user,
                db=mock_db
            )
        
        assert result["day_signals"] == {}
        assert result["week_trajectories"] == {}
        assert "End date" in result.get("message", "")
    
    def test_endpoint_returns_empty_when_feature_disabled(self, mock_db, mock_user):
        """Endpoint returns 200 with message when feature flag disabled."""
        from routers.calendar import get_calendar_signals_endpoint
        from datetime import date
        
        start = date(2026, 1, 1)
        end = date(2026, 1, 31)
        
        with patch('routers.calendar.is_feature_enabled') as mock_flag:
            mock_flag.return_value = False
            
            result = get_calendar_signals_endpoint(
                start_date=start,
                end_date=end,
                current_user=mock_user,
                db=mock_db
            )
        
        assert result["day_signals"] == {}
        assert result["week_trajectories"] == {}
        assert "not enabled" in result.get("message", "")
