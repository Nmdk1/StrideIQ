"""
Tests for AutoDiscovery Phase 0C.

Covers:
WS1 — 0B fidelity gaps:
  1A) interaction_scan score summary is value-bearing (not None)
  1B) FQS provenance preserved in persisted/report output

WS2 — Durable candidate memory:
  - same candidate across two runs increments times_seen
  - uniqueness constraint prevents duplicate rows
  - candidate rollup survives across runs

WS3 — Founder review state machine:
  - approve/reject/defer persist
  - optional note persists
  - review history auditable via review_log

WS4 — Controlled promotion staging:
  - approved candidate can be staged with promotion_target
  - staging intent persists
  - no athlete-facing mutation
  - no live registry mutation

WS5 — Founder review query output:
  - open candidates sorted by value
  - seen_multiple_times section populated
  - approved/rejected/deferred history present
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, call

import pytest


# ─────────────────────────────────────────────────────────────────────────────
#  WS1A — Interaction scan score summary is value-bearing
# ─────────────────────────────────────────────────────────────────────────────

class TestInteractionScanScoreSummary:
    """Phase 0C WS1-1A: aggregate_baseline_score must be numeric when candidates exist."""

    def _make_interaction_result(self, n_kept: int = 2, metric: str = "efficiency") -> Dict[str, Any]:
        """Create a mock interaction result with n_kept scored candidates."""
        from services.auto_discovery.interaction_loop import INTERACTION_KEEP_THRESHOLD

        kept_candidates = [
            {
                "factors": ["hrv_score", "weekly_volume"],
                "output_metric": metric,
                "effect_size": 0.85,
                "n_high": 12,
                "n_low": 10,
                "direction_label": f"higher {metric} when both hrv_score and weekly_volume are high",
                "interaction_score": 0.60,
                "score_components": {"effect_size_norm": 0.567, "sample_support": 0.6},
            }
        ] * n_kept

        return {
            "loop_type": "interaction_scan",
            "target_name": f"pairwise:{metric}",
            "baseline_config": {"output_metric": metric, "days": 180, "min_effect_size": 0.5},
            "candidate_config": {},
            "result_summary": {
                "output_metric": metric,
                "interactions_tested": n_kept + 3,
                "interactions_kept": n_kept,
                "top_interactions": kept_candidates,
                "threshold_statement": None,
                "error": None,
                "score_provenance": {
                    "component_values": {"effect_size_norm": 0.567, "sample_support": 0.6},
                    "component_quality": {"effect_size_norm": "exact", "sample_support": "exact"},
                    "has_inferred_components": False,
                },
            },
            "baseline_score": 0.60,  # mean interaction_score of kept
            "candidate_score": None,
            "score_delta": None,
            "failure_reason": None,
            "runtime_ms": 15,
        }

    def test_interaction_scan_summary_has_numeric_aggregate_score(self):
        """When interaction candidates exist, aggregate_baseline_score must not be None."""
        from services.auto_discovery.orchestrator import _build_score_summary

        # Build two experiment rows from the mock result.
        exp1 = MagicMock()
        exp1.loop_type = "interaction_scan"
        exp1.kept = True
        exp1.baseline_score = 0.60
        exp1.candidate_score = None
        exp1.score_delta = None

        exp2 = MagicMock()
        exp2.loop_type = "interaction_scan"
        exp2.kept = True
        exp2.baseline_score = 0.45
        exp2.candidate_score = None
        exp2.score_delta = None

        summary = _build_score_summary(
            experiment_rows=[exp1, exp2],
            rescan_results=[],
            stability={"stable": [], "strengthening": [], "recent_only": [], "unstable": []},
        )

        assert "interaction_scan" in summary
        scan = summary["interaction_scan"]
        assert scan["experiments_run"] == 2
        assert scan["kept"] == 2
        # The key 0C requirement: aggregate_baseline_score must be a real number when candidates kept.
        assert scan["aggregate_baseline_score"] is not None
        assert isinstance(scan["aggregate_baseline_score"], float)
        assert 0.0 < scan["aggregate_baseline_score"] < 1.0
        # aggregate_all_score covers all experiments (value-bearing, not None).
        assert scan["aggregate_all_score"] is not None
        assert isinstance(scan["aggregate_all_score"], float)
        # Loop design explicitly documented; candidate score absent by design.
        assert scan["loop_design"] == "single_arm_discovery"
        assert scan["aggregate_candidate_score"] is None  # single-arm: no A/B variant
        assert scan["aggregate_delta"] is None

    def test_interaction_scan_summary_none_when_no_candidates(self):
        """When no interaction experiments ran, interaction_scan section absent."""
        from services.auto_discovery.orchestrator import _build_score_summary

        exp = MagicMock()
        exp.loop_type = "correlation_rescan"
        exp.kept = True
        exp.baseline_score = 0.5
        exp.candidate_score = None
        exp.score_delta = None

        summary = _build_score_summary(
            experiment_rows=[exp],
            rescan_results=[],
            stability={"stable": [], "strengthening": [], "recent_only": [], "unstable": []},
        )
        # No interaction_scan experiments → section should be absent (not polluted).
        assert "interaction_scan" not in summary

    def test_aggregate_interaction_score_returns_mean(self):
        """_aggregate_interaction_score returns mean of interaction_score values."""
        from services.auto_discovery.interaction_loop import _aggregate_interaction_score

        candidates = [
            {"interaction_score": 0.6},
            {"interaction_score": 0.4},
            {"interaction_score": 0.8},
        ]
        result = _aggregate_interaction_score(candidates)
        assert result is not None
        assert abs(result - round((0.6 + 0.4 + 0.8) / 3, 4)) < 1e-6

    def test_aggregate_interaction_score_returns_none_for_empty(self):
        """_aggregate_interaction_score returns None when no candidates."""
        from services.auto_discovery.interaction_loop import _aggregate_interaction_score

        assert _aggregate_interaction_score([]) is None


# ─────────────────────────────────────────────────────────────────────────────
#  WS1B — FQS provenance preserved
# ─────────────────────────────────────────────────────────────────────────────

class TestFQSProvenancePreserved:
    """Phase 0C WS1-1B: score_provenance block must appear in experiment/report output."""

    def test_interaction_result_has_score_provenance(self):
        """Interaction loop result_summary must contain score_provenance."""
        from services.auto_discovery.interaction_loop import (
            run_pairwise_interaction_scan,
            INTERACTION_KEEP_THRESHOLD,
        )
        from services.auto_discovery.interaction_loop import _build_interaction_provenance, _score_interaction

        # Test _build_interaction_provenance directly.
        scored_candidate = _score_interaction({
            "factors": ["hrv_score", "weekly_volume"],
            "output_metric": "efficiency",
            "effect_size": 1.2,
            "n_high": 12,
            "n_low": 10,
            "direction_label": "higher efficiency when both are high",
        })
        provenance = _build_interaction_provenance([scored_candidate])

        assert "component_values" in provenance
        assert "component_quality" in provenance
        assert "has_inferred_components" in provenance
        # Interaction provenance uses exact measurements.
        assert provenance["has_inferred_components"] is False
        assert provenance["component_quality"]["effect_size_norm"] == "exact"
        assert provenance["component_quality"]["sample_support"] == "exact"

    def test_interaction_provenance_empty_for_no_candidates(self):
        """_build_interaction_provenance returns valid shape for empty input."""
        from services.auto_discovery.interaction_loop import _build_interaction_provenance

        provenance = _build_interaction_provenance([])
        assert provenance["component_values"] == {}
        assert "has_inferred_components" in provenance

    def test_tuning_provenance_has_component_quality(self):
        """Tuning loop provenance includes component quality labels."""
        from services.auto_discovery.tuning_loop import _build_tuning_provenance
        from services.auto_discovery.fqs_adapters import AthleteFindingFQSAdapter

        adapter = AthleteFindingFQSAdapter()
        provenance = _build_tuning_provenance(adapter)

        assert "component_values" in provenance
        assert "component_quality" in provenance
        assert "has_inferred_components" in provenance
        # AthleteFindingFQSAdapter has all inferred components.
        assert provenance["has_inferred_components"] is True
        assert provenance["component_quality"]["confidence"] == "inferred"
        assert provenance["component_quality"]["actionability"] == "registry_default"

    def test_rescan_provenance_from_score_rescan_window(self):
        """_score_rescan_window includes score_provenance in output."""
        from services.auto_discovery.orchestrator import _score_rescan_window
        from services.auto_discovery.fqs_adapters import CorrelationFindingFQSAdapter

        adapter = CorrelationFindingFQSAdapter()
        result_summary = {
            "findings_by_metric": {
                "efficiency": [
                    {
                        "input_name": "hrv_score",
                        "correlation_coefficient": 0.6,
                        "p_value": 0.01,
                        "sample_size": 30,
                        "direction": "positive",
                        "time_lag_days": 3,
                        "strength": "moderate",
                    }
                ]
            }
        }
        fqs_scores = _score_rescan_window(result_summary, adapter)

        assert "score_provenance" in fqs_scores
        provenance = fqs_scores["score_provenance"]
        assert "component_values" in provenance
        assert "component_quality" in provenance
        assert "has_inferred_components" in provenance
        assert isinstance(provenance["has_inferred_components"], bool)

    def test_rescan_provenance_component_quality_labels(self):
        """Rescan provenance preserves exact/inferred/registry_default labels."""
        from services.auto_discovery.orchestrator import _score_rescan_window
        from services.auto_discovery.fqs_adapters import CorrelationFindingFQSAdapter

        adapter = CorrelationFindingFQSAdapter()
        result_summary = {
            "findings_by_metric": {
                "efficiency": [
                    {
                        "correlation_coefficient": 0.7,
                        "sample_size": 25,
                        "time_lag_days": 0,
                        "strength": "strong",
                    }
                ]
            }
        }
        fqs_scores = _score_rescan_window(result_summary, adapter)
        quality = fqs_scores["score_provenance"]["component_quality"]

        assert quality["confidence"] == "exact"
        assert quality["actionability"] == "registry_default"
        assert quality["specificity"] == "inferred"
        assert quality["stability"] == "inferred"


# ─────────────────────────────────────────────────────────────────────────────
#  WS2 — Durable candidate memory
# ─────────────────────────────────────────────────────────────────────────────

class TestDurableCandidateMemory:
    """Phase 0C WS2: cross-run candidate upsert behavior."""

    def _make_db(self):
        """Build a minimal in-memory mock DB for candidate upsert tests."""
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        return db

    def _make_run(self, run_id=None):
        run = MagicMock()
        run.id = run_id or uuid.uuid4()
        return run

    def test_candidate_key_stable_finding(self):
        """Stable finding candidate key is deterministic."""
        from services.auto_discovery.orchestrator import _make_candidate_key

        payload = {
            "input_name": "hrv_score",
            "output_name": "efficiency",
            "direction": "positive",
        }
        key1 = _make_candidate_key("stable_finding", payload)
        key2 = _make_candidate_key("stable_finding", payload)
        assert key1 == key2
        assert "hrv_score" in key1
        assert "efficiency" in key1

    def test_candidate_key_interaction(self):
        """Interaction candidate key is deterministic and factor-order independent."""
        from services.auto_discovery.orchestrator import _make_candidate_key

        payload1 = {
            "factors": ["hrv_score", "weekly_volume"],
            "output_metric": "efficiency",
            "direction_label": "higher efficiency when both are high",
        }
        payload2 = {
            "factors": ["weekly_volume", "hrv_score"],  # reversed order
            "output_metric": "efficiency",
            "direction_label": "higher efficiency when both are high",
        }
        key1 = _make_candidate_key("interaction", payload1)
        key2 = _make_candidate_key("interaction", payload2)
        # Keys must be identical regardless of factor order.
        assert key1 == key2

    def test_candidate_key_registry_tuning(self):
        """Registry tuning candidate key is deterministic."""
        from services.auto_discovery.orchestrator import _make_candidate_key

        payload = {
            "investigation": "investigate_heat_tax",
            "parameter_change": {"min_activities": 5},
        }
        key1 = _make_candidate_key("registry_tuning", payload)
        key2 = _make_candidate_key("registry_tuning", payload)
        assert key1 == key2
        assert "investigate_heat_tax" in key1

    def test_new_candidate_inserted_with_open_status(self):
        """First time a candidate is seen, it is inserted with status='open'."""
        from services.auto_discovery.orchestrator import _upsert_candidates

        athlete_id = uuid.uuid4()
        run = self._make_run()
        db = self._make_db()

        report = {
            "stable_findings": [],
            "strengthened_findings": [],
            "candidate_interactions": {
                "cleared_threshold": True,
                "candidates": [
                    {
                        "factors": ["hrv_score", "weekly_volume"],
                        "output_metric": "efficiency",
                        "direction_label": "higher efficiency when both are high",
                        "interaction_score": 0.65,
                    }
                ],
            },
            "registry_tuning_candidates": {"cleared_threshold": False, "candidates": []},
        }

        _upsert_candidates(athlete_id=athlete_id, run=run, report=report, db=db)

        # Verify db.add was called with an AutoDiscoveryCandidate.
        db.add.assert_called_once()
        added = db.add.call_args[0][0]
        from models import AutoDiscoveryCandidate
        assert isinstance(added, AutoDiscoveryCandidate)
        assert added.current_status == "open"
        assert added.times_seen == 1

    def test_existing_candidate_increments_times_seen(self):
        """Re-appearing candidate increments times_seen and updates last_seen_run_id."""
        from services.auto_discovery.orchestrator import _upsert_candidates
        from models import AutoDiscoveryCandidate

        athlete_id = uuid.uuid4()
        run1_id = uuid.uuid4()
        run2_id = uuid.uuid4()

        existing = MagicMock(spec=AutoDiscoveryCandidate)
        existing.times_seen = 1
        existing.current_status = "open"
        existing.latest_score = 0.55
        existing.latest_score_delta = None
        existing.provenance_snapshot = None
        existing.last_seen_run_id = run1_id

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = existing

        run2 = self._make_run(run_id=run2_id)
        report = {
            "stable_findings": [],
            "strengthened_findings": [],
            "candidate_interactions": {
                "cleared_threshold": True,
                "candidates": [
                    {
                        "factors": ["hrv_score", "weekly_volume"],
                        "output_metric": "efficiency",
                        "direction_label": "higher efficiency when both are high",
                        "interaction_score": 0.70,
                    }
                ],
            },
            "registry_tuning_candidates": {"cleared_threshold": False, "candidates": []},
        }

        _upsert_candidates(athlete_id=athlete_id, run=run2, report=report, db=db)

        # times_seen should have been incremented.
        assert existing.times_seen == 2
        assert existing.last_seen_run_id == run2_id
        # db.add should NOT be called (update path, not insert).
        db.add.assert_not_called()

    def test_existing_review_status_preserved_on_reappearance(self):
        """current_status='approved' must not be overwritten when candidate re-appears."""
        from services.auto_discovery.orchestrator import _upsert_candidates
        from models import AutoDiscoveryCandidate

        athlete_id = uuid.uuid4()
        run_id = uuid.uuid4()

        existing = MagicMock(spec=AutoDiscoveryCandidate)
        existing.times_seen = 3
        existing.current_status = "approved"  # already reviewed
        existing.latest_score = 0.6
        existing.latest_score_delta = None
        existing.provenance_snapshot = None
        existing.last_seen_run_id = uuid.uuid4()

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = existing

        run = self._make_run(run_id=run_id)
        report = {
            "stable_findings": [],
            "strengthened_findings": [],
            "candidate_interactions": {
                "cleared_threshold": True,
                "candidates": [
                    {
                        "factors": ["hrv_score", "weekly_volume"],
                        "output_metric": "efficiency",
                        "direction_label": "higher efficiency when both are high",
                        "interaction_score": 0.72,
                    }
                ],
            },
            "registry_tuning_candidates": {"cleared_threshold": False, "candidates": []},
        }

        _upsert_candidates(athlete_id=athlete_id, run=run, report=report, db=db)

        # Approved status must be preserved.
        assert existing.current_status == "approved"
        assert existing.times_seen == 4  # incremented


# ─────────────────────────────────────────────────────────────────────────────
#  WS3 — Founder review state machine
# ─────────────────────────────────────────────────────────────────────────────

class TestFounderReviewStateMachine:
    """Phase 0C WS3: approve/reject/defer + audit log."""

    def _make_candidate_mock(self, status: str = "open"):
        from models import AutoDiscoveryCandidate
        c = MagicMock(spec=AutoDiscoveryCandidate)
        c.id = uuid.uuid4()
        c.athlete_id = uuid.uuid4()
        c.current_status = status
        c.reviewed_at = None
        c.updated_at = None
        c.promotion_target = None
        c.promotion_note = None
        return c

    def _patch_review(self, candidate, db_mock=None):
        """Patch db.query to return the candidate and return db mock."""
        db = db_mock or MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = candidate
        return db

    def test_approve_sets_status_and_review_log(self):
        """approve action: current_status → 'approved', review log created."""
        from services.auto_discovery.orchestrator import review_candidate
        from models import AutoDiscoveryReviewLog

        candidate = self._make_candidate_mock("open")
        db = self._patch_review(candidate)

        result = review_candidate(
            candidate_id=candidate.id,
            action="approve",
            db=db,
        )

        assert candidate.current_status == "approved"
        assert candidate.reviewed_at is not None
        # Verify review log was added.
        db.add.assert_called_once()
        log_arg = db.add.call_args[0][0]
        assert isinstance(log_arg, AutoDiscoveryReviewLog)
        assert log_arg.action == "approve"
        assert log_arg.previous_status == "open"
        assert log_arg.new_status == "approved"

    def test_reject_sets_status(self):
        """reject action: current_status → 'rejected'."""
        from services.auto_discovery.orchestrator import review_candidate

        candidate = self._make_candidate_mock("open")
        db = self._patch_review(candidate)

        review_candidate(candidate_id=candidate.id, action="reject", db=db)
        assert candidate.current_status == "rejected"

    def test_defer_sets_status(self):
        """defer action: current_status → 'deferred'."""
        from services.auto_discovery.orchestrator import review_candidate

        candidate = self._make_candidate_mock("open")
        db = self._patch_review(candidate)

        review_candidate(candidate_id=candidate.id, action="defer", db=db)
        assert candidate.current_status == "deferred"

    def test_note_persists(self):
        """Optional note is stored on the candidate and review log."""
        from services.auto_discovery.orchestrator import review_candidate
        from models import AutoDiscoveryReviewLog

        candidate = self._make_candidate_mock("open")
        db = self._patch_review(candidate)

        review_candidate(
            candidate_id=candidate.id,
            action="approve",
            db=db,
            note="Strong finding, validate next week",
        )

        # Note on candidate.
        assert candidate.promotion_note == "Strong finding, validate next week"
        # Note on log.
        log_arg = db.add.call_args[0][0]
        assert log_arg.note == "Strong finding, validate next week"

    def test_invalid_action_raises(self):
        """Invalid action raises ValueError."""
        from services.auto_discovery.orchestrator import review_candidate

        candidate = self._make_candidate_mock("open")
        db = self._patch_review(candidate)

        with pytest.raises(ValueError, match="Invalid action"):
            review_candidate(candidate_id=candidate.id, action="delete", db=db)

    def test_missing_candidate_raises(self):
        """Unknown candidate_id raises ValueError."""
        from services.auto_discovery.orchestrator import review_candidate

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None

        with pytest.raises(ValueError, match="not found"):
            review_candidate(candidate_id=uuid.uuid4(), action="approve", db=db)


# ─────────────────────────────────────────────────────────────────────────────
#  WS4 — Controlled promotion staging
# ─────────────────────────────────────────────────────────────────────────────

class TestControlledPromotionStaging:
    """Phase 0C WS4: approved candidates can be staged; no live mutation."""

    def _make_candidate_mock(self, status: str = "approved"):
        from models import AutoDiscoveryCandidate
        c = MagicMock(spec=AutoDiscoveryCandidate)
        c.id = uuid.uuid4()
        c.athlete_id = uuid.uuid4()
        c.current_status = status
        c.reviewed_at = None
        c.updated_at = None
        c.promotion_target = None
        c.promotion_note = None
        return c

    def test_stage_persists_promotion_target(self):
        """stage action sets promotion_target on candidate."""
        from services.auto_discovery.orchestrator import review_candidate

        candidate = self._make_candidate_mock("approved")
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = candidate

        review_candidate(
            candidate_id=candidate.id,
            action="stage",
            db=db,
            promotion_target="surface_candidate",
            note="Ready for product review",
        )

        assert candidate.promotion_target == "surface_candidate"
        assert candidate.promotion_note == "Ready for product review"
        assert candidate.current_status == "approved"

    def test_stage_invalid_target_raises(self):
        """stage with invalid promotion_target raises ValueError."""
        from services.auto_discovery.orchestrator import review_candidate

        candidate = self._make_candidate_mock("approved")
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = candidate

        with pytest.raises(ValueError, match="Invalid promotion_target"):
            review_candidate(
                candidate_id=candidate.id,
                action="stage",
                db=db,
                promotion_target="auto_apply_to_production",  # invalid
            )

    def test_stage_without_target_raises(self):
        """stage without promotion_target raises ValueError."""
        from services.auto_discovery.orchestrator import review_candidate

        candidate = self._make_candidate_mock("approved")
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = candidate

        with pytest.raises(ValueError, match="promotion_target is required"):
            review_candidate(
                candidate_id=candidate.id,
                action="stage",
                db=db,
            )

    def test_no_athlete_facing_mutation_from_staging(self):
        """Staging never writes to athlete-facing tables."""
        from services.auto_discovery.orchestrator import review_candidate
        from models import AutoDiscoveryReviewLog

        # The only ORM calls allowed are to AutoDiscoveryCandidate and AutoDiscoveryReviewLog.
        candidate = self._make_candidate_mock("approved")
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = candidate

        review_candidate(
            candidate_id=candidate.id,
            action="stage",
            db=db,
            promotion_target="registry_change_candidate",
        )

        # Only one db.add call — the review log.
        assert db.add.call_count == 1
        log = db.add.call_args[0][0]
        assert isinstance(log, AutoDiscoveryReviewLog)
        assert log.action == "stage"
        assert log.promotion_target == "registry_change_candidate"


# ─────────────────────────────────────────────────────────────────────────────
#  WS5 — Founder review query output
# ─────────────────────────────────────────────────────────────────────────────

class TestFounderReviewQueryOutput:
    """Phase 0C WS5: get_founder_review_summary returns structured output."""

    def _make_candidate(self, status: str, score: float, times_seen: int = 1):
        from models import AutoDiscoveryCandidate
        c = MagicMock(spec=AutoDiscoveryCandidate)
        c.id = uuid.uuid4()
        c.athlete_id = uuid.uuid4()
        c.candidate_type = "interaction"
        c.candidate_key = f"hrv_score:weekly_volume:efficiency:higher_{uuid.uuid4().hex[:4]}"
        c.current_status = status
        c.times_seen = times_seen
        c.latest_score = score
        c.latest_score_delta = 0.05
        c.first_seen_run_id = uuid.uuid4()
        c.last_seen_run_id = uuid.uuid4()
        c.promotion_target = None
        c.promotion_note = None
        c.reviewed_at = None
        c.latest_summary = {"output_metric": "efficiency"}
        c.provenance_snapshot = None
        return c

    def test_review_summary_sections_present(self):
        """get_founder_review_summary returns all required sections."""
        from services.auto_discovery.orchestrator import get_founder_review_summary

        athlete_id = uuid.uuid4()
        candidates = [
            self._make_candidate("open", 0.65, times_seen=2),
            self._make_candidate("open", 0.45, times_seen=1),
            self._make_candidate("approved", 0.80, times_seen=3),
            self._make_candidate("rejected", 0.20, times_seen=1),
            self._make_candidate("deferred", 0.50, times_seen=2),
        ]
        db = MagicMock()
        db.query.return_value.filter_by.return_value.all.return_value = candidates

        summary = get_founder_review_summary(athlete_id=athlete_id, db=db)

        assert "open_by_value" in summary
        assert "seen_multiple_times" in summary
        assert "approved" in summary
        assert "rejected" in summary
        assert "deferred" in summary
        assert summary["total_candidates"] == 5

    def test_open_candidates_sorted_by_score_desc(self):
        """open_by_value is sorted by latest_score descending."""
        from services.auto_discovery.orchestrator import get_founder_review_summary

        athlete_id = uuid.uuid4()
        c1 = self._make_candidate("open", 0.30)
        c2 = self._make_candidate("open", 0.80)
        c3 = self._make_candidate("open", 0.55)
        db = MagicMock()
        db.query.return_value.filter_by.return_value.all.return_value = [c1, c2, c3]

        summary = get_founder_review_summary(athlete_id=athlete_id, db=db)

        scores = [c["latest_score"] for c in summary["open_by_value"]]
        assert scores == sorted(scores, reverse=True)

    def test_seen_multiple_times_filters_correctly(self):
        """seen_multiple_times contains only open candidates with times_seen >= 2."""
        from services.auto_discovery.orchestrator import get_founder_review_summary

        athlete_id = uuid.uuid4()
        c_once = self._make_candidate("open", 0.5, times_seen=1)
        c_twice = self._make_candidate("open", 0.7, times_seen=2)
        c_many = self._make_candidate("open", 0.6, times_seen=5)
        db = MagicMock()
        db.query.return_value.filter_by.return_value.all.return_value = [c_once, c_twice, c_many]

        summary = get_founder_review_summary(athlete_id=athlete_id, db=db)

        recurring_times = [c["times_seen"] for c in summary["seen_multiple_times"]]
        assert all(t >= 2 for t in recurring_times)
        assert len(summary["seen_multiple_times"]) == 2

    def test_serialized_candidate_has_required_fields(self):
        """Each serialized candidate has id, candidate_type, times_seen, latest_score, etc."""
        from services.auto_discovery.orchestrator import get_founder_review_summary

        athlete_id = uuid.uuid4()
        c = self._make_candidate("open", 0.6)
        db = MagicMock()
        db.query.return_value.filter_by.return_value.all.return_value = [c]

        summary = get_founder_review_summary(athlete_id=athlete_id, db=db)

        item = summary["open_by_value"][0]
        assert "id" in item
        assert "candidate_type" in item
        assert "candidate_key" in item
        assert "current_status" in item
        assert "times_seen" in item
        assert "latest_score" in item
        assert "first_seen_run_id" in item
        assert "last_seen_run_id" in item


# ─────────────────────────────────────────────────────────────────────────────
#  Three-fix regression suite (advisor findings)
# ─────────────────────────────────────────────────────────────────────────────

class TestAdvisorFindingFixes:
    """
    Regression tests for the three advisor-review findings:
      Fix 1 (High)   — interaction_scan score summary aggregate_all_score is value-bearing
      Fix 2 (Medium) — stage action requires approved status
      Fix 3 (Medium) — interaction/tuning durable candidates carry provenance
    """

    # ── Fix 1: aggregate_all_score is numeric ────────────────────────────────

    def test_aggregate_all_score_is_numeric_when_experiments_exist(self):
        """aggregate_all_score must be a real float whenever interaction_scan ran."""
        from services.auto_discovery.orchestrator import _build_score_summary

        exp1 = MagicMock()
        exp1.loop_type = "interaction_scan"
        exp1.kept = False  # not kept — but all_score should still include it
        exp1.baseline_score = 0.30
        exp1.candidate_score = None
        exp1.score_delta = None

        exp2 = MagicMock()
        exp2.loop_type = "interaction_scan"
        exp2.kept = True
        exp2.baseline_score = 0.70
        exp2.candidate_score = None
        exp2.score_delta = None

        summary = _build_score_summary(
            experiment_rows=[exp1, exp2],
            rescan_results=[],
            stability={"stable": [], "strengthening": [], "recent_only": [], "unstable": []},
        )

        scan = summary["interaction_scan"]
        # aggregate_all_score covers kept + not-kept.
        assert scan["aggregate_all_score"] is not None
        assert isinstance(scan["aggregate_all_score"], float)
        assert abs(scan["aggregate_all_score"] - round((0.30 + 0.70) / 2, 4)) < 1e-6
        # aggregate_baseline_score is None because only 1 experiment is kept
        # and this test only checks all_score; kept score is a separate assertion.

    def test_aggregate_baseline_score_only_counts_kept(self):
        """aggregate_baseline_score reflects kept candidates only; not_kept excluded."""
        from services.auto_discovery.orchestrator import _build_score_summary

        kept = MagicMock()
        kept.loop_type = "interaction_scan"
        kept.kept = True
        kept.baseline_score = 0.80
        kept.candidate_score = None
        kept.score_delta = None

        not_kept = MagicMock()
        not_kept.loop_type = "interaction_scan"
        not_kept.kept = False
        not_kept.baseline_score = 0.20
        not_kept.candidate_score = None
        not_kept.score_delta = None

        summary = _build_score_summary(
            experiment_rows=[kept, not_kept],
            rescan_results=[],
            stability={"stable": [], "strengthening": [], "recent_only": [], "unstable": []},
        )

        scan = summary["interaction_scan"]
        # Baseline score = only kept experiment.
        assert scan["aggregate_baseline_score"] == 0.80
        # All score = both experiments.
        assert abs(scan["aggregate_all_score"] - 0.50) < 1e-6

    def test_loop_design_field_present_and_correct(self):
        """loop_design field must be 'single_arm_discovery'."""
        from services.auto_discovery.orchestrator import _build_score_summary

        exp = MagicMock()
        exp.loop_type = "interaction_scan"
        exp.kept = True
        exp.baseline_score = 0.55
        exp.candidate_score = None
        exp.score_delta = None

        summary = _build_score_summary(
            experiment_rows=[exp],
            rescan_results=[],
            stability={"stable": [], "strengthening": [], "recent_only": [], "unstable": []},
        )
        assert summary["interaction_scan"]["loop_design"] == "single_arm_discovery"

    # ── Fix 2: stage requires approved status ────────────────────────────────

    def _make_candidate(self, status: str):
        from models import AutoDiscoveryCandidate
        c = MagicMock(spec=AutoDiscoveryCandidate)
        c.id = uuid.uuid4()
        c.athlete_id = uuid.uuid4()
        c.current_status = status
        c.reviewed_at = None
        c.updated_at = None
        c.promotion_target = None
        c.promotion_note = None
        return c

    def test_stage_on_open_candidate_raises(self):
        """stage must be rejected when candidate status is 'open'."""
        from services.auto_discovery.orchestrator import review_candidate

        candidate = self._make_candidate("open")
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = candidate

        with pytest.raises(ValueError, match="must be approved first"):
            review_candidate(
                candidate_id=candidate.id,
                action="stage",
                db=db,
                promotion_target="surface_candidate",
            )

    def test_stage_on_rejected_candidate_raises(self):
        """stage must be rejected when candidate status is 'rejected'."""
        from services.auto_discovery.orchestrator import review_candidate

        candidate = self._make_candidate("rejected")
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = candidate

        with pytest.raises(ValueError, match="must be approved first"):
            review_candidate(
                candidate_id=candidate.id,
                action="stage",
                db=db,
                promotion_target="registry_change_candidate",
            )

    def test_stage_on_deferred_candidate_raises(self):
        """stage must be rejected when candidate status is 'deferred'."""
        from services.auto_discovery.orchestrator import review_candidate

        candidate = self._make_candidate("deferred")
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = candidate

        with pytest.raises(ValueError, match="must be approved first"):
            review_candidate(
                candidate_id=candidate.id,
                action="stage",
                db=db,
                promotion_target="manual_research_candidate",
            )

    def test_stage_on_approved_candidate_succeeds(self):
        """stage succeeds when candidate is already approved."""
        from services.auto_discovery.orchestrator import review_candidate

        candidate = self._make_candidate("approved")
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = candidate

        review_candidate(
            candidate_id=candidate.id,
            action="stage",
            db=db,
            promotion_target="investigation_upgrade_candidate",
        )
        assert candidate.promotion_target == "investigation_upgrade_candidate"
        assert candidate.current_status == "approved"  # unchanged

    # ── Fix 3: interaction/tuning candidates carry provenance ────────────────

    def test_interaction_candidate_upsert_carries_provenance(self):
        """Interaction candidates stored in durable memory must include provenance."""
        from services.auto_discovery.orchestrator import _upsert_candidates
        from models import AutoDiscoveryCandidate

        athlete_id = uuid.uuid4()
        run = MagicMock()
        run.id = uuid.uuid4()

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None

        report = {
            "stable_findings": [],
            "strengthened_findings": [],
            "candidate_interactions": {
                "cleared_threshold": True,
                "candidates": [
                    {
                        "factors": ["hrv_score", "weekly_volume"],
                        "output_metric": "efficiency",
                        "direction_label": "higher efficiency when both are high",
                        "interaction_score": 0.65,
                        "score_components": {
                            "effect_size_norm": 0.567,
                            "sample_support": 0.60,
                        },
                    }
                ],
            },
            "registry_tuning_candidates": {"cleared_threshold": False, "candidates": []},
        }

        _upsert_candidates(athlete_id=athlete_id, run=run, report=report, db=db)

        added = db.add.call_args[0][0]
        assert isinstance(added, AutoDiscoveryCandidate)
        provenance = added.provenance_snapshot
        assert provenance is not None
        assert "component_values" in provenance
        assert provenance["component_values"]["effect_size_norm"] == 0.567
        assert provenance["component_quality"]["effect_size_norm"] == "exact"
        assert provenance["has_inferred_components"] is False

    def test_tuning_candidate_summarize_includes_provenance(self):
        """summarize_tuning_results kept candidates must include score_provenance."""
        from services.auto_discovery.tuning_loop import summarize_tuning_results

        provenance = {
            "component_values": {},
            "component_quality": {"confidence": "inferred", "actionability": "registry_default"},
            "has_inferred_components": True,
        }

        exp = {
            "kept": True,
            "baseline_score": 0.40,
            "candidate_score": 0.46,
            "score_delta": 0.06,
            "baseline_config": {"investigation": "investigate_heat_tax", "params": {"min_activities": 20}},
            "candidate_config": {
                "investigation": "investigate_heat_tax",
                "changed_delta": {"min_activities": 16},
                "changed_param": "min_activities",
            },
            "result_summary": {
                "investigation": "investigate_heat_tax",
                "param_name": "min_activities",
                "kept": True,
                "rationale": "kept: score_delta 0.0600 > 0.03 and finding count stable",
                "baseline_error": None,
                "candidate_error": None,
                "score_provenance": provenance,
            },
        }

        result = summarize_tuning_results([exp])

        assert result["cleared_threshold"] is True
        cand = result["candidates"][0]
        assert "score_provenance" in cand
        assert cand["score_provenance"]["has_inferred_components"] is True

    def test_tuning_upsert_uses_score_provenance_from_candidate(self):
        """_upsert_candidates stores provenance from tuning candidate score_provenance."""
        from services.auto_discovery.orchestrator import _upsert_candidates
        from models import AutoDiscoveryCandidate

        athlete_id = uuid.uuid4()
        run = MagicMock()
        run.id = uuid.uuid4()

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None

        provenance = {
            "component_values": {},
            "component_quality": {"confidence": "inferred", "actionability": "registry_default"},
            "has_inferred_components": True,
        }

        report = {
            "stable_findings": [],
            "strengthened_findings": [],
            "candidate_interactions": {"cleared_threshold": False, "candidates": []},
            "registry_tuning_candidates": {
                "cleared_threshold": True,
                "candidates": [
                    {
                        "investigation": "investigate_heat_tax",
                        "parameter_change": {"min_activities": 16},
                        "baseline_score": 0.40,
                        "candidate_score": 0.46,
                        "score_delta": 0.06,
                        "kept": True,
                        "rationale": "kept",
                        "score_provenance": provenance,
                    }
                ],
            },
        }

        _upsert_candidates(athlete_id=athlete_id, run=run, report=report, db=db)

        added = db.add.call_args[0][0]
        assert isinstance(added, AutoDiscoveryCandidate)
        stored_provenance = added.provenance_snapshot
        assert stored_provenance is not None
        assert stored_provenance["has_inferred_components"] is True


# ─────────────────────────────────────────────────────────────────────────────
#  Migration integrity check
# ─────────────────────────────────────────────────────────────────────────────

class TestMigrationIntegrity:
    """Phase 0C: migration chain must be intact."""

    def test_migration_heads_check(self):
        """CI heads check script must pass with auto_discovery_002 as single head."""
        import subprocess, sys
        from pathlib import Path

        script = Path(__file__).resolve().parents[3] / ".github" / "scripts" / "ci_alembic_heads_check.py"
        result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        assert result.returncode == 0, (
            f"Heads check failed:\n{result.stdout}\n{result.stderr}"
        )

    def test_auto_discovery_002_revision_exists(self):
        """auto_discovery_002 migration file is present and well-formed."""
        from pathlib import Path
        import importlib.util

        versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        migration_file = versions_dir / "auto_discovery_002_add_candidate_table.py"
        assert migration_file.exists(), f"Migration file not found: {migration_file}"

        spec = importlib.util.spec_from_file_location("migration_002", migration_file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert mod.revision == "auto_discovery_002"
        assert mod.down_revision == "auto_discovery_001"
        assert hasattr(mod, "upgrade")
        assert hasattr(mod, "downgrade")

    def test_candidate_model_has_unique_constraint(self):
        """AutoDiscoveryCandidate has UniqueConstraint on (athlete_id, candidate_type, candidate_key)."""
        from models import AutoDiscoveryCandidate
        from sqlalchemy import UniqueConstraint

        constraints = AutoDiscoveryCandidate.__table_args__
        uc_names = [
            c.name for c in constraints
            if isinstance(c, UniqueConstraint)
        ]
        assert "uq_auto_disc_candidate_athlete_type_key" in uc_names
