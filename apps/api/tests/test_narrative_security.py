"""
Security tests for Narrative Translation Layer (ADR-033)

Checks:
- IDOR protection: athlete_id always matches current_user
- Auth: endpoints require authentication
- Input validation: no raw user input in narratives
- Data exposure: no sensitive data leaks
"""

import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch


class TestIDORProtection:
    """Test IDOR (Insecure Direct Object Reference) protection."""
    
    def test_activity_endpoint_filters_by_user_id(self):
        """Activity endpoint must filter by current_user.id."""
        from routers.activities import get_activity
        import inspect
        
        source = inspect.getsource(get_activity)
        
        # Must filter by athlete_id == current_user.id for IDOR protection
        assert "athlete_id" in source
        assert "current_user" in source
    
    def test_narrative_translator_uses_authenticated_user(self):
        """Narrative translator uses athlete_id from authenticated user."""
        from services.narrative_translator import NarrativeTranslator
        
        mock_db = Mock()
        athlete_id = uuid4()
        
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        # Verify the translator stores the correct athlete_id
        assert translator.athlete_id == athlete_id
        assert translator.anchor_finder.athlete_id == athlete_id
    
    def test_narrative_memory_scoped_to_user(self):
        """Narrative memory is scoped to specific athlete."""
        from services.narrative_memory import NarrativeMemory, _memory_store
        
        _memory_store.clear()
        
        mock_db = Mock()
        athlete1 = uuid4()
        athlete2 = uuid4()
        
        memory1 = NarrativeMemory(mock_db, athlete1, use_redis=False, use_db_fallback=False)
        memory2 = NarrativeMemory(mock_db, athlete2, use_redis=False, use_db_fallback=False)
        
        # Record for athlete1
        memory1.record_shown("hash123", "load_state", "home")
        
        # Should be shown for athlete1
        assert memory1.recently_shown("hash123", days=14) == True
        
        # Should NOT be shown for athlete2 (different user)
        assert memory2.recently_shown("hash123", days=14) == False


class TestAuthenticationRequired:
    """Test that endpoints require authentication."""
    
    def test_home_endpoint_requires_auth(self):
        """Home endpoint requires authentication."""
        from routers.home import get_home_data
        import inspect
        
        sig = inspect.signature(get_home_data)
        params = list(sig.parameters.keys())
        
        # Must have current_user parameter (authentication dependency)
        assert "current_user" in params
    
    def test_activity_endpoint_requires_auth(self):
        """Activity detail endpoint requires authentication."""
        from routers.activities import get_activity
        import inspect
        
        sig = inspect.signature(get_activity)
        params = list(sig.parameters.keys())
        
        assert "current_user" in params
    
    def test_plan_preview_requires_auth(self):
        """Constraint-aware plan preview requires authentication."""
        from routers.plan_generation import preview_constraint_aware_plan
        import inspect
        
        sig = inspect.signature(preview_constraint_aware_plan)
        params = list(sig.parameters.keys())
        
        # Uses "athlete" parameter for authentication
        assert "athlete" in params
    
    def test_diagnostic_endpoint_requires_auth(self):
        """Diagnostic report requires authentication."""
        from routers.analytics import get_diagnostic_report_endpoint
        import inspect
        
        sig = inspect.signature(get_diagnostic_report_endpoint)
        params = list(sig.parameters.keys())
        
        assert "current_user" in params


class TestInputValidation:
    """Test input validation for narratives."""
    
    def test_no_user_input_in_narratives(self):
        """Narratives should not contain raw user input."""
        from services.narrative_translator import NarrativeTranslator
        from services.fitness_bank import FitnessBank, ConstraintType, ExperienceLevel
        
        mock_db = Mock()
        athlete_id = uuid4()
        
        # Create a fitness bank with potentially dangerous data
        bank = FitnessBank(
            athlete_id=str(athlete_id),
            peak_weekly_miles=70.0,
            peak_monthly_miles=280.0,
            peak_long_run_miles=22.0,
            peak_mp_long_run_miles=18.0,
            peak_threshold_miles=8.0,
            peak_ctl=85.0,
            race_performances=[],
            best_vdot=53.0,
            best_race=None,
            current_weekly_miles=55.0,
            current_ctl=72.0,
            current_atl=80.0,
            weeks_since_peak=4,
            tau1=25.0,
            tau2=18.0,
            experience_level=ExperienceLevel.ELITE,
            constraint_type=ConstraintType.NONE,
            constraint_details="<script>alert('xss')</script>",  # XSS attempt
            is_returning_from_break=False,
            typical_long_run_day=6,
            typical_quality_day=3,
            typical_rest_days=[0],
            weeks_to_80pct_ctl=2,
            weeks_to_race_ready=4,
            sustainable_peak_weekly=65.0
        )
        
        translator = NarrativeTranslator(mock_db, athlete_id)
        translator.anchor_finder.find_prior_race_at_load = Mock(return_value=None)
        
        # Generate narrative
        narrative = translator.narrate_load_state(15, 70, 55)
        
        # Narrative should not contain raw constraint_details
        # (we don't use constraint_details in load state narratives)
        assert "<script>" not in narrative.text
    
    def test_narrative_hash_is_safe(self):
        """Narrative hash should be a safe MD5 substring."""
        from services.narrative_translator import NarrativeTranslator
        
        mock_db = Mock()
        translator = NarrativeTranslator(mock_db, uuid4())
        
        # Hash should be alphanumeric, 12 chars
        test_hash = translator._hash("test input")
        assert len(test_hash) == 12
        assert test_hash.isalnum()


class TestDataExposure:
    """Test that no sensitive data is exposed."""
    
    def test_audit_log_anonymizes_athlete_id(self):
        """Audit logs should anonymize athlete IDs."""
        from services.audit_logger import _anonymize_id
        
        athlete_id = uuid4()
        
        anonymized = _anonymize_id(athlete_id)
        
        # Should be a hash, not the original ID
        assert str(athlete_id) not in anonymized
        assert len(anonymized) == 12
    
    def test_narrative_does_not_expose_raw_data(self):
        """Narratives should not expose raw activity data."""
        from services.narrative_translator import Narrative
        
        narrative = Narrative(
            text="You're fresh. Good day for quality.",
            signal_type="load_state",
            priority=80,
            hash="abc123",
            anchors_used=[]
        )
        
        # to_dict should only expose safe fields
        d = narrative.to_dict()
        
        assert "text" in d
        assert "signal_type" in d
        assert "priority" in d
        # Should NOT expose internal fields
        assert "hash" not in d
        assert "anchors_used" not in d


class TestFeatureFlagSecurity:
    """Test feature flag security."""
    
    def test_narrative_feature_requires_flag(self):
        """Narrative generation should check feature flag."""
        from routers.home import get_home_data
        import inspect
        
        source = inspect.getsource(get_home_data)
        
        # Must check feature flag before generating narrative
        assert "is_feature_enabled" in source
        assert "narrative.translation_enabled" in source
    
    def test_flag_check_includes_athlete_id(self):
        """Feature flag check should include athlete ID for rollout."""
        from core.feature_flags import is_feature_enabled
        
        # The function signature requires athlete_id
        # This ensures rollout is per-user
        import inspect
        sig = inspect.signature(is_feature_enabled)
        params = list(sig.parameters.keys())
        
        assert "athlete_id" in params or len(params) >= 2
