"""
Unit tests for core/llm_client.py

Covers:
- Provider routing by model prefix
- Fallback chain behavior (kimi→anthropic→gemini, anthropic→gemini)
- JSON parse mode
- Canary gate logic (enabled/disabled, allowlist, missing key guard)
- Missing key startup validation
- call_llm_with_json_parse fence stripping and parse failure handling
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_settings(**kwargs):
    """Return a mock settings object with LLM fields."""
    s = MagicMock()
    s.KIMI_API_KEY = kwargs.get("KIMI_API_KEY", None)
    s.KIMI_BASE_URL = kwargs.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
    s.KIMI_CANARY_ENABLED = kwargs.get("KIMI_CANARY_ENABLED", False)
    s.KIMI_CANARY_ATHLETE_IDS = kwargs.get("KIMI_CANARY_ATHLETE_IDS", "")
    s.BRIEFING_PRIMARY_MODEL = kwargs.get("BRIEFING_PRIMARY_MODEL", "claude-sonnet-4-6")
    s.KNOWLEDGE_PRIMARY_MODEL = kwargs.get("KNOWLEDGE_PRIMARY_MODEL", "claude-sonnet-4-6")
    return s


def _make_llm_response(**kwargs):
    from core.llm_client import LLMResponse
    return LLMResponse(
        text=kwargs.get("text", "hello"),
        model=kwargs.get("model", "claude-sonnet-4-6"),
        provider=kwargs.get("provider", "anthropic"),
        input_tokens=kwargs.get("input_tokens", 100),
        output_tokens=kwargs.get("output_tokens", 50),
        latency_ms=kwargs.get("latency_ms", 200.0),
        finish_reason=kwargs.get("finish_reason", "end_turn"),
    )


# ---------------------------------------------------------------------------
# Provider routing
# ---------------------------------------------------------------------------

class TestProviderRouting:
    def test_claude_model_routes_to_anthropic(self):
        from core.llm_client import _provider_for_model
        assert _provider_for_model("claude-sonnet-4-6") == "anthropic"
        assert _provider_for_model("claude-3-5-sonnet-20241022") == "anthropic"

    def test_kimi_model_routes_to_kimi(self):
        from core.llm_client import _provider_for_model
        assert _provider_for_model("kimi-k2.5") == "kimi"

    def test_gemini_model_routes_to_gemini(self):
        from core.llm_client import _provider_for_model
        assert _provider_for_model("gemini-2.5-flash") == "gemini"
        assert _provider_for_model("gemini-3-flash-preview") == "gemini"

    def test_unknown_model_raises(self):
        from core.llm_client import _provider_for_model
        with pytest.raises(ValueError, match="Unknown model family"):
            _provider_for_model("gpt-4-turbo")


# ---------------------------------------------------------------------------
# call_llm — happy path
# ---------------------------------------------------------------------------

class TestCallLlmHappyPath:
    def test_calls_anthropic_adapter_for_claude(self):
        from core import llm_client
        response = _make_llm_response(model="claude-sonnet-4-6", provider="anthropic")
        mock_fn = MagicMock(return_value=response)
        with patch.dict(llm_client._ADAPTER_MAP, {"anthropic": mock_fn}):
            result = llm_client.call_llm(
                model="claude-sonnet-4-6",
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                temperature=0.3,
            )
        mock_fn.assert_called_once()
        assert result["provider"] == "anthropic"
        assert result["model"] == "claude-sonnet-4-6"

    def test_calls_kimi_adapter_for_kimi(self):
        from core import llm_client
        response = _make_llm_response(model="kimi-k2.5", provider="kimi")
        mock_fn = MagicMock(return_value=response)
        with patch.dict(llm_client._ADAPTER_MAP, {"kimi": mock_fn}):
            result = llm_client.call_llm(
                model="kimi-k2.5",
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                temperature=0.3,
            )
        mock_fn.assert_called_once()
        assert result["provider"] == "kimi"

    def test_calls_gemini_adapter_for_gemini(self):
        from core import llm_client
        response = _make_llm_response(model="gemini-2.5-flash", provider="gemini")
        mock_fn = MagicMock(return_value=response)
        with patch.dict(llm_client._ADAPTER_MAP, {"gemini": mock_fn}):
            result = llm_client.call_llm(
                model="gemini-2.5-flash",
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                temperature=0.3,
            )
        mock_fn.assert_called_once()
        assert result["provider"] == "gemini"


# ---------------------------------------------------------------------------
# Fallback chain
# ---------------------------------------------------------------------------

class TestFallbackChain:
    def test_kimi_failure_falls_back_to_anthropic(self):
        from core import llm_client
        sonnet_resp = _make_llm_response(model="claude-sonnet-4-6", provider="anthropic")

        mock_kimi = MagicMock(side_effect=RuntimeError("kimi down"))
        mock_ant = MagicMock(return_value=sonnet_resp)

        with patch.dict(llm_client._ADAPTER_MAP, {"kimi": mock_kimi, "anthropic": mock_ant}):
            result = llm_client.call_llm(
                model="kimi-k2.5",
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                temperature=0.3,
            )
        mock_ant.assert_called_once()
        assert result["provider"] == "anthropic"
        assert result["model"] == "claude-sonnet-4-6"

    def test_kimi_and_anthropic_failure_falls_back_to_gemini(self):
        from core import llm_client
        gemini_resp = _make_llm_response(model="gemini-2.5-flash", provider="gemini")

        mock_kimi = MagicMock(side_effect=RuntimeError("kimi down"))
        mock_ant = MagicMock(side_effect=RuntimeError("anthropic down"))
        mock_gem = MagicMock(return_value=gemini_resp)

        with patch.dict(llm_client._ADAPTER_MAP, {"kimi": mock_kimi, "anthropic": mock_ant, "gemini": mock_gem}):
            result = llm_client.call_llm(
                model="kimi-k2.5",
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                temperature=0.3,
            )
        mock_gem.assert_called_once()
        assert result["provider"] == "gemini"

    def test_anthropic_failure_falls_back_to_gemini(self):
        from core import llm_client
        gemini_resp = _make_llm_response(model="gemini-2.5-flash", provider="gemini")

        mock_ant = MagicMock(side_effect=RuntimeError("anthropic down"))
        mock_gem = MagicMock(return_value=gemini_resp)

        with patch.dict(llm_client._ADAPTER_MAP, {"anthropic": mock_ant, "gemini": mock_gem}):
            result = llm_client.call_llm(
                model="claude-sonnet-4-6",
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                temperature=0.3,
            )
        assert result["provider"] == "gemini"

    def test_all_providers_fail_raises_runtime_error(self):
        from core import llm_client

        mock_kimi = MagicMock(side_effect=RuntimeError("kimi down"))
        mock_ant = MagicMock(side_effect=RuntimeError("anthropic down"))
        mock_gem = MagicMock(side_effect=RuntimeError("gemini down"))

        with patch.dict(llm_client._ADAPTER_MAP, {"kimi": mock_kimi, "anthropic": mock_ant, "gemini": mock_gem}):
            with pytest.raises(RuntimeError, match="All LLM providers failed"):
                llm_client.call_llm(
                    model="kimi-k2.5",
                    system="sys",
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=100,
                    temperature=0.3,
                )


# ---------------------------------------------------------------------------
# JSON mode — fence stripping + parse handling
# ---------------------------------------------------------------------------

class TestJsonMode:
    def test_valid_json_returned(self):
        from core.llm_client import call_llm_with_json_parse
        resp = _make_llm_response(text='{"key": "value"}')
        with patch("core.llm_client.call_llm", return_value=resp):
            result = call_llm_with_json_parse(
                model="claude-sonnet-4-6",
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                temperature=0.3,
            )
        assert result == {"key": "value"}

    def test_markdown_fences_stripped(self):
        from core.llm_client import call_llm_with_json_parse
        fenced = '```json\n{"coach_noticed": "You ran well"}\n```'
        resp = _make_llm_response(text=fenced)
        with patch("core.llm_client.call_llm", return_value=resp):
            result = call_llm_with_json_parse(
                model="claude-sonnet-4-6",
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                temperature=0.3,
            )
        assert result == {"coach_noticed": "You ran well"}

    def test_parse_failure_returns_none(self):
        from core.llm_client import call_llm_with_json_parse
        resp = _make_llm_response(text="This is not JSON at all")
        with patch("core.llm_client.call_llm", return_value=resp):
            result = call_llm_with_json_parse(
                model="claude-sonnet-4-6",
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                temperature=0.3,
            )
        assert result is None

    def test_provider_failure_returns_none_not_raises(self):
        from core.llm_client import call_llm_with_json_parse
        with patch("core.llm_client.call_llm", side_effect=RuntimeError("all failed")):
            result = call_llm_with_json_parse(
                model="kimi-k2.5",
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                temperature=0.3,
            )
        assert result is None


# ---------------------------------------------------------------------------
# Canary gate
# ---------------------------------------------------------------------------

class TestCanaryGate:
    ATHLETE_A = str(uuid4())
    ATHLETE_B = str(uuid4())

    def test_canary_disabled_returns_primary_model(self):
        from core.llm_client import resolve_briefing_model
        settings = _mock_settings(KIMI_CANARY_ENABLED=False, BRIEFING_PRIMARY_MODEL="claude-sonnet-4-6")
        with patch("core.llm_client._get_settings", return_value=settings):
            model = resolve_briefing_model(athlete_id=self.ATHLETE_A)
        assert model == "claude-sonnet-4-6"

    def test_canary_enabled_allowlisted_athlete_gets_kimi(self):
        from core.llm_client import resolve_briefing_model
        settings = _mock_settings(
            KIMI_CANARY_ENABLED=True,
            KIMI_API_KEY="fake-key",
            KIMI_CANARY_ATHLETE_IDS=self.ATHLETE_A,
            BRIEFING_PRIMARY_MODEL="claude-sonnet-4-6",
        )
        with patch("core.llm_client._get_settings", return_value=settings):
            model = resolve_briefing_model(athlete_id=self.ATHLETE_A)
        assert model == "kimi-k2.5"

    def test_canary_enabled_non_allowlisted_athlete_gets_primary(self):
        from core.llm_client import resolve_briefing_model
        settings = _mock_settings(
            KIMI_CANARY_ENABLED=True,
            KIMI_API_KEY="fake-key",
            KIMI_CANARY_ATHLETE_IDS=self.ATHLETE_A,
            BRIEFING_PRIMARY_MODEL="claude-sonnet-4-6",
        )
        with patch("core.llm_client._get_settings", return_value=settings):
            model = resolve_briefing_model(athlete_id=self.ATHLETE_B)
        assert model == "claude-sonnet-4-6"

    def test_canary_enabled_but_missing_key_disables_canary(self):
        """If KIMI_CANARY_ENABLED=true but key is missing, fall back to primary silently."""
        from core.llm_client import resolve_briefing_model
        settings = _mock_settings(
            KIMI_CANARY_ENABLED=True,
            KIMI_API_KEY=None,  # key missing
            KIMI_CANARY_ATHLETE_IDS=self.ATHLETE_A,
            BRIEFING_PRIMARY_MODEL="claude-sonnet-4-6",
        )
        with patch("core.llm_client._get_settings", return_value=settings):
            with patch.dict(os.environ, {}, clear=True):  # ensure env var absent too
                model = resolve_briefing_model(athlete_id=self.ATHLETE_A)
        # Must fall back to primary — never route to Kimi without a key
        assert model == "claude-sonnet-4-6"

    def test_no_athlete_id_returns_primary_model(self):
        from core.llm_client import resolve_briefing_model
        settings = _mock_settings(
            KIMI_CANARY_ENABLED=True,
            KIMI_API_KEY="fake-key",
            KIMI_CANARY_ATHLETE_IDS=self.ATHLETE_A,
            BRIEFING_PRIMARY_MODEL="claude-sonnet-4-6",
        )
        with patch("core.llm_client._get_settings", return_value=settings):
            model = resolve_briefing_model(athlete_id=None)
        assert model == "claude-sonnet-4-6"

    def test_is_canary_athlete_true_for_allowlisted(self):
        from core.llm_client import is_canary_athlete
        settings = _mock_settings(
            KIMI_CANARY_ENABLED=True,
            KIMI_API_KEY="fake-key",
            KIMI_CANARY_ATHLETE_IDS=self.ATHLETE_A,
        )
        with patch("core.llm_client._get_settings", return_value=settings):
            assert is_canary_athlete(self.ATHLETE_A) is True

    def test_is_canary_athlete_false_for_non_allowlisted(self):
        from core.llm_client import is_canary_athlete
        settings = _mock_settings(
            KIMI_CANARY_ENABLED=True,
            KIMI_API_KEY="fake-key",
            KIMI_CANARY_ATHLETE_IDS=self.ATHLETE_A,
        )
        with patch("core.llm_client._get_settings", return_value=settings):
            assert is_canary_athlete(self.ATHLETE_B) is False

    def test_multiple_canary_athletes_comma_separated(self):
        from core.llm_client import resolve_briefing_model
        ids = f"{self.ATHLETE_A},{self.ATHLETE_B}"
        settings = _mock_settings(
            KIMI_CANARY_ENABLED=True,
            KIMI_API_KEY="fake-key",
            KIMI_CANARY_ATHLETE_IDS=ids,
            BRIEFING_PRIMARY_MODEL="claude-sonnet-4-6",
        )
        with patch("core.llm_client._get_settings", return_value=settings):
            assert resolve_briefing_model(athlete_id=self.ATHLETE_A) == "kimi-k2.5"
            assert resolve_briefing_model(athlete_id=self.ATHLETE_B) == "kimi-k2.5"


# ---------------------------------------------------------------------------
# Missing key validation
# ---------------------------------------------------------------------------

class TestMissingKeyValidation:
    def test_anthropic_missing_key_raises_runtime_error(self):
        from core.llm_client import _call_anthropic
        with patch.dict(os.environ, {}, clear=True):
            # Ensure ANTHROPIC_API_KEY not in env
            env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY not set"):
                    _call_anthropic(
                        model="claude-sonnet-4-6",
                        system="sys",
                        messages=[{"role": "user", "content": "hi"}],
                        max_tokens=100,
                        temperature=0.3,
                        response_mode="text",
                        timeout_s=10,
                    )

    def test_kimi_missing_key_raises_runtime_error(self):
        from core.llm_client import _call_kimi
        settings = _mock_settings(KIMI_API_KEY=None)
        with patch("core.llm_client._get_settings", return_value=settings):
            with patch.dict(os.environ, {k: v for k, v in os.environ.items() if k != "KIMI_API_KEY"}, clear=True):
                with pytest.raises(RuntimeError) as exc_info:
                    _call_kimi(
                        model="kimi-k2.5",
                        system="sys",
                        messages=[{"role": "user", "content": "hi"}],
                        max_tokens=100,
                        temperature=0.3,
                        response_mode="text",
                        timeout_s=10,
                    )
                # Either "KIMI_API_KEY not set" or "openai package not installed" —
                # both are valid runtime guards that prevent a live call
                assert "KIMI_API_KEY" in str(exc_info.value) or "openai" in str(exc_info.value)

    def test_canary_missing_key_does_not_raise_returns_primary(self):
        """Missing KIMI_API_KEY with canary enabled must never raise — silently disable canary."""
        from core.llm_client import resolve_briefing_model
        athlete_id = str(uuid4())
        settings = _mock_settings(
            KIMI_CANARY_ENABLED=True,
            KIMI_API_KEY=None,
            KIMI_CANARY_ATHLETE_IDS=athlete_id,
            BRIEFING_PRIMARY_MODEL="claude-sonnet-4-6",
        )
        with patch("core.llm_client._get_settings", return_value=settings):
            with patch.dict(os.environ, {k: v for k, v in os.environ.items() if k != "KIMI_API_KEY"}, clear=True):
                # Must not raise
                model = resolve_briefing_model(athlete_id=athlete_id)
        assert model == "claude-sonnet-4-6"
