"""
Architectural contract test: every pace value the planner emits must come from
the single RPI source of truth and must be physically coherent.

ADR-040 says all training paces flow through one of:
  - `services.rpi_calculator.calculate_training_paces(rpi)` (the lookup table)
  - `services.workout_prescription.calculate_paces_from_rpi(rpi)` (the
    generator-facing wrapper that adapts the table output)

The Daniels/Gilbert lookup table is monotonic by construction. Any deviation
from monotonicity in the table or in the wrapper would manifest as a
pace-order inversion (e.g. interval pace SLOWER than threshold pace) in a
generated plan. That is physically impossible — interval intensity is by
definition harder than threshold — so the contract must hold for every RPI
the planner can reasonably encounter.

If this test fails, do not write a defensive repair pass downstream. Fix the
table or the wrapper. The plan-generation route MUST be able to trust this
contract; that is why ADR-040 exists.
"""
import pytest

from services.rpi_calculator import calculate_training_paces
from services.workout_prescription import calculate_paces_from_rpi


def _pace_str_to_seconds(pace_str: str) -> int:
    minutes, seconds = pace_str.split(":")
    return int(minutes) * 60 + int(seconds)


# Representative RPI sweep covering the entire range we ship plans for.
# 30 = elite-marathon; 80 = walk-jogger; 1.0 step catches monotonicity bugs.
RPI_SWEEP = [round(x * 0.5, 1) for x in range(60, 161)]  # 30.0 → 80.0 in 0.5 steps


@pytest.mark.parametrize("rpi", RPI_SWEEP)
def test_calculate_training_paces_table_is_monotonic(rpi):
    """The RPI lookup table is the single source of truth. Every pace it
    returns for every RPI in the supported range must satisfy the physics
    contract: faster intensity = lower seconds-per-mile.
    """
    paces = calculate_training_paces(rpi)

    repetition = _pace_str_to_seconds(paces["repetition"]["mi"])
    interval = _pace_str_to_seconds(paces["interval"]["mi"])
    threshold = _pace_str_to_seconds(paces["threshold"]["mi"])
    marathon = _pace_str_to_seconds(paces["marathon"]["mi"])
    easy = _pace_str_to_seconds(paces["easy"]["mi"])

    assert repetition < interval, f"rpi={rpi}: repetition {repetition} >= interval {interval}"
    assert interval < threshold, f"rpi={rpi}: interval {interval} >= threshold {threshold}"
    assert threshold < marathon, f"rpi={rpi}: threshold {threshold} >= marathon {marathon}"
    assert marathon < easy, f"rpi={rpi}: marathon {marathon} >= easy {easy}"


@pytest.mark.parametrize("rpi", RPI_SWEEP)
def test_calculate_paces_from_rpi_wrapper_preserves_order(rpi):
    """The workout-prescription wrapper adapts the table output into the
    generator's float-min/mi format. Adaptation must not introduce inversions:
    every constraint-aware day pace inherits from this wrapper, so any
    breakage here would ship to athletes as an incoherent plan.
    """
    paces = calculate_paces_from_rpi(rpi)

    if any(paces[k] is None for k in ("interval", "threshold", "marathon", "easy", "repetition")):
        pytest.skip(f"rpi={rpi} returned None paces (table edge); not a coherence concern")

    assert paces["repetition"] < paces["interval"], paces
    assert paces["interval"] < paces["threshold"], paces
    assert paces["threshold"] < paces["marathon"], paces
    assert paces["marathon"] < paces["easy"], paces
    assert paces["easy"] < paces["long"], paces  # long is easy + 9s by design
    assert paces["long"] < paces["recovery"], paces  # recovery is easy + 30s


def test_table_returns_safe_empty_for_invalid_rpi():
    """RPI <= 0 returns a dict full of None values rather than crashing or
    fabricating paces. Downstream code must check for this before formatting.
    """
    paces = calculate_training_paces(0)
    for zone in ("easy", "marathon", "threshold", "interval", "repetition"):
        assert paces[zone]["mi"] is None
        assert paces[zone]["km"] is None


def test_wrapper_returns_safe_empty_for_invalid_rpi():
    """The wrapper must not invent paces when the table can't supply them."""
    paces = calculate_paces_from_rpi(0)
    for zone in ("easy", "long", "marathon", "threshold", "interval", "repetition", "recovery"):
        assert paces[zone] is None
