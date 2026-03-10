"""
Narration Accuracy Scorer Tests (Phase 3A-PRE)

These tests define the contract for the narration scoring function
BEFORE any LLM narration code exists. The scoring function must be
proven correct before it can be used to gate Phase 3B.

Three criteria, each binary:
    1. Factually correct vs intelligence engine data
    2. No raw metrics leaked (TSB, CTL, ATL, etc.)
    3. Actionable language (forward-looking guidance)

Window score = % of criteria passed across all narrations.
Gate for 3B: window score >= 90% sustained for 4 weeks.

Sources:
    docs/TRAINING_PLAN_REBUILD_PLAN.md (Parallel Track: Coach Trust)
"""

import pytest
import sys
import os
from datetime import date
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.narration_scorer import (
    NarrationScorer,
    NarrationScoreResult,
    WindowScoreResult,
    BANNED_ACRONYMS,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def scorer():
    return NarrationScorer()


def _ground_truth_load_spike(pct=25.0, current_km=60.5, prev_km=48.4):
    """Ground truth dict mimicking a LOAD_SPIKE insight."""
    return {
        "highest_mode": "inform",
        "insights": [
            {
                "rule_id": "LOAD_SPIKE",
                "mode": "inform",
                "data_cited": {
                    "current_km": current_km,
                    "previous_km": prev_km,
                    "pct_increase": pct,
                },
            }
        ],
    }


def _ground_truth_sustained_decline():
    """Ground truth dict for SUSTAINED_DECLINE (FLAG mode)."""
    return {
        "highest_mode": "flag",
        "insights": [
            {
                "rule_id": "SUSTAINED_DECLINE",
                "mode": "flag",
                "data_cited": {
                    "total_decline_pct": 8.5,
                    "weeks": 3,
                },
            }
        ],
    }


def _ground_truth_no_insights():
    """Ground truth with no fired rules (quiet day)."""
    return {
        "highest_mode": None,
        "insights": [],
    }


# ===========================================================================
# Criterion 1: Factual Accuracy
# ===========================================================================

class TestFactualAccuracy:
    """Narration must match the engine's data within ±2%."""

    def test_accurate_percentage_passes(self, scorer):
        """Narration citing 25% when engine says 25% → pass."""
        narration = (
            "Your training volume increased 25% this week compared to last. "
            "Consider monitoring how your body responds over the next few days."
        )
        gt = _ground_truth_load_spike(pct=25.0)
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.factually_correct is True
        assert len(result.factual_errors) == 0

    def test_percentage_within_tolerance_passes(self, scorer):
        """Narration citing 27% when engine says 25% → pass (within ±2%)."""
        narration = (
            "You ran about 27% more this week. "
            "Continue listening to your body as the load adapts."
        )
        gt = _ground_truth_load_spike(pct=25.0)
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.factually_correct is True

    def test_percentage_outside_tolerance_fails(self, scorer):
        """Narration citing 35% when engine says 25% → fail."""
        narration = (
            "Your training load spiked 35% this week. "
            "Be mindful of recovery in the next few days."
        )
        gt = _ground_truth_load_spike(pct=25.0)
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.factually_correct is False
        assert any("35" in e for e in result.factual_errors)

    def test_claiming_unfired_rule_fails(self, scorer):
        """Narration claims efficiency breakthrough when only LOAD_SPIKE fired."""
        narration = (
            "Your efficiency improved significantly this week! "
            "Consider building on this momentum."
        )
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.factually_correct is False
        assert result.contradicts_engine is True
        assert any("EFFICIENCY_BREAK" in e for e in result.factual_errors)

    def test_claiming_swap_in_inform_mode_fails(self, scorer):
        """Narration says it swapped the workout when mode is INFORM."""
        narration = (
            "Given the load increase, I've swapped your workout "
            "to an easy recovery run. Focus on staying relaxed."
        )
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.factually_correct is False
        assert result.contradicts_engine is True
        assert "INFORM" in (result.contradiction_detail or "")

    def test_no_percentages_with_no_ground_truth_pcts_passes(self, scorer):
        """Narration without percentages when no % data exists → pass."""
        narration = (
            "Solid consistency this week. Your body is responding well. "
            "Keep this rhythm going forward."
        )
        gt = _ground_truth_no_insights()
        result = scorer.score(narration, gt, insight_rule_ids=[])

        assert result.factually_correct is True

    def test_inventing_decline_when_none_detected_fails(self, scorer):
        """Narration claims decline but engine saw only a load spike."""
        narration = (
            "Your efficiency has been declining for the past few weeks. "
            "Consider taking a recovery day this week."
        )
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.factually_correct is False
        assert result.contradicts_engine is True

    def test_empty_narration_fails_all(self, scorer):
        """Empty string fails all criteria."""
        result = scorer.score("", _ground_truth_load_spike())

        assert result.factually_correct is False
        assert result.no_raw_metrics is False
        assert result.actionable_language is False
        assert result.score == 0.0

    def test_whitespace_only_narration_fails_all(self, scorer):
        """Whitespace-only string fails all criteria."""
        result = scorer.score("   \n\t  ", _ground_truth_load_spike())

        assert result.factually_correct is False
        assert result.score == 0.0


# ===========================================================================
# Criterion 2: No Raw Metrics Leaked
# ===========================================================================

class TestNoRawMetrics:
    """Coach must NEVER expose internal metric acronyms or raw values."""

    def test_clean_narration_passes(self, scorer):
        """No banned terms → pass."""
        narration = (
            "Your volume jumped this week. "
            "Listen to your body and consider how the extra load feels."
        )
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.no_raw_metrics is True
        assert len(result.banned_terms_found) == 0

    @pytest.mark.parametrize("acronym", list(BANNED_ACRONYMS))
    def test_each_banned_acronym_fails(self, scorer, acronym):
        """Every banned acronym must be caught."""
        narration = f"Your {acronym} is looking good this week. Keep it going forward."
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.no_raw_metrics is False
        assert any(acronym in t for t in result.banned_terms_found)

    def test_tsb_with_value_fails(self, scorer):
        """'TSB: -15' is a raw metric dump."""
        narration = (
            "Your TSB: -15 indicates you're still absorbing the load. "
            "Consider a lighter day tomorrow."
        )
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.no_raw_metrics is False

    def test_ctl_in_sentence_fails(self, scorer):
        """Even casual reference to CTL fails."""
        narration = (
            "Your CTL has been building steadily. "
            "This is a good sign going forward."
        )
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.no_raw_metrics is False

    def test_ef_with_value_fails(self, scorer):
        """'EF: 0.020' is an internal metric dump."""
        narration = (
            "Your EF: 0.020 is improving. "
            "Keep up the consistent effort this week."
        )
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.no_raw_metrics is False

    def test_human_friendly_efficiency_passes(self, scorer):
        """'Running efficiency' as a concept (not raw EF value) is fine."""
        narration = (
            "Your running efficiency has improved noticeably. "
            "This suggests the training is working well. Keep building on it."
        )
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.no_raw_metrics is True

    def test_vdot_anywhere_fails(self, scorer):
        """VDOT is a trademark and must never appear."""
        narration = (
            "Based on your VDOT estimate, you're in great shape. "
            "Focus on maintaining this level."
        )
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.no_raw_metrics is False


# ===========================================================================
# Criterion 3: Actionable Language
# ===========================================================================

class TestActionableLanguage:
    """Narration must contain forward-looking guidance, not just describe data."""

    def test_actionable_narration_passes(self, scorer):
        """Narration with forward-looking advice → pass."""
        narration = (
            "Your volume increased this week. "
            "Consider monitoring how your legs feel over the next few days."
        )
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.actionable_language is True
        assert len(result.actionable_phrases_found) > 0

    def test_purely_backward_looking_fails(self, scorer):
        """Only describing what happened, no guidance → fail."""
        narration = (
            "Your training volume increased 25% compared to last period. "
            "The largest single session was a long run on Saturday."
        )
        gt = _ground_truth_load_spike(pct=25.0)
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.actionable_language is False

    def test_consider_is_actionable(self, scorer):
        """'Consider' counts as actionable."""
        narration = "Volume is up. Consider how your body responds."
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.actionable_language is True
        assert "consider" in result.actionable_phrases_found

    def test_next_session_is_actionable(self, scorer):
        """Forward-looking time reference counts."""
        narration = "Great work. Your next session should feel strong."
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.actionable_language is True

    def test_listen_to_body_is_actionable(self, scorer):
        """Classic coaching advice is actionable."""
        narration = "Big week. Listen to your body and stay flexible."
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.actionable_language is True

    def test_multiple_actionable_phrases_all_captured(self, scorer):
        """Multiple action indicators are all found."""
        narration = (
            "Consider taking it easy tomorrow. "
            "Going forward, prioritize sleep and focus on recovery."
        )
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.actionable_language is True
        assert len(result.actionable_phrases_found) >= 2


# ===========================================================================
# Overall Score Computation
# ===========================================================================

class TestScoreComputation:
    """Score computation across criteria and windows."""

    def test_perfect_narration_scores_1_0(self, scorer):
        """All 3 criteria pass → score = 1.0."""
        narration = (
            "Your training volume increased about 25% this week. "
            "Consider monitoring how your body responds in the coming days."
        )
        gt = _ground_truth_load_spike(pct=25.0)
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.factually_correct is True
        assert result.no_raw_metrics is True
        assert result.actionable_language is True
        assert result.criteria_passed == 3
        assert result.score == pytest.approx(1.0)

    def test_one_criterion_fails_scores_0_67(self, scorer):
        """2 of 3 criteria pass → score ≈ 0.667."""
        narration = (
            "Your training volume increased about 50% this week. "  # Wrong %
            "Consider monitoring how your body responds in the coming days."
        )
        gt = _ground_truth_load_spike(pct=25.0)
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        # Factual: fail (50 vs 25), no metrics: pass, actionable: pass
        assert result.factually_correct is False
        assert result.no_raw_metrics is True
        assert result.actionable_language is True
        assert result.criteria_passed == 2
        assert result.score == pytest.approx(2.0 / 3.0)

    def test_two_criteria_fail_scores_0_33(self, scorer):
        """1 of 3 criteria pass → score ≈ 0.333."""
        narration = (
            "Your TSB is -15 and volume spiked 50% this week."
            # No actionable language either
        )
        gt = _ground_truth_load_spike(pct=25.0)
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        # Factual: fail (50 vs 25), metrics: fail (TSB), actionable: fail
        assert result.criteria_passed <= 1
        assert result.score <= (1.0 / 3.0) + 1e-9


# ===========================================================================
# Window Scoring (Aggregate for Phase 3B Gate)
# ===========================================================================

class TestWindowScoring:
    """Window-level aggregate scoring gates Phase 3B at 90%."""

    def test_all_perfect_window_passes_gate(self, scorer):
        """10 perfect narrations → 100% → passes 90% gate."""
        scores = []
        for _ in range(10):
            narration = (
                "Your training volume increased about 25% this week. "
                "Consider monitoring how your body responds going forward."
            )
            gt = _ground_truth_load_spike(pct=25.0)
            result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])
            scores.append(result)

        window = scorer.score_window(
            scores,
            window_start=date(2026, 2, 1),
            window_end=date(2026, 2, 7),
        )

        assert window.total_narrations == 10
        assert window.score == pytest.approx(1.0)
        assert window.passes_90_threshold is True
        assert window.factual_pass_rate == pytest.approx(1.0)
        assert window.no_metrics_pass_rate == pytest.approx(1.0)
        assert window.actionable_pass_rate == pytest.approx(1.0)

    def test_90_percent_exactly_passes_gate(self, scorer):
        """Window at exactly 90% → passes gate."""
        scores = []
        # 9 perfect narrations (27 criteria pass)
        for _ in range(9):
            s = NarrationScoreResult()
            s.factually_correct = True
            s.no_raw_metrics = True
            s.actionable_language = True
            s.compute()
            scores.append(s)

        # 1 narration with all 3 failing (0 criteria pass)
        s = NarrationScoreResult()
        s.factually_correct = False
        s.no_raw_metrics = False
        s.actionable_language = False
        s.compute()
        scores.append(s)

        window = scorer.score_window(
            scores,
            window_start=date(2026, 2, 1),
            window_end=date(2026, 2, 7),
        )

        # 27 / 30 = 0.90
        assert window.total_criteria_checks == 30
        assert window.total_criteria_passed == 27
        assert window.score == pytest.approx(0.90)
        assert window.passes_90_threshold is True

    def test_below_90_percent_fails_gate(self, scorer):
        """Window at 89% → does NOT pass gate."""
        scores = []
        # 8 perfect (24 pass) + 2 all-fail (0 pass) = 24/30 = 80%
        for _ in range(8):
            s = NarrationScoreResult()
            s.factually_correct = True
            s.no_raw_metrics = True
            s.actionable_language = True
            s.compute()
            scores.append(s)

        for _ in range(2):
            s = NarrationScoreResult()
            s.factually_correct = False
            s.no_raw_metrics = False
            s.actionable_language = False
            s.compute()
            scores.append(s)

        window = scorer.score_window(
            scores,
            window_start=date(2026, 2, 1),
            window_end=date(2026, 2, 7),
        )

        assert window.score == pytest.approx(0.80)
        assert window.passes_90_threshold is False

    def test_empty_window(self, scorer):
        """No narrations → score stays 0, doesn't crash."""
        window = scorer.score_window(
            [],
            window_start=date(2026, 2, 1),
            window_end=date(2026, 2, 7),
        )

        assert window.total_narrations == 0
        assert window.score == 0.0
        assert window.passes_90_threshold is False

    def test_per_criterion_pass_rates(self, scorer):
        """Individual criterion pass rates are tracked separately."""
        scores = []

        # Narration 1: all pass
        s1 = NarrationScoreResult()
        s1.factually_correct = True
        s1.no_raw_metrics = True
        s1.actionable_language = True
        s1.compute()
        scores.append(s1)

        # Narration 2: factual fails, others pass
        s2 = NarrationScoreResult()
        s2.factually_correct = False
        s2.no_raw_metrics = True
        s2.actionable_language = True
        s2.compute()
        scores.append(s2)

        window = scorer.score_window(
            scores,
            window_start=date(2026, 2, 1),
            window_end=date(2026, 2, 7),
        )

        assert window.factual_pass_rate == pytest.approx(0.5)
        assert window.no_metrics_pass_rate == pytest.approx(1.0)
        assert window.actionable_pass_rate == pytest.approx(1.0)
        # Overall: 5/6 ≈ 0.833
        assert window.score == pytest.approx(5.0 / 6.0)


# ===========================================================================
# Contradiction Detection
# ===========================================================================

class TestContradictionDetection:
    """Contradictions must be caught and logged for review."""

    def test_no_contradiction_when_matching(self, scorer):
        """Narration matches engine → no contradiction."""
        narration = (
            "Your training volume increased 25% this week. "
            "Continue listening to your body."
        )
        gt = _ground_truth_load_spike(pct=25.0)
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.contradicts_engine is False
        assert result.contradiction_detail is None

    def test_swap_claim_in_inform_mode_is_contradiction(self, scorer):
        """Claiming swap in INFORM mode is a direct contradiction."""
        narration = (
            "I've changed your plan to a recovery run today. "
            "Focus on easy effort."
        )
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.contradicts_engine is True
        assert "INFORM" in result.contradiction_detail

    def test_fabricating_rule_is_contradiction(self, scorer):
        """Claiming a rule that didn't fire is a contradiction."""
        narration = (
            "You've been missing sessions consistently. "
            "Consider what might be getting in the way."
        )
        # Engine only detected load spike, not missed sessions
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.contradicts_engine is True

    def test_flag_mode_narration_can_reference_severity(self, scorer):
        """In FLAG mode, stronger language is OK."""
        narration = (
            "Your efficiency has been declining for three weeks. "
            "This is unusual and worth paying attention to going forward."
        )
        gt = _ground_truth_sustained_decline()
        result = scorer.score(narration, gt, insight_rule_ids=["SUSTAINED_DECLINE"])

        assert result.contradicts_engine is False
        assert result.factually_correct is True


# ===========================================================================
# Edge Cases
# ===========================================================================

class TestEdgeCases:
    """Boundary conditions and edge cases."""

    def test_percentage_as_word_detected(self, scorer):
        """'25 percent' is caught same as '25%'."""
        narration = (
            "Your volume is up about 50 percent from last week. "
            "Consider monitoring recovery this week."
        )
        gt = _ground_truth_load_spike(pct=25.0)
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.factually_correct is False

    def test_multiple_percentages_all_checked(self, scorer):
        """Multiple percentages are all validated against ground truth."""
        narration = (
            "Your volume is up 25% and your completion rate is 90%. "
            "Consider maintaining this consistency going forward."
        )
        gt = {
            "highest_mode": "inform",
            "insights": [
                {
                    "rule_id": "LOAD_SPIKE",
                    "data_cited": {"pct_increase": 25.0},
                },
            ],
        }
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        # 25% matches, but 90% has no ground truth match — both need to
        # be within ±2% of something in ground truth.
        # 90 vs closest (25) = 65 difference → fail
        assert result.factually_correct is False

    def test_narration_with_no_numbers_is_safe(self, scorer):
        """Narration avoiding specific numbers entirely is fine."""
        narration = (
            "You had a bigger week than usual. "
            "Be mindful of how your body absorbs the extra work over the next few days."
        )
        gt = _ground_truth_load_spike()
        result = scorer.score(narration, gt, insight_rule_ids=["LOAD_SPIKE"])

        assert result.factually_correct is True
        assert result.no_raw_metrics is True
        assert result.actionable_language is True
        assert result.score == pytest.approx(1.0)

    def test_narration_none_fails_gracefully(self, scorer):
        """None narration → fails gracefully."""
        result = scorer.score(None, _ground_truth_load_spike())
        assert result.score == 0.0

    def test_narration_only_spaces_fails_gracefully(self, scorer):
        """Only whitespace → fails gracefully."""
        result = scorer.score("     ", _ground_truth_load_spike())
        assert result.score == 0.0
