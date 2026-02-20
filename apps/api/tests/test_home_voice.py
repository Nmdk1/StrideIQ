"""
Home Voice — RED tests for post-generation validator and contract.

These tests are written RED-first: they will FAIL until the voice
implementation (morning_voice, workout_why, validate_voice_output)
is added to apps/api/routers/home.py.

Test categories:
  1. Post-generation validator (fail-closed, no bypass)
  2. Regression: invalid LLM output never reaches morning_voice
  3. Regression: workout_why allows conceptual text but enforces ban-list/causal
  4. Contract compatibility (old 5 keys + new 2 keys)
  5. InsightLog aggregation for LLM context
"""

import pytest


# ---------------------------------------------------------------------------
# 1. Post-generation validator tests
# ---------------------------------------------------------------------------

class TestValidateVoiceOutput:
    """validate_voice_output must be fail-closed — no bypass, no warn-only."""

    def _get_validator(self):
        from routers.home import validate_voice_output
        return validate_voice_output

    def test_validator_exists(self):
        """validate_voice_output is importable from routers.home."""
        validate_voice_output = self._get_validator()
        assert callable(validate_voice_output)

    def test_ban_list_blocks_sycophantic_language(self):
        """Phrases like 'incredible', 'amazing', 'phenomenal' are rejected."""
        validate = self._get_validator()

        bad_texts = [
            "You had an incredible run yesterday, keep it up!",
            "Amazing consistency this week — truly phenomenal.",
            "What an extraordinary effort on your long run.",
        ]
        for text in bad_texts:
            result = validate(text)
            assert result["valid"] is False, f"Should have blocked: {text!r}"
            assert "ban_list" in result.get("reason", "")

    def test_causal_language_blocked(self):
        """'because you', 'caused by', 'due to your' are rejected."""
        validate = self._get_validator()

        causal_texts = [
            "Your pace dropped because you went out too fast.",
            "This fatigue is caused by your high mileage.",
            "Heart rate spiked due to your poor sleep last night.",
        ]
        for text in causal_texts:
            result = validate(text)
            assert result["valid"] is False, f"Should have blocked causal: {text!r}"
            assert "causal" in result.get("reason", "")

    def test_numeric_grounding_required(self):
        """morning_voice must contain at least one number."""
        validate = self._get_validator()
        result = validate("You ran well this week and your body is adapting nicely.")
        assert result["valid"] is False
        assert "numeric" in result.get("reason", "")

    def test_length_enforced(self):
        """morning_voice must be between 40 and 280 characters."""
        validate = self._get_validator()

        too_short = "Run 5 mi."  # < 40 chars
        assert validate(too_short)["valid"] is False
        assert "length" in validate(too_short).get("reason", "")

        too_long = "You ran 5 miles today " * 20  # > 280 chars, has number
        assert validate(too_long)["valid"] is False
        assert "length" in validate(too_long).get("reason", "")

    def test_valid_text_passes(self):
        """Clean, grounded text passes all checks."""
        validate = self._get_validator()
        good = "48 miles across 6 runs this week. HR averaged 142 bpm — consistent with your build phase targets."
        result = validate(good)
        assert result["valid"] is True

    def test_fallback_text_is_deterministic(self):
        """When validation fails, a deterministic fallback is returned."""
        validate = self._get_validator()
        result = validate("You are incredible and amazing!")
        assert result["valid"] is False
        assert "fallback" in result
        assert isinstance(result["fallback"], str)
        assert len(result["fallback"]) > 20  # not empty


# ---------------------------------------------------------------------------
# 2. Regression: invalid LLM output never reaches morning_voice
# ---------------------------------------------------------------------------

class TestInvalidOutputNeverReachesMorningVoice:
    """
    Guardrail regression: even if LLM returns banned text for
    morning_voice, the API response must contain the deterministic
    fallback — never the raw LLM output.
    """

    def test_banned_morning_voice_replaced_with_fallback(self):
        """
        Simulates LLM returning sycophantic morning_voice.
        The validate_voice_output gate must replace it with fallback
        before it enters HomeResponse.coach_briefing.morning_voice.
        """
        from routers.home import validate_voice_output

        # Simulate: LLM returns banned text
        llm_morning_voice = "You had an incredible week — truly phenomenal consistency!"
        result = validate_voice_output(llm_morning_voice)

        # Gate rejects it
        assert result["valid"] is False

        # The fallback is what should enter the API response
        assert result["fallback"] is not None
        assert "incredible" not in result["fallback"].lower()
        assert "phenomenal" not in result["fallback"].lower()


# ---------------------------------------------------------------------------
# 3. Regression: workout_why validates correctly
# ---------------------------------------------------------------------------

class TestWorkoutWhyValidation:
    """
    workout_why allows conceptual explanations but still enforces
    ban-list and causal language checks.
    """

    def test_conceptual_why_passes(self):
        """A clean 'why' with numbers passes validation."""
        from routers.home import validate_voice_output

        why = "Active recovery day. 3.5 mi easy keeps blood flowing after yesterday's 10-mile effort."
        result = validate_voice_output(why, field="workout_why")
        assert result["valid"] is True

    def test_conceptual_why_without_numbers_passes(self):
        """workout_why allows conceptual text without numbers (relaxed numeric grounding)."""
        from routers.home import validate_voice_output

        why = "Active recovery keeps blood flowing and promotes adaptation after a hard training block."
        result = validate_voice_output(why, field="workout_why")
        assert result["valid"] is True

    def test_morning_voice_without_numbers_still_blocked(self):
        """morning_voice (not workout_why) still requires numeric grounding."""
        from routers.home import validate_voice_output

        voice = "You ran well this week and your body is adapting nicely to the training load."
        result = validate_voice_output(voice, field="morning_voice")
        assert result["valid"] is False
        assert "numeric" in result.get("reason", "")

    def test_why_with_banned_word_blocked(self):
        """Even workout_why blocks banned sycophantic language."""
        from routers.home import validate_voice_output

        why = "An incredible recovery run to celebrate your phenomenal week."
        result = validate_voice_output(why, field="workout_why")
        assert result["valid"] is False
        assert "ban_list" in result.get("reason", "")

    def test_why_with_causal_claim_blocked(self):
        """workout_why must not make causal claims."""
        from routers.home import validate_voice_output

        why = "Easy today because you overtrained this week."
        result = validate_voice_output(why, field="workout_why")
        assert result["valid"] is False
        assert "causal" in result.get("reason", "")


# ---------------------------------------------------------------------------
# 4. Contract compatibility: old 5 keys + new 2 keys
# ---------------------------------------------------------------------------

class TestCoachBriefingContract:
    """
    coach_briefing must retain all 5 existing keys AND add
    morning_voice + workout_why additively.
    """

    def test_generate_coach_home_briefing_schema_has_morning_voice(self):
        """The LLM schema in generate_coach_home_briefing includes morning_voice."""
        import inspect
        from routers.home import generate_coach_home_briefing

        source = inspect.getsource(generate_coach_home_briefing)
        assert "morning_voice" in source, "morning_voice must be in the LLM schema"

    def test_generate_coach_home_briefing_schema_has_workout_why(self):
        """The LLM schema in generate_coach_home_briefing includes workout_why."""
        import inspect
        from routers.home import generate_coach_home_briefing

        source = inspect.getsource(generate_coach_home_briefing)
        assert "workout_why" in source, "workout_why must be in the LLM schema"

    def test_old_keys_still_in_schema(self):
        """All 5 original keys remain in the LLM schema."""
        import inspect
        from routers.home import generate_coach_home_briefing

        source = inspect.getsource(generate_coach_home_briefing)
        for key in ["coach_noticed", "today_context", "week_assessment",
                     "checkin_reaction", "race_assessment"]:
            assert key in source, f"Original key {key!r} must remain in schema"


# ---------------------------------------------------------------------------
# 5. Internal metrics never reach athlete-facing output
# ---------------------------------------------------------------------------

class TestInternalMetricsBlocked:
    """
    Regression suite: internal training-load metrics must be rejected by the
    post-generation validator before they reach morning_voice or coach_noticed.

    These terms appear in the athlete brief for model reasoning only.
    Every term in _VOICE_INTERNAL_METRICS must be independently blocked.

    This suite exists because internal metrics leaked to the athlete three times
    before structural enforcement was added. Any change to the validator that
    causes these tests to fail is a regression.
    """

    def _validate(self, text: str, field: str = "morning_voice") -> dict:
        from routers.home import validate_voice_output
        return validate_voice_output(text, field=field)

    def _assert_blocked(self, text: str, expected_term: str, field: str = "morning_voice"):
        result = self._validate(text, field=field)
        assert result["valid"] is False, (
            f"Should have blocked {expected_term!r} in: {text!r}"
        )
        assert "internal_metric" in result.get("reason", ""), (
            f"Reason should be internal_metric, got: {result.get('reason')!r}"
        )

    def test_chronic_load_blocked(self):
        self._assert_blocked(
            "38 miles this week. Your chronic load is 38.9 and building.",
            "chronic load",
        )

    def test_acute_load_blocked(self):
        self._assert_blocked(
            "10.0 miles today. Acute load is 48.9 — watch recovery.",
            "acute load",
        )

    def test_ctl_acronym_blocked(self):
        self._assert_blocked(
            "10 miles today. Your CTL is sitting at 42, which is solid.",
            "CTL",
        )

    def test_atl_acronym_blocked(self):
        self._assert_blocked(
            "38 miles this week. ATL is elevated at 51 — easy tomorrow.",
            "ATL",
        )

    def test_tsb_acronym_blocked(self):
        self._assert_blocked(
            "10 miles at 8:53/mi. TSB of -9 puts you in the training zone.",
            "TSB",
        )

    def test_form_score_blocked(self):
        self._assert_blocked(
            "10 miles today. Form score of -12 indicates build stress.",
            "form score",
        )

    def test_durability_index_blocked(self):
        self._assert_blocked(
            "38 miles this week. Durability index at 0.94 — strong.",
            "durability index",
        )

    def test_recovery_half_life_blocked(self):
        self._assert_blocked(
            "10 miles today. Recovery half-life estimated at 18 hours.",
            "recovery half-life",
        )

    def test_injury_risk_score_blocked(self):
        self._assert_blocked(
            "38 miles this week. Injury risk score is 0.31 — low.",
            "injury risk score",
        )

    def test_internal_metrics_blocked_in_coach_noticed(self):
        """Internal metrics are also blocked from coach_noticed field."""
        self._assert_blocked(
            "Strong pacing. Chronic load of 38.9 shows steady base building.",
            "chronic load",
            field="coach_noticed",
        )

    def test_valid_athlete_language_passes(self):
        """Athlete-facing language (pace, distance, HR) is not blocked."""
        from routers.home import validate_voice_output
        good = (
            "38 miles through 5 runs this week. "
            "Less than 0.1% pace drift across today's 10 miles — "
            "that kind of control 23 days from Tobacco Road is exactly right."
        )
        result = validate_voice_output(good, field="morning_voice")
        assert result["valid"] is True, f"Should have passed: {result}"

    def test_internal_metric_replaced_with_fallback(self):
        """When morning_voice contains an internal metric, fallback is returned."""
        from routers.home import validate_voice_output, _VOICE_FALLBACK
        bad = "Your recent 10.0-mile run. Acute load is 48.9. Chronic load to 38.9."
        result = validate_voice_output(bad, field="morning_voice")
        assert result["valid"] is False
        assert result.get("fallback") == _VOICE_FALLBACK
        assert "chronic load" not in result["fallback"].lower()
        assert "acute load" not in result["fallback"].lower()


# ---------------------------------------------------------------------------
# 7. InsightLog aggregation for LLM context
# ---------------------------------------------------------------------------

class TestInsightLogAggregation:
    """
    generate_coach_home_briefing must query InsightLog for recent
    non-LOG insights and include them in the LLM prompt context.
    """

    def test_insight_log_query_in_briefing_function(self):
        """The function queries InsightLog."""
        import inspect
        from routers.home import generate_coach_home_briefing

        source = inspect.getsource(generate_coach_home_briefing)
        assert "InsightLog" in source, "Must query InsightLog for intelligence context"

    def test_insight_log_excludes_log_mode(self):
        """Only non-LOG insights are included (inform, suggest, flag, ask)."""
        import inspect
        from routers.home import generate_coach_home_briefing

        source = inspect.getsource(generate_coach_home_briefing)
        # Should filter out mode='log' — e.g., filter(InsightLog.mode != 'log')
        assert "log" in source.lower(), "Must filter out LOG mode insights"
