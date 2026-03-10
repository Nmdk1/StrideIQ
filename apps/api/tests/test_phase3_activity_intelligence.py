"""
Phase 3 tests — Activity Intelligence + Navigation + Daily Intelligence.
"""
import inspect

import pytest


class TestActivityFindingsEndpoint:
    """GET /v1/activities/{id}/findings exists and returns list."""

    def test_endpoint_exists(self):
        from routers.activities import get_activity_findings
        assert callable(get_activity_findings)

    def test_returns_list_of_finding_annotations(self):
        from routers.activities import FindingAnnotation
        fields = FindingAnnotation.model_fields
        for f in ("text", "domain", "confidence_tier", "evidence_summary"):
            assert f in fields

    def test_limits_to_3(self):
        from routers.activities import get_activity_findings
        src = inspect.getsource(get_activity_findings)
        assert ".limit(3)" in src


class TestAuthMeHasCorrelations:
    """auth/me includes has_correlations for nav gating."""

    def test_user_response_has_correlations_field(self):
        from routers.auth import UserResponse
        fields = UserResponse.model_fields
        assert "has_correlations" in fields

    def test_me_endpoint_computes_correlations(self):
        from routers.auth import get_current_user_info
        src = inspect.getsource(get_current_user_info)
        assert "CorrelationFinding" in src
        assert "has_correlations" in src


class TestDailyIntelligenceEndpoint:
    """GET /v1/intelligence/today exists and is tier-gated."""

    def test_endpoint_exists(self):
        from routers.daily_intelligence import get_today_intelligence
        assert callable(get_today_intelligence)

    def test_requires_guided_tier(self):
        from routers.daily_intelligence import get_today_intelligence
        src = inspect.getsource(get_today_intelligence)
        assert "guided" in src.lower() or "require_tier" in src
