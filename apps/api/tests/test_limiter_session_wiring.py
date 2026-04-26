"""Limiter → Session Type Wiring Tests

Behavioral tests verifying that FingerprintParams.limiter drives
session type selection in the N1 plan engine per LIMITER_TAXONOMY.md
Layer 2 (LM-1 through LM-7).

Each test generates a real plan via generate_n1_plan and asserts on the
session types present across build weeks. No mocks of internal engine
functions — these test the full path from FingerprintParams to WeekPlan.

Test matrix covers:
  - 7 limiter values × 4 distances (key combinations, not full cartesian)
  - Distance floor invariants (5K always has intervals, 10K+ always has threshold)
  - LR quality gates (L-VOL starts quality LRs earlier, L-CEIL keeps LRs easy)
"""

from datetime import date, timedelta

import pytest

from services.fitness_bank import ExperienceLevel
from services.plan_framework.fingerprint_bridge import FingerprintParams
from services.plan_framework.n1_engine import generate_n1_plan


RACE_DATE = date(2026, 7, 1)
PLAN_START = date(2026, 4, 1)
HORIZON = 13

EXPERIENCED_KWARGS = dict(
    plan_start=PLAN_START,
    race_date=RACE_DATE,
    horizon_weeks=HORIZON,
    days_per_week=6,
    starting_vol=45.0,
    current_lr=14.0,
    applied_peak=55.0,
    experience=ExperienceLevel.EXPERIENCED,
    best_rpi=50.0,
)


def _is_taper(w):
    theme = w.theme.value if hasattr(w.theme, "value") else str(w.theme)
    return "taper" in theme.lower()


def _collect_midweek_types(weeks):
    """Extract midweek quality session types from build weeks (skip cutback/taper)."""
    types = []
    for w in weeks:
        if _is_taper(w):
            continue
        for d in w.days:
            if d.workout_type in (
                "cruise_intervals", "threshold_continuous",
                "intervals", "repetitions",
            ):
                types.append(d.workout_type)
    return types


def _collect_lr_types(weeks):
    """Extract long run types from build weeks (skip cutback/taper)."""
    types = []
    for w in weeks:
        if _is_taper(w) or w.is_cutback:
            continue
        for d in w.days:
            if d.workout_type in (
                "long_mp", "long_hmp", "long_progressive", "long_fast_finish",
            ):
                types.append(d.workout_type)
    return types


def _has_session_type(weeks, target_type):
    for w in weeks:
        for d in w.days:
            if d.workout_type == target_type:
                return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# LM-7: L-NONE — Distance Default (baseline / no change)
# ═══════════════════════════════════════════════════════════════════════

class TestLNoneDefault:
    """L-NONE (limiter=None) produces the distance-based default prescription."""

    def test_10k_threshold_primary(self):
        weeks = generate_n1_plan(
            race_distance="10k",
            fingerprint=FingerprintParams(limiter=None),
            **EXPERIENCED_KWARGS,
        )
        mw = _collect_midweek_types(weeks)
        threshold_count = sum(1 for t in mw if t in ("cruise_intervals", "threshold_continuous"))
        assert threshold_count >= 1, "10K L-NONE must have threshold sessions"

    def test_5k_intervals_primary(self):
        weeks = generate_n1_plan(
            race_distance="5k",
            fingerprint=FingerprintParams(limiter=None),
            **EXPERIENCED_KWARGS,
        )
        mw = _collect_midweek_types(weeks)
        interval_count = sum(1 for t in mw if t == "intervals")
        assert interval_count >= 1, "5K L-NONE must have interval sessions"


# ═══════════════════════════════════════════════════════════════════════
# LM-1: L-VOL — Volume emphasis, cap midweek, quality LRs earlier
# ═══════════════════════════════════════════════════════════════════════

class TestLVol:

    def test_10k_caps_midweek_to_floor(self):
        """L-VOL 10K: only threshold floor, no intervals."""
        weeks = generate_n1_plan(
            race_distance="10k",
            fingerprint=FingerprintParams(limiter="volume"),
            **EXPERIENCED_KWARGS,
        )
        mw = _collect_midweek_types(weeks)
        interval_count = sum(1 for t in mw if t == "intervals")
        threshold_count = sum(1 for t in mw if t in ("cruise_intervals", "threshold_continuous"))
        assert threshold_count >= 1, "10K floor: threshold must be present"
        assert interval_count == 0, "L-VOL 10K: intervals should be dropped"

    def test_5k_preserves_interval_floor(self):
        """L-VOL 5K: interval floor maintained (at reduced dose)."""
        weeks = generate_n1_plan(
            race_distance="5k",
            fingerprint=FingerprintParams(limiter="volume"),
            **EXPERIENCED_KWARGS,
        )
        mw = _collect_midweek_types(weeks)
        interval_count = sum(1 for t in mw if t == "intervals")
        threshold_count = sum(1 for t in mw if t in ("cruise_intervals", "threshold_continuous"))
        assert interval_count >= 1, "5K floor: intervals must be present"
        assert threshold_count == 0, "L-VOL 5K: threshold should be dropped (floor is intervals)"

    def test_quality_lrs_start_earlier_marathon(self):
        """L-VOL marathon: quality LRs appear earlier than L-NONE."""
        weeks_vol = generate_n1_plan(
            race_distance="marathon",
            fingerprint=FingerprintParams(limiter="volume"),
            **{**EXPERIENCED_KWARGS, "current_lr": 14.0},
        )
        weeks_none = generate_n1_plan(
            race_distance="marathon",
            fingerprint=FingerprintParams(limiter=None),
            **{**EXPERIENCED_KWARGS, "current_lr": 14.0},
        )
        vol_lr = _collect_lr_types(weeks_vol)
        none_lr = _collect_lr_types(weeks_none)
        assert len(vol_lr) >= len(none_lr), (
            f"L-VOL should have at least as many quality LRs: vol={len(vol_lr)}, none={len(none_lr)}"
        )


# ═══════════════════════════════════════════════════════════════════════
# LM-2: L-CEIL — Interval emphasis, LRs easy
# ═══════════════════════════════════════════════════════════════════════

class TestLCeil:

    def test_10k_intervals_primary(self):
        """L-CEIL 10K: intervals primary, threshold secondary."""
        weeks = generate_n1_plan(
            race_distance="10k",
            fingerprint=FingerprintParams(limiter="ceiling"),
            **EXPERIENCED_KWARGS,
        )
        mw = _collect_midweek_types(weeks)
        interval_count = sum(1 for t in mw if t == "intervals")
        assert interval_count >= 1, "L-CEIL 10K: must have interval sessions"

    def test_half_marathon_gets_10k_style(self):
        """L-CEIL half: 10K-style with intervals (DQ-5 speed-profile)."""
        weeks = generate_n1_plan(
            race_distance="half_marathon",
            fingerprint=FingerprintParams(limiter="ceiling"),
            **EXPERIENCED_KWARGS,
        )
        mw = _collect_midweek_types(weeks)
        interval_count = sum(1 for t in mw if t == "intervals")
        assert interval_count >= 1, "L-CEIL half: must have intervals (10K-style)"

    def test_lrs_kept_easy(self):
        """L-CEIL: long runs should all be plain easy long runs."""
        weeks = generate_n1_plan(
            race_distance="marathon",
            fingerprint=FingerprintParams(limiter="ceiling"),
            **{**EXPERIENCED_KWARGS, "current_lr": 14.0},
        )
        quality_lrs = _collect_lr_types(weeks)
        assert len(quality_lrs) == 0, f"L-CEIL: LRs must be easy, got quality: {quality_lrs}"

    def test_marathon_adds_intervals(self):
        """L-CEIL marathon: intervals appear (not in default marathon prescription)."""
        weeks = generate_n1_plan(
            race_distance="marathon",
            fingerprint=FingerprintParams(limiter="ceiling"),
            **{**EXPERIENCED_KWARGS, "current_lr": 14.0},
        )
        mw = _collect_midweek_types(weeks)
        interval_count = sum(1 for t in mw if t == "intervals")
        assert interval_count >= 1, "L-CEIL marathon: must have intervals"


# ═══════════════════════════════════════════════════════════════════════
# LM-3: L-THRESH — Threshold emphasis
# ═══════════════════════════════════════════════════════════════════════

class TestLThresh:

    def test_5k_threshold_primary_with_interval_floor(self):
        """L-THRESH 5K: threshold primary, interval floor maintained."""
        weeks = generate_n1_plan(
            race_distance="5k",
            fingerprint=FingerprintParams(limiter="threshold"),
            **EXPERIENCED_KWARGS,
        )
        mw = _collect_midweek_types(weeks)
        threshold_count = sum(1 for t in mw if t in ("cruise_intervals", "threshold_continuous"))
        interval_count = sum(1 for t in mw if t == "intervals")
        assert threshold_count >= 1, "L-THRESH 5K: must have threshold sessions"
        assert interval_count >= 1, "5K floor: must maintain interval floor"

    def test_10k_threshold_stays_primary(self):
        """L-THRESH 10K: threshold primary (matches default — correct)."""
        weeks = generate_n1_plan(
            race_distance="10k",
            fingerprint=FingerprintParams(limiter="threshold"),
            **EXPERIENCED_KWARGS,
        )
        mw = _collect_midweek_types(weeks)
        threshold_count = sum(1 for t in mw if t in ("cruise_intervals", "threshold_continuous"))
        assert threshold_count >= 1


# ═══════════════════════════════════════════════════════════════════════
# LM-4b: L-REC (solvable) — Recovery block, minimal quality
# ═══════════════════════════════════════════════════════════════════════

class TestLRecSolvable:

    def test_reduced_quality_count(self):
        """L-REC solvable: at most 1 quality session per build week."""
        weeks = generate_n1_plan(
            race_distance="10k",
            fingerprint=FingerprintParams(limiter="recovery"),
            **EXPERIENCED_KWARGS,
        )
        for w in weeks:
            if _is_taper(w) or w.is_cutback:
                continue
            quality_days = [
                d for d in w.days
                if d.workout_type in (
                    "cruise_intervals", "threshold_continuous",
                    "intervals", "repetitions",
                    "long_mp", "long_hmp", "long_progressive", "long_fast_finish",
                )
            ]
            assert len(quality_days) <= 1, (
                f"W{w.week_number}: L-REC solvable should have ≤1 quality, got {len(quality_days)}"
            )

    def test_lrs_kept_easy(self):
        """L-REC solvable: long runs should all be easy."""
        weeks = generate_n1_plan(
            race_distance="marathon",
            fingerprint=FingerprintParams(limiter="recovery"),
            **{**EXPERIENCED_KWARGS, "current_lr": 14.0},
        )
        quality_lrs = _collect_lr_types(weeks)
        assert len(quality_lrs) == 0, f"L-REC: LRs must be easy, got: {quality_lrs}"

    def test_early_weeks_no_quality(self):
        """L-REC solvable: early build weeks (ratio < 0.30) have no midweek quality."""
        weeks = generate_n1_plan(
            race_distance="10k",
            fingerprint=FingerprintParams(limiter="recovery"),
            **EXPERIENCED_KWARGS,
        )
        early_quality = []
        build_weeks = [w for w in weeks if not _is_taper(w) and not w.is_cutback]
        for w in build_weeks[:3]:
            for d in w.days:
                if d.workout_type in ("cruise_intervals", "threshold_continuous", "intervals"):
                    early_quality.append(d.workout_type)
        assert len(early_quality) == 0, (
            f"L-REC early weeks should have no quality, got: {early_quality}"
        )


# ═══════════════════════════════════════════════════════════════════════
# LM-6: L-SPEC — Race-specific, don't escalate
# ═══════════════════════════════════════════════════════════════════════

class TestLSpec:

    def test_matches_distance_default_10k(self):
        """L-SPEC 10K: same session types as L-NONE (organize, don't escalate)."""
        weeks_spec = generate_n1_plan(
            race_distance="10k",
            fingerprint=FingerprintParams(limiter="race_specific"),
            **EXPERIENCED_KWARGS,
        )
        weeks_none = generate_n1_plan(
            race_distance="10k",
            fingerprint=FingerprintParams(limiter=None),
            **EXPERIENCED_KWARGS,
        )
        spec_types = set(_collect_midweek_types(weeks_spec))
        none_types = set(_collect_midweek_types(weeks_none))
        assert spec_types == none_types, (
            f"L-SPEC should match L-NONE types: spec={spec_types}, none={none_types}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Distance Floor Invariants — must hold for ALL limiter values
# ═══════════════════════════════════════════════════════════════════════

class TestDistanceFloors:
    """Every limiter must preserve the minimum session type for the distance."""

    @pytest.mark.parametrize("limiter", [None, "volume", "ceiling", "threshold", "race_specific"])
    def test_5k_always_has_intervals(self, limiter):
        weeks = generate_n1_plan(
            race_distance="5k",
            fingerprint=FingerprintParams(limiter=limiter),
            **EXPERIENCED_KWARGS,
        )
        mw = _collect_midweek_types(weeks)
        interval_count = sum(1 for t in mw if t == "intervals")
        assert interval_count >= 1, f"5K with limiter={limiter}: interval floor violated"

    @pytest.mark.parametrize("limiter", [None, "volume", "ceiling", "threshold", "race_specific"])
    def test_10k_always_has_threshold(self, limiter):
        weeks = generate_n1_plan(
            race_distance="10k",
            fingerprint=FingerprintParams(limiter=limiter),
            **EXPERIENCED_KWARGS,
        )
        mw = _collect_midweek_types(weeks)
        threshold_count = sum(1 for t in mw if t in ("cruise_intervals", "threshold_continuous"))
        assert threshold_count >= 1, f"10K with limiter={limiter}: threshold floor violated"

    @pytest.mark.parametrize("limiter", [None, "volume", "ceiling", "threshold", "race_specific"])
    def test_half_always_has_threshold(self, limiter):
        weeks = generate_n1_plan(
            race_distance="half_marathon",
            fingerprint=FingerprintParams(limiter=limiter),
            **EXPERIENCED_KWARGS,
        )
        mw = _collect_midweek_types(weeks)
        threshold_count = sum(1 for t in mw if t in ("cruise_intervals", "threshold_continuous"))
        assert threshold_count >= 1, f"Half with limiter={limiter}: threshold floor violated"

    @pytest.mark.parametrize("limiter", [None, "volume", "ceiling", "threshold", "race_specific"])
    def test_marathon_always_has_threshold(self, limiter):
        weeks = generate_n1_plan(
            race_distance="marathon",
            fingerprint=FingerprintParams(limiter=limiter),
            **{**EXPERIENCED_KWARGS, "current_lr": 14.0},
        )
        mw = _collect_midweek_types(weeks)
        threshold_count = sum(1 for t in mw if t in ("cruise_intervals", "threshold_continuous"))
        assert threshold_count >= 1, f"Marathon with limiter={limiter}: threshold floor violated"


# ═══════════════════════════════════════════════════════════════════════
# Bridge detection: L-CEIL from CS-12 pattern
# ═══════════════════════════════════════════════════════════════════════

class TestBridgeLCeilDetection:

    def test_cs12_detects_ceiling(self):
        from services.plan_framework.fingerprint_bridge import _detect_limiter
        findings = [
            {
                "input_name": "days_since_quality",
                "output_metric": "pace_easy",
                "direction": "negative",
                "correlation_coefficient": -0.55,
                "times_confirmed": 5,
                "lifecycle_state": "active",
            },
        ]
        limiter, _ = _detect_limiter(findings)
        assert limiter == "ceiling"

    def test_cs11_detects_threshold(self):
        from services.plan_framework.fingerprint_bridge import _detect_limiter
        findings = [
            {
                "input_name": "days_since_quality",
                "output_metric": "pace_threshold",
                "direction": "positive",
                "correlation_coefficient": 0.60,
                "times_confirmed": 4,
                "lifecycle_state": "active",
            },
        ]
        limiter, _ = _detect_limiter(findings)
        assert limiter == "threshold"

    def test_lspec_takes_priority(self):
        from services.plan_framework.fingerprint_bridge import _detect_limiter
        findings = [
            {
                "input_name": "days_since_quality",
                "output_metric": "pace_easy",
                "direction": "negative",
                "correlation_coefficient": -0.55,
                "times_confirmed": 5,
                "lifecycle_state": "active",
            },
            {
                "input_name": "lspec_rule_based",
                "output_metric": "race_readiness",
                "direction": "positive",
                "correlation_coefficient": 1.0,
                "times_confirmed": 3,
                "lifecycle_state": "active_fixed",
            },
        ]
        limiter, _ = _detect_limiter(findings)
        assert limiter == "race_specific"


# ═══════════════════════════════════════════════════════════════════════
# CG-10: TSB → L-REC gate (half-life interaction)
# ═══════════════════════════════════════════════════════════════════════

class TestCG10Gate:

    def test_michael_tsb_not_lrec(self):
        """Michael: TSB r=0.52, half-life 23.8h → NOT L-REC (fast recoverer)."""
        from services.plan_framework.fingerprint_bridge import _detect_limiter
        findings = [
            {
                "input_name": "tsb",
                "output_metric": "pace_threshold",
                "direction": "positive",
                "correlation_coefficient": 0.52,
                "times_confirmed": 5,
                "lifecycle_state": "active",
            },
        ]
        limiter, notes = _detect_limiter(findings, recovery_half_life_hours=23.8)
        assert limiter is None, f"Michael should NOT be L-REC, got {limiter}"
        assert len(notes) >= 1, "Should have timing signal note"

    def test_slow_recoverer_tsb_is_lrec(self):
        """Slow recoverer: TSB r=0.55, half-life 52h → L-REC (passes gate)."""
        from services.plan_framework.fingerprint_bridge import _detect_limiter
        findings = [
            {
                "input_name": "tsb",
                "output_metric": "pace_threshold",
                "direction": "positive",
                "correlation_coefficient": 0.55,
                "times_confirmed": 5,
                "lifecycle_state": "active",
            },
        ]
        limiter, notes = _detect_limiter(findings, recovery_half_life_hours=52.0)
        assert limiter == "recovery"
        assert len(notes) == 0

    def test_tsb_no_halflife_not_lrec(self):
        """No half-life data: TSB correlation should NOT flag L-REC (conservative)."""
        from services.plan_framework.fingerprint_bridge import _detect_limiter
        findings = [
            {
                "input_name": "tsb",
                "output_metric": "efficiency",
                "direction": "positive",
                "correlation_coefficient": 0.55,
                "times_confirmed": 5,
                "lifecycle_state": "active",
            },
        ]
        limiter, notes = _detect_limiter(findings, recovery_half_life_hours=None)
        assert limiter is None
        assert len(notes) >= 1

    def test_non_tsb_recovery_signals_unaffected(self):
        """Non-TSB recovery signals (CS-8, CS-9) are NOT gated by CG-10."""
        from services.plan_framework.fingerprint_bridge import _detect_limiter
        findings = [
            {
                "input_name": "daily_session_stress",
                "output_metric": "efficiency",
                "direction": "negative",
                "correlation_coefficient": 0.58,
                "times_confirmed": 5,
                "lifecycle_state": "active",
            },
        ]
        limiter, _ = _detect_limiter(findings, recovery_half_life_hours=23.8)
        assert limiter == "recovery", "Non-TSB recovery signal should still count"

    def test_tsb_below_r_threshold(self):
        """TSB with |r| = 0.35 (below 0.45 threshold) → NOT L-REC even with slow recovery."""
        from services.plan_framework.fingerprint_bridge import _detect_limiter
        findings = [
            {
                "input_name": "tsb",
                "output_metric": "pace_threshold",
                "direction": "positive",
                "correlation_coefficient": 0.35,
                "times_confirmed": 5,
                "lifecycle_state": "active",
            },
        ]
        limiter, notes = _detect_limiter(findings, recovery_half_life_hours=52.0)
        assert limiter is None
        assert len(notes) >= 1
