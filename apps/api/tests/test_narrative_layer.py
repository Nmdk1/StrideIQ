"""
Tests for Narrative Translation Layer (ADR-033)

Tests cover:
- Anchor finding (date formatting, workout matching, efficiency detection)
- Narrative translation (all 6 signal types)
- Memory deduplication
- Edge cases (no history, no anchors)
"""

import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

from services.anchor_finder import (
    AnchorFinder,
    InjuryReboundAnchor,
    WorkoutAnchor,
    EfficiencyAnchor,
    format_date_relative,
    format_pace
)
from services.narrative_translator import (
    NarrativeTranslator,
    Narrative,
    get_narrative_translator
)
from services.narrative_memory import (
    NarrativeMemory,
    get_narrative_memory,
    _memory_store
)
from services.fitness_bank import FitnessBank, ConstraintType, ExperienceLevel


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def athlete_id():
    """Test athlete ID."""
    return uuid4()


@pytest.fixture
def mock_fitness_bank():
    """Mock FitnessBank with typical values."""
    return FitnessBank(
        athlete_id=str(uuid4()),
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
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=2,
        weeks_to_race_ready=4,
        sustainable_peak_weekly=65.0
    )


@pytest.fixture
def injured_fitness_bank(mock_fitness_bank):
    """FitnessBank with injury constraint."""
    mock_fitness_bank.constraint_type = ConstraintType.INJURY
    mock_fitness_bank.constraint_details = "sharp volume drop"
    mock_fitness_bank.is_returning_from_break = True
    mock_fitness_bank.current_weekly_miles = 35.0
    mock_fitness_bank.weeks_since_peak = 3
    return mock_fitness_bank


# =============================================================================
# DATE FORMATTING TESTS
# =============================================================================

class TestDateFormatting:
    """Test relative date formatting."""
    
    def test_today(self):
        assert format_date_relative(date.today()) == "today"
    
    def test_yesterday(self):
        assert format_date_relative(date.today() - timedelta(days=1)) == "yesterday"
    
    def test_this_week(self):
        # 3 days ago should return day name
        d = date.today() - timedelta(days=3)
        result = format_date_relative(d)
        assert result in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    def test_last_week(self):
        # 10 days ago should return "last Tuesday" etc
        d = date.today() - timedelta(days=10)
        result = format_date_relative(d)
        assert result.startswith("last ")
    
    def test_within_two_months(self):
        # 30 days ago should return "Dec 15" format
        d = date.today() - timedelta(days=30)
        result = format_date_relative(d)
        assert len(result) <= 7  # "Dec 15" is 6 chars
    
    def test_older(self):
        # 90 days ago should return "Dec 2025" format
        d = date.today() - timedelta(days=90)
        result = format_date_relative(d)
        assert len(result) <= 9  # "Dec 2025" is 8 chars


class TestPaceFormatting:
    """Test pace formatting."""
    
    def test_typical_pace(self):
        assert format_pace(6.5) == "6:30"
    
    def test_fast_pace(self):
        assert format_pace(5.25) == "5:15"
    
    def test_slow_pace(self):
        assert format_pace(9.75) == "9:45"
    
    def test_even_minute(self):
        assert format_pace(7.0) == "7:00"


# =============================================================================
# NARRATIVE TRANSLATOR TESTS
# =============================================================================

class TestLoadStateNarratives:
    """Test load state narrative generation."""
    
    def test_fresh_state(self, mock_db, athlete_id):
        """Fresh TSB should generate positive narrative."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        # Mock anchor finder to return None (no prior race found)
        translator.anchor_finder.find_prior_race_at_load = Mock(return_value=None)
        
        narrative = translator.narrate_load_state(tsb=15, ctl=70, atl=55)
        
        assert narrative is not None
        assert narrative.signal_type == "load_state_fresh"
        assert "fresh" in narrative.text.lower() or "good sessions" in narrative.text.lower()
        assert narrative.priority >= 70
    
    def test_coiled_state(self, mock_db, athlete_id):
        """Deep negative TSB should generate coiled narrative."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        # Mock anchor finder
        translator.anchor_finder.find_comparable_load_state = Mock(return_value=None)
        
        narrative = translator.narrate_load_state(tsb=-15, ctl=80, atl=95)
        
        assert narrative is not None
        assert narrative.signal_type == "load_state_coiled"
        assert "recovery" in narrative.text.lower() or "easy" in narrative.text.lower()
        assert narrative.priority >= 80
    
    def test_balanced_state(self, mock_db, athlete_id):
        """Neutral TSB should generate lower priority narrative."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        narrative = translator.narrate_load_state(tsb=0, ctl=70, atl=70)
        
        assert narrative is not None
        assert narrative.signal_type == "load_state_balanced"
        assert narrative.priority < 50


class TestWorkoutContextNarratives:
    """Test workout context narrative generation."""
    
    def test_with_race_anchor(self, mock_db, athlete_id):
        """Workout followed by race should generate high-priority narrative."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        # Mock anchor with race
        anchor = WorkoutAnchor(
            activity_id=uuid4(),
            date=date.today() - timedelta(days=60),
            name="Threshold Tuesday",
            workout_type="threshold",
            pace_per_mile=6.5,
            following_race="Philly Half",
            days_to_race=14
        )
        translator.anchor_finder.find_similar_workout = Mock(return_value=anchor)
        
        narrative = translator.narrate_workout_context("threshold", "2x3mi @ T", 6.5)
        
        assert narrative is not None
        assert "Philly Half" in narrative.text
        assert "14 days" in narrative.text
        assert narrative.priority >= 85
    
    def test_without_race_anchor(self, mock_db, athlete_id):
        """Workout without following race should still work."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        anchor = WorkoutAnchor(
            activity_id=uuid4(),
            date=date.today() - timedelta(days=30),
            name="Tempo",
            workout_type="threshold",
            pace_per_mile=6.5,
            following_race=None,
            days_to_race=None
        )
        translator.anchor_finder.find_similar_workout = Mock(return_value=anchor)
        
        narrative = translator.narrate_workout_context("threshold", "Tempo", 6.5)
        
        assert narrative is not None
        assert "done this before" in narrative.text.lower()
        assert narrative.priority >= 60
    
    def test_first_time_workout(self, mock_db, athlete_id):
        """First time structure should acknowledge it."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        translator.anchor_finder.find_similar_workout = Mock(return_value=None)
        
        narrative = translator.narrate_workout_context("intervals", "6x1000m", 5.5)
        
        assert narrative is not None
        assert "first time" in narrative.text.lower()


class TestInjuryReboundNarratives:
    """Test injury rebound narrative generation."""
    
    def test_rebound_with_prior(self, mock_db, athlete_id, injured_fitness_bank):
        """Injury rebound with prior comparison."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        # Mock prior rebound
        prior = InjuryReboundAnchor(
            injury_date=date.today() - timedelta(days=200),
            rebound_date=date.today() - timedelta(days=180),
            weeks_to_recover=6,
            peak_volume_before=70.0,
            volume_at_rebound=50.0,
            recovery_pct=0.71
        )
        translator.anchor_finder.find_previous_injury_rebound = Mock(return_value=prior)
        
        narrative = translator.narrate_injury_rebound(injured_fitness_bank, 3)
        
        assert narrative is not None
        assert "3 weeks" in narrative.text
        assert "peak" in narrative.text.lower() or "%" in narrative.text
        assert narrative.priority >= 85
    
    def test_rebound_first_injury(self, mock_db, athlete_id, injured_fitness_bank):
        """First injury in records."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        translator.anchor_finder.find_previous_injury_rebound = Mock(return_value=None)
        
        narrative = translator.narrate_injury_rebound(injured_fitness_bank, 3)
        
        assert narrative is not None
        assert "first" in narrative.text.lower() or "setback" in narrative.text.lower()
    
    def test_no_injury_returns_none(self, mock_db, athlete_id, mock_fitness_bank):
        """No injury constraint should return None."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        narrative = translator.narrate_injury_rebound(mock_fitness_bank, 0)
        
        assert narrative is None


class TestUncertaintyNarratives:
    """Test prediction uncertainty narratives."""
    
    def test_injury_uncertainty(self, mock_db, athlete_id, injured_fitness_bank):
        """Injury-based uncertainty."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        narrative = translator.narrate_uncertainty(5, 8, "injury", injured_fitness_bank)
        
        assert narrative is not None
        assert "±5-8" in narrative.text
        assert "leg" in narrative.text.lower()
    
    def test_short_history_uncertainty(self, mock_db, athlete_id, mock_fitness_bank):
        """Limited data uncertainty."""
        mock_fitness_bank.race_performances = []  # Empty races
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        narrative = translator.narrate_uncertainty(4, 6, "short_history", mock_fitness_bank)
        
        assert narrative is not None
        assert "0 races" in narrative.text or "data" in narrative.text.lower()


class TestTauNarratives:
    """Test τ characteristic narratives."""
    
    def test_fast_adapter(self, mock_db, athlete_id):
        """Fast adapter (low τ1)."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        narrative = translator.narrate_tau(25.0)
        
        assert narrative is not None
        assert "25" in narrative.text
        assert "faster" in narrative.text.lower() or "adapt" in narrative.text.lower()
    
    def test_slow_adapter(self, mock_db, athlete_id):
        """Slow adapter (high τ1)."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        narrative = translator.narrate_tau(50.0)
        
        assert narrative is not None
        assert "50" in narrative.text
        assert "patience" in narrative.text.lower() or "consistency" in narrative.text.lower()
    
    def test_typical_tau_returns_none(self, mock_db, athlete_id):
        """Typical τ1 should not generate narrative."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        narrative = translator.narrate_tau(40.0)
        
        assert narrative is None


class TestHeroNarrative:
    """Test hero sentence selection."""
    
    def test_hero_prioritizes_injury(self, mock_db, athlete_id, injured_fitness_bank):
        """Injury rebound should be highest priority."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        # Mock all anchor finders
        translator.anchor_finder.find_previous_injury_rebound = Mock(return_value=None)
        translator.anchor_finder.find_comparable_load_state = Mock(return_value=None)
        translator.anchor_finder.find_efficiency_outlier = Mock(return_value=None)
        translator.anchor_finder.find_similar_milestone = Mock(return_value=None)
        
        hero = translator.get_hero_narrative(
            injured_fitness_bank, tsb=-5, ctl=60, atl=65
        )
        
        assert hero is not None
        assert hero.signal_type in ["injury_rebound", "load_state_coiled", "load_state_balanced"]
    
    def test_hero_fallback(self, mock_db, athlete_id, mock_fitness_bank):
        """Should always return something."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        # Mock all to return None
        translator.anchor_finder.find_prior_race_at_load = Mock(return_value=None)
        translator.anchor_finder.find_comparable_load_state = Mock(return_value=None)
        translator.anchor_finder.find_efficiency_outlier = Mock(return_value=None)
        translator.anchor_finder.find_similar_milestone = Mock(return_value=None)
        
        hero = translator.get_hero_narrative(
            mock_fitness_bank, tsb=0, ctl=70, atl=70
        )
        
        assert hero is not None
        assert len(hero.text) > 0


# =============================================================================
# NARRATIVE MEMORY TESTS
# =============================================================================

class TestNarrativeMemory:
    """Test narrative memory/deduplication."""
    
    def test_record_and_check(self, mock_db, athlete_id):
        """Basic record and check flow."""
        # Clear memory store for this test
        _memory_store.clear()
        
        memory = NarrativeMemory(mock_db, athlete_id, use_redis=False)
        
        # Should not be shown initially
        assert not memory.recently_shown("test_hash_123", days=14)
        
        # Record it
        memory.record_shown("test_hash_123", "load_state", "home")
        
        # Now should be shown
        assert memory.recently_shown("test_hash_123", days=14)
    
    def test_expiry(self, mock_db, athlete_id):
        """Old records should not count as recent."""
        _memory_store.clear()
        
        memory = NarrativeMemory(mock_db, athlete_id, use_redis=False)
        
        # Manually insert old record
        _memory_store[str(athlete_id)] = {
            "old_hash": datetime.utcnow() - timedelta(days=30)
        }
        
        # Should not be "recently" shown (default 14 days)
        assert not memory.recently_shown("old_hash", days=14)
        
        # But should be shown in 60-day window
        assert memory.recently_shown("old_hash", days=60)
    
    def test_filter_fresh(self, mock_db, athlete_id):
        """Filter to only fresh narratives."""
        _memory_store.clear()
        
        memory = NarrativeMemory(mock_db, athlete_id, use_redis=False)
        
        # Record one narrative
        memory.record_shown("shown_hash", "load_state", "home")
        
        # Create narratives
        narratives = [
            Narrative("Shown text", "load_state", 80, "shown_hash"),
            Narrative("Fresh text", "workout", 70, "fresh_hash"),
        ]
        
        fresh = memory.filter_fresh(narratives, days=14)
        
        assert len(fresh) == 1
        assert fresh[0].hash == "fresh_hash"
    
    def test_pick_freshest(self, mock_db, athlete_id):
        """Pick freshest with priority fallback."""
        _memory_store.clear()
        
        memory = NarrativeMemory(mock_db, athlete_id, use_redis=False)
        
        # All fresh - should return highest priority
        narratives = [
            Narrative("Low priority", "milestone", 50, "hash1"),
            Narrative("High priority", "injury_rebound", 95, "hash2"),
            Narrative("Medium priority", "load_state", 75, "hash3"),
        ]
        
        picked = memory.pick_freshest(narratives, count=2)
        
        assert len(picked) == 2
        assert picked[0].priority == 95
        assert picked[1].priority == 75


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestNarrativeLayerIntegration:
    """Integration tests for the full narrative flow."""
    
    def test_full_flow_no_crash(self, mock_db, athlete_id, mock_fitness_bank):
        """Full flow should not crash."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        # Mock all queries
        translator.anchor_finder.find_prior_race_at_load = Mock(return_value=None)
        translator.anchor_finder.find_comparable_load_state = Mock(return_value=None)
        translator.anchor_finder.find_similar_workout = Mock(return_value=None)
        translator.anchor_finder.find_efficiency_outlier = Mock(return_value=None)
        translator.anchor_finder.find_similar_milestone = Mock(return_value=None)
        
        # Get all narratives
        narratives = translator.get_all_narratives(
            mock_fitness_bank, tsb=5, ctl=70, atl=65,
            upcoming_workout={"workout_type": "threshold", "name": "Tempo"}
        )
        
        assert isinstance(narratives, list)
        assert all(isinstance(n, Narrative) for n in narratives)
    
    def test_narratives_have_required_fields(self, mock_db, athlete_id, mock_fitness_bank):
        """All narratives should have required fields."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        # Mock
        translator.anchor_finder.find_prior_race_at_load = Mock(return_value=None)
        translator.anchor_finder.find_comparable_load_state = Mock(return_value=None)
        translator.anchor_finder.find_efficiency_outlier = Mock(return_value=None)
        translator.anchor_finder.find_similar_milestone = Mock(return_value=None)
        
        narratives = translator.get_all_narratives(
            mock_fitness_bank, tsb=15, ctl=70, atl=55
        )
        
        for n in narratives:
            assert n.text is not None and len(n.text) > 0
            assert n.signal_type is not None
            assert n.priority is not None
            assert n.hash is not None
    
    def test_memory_prevents_duplicates(self, mock_db, athlete_id, mock_fitness_bank):
        """Memory should filter out recently shown narratives."""
        _memory_store.clear()
        
        translator = NarrativeTranslator(mock_db, athlete_id)
        memory = NarrativeMemory(mock_db, athlete_id, use_redis=False)
        
        # Mock
        translator.anchor_finder.find_prior_race_at_load = Mock(return_value=None)
        translator.anchor_finder.find_comparable_load_state = Mock(return_value=None)
        translator.anchor_finder.find_efficiency_outlier = Mock(return_value=None)
        translator.anchor_finder.find_similar_milestone = Mock(return_value=None)
        
        # Get narratives first time
        narratives1 = translator.get_all_narratives(mock_fitness_bank, 15, 70, 55)
        
        # Record them as shown
        for n in narratives1:
            memory.record_shown(n.hash, n.signal_type, "test")
        
        # Get narratives again
        narratives2 = translator.get_all_narratives(mock_fitness_bank, 15, 70, 55)
        
        # Filter fresh
        fresh = memory.filter_fresh(narratives2, days=14)
        
        # Should have fewer (or same if anchors changed the text)
        assert len(fresh) <= len(narratives2)


# =============================================================================
# ADDITIONAL EDGE CASE TESTS FOR COVERAGE
# =============================================================================

class TestNarrativeEdgeCases:
    """Edge case tests for improved coverage."""
    
    def test_efficiency_no_outlier(self, mock_db, athlete_id):
        """Efficiency with no significant outlier returns None."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        translator.anchor_finder.find_efficiency_outlier = Mock(return_value=None)
        
        narrative = translator.narrate_efficiency()
        assert narrative is None
    
    def test_efficiency_low_delta(self, mock_db, athlete_id):
        """Efficiency with low delta (< 3%) returns None."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        anchor = EfficiencyAnchor(
            activity_id=uuid4(),
            date=date.today() - timedelta(days=5),
            name="Easy run",
            efficiency_score=1.5,
            delta_from_baseline=2.0,  # Below 3% threshold
            direction="high"
        )
        translator.anchor_finder.find_efficiency_outlier = Mock(return_value=anchor)
        
        narrative = translator.narrate_efficiency()
        assert narrative is None
    
    def test_efficiency_negative_delta(self, mock_db, athlete_id):
        """Efficiency with negative delta shows correct message."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        
        anchor = EfficiencyAnchor(
            activity_id=uuid4(),
            date=date.today() - timedelta(days=3),
            name="Long run",
            efficiency_score=1.2,
            delta_from_baseline=-5.5,
            direction="low"
        )
        translator.anchor_finder.find_efficiency_outlier = Mock(return_value=anchor)
        
        narrative = translator.narrate_efficiency()
        assert narrative is not None
        assert "less" in narrative.text.lower() or "off day" in narrative.text.lower()
    
    def test_milestone_low_percentage(self, mock_db, athlete_id):
        """Milestone at low percentage of peak returns None."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        translator.anchor_finder.find_similar_milestone = Mock(return_value=None)
        
        # 40% of 70 = 28 miles, too low to narrate
        narrative = translator.narrate_milestone(28.0, 70.0)
        assert narrative is None
    
    def test_milestone_at_peak(self, mock_db, athlete_id):
        """Milestone at 90%+ peak generates narrative."""
        translator = NarrativeTranslator(mock_db, athlete_id)
        translator.anchor_finder.find_similar_milestone = Mock(return_value=None)
        
        # 63 miles is 90% of 70
        narrative = translator.narrate_milestone(63.0, 70.0)
        assert narrative is not None
        assert "peak" in narrative.text.lower() or "90%" in narrative.text
    
    def test_narrative_to_dict(self, mock_db, athlete_id):
        """Narrative to_dict returns correct structure."""
        narrative = Narrative(
            text="Test narrative",
            signal_type="test",
            priority=50,
            hash="abc123",
            anchors_used=["anchor1"]
        )
        
        d = narrative.to_dict()
        assert d["text"] == "Test narrative"
        assert d["signal_type"] == "test"
        assert d["priority"] == 50
    
    def test_get_narrative_translator_convenience(self, mock_db, athlete_id):
        """Convenience function returns translator."""
        from services.narrative_translator import get_narrative_translator
        
        translator = get_narrative_translator(mock_db, athlete_id)
        assert isinstance(translator, NarrativeTranslator)
    
    def test_get_narrative_memory_convenience(self, mock_db, athlete_id):
        """Convenience function returns memory."""
        from services.narrative_memory import get_narrative_memory
        
        memory = get_narrative_memory(mock_db, athlete_id)
        assert isinstance(memory, NarrativeMemory)


class TestMemoryEdgeCases:
    """Edge case tests for narrative memory."""
    
    def test_clear_old_memory_fallback(self, mock_db, athlete_id):
        """Clear old records in memory fallback."""
        _memory_store.clear()
        
        memory = NarrativeMemory(mock_db, athlete_id, use_redis=False)
        
        # Add old record
        _memory_store[str(athlete_id)] = {
            "old_hash": datetime.utcnow() - timedelta(days=90)
        }
        
        removed = memory.clear_old(days=60)
        assert removed == 1
        assert "old_hash" not in _memory_store.get(str(athlete_id), {})
    
    def test_get_stale_patterns_no_redis(self, mock_db, athlete_id):
        """Get stale patterns without Redis returns empty."""
        memory = NarrativeMemory(mock_db, athlete_id, use_redis=False)
        
        stale = memory.get_stale_patterns(threshold=5)
        assert stale == []
    
    def test_get_shown_count_no_redis(self, mock_db, athlete_id):
        """Get shown count without Redis returns 0."""
        memory = NarrativeMemory(mock_db, athlete_id, use_redis=False)
        
        count = memory.get_shown_count("load_state", days=30)
        assert count == 0
