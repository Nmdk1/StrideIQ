"""Tests for correlation engine confounder control (Phase 1).

Covers:
  1. compute_partial_correlation correctness
  2. compute_partial_correlation insufficient data
  3. CONFOUNDER_MAP lookups
  4. CONFOUNDER_MAP missing pairs
  5. DIRECTION_EXPECTATIONS positive
  6. DIRECTION_EXPECTATIONS negative
  7. Confounded finding → is_active = False
  8. Non-confounded finding → is_active = True
  9. Counterintuitive + confounded → is_active = False
 10. Counterintuitive + NOT confounded → is_active = True, flag set
 11. Pair not in confounder map → bivariate r used, no partial_r
 12. Upsert preserves times_confirmed for re-runs
 13. get_surfaceable_findings excludes confounded
 14. No regressions: existing test_progress_knowledge.py passes (run separately)
"""
import math
import uuid
from datetime import date, timedelta, datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.orm import Session

from services.correlation_engine import (
    compute_partial_correlation,
    CONFOUNDER_MAP,
    DIRECTION_EXPECTATIONS,
    MIN_CORRELATION_STRENGTH,
    TEMPORAL_WEIGHTS,
    _align_time_series,
    _recency_weight,
    calculate_pearson_correlation,
    calculate_weighted_pearson_correlation,
    find_time_shifted_correlations,
)
from services.correlation_persistence import persist_correlation_findings
from models import CorrelationFinding


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ATHLETE_ID = uuid.uuid4()


def _make_series(values, start=date(2026, 1, 1)):
    """Build a list of (date, float) tuples from a list of values."""
    return [(start + timedelta(days=i), v) for i, v in enumerate(values)]


def _known_partial_r():
    """
    Build three series where we can verify the partial correlation by hand.

    x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    y = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]  (y = 2x, r_xy = 1.0)
    z = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]       (z = x, r_xz = 1.0)

    When z perfectly explains x, partial r_xy.z is undefined (denom = 0).
    So use a less degenerate case:

    x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    y = x + noise
    z = independent
    """
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    z = [5.0, 3.0, 8.0, 1.0, 9.0, 2.0, 7.0, 4.0, 6.0, 10.0]  # shuffled, low corr with x
    # y = x + some z influence
    y = [x_i + 0.5 * z_i for x_i, z_i in zip(x, z)]

    r_xy, _ = calculate_pearson_correlation(x, y)
    r_xz, _ = calculate_pearson_correlation(x, z)
    r_yz, _ = calculate_pearson_correlation(z, y)

    expected = (r_xy - r_xz * r_yz) / math.sqrt((1 - r_xz**2) * (1 - r_yz**2))

    return x, y, z, round(expected, 4)


# ---------------------------------------------------------------------------
# 1. compute_partial_correlation returns correct r_xy.z
# ---------------------------------------------------------------------------


def test_partial_correlation_correct():
    x_vals, y_vals, z_vals, expected = _known_partial_r()
    start = date(2026, 1, 1)

    x_series = _make_series(x_vals, start)
    y_series = _make_series(y_vals, start)
    z_series = _make_series(z_vals, start)

    result = compute_partial_correlation(x_series, y_series, z_series, lag_days=0)
    assert result is not None
    assert abs(result - expected) < 0.01, f"Expected ~{expected}, got {result}"


# ---------------------------------------------------------------------------
# 2. compute_partial_correlation returns None with insufficient data
# ---------------------------------------------------------------------------


def test_partial_correlation_insufficient_data():
    short = _make_series([1.0, 2.0, 3.0])  # < MIN_SAMPLE_SIZE (10)
    y = _make_series([4.0, 5.0, 6.0])
    z = _make_series([7.0, 8.0, 9.0])

    result = compute_partial_correlation(short, y, z, lag_days=0)
    assert result is None


# ---------------------------------------------------------------------------
# 3. CONFOUNDER_MAP: (readiness_1_5, efficiency) → atl
# ---------------------------------------------------------------------------


def test_confounder_map_motivation_efficiency():
    assert CONFOUNDER_MAP[("readiness_1_5", "efficiency")] == "daily_session_stress"


# ---------------------------------------------------------------------------
# 4. CONFOUNDER_MAP: (sleep_hours, efficiency) → not in map
# ---------------------------------------------------------------------------


def test_confounder_map_sleep_efficiency_not_in_map():
    assert ("sleep_hours", "efficiency") not in CONFOUNDER_MAP


# ---------------------------------------------------------------------------
# 5. DIRECTION_EXPECTATIONS: (readiness_1_5, efficiency) → "positive"
# ---------------------------------------------------------------------------


def test_direction_expectations_positive():
    assert DIRECTION_EXPECTATIONS[("readiness_1_5", "efficiency")] == "positive"


# ---------------------------------------------------------------------------
# 6. DIRECTION_EXPECTATIONS: (stress_1_5, completion) → "negative"
# ---------------------------------------------------------------------------


def test_direction_expectations_negative():
    assert DIRECTION_EXPECTATIONS[("stress_1_5", "completion")] == "negative"


# ---------------------------------------------------------------------------
# Persistence tests — mock DB session
# ---------------------------------------------------------------------------


def _mock_db():
    db = MagicMock(spec=Session)
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    return db


def _make_analysis_result(
    input_name="readiness_1_5",
    output_metric="efficiency",
    r=0.45,
    p=0.01,
    n=30,
    lag=3,
    direction="negative",
    partial_r=None,
    confounder_var=None,
    is_confounded=False,
    direction_expected="positive",
    direction_counterintuitive=True,
):
    return {
        "correlations": [{
            "input_name": input_name,
            "correlation_coefficient": r,
            "p_value": p,
            "sample_size": n,
            "time_lag_days": lag,
            "direction": direction,
            "strength": "moderate",
            "partial_correlation_coefficient": partial_r,
            "confounder_variable": confounder_var,
            "is_confounded": is_confounded,
            "direction_expected": direction_expected,
            "direction_counterintuitive": direction_counterintuitive,
        }],
        "output_metric": output_metric,
    }


# ---------------------------------------------------------------------------
# 7. Finding with |partial_r| < 0.3 → is_confounded = True, is_active = False
# ---------------------------------------------------------------------------


def test_confounded_finding_deactivated():
    db = _mock_db()
    result = _make_analysis_result(
        partial_r=0.1,
        confounder_var="atl",
        is_confounded=True,
    )

    persist_correlation_findings(ATHLETE_ID, result, db, "efficiency")

    # Check db.add was called with is_active=False
    added = db.add.call_args[0][0]
    assert added.is_active is False
    assert added.is_confounded is True
    assert added.partial_correlation_coefficient == 0.1
    assert added.confounder_variable == "atl"


# ---------------------------------------------------------------------------
# 8. Finding with |partial_r| >= 0.3 → is_confounded = False, is_active = True
# ---------------------------------------------------------------------------


def test_non_confounded_finding_active():
    db = _mock_db()
    result = _make_analysis_result(
        partial_r=0.42,
        confounder_var="atl",
        is_confounded=False,
        direction="positive",
        direction_counterintuitive=False,
        direction_expected="positive",
    )

    persist_correlation_findings(ATHLETE_ID, result, db, "efficiency")

    added = db.add.call_args[0][0]
    assert added.is_active is True
    assert added.is_confounded is False
    assert added.partial_correlation_coefficient == 0.42


# ---------------------------------------------------------------------------
# 9. Counterintuitive direction + confounded → is_active = False
# ---------------------------------------------------------------------------


def test_counterintuitive_and_confounded_deactivated():
    db = _mock_db()
    result = _make_analysis_result(
        direction="negative",
        direction_expected="positive",
        direction_counterintuitive=True,
        partial_r=0.05,
        confounder_var="atl",
        is_confounded=True,
    )

    persist_correlation_findings(ATHLETE_ID, result, db, "efficiency")

    added = db.add.call_args[0][0]
    assert added.is_active is False
    assert added.is_confounded is True
    assert added.direction_counterintuitive is True


# ---------------------------------------------------------------------------
# 10. Counterintuitive direction + NOT confounded → is_active = False (safety gate)
#     See Post-Delivery Correction in BUILDER_NOTE_2026-03-03.
# ---------------------------------------------------------------------------


def test_counterintuitive_direction_alone_does_not_suppress():
    """Counterintuitive direction without confounding is NOT suppressed.

    The data is the data — if a pattern is statistically significant and
    not explained by a confounder, the athlete's physiology may simply
    work differently than the textbook expectation.
    """
    db = _mock_db()
    result = _make_analysis_result(
        direction="negative",
        direction_expected="positive",
        direction_counterintuitive=True,
        partial_r=0.55,
        confounder_var="atl",
        is_confounded=False,
    )

    persist_correlation_findings(ATHLETE_ID, result, db, "efficiency")

    added = db.add.call_args[0][0]
    assert added.is_active is True
    assert added.direction_counterintuitive is True
    assert added.is_confounded is False


# ---------------------------------------------------------------------------
# 11. Finding NOT in confounder map → bivariate r used, no partial_r stored
# ---------------------------------------------------------------------------


def test_no_confounder_map_entry_uses_bivariate():
    db = _mock_db()
    result = _make_analysis_result(
        input_name="sleep_hours",
        output_metric="efficiency",
        direction="positive",
        direction_expected=None,
        direction_counterintuitive=False,
        partial_r=None,
        confounder_var=None,
        is_confounded=False,
    )

    persist_correlation_findings(ATHLETE_ID, result, db, "efficiency")

    added = db.add.call_args[0][0]
    assert added.is_active is True
    assert added.partial_correlation_coefficient is None
    assert added.confounder_variable is None
    assert added.is_confounded is False


# ---------------------------------------------------------------------------
# 12. Existing finding updated with new fields on re-run (upsert preserves times_confirmed)
# ---------------------------------------------------------------------------


def test_upsert_updates_confounder_fields():
    db = _mock_db()

    existing = MagicMock(spec=CorrelationFinding)
    existing.times_confirmed = 5
    existing.input_name = "readiness_1_5"
    existing.output_metric = "efficiency"
    existing.time_lag_days = 3
    existing.threshold_value = None
    existing.threshold_direction = None

    db.query.return_value.filter.return_value.first.return_value = existing
    db.query.return_value.filter.return_value.all.return_value = [existing]

    result = _make_analysis_result(
        partial_r=0.08,
        confounder_var="atl",
        is_confounded=True,
    )

    persist_correlation_findings(ATHLETE_ID, result, db, "efficiency")

    assert existing.times_confirmed == 6
    assert existing.partial_correlation_coefficient == 0.08
    assert existing.confounder_variable == "atl"
    assert existing.is_confounded is True
    assert existing.is_active is False


# ---------------------------------------------------------------------------
# 13. get_surfaceable_findings excludes confounded findings
# ---------------------------------------------------------------------------


def test_surfaceable_excludes_confounded():
    from services.correlation_persistence import get_surfaceable_findings

    active_finding = MagicMock(spec=CorrelationFinding)
    active_finding.id = uuid.uuid4()
    active_finding.is_active = True
    active_finding.is_confounded = False
    active_finding.direction_counterintuitive = False
    # Real string so the suppression-set membership check stays string-typed.
    # A MagicMock here would make .startswith() return a truthy MagicMock and
    # spuriously trip the passive-noise suppression gate.
    active_finding.input_name = "feedback_perceived_effort"
    active_finding.output_metric = "efficiency"
    active_finding.direction = "positive"
    active_finding.time_lag_days = 0
    active_finding.times_confirmed = 5
    active_finding.confidence = 0.8
    active_finding.last_surfaced_at = None

    confounded_finding = MagicMock(spec=CorrelationFinding)
    confounded_finding.id = uuid.uuid4()
    confounded_finding.is_active = False  # confounded → deactivated
    confounded_finding.is_confounded = True
    confounded_finding.direction_counterintuitive = False
    confounded_finding.input_name = "atl"
    confounded_finding.output_metric = "efficiency"
    confounded_finding.direction = "positive"
    confounded_finding.time_lag_days = 0
    confounded_finding.times_confirmed = 9
    confounded_finding.confidence = 0.9
    confounded_finding.last_surfaced_at = None

    db = MagicMock(spec=Session)
    # get_surfaceable_findings filters is_active == True, so the DB
    # query itself will only return active_finding.
    db.query.return_value.filter.return_value.all.return_value = [active_finding]

    # The chokepoint also consults sleep validity; bypass for this unit test.
    with patch(
        "services.intelligence.finding_eligibility.is_recent_sleep_invalid",
        return_value=False,
    ):
        results = get_surfaceable_findings(ATHLETE_ID, db, min_confirmations=1)
    assert len(results) == 1
    assert results[0] is active_finding


# ---------------------------------------------------------------------------
# 14. Partial correlation with lag shifts input correctly
# ---------------------------------------------------------------------------


def test_partial_correlation_with_lag():
    start = date(2026, 1, 1)
    x = _make_series([float(i) for i in range(15)], start)
    # y starts 2 days later — lag=2 will align them
    y = _make_series([float(i) * 2 + 1 for i in range(15)], start + timedelta(days=2))
    # z is non-linear / non-degenerate so denominator is non-zero
    z = _make_series(
        [5.0, 3.0, 8.0, 1.0, 9.0, 2.0, 7.0, 4.0, 6.0, 10.0, 3.0, 8.0, 2.0, 5.0, 7.0],
        start,
    )

    result = compute_partial_correlation(x, y, z, lag_days=2)
    assert result is not None
    assert -1.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# 15-19. Temporal weighting (Phase 2)
# ---------------------------------------------------------------------------

def test_recency_weight_l30():
    ref = datetime(2026, 3, 29, tzinfo=timezone.utc)
    obs = datetime(2026, 3, 15, tzinfo=timezone.utc)
    assert _recency_weight(obs, ref) == TEMPORAL_WEIGHTS[30]


def test_recency_weight_l90():
    ref = datetime(2026, 3, 29, tzinfo=timezone.utc)
    obs = datetime(2026, 2, 1, tzinfo=timezone.utc)
    assert _recency_weight(obs, ref) == TEMPORAL_WEIGHTS[90]


def test_recency_weight_l180():
    ref = datetime(2026, 3, 29, tzinfo=timezone.utc)
    obs = datetime(2025, 11, 1, tzinfo=timezone.utc)
    assert _recency_weight(obs, ref) == TEMPORAL_WEIGHTS[180]


def test_recency_weight_beyond_180():
    ref = datetime(2026, 3, 29, tzinfo=timezone.utc)
    obs = datetime(2025, 6, 1, tzinfo=timezone.utc)
    assert _recency_weight(obs, ref) == TEMPORAL_WEIGHTS[None]


def test_recency_weight_accepts_date_objects():
    """Ensure _recency_weight works with datetime.date, not just datetime."""
    ref = date(2026, 3, 29)
    obs = date(2026, 3, 20)
    assert _recency_weight(obs, ref) == TEMPORAL_WEIGHTS[30]


def test_weighted_pearson_uniform_matches_unweighted():
    """Uniform weights produce the same r as standard Pearson."""
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    y = [2.0, 4.1, 5.9, 8.2, 9.8, 12.1, 14.0, 15.9, 18.1, 20.0]
    w = [1.0] * 10

    r_std, _ = calculate_pearson_correlation(x, y)
    r_w, _ = calculate_weighted_pearson_correlation(x, y, w)

    assert abs(r_std - r_w) < 0.001


def test_temporal_weighting_weakens_old_signal():
    """A correlation that exists only in old data should weaken with weighting.

    Construct data where the first 120 days show strong positive correlation
    and the most recent 30 days show noise.  Temporal weighting (which
    gives 4x weight to L30) should produce a weaker |r| than unweighted.
    """
    ref = datetime(2026, 3, 29)
    n_old = 120
    n_recent = 30

    old_start = ref - timedelta(days=n_old + n_recent)
    recent_start = ref - timedelta(days=n_recent)

    old_input = [
        (old_start + timedelta(days=i), float(i))
        for i in range(n_old)
    ]
    old_output = [
        (old_start + timedelta(days=i), float(i) * 2.0 + 1.0)
        for i in range(n_old)
    ]

    import random
    rng = random.Random(42)
    recent_input = [
        (recent_start + timedelta(days=i), rng.uniform(0, 120))
        for i in range(n_recent)
    ]
    recent_output = [
        (recent_start + timedelta(days=i), rng.uniform(0, 250))
        for i in range(n_recent)
    ]

    all_input = old_input + recent_input
    all_output = old_output + recent_output

    results_unweighted = find_time_shifted_correlations(
        all_input, all_output, max_lag_days=0, min_samples=5,
        temporal_weighting=False, reference_date=ref,
    )
    results_weighted = find_time_shifted_correlations(
        all_input, all_output, max_lag_days=0, min_samples=5,
        temporal_weighting=True, reference_date=ref,
    )

    r_unweighted = results_unweighted[0].correlation_coefficient if results_unweighted else 0
    r_weighted = results_weighted[0].correlation_coefficient if results_weighted else 0

    assert abs(r_unweighted) > abs(r_weighted), (
        f"Temporal weighting should weaken old-only signal: "
        f"unweighted |r|={abs(r_unweighted):.3f} vs weighted |r|={abs(r_weighted):.3f}"
    )


def test_temporal_weighting_strengthens_recent_signal():
    """A correlation that exists only in recent data should strengthen with weighting.

    Construct data where the first 120 days are noise and the most recent
    30 days show strong positive correlation.  Temporal weighting (4x L30)
    should amplify the recent signal relative to unweighted.
    """
    ref = datetime(2026, 3, 29)
    n_old = 120
    n_recent = 30

    old_start = ref - timedelta(days=n_old + n_recent)
    recent_start = ref - timedelta(days=n_recent)

    import random
    rng = random.Random(99)
    old_input = [
        (old_start + timedelta(days=i), rng.uniform(0, 100))
        for i in range(n_old)
    ]
    old_output = [
        (old_start + timedelta(days=i), rng.uniform(0, 200))
        for i in range(n_old)
    ]

    recent_input = [
        (recent_start + timedelta(days=i), float(i))
        for i in range(n_recent)
    ]
    recent_output = [
        (recent_start + timedelta(days=i), float(i) * 3.0 + 5.0)
        for i in range(n_recent)
    ]

    all_input = old_input + recent_input
    all_output = old_output + recent_output

    results_unweighted = find_time_shifted_correlations(
        all_input, all_output, max_lag_days=0, min_samples=5,
        temporal_weighting=False, reference_date=ref,
    )
    results_weighted = find_time_shifted_correlations(
        all_input, all_output, max_lag_days=0, min_samples=5,
        temporal_weighting=True, reference_date=ref,
    )

    r_unweighted = results_unweighted[0].correlation_coefficient if results_unweighted else 0
    r_weighted = results_weighted[0].correlation_coefficient if results_weighted else 0

    assert abs(r_weighted) > abs(r_unweighted), (
        f"Temporal weighting should strengthen recent-only signal: "
        f"weighted |r|={abs(r_weighted):.3f} vs unweighted |r|={abs(r_unweighted):.3f}"
    )


def test_cs1_michael_analog_solved_limiter_weakens_below_cg1():
    """Michael's CS-1 scenario: strong historical r≈0.75 for long_run_ratio →
    pace_threshold, but no relationship in recent L90 data.

    Realistic data construction:
    - 70 old observations (beyond 180 days ago) where higher long run ratio
      correlates with faster threshold pace (r≈0.7), scatter not monotonic
    - 45 recent observations (L30 + L31-90) with no relationship — the athlete
      has solved the volume problem, long run ratio varies but threshold pace
      is stable

    With temporal weighting (L30=4x, L31-90=2x, beyond-180=0.75x), the 45
    recent noise points at high weight should dominate the 70 old points at
    low weight, dropping the weighted r below CG-1 (|r| < 0.30).
    """
    ref = datetime(2026, 3, 29)

    import random
    rng = random.Random(777)

    old_count = 70
    old_start = ref - timedelta(days=300)
    old_input = []
    old_output = []
    for i in range(old_count):
        d = old_start + timedelta(days=i * 2)
        lr_ratio = 0.22 + rng.gauss(0, 0.04)
        threshold_pace = 360 - 120 * lr_ratio + rng.gauss(0, 8)
        old_input.append((d, lr_ratio))
        old_output.append((d, threshold_pace))

    recent_count = 45
    recent_start = ref - timedelta(days=60)
    recent_input = []
    recent_output = []
    for i in range(recent_count):
        d = recent_start + timedelta(days=i)
        lr_ratio = 0.24 + rng.gauss(0, 0.04)
        threshold_pace = 330 + rng.gauss(0, 8)
        recent_input.append((d, lr_ratio))
        recent_output.append((d, threshold_pace))

    all_input = old_input + recent_input
    all_output = old_output + recent_output

    results_unweighted = find_time_shifted_correlations(
        all_input, all_output, max_lag_days=0, min_samples=5,
        temporal_weighting=False, reference_date=ref,
    )
    results_weighted = find_time_shifted_correlations(
        all_input, all_output, max_lag_days=0, min_samples=5,
        temporal_weighting=True, reference_date=ref,
    )

    r_unweighted = results_unweighted[0].correlation_coefficient if results_unweighted else 0
    r_weighted = results_weighted[0].correlation_coefficient if results_weighted else 0

    assert abs(r_unweighted) >= 0.30, (
        f"Unweighted should show historical signal above CG-1, got |r|={abs(r_unweighted):.3f}"
    )
    assert abs(r_weighted) < abs(r_unweighted), (
        f"Weighted should weaken solved-limiter signal: "
        f"unweighted={abs(r_unweighted):.3f} vs weighted={abs(r_weighted):.3f}"
    )
    assert abs(r_weighted) < 0.30, (
        f"Michael's CS-1 analog: solved limiter should drop below CG-1 gate (0.30), "
        f"got weighted |r|={abs(r_weighted):.3f}"
    )


def test_cs8_brian_analog_structural_trait_preserved():
    """Brian's CS-8 scenario: daily_session_stress → efficiency negative,
    stable across full history INCLUDING recent L90 data.

    With temporal weighting (0.75x beyond 180, 4x L30), the signal should
    remain strong because it is present in ALL time windows.  Structural
    traits must not be artificially suppressed by recency emphasis.

    The 0.75x beyond-180 weight was specifically set to preserve this.
    """
    ref = datetime(2026, 3, 29)

    import random
    rng = random.Random(888)

    total_days = 300
    start = ref - timedelta(days=total_days)
    all_input = [
        (start + timedelta(days=i), 50.0 + rng.gauss(0, 15))
        for i in range(total_days)
    ]
    all_output = [
        (start + timedelta(days=i), 0.90 - 0.001 * all_input[i][1] + rng.gauss(0, 0.01))
        for i in range(total_days)
    ]

    results_unweighted = find_time_shifted_correlations(
        all_input, all_output, max_lag_days=0, min_samples=5,
        temporal_weighting=False, reference_date=ref,
    )
    results_weighted = find_time_shifted_correlations(
        all_input, all_output, max_lag_days=0, min_samples=5,
        temporal_weighting=True, reference_date=ref,
    )

    r_unweighted = results_unweighted[0].correlation_coefficient if results_unweighted else 0
    r_weighted = results_weighted[0].correlation_coefficient if results_weighted else 0

    assert abs(r_unweighted) >= 0.50, (
        f"Unweighted should show strong structural signal, got |r|={abs(r_unweighted):.3f}"
    )
    assert abs(r_weighted) >= 0.50, (
        f"Brian's CS-8 analog: structural trait should remain strong under weighting, "
        f"got weighted |r|={abs(r_weighted):.3f}"
    )

    drift = abs(abs(r_unweighted) - abs(r_weighted))
    assert drift < 0.15, (
        f"Structural signal should not drift significantly: "
        f"unweighted={abs(r_unweighted):.3f}, weighted={abs(r_weighted):.3f}, drift={drift:.3f}"
    )
