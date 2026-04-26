from services.coaching._conversation_contract import (
    ConversationContractType,
    classify_conversation_contract,
    enforce_conversation_contract_output,
    validate_conversation_contract_response,
)


def test_classifies_correction_dispute_for_wrong_data_claim():
    contract = classify_conversation_contract(
        "It's in my activity history, April 26 2025. You are wrong."
    )

    assert contract.contract_type == ConversationContractType.CORRECTION_DISPUTE
    assert "verify" in contract.required_behavior.lower()
    assert "athlete-stated" in contract.required_behavior.lower()


def test_classifies_quick_check_and_keeps_brief_requirement():
    contract = classify_conversation_contract(
        "Quick check — what should my next easy run focus on? Keep it brief."
    )

    assert contract.contract_type == ConversationContractType.QUICK_CHECK
    assert contract.max_words <= 80


def test_classifies_race_strategy():
    contract = classify_conversation_contract(
        "I'm debating strategy for tomorrow's 5K tune-up race."
    )

    assert contract.contract_type == ConversationContractType.RACE_STRATEGY
    assert "execution" in contract.outcome_target.lower()


def test_classifies_same_day_race_as_race_day():
    contract = classify_conversation_contract(
        "I have a 5K this morning and need the execution plan."
    )

    assert contract.contract_type == ConversationContractType.RACE_DAY
    assert "today" in contract.outcome_target.lower()


def test_bicarb_without_same_day_context_is_decision_not_full_race_day():
    contract = classify_conversation_contract(
        "Should I take Maurten bicarb before my race?"
    )

    assert contract.contract_type == ConversationContractType.DECISION_POINT


def test_same_day_race_context_does_not_promote_unrelated_domains():
    context = [
        {
            "role": "user",
            "content": "I have a 5K this morning and I am going out at 5:50 pace.",
        },
        {
            "role": "assistant",
            "content": "Timeline: race-day execution plan. Warmup: jog and strides.",
        },
    ]

    nutrition = classify_conversation_contract(
        "I logged 1,100 calories so far and have a run later. Am I underfueling?",
        conversation_context=context,
    )
    recovery = classify_conversation_contract(
        "I slept 5.5 hours but feel fine. Should I run today?",
        conversation_context=context,
    )
    between_plan = classify_conversation_contract(
        "I'm between plans and don't know what to do this week. What should I do?",
        conversation_context=context,
    )

    assert nutrition.contract_type == ConversationContractType.DECISION_POINT
    assert recovery.contract_type == ConversationContractType.DECISION_POINT
    assert between_plan.contract_type == ConversationContractType.DECISION_POINT


def test_same_day_race_context_still_promotes_true_race_day_followup():
    context = [
        {
            "role": "user",
            "content": "I have a 5K this morning and I am going out at 5:50 pace.",
        }
    ]

    contract = classify_conversation_contract(
        "How should I handle packet pickup and warmup?",
        conversation_context=context,
    )

    assert contract.contract_type == ConversationContractType.RACE_DAY


def test_5k_tactical_correction_beats_race_day_followup():
    contract = classify_conversation_contract(
        "That's not how 5Ks are raced at the sharp end.",
        conversation_context=[
            {
                "role": "user",
                "content": "I have a 5K this morning and I am going out at 5:50 pace.",
            }
        ],
    )

    assert contract.contract_type == ConversationContractType.CORRECTION_DISPUTE


def test_race_day_contract_requires_execution_packet():
    user_message = "I have a 5K this morning and I'm taking bicarb."

    invalid, reason = validate_conversation_contract_response(
        user_message,
        "You are fit enough. Open controlled and trust your training.",
    )
    valid, ok_reason = validate_conversation_contract_response(
        user_message,
        (
            "Timeline: take bicarb after arrival, then packet pickup, warmup, and start. "
            "Warmup: jog 12 minutes, drills, then 4 strides. "
            "Mile 1: controlled 7/10 effort. Mile 2: press. Mile 3: commit. "
            "Cue: tall cadence and relaxed shoulders."
        ),
    )

    assert invalid is False
    assert reason == "race_day_missing_execution_packet"
    assert valid is True
    assert ok_reason == "ok"


def test_quick_check_rejects_and_trims_essay_response():
    user_message = "Quick check — keep it brief: should I run easy today?"
    contract = classify_conversation_contract(user_message)
    long_response = " ".join(["This is extra analysis."] * 40)

    valid, reason = validate_conversation_contract_response(user_message, long_response)
    trimmed = enforce_conversation_contract_output(user_message, long_response)

    assert valid is False
    assert reason == "quick_check_too_long"
    assert len(trimmed.split()) <= contract.max_words


def test_decision_point_requires_tradeoff_and_default_recommendation():
    user_message = "Should I postpone threshold tomorrow?"

    invalid, reason = validate_conversation_contract_response(
        user_message,
        "You have been training a lot lately, so think about how you feel.",
    )
    valid, ok_reason = validate_conversation_contract_response(
        user_message,
        "Decision: postpone threshold. Tradeoff: you preserve adaptation but lose one sharpness stimulus. Default: move it 24 hours.",
    )

    assert invalid is False
    assert reason == "decision_point_missing_frame"
    assert valid is True
    assert ok_reason == "ok"


def test_correction_dispute_requires_verification_language():
    user_message = "You are wrong, that race is in my activity history."

    invalid, reason = validate_conversation_contract_response(
        user_message,
        "I do not have that race, so let's move on.",
    )
    valid, ok_reason = validate_conversation_contract_response(
        user_message,
        'I searched activity history for "race" and found no match, so I cannot verify it from stored data yet.',
    )

    assert invalid is False
    assert reason == "correction_dispute_missing_verification"
    assert valid is True
    assert ok_reason == "ok"


def test_emotional_load_rejects_prying_when_boundary_is_food():
    user_message = "I'm stressed and want food, but I don't want to talk about life stuff."

    invalid, reason = validate_conversation_contract_response(
        user_message,
        "What is going on in your life that is making you stressed?",
    )
    valid, ok_reason = validate_conversation_contract_response(
        user_message,
        "That is enough context. Next step: eat a real meal with carbs and protein, then reassess the run in an hour.",
    )

    assert invalid is False
    assert reason == "emotional_load_prying"
    assert valid is True
    assert ok_reason == "ok"


def test_race_strategy_requires_execution_shape():
    user_message = "Give me a 5K race strategy for tomorrow."

    invalid, reason = validate_conversation_contract_response(
        user_message,
        "You are fit and should believe in yourself.",
    )
    valid, ok_reason = validate_conversation_contract_response(
        user_message,
        (
            "Objective: race assertively. Primary limiter: continuous pressure. "
            "False limiter: do not treat old injury-compromised anchors as current fitness. "
            "Pacing shape: open controlled, hold effort through mile 2, then close aggressively. "
            "Course risk: late rise. Execution cues: relax shoulders and keep cadence tall. "
            "Success beyond time: commit to the middle mile. Post-race learning: compare effort fade to splits."
        ),
    )

    assert invalid is False
    assert reason == "race_strategy_missing_packet"
    assert valid is True
    assert ok_reason == "ok"
