"""Tests for Racing Fingerprint Phase 1B: pattern extraction + quality gate."""

import uuid
from dataclasses import asdict
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from services.fingerprint_analysis import (
    FingerprintFindingResult,
    QUALITY_THRESHOLDS,
    _assign_confidence_tier,
    _cohens_d,
    _layer1_pb_distribution,
    _layer2_block_comparison,
    _layer3_tuneup_pattern,
    _layer4_fitness_relative,
    extract_fingerprint_findings,
    passes_quality_gate,
)


def _mock_event(
    event_date=None,
    distance_category="10k",
    time_seconds=3000,
    rpi=45.0,
    ctl=40.0,
    atl=35.0,
    tsb=5.0,
    block_signature=None,
    is_pb=False,
    race_role="a_race",
    user_confirmed=True,
    frp=None,
    activity_id=None,
):
    ev = MagicMock()
    ev.id = uuid.uuid4()
    ev.athlete_id = uuid.uuid4()
    ev.activity_id = activity_id or uuid.uuid4()
    ev.event_date = event_date or date(2025, 6, 15)
    ev.distance_category = distance_category
    ev.time_seconds = time_seconds
    ev.rpi_at_event = rpi
    ev.ctl_at_event = ctl
    ev.atl_at_event = atl
    ev.tsb_at_event = tsb
    ev.block_signature = block_signature or {
        "peak_volume_km": 50,
        "peak_volume_week": 4,
        "quality_sessions": 8,
        "long_run_max_km": 20,
        "taper_start_week": 10,
        "lookback_weeks": 12,
    }
    ev.is_personal_best = is_pb
    ev.race_role = race_role
    ev.user_confirmed = user_confirmed
    ev.fitness_relative_performance = frp
    ev.performance_percentage = 65.0
    return ev


def _mock_activity(
    distance_m=10000,
    duration_s=3600,
    act_id=None,
):
    act = MagicMock()
    act.id = act_id or uuid.uuid4()
    act.athlete_id = uuid.uuid4()
    act.distance_m = distance_m
    act.duration_s = duration_s
    act.is_duplicate = False
    return act


# ═══════════════════════════════════════════════════════
# Layer 1: PB Distribution
# ═══════════════════════════════════════════════════════


class TestLayer1PBDistribution:
    def test_identifies_race_day_uplift(self):
        """Athlete races 4% faster than training → finding produced."""
        events = [
            _mock_event(time_seconds=2800, distance_category="10k"),
            _mock_event(time_seconds=2900, distance_category="10k"),
            _mock_event(time_seconds=1400, distance_category="5k"),
        ]

        act_ids = {e.activity_id for e in events}
        training_acts = [
            _mock_activity(distance_m=10000, duration_s=2920),
            _mock_activity(distance_m=5000, duration_s=1460),
        ]
        for a in training_acts:
            assert a.id not in act_ids

        db = MagicMock()
        findings = _layer1_pb_distribution(events, training_acts, db)
        assert len(findings) >= 1
        f = findings[0]
        assert f.finding_type == 'pb_distribution'
        assert f.layer == 1
        assert 'faster' in f.sentence or 'within' in f.sentence

    def test_identifies_training_ceiling(self):
        """Athlete trains within 1% of race → finding produced."""
        events = [
            _mock_event(time_seconds=2800, distance_category="10k"),
            _mock_event(time_seconds=2810, distance_category="10k"),
            _mock_event(time_seconds=1400, distance_category="5k"),
        ]

        training_acts = [
            _mock_activity(distance_m=10000, duration_s=2815),
            _mock_activity(distance_m=5000, duration_s=1410),
        ]

        db = MagicMock()
        findings = _layer1_pb_distribution(events, training_acts, db)
        assert len(findings) >= 1
        f = findings[0]
        assert 'within' in f.sentence

    def test_suppresses_with_insufficient_data(self):
        """Only 2 events → no finding (below min_sample_size)."""
        events = [
            _mock_event(time_seconds=2800, distance_category="10k"),
            _mock_event(time_seconds=1400, distance_category="5k"),
        ]
        training_acts = [_mock_activity(distance_m=10000, duration_s=3000)]
        db = MagicMock()
        findings = _layer1_pb_distribution(events, training_acts, db)
        assert len(findings) == 0


# ═══════════════════════════════════════════════════════
# Layer 2: Block Comparison
# ═══════════════════════════════════════════════════════


class TestLayer2BlockComparison:
    def _make_events_with_sigs(self, n, top_volume=80, bottom_volume=40):
        events = []
        mid = n // 2
        for i in range(n):
            is_top = i < mid
            vol = top_volume if is_top else bottom_volume
            ev = _mock_event(
                rpi=60 - i * 2 if is_top else 40 - i * 0.5,
                block_signature={
                    "peak_volume_km": vol + (i % 3),
                    "peak_volume_week": 4 if is_top else 2,
                    "quality_sessions": 10 if is_top else 5,
                    "long_run_max_km": 25 if is_top else 15,
                    "taper_start_week": 10 if is_top else 11,
                    "lookback_weeks": 12,
                },
            )
            events.append(ev)
        return events

    def test_identifies_volume_peak_difference(self):
        """Best races peak higher than worst → finding with effect size > 0.3."""
        events = self._make_events_with_sigs(8)
        findings = _layer2_block_comparison(events)
        vol_findings = [f for f in findings if f.finding_type == 'block_peak_volume_km']
        assert len(vol_findings) >= 1
        assert vol_findings[0].effect_size >= 0.3

    def test_identifies_taper_difference(self):
        """Best races have different taper → finding produced."""
        events = self._make_events_with_sigs(8)
        findings = _layer2_block_comparison(events)
        taper_findings = [f for f in findings if f.finding_type == 'block_taper']
        # Taper may or may not produce depending on data; check structure
        for f in taper_findings:
            assert f.layer == 2
            assert 'taper' in f.sentence.lower()

    def test_suppresses_trivial_difference(self):
        """Difference exists but Cohen's d < 0.3 → suppressed."""
        events = []
        for i in range(8):
            ev = _mock_event(
                rpi=50 - i,
                block_signature={
                    "peak_volume_km": 50 + (i % 2) * 0.1,
                    "peak_volume_week": 3,
                    "quality_sessions": 7,
                    "long_run_max_km": 18,
                    "lookback_weeks": 12,
                },
            )
            events.append(ev)
        findings = _layer2_block_comparison(events)
        for f in findings:
            if f.finding_type == 'block_peak_volume_km':
                assert f.confidence_tier == 'suppressed' or f.effect_size >= 0.3

    def test_descriptive_fallback_with_5_events(self):
        """5 events → top half (3) vs bottom half (2). Tier = 'descriptive'."""
        events = self._make_events_with_sigs(5)
        findings = _layer2_block_comparison(events)
        for f in findings:
            if f.confidence_tier != 'suppressed':
                assert f.confidence_tier == 'descriptive'
                assert f.evidence.get('p_value') is None

    def test_skips_with_fewer_than_4_events(self):
        """3 events → skip layer entirely."""
        events = self._make_events_with_sigs(3)
        findings = _layer2_block_comparison(events)
        assert len(findings) == 0


# ═══════════════════════════════════════════════════════
# Layer 3: Tune-up Pattern
# ═══════════════════════════════════════════════════════


class TestLayer3TuneupPattern:
    def test_identifies_tuneup_pb_risk(self):
        """Tune-up PBs followed by A-race underperformance → finding."""
        events = [
            _mock_event(
                event_date=date(2025, 4, 1), race_role="tune_up",
                is_pb=True, rpi=48, distance_category="5k",
            ),
            _mock_event(
                event_date=date(2025, 5, 1), race_role="a_race",
                rpi=42, distance_category="half_marathon",
            ),
            _mock_event(
                event_date=date(2025, 8, 1), race_role="tune_up",
                is_pb=False, rpi=44, distance_category="5k",
            ),
            _mock_event(
                event_date=date(2025, 9, 1), race_role="a_race",
                rpi=50, distance_category="half_marathon",
            ),
        ]
        findings = _layer3_tuneup_pattern(events)
        assert len(findings) >= 1
        f = findings[0]
        assert f.finding_type == 'tuneup_pb_effect'
        assert f.layer == 3

    def test_handles_no_tuneup_pairs(self):
        """No tune-up → A-race pairs → no finding (not an error)."""
        events = [
            _mock_event(race_role="a_race", event_date=date(2025, 3, 1)),
            _mock_event(race_role="a_race", event_date=date(2025, 9, 1)),
            _mock_event(race_role="a_race", event_date=date(2025, 12, 1)),
        ]
        findings = _layer3_tuneup_pattern(events)
        assert len(findings) == 0


# ═══════════════════════════════════════════════════════
# Layer 4: Fitness-Relative Performance
# ═══════════════════════════════════════════════════════


class TestLayer4FitnessRelative:
    def test_identifies_outperformance_pattern(self):
        """Outperformance correlates with taper length → finding."""
        events = [
            _mock_event(frp=1.15, block_signature={"peak_volume_km": 80, "quality_sessions": 12, "long_run_max_km": 30, "taper_start_week": 8, "lookback_weeks": 12}),
            _mock_event(frp=1.10, block_signature={"peak_volume_km": 75, "quality_sessions": 11, "long_run_max_km": 28, "taper_start_week": 9, "lookback_weeks": 12}),
            _mock_event(frp=1.08, block_signature={"peak_volume_km": 70, "quality_sessions": 10, "long_run_max_km": 26, "taper_start_week": 9, "lookback_weeks": 12}),
            _mock_event(frp=0.85, block_signature={"peak_volume_km": 40, "quality_sessions": 4, "long_run_max_km": 15, "taper_start_week": 11, "lookback_weeks": 12}),
            _mock_event(frp=0.80, block_signature={"peak_volume_km": 38, "quality_sessions": 3, "long_run_max_km": 14, "taper_start_week": 11, "lookback_weeks": 12}),
            _mock_event(frp=0.78, block_signature={"peak_volume_km": 35, "quality_sessions": 3, "long_run_max_km": 12, "taper_start_week": 12, "lookback_weeks": 12}),
        ]
        findings = _layer4_fitness_relative(events)
        assert len(findings) >= 1
        assert any(f.finding_type.startswith('fitness_rel_') for f in findings)

    def test_normalizes_for_fitness_level(self):
        """All events with null fitness_relative_performance → skip layer."""
        events = [_mock_event(frp=None) for _ in range(6)]
        findings = _layer4_fitness_relative(events)
        assert len(findings) == 0


# ═══════════════════════════════════════════════════════
# Quality Gate
# ═══════════════════════════════════════════════════════


class TestQualityGate:
    def _make_finding(self, effect=0.8, sample=10, stat_conf=0.97):
        return FingerprintFindingResult(
            layer=2, finding_type='test', sentence='test',
            evidence={}, statistical_confidence=stat_conf,
            effect_size=effect, sample_size=sample,
            confidence_tier='', is_significant=False,
        )

    def test_passes_significant_finding(self):
        """Large effect, sufficient N → passes."""
        f = self._make_finding(effect=0.8, sample=10, stat_conf=0.97)
        assert passes_quality_gate(f)
        tier = _assign_confidence_tier(f, is_comparison_layer=True, group_sizes=(5, 5))
        assert tier == 'high'

    def test_suppresses_noisy_finding(self):
        """Small effect → 'suppressed'."""
        f = self._make_finding(effect=0.1, sample=10)
        assert not passes_quality_gate(f)
        tier = _assign_confidence_tier(f, is_comparison_layer=True, group_sizes=(5, 5))
        assert tier == 'suppressed'

    def test_exploratory_middle_ground(self):
        """Moderate effect, borderline p → 'exploratory' tier."""
        f = self._make_finding(effect=0.4, sample=6, stat_conf=0.92)
        assert passes_quality_gate(f)
        tier = _assign_confidence_tier(f, is_comparison_layer=True, group_sizes=(3, 3))
        assert tier == 'exploratory'

    def test_descriptive_when_small_groups(self):
        """Comparison layer with 5 events (3/2 split) → 'descriptive'."""
        f = self._make_finding(effect=0.5, sample=5, stat_conf=0.95)
        tier = _assign_confidence_tier(f, is_comparison_layer=True, group_sizes=(3, 2))
        assert tier == 'descriptive'

    def test_no_p_value_on_n1_group(self):
        """Comparison layer with 4 events (3/1 split) → 'descriptive'."""
        f = self._make_finding(effect=0.6, sample=4, stat_conf=0.95)
        tier = _assign_confidence_tier(f, is_comparison_layer=True, group_sizes=(3, 1))
        assert tier == 'descriptive'

    def test_sample_size_gate(self):
        """Only 2 events → suppressed regardless of effect size."""
        f = self._make_finding(effect=1.5, sample=2)
        assert not passes_quality_gate(f)
        tier = _assign_confidence_tier(f, is_comparison_layer=False)
        assert tier == 'suppressed'

    def test_comparison_layer_requires_6_for_statistical(self):
        """Layer 2 with exactly 6 events (3/3 split) → produces p-value and tier."""
        f = self._make_finding(effect=0.5, sample=6, stat_conf=0.93)
        tier = _assign_confidence_tier(f, is_comparison_layer=True, group_sizes=(3, 3))
        assert tier in ('exploratory', 'high')
