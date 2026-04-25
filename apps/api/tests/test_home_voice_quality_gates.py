"""
Home Voice Quality Gates — RED tests against the exact failure shown
to the founder in production on 2026-04-18.

Failure text (verbatim from screenshot, top paragraph / morning_voice):

    Your data shows a pattern worth discussing: your efficiency trend
    declines based on recovery ratio, observed 3 times with a 3-day lag
    before the effect appears. What do you think is driving this?
    Separately, your easy pace before 7 AM has been consistently slower
    across 18 observations — there's a threshold around 7 AM that you've
    respected well. This morning's 4x1 mile intervals at threshold pace
    are scheduled; yesterday's 8.0 miles at 8:46/mi with 177ft gain sets
    up the legs without residual fatigue. Tomorrow brings 14 miles at
    8:05/mi, so today's session is about hitting prescribed paces and
    beginning fueling for the back-to-back load.

Five concrete defects to gate against:

  1. Asks the athlete a literal question ("What do you think is driving
     this?"). Coaches don't ask the user to diagnose themselves.
  2. Surfaces a weak finding (N=3, 3-day lag) as if it's signal.
  3. "Separately, ..." — two unrelated topics in one paragraph,
     violating the system-prompt ONE-NEW-THING rule.
  4. Meta-preamble ("Your data shows a pattern worth discussing") —
     talking about having an observation instead of stating it.
  5. Length: 5 sentences when contract is 2-3.

These tests are RED until the post-generation validator and the
fingerprint context emerging-pattern path are tightened. They MUST
remain green afterwards. They MUST also leave the existing 80% of
good briefings passing — see the regression suite at the bottom.
"""

import pytest


# Verbatim text from the production screenshot. Do not edit.
BAD_MORNING_VOICE = (
    "Your data shows a pattern worth discussing: your efficiency trend "
    "declines based on recovery ratio, observed 3 times with a 3-day lag "
    "before the effect appears. What do you think is driving this? "
    "Separately, your easy pace before 7 AM has been consistently slower "
    "across 18 observations — there's a threshold around 7 AM that "
    "you've respected well. This morning's 4x1 mile intervals at "
    "threshold pace are scheduled; yesterday's 8.0 miles at 8:46/mi "
    "with 177ft gain sets up the legs without residual fatigue. "
    "Tomorrow brings 14 miles at 8:05/mi, so today's session is about "
    "hitting prescribed paces and beginning fueling for the back-to-back "
    "load."
)


# Verbatim text from the production screenshot, lower paragraph
# (coach_noticed). This is a *good* output and must continue to pass.
GOOD_COACH_NOTICED = (
    "Your easy pace degrades measurably with elevation gain — this has "
    "held across 41 of your runs. Yesterday's 8.0 miler at 8:46/mi "
    "carried 177ft of gain in 85°F heat, which explains why it landed "
    "55 seconds/mi slower than your easy ceiling despite modest effort. "
    "The pattern is consistent: more hills, slower easy pace, regardless "
    "of intent."
)


def _validate():
    from routers.home import validate_voice_output
    return validate_voice_output


# ---------------------------------------------------------------------------
# Failure-mode tests — each is a single defect from the bad screenshot.
# ---------------------------------------------------------------------------


class TestInterrogativeBan:
    """morning_voice and coach_noticed must not contain a literal question."""

    def test_question_in_morning_voice_blocked(self):
        validate = _validate()
        text = (
            "Your easy run yesterday was 8.0 miles at 8:46/mi. "
            "What do you think is driving this?"
        )
        result = validate(text, field="morning_voice")
        assert result["valid"] is False, "Question mark should be rejected"
        assert "interrogative" in result.get("reason", "")

    def test_question_in_coach_noticed_blocked(self):
        validate = _validate()
        text = (
            "Your easy pace degrades with elevation across 41 runs. "
            "Could that be the cause?"
        )
        result = validate(text, field="coach_noticed")
        assert result["valid"] is False
        assert "interrogative" in result.get("reason", "")

    def test_workout_why_may_contain_question_mark(self):
        # workout_why is conceptual; we don't gate questions there.
        # If a coach writes "Why this matters?" rhetorically it's fine.
        # This test pins the scope of the new gate.
        validate = _validate()
        text = "Active recovery keeps blood flowing after yesterday's 10-mile effort."
        result = validate(text, field="workout_why")
        assert result["valid"] is True


class TestMultiTopicTransitionBan:
    """morning_voice may not stitch two findings together with a transition."""

    @pytest.mark.parametrize("transition", [
        "Separately,",
        "separately,",
        "Additionally,",
        "Also,",
        "Meanwhile,",
        "On another note,",
        "Beyond that,",
    ])
    def test_transition_phrase_blocked(self, transition):
        validate = _validate()
        text = (
            f"You ran 8.0 miles at 8:46/mi yesterday. {transition} your "
            f"easy runs before 7 AM are slower across 18 observations."
        )
        result = validate(text, field="morning_voice")
        assert result["valid"] is False, (
            f"Transition phrase {transition!r} should be rejected"
        )
        assert "multi_topic" in result.get("reason", "")


class TestMetaPreambleBan:
    """morning_voice may not preface with 'Your data shows ...' style filler."""

    @pytest.mark.parametrize("preamble", [
        "Your data shows a pattern worth discussing:",
        "Your data shows",
        "Worth discussing:",
        "I've noticed a pattern in your data.",
        "Looking at your data,",
        "The data suggests",
        "There's a pattern worth noting.",
    ])
    def test_meta_preamble_blocked(self, preamble):
        validate = _validate()
        text = (
            f"{preamble} You ran 8.0 miles at 8:46/mi with 177ft of "
            f"gain in 85°F heat."
        )
        result = validate(text, field="morning_voice")
        assert result["valid"] is False, (
            f"Meta-preamble {preamble!r} should be rejected"
        )
        assert "meta_preamble" in result.get("reason", "")


class TestSentenceCap:
    """morning_voice is contracted to 1 paragraph, 2-3 sentences."""

    def test_three_sentences_passes(self):
        validate = _validate()
        text = (
            "You ran 8.0 miles at 8:46/mi yesterday with 177ft of gain. "
            "Heat-adjusted that lands close to your easy ceiling. "
            "Tomorrow's 4x1 mile threshold session is the priority."
        )
        result = validate(text, field="morning_voice")
        assert result["valid"] is True

    def test_five_sentences_truncated_or_blocked(self):
        # The exact bad output minus the question / transition / preamble
        # is still 5 sentences and must be capped. Either outcome is OK:
        #   - valid=True with truncated_text (preferred, preserves content)
        #   - valid=False with sentence_cap reason (fallback)
        validate = _validate()
        text = (
            "You ran 8.0 miles at 8:46/mi with 177ft of gain. "
            "Pace landed 55 seconds/mi slower than your easy ceiling. "
            "The heat was 85°F. "
            "Tomorrow's 4x1 mile threshold session is scheduled. "
            "Focus today is fueling for the back-to-back load."
        )
        result = validate(text, field="morning_voice")
        if result.get("valid"):
            # Truncation path — must have produced a shortened text that
            # is itself within the cap.
            truncated = result.get("truncated_text") or ""
            assert truncated, "Valid result must carry truncated_text"
            from routers.home import _split_sentences, _VOICE_SENTENCE_CAP
            assert len(_split_sentences(truncated)) <= _VOICE_SENTENCE_CAP
        else:
            assert "sentence_cap" in result.get("reason", "")


# ---------------------------------------------------------------------------
# End-to-end against the actual bad screenshot text.
# ---------------------------------------------------------------------------


class TestFullBadOutputIsRejected:
    """The exact string the founder saw must be rejected."""

    def test_bad_morning_voice_rejected(self):
        validate = _validate()
        result = validate(BAD_MORNING_VOICE, field="morning_voice")
        assert result["valid"] is False, (
            "The verbatim bad morning_voice must not pass validation"
        )
        # The reason should be one of the new gates we added (any of them
        # firing first is fine — they all describe a real defect).
        reason = result.get("reason", "")
        assert any(g in reason for g in (
            "interrogative", "multi_topic", "meta_preamble", "sentence_cap",
        )), f"Expected one of the new gates to fire, got: {reason!r}"


class TestRaceWeekLoadSafety:
    """Race-week briefing must not turn normal load into readiness sabotage."""

    def test_cached_race_week_active_calorie_drag_claim_is_cleared(self):
        from routers.home import _normalize_cached_briefing_payload

        payload = {
            "coach_noticed": (
                "Your active calorie burn negatively affects running efficiency "
                "with a 5-day lag — I've seen this consistently across 30 of "
                "your runs. That means the high calorie output from your "
                "13.8-mile long run 6 days ago and your Tuesday 8-miler at "
                "7:50/mi could still be suppressing your efficiency today."
            ),
            "morning_voice": (
                "You're racing the Tuscaloosa Mayors Cup 5K this morning — "
                "3.1 miles. Your freshness is sitting where it has been for "
                "your best performances."
            ),
            "race_assessment": (
                "Today's 5K effort fits well as a sharpener without draining you."
            ),
        }

        sanitized = _normalize_cached_briefing_payload(
            payload, garmin_sleep_h=None, checkin_sleep_h=None
        )

        assert sanitized["coach_noticed"] is None

    def test_race_week_active_calorie_drag_claim_is_cleared_before_cache(self):
        from routers.home import _apply_race_week_coach_noticed_safety

        result = {
            "coach_noticed": (
                "Your active calorie burn is dragging down your running "
                "efficiency with a 5-day lag."
            ),
        }

        sanitized = _apply_race_week_coach_noticed_safety(
            result, race_data={"days_remaining": 7}
        )

        assert sanitized["coach_noticed"] is None

    def test_positive_race_week_observation_is_not_cleared(self):
        from routers.home import _apply_race_week_coach_noticed_safety

        result = {
            "coach_noticed": (
                "Your pacing control has held steady across the taper, with "
                "yesterday's 2.2-mile shakeout staying relaxed at HR 132."
            ),
        }

        sanitized = _apply_race_week_coach_noticed_safety(
            result, race_data={"days_remaining": 7}
        )

        assert sanitized["coach_noticed"] == result["coach_noticed"]


# ---------------------------------------------------------------------------
# Regression: don't destroy the 80% of good briefings.
# ---------------------------------------------------------------------------


class TestGoodOutputsStillPass:
    """The good orange coach_noticed in the screenshot must stay valid.

    Plus a sample of strong morning_voice shapes seen in production.
    """

    def test_good_coach_noticed_passes(self):
        validate = _validate()
        result = validate(GOOD_COACH_NOTICED, field="coach_noticed")
        assert result["valid"] is True, (
            f"The verbatim good coach_noticed must continue to pass. "
            f"Got: {result}"
        )

    def test_strong_morning_voice_passes(self):
        validate = _validate()
        text = (
            "8.0 miles at 8:46/mi this morning with 177ft of gain in 85°F "
            "heat — heat-adjusted that's right on your easy ceiling. "
            "This week is back-loaded with tomorrow's 4x1 mile threshold "
            "session and a 14-miler over the weekend."
        )
        result = validate(text, field="morning_voice")
        assert result["valid"] is True, (
            f"Strong, specific morning_voice must pass. Got: {result}"
        )

    def test_short_morning_voice_passes(self):
        validate = _validate()
        text = (
            "Recovery day with a 3.5 mi shake-out at 9:30/mi. "
            "Tomorrow's 4x1 mile threshold session is the priority — "
            "focus tonight on sleep and fueling."
        )
        result = validate(text, field="morning_voice")
        assert result["valid"] is True

    def test_existing_good_simple_voice_passes(self):
        # From the existing test suite — keep this passing.
        validate = _validate()
        text = (
            "48 miles across 6 runs this week. HR averaged 142 bpm — "
            "consistent with your build phase targets."
        )
        result = validate(text, field="morning_voice")
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# Strip-and-recover: when a single bad sentence is removed, what remains
# should re-validate successfully whenever possible. Better than blanket
# fallback.
# ---------------------------------------------------------------------------


class TestStripAndRecover:
    """When the offending content is one sentence, strip it and keep the rest."""

    def test_strip_question_keeps_rest(self):
        from routers.home import _strip_disallowed_sentences  # NEW helper
        text = (
            "You ran 8.0 miles at 8:46/mi yesterday. "
            "What do you think is driving this? "
            "Tomorrow's 4x1 mile threshold session is scheduled."
        )
        out = _strip_disallowed_sentences(text)
        assert out["removed"] is True
        assert "?" not in out["text"]
        assert "8:46" in out["text"]
        assert "threshold session" in out["text"]

    def test_strip_meta_preamble_sentence_keeps_rest(self):
        from routers.home import _strip_disallowed_sentences
        text = (
            "Your data shows a pattern worth discussing: efficiency "
            "trend declines. "
            "You ran 8.0 miles at 8:46/mi with 177ft of gain."
        )
        out = _strip_disallowed_sentences(text)
        assert out["removed"] is True
        assert "your data shows" not in out["text"].lower()
        assert "8:46" in out["text"]

    def test_strip_transition_sentence_keeps_rest(self):
        from routers.home import _strip_disallowed_sentences
        text = (
            "You ran 8.0 miles at 8:46/mi yesterday. "
            "Separately, your easy runs before 7 AM are slower across "
            "18 observations."
        )
        out = _strip_disallowed_sentences(text)
        assert out["removed"] is True
        assert "separately" not in out["text"].lower()
        assert "8:46" in out["text"]

    def test_nothing_to_strip_returns_unchanged(self):
        from routers.home import _strip_disallowed_sentences
        text = "You ran 8.0 miles at 8:46/mi with 177ft of gain in 85°F heat."
        out = _strip_disallowed_sentences(text)
        assert out["removed"] is False
        assert out["text"].strip() == text.strip()


# ---------------------------------------------------------------------------
# Fingerprint context: morning-voice lane must not request an interrogative.
# ---------------------------------------------------------------------------


class TestFingerprintEmergingQuestionGate:
    """build_fingerprint_prompt_section must support suppressing the
    'Suggested question' / 'ASK ABOUT THIS FIRST' framing for the
    morning_voice lane. Chat coach lane keeps it.
    """

    def test_function_accepts_include_emerging_question_kwarg(self):
        # The signature must support the new flag — calling it should not
        # raise TypeError.
        from services.fingerprint_context import build_fingerprint_prompt_section
        import inspect

        sig = inspect.signature(build_fingerprint_prompt_section)
        assert "include_emerging_question" in sig.parameters, (
            "build_fingerprint_prompt_section must accept "
            "include_emerging_question to gate the morning_voice lane"
        )

    def test_morning_voice_caller_passes_false(self):
        # The morning_voice fingerprint_summary lane in
        # generate_coach_home_briefing must call with
        # include_emerging_question=False.
        import inspect
        from routers.home import generate_coach_home_briefing

        source = inspect.getsource(generate_coach_home_briefing)
        assert "include_emerging_question=False" in source, (
            "generate_coach_home_briefing must suppress the emerging "
            "question for the morning_voice lane"
        )
