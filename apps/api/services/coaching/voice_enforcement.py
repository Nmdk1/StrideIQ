from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import Any, Callable

TEMPLATE_PHRASE_BLOCKLIST = (
    "consider",
    "you might want to",
    "great question",
    "well done",
    "solid and practical",
    "disciplined fueling",
    "no guilt",
    "real food, controlled, satisfying",
    "real food, controlled",
    "healthy in the way that matters",
    "natural sweetness without junk",
    "great for satiety and muscle repair",
    "love that you",
    "amazing job",
    "proud of you",
    "keep up the great work",
    "that's awesome",
    "keep crushing it",
    "you've got this",
    "trust the process",
    "listen to your body",
)


class VoiceContractViolation(RuntimeError):
    def __init__(self, hits: list[str]):
        self.hits = hits
        super().__init__(f"template_phrase_blocklist_hit:{','.join(hits)}")


@dataclass(frozen=True)
class VoiceCheckResult:
    ok: bool
    hits: list[str]


def check_response(response_text: str) -> dict[str, Any]:
    text = response_text or ""
    hits = []
    for phrase in TEMPLATE_PHRASE_BLOCKLIST:
        pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(phrase)
    return {"ok": not hits, "hits": hits}


async def _call_retry(
    retry_callable: Callable[[str], Any],
    instruction: str,
) -> str:
    result = retry_callable(instruction)
    if inspect.isawaitable(result):
        result = await result
    return str(result or "")


async def enforce_voice(
    response_text: str,
    retry_callable: Callable[[str], Any],
    *,
    max_retries: int = 2,
) -> dict[str, Any]:
    current = response_text or ""
    total_hits: list[str] = []
    for _ in range(max_retries + 1):
        check = check_response(current)
        hits = list(check["hits"])
        if not hits:
            return {
                "response": current,
                "template_phrase_count": len(total_hits),
                "template_phrase_hits": total_hits,
                "retried": bool(total_hits),
            }
        total_hits.extend(hits)
        if len(total_hits) > max_retries * max(1, len(hits)):
            break
        instruction = (
            "Rewrite the answer without these forbidden template phrases: "
            f"{', '.join(hits)}. Keep the athlete-specific facts and decision."
        )
        current = await _call_retry(retry_callable, instruction)
    raise VoiceContractViolation(total_hits)
