from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Sequence


class ConversationContractType(str, Enum):
    QUICK_CHECK = "quick_check"
    DECISION_POINT = "decision_point"
    RACE_STRATEGY = "race_strategy"
    RACE_DAY = "race_day"
    POST_RUN_INTERPRETATION = "post_run_interpretation"
    EMOTIONAL_LOAD = "emotional_load"
    CORRECTION_DISPUTE = "correction_dispute"
    IDENTITY_CONTEXT_UPDATE = "identity_context_update"
    DEEP_ANALYSIS = "deep_analysis"
    GENERAL = "general"


@dataclass(frozen=True)
class ConversationContract:
    contract_type: ConversationContractType
    outcome_target: str
    required_behavior: str
    max_words: int | None = None


_CORRECTION_RE = re.compile(
    r"\b("
    r"you(?:'re| are) wrong|that(?:'s| is) wrong|not true|"
    r"that(?:'s| is) not how|"
    r"you can see it|it(?:'s| is) in (?:my )?(?:activity|training|plan|history)|"
    r"i (?:just )?checked|actually\b|today is|today\s+is"
    r"|do(?:n't| not) treat|do(?:n't| not) use|not a fair|not a clean"
    r")\b",
    re.IGNORECASE,
)

_PRYING_RE = re.compile(
    r"\b("
    r"what(?:'s| is) going on|tell me (?:more )?about (?:your )?life|"
    r"why are you stressed|what caused (?:the )?stress|unpack that"
    r")\b",
    re.IGNORECASE,
)

_EVIDENCE_HEADING_RE = re.compile(r"(?mi)(^|\n)##\s*Evidence\s*\n")
_DATE_REPAIR_RE = re.compile(
    r"\b(?:on\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?\b",
    re.IGNORECASE,
)
_WORKOUT_EVIDENCE_DISPUTE_RE = re.compile(
    r"\bi\s+(?:did|ran|have done)\b.*\b(?:\d{1,2}\s*(?:x|by)\s*)?(?:200|300|400|600|800|1000|1200|1600|mile)s?\b.*\b(?:faster|harder|quicker|workout|session)\b",
    re.IGNORECASE,
)


def _context_to_text(conversation_context: Sequence[Any] | str | None) -> str:
    if conversation_context is None:
        return ""
    if isinstance(conversation_context, str):
        return conversation_context
    parts: list[str] = []
    for item in conversation_context:
        if isinstance(item, dict):
            content = item.get("content")
            if content:
                parts.append(str(content))
        elif item is not None:
            parts.append(str(item))
    return "\n".join(parts)


def _has_same_day_race_context(text: str) -> bool:
    lower = (text or "").lower()
    raceish = any(
        token in lower
        for token in (
            "race",
            "5k",
            "10k",
            "half marathon",
            "marathon",
            "tune up",
            "tune-up",
        )
    )
    same_day = any(
        token in lower
        for token in (
            "today",
            "this morning",
            "tonight",
            "in 1 hour",
            "in 2 hours",
            "in 3 hours",
            "in 4 hours",
            "packet pickup",
            "warmup",
            "warm up",
        )
    )
    return raceish and same_day


def _is_race_day_followup(text: str) -> bool:
    lower = (text or "").lower()
    return any(
        token in lower
        for token in (
            "pace",
            "5:50",
            "5:55",
            "bicarb",
            "maurten",
            "warmup",
            "warm up",
            "packet pickup",
            "mile",
            "split",
            "go out",
            "going out",
        )
    )


def _is_failed_lookup_context(text: str) -> bool:
    lower = (text or "").lower()
    return any(token in lower for token in ("could not find", "can't find", "did not find", "no activities matched"))


def classify_conversation_contract(
    message: str,
    conversation_context: Sequence[Any] | str | None = None,
) -> ConversationContract:
    text = (message or "").strip()
    lower = text.lower()
    context_text = _context_to_text(conversation_context)
    message_same_day_race_context = _has_same_day_race_context(text)
    thread_same_day_race_context = _has_same_day_race_context(context_text)

    if (
        _CORRECTION_RE.search(text)
        or _WORKOUT_EVIDENCE_DISPUTE_RE.search(text)
        or (_is_failed_lookup_context(context_text) and _DATE_REPAIR_RE.search(text))
    ):
        return ConversationContract(
            contract_type=ConversationContractType.CORRECTION_DISPUTE,
            outcome_target="Repair trust by verifying the athlete's correction before making new claims.",
            required_behavior=(
                "Verify with tools when possible; otherwise label the correction as athlete-stated. "
                "Do not repeat the disputed claim. State what was searched if a lookup fails."
            ),
            max_words=160,
        )

    if "quick check" in lower or "keep it brief" in lower:
        return ConversationContract(
            contract_type=ConversationContractType.QUICK_CHECK,
            outcome_target="Give concise executable guidance.",
            required_behavior="Answer directly in a few sentences; avoid broad analysis unless asked.",
            max_words=80,
        )

    if thread_same_day_race_context and _is_race_day_followup(text):
        return ConversationContract(
            contract_type=ConversationContractType.RACE_DAY,
            outcome_target="Help the athlete execute today's race decision with confidence and precision.",
            required_behavior=(
                "Use race-day execution mode: timeline, warmup, supplement/fueling timing when relevant, "
                "mile-by-mile effort cues, and one mental cue. Do not relitigate whether the athlete should race."
            ),
            max_words=260,
        )

    race_terms = (
        "race",
        "5k",
        "10k",
        "half marathon",
        "marathon",
        "tune up",
        "tune-up",
        "mayor",
    )
    strategy_terms = (
        "strategy",
        "plan",
        "pacing",
        "pace",
        "execution",
        "execute",
        "tactic",
        "approach",
        "tomorrow",
    )
    if message_same_day_race_context:
        return ConversationContract(
            contract_type=ConversationContractType.RACE_DAY,
            outcome_target="Help the athlete execute today's race decision with confidence and precision.",
            required_behavior=(
                "Use race-day execution mode: timeline, warmup, supplement/fueling timing when relevant, "
                "mile-by-mile effort cues, and one mental cue. Do not relitigate whether the athlete should race."
            ),
            max_words=260,
        )

    if any(token in lower for token in race_terms) and any(token in lower for token in strategy_terms):
        return ConversationContract(
            contract_type=ConversationContractType.RACE_STRATEGY,
            outcome_target="Produce an execution plan that makes the athlete strategically sharper.",
            required_behavior=(
                "Use the race strategy packet. Identify the realistic objective, primary limiter, "
                "false limiter, pacing or effort shape, course-specific risk, execution cues, "
                "success definition beyond time, and post-race learning target."
            ),
            max_words=260,
        )

    if any(token in lower for token in ("should i", "do i", "am i", "move", "postpone", "shift", "choose")):
        return ConversationContract(
            contract_type=ConversationContractType.DECISION_POINT,
            outcome_target="Clarify the tradeoff and give a decision frame.",
            required_behavior="Name the decision, the main tradeoff, and a default recommendation.",
            max_words=180,
        )

    if any(token in lower for token in ("stressed", "depleted", "overwhelmed", "angry", "scared")):
        return ConversationContract(
            contract_type=ConversationContractType.EMOTIONAL_LOAD,
            outcome_target="Make the athlete steadier and more capable without prying.",
            required_behavior="Acknowledge the state, respect boundaries, and give one grounded next step.",
            max_words=160,
        )

    return ConversationContract(
        contract_type=ConversationContractType.GENERAL,
        outcome_target="Answer the athlete's latest request usefully and truthfully.",
        required_behavior="Use tools for data claims; suppress unsupported claims.",
        max_words=None,
    )


def _split_main_and_evidence(text: str) -> tuple[str, str]:
    match = _EVIDENCE_HEADING_RE.search(text or "")
    if not match:
        return (text or "").strip(), ""
    split_idx = match.start() + (1 if match.group(1) == "\n" else 0)
    return (text[:split_idx] or "").strip(), (text[split_idx:] or "").strip()


def _word_count(text: str) -> int:
    return len((text or "").split())


def _limit_words(text: str, max_words: int) -> str:
    words = (text or "").split()
    if len(words) <= max_words:
        return (text or "").strip()
    truncated = " ".join(words[:max_words]).rstrip(" ,;:")
    sentence_end = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
    if sentence_end >= max(0, len(truncated) // 4):
        return truncated[: sentence_end + 1].strip()
    return truncated + "."


def validate_conversation_contract_response(
    user_message: str,
    assistant_message: str,
    conversation_context: Sequence[Any] | str | None = None,
) -> tuple[bool, str]:
    contract = classify_conversation_contract(user_message, conversation_context=conversation_context)
    main, _evidence = _split_main_and_evidence(assistant_message or "")
    lower = main.lower()

    if contract.contract_type == ConversationContractType.QUICK_CHECK:
        if contract.max_words and _word_count(main) > contract.max_words:
            return False, "quick_check_too_long"
        return True, "ok"

    if contract.contract_type == ConversationContractType.DECISION_POINT:
        has_decision = any(
            token in lower
            for token in (
                "decision:",
                "default:",
                "recommend",
                "i'd",
                "i would",
                "should",
                "run",
                "rest",
                "cross-train",
                "move",
                "skip",
                "eat",
                "take",
                "do this",
            )
        )
        has_tradeoff = any(
            token in lower
            for token in (
                "tradeoff",
                "trade-off",
                "cost",
                "risk",
                "because",
                "but",
                "if",
                "unless",
                "watch",
                "instead",
            )
        )
        if not (has_decision and has_tradeoff):
            return False, "decision_point_missing_frame"
        return True, "ok"

    if contract.contract_type == ConversationContractType.CORRECTION_DISPUTE:
        has_verification = any(
            token in lower
            for token in (
                "i searched",
                "searched",
                "verified",
                "could not verify",
                "can't verify",
                "cannot verify",
                "athlete-stated",
                "you are right",
                "you're right",
            )
        )
        if not has_verification:
            return False, "correction_dispute_missing_verification"
        return True, "ok"

    if contract.contract_type == ConversationContractType.EMOTIONAL_LOAD:
        if _PRYING_RE.search(main):
            return False, "emotional_load_prying"
        has_next_step = any(token in lower for token in ("next step", "eat", "meal", "snack", "drink", "do this"))
        if not has_next_step:
            return False, "emotional_load_missing_next_step"
        return True, "ok"

    if contract.contract_type == ConversationContractType.RACE_STRATEGY:
        required_groups = {
            "objective": ("objective", "goal", "target", "realistic", "race for"),
            "pacing_shape": ("pacing", "pace", "effort shape", "open", "hold", "close", "surge"),
            "course_risk": ("course", "hill", "rise", "gain", "turn", "wind", "weather", "risk"),
        }
        missing = [
            name
            for name, tokens in required_groups.items()
            if not any(token in lower for token in tokens)
        ]
        if missing:
            return False, "race_strategy_missing_packet"
        return True, "ok"

    if contract.contract_type == ConversationContractType.RACE_DAY:
        required_groups = {
            "timeline": ("timeline", "leave", "arrival", "arrive", "packet", "start"),
            "warmup": ("warmup", "warm up", "strides", "drills"),
            "execution": ("mile", "first", "second", "third", "effort", "pace"),
            "cue": ("cue", "cues", "relax", "commit", "controlled"),
        }
        lower_text = lower
        missing = [
            name
            for name, tokens in required_groups.items()
            if not any(token in lower_text for token in tokens)
        ]
        if missing:
            return False, "race_day_missing_execution_packet"
        return True, "ok"

    return True, "ok"


def build_conversation_contract_retry_instruction(
    user_message: str,
    reason: str,
    conversation_context: Sequence[Any] | str | None = None,
) -> str:
    contract = classify_conversation_contract(user_message, conversation_context=conversation_context)
    base = (
        "Your previous answer violated the conversation outcome contract. "
        f"Reason: {reason}. "
    )
    if contract.contract_type == ConversationContractType.QUICK_CHECK:
        return base + f"Answer in no more than {contract.max_words or 80} words. No broad analysis."
    if contract.contract_type == ConversationContractType.DECISION_POINT:
        return base + "Use this shape: Decision, Tradeoff, Default recommendation. Keep it concise."
    if contract.contract_type == ConversationContractType.CORRECTION_DISPUTE:
        return base + "Verify with tools if possible; otherwise label the claim athlete-stated. State what was searched."
    if contract.contract_type == ConversationContractType.EMOTIONAL_LOAD:
        return base + "Do not pry. Give grounded food/recovery guidance and one next step."
    if contract.contract_type == ConversationContractType.RACE_STRATEGY:
        return base + (
            "Use this shape: Objective, Primary limiter, False limiter, Pacing shape, "
            "Course risk, Execution cues, Success beyond time, Post-race learning. "
            "Ground it in the race strategy packet and state uncertainty instead of guessing."
        )
    if contract.contract_type == ConversationContractType.RACE_DAY:
        return base + (
            "Use race-day execution mode: timeline, warmup, supplement/fueling timing if relevant, "
            "mile-by-mile effort cues, and one mental cue. Support the athlete's decision."
        )
    return base + contract.required_behavior


def enforce_conversation_contract_output(
    user_message: str,
    assistant_message: str,
    conversation_context: Sequence[Any] | str | None = None,
) -> str:
    contract = classify_conversation_contract(user_message, conversation_context=conversation_context)
    if contract.contract_type != ConversationContractType.QUICK_CHECK or not contract.max_words:
        return (assistant_message or "").strip()

    main, evidence = _split_main_and_evidence(assistant_message or "")
    trimmed = _limit_words(main, contract.max_words)
    if evidence:
        return f"{trimmed}\n\n{evidence}".strip()
    return trimmed
