"""
Tests for Phase 1D: Taper Democratization

Covers:
  1. TaperCalculator signal priority hierarchy
  2. Recovery-to-taper rebound mapping
  3. Phase builder taper_days integration
  4. Observed taper pattern analysis (pre_race_fingerprinting extension)
  5. Edge cases: no data, conflicting signals, boundary values
"""

from __future__ import annotations

import pytest
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from services.taper_calculator import (
    TaperCalculator,
    TaperRecommendation,
    classify_rebound_speed,
)
from services.plan_framework.constants import (
    Distance,
    ReboundSpeed,
    TAPER_DAYS_BY_REBOUND,
    TAPER_DAYS_DEFAULT,
    VolumeTier,
)
from services.plan_framework.phase_builder import PhaseBuilder


# ===================================================================
# Fixtures / helpers
# ===================================================================


@dataclass
class FakeProfile:
    """Minimal AthleteProfile stand-in for taper tests."""
    recovery_half_life_hours: Optional[float] = None
    recovery_confidence: float = 0.0
    volume_tier: VolumeTier = VolumeTier.MID


@dataclass
class FakeObservedTaper:
    """Minimal ObservedTaperPattern stand-in."""
    taper_days: int = 12
    confidence: float = 0.6
    rationale: str = "Based on 3 best races."


@dataclass
class FakeBanisterModel:
    """Minimal BanisterModel stand-in."""
    confidence: "FakeConfidence" = None
    tau1: float = 42.0
    tau2: float = 7.0

    def calculate_optimal_taper_days(self) -> int:
        """Simplified — just use 2 × τ2 clamped."""
        return max(7, min(21, int(2 * self.tau2)))

    def get_taper_rationale(self) -> str:
        return f"Model: τ1={self.tau1}, τ2={self.tau2}"


class FakeConfidence:
    def __init__(self, val: str):
        self.value = val


# ===================================================================
# GROUP 1: Signal Priority Hierarchy
# ===================================================================


class TestSignalPriority:
    """Verify the correct signal is chosen at each priority level."""

    def test_priority_1_observed_taper_wins(self):
        """When all signals available, observed taper history wins."""
        calc = TaperCalculator()
        rec = calc.calculate(
            distance="marathon",
            profile=FakeProfile(recovery_half_life_hours=40, recovery_confidence=0.8),
            banister_model=FakeBanisterModel(confidence=FakeConfidence("high")),
            observed_taper=FakeObservedTaper(taper_days=11, confidence=0.7),
        )
        assert rec.source == "race_history"
        assert rec.taper_days == 11

    def test_priority_2_recovery_rebound_when_no_race_history(self):
        """Recovery rebound is used when no observed taper history."""
        calc = TaperCalculator()
        rec = calc.calculate(
            distance="marathon",
            profile=FakeProfile(recovery_half_life_hours=40, recovery_confidence=0.8),
            banister_model=FakeBanisterModel(confidence=FakeConfidence("high")),
            observed_taper=None,
        )
        assert rec.source == "recovery_rebound"

    def test_priority_3_banister_when_no_profile(self):
        """Banister model is used when no profile or race history."""
        calc = TaperCalculator()
        rec = calc.calculate(
            distance="marathon",
            profile=None,
            banister_model=FakeBanisterModel(confidence=FakeConfidence("moderate")),
            observed_taper=None,
        )
        assert rec.source == "banister"

    def test_priority_4_default_when_nothing(self):
        """Falls to population default when no signals."""
        calc = TaperCalculator()
        rec = calc.calculate(
            distance="marathon",
            profile=None,
            banister_model=None,
            observed_taper=None,
        )
        assert rec.source == "default"
        assert rec.taper_days == 14  # Marathon default

    def test_priority_2_skipped_when_low_confidence(self):
        """Recovery rebound skipped when confidence < 0.4."""
        calc = TaperCalculator()
        rec = calc.calculate(
            distance="marathon",
            profile=FakeProfile(recovery_half_life_hours=40, recovery_confidence=0.3),
            banister_model=None,
            observed_taper=None,
        )
        assert rec.source == "default"

    def test_priority_3_skipped_when_uncalibrated(self):
        """Banister skipped when model is uncalibrated."""
        calc = TaperCalculator()
        rec = calc.calculate(
            distance="marathon",
            profile=None,
            banister_model=FakeBanisterModel(confidence=FakeConfidence("uncalibrated")),
            observed_taper=None,
        )
        assert rec.source == "default"

    def test_priority_1_skipped_when_low_confidence(self):
        """Observed taper skipped when confidence < 0.3."""
        calc = TaperCalculator()
        rec = calc.calculate(
            distance="marathon",
            profile=FakeProfile(recovery_half_life_hours=40, recovery_confidence=0.8),
            observed_taper=FakeObservedTaper(taper_days=10, confidence=0.2),
        )
        assert rec.source == "recovery_rebound"  # Falls to P2

    def test_priority_3_banister_produces_correct_days(self):
        """When Banister fires, its taper_days flow through correctly."""
        calc = TaperCalculator()
        # FakeBanisterModel with tau2=7 → calculate_optimal_taper_days() = 2*7 = 14
        rec = calc.calculate(
            distance="marathon",
            profile=None,
            banister_model=FakeBanisterModel(
                confidence=FakeConfidence("high"), tau1=42.0, tau2=7.0
            ),
            observed_taper=None,
        )
        assert rec.source == "banister"
        assert rec.taper_days == 14


# ===================================================================
# GROUP 2: Recovery Rebound Mapping
# ===================================================================


class TestRecoveryReboundMapping:
    """Verify the direct observable → prescription mapping."""

    def test_classify_fast(self):
        assert classify_rebound_speed(30) == ReboundSpeed.FAST
        assert classify_rebound_speed(36) == ReboundSpeed.FAST

    def test_classify_normal(self):
        assert classify_rebound_speed(37) == ReboundSpeed.NORMAL
        assert classify_rebound_speed(60) == ReboundSpeed.NORMAL

    def test_classify_slow(self):
        assert classify_rebound_speed(61) == ReboundSpeed.SLOW
        assert classify_rebound_speed(80) == ReboundSpeed.SLOW

    @pytest.mark.parametrize("half_life,distance,expected_days", [
        (30, "marathon", 10),
        (30, "half_marathon", 7),
        (30, "10k", 5),
        (30, "5k", 4),
        (45, "marathon", 13),
        (45, "half_marathon", 9),
        (45, "10k", 7),
        (45, "5k", 5),
        (70, "marathon", 17),
        (70, "half_marathon", 12),
        (70, "10k", 9),
        (70, "5k", 7),
    ])
    def test_rebound_to_taper_mapping(self, half_life, distance, expected_days):
        """Each (rebound, distance) pair maps to the correct taper days."""
        calc = TaperCalculator()
        profile = FakeProfile(
            recovery_half_life_hours=half_life,
            recovery_confidence=0.8,
        )
        rec = calc.calculate(distance=distance, profile=profile)
        assert rec.source == "recovery_rebound"
        assert rec.taper_days == expected_days

    def test_fast_recoverer_gets_shorter_taper(self):
        """Fast recoverer should get shortest taper for each distance."""
        calc = TaperCalculator()
        fast = FakeProfile(recovery_half_life_hours=30, recovery_confidence=0.8)
        slow = FakeProfile(recovery_half_life_hours=70, recovery_confidence=0.8)
        for dist in ["marathon", "half_marathon", "10k", "5k"]:
            fast_rec = calc.calculate(distance=dist, profile=fast)
            slow_rec = calc.calculate(distance=dist, profile=slow)
            assert fast_rec.taper_days < slow_rec.taper_days, (
                f"Fast recoverer should get shorter taper for {dist}"
            )

    def test_longer_race_gets_longer_taper(self):
        """Marathon taper > half taper > 10K taper > 5K taper for same athlete."""
        calc = TaperCalculator()
        profile = FakeProfile(recovery_half_life_hours=45, recovery_confidence=0.8)
        days = {}
        for dist in ["marathon", "half_marathon", "10k", "5k"]:
            rec = calc.calculate(distance=dist, profile=profile)
            days[dist] = rec.taper_days
        assert days["marathon"] > days["half_marathon"]
        assert days["half_marathon"] > days["10k"]
        assert days["10k"] >= days["5k"]


# ===================================================================
# GROUP 3: Defaults
# ===================================================================


class TestDefaults:
    """Population defaults when no personalized signal is available."""

    @pytest.mark.parametrize("distance,expected", [
        ("marathon", 14),
        ("half_marathon", 10),
        ("10k", 7),
        ("5k", 5),
    ])
    def test_default_taper_days(self, distance, expected):
        calc = TaperCalculator()
        rec = calc.calculate(distance=distance)
        assert rec.source == "default"
        assert rec.taper_days == expected
        assert rec.confidence == 0.2  # Low confidence for defaults

    def test_default_disclosure_is_honest(self):
        calc = TaperCalculator()
        rec = calc.calculate(distance="marathon")
        assert "template" in rec.disclosure.lower() or "standard" in rec.disclosure.lower()


# ===================================================================
# GROUP 4: Phase Builder Integration
# ===================================================================


class TestPhaseBuilderTaperDays:
    """Verify phase builder correctly converts taper_days to structure."""

    def test_taper_days_to_weeks_mapping(self):
        pb = PhaseBuilder()
        assert pb._taper_days_to_weeks(5) == 1
        assert pb._taper_days_to_weeks(7) == 1
        assert pb._taper_days_to_weeks(8) == 2
        assert pb._taper_days_to_weeks(10) == 2
        assert pb._taper_days_to_weeks(14) == 2
        assert pb._taper_days_to_weeks(15) == 3
        assert pb._taper_days_to_weeks(21) == 3

    def test_build_phases_with_taper_days_marathon(self):
        pb = PhaseBuilder()
        phases = pb.build_phases(
            distance="marathon", duration_weeks=18, tier="mid", taper_days=17
        )
        # 17 days → 3 taper weeks → should have "Early Taper" + "Taper" + "Race Week"
        taper_phases = [p for p in phases if p.phase_type.value == "taper"]
        race_phases = [p for p in phases if p.phase_type.value == "race"]
        assert len(taper_phases) >= 2, "Should have early taper + main taper"
        assert len(race_phases) == 1
        # Progressive: early taper volume_modifier > main taper volume_modifier
        assert taper_phases[0].volume_modifier >= taper_phases[1].volume_modifier

    def test_build_phases_with_short_taper(self):
        pb = PhaseBuilder()
        phases = pb.build_phases(
            distance="5k", duration_weeks=8, tier="mid", taper_days=5
        )
        # 5 days → 1 taper week → just taper + race week
        taper_phases = [p for p in phases if p.phase_type.value == "taper"]
        race_phases = [p for p in phases if p.phase_type.value == "race"]
        assert len(race_phases) == 1

    def test_build_phases_backward_compatible(self):
        """Without taper_days, uses legacy TAPER_WEEKS."""
        pb = PhaseBuilder()
        phases_default = pb.build_phases(
            distance="marathon", duration_weeks=18, tier="mid"
        )
        # Should work exactly as before
        assert any(p.phase_type.value == "taper" for p in phases_default)
        assert any(p.phase_type.value == "race" for p in phases_default)

    def test_progressive_taper_volume_modifiers(self):
        """3-week taper should have 70% → 50% → 30% (race week)."""
        pb = PhaseBuilder()
        phases = pb.build_phases(
            distance="marathon", duration_weeks=18, tier="mid", taper_days=17
        )
        taper_phases = [p for p in phases if p.phase_type.value == "taper"]
        race_phase = [p for p in phases if p.phase_type.value == "race"][0]

        # Early taper should be 70%, main taper 50%, race 30%
        if len(taper_phases) >= 2:
            assert taper_phases[0].volume_modifier == pytest.approx(0.70, abs=0.05)
            assert taper_phases[1].volume_modifier == pytest.approx(0.50, abs=0.05)
        assert race_phase.volume_modifier == pytest.approx(0.30, abs=0.05)


# ===================================================================
# GROUP 5: Observed Taper Pattern Analysis
# ===================================================================


class TestObservedTaperPattern:
    """Test derive_pre_race_taper_pattern from pre_race_fingerprinting."""

    @staticmethod
    def _make_activity(d: date, miles: float, sport: str = "run", **kwargs):
        """Create a minimal fake activity."""

        class FakeAct:
            pass

        a = FakeAct()
        a.start_time = datetime(d.year, d.month, d.day)
        a.distance_m = miles * 1609.344
        a.sport = sport
        for k, v in kwargs.items():
            setattr(a, k, v)
        return a

    @staticmethod
    def _make_race(d: date, miles: float, perf_pct: float):
        """Create a fake race activity with performance percentage."""

        class FakeRace:
            pass

        r = FakeRace()
        r.start_time = datetime(d.year, d.month, d.day)
        r.distance_m = miles * 1609.344
        r.sport = "run"
        r.performance_percentage = perf_pct
        r.performance_percentage_national = None
        return r

    def test_returns_none_with_insufficient_races(self):
        from services.pre_race_fingerprinting import derive_pre_race_taper_pattern

        acts = [self._make_activity(date(2025, 6, 1), 5)]
        races = [self._make_race(date(2025, 7, 1), 26.2, 72.0)]
        result = derive_pre_race_taper_pattern(acts, races, min_races=2)
        assert result is None

    def test_detects_taper_pattern_from_two_races(self):
        from services.pre_race_fingerprinting import derive_pre_race_taper_pattern

        # Build 8 weeks of training at ~50 mpw, then taper to ~25 mpw
        # for 10 days before two races.
        activities = []
        base_date = date(2025, 1, 1)

        # 8 weeks of 50mpw training
        for week in range(8):
            for day in range(6):
                d = base_date + timedelta(days=week * 7 + day)
                activities.append(self._make_activity(d, 8.0))

        # Race 1: March 1 — taper for 10 days before
        race1_date = date(2025, 3, 1)
        # 10 days before race1: reduced volume
        for offset in range(10, 0, -1):
            d = race1_date - timedelta(days=offset)
            activities.append(self._make_activity(d, 4.0))  # Half volume

        # More training between races
        for day in range(30):
            d = race1_date + timedelta(days=7 + day)
            activities.append(self._make_activity(d, 8.0))

        # Race 2: May 1 — similar taper
        race2_date = date(2025, 5, 1)
        for offset in range(12, 0, -1):
            d = race2_date - timedelta(days=offset)
            activities.append(self._make_activity(d, 4.0))

        race1 = self._make_race(race1_date, 26.2, 78.0)
        race2 = self._make_race(race2_date, 26.2, 75.0)

        result = derive_pre_race_taper_pattern(
            activities, [race1, race2], min_races=2
        )
        assert result is not None
        assert result.n_races_analyzed >= 2
        assert result.confidence >= 0.3
        assert 3 <= result.taper_days <= 21

    def test_returns_none_when_no_performance_pct(self):
        from services.pre_race_fingerprinting import derive_pre_race_taper_pattern

        class NoPerf:
            start_time = datetime(2025, 6, 1)
            distance_m = 42195
            sport = "run"
            performance_percentage = None
            performance_percentage_national = None

        acts = [self._make_activity(date(2025, 5, 15), 8)]
        result = derive_pre_race_taper_pattern(acts, [NoPerf(), NoPerf()], min_races=2)
        assert result is None


# ===================================================================
# GROUP 6: Edge Cases
# ===================================================================


class TestEdgeCases:

    def test_invalid_distance_falls_to_marathon(self):
        calc = TaperCalculator()
        rec = calc.calculate(distance="ultra_marathon")
        assert rec.source == "default"
        assert rec.taper_days == 14  # Marathon default

    def test_taper_days_clamped_to_range(self):
        """Observed taper with extreme values should be clamped."""
        calc = TaperCalculator()
        rec = calc.calculate(
            distance="marathon",
            observed_taper=FakeObservedTaper(taper_days=30, confidence=0.8),
        )
        assert rec.taper_days <= 21

    def test_taper_days_minimum_clamped(self):
        calc = TaperCalculator()
        rec = calc.calculate(
            distance="5k",
            observed_taper=FakeObservedTaper(taper_days=1, confidence=0.8),
        )
        assert rec.taper_days >= 3

    def test_recommendation_has_required_fields(self):
        calc = TaperCalculator()
        rec = calc.calculate(distance="marathon")
        assert isinstance(rec.taper_days, int)
        assert isinstance(rec.source, str)
        assert isinstance(rec.confidence, float)
        assert isinstance(rec.rationale, str)
        assert isinstance(rec.disclosure, str)
        assert 0.0 <= rec.confidence <= 1.0

    def test_all_rebound_distance_combinations_have_entries(self):
        """Every (ReboundSpeed, Distance) pair must exist in the lookup."""
        for speed in ReboundSpeed:
            for dist in Distance:
                assert (speed, dist) in TAPER_DAYS_BY_REBOUND, (
                    f"Missing entry for ({speed.value}, {dist.value})"
                )

    def test_banister_low_confidence_skipped(self):
        """Banister with 'low' confidence should not be used."""
        calc = TaperCalculator()
        rec = calc.calculate(
            distance="marathon",
            banister_model=FakeBanisterModel(confidence=FakeConfidence("low")),
        )
        assert rec.source == "default"


# ===================================================================
# GROUP 7: TaperRecommendation content quality
# ===================================================================


class TestRecommendationContent:

    def test_disclosure_mentions_data_source(self):
        calc = TaperCalculator()
        # Recovery rebound
        rec = calc.calculate(
            distance="marathon",
            profile=FakeProfile(recovery_half_life_hours=45, recovery_confidence=0.8),
        )
        assert "recovery" in rec.disclosure.lower() or "bounce" in rec.disclosure.lower()

    def test_rationale_includes_days(self):
        calc = TaperCalculator()
        rec = calc.calculate(
            distance="marathon",
            profile=FakeProfile(recovery_half_life_hours=45, recovery_confidence=0.8),
        )
        assert str(rec.taper_days) in rec.rationale

    def test_default_rationale_mentions_personalization(self):
        calc = TaperCalculator()
        rec = calc.calculate(distance="half_marathon")
        assert "personalized" in rec.rationale.lower() or "standard" in rec.rationale.lower()
