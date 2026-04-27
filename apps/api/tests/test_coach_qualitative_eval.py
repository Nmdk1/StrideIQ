from services.coaching.qualitative_eval import (
    evaluate_case_qualitative_response,
    evaluate_qualitative_response,
)


def test_easy_run_failure_catches_overlong_numeric_data_dump():
    bad_response = (
        "Your easy runs have been drifting faster. Yesterday's 9.15-miler started "
        "at 8:44/mi and finished at 8:15/mi - a 5.6% negative split that took you "
        "from aerobic into moderate territory without a perceived effort shift "
        "(you logged it as 3/10). Same pattern on April 22 and April 19: strong "
        "finishes of 3.9% and 7.3%. The pace isn't the problem; the compression is. "
        "You're tightening the effort band on days that should expand it. With the "
        "Coke 10K five days out, the risk isn't that you'll ruin the race - it's "
        "that you're spending glycogen and neuromuscular freshness on runs that "
        "should be building fatigue resistance. At 57, that recovery cost lingers. "
        "One thing: cap the second half of every easy run at or slower than the "
        "first half. If you negative-split again this week, the effort prescription "
        "has failed. How do you want to enforce that - out-and-back route, watch "
        "alert, or run with someone slower?"
    )

    result = evaluate_qualitative_response(
        user_message="What is one thing I should pay attention to on easy runs this week?",
        assistant_text=bad_response,
        contract_type="quick_check",
        qualitative_contract={
            "max_words": 80,
            "max_athlete_numeric_anchors": 2,
            "max_followup_questions": 1,
            "irrelevant_context_terms": ["Coke 10K"],
        },
    )

    assert not result.passed
    assert any(failure.startswith("word_count_exceeds:") for failure in result.failures)
    assert any(failure.startswith("numeric_anchor_count_exceeds:") for failure in result.failures)
    assert "irrelevant_context_present:Coke 10K" in result.failures


def test_easy_run_passing_shape_is_short_and_coach_like():
    response = (
        "Watch whether the second half turns into a progression run. Keep the back "
        "half no faster than the front half; if you keep closing hard, the easy-day "
        "prescription is failing."
    )

    result = evaluate_qualitative_response(
        user_message="What is one thing I should pay attention to on easy runs this week?",
        assistant_text=response,
        contract_type="quick_check",
        qualitative_contract={
            "max_words": 80,
            "max_athlete_numeric_anchors": 2,
            "max_followup_questions": 1,
            "irrelevant_context_terms": ["Coke 10K", "calf"],
        },
    )

    assert result.passed, result.failures
    assert result.athlete_numeric_anchor_count == 0


def test_nutrition_relevance_failure_catches_unrelated_training_bleed():
    bad_response = (
        "You tolerate gels well - that simplifies things. The slosh tells me your "
        "gastric emptying rate is the bottleneck, not carbohydrate absorption. For "
        "a 10K at your effort level, you don't need much volume to get the benefit. "
        "Here's the adjustment: take one gel 10-15 minutes before the start with "
        "4-6 oz of water. One thing I'm surfacing: your April 18 medium-long run "
        "had pace drift and a 15.6% fade in the final quarter. Keep that contrast "
        "in mind Saturday: controlled early, let the back half find you."
    )

    result = evaluate_qualitative_response(
        user_message="I usually tolerate gels but get stomach slosh with too much fluid. Adjust that advice.",
        assistant_text=bad_response,
        domain="nutrition_fueling",
        qualitative_contract={
            "max_words": 120,
            "max_athlete_numeric_anchors": 2,
            "max_followup_questions": 1,
            "irrelevant_context_terms": ["April 18", "Saturday", "pace drift"],
        },
    )

    assert not result.passed
    assert "irrelevant_context_present:April 18" in result.failures
    assert "irrelevant_context_present:Saturday" in result.failures
    assert "irrelevant_context_present:pace drift" in result.failures


def test_nutrition_protocol_numbers_do_not_count_as_athlete_specific_anchors():
    response = (
        "Gel stays. Fluid drops. Take one gel 10-15 minutes before the start with "
        "4-6 oz water, then skip extra fluid unless heat changes the equation."
    )

    result = evaluate_qualitative_response(
        user_message="I usually tolerate gels but get stomach slosh with too much fluid. Adjust that advice.",
        assistant_text=response,
        domain="nutrition_fueling",
        qualitative_contract={
            "max_words": 80,
            "max_athlete_numeric_anchors": 0,
            "max_followup_questions": 0,
        },
    )

    assert result.passed, result.failures
    assert result.athlete_numeric_anchor_count == 0


def test_system_language_is_rejected_from_visible_coach_answers():
    result = evaluate_qualitative_response(
        user_message="Should tomorrow be more endurance or sharpening?",
        assistant_text=(
            "The athlete_facts packet says target_event is short road races, so "
            "the runtime tool should use that context block and calendar_context."
        ),
        contract_type="decision_point",
    )

    assert not result.passed
    assert "system_language_present:athlete_facts" in result.failures
    assert "system_language_present:packet" in result.failures
    assert "system_language_present:runtime" in result.failures
    assert "system_language_present:tool" in result.failures
    assert "system_language_present:calendar_context" in result.failures
    assert "system_language_present:context block" in result.failures


def test_visible_structural_labels_fail_but_implicit_structure_passes():
    labeled = evaluate_qualitative_response(
        user_message="Should I run easy, cross-train, or rest?",
        assistant_text=(
            "The read: the calf is irritated but not declared.\nDecision for today: "
            "cross-train and reassess tomorrow."
        ),
        contract_type="decision_point",
    )
    implicit = evaluate_qualitative_response(
        user_message="Should I run easy, cross-train, or rest?",
        assistant_text=(
            "Cross-train today. The calf is irritated but not declared, so buy one "
            "low-impact day and reassess tomorrow."
        ),
        contract_type="decision_point",
        qualitative_contract={"must_lead_with_decision": "mode_conditioned"},
    )

    assert not labeled.passed
    assert "visible_section_present:The read" in labeled.failures
    assert "visible_section_present:Decision for today" in labeled.failures
    assert implicit.passed, implicit.failures


def test_must_lead_with_decision_is_mode_conditioned():
    observe_and_ask = evaluate_qualitative_response(
        user_message="Why do easy runs feel harder lately?",
        assistant_text=(
            "Your breathing is the signal that catches my attention. The same "
            "clock pace may be sitting closer to threshold right now. What's it "
            "feel like from your end?"
        ),
        contract_type="general",
        mode="observe_and_ask",
        qualitative_contract={"must_lead_with_decision": "mode_conditioned"},
    )
    uncertainty = evaluate_qualitative_response(
        user_message="Do I usually rebound after bad workouts?",
        assistant_text=(
            "I checked the recent history and don't have enough similar groupings "
            "to make an honest call yet."
        ),
        contract_type="general",
        mode="uncertainty_disclosure",
        qualitative_contract={"must_lead_with_decision": "mode_conditioned"},
    )
    decision_point = evaluate_qualitative_response(
        user_message="Should I run easy or rest?",
        assistant_text="Your calf soreness is the part that matters. I would cross-train.",
        contract_type="decision_point",
        qualitative_contract={"must_lead_with_decision": "mode_conditioned"},
    )

    assert observe_and_ask.passed, observe_and_ask.failures
    assert uncertainty.passed, uncertainty.failures
    assert not decision_point.passed
    assert "does_not_lead_with_decision" in decision_point.failures


def test_repeated_unknown_phrase_fails_when_prior_answer_already_asked():
    prior_turns = [
        {
            "role": "assistant",
            "content": "I don't have your current pace zones. What paces are true right now?",
        }
    ]

    result = evaluate_qualitative_response(
        user_message="Given that, should tomorrow be endurance or sharpening?",
        assistant_text=(
            "Tomorrow should be easy plus strides. I don't have your current pace "
            "zones, so give me easy, threshold, and interval pace."
        ),
        contract_type="decision_point",
        prior_turns=prior_turns,
    )

    assert not result.passed
    assert (
        "repeated_unknown_phrase:i don't have your current pace zones"
        in result.failures
    )


def test_case_helper_uses_qualitative_contract():
    case = {
        "domain": "daily_training_adjustment",
        "user_message": "What is one thing I should pay attention to on easy runs this week?",
        "conversation_turns": [],
        "qualitative_contract": {
            "max_words": 80,
            "max_athlete_numeric_anchors": 2,
            "max_followup_questions": 1,
            "irrelevant_context_terms": ["Coke 10K"],
        },
        "passing_answer": (
            "Watch the second half. Keep it no faster than the first; if you keep "
            "closing hard, the easy-day prescription is failing."
        ),
    }

    result = evaluate_case_qualitative_response(case)

    assert result.passed, result.failures
