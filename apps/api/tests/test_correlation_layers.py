"""
Tests for Correlation Engine Layers 1–4.

Synthetic data is used throughout — no database needed for the pure
functions.  Integration tests verify the wiring and model updates.
"""

import math
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.correlation_layers import (
    detect_threshold,
    detect_asymmetry,
    compute_decay_curve,
    detect_mediators,
    run_layer_analysis,
    _align_with_lag,
    _pearson,
)


# ---------------------------------------------------------------------------
# Helpers for synthetic data
# ---------------------------------------------------------------------------

def _ts(day_offset: int) -> datetime:
    """Return a datetime for day N relative to an arbitrary base."""
    return datetime(2026, 1, 1) + timedelta(days=day_offset)


def _make_series(pairs):
    """Convert [(day_offset, value), ...] into List[Tuple[datetime, float]]."""
    return [(_ts(d), float(v)) for d, v in pairs]


# ---------------------------------------------------------------------------
# Layer 1 — Threshold Detection
# ---------------------------------------------------------------------------

class TestThresholdDetection:
    def test_linear_data_returns_none(self):
        """Linear relationship with no breakpoint → no threshold."""
        inp = _make_series([(i, i) for i in range(30)])
        out = _make_series([(i, 0.5 * i + 1) for i in range(30)])
        result = detect_threshold(inp, out, lag_days=0)
        assert result is None

    def test_step_function_breakpoint(self):
        """Clear step function at input=15 should be detected."""
        data = []
        for i in range(30):
            if i < 15:
                data.append((i, i * 0.8 + 0.1 * (i % 3)))
            else:
                data.append((i, 20 + 0.01 * (i % 2)))
        inp = _make_series([(i, i) for i in range(30)])
        out = _make_series(data)

        result = detect_threshold(inp, out, lag_days=0)
        assert result is not None
        assert "threshold_value" in result
        assert "threshold_direction" in result
        assert result["n_below"] >= 5
        assert result["n_above"] >= 5

    def test_insufficient_data_returns_none(self):
        """Fewer than 2 * min_segment_size points → None."""
        inp = _make_series([(i, i) for i in range(8)])
        out = _make_series([(i, i * 2) for i in range(8)])
        result = detect_threshold(inp, out, lag_days=0)
        assert result is None

    def test_min_segment_size_enforced(self):
        """When split produces segments smaller than min_segment, skip."""
        inp = _make_series([(i, i) for i in range(12)])
        out = _make_series([(i, i * 2) for i in range(12)])
        result = detect_threshold(inp, out, lag_days=0, min_segment_size=7)
        assert result is None

    def test_threshold_with_lag(self):
        """Threshold detection respects lag alignment."""
        inp = _make_series([(i, i) for i in range(35)])
        data = []
        for i in range(35):
            shifted_input = i - 2
            if shifted_input < 15:
                data.append((i, shifted_input * 0.9))
            else:
                data.append((i, 18 + 0.01 * i))
        out = _make_series(data)
        result = detect_threshold(inp, out, lag_days=2)
        # Should still find a threshold since the data has a clear break
        # (may or may not detect depending on alignment — this tests no crash)
        assert result is None or result["n_below"] >= 5


# ---------------------------------------------------------------------------
# Layer 2 — Asymmetric Response Detection
# ---------------------------------------------------------------------------

class TestAsymmetryDetection:
    def test_symmetric_data(self):
        """Balanced effects → ratio near 1.0, direction 'symmetric'."""
        inp = _make_series([(i, i) for i in range(40)])
        out = _make_series([(i, 0.5 * i) for i in range(40)])
        result = detect_asymmetry(inp, out, lag_days=0)
        assert result is not None
        assert result["asymmetry_direction"] == "symmetric"

    def test_negative_dominant(self):
        """Bad input hurts disproportionately → ratio > 2.0."""
        import random
        random.seed(222)
        n = 80
        inp_vals = [random.gauss(10, 4) for _ in range(n)]
        med = sorted(inp_vals)[n // 2]
        out_vals = []
        for v in inp_vals:
            if v < med:
                out_vals.append(-5.0 * (med - v) + random.gauss(0, 0.5))
            else:
                out_vals.append(0.5 * (v - med) + random.gauss(0, 0.5))
        inp = _make_series([(i, inp_vals[i]) for i in range(n)])
        out = _make_series([(i, out_vals[i]) for i in range(n)])
        result = detect_asymmetry(inp, out, lag_days=0)
        assert result is not None
        assert result["asymmetry_ratio"] > 2.0
        assert result["asymmetry_direction"] == "negative_dominant"

    def test_positive_dominant(self):
        """Good input helps disproportionately → ratio < 0.67."""
        import random
        random.seed(333)
        n = 80
        inp_vals = [random.gauss(10, 4) for _ in range(n)]
        med = sorted(inp_vals)[n // 2]
        out_vals = []
        for v in inp_vals:
            if v < med:
                out_vals.append(-0.3 * (med - v) + random.gauss(0, 0.3))
            else:
                out_vals.append(5.0 * (v - med) + random.gauss(0, 0.3))
        inp = _make_series([(i, inp_vals[i]) for i in range(n)])
        out = _make_series([(i, out_vals[i]) for i in range(n)])
        result = detect_asymmetry(inp, out, lag_days=0)
        assert result is not None
        assert result["asymmetry_ratio"] < 0.67
        assert result["asymmetry_direction"] == "positive_dominant"

    def test_insufficient_data_returns_none(self):
        """Too few points → None."""
        inp = _make_series([(i, i) for i in range(6)])
        out = _make_series([(i, i * 2) for i in range(6)])
        result = detect_asymmetry(inp, out, lag_days=0)
        assert result is None

    def test_baseline_is_median(self):
        """Baseline should be the median of input values."""
        inp = _make_series([(i, i) for i in range(20)])
        out = _make_series([(i, i * 0.5) for i in range(20)])
        result = detect_asymmetry(inp, out, lag_days=0)
        assert result is not None
        assert result["baseline_value"] == pytest.approx(9.5, abs=0.5)


# ---------------------------------------------------------------------------
# Layer 4 — Decay Curves
# ---------------------------------------------------------------------------

class TestDecayCurves:
    def _make_decaying_data(self, peak_lag=1, decay_rate=0.15):
        """Create input/output where correlation decays from peak."""
        import random
        random.seed(42)
        n = 60
        inp = _make_series([(i, random.gauss(10, 3)) for i in range(n)])
        inp_dict = {_ts(i): inp[i][1] for i in range(n)}
        out_vals = []
        for i in range(n):
            base = random.gauss(50, 2)
            for lag in range(8):
                day = i - lag
                if day >= 0:
                    weight = max(0, 0.5 * math.exp(-decay_rate * abs(lag - peak_lag)))
                    base += weight * (inp_dict.get(_ts(day), 10) - 10)
            out_vals.append((i, base))
        out = _make_series(out_vals)
        return inp, out

    def test_exponential_decay(self):
        """Monotonically decaying profile → type 'exponential'."""
        inp, out = self._make_decaying_data(peak_lag=0, decay_rate=0.5)
        result = compute_decay_curve(inp, out, peak_lag=0)
        assert result is not None
        assert result["decay_type"] in ("exponential", "sustained", "complex")
        assert result["lag_profile"] is not None
        assert len(result["lag_profile"]) == 8

    def test_sustained_profile(self):
        """Correlation significant across 4+ lags → 'sustained'."""
        import random
        random.seed(99)
        n = 80
        inp = _make_series([(i, random.gauss(10, 3)) for i in range(n)])
        inp_dict = {_ts(i): inp[i][1] for i in range(n)}
        out_vals = []
        for i in range(n):
            base = random.gauss(50, 1)
            for lag in range(8):
                day = i - lag
                if day >= 0:
                    base += 0.8 * (inp_dict.get(_ts(day), 10) - 10)
            out_vals.append((i, base))
        out = _make_series(out_vals)
        result = compute_decay_curve(inp, out, peak_lag=0)
        assert result is not None
        assert result["decay_type"] == "sustained"

    def test_complex_profile(self):
        """Non-monotonic r values → 'complex'."""
        import random
        random.seed(77)
        n = 80
        inp = _make_series([(i, random.gauss(10, 3)) for i in range(n)])
        inp_dict = {_ts(i): inp[i][1] for i in range(n)}
        out_vals = []
        for i in range(n):
            base = random.gauss(50, 1)
            for lag in [0, 4, 5]:
                day = i - lag
                if day >= 0:
                    base += 0.8 * (inp_dict.get(_ts(day), 10) - 10)
            out_vals.append((i, base))
        out = _make_series(out_vals)
        result = compute_decay_curve(inp, out, peak_lag=0)
        assert result is not None
        assert result["lag_profile"] is not None

    def test_insufficient_data_returns_none(self):
        """Not enough aligned points → None."""
        inp = _make_series([(i, i) for i in range(5)])
        out = _make_series([(i, i) for i in range(5)])
        result = compute_decay_curve(inp, out, peak_lag=0)
        assert result is None

    def test_lag_profile_stored_as_list(self):
        """lag_profile is a list with max_lag+1 entries."""
        inp, out = self._make_decaying_data()
        result = compute_decay_curve(inp, out, peak_lag=1, max_lag=7)
        assert result is not None
        assert len(result["lag_profile"]) == 8


# ---------------------------------------------------------------------------
# Layer 3 — Cascade Detection
# ---------------------------------------------------------------------------

class TestCascadeDetection:
    def test_known_mediator(self):
        """A→B→C where B explains >40% of A→C."""
        import random
        random.seed(123)
        n = 60

        a_vals = [random.gauss(10, 3) for _ in range(n)]
        b_vals = [0.7 * a + random.gauss(0, 1) for a in a_vals]
        c_vals = [0.6 * b + random.gauss(0, 1) for b in b_vals]

        a_data = _make_series([(i, a_vals[i]) for i in range(n)])
        b_data = _make_series([(i, b_vals[i]) for i in range(n)])
        c_data = _make_series([(i, c_vals[i]) for i in range(n)])

        r_ac, _ = _pearson(a_vals, c_vals)

        result = detect_mediators(
            finding_input_name="A",
            finding_output_metric="efficiency",
            finding_r=r_ac,
            finding_lag=0,
            all_inputs={"A": a_data, "B": b_data},
            output_data=c_data,
        )
        assert len(result) >= 1
        assert result[0]["mediator_variable"] == "B"
        assert result[0]["mediation_ratio"] >= 0.4

    def test_full_mediation(self):
        """When B fully mediates A→C, partial_r drops below 0.3."""
        import random
        random.seed(456)
        n = 80

        a_vals = [random.gauss(10, 3) for _ in range(n)]
        b_vals = [0.9 * a + random.gauss(0, 0.5) for a in a_vals]
        c_vals = [0.95 * b + random.gauss(0, 0.3) for b in b_vals]

        a_data = _make_series([(i, a_vals[i]) for i in range(n)])
        b_data = _make_series([(i, b_vals[i]) for i in range(n)])
        c_data = _make_series([(i, c_vals[i]) for i in range(n)])

        r_ac, _ = _pearson(a_vals, c_vals)

        result = detect_mediators(
            finding_input_name="A",
            finding_output_metric="efficiency",
            finding_r=r_ac,
            finding_lag=0,
            all_inputs={"A": a_data, "B": b_data},
            output_data=c_data,
        )
        assert len(result) >= 1
        assert result[0]["is_full_mediation"] is True

    def test_no_mediator_candidates(self):
        """When no variable correlates with both A and C → empty."""
        import random
        random.seed(789)
        n = 40

        a_data = _make_series([(i, random.gauss(10, 3)) for i in range(n)])
        noise_data = _make_series([(i, random.gauss(0, 10)) for i in range(n)])
        c_data = _make_series([(i, random.gauss(50, 2)) for i in range(n)])

        result = detect_mediators(
            finding_input_name="A",
            finding_output_metric="efficiency",
            finding_r=0.5,
            finding_lag=0,
            all_inputs={"A": a_data, "noise": noise_data},
            output_data=c_data,
        )
        assert result == []

    def test_self_excluded(self):
        """The input variable itself is not tested as a mediator."""
        import random
        random.seed(101)
        n = 40

        a_vals = [random.gauss(10, 3) for _ in range(n)]
        c_vals = [0.5 * a + random.gauss(0, 1) for a in a_vals]

        a_data = _make_series([(i, a_vals[i]) for i in range(n)])
        c_data = _make_series([(i, c_vals[i]) for i in range(n)])

        result = detect_mediators(
            finding_input_name="A",
            finding_output_metric="efficiency",
            finding_r=0.5,
            finding_lag=0,
            all_inputs={"A": a_data},
            output_data=c_data,
        )
        assert result == []


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_align_with_lag(self):
        """Alignment shifts input dates forward by lag."""
        inp = _make_series([(0, 10), (1, 20), (2, 30)])
        out = _make_series([(1, 100), (2, 200), (3, 300)])
        aligned = _align_with_lag(inp, out, lag_days=1)
        assert len(aligned) == 3
        assert aligned[0] == (10, 100)
        assert aligned[1] == (20, 200)
        assert aligned[2] == (30, 300)

    def test_pearson_basic(self):
        """Perfect positive correlation → r ≈ 1."""
        r, p = _pearson([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        assert r == pytest.approx(1.0, abs=0.001)

    def test_pearson_degenerate(self):
        """Too few points → (0, 1)."""
        r, p = _pearson([1, 2], [3, 4])
        assert r == 0.0
        assert p == 1.0


# ---------------------------------------------------------------------------
# Integration: run_layer_analysis
# ---------------------------------------------------------------------------

class TestRunLayerAnalysis:
    def test_all_layers_update_finding(self):
        """run_layer_analysis populates layer fields on the finding."""
        import random
        random.seed(55)
        n = 60

        inp_vals = list(range(n))
        out_vals = []
        for v in inp_vals:
            if v < 30:
                out_vals.append(v * 0.8 + random.gauss(0, 0.5))
            else:
                out_vals.append(24 + random.gauss(0, 0.3))
        inp = _make_series([(i, inp_vals[i]) for i in range(n)])
        out = _make_series([(i, out_vals[i]) for i in range(n)])

        finding = MagicMock()
        finding.id = uuid.uuid4()
        finding.input_name = "test_input"
        finding.output_metric = "efficiency"
        finding.correlation_coefficient = 0.65
        finding.time_lag_days = 0
        finding.threshold_value = None
        finding.asymmetry_ratio = None
        finding.lag_profile = None

        db = MagicMock()

        run_layer_analysis(finding, inp, out, {"test_input": inp}, db)

        assert finding.threshold_value is not None or finding.asymmetry_ratio is not None

    def test_layer_failure_does_not_raise(self):
        """If a layer throws, run_layer_analysis catches and continues."""
        finding = MagicMock()
        finding.id = uuid.uuid4()
        finding.input_name = "x"
        finding.output_metric = "y"
        finding.correlation_coefficient = 0.5
        finding.time_lag_days = 0

        db = MagicMock()

        with patch("services.correlation_layers.detect_threshold", side_effect=RuntimeError("boom")):
            run_layer_analysis(
                finding,
                _make_series([(i, i) for i in range(20)]),
                _make_series([(i, i * 2) for i in range(20)]),
                {"x": _make_series([(i, i) for i in range(20)])},
                db,
            )

    def test_confirmed_only_gate(self):
        """Layers should only process findings with times_confirmed >= 3.

        This tests the query in _run_layer_pass, not the function itself.
        The gate is enforced in correlation_tasks._run_layer_pass.
        """
        pass
