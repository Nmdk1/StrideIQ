from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from services.coaching._conversation_contract import (
    classify_conversation_contract,
    validate_conversation_contract_response,
)


DIMENSIONS = {
    "factual_grounding",
    "correction_incorporation",
    "decision_clarity",
    "athlete_agency",
    "n1_specificity",
    "emotional_appropriateness",
    "non_obvious_usefulness",
    "evidence_quality",
}


@dataclass(frozen=True)
class CoachValueEvalResult:
    case_id: str
    passed: bool
    score: int
    max_score: int
    passed_dimensions: tuple[str, ...]
    failures: tuple[str, ...]


def _lower(text: str) -> str:
    return (text or "").lower()


def _phrase_present(text: str, phrase: str) -> bool:
    return _lower(phrase) in _lower(text)


def _regex_present(text: str, pattern: str) -> bool:
    return re.search(pattern, text or "", flags=re.IGNORECASE | re.MULTILINE) is not None


def _mark_dimension(passed_dimensions: set[str], dimension: str | None) -> None:
    if dimension:
        passed_dimensions.add(dimension)


def _check_required_phrases(
    *,
    assistant_text: str,
    specs: Sequence[Mapping[str, Any]],
    passed_dimensions: set[str],
    failures: list[str],
) -> None:
    for spec in specs:
        phrase = str(spec.get("text") or "")
        if not phrase:
            continue
        if _phrase_present(assistant_text, phrase):
            _mark_dimension(passed_dimensions, spec.get("dimension"))
        else:
            failures.append(f"missing_required_phrase:{phrase}")


def _check_required_regex(
    *,
    assistant_text: str,
    specs: Sequence[Mapping[str, Any]],
    passed_dimensions: set[str],
    failures: list[str],
) -> None:
    for spec in specs:
        pattern = str(spec.get("pattern") or "")
        if not pattern:
            continue
        if _regex_present(assistant_text, pattern):
            _mark_dimension(passed_dimensions, spec.get("dimension"))
        else:
            failures.append(f"missing_required_regex:{pattern}")


def _check_forbidden_phrases(
    *,
    assistant_text: str,
    specs: Sequence[Mapping[str, Any]],
    failures: list[str],
) -> None:
    for spec in specs:
        phrase = str(spec.get("text") or "")
        if phrase and _phrase_present(assistant_text, phrase):
            failures.append(f"forbidden_phrase_present:{phrase}")


def _check_forbidden_regex(
    *,
    assistant_text: str,
    specs: Sequence[Mapping[str, Any]],
    failures: list[str],
) -> None:
    for spec in specs:
        pattern = str(spec.get("pattern") or "")
        if pattern and _regex_present(assistant_text, pattern):
            failures.append(f"forbidden_regex_present:{pattern}")


def _check_tools(
    *,
    required_tools: Sequence[str],
    tools_called: Sequence[str],
    passed_dimensions: set[str],
    failures: list[str],
) -> None:
    called = set(tools_called or [])
    for tool in required_tools:
        if tool in called:
            passed_dimensions.add("factual_grounding")
            passed_dimensions.add("evidence_quality")
        else:
            failures.append(f"missing_required_tool:{tool}")


def _check_contract(
    *,
    case: Mapping[str, Any],
    assistant_text: str,
    passed_dimensions: set[str],
    failures: list[str],
) -> None:
    expected_contract = case.get("contract_type")
    if expected_contract:
        actual = classify_conversation_contract(str(case.get("user_message") or ""))
        if actual.contract_type.value != expected_contract:
            failures.append(f"contract_type_mismatch:{actual.contract_type.value}!={expected_contract}")

    contract_ok, reason = validate_conversation_contract_response(
        str(case.get("user_message") or ""),
        assistant_text,
    )
    if not contract_ok:
        failures.append(f"conversation_contract:{reason}")
        return

    contract_type = classify_conversation_contract(str(case.get("user_message") or "")).contract_type.value
    if contract_type == "decision_point":
        passed_dimensions.add("decision_clarity")
    elif contract_type == "correction_dispute":
        passed_dimensions.add("correction_incorporation")
        passed_dimensions.add("evidence_quality")
    elif contract_type == "emotional_load":
        passed_dimensions.add("emotional_appropriateness")
    elif contract_type == "race_strategy":
        passed_dimensions.add("decision_clarity")
        passed_dimensions.add("non_obvious_usefulness")
    elif contract_type == "race_day":
        passed_dimensions.add("decision_clarity")
        passed_dimensions.add("athlete_agency")
        passed_dimensions.add("non_obvious_usefulness")


def evaluate_coach_value_response(
    case: Mapping[str, Any],
    *,
    assistant_text: str | None = None,
    tools_called: Sequence[str] | None = None,
) -> CoachValueEvalResult:
    """Evaluate a coach answer against a behavioral value case.

    The harness intentionally avoids exact-prose matching. Cases define the
    facts, tools, forbidden claims, and contract shape needed for the athlete
    to leave the exchange better informed or more capable.
    """

    case_id = str(case.get("id") or "unknown_case")
    text = assistant_text if assistant_text is not None else str(case.get("assistant_response") or "")
    called_tools = list(tools_called if tools_called is not None else case.get("tools_called") or [])
    failures: list[str] = []
    passed_dimensions: set[str] = set()

    _check_contract(
        case=case,
        assistant_text=text,
        passed_dimensions=passed_dimensions,
        failures=failures,
    )
    _check_tools(
        required_tools=list(case.get("required_tools") or []),
        tools_called=called_tools,
        passed_dimensions=passed_dimensions,
        failures=failures,
    )
    _check_required_phrases(
        assistant_text=text,
        specs=list(case.get("required_phrases") or []),
        passed_dimensions=passed_dimensions,
        failures=failures,
    )
    _check_required_regex(
        assistant_text=text,
        specs=list(case.get("required_regex") or []),
        passed_dimensions=passed_dimensions,
        failures=failures,
    )
    _check_forbidden_phrases(
        assistant_text=text,
        specs=list(case.get("forbidden_phrases") or []),
        failures=failures,
    )
    _check_forbidden_regex(
        assistant_text=text,
        specs=list(case.get("forbidden_regex") or []),
        failures=failures,
    )

    required_dimensions = set(case.get("required_dimensions") or [])
    unknown_dimensions = required_dimensions - DIMENSIONS
    if unknown_dimensions:
        failures.append(f"unknown_dimensions:{','.join(sorted(unknown_dimensions))}")

    missing_dimensions = required_dimensions - passed_dimensions
    for dimension in sorted(missing_dimensions):
        failures.append(f"missing_dimension:{dimension}")

    score = len(passed_dimensions & DIMENSIONS)
    min_score = int(case.get("min_score") or len(required_dimensions))
    if score < min_score:
        failures.append(f"score_below_min:{score}<{min_score}")

    return CoachValueEvalResult(
        case_id=case_id,
        passed=not failures,
        score=score,
        max_score=len(DIMENSIONS),
        passed_dimensions=tuple(sorted(passed_dimensions & DIMENSIONS)),
        failures=tuple(failures),
    )
