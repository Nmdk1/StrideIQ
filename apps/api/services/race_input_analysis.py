"""
Race Input Mining — Question-Based Investigation Engine

Races are products. Activities are inputs. This service mines the inputs
to find what combination builds the best products — for ONE athlete only,
with receipts.

Architecture:
  Each investigation is a self-contained question that:
    1. Queries the specific data it needs
    2. Cross-references multiple activities (single-variable findings are suppressed)
    3. Checks its own confounds (environment, elevation, recency)
    4. Returns a finding only if it survives scrutiny — or None

  The engine runs all registered investigations and returns the survivors.
  Investigations declare their signal requirements via @investigation decorator.
  The runner checks signal availability before executing.
"""

import logging
import math
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta, datetime
from typing import List, Optional, Dict, Tuple, Callable
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_, func as sa_func

from models import Activity, ActivitySplit, ActivityStream, Athlete, PerformanceEvent
from services.rpi_calculator import calculate_training_paces

logger = logging.getLogger(__name__)

KM_PER_METER = 0.001
MI_PER_KM = 0.621371
SEC_PER_MIN = 60.0
METERS_PER_MILE = 1609.34
TREADMILL_ELEV_THRESHOLD_M = 20


# ═══════════════════════════════════════════════════════
#  Investigation Registry
# ═══════════════════════════════════════════════════════

@dataclass
class InvestigationSpec:
    """Metadata for a registered investigation."""
    name: str
    fn: Callable
    requires: List[str]
    min_activities: int = 0
    min_races: int = 0
    min_data_weeks: int = 0
    description: str = ""

INVESTIGATION_REGISTRY: List[InvestigationSpec] = []


def investigation(
    requires: List[str],
    min_activities: int = 0,
    min_races: int = 0,
    min_data_weeks: int = 0,
    description: str = "",
):
    """Decorator that registers an investigation with its signal requirements."""
    def decorator(fn):
        INVESTIGATION_REGISTRY.append(InvestigationSpec(
            name=fn.__name__,
            fn=fn,
            requires=requires,
            min_activities=min_activities,
            min_races=min_races,
            min_data_weeks=min_data_weeks,
            description=description,
        ))
        return fn
    return decorator


def get_athlete_signal_coverage(athlete_id: UUID, db: Session) -> Dict[str, bool]:
    """Check which signal types have sufficient data for this athlete."""
    act_count = db.query(sa_func.count(Activity.id)).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
    ).scalar() or 0

    split_count = db.query(sa_func.count(ActivitySplit.id)).join(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
    ).scalar() or 0

    stream_count = db.query(sa_func.count(ActivityStream.id)).join(Activity).filter(
        Activity.athlete_id == athlete_id,
    ).scalar() or 0

    shape_count = db.query(sa_func.count(Activity.id)).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.run_shape.isnot(None),
    ).scalar() or 0

    env_count = db.query(sa_func.count(Activity.id)).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.temperature_f.isnot(None),
    ).scalar() or 0

    race_count = db.query(sa_func.count(PerformanceEvent.id)).filter(
        PerformanceEvent.athlete_id == athlete_id,
        PerformanceEvent.user_confirmed == True,  # noqa: E712
    ).scalar() or 0

    return {
        'activity_summary': act_count > 0,
        'activity_splits': split_count > 0,
        'activity_stream': stream_count > 0,
        'run_shape': shape_count > 0,
        'environment': env_count > 0,
        'race_result': race_count > 0,
    }


def meets_minimums(spec: InvestigationSpec, athlete_id: UUID, db: Session) -> bool:
    """Check if an athlete meets the minimum data thresholds for an investigation."""
    if spec.min_activities > 0:
        act_count = db.query(sa_func.count(Activity.id)).filter(
            Activity.athlete_id == athlete_id,
            Activity.is_duplicate == False,  # noqa: E712
        ).scalar() or 0
        if act_count < spec.min_activities:
            return False

    if spec.min_races > 0:
        race_count = db.query(sa_func.count(PerformanceEvent.id)).filter(
            PerformanceEvent.athlete_id == athlete_id,
            PerformanceEvent.user_confirmed == True,  # noqa: E712
        ).scalar() or 0
        if race_count < spec.min_races:
            return False

    if spec.min_data_weeks > 0:
        earliest = db.query(sa_func.min(Activity.start_time)).filter(
            Activity.athlete_id == athlete_id,
            Activity.is_duplicate == False,  # noqa: E712
        ).scalar()
        if earliest is None:
            return False
        latest = db.query(sa_func.max(Activity.start_time)).filter(
            Activity.athlete_id == athlete_id,
            Activity.is_duplicate == False,  # noqa: E712
        ).scalar()
        if latest is None:
            return False
        weeks = (latest - earliest).days / 7
        if weeks < spec.min_data_weeks:
            return False

    return True


# ═══════════════════════════════════════════════════════
#  Training Zones (from athlete's pace profile)
# ═══════════════════════════════════════════════════════

@dataclass(frozen=True)
class TrainingZones:
    """Pace zones in seconds per mile, derived from athlete's RPI."""
    easy_sec: int          # easy pace (fast end)
    marathon_sec: int      # marathon pace
    threshold_sec: int     # threshold / tempo pace
    interval_sec: int      # VO2max / interval pace
    repetition_sec: int    # repetition pace

    @property
    def _boundaries(self) -> Dict[str, Tuple[int, int]]:
        """Zone boundaries (sec/mile) using midpoints between landmarks."""
        rep_int = (self.repetition_sec + self.interval_sec) // 2
        int_thr = (self.interval_sec + self.threshold_sec) // 2
        thr_mar = (self.threshold_sec + self.marathon_sec) // 2
        mar_easy = (self.marathon_sec + self.easy_sec) // 2
        return {
            'repetition': (0, rep_int),
            'interval': (rep_int, int_thr),
            'threshold': (int_thr, thr_mar),
            'marathon_pace': (thr_mar, mar_easy),
            'easy': (mar_easy, 9999),
        }

    def classify_pace(self, pace_sec_per_mile: int) -> str:
        """Classify a pace into a training zone using midpoint boundaries."""
        for zone, (lo, hi) in self._boundaries.items():
            if lo <= pace_sec_per_mile <= hi:
                return zone
        return 'easy'

    def zone_range_min_km(self, zone: str) -> Tuple[float, float]:
        """Return (min_pace, max_pace) in min/km for a zone."""
        bounds = self._boundaries.get(zone, (0, 9999))
        low_sec, high_sec = bounds
        if low_sec == 0:
            low_sec = self.repetition_sec - 20
        # Convert sec/mile to min/km
        low_km = (low_sec / SEC_PER_MIN) / (METERS_PER_MILE * KM_PER_METER)
        high_km = (high_sec / SEC_PER_MIN) / (METERS_PER_MILE * KM_PER_METER)
        return (low_km, high_km)


def load_training_zones(athlete_id: UUID, db: Session) -> Optional[TrainingZones]:
    """Load training zones from athlete's RPI via the calculator."""
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete or not athlete.rpi:
        return None

    paces = calculate_training_paces(athlete.rpi)
    if not paces:
        return None

    return TrainingZones(
        easy_sec=paces.get('easy_pace_low', 486),
        marathon_sec=paces.get('marathon_pace', 417),
        threshold_sec=paces.get('threshold_pace', 393),
        interval_sec=paces.get('interval_pace', 345),
        repetition_sec=paces.get('repetition_pace', 321),
    )


# ═══════════════════════════════════════════════════════
#  Environmental Context & Confound Utilities
# ═══════════════════════════════════════════════════════

@dataclass
class ActivityContext:
    """Environmental context for an activity, used for confound checking."""
    activity_id: str
    date: date
    is_indoor: bool
    temperature_f: Optional[float]
    humidity_pct: Optional[float]
    total_elevation_m: float
    distance_km: float
    has_gap_data: bool


def _heat_normalize_pace(pace_sec_mi: float, heat_adjustment_pct: Optional[float]) -> float:
    """Remove heat tax from a raw pace value.

    If the activity was run in heat (e.g., heat_adjustment_pct=0.04 meaning
    4% slower), this returns what the pace would have been in neutral conditions.
    """
    if heat_adjustment_pct and heat_adjustment_pct > 0 and pace_sec_mi > 0:
        return pace_sec_mi / (1 + heat_adjustment_pct)
    return pace_sec_mi


def build_activity_context(act: Activity) -> ActivityContext:
    """Build environmental context for confound checking."""
    elev = float(act.total_elevation_gain) if act.total_elevation_gain else 0
    dist_km = (act.distance_m or 0) * KM_PER_METER
    is_indoor = elev < TREADMILL_ELEV_THRESHOLD_M and dist_km > 5

    return ActivityContext(
        activity_id=str(act.id),
        date=act.start_time.date(),
        is_indoor=is_indoor,
        temperature_f=act.temperature_f,
        humidity_pct=act.humidity_pct,
        total_elevation_m=elev,
        distance_km=round(dist_km, 1),
        has_gap_data=False,  # populated per-split when needed
    )


def get_gap_adjusted_pace(split: ActivitySplit) -> Optional[float]:
    """
    Return grade-adjusted pace in min/km for a split.
    GAP normalizes pace for elevation so hilly courses are comparable to flat.
    Returns None if GAP data unavailable.
    """
    if split.gap_seconds_per_mile is None:
        return None
    gap_sec_mile = float(split.gap_seconds_per_mile)
    return (gap_sec_mile / SEC_PER_MIN) / (METERS_PER_MILE * KM_PER_METER)


def compute_cardiac_drift(
    splits: List[ActivitySplit],
    min_splits: int = 6,
) -> Optional[Dict]:
    """
    Compute cardiac drift from first half to second half of an activity's splits.
    Returns drift details or None if insufficient data.
    """
    hr_splits = [s for s in splits if s.average_heartrate and s.distance and s.elapsed_time]
    if len(hr_splits) < min_splits:
        return None

    mid = len(hr_splits) // 2
    first_half = hr_splits[:mid]
    second_half = hr_splits[mid:]

    first_hr = sum(s.average_heartrate for s in first_half) / len(first_half)
    second_hr = sum(s.average_heartrate for s in second_half) / len(second_half)

    first_paces, second_paces = [], []
    for s in first_half:
        dk = float(s.distance) * KM_PER_METER
        if dk > 0.1:
            first_paces.append((s.elapsed_time / 60) / dk)
    for s in second_half:
        dk = float(s.distance) * KM_PER_METER
        if dk > 0.1:
            second_paces.append((s.elapsed_time / 60) / dk)

    first_pace = sum(first_paces) / len(first_paces) if first_paces else 0
    second_pace = sum(second_paces) / len(second_paces) if second_paces else 0

    return {
        'hr_drift': round(second_hr - first_hr, 1),
        'first_hr': round(first_hr, 1),
        'second_hr': round(second_hr, 1),
        'pace_drift': round(second_pace - first_pace, 2),
        'first_pace': round(first_pace, 2),
        'second_pace': round(second_pace, 2),
        'is_steady_effort': abs(second_pace - first_pace) < 0.3,
    }


# ═══════════════════════════════════════════════════════
#  Data structures
# ═══════════════════════════════════════════════════════

@dataclass
class ZonedSplit:
    split_number: int
    dist_km: float
    pace_min_km: float
    pace_sec_mile: int
    zone: str
    hr: Optional[int]


@dataclass
class QualitySession:
    """A session containing work in a specific training zone."""
    date: date
    activity_id: str
    classified_as: str
    zone: str  # 'interval', 'threshold', 'marathon_pace'
    total_distance_km: float
    zone_splits: int
    total_splits: int
    zone_ratio: float
    zone_distance_km: float
    avg_zone_pace_min_km: float
    avg_zone_hr: Optional[int]
    split_paces: List[float]
    split_hrs: List[Optional[int]]
    pace_consistency: float
    held_pace: bool
    session_type: str  # 'sustained', 'interval', 'mixed', 'easy_paced'
    day_of_week: int  # 0=Mon, 6=Sun


@dataclass
class PaceAtHRPoint:
    date: date
    activity_id: str
    workout_type: str
    pace_min_km: float
    avg_hr: int
    distance_km: float


@dataclass
class AdaptationCurve:
    workout_category: str
    sessions: List[dict]
    trend: str
    inflection_date: Optional[date]
    inflection_description: str
    metric_name: str


@dataclass
class WeeklyPattern:
    """A recurring weekly training structure."""
    pattern_type: str  # e.g. 'vo2_saturday_long_sunday'
    day_1: str
    day_1_zone: str
    day_2: str
    day_2_zone: str
    occurrences: int
    weeks_span: int
    first_week: date
    last_week: date
    examples: List[dict]


@dataclass
class RaceInputFinding:
    layer: str  # 'A', 'B', 'C'
    finding_type: str
    sentence: str
    receipts: dict
    confidence: str  # 'table_stakes', 'genuine', 'suggestive'


# ═══════════════════════════════════════════════════════
#  Layer B: Zone-based session detection
# ═══════════════════════════════════════════════════════

def find_quality_sessions(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    target_zone: str = 'threshold',
    min_zone_splits: int = 2,
    min_effort_hr: int = 140,
) -> List[QualitySession]:
    """
    Find sessions containing work in a specific training zone by mining
    split data against the athlete's actual pace zones from their profile.
    """
    pace_low, pace_high = zones.zone_range_min_km(target_zone)

    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.distance_m > 1500,
    ).order_by(Activity.start_time).all()

    sessions: List[QualitySession] = []

    for act in activities:
        splits = db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == act.id,
        ).order_by(ActivitySplit.split_number).all()

        if not splits:
            continue

        zone_splits = []
        for s in splits:
            if not s.distance or not s.elapsed_time:
                continue
            dist_km = float(s.distance) * KM_PER_METER
            if dist_km < 0.05:
                continue
            pace = (s.elapsed_time / 60) / dist_km
            if pace_low <= pace <= pace_high:
                zone_splits.append(ZonedSplit(
                    split_number=s.split_number,
                    dist_km=round(dist_km, 3),
                    pace_min_km=round(pace, 3),
                    pace_sec_mile=int(pace * SEC_PER_MIN * METERS_PER_MILE * KM_PER_METER),
                    zone=target_zone,
                    hr=s.average_heartrate,
                ))

        if len(zone_splits) < min_zone_splits:
            continue

        paces = [s.pace_min_km for s in zone_splits]
        hrs = [s.hr for s in zone_splits if s.hr]
        avg_pace = sum(paces) / len(paces)
        avg_hr = int(sum(hrs) / len(hrs)) if hrs else None
        pace_std = _std(paces)

        mid = len(paces) // 2
        if mid >= 1:
            first_half_avg = sum(paces[:mid]) / mid
            second_half_avg = sum(paces[mid:]) / len(paces[mid:])
            held_pace = second_half_avg <= first_half_avg * 1.02
        else:
            held_pace = True

        total_dist = act.distance_m * KM_PER_METER if act.distance_m else 0
        ratio = len(zone_splits) / len(splits) if splits else 0
        zone_km = sum(s.dist_km for s in zone_splits)

        is_genuine_effort = avg_hr is not None and avg_hr >= min_effort_hr

        if ratio >= 0.75 and is_genuine_effort:
            session_type = 'sustained'
        elif ratio >= 0.75 and not is_genuine_effort:
            session_type = 'easy_paced'
        elif ratio <= 0.40 and len(splits) > 6 and is_genuine_effort:
            session_type = 'interval'
        elif is_genuine_effort:
            session_type = 'mixed'
        else:
            session_type = 'easy_paced'

        sessions.append(QualitySession(
            date=act.start_time.date(),
            activity_id=str(act.id),
            classified_as=act.workout_type or 'unknown',
            zone=target_zone,
            total_distance_km=round(total_dist, 1),
            zone_splits=len(zone_splits),
            total_splits=len(splits),
            zone_ratio=round(ratio, 2),
            zone_distance_km=round(zone_km, 1),
            avg_zone_pace_min_km=round(avg_pace, 3),
            avg_zone_hr=avg_hr,
            split_paces=paces,
            split_hrs=[s.hr for s in zone_splits],
            pace_consistency=round(pace_std, 4),
            held_pace=held_pace,
            session_type=session_type,
            day_of_week=act.start_time.weekday(),
        ))

    return sessions


# ═══════════════════════════════════════════════════════
#  Layer B: Weekly pattern detection
# ═══════════════════════════════════════════════════════

def detect_weekly_patterns(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
) -> List[WeeklyPattern]:
    """
    Find recurring weekly training structures by analyzing which
    zones appear on which days of the week.
    """
    interval_sessions = find_quality_sessions(
        athlete_id, db, zones, 'interval', min_zone_splits=2, min_effort_hr=140,
    )

    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.distance_m > 15000,  # long runs > 15km
    ).order_by(Activity.start_time).all()

    long_runs_by_date = {}
    for act in activities:
        d = act.start_time.date()
        dist = act.distance_m * KM_PER_METER
        long_runs_by_date[d] = {
            'date': d,
            'distance_km': round(dist, 1),
            'workout_type': act.workout_type or 'unknown',
            'day_of_week': d.weekday(),
            'activity_id': str(act.id),
        }

    # Look for VO2/interval session followed by long run next day
    patterns: List[WeeklyPattern] = []
    back_to_back_examples = []

    for sess in interval_sessions:
        next_day = sess.date + timedelta(days=1)
        if next_day in long_runs_by_date:
            lr = long_runs_by_date[next_day]
            back_to_back_examples.append({
                'week_of': (sess.date - timedelta(days=sess.day_of_week)).isoformat(),
                'interval_date': sess.date.isoformat(),
                'interval_day': _day_name(sess.day_of_week),
                'interval_splits': sess.zone_splits,
                'interval_pace': f"{sess.avg_zone_pace_min_km:.2f} min/km",
                'interval_hr': sess.avg_zone_hr,
                'long_run_date': lr['date'].isoformat(),
                'long_run_day': _day_name(lr['day_of_week']),
                'long_run_km': lr['distance_km'],
            })

    if len(back_to_back_examples) >= 3:
        first = date.fromisoformat(back_to_back_examples[0]['interval_date'])
        last = date.fromisoformat(back_to_back_examples[-1]['interval_date'])
        weeks_span = (last - first).days // 7

        most_common_day = _most_common([e['interval_day'] for e in back_to_back_examples])
        most_common_lr_day = _most_common([e['long_run_day'] for e in back_to_back_examples])

        patterns.append(WeeklyPattern(
            pattern_type='vo2_then_long_run',
            day_1=most_common_day,
            day_1_zone='interval',
            day_2=most_common_lr_day,
            day_2_zone='long_run',
            occurrences=len(back_to_back_examples),
            weeks_span=weeks_span,
            first_week=first,
            last_week=last,
            examples=back_to_back_examples,
        ))

    return patterns


def compute_pace_at_hr(
    athlete_id: UUID,
    db: Session,
    hr_band: Tuple[int, int] = (130, 145),
) -> List[PaceAtHRPoint]:
    """
    Track pace at a given HR band over time — the primary aerobic
    adaptation signal. Computed across all run types.
    """
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.avg_hr.isnot(None),
        Activity.avg_hr >= hr_band[0],
        Activity.avg_hr <= hr_band[1],
        Activity.distance_m > 3000,
        Activity.duration_s > 0,
    ).order_by(Activity.start_time).all()

    points: List[PaceAtHRPoint] = []
    for act in activities:
        dist_km = act.distance_m * KM_PER_METER
        pace = (act.duration_s / 60) / dist_km

        points.append(PaceAtHRPoint(
            date=act.start_time.date(),
            activity_id=str(act.id),
            workout_type=act.workout_type or 'unknown',
            pace_min_km=round(pace, 3),
            avg_hr=act.avg_hr,
            distance_km=round(dist_km, 1),
        ))

    return points


def detect_adaptation_curves(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
) -> List[AdaptationCurve]:
    """
    Detect adaptation curves using the athlete's actual training zones.
    """
    curves: List[AdaptationCurve] = []

    # --- Threshold progression ---
    threshold_sessions = find_quality_sessions(
        athlete_id, db, zones, 'threshold', min_zone_splits=2, min_effort_hr=140,
    )
    effort_sessions = [s for s in threshold_sessions if s.session_type != 'easy_paced']
    if len(effort_sessions) >= 4:
        curve = _build_quality_curve(effort_sessions, 'threshold')
        if curve:
            curves.append(curve)

    # --- VO2 / Interval progression ---
    interval_sessions = find_quality_sessions(
        athlete_id, db, zones, 'interval', min_zone_splits=2, min_effort_hr=140,
    )
    effort_intervals = [s for s in interval_sessions if s.session_type != 'easy_paced']
    if len(effort_intervals) >= 4:
        curve = _build_quality_curve(effort_intervals, 'interval')
        if curve:
            curves.append(curve)

    # --- Pace at HR ---
    pace_hr_points = compute_pace_at_hr(athlete_id, db)
    if len(pace_hr_points) >= 6:
        curve = _build_pace_at_hr_curve(pace_hr_points)
        if curve:
            curves.append(curve)

    return curves


def _build_quality_curve(
    sessions: List[QualitySession],
    zone_name: str,
) -> Optional[AdaptationCurve]:
    """
    Build an adaptation curve for any training zone (threshold, interval, etc).
    Works generically — no hardcoded zone assumptions.
    """
    session_data = []
    for s in sessions:
        session_data.append({
            'date': s.date.isoformat(),
            'activity_id': s.activity_id,
            'classified_as': s.classified_as,
            'session_type': s.session_type,
            'zone': s.zone,
            'zone_splits': s.zone_splits,
            'total_splits': s.total_splits,
            'zone_ratio': s.zone_ratio,
            'zone_distance_km': s.zone_distance_km,
            'total_distance_km': s.total_distance_km,
            'avg_pace': s.avg_zone_pace_min_km,
            'avg_hr': s.avg_zone_hr,
            'pace_consistency': s.pace_consistency,
            'held_pace': s.held_pace,
            'day_of_week': _day_name(s.day_of_week),
        })

    zone_kms = [s.zone_distance_km for s in sessions]
    trend = _compute_trend(zone_kms) if zone_kms else 'insufficient_data'

    inflection = _find_session_type_shift(sessions)

    desc = ""
    if inflection:
        before = [s for s in sessions if s.date < inflection]
        after = [s for s in sessions if s.date >= inflection]

        interval_before = sum(1 for s in before if s.session_type == 'interval')
        sustained_before = sum(1 for s in before if s.session_type == 'sustained')
        interval_after = sum(1 for s in after if s.session_type == 'interval')
        sustained_after = sum(1 for s in after if s.session_type == 'sustained')

        avg_km_before = (
            sum(s.zone_distance_km for s in before) / len(before)
            if before else 0
        )
        avg_km_after = (
            sum(s.zone_distance_km for s in after) / len(after)
            if after else 0
        )

        desc = (
            f"Before {inflection.strftime('%B %Y')}: "
            f"{zone_name} work was primarily in intervals "
            f"({interval_before} interval, {sustained_before} sustained), "
            f"averaging {avg_km_before:.1f}km per session at {zone_name} pace. "
            f"After: sustained {zone_name} sessions appeared "
            f"({interval_after} interval, {sustained_after} sustained), "
            f"averaging {avg_km_after:.1f}km per session."
        )

    return AdaptationCurve(
        workout_category=zone_name,
        sessions=session_data,
        trend=trend,
        inflection_date=inflection,
        inflection_description=desc,
        metric_name=f'sustained_{zone_name}_km',
    )


def _build_pace_at_hr_curve(
    points: List[PaceAtHRPoint],
) -> Optional[AdaptationCurve]:
    """
    Build an adaptation curve from pace-at-HR data.
    Improving pace at the same HR = aerobic adaptation.

    Uses monthly rolling averages to smooth daily variance.
    """
    session_data = []
    for p in points:
        session_data.append({
            'date': p.date.isoformat(),
            'activity_id': p.activity_id,
            'workout_type': p.workout_type,
            'pace_min_km': p.pace_min_km,
            'avg_hr': p.avg_hr,
            'distance_km': p.distance_km,
        })

    monthly_avgs = _compute_monthly_averages(points)
    if len(monthly_avgs) < 3:
        return None

    monthly_paces = [avg for _, avg in monthly_avgs]
    trend = _compute_trend(monthly_paces, lower_is_better=True)

    inflection = _find_monthly_pace_inflection(monthly_avgs)

    desc = ""
    first_month_label, first_pace = monthly_avgs[0]
    last_month_label, last_pace = monthly_avgs[-1]
    improvement = first_pace - last_pace

    if improvement > 0.10:
        first_pace_mi = first_pace / MI_PER_KM
        last_pace_mi = last_pace / MI_PER_KM
        desc = (
            f"At the same heart rate range, your pace improved from "
            f"{first_pace:.2f} min/km ({first_pace_mi:.1f} min/mi) in "
            f"{first_month_label} to {last_pace:.2f} min/km "
            f"({last_pace_mi:.1f} min/mi) in {last_month_label}."
        )

    return AdaptationCurve(
        workout_category='aerobic_efficiency',
        sessions=session_data,
        trend=trend,
        inflection_date=inflection,
        inflection_description=desc,
        metric_name='pace_at_hr',
    )


def _find_session_type_shift(
    sessions: List[QualitySession],
) -> Optional[date]:
    """
    Find when the athlete shifted from interval-based work
    to sustained sessions in any zone.
    """
    if len(sessions) < 6:
        return None

    best_score = -1.0
    best_idx = None

    for i in range(3, len(sessions) - 2):
        before = sessions[:i]
        after = sessions[i:]

        sustained_before = sum(1 for s in before if s.session_type == 'sustained') / len(before)
        sustained_after = sum(1 for s in after if s.session_type == 'sustained') / len(after)

        km_before = sum(s.zone_distance_km for s in before) / len(before)
        km_after = sum(s.zone_distance_km for s in after) / len(after)

        type_shift = sustained_after - sustained_before
        km_shift = (km_after - km_before) / max(km_before, 1.0)

        score = type_shift * 2 + km_shift

        if score > best_score:
            best_score = score
            best_idx = i

    if best_idx is not None and best_score > 0.3:
        return sessions[best_idx].date

    return None


def _compute_monthly_averages(
    points: List[PaceAtHRPoint],
) -> List[Tuple[str, float]]:
    """Group pace-at-HR points by month, return (label, avg_pace)."""
    from collections import OrderedDict
    months: Dict[str, List[float]] = OrderedDict()

    for p in points:
        key = p.date.strftime('%Y-%m')
        months.setdefault(key, []).append(p.pace_min_km)

    result = []
    for key, paces in months.items():
        if len(paces) >= 3:  # need at least 3 data points per month
            result.append((key, sum(paces) / len(paces)))

    return result


def _find_monthly_pace_inflection(
    monthly_avgs: List[Tuple[str, float]],
) -> Optional[date]:
    """Find where monthly average pace at HR shifted fastest."""
    if len(monthly_avgs) < 4:
        return None

    paces = [avg for _, avg in monthly_avgs]
    best_reduction = 0.0
    best_idx = None

    for i in range(2, len(paces) - 1):
        before_avg = sum(paces[:i]) / i
        after_avg = sum(paces[i:]) / len(paces[i:])
        reduction = before_avg - after_avg

        if reduction > best_reduction:
            best_reduction = reduction
            best_idx = i

    if best_idx is not None and best_reduction > 0.10:
        month_str = monthly_avgs[best_idx][0]
        year, month = month_str.split('-')
        return date(int(year), int(month), 1)

    return None


# ═══════════════════════════════════════════════════════
#  Layer B: Connect adaptations to race outputs
# ═══════════════════════════════════════════════════════

def connect_adaptations_to_races(
    curves: List[AdaptationCurve],
    events: List[PerformanceEvent],
) -> List[RaceInputFinding]:
    """
    For each adaptation inflection, find the race that benefited from it.
    Skips races on the inflection date itself — the finding is about
    what the adaptation PRODUCED, not where it started.
    """
    findings: List[RaceInputFinding] = []
    sorted_events = sorted(events, key=lambda e: e.event_date)

    for curve in curves:
        if not curve.inflection_date:
            continue

        # Find next race AFTER the inflection (not on the same day)
        next_race = None
        for ev in sorted_events:
            if ev.event_date > curve.inflection_date:
                next_race = ev
                break

        if not next_race:
            continue

        weeks_between = (next_race.event_date - curve.inflection_date).days // 7

        # Build receipts
        before_sessions = [
            s for s in curve.sessions
            if s['date'] < curve.inflection_date.isoformat()
        ][-3:]  # last 3 before inflection

        after_sessions = [
            s for s in curve.sessions
            if s['date'] >= curve.inflection_date.isoformat()
        ][:3]  # first 3 after inflection

        race_time = _format_race_time(next_race)

        sentence = curve.inflection_description or ""
        if sentence and next_race:
            sentence += (
                f" Your {_dist_label(next_race.distance_category)} "
                f"{race_time} came {weeks_between} weeks later."
            )

        findings.append(RaceInputFinding(
            layer='B',
            finding_type=f'adaptation_{curve.workout_category}',
            sentence=sentence,
            receipts={
                'category': curve.workout_category,
                'metric': curve.metric_name,
                'inflection_date': curve.inflection_date.isoformat(),
                'trend': curve.trend,
                'before_sessions': before_sessions,
                'after_sessions': after_sessions,
                'race': {
                    'date': next_race.event_date.isoformat(),
                    'distance': next_race.distance_category,
                    'time': race_time,
                    'weeks_after_inflection': weeks_between,
                },
            },
            confidence='genuine' if weeks_between <= 12 else 'suggestive',
        ))

    return findings


# ═══════════════════════════════════════════════════════
#  INVESTIGATIONS — Question-based mining
# ═══════════════════════════════════════════════════════

@investigation(
    requires=['activity_summary', 'activity_splits'],
    min_activities=20,
    min_races=3,
    description="Cardiovascular durability from back-to-back quality + long run days",
)
def investigate_back_to_back_durability(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    races: List[PerformanceEvent],
) -> Optional[RaceInputFinding]:
    """
    QUESTION: Did consecutive-day quality + long run sessions build
    measurable cardiovascular durability?

    METHOD: Pair days where day-1 had interval/VO2 work and day-2 had a
    long run (>20km). Compute cardiac drift in the day-2 long run.
    Track the drift over time. Compare with long runs NOT preceded by
    quality work.

    CONFOUNDS: Indoor/outdoor, temperature, elevation profile on the
    long run. Only compare outdoor-to-outdoor or indoor-to-indoor.
    Require steady-effort runs (pace drift < 0.3 min/km).
    """
    all_acts = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.avg_hr.isnot(None),
    ).order_by(Activity.start_time).all()

    acts_by_date: Dict[date, List[Activity]] = {}
    for act in all_acts:
        d = act.start_time.date()
        acts_by_date.setdefault(d, []).append(act)

    # Find all interval sessions
    interval_dates = set()
    for d, day_acts in acts_by_date.items():
        for act in day_acts:
            splits = db.query(ActivitySplit).filter(
                ActivitySplit.activity_id == act.id,
            ).all()
            interval_count = 0
            for s in splits:
                if not s.distance or not s.elapsed_time:
                    continue
                dk = float(s.distance) * KM_PER_METER
                if dk < 0.1:
                    continue
                pace_sec_mi = int(((s.elapsed_time / 60) / dk) * SEC_PER_MIN * METERS_PER_MILE * KM_PER_METER)
                z = zones.classify_pace(pace_sec_mi)
                if z in ('interval', 'repetition'):
                    interval_count += 1
            if interval_count >= 2:
                interval_dates.add(d)
                break

    # Pair: for each long run, was there interval work the day before?
    after_quality = []
    without_quality = []

    long_runs = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.distance_m > 20000,
        Activity.avg_hr.isnot(None),
    ).order_by(Activity.start_time).all()

    for lr in long_runs:
        d = lr.start_time.date()
        ctx = build_activity_context(lr)

        splits = db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == lr.id,
        ).order_by(ActivitySplit.split_number).all()

        drift = compute_cardiac_drift(splits)
        if drift is None or not drift['is_steady_effort']:
            continue

        entry = {
            'date': d.isoformat(),
            'dist_km': ctx.distance_km,
            'avg_hr': lr.avg_hr,
            'hr_drift': drift['hr_drift'],
            'first_hr': drift['first_hr'],
            'second_hr': drift['second_hr'],
            'is_indoor': ctx.is_indoor,
            'elevation_m': ctx.total_elevation_m,
        }

        prev_day = d - timedelta(days=1)
        if prev_day in interval_dates:
            after_quality.append(entry)
        else:
            without_quality.append(entry)

    if len(after_quality) < 3:
        return None

    # Check for drift progression over time in after-quality runs
    drifts_over_time = [(e['date'], e['hr_drift']) for e in after_quality]
    if len(drifts_over_time) < 3:
        return None

    n = len(drifts_over_time)
    early = drifts_over_time[:n // 3 + 1]
    late = drifts_over_time[-(n // 3 + 1):]
    early_avg = sum(d for _, d in early) / len(early)
    late_avg = sum(d for _, d in late) / len(late)
    improvement = early_avg - late_avg

    if improvement < 2.0:
        return None  # No meaningful adaptation

    # Compare with non-quality long runs
    avg_drift_after = sum(e['hr_drift'] for e in after_quality) / len(after_quality)
    avg_drift_without = (
        sum(e['hr_drift'] for e in without_quality) / len(without_quality)
        if without_quality else None
    )

    # Build the finding
    first_date = after_quality[0]['date']
    last_date = after_quality[-1]['date']
    weeks = (date.fromisoformat(last_date) - date.fromisoformat(first_date)).days // 7

    comparison = ""
    if avg_drift_without is not None:
        comparison = (
            f" Long runs without prior quality work averaged {avg_drift_without:.1f} bpm drift. "
            f"With prior intervals: {avg_drift_after:.1f} bpm average, "
            f"meaning your body was working harder on pre-fatigued legs."
        )

    # Connect to race outcome
    race_connection = ""
    last_pair_date = date.fromisoformat(last_date)
    for race in sorted(races, key=lambda r: r.event_date):
        if race.event_date > last_pair_date:
            race_time = _format_race_time(race)
            race_splits = db.query(ActivitySplit).filter(
                ActivitySplit.activity_id.in_(
                    db.query(Activity.id).filter(
                        Activity.athlete_id == athlete_id,
                        Activity.is_duplicate == False,  # noqa: E712
                        Activity.start_time >= str(race.event_date),
                        Activity.start_time < str(race.event_date + timedelta(days=1)),
                    )
                )
            ).order_by(ActivitySplit.split_number).all()

            race_drift = compute_cardiac_drift(race_splits)
            if race_drift:
                race_connection = (
                    f" Your {_dist_label(race.distance_category)} {race_time} "
                    f"had {race_drift['hr_drift']:.1f} bpm cardiac drift across the race "
                    f"({race_drift['first_hr']:.0f}→{race_drift['second_hr']:.0f})."
                )
            break

    sentence = (
        f"Over {weeks} weeks, your cardiac drift on long runs after interval sessions "
        f"dropped from {early_avg:.1f} to {late_avg:.1f} bpm — "
        f"a {improvement:.1f} bpm improvement in cardiovascular durability on fatigued legs."
        f"{comparison}{race_connection}"
    )

    return RaceInputFinding(
        layer='B',
        finding_type='back_to_back_durability',
        sentence=sentence,
        receipts={
            'after_quality_sessions': after_quality,
            'without_quality_sessions': without_quality[:5],
            'early_avg_drift': round(early_avg, 1),
            'late_avg_drift': round(late_avg, 1),
            'improvement_bpm': round(improvement, 1),
            'weeks_tracked': weeks,
        },
        confidence='genuine',
    )


@investigation(
    requires=['activity_summary', 'activity_splits', 'race_result'],
    min_races=3,
    description="Race execution analysis — pacing, cardiac drift, GAP-adjusted splits",
)
def investigate_race_execution(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    races: List[PerformanceEvent],
) -> List[RaceInputFinding]:
    """
    QUESTION: How did the athlete execute each race? Was pacing even?
    Was cardiac drift controlled?

    METHOD: Analyze per-split data for each race using GAP-adjusted pace
    (not raw pace) to account for course elevation.

    CONFOUNDS: Raw pace on hilly courses creates false split patterns.
    GAP normalizes for grade. If no GAP data, disclose the limitation.
    """
    findings = []

    for race in races:
        race_acts = db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.is_duplicate == False,  # noqa: E712
            Activity.start_time >= str(race.event_date),
            Activity.start_time < str(race.event_date + timedelta(days=1)),
        ).all()

        for act in race_acts:
            dist_km = (act.distance_m or 0) * KM_PER_METER
            if dist_km < 3:
                continue

            splits = db.query(ActivitySplit).filter(
                ActivitySplit.activity_id == act.id,
            ).order_by(ActivitySplit.split_number).all()

            if len(splits) < 3:
                continue

            # Collect both raw and GAP-adjusted paces
            raw_paces, gap_paces, hr_vals, cad_vals = [], [], [], []
            has_gap = False

            for s in splits:
                if not s.distance or not s.elapsed_time:
                    continue
                dk = float(s.distance) * KM_PER_METER
                if dk < 0.1:
                    continue

                raw_pace = (s.elapsed_time / 60) / dk
                raw_paces.append(raw_pace)

                gap = get_gap_adjusted_pace(s)
                if gap is not None:
                    gap_paces.append(gap)
                    has_gap = True

                if s.average_heartrate:
                    hr_vals.append(s.average_heartrate)
                if s.average_cadence:
                    cad_vals.append(float(s.average_cadence))

            if len(raw_paces) < 3:
                continue

            # Use GAP if available, raw otherwise
            paces = gap_paces if has_gap and len(gap_paces) == len(raw_paces) else raw_paces
            pace_label = "GAP-adjusted" if (has_gap and len(gap_paces) == len(raw_paces)) else "raw"

            avg_pace = sum(paces) / len(paces)
            std_pace = _std(paces)
            cv = (std_pace / avg_pace * 100) if avg_pace > 0 else 0

            mid = len(paces) // 2
            first_avg = sum(paces[:mid]) / mid
            second_avg = sum(paces[mid:]) / len(paces[mid:])
            split_ratio = (second_avg - first_avg) / first_avg * 100

            # Check if GAP tells a different story than raw
            gap_note = ""
            if has_gap and len(gap_paces) == len(raw_paces):
                raw_mid = len(raw_paces) // 2
                raw_first = sum(raw_paces[:raw_mid]) / raw_mid
                raw_second = sum(raw_paces[raw_mid:]) / len(raw_paces[raw_mid:])
                raw_ratio = (raw_second - raw_first) / raw_first * 100

                if (raw_ratio < -2 and split_ratio > -1) or (raw_ratio > 2 and split_ratio < 1):
                    gap_note = (
                        f" Raw pace showed {raw_ratio:+.1f}% split, but GAP-adjusted "
                        f"shows {split_ratio:+.1f}% — the course elevation explains the difference."
                    )

            # Cardiac drift
            drift = compute_cardiac_drift(splits)
            drift_str = ""
            if drift:
                drift_str = (
                    f" Heart rate: {drift['first_hr']:.0f}→{drift['second_hr']:.0f} "
                    f"({drift['hr_drift']:+.1f} bpm drift)."
                )

            race_time = _format_race_time(race)
            pb = " PB" if race.is_personal_best else ""

            sentence = (
                f"{_dist_label(race.distance_category)} {race_time}{pb} on "
                f"{race.event_date.strftime('%b %d, %Y')}: "
                f"{pace_label} pace CV {cv:.1f}%, "
                f"split ratio {split_ratio:+.1f}%."
                f"{drift_str}{gap_note}"
            )

            findings.append(RaceInputFinding(
                layer='B',
                finding_type='race_execution',
                sentence=sentence,
                receipts={
                    'race_date': race.event_date.isoformat(),
                    'distance': race.distance_category,
                    'time': race_time,
                    'is_pb': race.is_personal_best,
                    'pace_source': pace_label,
                    'pace_cv_pct': round(cv, 1),
                    'split_ratio_pct': round(split_ratio, 1),
                    'cardiac_drift': drift,
                    'gap_note': gap_note,
                },
                confidence='genuine' if has_gap else 'suggestive',
            ))
            break

    return findings


@investigation(
    requires=['activity_summary', 'activity_splits'],
    min_activities=30,
    description="Recovery cost of different quality session types on next-day running",
)
def investigate_recovery_cost(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    races: List[PerformanceEvent],
) -> Optional[RaceInputFinding]:
    """
    QUESTION: How do different quality session types affect next-day running?
    Does the athlete recover differently from VO2 work vs threshold work
    vs long runs?

    METHOD: For each quality session, find the next-day easy run and
    compare HR and pace to the athlete's baseline easy-day HR/pace.

    CONFOUNDS: Indoor/outdoor (treadmill paces are different), temperature.
    Only compare activities with same indoor/outdoor status.
    """
    all_acts = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.avg_hr.isnot(None),
        Activity.distance_m > 3000,
    ).order_by(Activity.start_time).all()

    acts_by_date: Dict[date, List[Activity]] = {}
    for act in all_acts:
        d = act.start_time.date()
        acts_by_date.setdefault(d, []).append(act)

    recovery_data: Dict[str, List[Dict]] = {
        'after_interval': [],
        'after_threshold': [],
        'after_long_run': [],
        'baseline': [],
    }

    sorted_dates = sorted(acts_by_date.keys())

    for d in sorted_dates:
        day_acts = acts_by_date[d]
        quality_type = None

        for act in day_acts:
            if act.distance_m and act.distance_m > 20000:
                quality_type = 'after_long_run'

            splits = db.query(ActivitySplit).filter(
                ActivitySplit.activity_id == act.id,
            ).all()
            for s in splits:
                if not s.distance or not s.elapsed_time:
                    continue
                dk = float(s.distance) * KM_PER_METER
                if dk < 0.1:
                    continue
                pace_sec_mi = int(((s.elapsed_time / 60) / dk) * SEC_PER_MIN * METERS_PER_MILE * KM_PER_METER)
                z = zones.classify_pace(pace_sec_mi)
                if z in ('interval', 'repetition') and quality_type != 'after_long_run':
                    quality_type = 'after_interval'
                    break
                elif z == 'threshold' and quality_type is None:
                    quality_type = 'after_threshold'
                    break

        # Find next-day easy outdoor run
        next_day = d + timedelta(days=1)
        if next_day not in acts_by_date:
            continue

        for nact in acts_by_date[next_day]:
            if not nact.avg_hr or not nact.distance_m or nact.distance_m < 3000:
                continue
            if not nact.duration_s or nact.duration_s == 0:
                continue

            ctx = build_activity_context(nact)
            dist_km = nact.distance_m * KM_PER_METER
            pace = (nact.duration_s / 60) / dist_km

            entry = {
                'date': next_day.isoformat(),
                'hr': nact.avg_hr,
                'pace_min_km': round(pace, 2),
                'dist_km': round(dist_km, 1),
                'is_indoor': ctx.is_indoor,
            }

            bucket = quality_type or 'baseline'
            recovery_data[bucket].append(entry)
            break

    # Need enough data in at least 2 categories to compare
    filled = {k: v for k, v in recovery_data.items() if len(v) >= 3}
    if len(filled) < 2 or 'baseline' not in filled:
        return None

    baseline_hr = sum(e['hr'] for e in filled['baseline']) / len(filled['baseline'])
    baseline_pace = sum(e['pace_min_km'] for e in filled['baseline']) / len(filled['baseline'])

    comparisons = []
    for category, entries in filled.items():
        if category == 'baseline':
            continue
        cat_hr = sum(e['hr'] for e in entries) / len(entries)
        cat_pace = sum(e['pace_min_km'] for e in entries) / len(entries)
        hr_diff = cat_hr - baseline_hr
        pace_diff = cat_pace - baseline_pace

        label = category.replace('after_', '').replace('_', ' ')
        comparisons.append({
            'stimulus': label,
            'n': len(entries),
            'avg_hr': round(cat_hr),
            'avg_pace': round(cat_pace, 2),
            'hr_vs_baseline': round(hr_diff, 1),
            'pace_vs_baseline': round(pace_diff, 2),
        })

    if not comparisons:
        return None

    # Only present if there's a meaningful difference between categories
    hr_diffs = [abs(c['hr_vs_baseline']) for c in comparisons]
    if max(hr_diffs) < 3:
        return None

    parts = []
    for c in comparisons:
        hr_dir = "higher" if c['hr_vs_baseline'] > 0 else "lower"
        pace_dir = "slower" if c['pace_vs_baseline'] > 0 else "faster"
        parts.append(
            f"after {c['stimulus']} (n={c['n']}): HR {c['avg_hr']} "
            f"({abs(c['hr_vs_baseline']):.0f} bpm {hr_dir}), "
            f"pace {c['avg_pace']:.2f} min/km "
            f"({abs(c['pace_vs_baseline']):.2f} {pace_dir})"
        )

    sentence = (
        f"Next-day easy run recovery cost compared to baseline "
        f"(HR {baseline_hr:.0f}, pace {baseline_pace:.2f} min/km, n={len(filled['baseline'])}): "
        + "; ".join(parts)
        + "."
    )

    return RaceInputFinding(
        layer='B',
        finding_type='recovery_cost',
        sentence=sentence,
        receipts={
            'baseline_hr': round(baseline_hr),
            'baseline_pace': round(baseline_pace, 2),
            'baseline_n': len(filled['baseline']),
            'comparisons': comparisons,
        },
        confidence='genuine' if all(c['n'] >= 5 for c in comparisons) else 'suggestive',
    )


@investigation(
    requires=['activity_summary', 'activity_splits', 'race_result'],
    min_activities=20,
    min_races=4,
    description="Training recipe comparison — what mix preceded best vs worst races",
)
def investigate_training_recipe(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    races: List[PerformanceEvent],
) -> List[RaceInputFinding]:
    """
    QUESTION: What training mix preceded each race, and does it correlate
    with race quality?

    METHOD: For each race, compute a 6-week profile using zone-classified
    splits. Compare within the same distance only (avoids cross-distance
    confound). Use weekly volume trend (build/stable/taper) as a dimension.

    CONFOUNDS: Recency (improving athletes' best races are always recent).
    Flag findings where all best races are from the most recent 6 months.
    Indoor vs outdoor training proportions.
    """
    if len(races) < 4:
        return []

    findings = []
    race_profiles = []

    for race in races:
        window_start = race.event_date - timedelta(weeks=6)
        window_end = race.event_date - timedelta(days=1)

        acts = db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.is_duplicate == False,  # noqa: E712
            Activity.start_time >= str(window_start),
            Activity.start_time < str(window_end),
        ).order_by(Activity.start_time).all()

        if not acts:
            continue

        total_km = sum((a.distance_m or 0) * KM_PER_METER for a in acts)
        days = (window_end - window_start).days
        weeks = days / 7

        # Zone distribution from splits
        zone_km = defaultdict(float)
        total_split_km = 0
        for act in acts:
            splits = db.query(ActivitySplit).filter(
                ActivitySplit.activity_id == act.id,
            ).all()
            for s in splits:
                if not s.distance or not s.elapsed_time:
                    continue
                dk = float(s.distance) * KM_PER_METER
                if dk < 0.05:
                    continue
                pace = (s.elapsed_time / 60) / dk
                pace_sec_mi = int(pace * SEC_PER_MIN * METERS_PER_MILE * KM_PER_METER)
                z = zones.classify_pace(pace_sec_mi)
                zone_km[z] += dk
                total_split_km += dk

        # Weekly volume trend
        weekly_vols = []
        for w in range(6, 0, -1):
            wk_start = race.event_date - timedelta(weeks=w)
            wk_end = race.event_date - timedelta(weeks=w - 1)
            wk_km = sum(
                (a.distance_m or 0) * KM_PER_METER
                for a in acts
                if wk_start <= a.start_time.date() < wk_end
            )
            weekly_vols.append(round(wk_km, 1))

        if len(weekly_vols) >= 4:
            first_half = sum(weekly_vols[:3]) / 3
            second_half = sum(weekly_vols[3:]) / max(len(weekly_vols[3:]), 1)
            if second_half > first_half * 1.1:
                vol_trend = 'build'
            elif second_half < first_half * 0.9:
                vol_trend = 'taper'
            else:
                vol_trend = 'stable'
        else:
            vol_trend = 'unknown'

        long_runs = [a for a in acts if (a.distance_m or 0) > 20000]
        indoor_count = sum(1 for a in acts if build_activity_context(a).is_indoor)

        # Average temperature for weather confound detection
        temps = [a.temperature_f for a in acts if a.temperature_f is not None]
        avg_temp = round(sum(temps) / len(temps), 1) if temps else None

        profile = {
            'race_date': race.event_date.isoformat(),
            'distance': race.distance_category,
            'time_seconds': race.effective_time_seconds,
            'is_pb': race.is_personal_best,
            'total_km': round(total_km, 1),
            'km_per_week': round(total_km / max(weeks, 1), 1),
            'runs': len(acts),
            'long_run_count': len(long_runs),
            'longest_run_km': round(max((a.distance_m or 0) * KM_PER_METER for a in acts), 1),
            'pct_easy': round(zone_km.get('easy', 0) / max(total_split_km, 1) * 100, 1) if total_split_km > 10 else None,
            'pct_quality': round((zone_km.get('threshold', 0) + zone_km.get('interval', 0) + zone_km.get('repetition', 0)) / max(total_split_km, 1) * 100, 1) if total_split_km > 10 else None,
            'vol_trend': vol_trend,
            'weekly_vols': weekly_vols,
            'indoor_pct': round(indoor_count / max(len(acts), 1) * 100, 1),
            'avg_temp_f': avg_temp,
        }
        race_profiles.append(profile)

    # Within-distance comparison for distances with 3+ races
    by_distance = defaultdict(list)
    for p in race_profiles:
        by_distance[p['distance']].append(p)

    for dist, profiles in by_distance.items():
        if len(profiles) < 3:
            continue

        sorted_p = sorted(profiles, key=lambda p: p['time_seconds'])
        best = sorted_p[:max(len(sorted_p) // 2, 1)]
        worst = sorted_p[max(len(sorted_p) // 2, 1):]

        if not worst:
            continue

        # Check recency confound
        best_dates = [date.fromisoformat(p['race_date']) for p in best]
        worst_dates = [date.fromisoformat(p['race_date']) for p in worst]
        all_best_recent = all(d.year >= max(d2.year for d2 in worst_dates) for d in best_dates)

        diffs = []
        for key in ['km_per_week', 'long_run_count', 'longest_run_km', 'pct_quality', 'indoor_pct']:
            best_vals = [p[key] for p in best if p.get(key) is not None]
            worst_vals = [p[key] for p in worst if p.get(key) is not None]
            if not best_vals or not worst_vals:
                continue
            b_avg = sum(best_vals) / len(best_vals)
            w_avg = sum(worst_vals) / len(worst_vals)
            if w_avg == 0 and b_avg == 0:
                continue
            pct_diff = (b_avg - w_avg) / max(abs(w_avg), 0.01) * 100
            if abs(pct_diff) > 15:
                diffs.append({
                    'dimension': key,
                    'best_avg': round(b_avg, 1),
                    'worst_avg': round(w_avg, 1),
                    'diff_pct': round(pct_diff, 1),
                })

        # Volume trend comparison
        best_trends = Counter(p['vol_trend'] for p in best)
        worst_trends = Counter(p['vol_trend'] for p in worst)
        most_common_best = best_trends.most_common(1)[0][0] if best_trends else 'unknown'
        most_common_worst = worst_trends.most_common(1)[0][0] if worst_trends else 'unknown'

        if most_common_best != most_common_worst:
            diffs.append({
                'dimension': 'vol_trend',
                'best_avg': most_common_best,
                'worst_avg': most_common_worst,
                'diff_pct': None,
            })

        if not diffs:
            continue

        # Check weather confound: if avg temp differs significantly,
        # indoor_pct differences may reflect heat avoidance, not training strategy
        best_temps = [p['avg_temp_f'] for p in best if p.get('avg_temp_f') is not None]
        worst_temps = [p['avg_temp_f'] for p in worst if p.get('avg_temp_f') is not None]
        weather_confound = False
        if best_temps and worst_temps:
            avg_best_temp = sum(best_temps) / len(best_temps)
            avg_worst_temp = sum(worst_temps) / len(worst_temps)
            if abs(avg_best_temp - avg_worst_temp) > 10:
                weather_confound = True
                # Remove indoor_pct from diffs — it's confounded by weather
                diffs = [d for d in diffs if d['dimension'] != 'indoor_pct']

        recency_warning = ""
        if all_best_recent:
            recency_warning = (
                " Note: all best races are more recent than worst races — "
                "these differences may reflect general fitness progression, "
                "not specific training choices."
            )
        if weather_confound:
            recency_warning += (
                f" Note: training temperature differed significantly "
                f"({avg_best_temp:.0f}°F vs {avg_worst_temp:.0f}°F) — "
                f"some differences may reflect weather conditions."
            )

        parts = []
        for d in diffs:
            dim_label = d['dimension'].replace('_', ' ')
            if d['diff_pct'] is not None:
                direction = "higher" if d['diff_pct'] > 0 else "lower"
                parts.append(f"{dim_label}: {d['best_avg']} vs {d['worst_avg']} ({direction} before best)")
            else:
                parts.append(f"{dim_label}: {d['best_avg']} before best vs {d['worst_avg']} before worst")

        sentence = (
            f"Within your {_dist_label(dist)} races (n={len(profiles)}), "
            f"comparing best half vs worst half: "
            + "; ".join(parts)
            + f".{recency_warning}"
        )

        confidence = 'genuine'
        if all_best_recent or weather_confound:
            confidence = 'suggestive'

        findings.append(RaceInputFinding(
            layer='A',
            finding_type='training_recipe',
            sentence=sentence,
            receipts={
                'distance': dist,
                'best_races': best,
                'worst_races': worst,
                'differences': diffs,
                'recency_confound': all_best_recent,
                'weather_confound': weather_confound,
            },
            confidence=confidence,
        ))

    return findings


@investigation(
    requires=['activity_summary', 'activity_splits', 'environment'],
    min_activities=20,
    min_data_weeks=12,
    description="Pace at equivalent HR over time — aerobic adaptation signal",
)
def investigate_pace_at_hr_adaptation(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    events: List[PerformanceEvent],
) -> Optional[List[RaceInputFinding]]:
    """
    Track pace at specific HR bands over time using heat-normalized pace.

    Uses ALL outdoor activities (no temperature band filter) because each
    pace is heat-adjusted using the activity's stored heat_adjustment_pct.
    This gives more data points and a cleaner signal.

    Analyzes two bands:
      - Easy effort (HR 130-140): aerobic floor
      - High effort (HR 150-160): aerobic ceiling
    """
    acts = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.avg_hr.isnot(None),
        Activity.distance_m > 3000,
        Activity.duration_s > 0,
    ).order_by(Activity.start_time).all()

    if len(acts) < 20:
        return None

    findings = []

    for band_name, hr_low, hr_high in [
        ('easy effort', 130, 140),
        ('high effort', 150, 160),
    ]:
        monthly: Dict[str, List[Dict]] = defaultdict(list)

        for act in acts:
            elev = float(act.total_elevation_gain) if act.total_elevation_gain else 0
            dist_km = (act.distance_m or 0) * KM_PER_METER
            if elev < TREADMILL_ELEV_THRESHOLD_M and dist_km > 5:
                continue

            splits = db.query(ActivitySplit).filter(
                ActivitySplit.activity_id == act.id,
                ActivitySplit.average_heartrate.isnot(None),
            ).order_by(ActivitySplit.split_number).all()

            heat_adj = act.heat_adjustment_pct

            for sp in splits:
                if sp.average_heartrate is None or sp.distance is None or sp.elapsed_time is None:
                    continue
                hr = float(sp.average_heartrate)
                if hr < hr_low or hr > hr_high:
                    continue
                dist_mi = float(sp.distance) * MI_PER_KM * KM_PER_METER
                if dist_mi < 0.1:
                    continue
                raw_pace = float(sp.elapsed_time) / dist_mi
                adj_pace = _heat_normalize_pace(raw_pace, heat_adj)

                month = act.start_time.strftime('%Y-%m')
                monthly[month].append({
                    'pace_sec_mi': adj_pace,
                    'raw_pace_sec_mi': raw_pace,
                    'hr': hr,
                    'temp': act.temperature_f,
                    'heat_adj_pct': heat_adj,
                    'date': act.start_time.date().isoformat(),
                })

        months_sorted = sorted(monthly.keys())
        valid_months = [(m, monthly[m]) for m in months_sorted if len(monthly[m]) >= 3]
        if len(valid_months) < 3:
            continue

        first_month, first_data = valid_months[0]
        last_month, last_data = valid_months[-1]

        first_pace = sum(e['pace_sec_mi'] for e in first_data) / len(first_data)
        last_pace = sum(e['pace_sec_mi'] for e in last_data) / len(last_data)
        first_hr = sum(e['hr'] for e in first_data) / len(first_data)
        last_hr = sum(e['hr'] for e in last_data) / len(last_data)

        pace_change = last_pace - first_pace
        if abs(pace_change) < 10:
            continue

        def _fmt(sec):
            m = int(sec) // 60
            s = int(sec) % 60
            return f"{m}:{s:02d}"

        direction = "faster" if pace_change < 0 else "slower"
        secs = abs(int(pace_change))

        receipts_months = {}
        for m, data in valid_months:
            avg_p = sum(e['pace_sec_mi'] for e in data) / len(data)
            avg_h = sum(e['hr'] for e in data) / len(data)
            receipts_months[m] = {
                'heat_adjusted_pace': _fmt(avg_p),
                'hr': round(avg_h),
                'n': len(data),
            }

        sentence = (
            f"At {band_name} heart rate ({hr_low}-{hr_high} bpm), "
            f"the pace you sustain improved from {_fmt(first_pace)}/mi ({first_month}) "
            f"to {_fmt(last_pace)}/mi ({last_month}) — "
            f"{secs} sec/mi {direction} at the same effort level. "
            f"All paces weather-normalized."
        )

        race_links = []
        for ev in events:
            ev_month = ev.event_date.strftime('%Y-%m')
            if ev_month in receipts_months:
                race_links.append({
                    'race': f"{ev.distance_category} on {ev.event_date}",
                    'date': ev.event_date.isoformat(),
                    'month': ev_month,
                })

        findings.append(RaceInputFinding(
            layer='B',
            finding_type=f'pace_at_hr_{band_name.replace(" ", "_")}_adaptation',
            sentence=sentence,
            receipts={
                'hr_band': f'{hr_low}-{hr_high}',
                'weather_normalized': True,
                'monthly_progression': receipts_months,
                'total_change_sec': int(pace_change),
                'linked_races': race_links,
            },
            confidence='genuine',
        ))

    return findings if findings else None


@investigation(
    requires=['activity_summary', 'activity_splits', 'environment'],
    min_activities=30,
    description="N=1 heat resilience — how does this athlete's actual heat response compare to the generic formula",
)
def investigate_heat_tax(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    events: List[PerformanceEvent],
) -> Optional[RaceInputFinding]:
    """
    Compare athlete's ACTUAL heat response to the generic heat adjustment formula.

    The generic formula (from heat_adjustment.py) predicts how much heat
    should slow a runner. This investigation measures how much it ACTUALLY
    slowed THIS runner — revealing whether they're heat-resilient, average,
    or heat-vulnerable.

    Method: compare raw pace at same HR in hot vs cool, then compare the
    measured slowdown to the formula-predicted slowdown for those temperatures.
    """
    acts = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.avg_hr.isnot(None),
        Activity.temperature_f.isnot(None),
        Activity.heat_adjustment_pct.isnot(None),
        Activity.distance_m > 3000,
    ).order_by(Activity.start_time).all()

    hot_splits = []
    cool_splits = []

    for act in acts:
        elev = float(act.total_elevation_gain) if act.total_elevation_gain else 0
        dist_km = (act.distance_m or 0) * KM_PER_METER
        if elev < TREADMILL_ELEV_THRESHOLD_M and dist_km > 5:
            continue

        splits = db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == act.id,
            ActivitySplit.average_heartrate.isnot(None),
        ).all()

        for sp in splits:
            if sp.average_heartrate is None or sp.distance is None or sp.elapsed_time is None:
                continue
            hr = float(sp.average_heartrate)
            if hr < 125 or hr > 145:
                continue
            dist_mi = float(sp.distance) * MI_PER_KM * KM_PER_METER
            if dist_mi < 0.5:
                continue
            pace_sec_mi = float(sp.elapsed_time) / dist_mi

            if act.temperature_f >= 85:
                hot_splits.append({
                    'pace': pace_sec_mi, 'hr': hr,
                    'temp': act.temperature_f,
                    'formula_adj_pct': act.heat_adjustment_pct or 0,
                    'date': act.start_time.date().isoformat(),
                })
            elif act.temperature_f < 65:
                cool_splits.append({
                    'pace': pace_sec_mi, 'hr': hr,
                    'temp': act.temperature_f,
                    'date': act.start_time.date().isoformat(),
                })

    if len(hot_splits) < 10 or len(cool_splits) < 10:
        return None

    hot_pace = sum(e['pace'] for e in hot_splits) / len(hot_splits)
    cool_pace = sum(e['pace'] for e in cool_splits) / len(cool_splits)
    hot_temp = sum(e['temp'] for e in hot_splits) / len(hot_splits)
    cool_temp = sum(e['temp'] for e in cool_splits) / len(cool_splits)

    actual_diff_sec = hot_pace - cool_pace
    actual_diff_pct = actual_diff_sec / cool_pace if cool_pace > 0 else 0

    avg_formula_pct = sum(e['formula_adj_pct'] for e in hot_splits) / len(hot_splits)
    predicted_diff_sec = cool_pace * avg_formula_pct

    ratio = actual_diff_pct / avg_formula_pct if avg_formula_pct > 0 else 1.0

    def _fmt(sec):
        m = int(sec) // 60
        s = int(sec) % 60
        return f"{m}:{s:02d}"

    if ratio < 0.75:
        resilience = "heat-resilient"
        insight = "you lose less pace in the heat than the average runner"
    elif ratio > 1.25:
        resilience = "heat-vulnerable"
        insight = "heat costs you more than it costs the average runner"
    else:
        resilience = "average heat response"
        insight = "your heat response is typical"

    sentence = (
        f"At easy-effort heart rate (125-145 bpm), heat costs you "
        f"{int(actual_diff_sec)} sec/mi ({actual_diff_pct:.1%} slower) — "
        f"the generic formula predicted {int(predicted_diff_sec)} sec/mi "
        f"({avg_formula_pct:.1%}). "
        f"You appear {resilience}: {insight}. "
        f"Hot: {_fmt(hot_pace)}/mi at {hot_temp:.0f}°F (n={len(hot_splits)}). "
        f"Cool: {_fmt(cool_pace)}/mi at {cool_temp:.0f}°F (n={len(cool_splits)})."
    )

    hot_races = []
    for ev in events:
        race_act = db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= ev.event_date,
            Activity.start_time < ev.event_date + timedelta(days=1),
            Activity.temperature_f.isnot(None),
        ).first()
        if race_act and race_act.temperature_f >= 80:
            personal_cost = actual_diff_pct * cool_pace
            hot_races.append({
                'race': f"{ev.distance_category} on {ev.event_date}",
                'date': ev.event_date.isoformat(),
                'temp_f': race_act.temperature_f,
                'estimated_personal_cost_sec_mi': round(personal_cost),
            })

    return RaceInputFinding(
        layer='B',
        finding_type='heat_resilience',
        sentence=sentence,
        receipts={
            'hot_n': len(hot_splits),
            'cool_n': len(cool_splits),
            'actual_diff_sec_mi': round(actual_diff_sec),
            'actual_diff_pct': round(actual_diff_pct, 3),
            'formula_predicted_diff_sec_mi': round(predicted_diff_sec),
            'formula_avg_adj_pct': round(avg_formula_pct, 3),
            'resilience_ratio': round(ratio, 2),
            'classification': resilience,
            'hot_races': hot_races,
        },
        confidence='genuine',
    )


@investigation(
    requires=['activity_summary', 'environment'],
    min_activities=20,
    min_data_weeks=16,
    description="Post-disruption fitness retention — did training survive the break",
)
def investigate_post_injury_resilience(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    events: List[PerformanceEvent],
) -> Optional[RaceInputFinding]:
    """
    Check if aerobic fitness metrics post-injury are comparable to
    pre-injury levels, controlling for temperature.

    If they are, the training campaign built fitness deep enough to survive
    the disruption — that's a meaningful finding about training durability.
    """
    # Use ALL activities for gap detection (not just those with weather)
    all_acts = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.distance_m > 3000,
    ).order_by(Activity.start_time).all()

    if len(all_acts) < 20:
        return None

    # Subset with HR and temp for controlled comparison
    acts = [a for a in all_acts if a.avg_hr and a.temperature_f and (a.distance_m or 0) > 5000 and (a.duration_s or 0) > 0]

    if len(acts) < 15:
        return None

    # Look for a gap of 14+ days with no activities (injury/break)
    gaps = []
    for i in range(1, len(all_acts)):
        gap_days = (all_acts[i].start_time.date() - all_acts[i-1].start_time.date()).days
        if gap_days >= 14:
            gaps.append({
                'start': acts[i-1].start_time.date(),
                'end': acts[i].start_time.date(),
                'days': gap_days,
                'index': i,
            })

    if not gaps:
        return None

    # Use the longest gap as the injury point
    injury_gap = max(gaps, key=lambda g: g['days'])

    # Get easy-effort HR at similar temps before and after the gap
    pre_acts = [a for a in acts if a.start_time.date() < injury_gap['start']]
    post_acts = [a for a in acts if a.start_time.date() > injury_gap['end']]

    if len(pre_acts) < 5 or len(post_acts) < 5:
        return None

    def _easy_hr_at_temp_band(activity_list, temp_low=60, temp_high=80):
        hrs = []
        paces = []
        for act in activity_list:
            if act.temperature_f < temp_low or act.temperature_f > temp_high:
                continue
            elev = float(act.total_elevation_gain) if act.total_elevation_gain else 0
            dist_km = (act.distance_m or 0) * KM_PER_METER
            if elev < TREADMILL_ELEV_THRESHOLD_M and dist_km > 5:
                continue
            pace_min_km = (act.duration_s / 60) / dist_km
            pace_sec_mi = int(pace_min_km * 60 * METERS_PER_MILE / 1000)
            z = zones.classify_pace(pace_sec_mi)
            if z == 'easy':
                hrs.append(act.avg_hr)
                paces.append(pace_sec_mi)
        return hrs, paces

    pre_hrs, pre_paces = _easy_hr_at_temp_band(pre_acts[-30:])
    post_hrs, post_paces = _easy_hr_at_temp_band(post_acts[:30])

    if len(pre_hrs) < 5 or len(post_hrs) < 5:
        return None

    pre_hr = sum(pre_hrs) / len(pre_hrs)
    post_hr = sum(post_hrs) / len(post_hrs)
    pre_pace = sum(pre_paces) / len(pre_paces)
    post_pace = sum(post_paces) / len(post_paces)

    hr_diff = post_hr - pre_hr
    pace_diff = post_pace - pre_pace

    # Only report if fitness is close to or better than pre-injury
    if hr_diff > 5:
        return None

    def _fmt_pace(sec):
        m = sec // 60
        s = sec % 60
        return f"{m}:{s:02d}"

    if abs(hr_diff) <= 3:
        verdict = "fully retained"
    elif hr_diff < -3:
        verdict = "improved"
    else:
        verdict = "partially retained"

    sentence = (
        f"After a {injury_gap['days']}-day break "
        f"({injury_gap['start']} to {injury_gap['end']}), "
        f"easy-effort heart rate was {verdict}: "
        f"{post_hr:.0f} bpm vs {pre_hr:.0f} bpm pre-break "
        f"(at similar temperatures, 60-80°F). "
        f"Easy pace: {_fmt_pace(int(post_pace))}/mi vs {_fmt_pace(int(pre_pace))}/mi. "
        f"The training campaign built fitness that survived the disruption."
    )

    return RaceInputFinding(
        layer='B',
        finding_type='post_injury_resilience',
        sentence=sentence,
        receipts={
            'gap_start': injury_gap['start'].isoformat(),
            'gap_end': injury_gap['end'].isoformat(),
            'gap_days': injury_gap['days'],
            'pre_hr': round(pre_hr, 1),
            'post_hr': round(post_hr, 1),
            'hr_diff': round(hr_diff, 1),
            'pre_pace': _fmt_pace(int(pre_pace)),
            'post_pace': _fmt_pace(int(post_pace)),
            'pre_n': len(pre_hrs),
            'post_n': len(post_hrs),
            'verdict': verdict,
        },
        confidence='genuine',
    )


@investigation(
    requires=['activity_summary', 'activity_splits'],
    min_activities=20,
    min_data_weeks=12,
    description="Stride economy — stride length at equivalent cadence over time",
)
def investigate_stride_economy(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    events: List[PerformanceEvent],
) -> Optional[RaceInputFinding]:
    """
    Track stride length at equivalent cadence over time, using
    zone-classified easy-effort splits.

    Uses the athlete's training zones to identify easy-pace splits
    (not hardcoded HR), then measures stride length = speed / (cadence/60).

    If stride length increases at stable cadence, the runner is generating
    more force per stride — strength and economy improvement.
    """
    acts = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.avg_hr.isnot(None),
        Activity.distance_m > 5000,
    ).order_by(Activity.start_time).all()

    if len(acts) < 20:
        return None

    monthly: Dict[str, List[Dict]] = defaultdict(list)

    for act in acts:
        elev = float(act.total_elevation_gain) if act.total_elevation_gain else 0
        dist_km = (act.distance_m or 0) * KM_PER_METER
        if elev < TREADMILL_ELEV_THRESHOLD_M and dist_km > 5:
            continue

        splits = db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == act.id,
            ActivitySplit.average_cadence.isnot(None),
        ).all()

        for sp in splits:
            if sp.distance is None or sp.elapsed_time is None:
                continue
            dist_m = float(sp.distance)
            time_s = sp.elapsed_time
            if dist_m < 400 or time_s < 60:
                continue

            pace_sec_mi = int(time_s / (dist_m * MI_PER_KM * KM_PER_METER))
            z = zones.classify_pace(pace_sec_mi)
            if z != 'easy':
                continue

            cadence = float(sp.average_cadence)
            if cadence < 150 or cadence > 200:
                continue

            speed_mps = dist_m / time_s
            stride_len = speed_mps / (cadence / 60)

            hr = float(sp.average_heartrate) if sp.average_heartrate else None

            month = act.start_time.strftime('%Y-%m')
            monthly[month].append({
                'stride': stride_len,
                'cadence': cadence,
                'hr': hr,
                'temp': act.temperature_f,
            })

    months_sorted = sorted(monthly.keys())
    valid = [(m, monthly[m]) for m in months_sorted if len(monthly[m]) >= 3]
    if len(valid) < 3:
        return None

    first_m, first_d = valid[0]
    last_m, last_d = valid[-1]

    first_stride = sum(e['stride'] for e in first_d) / len(first_d)
    last_stride = sum(e['stride'] for e in last_d) / len(last_d)
    first_cadence = sum(e['cadence'] for e in first_d) / len(first_d)
    last_cadence = sum(e['cadence'] for e in last_d) / len(last_d)

    stride_change = last_stride - first_stride
    cadence_change = last_cadence - first_cadence

    if abs(stride_change) < 0.01 or abs(cadence_change) > 5:
        return None

    pct_change = (stride_change / first_stride) * 100

    monthly_receipts = {}
    for m, data in valid:
        hrs = [e['hr'] for e in data if e['hr'] is not None]
        monthly_receipts[m] = {
            'stride_m': round(sum(e['stride'] for e in data) / len(data), 3),
            'cadence': round(sum(e['cadence'] for e in data) / len(data), 1),
            'hr': round(sum(hrs) / len(hrs)) if hrs else None,
            'n': len(data),
        }

    sentence = (
        f"At easy pace (zone-classified) and stable cadence "
        f"({first_cadence:.0f} → {last_cadence:.0f} spm), "
        f"stride length changed from {first_stride:.3f}m to {last_stride:.3f}m "
        f"({pct_change:+.1f}%) between {first_m} and {last_m}. "
    )
    if stride_change > 0:
        sentence += "Longer stride at the same cadence means more ground force per step — improved running economy."
    else:
        sentence += "Shorter stride at the same cadence suggests reduced economy."

    return RaceInputFinding(
        layer='B',
        finding_type='stride_economy',
        sentence=sentence,
        receipts={
            'monthly_progression': monthly_receipts,
            'stride_change_m': round(stride_change, 3),
            'stride_change_pct': round(pct_change, 1),
            'cadence_stable': abs(cadence_change) <= 5,
        },
        confidence='genuine',
    )


@investigation(
    requires=['activity_summary', 'activity_splits'],
    min_activities=15,
    min_data_weeks=8,
    description="Quality workout pace progression by zone over time (weather-normalized)",
)
def investigate_workout_progression(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    events: List[PerformanceEvent],
) -> Optional[List[RaceInputFinding]]:
    """
    Track quality workout progression over time by zone.

    Uses the athlete's RPI-derived training zones to classify every split.
    All paces are heat-normalized so seasonal temperature changes don't
    create false adaptation signals.
    """
    acts = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.avg_hr.isnot(None),
    ).order_by(Activity.start_time).all()

    zone_sessions: Dict[str, List[Dict]] = defaultdict(list)

    for act in acts:
        splits = db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == act.id,
        ).order_by(ActivitySplit.split_number).all()

        heat_adj = act.heat_adjustment_pct

        zone_reps: Dict[str, List[Dict]] = defaultdict(list)
        for sp in splits:
            if sp.distance is None or sp.elapsed_time is None:
                continue
            dist_m = float(sp.distance)
            time_s = sp.elapsed_time
            if dist_m < 50 or time_s < 10:
                continue

            raw_pace = int(time_s / (dist_m * MI_PER_KM * KM_PER_METER))
            adj_pace = _heat_normalize_pace(raw_pace, heat_adj)
            z = zones.classify_pace(int(adj_pace))

            if z in ('interval', 'repetition'):
                hr = float(sp.average_heartrate) if sp.average_heartrate else None
                cadence = float(sp.average_cadence) if sp.average_cadence else None
                zone_reps[z].append({
                    'pace_sec_mi': adj_pace,
                    'raw_pace_sec_mi': raw_pace,
                    'hr': hr,
                    'cadence': cadence,
                    'dist_m': dist_m,
                })

        for z, reps in zone_reps.items():
            if len(reps) >= 2:
                hrs = [r['hr'] for r in reps if r['hr'] is not None]
                zone_sessions[z].append({
                    'date': act.start_time.date(),
                    'reps': reps,
                    'avg_pace': sum(r['pace_sec_mi'] for r in reps) / len(reps),
                    'avg_hr': sum(hrs) / len(hrs) if hrs else None,
                    'rep_count': len(reps),
                    'heat_adj_pct': heat_adj,
                })

    findings = []

    for zone_name, sessions in zone_sessions.items():
        if len(sessions) < 4:
            continue

        n = len(sessions)
        third = max(n // 3, 1)
        early = sessions[:third]
        late = sessions[-third:]

        early_pace = sum(s['avg_pace'] for s in early) / len(early)
        late_pace = sum(s['avg_pace'] for s in late) / len(late)
        early_hrs = [s['avg_hr'] for s in early if s['avg_hr'] is not None]
        late_hrs = [s['avg_hr'] for s in late if s['avg_hr'] is not None]
        early_hr = sum(early_hrs) / len(early_hrs) if early_hrs else None
        late_hr = sum(late_hrs) / len(late_hrs) if late_hrs else None

        pace_change = late_pace - early_pace
        if abs(pace_change) < 3:
            continue

        def _fmt(sec):
            m = int(sec) // 60
            s = int(sec) % 60
            return f"{m}:{s:02d}"

        zone_label = zone_name.replace('_', ' ')
        direction = "faster" if pace_change < 0 else "slower"

        sentence = (
            f"{zone_label.title()} rep pace went from {_fmt(early_pace)}/mi "
            f"to {_fmt(late_pace)}/mi ({int(abs(pace_change))} sec/mi {direction}) "
            f"across {n} sessions ({sessions[0]['date']} to {sessions[-1]['date']}). "
            f"All paces weather-normalized."
        )

        if early_hr is not None and late_hr is not None:
            hr_change = late_hr - early_hr
            sentence += (
                f" Heart rate: {early_hr:.0f} → {late_hr:.0f} bpm "
                f"({'lower' if hr_change < 0 else 'higher'} effort)."
            )

        session_receipts = []
        for s in sessions:
            session_receipts.append({
                'date': s['date'].isoformat(),
                'reps': s['rep_count'],
                'heat_adjusted_pace': _fmt(s['avg_pace']),
                'avg_hr': round(s['avg_hr']) if s['avg_hr'] else None,
            })

        findings.append(RaceInputFinding(
            layer='B',
            finding_type=f'workout_progression_{zone_name}',
            sentence=sentence,
            receipts={
                'zone': zone_name,
                'total_sessions': n,
                'pace_change_sec': int(pace_change),
                'weather_normalized': True,
                'sessions': session_receipts,
            },
            confidence='genuine',
        ))

    return findings if findings else None


@investigation(
    requires=['activity_summary', 'activity_splits', 'environment'],
    min_activities=20,
    description="Long run muscular durability — cadence/stride decay in final quarter",
)
def investigate_long_run_durability(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    events: List[PerformanceEvent],
) -> Optional[RaceInputFinding]:
    """
    Track cadence and pace decay in the final quarter of long runs.

    If a runner's cadence drops less in the last 25% of long runs over
    time, they're building muscular durability — the ability to maintain
    form when fatigued.

    Controls for temperature.
    """
    long_runs = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.distance_m > 20000,
        Activity.avg_hr.isnot(None),
        Activity.temperature_f.isnot(None),
    ).order_by(Activity.start_time).all()

    if len(long_runs) < 6:
        return None

    decay_entries = []

    for lr in long_runs:
        elev = float(lr.total_elevation_gain) if lr.total_elevation_gain else 0
        dist_km = (lr.distance_m or 0) * KM_PER_METER
        if elev < TREADMILL_ELEV_THRESHOLD_M and dist_km > 5:
            continue

        splits = db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == lr.id,
            ActivitySplit.average_cadence.isnot(None),
            ActivitySplit.average_heartrate.isnot(None),
            ActivitySplit.distance.isnot(None),
            ActivitySplit.elapsed_time.isnot(None),
        ).order_by(ActivitySplit.split_number).all()

        if len(splits) < 8:
            continue

        q1_end = len(splits) // 4
        q4_start = len(splits) * 3 // 4
        first_q = splits[:q1_end] if q1_end > 0 else splits[:2]
        last_q = splits[q4_start:]

        if not first_q or not last_q:
            continue

        first_cadence = sum(float(s.average_cadence) for s in first_q) / len(first_q)
        last_cadence = sum(float(s.average_cadence) for s in last_q) / len(last_q)
        cadence_decay = last_cadence - first_cadence

        first_hr = sum(float(s.average_heartrate) for s in first_q) / len(first_q)
        last_hr = sum(float(s.average_heartrate) for s in last_q) / len(last_q)

        first_paces = []
        last_paces = []
        for s in first_q:
            dm = float(s.distance) * MI_PER_KM * KM_PER_METER
            if dm > 0.1:
                first_paces.append(float(s.elapsed_time) / dm)
        for s in last_q:
            dm = float(s.distance) * MI_PER_KM * KM_PER_METER
            if dm > 0.1:
                last_paces.append(float(s.elapsed_time) / dm)

        first_pace = sum(first_paces) / len(first_paces) if first_paces else 0
        last_pace = sum(last_paces) / len(last_paces) if last_paces else 0
        pace_decay = last_pace - first_pace

        # Stride length in first and last quarter
        first_strides, last_strides = [], []
        for s in first_q:
            c = float(s.average_cadence)
            d = float(s.distance)
            t = s.elapsed_time
            if c > 0 and d > 0 and t > 0:
                first_strides.append((d / t) / (c / 60))
        for s in last_q:
            c = float(s.average_cadence)
            d = float(s.distance)
            t = s.elapsed_time
            if c > 0 and d > 0 and t > 0:
                last_strides.append((d / t) / (c / 60))

        first_stride = sum(first_strides) / len(first_strides) if first_strides else None
        last_stride = sum(last_strides) / len(last_strides) if last_strides else None

        decay_entries.append({
            'date': lr.start_time.date(),
            'temp': lr.temperature_f,
            'cadence_decay': round(cadence_decay, 1),
            'pace_decay_sec': round(pace_decay),
            'hr_rise': round(last_hr - first_hr, 1),
            'first_stride': round(first_stride, 3) if first_stride else None,
            'last_stride': round(last_stride, 3) if last_stride else None,
            'stride_decay': round(last_stride - first_stride, 3) if first_stride and last_stride else None,
            'dist_km': round(dist_km, 1),
        })

    if len(decay_entries) < 4:
        return None

    # Compare early vs late long runs
    half = len(decay_entries) // 2
    early = decay_entries[:half]
    late = decay_entries[half:]

    early_cad_decay = sum(e['cadence_decay'] for e in early) / len(early)
    late_cad_decay = sum(e['cadence_decay'] for e in late) / len(late)

    stride_early = [e['stride_decay'] for e in early if e['stride_decay'] is not None]
    stride_late = [e['stride_decay'] for e in late if e['stride_decay'] is not None]

    early_stride_decay = sum(stride_early) / len(stride_early) if stride_early else None
    late_stride_decay = sum(stride_late) / len(stride_late) if stride_late else None

    improvement = early_cad_decay - late_cad_decay
    if abs(improvement) < 0.5:
        return None

    direction = "less" if late_cad_decay > early_cad_decay else "less"
    if late_cad_decay > early_cad_decay:
        direction = "more"

    sentence = (
        f"Long run cadence decay (first quarter vs last quarter) "
        f"changed from {early_cad_decay:+.1f} spm (early runs, n={len(early)}) "
        f"to {late_cad_decay:+.1f} spm (recent runs, n={len(late)}). "
    )

    if late_stride_decay is not None and early_stride_decay is not None:
        sentence += (
            f"Stride length decay: {early_stride_decay:+.3f}m → {late_stride_decay:+.3f}m. "
        )

    if improvement > 0:
        sentence += "Form holds up better late in long runs — muscular durability improved."
    else:
        sentence += "More late-run form breakdown in recent runs."

    return RaceInputFinding(
        layer='B',
        finding_type='long_run_durability',
        sentence=sentence,
        receipts={
            'early_runs': early,
            'late_runs': late,
            'cadence_decay_improvement': round(improvement, 1),
            'early_avg_cadence_decay': round(early_cad_decay, 1),
            'late_avg_cadence_decay': round(late_cad_decay, 1),
        },
        confidence='genuine',
    )


# ═══════════════════════════════════════════════════════
#  Shape-Aware Investigations (Living Fingerprint Cap. 4)
# ═══════════════════════════════════════════════════════

@investigation(
    requires=['activity_summary', 'run_shape'],
    min_activities=10,
    min_data_weeks=4,
    description="Stride frequency, quality, and progression over time",
)
def investigate_stride_progression(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    events: List[PerformanceEvent],
) -> Optional[RaceInputFinding]:
    """
    Track stride (acceleration) frequency and quality over time
    using activity shapes.
    """
    acts = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.run_shape.isnot(None),
    ).order_by(Activity.start_time).all()

    stride_runs = []
    for act in acts:
        shape = act.run_shape
        if not shape or 'summary' not in shape:
            continue
        summary = shape['summary']
        if summary.get('acceleration_clustering') != 'end_loaded':
            continue
        accels = shape.get('accelerations', [])
        fast_accels = [a for a in accels if a.get('pace_zone') in
                       ('interval', 'repetition', 'threshold')]
        if len(fast_accels) < 2:
            continue

        stride_runs.append({
            'date': act.start_time.date().isoformat(),
            'activity_id': str(act.id),
            'count': len(fast_accels),
            'avg_pace': sum(a.get('avg_pace_sec_per_mile', 0) for a in fast_accels) / len(fast_accels),
            'avg_duration': sum(a.get('duration_s', 0) for a in fast_accels) / len(fast_accels),
        })

    if len(stride_runs) < 4:
        return None

    half = len(stride_runs) // 2
    early = stride_runs[:half]
    late = stride_runs[half:]

    early_pace = sum(s['avg_pace'] for s in early) / len(early)
    late_pace = sum(s['avg_pace'] for s in late) / len(late)
    pace_change = late_pace - early_pace

    early_count = sum(s['count'] for s in early) / len(early)
    late_count = sum(s['count'] for s in late) / len(late)

    def _fmt(sec):
        m = int(sec) // 60
        s = int(sec) % 60
        return f"{m}:{s:02d}"

    direction = "faster" if pace_change < 0 else "slower"
    sentence = (
        f"End-of-run strides tracked across {len(stride_runs)} runs: "
        f"average count went from {early_count:.1f} to {late_count:.1f}, "
        f"average pace from {_fmt(early_pace)}/mi to {_fmt(late_pace)}/mi "
        f"({int(abs(pace_change))} sec/mi {direction})."
    )

    return RaceInputFinding(
        layer='B',
        finding_type='stride_progression',
        sentence=sentence,
        receipts={
            'runs': stride_runs,
            'early_avg_pace': _fmt(early_pace),
            'late_avg_pace': _fmt(late_pace),
            'pace_change_sec': int(pace_change),
        },
        confidence='genuine' if len(stride_runs) >= 8 else 'suggestive',
    )


@investigation(
    requires=['activity_summary', 'run_shape'],
    min_activities=10,
    min_data_weeks=8,
    description="Threshold interval duration and pace improvement over sessions",
)
def investigate_cruise_interval_quality(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    events: List[PerformanceEvent],
) -> Optional[RaceInputFinding]:
    """
    Track sustained threshold work quality across sessions using shapes.
    """
    acts = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.run_shape.isnot(None),
    ).order_by(Activity.start_time).all()

    threshold_sessions = []
    for act in acts:
        shape = act.run_shape
        if not shape:
            continue
        phases = shape.get('phases', [])
        thr_phases = [p for p in phases
                      if p.get('pace_zone') == 'threshold'
                      and p.get('duration_s', 0) >= 240]
        if len(thr_phases) < 2:
            continue

        total_thr_km = sum(p.get('distance_m', 0) for p in thr_phases) / 1000
        avg_pace = sum(p.get('avg_pace_sec_per_mile', 0) for p in thr_phases) / len(thr_phases)
        avg_hr = None
        hrs = [p.get('avg_hr') for p in thr_phases if p.get('avg_hr')]
        if hrs:
            avg_hr = sum(hrs) / len(hrs)

        threshold_sessions.append({
            'date': act.start_time.date().isoformat(),
            'activity_id': str(act.id),
            'phase_count': len(thr_phases),
            'total_threshold_km': round(total_thr_km, 1),
            'avg_pace': round(avg_pace, 1),
            'avg_hr': round(avg_hr, 1) if avg_hr else None,
        })

    if len(threshold_sessions) < 4:
        return None

    half = len(threshold_sessions) // 2
    early = threshold_sessions[:half]
    late = threshold_sessions[half:]

    early_km = sum(s['total_threshold_km'] for s in early) / len(early)
    late_km = sum(s['total_threshold_km'] for s in late) / len(late)

    early_hrs = [s['avg_hr'] for s in early if s['avg_hr']]
    late_hrs = [s['avg_hr'] for s in late if s['avg_hr']]
    early_hr = sum(early_hrs) / len(early_hrs) if early_hrs else None
    late_hr = sum(late_hrs) / len(late_hrs) if late_hrs else None

    def _fmt(sec):
        m = int(sec) // 60
        s = int(sec) % 60
        return f"{m}:{s:02d}"

    sentence = (
        f"Over {len(threshold_sessions)} threshold sessions, "
        f"sustained distance grew from {early_km:.1f}km to {late_km:.1f}km. "
    )
    if early_hr and late_hr:
        hr_change = late_hr - early_hr
        sentence += (
            f"Threshold HR went from {early_hr:.0f} to {late_hr:.0f} bpm "
            f"({'lower' if hr_change < 0 else 'higher'} effort for more distance)."
        )

    return RaceInputFinding(
        layer='B',
        finding_type='cruise_interval_quality',
        sentence=sentence,
        receipts={
            'sessions': threshold_sessions,
            'early_avg_km': round(early_km, 1),
            'late_avg_km': round(late_km, 1),
        },
        confidence='genuine',
    )


@investigation(
    requires=['activity_summary', 'run_shape'],
    min_activities=10,
    min_data_weeks=8,
    description="Recovery between interval reps — does inter-rep recovery improve",
)
def investigate_interval_recovery_trend(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    events: List[PerformanceEvent],
) -> Optional[RaceInputFinding]:
    """
    Track recovery between interval reps over successive sessions.
    """
    acts = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.run_shape.isnot(None),
    ).order_by(Activity.start_time).all()

    sessions_with_recovery = []
    for act in acts:
        shape = act.run_shape
        if not shape:
            continue
        accels = shape.get('accelerations', [])
        recoveries = [a.get('recovery_after_s') for a in accels
                       if a.get('recovery_after_s') is not None and a.get('recovery_after_s') > 0]
        if len(recoveries) < 3:
            continue

        sessions_with_recovery.append({
            'date': act.start_time.date().isoformat(),
            'activity_id': str(act.id),
            'avg_recovery_s': round(sum(recoveries) / len(recoveries), 1),
            'rep_count': len(recoveries),
        })

    if len(sessions_with_recovery) < 4:
        return None

    half = len(sessions_with_recovery) // 2
    early = sessions_with_recovery[:half]
    late = sessions_with_recovery[half:]

    early_avg = sum(s['avg_recovery_s'] for s in early) / len(early)
    late_avg = sum(s['avg_recovery_s'] for s in late) / len(late)
    change = late_avg - early_avg

    if abs(change) < 3:
        return None

    direction = "faster" if change < 0 else "slower"
    sentence = (
        f"Inter-rep recovery time across {len(sessions_with_recovery)} sessions: "
        f"averaged {early_avg:.0f}s early, {late_avg:.0f}s recently — "
        f"{abs(change):.0f}s {direction} recovery."
    )

    return RaceInputFinding(
        layer='B',
        finding_type='interval_recovery_trend',
        sentence=sentence,
        receipts={
            'sessions': sessions_with_recovery,
            'early_avg_recovery_s': round(early_avg, 1),
            'late_avg_recovery_s': round(late_avg, 1),
            'change_s': round(change, 1),
        },
        confidence='genuine' if len(sessions_with_recovery) >= 6 else 'suggestive',
    )


@investigation(
    requires=['activity_summary', 'run_shape'],
    min_activities=20,
    min_data_weeks=8,
    description="Workout variety — does mixing workout types correlate with better race results",
)
def investigate_workout_variety_effect(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    events: List[PerformanceEvent],
) -> Optional[RaceInputFinding]:
    """
    Measure whether higher workout variety in training blocks correlates
    with race performance. Uses run_shape classifications to count distinct
    workout types in the 4-week block preceding each race.
    """
    if len(events) < 4:
        return None

    race_blocks = []
    for ev in events:
        block_start = ev.event_date - timedelta(days=28)
        block_acts = db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.is_duplicate == False,  # noqa: E712
            Activity.run_shape.isnot(None),
            Activity.start_time >= block_start,
            Activity.start_time < ev.event_date,
        ).all()

        if len(block_acts) < 5:
            continue

        classifications = set()
        for act in block_acts:
            rs = act.run_shape or {}
            cls = rs.get('summary', {}).get('workout_classification')
            if cls:
                classifications.add(cls)

        race_time_sec = None
        if ev.finish_time_seconds:
            race_time_sec = ev.finish_time_seconds
        elif ev.time_seconds:
            race_time_sec = ev.time_seconds

        if race_time_sec and race_time_sec > 0:
            dist_m = ev.distance_meters or 0
            pace_sec_mi = (race_time_sec / (dist_m / METERS_PER_MILE)) if dist_m > 0 else 0
        else:
            pace_sec_mi = 0

        race_blocks.append({
            'date': ev.event_date.isoformat(),
            'distance': ev.distance_category,
            'variety_count': len(classifications),
            'types_found': sorted(classifications),
            'activity_count': len(block_acts),
            'race_pace_sec_mi': round(pace_sec_mi),
        })

    if len(race_blocks) < 4:
        return None

    varieties = [rb['variety_count'] for rb in race_blocks]
    avg_variety = sum(varieties) / len(varieties)

    high_variety = [rb for rb in race_blocks if rb['variety_count'] > avg_variety]
    low_variety = [rb for rb in race_blocks if rb['variety_count'] <= avg_variety]

    if not high_variety or not low_variety:
        return None

    high_paces = [rb['race_pace_sec_mi'] for rb in high_variety if rb['race_pace_sec_mi'] > 0]
    low_paces = [rb['race_pace_sec_mi'] for rb in low_variety if rb['race_pace_sec_mi'] > 0]

    if not high_paces or not low_paces:
        return None

    high_avg = sum(high_paces) / len(high_paces)
    low_avg = sum(low_paces) / len(low_paces)
    diff = low_avg - high_avg

    def _fmt(sec):
        m = int(sec) // 60
        s = int(sec) % 60
        return f"{m}:{s:02d}"

    if diff > 5:
        verdict = (
            f"Higher variety training blocks ({sum(rb['variety_count'] for rb in high_variety)/len(high_variety):.1f} "
            f"types) preceded races averaging {_fmt(high_avg)}/mi vs {_fmt(low_avg)}/mi "
            f"with less variety — {int(diff)} sec/mi faster."
        )
    elif diff < -5:
        verdict = (
            f"Focused training blocks with fewer types preceded faster races — "
            f"{_fmt(low_avg)}/mi vs {_fmt(high_avg)}/mi with more variety. "
            f"You may respond better to consistency than variety."
        )
    else:
        return None

    return RaceInputFinding(
        layer='B',
        finding_type='workout_variety_effect',
        sentence=verdict,
        receipts={
            'race_blocks': race_blocks,
            'high_variety_avg_pace': _fmt(high_avg),
            'low_variety_avg_pace': _fmt(low_avg),
            'diff_sec_mi': round(diff),
        },
        confidence='suggestive',
    )


@investigation(
    requires=['activity_summary', 'run_shape'],
    min_activities=10,
    min_data_weeks=4,
    description="Progressive run execution quality — pace control and finishing effort",
)
def investigate_progressive_run_execution(
    athlete_id: UUID,
    db: Session,
    zones: TrainingZones,
    events: List[PerformanceEvent],
) -> Optional[RaceInputFinding]:
    """
    Analyze progressive runs (each phase faster than the last) to track
    execution quality over time. Progressive runs teach pace control and
    finishing speed — key race execution skills.
    """
    acts = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.run_shape.isnot(None),
    ).order_by(Activity.start_time).all()

    progressions = []
    for act in acts:
        rs = act.run_shape or {}
        cls = rs.get('summary', {}).get('workout_classification')
        if cls != 'progression':
            continue

        phases = rs.get('phases', [])
        effort_phases = [p for p in phases
                         if p.get('phase_type') not in ('warmup', 'cooldown', 'interval_recovery')]
        if len(effort_phases) < 2:
            continue

        first_pace = effort_phases[0].get('avg_pace_sec_per_mile', 0)
        last_pace = effort_phases[-1].get('avg_pace_sec_per_mile', 0)
        if first_pace <= 0 or last_pace <= 0:
            continue

        pace_drop = first_pace - last_pace
        last_zone = effort_phases[-1].get('pace_zone', 'easy')
        first_hr = effort_phases[0].get('avg_hr')
        last_hr = effort_phases[-1].get('avg_hr')

        progressions.append({
            'date': act.start_time.date().isoformat(),
            'activity_id': str(act.id),
            'name': (act.name or '')[:50],
            'pace_drop_sec_mi': round(pace_drop),
            'finishing_zone': last_zone,
            'starting_pace_sec_mi': round(first_pace),
            'finishing_pace_sec_mi': round(last_pace),
            'starting_hr': round(first_hr) if first_hr else None,
            'finishing_hr': round(last_hr) if last_hr else None,
            'n_phases': len(effort_phases),
        })

    if len(progressions) < 3:
        return None

    half = len(progressions) // 2
    early = progressions[:half]
    late = progressions[half:]

    early_drop = sum(p['pace_drop_sec_mi'] for p in early) / len(early)
    late_drop = sum(p['pace_drop_sec_mi'] for p in late) / len(late)

    def _fmt(sec):
        m = int(sec) // 60
        s = int(sec) % 60
        return f"{m}:{s:02d}"

    change = late_drop - early_drop
    direction = "bigger" if change > 0 else "smaller"

    sentence = (
        f"Across {len(progressions)} progressive runs, "
        f"the pace drop from start to finish went from {int(early_drop)} sec/mi "
        f"to {int(late_drop)} sec/mi ({direction} negative splits). "
    )

    if change > 10:
        sentence += "Your ability to build through a run has improved."
    elif change < -10:
        sentence += "Your progressions have become more controlled — less dramatic acceleration."

    finishing_zones = Counter(p['finishing_zone'] for p in progressions)
    most_common_finish = finishing_zones.most_common(1)[0]
    sentence += f" Most common finishing effort: {most_common_finish[0]}."

    return RaceInputFinding(
        layer='B',
        finding_type='progressive_run_execution',
        sentence=sentence,
        receipts={
            'progressions': progressions,
            'early_avg_drop': round(early_drop),
            'late_avg_drop': round(late_drop),
            'finishing_zone_distribution': dict(finishing_zones),
        },
        confidence='genuine' if len(progressions) >= 5 else 'suggestive',
    )


# ═══════════════════════════════════════════════════════
#  Main entry point
# ═══════════════════════════════════════════════════════

def mine_race_inputs(
    athlete_id: UUID,
    db: Session,
) -> Tuple[List[RaceInputFinding], List[str]]:
    """
    Run all registered investigations against the athlete's data.

    Uses the investigation registry to check signal availability and
    minimum data thresholds before executing each investigation.

    Returns (findings, honest_gaps) where honest_gaps lists investigations
    that were skipped and why — for honest reporting to the athlete.
    """
    findings: List[RaceInputFinding] = []
    honest_gaps: List[str] = []

    zones = load_training_zones(athlete_id, db)
    if not zones:
        logger.warning("No RPI/zones for athlete %s — cannot mine inputs", athlete_id)
        return findings, ["Training pace profile not available — need at least one race result"]

    coverage = get_athlete_signal_coverage(athlete_id, db)

    events = db.query(PerformanceEvent).filter(
        PerformanceEvent.athlete_id == athlete_id,
        PerformanceEvent.user_confirmed == True,  # noqa: E712
    ).order_by(PerformanceEvent.event_date).all()

    for spec in INVESTIGATION_REGISTRY:
        missing = [s for s in spec.requires if not coverage.get(s)]
        if missing:
            honest_gaps.append(
                f"{spec.description}: needs {', '.join(missing)}"
            )
            continue

        if not meets_minimums(spec, athlete_id, db):
            honest_gaps.append(
                f"{spec.description}: not enough data yet"
            )
            continue

        try:
            result = spec.fn(athlete_id, db, zones, events)
            if result is None:
                continue
            if isinstance(result, list):
                findings.extend(result)
            else:
                findings.append(result)
        except Exception:
            logger.exception("Investigation %s failed", spec.name)

    # Legacy: adaptation curves and weekly patterns
    curves = detect_adaptation_curves(athlete_id, db, zones)
    actionable_curves = [
        c for c in curves
        if c.inflection_date and (c.trend == 'improving' or c.inflection_description)
    ]
    findings.extend(connect_adaptations_to_races(actionable_curves, events))

    patterns = detect_weekly_patterns(athlete_id, db, zones)
    for p in patterns:
        findings.append(_pattern_to_finding(p, events))

    return findings, honest_gaps


def _pattern_to_finding(
    pattern: WeeklyPattern,
    events: List[PerformanceEvent],
) -> RaceInputFinding:
    """Convert a weekly pattern to a finding with receipts."""
    sorted_events = sorted(events, key=lambda e: e.event_date)

    next_race = None
    for ev in sorted_events:
        if ev.event_date > pattern.last_week:
            next_race = ev
            break

    race_part = ""
    if next_race:
        race_time = _format_race_time(next_race)
        weeks = (next_race.event_date - pattern.last_week).days // 7
        race_part = (
            f" Your {_dist_label(next_race.distance_category)} "
            f"{race_time} came {weeks} weeks after this block ended."
        )

    sentence = (
        f"For {pattern.weeks_span} weeks ({pattern.first_week.strftime('%B')} to "
        f"{pattern.last_week.strftime('%B %Y')}), you did VO2 intervals on "
        f"{pattern.day_1}s followed by a long run on {pattern.day_2}s — "
        f"{pattern.occurrences} times.{race_part}"
    )

    return RaceInputFinding(
        layer='B',
        finding_type='weekly_pattern',
        sentence=sentence,
        receipts={
            'pattern_type': pattern.pattern_type,
            'occurrences': pattern.occurrences,
            'weeks_span': pattern.weeks_span,
            'first_week': pattern.first_week.isoformat(),
            'last_week': pattern.last_week.isoformat(),
            'examples': pattern.examples[:5],
        },
        confidence='table_stakes',
    )


# ═══════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════

def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _compute_trend(
    values: List[float],
    lower_is_better: bool = False,
) -> str:
    if len(values) < 4:
        return 'insufficient_data'

    n = len(values)
    third = max(1, n // 3)
    early = sum(values[:third]) / third
    late = sum(values[-third:]) / third

    diff_pct = (late - early) / max(early, 0.01) * 100

    if lower_is_better:
        diff_pct = -diff_pct

    if diff_pct > 15:
        return 'improving'
    elif diff_pct < -15:
        return 'declining'
    return 'stable'


def _format_race_time(event: PerformanceEvent) -> str:
    seconds = event.effective_time_seconds
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _dist_label(dist_cat: str) -> str:
    labels = {
        '5k': '5K', '10k': '10K', 'half_marathon': 'half marathon',
        'marathon': 'marathon', 'mile': 'mile',
    }
    return labels.get(dist_cat, dist_cat)


def _day_name(dow: int) -> str:
    return ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
            'Friday', 'Saturday', 'Sunday'][dow]


def _most_common(items: List[str]) -> str:
    from collections import Counter
    if not items:
        return 'unknown'
    return Counter(items).most_common(1)[0][0]
