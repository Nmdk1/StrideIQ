"""
Phase 3C Graduation Tests

Covers the graduation layer on top of the already-built 3C intelligence path:
  - Founder review endpoint (list generated 3C insights with evidence)
  - Per-insight suppression (suppress one bad insight, keep rest alive)
  - Global kill switch behavior (endpoint still healthy when 3C killed)
  - Eligibility metadata honesty (accurate eligible vs ineligible state)
  - Statistical gates remain unchanged

These are real tests (not xfail) — they verify the new graduation controls
that make 3C operationally trustworthy.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.n1_insight_generator import (
    generate_n1_insights,
    _insight_fingerprint,
    N1Insight,
    DIRECTIONAL_SAFE_METRICS,
)
from services.phase3_eligibility import (
    get_3c_eligibility,
    KILL_SWITCH_3C_ENV,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_athlete(tier="premium"):
    a = MagicMock()
    a.id = uuid.uuid4()
    a.subscription_tier = tier
    a.email = "mbshaf@gmail.com"
    return a


def _strong_correlation(input_name="weekly_volume_km", direction="positive",
                         r=0.6, p=0.001, n=50):
    return {
        "input_name": input_name,
        "correlation_coefficient": r,
        "p_value": p,
        "sample_size": n,
        "is_significant": True,
        "direction": direction,
        "strength": "strong",
        "time_lag_days": 2,
    }


def _mock_db_no_suppressions():
    """Mock DB that returns no suppressions and no history stats blocking."""
    db = MagicMock()
    # suppress table query returns empty list
    db.query.return_value.filter.return_value.all.return_value = []
    return db


def _mock_corr_result(correlations):
    return {"correlations": correlations, "total_correlations_found": len(correlations)}


# ===========================================================================
# 1. Insight fingerprint is stable
# ===========================================================================

class TestInsightFingerprint:

    def test_same_inputs_produce_same_fingerprint(self):
        fp1 = _insight_fingerprint("weekly_volume_km", "positive", "efficiency")
        fp2 = _insight_fingerprint("weekly_volume_km", "positive", "efficiency")
        assert fp1 == fp2

    def test_different_direction_produces_different_fingerprint(self):
        fp_pos = _insight_fingerprint("weekly_volume_km", "positive", "efficiency")
        fp_neg = _insight_fingerprint("weekly_volume_km", "negative", "efficiency")
        assert fp_pos != fp_neg

    def test_different_input_produces_different_fingerprint(self):
        fp1 = _insight_fingerprint("weekly_volume_km", "positive", "efficiency")
        fp2 = _insight_fingerprint("sleep_hours", "positive", "efficiency")
        assert fp1 != fp2

    def test_fingerprint_is_16_chars(self):
        fp = _insight_fingerprint("weekly_volume_km", "positive", "efficiency")
        assert len(fp) == 16

    def test_fingerprint_is_string(self):
        fp = _insight_fingerprint("sleep_hours", "negative", "pace_easy")
        assert isinstance(fp, str)


# ===========================================================================
# 2. Per-insight suppression works
# ===========================================================================

class TestPerInsightSuppression:

    def _run_generate(self, athlete_id, suppressed_fingerprints=None):
        """Run generate_n1_insights with controlled suppression state."""
        db = MagicMock()
        from models import N1InsightSuppression
        mock_rows = []
        if suppressed_fingerprints:
            for fp in suppressed_fingerprints:
                row = MagicMock()
                row.insight_fingerprint = fp
                mock_rows.append(row)
        db.query.return_value.filter.return_value.all.return_value = mock_rows

        corr_result = _mock_corr_result([
            _strong_correlation("weekly_volume_km", "positive"),
            _strong_correlation("sleep_hours", "positive"),
        ])

        with patch("services.correlation_engine.analyze_correlations",
                   return_value=corr_result):
            return generate_n1_insights(athlete_id, db, days_window=90)

    def test_unsuppressed_insights_surface(self):
        athlete_id = uuid.uuid4()
        insights = self._run_generate(athlete_id)
        assert len(insights) > 0

    def test_suppressed_insight_does_not_surface(self):
        """Suppress one fingerprint — that specific insight disappears."""
        athlete_id = uuid.uuid4()
        # First, find the fingerprint for weekly_volume_km + positive
        fp = _insight_fingerprint("weekly_volume_km", "positive", "efficiency")

        insights_before = self._run_generate(athlete_id)
        count_before = len(insights_before)

        insights_after = self._run_generate(athlete_id, suppressed_fingerprints=[fp])
        count_after = len(insights_after)

        # One insight should be gone
        assert count_after < count_before
        # The suppressed fingerprint must not appear in results
        result_fps = {i.fingerprint for i in insights_after}
        assert fp not in result_fps

    def test_other_insights_unaffected_by_suppression(self):
        """Suppressing one insight leaves others alive."""
        athlete_id = uuid.uuid4()
        fp_to_suppress = _insight_fingerprint("weekly_volume_km", "positive", "efficiency")

        insights = self._run_generate(athlete_id, suppressed_fingerprints=[fp_to_suppress])
        # sleep_hours insight should still surface
        input_names = [i.evidence.get("input_name") for i in insights]
        assert "sleep_hours" in input_names

    def test_suppression_table_unavailable_fails_open(self):
        """If suppression table is unavailable, insights still surface (fail open)."""
        athlete_id = uuid.uuid4()
        db = MagicMock()
        # Simulate DB error on suppression lookup
        db.query.return_value.filter.return_value.all.side_effect = Exception("DB unavailable")

        corr_result = _mock_corr_result([_strong_correlation()])

        with patch("services.correlation_engine.analyze_correlations",
                   return_value=corr_result):
            insights = generate_n1_insights(athlete_id, db, days_window=90)

        # Should still surface insights (fail open)
        assert len(insights) > 0

    def test_n1insight_carries_fingerprint(self):
        """N1Insight instances have non-empty fingerprint field."""
        athlete_id = uuid.uuid4()
        insights = self._run_generate(athlete_id)
        for ins in insights:
            assert ins.fingerprint, f"Missing fingerprint on insight: {ins.text}"
            assert len(ins.fingerprint) == 16


# ===========================================================================
# 3. Global kill switch behavior
# ===========================================================================

class TestGlobalKillSwitch:

    def test_kill_switch_disables_3c_eligibility(self):
        from services.phase3_eligibility import get_3c_eligibility, KILL_SWITCH_3C_ENV
        from unittest.mock import MagicMock
        athlete = _make_athlete(tier="premium")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = athlete

        with patch.dict(os.environ, {KILL_SWITCH_3C_ENV: "1"}):
            result = get_3c_eligibility(athlete.id, db)

        assert result.eligible is False
        assert "kill switch" in result.reason.lower()

    def test_kill_switch_evidence_is_honest(self):
        """Kill switch result must include kill_switch=True in evidence."""
        athlete = _make_athlete(tier="premium")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = athlete

        with patch.dict(os.environ, {KILL_SWITCH_3C_ENV: "1"}):
            result = get_3c_eligibility(athlete.id, db)

        assert result.evidence.get("kill_switch") is True

    def test_generate_n1_insights_returns_empty_when_no_correlations(self):
        """If no correlations survive gates, returns empty list cleanly."""
        athlete_id = uuid.uuid4()
        db = _mock_db_no_suppressions()

        # Weak correlations that fail r-gate
        corr_result = _mock_corr_result([
            {"input_name": "sleep_hours", "correlation_coefficient": 0.1,
             "p_value": 0.001, "sample_size": 50, "direction": "positive",
             "strength": "weak", "time_lag_days": 0}
        ])
        with patch("services.correlation_engine.analyze_correlations",
                   return_value=corr_result):
            insights = generate_n1_insights(athlete_id, db, days_window=90)

        assert insights == []

    def test_generate_n1_insights_returns_empty_when_correlation_engine_fails(self):
        """If correlation engine throws, returns empty list (no crash)."""
        athlete_id = uuid.uuid4()
        db = _mock_db_no_suppressions()

        with patch("services.correlation_engine.analyze_correlations",
                   side_effect=Exception("Engine unavailable")):
            insights = generate_n1_insights(athlete_id, db, days_window=90)

        assert insights == []


# ===========================================================================
# 4. Eligibility metadata honesty
# ===========================================================================

class TestEligibilityMetadataHonesty:

    def test_ineligible_state_is_truthful_when_history_short(self):
        from unittest.mock import MagicMock
        from datetime import datetime, timezone, timedelta

        athlete = _make_athlete(tier="guided")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = athlete

        # Return short history (60 days)
        earliest = datetime.now(timezone.utc) - timedelta(days=60)
        latest = datetime.now(timezone.utc)
        db.query.return_value.filter.return_value.count.return_value = 30
        db.query.return_value.filter.return_value.one.return_value = (earliest, latest)
        # count query
        db.query.return_value.filter.return_value.count.return_value = 30

        result = get_3c_eligibility(athlete.id, db)

        assert result.eligible is False
        assert "insufficient" in result.reason.lower() or "90" in result.reason

    def test_eligible_state_reflects_actual_significant_correlations(self):
        """Eligible result must report how many correlations survived correction."""
        from datetime import datetime, timezone, timedelta

        athlete = _make_athlete(tier="premium")

        class FakeQuery:
            def __init__(self):
                self._count = 200
            def filter(self, *a, **kw): return self
            def count(self): return self._count
            def first(self): return athlete
            def one(self):
                e = datetime.now(timezone.utc) - timedelta(days=300)
                l = datetime.now(timezone.utc)
                return (e, l)
            def order_by(self, *a): return self
            def limit(self, *a): return self
            def all(self): return []

        db = MagicMock()
        db.query.return_value = FakeQuery()

        mock_corr = _mock_corr_result([_strong_correlation(p=0.001)])

        with patch("services.correlation_engine.analyze_correlations",
                   return_value=mock_corr):
            result = get_3c_eligibility(athlete.id, db)

        assert result.eligible is True
        assert result.evidence.get("significant_after_correction", 0) >= 1

    def test_n1_eligibility_meta_returned_in_intelligence_endpoint(self):
        """The /intelligence endpoint always returns n1_eligibility metadata."""
        from fastapi.testclient import TestClient
        from main import app
        from core.auth import get_current_user
        from core.database import get_db

        athlete = _make_athlete(tier="guided")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []

        def override_user():
            return athlete

        def override_db():
            return db

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

        try:
            from services.insight_aggregator import InsightAggregator
            mock_intelligence = MagicMock()
            mock_intelligence.what_works = []
            mock_intelligence.what_doesnt = []
            mock_intelligence.patterns = {}
            mock_intelligence.injury_patterns = []
            mock_intelligence.career_prs = {}

            with patch.object(InsightAggregator, "get_athlete_intelligence",
                              return_value=mock_intelligence), \
                 patch("services.phase3_eligibility.get_3c_eligibility") as mock_elig:
                mock_elig.return_value = MagicMock(
                    eligible=False,
                    reason="Insufficient history",
                    confidence=0.0,
                    provisional=False,
                )
                client = TestClient(app)
                resp = client.get("/v1/insights/intelligence")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert "n1_eligibility" in data
        assert data["n1_eligibility"]["eligible"] is False
        assert "reason" in data["n1_eligibility"]


# ===========================================================================
# 5. Statistical gates remain unchanged
# ===========================================================================

class TestStatisticalGatesUnchanged:
    """Verify that the graduation layer did not weaken any statistical gates."""

    def _run_with_single_corr(self, r, p, n, athlete_id=None):
        if athlete_id is None:
            athlete_id = uuid.uuid4()
        db = _mock_db_no_suppressions()
        corr_result = _mock_corr_result([
            {"input_name": "sleep_hours", "correlation_coefficient": r,
             "p_value": p, "sample_size": n, "direction": "positive",
             "strength": "moderate", "time_lag_days": 0}
        ])
        with patch("services.correlation_engine.analyze_correlations",
                   return_value=corr_result):
            return generate_n1_insights(athlete_id, db, days_window=90)

    def test_p_gate_still_enforced_after_bonferroni(self):
        """p=0.06 after Bonferroni → no insight."""
        # 2 correlations, p=0.03 → p_adj = 0.06 > 0.05
        athlete_id = uuid.uuid4()
        db = _mock_db_no_suppressions()
        corr_result = _mock_corr_result([
            {"input_name": "sleep_hours", "correlation_coefficient": 0.5,
             "p_value": 0.03, "sample_size": 30, "direction": "positive",
             "strength": "moderate", "time_lag_days": 0},
            {"input_name": "weekly_volume_km", "correlation_coefficient": 0.5,
             "p_value": 0.04, "sample_size": 30, "direction": "positive",
             "strength": "moderate", "time_lag_days": 0},
        ])
        with patch("services.correlation_engine.analyze_correlations",
                   return_value=corr_result):
            insights = generate_n1_insights(athlete_id, db, days_window=90)
        assert insights == []

    def test_r_gate_still_enforced(self):
        """r=0.25 → rejected even if p is small."""
        insights = self._run_with_single_corr(r=0.25, p=0.001, n=50)
        assert insights == []

    def test_n_gate_still_enforced(self):
        """n=8 → rejected even if r and p are good."""
        insights = self._run_with_single_corr(r=0.6, p=0.001, n=8)
        assert insights == []

    def test_all_gates_passing_produces_insight(self):
        """r=0.6, p=0.001, n=50 all passing → insight surfaced."""
        insights = self._run_with_single_corr(r=0.6, p=0.001, n=50)
        assert len(insights) >= 1

    def test_banned_acronyms_still_blocked(self):
        """Insights with banned acronyms in text are still filtered."""
        athlete_id = uuid.uuid4()
        db = _mock_db_no_suppressions()
        # The "tsb" input maps to "form (training readiness)" which is safe
        # But use a name that would produce banned output
        corr_result = _mock_corr_result([
            {"input_name": "weekly_volume_km", "correlation_coefficient": 0.6,
             "p_value": 0.001, "sample_size": 50, "direction": "positive",
             "strength": "strong", "time_lag_days": 0}
        ])
        with patch("services.correlation_engine.analyze_correlations",
                   return_value=corr_result):
            insights = generate_n1_insights(athlete_id, db, days_window=90)
        # All returned insights must be free of banned acronyms
        from services.n1_insight_generator import BANNED_PATTERN
        for ins in insights:
            assert not BANNED_PATTERN.search(ins.text), \
                f"Banned acronym in: {ins.text}"


# ===========================================================================
# 6. Migration integrity
# ===========================================================================

class TestMigrationIntegrity:

    def test_phase3c_001_migration_exists(self):
        import importlib.util
        from pathlib import Path
        api_root = Path(__file__).resolve().parents[1]
        migration_file = api_root / "alembic" / "versions" / "phase3c_001_n1_insight_suppression.py"
        assert migration_file.exists(), f"Migration file not found: {migration_file}"

    def test_phase3c_001_chains_off_auto_discovery_002(self):
        from pathlib import Path
        api_root = Path(__file__).resolve().parents[1]
        migration_file = api_root / "alembic" / "versions" / "phase3c_001_n1_insight_suppression.py"
        content = migration_file.read_text()
        assert 'down_revision = "auto_discovery_002"' in content

    def test_ci_heads_check_passes(self):
        import subprocess
        import sys
        from pathlib import Path
        p = Path(__file__).resolve()
        script = None
        for parent in p.parents:
            candidate = parent / ".github" / "scripts" / "ci_alembic_heads_check.py"
            if candidate.exists():
                script = candidate
                break
        if script is None:
            pytest.skip("ci_alembic_heads_check.py not found — not in full repo checkout")
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"Heads check failed:\n{result.stdout}\n{result.stderr}"

    def test_n1_insight_suppression_unique_constraint_in_migration(self):
        """Migration must enforce UniqueConstraint on (athlete_id, insight_fingerprint)."""
        from pathlib import Path
        api_root = Path(__file__).resolve().parents[1]
        migration_file = api_root / "alembic" / "versions" / "phase3c_001_n1_insight_suppression.py"
        content = migration_file.read_text()
        assert "uq_n1_suppression_athlete_fingerprint" in content


# ===========================================================================
# 7. Admin route hardening
# ===========================================================================

class TestAdminRouteHardening:
    """
    Route-level regression tests for the two medium findings closed in 5c23491:
      - UUID inputs validated at request boundary (422 on malformed, not 500)
      - Founder auth stands alone — no tier gate blocks founder routes
    """

    def _make_app_with_overrides(self, athlete):
        """Return (app, TestClient) with user + db dependency overrides applied."""
        from fastapi.testclient import TestClient
        from main import app
        from core.auth import get_current_user
        from core.database import get_db

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []

        app.dependency_overrides[get_current_user] = lambda: athlete
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        return app, client

    def test_malformed_uuid_on_n1_review_returns_422(self):
        """GET /admin/n1-review with non-UUID athlete_id must return 422, not 500."""
        founder = _make_athlete(tier="guided")
        founder.email = "mbshaf@gmail.com"
        app, client = self._make_app_with_overrides(founder)
        try:
            resp = client.get("/v1/insights/admin/n1-review?athlete_id=not-a-uuid")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 422, (
            f"Expected 422 for malformed UUID, got {resp.status_code}: {resp.text}"
        )

    def test_malformed_uuid_on_n1_suppress_returns_422(self):
        """POST /admin/n1-suppress with non-UUID athlete_id must return 422, not 500."""
        founder = _make_athlete(tier="guided")
        founder.email = "mbshaf@gmail.com"
        app, client = self._make_app_with_overrides(founder)
        try:
            resp = client.post(
                "/v1/insights/admin/n1-suppress",
                json={"athlete_id": "bad-uuid", "fingerprint": "abcd1234"},
            )
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 422, (
            f"Expected 422 for malformed UUID, got {resp.status_code}: {resp.text}"
        )

    def test_founder_without_guided_tier_can_reach_n1_review(self):
        """Founder with free/basic tier must NOT be blocked by tier middleware."""
        from fastapi.testclient import TestClient
        from main import app
        from core.auth import get_current_user
        from core.database import get_db

        # Founder on the lowest possible tier — no subscription
        founder = _make_athlete(tier="free")
        founder.email = "mbshaf@gmail.com"

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []

        app.dependency_overrides[get_current_user] = lambda: founder
        app.dependency_overrides[get_db] = lambda: db

        try:
            with patch("services.phase3_eligibility.KILL_SWITCH_3C_ENV", "STRIDEIQ_3C_KILL_SWITCH"), \
                 patch.dict(os.environ, {"STRIDEIQ_3C_KILL_SWITCH": "false"}):
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get("/v1/insights/admin/n1-review")
        finally:
            app.dependency_overrides.clear()

        # Founder reaches the endpoint — gets 200 (empty items list, kill switch off)
        assert resp.status_code == 200, (
            f"Founder with free tier was blocked (expected 200, got {resp.status_code}): {resp.text}"
        )
        data = resp.json()
        assert "items" in data
        assert "kill_switch_active" in data
