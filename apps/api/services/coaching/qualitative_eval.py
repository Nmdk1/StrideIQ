from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from services.coaching._conversation_contract import classify_conversation_contract


DEFAULT_WORD_LIMITS = {
    "quick_check": 120,
    "decision_point": 220,
    "nutrition_fueling": 260,
    "recovery_sleep_stress": 220,
    "injury_pain_triage": 240,
    "race_strategy": 420,
    "race_day": 360,
    "post_run_interpretation": 380,
    "deep_analysis": 700,
}

DEFAULT_NUMERIC_ANCHOR_LIMITS = {
    "quick_check": 2,
    "decision_point": 4,
    "nutrition_fueling": 3,
    "recovery_sleep_stress": 3,
    "injury_pain_triage": 3,
    "race_strategy": 8,
    "race_day": 6,
    "post_run_interpretation": 8,
    "deep_analysis": 14,
}

SYSTEM_LANGUAGE_TERMS = (
    "athlete_facts",
    "unknown in your profile",
    "unknowns",
    "ledger",
    "packet",
    "runtime",
    "tool",
    "calendar_context",
    "nutrition_context",
    "retrieved evidence",
    "confidence athlete_stated",
    "context block",
    "same_turn_table_evidence",
)

FORBIDDEN_VISIBLE_SECTIONS = (
    "The unasked",
    "The read",
    "The deeper read",
    "Decision for today",
)

UNKNOWN_PHRASES = (
    "i don't have your current pace zones",
    "i do not have your current pace zones",
    "i don't have your pace zones",
    "i do not have your pace zones",
    "unknown in your profile",
)

MODE_DECISION_LEAD_REQUIRED = frozenset(
    {
        "quick_check",
        "decision_point",
        "race_strategy",
        "race_day",
        "nutrition_fueling",
        "recovery_sleep_stress",
        "injury_pain_triage",
    }
)
MODE_DECISION_LEAD_EXEMPT = frozenset(
    {
        "observe_and_ask",
        "uncertainty_disclosure",
        "asking_after_work",
        "correction",
        "correction_dispute",
        "engage_and_reason",
    }
)

_WORD_RE = re.compile(r"\b[\w'-]+\b")
_QUESTION_RE = re.compile(r"\?")
_LINE_START_RE_TEMPLATE = r"(?im)^\s*(?:#{{1,6}}\s*)?{label}\s*:"
_NUMERIC_RE = re.compile(
    r"(?<![\w])(?:\d+(?:[:.]\d+)?(?:\s*[-–]\s*\d+(?:[:.]\d+)?)?)"
    r"(?:\s*(?:%|/mi|mi|mile|miles|bpm|ft|k|K|x|×))?(?![\w])"
)


@dataclass(frozen=True)
class QualitativeEvalResult:
    passed: bool
    failures: tuple[str, ...]
    word_count: int
    athlete_numeric_anchor_count: int
    followup_question_count: int


def _lower(text: str) -> str:
    return (text or "").lower()


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def _question_count(text: str) -> int:
    return len(_QUESTION_RE.findall(text or ""))


def _sentence_windows(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]


def _looks_like_general_protocol(window: str) -> bool:
    lower = _lower(window)
    protocol_terms = (
        "gel",
        "water",
        "fluid",
        "oz",
        "carb",
        "protein",
        "caffeine",
        "electrolyte",
        "breakfast",
        "dinner",
        "before the start",
        "before the workout",
        "pre-start",
        "g/kg",
        "mg/kg",
    )
    return any(term in lower for term in protocol_terms)


def _athlete_numeric_anchor_count(text: str) -> int:
    count = 0
    for window in _sentence_windows(text):
        matches = _NUMERIC_RE.findall(window)
        if not matches:
            continue
        if _looks_like_general_protocol(window):
            continue
        count += len(matches)
    return count


def _contains_phrase(text: str, phrase: str) -> bool:
    return phrase.lower() in _lower(text)


def _visible_section_present(text: str, label: str) -> bool:
    pattern = _LINE_START_RE_TEMPLATE.format(label=re.escape(label))
    return re.search(pattern, text or "") is not None


def _find_repeated_unknowns(
    assistant_text: str,
    prior_turns: Sequence[Mapping[str, Any]] | None,
) -> list[str]:
    if not prior_turns:
        return []
    prior_assistant_text = "\n".join(
        str(turn.get("content") or "")
        for turn in prior_turns
        if str(turn.get("role") or "").lower() in {"assistant", "coach"}
    )
    repeated = []
    for phrase in UNKNOWN_PHRASES:
        if _contains_phrase(assistant_text, phrase) and _contains_phrase(
            prior_assistant_text, phrase
        ):
            repeated.append(phrase)
    return repeated


def _starts_with_decision(text: str) -> bool:
    stripped = (text or "").strip().lower()
    decision_starts = (
        "decision",
        "default",
        "run ",
        "rest",
        "cross-train",
        "skip",
        "move",
        "keep ",
        "take ",
        "do ",
        "use ",
        "cap ",
        "gel ",
        "sharpen",
        "easy ",
        "no ",
        "yes",
    )
    return stripped.startswith(decision_starts)


def _must_lead_with_decision_applies(value: Any, mode: str, contract_type: str) -> bool:
    if value is False or value is None:
        return False
    if str(mode) in MODE_DECISION_LEAD_EXEMPT:
        return False
    if value == "mode_conditioned":
        return str(mode) in MODE_DECISION_LEAD_REQUIRED or contract_type in MODE_DECISION_LEAD_REQUIRED
    return bool(value)


def _contract_type_for(
    user_message: str,
    contract_type: str | None,
    prior_turns: Sequence[Mapping[str, Any]] | None,
) -> str:
    if contract_type:
        return contract_type
    return classify_conversation_contract(
        user_message,
        conversation_context=list(prior_turns or []),
    ).contract_type.value


def _limit_for(
    qualitative_contract: Mapping[str, Any] | None,
    key: str,
    contract_type: str,
    domain: str | None,
    defaults: Mapping[str, int],
) -> int | None:
    if qualitative_contract and qualitative_contract.get(key) is not None:
        return int(qualitative_contract[key])
    if domain and domain in defaults:
        return defaults[domain]
    return defaults.get(contract_type)


def evaluate_qualitative_response(
    *,
    user_message: str,
    assistant_text: str,
    contract_type: str | None = None,
    domain: str | None = None,
    prior_turns: Sequence[Mapping[str, Any]] | None = None,
    expected_relevant_terms: Sequence[str] | None = None,
    irrelevant_context_terms: Sequence[str] | None = None,
    qualitative_contract: Mapping[str, Any] | None = None,
    mode: str | None = None,
) -> QualitativeEvalResult:
    resolved_contract_type = _contract_type_for(user_message, contract_type, prior_turns)
    resolved_mode = str(
        mode
        or (qualitative_contract or {}).get("artifact5_mode")
        or resolved_contract_type
    )
    text = assistant_text or ""
    failures: list[str] = []

    words = _word_count(text)
    word_limit = _limit_for(
        qualitative_contract,
        "max_words",
        resolved_contract_type,
        domain,
        DEFAULT_WORD_LIMITS,
    )
    if word_limit is not None and words > word_limit:
        failures.append(f"word_count_exceeds:{words}>{word_limit}")

    numeric_count = _athlete_numeric_anchor_count(text)
    numeric_limit = _limit_for(
        qualitative_contract,
        "max_athlete_numeric_anchors",
        resolved_contract_type,
        domain,
        DEFAULT_NUMERIC_ANCHOR_LIMITS,
    )
    if numeric_limit is not None and numeric_count > numeric_limit:
        failures.append(f"numeric_anchor_count_exceeds:{numeric_count}>{numeric_limit}")

    max_questions = (
        int(qualitative_contract.get("max_followup_questions"))
        if qualitative_contract and qualitative_contract.get("max_followup_questions") is not None
        else 1
    )
    questions = _question_count(text)
    if questions > max_questions:
        failures.append(f"followup_question_count_exceeds:{questions}>{max_questions}")

    if not qualitative_contract or qualitative_contract.get("forbidden_system_terms", True):
        for term in SYSTEM_LANGUAGE_TERMS:
            if _contains_phrase(text, term):
                failures.append(f"system_language_present:{term}")

    visible_sections = list(
        (qualitative_contract or {}).get("forbidden_visible_sections")
        or FORBIDDEN_VISIBLE_SECTIONS
    )
    for section in visible_sections:
        if _visible_section_present(text, str(section).rstrip(":")):
            failures.append(f"visible_section_present:{str(section).rstrip(':')}")

    combined_irrelevant_terms = list(irrelevant_context_terms or []) + list(
        (qualitative_contract or {}).get("irrelevant_context_terms") or []
    )
    for term in combined_irrelevant_terms:
        if term and _contains_phrase(text, str(term)):
            failures.append(f"irrelevant_context_present:{term}")

    repeated_unknowns = _find_repeated_unknowns(text, prior_turns)
    for phrase in repeated_unknowns:
        failures.append(f"repeated_unknown_phrase:{phrase}")

    if _must_lead_with_decision_applies(
        (qualitative_contract or {}).get("must_lead_with_decision"),
        resolved_mode,
        resolved_contract_type,
    ) and not _starts_with_decision(text):
        failures.append("does_not_lead_with_decision")

    for term in expected_relevant_terms or []:
        if term and not _contains_phrase(text, str(term)):
            failures.append(f"missing_relevant_term:{term}")

    return QualitativeEvalResult(
        passed=not failures,
        failures=tuple(failures),
        word_count=words,
        athlete_numeric_anchor_count=numeric_count,
        followup_question_count=questions,
    )


def evaluate_case_qualitative_response(
    case: Mapping[str, Any],
    *,
    assistant_text: str | None = None,
) -> QualitativeEvalResult:
    qualitative_contract = case.get("qualitative_contract")
    text = assistant_text if assistant_text is not None else str(case.get("passing_answer") or "")
    return evaluate_qualitative_response(
        user_message=str(case.get("user_message") or ""),
        assistant_text=text,
        contract_type=str(case.get("contract_type") or "") or None,
        domain=str(case.get("domain") or "") or None,
        prior_turns=list(case.get("conversation_turns") or []),
        qualitative_contract=(
            qualitative_contract if isinstance(qualitative_contract, Mapping) else None
        ),
        mode=str(case.get("artifact5_mode") or "") or None,
    )
