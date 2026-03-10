"""
Campaign Detection — Phase 1C

Finds inflection points in an athlete's training volume history,
constructs training campaigns from those inflection points, and
classifies disruptions (injury vs taper vs life event).
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import List, Optional, Dict
from uuid import UUID

from sqlalchemy.orm import Session

from models import Activity, PerformanceEvent

logger = logging.getLogger(__name__)

KM_PER_METER = 0.001


@dataclass
class InflectionPoint:
    date: date
    type: str  # 'step_up', 'step_down', 'disruption'
    before_avg_weekly_km: float
    after_avg_weekly_km: float
    change_pct: float
    sustained_weeks: int


@dataclass
class CampaignPhase:
    name: str  # 'base_building', 'escalation', 'race_specific', 'taper', 'disrupted'
    start_date: date
    end_date: date
    weeks: int
    avg_volume_km: float
    intensity_distribution: dict = field(default_factory=dict)


@dataclass
class TrainingCampaign:
    athlete_id: UUID
    start_date: date
    end_date: date
    end_reason: str  # 'race', 'disruption', 'new_campaign', 'ongoing'
    phases: List[CampaignPhase]
    linked_races: List[UUID]
    total_weeks: int
    peak_weekly_volume_km: float
    avg_weekly_volume_km: float


def _compute_weekly_volumes(
    athlete_id: UUID,
    db: Session,
) -> List[tuple]:
    """
    Returns a sorted list of (week_start_date, volume_km) tuples.
    Week starts on Monday. Excludes duplicate activities.
    """
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.distance_m.isnot(None),
        Activity.distance_m > 0,
        Activity.is_duplicate == False,  # noqa: E712
    ).order_by(Activity.start_time).all()

    if not activities:
        return []

    weekly: Dict[date, float] = {}
    for act in activities:
        act_date = act.start_time.date()
        week_start = act_date - timedelta(days=act_date.weekday())
        dist_km = float(act.distance_m) * KM_PER_METER
        weekly[week_start] = weekly.get(week_start, 0.0) + dist_km

    if not weekly:
        return []

    all_weeks = sorted(weekly.keys())
    first_week = all_weeks[0]
    last_week = all_weeks[-1]

    result = []
    current = first_week
    while current <= last_week:
        result.append((current, weekly.get(current, 0.0)))
        current += timedelta(weeks=1)

    return result


def _rolling_average(
    weekly_volumes: List[tuple],
    window: int = 4,
) -> List[tuple]:
    """Compute a rolling average of weekly volumes over `window` weeks."""
    if len(weekly_volumes) < window:
        return []

    result = []
    for i in range(window - 1, len(weekly_volumes)):
        window_vols = [weekly_volumes[j][1] for j in range(i - window + 1, i + 1)]
        avg = sum(window_vols) / window
        result.append((weekly_volumes[i][0], avg))

    return result


def detect_inflection_points(
    athlete_id: UUID,
    db: Session,
    min_change_pct: float = 20.0,
    min_sustained_weeks: int = 4,
) -> List[InflectionPoint]:
    """
    Find dates where weekly volume shifted significantly and held.

    Uses a baseline-tracking approach: maintains a stable baseline and
    looks for the rolling average to shift by >= min_change_pct from that
    baseline and hold for min_sustained_weeks.
    """
    weekly_volumes = _compute_weekly_volumes(athlete_id, db)
    if len(weekly_volumes) < 8:
        return []

    rolling = _rolling_average(weekly_volumes, window=4)
    if len(rolling) < 2:
        return []

    inflections: List[InflectionPoint] = []

    # Check for disruptions: both instant cliffs and progressive declines
    for i in range(4, len(weekly_volumes)):
        prev_4wk = [weekly_volumes[j][1] for j in range(i - 4, i)]
        avg_before = sum(prev_4wk) / len(prev_4wk)

        if avg_before < 10.0:
            continue

        curr_vol = weekly_volumes[i][1]

        # Pattern 1: Instant cliff — volume drops to < 25% in one week
        if curr_vol < avg_before * 0.25:
            sustained = _count_sustained_low(
                weekly_volumes, i, threshold=avg_before * 0.25
            )
            if sustained >= 2:
                drop_pct = ((curr_vol - avg_before) / avg_before) * 100
                inflections.append(InflectionPoint(
                    date=weekly_volumes[i][0],
                    type='disruption',
                    before_avg_weekly_km=round(avg_before, 1),
                    after_avg_weekly_km=round(curr_vol, 1),
                    change_pct=round(drop_pct, 1),
                    sustained_weeks=sustained,
                ))
                break

        # Pattern 2: Progressive disruption — volume declines >70% over
        # 3-5 weeks (e.g., injury where athlete keeps racing briefly)
        if i + 4 < len(weekly_volumes):
            window_ahead = [weekly_volumes[i + j][1] for j in range(5)]
            min_in_window = min(window_ahead)
            if min_in_window < avg_before * 0.10:
                # Reached near-zero within 5 weeks — find the onset
                onset_idx = i
                for j in range(5):
                    if weekly_volumes[i + j][1] < avg_before * 0.30:
                        onset_idx = i + j
                        break

                sustained = _count_sustained_low(
                    weekly_volumes, onset_idx, threshold=avg_before * 0.30
                )
                if sustained >= 2:
                    onset_vol = weekly_volumes[onset_idx][1]
                    drop_pct = ((onset_vol - avg_before) / avg_before) * 100
                    inflections.append(InflectionPoint(
                        date=weekly_volumes[i][0],
                        type='disruption',
                        before_avg_weekly_km=round(avg_before, 1),
                        after_avg_weekly_km=round(onset_vol, 1),
                        change_pct=round(drop_pct, 1),
                        sustained_weeks=sustained,
                    ))
                    break

    # Detect step_up / step_down using non-overlapping block comparison
    block_size = 4
    n_blocks = len(rolling) // block_size
    if n_blocks < 2:
        return inflections

    block_avgs = []
    for b in range(n_blocks):
        start = b * block_size
        end = start + block_size
        block_vals = [rolling[j][1] for j in range(start, min(end, len(rolling)))]
        block_avg = sum(block_vals) / len(block_vals)
        block_date = rolling[start][0]
        block_avgs.append((block_date, block_avg))

    for i in range(1, len(block_avgs)):
        prev_block_avg = block_avgs[i - 1][1]
        curr_block_avg = block_avgs[i][1]
        block_date = block_avgs[i][0]

        base = max(prev_block_avg, 1.0)
        change_pct = ((curr_block_avg - prev_block_avg) / base) * 100

        if abs(change_pct) < min_change_pct:
            continue

        # Check if this is within a disruption period
        is_in_disruption = False
        for d in inflections:
            if d.type == 'disruption' and block_date >= d.date:
                is_in_disruption = True
                break
        if is_in_disruption:
            continue

        # Verify the new level is sustained using raw rolling average values
        rolling_start = i * block_size
        sustained = 0
        for j in range(rolling_start, len(rolling)):
            j_avg = rolling[j][1]
            if change_pct > 0 and j_avg >= prev_block_avg * (1 + min_change_pct / 200):
                sustained += 1
            elif change_pct < 0 and j_avg <= prev_block_avg * (1 - min_change_pct / 200):
                sustained += 1
            else:
                break

        if sustained < min_sustained_weeks:
            continue

        ip_type = 'step_up' if change_pct > 0 else 'step_down'

        inflections.append(InflectionPoint(
            date=block_date,
            type=ip_type,
            before_avg_weekly_km=round(prev_block_avg, 1),
            after_avg_weekly_km=round(curr_block_avg, 1),
            change_pct=round(change_pct, 1),
            sustained_weeks=sustained,
        ))

    inflections.sort(key=lambda ip: ip.date)
    return inflections


def _count_sustained_low(
    weekly_volumes: List[tuple],
    start_idx: int,
    threshold: float,
) -> int:
    """Count consecutive weeks below threshold from start_idx."""
    count = 0
    for i in range(start_idx, len(weekly_volumes)):
        if weekly_volumes[i][1] < threshold:
            count += 1
        else:
            break
    return count


def build_campaigns(
    athlete_id: UUID,
    inflection_points: List[InflectionPoint],
    events: List[PerformanceEvent],
    db: Session,
) -> List[TrainingCampaign]:
    """
    Construct training campaigns from inflection points and confirmed races.

    A campaign starts at the first step_up. Subsequent step_ups before a
    disruption are escalation phases within the same campaign — not separate
    campaigns. A campaign ends at a disruption or today.

    Races within the campaign window (and up to 4 weeks after a disruption
    for residual-fitness races) are linked.
    """
    weekly_volumes = _compute_weekly_volumes(athlete_id, db)
    if not weekly_volumes or not inflection_points:
        return []

    sorted_ips = sorted(inflection_points, key=lambda ip: ip.date)
    campaigns: List[TrainingCampaign] = []

    campaign_step_ups: List[InflectionPoint] = []

    def _finalize_campaign(step_ups: List[InflectionPoint], end: date, reason: str):
        # When multiple step_ups cluster before a disruption, the last one
        # is the campaign start — earlier ones were pre-campaign ramp/racing.
        start = step_ups[-1].date

        residual_cutoff = end + timedelta(weeks=4) if reason == 'disruption' else end
        linked_race_ids = [
            ev.id for ev in events
            if start <= ev.event_date <= residual_cutoff
        ]

        phases = _detect_phases(start, end, weekly_volumes, athlete_id, db)

        campaign_weeks_data = [
            (ws, vol) for ws, vol in weekly_volumes
            if start <= ws <= end
        ]
        total_weeks = max(1, (end - start).days // 7)
        peak_vol = max((vol for _, vol in campaign_weeks_data), default=0.0)
        avg_vol = (
            sum(vol for _, vol in campaign_weeks_data) / len(campaign_weeks_data)
            if campaign_weeks_data else 0.0
        )

        campaigns.append(TrainingCampaign(
            athlete_id=athlete_id,
            start_date=start,
            end_date=end,
            end_reason=reason,
            phases=phases,
            linked_races=linked_race_ids,
            total_weeks=total_weeks,
            peak_weekly_volume_km=round(peak_vol, 1),
            avg_weekly_volume_km=round(avg_vol, 1),
        ))

    for ip in sorted_ips:
        if ip.type == 'step_up':
            campaign_step_ups.append(ip)

        elif ip.type == 'disruption':
            if campaign_step_ups:
                _finalize_campaign(campaign_step_ups, ip.date, 'disruption')
                campaign_step_ups = []

    # If step_ups are still open, close as ongoing
    if campaign_step_ups:
        _finalize_campaign(campaign_step_ups, date.today(), 'ongoing')

    return campaigns


def _detect_phases(
    start_date: date,
    end_date: date,
    weekly_volumes: List[tuple],
    athlete_id: UUID,
    db: Session,
) -> List[CampaignPhase]:
    """
    Detect training phases within a campaign by analyzing volume trends
    and intensity patterns over the campaign period.
    """
    campaign_weeks = [
        (ws, vol) for ws, vol in weekly_volumes
        if start_date <= ws <= end_date
    ]

    if len(campaign_weeks) < 4:
        return [CampaignPhase(
            name='base_building',
            start_date=start_date,
            end_date=end_date,
            weeks=max(1, (end_date - start_date).days // 7),
            avg_volume_km=round(
                sum(v for _, v in campaign_weeks) / max(1, len(campaign_weeks)), 1
            ),
        )]

    # Split into thirds and analyze volume trend
    n = len(campaign_weeks)
    third = max(1, n // 3)

    early = campaign_weeks[:third]
    mid = campaign_weeks[third:2 * third]
    late = campaign_weeks[2 * third:]

    early_avg = sum(v for _, v in early) / len(early)
    mid_avg = sum(v for _, v in mid) / len(mid) if mid else early_avg
    late_avg = sum(v for _, v in late) / len(late) if late else mid_avg

    phases = []

    # Early phase: usually base building
    early_end = mid[0][0] - timedelta(days=1) if mid else end_date
    phases.append(CampaignPhase(
        name='base_building',
        start_date=early[0][0],
        end_date=early_end,
        weeks=len(early),
        avg_volume_km=round(early_avg, 1),
    ))

    # Mid phase: escalation if volume is higher or similar
    if mid:
        mid_end = late[0][0] - timedelta(days=1) if late else end_date
        mid_name = 'escalation' if mid_avg >= early_avg * 0.9 else 'base_building'
        phases.append(CampaignPhase(
            name=mid_name,
            start_date=mid[0][0],
            end_date=mid_end,
            weeks=len(mid),
            avg_volume_km=round(mid_avg, 1),
        ))

    # Late phase
    if late:
        if late_avg < mid_avg * 0.7:
            late_name = 'taper'
        elif late_avg >= mid_avg * 0.9:
            late_name = 'race_specific'
        else:
            late_name = 'race_specific'

        # Check if the last few weeks are a cliff (disruption)
        if len(late) >= 2:
            last_two = [v for _, v in late[-2:]]
            if all(v < early_avg * 0.25 for v in last_two):
                late_name = 'disrupted'

        phases.append(CampaignPhase(
            name=late_name,
            start_date=late[0][0],
            end_date=late[-1][0] + timedelta(days=6),
            weeks=len(late),
            avg_volume_km=round(late_avg, 1),
        ))

    return phases


def classify_disruption(
    athlete_id: UUID,
    disruption_date: date,
    db: Session,
) -> dict:
    """
    Describe the volume pattern around a disruption using only what the
    data shows. No guessing at cause — we can't know from mileage data
    whether it was injury, illness, or life event.

    Returns the observable pattern: how much volume was there before,
    how quickly it declined, how long the low period lasted, and whether
    recovery has started.
    """
    weekly_volumes = _compute_weekly_volumes(athlete_id, db)
    if not weekly_volumes:
        return {
            'severity': 'unknown',
            'duration_weeks': 0,
            'volume_before_km': 0.0,
            'volume_during_km': 0.0,
            'volume_after_km': 0.0,
            'recovery_pattern': 'unknown',
            'decline_pattern': 'unknown',
        }

    # Volume in the 4 weeks before disruption
    before_start = disruption_date - timedelta(weeks=4)
    before_vols = [vol for ws, vol in weekly_volumes if before_start <= ws < disruption_date]
    volume_before = sum(before_vols) / max(1, len(before_vols))

    # Scan 12-week window after disruption date for the low-volume period.
    # Progressive disruptions may take weeks to reach near-zero.
    low_threshold = volume_before * 0.30
    post_window = [
        (ws, vol) for ws, vol in weekly_volumes
        if disruption_date <= ws <= disruption_date + timedelta(weeks=12)
    ]

    low_weeks = [(ws, vol) for ws, vol in post_window if vol < low_threshold]
    duration_weeks = len(low_weeks)

    volume_during = (
        sum(v for _, v in low_weeks) / len(low_weeks)
        if low_weeks else 0.0
    )

    # Decline pattern: did volume drop instantly or taper down?
    if post_window:
        first_week_vol = post_window[0][1]
        if first_week_vol < low_threshold:
            decline_pattern = 'immediate'
        else:
            decline_pattern = 'progressive'
    else:
        decline_pattern = 'unknown'

    # Recovery: look at volume after the low period
    low_end = disruption_date + timedelta(weeks=12)
    if low_weeks:
        low_end = max(ws for ws, _ in low_weeks) + timedelta(weeks=1)

    recovery_vols = [
        vol for ws, vol in weekly_volumes
        if ws >= low_end
    ]

    if not recovery_vols:
        recovery_pattern = 'not_yet_recovered'
    elif len(recovery_vols) >= 4:
        avg_first_4 = sum(recovery_vols[:4]) / 4
        if avg_first_4 > volume_before * 0.6:
            recovery_pattern = 'rapid'
        elif avg_first_4 > volume_before * 0.3:
            recovery_pattern = 'gradual'
        else:
            recovery_pattern = 'slow'
    else:
        avg_recovery = sum(recovery_vols) / len(recovery_vols)
        if avg_recovery > volume_before * 0.4:
            recovery_pattern = 'gradual'
        else:
            recovery_pattern = 'slow'

    # Severity: only from the volume pattern
    min_vol_in_window = min((v for _, v in post_window), default=volume_before)
    if min_vol_in_window < 1.0 and duration_weeks >= 4:
        severity = 'complete_stop'
    elif min_vol_in_window < volume_before * 0.10:
        severity = 'near_complete_stop'
    elif duration_weeks >= 2:
        severity = 'major_reduction'
    elif duration_weeks >= 1:
        severity = 'moderate_reduction'
    else:
        severity = 'minor'

    return {
        'severity': severity,
        'decline_pattern': decline_pattern,
        'duration_weeks': duration_weeks,
        'volume_before_km': round(volume_before, 1),
        'volume_during_km': round(volume_during, 1),
        'volume_after_km': round(
            sum(recovery_vols[:4]) / max(1, len(recovery_vols[:4])), 1
        ) if recovery_vols else 0.0,
        'recovery_pattern': recovery_pattern,
    }


def store_campaign_data_on_events(
    athlete_id: UUID,
    campaigns: List[TrainingCampaign],
    db: Session,
) -> int:
    """
    Store campaign summary on each linked PerformanceEvent.
    Clears stale campaign_data first, then sets fresh values.
    Returns the number of events updated.
    """
    db.query(PerformanceEvent).filter(
        PerformanceEvent.athlete_id == athlete_id,
        PerformanceEvent.campaign_data.isnot(None),
    ).update({PerformanceEvent.campaign_data: None}, synchronize_session='fetch')

    updated = 0
    for campaign in campaigns:
        campaign_summary = {
            'start_date': campaign.start_date.isoformat(),
            'end_date': campaign.end_date.isoformat(),
            'end_reason': campaign.end_reason,
            'total_weeks': campaign.total_weeks,
            'peak_weekly_volume_km': campaign.peak_weekly_volume_km,
            'avg_weekly_volume_km': campaign.avg_weekly_volume_km,
            'phases': [
                {
                    'name': p.name,
                    'start_date': p.start_date.isoformat(),
                    'end_date': p.end_date.isoformat(),
                    'weeks': p.weeks,
                    'avg_volume_km': p.avg_volume_km,
                }
                for p in campaign.phases
            ],
        }

        for race_id in campaign.linked_races:
            event = db.query(PerformanceEvent).filter(
                PerformanceEvent.id == race_id,
                PerformanceEvent.athlete_id == athlete_id,
            ).first()
            if event:
                event.campaign_data = campaign_summary
                # Tag residual fitness races
                if (campaign.end_reason == 'disruption'
                        and event.event_date > campaign.end_date):
                    campaign_summary_with_residual = dict(campaign_summary)
                    campaign_summary_with_residual['raced_on_residual_fitness'] = True
                    event.campaign_data = campaign_summary_with_residual
                updated += 1

    db.flush()
    return updated
