from services.coaching._conversation_contract import (
    ConversationContractType,
    classify_conversation_contract,
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
