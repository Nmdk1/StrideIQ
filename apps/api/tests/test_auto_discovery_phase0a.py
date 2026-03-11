"""
Tests for AutoDiscovery Phase 0A.

Covers:
1. FQS adapters — component outputs and component_quality labels.
2. InvestigationSpec extension — pilot shadow metadata.
3. Feature flag gating — can disable without code changes.
4. Integration run — run row, experiment rows, report sections, no-surface
   guarantee, no-production-mutation guarantee.

DB-backed tests use the conftest.py transactional rollback fixture.
Non-DB tests are pure unit tests.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
#  Helper builders for stub models
# ─────────────────────────────────────────────────────────────────────────────

def _make_correlation_finding(**kwargs) -> MagicMock:
    """Build a stub CorrelationFinding-like object for FQS tests."""
    defaults = {
        "times_confirmed": 5,
        "last_confirmed_at": datetime.now(timezone.utc),
        "is_active": True,
        "threshold_value": 7.5,
        "asymmetry_ratio": 1.3,
        "decay_half_life_days": 14.0,
        "time_lag_days": 2,
        "sample_size": 25,
        "input_name": "sleep_hours",
        "output_metric": "efficiency",
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_athlete_finding(**kwargs) -> MagicMock:
    """Build a stub AthleteFinding-like object for FQS tests."""
    now = datetime.now(timezone.utc)
    defaults = {
        "confidence": "genuine",
        "last_confirmed_at": now,
        "first_detected_at": now - timedelta(days=45),
        "is_active": True,
        "receipts": {"pace": 1, "hr": 2, "weather": 3},
        "sentence": "When your sleep exceeds 7h you run 8% faster at equivalent heart rate.",
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# ─────────────────────────────────────────────────────────────────────────────
#  1. FQS Adapters — CorrelationFindingFQSAdapter
# ─────────────────────────────────────────────────────────────────────────────

class TestCorrelationFindingFQSAdapter:
    """Validate the CorrelationFindingFQSAdapter interface and quality labels."""

    def setup_method(self):
        from services.auto_discovery.fqs_adapters import CorrelationFindingFQSAdapter
        self.adapter = CorrelationFindingFQSAdapter()

    def test_returns_required_schema_keys(self):
        finding = _make_correlation_finding()
        result = self.adapter.score(finding)
        assert "origin" in result
        assert "base_score" in result
        assert "final_score" in result
        assert "components" in result
        assert "component_quality" in result

    def test_origin_is_correlation(self):
        result = self.adapter.score(_make_correlation_finding())
        assert result["origin"] == "correlation"

    def test_component_quality_labels_correct(self):
        result = self.adapter.score(_make_correlation_finding())
        cq = result["component_quality"]
        assert cq["confidence"] == "exact"
        assert cq["specificity"] == "inferred"
        assert cq["actionability"] == "registry_default"
        assert cq["stability"] == "inferred"

    def test_all_component_keys_present(self):
        result = self.adapter.score(_make_correlation_finding())
        comps = result["components"]
        for key in ("confidence", "specificity", "actionability", "stability", "cascade_bonus"):
            assert key in comps, f"Missing component: {key}"

    def test_final_score_bounded_0_1(self):
        result = self.adapter.score(_make_correlation_finding())
        assert 0.0 <= result["final_score"] <= 1.0
        assert 0.0 <= result["base_score"] <= 1.0

    def test_inactive_finding_penalises_confidence(self):
        active_r = self.adapter.score(_make_correlation_finding(is_active=True))
        inactive_r = self.adapter.score(_make_correlation_finding(is_active=False))
        assert active_r["components"]["confidence"] > inactive_r["components"]["confidence"]

    def test_cascade_bonus_requires_all_three_layers(self):
        # All three layers populated → bonus > 0.
        full = _make_correlation_finding(
            threshold_value=7.0,
            asymmetry_ratio=1.2,
            decay_half_life_days=10.0,
        )
        partial = _make_correlation_finding(
            threshold_value=7.0,
            asymmetry_ratio=None,
            decay_half_life_days=None,
        )
        assert self.adapter.score(full)["components"]["cascade_bonus"] > 0
        assert self.adapter.score(partial)["components"]["cascade_bonus"] == 0.0

    def test_old_finding_has_lower_score_than_recent(self):
        old_date = datetime.now(timezone.utc) - timedelta(days=400)
        recent = self.adapter.score(_make_correlation_finding())
        old = self.adapter.score(_make_correlation_finding(last_confirmed_at=old_date, is_active=False))
        assert recent["final_score"] > old["final_score"]


# ─────────────────────────────────────────────────────────────────────────────
#  2. FQS Adapters — AthleteFindingFQSAdapter
# ─────────────────────────────────────────────────────────────────────────────

class TestAthleteFindingFQSAdapter:
    """Validate the AthleteFindingFQSAdapter interface and quality labels."""

    def setup_method(self):
        from services.auto_discovery.fqs_adapters import AthleteFindingFQSAdapter
        self.adapter = AthleteFindingFQSAdapter()

    def test_returns_required_schema_keys(self):
        result = self.adapter.score(_make_athlete_finding())
        for key in ("origin", "base_score", "final_score", "components", "component_quality"):
            assert key in result

    def test_origin_is_investigation(self):
        result = self.adapter.score(_make_athlete_finding())
        assert result["origin"] == "investigation"

    def test_component_quality_labels_correct(self):
        cq = self.adapter.score(_make_athlete_finding())["component_quality"]
        assert cq["confidence"] == "inferred"
        assert cq["specificity"] == "inferred"
        assert cq["actionability"] == "registry_default"
        assert cq["stability"] == "inferred"

    def test_genuine_confidence_scores_higher_than_suggestive(self):
        genuine = self.adapter.score(_make_athlete_finding(confidence="genuine"))
        suggestive = self.adapter.score(_make_athlete_finding(confidence="suggestive"))
        assert genuine["components"]["confidence"] > suggestive["components"]["confidence"]

    def test_superseded_finding_has_low_stability(self):
        active = self.adapter.score(_make_athlete_finding(is_active=True))
        superseded = self.adapter.score(_make_athlete_finding(is_active=False))
        assert active["components"]["stability"] > superseded["components"]["stability"]

    def test_richer_receipts_score_higher_specificity(self):
        rich = _make_athlete_finding(receipts={str(i): i for i in range(6)})
        sparse = _make_athlete_finding(receipts={"one": 1})
        rich_r = self.adapter.score(rich)
        sparse_r = self.adapter.score(sparse)
        assert rich_r["components"]["specificity"] > sparse_r["components"]["specificity"]

    def test_final_score_bounded_0_1(self):
        result = self.adapter.score(_make_athlete_finding())
        assert 0.0 <= result["final_score"] <= 1.0

    def test_cascade_bonus_is_zero_in_phase_0(self):
        result = self.adapter.score(_make_athlete_finding())
        assert result["components"]["cascade_bonus"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  3. InvestigationSpec — pilot shadow metadata
# ─────────────────────────────────────────────────────────────────────────────

class TestInvestigationSpecPilotMetadata:
    """Verify Phase-0 shadow metadata was applied to the pilot subset."""

    def test_pilot_subset_count(self):
        from services.race_input_analysis import INVESTIGATION_REGISTRY
        pilot = [s for s in INVESTIGATION_REGISTRY if s.shadow_enabled]
        assert 4 <= len(pilot) <= 6, f"Pilot count out of range: {len(pilot)}"

    def test_pilot_specs_have_tunable_params(self):
        from services.race_input_analysis import INVESTIGATION_REGISTRY
        for spec in INVESTIGATION_REGISTRY:
            if spec.shadow_enabled:
                assert len(spec.tunable_params) >= 1, (
                    f"{spec.name} is shadow_enabled but has no tunable_params"
                )

    def test_pilot_specs_have_actionability_class(self):
        from services.race_input_analysis import INVESTIGATION_REGISTRY, InvestigationSpec
        valid = {"controllable", "environmental", "mixed"}
        for spec in INVESTIGATION_REGISTRY:
            if spec.shadow_enabled:
                assert spec.actionability_class in valid

    def test_non_pilot_specs_have_shadow_disabled(self):
        from services.race_input_analysis import INVESTIGATION_REGISTRY
        pilot_names = {s.name for s in INVESTIGATION_REGISTRY if s.shadow_enabled}
        for spec in INVESTIGATION_REGISTRY:
            if spec.name not in pilot_names:
                assert not spec.shadow_enabled

    def test_runtime_cost_hint_values_valid(self):
        from services.race_input_analysis import INVESTIGATION_REGISTRY
        valid = {"low", "medium", "high"}
        for spec in INVESTIGATION_REGISTRY:
            if spec.shadow_enabled:
                assert spec.runtime_cost_hint in valid


# ─────────────────────────────────────────────────────────────────────────────
#  4. Feature flag gating
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoDiscoveryFeatureFlags:
    """Verify gating helpers respect flag state without hardcoded logic."""

    def _make_flag_service(self, enabled: bool, allowed_ids=None):
        """Return a mock FeatureFlagService that returns the given state."""
        svc = MagicMock()
        svc.is_enabled.return_value = enabled
        flag_data = {"enabled": enabled, "allowed_athlete_ids": allowed_ids or []}
        svc._get_flag.return_value = flag_data
        return svc

    def test_disabled_flag_returns_false_for_system(self):
        db = MagicMock()
        with patch("services.auto_discovery.feature_flags.is_feature_enabled", return_value=False):
            from services.auto_discovery.feature_flags import is_auto_discovery_enabled
            assert not is_auto_discovery_enabled("some-athlete", db)

    def test_enabled_flag_returns_true_for_system(self):
        db = MagicMock()
        with patch("services.auto_discovery.feature_flags.is_feature_enabled", return_value=True):
            from services.auto_discovery.feature_flags import is_auto_discovery_enabled
            assert is_auto_discovery_enabled("some-athlete", db)

    def test_rescan_requires_both_system_and_loop_enabled(self):
        """Rescan should only be True when both master and loop flags are True."""
        db = MagicMock()
        # Both enabled
        with patch("services.auto_discovery.feature_flags.is_feature_enabled", return_value=True):
            from services.auto_discovery.feature_flags import is_rescan_enabled
            assert is_rescan_enabled("athlete", db)

    def test_rescan_false_when_system_disabled(self):
        db = MagicMock()
        # Master off → rescan off regardless of loop flag
        call_count = [0]
        def _flag(key, athlete_id, db_):
            call_count[0] += 1
            # System flag disabled, loop flag enabled
            return key != "auto_discovery.enabled"
        with patch("services.auto_discovery.feature_flags.is_feature_enabled", side_effect=_flag):
            from services.auto_discovery.feature_flags import is_rescan_enabled
            assert not is_rescan_enabled("athlete", db)

    def test_live_mutation_always_false_in_phase_0(self):
        db = MagicMock()
        with patch("services.auto_discovery.feature_flags.is_feature_enabled", return_value=True):
            from services.auto_discovery.feature_flags import is_live_mutation_enabled
            assert not is_live_mutation_enabled("athlete", db)

    def test_athlete_surfacing_always_false_in_phase_0(self):
        db = MagicMock()
        with patch("services.auto_discovery.feature_flags.is_feature_enabled", return_value=True):
            from services.auto_discovery.feature_flags import is_athlete_surfacing_enabled
            assert not is_athlete_surfacing_enabled("athlete", db)

    def test_seed_flags_all_disabled_by_default(self):
        from services.auto_discovery.feature_flags import SEED_FLAGS
        for flag in SEED_FLAGS:
            assert not flag["enabled"], f"Flag {flag['key']} should default to disabled"
            assert flag["rollout_percentage"] == 0


# ─────────────────────────────────────────────────────────────────────────────
#  5. Integration — run, experiment rows, report sections, guarantees
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoDiscoveryIntegration:
    """
    Integration tests for the orchestrator.

    These are DB-backed and depend on the conftest transactional fixture.
    They mock the rescan loop to avoid network/data requirements in CI.
    """

    @pytest.fixture
    def mock_rescan_results(self):
        """Stub rescan loop results — one window, no real DB queries."""
        return [
            {
                "loop_type": "correlation_rescan",
                "target_name": "multiwindow:90d",
                "baseline_config": {"window_days": 90, "window_label": "90d"},
                "candidate_config": {},
                "result_summary": {
                    "window_label": "90d",
                    "findings_by_metric": {
                        "efficiency": [
                            {"input_name": "sleep_hours", "correlation_coefficient": 0.45,
                             "p_value": 0.01, "sample_size": 22, "direction": "positive"},
                        ]
                    },
                    "total_findings": 1,
                    "error": None,
                },
                "failure_reason": None,
                "runtime_ms": 250,
            }
        ]

    def test_run_creates_run_row(self, db_session, test_athlete, mock_rescan_results):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete
        from models import AutoDiscoveryRun

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan",
                   return_value=mock_rescan_results):
            with patch.object(db_session, "rollback"):  # neutralise rollback in test txn
                run = run_auto_discovery_for_athlete(
                    athlete_id=test_athlete.id,
                    db=db_session,
                    enabled_loops=["correlation_rescan"],
                )

        assert run.id is not None
        assert str(run.athlete_id) == str(test_athlete.id)
        assert run.status in ("completed", "partial")

    def test_run_creates_experiment_rows(self, db_session, test_athlete, mock_rescan_results):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete
        from models import AutoDiscoveryExperiment

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan",
                   return_value=mock_rescan_results):
            with patch.object(db_session, "rollback"):
                run = run_auto_discovery_for_athlete(
                    athlete_id=test_athlete.id,
                    db=db_session,
                    enabled_loops=["correlation_rescan"],
                )

        experiments = db_session.query(AutoDiscoveryExperiment).filter_by(run_id=run.id).all()
        assert len(experiments) >= 1

    def test_run_report_has_all_required_sections(self, db_session, test_athlete, mock_rescan_results):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan",
                   return_value=mock_rescan_results):
            with patch.object(db_session, "rollback"):
                run = run_auto_discovery_for_athlete(
                    athlete_id=test_athlete.id,
                    db=db_session,
                    enabled_loops=["correlation_rescan"],
                )

        report = run.report
        required_sections = [
            "stable_findings",
            "strengthened_findings",
            "candidate_interactions",
            "registry_tuning_candidates",
            "discarded_experiments",
            "score_summary",
            "no_surface_guarantee",
        ]
        for section in required_sections:
            assert section in report, f"Report missing required section: {section}"

    def test_no_surface_guarantee_is_false(self, db_session, test_athlete, mock_rescan_results):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan",
                   return_value=mock_rescan_results):
            with patch.object(db_session, "rollback"):
                run = run_auto_discovery_for_athlete(
                    athlete_id=test_athlete.id,
                    db=db_session,
                    enabled_loops=["correlation_rescan"],
                )

        guarantee = run.report["no_surface_guarantee"]
        assert guarantee["athlete_facing_surfaces_mutated"] is False
        assert guarantee["production_registry_values_mutated"] is False
        assert guarantee["live_mutation_enabled"] is False

    def test_no_correlation_finding_rows_committed(self, db_session, test_athlete, mock_rescan_results):
        """
        Verify that the shadow run does not commit rows to correlation_finding.
        We spy on db_session.add and assert CorrelationFinding is never added.
        """
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete
        from models import CorrelationFinding

        added_types = []
        original_add = db_session.add

        def _spying_add(obj):
            added_types.append(type(obj).__name__)
            return original_add(obj)

        db_session.add = _spying_add

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan",
                   return_value=mock_rescan_results):
            with patch.object(db_session, "rollback"):
                run_auto_discovery_for_athlete(
                    athlete_id=test_athlete.id,
                    db=db_session,
                    enabled_loops=["correlation_rescan"],
                )

        db_session.add = original_add
        assert "CorrelationFinding" not in added_types, (
            "CorrelationFinding rows should never be committed by the orchestrator"
        )

    def test_experiment_rows_contain_required_fields(self, db_session, test_athlete, mock_rescan_results):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete
        from models import AutoDiscoveryExperiment

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan",
                   return_value=mock_rescan_results):
            with patch.object(db_session, "rollback"):
                run = run_auto_discovery_for_athlete(
                    athlete_id=test_athlete.id,
                    db=db_session,
                    enabled_loops=["correlation_rescan"],
                )

        exp = db_session.query(AutoDiscoveryExperiment).filter_by(run_id=run.id).first()
        assert exp is not None
        assert exp.loop_type == "correlation_rescan"
        assert exp.target_name is not None
        assert exp.baseline_config is not None
        assert exp.result_summary is not None


# ─────────────────────────────────────────────────────────────────────────────
#  6. Window stability classification
# ─────────────────────────────────────────────────────────────────────────────

class TestWindowStabilityClassification:
    """Unit tests for the stability summarizer — no DB needed."""

    def _make_results(self, windows_with_findings: Dict[str, list]) -> list:
        """Build mock experiment results for given window labels."""
        results = []
        for label, findings in windows_with_findings.items():
            results.append({
                "loop_type": "correlation_rescan",
                "target_name": f"multiwindow:{label}",
                "baseline_config": {},
                "candidate_config": {},
                "result_summary": {
                    "window_label": label,
                    "findings_by_metric": {"efficiency": findings},
                    "total_findings": len(findings),
                    "error": None,
                },
                "failure_reason": None,
                "runtime_ms": 100,
            })
        return results

    def test_stable_finding_appears_in_all_windows(self):
        from services.auto_discovery.rescan_loop import summarize_window_stability
        finding = {"input_name": "sleep_hours"}
        results = self._make_results({
            "30d": [finding],
            "60d": [finding],
            "90d": [finding],
            "180d": [finding],
            "365d": [finding],
            "full_history": [finding],
        })
        summary = summarize_window_stability(results)
        stable_inputs = [s["input"] for s in summary["stable"]]
        assert "sleep_hours" in stable_inputs

    def test_recent_only_finding_short_windows_only(self):
        from services.auto_discovery.rescan_loop import summarize_window_stability
        finding = {"input_name": "rpe_1_10"}
        results = self._make_results({
            "30d": [finding],
            "60d": [finding],
            "90d": [finding],
            "180d": [],
            "365d": [],
            "full_history": [],
        })
        summary = summarize_window_stability(results)
        recent_inputs = [s["input"] for s in summary["recent_only"]]
        assert "rpe_1_10" in recent_inputs

    def test_empty_results_returns_empty_sections(self):
        from services.auto_discovery.rescan_loop import summarize_window_stability
        summary = summarize_window_stability([])
        assert summary["stable"] == []
        assert summary["recent_only"] == []
        assert summary["strengthening"] == []
        assert summary["unstable"] == []
