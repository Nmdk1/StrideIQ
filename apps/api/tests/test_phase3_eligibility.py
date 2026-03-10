"""Tests for Phase 3B/3C eligibility service.

Covers:
- 3C unlocks immediately for athlete with 2y synced history, day-1 production.
- 3C blocked for <90d history even if production age low.
- 3C blocked when stats fail any gate (p, r, n).
- 3C applies multiple-testing correction (Bonferroni).
- 3B unlocks for premium athlete with rich history and valid context.
- 3B returns ineligible for sparse context.
- 3B respects kill switch.
- Tier gating: guided gets 3C but not 3B workout narratives.
"""
import os
import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from uuid import uuid4

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.phase3_eligibility import (
    get_3b_eligibility,
    get_3c_eligibility,
    EligibilityResult,
    MIN_HISTORY_SPAN_DAYS,
    MIN_TOTAL_RUNS,
    TIERS_3B,
    TIERS_3C,
    KILL_SWITCH_3B_ENV,
    KILL_SWITCH_3C_ENV,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_athlete(tier="premium"):
    a = MagicMock()
    a.id = uuid4()
    a.subscription_tier = tier
    a.has_active_subscription = tier in {"premium", "guided", "elite", "pro"}
    return a


def _make_activity(athlete_id, days_ago=0, sport="run"):
    a = MagicMock()
    a.athlete_id = athlete_id
    a.sport = sport
    a.start_time = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return a


class FakeQuery:
    """Chainable mock for SQLAlchemy queries."""

    def __init__(self, rows=None, count_val=0, one_val=None):
        self._rows = rows or []
        self._count_val = count_val
        self._one_val = one_val

    def filter(self, *a, **kw):
        return self

    def count(self):
        return self._count_val

    def one(self):
        return self._one_val

    def first(self):
        return self._rows[0] if self._rows else None

    def order_by(self, *a):
        return self

    def limit(self, *a):
        return self

    def all(self):
        return self._rows


def _mock_db_for_athlete(athlete, total_runs=100, span_days=200,
                         has_workout=True, narration_score=0.95,
                         narration_rows=10):
    """Build a mock db session for eligibility tests."""
    from models import Athlete, Activity, PlannedWorkout, NarrationLog

    earliest = datetime.now(timezone.utc) - timedelta(days=span_days)
    latest = datetime.now(timezone.utc)

    athlete_query = FakeQuery(rows=[athlete])
    activity_count_query = FakeQuery(count_val=total_runs, one_val=(earliest, latest))

    workout_row = MagicMock() if has_workout else None
    workout_query = FakeQuery(rows=[workout_row] if has_workout else [])

    narr_rows = [MagicMock(score=narration_score) for _ in range(narration_rows)]
    narr_query = FakeQuery(rows=narr_rows)

    def side_effect(*args, **kwargs):
        # db.query() may receive one model or multiple columns (e.g. func.min, func.max)
        model = args[0] if args else None
        if model is Athlete or (hasattr(model, '__tablename__') and getattr(model, '__tablename__', None) == 'athlete'):
            return athlete_query
        if model is Activity or (hasattr(model, '__tablename__') and getattr(model, '__tablename__', None) == 'activity'):
            return activity_count_query
        if model is PlannedWorkout or (hasattr(model, '__tablename__') and getattr(model, '__tablename__', None) == 'planned_workout'):
            return workout_query
        if model is NarrationLog or (hasattr(model, '__tablename__') and getattr(model, '__tablename__', None) == 'narration_log'):
            return narr_query
        # For func.min / func.max aggregate queries, return activity stats
        return activity_count_query

    db = MagicMock()
    db.query.side_effect = side_effect
    return db


# ---------------------------------------------------------------------------
# 3C: Immediate unlock with synced history
# ---------------------------------------------------------------------------

class TestPhase3CEligibility:

    def test_3c_unlocks_with_2y_synced_history_day1_production(self):
        """Athlete with 2 years of synced Strava history qualifies on day 1."""
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=400, span_days=730)

        # Mock correlation engine to return significant results
        mock_corr = {
            "correlations": [
                {
                    "input_name": "weekly_volume_km",
                    "correlation_coefficient": 0.55,
                    "p_value": 0.001,
                    "sample_size": 50,
                    "is_significant": True,
                    "direction": "positive",
                    "strength": "moderate",
                    "time_lag_days": 2,
                },
            ],
            "total_correlations_found": 1,
        }

        with patch("services.correlation_engine.analyze_correlations", return_value=mock_corr):
            result = get_3c_eligibility(athlete.id, db)

        assert result.eligible is True
        assert "significant" in result.reason.lower()
        assert result.evidence["history_span_days"] >= 90

    def test_3c_blocked_under_90d_history(self):
        """Athlete with only 60 days of history is blocked."""
        athlete = _make_athlete(tier="guided")
        db = _mock_db_for_athlete(athlete, total_runs=30, span_days=60)

        result = get_3c_eligibility(athlete.id, db)

        assert result.eligible is False
        assert "insufficient" in result.reason.lower() or "90" in result.reason

    def test_3c_blocked_when_p_value_fails(self):
        """Correlations with p > 0.05 after Bonferroni are rejected."""
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=100, span_days=200)

        # p=0.03 with 2 tests → Bonferroni p_adj = 0.06 > 0.05
        mock_corr = {
            "correlations": [
                {
                    "input_name": "sleep_hours",
                    "correlation_coefficient": 0.4,
                    "p_value": 0.03,
                    "sample_size": 20,
                    "is_significant": True,
                    "direction": "positive",
                    "strength": "moderate",
                    "time_lag_days": 0,
                },
                {
                    "input_name": "weekly_volume_km",
                    "correlation_coefficient": 0.35,
                    "p_value": 0.04,
                    "sample_size": 20,
                    "is_significant": True,
                    "direction": "positive",
                    "strength": "moderate",
                    "time_lag_days": 0,
                },
            ],
        }

        with patch("services.correlation_engine.analyze_correlations", return_value=mock_corr):
            result = get_3c_eligibility(athlete.id, db)

        assert result.eligible is False
        assert "correction" in result.reason.lower() or "bonferroni" in result.reason.lower()

    def test_3c_blocked_when_r_too_low(self):
        """Correlation with |r| < 0.3 is rejected even if p is tiny."""
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=100, span_days=200)

        mock_corr = {
            "correlations": [
                {
                    "input_name": "sleep_hours",
                    "correlation_coefficient": 0.15,
                    "p_value": 0.001,
                    "sample_size": 100,
                    "is_significant": True,
                    "direction": "positive",
                    "strength": "weak",
                    "time_lag_days": 0,
                },
            ],
        }

        with patch("services.correlation_engine.analyze_correlations", return_value=mock_corr):
            result = get_3c_eligibility(athlete.id, db)

        assert result.eligible is False

    def test_3c_blocked_when_n_too_low(self):
        """Correlation with n < 10 is rejected."""
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=100, span_days=200)

        mock_corr = {
            "correlations": [
                {
                    "input_name": "sleep_hours",
                    "correlation_coefficient": 0.6,
                    "p_value": 0.01,
                    "sample_size": 8,
                    "is_significant": True,
                    "direction": "positive",
                    "strength": "moderate",
                    "time_lag_days": 0,
                },
            ],
        }

        with patch("services.correlation_engine.analyze_correlations", return_value=mock_corr):
            result = get_3c_eligibility(athlete.id, db)

        assert result.eligible is False

    def test_3c_bonferroni_applied(self):
        """With 20 tests, a p=0.01 becomes p_adj=0.20 and is rejected."""
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=200, span_days=300)

        # 20 correlations, all with p=0.01 → Bonferroni p_adj = 0.20 > 0.05
        mock_corr = {
            "correlations": [
                {
                    "input_name": f"input_{i}",
                    "correlation_coefficient": 0.35,
                    "p_value": 0.01,
                    "sample_size": 15,
                    "is_significant": True,
                    "direction": "positive",
                    "strength": "moderate",
                    "time_lag_days": 0,
                }
                for i in range(20)
            ],
        }

        with patch("services.correlation_engine.analyze_correlations", return_value=mock_corr):
            result = get_3c_eligibility(athlete.id, db)

        assert result.eligible is False
        assert result.evidence["correlations_tested"] == 20

    def test_3c_bonferroni_allows_strong_signal(self):
        """With 20 tests, p=0.001 → p_adj=0.02 still passes."""
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=200, span_days=300)

        mock_corr = {
            "correlations": [
                {
                    "input_name": "weekly_volume_km",
                    "correlation_coefficient": 0.6,
                    "p_value": 0.001,
                    "sample_size": 50,
                    "is_significant": True,
                    "direction": "positive",
                    "strength": "strong",
                    "time_lag_days": 0,
                },
            ] + [
                {
                    "input_name": f"noise_{i}",
                    "correlation_coefficient": 0.1,
                    "p_value": 0.5,
                    "sample_size": 15,
                    "is_significant": False,
                    "direction": "positive",
                    "strength": "weak",
                    "time_lag_days": 0,
                }
                for i in range(19)
            ],
        }

        with patch("services.correlation_engine.analyze_correlations", return_value=mock_corr):
            result = get_3c_eligibility(athlete.id, db)

        assert result.eligible is True


# ---------------------------------------------------------------------------
# 3C: Tier gating
# ---------------------------------------------------------------------------

class TestPhase3CTierGating:

    def test_3c_free_tier_blocked(self):
        athlete = _make_athlete(tier="free")
        db = _mock_db_for_athlete(athlete, total_runs=200, span_days=300)
        result = get_3c_eligibility(athlete.id, db)
        assert result.eligible is False
        assert "tier" in result.reason.lower()

    def test_3c_guided_tier_allowed(self):
        """Guided tier gets 3C access."""
        athlete = _make_athlete(tier="guided")
        db = _mock_db_for_athlete(athlete, total_runs=200, span_days=300)

        mock_corr = {
            "correlations": [
                {
                    "input_name": "weekly_volume_km",
                    "correlation_coefficient": 0.55,
                    "p_value": 0.001,
                    "sample_size": 50,
                    "is_significant": True,
                    "direction": "positive",
                    "strength": "moderate",
                    "time_lag_days": 0,
                },
            ],
        }
        with patch("services.correlation_engine.analyze_correlations", return_value=mock_corr):
            result = get_3c_eligibility(athlete.id, db)

        assert result.eligible is True

    def test_3c_kill_switch(self):
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=200, span_days=300)
        with patch.dict(os.environ, {KILL_SWITCH_3C_ENV: "1"}):
            result = get_3c_eligibility(athlete.id, db)
        assert result.eligible is False
        assert "kill switch" in result.reason.lower()


# ---------------------------------------------------------------------------
# 3B: Eligibility
# ---------------------------------------------------------------------------

class TestPhase3BEligibility:

    def test_3b_unlocks_premium_with_rich_history(self):
        """Premium athlete with 200 days history and a planned workout qualifies."""
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=150, span_days=200,
                                  has_workout=True, narration_score=0.95)
        result = get_3b_eligibility(athlete.id, db)
        assert result.eligible is True

    def test_3b_blocked_for_free_tier(self):
        athlete = _make_athlete(tier="free")
        db = _mock_db_for_athlete(athlete, total_runs=200, span_days=300)
        result = get_3b_eligibility(athlete.id, db)
        assert result.eligible is False
        assert "premium" in result.reason.lower()

    def test_3b_guided_tier_blocked(self):
        """Guided tier gets 3C but NOT 3B."""
        athlete = _make_athlete(tier="guided")
        db = _mock_db_for_athlete(athlete, total_runs=200, span_days=300)
        result = get_3b_eligibility(athlete.id, db)
        assert result.eligible is False
        assert "premium" in result.reason.lower()

    def test_3b_no_planned_workout(self):
        """No planned workout for target date → ineligible."""
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=200, span_days=300,
                                  has_workout=False)
        result = get_3b_eligibility(athlete.id, db)
        assert result.eligible is False
        assert "planned workout" in result.reason.lower()

    def test_3b_sparse_history(self):
        """Too little history → ineligible."""
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=10, span_days=30)
        result = get_3b_eligibility(athlete.id, db)
        assert result.eligible is False
        assert "insufficient" in result.reason.lower()

    def test_3b_unlocks_by_run_count_even_with_short_span(self):
        """60+ runs in <90 days still qualifies (run count OR span)."""
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=65, span_days=60,
                                  has_workout=True)
        result = get_3b_eligibility(athlete.id, db)
        assert result.eligible is True

    def test_3b_kill_switch(self):
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=200, span_days=300,
                                  has_workout=True)
        with patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "1"}):
            result = get_3b_eligibility(athlete.id, db)
        assert result.eligible is False
        assert "kill switch" in result.reason.lower()

    def test_3b_provisional_when_narration_quality_unknown(self):
        """If no narration quality data yet, eligible but provisional."""
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=200, span_days=300,
                                  has_workout=True, narration_rows=0)
        result = get_3b_eligibility(athlete.id, db)
        assert result.eligible is True
        assert result.provisional is True


# ---------------------------------------------------------------------------
# Cross-tier: guided gets 3C but not 3B
# ---------------------------------------------------------------------------

class TestSyncedHistorySufficiency:
    """Verify that only synced (provider-backed) activities count."""

    def test_manual_only_history_does_not_unlock_3c(self):
        """All manual entries, no provider → should not unlock."""
        athlete = _make_athlete(tier="premium")
        # Build a mock where activity count query returns 0 synced runs
        # (the filter now excludes manual-only)
        db = _mock_db_for_athlete(athlete, total_runs=0, span_days=0)

        result = get_3c_eligibility(athlete.id, db)
        assert result.eligible is False
        assert "insufficient" in result.reason.lower() or "data" in result.reason.lower()

    def test_synced_history_unlocks_day1(self):
        """Synced 2y of Strava history → unlocks immediately."""
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=400, span_days=730)

        mock_corr = {
            "correlations": [
                {
                    "input_name": "weekly_volume_km",
                    "correlation_coefficient": 0.55,
                    "p_value": 0.001,
                    "sample_size": 50,
                    "is_significant": True,
                    "direction": "positive",
                    "strength": "moderate",
                    "time_lag_days": 2,
                },
            ],
        }
        with patch("services.correlation_engine.analyze_correlations", return_value=mock_corr):
            result = get_3c_eligibility(athlete.id, db)

        assert result.eligible is True

    def test_manual_only_does_not_unlock_3b(self):
        athlete = _make_athlete(tier="premium")
        db = _mock_db_for_athlete(athlete, total_runs=0, span_days=0, has_workout=True)
        result = get_3b_eligibility(athlete.id, db)
        assert result.eligible is False


class TestCrossTierGating:

    def test_guided_gets_3c_not_3b(self):
        athlete = _make_athlete(tier="guided")

        db_3b = _mock_db_for_athlete(athlete, total_runs=200, span_days=300,
                                     has_workout=True)
        result_3b = get_3b_eligibility(athlete.id, db_3b)
        assert result_3b.eligible is False

        db_3c = _mock_db_for_athlete(athlete, total_runs=200, span_days=300)
        mock_corr = {
            "correlations": [
                {
                    "input_name": "weekly_volume_km",
                    "correlation_coefficient": 0.55,
                    "p_value": 0.001,
                    "sample_size": 50,
                    "is_significant": True,
                    "direction": "positive",
                    "strength": "moderate",
                    "time_lag_days": 0,
                },
            ],
        }
        with patch("services.correlation_engine.analyze_correlations", return_value=mock_corr):
            result_3c = get_3c_eligibility(athlete.id, db_3c)
        assert result_3c.eligible is True

    def test_elite_gets_3c(self):
        """Elite tier qualifies for 3C (backward compat with router)."""
        athlete = _make_athlete(tier="elite")
        db = _mock_db_for_athlete(athlete, total_runs=200, span_days=300)
        mock_corr = {
            "correlations": [
                {
                    "input_name": "weekly_volume_km",
                    "correlation_coefficient": 0.55,
                    "p_value": 0.001,
                    "sample_size": 50,
                    "is_significant": True,
                    "direction": "positive",
                    "strength": "moderate",
                    "time_lag_days": 0,
                },
            ],
        }
        with patch("services.correlation_engine.analyze_correlations", return_value=mock_corr):
            result = get_3c_eligibility(athlete.id, db)
        assert result.eligible is True

    def test_pro_gets_3c(self):
        """Pro tier qualifies for 3C (aligned with router)."""
        athlete = _make_athlete(tier="pro")
        db = _mock_db_for_athlete(athlete, total_runs=200, span_days=300)
        mock_corr = {
            "correlations": [
                {
                    "input_name": "weekly_volume_km",
                    "correlation_coefficient": 0.55,
                    "p_value": 0.001,
                    "sample_size": 50,
                    "is_significant": True,
                    "direction": "positive",
                    "strength": "moderate",
                    "time_lag_days": 0,
                },
            ],
        }
        with patch("services.correlation_engine.analyze_correlations", return_value=mock_corr):
            result = get_3c_eligibility(athlete.id, db)
        assert result.eligible is True

    def test_free_gets_neither(self):
        athlete = _make_athlete(tier="free")
        db = _mock_db_for_athlete(athlete, total_runs=200, span_days=300, has_workout=True)
        assert get_3b_eligibility(athlete.id, db).eligible is False
        assert get_3c_eligibility(athlete.id, db).eligible is False
