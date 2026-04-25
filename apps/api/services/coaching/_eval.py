from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


REAL_COACH_DOMAINS = {
    "daily_training_adjustment",
    "workout_execution",
    "nutrition_fueling",
    "recovery_sleep_stress",
    "between_plan_maintenance",
    "race_planning",
    "race_day",
    "post_run_interpretation",
    "correction_dispute",
    "emotional_frustrated_athlete",
    "injury_pain_triage",
}

CASE_TYPES = {"straightforward", "adversarial", "edge"}
OUTCOME_DIMENSIONS = {
    "clearer",
    "steadier",
    "sharper",
    "safer",
    "better_fueled",
    "better_calibrated",
    "better_execution",
    "better_informed",
}
FAILURE_SEVERITIES = {"fatal", "major", "minor"}

REQUIRED_CASE_FIELDS = {
    "id",
    "domain",
    "case_type",
    "situation",
    "conversation_turns",
    "user_message",
    "required_context",
    "expected_coaching_truths",
    "retrieved_evidence_expected",
    "bad_coaching_patterns",
    "excellent_answer_traits",
    "baseline_answer",
    "baseline_comparison_rubric",
    "must_not",
    "tools_required_if_data_claiming",
    "outcome_dimension",
    "failure_severity",
    "passing_answer",
    "failing_answer",
}


@dataclass(frozen=True)
class RealCoachEvalResult:
    case_id: str
    domain: str
    case_type: str
    passed: bool
    failures: tuple[str, ...]
    severity: str


@dataclass(frozen=True)
class Tier3JudgeResult:
    case_id: str
    domain: str
    passed: bool
    score: float
    failures: tuple[str, ...]


def load_real_coach_cases(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("coach eval fixture must be a list of cases")
    return data


def _lower(text: str) -> str:
    return (text or "").lower()


def _spec_present(text: str, spec: Any) -> bool:
    if isinstance(spec, str):
        return spec.lower() in _lower(text)
    if not isinstance(spec, Mapping):
        return False
    phrase = spec.get("phrase")
    if phrase:
        return str(phrase).lower() in _lower(text)
    pattern = spec.get("pattern")
    if pattern:
        return re.search(str(pattern), text or "", flags=re.IGNORECASE | re.MULTILINE) is not None
    return False


def _contains_any(text: str, phrases: Sequence[str]) -> bool:
    return any(str(phrase).lower() in _lower(text) for phrase in phrases)


def _contains_all(text: str, phrases: Sequence[str]) -> bool:
    return all(str(phrase).lower() in _lower(text) for phrase in phrases)


def validate_real_coach_case(case: Mapping[str, Any]) -> tuple[str, ...]:
    failures: list[str] = []
    missing = REQUIRED_CASE_FIELDS - set(case.keys())
    for field in sorted(missing):
        failures.append(f"missing_field:{field}")

    domain = str(case.get("domain") or "")
    if domain not in REAL_COACH_DOMAINS:
        failures.append(f"invalid_domain:{domain}")

    case_type = str(case.get("case_type") or "")
    if case_type not in CASE_TYPES:
        failures.append(f"invalid_case_type:{case_type}")

    outcome = str(case.get("outcome_dimension") or "")
    if outcome not in OUTCOME_DIMENSIONS:
        failures.append(f"invalid_outcome_dimension:{outcome}")

    severity = str(case.get("failure_severity") or "")
    if severity not in FAILURE_SEVERITIES:
        failures.append(f"invalid_failure_severity:{severity}")

    list_fields = (
        "conversation_turns",
        "required_context",
        "expected_coaching_truths",
        "retrieved_evidence_expected",
        "bad_coaching_patterns",
        "excellent_answer_traits",
        "baseline_comparison_rubric",
        "must_not",
        "tools_required_if_data_claiming",
    )
    for field in list_fields:
        value = case.get(field)
        if not isinstance(value, list) or not value:
            failures.append(f"invalid_list_field:{field}")

    if not case.get("baseline_answer"):
        failures.append("missing_baseline_answer")

    if not isinstance(case.get("situation"), Mapping):
        failures.append("invalid_situation")

    if not str(case.get("user_message") or "").strip():
        failures.append("missing_user_message")

    if not str(case.get("passing_answer") or "").strip():
        failures.append("missing_passing_answer")

    if not str(case.get("failing_answer") or "").strip():
        failures.append("missing_failing_answer")

    for idx, truth in enumerate(case.get("expected_coaching_truths") or []):
        if not isinstance(truth, Mapping):
            failures.append(f"invalid_truth:{idx}")
            continue
        if not truth.get("id"):
            failures.append(f"missing_truth_id:{idx}")
        if not truth.get("description"):
            failures.append(f"missing_truth_description:{idx}")
        if not truth.get("must_include_any") and not truth.get("must_include_all"):
            failures.append(f"truth_has_no_assertion:{truth.get('id') or idx}")

    for idx, evidence in enumerate(case.get("retrieved_evidence_expected") or []):
        if not isinstance(evidence, Mapping):
            failures.append(f"invalid_evidence:{idx}")
            continue
        if not evidence.get("tool"):
            failures.append(f"missing_evidence_tool:{idx}")
        if not evidence.get("must_include"):
            failures.append(f"missing_evidence_must_include:{idx}")
        if not evidence.get("reason"):
            failures.append(f"missing_evidence_reason:{idx}")

    return tuple(failures)


def _check_truths(case: Mapping[str, Any], assistant_text: str, failures: list[str]) -> None:
    for truth in case.get("expected_coaching_truths") or []:
        truth_id = str(truth.get("id") or "unknown_truth")
        include_any = list(truth.get("must_include_any") or [])
        include_all = list(truth.get("must_include_all") or [])
        if include_any and not _contains_any(assistant_text, include_any):
            failures.append(f"missing_expected_truth_any:{truth_id}")
        if include_all and not _contains_all(assistant_text, include_all):
            failures.append(f"missing_expected_truth_all:{truth_id}")


def _check_bad_patterns(case: Mapping[str, Any], assistant_text: str, failures: list[str]) -> None:
    for spec in case.get("bad_coaching_patterns") or []:
        if _spec_present(assistant_text, spec):
            label = spec if isinstance(spec, str) else spec.get("id") or spec.get("phrase") or spec.get("pattern")
            failures.append(f"bad_coaching_pattern_present:{label}")


def _check_must_not(case: Mapping[str, Any], assistant_text: str, failures: list[str]) -> None:
    for spec in case.get("must_not") or []:
        if _spec_present(assistant_text, spec):
            label = spec if isinstance(spec, str) else spec.get("id") or spec.get("phrase") or spec.get("pattern")
            failures.append(f"must_not_present:{label}")


def _check_tools(case: Mapping[str, Any], tools_called: Sequence[str], failures: list[str]) -> None:
    called = set(tools_called or [])
    for tool in case.get("tools_required_if_data_claiming") or []:
        if tool not in called:
            failures.append(f"missing_required_tool:{tool}")


def _evidence_blob(evidence: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for value in evidence.values():
        if isinstance(value, (str, int, float, bool)):
            parts.append(str(value))
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            parts.extend(str(item) for item in value)
        elif isinstance(value, Mapping):
            parts.append(_evidence_blob(value))
    return " ".join(parts)


def _check_retrieved_evidence(
    case: Mapping[str, Any],
    retrieved_evidence: Sequence[Mapping[str, Any]],
    failures: list[str],
) -> None:
    for expected in case.get("retrieved_evidence_expected") or []:
        tool = str(expected.get("tool") or "")
        needles = [str(item) for item in (expected.get("must_include") or [])]
        matching = [
            evidence
            for evidence in retrieved_evidence or []
            if str(evidence.get("tool") or "") == tool
        ]
        if not matching:
            failures.append(f"missing_retrieved_evidence_tool:{tool}")
            continue
        combined = " ".join(_evidence_blob(evidence) for evidence in matching)
        missing = [needle for needle in needles if needle.lower() not in _lower(combined)]
        if missing:
            failures.append(f"missing_retrieved_evidence:{tool}:{','.join(missing)}")


def evaluate_real_coach_response(
    case: Mapping[str, Any],
    *,
    assistant_text: str | None = None,
    tools_called: Sequence[str] | None = None,
    retrieved_evidence: Sequence[Mapping[str, Any]] | None = None,
) -> RealCoachEvalResult:
    """Evaluate a response against Phase 8 deterministic coaching truth checks."""

    schema_failures = list(validate_real_coach_case(case))
    text = assistant_text if assistant_text is not None else str(case.get("passing_answer") or "")
    called = list(tools_called if tools_called is not None else case.get("tools_called") or [])
    evidence = list(
        retrieved_evidence
        if retrieved_evidence is not None
        else case.get("retrieved_evidence") or []
    )
    failures: list[str] = list(schema_failures)

    if not text.strip():
        failures.append("empty_response")

    _check_truths(case, text, failures)
    _check_bad_patterns(case, text, failures)
    _check_must_not(case, text, failures)
    _check_tools(case, called, failures)
    _check_retrieved_evidence(case, evidence, failures)

    return RealCoachEvalResult(
        case_id=str(case.get("id") or "unknown_case"),
        domain=str(case.get("domain") or "unknown_domain"),
        case_type=str(case.get("case_type") or "unknown_case_type"),
        passed=not failures,
        failures=tuple(failures),
        severity=str(case.get("failure_severity") or "fatal"),
    )


def build_tier3_judge_payload(
    case: Mapping[str, Any],
    *,
    assistant_text: str,
    retrieved_evidence: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the rubric payload for nightly/pre-deploy LLM-as-judge scoring."""

    return {
        "case_id": case.get("id"),
        "domain": case.get("domain"),
        "case_type": case.get("case_type"),
        "situation": case.get("situation"),
        "conversation_turns": case.get("conversation_turns"),
        "expected_coaching_truths": case.get("expected_coaching_truths"),
        "retrieved_evidence_summary": list(
            retrieved_evidence
            if retrieved_evidence is not None
            else case.get("retrieved_evidence") or []
        ),
        "baseline_answer": case.get("baseline_answer"),
        "baseline_comparison_rubric": case.get("baseline_comparison_rubric"),
        "outcome_dimension": case.get("outcome_dimension"),
        "failure_severity": case.get("failure_severity"),
        "coach_response": assistant_text,
        "scoring_instruction": (
            "Score whether the coach response is tactically correct for this "
            "athlete, meets or beats the baseline answer's utility, and serves "
            "the outcome dimension. Do not reward contract shape by itself."
        ),
    }


def evaluate_tier3_judge_scores(
    case: Mapping[str, Any],
    judge_scores: Mapping[str, Any],
    *,
    min_average: float = 4.0,
    min_dimension: float = 3.0,
) -> Tier3JudgeResult:
    """Normalize a nightly judge response into a deterministic pass/fail result."""

    required_dimensions = (
        "tactical_correctness",
        "baseline_utility",
        "outcome_served",
        "evidence_usefulness",
    )
    failures: list[str] = []
    scores: list[float] = []
    for dimension in required_dimensions:
        raw = judge_scores.get(dimension)
        try:
            score = float(raw)
        except (TypeError, ValueError):
            failures.append(f"missing_judge_score:{dimension}")
            continue
        if score < min_dimension:
            failures.append(f"judge_dimension_below_min:{dimension}:{score:g}<{min_dimension:g}")
        scores.append(score)

    average = sum(scores) / len(scores) if scores else 0.0
    if average < min_average:
        failures.append(f"judge_average_below_min:{average:.2f}<{min_average:.2f}")

    return Tier3JudgeResult(
        case_id=str(case.get("id") or "unknown_case"),
        domain=str(case.get("domain") or "unknown_domain"),
        passed=not failures,
        score=round(average, 2),
        failures=tuple(failures),
    )


def summarize_tier3_domain_scores(results: Sequence[Tier3JudgeResult]) -> dict[str, Any]:
    domain_scores: dict[str, list[float]] = {}
    domain_failures: dict[str, int] = {}
    for result in results:
        domain_scores.setdefault(result.domain, []).append(result.score)
        if not result.passed:
            domain_failures[result.domain] = domain_failures.get(result.domain, 0) + 1

    domains = {
        domain: {
            "average_score": round(sum(scores) / len(scores), 2),
            "cases": len(scores),
            "failures": domain_failures.get(domain, 0),
        }
        for domain, scores in sorted(domain_scores.items())
    }
    return {
        "total_cases": len(results),
        "passed_cases": sum(1 for result in results if result.passed),
        "failed_cases": sum(1 for result in results if not result.passed),
        "domains": domains,
    }


def summarize_real_coach_results(results: Sequence[RealCoachEvalResult]) -> dict[str, Any]:
    domain_summary: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = domain_summary.setdefault(result.domain, {"passed": 0, "failed": 0})
        bucket["passed" if result.passed else "failed"] += 1
    return {
        "total": len(results),
        "passed": sum(1 for result in results if result.passed),
        "failed": sum(1 for result in results if not result.passed),
        "domains": domain_summary,
    }
