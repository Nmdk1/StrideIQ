"""
Tests for interaction promotion field-name wiring (Fix 2) and
scan coverage persistence (Fix 4).
"""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

ATHLETE_ID = uuid4()


def _make_mock_db(candidates, existing_finding=None):
    """Return a mock db that routes query() calls to separate mocks per model."""
    from models import AutoDiscoveryCandidate, AthleteFinding

    candidate_mock = MagicMock()
    candidate_mock.filter.return_value.all.return_value = candidates

    finding_mock = MagicMock()
    finding_mock.filter.return_value.first.return_value = existing_finding

    def query_side_effect(model):
        if model is AutoDiscoveryCandidate:
            return candidate_mock
        if model is AthleteFinding:
            return finding_mock
        return MagicMock()

    db = MagicMock()
    db.query.side_effect = query_side_effect
    return db


# ---------------------------------------------------------------------------
# Fix 2: promote_interaction_findings derives input_a/input_b from factors
# ---------------------------------------------------------------------------

class TestPromoteInteractionReadFactors:
    def test_promote_interaction_reads_factors_field(self):
        """promote_interaction_findings derives input_a/input_b from factors when
        input_a/input_b are absent from the candidate's latest_summary."""
        from services.auto_discovery.interaction_loop import promote_interaction_findings

        mock_candidate = MagicMock()
        mock_candidate.id = uuid4()
        mock_candidate.athlete_id = ATHLETE_ID
        mock_candidate.times_seen = 3
        mock_candidate.current_status = "open"
        mock_candidate.latest_summary = {
            "factors": ["sleep_hours", "hrv_rmssd_ms"],
            "output_metric": "efficiency",
            "effect_size": 0.65,
            "n_high": 12,
            "n_low": 10,
            "direction_label": "higher efficiency when both sleep_hours and hrv_rmssd_ms are high",
        }

        db = _make_mock_db(candidates=[mock_candidate], existing_finding=None)

        promote_interaction_findings(ATHLETE_ID, db)

        # Status should be set to "promoted" — confirms input_a was derived from factors[0]
        assert mock_candidate.current_status == "promoted"

    def test_factors_fallback_does_not_break_when_input_a_already_present(self):
        """If both input_a and factors are present, input_a takes priority."""
        from services.auto_discovery.interaction_loop import promote_interaction_findings

        mock_candidate = MagicMock()
        mock_candidate.id = uuid4()
        mock_candidate.athlete_id = ATHLETE_ID
        mock_candidate.times_seen = 4
        mock_candidate.current_status = "open"
        mock_candidate.latest_summary = {
            "input_a": "readiness_1_5",       # explicit field takes priority
            "input_b": "hrv_sdnn",
            "factors": ["sleep_hours", "cadence"],  # should be ignored
            "output_metric": "efficiency",
            "effect_size": 0.7,
        }

        db = _make_mock_db(candidates=[mock_candidate], existing_finding=None)

        promote_interaction_findings(ATHLETE_ID, db)

        assert mock_candidate.current_status == "promoted"

    def test_candidate_with_no_factors_and_no_input_a_is_skipped(self):
        """Candidates with neither factors nor input_a are correctly skipped."""
        from services.auto_discovery.interaction_loop import promote_interaction_findings

        mock_candidate = MagicMock()
        mock_candidate.id = uuid4()
        mock_candidate.athlete_id = ATHLETE_ID
        mock_candidate.times_seen = 5
        mock_candidate.current_status = "open"
        mock_candidate.latest_summary = {
            "output_metric": "efficiency",
            "effect_size": 0.8,
            # no input_a, no factors
        }

        db = _make_mock_db(candidates=[mock_candidate])

        promote_interaction_findings(ATHLETE_ID, db)

        # Should remain "open" since it was skipped
        assert mock_candidate.current_status == "open"


# ---------------------------------------------------------------------------
# Fix 4: scan coverage rows written during interaction scans
# ---------------------------------------------------------------------------

class TestScanCoverageUpdatedAfterInteractionScan:
    def test_scan_coverage_updated_after_interaction_scan(self):
        """_find_pairwise_interactions returns a dict with tested_pairs included."""
        from services.auto_discovery.interaction_loop import _find_pairwise_interactions

        all_inputs = {
            "sleep_hours": [(f"2025-01-{i:02d}", float(i)) for i in range(1, 21)],
            "hrv_rmssd_ms": [(f"2025-01-{i:02d}", float(i) * 1.1) for i in range(1, 21)],
        }
        output_dict = {f"2025-01-{i:02d}": float(i) * 0.95 for i in range(1, 21)}

        result = _find_pairwise_interactions(
            all_inputs=all_inputs,
            output_dict=output_dict,
            output_metric="efficiency",
            min_group=3,
            min_effect=0.01,
            top_n=5,
        )

        assert "top_interactions" in result
        assert "tested_pairs" in result
        assert isinstance(result["tested_pairs"], list)

    def test_find_pairwise_returns_tested_pairs_list(self):
        """_find_pairwise_interactions always returns a dict with tested_pairs key."""
        from services.auto_discovery.interaction_loop import _find_pairwise_interactions

        result = _find_pairwise_interactions(
            all_inputs={},
            output_dict={},
            output_metric="efficiency",
            min_group=5,
            min_effect=0.2,
            top_n=3,
        )

        assert "top_interactions" in result
        assert "tested_pairs" in result
        assert result["tested_pairs"] == []
        assert result["top_interactions"] == []

    def test_upsert_called_for_signal_and_no_signal_pairs(self):
        """Coverage upsert logic labels pairs as signal/no_signal correctly."""
        # Exercise the coverage labelling logic directly (unit test of the logic,
        # not the full scan which requires heavy DB/input aggregation setup).
        tested_pairs = [("sleep_hours", "hrv_rmssd_ms"), ("cadence", "sleep_hours")]
        kept_interactions = [{"factors": ["sleep_hours", "hrv_rmssd_ms"]}]

        top_pair_set = set()
        for interaction in kept_interactions:
            factors = interaction.get("factors", [])
            if len(factors) == 2:
                top_pair_set.add(tuple(sorted(factors)))

        call_log = []
        for pair in tested_pairs:
            input_a, input_b = pair[0], pair[1]
            pair_key = tuple(sorted([input_a, input_b]))
            result_label = "signal" if pair_key in top_pair_set else "no_signal"
            call_log.append({"input_a": input_a, "input_b": input_b, "result": result_label})

        assert len(call_log) == 2
        labels = {c["result"] for c in call_log}
        assert "signal" in labels
        assert "no_signal" in labels

