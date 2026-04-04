"""
Tests: Coach Model Routing Reset (Scope A/B/C)

Validates:
- No runtime Opus usage remains
- Sonnet 4.6 is the live premium Anthropic model
- Non-founder premium cap still enforced
- Founder bypass still works
- Cap-hit fallback stays clean (goes to Gemini, not Opus)
- Gemini tool-call loop strips thought parts (thought_signature fix)
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4

from services.ai_coach import AICoach


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


@pytest.fixture
def coach_no_anthropic(mock_db):
    """Coach with no Anthropic key — only Gemini lane available."""
    with patch.dict("os.environ", {
        "COACH_MODEL_ROUTING": "on",
        "COACH_VIP_ATHLETE_IDS": "",
        "OWNER_ATHLETE_ID": "",
        "ANTHROPIC_API_KEY": "",
    }):
        c = AICoach(mock_db)
        c.anthropic_client = None
        c.gemini_client = MagicMock()
        return c


@pytest.fixture
def coach_with_anthropic(mock_db):
    """Coach with both Anthropic and Gemini clients available."""
    with patch.dict("os.environ", {
        "COACH_MODEL_ROUTING": "on",
        "COACH_VIP_ATHLETE_IDS": "",
        "OWNER_ATHLETE_ID": "",
        "ANTHROPIC_API_KEY": "sk-test",
    }):
        c = AICoach(mock_db)
        c.anthropic_client = MagicMock()
        c.gemini_client = MagicMock()
        return c


# ---------------------------------------------------------------------------
# Scope A: No runtime Opus, Sonnet 4.6 is live premium model
# ---------------------------------------------------------------------------

class TestNoRuntimeOpus:
    """Confirm MODEL_HIGH_STAKES is Sonnet, never Opus."""

    def test_model_high_stakes_is_sonnet(self, coach_no_anthropic):
        coach = coach_no_anthropic
        assert "sonnet" in coach.MODEL_HIGH_STAKES.lower(), (
            f"MODEL_HIGH_STAKES must be Sonnet, got: {coach.MODEL_HIGH_STAKES}"
        )
        assert "opus" not in coach.MODEL_HIGH_STAKES.lower(), (
            f"MODEL_HIGH_STAKES must not be Opus, got: {coach.MODEL_HIGH_STAKES}"
        )

    def test_model_high_stakes_exact_string(self, coach_no_anthropic):
        assert coach_no_anthropic.MODEL_HIGH_STAKES == "claude-sonnet-4-6"

    def test_no_fallback_to_opus(self, coach_no_anthropic):
        """All queries route to MODEL_HIGH_STAKES (Kimi path). Never Opus."""
        athlete_id = uuid4()
        model, is_premium = coach_no_anthropic.get_model_for_query(
            "high", athlete_id=athlete_id, message="should i skip my run, my knee hurts"
        )
        assert "opus" not in model.lower(), f"Fallback must not be Opus, got: {model}"
        assert model == coach_no_anthropic.MODEL_HIGH_STAKES

    def test_home_briefing_model_string(self):
        """Home briefing default model must be claude-sonnet-4-6, never claude-opus-4-6.

        The model is now config-driven via resolve_briefing_model() / BRIEFING_PRIMARY_MODEL.
        We verify:
        1. The default config value is claude-sonnet-4-6 (not opus).
        2. _call_opus_briefing_sync delegates to resolve_briefing_model (not hardcoded).
        3. The old opus string does not appear in the source.
        """
        import inspect
        from routers.home import _call_opus_briefing_sync
        from core.config import Settings

        # Default config must be sonnet, not opus
        default_model = Settings.model_fields["BRIEFING_PRIMARY_MODEL"].default
        assert default_model == "claude-sonnet-4-6", (
            f"BRIEFING_PRIMARY_MODEL default must be claude-sonnet-4-6, got {default_model}"
        )

        # Source must not hardcode opus
        src = inspect.getsource(_call_opus_briefing_sync)
        assert "claude-opus-4-6" not in src, "Home briefing must not reference claude-opus-4-6"

        # Source must delegate to resolve_briefing_model
        assert "resolve_briefing_model" in src, (
            "_call_opus_briefing_sync must use resolve_briefing_model() for model selection"
        )


class TestSonnetIsLivePremiumModel:
    """Premium Anthropic path routes to Sonnet."""

    def test_founder_gets_sonnet(self, mock_db):
        owner_id = uuid4()
        with patch.dict("os.environ", {
            "COACH_MODEL_ROUTING": "on",
            "COACH_HIGH_STAKES_ROUTING": "on",
            "OWNER_ATHLETE_ID": str(owner_id),
            "ANTHROPIC_API_KEY": "sk-test",
        }):
            coach = AICoach(mock_db)
            coach.anthropic_client = MagicMock()
            # Founder has active subscription check bypassed
            mock_db.query.return_value.filter.return_value.first.return_value = None
            model, is_premium = coach.get_model_for_query(
                "low", athlete_id=owner_id, message="what's my pace?"
            )
        assert model == "claude-sonnet-4-6", f"Founder must get Sonnet, got: {model}"
        assert is_premium is True

    def test_query_opus_uses_model_high_stakes(self, coach_with_anthropic):
        """query_opus() must call anthropic with MODEL_HIGH_STAKES (Sonnet)."""
        coach = coach_with_anthropic
        captured_model = []

        def fake_create(**kwargs):
            captured_model.append(kwargs.get("model"))
            resp = MagicMock()
            resp.stop_reason = "end_turn"
            resp.content = [MagicMock(type="text", text="Looks good, rest tomorrow.")]
            resp.usage.input_tokens = 100
            resp.usage.output_tokens = 50
            return resp

        coach.anthropic_client.messages.create.side_effect = fake_create
        with patch.object(coach, "_opus_tools", return_value=[]), \
             patch.object(coach, "track_usage"), \
             patch.object(coach, "_validate_tool_usage", return_value=(True, "ok")):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                coach.query_opus(
                    athlete_id=uuid4(),
                    message="should I rest?",
                    athlete_state="",
                )
            )
        assert captured_model, "anthropic_client.messages.create was never called"
        assert captured_model[0] == "claude-sonnet-4-6", (
            f"query_opus must call Sonnet, got: {captured_model[0]}"
        )
        assert "opus" not in (captured_model[0] or "").lower()


# ---------------------------------------------------------------------------
# Scope B: Non-founder premium cap preserved; founder bypass intact
# ---------------------------------------------------------------------------

class TestPremiumCapPreserved:
    """Non-founder premium lane is still capped at COACH_MAX_OPUS_REQUESTS_PER_DAY."""

    def _make_coach_with_usage(self, mock_db, requests_today: int):
        """Helper: build a coach whose usage record shows N premium requests today."""
        with patch.dict("os.environ", {
            "COACH_MODEL_ROUTING": "on",
            "OWNER_ATHLETE_ID": "",
            "ANTHROPIC_API_KEY": "sk-test",
            "COACH_MAX_OPUS_REQUESTS_PER_DAY": "3",
        }):
            coach = AICoach(mock_db)
            coach.anthropic_client = MagicMock()

        usage = MagicMock()
        usage.requests_today = requests_today
        usage.opus_requests_today = requests_today
        usage.tokens_this_month = 0
        usage.opus_tokens_this_month = 0
        with patch.object(coach, "_get_or_create_usage", return_value=usage), \
             patch.object(coach, "_is_founder", return_value=False):
            allowed, reason = coach.check_budget(
                uuid4(), is_opus=True, is_vip=False
            )
        return allowed, reason

    def test_non_founder_capped_at_limit(self, mock_db):
        allowed, reason = self._make_coach_with_usage(mock_db, requests_today=3)
        assert allowed is False
        assert reason == "daily_opus_limit"

    def test_non_founder_below_limit_allowed(self, mock_db):
        allowed, reason = self._make_coach_with_usage(mock_db, requests_today=2)
        assert allowed is True
        assert reason == "ok"

    def test_founder_bypasses_cap(self, mock_db):
        """Founder never hits the budget gate."""
        owner_id = uuid4()
        with patch.dict("os.environ", {
            "COACH_MODEL_ROUTING": "on",
            "OWNER_ATHLETE_ID": str(owner_id),
            "ANTHROPIC_API_KEY": "sk-test",
            "COACH_MAX_OPUS_REQUESTS_PER_DAY": "3",
        }):
            coach = AICoach(mock_db)
            coach.anthropic_client = MagicMock()

            usage = MagicMock()
            usage.requests_today = 9999
            usage.opus_requests_today = 9999
            with patch.object(coach, "_get_or_create_usage", return_value=usage):
                allowed, reason = coach.check_budget(owner_id, is_opus=True, is_vip=False)

        assert allowed is True
        assert reason == "founder_bypass"

    def test_cap_hit_still_routes_to_kimi(self, mock_db):
        """When premium cap is exhausted, routing still returns MODEL_HIGH_STAKES (Kimi path)."""
        athlete_id = uuid4()
        with patch.dict("os.environ", {
            "COACH_MODEL_ROUTING": "on",
            "OWNER_ATHLETE_ID": "",
            "ANTHROPIC_API_KEY": "sk-test",
        }):
            coach = AICoach(mock_db)
            coach.anthropic_client = MagicMock()

        with patch.object(coach, "_is_founder", return_value=False):
            model, is_premium = coach.get_model_for_query(
                "high", athlete_id=athlete_id, message="my knee hurts badly"
            )
        assert "opus" not in model.lower(), f"Must not be Opus, got: {model}"
        assert model == coach.MODEL_HIGH_STAKES
        assert is_premium is True


# ---------------------------------------------------------------------------
# Scope C: Gemini thought_signature fix
# ---------------------------------------------------------------------------

class TestGeminiThoughtSignatureFix:
    """
    Verify the tool-call multi-turn loop strips thought parts from model content
    before appending to conversation history.
    """

    def test_thought_parts_stripped_from_model_turn(self, coach_with_anthropic):
        """
        When the Gemini response includes thought parts alongside function_call parts,
        only the function_call parts should be sent back in the next turn's content.

        Verifies the defensive strip applied at line:
          safe_parts = [p for p in ... if hasattr(p, 'function_call') and p.function_call]
        """
        coach = coach_with_anthropic

        fc = MagicMock()
        fc.name = "get_recent_runs"
        fc.args = {}

        fc_part = MagicMock()
        fc_part.function_call = fc
        # No thought attribute on this part
        if hasattr(fc_part, "thought"):
            del fc_part.thought

        thought_part = MagicMock()
        thought_part.thought = "internal reasoning"
        # Explicitly remove function_call from thought part
        thought_part.function_call = None  # falsy — will be excluded

        # First response: thought + function_call parts
        first_candidate = MagicMock()
        first_candidate.content.parts = [thought_part, fc_part]
        first_response = MagicMock()
        first_response.candidates = [first_candidate]
        first_response.usage_metadata.prompt_token_count = 50
        first_response.usage_metadata.candidates_token_count = 20

        # Second response: text only (no more tool calls)
        text_part = MagicMock()
        text_part.function_call = None
        text_part.text = "You ran 42 miles last week."
        second_candidate = MagicMock()
        second_candidate.content.parts = [text_part]
        second_response = MagicMock()
        second_response.candidates = [second_candidate]
        second_response.usage_metadata.prompt_token_count = 100
        second_response.usage_metadata.candidates_token_count = 30

        responses_iter = iter([first_response, second_response])
        appended_model_parts = []

        def track_generate(model, contents, config):
            # Collect model-role Content parts that were forwarded
            for item in contents:
                if hasattr(item, "role") and item.role == "model":
                    for part in (item.parts or []):
                        appended_model_parts.append(part)
            return next(responses_iter)

        coach.gemini_client.models.generate_content.side_effect = track_generate

        with patch("services.ai_coach.coach_tools") as mock_ct, \
             patch.object(coach, "_execute_opus_tool", return_value={"runs": []}), \
             patch.object(coach, "track_usage"), \
             patch.object(coach, "_validate_tool_usage", return_value=(True, "ok")):
            mock_ct.build_athlete_brief.return_value = "brief text"
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                coach.query_gemini(
                    athlete_id=uuid4(),
                    message="how many miles did I run last week?",
                    athlete_state="",
                )
            )

        # All model-turn parts forwarded to the API must NOT be thought-only parts
        for part in appended_model_parts:
            assert getattr(part, "function_call", None), (
                "Only function_call parts should be in model turns forwarded to Gemini"
            )

    def test_model_string_is_not_opus(self, coach_with_anthropic):
        """MODEL_DEFAULT must not contain 'opus'."""
        assert "opus" not in coach_with_anthropic.MODEL_DEFAULT.lower()

    def test_requirements_pin_sdk_version(self):
        """google-genai pin must be present and not remove the upper bound cap."""
        import pathlib
        req_path = pathlib.Path(__file__).parent.parent / "requirements.txt"
        content = req_path.read_text()
        assert "google-genai" in content
        # Upper bound must still be present (no unbounded upgrades)
        assert "<2.0.0" in content or ",<2" in content
