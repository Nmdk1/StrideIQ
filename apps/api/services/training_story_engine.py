"""
Training Story Engine — Synthesis Layer

Takes the flat list of RaceInputFindings from the investigation engine
and builds connections between them. Produces:
  - Race Stories: what built each race outcome
  - Progressions: session-by-session / monthly build sequences
  - Connections: how findings relate to each other (mechanism-based)
  - Campaign Narrative: overarching training arc when one exists
  - Honest Gaps: what the system can't yet determine

Operates entirely on finding receipts — no database queries. Fast,
testable, and decoupled from the investigation engine.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import List, Optional, Dict, Tuple

from models import PerformanceEvent
from services.race_input_analysis import RaceInputFinding

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
#  Finding Classification Registry
# ═══════════════════════════════════════════════════════

FINDING_ROLES: Dict[str, str] = {
    # Inputs — training behaviors the athlete chose
    'weekly_pattern': 'input',
    'training_recipe': 'input',
    'workout_variety_effect': 'input',

    # Adaptations — measurable physiological changes
    'pace_at_hr_easy_adaptation': 'adaptation',
    'pace_at_hr_threshold_adaptation': 'adaptation',
    'pace_at_hr_easy_effort_adaptation': 'adaptation',
    'pace_at_hr_high_effort_adaptation': 'adaptation',
    'back_to_back_durability': 'adaptation',
    'workout_progression_interval': 'adaptation',
    'workout_progression_repetition': 'adaptation',
    'adaptation_threshold': 'adaptation',
    'adaptation_interval': 'adaptation',
    'adaptation_pace_at_hr': 'adaptation',
    'stride_economy': 'adaptation',
    'long_run_durability': 'adaptation',
    'post_injury_resilience': 'adaptation',
    'stride_progression': 'adaptation',
    'cruise_interval_quality': 'adaptation',
    'interval_recovery_trend': 'adaptation',
    'progressive_run_execution': 'adaptation',

    # Outcomes — race performances
    'race_execution': 'outcome',

    # Contextual — constants that modify interpretation
    'heat_tax': 'contextual',
    'heat_resilience': 'contextual',
    'recovery_cost': 'contextual',
}

# Which input types can plausibly drive which adaptation types.
# Only connections with a mechanism in this registry are created.
MECHANISM_REGISTRY: Dict[str, List[str]] = {
    'weekly_pattern': [
        'back_to_back_durability',
        'pace_at_hr_easy_adaptation',
        'pace_at_hr_easy_effort_adaptation',
        'long_run_durability',
        'stride_progression',
    ],
    'training_recipe': [
        'pace_at_hr_easy_adaptation',
        'pace_at_hr_threshold_adaptation',
        'pace_at_hr_easy_effort_adaptation',
        'pace_at_hr_high_effort_adaptation',
        'workout_progression_interval',
        'workout_progression_repetition',
        'adaptation_threshold',
        'adaptation_interval',
        'stride_economy',
        'cruise_interval_quality',
        'interval_recovery_trend',
    ],
    'workout_variety_effect': [
        'workout_progression_interval',
        'workout_progression_repetition',
        'progressive_run_execution',
    ],
}

# Which adaptations directly feed race performance.
ADAPTATION_TO_OUTCOME: Dict[str, List[str]] = {
    'pace_at_hr_easy_adaptation': ['half_marathon', 'marathon', '10k'],
    'pace_at_hr_threshold_adaptation': ['5k', '10k', 'half_marathon'],
    'pace_at_hr_easy_effort_adaptation': ['half_marathon', 'marathon', '10k'],
    'pace_at_hr_high_effort_adaptation': ['5k', '10k', 'half_marathon'],
    'back_to_back_durability': ['half_marathon', 'marathon'],
    'adaptation_threshold': ['10k', 'half_marathon', 'marathon'],
    'adaptation_interval': ['mile', '5k', '10k'],
    'workout_progression_interval': ['mile', '5k', '10k'],
    'workout_progression_repetition': ['mile', '5k'],
    'stride_economy': ['5k', '10k', 'half_marathon', 'marathon'],
    'long_run_durability': ['half_marathon', 'marathon'],
    'post_injury_resilience': ['5k', '10k', 'half_marathon', 'marathon', 'mile'],
    'stride_progression': ['5k', '10k', 'half_marathon', 'marathon', 'mile'],
    'cruise_interval_quality': ['10k', 'half_marathon', 'marathon'],
    'interval_recovery_trend': ['5k', '10k', 'half_marathon'],
    'progressive_run_execution': ['10k', 'half_marathon', 'marathon'],
}


# ═══════════════════════════════════════════════════════
#  Data Model
# ═══════════════════════════════════════════════════════

@dataclass
class DateRange:
    start: Optional[date]
    end: Optional[date]

    @property
    def is_timeless(self) -> bool:
        return self.start is None and self.end is None

    def overlaps(self, other: 'DateRange') -> bool:
        if self.is_timeless or other.is_timeless:
            return False
        return self.start <= other.end and other.start <= self.end

    def precedes(self, other: 'DateRange', max_gap_weeks: int = 16) -> bool:
        if self.is_timeless or other.is_timeless:
            return False
        gap = (other.start - self.end).days
        return 0 <= gap <= max_gap_weeks * 7


@dataclass
class Connection:
    """A mechanism-based relationship between two findings."""
    from_index: int
    to_index: int
    from_type: str
    to_type: str
    connection_type: str    # 'input_to_adaptation', 'adaptation_to_outcome',
                            # 'compounding', 'confound_adjustment'
    mechanism: str          # why this connection exists
    temporal: str           # 'overlapping', 'sequential', 'contextual'


@dataclass
class Progression:
    """A consecutive build sequence extracted from a finding's receipts."""
    finding_index: int
    finding_type: str
    metric_name: str
    unit: str
    data_points: List[Dict]
    trend: str
    biggest_jump: Optional[Dict]
    duration_weeks: int


@dataclass
class RaceStory:
    """What built a specific race outcome."""
    race_date: date
    distance: str
    time_display: str
    is_pb: bool
    contributing_inputs: List[Dict]
    peaking_adaptations: List[Dict]
    race_evidence: Dict
    confounds: List[str]
    confidence: str


@dataclass
class TrainingStory:
    """The complete synthesized training story."""
    findings: List[Dict]
    race_stories: List[RaceStory]
    progressions: List[Progression]
    connections: List[Connection]
    campaign_narrative: Optional[Dict]
    honest_gaps: List[str]

    def to_dict(self) -> dict:
        return {
            'race_stories': [asdict(rs) for rs in self.race_stories],
            'progressions': [asdict(p) for p in self.progressions],
            'connections': [asdict(c) for c in self.connections],
            'campaign_narrative': self.campaign_narrative,
            'honest_gaps': self.honest_gaps,
            'finding_count': len(self.findings),
        }

    def to_coach_context(self) -> str:
        """Concise summary for coach briefing prompt context."""
        lines = []

        if self.campaign_narrative:
            lines.append(f"Training Campaign: {self.campaign_narrative['summary']}")

        for rs in self.race_stories:
            pb_tag = " (PB)" if rs.is_pb else ""
            lines.append(
                f"Race Story — {rs.distance} {rs.time_display}{pb_tag} "
                f"({rs.race_date}):"
            )
            for a in rs.peaking_adaptations:
                lines.append(f"  - {a['summary']}")
            for inp in rs.contributing_inputs:
                lines.append(f"  - Input: {inp['summary']}")
            if rs.confounds:
                lines.append(f"  - Confounds: {', '.join(rs.confounds)}")

        for p in self.progressions:
            if p.data_points:
                first = p.data_points[0]
                last = p.data_points[-1]
                lines.append(
                    f"Progression ({p.metric_name}): "
                    f"{first.get('value', '?')} → {last.get('value', '?')} {p.unit} "
                    f"over {p.duration_weeks} weeks ({p.trend})"
                )

        if self.honest_gaps:
            lines.append("Gaps: " + "; ".join(self.honest_gaps[:3]))

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════
#  Step 1: Timeline Extraction
# ═══════════════════════════════════════════════════════

def _parse_date(val) -> Optional[date]:
    """Parse a date from string or date object."""
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return date.fromisoformat(val[:10])
        except (ValueError, TypeError):
            return None
    return None


def extract_date_range(finding: RaceInputFinding) -> DateRange:
    """Pull a date range from a finding's receipts."""
    r = finding.receipts
    ft = finding.finding_type

    if ft in ('heat_tax', 'recovery_cost'):
        return DateRange(None, None)

    if ft == 'race_execution':
        d = _parse_date(r.get('race_date'))
        return DateRange(d, d)

    if ft == 'weekly_pattern':
        return DateRange(
            _parse_date(r.get('first_week')),
            _parse_date(r.get('last_week')),
        )

    if ft == 'back_to_back_durability':
        sessions = r.get('after_quality_sessions', [])
        if sessions:
            dates = [_parse_date(s.get('date')) for s in sessions]
            dates = [d for d in dates if d]
            without = r.get('without_quality_sessions', [])
            all_dates = dates + [
                d for d in [_parse_date(s.get('date')) for s in without] if d
            ]
            if all_dates:
                return DateRange(min(all_dates), max(all_dates))

    if ft.startswith('pace_at_hr_'):
        progression = r.get('monthly_progression', {})
        if progression:
            months = sorted(progression.keys())
            if months:
                return DateRange(
                    _parse_date(months[0] + '-01'),
                    _parse_date(months[-1] + '-28'),
                )

    if ft.startswith('workout_progression_'):
        sessions = r.get('sessions', [])
        if sessions:
            dates = [_parse_date(s.get('date')) for s in sessions]
            dates = [d for d in dates if d]
            if dates:
                return DateRange(min(dates), max(dates))

    if ft.startswith('adaptation_'):
        before = r.get('before_sessions', [])
        after = r.get('after_sessions', [])
        all_sessions = before + after
        if all_sessions:
            dates = [_parse_date(s.get('date')) for s in all_sessions]
            dates = [d for d in dates if d]
            if dates:
                return DateRange(min(dates), max(dates))

    if ft in ('training_recipe',):
        best = r.get('best_races', [])
        worst = r.get('worst_races', [])
        all_races = best + worst
        dates = [_parse_date(race.get('race_date')) for race in all_races]
        dates = [d for d in dates if d]
        if dates:
            return DateRange(min(dates) - timedelta(days=42), max(dates))

    if ft == 'post_injury_resilience':
        gs = _parse_date(r.get('gap_start'))
        ge = _parse_date(r.get('gap_end'))
        if gs and ge:
            return DateRange(gs - timedelta(days=28), ge + timedelta(days=28))

    if ft == 'stride_economy':
        progression = r.get('monthly_progression', {})
        if isinstance(progression, dict):
            months = sorted(progression.keys())
            if months:
                return DateRange(
                    _parse_date(months[0] + '-01'),
                    _parse_date(months[-1] + '-28'),
                )

    if ft == 'long_run_durability':
        early = r.get('early_runs', [])
        late = r.get('late_runs', [])
        all_runs = early + late
        dates = [_parse_date(run.get('date')) for run in all_runs]
        dates = [d for d in dates if d]
        if dates:
            return DateRange(min(dates), max(dates))

    return DateRange(None, None)


# ═══════════════════════════════════════════════════════
#  Step 2: Progression Extraction
# ═══════════════════════════════════════════════════════

def extract_progressions(
    findings: List[RaceInputFinding],
) -> List[Progression]:
    """Pull build sequences from finding receipts."""
    progressions = []

    for idx, f in enumerate(findings):
        r = f.receipts
        ft = f.finding_type

        if ft.startswith('pace_at_hr_'):
            prog = r.get('monthly_progression', {})
            if not prog:
                continue
            zone = 'easy' if 'easy' in ft else 'threshold'
            hr_band = r.get('hr_band', '')
            points = []
            for month_key in sorted(prog.keys()):
                entry = prog[month_key]
                points.append({
                    'date': f"{month_key}-15",
                    'value': entry.get('pace', '?'),
                    'hr': entry.get('hr'),
                    'temp_f': entry.get('temp_f'),
                    'n': entry.get('n'),
                })

            if len(points) >= 2:
                total_change = r.get('total_change_sec', 0)
                jumps = []
                for i in range(1, len(points)):
                    prev_p = _pace_to_sec(points[i - 1]['value'])
                    curr_p = _pace_to_sec(points[i]['value'])
                    if prev_p and curr_p:
                        jumps.append({
                            'from_month': points[i - 1]['date'][:7],
                            'to_month': points[i]['date'][:7],
                            'change_sec': curr_p - prev_p,
                        })

                biggest = min(jumps, key=lambda j: j['change_sec']) if jumps else None

                first_date = _parse_date(points[0]['date'])
                last_date = _parse_date(points[-1]['date'])
                weeks = (last_date - first_date).days // 7 if first_date and last_date else 0

                progressions.append(Progression(
                    finding_index=idx,
                    finding_type=ft,
                    metric_name=f'Pace at {zone} HR ({hr_band} bpm)',
                    unit='/mi',
                    data_points=points,
                    trend='improving' if total_change < -5 else 'stable',
                    biggest_jump=biggest,
                    duration_weeks=weeks,
                ))

        elif ft.startswith('workout_progression_'):
            sessions = r.get('sessions', [])
            zone = r.get('zone', ft.replace('workout_progression_', ''))
            if len(sessions) >= 3:
                points = []
                for s in sessions:
                    points.append({
                        'date': s.get('date'),
                        'value': s.get('avg_pace'),
                        'hr': s.get('avg_hr'),
                        'reps': s.get('reps'),
                        'temp_f': s.get('temp_f'),
                    })

                pace_change = r.get('pace_change_sec', 0)
                first_d = _parse_date(sessions[0].get('date'))
                last_d = _parse_date(sessions[-1].get('date'))
                weeks = (last_d - first_d).days // 7 if first_d and last_d else 0

                progressions.append(Progression(
                    finding_index=idx,
                    finding_type=ft,
                    metric_name=f'{zone.title()} rep pace',
                    unit='/mi',
                    data_points=points,
                    trend='improving' if pace_change < -3 else 'stable',
                    biggest_jump=None,
                    duration_weeks=weeks,
                ))

        elif ft.startswith('adaptation_'):
            before = r.get('before_sessions', [])
            after = r.get('after_sessions', [])
            inflection = r.get('inflection_date')
            metric = r.get('metric', ft.replace('adaptation_', ''))

            if before and after:
                before_pts = []
                for s in before[-3:]:
                    before_pts.append({
                        'date': s.get('date'),
                        'value': f"{s.get('zone_distance_km', 0):.1f}km" if 'zone_distance_km' in s else str(s.get('avg_pace', '?')),
                        'session_type': s.get('session_type'),
                        'hr': s.get('avg_hr'),
                    })
                after_pts = []
                for s in after[:3]:
                    after_pts.append({
                        'date': s.get('date'),
                        'value': f"{s.get('zone_distance_km', 0):.1f}km" if 'zone_distance_km' in s else str(s.get('avg_pace', '?')),
                        'session_type': s.get('session_type'),
                        'hr': s.get('avg_hr'),
                    })

                all_pts = before_pts + after_pts
                first_d = _parse_date(all_pts[0]['date']) if all_pts else None
                last_d = _parse_date(all_pts[-1]['date']) if all_pts else None
                weeks = (last_d - first_d).days // 7 if first_d and last_d else 0

                progressions.append(Progression(
                    finding_index=idx,
                    finding_type=ft,
                    metric_name=f'{metric.title()} work volume/type',
                    unit='',
                    data_points=all_pts,
                    trend=r.get('trend', 'improving'),
                    biggest_jump={'inflection_date': inflection} if inflection else None,
                    duration_weeks=weeks,
                ))

        elif ft == 'back_to_back_durability':
            sessions = r.get('after_quality_sessions', [])
            if len(sessions) >= 2:
                points = []
                for s in sessions:
                    points.append({
                        'date': s.get('date'),
                        'value': f"{s.get('hr_drift', 0):.1f} bpm drift",
                        'hr_drift': s.get('hr_drift'),
                        'dist_km': s.get('dist_km'),
                    })

                first_d = _parse_date(sessions[0].get('date'))
                last_d = _parse_date(sessions[-1].get('date'))
                weeks = (last_d - first_d).days // 7 if first_d and last_d else 0

                progressions.append(Progression(
                    finding_index=idx,
                    finding_type=ft,
                    metric_name='Cardiac drift on fatigued long runs',
                    unit='bpm',
                    data_points=points,
                    trend='improving' if r.get('improvement_bpm', 0) > 0 else 'stable',
                    biggest_jump=None,
                    duration_weeks=weeks,
                ))

    return progressions


def _pace_to_sec(pace_str: str) -> Optional[int]:
    """Convert '8:56' format to total seconds."""
    if not pace_str or pace_str == '?':
        return None
    try:
        parts = pace_str.split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return None


# ═══════════════════════════════════════════════════════
#  Step 3: Race Story Construction
# ═══════════════════════════════════════════════════════

def _format_time(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def construct_race_stories(
    findings: List[RaceInputFinding],
    date_ranges: List[DateRange],
    events: List[PerformanceEvent],
) -> List[RaceStory]:
    """Build per-race attribution from findings."""
    stories = []

    race_findings = [
        (i, f) for i, f in enumerate(findings)
        if f.finding_type == 'race_execution'
    ]

    for race_idx, race_finding in race_findings:
        race_date = _parse_date(race_finding.receipts.get('race_date'))
        if not race_date:
            continue

        distance = race_finding.receipts.get('distance', '?')
        time_display = race_finding.receipts.get('time', '?')
        is_pb = race_finding.receipts.get('is_pb', False)

        contributing_inputs = []
        peaking_adaptations = []
        confounds = []

        for i, f in enumerate(findings):
            if i == race_idx:
                continue

            role = FINDING_ROLES.get(f.finding_type, 'unknown')
            dr = date_ranges[i]

            if role == 'input':
                if dr.is_timeless:
                    continue
                if dr.end and race_date and dr.end <= race_date:
                    gap_days = (race_date - dr.end).days
                    if gap_days <= 112:
                        contributing_inputs.append({
                            'finding_index': i,
                            'finding_type': f.finding_type,
                            'summary': f.sentence[:200],
                            'ended_days_before_race': gap_days,
                        })
                elif dr.overlaps(DateRange(race_date - timedelta(days=112), race_date)):
                    contributing_inputs.append({
                        'finding_index': i,
                        'finding_type': f.finding_type,
                        'summary': f.sentence[:200],
                        'ended_days_before_race': 0,
                    })

            elif role == 'adaptation':
                relevant_distances = ADAPTATION_TO_OUTCOME.get(f.finding_type, [])
                if relevant_distances and distance not in relevant_distances:
                    continue

                if dr.is_timeless:
                    continue

                active_near_race = (
                    dr.overlaps(DateRange(race_date - timedelta(days=84), race_date))
                    or dr.precedes(DateRange(race_date, race_date), max_gap_weeks=4)
                )
                if active_near_race:
                    summary = f.sentence[:200]
                    value_at_race = _extract_value_near_date(f, race_date)
                    if value_at_race:
                        summary += f" (at race time: {value_at_race})"

                    peaking_adaptations.append({
                        'finding_index': i,
                        'finding_type': f.finding_type,
                        'summary': summary,
                        'value_at_race': value_at_race,
                        'confidence': f.confidence,
                    })

            elif role == 'contextual':
                if f.finding_type == 'heat_tax':
                    hot_races = f.receipts.get('hot_races', [])
                    for hr_entry in hot_races:
                        hr_date = _parse_date(hr_entry.get('date'))
                        if hr_date == race_date:
                            cost = hr_entry.get('expected_cost_sec_mi', 0)
                            confounds.append(
                                f"Heat tax: ~{cost} sec/mi at "
                                f"{hr_entry.get('temp_f', '?')}°F"
                            )

        # Determine story confidence
        if race_finding.confidence == 'suggestive':
            confounds_from_recipe = [
                f for f in findings
                if f.finding_type == 'training_recipe'
                and f.receipts.get('recency_confound')
            ]
            for cf in confounds_from_recipe:
                if distance in (cf.receipts.get('distance', '')):
                    confounds.append("Recency confound: best races are most recent")

            weather_confound_recipes = [
                f for f in findings
                if f.finding_type == 'training_recipe'
                and f.receipts.get('weather_confound')
            ]
            for wf in weather_confound_recipes:
                if distance in (wf.receipts.get('distance', '')):
                    confounds.append("Weather confound: training temperature differed")

        confidence = 'strong'
        if len(confounds) >= 2:
            confidence = 'suggestive'
        elif len(confounds) == 1:
            confidence = 'moderate'

        race_evidence = {
            'pace_cv_pct': race_finding.receipts.get('pace_cv_pct'),
            'split_ratio_pct': race_finding.receipts.get('split_ratio_pct'),
            'cardiac_drift': race_finding.receipts.get('cardiac_drift'),
        }

        stories.append(RaceStory(
            race_date=race_date,
            distance=distance,
            time_display=time_display,
            is_pb=is_pb,
            contributing_inputs=contributing_inputs,
            peaking_adaptations=peaking_adaptations,
            race_evidence=race_evidence,
            confounds=confounds,
            confidence=confidence,
        ))

    stories.sort(key=lambda s: s.race_date)
    return stories


def _extract_value_near_date(
    finding: RaceInputFinding,
    target_date: date,
) -> Optional[str]:
    """Extract the finding's metric value closest to a specific date."""
    r = finding.receipts
    ft = finding.finding_type

    if ft.startswith('pace_at_hr_'):
        prog = r.get('monthly_progression', {})
        target_month = target_date.strftime('%Y-%m')
        if target_month in prog:
            return prog[target_month].get('pace')
        nearby = sorted(prog.keys(), key=lambda m: abs(
            (_parse_date(m + '-15') or target_date) - target_date
        ).days if _parse_date(m + '-15') else 999)
        if nearby:
            return prog[nearby[0]].get('pace')

    if ft == 'back_to_back_durability':
        return f"{r.get('late_avg_drift', '?')} bpm drift"

    if ft.startswith('workout_progression_'):
        sessions = r.get('sessions', [])
        if sessions:
            closest = min(sessions, key=lambda s: abs(
                (_parse_date(s.get('date')) or target_date) - target_date
            ).days if _parse_date(s.get('date')) else 999)
            return closest.get('avg_pace')

    return None


# ═══════════════════════════════════════════════════════
#  Step 4: Connection Detection (Mechanism-Based)
# ═══════════════════════════════════════════════════════

def detect_connections(
    findings: List[RaceInputFinding],
    date_ranges: List[DateRange],
    race_stories: List[RaceStory],
) -> List[Connection]:
    """
    Build connections backward from outcomes.

    Only creates connections where a physiological mechanism exists
    in the registry. Temporal overlap alone is not sufficient.
    """
    connections = []

    # Input → Adaptation connections
    for i, f_input in enumerate(findings):
        role_i = FINDING_ROLES.get(f_input.finding_type)
        if role_i != 'input':
            continue

        driveable = MECHANISM_REGISTRY.get(f_input.finding_type, [])
        if not driveable:
            continue

        for j, f_adapt in enumerate(findings):
            if i == j:
                continue
            role_j = FINDING_ROLES.get(f_adapt.finding_type)
            if role_j != 'adaptation':
                continue

            matches_mechanism = any(
                f_adapt.finding_type.startswith(d) for d in driveable
            )
            if not matches_mechanism:
                continue

            dr_i = date_ranges[i]
            dr_j = date_ranges[j]

            if dr_i.overlaps(dr_j) or dr_i.precedes(dr_j, max_gap_weeks=8):
                temporal = 'overlapping' if dr_i.overlaps(dr_j) else 'sequential'
                connections.append(Connection(
                    from_index=i,
                    to_index=j,
                    from_type=f_input.finding_type,
                    to_type=f_adapt.finding_type,
                    connection_type='input_to_adaptation',
                    mechanism=(
                        f"{f_input.finding_type} can drive "
                        f"{f_adapt.finding_type} through sustained "
                        f"training stimulus"
                    ),
                    temporal=temporal,
                ))

    # Adaptation → Outcome connections (via race stories)
    for story in race_stories:
        for adapt in story.peaking_adaptations:
            adapt_idx = adapt['finding_index']
            race_indices = [
                i for i, f in enumerate(findings)
                if f.finding_type == 'race_execution'
                and _parse_date(f.receipts.get('race_date')) == story.race_date
            ]
            for race_idx in race_indices:
                connections.append(Connection(
                    from_index=adapt_idx,
                    to_index=race_idx,
                    from_type=findings[adapt_idx].finding_type,
                    to_type='race_execution',
                    connection_type='adaptation_to_outcome',
                    mechanism=(
                        f"{findings[adapt_idx].finding_type} was active/peaking "
                        f"near {story.distance} on {story.race_date}"
                    ),
                    temporal='overlapping',
                ))

    # Compounding — two adaptations improving in the same window
    # Only connect pairs where there's tight temporal alignment, not just
    # "both happened during the same 6-month period." Require >50% overlap
    # relative to the shorter range.
    adaptation_indices = [
        i for i, f in enumerate(findings)
        if FINDING_ROLES.get(f.finding_type) == 'adaptation'
    ]
    seen_pairs = set()
    for i in adaptation_indices:
        for j in adaptation_indices:
            if i >= j:
                continue
            pair = (i, j)
            if pair in seen_pairs:
                continue
            dr_i = date_ranges[i]
            dr_j = date_ranges[j]
            if not dr_i.overlaps(dr_j):
                continue
            if dr_i.is_timeless or dr_j.is_timeless:
                continue

            overlap_start = max(dr_i.start, dr_j.start)
            overlap_end = min(dr_i.end, dr_j.end)
            overlap_days = (overlap_end - overlap_start).days
            shorter = min(
                (dr_i.end - dr_i.start).days,
                (dr_j.end - dr_j.start).days,
            )
            if shorter <= 0:
                continue
            overlap_ratio = overlap_days / shorter
            if overlap_ratio < 0.5:
                continue

            seen_pairs.add(pair)
            connections.append(Connection(
                from_index=i,
                to_index=j,
                from_type=findings[i].finding_type,
                to_type=findings[j].finding_type,
                connection_type='compounding',
                mechanism=(
                    f"{findings[i].finding_type} and "
                    f"{findings[j].finding_type} were both improving "
                    f"during the same training period "
                    f"({overlap_days} days overlap)"
                ),
                temporal='overlapping',
            ))

    # Deduplicate: only keep one connection per (from_type, to_type, connection_type)
    seen_connection_keys = set()
    deduped = []
    for c in connections:
        key = (c.from_type, c.to_type, c.connection_type)
        if key not in seen_connection_keys:
            seen_connection_keys.add(key)
            deduped.append(c)
    connections = deduped

    # Confound adjustments — one per contextual finding, applied to suggestive outcomes
    for i, f in enumerate(findings):
        if FINDING_ROLES.get(f.finding_type) != 'contextual':
            continue
        applied = False
        for j, f2 in enumerate(findings):
            if i == j or applied:
                continue
            role_j = FINDING_ROLES.get(f2.finding_type)
            if role_j != 'outcome':
                continue
            if f.finding_type == 'heat_tax' and f2.confidence == 'suggestive':
                key = (f.finding_type, f2.finding_type, 'confound_adjustment')
                if key not in seen_connection_keys:
                    seen_connection_keys.add(key)
                    connections.append(Connection(
                        from_index=i,
                        to_index=j,
                        from_type=f.finding_type,
                        to_type=f2.finding_type,
                        connection_type='confound_adjustment',
                        mechanism='Temperature differences may explain part of the observed change',
                        temporal='contextual',
                    ))
                    applied = True

    return connections


# ═══════════════════════════════════════════════════════
#  Step 5: Campaign Detection (reads from real campaign_detection.py output)
# ═══════════════════════════════════════════════════════

def _get_campaign_from_events(
    race_stories: List[RaceStory],
    events: List["PerformanceEvent"],
) -> Optional[Dict]:
    """
    Read campaign data from PerformanceEvent.campaign_data (populated by
    the real campaign detector in campaign_detection.py).

    Returns the most recent campaign that has linked races, or None.
    If no campaign_data exists yet, returns None — silence is better
    than a wrong narrative.
    """
    campaigns_seen: Dict[tuple, Dict] = {}
    for ev in events:
        if ev.campaign_data and isinstance(ev.campaign_data, dict):
            start = ev.campaign_data.get('start_date')
            end = ev.campaign_data.get('end_date')
            if not start or not end:
                continue
            key = (start, end)
            record = campaigns_seen.get(key)
            if record is None:
                campaigns_seen[key] = {
                    'campaign': ev.campaign_data,
                    'latest_linked_race_date': ev.event_date,
                }
            else:
                if ev.event_date and (
                    record['latest_linked_race_date'] is None
                    or ev.event_date > record['latest_linked_race_date']
                ):
                    record['latest_linked_race_date'] = ev.event_date

    if not campaigns_seen:
        return None

    latest_record = max(
        campaigns_seen.values(),
        key=lambda r: r.get('latest_linked_race_date') or date.min,
    )
    latest = latest_record['campaign']

    span_weeks = latest.get('total_weeks', 0)
    end_reason = latest.get('end_reason', 'unknown')

    summary = f"{span_weeks}-week training arc"
    if end_reason == 'disruption':
        summary += " (ended by disruption)"
    elif end_reason == 'ongoing':
        summary += " (ongoing)"

    return {
        'start_date': latest.get('start_date'),
        'end_date': latest.get('end_date'),
        'span_weeks': span_weeks,
        'end_reason': end_reason,
        'phases': latest.get('phases', []),
        'summary': summary,
    }


# ═══════════════════════════════════════════════════════
#  Step 6: Honest Gaps
# ═══════════════════════════════════════════════════════

INVESTIGATION_DESCRIPTIONS = {
    'stride_economy': (
        'Stride economy tracking needs more months of cadence data '
        'at consistent temperatures to detect stride length changes.'
    ),
    'long_run_durability': (
        'Long run durability tracking needs cadence data on more long '
        'runs to detect form decay patterns.'
    ),
    'post_injury_resilience': (
        'Post-injury resilience analysis requires a training gap of '
        '14+ days with temperature-controlled data before and after.'
    ),
}


def identify_gaps(
    findings: List[RaceInputFinding],
    all_investigation_names: List[str],
) -> List[str]:
    """Identify what investigations returned None and why."""
    found_types = set()
    for f in findings:
        found_types.add(f.finding_type)
        base = f.finding_type.split('_')[0]
        found_types.add(base)

    gaps = []
    for name in all_investigation_names:
        short_name = name.replace('investigate_', '')

        is_found = any(
            ft.startswith(short_name) or short_name.startswith(ft)
            for ft in found_types
        )
        if is_found:
            continue

        desc = INVESTIGATION_DESCRIPTIONS.get(short_name)
        if desc:
            gaps.append(desc)

    return gaps


# ═══════════════════════════════════════════════════════
#  Orchestrator
# ═══════════════════════════════════════════════════════

ALL_INVESTIGATION_NAMES = [
    'investigate_back_to_back_durability',
    'investigate_race_execution',
    'investigate_recovery_cost',
    'investigate_training_recipe',
    'investigate_pace_at_hr_adaptation',
    'investigate_heat_tax',
    'investigate_post_injury_resilience',
    'investigate_stride_economy',
    'investigate_workout_progression',
    'investigate_long_run_durability',
]


def synthesize_training_story(
    findings: List[RaceInputFinding],
    events: List[PerformanceEvent],
) -> TrainingStory:
    """
    Main entry point. Takes findings from mine_race_inputs() and
    builds the complete training story.
    """
    date_ranges = [extract_date_range(f) for f in findings]

    progressions = extract_progressions(findings)

    race_stories = construct_race_stories(findings, date_ranges, events)

    connections = detect_connections(findings, date_ranges, race_stories)

    campaign = _get_campaign_from_events(race_stories, events)

    gaps = identify_gaps(findings, ALL_INVESTIGATION_NAMES)

    finding_dicts = []
    for i, f in enumerate(findings):
        finding_dicts.append({
            'index': i,
            'layer': f.layer,
            'type': f.finding_type,
            'role': FINDING_ROLES.get(f.finding_type, 'unknown'),
            'sentence': f.sentence,
            'confidence': f.confidence,
            'date_range': {
                'start': date_ranges[i].start.isoformat() if date_ranges[i].start else None,
                'end': date_ranges[i].end.isoformat() if date_ranges[i].end else None,
            },
        })

    return TrainingStory(
        findings=finding_dicts,
        race_stories=race_stories,
        progressions=progressions,
        connections=connections,
        campaign_narrative=campaign,
        honest_gaps=gaps,
    )
