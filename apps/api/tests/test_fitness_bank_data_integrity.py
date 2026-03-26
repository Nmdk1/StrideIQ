"""
Tests for fitness bank data integrity fixes:
1. require_trusted_duplicate_flags=True (no fallback dedupe)
2. _find_best_race: peak RPI selection, no recency decay
3. Quality sessions penalty skip within 35 days of marathon

These three fixes ensure the fitness bank returns correct values before
plan generation consumes them.
"""

import inspect
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from services.fitness_bank import (
    ConstraintType,
    ExperienceLevel,
    FitnessBank,
    FitnessBankCalculator,
    RacePerformance,
)
from services.constraint_aware_planner import ConstraintAwarePlanner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_race(
    *,
    days_ago: int = 30,
    distance: str = "10k",
    distance_m: float = 10000,
    finish_time_seconds: int = 2400,
    rpi: float = 50.0,
    confidence: float = 1.0,
    conditions: str = None,
    name: str = None,
) -> RacePerformance:
    return RacePerformance(
        date=date.today() - timedelta(days=days_ago),
        distance=distance,
        distance_m=distance_m,
        finish_time_seconds=finish_time_seconds,
        pace_per_mile=finish_time_seconds / 60.0 / (distance_m / 1609.344),
        rpi=rpi,
        confidence=confidence,
        conditions=conditions,
        name=name,
    )


def _make_bank(
    *,
    races: list = None,
    best_rpi: float = 50.0,
    current_weekly_miles: float = 50.0,
    peak_weekly_miles: float = 65.0,
    constraint_type: ConstraintType = ConstraintType.NONE,
    experience: ExperienceLevel = ExperienceLevel.EXPERIENCED,
    quality_sessions_28d: int = 4,
) -> FitnessBank:
    best_race = races[0] if races else None
    return FitnessBank(
        athlete_id="test-data-integrity",
        peak_weekly_miles=peak_weekly_miles,
        peak_monthly_miles=peak_weekly_miles * 4,
        peak_long_run_miles=18.0,
        peak_mp_long_run_miles=10.0,
        peak_threshold_miles=7.0,
        peak_ctl=80.0,
        race_performances=races or [],
        best_rpi=best_rpi,
        best_race=best_race,
        current_weekly_miles=current_weekly_miles,
        current_ctl=60.0,
        current_atl=50.0,
        weeks_since_peak=4,
        current_long_run_miles=13.0,
        average_long_run_miles=14.0,
        tau1=35.0,
        tau2=7.0,
        experience_level=experience,
        constraint_type=constraint_type,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=0,
        weeks_to_race_ready=0,
        sustainable_peak_weekly=peak_weekly_miles * 0.92,
        recent_quality_sessions_28d=quality_sessions_28d,
    )


# =============================================================================
# FIX 1: require_trusted_duplicate_flags=True
# =============================================================================

class TestTrustedDuplicateFlags:

    def test_fitness_bank_calculator_uses_trusted_flags(self):
        """FitnessBankCalculator.calculate must pass require_trusted_duplicate_flags=True."""
        source = inspect.getsource(FitnessBankCalculator.calculate)
        assert "require_trusted_duplicate_flags=True" in source

    def test_fitness_bank_calculator_does_not_use_fallback_dedupe(self):
        """The old fallback (require_trusted_duplicate_flags=False) must not appear."""
        source = inspect.getsource(FitnessBankCalculator.calculate)
        assert "require_trusted_duplicate_flags=False" not in source


# =============================================================================
# FIX 2: _find_best_race — peak RPI, no recency decay
# =============================================================================

class TestFindBestRace:

    def _calc(self):
        return FitnessBankCalculator(MagicMock())

    def test_empty_races_returns_default(self):
        rpi, race = self._calc()._find_best_race([])
        assert rpi == 45.0
        assert race is None

    def test_single_valid_race(self):
        race = _make_race(days_ago=60, rpi=53.0)
        rpi, best = self._calc()._find_best_race([race])
        assert rpi == pytest.approx(53.0)
        assert best is race

    def test_peak_rpi_wins_over_recent_lower_rpi(self):
        """The founder scenario: a recent post-marathon 10-miler (RPI 48.66)
        must NOT beat an older 10K PR (RPI 53.18) just because it's more recent."""
        old_pr = _make_race(days_ago=103, rpi=53.18, distance="10k", name="10K PR")
        recent_junk = _make_race(days_ago=19, rpi=48.66, distance="10_mile", name="Post-marathon 10mi")
        rpi, best = self._calc()._find_best_race([recent_junk, old_pr])
        assert rpi == pytest.approx(53.18)
        assert best is old_pr

    def test_recency_does_not_influence_selection(self):
        """Two races with identical RPI*confidence — the one with higher raw RPI wins,
        not the more recent one."""
        old = _make_race(days_ago=300, rpi=52.0, confidence=1.0)
        new = _make_race(days_ago=10, rpi=50.0, confidence=1.0)
        rpi, best = self._calc()._find_best_race([new, old])
        assert rpi == pytest.approx(52.0)
        assert best is old

    def test_confidence_multiplier_influences_selection_not_return(self):
        """A hilly race (confidence=1.05) with RPI 51 should beat a flat race
        (confidence=1.0) with RPI 51, but the returned RPI is the raw value."""
        flat = _make_race(days_ago=60, rpi=51.0, confidence=1.0)
        hilly = _make_race(days_ago=90, rpi=51.0, confidence=1.05)
        rpi, best = self._calc()._find_best_race([flat, hilly])
        assert best is hilly
        assert rpi == pytest.approx(51.0)

    def test_24_month_window(self):
        """Races older than 24 months are excluded from the primary window."""
        old = _make_race(days_ago=740, rpi=55.0)
        recent = _make_race(days_ago=60, rpi=48.0)
        rpi, best = self._calc()._find_best_race([old, recent])
        assert rpi == pytest.approx(48.0)
        assert best is recent

    def test_fallback_when_no_races_in_24_month_window(self):
        """If ALL races are older than 24 months, fall back to any valid race."""
        old = _make_race(days_ago=800, rpi=55.0)
        rpi, best = self._calc()._find_best_race([old])
        assert rpi == pytest.approx(55.0)
        assert best is old

    def test_low_rpi_excluded(self):
        """Races with RPI < 35 are not valid race efforts."""
        junk = _make_race(days_ago=30, rpi=30.0)
        rpi, best = self._calc()._find_best_race([junk])
        assert rpi == 45.0
        assert best is None

    def test_low_confidence_excluded(self):
        """Races with confidence < 0.5 are excluded."""
        anomaly = _make_race(days_ago=30, rpi=55.0, confidence=0.4)
        rpi, best = self._calc()._find_best_race([anomaly])
        assert rpi == 45.0
        assert best is None

    def test_mixed_valid_and_invalid(self):
        """Only valid races participate in selection."""
        invalid_low_rpi = _make_race(days_ago=30, rpi=30.0)
        invalid_low_conf = _make_race(days_ago=30, rpi=55.0, confidence=0.3)
        valid = _make_race(days_ago=60, rpi=50.0, confidence=1.0)
        rpi, best = self._calc()._find_best_race([invalid_low_rpi, invalid_low_conf, valid])
        assert rpi == pytest.approx(50.0)
        assert best is valid

    def test_limping_race_boosted_by_confidence(self):
        """A limping race (confidence=1.2) at RPI 50 should beat a normal race at RPI 50."""
        normal = _make_race(days_ago=60, rpi=50.0, confidence=1.0)
        limping = _make_race(days_ago=90, rpi=50.0, confidence=1.2, conditions="limping")
        rpi, best = self._calc()._find_best_race([normal, limping])
        assert best is limping
        assert rpi == pytest.approx(50.0)

    def test_raw_rpi_returned_not_adjusted(self):
        """_find_best_race returns the raw RPI, not rpi*confidence."""
        race = _make_race(days_ago=30, rpi=53.0, confidence=1.1)
        rpi, _ = self._calc()._find_best_race([race])
        assert rpi == pytest.approx(53.0)


# =============================================================================
# FIX 3: Quality sessions penalty skip within 35 days of marathon
# =============================================================================

class TestQualityPenaltyPostMarathon:
    """Tests for _predict_race skipping quality penalty in post-marathon recovery."""

    def _predict(self, bank: FitnessBank, distance: str = "10k"):
        planner = ConstraintAwarePlanner(db=MagicMock())
        predicted, ci, scenarios, tags, uncertainty = planner._predict_race(
            bank, distance, goal_time=None,
        )
        return scenarios["base"]["time"], tags

    def test_no_quality_penalty_within_35_days_of_marathon(self):
        """An athlete 20 days post-marathon with 0 quality sessions should NOT
        get the -1.5 RPI penalty.  Skipping intervals after a marathon is correct."""
        marathon_race = _make_race(
            days_ago=20, distance="marathon", distance_m=42195,
            finish_time_seconds=3 * 3600, rpi=52.0,
        )
        bank = _make_bank(
            races=[marathon_race],
            best_rpi=53.0,
            quality_sessions_28d=0,
            current_weekly_miles=33.0,
            peak_weekly_miles=65.0,
        )
        base_time, tags = self._predict(bank)

        bank_with_penalty = _make_bank(
            races=[],
            best_rpi=53.0,
            quality_sessions_28d=0,
            current_weekly_miles=33.0,
            peak_weekly_miles=65.0,
        )
        penalized_time, _ = self._predict(bank_with_penalty)

        assert "quality_gap" not in tags or base_time != penalized_time

    def test_quality_penalty_applied_outside_35_days(self):
        """An athlete 40 days post-marathon with 0 quality sessions SHOULD
        get the quality penalty — recovery window has passed."""
        old_marathon = _make_race(
            days_ago=40, distance="marathon", distance_m=42195,
            finish_time_seconds=3 * 3600, rpi=52.0,
        )
        bank = _make_bank(
            races=[old_marathon],
            best_rpi=53.0,
            quality_sessions_28d=0,
            current_weekly_miles=50.0,
            peak_weekly_miles=65.0,
        )
        _, tags = self._predict(bank)
        assert "quality_gap" in tags

    def test_half_marathon_also_triggers_recovery_window(self):
        """A half marathon within 35 days should also skip the penalty."""
        half = _make_race(
            days_ago=15, distance="half_marathon", distance_m=21097,
            finish_time_seconds=90 * 60, rpi=52.0,
        )
        bank_with_half = _make_bank(
            races=[half],
            best_rpi=53.0,
            quality_sessions_28d=0,
            current_weekly_miles=40.0,
            peak_weekly_miles=60.0,
        )
        bank_no_race = _make_bank(
            races=[],
            best_rpi=53.0,
            quality_sessions_28d=0,
            current_weekly_miles=40.0,
            peak_weekly_miles=60.0,
        )
        time_with_half, _ = self._predict(bank_with_half)
        time_no_race, _ = self._predict(bank_no_race)
        assert time_with_half != time_no_race

    def test_5k_does_not_trigger_recovery_window(self):
        """A 5K race should NOT suppress the quality penalty — it's too short
        to warrant a recovery window."""
        short_race = _make_race(
            days_ago=15, distance="5k", distance_m=5000,
            finish_time_seconds=20 * 60, rpi=53.0,
        )
        bank_5k = _make_bank(
            races=[short_race],
            best_rpi=53.0,
            quality_sessions_28d=0,
            current_weekly_miles=50.0,
            peak_weekly_miles=65.0,
        )
        bank_no_race = _make_bank(
            races=[],
            best_rpi=53.0,
            quality_sessions_28d=0,
            current_weekly_miles=50.0,
            peak_weekly_miles=65.0,
        )
        time_5k, _ = self._predict(bank_5k)
        time_no, _ = self._predict(bank_no_race)
        assert time_5k == time_no

    def test_penalty_applied_when_quality_sessions_present(self):
        """Even within 35 days of marathon, if quality_sessions_28d >= 5,
        no penalty applies regardless — this tests the normal path."""
        marathon_race = _make_race(
            days_ago=20, distance="marathon", distance_m=42195,
            finish_time_seconds=3 * 3600, rpi=52.0,
        )
        bank = _make_bank(
            races=[marathon_race],
            best_rpi=53.0,
            quality_sessions_28d=6,
            current_weekly_miles=55.0,
            peak_weekly_miles=65.0,
        )
        _, tags = self._predict(bank)
        assert "quality_gap" not in tags

    def test_base_rpi_preserved_post_marathon_no_quality(self):
        """The base_rpi for a post-marathon athlete with 0 quality sessions
        should only reflect the current_ratio penalty, NOT the quality gap penalty."""
        marathon_race = _make_race(
            days_ago=20, distance="marathon", distance_m=42195,
            finish_time_seconds=3 * 3600 + 20 * 60, rpi=49.0,
        )
        bank = _make_bank(
            races=[marathon_race],
            best_rpi=53.0,
            quality_sessions_28d=0,
            current_weekly_miles=33.0,
            peak_weekly_miles=65.0,
        )
        planner = ConstraintAwarePlanner(db=MagicMock())
        _, _, scenarios, _, _ = planner._predict_race(bank, "10k", None)

        from services.fitness_bank import rpi_equivalent_time
        base_time_sec = rpi_equivalent_time(53.0 - 0.8, 10000)
        predicted_base = planner._format_time_seconds(base_time_sec)
        assert scenarios["base"]["time"] == predicted_base
