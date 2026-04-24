import json
from pathlib import Path

import pytest

from services.coaching._value_eval import DIMENSIONS, evaluate_coach_value_response


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "coach_value_cases.json"


@pytest.fixture(scope="module")
def coach_value_cases():
    with FIXTURE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _case_by_id(cases, case_id):
    return next(case for case in cases if case["id"] == case_id)


def test_fixture_covers_phase5_dimensions(coach_value_cases):
    covered = set()
    case_ids = set()
    for case in coach_value_cases:
        case_ids.add(case["id"])
        covered.update(case.get("required_dimensions") or [])

    assert {
        "older_activity_correction",
        "nutrition_total_additive",
        "stress_food_boundary",
        "aggressive_5k_strategy",
        "social_run_efficiency_context",
        "athlete_decides_training_choice",
    }.issubset(case_ids)
    assert DIMENSIONS.issubset(covered)


@pytest.mark.parametrize("case_id", [
    "older_activity_correction",
    "nutrition_total_additive",
    "stress_food_boundary",
    "aggressive_5k_strategy",
    "social_run_efficiency_context",
    "athlete_decides_training_choice",
])
def test_good_value_cases_pass(coach_value_cases, case_id):
    case = _case_by_id(coach_value_cases, case_id)
    result = evaluate_coach_value_response(case)

    assert result.passed, result.failures
    assert result.score >= case["min_score"]
    assert set(case["required_dimensions"]).issubset(result.passed_dimensions)


@pytest.mark.parametrize("case_id", [
    "older_activity_correction",
    "nutrition_total_additive",
    "stress_food_boundary",
    "aggressive_5k_strategy",
    "social_run_efficiency_context",
    "athlete_decides_training_choice",
])
def test_bad_value_cases_fail(coach_value_cases, case_id):
    case = _case_by_id(coach_value_cases, case_id)
    result = evaluate_coach_value_response(
        case,
        assistant_text=case["bad_response"],
        tools_called=[],
    )

    assert not result.passed
    assert result.failures


def test_missing_required_tool_fails_even_when_text_sounds_good(coach_value_cases):
    case = _case_by_id(coach_value_cases, "aggressive_5k_strategy")
    result = evaluate_coach_value_response(case, tools_called=[])

    assert not result.passed
    assert "missing_required_tool:get_race_strategy_packet" in result.failures


def test_forbidden_claim_blocks_otherwise_good_answer(coach_value_cases):
    case = _case_by_id(coach_value_cases, "nutrition_total_additive")
    contaminated = case["assistant_response"] + " Earlier I said 1,190 calories."
    result = evaluate_coach_value_response(case, assistant_text=contaminated)

    assert not result.passed
    assert "forbidden_phrase_present:1,190" in result.failures


def test_conversation_contract_failure_is_reported(coach_value_cases):
    case = _case_by_id(coach_value_cases, "stress_food_boundary")
    result = evaluate_coach_value_response(
        case,
        assistant_text="What is going on in your life that is making you stressed?",
    )

    assert not result.passed
    assert "conversation_contract:emotional_load_prying" in result.failures
