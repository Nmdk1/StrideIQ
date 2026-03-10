"""
Security Tests: Authentication Required on Previously Unauthenticated Endpoints

These tests verify that endpoints that previously had NO authentication
now properly require authentication and enforce ownership.

Run with: pytest tests/test_security_auth_required.py -v
"""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import date

# Import app after setting test environment
import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-at-least-32-chars")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "test-encryption-key-32-chars-ok")

from main import app


client = TestClient(app)


class TestBodyCompositionAuthRequired:
    """Test that body_composition endpoints require authentication."""
    
    def test_create_body_composition_requires_auth(self):
        """POST /v1/body-composition should return 401 without auth."""
        response = client.post("/v1/body-composition", json={
            "athlete_id": str(uuid4()),
            "date": str(date.today()),
            "weight_kg": 70.0
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_get_body_composition_requires_auth(self):
        """GET /v1/body-composition should return 401 without auth."""
        response = client.get(f"/v1/body-composition?athlete_id={uuid4()}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_get_body_composition_by_id_requires_auth(self):
        """GET /v1/body-composition/{id} should return 401 without auth."""
        response = client.get(f"/v1/body-composition/{uuid4()}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_update_body_composition_requires_auth(self):
        """PUT /v1/body-composition/{id} should return 401 without auth."""
        response = client.put(f"/v1/body-composition/{uuid4()}", json={
            "athlete_id": str(uuid4()),
            "date": str(date.today()),
            "weight_kg": 71.0
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_delete_body_composition_requires_auth(self):
        """DELETE /v1/body-composition/{id} should return 401 without auth."""
        response = client.delete(f"/v1/body-composition/{uuid4()}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestWorkPatternAuthRequired:
    """Test that work_pattern endpoints require authentication."""
    
    def test_create_work_pattern_requires_auth(self):
        """POST /v1/work-patterns should return 401 without auth."""
        response = client.post("/v1/work-patterns", json={
            "athlete_id": str(uuid4()),
            "date": str(date.today()),
            "work_hours": 8.0
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_get_work_patterns_requires_auth(self):
        """GET /v1/work-patterns should return 401 without auth."""
        response = client.get(f"/v1/work-patterns?athlete_id={uuid4()}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_get_work_pattern_by_id_requires_auth(self):
        """GET /v1/work-patterns/{id} should return 401 without auth."""
        response = client.get(f"/v1/work-patterns/{uuid4()}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_update_work_pattern_requires_auth(self):
        """PUT /v1/work-patterns/{id} should return 401 without auth."""
        response = client.put(f"/v1/work-patterns/{uuid4()}", json={
            "athlete_id": str(uuid4()),
            "date": str(date.today()),
            "work_hours": 9.0
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_delete_work_pattern_requires_auth(self):
        """DELETE /v1/work-patterns/{id} should return 401 without auth."""
        response = client.delete(f"/v1/work-patterns/{uuid4()}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestNutritionAuthRequired:
    """Test that nutrition endpoints require authentication."""
    
    def test_nutrition_parse_available_no_auth_required(self):
        """GET /v1/nutrition/parse/available is a capability check - no auth needed."""
        response = client.get("/v1/nutrition/parse/available")
        # This should work without auth (capability check)
        assert response.status_code == 200, f"Capability check should not require auth"
    
    def test_create_nutrition_requires_auth(self):
        """POST /v1/nutrition should return 401 without auth."""
        response = client.post("/v1/nutrition", json={
            "athlete_id": str(uuid4()),
            "date": str(date.today()),
            "entry_type": "daily"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_get_nutrition_entries_requires_auth(self):
        """GET /v1/nutrition should return 401 without auth."""
        response = client.get(f"/v1/nutrition?athlete_id={uuid4()}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_get_nutrition_by_id_requires_auth(self):
        """GET /v1/nutrition/{id} should return 401 without auth."""
        response = client.get(f"/v1/nutrition/{uuid4()}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_update_nutrition_requires_auth(self):
        """PUT /v1/nutrition/{id} should return 401 without auth."""
        response = client.put(f"/v1/nutrition/{uuid4()}", json={
            "athlete_id": str(uuid4()),
            "date": str(date.today()),
            "entry_type": "daily"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_delete_nutrition_requires_auth(self):
        """DELETE /v1/nutrition/{id} should return 401 without auth."""
        response = client.delete(f"/v1/nutrition/{uuid4()}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestFeedbackAuthRequired:
    """Test that feedback endpoints require authentication."""
    
    def test_observe_requires_auth(self):
        """GET /v1/feedback/athletes/{id}/observe should return 401 without auth."""
        response = client.get(f"/v1/feedback/athletes/{uuid4()}/observe")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_hypothesize_requires_auth(self):
        """GET /v1/feedback/athletes/{id}/hypothesize should return 401 without auth."""
        response = client.get(f"/v1/feedback/athletes/{uuid4()}/hypothesize")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_intervene_requires_auth(self):
        """GET /v1/feedback/athletes/{id}/intervene should return 401 without auth."""
        response = client.get(f"/v1/feedback/athletes/{uuid4()}/intervene")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_loop_requires_auth(self):
        """GET /v1/feedback/athletes/{id}/loop should return 401 without auth."""
        response = client.get(f"/v1/feedback/athletes/{uuid4()}/loop")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_validate_requires_auth(self):
        """POST /v1/feedback/athletes/{id}/validate should return 401 without auth."""
        response = client.post(
            f"/v1/feedback/athletes/{uuid4()}/validate",
            params={
                "intervention_date": "2026-01-01T00:00:00",
                "metric_to_track": "pace",
                "expected_improvement": "5%"
            }
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestV1ActivityModificationAuthRequired:
    """Test that activity modification endpoints require authentication."""
    
    def test_mark_race_requires_auth(self):
        """POST /v1/activities/{id}/mark-race should return 401 without auth."""
        response = client.post(f"/v1/activities/{uuid4()}/mark-race")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_backfill_splits_requires_auth(self):
        """POST /v1/activities/{id}/backfill-splits should return 401 without auth."""
        response = client.post(f"/v1/activities/{uuid4()}/backfill-splits")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestKnowledgeRpiAuthRequired:
    """Test that RPI endpoints with athlete_id require authentication."""
    
    def test_rpi_formula_with_athlete_id_requires_auth(self):
        """GET /v1/knowledge/rpi/formula?athlete_id=X should return 401 without auth."""
        response = client.get(f"/v1/knowledge/rpi/formula?athlete_id={uuid4()}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_rpi_pace_tables_with_athlete_id_requires_auth(self):
        """GET /v1/knowledge/rpi/pace-tables?athlete_id=X should return 401 without auth."""
        response = client.get(f"/v1/knowledge/rpi/pace-tables?athlete_id={uuid4()}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_rpi_formula_requires_auth(self):
        """GET /v1/knowledge/rpi/formula requires auth - knowledge base is protected."""
        response = client.get("/v1/knowledge/rpi/formula")
        # SECURITY FIX: Knowledge base now requires authentication
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


# ============================================================================
# Ownership Tests (require authenticated user fixtures)
# These test that even authenticated users can only access their OWN data
# ============================================================================

# Note: These tests require setting up authenticated users and will be
# implemented in a follow-up after the auth fixtures are in place.

class TestOwnershipEnforcement:
    """
    Test that authenticated users can only access their own data.
    
    TODO: Implement after auth fixtures are set up.
    These tests will:
    1. Create user A and user B
    2. Create data for user A
    3. Verify user B cannot access user A's data (403)
    4. Verify user A can access their own data (200)
    """
    
    @pytest.mark.skip(reason="Requires auth fixtures - implement in Phase 2")
    def test_user_cannot_access_other_users_body_composition(self):
        pass
    
    @pytest.mark.skip(reason="Requires auth fixtures - implement in Phase 2")
    def test_user_cannot_access_other_users_nutrition(self):
        pass
    
    @pytest.mark.skip(reason="Requires auth fixtures - implement in Phase 2")
    def test_user_cannot_access_other_users_work_patterns(self):
        pass
    
    @pytest.mark.skip(reason="Requires auth fixtures - implement in Phase 2")
    def test_user_cannot_access_other_users_feedback(self):
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
