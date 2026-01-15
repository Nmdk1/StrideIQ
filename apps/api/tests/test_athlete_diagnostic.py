"""
Unit tests for Athlete Diagnostic Report Service

Tests report generation, data extraction, and recommendation logic.

ADR-019: On-Demand Diagnostic Report
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock
from uuid import uuid4

from services.athlete_diagnostic import (
    FindingType,
    DataQuality,
    Phase,
    KeyFinding,
    PersonalBestEntry,
    WeekVolume,
    RecentRun,
    RaceEntry,
    DataAvailable,
    DataMissing,
    Recommendation,
    ExecutiveSummary,
    VolumeTrajectory,
    EfficiencyAnalysis,
    DataQualityAssessment,
    Recommendations,
    DiagnosticReport,
    format_pace,
    get_personal_best_profile,
    classify_phase,
    get_volume_trajectory,
    get_efficiency_trend,
    get_race_history,
    get_data_quality_assessment,
    generate_recommendations,
    generate_key_findings,
    generate_diagnostic_report,
    diagnostic_report_to_dict,
)


class TestEnums:
    """Test enum values."""
    
    def test_finding_types(self):
        """All finding types exist."""
        assert FindingType.POSITIVE.value == "positive"
        assert FindingType.WARNING.value == "warning"
        assert FindingType.INFO.value == "info"
    
    def test_data_quality_levels(self):
        """All data quality levels exist."""
        assert DataQuality.EXCELLENT.value == "excellent"
        assert DataQuality.GOOD.value == "good"
        assert DataQuality.LIMITED.value == "limited"
        assert DataQuality.INSUFFICIENT.value == "insufficient"
    
    def test_phase_values(self):
        """All phase types exist."""
        assert Phase.BUILD.value == "build"
        assert Phase.PEAK.value == "peak"
        assert Phase.TAPER.value == "taper"
        assert Phase.RECOVERY.value == "recovery"
        assert Phase.RETURN.value == "return"
        assert Phase.BASE.value == "base"


class TestFormatPace:
    """Test pace formatting."""
    
    def test_format_pace_integer_minutes(self):
        """Formats whole minute paces."""
        assert format_pace(300) == "5:00"  # 5:00/km
    
    def test_format_pace_with_seconds(self):
        """Formats paces with seconds."""
        assert format_pace(285) == "4:45"  # 4:45/km
        assert format_pace(227) == "3:47"  # 3:47/km
    
    def test_format_pace_single_digit_seconds(self):
        """Zero-pads single-digit seconds."""
        assert format_pace(303) == "5:03"  # 5:03/km


class TestClassifyPhase:
    """Test training phase classification."""
    
    def test_peak_phase(self):
        """High volume relative to peak is PEAK."""
        assert classify_phase(100, 110, 95) == Phase.PEAK.value
        assert classify_phase(110, 110, 105) == Phase.PEAK.value
    
    def test_build_phase(self):
        """Increasing volume below peak is BUILD."""
        assert classify_phase(80, 110, 70) == Phase.BUILD.value
    
    def test_taper_phase(self):
        """Decreasing volume below peak is TAPER."""
        assert classify_phase(80, 110, 90) == Phase.TAPER.value
    
    def test_recovery_phase(self):
        """Very low volume is RECOVERY."""
        assert classify_phase(30, 110, 40) == Phase.RECOVERY.value
    
    def test_return_phase(self):
        """Increasing from very low is RETURN."""
        # 50km increasing from 40km with 110 peak = ~45% of peak, increasing
        assert classify_phase(50, 110, 40) == Phase.RETURN.value
    
    def test_base_phase_no_peak(self):
        """Zero peak volume returns BASE."""
        assert classify_phase(50, 0, None) == Phase.BASE.value


class TestDataclasses:
    """Test dataclass instantiation."""
    
    def test_key_finding(self):
        """Can create KeyFinding."""
        kf = KeyFinding(type="positive", text="Test finding")
        assert kf.type == "positive"
        assert kf.text == "Test finding"
    
    def test_personal_best_entry(self):
        """Can create PersonalBestEntry."""
        pb = PersonalBestEntry(
            distance="5K",
            distance_meters=5000,
            time_seconds=1200,
            pace_per_km="4:00",
            is_race=True,
            validated=True
        )
        assert pb.distance == "5K"
        assert pb.time_seconds == 1200
    
    def test_week_volume(self):
        """Can create WeekVolume."""
        wv = WeekVolume(
            week="2026-W01",
            distance_km=80.5,
            duration_hrs=7.2,
            runs=6,
            phase="build"
        )
        assert wv.week == "2026-W01"
        assert wv.distance_km == 80.5
    
    def test_recommendation(self):
        """Can create Recommendation."""
        rec = Recommendation(
            action="Start check-ins",
            reason="Unlock correlations",
            effort="10 sec/day"
        )
        assert rec.action == "Start check-ins"
        assert rec.effort == "10 sec/day"
    
    def test_recommendation_no_effort(self):
        """Recommendation works without effort."""
        rec = Recommendation(
            action="Don't do X",
            reason="It's bad"
        )
        assert rec.effort is None


class TestGetPersonalBestProfile:
    """Test personal best extraction."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_extracts_pbs(self, mock_db):
        """Extracts PBs with pace calculation."""
        # Create mock PB
        mock_pb = MagicMock()
        mock_pb.distance_category = "5k"
        mock_pb.distance_meters = 5000
        mock_pb.time_seconds = 1200  # 20:00
        mock_pb.is_race = True
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_pb]
        
        result = get_personal_best_profile("test-athlete", mock_db)
        
        assert len(result) == 1
        assert result[0].distance == "5K"
        assert result[0].pace_per_km == "4:00"
        assert result[0].is_race is True
    
    def test_handles_empty(self, mock_db):
        """Returns empty list when no PBs."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        result = get_personal_best_profile("test-athlete", mock_db)
        
        assert result == []
    
    def test_formats_distance_names(self, mock_db):
        """Formats distance names correctly."""
        mock_pb1 = MagicMock()
        mock_pb1.distance_category = "half_marathon"
        mock_pb1.distance_meters = 21097
        mock_pb1.time_seconds = 5400
        mock_pb1.is_race = True
        
        mock_pb2 = MagicMock()
        mock_pb2.distance_category = "mile"
        mock_pb2.distance_meters = 1609
        mock_pb2.time_seconds = 360
        mock_pb2.is_race = True
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_pb1, mock_pb2]
        
        result = get_personal_best_profile("test-athlete", mock_db)
        
        assert result[0].distance == "Half Marathon"
        assert result[1].distance == "Mile"


class TestGetVolumeTrajectory:
    """Test volume trajectory calculation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_handles_no_activities(self, mock_db):
        """Returns empty trajectory for no activities."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        result = get_volume_trajectory("test-athlete", mock_db, weeks=12)
        
        assert result.weeks == []
        assert result.total_km == 0
        assert result.total_runs == 0
    
    def test_calculates_weekly_totals(self, mock_db):
        """Aggregates activities by week."""
        now = datetime.now(timezone.utc)
        
        mock_activity = MagicMock()
        mock_activity.start_time = now
        mock_activity.distance_m = 10000
        mock_activity.duration_s = 3600
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_activity]
        
        result = get_volume_trajectory("test-athlete", mock_db, weeks=12)
        
        assert result.total_km == 10.0
        assert result.total_runs == 1


class TestGetEfficiencyTrend:
    """Test efficiency trend calculation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_handles_no_hr_data(self, mock_db):
        """Returns message when no HR data."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        result = get_efficiency_trend("test-athlete", mock_db, weeks=12)
        
        assert result.average is None
        assert result.trend_pct is None
        assert "Insufficient" in result.interpretation
    
    def test_calculates_efficiency(self, mock_db):
        """Calculates efficiency from runs with HR."""
        now = datetime.now(timezone.utc)
        
        # Create 10 mock runs with HR
        runs = []
        for i in range(10):
            run = MagicMock()
            run.start_time = now - timedelta(days=i)
            run.name = f"Run {i}"
            run.distance_m = 10000
            run.duration_s = 3600
            run.avg_hr = 150
            runs.append(run)
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = runs
        
        result = get_efficiency_trend("test-athlete", mock_db, weeks=12)
        
        assert result.average is not None
        assert result.runs_with_hr == 10
        assert len(result.recent_runs) <= 10


class TestGetDataQualityAssessment:
    """Test data quality assessment."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_detects_missing_checkins(self, mock_db):
        """Flags missing check-in data."""
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        
        result = get_data_quality_assessment("test-athlete", mock_db)
        
        assert 'daily_checkins' in result.missing
        assert len(result.unanswerable_questions) > 0
    
    def test_classifies_activity_quality(self, mock_db):
        """Classifies activity data quality."""
        # Mock counts: 100 activities, 50 with HR, 5 PBs, 0 checkins
        mock_db.query.return_value.filter.return_value.count.side_effect = [100, 50, 5, 0, 0]
        
        result = get_data_quality_assessment("test-athlete", mock_db)
        
        assert 'activities' in result.available
        assert result.available['activities'].quality == 'excellent'


class TestGenerateRecommendations:
    """Test recommendation generation."""
    
    def test_recommends_checkins_when_missing(self):
        """Recommends check-ins when no data."""
        data_quality = DataQualityAssessment(
            available={},
            missing={'daily_checkins': DataMissing(impact="Cannot correlate")},
            unanswerable_questions=[]
        )
        efficiency = EfficiencyAnalysis(
            average=1.5, trend_pct=0, interpretation="Stable",
            recent_runs=[], runs_with_hr=10
        )
        volume = VolumeTrajectory(
            weeks=[], total_km=100, total_runs=10,
            peak_week="2026-W01", peak_volume_km=50, current_vs_peak_pct=-20
        )
        
        result = generate_recommendations(data_quality, efficiency, volume)
        
        assert len(result.high_priority) > 0
        assert any("check-in" in r.action.lower() for r in result.high_priority)
    
    def test_warns_against_chasing_metrics_in_recovery(self):
        """Warns against chasing metrics during recovery."""
        data_quality = DataQualityAssessment(
            available={}, missing={}, unanswerable_questions=[]
        )
        efficiency = EfficiencyAnalysis(
            average=1.5, trend_pct=-5.4, interpretation="Declining",
            recent_runs=[], runs_with_hr=10
        )
        volume = VolumeTrajectory(
            weeks=[WeekVolume(week="2026-W01", distance_km=30, duration_hrs=3, runs=3, phase="recovery")],
            total_km=30, total_runs=3,
            peak_week="2025-W47", peak_volume_km=100, current_vs_peak_pct=-70
        )
        
        result = generate_recommendations(data_quality, efficiency, volume)
        
        assert len(result.do_not_do) > 0


class TestGenerateKeyFindings:
    """Test key finding generation."""
    
    def test_positive_finding_for_pbs(self):
        """Generates positive finding for validated PBs."""
        data_quality = DataQualityAssessment(
            available={}, missing={}, unanswerable_questions=[]
        )
        efficiency = EfficiencyAnalysis(
            average=1.5, trend_pct=0, interpretation="Stable",
            recent_runs=[], runs_with_hr=10
        )
        volume = VolumeTrajectory(
            weeks=[], total_km=100, total_runs=10,
            peak_week="2026-W01", peak_volume_km=50, current_vs_peak_pct=-20
        )
        
        result = generate_key_findings(6, efficiency, data_quality, volume)
        
        positive_findings = [f for f in result if f.type == FindingType.POSITIVE.value]
        assert len(positive_findings) >= 1
    
    def test_warning_for_efficiency_decline(self):
        """Generates warning for efficiency decline."""
        data_quality = DataQualityAssessment(
            available={}, missing={}, unanswerable_questions=[]
        )
        efficiency = EfficiencyAnalysis(
            average=1.5, trend_pct=-5.4, interpretation="declining",
            recent_runs=[], runs_with_hr=10
        )
        volume = VolumeTrajectory(
            weeks=[], total_km=100, total_runs=10,
            peak_week="2026-W01", peak_volume_km=50, current_vs_peak_pct=-20
        )
        
        result = generate_key_findings(6, efficiency, data_quality, volume)
        
        warning_findings = [f for f in result if f.type == FindingType.WARNING.value]
        assert len(warning_findings) >= 1


class TestDiagnosticReportToDict:
    """Test report serialization."""
    
    def test_serializes_full_report(self):
        """Serializes complete report to dict."""
        report = DiagnosticReport(
            generated_at="2026-01-14T12:00:00Z",
            athlete_id="test-id",
            period_start="2025-07-01",
            period_end="2026-01-14",
            executive_summary=ExecutiveSummary(
                total_activities=100,
                total_distance_km=500,
                peak_volume_km=50,
                current_phase="recovery",
                efficiency_trend_pct=-5.4,
                key_findings=[KeyFinding(type="positive", text="Test")],
                date_range_start="2025-07-01",
                date_range_end="2026-01-14"
            ),
            personal_bests=[
                PersonalBestEntry(
                    distance="5K", distance_meters=5000,
                    time_seconds=1200, pace_per_km="4:00",
                    is_race=True, validated=True
                )
            ],
            volume_trajectory=VolumeTrajectory(
                weeks=[], total_km=500, total_runs=50,
                peak_week="2025-W47", peak_volume_km=50, current_vs_peak_pct=-40
            ),
            efficiency_analysis=EfficiencyAnalysis(
                average=1.5, trend_pct=-5.4, interpretation="Declining",
                recent_runs=[], runs_with_hr=30
            ),
            race_history=[],
            data_quality=DataQualityAssessment(
                available={'activities': DataAvailable(count=100, quality='excellent')},
                missing={},
                unanswerable_questions=[]
            ),
            recommendations=Recommendations(
                high_priority=[], medium_priority=[], do_not_do=[]
            )
        )
        
        result = diagnostic_report_to_dict(report)
        
        assert result['generated_at'] == "2026-01-14T12:00:00Z"
        assert result['executive_summary']['total_activities'] == 100
        assert len(result['personal_bests']) == 1
        assert result['personal_bests'][0]['distance'] == "5K"


class TestGenerateDiagnosticReport:
    """Test full report generation."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_generates_report_with_no_data(self, mock_db):
        """Handles athlete with no activities gracefully."""
        # Mock empty queries
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        result = generate_diagnostic_report("test-athlete", mock_db)
        
        assert result is not None
        assert result.athlete_id == "test-athlete"
        assert result.executive_summary.total_activities == 0


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_format_pace_zero(self):
        """Handles zero pace."""
        assert format_pace(0) == "0:00"
    
    def test_classify_phase_equal_volumes(self):
        """Handles equal current and previous volumes."""
        result = classify_phase(80, 100, 80)
        assert result in [Phase.TAPER.value, Phase.BUILD.value]
    
    def test_key_finding_empty_text(self):
        """KeyFinding works with empty text."""
        kf = KeyFinding(type="info", text="")
        assert kf.text == ""
