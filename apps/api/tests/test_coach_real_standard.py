import json
from pathlib import Path

import pytest

from services.coaching._eval import (
    CASE_TYPES,
    REAL_COACH_DOMAINS,
    build_tier3_judge_payload,
    evaluate_real_coach_response,
    summarize_real_coach_results,
    validate_real_coach_case,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "coach_eval_cases.json"


@pytest.fixture(scope="module")
def coach_eval_cases():
    with FIXTURE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _artifact7_case(coach_eval_cases):
    case = dict(coach_eval_cases[0])
    case.update(
        {
            "eval_schema_version": "artifact7.v1",
            "baseline_voice": "green",
            "baseline_citation": {
                "doc": "GREEN_COACHING_PHILOSOPHY_EXPANDED_2026-04-10.md",
                "section": "1. Plans Written in Pencil",
            },
            "artifact5_mode": "engage_and_reason",
            "source_replay_type": "founder_curated",
        }
    )
    return case


def test_phase8_case_bank_covers_all_real_coach_domains(coach_eval_cases):
    assert len(coach_eval_cases) >= len(REAL_COACH_DOMAINS) * 3

    coverage = {
        domain: {case["case_type"] for case in coach_eval_cases if case["domain"] == domain}
        for domain in REAL_COACH_DOMAINS
    }

    assert set(coverage) == REAL_COACH_DOMAINS
    for domain, case_types in coverage.items():
        assert case_types == CASE_TYPES, domain


def test_phase8_case_bank_has_required_structure(coach_eval_cases):
    case_ids = set()
    for case in coach_eval_cases:
        assert case["id"] not in case_ids
        case_ids.add(case["id"])

        failures = validate_real_coach_case(case)
        assert not failures, f"{case['id']}: {failures}"

        assert case["baseline_answer"]
        assert case["expected_coaching_truths"]
        assert case["retrieved_evidence_expected"]
        assert case["baseline_comparison_rubric"]
        assert case["failure_severity"] in {"fatal", "major", "minor"}


def test_phase8_missing_schema_version_defaults_to_phase8(coach_eval_cases):
    case = dict(coach_eval_cases[0])

    assert "eval_schema_version" not in case
    assert validate_real_coach_case(case) == ()


def test_artifact7_case_validates_with_voice_citation_and_mode(coach_eval_cases):
    case = _artifact7_case(coach_eval_cases)

    assert validate_real_coach_case(case) == ()


@pytest.mark.parametrize(
    ("field", "expected_failure"),
    [
        ("baseline_voice", "missing_field:baseline_voice"),
        ("baseline_citation", "missing_field:baseline_citation"),
        ("artifact5_mode", "missing_field:artifact5_mode"),
        ("source_replay_type", "missing_field:source_replay_type"),
    ],
)
def test_artifact7_missing_required_fields_fail(coach_eval_cases, field, expected_failure):
    case = _artifact7_case(coach_eval_cases)
    case.pop(field)

    failures = validate_real_coach_case(case)

    assert expected_failure in failures


@pytest.mark.parametrize(
    ("voice", "expected_failure"),
    [
        ("eyestone", "blocked_voice:eyestone"),
        ("mcmillan", "blocked_voice:mcmillan"),
    ],
)
def test_artifact7_blocked_voices_fail_validation(coach_eval_cases, voice, expected_failure):
    case = _artifact7_case(coach_eval_cases)
    case["baseline_voice"] = voice

    failures = validate_real_coach_case(case)

    assert expected_failure in failures


def test_artifact7_unknown_voice_fails_validation(coach_eval_cases):
    case = _artifact7_case(coach_eval_cases)
    case["baseline_voice"] = "anonymous"

    failures = validate_real_coach_case(case)

    assert "invalid_voice:anonymous" in failures


def test_artifact7_missing_reference_doc_fails_validation(coach_eval_cases):
    case = _artifact7_case(coach_eval_cases)
    case["baseline_citation"] = {
        "doc": "MISSING_COACH_REFERENCE.md",
        "section": "Plans Written in Pencil",
    }

    failures = validate_real_coach_case(case)

    assert "missing_reference_doc:MISSING_COACH_REFERENCE.md" in failures


def test_artifact7_missing_reference_section_fails_validation(coach_eval_cases):
    case = _artifact7_case(coach_eval_cases)
    case["baseline_citation"] = {
        "doc": "GREEN_COACHING_PHILOSOPHY_EXPANDED_2026-04-10.md",
        "section": "No Such Section",
    }

    failures = validate_real_coach_case(case)

    assert "missing_reference_section:No Such Section" in failures


def test_artifact7_invalid_mode_fails_validation(coach_eval_cases):
    case = _artifact7_case(coach_eval_cases)
    case["artifact5_mode"] = "vibes_only"

    failures = validate_real_coach_case(case)

    assert "invalid_artifact5_mode:vibes_only" in failures


def test_artifact7_invalid_source_replay_type_fails_validation(coach_eval_cases):
    case = _artifact7_case(coach_eval_cases)
    case["source_replay_type"] = "memory"

    failures = validate_real_coach_case(case)

    assert "invalid_source_replay_type:memory" in failures


def test_unknown_eval_schema_version_fails_validation(coach_eval_cases):
    case = dict(coach_eval_cases[0])
    case["eval_schema_version"] = "future.v1"

    failures = validate_real_coach_case(case)

    assert "unknown_schema_version:future.v1" in failures


def test_phase8_includes_2026_04_25_5k_dispute_trajectory(coach_eval_cases):
    case = next(case for case in coach_eval_cases if case["id"] == "correction_5k_positive_split")

    assert len(case["conversation_turns"]) >= 3
    assert case["conversation_turns"][1]["role"] == "coach"
    assert "negative split" in case["conversation_turns"][1]["content"]
    assert "positive split" in case["passing_answer"]


@pytest.mark.parametrize("case_id", [case["id"] for case in json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))])
def test_phase8_passing_answers_meet_deterministic_truths(coach_eval_cases, case_id):
    case = next(item for item in coach_eval_cases if item["id"] == case_id)
    result = evaluate_real_coach_response(case)

    assert result.passed, result.failures


@pytest.mark.parametrize("case_id", [case["id"] for case in json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))])
def test_phase8_failing_answers_fail_deterministic_truths(coach_eval_cases, case_id):
    case = next(item for item in coach_eval_cases if item["id"] == case_id)
    result = evaluate_real_coach_response(
        case,
        assistant_text=case["failing_answer"],
        tools_called=[],
        retrieved_evidence=[],
    )

    assert not result.passed
    assert result.failures


def test_phase8_missing_tool_blocks_data_claiming(coach_eval_cases):
    case = next(case for case in coach_eval_cases if case["id"] == "race_day_5k_execution")
    result = evaluate_real_coach_response(case, tools_called=[])

    assert not result.passed
    assert "missing_required_tool:get_race_strategy_packet" in result.failures


def test_phase8_missing_retrieved_evidence_blocks_proxy_green(coach_eval_cases):
    case = next(case for case in coach_eval_cases if case["id"] == "workout_stale_zones")
    result = evaluate_real_coach_response(case, retrieved_evidence=[])

    assert not result.passed
    assert "missing_retrieved_evidence_tool:get_training_paces" in result.failures
    assert "missing_retrieved_evidence_tool:search_activities" in result.failures


def test_phase8_tier3_payload_contains_judge_rubric_not_system_prompt(coach_eval_cases):
    case = next(case for case in coach_eval_cases if case["id"] == "nutrition_partial_day")
    payload = build_tier3_judge_payload(case, assistant_text=case["passing_answer"])

    assert payload["case_id"] == "nutrition_partial_day"
    assert payload["baseline_answer"] == case["baseline_answer"]
    assert payload["expected_coaching_truths"] == case["expected_coaching_truths"]
    assert payload["baseline_comparison_rubric"] == case["baseline_comparison_rubric"]
    assert "system_prompt" not in payload
    assert "Do not reward contract shape by itself" in payload["scoring_instruction"]


def test_phase8_summary_reports_per_domain_scores(coach_eval_cases):
    results = [evaluate_real_coach_response(case) for case in coach_eval_cases]
    summary = summarize_real_coach_results(results)

    assert summary["total"] == len(coach_eval_cases)
    assert summary["failed"] == 0
    assert set(summary["domains"]) == REAL_COACH_DOMAINS
    assert summary["domains"]["race_day"]["passed"] == 3
