import json
from pathlib import Path

from services.coaching._eval import (
    REAL_COACH_DOMAINS,
    build_tier3_judge_payload,
    evaluate_tier3_judge_scores,
    summarize_tier3_domain_scores,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "coach_eval_cases.json"


def _cases():
    with FIXTURE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _strong_judge_scores(case):
    scores = {
        "tactical_correctness": 4,
        "baseline_utility": 4,
        "outcome_served": 4,
        "evidence_usefulness": 4,
    }
    if case.get("eval_schema_version") == "artifact7.v1":
        scores["voice_alignment"] = 4
    return scores


def test_tier3_judge_payloads_are_available_for_every_phase8_case():
    for case in _cases():
        payload = build_tier3_judge_payload(case, assistant_text=case["passing_answer"])

        assert payload["case_id"] == case["id"]
        assert payload["baseline_answer"]
        assert payload["baseline_comparison_rubric"]
        assert payload["expected_coaching_truths"]
        assert payload["retrieved_evidence_summary"]
        assert payload["coach_response"] == case["passing_answer"]


def test_tier3_scored_eval_accepts_strong_judge_scores():
    case = next(case for case in _cases() if case["id"] == "race_day_5k_execution")
    result = evaluate_tier3_judge_scores(
        case,
        {
            "tactical_correctness": 5,
            "baseline_utility": 4,
            "outcome_served": 5,
            "evidence_usefulness": 4,
        },
    )

    assert result.passed
    assert result.score == 4.5


def test_tier3_phase8_does_not_require_voice_alignment():
    case = next(case for case in _cases() if case["id"] == "race_day_5k_execution")
    result = evaluate_tier3_judge_scores(
        case,
        {
            "tactical_correctness": 5,
            "baseline_utility": 4,
            "outcome_served": 5,
            "evidence_usefulness": 4,
        },
    )

    assert result.passed
    assert "missing_judge_score:voice_alignment" not in result.failures


def test_tier3_artifact7_requires_voice_alignment():
    case = dict(next(case for case in _cases() if case["id"] == "race_day_5k_execution"))
    case["eval_schema_version"] = "artifact7.v1"
    result = evaluate_tier3_judge_scores(
        case,
        {
            "tactical_correctness": 5,
            "baseline_utility": 4,
            "outcome_served": 5,
            "evidence_usefulness": 4,
        },
    )

    assert not result.passed
    assert "missing_judge_score:voice_alignment" in result.failures


def test_tier3_scored_eval_rejects_answers_worse_than_baseline():
    case = next(case for case in _cases() if case["id"] == "nutrition_partial_day")
    result = evaluate_tier3_judge_scores(
        case,
        {
            "tactical_correctness": 4,
            "baseline_utility": 2,
            "outcome_served": 4,
            "evidence_usefulness": 4,
        },
    )

    assert not result.passed
    assert "judge_dimension_below_min:baseline_utility:2<3" in result.failures


def test_tier3_domain_summary_reports_per_domain_scores():
    cases = _cases()
    results = [
        evaluate_tier3_judge_scores(
            case,
            _strong_judge_scores(case),
        )
        for case in cases
    ]
    summary = summarize_tier3_domain_scores(results)

    assert summary["total_cases"] == len(cases)
    assert summary["failed_cases"] == 0
    assert set(summary["domains"]) == REAL_COACH_DOMAINS
    assert summary["domains"]["race_day"]["average_score"] == 4.0
    assert summary["domains"]["race_day"]["cases"] == 3
