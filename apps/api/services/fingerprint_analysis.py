"""
Fingerprint Analysis — Racing Fingerprint Phase 1B

Four-layer pattern extraction across confirmed PerformanceEvents.
Each layer answers a different question about an athlete's racing history.
Every finding produces a sentence. The sentence is the product.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import Activity, PerformanceEvent, StoredFingerprintFinding

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
    db.query(StoredFingerprintFinding).filter(
        StoredFingerprintFinding.athlete_id == athlete_id
    ).delete()

    stored = 0
    for f in findings:
        if f.confidence_tier == 'suppressed':
            continue
        sf = StoredFingerprintFinding(
            athlete_id=athlete_id,
            layer=f.layer,
            finding_type=f.finding_type,
            sentence=f.sentence,
            evidence=f.evidence,
            statistical_confidence=f.statistical_confidence,
            effect_size=f.effect_size,
            sample_size=f.sample_size,
            confidence_tier=f.confidence_tier,
        )
        db.add(sf)
        stored += 1

    return stored


def passes_quality_gate(finding: FingerprintFindingResult) -> bool:
    """Returns True if the finding clears the automated quality gate."""
    if finding.sample_size < QUALITY_THRESHOLDS['min_sample_size']:
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
# Layer 2: Block Signature Comparison
# ═══════════════════════════════════════════════════════

def _layer2_block_comparison(
    events: List[PerformanceEvent],
    units: str = "imperial",
) -> List[FingerprintFindingResult]:
    """What training patterns preceded the best races?"""
    events_with_sigs = [e for e in events if e.block_signature and e.rpi_at_event]
    if len(events_with_sigs) < 4:
        return []

    sorted_events = sorted(events_with_sigs, key=lambda e: e.rpi_at_event, reverse=True)
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
            sample_size=len(events_with_sigs),
            confidence_tier='',
            is_significant=False,
        )
        finding.confidence_tier = _assign_confidence_tier(
            finding, is_comparison_layer=True, group_sizes=group_sizes
        )
        finding.is_significant = finding.confidence_tier != 'suppressed'
        findings.append(finding)

    # Taper comparison
    top_tapers = [
        e.block_signature.get('taper_start_week') for e in top_group
        if e.block_signature.get('taper_start_week') is not None
    ]
    bottom_tapers = [
        e.block_signature.get('taper_start_week') for e in bottom_group
        if e.block_signature.get('taper_start_week') is not None
    ]

    if top_tapers and bottom_tapers:
        top_taper_weeks = [
            e.block_signature.get('lookback_weeks', 12) - t
            for e, t in zip(top_group, top_tapers) if t is not None
        ]
        bottom_taper_weeks = [
            e.block_signature.get('lookback_weeks', 12) - t
            for e, t in zip(bottom_group, bottom_tapers) if t is not None
        ]

        if top_taper_weeks and bottom_taper_weeks:
            d = _cohens_d(top_taper_weeks, bottom_taper_weeks)
            p_value = _mann_whitney_u(top_taper_weeks, bottom_taper_weeks) if can_stat_test else None
            stat_conf = (1 - p_value) if p_value is not None else 0.5

            top_mean = _mean(top_taper_weeks)
            bottom_mean = _mean(bottom_taper_weeks)

            if abs(top_mean - bottom_mean) >= 0.5:
                sentence = (
                    f"Your best races had a taper starting {top_mean:.0f} weeks out "
                    f"vs {bottom_mean:.0f} weeks for weaker races."
                )

                finding = FingerprintFindingResult(
                    layer=2,
                    finding_type='block_taper',
                    sentence=sentence,
                    evidence={
                        'dimension': 'taper_weeks_before_race',
                        'top_mean': round(top_mean, 1),
                        'bottom_mean': round(bottom_mean, 1),
                        'p_value': round(p_value, 4) if p_value is not None else None,
                        'n_top': len(top_taper_weeks),
                        'n_bottom': len(bottom_taper_weeks),
                    },
                    statistical_confidence=round(stat_conf, 3),
                    effect_size=round(abs(d), 2),
                    sample_size=len(events_with_sigs),
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

    KM_TO_MI = 0.621371
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
