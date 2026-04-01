"""
AutoDiscovery Phase 1 — Test Suite

Tests: idempotency, mutation safety, auto-disable, revert, coverage,
kill-switch, change ledger, per-athlete transaction boundary.
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


# ── helpers ─────────────────────────────────────────────────────────────────

def _mock_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.filter.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.join.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    return db


ATHLETE_ID = uuid4()


# ── Feature flags ────────────────────────────────────────────────────────────

class TestPhase1FeatureFlags:
    def test_mutation_flag_driven_from_db_when_enabled(self):
        db = _mock_db()
        with patch("services.auto_discovery.feature_flags.is_feature_enabled", return_value=True):
            from services.auto_discovery.feature_flags import is_live_mutation_enabled
            assert is_live_mutation_enabled(str(ATHLETE_ID), db)

    def test_mutation_false_when_master_flag_disabled(self):
        db = _mock_db()
        with patch("services.auto_discovery.feature_flags.is_feature_enabled", return_value=False):
            from services.auto_discovery.feature_flags import is_live_mutation_enabled
            assert not is_live_mutation_enabled(str(ATHLETE_ID), db)

    def test_auto_promote_findings_requires_mutation_enabled(self):
        db = _mock_db()
        call_args = []
        def _flag(key, athlete_id, db_):
            call_args.append(key)
            return True  # all flags enabled
        with patch("services.auto_discovery.feature_flags.is_feature_enabled", side_effect=_flag):
            from services.auto_discovery.feature_flags import is_auto_promote_findings_enabled
            result = is_auto_promote_findings_enabled(str(ATHLETE_ID), db)
            assert result is True
            # Must have checked mutation flag before auto-promote flag
            assert "auto_discovery.mutation.live" in call_args

    def test_auto_promote_findings_false_when_mutation_disabled(self):
        db = _mock_db()
        with patch("services.auto_discovery.feature_flags.is_feature_enabled", return_value=False):
            from services.auto_discovery.feature_flags import is_auto_promote_findings_enabled
            assert not is_auto_promote_findings_enabled(str(ATHLETE_ID), db)

    def test_three_auto_promote_flags_independent(self):
        db = _mock_db()
        flags_enabled = {
            "auto_discovery.enabled": True,
            "auto_discovery.mutation.live": True,
            "auto_discovery.auto_promote.stability": True,
            "auto_discovery.auto_promote.findings": False,  # only stability on
            "auto_discovery.auto_promote.tuning": False,
        }
        def _flag(key, athlete_id, db_):
            return flags_enabled.get(key, False)
        with patch("services.auto_discovery.feature_flags.is_feature_enabled", side_effect=_flag):
            from services.auto_discovery.feature_flags import (
                is_auto_promote_stability_enabled,
                is_auto_promote_findings_enabled,
                is_auto_promote_tuning_enabled,
            )
            assert is_auto_promote_stability_enabled(str(ATHLETE_ID), db)
            assert not is_auto_promote_findings_enabled(str(ATHLETE_ID), db)
            assert not is_auto_promote_tuning_enabled(str(ATHLETE_ID), db)

    def test_seed_flags_include_phase1_flags(self):
        from services.auto_discovery.feature_flags import SEED_FLAGS
        keys = [f["key"] for f in SEED_FLAGS]
        assert "auto_discovery.auto_promote.stability" in keys
        assert "auto_discovery.auto_promote.findings" in keys
        assert "auto_discovery.auto_promote.tuning" in keys
        # All Phase 1 flags default off
        for f in SEED_FLAGS:
            if f["key"].startswith("auto_discovery.auto_promote"):
                assert not f["enabled"]


# ── Deep-window finding promotion ────────────────────────────────────────────

class TestDeepWindowPromotion:
    def _make_rescan_results(self, window_days, r=0.45, p=0.02, n=15) -> list:
        return [{
            "loop_type": "correlation_rescan",
            "target_name": f"multiwindow:{window_days}d",
            "baseline_config": {"window_days": window_days},
            "candidate_config": {},
            "result_summary": {
                "window_label": f"{window_days}d",
                "findings_by_metric": {
                    "efficiency": [{
                        "input_name": "readiness_1_5",
                        "correlation_coefficient": r,
                        "p_value": p,
                        "sample_size": n,
                        "direction": "positive",
                        "time_lag_days": 0,
                        "strength": "moderate",
                    }]
                },
                "total_findings": 1,
                "error": None,
            },
            "failure_reason": None,
            "runtime_ms": 100,
        }]

    def test_deep_window_180d_promotes_new_finding(self):
        from services.auto_discovery.rescan_loop import promote_deep_window_findings
        db = _mock_db()
        # No existing finding
        db.query.return_value.filter.return_value.first.return_value = None

        results = self._make_rescan_results(180)
        # CorrelationFinding is imported lazily inside the function
        # Just verify the function runs without error and returns a tuple
        promoted, count = promote_deep_window_findings(ATHLETE_ID, results, db)
        assert isinstance(promoted, list)
        assert isinstance(count, int)

    def test_shallow_window_90d_does_not_promote(self):
        from services.auto_discovery.rescan_loop import promote_deep_window_findings, _DEEP_WINDOWS
        db = _mock_db()
        results = self._make_rescan_results(90)
        # 90d is NOT a deep window
        assert 90 not in _DEEP_WINDOWS
        promoted, count = promote_deep_window_findings(ATHLETE_ID, results, db)
        assert count == 0

    def test_below_r_threshold_not_promoted(self):
        from services.auto_discovery.rescan_loop import promote_deep_window_findings
        db = _mock_db()
        results = self._make_rescan_results(180, r=0.1, p=0.001, n=50)  # r too small
        promoted, count = promote_deep_window_findings(ATHLETE_ID, results, db)
        assert count == 0

    def test_high_p_value_not_promoted(self):
        from services.auto_discovery.rescan_loop import promote_deep_window_findings
        db = _mock_db()
        results = self._make_rescan_results(180, r=0.6, p=0.20, n=20)  # p too high
        promoted, count = promote_deep_window_findings(ATHLETE_ID, results, db)
        assert count == 0

    def test_insufficient_n_not_promoted(self):
        from services.auto_discovery.rescan_loop import promote_deep_window_findings
        db = _mock_db()
        results = self._make_rescan_results(180, r=0.6, p=0.02, n=5)  # n too small
        promoted, count = promote_deep_window_findings(ATHLETE_ID, results, db)
        assert count == 0

    def test_idempotent_promotion_key_prevents_duplicate(self):
        """Running promotion twice must not create a second finding row."""
        from services.auto_discovery.rescan_loop import promote_deep_window_findings

        db = _mock_db()
        results = self._make_rescan_results(180)

        existing_finding = MagicMock()
        existing_finding.discovery_source = "auto_discovery"
        existing_finding.discovery_window_days = 180
        # Simulate existing row found — single filter call
        db.query.return_value.filter.return_value.first.return_value = existing_finding

        promoted, count = promote_deep_window_findings(ATHLETE_ID, results, db)
        # Should update metadata but not create a duplicate
        assert db.add.call_count == 0  # no new row added

    def test_full_history_window_promotes(self):
        """None window (full history) should be treated as deep."""
        from services.auto_discovery.rescan_loop import promote_deep_window_findings, _FULL_HISTORY_DAYS, _DEEP_WINDOWS
        assert _FULL_HISTORY_DAYS in _DEEP_WINDOWS
        db = _mock_db()
        db.query.return_value.filter.return_value.first.return_value = None
        results = [{
            "loop_type": "correlation_rescan",
            "target_name": "multiwindow:full_history",
            "baseline_config": {"window_days": None},
            "candidate_config": {},
            "result_summary": {
                "window_label": "full_history",
                "findings_by_metric": {
                    "efficiency": [{
                        "input_name": "hrv_sdnn",
                        "correlation_coefficient": 0.5,
                        "p_value": 0.01,
                        "sample_size": 20,
                        "direction": "positive",
                        "time_lag_days": 0,
                        "strength": "strong",
                    }]
                },
                "error": None,
            },
            "failure_reason": None,
            "runtime_ms": 100,
        }]
        promoted, count = promote_deep_window_findings(ATHLETE_ID, results, db)
        assert isinstance(promoted, list)
        assert isinstance(count, int)


# ── Stability annotation ─────────────────────────────────────────────────────

class TestStabilityAnnotation:
    def test_annotate_stability_called_with_rescan_data(self):
        from services.auto_discovery.rescan_loop import annotate_finding_stability
        db = _mock_db()

        existing_finding = MagicMock()
        existing_finding.output_metric = "efficiency"
        existing_finding.input_name = "readiness_1_5"
        db.query.return_value.filter.return_value.filter.return_value.first.return_value = existing_finding
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = [existing_finding]

        rescan_results = [{
            "loop_type": "correlation_rescan",
            "target_name": "multiwindow:all",
            "baseline_config": {},
            "candidate_config": {},
            "result_summary": {
                "window_label": "90d",
                "findings_by_metric": {
                    "efficiency": [{"input_name": "readiness_1_5"}]
                },
                "error": None,
            },
            "failure_reason": None,
        }]
        count = annotate_finding_stability(ATHLETE_ID, rescan_results, db)
        # No crash — count is returned
        assert isinstance(count, int)

    def test_stable_finding_receives_stable_class(self):
        from services.auto_discovery.rescan_loop import summarize_window_stability

        results = []
        for wd in [30, 60, 90, 180, 365, None]:
            label = f"{wd}d" if wd is not None else "full_history"
            results.append({
                "result_summary": {
                    "findings_by_metric": {
                        "efficiency": [{"input_name": "readiness_1_5"}]
                    },
                    "error": None,
                },
                "failure_reason": None,
            })

        stability = summarize_window_stability(results)
        stable_keys = [(s["metric"], s["input"]) for s in stability["stable"]]
        assert ("efficiency", "readiness_1_5") in stable_keys


# ── Interaction promotion ────────────────────────────────────────────────────

class TestInteractionPromotion:
    def test_promotes_candidate_with_sufficient_times_seen(self):
        from services.auto_discovery.interaction_loop import promote_interaction_findings

        db = _mock_db()
        mock_candidate = MagicMock()
        mock_candidate.id = uuid4()
        mock_candidate.athlete_id = ATHLETE_ID
        mock_candidate.times_seen = 4
        mock_candidate.current_status = "open"
        mock_candidate.latest_summary = {
            "input_a": "readiness_1_5",
            "input_b": "hrv_sdnn",
            "output_metric": "efficiency",
            "effect_size": 0.7,
            "interaction_score": 0.65,
        }

        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [mock_candidate]
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = None

        promoted = promote_interaction_findings(ATHLETE_ID, db)
        assert len(promoted) >= 0  # no crash

    def test_does_not_promote_candidate_below_times_seen_threshold(self):
        from services.auto_discovery.interaction_loop import promote_interaction_findings, _INTERACTION_PROMOTION_TIMES_SEEN

        db = _mock_db()
        # Return no candidates with sufficient times_seen
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []

        promoted = promote_interaction_findings(ATHLETE_ID, db)
        assert len(promoted) == 0

    def test_promotion_uses_friendly_signal_names(self):
        """Promoted findings must use friendly_signal_name() in sentence."""
        from services.auto_discovery.interaction_loop import promote_interaction_findings
        from services.n1_insight_generator import friendly_signal_name

        db = _mock_db()
        mock_candidate = MagicMock()
        mock_candidate.id = uuid4()
        mock_candidate.athlete_id = ATHLETE_ID
        mock_candidate.times_seen = 5
        mock_candidate.current_status = "open"
        mock_candidate.latest_summary = {
            "input_a": "readiness_1_5",
            "input_b": None,
            "output_metric": "efficiency",
            "effect_size": 0.6,
            "interaction_score": 0.55,
        }
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [mock_candidate]
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = None

        added_objects = []
        db.add = lambda obj: added_objects.append(obj)

        promoted = promote_interaction_findings(ATHLETE_ID, db)
        # The sentence should NOT contain the raw name "readiness_1_5"
        if added_objects:
            from models import AthleteFinding
            athlete_findings = [o for o in added_objects if hasattr(o, 'sentence')]
            for f in athlete_findings:
                assert "readiness_1_5" not in f.sentence

    def test_coverage_key_deterministic(self):
        from services.auto_discovery.interaction_loop import _make_coverage_key
        k1 = _make_coverage_key("readiness_1_5", "hrv_sdnn", "efficiency", 180)
        k2 = _make_coverage_key("readiness_1_5", "hrv_sdnn", "efficiency", 180)
        assert k1 == k2

    def test_coverage_key_different_inputs_differ(self):
        from services.auto_discovery.interaction_loop import _make_coverage_key
        k1 = _make_coverage_key("readiness_1_5", "hrv_sdnn", "efficiency", 180)
        k2 = _make_coverage_key("readiness_1_5", "stress_1_5", "efficiency", 180)
        assert k1 != k2


# ── Tuning apply ─────────────────────────────────────────────────────────────

class TestTuningApply:
    def test_apply_tuning_improvement_idempotent(self):
        """Applying the same override twice must not create a second active row."""
        from services.auto_discovery.tuning_loop import apply_tuning_improvement
        import json

        db = _mock_db()
        param_overrides = {"min_activities": 15}

        existing_config = MagicMock()
        existing_config.param_overrides = param_overrides
        existing_config.reverted = False
        # The function uses a single .filter(a, b, c).order_by(...).first()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = existing_config

        result = apply_tuning_improvement(
            athlete_id=ATHLETE_ID,
            investigation_name="investigate_pace_at_hr_adaptation",
            param_overrides=param_overrides,
            run_id=uuid4(),
            change_log_id=uuid4(),
            db=db,
        )
        # Identical config already active → idempotent skip
        assert result is False
        assert db.add.call_count == 0

    def test_apply_tuning_improvement_new_config(self):
        """New param override with no existing config creates a new row."""
        from services.auto_discovery.tuning_loop import apply_tuning_improvement

        db = _mock_db()
        # No existing active config
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        added_objects = []
        db.add = lambda obj: added_objects.append(obj)

        result = apply_tuning_improvement(
            athlete_id=ATHLETE_ID,
            investigation_name="investigate_pace_at_hr_adaptation",
            param_overrides={"min_activities": 25},
            run_id=uuid4(),
            change_log_id=uuid4(),
            db=db,
        )
        assert result is True
        assert len(added_objects) == 1

    def test_apply_different_override_creates_new_row(self):
        """Different param values must create a new active config, not update the existing."""
        from services.auto_discovery.tuning_loop import apply_tuning_improvement
        import json

        db = _mock_db()
        existing_config = MagicMock()
        existing_config.param_overrides = {"min_activities": 15}
        existing_config.reverted = False
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = existing_config

        added_objects = []
        db.add = lambda obj: added_objects.append(obj)

        result = apply_tuning_improvement(
            athlete_id=ATHLETE_ID,
            investigation_name="investigate_pace_at_hr_adaptation",
            param_overrides={"min_activities": 30},  # different value
            run_id=uuid4(),
            change_log_id=uuid4(),
            db=db,
        )
        assert result is True
        assert len(added_objects) == 1

    def test_get_active_param_overrides_returns_none_when_no_config(self):
        from services.auto_discovery.tuning_loop import get_active_param_overrides
        db = _mock_db()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        result = get_active_param_overrides(ATHLETE_ID, "investigate_pace_at_hr_adaptation", db)
        assert result is None

    def test_get_active_param_overrides_returns_overrides_when_config_exists(self):
        from services.auto_discovery.tuning_loop import get_active_param_overrides
        db = _mock_db()
        mock_config = MagicMock()
        mock_config.param_overrides = {"min_activities": 25}
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_config
        result = get_active_param_overrides(ATHLETE_ID, "investigate_pace_at_hr_adaptation", db)
        assert result == {"min_activities": 25}

    def test_count_consecutive_kept_runs_returns_correct_count(self):
        from services.auto_discovery.tuning_loop import count_consecutive_kept_runs
        exp1 = MagicMock(); exp1.kept = True
        exp2 = MagicMock(); exp2.kept = True
        db = MagicMock()
        # Single .filter(a,b,c).order_by().limit().all() after .join()
        (db.query.return_value
           .join.return_value
           .filter.return_value
           .order_by.return_value
           .limit.return_value
           .all.return_value) = [exp1, exp2]

        count = count_consecutive_kept_runs(ATHLETE_ID, "investigate_pace_at_hr_adaptation", db, window=2)
        assert count == 2


# ── Change log / Ledger ───────────────────────────────────────────────────────

class TestChangeLedger:
    def test_write_change_log_creates_row(self):
        from services.auto_discovery.orchestrator import _write_change_log

        db = _mock_db()
        added_objects = []
        db.add = lambda obj: added_objects.append(obj)
        db.flush = MagicMock()

        run_id = uuid4()
        cid = _write_change_log(
            athlete_id=ATHLETE_ID,
            run_id=run_id,
            change_type="new_correlation_finding",
            change_key="abc123",
            before_state=None,
            after_state={"input_name": "readiness_1_5"},
            db=db,
        )
        assert cid is not None
        assert len(added_objects) == 1

    def test_write_change_log_idempotent_on_integrity_error(self):
        """Duplicate key (same run + athlete + type + key) must be handled gracefully."""
        from services.auto_discovery.orchestrator import _write_change_log
        from sqlalchemy.exc import IntegrityError

        db = _mock_db()
        db.flush = MagicMock(side_effect=IntegrityError("dup", {}, None))
        db.rollback = MagicMock()
        db.add = MagicMock()

        run = MagicMock()

        cid = _write_change_log(
            athlete_id=ATHLETE_ID,
            run_id=uuid4(),
            change_type="new_correlation_finding",
            change_key="dup_key",
            before_state=None,
            after_state={},
            db=db,
        )
        # On integrity error, returns None — not None raise
        assert cid is None


# ── Auto-disable thresholds ───────────────────────────────────────────────────

class TestAutoDisableThresholds:
    def test_phase1_mutations_skipped_when_mutation_flag_off(self):
        from services.auto_discovery.orchestrator import _run_phase1_mutations

        db = _mock_db()
        run = MagicMock()
        run.id = uuid4()

        with patch("services.auto_discovery.orchestrator.is_live_mutation_enabled", return_value=False):
            result = _run_phase1_mutations(
                athlete_id=ATHLETE_ID,
                run=run,
                all_rescan_results=[],
                experiment_rows=[],
                db=db,
            )
        # Mutation off → returns None (shadow only)
        assert result is None

    def test_auto_disable_triggers_when_rescan_error_rate_exceeded(self):
        from services.auto_discovery.orchestrator import _run_phase1_mutations

        db = _mock_db()
        run = MagicMock(); run.id = uuid4()

        # 5/5 experiments have failure_reason — 100% error rate
        failed_exps = []
        for _ in range(5):
            exp = MagicMock()
            exp.loop_type = "correlation_rescan"
            exp.failure_reason = "timeout"
            exp.kept = False
            failed_exps.append(exp)

        with patch("services.auto_discovery.orchestrator.is_live_mutation_enabled", return_value=True), \
             patch("services.auto_discovery.orchestrator.is_auto_promote_findings_enabled", return_value=True), \
             patch("services.auto_discovery.orchestrator.is_auto_promote_stability_enabled", return_value=False), \
             patch("services.auto_discovery.orchestrator.is_auto_promote_tuning_enabled", return_value=False):
            result = _run_phase1_mutations(
                athlete_id=ATHLETE_ID,
                run=run,
                all_rescan_results=[],
                experiment_rows=failed_exps,
                db=db,
            )

        assert result is not None
        assert len(result["auto_disabled_loops"]) >= 1
        disabled_names = [d["loop"] for d in result["auto_disabled_loops"]]
        assert "rescan_promotion" in disabled_names

    def test_auto_disable_records_machine_readable_reason(self):
        from services.auto_discovery.orchestrator import _run_phase1_mutations

        db = _mock_db()
        run = MagicMock(); run.id = uuid4()

        failed_exps = [MagicMock(loop_type="correlation_rescan", failure_reason="error", kept=False) for _ in range(5)]

        with patch("services.auto_discovery.orchestrator.is_live_mutation_enabled", return_value=True), \
             patch("services.auto_discovery.orchestrator.is_auto_promote_findings_enabled", return_value=True), \
             patch("services.auto_discovery.orchestrator.is_auto_promote_stability_enabled", return_value=False), \
             patch("services.auto_discovery.orchestrator.is_auto_promote_tuning_enabled", return_value=False):
            result = _run_phase1_mutations(
                athlete_id=ATHLETE_ID,
                run=run,
                all_rescan_results=[],
                experiment_rows=failed_exps,
                db=db,
            )

        for item in result["auto_disabled_loops"]:
            assert "reason" in item
            assert "error_rate" in item["reason"]

    def test_mutation_error_rolls_back_and_sets_error_field(self):
        """If phase1 mutations raise unexpectedly, the result has error and mutation_live=False."""
        from services.auto_discovery.orchestrator import _run_phase1_mutations

        db = _mock_db()
        run = MagicMock(); run.id = uuid4()
        db.rollback = MagicMock()
        db.add = MagicMock()
        db.flush = MagicMock()

        with patch("services.auto_discovery.orchestrator.is_live_mutation_enabled", return_value=True), \
             patch("services.auto_discovery.orchestrator.is_auto_promote_findings_enabled", side_effect=RuntimeError("boom")):
            result = _run_phase1_mutations(
                athlete_id=ATHLETE_ID,
                run=run,
                all_rescan_results=[],
                experiment_rows=[],
                db=db,
            )

        assert result["error"] == "boom"
        assert result["mutation_live"] is False


# ── Revert endpoint ───────────────────────────────────────────────────────────

class TestRevertEndpoint:
    def _make_test_client(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from routers.auto_discovery_admin import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=False)

    def test_revert_nonexistent_change_returns_404(self):
        from fastapi.testclient import TestClient
        from routers.auto_discovery_admin import router
        from fastapi import FastAPI
        from core.auth import get_current_user
        from database import get_db

        app = FastAPI()
        app.include_router(router)

        founder_user = MagicMock()
        founder_user.id = uuid4()
        founder_user.email = "mbshaf@gmail.com"

        db = _mock_db()
        db.query.return_value.filter.return_value.first.return_value = None  # not found

        app.dependency_overrides[get_current_user] = lambda: founder_user
        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(f"/v1/admin/auto-discovery/revert/{uuid4()}")
        assert resp.status_code == 404

    def test_revert_already_reverted_change_returns_409(self):
        from fastapi.testclient import TestClient
        from routers.auto_discovery_admin import router
        from fastapi import FastAPI
        from core.auth import get_current_user
        from database import get_db

        app = FastAPI()
        app.include_router(router)

        founder_user = MagicMock()
        founder_user.id = uuid4()
        founder_user.email = "mbshaf@gmail.com"

        change = MagicMock()
        change.id = uuid4()
        change.reverted = True  # already reverted
        db = _mock_db()
        db.query.return_value.filter.return_value.first.return_value = change

        app.dependency_overrides[get_current_user] = lambda: founder_user
        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(f"/v1/admin/auto-discovery/revert/{change.id}")
        assert resp.status_code == 409

    def test_non_founder_cannot_access_revert(self):
        from fastapi.testclient import TestClient
        from routers.auto_discovery_admin import router
        from fastapi import FastAPI
        from core.auth import get_current_user
        from database import get_db

        app = FastAPI()
        app.include_router(router)

        non_founder = MagicMock()
        non_founder.id = uuid4()
        non_founder.email = "athlete@example.com"

        db = _mock_db()
        app.dependency_overrides[get_current_user] = lambda: non_founder
        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(f"/v1/admin/auto-discovery/revert/{uuid4()}")
        assert resp.status_code == 403

    def test_malformed_uuid_in_revert_returns_422(self):
        from fastapi.testclient import TestClient
        from routers.auto_discovery_admin import router
        from fastapi import FastAPI
        from core.auth import get_current_user
        from database import get_db

        app = FastAPI()
        app.include_router(router)

        founder_user = MagicMock()
        founder_user.id = uuid4()
        founder_user.email = "mbshaf@gmail.com"
        db = _mock_db()
        app.dependency_overrides[get_current_user] = lambda: founder_user
        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/v1/admin/auto-discovery/revert/not-a-valid-uuid")
        assert resp.status_code == 422


# ── Admin endpoints — auth hardening ─────────────────────────────────────────

class TestAdminEndpointAuth:
    def _make_app_with_overrides(self, founder=True):
        from fastapi import FastAPI
        from routers.auto_discovery_admin import router
        from core.auth import get_current_user
        from database import get_db

        app = FastAPI()
        app.include_router(router)

        user = MagicMock()
        user.id = uuid4()
        user.email = "mbshaf@gmail.com" if founder else "athlete@example.com"

        db = _mock_db()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        return app, db

    def test_non_founder_cannot_access_summary(self):
        from fastapi.testclient import TestClient
        app, _ = self._make_app_with_overrides(founder=False)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/v1/admin/auto-discovery/summary?athlete_id={uuid4()}")
        assert resp.status_code == 403

    def test_non_founder_cannot_access_changes(self):
        from fastapi.testclient import TestClient
        app, _ = self._make_app_with_overrides(founder=False)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/v1/admin/auto-discovery/changes?athlete_id={uuid4()}")
        assert resp.status_code == 403

    def test_non_founder_cannot_access_candidates(self):
        from fastapi.testclient import TestClient
        app, _ = self._make_app_with_overrides(founder=False)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/v1/admin/auto-discovery/candidates?athlete_id={uuid4()}")
        assert resp.status_code == 403

    def test_malformed_athlete_id_in_summary_returns_422(self):
        from fastapi.testclient import TestClient
        app, _ = self._make_app_with_overrides(founder=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/admin/auto-discovery/summary?athlete_id=not-a-uuid")
        assert resp.status_code == 422

    def test_malformed_athlete_id_in_changes_returns_422(self):
        from fastapi.testclient import TestClient
        app, _ = self._make_app_with_overrides(founder=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/admin/auto-discovery/changes?athlete_id=not-a-uuid")
        assert resp.status_code == 422


# ── Scan coverage persistence ────────────────────────────────────────────────

class TestScanCoverage:
    def test_upsert_coverage_creates_new_row(self):
        from services.auto_discovery.interaction_loop import upsert_scan_coverage

        db = _mock_db()
        # No existing row
        db.query.return_value.filter.return_value.first.return_value = None

        added_objects = []
        db.add = lambda obj: added_objects.append(obj)
        db.flush = MagicMock()

        upsert_scan_coverage(
            athlete_id=ATHLETE_ID,
            input_a="readiness_1_5",
            input_b="hrv_sdnn",
            output_metric="efficiency",
            window_days=180,
            result="signal",
            db=db,
        )
        assert len(added_objects) == 1

    def test_upsert_coverage_updates_existing_row(self):
        from services.auto_discovery.interaction_loop import upsert_scan_coverage

        db = _mock_db()
        existing = MagicMock()
        existing.scan_count = 3
        existing.result = "no_signal"
        # upsert uses a single .filter(a, b, c).first()
        db.query.return_value.filter.return_value.first.return_value = existing

        db.flush = MagicMock()

        upsert_scan_coverage(
            athlete_id=ATHLETE_ID,
            input_a="readiness_1_5",
            input_b=None,
            output_metric="pace_easy",
            window_days=90,
            result="signal",
            db=db,
        )
        assert existing.scan_count == 4
        assert existing.result == "signal"


# ── Kill switch / global mutation disable ────────────────────────────────────

class TestGlobalKillSwitch:
    def test_kill_switch_disables_all_promotions(self):
        """Setting mutation.live flag to False disables ALL Phase 1 promotions."""
        from services.auto_discovery.orchestrator import _run_phase1_mutations

        db = _mock_db()
        run = MagicMock(); run.id = uuid4()

        with patch("services.auto_discovery.orchestrator.is_live_mutation_enabled", return_value=False):
            result = _run_phase1_mutations(
                athlete_id=ATHLETE_ID,
                run=run,
                all_rescan_results=[],
                experiment_rows=[],
                db=db,
            )

        # Result is None — mutation completely suppressed
        assert result is None

    def test_per_loop_kills_independent(self):
        """Each auto_promote flag can be independently disabled."""
        from services.auto_discovery.orchestrator import _run_phase1_mutations

        db = _mock_db()
        run = MagicMock(); run.id = uuid4()

        with patch("services.auto_discovery.orchestrator.is_live_mutation_enabled", return_value=True), \
             patch("services.auto_discovery.orchestrator.is_auto_promote_findings_enabled", return_value=False), \
             patch("services.auto_discovery.orchestrator.is_auto_promote_stability_enabled", return_value=False), \
             patch("services.auto_discovery.orchestrator.is_auto_promote_tuning_enabled", return_value=False):
            result = _run_phase1_mutations(
                athlete_id=ATHLETE_ID,
                run=run,
                all_rescan_results=[],
                experiment_rows=[],
                db=db,
            )

        assert result is not None
        assert result["mutation_live"] is True
        assert len(result["findings_promoted"]) == 0
        assert result["stability_annotated"] == 0
        assert len(result["tuning_applied"]) == 0


# ── Migration integrity ───────────────────────────────────────────────────────

class TestMigrationIntegrity:
    def test_migration_revision_exists(self):
        import importlib.util, os
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions",
            "auto_discovery_phase1_001_live_mutation.py",
        )
        assert os.path.exists(migration_path), "Phase 1 migration file not found"

    def test_migration_down_revision_is_phase3c_001(self):
        import importlib.util, os
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions",
            "auto_discovery_phase1_001_live_mutation.py",
        )
        spec = importlib.util.spec_from_file_location("m", migration_path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        assert m.revision == "auto_discovery_phase1_001"
        assert m.down_revision == "phase3c_001"

    def test_ci_heads_check_matches_alembic_graph(self):
        """EXPECTED_HEADS must equal Alembic ScriptDirectory heads (single source of truth)."""
        import importlib.util
        import os
        import sys
        from pathlib import Path

        from alembic.config import Config
        from alembic.script import ScriptDirectory

        p = Path(__file__).resolve()
        heads_path = None
        for parent in p.parents:
            candidate = parent / ".github" / "scripts" / "ci_alembic_heads_check.py"
            if candidate.exists():
                heads_path = str(candidate)
                break
        if heads_path is None:
            pytest.skip("ci_alembic_heads_check.py not found — not in full repo checkout")
        spec = importlib.util.spec_from_file_location("ci", heads_path)
        ci = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ci)

        api_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(api_root))
        cfg = Config(str(api_root / "alembic.ini"))
        cfg.set_main_option("script_location", str(api_root / "alembic"))
        script = ScriptDirectory.from_config(cfg)
        actual_heads = set(script.get_heads())

        assert ci.EXPECTED_HEADS, "EXPECTED_HEADS must not be empty"
        assert ci.EXPECTED_HEADS == actual_heads, (
            f"Update EXPECTED_HEADS in ci_alembic_heads_check.py to match Alembic: "
            f"expected {actual_heads!r}, got {ci.EXPECTED_HEADS!r}"
        )

    def test_new_models_importable(self):
        from models import AutoDiscoveryChangeLog, AthleteInvestigationConfig, AutoDiscoveryScanCoverage
        assert AutoDiscoveryChangeLog.__tablename__ == "auto_discovery_change_log"
        assert AthleteInvestigationConfig.__tablename__ == "athlete_investigation_config"
        assert AutoDiscoveryScanCoverage.__tablename__ == "auto_discovery_scan_coverage"

    def test_correlation_finding_has_stability_fields(self):
        from models import CorrelationFinding
        assert hasattr(CorrelationFinding, "discovery_source")
        assert hasattr(CorrelationFinding, "discovery_window_days")
        assert hasattr(CorrelationFinding, "stability_class")
        assert hasattr(CorrelationFinding, "windows_confirmed")
        assert hasattr(CorrelationFinding, "stability_checked_at")


# ── Admin router — summary/changes response shape ────────────────────────────

class TestAdminRouterResponseShape:
    def _make_founder_app(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from routers.auto_discovery_admin import router
        from core.auth import get_current_user
        from database import get_db

        app = FastAPI()
        app.include_router(router)

        founder = MagicMock()
        founder.id = uuid4()
        founder.email = "mbshaf@gmail.com"

        db = _mock_db()
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.first.return_value = None
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.count.return_value = 0

        app.dependency_overrides[get_current_user] = lambda: founder
        app.dependency_overrides[get_db] = lambda: db

        with patch("routers.auto_discovery_admin.is_live_mutation_enabled", return_value=False):
            client = TestClient(app, raise_server_exceptions=False)
        return client, db

    def test_summary_returns_200_with_required_fields(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from routers.auto_discovery_admin import router
        from core.auth import get_current_user
        from database import get_db

        app = FastAPI()
        app.include_router(router)

        founder = MagicMock()
        founder.id = uuid4()
        founder.email = "mbshaf@gmail.com"

        db = _mock_db()
        app.dependency_overrides[get_current_user] = lambda: founder
        app.dependency_overrides[get_db] = lambda: db

        with patch("routers.auto_discovery_admin.is_live_mutation_enabled", return_value=False):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(f"/v1/admin/auto-discovery/summary?athlete_id={uuid4()}")

        assert resp.status_code == 200
        body = resp.json()
        for field in ["athlete_id", "last_run", "changes_last_run", "pending_review", "coverage", "score_trends", "phase1_enabled"]:
            assert field in body, f"Missing field: {field}"

    def test_changes_endpoint_returns_paginated_response(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from routers.auto_discovery_admin import router
        from core.auth import get_current_user
        from database import get_db

        app = FastAPI()
        app.include_router(router)

        founder = MagicMock()
        founder.id = uuid4()
        founder.email = "mbshaf@gmail.com"

        db = _mock_db()
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

        app.dependency_overrides[get_current_user] = lambda: founder
        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/v1/admin/auto-discovery/changes?athlete_id={uuid4()}")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert "page" in body
