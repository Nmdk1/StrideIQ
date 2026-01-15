"""
Athlete Diagnostic Report Service

Generates comprehensive, plain-language diagnostic reports for athletes.
Provides insights into training status, progress, data quality, and recommendations.

ADR-019: On-Demand Diagnostic Report
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Athlete, Activity, PersonalBest, DailyCheckin


class FindingType(str, Enum):
    """Types of findings in the report."""
    POSITIVE = "positive"
    WARNING = "warning"
    INFO = "info"


class DataQuality(str, Enum):
    """Data quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class Phase(str, Enum):
    """Training phase classification."""
    BUILD = "build"
    PEAK = "peak"
    TAPER = "taper"
    RECOVERY = "recovery"
    RETURN = "return"
    BASE = "base"


@dataclass
class KeyFinding:
    """A key finding for the executive summary."""
    type: str  # positive, warning, info
    text: str


@dataclass
class PersonalBestEntry:
    """A personal best record."""
    distance: str
    distance_meters: int
    time_seconds: float
    pace_per_km: str
    is_race: bool
    validated: bool


@dataclass
class WeekVolume:
    """Weekly volume data."""
    week: str
    distance_km: float
    duration_hrs: float
    runs: int
    phase: str


@dataclass
class RecentRun:
    """Recent run with efficiency data."""
    date: str
    name: str
    distance_km: float
    pace_min_km: float
    avg_hr: int
    efficiency: float


@dataclass
class RaceEntry:
    """Race history entry."""
    date: str
    name: str
    distance_km: float
    time_seconds: float
    pace_per_km: str
    notes: str


@dataclass 
class DataAvailable:
    """Available data category."""
    count: int
    quality: str


@dataclass
class DataMissing:
    """Missing data category."""
    impact: str


@dataclass
class Recommendation:
    """A recommendation for the athlete."""
    action: str
    reason: str
    effort: Optional[str] = None


@dataclass
class ExecutiveSummary:
    """Executive summary of training status."""
    total_activities: int
    total_distance_km: float
    peak_volume_km: float
    current_phase: str
    efficiency_trend_pct: Optional[float]
    key_findings: List[KeyFinding]
    date_range_start: str
    date_range_end: str


@dataclass
class VolumeTrajectory:
    """Volume trajectory over time."""
    weeks: List[WeekVolume]
    total_km: float
    total_runs: int
    peak_week: str
    peak_volume_km: float
    current_vs_peak_pct: float


@dataclass
class EfficiencyAnalysis:
    """Efficiency trend analysis."""
    average: Optional[float]
    trend_pct: Optional[float]
    interpretation: str
    recent_runs: List[RecentRun]
    runs_with_hr: int


@dataclass
class DataQualityAssessment:
    """Assessment of data quality and gaps."""
    available: Dict[str, DataAvailable]
    missing: Dict[str, DataMissing]
    unanswerable_questions: List[str]


@dataclass
class Recommendations:
    """Prioritized recommendations."""
    high_priority: List[Recommendation]
    medium_priority: List[Recommendation]
    do_not_do: List[Recommendation]


@dataclass
class DiagnosticReport:
    """Full diagnostic report."""
    generated_at: str
    athlete_id: str
    period_start: str
    period_end: str
    executive_summary: ExecutiveSummary
    personal_bests: List[PersonalBestEntry]
    volume_trajectory: VolumeTrajectory
    efficiency_analysis: EfficiencyAnalysis
    race_history: List[RaceEntry]
    data_quality: DataQualityAssessment
    recommendations: Recommendations


def format_pace(seconds_per_km: float) -> str:
    """Format pace as mm:ss/km."""
    mins = int(seconds_per_km // 60)
    secs = int(seconds_per_km % 60)
    return f"{mins}:{secs:02d}"


def get_personal_best_profile(athlete_id: str, db: Session) -> List[PersonalBestEntry]:
    """Extract personal best profile with pace analysis."""
    pbs = db.query(PersonalBest).filter(
        PersonalBest.athlete_id == athlete_id
    ).order_by(PersonalBest.distance_meters).all()
    
    result = []
    for pb in pbs:
        pace_seconds = pb.time_seconds / (pb.distance_meters / 1000)
        result.append(PersonalBestEntry(
            distance=pb.distance_category.upper() if pb.distance_category in ['5k', '10k', '15k', '25k', '30k'] else pb.distance_category.replace('_', ' ').title(),
            distance_meters=int(pb.distance_meters),
            time_seconds=float(pb.time_seconds),
            pace_per_km=format_pace(pace_seconds),
            is_race=pb.is_race or False,
            validated=pb.is_race or False  # Races are considered validated
        ))
    
    return result


def classify_phase(volume_km: float, peak_volume_km: float, prev_volume_km: Optional[float]) -> str:
    """Classify training phase based on volume patterns."""
    if peak_volume_km == 0:
        return Phase.BASE.value
    
    ratio = volume_km / peak_volume_km
    
    if ratio >= 0.9:
        return Phase.PEAK.value
    elif ratio >= 0.7:
        if prev_volume_km and volume_km > prev_volume_km:
            return Phase.BUILD.value
        else:
            return Phase.TAPER.value
    elif ratio >= 0.4:
        if prev_volume_km and volume_km > prev_volume_km:
            return Phase.RETURN.value
        else:
            return Phase.RECOVERY.value
    else:
        return Phase.RECOVERY.value


def get_volume_trajectory(athlete_id: str, db: Session, weeks: int = 12) -> VolumeTrajectory:
    """Calculate weekly volume trajectory."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=weeks * 7)
    
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= cutoff
    ).order_by(Activity.start_time).all()
    
    # Group by week
    week_data = defaultdict(lambda: {'distance': 0, 'duration': 0, 'count': 0})
    for a in activities:
        week_num = a.start_time.isocalendar()[1]
        year = a.start_time.year
        key = f"{year}-W{week_num:02d}"
        week_data[key]['distance'] += a.distance_m or 0
        week_data[key]['duration'] += a.duration_s or 0
        week_data[key]['count'] += 1
    
    # Find peak volume
    peak_volume = max((w['distance'] for w in week_data.values()), default=0) / 1000
    peak_week = ""
    for week, data in week_data.items():
        if data['distance'] / 1000 >= peak_volume:
            peak_week = week
    
    # Build week list with phases
    sorted_weeks = sorted(week_data.keys())
    week_list = []
    prev_volume = None
    for week in sorted_weeks:
        data = week_data[week]
        volume_km = data['distance'] / 1000
        phase = classify_phase(volume_km, peak_volume, prev_volume)
        week_list.append(WeekVolume(
            week=week,
            distance_km=round(volume_km, 1),
            duration_hrs=round(data['duration'] / 3600, 1),
            runs=data['count'],
            phase=phase
        ))
        prev_volume = volume_km
    
    total_km = sum(w['distance'] for w in week_data.values()) / 1000
    total_runs = sum(w['count'] for w in week_data.values())
    
    # Current vs peak
    current_volume = week_list[-1].distance_km if week_list else 0
    current_vs_peak = ((current_volume - peak_volume) / peak_volume * 100) if peak_volume > 0 else 0
    
    return VolumeTrajectory(
        weeks=week_list,
        total_km=round(total_km, 1),
        total_runs=total_runs,
        peak_week=peak_week,
        peak_volume_km=round(peak_volume, 1),
        current_vs_peak_pct=round(current_vs_peak, 1)
    )


def get_efficiency_trend(athlete_id: str, db: Session, weeks: int = 12) -> EfficiencyAnalysis:
    """Calculate efficiency trend analysis."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=weeks * 7)
    
    # Get runs with HR data
    runs = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= cutoff,
        Activity.avg_hr != None,
        Activity.avg_hr > 100,
        Activity.distance_m > 3000
    ).order_by(Activity.start_time).all()
    
    if not runs:
        return EfficiencyAnalysis(
            average=None,
            trend_pct=None,
            interpretation="Insufficient heart rate data for efficiency analysis.",
            recent_runs=[],
            runs_with_hr=0
        )
    
    # Calculate efficiency for each run
    efficiencies = []
    recent_runs = []
    for a in runs:
        if a.avg_hr and a.duration_s and a.distance_m:
            pace_min_km = (a.duration_s / 60) / (a.distance_m / 1000)
            eff = a.distance_m / (a.avg_hr * a.duration_s / 60)
            efficiencies.append(eff)
            recent_runs.append(RecentRun(
                date=a.start_time.strftime('%Y-%m-%d'),
                name=(a.name or 'Run')[:40],
                distance_km=round(a.distance_m / 1000, 1),
                pace_min_km=round(pace_min_km, 2),
                avg_hr=int(a.avg_hr),
                efficiency=round(eff, 4)
            ))
    
    if len(efficiencies) < 5:
        return EfficiencyAnalysis(
            average=round(sum(efficiencies) / len(efficiencies), 4) if efficiencies else None,
            trend_pct=None,
            interpretation="Need more runs with heart rate data to calculate trend.",
            recent_runs=recent_runs[-10:],
            runs_with_hr=len(runs)
        )
    
    # Calculate trend
    avg_eff = sum(efficiencies) / len(efficiencies)
    first_half = sum(efficiencies[:len(efficiencies)//2]) / (len(efficiencies)//2)
    second_half = sum(efficiencies[len(efficiencies)//2:]) / (len(efficiencies) - len(efficiencies)//2)
    trend_pct = ((second_half - first_half) / first_half) * 100 if first_half > 0 else 0
    
    # Generate interpretation
    if abs(trend_pct) < 2:
        interpretation = "Efficiency stable — consistent cardiovascular performance."
    elif trend_pct > 5:
        interpretation = "Efficiency improving — aerobic fitness developing."
    elif trend_pct > 0:
        interpretation = "Slight efficiency improvement — trending positive."
    elif trend_pct > -5:
        interpretation = "Slight efficiency decline — may be normal variation or fatigue."
    else:
        interpretation = "Efficiency declining — expected during recovery or heavy training blocks."
    
    return EfficiencyAnalysis(
        average=round(avg_eff, 4),
        trend_pct=round(trend_pct, 1),
        interpretation=interpretation,
        recent_runs=recent_runs[-10:],
        runs_with_hr=len(runs)
    )


def get_race_history(athlete_id: str, db: Session, limit: int = 5) -> List[RaceEntry]:
    """Get recent race history."""
    races = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_race_candidate == True
    ).order_by(Activity.start_time.desc()).limit(limit).all()
    
    result = []
    for r in races:
        if r.distance_m and r.duration_s:
            pace_seconds = r.duration_s / (r.distance_m / 1000)
            result.append(RaceEntry(
                date=r.start_time.strftime('%Y-%m-%d'),
                name=(r.name or 'Race')[:50],
                distance_km=round(r.distance_m / 1000, 1),
                time_seconds=float(r.duration_s),
                pace_per_km=format_pace(pace_seconds),
                notes=""
            ))
    
    return result


def get_data_quality_assessment(athlete_id: str, db: Session) -> DataQualityAssessment:
    """Assess data quality and identify gaps."""
    # Count activities
    total_activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id
    ).count()
    
    # Count runs with HR
    runs_with_hr = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.avg_hr != None,
        Activity.avg_hr > 100
    ).count()
    
    # Count PBs
    pb_count = db.query(PersonalBest).filter(
        PersonalBest.athlete_id == athlete_id
    ).count()
    
    # Count check-ins
    checkin_count = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == athlete_id
    ).count()
    
    # Count check-ins with HRV
    hrv_count = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.hrv_rmssd != None
    ).count()
    
    # Build available data
    available = {}
    
    if total_activities >= 50:
        available['activities'] = DataAvailable(count=total_activities, quality=DataQuality.EXCELLENT.value)
    elif total_activities >= 20:
        available['activities'] = DataAvailable(count=total_activities, quality=DataQuality.GOOD.value)
    elif total_activities >= 5:
        available['activities'] = DataAvailable(count=total_activities, quality=DataQuality.LIMITED.value)
    else:
        available['activities'] = DataAvailable(count=total_activities, quality=DataQuality.INSUFFICIENT.value)
    
    if runs_with_hr >= 30:
        available['heart_rate'] = DataAvailable(count=runs_with_hr, quality=DataQuality.EXCELLENT.value)
    elif runs_with_hr >= 15:
        available['heart_rate'] = DataAvailable(count=runs_with_hr, quality=DataQuality.GOOD.value)
    elif runs_with_hr >= 5:
        available['heart_rate'] = DataAvailable(count=runs_with_hr, quality=DataQuality.LIMITED.value)
    
    if pb_count >= 5:
        available['personal_bests'] = DataAvailable(count=pb_count, quality=DataQuality.EXCELLENT.value)
    elif pb_count >= 2:
        available['personal_bests'] = DataAvailable(count=pb_count, quality=DataQuality.GOOD.value)
    elif pb_count >= 1:
        available['personal_bests'] = DataAvailable(count=pb_count, quality=DataQuality.LIMITED.value)
    
    # Build missing data
    missing = {}
    unanswerable = []
    
    if checkin_count == 0:
        missing['daily_checkins'] = DataMissing(impact="Cannot correlate sleep, stress, or soreness with performance")
        unanswerable.append("Does sleep quality affect your running efficiency?")
        unanswerable.append("Does stress correlate with performance?")
        unanswerable.append("Does muscle soreness predict injury risk?")
    
    if hrv_count == 0:
        missing['hrv'] = DataMissing(impact="Cannot assess readiness or recovery status")
        unanswerable.append("What's your optimal HRV range for quality sessions?")
    
    # Nutrition always missing (not yet implemented)
    missing['nutrition'] = DataMissing(impact="Cannot correlate fueling with performance")
    unanswerable.append("How does nutrition timing affect your performance?")
    
    # Body composition always missing (not yet implemented)
    missing['body_composition'] = DataMissing(impact="Cannot track weight trends or correlate with performance")
    
    return DataQualityAssessment(
        available=available,
        missing=missing,
        unanswerable_questions=unanswerable
    )


def generate_recommendations(
    data_quality: DataQualityAssessment,
    efficiency_analysis: EfficiencyAnalysis,
    volume_trajectory: VolumeTrajectory
) -> Recommendations:
    """Generate prioritized recommendations based on report data."""
    high_priority = []
    medium_priority = []
    do_not_do = []
    
    # Check-ins recommendation
    if 'daily_checkins' in data_quality.missing:
        high_priority.append(Recommendation(
            action="Start morning check-ins",
            reason="Unlocks sleep, stress, and soreness correlation analysis",
            effort="10 seconds/day for 4 weeks"
        ))
    
    # Volume-based recommendations
    if volume_trajectory.current_vs_peak_pct < -50:
        # Low volume relative to peak
        current_phase = volume_trajectory.weeks[-1].phase if volume_trajectory.weeks else "unknown"
        if current_phase in [Phase.RECOVERY.value, Phase.RETURN.value]:
            high_priority.append(Recommendation(
                action="Continue conservative return",
                reason=f"Current volume {abs(volume_trajectory.current_vs_peak_pct):.0f}% below peak — appropriate for recovery phase",
                effort="Gradual weekly increases of 10-15%"
            ))
            do_not_do.append(Recommendation(
                action="Add quality sessions prematurely",
                reason="Aerobic base should be rebuilt before intensity work"
            ))
    
    # Efficiency-based recommendations
    if efficiency_analysis.trend_pct and efficiency_analysis.trend_pct < -3:
        do_not_do.append(Recommendation(
            action="Chase efficiency metrics during recovery",
            reason="Decline is expected during reduced volume or recovery phases"
        ))
    
    # HR data recommendation
    if 'heart_rate' not in data_quality.available:
        medium_priority.append(Recommendation(
            action="Wear HR monitor for more runs",
            reason="Enables efficiency and cardiac drift analysis",
            effort="Use HR strap for 80%+ of runs"
        ))
    
    # Weight logging
    if 'body_composition' in data_quality.missing:
        medium_priority.append(Recommendation(
            action="Log weight weekly",
            reason="Enables body composition tracking and weight-performance correlation"
        ))
    
    # Workout naming
    medium_priority.append(Recommendation(
        action="Name workouts by intent",
        reason="Activity names like 'Tempo Run' or 'Recovery' help classify workout types",
        effort="Add descriptive names in Strava/Garmin"
    ))
    
    return Recommendations(
        high_priority=high_priority,
        medium_priority=medium_priority,
        do_not_do=do_not_do
    )


def generate_key_findings(
    pb_count: int,
    efficiency_analysis: EfficiencyAnalysis,
    data_quality: DataQualityAssessment,
    volume_trajectory: VolumeTrajectory
) -> List[KeyFinding]:
    """Generate key findings for executive summary."""
    findings = []
    
    # PB finding
    if pb_count >= 5:
        findings.append(KeyFinding(
            type=FindingType.POSITIVE.value,
            text=f"Personal bests validated across {pb_count} distances"
        ))
    elif pb_count > 0:
        findings.append(KeyFinding(
            type=FindingType.INFO.value,
            text=f"{pb_count} personal best(s) recorded — race more distances to build profile"
        ))
    
    # Efficiency finding
    if efficiency_analysis.trend_pct is not None:
        if efficiency_analysis.trend_pct > 3:
            findings.append(KeyFinding(
                type=FindingType.POSITIVE.value,
                text=f"Efficiency improving ({efficiency_analysis.trend_pct:+.1f}%) — aerobic fitness developing"
            ))
        elif efficiency_analysis.trend_pct < -3:
            findings.append(KeyFinding(
                type=FindingType.WARNING.value,
                text=f"Efficiency trending down ({efficiency_analysis.trend_pct:+.1f}%) — {efficiency_analysis.interpretation.lower()}"
            ))
    
    # Data quality findings
    if 'daily_checkins' in data_quality.missing:
        findings.append(KeyFinding(
            type=FindingType.WARNING.value,
            text="Zero check-in data — prevents sleep/stress correlation analysis"
        ))
    
    # Volume finding
    if volume_trajectory.total_runs > 0:
        findings.append(KeyFinding(
            type=FindingType.INFO.value,
            text=f"Logged {volume_trajectory.total_km:.0f} km across {volume_trajectory.total_runs} runs in last 12 weeks"
        ))
    
    return findings


def generate_diagnostic_report(athlete_id: str, db: Session) -> DiagnosticReport:
    """
    Generate comprehensive diagnostic report for an athlete.
    
    Args:
        athlete_id: UUID of the athlete
        db: Database session
        
    Returns:
        DiagnosticReport dataclass with all sections
    """
    now = datetime.now(timezone.utc)
    
    # Get date range
    first_activity = db.query(Activity).filter(
        Activity.athlete_id == athlete_id
    ).order_by(Activity.start_time).first()
    
    last_activity = db.query(Activity).filter(
        Activity.athlete_id == athlete_id
    ).order_by(Activity.start_time.desc()).first()
    
    period_start = first_activity.start_time.strftime('%Y-%m-%d') if first_activity else now.strftime('%Y-%m-%d')
    period_end = last_activity.start_time.strftime('%Y-%m-%d') if last_activity else now.strftime('%Y-%m-%d')
    
    # Generate each section
    personal_bests = get_personal_best_profile(athlete_id, db)
    volume_trajectory = get_volume_trajectory(athlete_id, db, weeks=12)
    efficiency_analysis = get_efficiency_trend(athlete_id, db, weeks=12)
    race_history = get_race_history(athlete_id, db, limit=5)
    data_quality = get_data_quality_assessment(athlete_id, db)
    
    # Generate recommendations based on data
    recommendations = generate_recommendations(data_quality, efficiency_analysis, volume_trajectory)
    
    # Generate key findings
    key_findings = generate_key_findings(
        len(personal_bests), efficiency_analysis, data_quality, volume_trajectory
    )
    
    # Determine current phase
    current_phase = volume_trajectory.weeks[-1].phase if volume_trajectory.weeks else Phase.BASE.value
    
    # Build executive summary
    total_activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id
    ).count()
    
    executive_summary = ExecutiveSummary(
        total_activities=total_activities,
        total_distance_km=volume_trajectory.total_km,
        peak_volume_km=volume_trajectory.peak_volume_km,
        current_phase=current_phase,
        efficiency_trend_pct=efficiency_analysis.trend_pct,
        key_findings=key_findings,
        date_range_start=period_start,
        date_range_end=period_end
    )
    
    return DiagnosticReport(
        generated_at=now.isoformat(),
        athlete_id=str(athlete_id),
        period_start=period_start,
        period_end=period_end,
        executive_summary=executive_summary,
        personal_bests=personal_bests,
        volume_trajectory=volume_trajectory,
        efficiency_analysis=efficiency_analysis,
        race_history=race_history,
        data_quality=data_quality,
        recommendations=recommendations
    )


def diagnostic_report_to_dict(report: DiagnosticReport) -> Dict[str, Any]:
    """Convert DiagnosticReport to dictionary for JSON serialization."""
    return {
        'generated_at': report.generated_at,
        'athlete_id': report.athlete_id,
        'period_start': report.period_start,
        'period_end': report.period_end,
        'executive_summary': {
            'total_activities': report.executive_summary.total_activities,
            'total_distance_km': report.executive_summary.total_distance_km,
            'peak_volume_km': report.executive_summary.peak_volume_km,
            'current_phase': report.executive_summary.current_phase,
            'efficiency_trend_pct': report.executive_summary.efficiency_trend_pct,
            'key_findings': [{'type': f.type, 'text': f.text} for f in report.executive_summary.key_findings],
            'date_range_start': report.executive_summary.date_range_start,
            'date_range_end': report.executive_summary.date_range_end
        },
        'personal_bests': [
            {
                'distance': pb.distance,
                'distance_meters': pb.distance_meters,
                'time_seconds': pb.time_seconds,
                'pace_per_km': pb.pace_per_km,
                'is_race': pb.is_race,
                'validated': pb.validated
            }
            for pb in report.personal_bests
        ],
        'volume_trajectory': {
            'weeks': [
                {
                    'week': w.week,
                    'distance_km': w.distance_km,
                    'duration_hrs': w.duration_hrs,
                    'runs': w.runs,
                    'phase': w.phase
                }
                for w in report.volume_trajectory.weeks
            ],
            'total_km': report.volume_trajectory.total_km,
            'total_runs': report.volume_trajectory.total_runs,
            'peak_week': report.volume_trajectory.peak_week,
            'peak_volume_km': report.volume_trajectory.peak_volume_km,
            'current_vs_peak_pct': report.volume_trajectory.current_vs_peak_pct
        },
        'efficiency_analysis': {
            'average': report.efficiency_analysis.average,
            'trend_pct': report.efficiency_analysis.trend_pct,
            'interpretation': report.efficiency_analysis.interpretation,
            'recent_runs': [
                {
                    'date': r.date,
                    'name': r.name,
                    'distance_km': r.distance_km,
                    'pace_min_km': r.pace_min_km,
                    'avg_hr': r.avg_hr,
                    'efficiency': r.efficiency
                }
                for r in report.efficiency_analysis.recent_runs
            ],
            'runs_with_hr': report.efficiency_analysis.runs_with_hr
        },
        'race_history': [
            {
                'date': r.date,
                'name': r.name,
                'distance_km': r.distance_km,
                'time_seconds': r.time_seconds,
                'pace_per_km': r.pace_per_km,
                'notes': r.notes
            }
            for r in report.race_history
        ],
        'data_quality': {
            'available': {
                k: {'count': v.count, 'quality': v.quality}
                for k, v in report.data_quality.available.items()
            },
            'missing': {
                k: {'impact': v.impact}
                for k, v in report.data_quality.missing.items()
            },
            'unanswerable_questions': report.data_quality.unanswerable_questions
        },
        'recommendations': {
            'high_priority': [
                {'action': r.action, 'reason': r.reason, 'effort': r.effort}
                for r in report.recommendations.high_priority
            ],
            'medium_priority': [
                {'action': r.action, 'reason': r.reason, 'effort': r.effort}
                for r in report.recommendations.medium_priority
            ],
            'do_not_do': [
                {'action': r.action, 'reason': r.reason}
                for r in report.recommendations.do_not_do
            ]
        }
    }
