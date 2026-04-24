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
