from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.config import settings
from services.coaching.ledger import PendingConflict, set_fact


@dataclass(frozen=True)
class ProposedFact:
    field: str
    value: Any
    source: str
    confidence: str = "athlete_stated"
    asserted_at: datetime | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _first_float(patterns: tuple[str, ...], text: str) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _first_int(patterns: tuple[str, ...], text: str) -> int | None:
    value = _first_float(patterns, text)
    return int(value) if value is not None else None


def _extract_standing_overrides(message: str, asserted_at: datetime) -> list[str]:
    lower = message.lower()
    overrides: list[str] = []
    if _contains_any(
        lower,
        (
            "do not give me fueling advice",
            "don't give me fueling advice",
            "no fueling advice",
        ),
    ):
        overrides.append("no_unsolicited_fueling_advice")
    if _contains_any(
        lower,
        (
            "don't operate on population models",
            "do not operate on population models",
            "no population models",
        ),
    ):
        overrides.append("avoid_population_model_assumptions")
    if _contains_any(
        lower,
        (
            "only do trap bar deadlifts",
            "only use trap bar deadlifts",
            "i only do trap bar deadlifts",
        ),
    ):
        overrides.append("strength_lift_preference:trap_bar_deadlift_only")
    if "my recovery is" in lower and _contains_any(lower, ("faster", "much faster")):
        overrides.append("athlete_reports_fast_recovery_relative_to_population")
    return [
        {
            "domain": item.split(":", 1)[0],
            "value": item.split(":", 1)[1] if ":" in item else item,
            "asserted_at": asserted_at.isoformat(),
        }
        for item in overrides
    ]


def extract_facts_from_turn(
    athlete_id: UUID,
    turn: str,
    *,
    source: str,
    asserted_at: datetime | None = None,
) -> list[ProposedFact]:
    del athlete_id  # Reserved for future athlete-specific extraction context.
    message = (turn or "").strip()
    lower = message.lower()
    if not message:
        return []

    asserted = asserted_at or _now()
    facts: list[ProposedFact] = []

    weekly_volume = _first_float(
        (
            r"\b(?:i'?m|i am|currently)?\s*(?:a\s+)?(\d+(?:\.\d+)?)\s*mpw\b",
            r"\b(?:run|running|average|averaging)\s*(\d+(?:\.\d+)?)\s*(?:miles|mi)\s*(?:a|per)?\s*week\b",
        ),
        lower,
    )
    if weekly_volume is not None:
        facts.append(
            ProposedFact(
                field="weekly_volume_mpw",
                value=weekly_volume,
                source=source,
                asserted_at=asserted,
            )
        )

    age = _first_int(
        (
            r"\bi\s*(?:am|'m)\s*(\d{2})\b",
            r"\b(\d{2})\s*(?:years old|yo)\b",
            r"\bi'?m\s*(\d{2})\s+not\s+\d{2}\b",
        ),
        lower,
    )
    if age is not None and 10 <= age <= 99:
        facts.append(
            ProposedFact(field="age", value=age, source=source, asserted_at=asserted)
        )

    current_weight = _first_float(
        (
            r"\b(?:i\s+weigh|current weight is|currently weigh)\s*(\d+(?:\.\d+)?)\s*(?:lb|lbs|pounds)\b",
        ),
        lower,
    )
    if current_weight is not None:
        facts.append(
            ProposedFact(
                field="current_weight_lbs",
                value=current_weight,
                source=source,
                asserted_at=asserted,
            )
        )

    target_weight_loss = _first_float(
        (r"\b(?:drop|lose|cut)\s*(\d+(?:\.\d+)?)\s*(?:lb|lbs|pounds)\b",),
        lower,
    )
    if target_weight_loss is not None and _contains_any(
        lower,
        ("before fall", "by fall", "this summer", "weight loss", "mass reduction"),
    ):
        facts.append(
            ProposedFact(
                field="cut_active",
                value={
                    "flag": True,
                    "start_date": asserted.date().isoformat(),
                    "target_deficit_kcal": None,
                    "target_loss_lbs": target_weight_loss,
                },
                source=source,
                asserted_at=asserted,
            )
        )

    target_event_match = re.search(
        r"\b(?P<distance>5k|10k|half(?: marathon)?|marathon|ultra)\b.*?\b(?P<time>sub\s*\d+(?::\d{2})?)",
        lower,
        flags=re.IGNORECASE,
    )
    if target_event_match is None:
        target_event_match = re.search(
            r"\b(?P<time>sub\s*\d+(?::\d{2})?)\s*(?P<distance>5k|10k|half(?: marathon)?|marathon|ultra)\b",
            lower,
            flags=re.IGNORECASE,
        )
    if target_event_match and _contains_any(lower, ("goal", "goals", "target", "fall")):
        distance = target_event_match.group("distance").replace(" ", "_")
        if distance in {"half", "half_marathon"}:
            distance = "half_marathon"
        facts.append(
            ProposedFact(
                field="target_event",
                value={
                    "distance": distance,
                    "date": None,
                    "goal_time": target_event_match.group("time").replace(" ", ""),
                },
                source=source,
                asserted_at=asserted,
            )
        )

    if _contains_any(lower, ("injured", "injury", "post injury", "came back")):
        facts.append(
            ProposedFact(
                field="recent_injuries",
                value=[
                    {
                        "site": None,
                        "severity": None,
                        "started_at": None,
                        "status": "recent_or_returning",
                    }
                ],
                source=source,
                asserted_at=asserted,
            )
        )

    standing_overrides = _extract_standing_overrides(message, asserted)
    if standing_overrides:
        facts.append(
            ProposedFact(
                field="standing_overrides",
                value=standing_overrides,
                source=source,
                asserted_at=asserted,
            )
        )

    return facts


async def extract_facts_from_turn_with_optional_llm(
    athlete_id: UUID,
    turn: str,
    *,
    source: str,
    asserted_at: datetime | None = None,
) -> list[ProposedFact]:
    facts = extract_facts_from_turn(
        athlete_id,
        turn,
        source=source,
        asserted_at=asserted_at,
    )
    if facts or not settings.COACH_LEDGER_LLM_EXTRACTION_ENABLED:
        return facts
    # Phase B2 wires the off-by-default seam only. Artifact 9 allows inferred
    # LLM facts later, but deterministic extraction is the production path now.
    return []


def persist_proposed_facts(
    db: Session,
    athlete_id: UUID,
    facts: list[ProposedFact],
) -> list[Any]:
    results: list[Any] = []
    for fact in facts:
        result = set_fact(
            db,
            athlete_id,
            fact.field,
            fact.value,
            source=fact.source,
            confidence=fact.confidence,
            asserted_at=fact.asserted_at,
        )
        if result is not None:
            results.append(result)
    return results
