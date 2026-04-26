"""Marathon/half-marathon readiness gate — lifetime-evidence bypass.

The recent-4-week long-run window in fitness_bank filters out activities
> 24 mi as suspected races. For an experienced ultra runner whose recent
training maxed out at, say, 10 mi (with 38–50 mi sessions silently
filtered as suspected races), the legacy gate would refuse to build a
marathon plan.

These tests prove:

1. An ultra runner with current_lr < 12 but lifetime peak_long_run >= 14
   AND `long_run_capability_proven=True` PASSES the gate (B fix).
2. A true partial-data athlete (peak_long_run synthetically defaulted to
   15.0 with `long_run_capability_proven=False`) still triggers the gate
   — the synthetic default does NOT satisfy the bypass.
3. A true beginner with low peak still triggers the gate.
4. Half-marathon gate behaves analogously at the 8-mile threshold.

Reference: services/plan_framework/n1_engine.py::resolve_athlete_state.
"""

from datetime import date

import pytest

from services.fitness_bank import ExperienceLevel
from services.plan_framework.n1_engine import (
    ReadinessGateError,
    resolve_athlete_state,
)


PLAN_START = date(2026, 4, 1)
RACE_DATE = date(2026, 7, 1)


def _state_kwargs(**overrides):
    base = dict(
        race_distance="marathon",
        race_date=RACE_DATE,
        plan_start=PLAN_START,
        horizon_weeks=13,
        days_per_week=5,
        starting_vol=30.0,
        current_lr=10.0,
        applied_peak=45.0,
        experience=ExperienceLevel.EXPERIENCED,
        best_rpi=50.0,
    )
    base.update(overrides)
    return base


# ── B: bypass for proven lifetime capability ─────────────────────────


def test_marathon_gate_bypassed_for_ultra_runner():
    """Dejan-shaped athlete: recent training-LR window low, lifetime peak high."""
    state = resolve_athlete_state(
        **_state_kwargs(
            current_lr=10.0,
            peak_long_run_miles=49.9,
            long_run_capability_proven=True,
        )
    )
    assert state.race_distance == "marathon"
    assert state.current_long_run_miles == 10.0


def test_marathon_gate_bypassed_at_threshold():
    """Lifetime peak exactly at the bypass floor (14 mi) is sufficient."""
    state = resolve_athlete_state(
        **_state_kwargs(
            current_lr=10.0,
            peak_long_run_miles=14.0,
            long_run_capability_proven=True,
        )
    )
    assert state.race_distance == "marathon"


def test_half_marathon_gate_bypassed_for_capable_athlete():
    state = resolve_athlete_state(
        **_state_kwargs(
            race_distance="half_marathon",
            current_lr=6.0,
            peak_long_run_miles=10.0,
            long_run_capability_proven=True,
        )
    )
    assert state.race_distance == "half_marathon"


# ── Bypass MUST NOT fire on synthetic defaults ───────────────────────


def test_marathon_gate_blocks_partial_data_with_synthetic_peak():
    """Athlete who has trained but never run >= 13mi: peak_long defaults to 15.0
    in fitness_bank, but `long_run_capability_proven` is False — bypass must
    refuse to engage even though the numeric peak meets the threshold."""
    with pytest.raises(ReadinessGateError) as exc_info:
        resolve_athlete_state(
            **_state_kwargs(
                current_lr=10.0,
                peak_long_run_miles=15.0,
                long_run_capability_proven=False,
            )
        )
    assert "current long run is 10mi" in str(exc_info.value)
    assert "lifetime peak 15mi" in str(exc_info.value)


def test_marathon_gate_blocks_true_beginner():
    """No lifetime evidence at all."""
    with pytest.raises(ReadinessGateError):
        resolve_athlete_state(
            **_state_kwargs(
                current_lr=4.0,
                peak_long_run_miles=6.0,
                long_run_capability_proven=False,
            )
        )


def test_marathon_gate_blocks_proven_but_below_threshold():
    """Has run a long run >= 13mi at some point, but lifetime peak < 14
    (the safety floor for marathon week-1 long run). Still refuses."""
    with pytest.raises(ReadinessGateError):
        resolve_athlete_state(
            **_state_kwargs(
                current_lr=10.0,
                peak_long_run_miles=13.0,
                long_run_capability_proven=True,
            )
        )


def test_half_marathon_gate_blocks_proven_but_below_threshold():
    with pytest.raises(ReadinessGateError):
        resolve_athlete_state(
            **_state_kwargs(
                race_distance="half_marathon",
                current_lr=4.0,
                peak_long_run_miles=7.0,
                long_run_capability_proven=True,
            )
        )


# ── Pre-existing gate behavior is unchanged ──────────────────────────


def test_marathon_gate_still_passes_with_adequate_current_lr():
    """current_lr >= 12 has always passed; no bypass needed."""
    state = resolve_athlete_state(
        **_state_kwargs(
            current_lr=14.0,
            peak_long_run_miles=0.0,
            long_run_capability_proven=False,
        )
    )
    assert state.current_long_run_miles == 14.0


def test_day_one_athlete_unaffected_by_gate():
    """is_day_one path (no training history) bypasses the gate by design."""
    state = resolve_athlete_state(
        **_state_kwargs(
            current_lr=0.0,
            starting_vol=0.0,
            peak_long_run_miles=0.0,
            long_run_capability_proven=False,
        )
    )
    assert state.is_day_one is True
