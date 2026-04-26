"""
Fingerprint Analysis — Racing Fingerprint Phase 1C

Five-layer pattern extraction across confirmed PerformanceEvents.
Each layer answers a different question about an athlete's racing history.
Every finding produces a sentence. The sentence is the product.

Layers 1-4 from Phase 1B. Layer 5 (trajectory) added in Phase 1C.
Layer 2 now uses campaign_data when available (Phase 1C revision).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import Activity, PerformanceEvent, AthleteFinding

logger = logging.getLogger(__name__)

QUALITY_THRESHOLDS = {
    'min_sample_size': 3,
    'min_effect_size': 0.3,
    'max_p_value': 0.10,
    'min_comparison_total': 6,
    'min_per_group': 3,
    'high_confidence_sample': 8,
    'high_confidence_per_group': 4,
    'high_confidence_effect': 0.5,
    'high_confidence_p': 0.05,
}


@dataclass
class FingerprintFindingResult:
    layer: int
    finding_type: str
    sentence: str
    evidence: dict
    statistical_confidence: float
    effect_size: float
    sample_size: int
    confidence_tier: str
    is_significant: bool


def extract_fingerprint_findings(
    athlete_id: UUID,
    db: Session,
) -> List[FingerprintFindingResult]:
    """
    Run all four layers of pattern extraction across confirmed events.
    Returns findings sorted by significance (quality-gate-passing first).
    """
    from models import Athlete as AthleteModel
    athlete = db.query(AthleteModel).filter(AthleteModel.id == athlete_id).first()
    units = athlete.preferred_units if athlete else "imperial"

    events = db.query(PerformanceEvent).filter(
        PerformanceEvent.athlete_id == athlete_id,
        PerformanceEvent.user_confirmed == True,  # noqa: E712
    ).order_by(PerformanceEvent.event_date).all()

    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
    ).all()

    all_findings: List[FingerprintFindingResult] = []

    try:
        all_findings.extend(_layer1_pb_distribution(events, activities, db))
    except Exception as e:
        logger.warning("Layer 1 failed: %s", e)

    try:
        all_findings.extend(_layer2_block_comparison(events, units=units))
    except Exception as e:
        logger.warning("Layer 2 failed: %s", e)

    try:
        all_findings.extend(_layer3_tuneup_pattern(events))
    except Exception as e:
        logger.warning("Layer 3 failed: %s", e)

    try:
        all_findings.extend(_layer4_fitness_relative(events, units=units))
    except Exception as e:
        logger.warning("Layer 4 failed: %s", e)

    try:
        all_findings.extend(_layer5_trajectory(events, units=units))
    except Exception as e:
        logger.warning("Layer 5 failed: %s", e)

    all_findings.sort(key=lambda f: (
        0 if f.confidence_tier == 'high' else
        1 if f.confidence_tier == 'exploratory' else
        2 if f.confidence_tier == 'descriptive' else 3,
        -f.effect_size,
    ))

    return all_findings


def store_findings(
    athlete_id: UUID,
    findings: List[FingerprintFindingResult],
    db: Session,
) -> int:
    """
    Store quality-gate-passing findings. Replaces previous findings
    for this athlete (full recompute model).
    """
    from datetime import datetime, timezone

    db.query(AthleteFinding).filter(
        AthleteFinding.athlete_id == athlete_id
    ).delete()

    stored = 0
    for f in findings:
        if f.confidence_tier == 'suppressed':
            continue
        sf = AthleteFinding(
            athlete_id=athlete_id,
            investigation_name=f'legacy_layer{f.layer}',
            finding_type=f.finding_type,
            sentence=f.sentence,
            receipts=f.evidence,
            confidence=f.confidence_tier,
            first_detected_at=datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc),
            is_active=True,
        )
        db.add(sf)
        stored += 1

    return stored


def passes_quality_gate(finding: FingerprintFindingResult) -> bool:
    """Returns True if the finding clears the automated quality gate."""
    # Trajectory findings are factual observations (you went from X to Y),
    # not statistical inferences — they need strong effect size, not large
    # sample size. A 7-minute half marathon PB across 2 races speaks for itself.
    is_trajectory = finding.finding_type.startswith('trajectory_')
    min_n = 2 if is_trajectory else QUALITY_THRESHOLDS['min_sample_size']

    if finding.sample_size < min_n:
        return False
    if abs(finding.effect_size) < QUALITY_THRESHOLDS['min_effect_size']:
        return False
    return True


def _assign_confidence_tier(
    finding: FingerprintFindingResult,
    is_comparison_layer: bool = False,
    group_sizes: Optional[tuple] = None,
) -> str:
    """Determine the confidence tier for a finding."""
    if not passes_quality_gate(finding):
        return 'suppressed'

    if is_comparison_layer:
        if group_sizes and min(group_sizes) < QUALITY_THRESHOLDS['min_per_group']:
            return 'descriptive'

        if (finding.sample_size >= QUALITY_THRESHOLDS['high_confidence_sample'] and
                abs(finding.effect_size) >= QUALITY_THRESHOLDS['high_confidence_effect'] and
                finding.statistical_confidence >= (1 - QUALITY_THRESHOLDS['high_confidence_p'])):
            if group_sizes and min(group_sizes) >= QUALITY_THRESHOLDS['high_confidence_per_group']:
                return 'high'

        if finding.statistical_confidence >= (1 - QUALITY_THRESHOLDS['max_p_value']):
            return 'exploratory'

        return 'descriptive'

    # Descriptive layers (1 and 3)
    if (finding.sample_size >= QUALITY_THRESHOLDS['high_confidence_sample'] and
            abs(finding.effect_size) >= QUALITY_THRESHOLDS['high_confidence_effect']):
        return 'high'

    return 'exploratory'


def _cohens_d(group_a: List[float], group_b: List[float]) -> float:
    """Compute Cohen's d from two groups using pooled standard deviation."""
    if len(group_a) < 1 or len(group_b) < 1:
        return 0.0
    mean_a = sum(group_a) / len(group_a)
    mean_b = sum(group_b) / len(group_b)

    n_a, n_b = len(group_a), len(group_b)

    if n_a + n_b <= 2:
        return abs(mean_a - mean_b)

    var_a = sum((x - mean_a) ** 2 for x in group_a) / max(n_a - 1, 1)
    var_b = sum((x - mean_b) ** 2 for x in group_b) / max(n_b - 1, 1)

    pooled_sd = math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))
    if pooled_sd == 0:
        return 0.0

    return (mean_a - mean_b) / pooled_sd


def _mann_whitney_u(group_a: List[float], group_b: List[float]) -> Optional[float]:
    """Simple Mann-Whitney U test returning approximate p-value.
    Returns None if either group has < 3 elements."""
    if len(group_a) < 3 or len(group_b) < 3:
        return None

    try:
        from scipy.stats import mannwhitneyu
        _, p = mannwhitneyu(group_a, group_b, alternative='two-sided')
        return float(p)
    except ImportError:
        pass

    # Fallback: manual U statistic with normal approximation
    combined = [(v, 'a') for v in group_a] + [(v, 'b') for v in group_b]
    combined.sort(key=lambda x: x[0])

    # Assign ranks (handle ties with average rank)
    ranks: Dict[int, float] = {}
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2
        for k in range(i, j):
            ranks[k] = avg_rank
        i = j

    r_a = sum(ranks[i] for i, (_, g) in enumerate(combined) if g == 'a')
    n_a, n_b = len(group_a), len(group_b)
    u_a = r_a - n_a * (n_a + 1) / 2
    u = min(u_a, n_a * n_b - u_a)

    mu = n_a * n_b / 2
    sigma = math.sqrt(n_a * n_b * (n_a + n_b + 1) / 12)
    if sigma == 0:
        return 1.0
    z = abs((u - mu) / sigma)

    # Approximate two-tailed p from z using error function
    p = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
    return max(p, 0.0001)


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))


def _format_pace(sec_per_mile: float, units: str = "imperial") -> str:
    """Format pace as min:ss/mi (imperial) or min:ss/km (metric)."""
    if units == "metric":
        sec_per_unit = sec_per_mile / 1.60934
        label = "/km"
    else:
        sec_per_unit = sec_per_mile
        label = "/mi"
    mins = int(sec_per_unit // 60)
    secs = int(sec_per_unit % 60)
    return f"{mins}:{secs:02d}{label}"


# ═══════════════════════════════════════════════════════
# Layer 1: PB Distribution
# ═══════════════════════════════════════════════════════

def _layer1_pb_distribution(
    events: List[PerformanceEvent],
    activities: List[Activity],
    db: Session,
) -> List[FingerprintFindingResult]:
    """Where do PBs live — race day vs training?"""
    if len(events) < 3:
        return []

    findings: List[FingerprintFindingResult] = []

    # Group events by distance category
    by_dist: Dict[str, List[PerformanceEvent]] = {}
    for ev in events:
        by_dist.setdefault(ev.distance_category, []).append(ev)

    # For each distance with race events, find best training effort
    race_uplifts = []
    for dist_cat, dist_events in by_dist.items():
        best_race = min(dist_events, key=lambda e: e.time_seconds)

        from services.personal_best import DISTANCE_CATEGORIES
        if dist_cat not in DISTANCE_CATEGORIES:
            continue
        lo, hi = DISTANCE_CATEGORIES[dist_cat]

        # Find best training run at this distance (non-race)
        event_act_ids = {e.activity_id for e in events}
        training_acts = [
            a for a in activities
            if a.distance_m and lo <= float(a.distance_m) <= hi
            and a.id not in event_act_ids
            and a.duration_s and a.duration_s > 0
        ]

        if not training_acts:
            continue

        best_training = min(training_acts, key=lambda a: a.duration_s)
        if best_training.duration_s > 0:
            uplift = (best_training.duration_s - best_race.time_seconds) / best_training.duration_s * 100
            race_uplifts.append({
                'distance': dist_cat,
                'race_time': best_race.time_seconds,
                'training_time': best_training.duration_s,
                'uplift_pct': round(uplift, 1),
            })

    if not race_uplifts:
        return []

    avg_uplift = _mean([u['uplift_pct'] for u in race_uplifts])
    effect = abs(avg_uplift) / max(_std([u['uplift_pct'] for u in race_uplifts]), 1.0)

    if abs(avg_uplift) >= 2.0:
        sentence = f"You race {abs(avg_uplift):.0f}% faster than your best training efforts at the same distances."
    else:
        sentence = f"Your training and race performances are within {abs(avg_uplift):.0f}% — you push close to race intensity in training."

    finding = FingerprintFindingResult(
        layer=1,
        finding_type='pb_distribution',
        sentence=sentence,
        evidence={'uplifts': race_uplifts, 'avg_uplift_pct': round(avg_uplift, 1)},
        statistical_confidence=min(len(race_uplifts) / 5.0, 1.0),
        effect_size=round(effect, 2),
        sample_size=len(events),
        confidence_tier='',
        is_significant=False,
    )
    finding.confidence_tier = _assign_confidence_tier(finding, is_comparison_layer=False)
    finding.is_significant = finding.confidence_tier != 'suppressed'
    findings.append(finding)

    return findings


# ═══════════════════════════════════════════════════════
# Layer 2: Campaign Comparison (upgraded from Block Signature)
# ═══════════════════════════════════════════════════════

def _layer2_block_comparison(
    events: List[PerformanceEvent],
    units: str = "imperial",
) -> List[FingerprintFindingResult]:
    """What training patterns preceded the best races?

    Uses campaign_data when available (Phase 1C), falling back to
    block_signature for backward compatibility.
    """
    # Prefer campaign data for comparison
    events_with_campaigns = [e for e in events if e.campaign_data and e.rpi_at_event]
    if len(events_with_campaigns) >= 4:
        return _layer2_campaign_comparison(events_with_campaigns, units)

    # Fallback to block signature
    events_with_sigs = [e for e in events if e.block_signature and e.rpi_at_event]
    if len(events_with_sigs) < 4:
        return []
    return _layer2_block_signature_comparison(events_with_sigs, units)


def _layer2_campaign_comparison(
    events: List[PerformanceEvent],
    units: str = "imperial",
) -> List[FingerprintFindingResult]:
    """Compare full campaign dimensions between best and worst races."""
    sorted_events = sorted(events, key=lambda e: e.rpi_at_event, reverse=True)
    mid = len(sorted_events) // 2
    top_group = sorted_events[:mid]
    bottom_group = sorted_events[mid:]

    findings: List[FingerprintFindingResult] = []
    group_sizes = (len(top_group), len(bottom_group))
    can_stat_test = min(group_sizes) >= QUALITY_THRESHOLDS['min_per_group']

    KM_TO_MI = 0.621371
    is_imperial = units != "metric"
    dist_unit = "mi" if is_imperial else "km"

    dimensions = [
        ('total_weeks', 'campaign length', 'weeks', False),
        ('peak_weekly_volume_km', 'peak weekly volume', f'{dist_unit}/week', is_imperial),
        ('avg_weekly_volume_km', 'average weekly volume', f'{dist_unit}/week', is_imperial),
    ]

    for dim_key, dim_label, dim_unit, needs_conversion in dimensions:
        top_vals = [
            e.campaign_data.get(dim_key, 0) for e in top_group
            if e.campaign_data.get(dim_key) is not None
        ]
        bottom_vals = [
            e.campaign_data.get(dim_key, 0) for e in bottom_group
            if e.campaign_data.get(dim_key) is not None
        ]

        if not top_vals or not bottom_vals:
            continue

        d = _cohens_d(top_vals, bottom_vals)
        p_value = None
        stat_conf = 0.5

        if can_stat_test:
            p_value = _mann_whitney_u(top_vals, bottom_vals)
            if p_value is not None:
                stat_conf = 1 - p_value

        top_mean = _mean(top_vals)
        bottom_mean = _mean(bottom_vals)
        diff = top_mean - bottom_mean

        # Suppress trivially small differences — with a single campaign,
        # best and worst races share identical campaign stats so any
        # difference is noise.
        overall_mean = (top_mean + bottom_mean) / 2
        if overall_mean > 0 and abs(diff) / overall_mean < 0.10:
            continue
        if abs(diff) < 0.01:
            continue

        display_top = top_mean * KM_TO_MI if needs_conversion else top_mean
        display_bottom = bottom_mean * KM_TO_MI if needs_conversion else bottom_mean

        direction = "higher" if diff > 0 else "lower"

        # Narrative-quality sentence that references campaign scope
        if dim_key == 'total_weeks':
            sentence = (
                f"Your best races came after campaigns averaging {display_top:.0f} weeks "
                f"of sustained preparation, vs {display_bottom:.0f} weeks for weaker races."
            )
        elif dim_key == 'peak_weekly_volume_km':
            sentence = (
                f"Your best races followed campaigns with peak volume of "
                f"{display_top:.0f} {dim_unit}, "
                f"vs {display_bottom:.0f} {dim_unit} for weaker races."
            )
        elif dim_key == 'avg_weekly_volume_km':
            sentence = (
                f"The campaigns behind your best races averaged "
                f"{display_top:.0f} {dim_unit} consistently, "
                f"vs {display_bottom:.0f} {dim_unit} for weaker races."
            )
        else:
            sentence = (
                f"Your best races had {direction} {dim_label}: "
                f"{display_top:.0f} vs {display_bottom:.0f} {dim_unit}."
            )

        finding = FingerprintFindingResult(
            layer=2,
            finding_type=f'campaign_{dim_key}',
            sentence=sentence,
            evidence={
                'dimension': dim_key,
                'source': 'campaign_data',
                'top_mean': round(top_mean, 1),
                'top_std': round(_std(top_vals), 1),
                'bottom_mean': round(bottom_mean, 1),
                'bottom_std': round(_std(bottom_vals), 1),
                'p_value': round(p_value, 4) if p_value is not None else None,
                'n_top': len(top_vals),
                'n_bottom': len(bottom_vals),
            },
            statistical_confidence=round(stat_conf, 3),
            effect_size=round(abs(d), 2),
            sample_size=len(events),
            confidence_tier='',
            is_significant=False,
        )
        finding.confidence_tier = _assign_confidence_tier(
            finding, is_comparison_layer=True, group_sizes=group_sizes
        )
        finding.is_significant = finding.confidence_tier != 'suppressed'
        findings.append(finding)

    # Phase composition comparison
    top_phases = []
    bottom_phases = []
    for e in top_group:
        if e.campaign_data.get('phases'):
            top_phases.append([p['name'] for p in e.campaign_data['phases']])
    for e in bottom_group:
        if e.campaign_data.get('phases'):
            bottom_phases.append([p['name'] for p in e.campaign_data['phases']])

    if top_phases and bottom_phases:
        top_has_escalation = sum(1 for pp in top_phases if 'escalation' in pp) / len(top_phases)
        bottom_has_escalation = sum(1 for pp in bottom_phases if 'escalation' in pp) / len(bottom_phases)

        if top_has_escalation > bottom_has_escalation + 0.3:
            sentence = (
                "Your best races followed campaigns with a distinct escalation phase — "
                "you built a base then deliberately increased intensity."
            )
            finding = FingerprintFindingResult(
                layer=2,
                finding_type='campaign_escalation',
                sentence=sentence,
                evidence={
                    'top_escalation_rate': round(top_has_escalation, 2),
                    'bottom_escalation_rate': round(bottom_has_escalation, 2),
                },
                statistical_confidence=0.6,
                effect_size=round(abs(top_has_escalation - bottom_has_escalation), 2),
                sample_size=len(events),
                confidence_tier='',
                is_significant=False,
            )
            finding.confidence_tier = _assign_confidence_tier(finding, is_comparison_layer=False)
            finding.is_significant = finding.confidence_tier != 'suppressed'
            findings.append(finding)

    # Check for disruption context
    residual_races = [
        e for e in events
        if e.campaign_data.get('raced_on_residual_fitness')
    ]
    if residual_races:
        best_residual = max(residual_races, key=lambda e: e.rpi_at_event)
        campaign_weeks = best_residual.campaign_data.get('total_weeks', 0)
        sentence = (
            f"You raced on residual fitness after your campaign was interrupted — "
            f"and still performed at a high level. "
            f"That {campaign_weeks}-week campaign built deep fitness."
        )
        finding = FingerprintFindingResult(
            layer=2,
            finding_type='residual_fitness',
            sentence=sentence,
            evidence={
                'residual_race_count': len(residual_races),
                'campaign_weeks': campaign_weeks,
                'best_residual_rpi': round(best_residual.rpi_at_event, 1) if best_residual.rpi_at_event else None,
            },
            statistical_confidence=0.7,
            effect_size=0.5,
            sample_size=len(events),
            confidence_tier='',
            is_significant=False,
        )
        finding.confidence_tier = _assign_confidence_tier(finding, is_comparison_layer=False)
        finding.is_significant = finding.confidence_tier != 'suppressed'
        findings.append(finding)

    return findings


def _layer2_block_signature_comparison(
    events: List[PerformanceEvent],
    units: str = "imperial",
) -> List[FingerprintFindingResult]:
    """Fallback: compare block signatures when campaign data isn't available."""
    sorted_events = sorted(events, key=lambda e: e.rpi_at_event, reverse=True)
    mid = len(sorted_events) // 2
    top_group = sorted_events[:mid]
    bottom_group = sorted_events[mid:]

    findings: List[FingerprintFindingResult] = []
    group_sizes = (len(top_group), len(bottom_group))
    can_stat_test = min(group_sizes) >= QUALITY_THRESHOLDS['min_per_group']

    KM_TO_MI = 0.621371
    is_imperial = units != "metric"
    dist_unit = "mi" if is_imperial else "km"

    dimensions = [
        ('peak_volume_km', 'peak training volume', f'{dist_unit}/week', is_imperial),
        ('peak_volume_week', 'peak volume timing', 'weeks before race', False),
        ('quality_sessions', 'hard sessions in the block', 'sessions', False),
        ('long_run_max_km', 'longest run', dist_unit, is_imperial),
    ]

    for dim_key, dim_label, dim_unit, needs_conversion in dimensions:
        top_vals = [
            e.block_signature.get(dim_key, 0) for e in top_group
            if e.block_signature.get(dim_key) is not None
        ]
        bottom_vals = [
            e.block_signature.get(dim_key, 0) for e in bottom_group
            if e.block_signature.get(dim_key) is not None
        ]

        if not top_vals or not bottom_vals:
            continue

        d = _cohens_d(top_vals, bottom_vals)
        p_value = None
        stat_conf = 0.5

        if can_stat_test:
            p_value = _mann_whitney_u(top_vals, bottom_vals)
            if p_value is not None:
                stat_conf = 1 - p_value

        top_mean = _mean(top_vals)
        bottom_mean = _mean(bottom_vals)
        diff = top_mean - bottom_mean

        if abs(diff) < 0.01:
            continue

        display_top = top_mean * KM_TO_MI if needs_conversion else top_mean
        display_bottom = bottom_mean * KM_TO_MI if needs_conversion else bottom_mean

        direction = "higher" if diff > 0 else "lower"
        sentence = (
            f"Your best races had {direction} {dim_label}: "
            f"{display_top:.0f} vs {display_bottom:.0f} {dim_unit}."
        )

        finding = FingerprintFindingResult(
            layer=2,
            finding_type=f'block_{dim_key}',
            sentence=sentence,
            evidence={
                'dimension': dim_key,
                'source': 'block_signature',
                'top_mean': round(top_mean, 1),
                'top_std': round(_std(top_vals), 1),
                'bottom_mean': round(bottom_mean, 1),
                'bottom_std': round(_std(bottom_vals), 1),
                'p_value': round(p_value, 4) if p_value is not None else None,
                'n_top': len(top_vals),
                'n_bottom': len(bottom_vals),
            },
            statistical_confidence=round(stat_conf, 3),
            effect_size=round(abs(d), 2),
            sample_size=len(events),
            confidence_tier='',
            is_significant=False,
        )
        finding.confidence_tier = _assign_confidence_tier(
            finding, is_comparison_layer=True, group_sizes=group_sizes
        )
        finding.is_significant = finding.confidence_tier != 'suppressed'
        findings.append(finding)

    return findings


# ═══════════════════════════════════════════════════════
# Layer 3: Tune-up to A-Race Relationship
# ═══════════════════════════════════════════════════════

def _layer3_tuneup_pattern(
    events: List[PerformanceEvent],
) -> List[FingerprintFindingResult]:
    """Do tune-up PBs predict or anti-predict A-race success?"""
    tuneups = [e for e in events if e.race_role == 'tune_up']
    a_races = [e for e in events if e.race_role == 'a_race']

    pairs = []
    for tu in tuneups:
        for ar in a_races:
            gap = (ar.event_date - tu.event_date).days
            if 7 <= gap <= 56:
                pairs.append((tu, ar))
                break

    if len(pairs) < 2:
        return []

    findings: List[FingerprintFindingResult] = []

    # Check if tune-up PBs correlate with A-race outcome
    tu_pb_araces = [ar.rpi_at_event for tu, ar in pairs if tu.is_personal_best and ar.rpi_at_event]
    tu_nopb_araces = [ar.rpi_at_event for tu, ar in pairs if not tu.is_personal_best and ar.rpi_at_event]

    if tu_pb_araces and tu_nopb_araces:
        d = _cohens_d(tu_pb_araces, tu_nopb_araces)
        diff_mean = _mean(tu_pb_araces) - _mean(tu_nopb_araces)

        if diff_mean > 0:
            sentence = "When you set a personal best in your tune-up race, your main race performance tends to be stronger."
        else:
            sentence = "Setting a personal best in your tune-up race hasn't predicted better main race performance — your body may need more recovery after peak efforts."

        finding = FingerprintFindingResult(
            layer=3,
            finding_type='tuneup_pb_effect',
            sentence=sentence,
            evidence={
                'pairs_with_tu_pb': len(tu_pb_araces),
                'pairs_without_tu_pb': len(tu_nopb_araces),
                'avg_arace_rpi_after_pb': round(_mean(tu_pb_araces), 1) if tu_pb_araces else None,
                'avg_arace_rpi_after_nopb': round(_mean(tu_nopb_araces), 1) if tu_nopb_araces else None,
            },
            statistical_confidence=min(len(pairs) / 5.0, 1.0),
            effect_size=round(abs(d), 2),
            sample_size=len(pairs),
            confidence_tier='',
            is_significant=False,
        )
        finding.confidence_tier = _assign_confidence_tier(finding, is_comparison_layer=False)
        finding.is_significant = finding.confidence_tier != 'suppressed'
        findings.append(finding)

    # Gap analysis
    gaps = [(ar.event_date - tu.event_date).days for tu, ar in pairs if ar.rpi_at_event]
    rpis = [ar.rpi_at_event for _, ar in pairs if ar.rpi_at_event]
    if len(gaps) >= 3 and len(rpis) >= 3:
        short_gap = [(g, r) for g, r in zip(gaps, rpis) if g <= 28]
        long_gap = [(g, r) for g, r in zip(gaps, rpis) if g > 28]

        if short_gap and long_gap:
            short_rpis = [r for _, r in short_gap]
            long_rpis = [r for _, r in long_gap]
            d = _cohens_d(long_rpis, short_rpis)

            if abs(d) >= 0.3:
                better = "longer" if _mean(long_rpis) > _mean(short_rpis) else "shorter"
                sentence = f"You tend to race better with a {better} gap between your tune-up and main race."

                finding = FingerprintFindingResult(
                    layer=3,
                    finding_type='tuneup_gap',
                    sentence=sentence,
                    evidence={
                        'short_gap_avg_days': round(_mean([g for g, _ in short_gap]), 0),
                        'long_gap_avg_days': round(_mean([g for g, _ in long_gap]), 0),
                        'short_gap_count': len(short_gap),
                        'long_gap_count': len(long_gap),
                    },
                    statistical_confidence=min(len(pairs) / 5.0, 1.0),
                    effect_size=round(abs(d), 2),
                    sample_size=len(pairs),
                    confidence_tier='',
                    is_significant=False,
                )
                finding.confidence_tier = _assign_confidence_tier(finding, is_comparison_layer=False)
                finding.is_significant = finding.confidence_tier != 'suppressed'
                findings.append(finding)

    return findings


# ═══════════════════════════════════════════════════════
# Layer 4: Fitness-Relative Performance
# ═══════════════════════════════════════════════════════

def _layer4_fitness_relative(
    events: List[PerformanceEvent],
    units: str = "imperial",
) -> List[FingerprintFindingResult]:
    """What training patterns produce outperformance of fitness level?

    Activation gate: requires fitness_relative_performance to be non-null.
    """
    with_frp = [e for e in events if e.fitness_relative_performance is not None]
    if len(with_frp) < 4:
        return []

    sorted_by_frp = sorted(with_frp, key=lambda e: e.fitness_relative_performance, reverse=True)
    mid = len(sorted_by_frp) // 2
    outperformers = sorted_by_frp[:mid]
    underperformers = sorted_by_frp[mid:]

    findings: List[FingerprintFindingResult] = []
    group_sizes = (len(outperformers), len(underperformers))
    can_stat_test = min(group_sizes) >= QUALITY_THRESHOLDS['min_per_group']

    is_imperial = units != "metric"

    dimensions = [
        ('peak_volume_km', 'peak training volume', is_imperial),
        ('taper_start_week', 'taper timing', False),
        ('quality_sessions', 'hard sessions', False),
        ('long_run_max_km', 'longest run', is_imperial),
    ]

    for dim_key, dim_label, needs_conversion in dimensions:
        out_vals = [
            e.block_signature.get(dim_key, 0) for e in outperformers
            if e.block_signature and e.block_signature.get(dim_key) is not None
        ]
        under_vals = [
            e.block_signature.get(dim_key, 0) for e in underperformers
            if e.block_signature and e.block_signature.get(dim_key) is not None
        ]

        if not out_vals or not under_vals:
            continue

        d = _cohens_d(out_vals, under_vals)
        p_value = _mann_whitney_u(out_vals, under_vals) if can_stat_test else None
        stat_conf = (1 - p_value) if p_value is not None else 0.5

        if abs(d) < 0.2:
            continue

        direction = "higher" if _mean(out_vals) > _mean(under_vals) else "lower"
        sentence = (
            f"When you outperform your fitness level, you tend to have {direction} {dim_label} "
            f"in the training block."
        )

        finding = FingerprintFindingResult(
            layer=4,
            finding_type=f'fitness_rel_{dim_key}',
            sentence=sentence,
            evidence={
                'outperformer_mean': round(_mean(out_vals), 1),
                'underperformer_mean': round(_mean(under_vals), 1),
                'p_value': round(p_value, 4) if p_value is not None else None,
                'n_out': len(out_vals),
                'n_under': len(under_vals),
            },
            statistical_confidence=round(stat_conf, 3),
            effect_size=round(abs(d), 2),
            sample_size=len(with_frp),
            confidence_tier='',
            is_significant=False,
        )
        finding.confidence_tier = _assign_confidence_tier(
            finding, is_comparison_layer=True, group_sizes=group_sizes
        )
        finding.is_significant = finding.confidence_tier != 'suppressed'
        findings.append(finding)

    return findings


# ═══════════════════════════════════════════════════════
# Layer 5: Performance Trajectory
# ═══════════════════════════════════════════════════════

def _layer5_trajectory(
    events: List[PerformanceEvent],
    units: str = "imperial",
) -> List[FingerprintFindingResult]:
    """
    Analyze performance trajectory across all races.

    Detects:
    - Continuous improvement (PB every race when healthy)
    - Improvement rate acceleration
    - Disruption resilience (residual fitness races)
    - Per-distance trajectory
    """
    if len(events) < 4:
        return []

    findings: List[FingerprintFindingResult] = []

    by_dist: Dict[str, List[PerformanceEvent]] = {}
    for ev in events:
        by_dist.setdefault(ev.distance_category, []).append(ev)

    rpi_events = sorted(
        [e for e in events if e.rpi_at_event],
        key=lambda e: e.event_date,
    )

    if len(rpi_events) >= 4:
        findings.extend(_detect_pb_chain(rpi_events))
        findings.extend(_detect_improvement_acceleration(rpi_events))
        findings.extend(_detect_disruption_impact(rpi_events))

    for dist_cat, dist_events in by_dist.items():
        if len(dist_events) < 2:
            continue
        sorted_de = sorted(dist_events, key=lambda e: e.event_date)
        findings.extend(_detect_distance_trajectory(sorted_de, dist_cat))

    return findings


def _detect_pb_chain(
    events: List[PerformanceEvent],
) -> List[FingerprintFindingResult]:
    """Detect continuous improvement across races (using RPI)."""
    findings = []

    best_streak = 0
    current_streak = 1
    streak_start = 0
    best_start = 0

    for i in range(1, len(events)):
        if events[i].rpi_at_event > events[i-1].rpi_at_event:
            current_streak += 1
            if current_streak > best_streak:
                best_streak = current_streak
                best_start = streak_start
        else:
            current_streak = 1
            streak_start = i

    if best_streak >= 3:
        streak_events = events[best_start:best_start + best_streak]
        first_date = streak_events[0].event_date
        last_date = streak_events[-1].event_date
        months = max(1, (last_date - first_date).days // 30)

        total_improvement = (
            (streak_events[-1].rpi_at_event - streak_events[0].rpi_at_event)
            / streak_events[0].rpi_at_event * 100
        )

        sentence = (
            f"You improved across {best_streak} consecutive races over {months} months, "
            f"with each race faster than the last."
        )

        finding = FingerprintFindingResult(
            layer=5,
            finding_type='pb_chain',
            sentence=sentence,
            evidence={
                'streak_length': best_streak,
                'months': months,
                'total_improvement_pct': round(total_improvement, 1),
                'first_date': first_date.isoformat(),
                'last_date': last_date.isoformat(),
            },
            statistical_confidence=min(best_streak / 6.0, 1.0),
            effect_size=round(abs(total_improvement) / 10, 2),
            sample_size=len(events),
            confidence_tier='',
            is_significant=False,
        )
        finding.confidence_tier = _assign_confidence_tier(finding, is_comparison_layer=False)
        finding.is_significant = finding.confidence_tier != 'suppressed'
        findings.append(finding)

    return findings


def _detect_improvement_acceleration(
    events: List[PerformanceEvent],
) -> List[FingerprintFindingResult]:
    """Detect when improvement rate increased."""
    if len(events) < 6:
        return []

    findings = []

    rates = []
    for i in range(1, len(events)):
        days = max(1, (events[i].event_date - events[i-1].event_date).days)
        rpi_change = events[i].rpi_at_event - events[i-1].rpi_at_event
        rate_per_month = (rpi_change / events[i-1].rpi_at_event) * (30 / days) * 100
        rates.append({
            'date': events[i].event_date,
            'rate_per_month': rate_per_month,
            'event': events[i],
        })

    if len(rates) < 4:
        return []

    mid = len(rates) // 2
    early_rates = [r['rate_per_month'] for r in rates[:mid]]
    late_rates = [r['rate_per_month'] for r in rates[mid:]]

    early_avg = _mean(early_rates)
    late_avg = _mean(late_rates)

    if late_avg > early_avg * 1.5 and late_avg > 0.5:
        acceleration_date = rates[mid]['date']
        sentence = (
            f"Your improvement rate accelerated after "
            f"{acceleration_date.strftime('%B %Y')}. "
            f"Something changed in your training that made you get faster, faster."
        )

        acceleration_event = rates[mid]['event']
        if acceleration_event.campaign_data:
            campaign_weeks = acceleration_event.campaign_data.get('total_weeks', 0)
            if campaign_weeks > 0:
                sentence = (
                    f"Your improvement rate accelerated after "
                    f"{acceleration_date.strftime('%B %Y')}. "
                    f"The {campaign_weeks}-week campaign that followed produced "
                    f"your steepest gains."
                )

        d = _cohens_d(late_rates, early_rates)

        finding = FingerprintFindingResult(
            layer=5,
            finding_type='improvement_acceleration',
            sentence=sentence,
            evidence={
                'early_rate_pct_per_month': round(early_avg, 2),
                'late_rate_pct_per_month': round(late_avg, 2),
                'acceleration_date': acceleration_date.isoformat(),
                'acceleration_factor': round(late_avg / max(early_avg, 0.01), 1),
            },
            statistical_confidence=min(len(rates) / 8.0, 1.0),
            effect_size=round(abs(d), 2),
            sample_size=len(events),
            confidence_tier='',
            is_significant=False,
        )
        finding.confidence_tier = _assign_confidence_tier(finding, is_comparison_layer=False)
        finding.is_significant = finding.confidence_tier != 'suppressed'
        findings.append(finding)

    return findings


def _detect_disruption_impact(
    events: List[PerformanceEvent],
) -> List[FingerprintFindingResult]:
    """Detect races on residual fitness after disruption."""
    findings = []

    residual_races = [
        e for e in events
        if e.campaign_data and e.campaign_data.get('raced_on_residual_fitness')
        and e.rpi_at_event
    ]

    if not residual_races:
        return []

    best_residual = max(residual_races, key=lambda e: e.rpi_at_event)
    all_rpis = sorted([e.rpi_at_event for e in events if e.rpi_at_event], reverse=True)

    try:
        rank = all_rpis.index(best_residual.rpi_at_event) + 1
    except ValueError:
        rank = len(all_rpis)
    percentile = (1 - rank / len(all_rpis)) * 100

    if percentile >= 50:
        campaign_weeks = best_residual.campaign_data.get('total_weeks', 0)
        sentence = (
            f"Even racing after your training was disrupted, "
            f"you produced one of your top performances. "
            f"The {campaign_weeks}-week campaign built fitness that lasted "
            f"beyond the interruption."
        )

        finding = FingerprintFindingResult(
            layer=5,
            finding_type='disruption_resilience',
            sentence=sentence,
            evidence={
                'residual_race_date': best_residual.event_date.isoformat(),
                'residual_rpi': round(best_residual.rpi_at_event, 1),
                'overall_rank': rank,
                'total_races': len(all_rpis),
                'performance_percentile': round(percentile, 0),
                'campaign_weeks': campaign_weeks,
            },
            statistical_confidence=0.7,
            effect_size=round(percentile / 100, 2),
            sample_size=len(events),
            confidence_tier='',
            is_significant=False,
        )
        finding.confidence_tier = _assign_confidence_tier(finding, is_comparison_layer=False)
        finding.is_significant = finding.confidence_tier != 'suppressed'
        findings.append(finding)

    return findings


def _detect_distance_trajectory(
    events: List[PerformanceEvent],
    dist_cat: str,
) -> List[FingerprintFindingResult]:
    """Detect trajectory at a specific distance.

    Compares first race to fastest race (not just consecutive PBs).
    For 2-race distances, requires a larger improvement to surface.
    """
    findings = []

    first_time = events[0].effective_time_seconds
    fastest = min(events, key=lambda e: e.effective_time_seconds)
    fastest_time = fastest.effective_time_seconds

    if fastest_time >= first_time:
        return findings

    total_improvement = (first_time - fastest_time) / first_time * 100

    # 2-race distances need a bigger improvement to be worth surfacing
    min_improvement = 5.0 if len(events) == 2 else 3.0
    if total_improvement < min_improvement:
        return findings

    # Check for all-PB pattern
    pb_count = 0
    best_so_far = first_time
    all_pb = True
    for i in range(1, len(events)):
        t = events[i].effective_time_seconds
        if t < best_so_far:
            pb_count += 1
            best_so_far = t
        else:
            all_pb = False

    first_str = _format_time(first_time)
    fastest_str = _format_time(fastest_time)
    dist_label = _dist_label(dist_cat)
    months = max(1, (fastest.event_date - events[0].event_date).days // 30)

    time_diff = first_time - fastest_time
    minutes_diff = time_diff // 60
    has_large_absolute_drop = minutes_diff >= 5

    if all_pb and len(events) >= 3:
        sentence = (
            f"Every {dist_label} you've raced has been faster than the last — "
            f"from {first_str} to {fastest_str} over {months} months."
        )
    elif has_large_absolute_drop and minutes_diff >= 60:
        sentence = (
            f"You've taken {minutes_diff // 60} minutes {minutes_diff % 60} seconds "
            f"off your {dist_label} — from {first_str} to {fastest_str} "
            f"over {months} months."
        )
    elif has_large_absolute_drop:
        sentence = (
            f"You've taken {minutes_diff} minutes off your {dist_label} — "
            f"from {first_str} to {fastest_str} over {months} months."
        )
    else:
        sentence = (
            f"You've dropped your {dist_label} from {first_str} to {fastest_str} "
            f"over {months} months — {total_improvement:.0f}% faster."
        )

    finding = FingerprintFindingResult(
        layer=5,
        finding_type=f'trajectory_{dist_cat}',
        sentence=sentence,
        evidence={
            'distance': dist_cat,
            'first_time': first_time,
            'fastest_time': fastest_time,
            'improvement_pct': round(total_improvement, 1),
            'pb_count': pb_count,
            'race_count': len(events),
            'all_pbs': all_pb,
            'months': months,
        },
        statistical_confidence=min(len(events) / 5.0, 1.0),
        effect_size=round(total_improvement / 10, 2),
        sample_size=len(events),
        confidence_tier='',
        is_significant=False,
    )
    finding.confidence_tier = _assign_confidence_tier(finding, is_comparison_layer=False)
    finding.is_significant = finding.confidence_tier != 'suppressed'
    findings.append(finding)

    return findings


def _format_time(seconds: int) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _dist_label(dist_cat: str) -> str:
    """Human-friendly distance name."""
    labels = {
        'mile': 'mile',
        '5k': '5K',
        '10k': '10K',
        'half_marathon': 'half marathon',
        'marathon': 'marathon',
        '50k': '50K',
    }
    return labels.get(dist_cat, dist_cat)
