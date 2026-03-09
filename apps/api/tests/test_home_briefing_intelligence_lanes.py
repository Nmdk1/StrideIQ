"""
Tests for home briefing intelligence lanes — structural separation,
system-speak removal, and diversity enforcement.
"""

import inspect
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(**overrides):
    defaults = {
        "id": uuid4(),
        "athlete_id": uuid4(),
        "input_name": "sleep_hours",
        "output_metric": "efficiency",
        "direction": "positive",
        "time_lag_days": 1,
        "correlation_coefficient": 0.62,
        "p_value": 0.001,
        "sample_size": 45,
        "strength": "strong",
        "times_confirmed": 8,
        "first_detected_at": datetime.now(timezone.utc) - timedelta(days=90),
        "last_confirmed_at": datetime.now(timezone.utc) - timedelta(hours=3),
        "insight_text": "More sleep improves your next-day efficiency",
        "category": "what_works",
        "confidence": 0.85,
        "is_active": True,
        "threshold_value": 6.2,
        "threshold_direction": "below_hurts",
        "r_below_threshold": -0.71,
        "r_above_threshold": 0.15,
        "n_below_threshold": 18,
        "n_above_threshold": 27,
        "asymmetry_ratio": 3.1,
        "asymmetry_direction": "negative_stronger",
        "effect_below_baseline": -0.71,
        "effect_above_baseline": 0.15,
        "decay_half_life_days": 2.0,
        "decay_type": "exponential",
        "is_confounded": False,
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


# ---------------------------------------------------------------------------
# 1. Prompt contract: no confirmation count instructions
# ---------------------------------------------------------------------------

def test_prompt_contract_removes_confirmation_count_instructions():
    """
    The system prompt must NOT tell the LLM to reference evidence counts
    or require confirmation counts — these are system-speak.
    """
    from routers.home import generate_coach_home_briefing

    source = inspect.getsource(generate_coach_home_briefing)

    banned_phrases = [
        "reference them by evidence count",
        "NEVER reference a pattern without its confirmation count",
    ]
    for phrase in banned_phrases:
        assert phrase not in source, (
            f"Prompt still contains banned phrase: '{phrase}'"
        )


# ---------------------------------------------------------------------------
# 2. Schema fields have explicit lane blocks
# ---------------------------------------------------------------------------

def test_schema_fields_have_explicit_lane_blocks():
    """
    Each required schema field description must contain
    'YOUR DATA FOR THIS FIELD:' to enforce structural lane separation.
    """
    with patch("services.coach_tools.build_athlete_brief", return_value="(brief)"), \
         patch("routers.home._build_rich_intelligence_context", return_value=""), \
         patch("routers.home.compute_coach_noticed", return_value=None), \
         patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(None, None)), \
         patch("services.fingerprint_context.build_fingerprint_prompt_section", return_value=None):
        from routers.home import generate_coach_home_briefing

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        result = generate_coach_home_briefing(
            athlete_id=str(uuid4()),
            db=mock_db,
            skip_cache=True,
        )

        assert result is not None
        assert len(result) > 1, "Expected tuple, not cached result"
        schema_fields = result[2]

        required_lane_fields = [
            "coach_noticed", "today_context", "week_assessment",
            "checkin_reaction", "race_assessment", "morning_voice",
        ]
        for field_name in required_lane_fields:
            desc = schema_fields.get(field_name, "")
            assert "YOUR DATA FOR THIS FIELD:" in desc, (
                f"Field '{field_name}' missing lane block 'YOUR DATA FOR THIS FIELD:'"
            )


# ---------------------------------------------------------------------------
# 3. compute_coach_noticed uses times_confirmed >= 3
# ---------------------------------------------------------------------------

def test_compute_coach_noticed_uses_confirmed_threshold():
    """
    The persisted finding gate in compute_coach_noticed must require
    times_confirmed >= 3, not >= 1. Live correlation calls must be removed.
    """
    source = inspect.getsource(
        __import__("routers.home", fromlist=["compute_coach_noticed"]).compute_coach_noticed
    )
    assert "times_confirmed >= 3" in source, (
        "compute_coach_noticed must gate on times_confirmed >= 3"
    )
    # Must not import or call the live correlation engine
    assert "from services.correlation_engine" not in source, (
        "compute_coach_noticed must not import live correlation engine"
    )


# ---------------------------------------------------------------------------
# 4. compute_coach_noticed does not emit stats language
# ---------------------------------------------------------------------------

def test_compute_coach_noticed_does_not_emit_stats_language():
    """
    The text returned by compute_coach_noticed for a fingerprint finding
    must not contain statistical internals.
    """
    from routers.home import compute_coach_noticed

    finding = _make_finding(times_confirmed=5)

    mock_db = MagicMock()
    query_chain = MagicMock()
    query_chain.filter.return_value = query_chain
    query_chain.order_by.return_value = query_chain
    query_chain.limit.return_value = query_chain
    query_chain.all.return_value = [finding]
    mock_db.query.return_value = query_chain

    with patch("routers.home._is_finding_in_cooldown", return_value=False):
        result = compute_coach_noticed(str(uuid4()), mock_db)

    assert result is not None
    text = result.text.lower()
    banned = ["confirmed", "r=", "correlation", "observations", "p-value", "times_confirmed"]
    for term in banned:
        assert term not in text, (
            f"coach_noticed text contains banned stats term '{term}': {result.text}"
        )


# ---------------------------------------------------------------------------
# 5. Diversity validator flags cross-lane leakage
# ---------------------------------------------------------------------------

def test_diversity_validator_flags_cross_lane_leakage():
    """
    When fingerprint terms from morning_voice appear in 2+ other fields,
    the diversity validator should log a warning.
    """
    from routers.home import _validate_briefing_diversity

    fields = {
        "morning_voice": "Your sleep cliff is at 6.2h — efficiency drops below that threshold.",
        "coach_noticed": "Your sleep cliff data shows a clear pattern in your threshold zone.",
        "week_assessment": "The sleep cliff effect dominated this week's efficiency numbers.",
        "today_context": "Easy 5 miles today.",
    }

    import logging
    with patch.object(logging.getLogger("routers.home"), "warning") as mock_warn:
        result = _validate_briefing_diversity(fields, "test-athlete")

    assert result == fields  # monitor mode — returns unchanged
    mock_warn.assert_called_once()
    call_args = mock_warn.call_args[0][0]
    assert "diversity violation" in call_args.lower()


# ---------------------------------------------------------------------------
# 6. Same finding in 3+ fields is flagged
# ---------------------------------------------------------------------------

def test_repetition_enforcement_same_finding_not_in_3plus_fields():
    """
    When fingerprint terms leak into 3+ non-morning fields,
    the diversity validator logs a warning with all leaking field names.
    """
    from routers.home import _validate_briefing_diversity

    fields = {
        "morning_voice": "Your sleep threshold is at 6.2h. Below that, efficiency drops sharply.",
        "coach_noticed": "The threshold effect from your sleep patterns is relevant today.",
        "week_assessment": "Sleep threshold has been the dominant factor this week.",
        "checkin_reaction": "Your threshold data says keep sleep high tonight.",
        "today_context": "Easy recovery run.",
    }

    import logging
    with patch.object(logging.getLogger("routers.home"), "warning") as mock_warn:
        result = _validate_briefing_diversity(fields, "test-athlete")

    assert result == fields
    mock_warn.assert_called_once()
    warn_msg = str(mock_warn.call_args)
    assert "coach_noticed" in warn_msg
    assert "week_assessment" in warn_msg
    assert "checkin_reaction" in warn_msg
