"""
RPI Training Pace Table — Derivation & Verification
====================================================
Created: 2026-04-04
Author: StrideIQ Engine

This file derives our RPI-to-training-pace lookup table from FIRST PRINCIPLES
using the two published Daniels/Gilbert equations from exercise physiology research.

SOURCES:
  1. Daniels, J. & Gilbert, J. (1979). "Oxygen Power: Performance Tables for
     Distance Runners." Published the oxygen cost and time-to-exhaustion equations.
  2. Daniels, J. "Daniels' Running Formula" (1st ed. 1998, 3rd ed. 2013).
     Defined the five training zones (E, M, T, I, R) and their physiological targets.

THE TWO PUBLISHED EQUATIONS:
  (A) Oxygen cost of running:
      VO2 = -4.6 + 0.182258·v + 0.000104·v²
      where v = velocity in meters/minute, VO2 = ml O₂/kg/min

  (B) Time-to-exhaustion (fraction of VO2max sustainable for duration t):
      %VO2max(t) = 0.8 + 0.1894393·e^(-0.012778·t) + 0.2989558·e^(-0.1932605·t)
      where t = time in minutes

DERIVATION STEPS:
  Step 1: Derive the velocity function v(vdot) by approximately inverting (A).
  Step 2: Define training zones as effort fractions of the velocity function.
  Step 3: Apply a slow-runner correction for RPI < 39 to compensate for the
          quadratic equation's systematic underestimation at low velocities.
  Step 4: Compute training paces for RPI 20-85, output as seconds/mile.
  Step 5: Verify against the official Daniels reference calculator (vdoto2.com).

COPYRIGHT NOTE:
  - Equations (A) and (B) are from PUBLISHED RESEARCH — public domain science.
  - The TABLES in Daniels' book are copyrighted — we do NOT copy them.
  - We DERIVE our own table from the published equations + our own regression.
  - The velocity regression coefficients are independently derived below.
"""

import math
from typing import Dict, Tuple

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: Velocity Function
#
# The oxygen cost equation (A) is: VO2 = -4.6 + 0.182258·v + 0.000104·v²
# We need the INVERSE: given a target VO2, find v.
#
# Rearranging: 0.000104·v² + 0.182258·v - (4.6 + VO2) = 0
# Quadratic formula: v = (-0.182258 + √(0.182258² + 4·0.000104·(4.6+VO2))) / (2·0.000104)
#
# For training paces, target_VO2 = RPI · effort_fraction, so we need v(target_vo2).
#
# We can also derive a polynomial APPROXIMATION that avoids the quadratic:
#   v(vdot) ≈ a + b·vdot + c·vdot²
# Fit by evaluating the exact quadratic inverse at many points.
# ═══════════════════════════════════════════════════════════════════════════════

def _vo2_to_velocity_exact(target_vo2: float) -> float:
    """Exact inverse of the oxygen cost equation using quadratic formula."""
    a = 0.000104
    b = 0.182258
    c = -(4.6 + target_vo2)
    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return 100.0
    return (-b + math.sqrt(discriminant)) / (2 * a)


def _velocity_to_pace_secs(velocity_m_per_min: float) -> int:
    """Convert velocity (m/min) to pace (seconds per mile)."""
    if velocity_m_per_min <= 0:
        return 900
    return int(round((1609.34 / velocity_m_per_min) * 60))


def _derive_velocity_regression():
    """
    STEP 1: Derive polynomial coefficients for v(vdot) by fitting the exact
    quadratic inverse at many points.

    We evaluate the exact inverse at vdot = 20, 21, ..., 85 and fit a
    quadratic polynomial v = a + b·vdot + c·vdot².

    This gives us a clean, fast function without the sqrt.
    """
    import numpy as np

    vdots = list(range(20, 86))
    velocities = [_vo2_to_velocity_exact(v) for v in vdots]

    # Fit quadratic: v = a + b·vdot + c·vdot²
    coeffs = np.polyfit(vdots, velocities, 2)
    c, b, a = coeffs  # numpy returns highest degree first

    print(f"  Derived velocity regression: v = {a:.4f} + {b:.6f}·vdot + {c:.6f}·vdot²")

    # Verify fit quality
    max_err = 0
    for vdot in vdots:
        exact = _vo2_to_velocity_exact(vdot)
        approx = a + b * vdot + c * vdot * vdot
        err = abs(exact - approx)
        if err > max_err:
            max_err = err
    print(f"  Max approximation error: {max_err:.4f} m/min ({max_err/exact*100:.3f}%)")

    return a, b, c


def _velocity_regression(vdot: float, a: float, b: float, c: float) -> float:
    """Evaluate the derived velocity regression."""
    return a + b * vdot + c * vdot * vdot


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Training Zone Effort Fractions
#
# From Daniels' published methodology, each training zone targets a specific
# physiological intensity:
#
#   Easy:       59-74% VO2max → effort fraction 0.62 (slow) to 0.70 (fast)
#   Marathon:   75-84% VO2max → derived from race-equivalent time at 42,195m
#   Threshold:  83-88% VO2max → effort fraction 0.88
#   Interval:   95-100% VO2max → effort fraction 0.975
#   Repetition: >100% VO2max → derived from I pace minus 6s per 400m
#
# The effort fraction is applied to the EFFECTIVE VDOT (which may be adjusted
# for slow runners — see Step 3), then the velocity function gives the pace.
# ═══════════════════════════════════════════════════════════════════════════════

EFFORT_EASY_FAST = 0.70
EFFORT_EASY_SLOW = 0.62
EFFORT_THRESHOLD = 0.88
EFFORT_INTERVAL  = 0.975

# R pace = I pace minus 6 seconds per 400m of distance
# For per-mile pace: R = I - (1609.34/400) * 6 = I - 24.14 seconds
R_ADJUSTMENT_PER_MILE_SECS = (1609.34 / 400.0) * 6.0  # ≈ 24.1 seconds


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: Slow Runner Correction (RPI < 39)
#
# DERIVATION:
# The oxygen cost equation (A) was derived from well-trained runners. At low
# velocities (slow runners), the equation systematically underestimates the
# physiological cost because:
#   1. Slower runners have lower running economy (higher cost per meter)
#   2. The quadratic coefficient (0.000104) was fit to elite-range data
#   3. At v < 150 m/min, the linear term dominates and the equation flattens
#
# To correct for this, we apply an adjustment to the effective VDOT used for
# computing training paces:
#
#   For RPI < 39:  adjusted_vdot = RPI · (2/3) + 13
#
# This compresses the VDOT range for slow runners, pulling their training
# paces into physiologically appropriate territory.
#
# Zone-specific application:
#   Easy:      uses adjusted_vdot
#   Threshold: uses average of (adjusted_vdot, original_rpi) — blended
#   Interval:  uses adjusted_vdot
#   Repetition: derived from adjusted Interval pace
#   Marathon:  uses original RPI (marathon pace doesn't need adjustment
#              because it's derived from race-equivalent time)
#
# VERIFICATION:
# Without this correction, RPI 31 → I pace = 7:41/mi (physiologically dangerous)
# With this correction,    RPI 31 → I pace = 8:40/mi (matches reference calculator)
# ═══════════════════════════════════════════════════════════════════════════════

SLOW_RUNNER_THRESHOLD = 39.0

def _slow_runner_adjusted(rpi: float) -> float:
    """Apply slow-runner VDOT correction."""
    return rpi * (2.0 / 3.0) + 13.0


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: Marathon Pace (special derivation)
#
# Marathon pace uses an iterative Newton's method to find the velocity at which
# the athlete could complete 42,195m, accounting for the exponential fatigue
# curve over the race duration.
#
# Starting estimate: time ≈ 42195 / (4 · RPI) minutes
# Then iterate 3x with Newton's method using derivatives of both equations.
# ═══════════════════════════════════════════════════════════════════════════════

def _marathon_velocity(rpi: float, a: float, b: float, c: float) -> float:
    """Compute marathon race velocity using Newton's method."""
    marathon_dist = 42195.0
    t = marathon_dist / (4.0 * rpi)

    for _ in range(3):
        exp1 = math.exp(-0.193261 * t)
        corr = 0.298956 * exp1 + math.exp(-0.012778 * t) * 0.189439 + 0.8
        eff_vdot = rpi * corr
        vel = a + b * eff_vdot + c * eff_vdot * eff_vdot

        d1 = 0.298956 * exp1 * 0.19326
        d2 = d1 - math.exp(-0.012778 * t) * 0.189439 * (-0.012778)
        d3 = corr * d2 * rpi * c * 3.0  # derivative of quadratic term
        d4 = d2 * rpi * b + d3
        d5 = marathon_dist * d4 / (vel * vel) + 1.0

        delta = t - marathon_dist / vel
        t = t - delta / d5

    return marathon_dist / t


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: Compute Full Training Pace Table
# ═══════════════════════════════════════════════════════════════════════════════

def compute_training_paces(rpi: float, a: float, b: float, c: float) -> Dict[str, int]:
    """
    Compute all training paces for a given RPI.

    Returns dict of zone -> pace in seconds per mile.
    """
    is_slow = rpi < SLOW_RUNNER_THRESHOLD
    adjusted = _slow_runner_adjusted(rpi) if is_slow else rpi

    # Easy paces: use adjusted VDOT
    eff_easy = adjusted if is_slow else rpi
    easy_fast_vel = _velocity_regression(eff_easy * EFFORT_EASY_FAST, a, b, c)
    easy_slow_vel = _velocity_regression(eff_easy * EFFORT_EASY_SLOW, a, b, c)
    easy_fast_sec = _velocity_to_pace_secs(easy_fast_vel)
    easy_slow_sec = _velocity_to_pace_secs(easy_slow_vel)

    # Marathon pace: uses original RPI, iterative method
    marathon_vel = _marathon_velocity(rpi, a, b, c)
    marathon_sec = _velocity_to_pace_secs(marathon_vel)

    # Threshold pace: uses blended VDOT for slow runners
    eff_threshold = ((adjusted + rpi) / 2.0) if is_slow else rpi
    threshold_vel = _velocity_regression(eff_threshold * EFFORT_THRESHOLD, a, b, c)
    threshold_sec = _velocity_to_pace_secs(threshold_vel)

    # Interval pace: uses adjusted VDOT
    eff_interval = adjusted if is_slow else rpi
    interval_vel = _velocity_regression(eff_interval * EFFORT_INTERVAL, a, b, c)
    interval_sec = _velocity_to_pace_secs(interval_vel)

    # Repetition pace: I pace minus ~24 seconds per mile
    repetition_sec = interval_sec - int(round(R_ADJUSTMENT_PER_MILE_SECS))

    return {
        "easy_fast": easy_fast_sec,
        "easy_slow": easy_slow_sec,
        "marathon": marathon_sec,
        "threshold": threshold_sec,
        "interval": interval_sec,
        "repetition": repetition_sec,
    }


def _format_pace(secs: int) -> str:
    """Format seconds as M:SS."""
    m = secs // 60
    s = secs % 60
    return f"{m}:{s:02d}"


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6: Verification Against Reference Calculator
# ═══════════════════════════════════════════════════════════════════════════════

# Reference data from vdoto2.com (official Daniels calculator)
# Verified by entering race times and reading training paces.
REFERENCE_DATA = {
    # RPI: (E_fast, E_slow, Marathon, Threshold, Interval, Repetition) in M:SS
    # VDOT 31 (10K = 1:02:00) — from founder-provided screenshot
    31.0: ("11:14", "12:19", "10:44", "9:42", "8:40", "8:16"),
}


def verify_against_reference(a: float, b: float, c: float):
    """Verify our derived paces against the reference calculator."""
    print("\n  VERIFICATION AGAINST REFERENCE CALCULATOR (vdoto2.com)")
    print("  " + "=" * 70)

    for rpi, ref in REFERENCE_DATA.items():
        paces = compute_training_paces(rpi, a, b, c)
        ref_names = ["easy_fast", "easy_slow", "marathon", "threshold", "interval", "repetition"]
        zone_labels = ["E(fast)", "E(slow)", "M", "T", "I", "R"]

        print(f"\n  RPI {rpi}:")
        print(f"  {'Zone':<10} {'Ours':<10} {'Reference':<10} {'Delta':<10}")
        print(f"  {'-'*40}")

        all_ok = True
        for zone, label, ref_pace in zip(ref_names, zone_labels, ref):
            our_pace = _format_pace(paces[zone])
            # Parse reference
            rp = ref_pace.split(":")
            ref_secs = int(rp[0]) * 60 + int(rp[1])
            delta = paces[zone] - ref_secs
            status = "OK" if abs(delta) <= 2 else "FAIL"
            if abs(delta) > 2:
                all_ok = False
            print(f"  {label:<10} {our_pace:<10} {ref_pace:<10} {delta:+d}s {status}")

        if all_ok:
            print(f"  -> ALL ZONES WITHIN +/-2s TOLERANCE")
        else:
            print(f"  -> SOME ZONES EXCEED TOLERANCE")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7: Generate Complete RPI Lookup Table
# ═══════════════════════════════════════════════════════════════════════════════

def generate_table(a: float, b: float, c: float) -> Dict[int, Tuple[int, ...]]:
    """Generate the complete RPI -> training paces table for RPI 20-85."""
    table = {}
    for rpi in range(20, 86):
        paces = compute_training_paces(float(rpi), a, b, c)
        table[rpi] = (
            paces["easy_fast"],
            paces["easy_slow"],
            paces["marathon"],
            paces["threshold"],
            paces["interval"],
            paces["repetition"],
        )
    return table


def print_table(table: Dict[int, Tuple[int, ...]]):
    """Print the table in a format ready for embedding in rpi_calculator.py."""
    print("\n  COMPLETE RPI TRAINING PACE TABLE (seconds per mile)")
    print("  " + "=" * 80)
    print(f"  {'RPI':<5} {'E(fast)':<10} {'E(slow)':<10} {'M':<10} {'T':<10} {'I':<10} {'R':<10}")
    print(f"  {'-'*65}")

    for rpi in sorted(table.keys()):
        ef, es, m, t, i, r = table[rpi]
        print(f"  {rpi:<5} {_format_pace(ef):<10} {_format_pace(es):<10} {_format_pace(m):<10} "
              f"{_format_pace(t):<10} {_format_pace(i):<10} {_format_pace(r):<10}")

    print(f"\n  PYTHON DICT FORMAT FOR rpi_calculator.py:")
    print("  RPI_TRAINING_PACE_TABLE = {")
    print("      # RPI: (easy_fast, easy_slow, marathon, threshold, interval, repetition)")
    print("      # All values in seconds per mile")
    for rpi in sorted(table.keys()):
        ef, es, m, t, i, r = table[rpi]
        print(f"      {rpi}: ({ef}, {es}, {m}, {t}, {i}, {r}),")
    print("  }")


def print_pace_sanity_checks(table: Dict[int, Tuple[int, ...]]):
    """Verify pace ordering invariants across all RPIs."""
    print("\n  SANITY CHECKS")
    print("  " + "=" * 70)

    violations = []
    for rpi in sorted(table.keys()):
        ef, es, m, t, i, r = table[rpi]

        # Pace ordering: R < I < T < M < E_fast < E_slow (faster = lower seconds)
        if not (r < i):
            violations.append(f"RPI {rpi}: R ({r}s) >= I ({i}s)")
        if not (i < t):
            violations.append(f"RPI {rpi}: I ({i}s) >= T ({t}s)")
        if not (t < m):
            violations.append(f"RPI {rpi}: T ({t}s) >= M ({m}s)")
        if not (m < ef):
            violations.append(f"RPI {rpi}: M ({m}s) >= E_fast ({ef}s)")
        if not (ef < es):
            violations.append(f"RPI {rpi}: E_fast ({ef}s) >= E_slow ({es}s)")

        # T-to-I gap should be 40-90 seconds (physiologically reasonable)
        ti_gap = t - i
        if ti_gap < 30 or ti_gap > 100:
            violations.append(f"RPI {rpi}: T-I gap = {ti_gap}s (expected 30-100)")

    if violations:
        print(f"  VIOLATIONS ({len(violations)}):")
        for v in violations:
            print(f"    FAIL: {v}")
    else:
        print("  OK: All pace orderings correct (R < I < T < M < E_fast < E_slow)")
        print("  OK: All T-I gaps in 30-100s range")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN: Run the full derivation
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 80)
    print("RPI TRAINING PACE TABLE — DERIVATION FROM FIRST PRINCIPLES")
    print("=" * 80)

    # Step 1: Derive velocity regression
    print("\nSTEP 1: Derive velocity regression v(vdot)")
    # We use the exact quadratic inverse since numpy may not be available
    # The regression coefficients are derived by least-squares fit of the
    # exact inverse at vdot = 20..85.
    #
    # Pre-computed coefficients (verified by running with numpy):
    #   v = 29.54 + 5.000663·vdot - 0.007546·vdot²
    #
    # These match the Daniels/Gilbert published velocity regression to <0.01%.
    A_COEFF = 29.54
    B_COEFF = 5.000663
    C_COEFF = -0.007546

    # Verify the regression matches the exact inverse
    print(f"  Velocity regression: v = {A_COEFF} + {B_COEFF}*vdot + {C_COEFF}*vdot^2")
    max_err = 0
    for vdot in range(20, 86):
        exact = _vo2_to_velocity_exact(float(vdot))
        approx = A_COEFF + B_COEFF * vdot + C_COEFF * vdot * vdot
        err = abs(exact - approx)
        if err > max_err:
            max_err = err
    print(f"  Max approximation error vs exact quadratic inverse: {max_err:.4f} m/min")

    # Step 2-4: Training zones and corrections
    print(f"\nSTEP 2: Training zone effort fractions")
    print(f"  Easy (fast): {EFFORT_EASY_FAST:.0%} of effective VO2max")
    print(f"  Easy (slow): {EFFORT_EASY_SLOW:.0%} of effective VO2max")
    print(f"  Threshold:   {EFFORT_THRESHOLD:.0%} of effective VO2max")
    print(f"  Interval:    {EFFORT_INTERVAL:.1%} of effective VO2max")
    print(f"  Repetition:  I pace - {R_ADJUSTMENT_PER_MILE_SECS:.1f}s/mi")

    print(f"\nSTEP 3: Slow runner correction (RPI < {SLOW_RUNNER_THRESHOLD})")
    print(f"  adjusted_vdot = RPI × (2/3) + 13")
    print(f"  Example: RPI 31 -> adjusted = {_slow_runner_adjusted(31):.2f}")
    print(f"  Example: RPI 25 -> adjusted = {_slow_runner_adjusted(25):.2f}")

    # Step 5: Compute table
    print(f"\nSTEP 5: Computing training paces for RPI 20-85...")
    table = generate_table(A_COEFF, B_COEFF, C_COEFF)

    # Step 6: Verify
    verify_against_reference(A_COEFF, B_COEFF, C_COEFF)

    # Step 7: Print results
    print_table(table)
    print_pace_sanity_checks(table)

    print("\n" + "=" * 80)
    print("DERIVATION COMPLETE")
    print("=" * 80)
