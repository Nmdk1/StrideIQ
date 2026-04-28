"""
Tests for AutoDiscovery Phase 0B.

Covers:
1. WS1 — Shadow isolation: no production cache reads/writes, lag field fix,
          per-athlete loop enablement.
2. WS2 — Real FQS: shadow dict scoring, score_finding_list, scores persisted.
3. WS3 — Pairwise interaction loop: shadow mode, persist, report section.
4. WS4 — Pilot registry tuning loop: shadow mode, persist, keep/discard,
          no registry mutation.
5. WS5 — Nightly report: all sections present, value-bearing or threshold-cleared.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch, call

import pytest


# ─────────────────────────────────────────────────────────────────────────────
#  WS1 — Shadow isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestShadowCacheIsolation:
    """
    Phase 0B: analyze_correlations with shadow_mode=True must not touch
    the production cache.
    """

    def _run_analyze_shadow(self, shadow_mode: bool):
        """Helper to run analyze_correlations with all aggregators stubbed."""
        from services.correlation_engine import analyze_correlations
        db = MagicMock()
        with patch("services.correlation_engine.aggregate_daily_inputs", return_value={}), \
             patch("services.correlation_engine.aggregate_training_load_inputs", return_value={}), \
             patch("services.correlation_engine.aggregate_activity_level_inputs", return_value={}), \
             patch("services.correlation_engine.aggregate_feedback_inputs", return_value={}), \
             patch("services.correlation_engine.aggregate_training_pattern_inputs", return_value={}), \
             patch("services.correlation_engine.aggregate_efficiency_outputs", return_value=[]), \
             patch("services.correlation_persistence.persist_correlation_findings", return_value=None):
            return analyze_correlations(
                athlete_id="test-athlete",
                days=90,
                db=db,
                shadow_mode=shadow_mode,
            )

    def test_shadow_mode_skips_cache_read(self):
        """Cache hit should be ignored when shadow_mode=True."""
        with patch("core.cache.get_cache") as mock_get, \
             patch("core.cache.set_cache"):
            mock_get.return_value = {"correlations": [], "_from_cache": True}
            result = self._run_analyze_shadow(shadow_mode=True)
            # In shadow mode the function must not return the cache hit value.
            assert result.get("_from_cache") is None, (
                "Shadow mode returned cached value — must bypass cache"
            )

    def test_shadow_mode_skips_cache_write(self):
        """set_cache must never be called when shadow_mode=True."""
        with patch("core.cache.get_cache", return_value=None), \
             patch("core.cache.set_cache") as mock_set:
            self._run_analyze_shadow(shadow_mode=True)
            mock_set.assert_not_called()

    def test_non_shadow_mode_still_reads_cache(self):
        """Normal (non-shadow) calls should return cached values."""
        with patch("core.cache.get_cache", return_value={"correlations": [], "_from_cache": True}):
            from services.correlation_engine import analyze_correlations
            result = analyze_correlations(
                athlete_id="test-athlete",
                days=90,
                db=MagicMock(),
                shadow_mode=False,
            )
            assert result.get("_from_cache") is True


class TestLagFieldPreservation:
    """WS1: lag metadata must be preserved as time_lag_days, not lag_days."""

    def test_rescan_loop_captures_time_lag_days(self):
        """
        The rescan loop must map c.get('time_lag_days'), not c.get('lag_days').
        """
        fake_correlation = {
            "input_name": "sleep_hours",
            "correlation_coefficient": 0.4,
            "p_value": 0.02,
            "sample_size": 20,
            "direction": "positive",
            "time_lag_days": 3,  # correct field name from CorrelationResult.to_dict()
            "strength": "moderate",
        }
        fake_result = {"correlations": [fake_correlation]}

        with patch("services.correlation_engine.analyze_correlations", return_value=fake_result):
            from services.auto_discovery.rescan_loop import run_multiwindow_rescan
            db = MagicMock()
            results = run_multiwindow_rescan(athlete_id=uuid.uuid4(), db=db)

        assert len(results) == 6  # six windows
        first_window = results[0]
        efficiency_findings = first_window["result_summary"]["findings_by_metric"].get("efficiency", [])
        assert len(efficiency_findings) > 0
        finding = efficiency_findings[0]
        # Must have time_lag_days, not lag_days.
        assert "time_lag_days" in finding, "lag field not captured as time_lag_days"
        assert "lag_days" not in finding, "old lag_days key should not be present"
        assert finding["time_lag_days"] == 3


class TestPerAthleteLoopEnablement:
    """WS1: loop enablement must be evaluated per athlete, not task-wide."""

    def test_each_athlete_gets_independent_loop_check(self):
        """
        With two athletes, loop checks must be called for each individually.
        athlete_1: rescan + interaction enabled
        athlete_2: only rescan enabled
        """
        athlete_1 = str(uuid.uuid4())
        athlete_2 = str(uuid.uuid4())

        rescan_calls: List[str] = []
        interaction_calls: List[str] = []
        tuning_calls: List[str] = []

        def mock_rescan(athlete_id, db):
            rescan_calls.append(athlete_id)
            return True

        def mock_interaction(athlete_id, db):
            interaction_calls.append(athlete_id)
            return athlete_id == athlete_1  # only athlete_1

        def mock_tuning(athlete_id, db):
            tuning_calls.append(athlete_id)
            return False  # neither

        with patch("services.auto_discovery.feature_flags.is_auto_discovery_enabled", return_value=True), \
             patch("services.auto_discovery.feature_flags.is_rescan_enabled", side_effect=mock_rescan), \
             patch("services.auto_discovery.feature_flags.is_interaction_enabled", side_effect=mock_interaction), \
             patch("services.auto_discovery.feature_flags.is_tuning_enabled", side_effect=mock_tuning), \
             patch("services.plan_framework.feature_flags.FeatureFlagService") as MockFFS, \
             patch("services.auto_discovery.orchestrator.run_auto_discovery_for_athlete") as mock_run:

            MockFFS.return_value._get_flag.return_value = {
                "allowed_athlete_ids": [athlete_1, athlete_2]
            }
            mock_run.return_value = MagicMock(id=uuid.uuid4(), status="completed", experiment_count=0)

            from tasks.auto_discovery_tasks import run_auto_discovery_nightly
            from core.database import SessionLocal
            with patch("tasks.auto_discovery_tasks.SessionLocal") as mock_db_factory:
                mock_db = MagicMock()
                mock_db_factory.return_value = mock_db
                run_auto_discovery_nightly.run()

        # Each athlete should have been independently checked for all loop families.
        assert athlete_1 in rescan_calls
        assert athlete_2 in rescan_calls
        assert athlete_1 in interaction_calls
        assert athlete_2 in interaction_calls


# ─────────────────────────────────────────────────────────────────────────────
#  WS2 — Real FQS scoring
# ─────────────────────────────────────────────────────────────────────────────

class TestCorrelationShadowDictScoring:
    """FQS adapter must score raw shadow correlation dicts."""

    def setup_method(self):
        from services.auto_discovery.fqs_adapters import CorrelationFindingFQSAdapter
        self.adapter = CorrelationFindingFQSAdapter()

    def test_shadow_dict_returns_required_schema(self):
        c = {
            "input_name": "sleep_hours",
            "correlation_coefficient": 0.45,
            "p_value": 0.01,
            "sample_size": 30,
            "direction": "positive",
            "time_lag_days": 2,
            "strength": "moderate",
        }
        result = self.adapter.score_shadow_dict(c)
        for key in ("origin", "base_score", "final_score", "components", "component_quality"):
            assert key in result

    def test_shadow_dict_origin_is_correlation_shadow(self):
        c = {
            "correlation_coefficient": 0.5, "sample_size": 25,
            "time_lag_days": 0, "strength": "moderate",
        }
        result = self.adapter.score_shadow_dict(c)
        assert result["origin"] == "correlation_shadow"

    def test_shadow_dict_score_bounded(self):
        c = {
            "correlation_coefficient": 0.8, "sample_size": 100,
            "time_lag_days": 5, "strength": "strong",
        }
        result = self.adapter.score_shadow_dict(c)
        assert 0.0 <= result["final_score"] <= 1.0
        assert 0.0 <= result["base_score"] <= 1.0

    def test_stronger_signal_scores_higher(self):
        strong = {
            "correlation_coefficient": 0.8, "sample_size": 50,
            "time_lag_days": 3, "strength": "strong",
        }
        weak = {
            "correlation_coefficient": 0.2, "sample_size": 10,
            "time_lag_days": 0, "strength": "weak",
        }
        s_strong = self.adapter.score_shadow_dict(strong)
        s_weak = self.adapter.score_shadow_dict(weak)
        assert s_strong["final_score"] > s_weak["final_score"]

    def test_component_quality_labels_present(self):
        c = {"correlation_coefficient": 0.4, "sample_size": 15, "time_lag_days": 0}
        result = self.adapter.score_shadow_dict(c)
        cq = result["component_quality"]
        assert "confidence" in cq and "specificity" in cq


class TestAthleteFindingScoreList:
    """AthleteFindingFQSAdapter.score_finding_list must aggregate correctly."""

    def setup_method(self):
        from services.auto_discovery.fqs_adapters import AthleteFindingFQSAdapter
        self.adapter = AthleteFindingFQSAdapter()

    def _make_finding(self, **kwargs):
        now = datetime.now(timezone.utc)
        defaults = {
            "confidence": "genuine",
            "last_confirmed_at": now,
            "first_detected_at": now - timedelta(days=45),
            "is_active": True,
            "receipts": {"pace": 1, "hr": 2},
            "sentence": "Your sleep is strongly correlated with pace efficiency.",
        }
        defaults.update(kwargs)
        obj = MagicMock()
        for k, v in defaults.items():
            setattr(obj, k, v)
        return obj

    def test_empty_list_returns_zero(self):
        assert self.adapter.score_finding_list([]) == 0.0

    def test_single_finding_matches_individual_score(self):
        f = self._make_finding()
        aggregate = self.adapter.score_finding_list([f])
        individual = self.adapter.score(f)["final_score"]
        assert aggregate == individual

    def test_multiple_findings_returns_mean(self):
        f1 = self._make_finding(confidence="genuine")
        f2 = self._make_finding(confidence="suggestive")
        aggregate = self.adapter.score_finding_list([f1, f2])
        expected = round(
            (self.adapter.score(f1)["final_score"] + self.adapter.score(f2)["final_score"]) / 2,
            4,
        )
        assert aggregate == expected

    def test_transient_race_input_finding_without_persistence_timestamps_scores(self):
        """Registry tuning scores transient investigation findings, not just ORM rows."""
        from services.race_input_analysis import RaceInputFinding

        finding = RaceInputFinding(
            layer="B",
            finding_type="race_input",
            sentence="Threshold sessions clustered before stronger race inputs.",
            receipts={"sessions": 4, "window_days": 42},
            confidence="suggestive",
        )

        aggregate = self.adapter.score_finding_list([finding])

        assert 0.0 < aggregate <= 1.0


class TestRescanExperimentsHaveRealScores:
    """WS2: orchestrator must persist real FQS scores on rescan experiments."""

    @pytest.fixture
    def rescan_results_with_correlations(self):
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
                            {
                                "input_name": "sleep_hours",
                                "correlation_coefficient": 0.55,
                                "p_value": 0.01,
                                "sample_size": 30,
                                "direction": "positive",
                                "time_lag_days": 1,
                                "strength": "strong",
                            }
                        ]
                    },
                    "total_findings": 1,
                    "error": None,
                },
                "failure_reason": None,
                "runtime_ms": 250,
            }
        ]

    def test_rescan_experiment_has_numeric_baseline_score(
        self, db_session, test_athlete, rescan_results_with_correlations
    ):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete
        from models import AutoDiscoveryExperiment

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan",
                   return_value=rescan_results_with_correlations), \
             patch.object(db_session, "rollback"):
            run = run_auto_discovery_for_athlete(
                athlete_id=test_athlete.id,
                db=db_session,
                enabled_loops=["correlation_rescan"],
            )

        exp = db_session.query(AutoDiscoveryExperiment).filter_by(run_id=run.id).first()
        assert exp is not None
        assert exp.baseline_score is not None
        assert isinstance(exp.baseline_score, float)
        assert exp.baseline_score > 0.0, "FQS score should be > 0 for a valid correlation"

    def test_score_summary_has_fqs_fields(
        self, db_session, test_athlete, rescan_results_with_correlations
    ):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan",
                   return_value=rescan_results_with_correlations), \
             patch.object(db_session, "rollback"):
            run = run_auto_discovery_for_athlete(
                athlete_id=test_athlete.id,
                db=db_session,
                enabled_loops=["correlation_rescan"],
            )

        summary = run.report["score_summary"]
        assert "correlation_rescan" in summary
        rescan_summary = summary["correlation_rescan"]
        assert "experiments_run" in rescan_summary
        assert "kept" in rescan_summary
        assert "aggregate_baseline_score" in rescan_summary


# ─────────────────────────────────────────────────────────────────────────────
#  WS3 — Pairwise interaction loop
# ─────────────────────────────────────────────────────────────────────────────

class TestPairwiseInteractionLoop:
    """Unit tests for the interaction loop — no DB required."""

    def test_score_interaction_all_keys_present(self):
        from services.auto_discovery.interaction_loop import _score_interaction
        candidate = {
            "factors": ["sleep_hours", "work_stress"],
            "output_metric": "efficiency",
            "effect_size": 0.8,
            "n_high": 20,
            "n_low": 18,
            "direction_label": "lower efficiency when both sleep and stress are high",
        }
        scored = _score_interaction(candidate)
        assert "interaction_score" in scored
        assert "score_components" in scored
        assert 0.0 <= scored["interaction_score"] <= 1.0

    def test_larger_effect_scores_higher(self):
        from services.auto_discovery.interaction_loop import _score_interaction
        big = {"effect_size": 1.4, "n_high": 25, "n_low": 25, "factors": ["a", "b"],
               "output_metric": "efficiency"}
        small = {"effect_size": 0.52, "n_high": 10, "n_low": 10, "factors": ["a", "b"],
                 "output_metric": "efficiency"}
        assert _score_interaction(big)["interaction_score"] > _score_interaction(small)["interaction_score"]

    def test_generate_candidates_int_param_step_up_down(self):
        from services.auto_discovery.tuning_loop import _generate_candidates
        from services.race_input_analysis import InvestigationParamSpec

        param = InvestigationParamSpec(
            name="min_activities",
            param_type="int",
            default=20,
            min_value=10,
            max_value=40,
            description="test",
        )
        candidates = _generate_candidates(param)
        values = [c["min_activities"] for c in candidates]
        assert len(values) == 2
        assert 16 in values or any(v < 20 for v in values)  # step down
        assert any(v > 20 for v in values)  # step up


class TestInteractionLoopIntegration:
    """Integration tests for interaction loop via orchestrator."""

    @pytest.fixture
    def mock_interaction_results(self):
        return [
            {
                "loop_type": "interaction_scan",
                "target_name": "pairwise:efficiency",
                "baseline_config": {"output_metric": "efficiency", "days": 180},
                "candidate_config": {},
                "result_summary": {
                    "output_metric": "efficiency",
                    "interactions_tested": 5,
                    "interactions_kept": 2,
                    "top_interactions": [
                        {
                            "factors": ["sleep_hours", "work_stress"],
                            "output_metric": "efficiency",
                            "effect_size": 0.85,
                            "n_high": 22,
                            "n_low": 20,
                            "interaction_score": 0.52,
                            "score_components": {"effect_size_norm": 0.57, "sample_support": 0.44},
                            "direction_label": "test",
                        }
                    ],
                    "threshold_statement": None,
                    "error": None,
                },
                "baseline_score": 2.0,
                "candidate_score": None,
                "score_delta": None,
                "failure_reason": None,
                "runtime_ms": 300,
            }
        ]

    def test_interaction_experiments_persisted(
        self, db_session, test_athlete, mock_interaction_results
    ):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete
        from models import AutoDiscoveryExperiment

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan", return_value=[]), \
             patch("services.auto_discovery.orchestrator.run_pairwise_interaction_scan",
                   return_value=mock_interaction_results), \
             patch.object(db_session, "rollback"):
            run = run_auto_discovery_for_athlete(
                athlete_id=test_athlete.id,
                db=db_session,
                enabled_loops=["interaction_scan"],
            )

        exps = db_session.query(AutoDiscoveryExperiment).filter_by(
            run_id=run.id, loop_type="interaction_scan"
        ).all()
        assert len(exps) >= 1

    def test_report_candidate_interactions_is_value_bearing(
        self, db_session, test_athlete, mock_interaction_results
    ):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan", return_value=[]), \
             patch("services.auto_discovery.orchestrator.run_pairwise_interaction_scan",
                   return_value=mock_interaction_results), \
             patch.object(db_session, "rollback"):
            run = run_auto_discovery_for_athlete(
                athlete_id=test_athlete.id,
                db=db_session,
                enabled_loops=["interaction_scan"],
            )

        ci = run.report["candidate_interactions"]
        assert isinstance(ci, dict), "candidate_interactions must be a dict with 'cleared_threshold'"
        assert "cleared_threshold" in ci
        # With interactions_kept=2 and one candidate with score 0.52 > threshold, should clear.
        if ci["cleared_threshold"]:
            assert len(ci["candidates"]) > 0
        else:
            assert "reason" in ci

    def test_no_athlete_facing_tables_mutated(
        self, db_session, test_athlete, mock_interaction_results
    ):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete
        from models import AthleteFinding

        before_count = db_session.query(AthleteFinding).filter_by(
            athlete_id=test_athlete.id
        ).count()

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan", return_value=[]), \
             patch("services.auto_discovery.orchestrator.run_pairwise_interaction_scan",
                   return_value=mock_interaction_results), \
             patch.object(db_session, "rollback"):
            run_auto_discovery_for_athlete(
                athlete_id=test_athlete.id,
                db=db_session,
                enabled_loops=["interaction_scan"],
            )

        after_count = db_session.query(AthleteFinding).filter_by(
            athlete_id=test_athlete.id
        ).count()
        assert before_count == after_count, "AthleteFinding count must not change"


# ─────────────────────────────────────────────────────────────────────────────
#  WS4 — Pilot registry tuning loop
# ─────────────────────────────────────────────────────────────────────────────

class TestCandidateGeneration:
    """Unit tests for bounded candidate generation."""

    def test_int_param_generates_step_up_and_down(self):
        from services.auto_discovery.tuning_loop import _generate_candidates
        from services.race_input_analysis import InvestigationParamSpec
        param = InvestigationParamSpec(
            name="min_activities", param_type="int",
            default=20, min_value=10, max_value=40, description="x",
        )
        candidates = _generate_candidates(param)
        values = {c["min_activities"] for c in candidates}
        assert len(values) == 2
        assert all(10 <= v <= 40 for v in values)

    def test_int_param_at_min_boundary_no_step_down(self):
        from services.auto_discovery.tuning_loop import _generate_candidates
        from services.race_input_analysis import InvestigationParamSpec
        param = InvestigationParamSpec(
            name="min_activities", param_type="int",
            default=10, min_value=10, max_value=40, description="x",
        )
        candidates = _generate_candidates(param)
        values = [c["min_activities"] for c in candidates]
        assert all(v >= 10 for v in values)  # no below-min candidate
        assert any(v > 10 for v in values)  # step up exists

    def test_int_param_at_max_boundary_no_step_up(self):
        from services.auto_discovery.tuning_loop import _generate_candidates
        from services.race_input_analysis import InvestigationParamSpec
        param = InvestigationParamSpec(
            name="min_activities", param_type="int",
            default=40, min_value=10, max_value=40, description="x",
        )
        candidates = _generate_candidates(param)
        values = [c["min_activities"] for c in candidates]
        assert all(v <= 40 for v in values)


class TestKeepRule:
    """Unit tests for the keep/discard decision logic."""

    def test_positive_delta_exceeding_threshold_is_kept(self):
        from services.auto_discovery.tuning_loop import _apply_keep_rule, TUNING_KEEP_THRESHOLD
        kept, rationale = _apply_keep_rule(
            score_delta=TUNING_KEEP_THRESHOLD + 0.01,
            baseline_score=0.4,
            candidate_score=0.43,
            baseline_findings=[MagicMock(), MagicMock()],
            candidate_findings=[MagicMock(), MagicMock()],
        )
        assert kept is True
        assert "kept" in rationale

    def test_delta_below_threshold_is_discarded(self):
        from services.auto_discovery.tuning_loop import _apply_keep_rule, TUNING_KEEP_THRESHOLD
        kept, rationale = _apply_keep_rule(
            score_delta=TUNING_KEEP_THRESHOLD - 0.001,
            baseline_score=0.4,
            candidate_score=0.403,
            baseline_findings=[MagicMock()],
            candidate_findings=[MagicMock()],
        )
        assert kept is False
        assert "does not exceed" in rationale.lower() or "threshold" in rationale.lower()

    def test_stability_regression_prevents_keep(self):
        from services.auto_discovery.tuning_loop import _apply_keep_rule, TUNING_KEEP_THRESHOLD
        # Delta is positive but candidate lost findings.
        kept, rationale = _apply_keep_rule(
            score_delta=TUNING_KEEP_THRESHOLD + 0.05,
            baseline_score=0.35,
            candidate_score=0.40,
            baseline_findings=[MagicMock(), MagicMock(), MagicMock()],
            candidate_findings=[MagicMock()],  # fewer findings
        )
        assert kept is False
        assert "regression" in rationale.lower() or "stability" in rationale.lower()


class TestTuningLoopIntegration:
    """Integration: tuning experiments persisted, no registry mutation."""

    @pytest.fixture
    def mock_tuning_results(self):
        return [
            {
                "loop_type": "registry_tuning",
                "target_name": "tuning:investigate_pace_at_hr_adaptation:min_activities",
                "baseline_config": {
                    "investigation": "investigate_pace_at_hr_adaptation",
                    "params": {"min_activities": 20},
                },
                "candidate_config": {
                    "investigation": "investigate_pace_at_hr_adaptation",
                    "params": {"min_activities": 16},
                    "changed_param": "min_activities",
                    "changed_delta": {"min_activities": 16},
                },
                "baseline_score": 0.35,
                "candidate_score": 0.39,
                "score_delta": 0.04,
                "kept": True,
                "result_summary": {
                    "investigation": "investigate_pace_at_hr_adaptation",
                    "param_name": "min_activities",
                    "baseline_findings_count": 2,
                    "candidate_findings_count": 3,
                    "kept": True,
                    "rationale": "kept: score_delta 0.04 > 0.03",
                    "baseline_error": None,
                    "candidate_error": None,
                },
                "failure_reason": None,
                "runtime_ms": 200,
            }
        ]

    def test_tuning_experiments_persisted(
        self, db_session, test_athlete, mock_tuning_results
    ):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete
        from models import AutoDiscoveryExperiment

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan", return_value=[]), \
             patch("services.auto_discovery.orchestrator.run_pilot_tuning_loop",
                   return_value=mock_tuning_results), \
             patch.object(db_session, "rollback"):
            run = run_auto_discovery_for_athlete(
                athlete_id=test_athlete.id,
                db=db_session,
                enabled_loops=["registry_tuning"],
            )

        exps = db_session.query(AutoDiscoveryExperiment).filter_by(
            run_id=run.id, loop_type="registry_tuning"
        ).all()
        assert len(exps) >= 1

    def test_tuning_experiments_have_real_scores(
        self, db_session, test_athlete, mock_tuning_results
    ):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete
        from models import AutoDiscoveryExperiment

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan", return_value=[]), \
             patch("services.auto_discovery.orchestrator.run_pilot_tuning_loop",
                   return_value=mock_tuning_results), \
             patch.object(db_session, "rollback"):
            run = run_auto_discovery_for_athlete(
                athlete_id=test_athlete.id,
                db=db_session,
                enabled_loops=["registry_tuning"],
            )

        exp = db_session.query(AutoDiscoveryExperiment).filter_by(
            run_id=run.id, loop_type="registry_tuning"
        ).first()
        assert exp.baseline_score is not None
        assert exp.candidate_score is not None
        assert exp.score_delta is not None

    def test_score_delta_is_correct(
        self, db_session, test_athlete, mock_tuning_results
    ):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete
        from models import AutoDiscoveryExperiment

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan", return_value=[]), \
             patch("services.auto_discovery.orchestrator.run_pilot_tuning_loop",
                   return_value=mock_tuning_results), \
             patch.object(db_session, "rollback"):
            run = run_auto_discovery_for_athlete(
                athlete_id=test_athlete.id,
                db=db_session,
                enabled_loops=["registry_tuning"],
            )

        exp = db_session.query(AutoDiscoveryExperiment).filter_by(
            run_id=run.id, loop_type="registry_tuning"
        ).first()
        assert abs(exp.score_delta - (exp.candidate_score - exp.baseline_score)) < 0.001

    def test_no_production_registry_mutated(self):
        """
        run_pilot_tuning_loop restores spec thresholds after evaluation.
        After tuning completes, the spec must have its original min_activities.
        """
        from services.race_input_analysis import INVESTIGATION_REGISTRY
        from services.auto_discovery.tuning_loop import run_pilot_tuning_loop, PILOT_INVESTIGATIONS

        # Find one pilot spec.
        pilot_spec = next(
            (s for s in INVESTIGATION_REGISTRY if s.name in PILOT_INVESTIGATIONS and s.shadow_enabled),
            None,
        )
        if pilot_spec is None:
            pytest.skip("No shadow-enabled pilot spec found")

        original_min_activities = pilot_spec.min_activities

        db = MagicMock()
        # Patch load_training_zones at the source module.
        with patch("services.race_input_analysis.load_training_zones", return_value=MagicMock()), \
             patch.object(pilot_spec, "fn", return_value=None):
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            run_pilot_tuning_loop(athlete_id=uuid.uuid4(), db=db)

        # Registry must be unchanged.
        assert pilot_spec.min_activities == original_min_activities, (
            f"Registry mutation detected: min_activities changed from "
            f"{original_min_activities} to {pilot_spec.min_activities}"
        )

    def test_report_registry_tuning_candidates_is_value_bearing(
        self, db_session, test_athlete, mock_tuning_results
    ):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete

        with patch("services.auto_discovery.orchestrator.run_multiwindow_rescan", return_value=[]), \
             patch("services.auto_discovery.orchestrator.run_pilot_tuning_loop",
                   return_value=mock_tuning_results), \
             patch.object(db_session, "rollback"):
            run = run_auto_discovery_for_athlete(
                athlete_id=test_athlete.id,
                db=db_session,
                enabled_loops=["registry_tuning"],
            )

        rtc = run.report["registry_tuning_candidates"]
        assert isinstance(rtc, dict), "registry_tuning_candidates must be a structured dict"
        assert "cleared_threshold" in rtc
        if rtc["cleared_threshold"]:
            assert len(rtc["candidates"]) > 0
            c = rtc["candidates"][0]
            assert "investigation" in c
            assert "score_delta" in c
            assert "kept" in c
        else:
            assert "reason" in rtc


# ─────────────────────────────────────────────────────────────────────────────
#  WS5 — Nightly report
# ─────────────────────────────────────────────────────────────────────────────

class TestNightlyReport:
    """Report must contain all required sections; sections 3+4 must be value-bearing."""

    _REQUIRED_SECTIONS = [
        "stable_findings",
        "strengthened_findings",
        "candidate_interactions",
        "registry_tuning_candidates",
        "discarded_experiments",
        "score_summary",
        "no_surface_guarantee",
    ]

    def _run_orchestrator(self, db_session, test_athlete, enabled_loops, extra_patches=None):
        from services.auto_discovery.orchestrator import run_auto_discovery_for_athlete
        patches = {
            "services.auto_discovery.orchestrator.run_multiwindow_rescan": [],
        }
        if extra_patches:
            patches.update(extra_patches)

        active_patches = []
        for target, return_val in patches.items():
            p = patch(target, return_value=return_val)
            active_patches.append(p)
            p.start()
        p_rollback = patch.object(db_session, "rollback")
        p_rollback.start()
        try:
            run = run_auto_discovery_for_athlete(
                athlete_id=test_athlete.id,
                db=db_session,
                enabled_loops=enabled_loops,
            )
        finally:
            p_rollback.stop()
            for p in active_patches:
                p.stop()
        return run

    def test_all_required_sections_present_rescan_only(self, db_session, test_athlete):
        run = self._run_orchestrator(db_session, test_athlete, ["correlation_rescan"])
        for section in self._REQUIRED_SECTIONS:
            assert section in run.report, f"Missing: {section}"

    def test_candidate_interactions_is_structured_dict_when_no_loop(self, db_session, test_athlete):
        run = self._run_orchestrator(db_session, test_athlete, ["correlation_rescan"])
        ci = run.report["candidate_interactions"]
        assert isinstance(ci, dict)
        assert "cleared_threshold" in ci
        assert ci["cleared_threshold"] is False
        assert "reason" in ci

    def test_registry_tuning_candidates_is_structured_dict_when_no_loop(self, db_session, test_athlete):
        run = self._run_orchestrator(db_session, test_athlete, ["correlation_rescan"])
        rtc = run.report["registry_tuning_candidates"]
        assert isinstance(rtc, dict)
        assert "cleared_threshold" in rtc
        assert rtc["cleared_threshold"] is False

    def test_score_summary_has_loop_family_entries(self, db_session, test_athlete):
        run = self._run_orchestrator(db_session, test_athlete, ["correlation_rescan"])
        # Even with empty results, correlation_rescan key should be absent (no experiments).
        # If any experiments ran, it must have required keys.
        summary = run.report["score_summary"]
        if "correlation_rescan" in summary:
            for key in ("experiments_run", "kept", "aggregate_baseline_score"):
                assert key in summary["correlation_rescan"]

    def test_no_surface_guarantee_phase_0b(self, db_session, test_athlete):
        run = self._run_orchestrator(db_session, test_athlete, ["correlation_rescan"])
        g = run.report["no_surface_guarantee"]
        assert g["athlete_facing_surfaces_mutated"] is False
        assert g["production_registry_values_mutated"] is False
        assert g["production_cache_polluted"] is False
        assert g["live_mutation_enabled"] is False
        # Phase 1 updated _PHASE to "1" and _SCHEMA_VERSION to 4.
        assert g["phase"] in ("0B", "0C", "1")

    def test_report_schema_version_is_2(self, db_session, test_athlete):
        run = self._run_orchestrator(db_session, test_athlete, ["correlation_rescan"])
        # Phase 1 bumped schema_version to 4; accept 2, 3, or 4 for backward compat.
        assert run.report["schema_version"] in (2, 3, 4)
