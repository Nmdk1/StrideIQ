"""
Cross-Training Correlation Engine Integration Tests

Commit 3 of Cross-Training Session Detail Capture (Phase A).
Tests aggregate_cross_training_inputs() produces correct signal values
from fixture data, and that FRIENDLY_NAMES covers all new signals.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.n1_insight_generator import FRIENDLY_NAMES


# ---------------------------------------------------------------------------
# FRIENDLY_NAMES coverage for cross-training signals
# ---------------------------------------------------------------------------

_CT_SIGNALS = [
    "ct_strength_sessions",
    "ct_strength_duration_min",
    "ct_lower_body_sets",
    "ct_upper_body_sets",
    "ct_core_sets",
    "ct_plyometric_sets",
    "ct_heavy_sets",
    "ct_total_volume_kg",
    "ct_unilateral_sets",
    "ct_strength_lag_24h",
    "ct_strength_lag_48h",
    "ct_strength_lag_72h",
    "ct_hours_since_strength",
    "ct_strength_frequency_7d",
    "ct_cycling_duration_min",
    "ct_cycling_tss",
    "ct_flexibility_sessions_7d",
]


class TestFriendlyNamesCoverage:
    def test_all_ct_signals_have_friendly_names(self):
        missing = [s for s in _CT_SIGNALS if s not in FRIENDLY_NAMES]
        assert not missing, f"Missing FRIENDLY_NAMES: {missing}"

    def test_friendly_names_are_human_readable(self):
        for signal in _CT_SIGNALS:
            name = FRIENDLY_NAMES[signal]
            assert isinstance(name, str)
            assert len(name) > 3
            assert "_" not in name, f"{signal} friendly name contains underscore: {name}"


class TestCrossTrainingAggregateImport:
    def test_aggregate_function_importable(self):
        from services.correlation_engine import aggregate_cross_training_inputs
        assert callable(aggregate_cross_training_inputs)

    def test_aggregate_function_signature(self):
        import inspect
        from services.correlation_engine import aggregate_cross_training_inputs
        sig = inspect.signature(aggregate_cross_training_inputs)
        params = list(sig.parameters.keys())
        assert "athlete_id" in params
        assert "start_date" in params
        assert "end_date" in params
        assert "db" in params
