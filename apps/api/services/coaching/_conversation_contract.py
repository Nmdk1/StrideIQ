from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


class ConversationContractType(str, Enum):
    QUICK_CHECK = "quick_check"
    DECISION_POINT = "decision_point"
    RACE_STRATEGY = "race_strategy"
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
    r"you can see it|it(?:'s| is) in (?:my )?(?:activity|training|plan|history)|"
    r"i (?:just )?checked|actually\b|today is|today\s+is"
    r")\b",
    re.IGNORECASE,
)


def classify_conversation_contract(message: str) -> ConversationContract:
    text = (message or "").strip()
    lower = text.lower()

    if _CORRECTION_RE.search(text):
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

    if "race" in lower and any(
        token in lower for token in ("strategy", "tomorrow", "5k", "10k", "tune up", "tune-up", "pacing")
    ):
        return ConversationContract(
            contract_type=ConversationContractType.RACE_STRATEGY,
            outcome_target="Produce an execution plan that makes the athlete strategically sharper.",
            required_behavior=(
                "Ground the answer in race history, course/activity evidence, current training, "
                "and athlete-stated psychology when available."
            ),
            max_words=260,
        )

    if any(token in lower for token in ("should i", "do i", "move", "postpone", "shift", "choose")):
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
