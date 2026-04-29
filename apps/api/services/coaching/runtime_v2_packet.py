from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from core.config import settings
from models import Activity, ActivitySplit, NutritionEntry, TrainingPlan
from services.coach_tools.performance import get_race_predictions, get_training_paces
from services.coaching.ledger import (
    SENSITIVE_FACT_FIELDS,
    VALID_FACT_FIELDS,
    PendingConflict,
    get_ledger,
)
from services.coaching.recent_activities_block import compute_recent_activities
from services.coaching.runtime_v2 import PACKET_SCHEMA_VERSION
from services.coaching.thread_lifecycle import recent_threads_block
from services.coaching.unknowns_block import (
    SUGGESTED_QUESTIONS,
    compute_unknowns,
    detect_query_class,
)
from services.timezone_utils import (
    athlete_local_today,
    get_athlete_timezone_from_db,
    to_activity_local_date,
)

ASSEMBLER_VERSION = "coach_runtime_v2_0_a_packet_assembler_001"
MODE_CLASSIFIER_VERSION = "coach_mode_classifier_v2_0_a"
LEDGER_COVERAGE_SHIM_THRESHOLD = 0.5
LEGACY_CONTEXT_BRIDGE_MAX_CHARS = 3000
ACTIVITY_EVIDENCE_RECENT_ROWS_LIMIT = 4
NUTRITION_CONTEXT_ENTRY_LIMIT = 12
PERFORMANCE_PACE_HISTORY_LIMIT = 5
PACKET_MAX_ESTIMATED_TOKENS = 5000

logger = logging.getLogger(__name__)

ARTIFACT5_MODES = (
    "observe_and_ask",
    "engage_and_reason",
    "acknowledge_and_redirect",
    "pattern_observation",
    "pushback",
    "celebration",
    "uncertainty_disclosure",
    "asking_after_work",
    "racing_preparation_judgment",
    "brief_status_update",
    "correction",
    "mode_uncertain",
)


class V2PacketInvariantError(RuntimeError):
    """Raised when a visible V2 request cannot safely build a packet."""


_TEMPORAL_BRIDGE_PATTERN = re.compile(
    r"\b("
    r"today|tonight|tomorrow|yesterday|race|raced|racing|race[- ]?day|"
    r"race[- ]?week|taper|days? until|days? out|this morning|this week|"
    r"last night|last run|recent run|upcoming|"
    r"one day|two days|three days|four days|five days|six days|seven days|"
    r"eight days|nine days|ten days"
    r")\b",
    flags=re.IGNORECASE,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _estimated_tokens(value: Any) -> int:
    text = json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)
    return max(1, len(text) // 4)


def _empty_recent_activities(generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": "coach_runtime_v2.recent_activities.v1",
        "status": "unavailable",
        "generated_at": generated_at,
        "window_days": 14,
        "ordered": "most_recent_first",
        "data": {"recent_activities": [], "aggregates": {}},
        "token_budget": {
            "target_tokens": 1500,
            "max_tokens": 2500,
            "estimated_tokens": 1,
        },
        "provenance": [],
        "unknowns": [
            {
                "field": "recent_activities",
                "reason": "db_unavailable",
                "suggested_question": "What recent session should I anchor this answer to?",
            }
        ],
    }


def _empty_recent_threads() -> dict[str, Any]:
    return {
        "schema_version": "coach_runtime_v2.recent_threads.v1",
        "status": "unavailable",
        "recent_threads": [],
        "token_budget": {"max_tokens": 2000, "estimated_tokens": 1},
    }


def _detect_nutrition_context_kind(message: str) -> str | None:
    lower = (message or "").lower()

    def has_any(terms: tuple[str, ...]) -> bool:
        for term in terms:
            pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
            if re.search(pattern, lower, flags=re.IGNORECASE):
                return True
        return False

    pattern_terms = (
        "trend",
        "pattern",
        "grouping",
        "similar",
        "correlat",
        "compare",
        "block",
    )
    body_comp_terms = (
        "body composition",
        "body comp",
        "weight",
        "cut",
        "deficit",
        "lean mass",
        "lose pounds",
        "drop pounds",
    )
    race_fueling_terms = ("race morning", "race fueling", "bicarb", "maurten")
    workout_fueling_terms = (
        "fuel",
        "fueling",
        "gel",
        "gels",
        "hydration",
        "electrolyte",
        "caffeine",
        "stomach",
        "gut",
        "slosh",
    )
    food_log_terms = (
        "eat",
        "eaten",
        "ate",
        "food",
        "meal",
        "breakfast",
        "lunch",
        "dinner",
        "snack",
        "calorie",
        "calories",
        "macro",
        "macros",
        "protein",
        "carb",
        "carbs",
        "fat",
        "nutrition",
        "logged",
    )
    if has_any(pattern_terms) and has_any(food_log_terms + workout_fueling_terms):
        return "pattern_mining"
    if has_any(body_comp_terms):
        return "body_composition"
    if has_any(race_fueling_terms):
        return "race_fueling"
    if has_any(workout_fueling_terms):
        return "training_day_fueling"
    if has_any(food_log_terms):
        if "yesterday" in lower and "today" in lower:
            return "date_range_named_days"
        if "yesterday" in lower:
            return "date_range_yesterday"
        if any(
            re.search(r"(?<!\w)" + name + r"(?!\w)", lower)
            for name in _WEEKDAY_INDEX
        ):
            return "date_range_named_days"
        if any(
            term in lower
            for term in ("last week", "this week", "past week", "7 days")
        ):
            return "date_range_week"
        return "current_log"
    return None


_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _mentioned_weekday_dates(message_lower: str, today: date) -> list[date]:
    dates: list[date] = []
    for name, weekday in _WEEKDAY_INDEX.items():
        if not re.search(r"(?<!\w)" + name + r"(?!\w)", message_lower):
            continue
        delta = (today.weekday() - weekday) % 7
        dates.append(today - timedelta(days=delta))
    if re.search(r"(?<!\w)today(?!\w)", message_lower):
        dates.append(today)
    if re.search(r"(?<!\w)yesterday(?!\w)", message_lower):
        dates.append(today - timedelta(days=1))
    return sorted(set(dates))


def _requested_named_dates(message_lower: str, today: date) -> list[dict[str, str]]:
    named_dates: list[dict[str, str]] = []
    seen: set[tuple[str, date]] = set()
    for name, weekday in _WEEKDAY_INDEX.items():
        if not re.search(r"(?<!\w)" + name + r"(?!\w)", message_lower):
            continue
        delta = (today.weekday() - weekday) % 7
        target = today - timedelta(days=delta)
        key = (name, target)
        if key in seen:
            continue
        seen.add(key)
        named_dates.append({"label": name.title(), "date": target.isoformat()})
    if re.search(r"(?<!\w)today(?!\w)", message_lower):
        key = ("today", today)
        if key not in seen:
            seen.add(key)
            named_dates.append({"label": "today", "date": today.isoformat()})
    if re.search(r"(?<!\w)yesterday(?!\w)", message_lower):
        target = today - timedelta(days=1)
        key = ("yesterday", target)
        if key not in seen:
            seen.add(key)
            named_dates.append({"label": "yesterday", "date": target.isoformat()})
    return named_dates


def _nutrition_date_window(
    kind: str,
    today: date,
    message: str = "",
) -> tuple[date, date]:
    if kind == "date_range_yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if kind == "date_range_named_days":
        dates = _mentioned_weekday_dates((message or "").lower(), today)
        if dates:
            return min(dates), max(dates)
    if kind in {"date_range_week", "pattern_mining", "body_composition"}:
        return today - timedelta(days=6), today
    return today, today


def _nutrition_entry_row(entry: NutritionEntry) -> dict[str, Any]:
    return {
        "date": entry.date.isoformat() if entry.date else None,
        "entry_type": entry.entry_type or "daily",
        "notes": (entry.notes or "")[:100],
        "calories": round(float(entry.calories or 0)),
        "protein_g": round(float(entry.protein_g or 0)),
        "carbs_g": round(float(entry.carbs_g or 0)),
        "fat_g": round(float(entry.fat_g or 0)),
        "caffeine_mg": round(float(entry.caffeine_mg or 0)),
        "fluid_ml": round(float(entry.fluid_ml or 0)),
        "macro_source": entry.macro_source,
        "linked_activity_id": str(entry.activity_id) if entry.activity_id else None,
    }


def _nutrition_response_guidance(kind: str) -> str:
    if kind == "date_range_named_days":
        return (
            "Answer from the logged nutrition rows, name each requested day explicitly, "
            "compare the named days when more than one is requested, and preserve any "
            "training, lifting, recovery, race, or body-composition linkage the athlete "
            "explicitly included in the question."
        )
    if kind in {
        "current_log",
        "date_range_yesterday",
        "date_range_week",
    }:
        return (
            "Answer from the logged nutrition rows, but preserve any training, "
            "lifting, recovery, race, or body-composition linkage the athlete "
            "explicitly included in the question."
        )
    if kind == "pattern_mining":
        return (
            "Look for compact nutrition patterns, but name the limits of the "
            "logged window before making any training linkage."
        )
    if kind == "body_composition":
        return (
            "Tie nutrition to the body-composition goal only as far as the logged "
            "window supports; do not imply unlogged intake is known."
        )
    return (
        "Use the nutrition slice for the athlete's fueling question and avoid "
        "unrelated context unless it changes the fueling decision."
    )


def _summarize_nutrition_entries(
    entries: list[NutritionEntry],
    *,
    today: date,
) -> dict[str, Any]:
    by_date: dict[str, dict[str, float]] = {}
    for entry in entries:
        if not entry.date:
            continue
        key = entry.date.isoformat()
        totals = by_date.setdefault(
            key,
            {
                "calories": 0.0,
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fat_g": 0.0,
                "caffeine_mg": 0.0,
                "fluid_ml": 0.0,
                "entry_count": 0.0,
            },
        )
        totals["calories"] += float(entry.calories or 0)
        totals["protein_g"] += float(entry.protein_g or 0)
        totals["carbs_g"] += float(entry.carbs_g or 0)
        totals["fat_g"] += float(entry.fat_g or 0)
        totals["caffeine_mg"] += float(entry.caffeine_mg or 0)
        totals["fluid_ml"] += float(entry.fluid_ml or 0)
        totals["entry_count"] += 1

    def rounded(values: dict[str, float]) -> dict[str, Any]:
        return {
            "calories": round(values.get("calories", 0)),
            "protein_g": round(values.get("protein_g", 0)),
            "carbs_g": round(values.get("carbs_g", 0)),
            "fat_g": round(values.get("fat_g", 0)),
            "caffeine_mg": round(values.get("caffeine_mg", 0)),
            "fluid_ml": round(values.get("fluid_ml", 0)),
            "entry_count": int(values.get("entry_count", 0)),
            "is_complete_day_total": False,
        }

    normalized_by_date = {
        day: rounded(values) for day, values in sorted(by_date.items(), reverse=True)
    }
    today_key = today.isoformat()
    today_totals = normalized_by_date.get(
        today_key,
        {
            "calories": 0,
            "protein_g": 0,
            "carbs_g": 0,
            "fat_g": 0,
            "caffeine_mg": 0,
            "fluid_ml": 0,
            "entry_count": 0,
            "is_complete_day_total": False,
        },
    )
    return {
        "today": {"date": today_key, **today_totals},
        "by_date": normalized_by_date,
    }


def _bounded_nutrition_context_entries(
    entries: list[NutritionEntry],
    *,
    kind: str,
) -> list[NutritionEntry]:
    ordered = sorted(
        entries,
        key=lambda entry: (
            entry.date or date.min,
            entry.created_at or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    if kind != "date_range_named_days":
        return ordered[:NUTRITION_CONTEXT_ENTRY_LIMIT]

    dates = sorted({entry.date for entry in ordered if entry.date}, reverse=True)
    if not dates:
        return ordered[:NUTRITION_CONTEXT_ENTRY_LIMIT]
    per_date_limit = max(1, NUTRITION_CONTEXT_ENTRY_LIMIT // len(dates))
    selected: list[NutritionEntry] = []
    selected_ids: set[Any] = set()
    for target_date in dates:
        day_entries = [entry for entry in ordered if entry.date == target_date]
        for entry in day_entries[:per_date_limit]:
            selected.append(entry)
            selected_ids.add(entry.id)
    if len(selected) < NUTRITION_CONTEXT_ENTRY_LIMIT:
        for entry in ordered:
            if entry.id in selected_ids:
                continue
            selected.append(entry)
            if len(selected) >= NUTRITION_CONTEXT_ENTRY_LIMIT:
                break
    return selected[:NUTRITION_CONTEXT_ENTRY_LIMIT]


def build_nutrition_context_state(
    *,
    athlete_id: UUID,
    db: Session | None,
    message: str,
    now_utc: datetime | None = None,
) -> dict[str, Any] | None:
    kind = _detect_nutrition_context_kind(message)
    if kind is None:
        return None

    generated_at = _utc_now_iso()
    if db is None:
        return {
            "schema_version": "coach_runtime_v2.nutrition_context.v1",
            "status": "unavailable",
            "generated_at": generated_at,
            "data": {
                "query_type": kind,
                "response_guidance": _nutrition_response_guidance(kind),
                "coverage": {
                    "entries_found": 0,
                    "entries_returned": 0,
                    "interpretation": "nutrition_db_unavailable",
                },
                "entries": [],
                "known_limitations": ["Nutrition database session unavailable."],
            },
            "unknowns": [
                {
                    "field": "nutrition_log",
                    "reason": "db_unavailable",
                    "suggested_question": "What did you eat, and when did you eat it?",
                }
            ],
            "provenance": [],
        }

    try:
        tz_name = get_athlete_timezone_from_db(db, athlete_id)
        today = athlete_local_today(tz_name, now_utc=now_utc)
        start_date, end_date = _nutrition_date_window(kind, today, message)
        base_query = db.query(NutritionEntry).filter(
            NutritionEntry.athlete_id == athlete_id,
            NutritionEntry.date >= start_date,
            NutritionEntry.date <= end_date,
        )
        summary_entries = (
            base_query
            .order_by(NutritionEntry.date.desc(), NutritionEntry.created_at.desc())
            .all()
        )
        entries_found = len(summary_entries)
        entries = _bounded_nutrition_context_entries(summary_entries, kind=kind)
        summary = _summarize_nutrition_entries(summary_entries, today=today)
        coverage = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "entries_found": entries_found,
            "entries_returned": len(entries),
            "entry_limit": NUTRITION_CONTEXT_ENTRY_LIMIT,
            "interpretation": "partial_logs_additive_not_complete_day_total",
        }
        if kind == "date_range_named_days":
            coverage["requested_named_dates"] = _requested_named_dates(
                message_lower, today
            )
        data = {
            "query_type": kind,
            "response_guidance": _nutrition_response_guidance(kind),
            "coverage": coverage,
            "today": summary["today"],
            "by_date": summary["by_date"],
            "entries": [_nutrition_entry_row(entry) for entry in entries],
            "known_limitations": [
                "Nutrition entries are logged-so-far records, not proof of full-day intake.",
                "Unlogged food is not visible in this slice.",
            ],
        }
        return {
            "schema_version": "coach_runtime_v2.nutrition_context.v1",
            "status": "complete",
            "generated_at": generated_at,
            "data": data,
            "unknowns": [],
            "provenance": [
                {
                    "field_path": "blocks.nutrition_context.data",
                    "source_system": "nutrition_entry",
                    "source_id": str(athlete_id),
                    "source_timestamp": generated_at,
                    "observed_at": generated_at,
                    "confidence": "high",
                    "derivation_chain": ["nutrition_entry.date_range_query"],
                }
            ],
        }
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        return {
            "schema_version": "coach_runtime_v2.nutrition_context.v1",
            "status": "unavailable",
            "generated_at": generated_at,
            "data": {
                "query_type": kind,
                "response_guidance": _nutrition_response_guidance(kind),
                "coverage": {
                    "entries_found": 0,
                    "entries_returned": 0,
                    "interpretation": "nutrition_lookup_failed",
                },
                "entries": [],
                "known_limitations": [f"Nutrition lookup failed: {type(exc).__name__}"],
            },
            "unknowns": [
                {
                    "field": "nutrition_log",
                    "reason": "lookup_failed",
                    "suggested_question": "What did you eat, and when did you eat it?",
                }
            ],
            "provenance": [],
        }


def _performance_pace_context_relevant(message: str, query_class: str) -> bool:
    lower = (message or "").lower()
    if query_class in {"race_planning", "interval_pace_question"}:
        return True

    def contains_phrase(term: str) -> bool:
        return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", lower))

    pace_or_intensity_terms = (
        "pace",
        "paces",
        "pace zone",
        "pace zones",
        "rpi",
        "threshold",
        "tempo",
        "interval",
        "repetition",
        "rep pace",
        "easy pace",
        "easy run",
        "marathon pace",
        "10k pace",
        "5k time",
        "sub 40",
        "sub-40",
        "39:30",
    )
    training_context_terms = (
        "workout",
        "session",
        "training",
        "too hard",
        "too easy",
        "intensity",
        "effort",
        "run today",
        "should i run",
    )
    return any(contains_phrase(term) for term in pace_or_intensity_terms) or (
        any(contains_phrase(term) for term in training_context_terms)
        and any(
            contains_phrase(term)
            for term in (
                "hard",
                "easy",
                "threshold",
                "tempo",
                "interval",
                "pace",
                "effort",
            )
        )
    )


def _compact_race_history(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for row in rows[:PERFORMANCE_PACE_HISTORY_LIMIT]:
        compact.append(
            {
                "distance": row.get("distance"),
                "time": row.get("time"),
                "time_seconds": row.get("time_seconds"),
                "date": row.get("date"),
                "is_race": row.get("is_race"),
            }
        )
    return compact


def build_performance_pace_context_state(
    *,
    athlete_id: UUID,
    db: Session | None,
    message: str,
    query_class: str,
) -> dict[str, Any] | None:
    if not _performance_pace_context_relevant(message, query_class):
        return None

    generated_at = _utc_now_iso()
    unavailable = {
        "schema_version": "coach_runtime_v2.performance_pace_context.v1",
        "status": "unavailable",
        "generated_at": generated_at,
        "data": {
            "query_type": query_class,
            "coverage": "unavailable",
            "rpi": None,
            "training_paces": {},
            "race_equivalents": {},
            "race_history": [],
            "response_guidance": (
                "If RPI pace anchors are unavailable, say exactly what is missing. "
                "Do not invent training or race paces."
            ),
        },
        "unknowns": [
            {
                "field": "pace_zones",
                "reason": "rpi_pace_context_unavailable",
                "suggested_question": "What recent race or time trial should anchor your paces?",
            }
        ],
        "provenance": [],
    }
    if db is None:
        return unavailable

    try:
        training = get_training_paces(db, athlete_id)
        predictions = get_race_predictions(db, athlete_id)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return unavailable

    training_data = training.get("data") if training.get("ok") else {}
    prediction_data = predictions.get("data") if predictions.get("ok") else {}
    rpi = training_data.get("rpi") or prediction_data.get("rpi")
    if not rpi:
        return unavailable

    return {
        "schema_version": "coach_runtime_v2.performance_pace_context.v1",
        "status": "complete",
        "generated_at": generated_at,
        "data": {
            "query_type": query_class,
            "coverage": "rpi_training_paces_and_race_equivalents",
            "rpi": rpi,
            "training_paces": training_data.get("paces") or {},
            "raw_seconds_per_mile": training_data.get("raw_seconds_per_mile") or {},
            "race_equivalents": prediction_data.get("predictions") or {},
            "race_history": _compact_race_history(
                list(prediction_data.get("race_history") or [])
            ),
            "response_guidance": (
                "RPI training paces and race equivalents are authoritative pace "
                "anchors for training intensity, workout execution, easy-run discipline, "
                "and race planning when present. Do not ask the athlete to provide "
                "pace zones just because the durable ledger field is empty. If the "
                "athlete says the RPI paces are stale, treat that as a correction and ask "
                "what changed."
            ),
        },
        "unknowns": [],
        "provenance": [
            {
                "field_path": "blocks.performance_pace_context.data",
                "source_system": "rpi_pace_services",
                "source_id": str(athlete_id),
                "source_timestamp": generated_at,
                "observed_at": generated_at,
                "confidence": "high",
                "derivation_chain": [
                    "athlete.rpi",
                    "get_training_paces",
                    "get_race_predictions",
                ],
            }
        ],
    }


def _athlete_facts_payload(db: Session | None, athlete_id: UUID) -> dict[str, Any]:
    if db is None:
        return {}
    try:
        payload = (
            get_ledger(db, athlete_id, create=False, redact_sensitive=True).payload
            or {}
        )
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _ledger_field_coverage(facts: dict[str, Any]) -> float:
    if not VALID_FACT_FIELDS:
        return 0.0
    populated = sum(
        1
        for field in VALID_FACT_FIELDS
        if (facts.get(field) or {}).get("value") is not None
    )
    return round(populated / len(VALID_FACT_FIELDS), 3)


def _trim_v2_data_to_budget(data: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    """Fit packet data under budget while preserving the current athlete turn."""

    omitted: list[dict[str, Any]] = []

    def estimate() -> int:
        return _estimated_tokens(data)

    def record(block: str, reason: str) -> None:
        omitted.append({"block": block, "reason": reason})

    token_estimate = estimate()
    conversation = data.get("conversation") or {}
    recent_context = list(conversation.get("recent_context") or [])
    if token_estimate > PACKET_MAX_ESTIMATED_TOKENS and len(recent_context) > 2:
        conversation["recent_context"] = recent_context[-2:]
        record("conversation.recent_context", "trimmed_to_last_2_for_packet_budget")
        token_estimate = estimate()
    if token_estimate > PACKET_MAX_ESTIMATED_TOKENS and conversation.get(
        "recent_context"
    ):
        conversation["recent_context"] = []
        record("conversation.recent_context", "omitted_for_packet_budget")
        token_estimate = estimate()

    recent_activities = data.get("recent_activities") or {}
    activity_rows = list(recent_activities.get("recent_activities") or [])
    if token_estimate > PACKET_MAX_ESTIMATED_TOKENS and len(activity_rows) > 3:
        recent_activities["recent_activities"] = activity_rows[:3]
        record("recent_activities.recent_activities", "trimmed_to_3_for_packet_budget")
        token_estimate = estimate()
    activity_rows = list(recent_activities.get("recent_activities") or [])
    if token_estimate > PACKET_MAX_ESTIMATED_TOKENS and len(activity_rows) > 1:
        recent_activities["recent_activities"] = activity_rows[:1]
        record("recent_activities.recent_activities", "trimmed_to_1_for_packet_budget")
        token_estimate = estimate()

    activity_evidence = data.get("activity_evidence_state") or {}
    evidence_rows = list(activity_evidence.get("recent_activities") or [])
    if token_estimate > PACKET_MAX_ESTIMATED_TOKENS and evidence_rows:
        activity_evidence["recent_activities"] = []
        record(
            "activity_evidence_state.recent_activities",
            "omitted_duplicate_rows_for_packet_budget",
        )
        token_estimate = estimate()

    recent_threads = data.get("recent_threads") or []
    if token_estimate > PACKET_MAX_ESTIMATED_TOKENS and len(recent_threads) > 1:
        data["recent_threads"] = recent_threads[:1]
        record("recent_threads", "trimmed_to_1_for_packet_budget")
        token_estimate = estimate()

    return token_estimate, omitted


def _ledger_coverage_shim_threshold() -> float:
    return float(
        getattr(
            settings,
            "COACH_LEDGER_COVERAGE_SHIM_THRESHOLD",
            LEDGER_COVERAGE_SHIM_THRESHOLD,
        )
    )


def _conflict_suggested_question(conflict: PendingConflict) -> str:
    if conflict.field in SUGGESTED_QUESTIONS:
        return SUGGESTED_QUESTIONS[conflict.field]
    if conflict.field in SENSITIVE_FACT_FIELDS:
        return f"I have conflicting records for {conflict.field}. Which value is current?"
    return (
        f"Earlier you said {conflict.existing.get('value')} for {conflict.field}; "
        f"I just heard {conflict.proposed.get('value')}. Which is current?"
    )


def _serialize_pending_conflicts(
    pending_conflicts: list[PendingConflict] | None,
) -> list[dict[str, Any]]:
    serialized = []
    for conflict in pending_conflicts or []:
        sensitive = conflict.field in SENSITIVE_FACT_FIELDS
        existing_value = conflict.existing.get("value")
        proposed_value = conflict.proposed.get("value")
        if sensitive:
            existing_value = "[redacted]"
            proposed_value = "[redacted]"
        serialized.append(
            {
                "field": conflict.field,
                "existing_value": existing_value,
                "existing_confidence": conflict.existing.get("confidence"),
                "existing_asserted_at": conflict.existing.get("asserted_at"),
                "proposed_value": proposed_value,
                "proposed_confidence": conflict.proposed.get("confidence"),
                "proposed_source": conflict.proposed.get("source"),
                "suggested_question": _conflict_suggested_question(conflict),
            }
        )
    return serialized


def _relative_date(target: date, today: date) -> str:
    delta = (target - today).days
    if delta == 0:
        return "today"
    if delta == -1:
        return "yesterday"
    if delta == 1:
        return "tomorrow"
    if delta < 0:
        return f"{abs(delta)} days ago"
    return f"in {delta} days"


def _activity_is_race(activity: Activity) -> bool:
    return bool(
        getattr(activity, "user_verified_race", None) is True
        or getattr(activity, "is_race_candidate", None) is True
        or (getattr(activity, "workout_type", "") or "").lower() == "race"
    )


def _distance_miles(activity: Activity) -> float | None:
    if getattr(activity, "distance_m", None) is None:
        return None
    return float(activity.distance_m) / 1609.344


def _pace_seconds_per_mile(activity: Activity) -> float | None:
    distance_miles = _distance_miles(activity)
    duration_s = getattr(activity, "duration_s", None)
    if not distance_miles or not duration_s or distance_miles <= 0:
        return None
    return float(duration_s) / distance_miles


def _pace_display(seconds_per_mile: float | None) -> str | None:
    if seconds_per_mile is None:
        return None
    total = int(round(seconds_per_mile))
    return f"{total // 60}:{total % 60:02d}/mi"


def _parse_activity_classification_override(message: str) -> dict[str, Any] | None:
    lower = (message or "").lower()
    if "race" not in lower or not any(
        term in lower for term in ("was", "label", "tag", "3.1", "5k")
    ):
        return None

    target_distance_m = None
    distance_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mile|mi|miler)", lower)
    if distance_match:
        target_distance_m = round(float(distance_match.group(1)) * 1609.344)
    elif "5k" in lower or "5 k" in lower:
        target_distance_m = 5000

    return {
        "classification": "race_effort",
        "reason": "athlete_same_turn_correction",
        "target_distance_m": target_distance_m,
        "scope": "current_turn",
    }


def _activity_matches_override(
    activity: Activity, override: dict[str, Any] | None
) -> bool:
    if not override:
        return False
    target_distance_m = override.get("target_distance_m")
    if target_distance_m is None:
        return True
    distance_m = getattr(activity, "distance_m", None)
    if distance_m is None:
        return False
    return abs(float(distance_m) - float(target_distance_m)) <= 900


def _classify_activity_hardness(
    activity: Activity,
    *,
    effort_class: str | None,
    override: dict[str, Any] | None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    pace_s_mile = _pace_seconds_per_mile(activity)
    distance_m = float(getattr(activity, "distance_m", 0) or 0)
    duration_s = float(getattr(activity, "duration_s", 0) or 0)
    workout_type = (getattr(activity, "workout_type", None) or "").lower()
    name = (getattr(activity, "name", None) or "").lower()
    intensity_score = getattr(activity, "intensity_score", None)

    if _activity_matches_override(activity, override):
        return "race_effort", ["athlete_same_turn_override"]

    if _activity_is_race(activity):
        return "race_effort", ["race_flag"]

    if pace_s_mile is not None and 4500 <= distance_m <= 5600 and duration_s <= 1500:
        return "race_effort", ["5k_distance_fast_duration"]

    if pace_s_mile is not None and duration_s <= 900 and pace_s_mile <= 430:
        return "short_fast", ["short_fast_pace_duration"]

    if workout_type in {
        "threshold",
        "threshold_run",
        "tempo_run",
        "tempo",
        "threshold_intervals",
    }:
        return "threshold", ["workout_type_threshold"]

    if effort_class == "hard":
        reasons.append("effort_classifier_hard")
        if pace_s_mile is not None and pace_s_mile <= 420:
            return "threshold", reasons + ["fast_average_pace"]
        return "hard", reasons

    if intensity_score is not None:
        if float(intensity_score) >= 70:
            return "hard", ["intensity_score_high"]
        if float(intensity_score) >= 55:
            return "threshold", ["intensity_score_moderate_high"]

    if effort_class == "moderate":
        return "moderate", ["effort_classifier_moderate"]

    if any(term in name for term in ("tempo", "threshold", "race", "5k")):
        return "moderate", ["name_signal_weak"]

    return "easy", ["default_easy"]


def _split_pace_seconds_per_mile(split: ActivitySplit) -> float | None:
    distance_m = float(getattr(split, "distance", 0) or 0)
    time_s = getattr(split, "moving_time", None) or getattr(split, "elapsed_time", None)
    if distance_m <= 0 or not time_s:
        return None
    return float(time_s) / (distance_m / 1609.344)


def _build_execution_quality(
    activity: Activity,
    *,
    db: Session | None,
    same_turn_execution_override: dict[str, Any] | None,
) -> dict[str, Any]:
    if same_turn_execution_override and _activity_matches_override(
        activity, same_turn_execution_override
    ):
        return {
            "status": same_turn_execution_override["status"],
            "confidence": "high",
            "source": "athlete_same_turn_correction",
            "split_count": None,
            "pace_decay_pct": None,
            "can_claim_controlled": False,
            "must_ask_followup": False,
            "evidence": same_turn_execution_override["evidence"],
        }

    if db is None:
        return {
            "status": "unknown",
            "confidence": "low",
            "source": "missing_db",
            "split_count": 0,
            "pace_decay_pct": None,
            "can_claim_controlled": False,
            "must_ask_followup": True,
            "evidence": "No split evidence available.",
        }

    try:
        splits = (
            db.query(ActivitySplit)
            .filter(ActivitySplit.activity_id == activity.id)
            .order_by(ActivitySplit.split_number.asc())
            .all()
        )
    except Exception:
        splits = []

    paces = [
        pace
        for pace in (_split_pace_seconds_per_mile(split) for split in splits or [])
        if pace is not None
    ]
    if len(paces) < 2:
        return {
            "status": "unknown",
            "confidence": "low",
            "source": "insufficient_splits",
            "split_count": len(paces),
            "pace_decay_pct": None,
            "can_claim_controlled": False,
            "must_ask_followup": True,
            "evidence": "Split evidence is insufficient; ask how the effort went after checking available activity data.",
        }

    mid = len(paces) // 2
    first_half = sum(paces[:mid]) / len(paces[:mid])
    second_half = sum(paces[mid:]) / len(paces[mid:])
    decay_pct = ((second_half - first_half) / first_half) * 100 if first_half else 0
    if decay_pct > 6:
        status = "pacing_suffered"
        can_claim_controlled = False
    elif decay_pct > 3:
        status = "late_fade"
        can_claim_controlled = False
    elif decay_pct >= -3:
        status = "even_pacing"
        can_claim_controlled = True
    else:
        status = "negative_split"
        can_claim_controlled = True

    return {
        "status": status,
        "confidence": "medium",
        "source": "activity_splits",
        "split_count": len(paces),
        "pace_decay_pct": round(decay_pct, 1),
        "can_claim_controlled": can_claim_controlled,
        "must_ask_followup": False,
        "evidence": (
            f"First-half average {_pace_display(first_half)}, second-half average "
            f"{_pace_display(second_half)}, decay {decay_pct:+.1f}%."
        ),
    }


def _parse_execution_quality_override(message: str) -> dict[str, Any] | None:
    lower = (message or "").lower()
    negative_terms = (
        "wasn't controlled",
        "was not controlled",
        "not controlled",
        "pacing suffered",
        "pacing fell apart",
        "blew up",
        "faded",
        "didn't have a good go",
        "did not have a good go",
        "bad race",
        "went badly",
    )
    if not any(term in lower for term in negative_terms):
        return None

    activity_override = _parse_activity_classification_override(message) or {}
    return {
        "status": "athlete_reported_pacing_suffered",
        "reason": "athlete_same_turn_correction",
        "target_distance_m": activity_override.get("target_distance_m"),
        "scope": "current_turn",
        "evidence": message,
    }


def _override_value(value: Any, *, duration: str) -> dict[str, Any]:
    return {
        "value": value,
        "duration": duration,
    }


def _unwrap_override_value(override_value: Any) -> Any:
    if isinstance(override_value, dict) and "value" in override_value:
        return override_value.get("value")
    return override_value


def _activity_summary(
    activity: Activity, *, today: date, athlete_tz: Any
) -> dict[str, Any]:
    local_date = to_activity_local_date(activity, athlete_tz)
    return {
        "activity_id": str(activity.id),
        "date": local_date.isoformat(),
        "relative_date": _relative_date(local_date, today),
        "sport": getattr(activity, "sport", None),
        "name": getattr(activity, "name", None),
        "workout_type": getattr(activity, "workout_type", None),
        "distance_m": (
            int(activity.distance_m) if activity.distance_m is not None else None
        ),
        "is_race": _activity_is_race(activity),
        "race_confidence": (
            float(activity.race_confidence)
            if activity.race_confidence is not None
            else None
        ),
    }


def build_activity_evidence_state(
    *,
    athlete_id: UUID,
    db: Session | None,
    calendar_context: dict[str, Any],
    activity_override: dict[str, Any] | None,
    execution_override: dict[str, Any] | None,
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    today_local = (calendar_context.get("data") or {}).get("today_local")
    if db is None or not today_local:
        return {
            "schema_version": "coach_runtime_v2.activity_evidence.v1",
            "status": "unavailable",
            "generated_at": generated_at,
            "data": {
                "recent_activities": [],
                "yesterday": None,
                "activity_classification_override": activity_override,
                "execution_quality_override": execution_override,
            },
            "unknowns": [
                {
                    "reason": "service_unavailable",
                    "field": "activity_evidence",
                    "detail": "Database session or calendar context unavailable.",
                    "retryable": True,
                }
            ],
            "provenance": [],
        }

    try:
        athlete_tz = get_athlete_timezone_from_db(db, athlete_id)
        today = date.fromisoformat(today_local)
        activities = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
            )
            .order_by(Activity.start_time.desc())
            .limit(12)
            .all()
        )
    except Exception as exc:
        return {
            "schema_version": "coach_runtime_v2.activity_evidence.v1",
            "status": "unavailable",
            "generated_at": generated_at,
            "data": {
                "recent_activities": [],
                "yesterday": None,
                "activity_classification_override": activity_override,
                "execution_quality_override": execution_override,
            },
            "unknowns": [
                {
                    "reason": "service_unavailable",
                    "field": "activity_evidence",
                    "detail": exc.__class__.__name__,
                    "retryable": True,
                }
            ],
            "provenance": [],
        }

    effort_classes: dict[Any, str] = {}
    try:
        from services.effort_classification import classify_effort_bulk

        effort_classes = classify_effort_bulk(
            list(activities or []), str(athlete_id), db
        )
    except Exception:
        effort_classes = {}

    rows = []
    for activity in list(activities or []):
        try:
            local_date = to_activity_local_date(activity, athlete_tz)
            effort_class = effort_classes.get(activity.id)
            hardness, reasons = _classify_activity_hardness(
                activity,
                effort_class=effort_class,
                override=activity_override,
            )
            execution_quality = _build_execution_quality(
                activity,
                db=db,
                same_turn_execution_override=execution_override,
            )
            pace_s_mile = _pace_seconds_per_mile(activity)
            rows.append(
                {
                    "activity_id": str(activity.id),
                    "date": local_date.isoformat(),
                    "relative_date": _relative_date(local_date, today),
                    "name": getattr(activity, "name", None),
                    "distance_m": (
                        int(activity.distance_m)
                        if activity.distance_m is not None
                        else None
                    ),
                    "distance_mi": (
                        round(_distance_miles(activity), 2)
                        if _distance_miles(activity) is not None
                        else None
                    ),
                    "duration_s": (
                        int(activity.duration_s)
                        if activity.duration_s is not None
                        else None
                    ),
                    "pace_per_mile": _pace_display(pace_s_mile),
                    "pace_seconds_per_mile": (
                        round(pace_s_mile, 1) if pace_s_mile is not None else None
                    ),
                    "avg_hr": (
                        int(getattr(activity, "avg_hr"))
                        if getattr(activity, "avg_hr", None) is not None
                        else None
                    ),
                    "workout_type_label": getattr(activity, "workout_type", None),
                    "effort_class": effort_class,
                    "hardness": hardness,
                    "classification_reasons": reasons,
                    "execution_quality": execution_quality,
                    "is_race": hardness == "race_effort",
                    "source_label_is_authoritative": False,
                }
            )
        except Exception:
            continue

    yesterday = today - timedelta(days=1)
    yesterday_rows = [row for row in rows if row["date"] == yesterday.isoformat()]
    quality_hardness = {"race_effort", "threshold", "short_fast", "hard", "moderate"}
    yesterday_quality = [
        row for row in yesterday_rows if row["hardness"] in quality_hardness
    ]
    race_quality_rows = [
        row for row in yesterday_quality if row["hardness"] == "race_effort"
    ]
    execution_rows = [
        row["execution_quality"]
        for row in race_quality_rows
        if row.get("execution_quality")
    ]
    execution_negative = any(
        row["status"]
        in {"pacing_suffered", "late_fade", "athlete_reported_pacing_suffered"}
        for row in execution_rows
    )
    execution_unknown = any(row["status"] == "unknown" for row in execution_rows)
    can_claim_confidence = bool(execution_rows) and all(
        row.get("can_claim_controlled") for row in execution_rows
    )

    return {
        "schema_version": "coach_runtime_v2.activity_evidence.v1",
        "status": "complete",
        "generated_at": generated_at,
        "data": {
            "recent_activities": rows[:ACTIVITY_EVIDENCE_RECENT_ROWS_LIMIT],
            "activity_classification_override": activity_override,
            "execution_quality_override": execution_override,
            "yesterday": {
                "date": yesterday.isoformat(),
                "activity_count": len(yesterday_rows),
                "total_distance_mi": round(
                    sum((row.get("distance_mi") or 0) for row in yesterday_rows), 2
                ),
                "all_easy": bool(yesterday_rows) and not yesterday_quality,
                "race_effort_present": any(
                    row["hardness"] == "race_effort" for row in yesterday_rows
                ),
                "threshold_effort_present": any(
                    row["hardness"] == "threshold" for row in yesterday_rows
                ),
                "short_fast_effort_present": any(
                    row["hardness"] == "short_fast" for row in yesterday_rows
                ),
                "quality_effort_count": len(yesterday_quality),
                "race_execution_quality": {
                    "status": (
                        "negative"
                        if execution_negative
                        else (
                            "unknown"
                            if execution_unknown or not execution_rows
                            else (
                                "controlled_or_even"
                                if can_claim_confidence
                                else "mixed"
                            )
                        )
                    ),
                    "can_claim_controlled_or_confident": can_claim_confidence,
                    "must_ask_how_it_went": bool(
                        race_quality_rows
                        and (
                            execution_unknown
                            or not execution_rows
                            or not can_claim_confidence
                        )
                    ),
                    "forbidden_claims_without_more_evidence": (
                        [
                            "controlled",
                            "executed well",
                            "banked confidence",
                            "good go",
                            "sharpest tool in the box",
                        ]
                        if race_quality_rows and not can_claim_confidence
                        else []
                    ),
                    "evidence": execution_rows,
                },
                "quality_summary": [
                    {
                        "activity_id": row["activity_id"],
                        "distance_mi": row["distance_mi"],
                        "pace_per_mile": row["pace_per_mile"],
                        "hardness": row["hardness"],
                        "classification_reasons": row["classification_reasons"],
                        "execution_quality": row["execution_quality"],
                    }
                    for row in yesterday_quality
                ],
            },
        },
        "unknowns": [],
        "provenance": [
            {
                "field_path": "blocks.activity_evidence.data",
                "source_system": "deterministic_computation",
                "source_id": None,
                "source_timestamp": generated_at,
                "observed_at": generated_at,
                "confidence": "high",
                "derivation_chain": [
                    "Activity",
                    "effort_classification",
                    "pace_duration_rules",
                    "same_turn_activity_override",
                ],
            }
        ],
    }


def build_training_adaptation_context(
    *,
    calendar_context: dict[str, Any],
    activity_evidence: dict[str, Any],
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    calendar_data = calendar_context.get("data") or {}
    evidence_data = activity_evidence.get("data") or {}
    upcoming_race = calendar_data.get("upcoming_race") or {}
    days_until = upcoming_race.get("days_until_race")
    yesterday = evidence_data.get("yesterday") or {}
    race_effort = bool(yesterday.get("race_effort_present"))
    threshold_effort = bool(yesterday.get("threshold_effort_present"))
    short_fast = bool(yesterday.get("short_fast_effort_present"))
    quality_count = int(yesterday.get("quality_effort_count") or 0)
    race_execution = yesterday.get("race_execution_quality") or {}
    race_execution_status = race_execution.get("status")
    can_claim_confidence = bool(race_execution.get("can_claim_controlled_or_confident"))
    must_ask_how_it_went = bool(race_execution.get("must_ask_how_it_went"))
    close_to_target = isinstance(days_until, int) and 0 <= days_until <= 7

    if close_to_target and (race_effort or threshold_effort or short_fast):
        likely_effect = (
            "hard_stimulus_not_meaningful_new_fitness_before_target"
            if not can_claim_confidence
            else "sharpness_or_confidence_not_meaningful_new_fitness_before_target"
        )
        fitness_window = "mostly_after_target"
        fatigue_cost = "meaningful"
        recommendation_bias = (
            "ask_after_work_then_protect_freshness"
            if must_ask_how_it_went
            else "protect_freshness"
        )
    elif race_effort or threshold_effort or short_fast:
        likely_effect = "fitness_stimulus_possible_with_recovery_window"
        fitness_window = "future_adaptation_window_available"
        fatigue_cost = "meaningful"
        recommendation_bias = "absorb_before_next_quality"
    elif yesterday.get("all_easy"):
        likely_effect = "maintenance_volume"
        fitness_window = "minimal_new_fitness"
        fatigue_cost = "low"
        recommendation_bias = "continue_plan"
    else:
        likely_effect = "unknown"
        fitness_window = "unknown"
        fatigue_cost = "unknown"
        recommendation_bias = "ask_after_work"

    return {
        "schema_version": "coach_runtime_v2.training_adaptation.v1",
        "status": "complete",
        "generated_at": generated_at,
        "data": {
            "target_event_days_until": days_until,
            "target_event_name": upcoming_race.get("name"),
            "stimulus_window": "yesterday",
            "stimulus_event_mix": {
                "race_effort_present": race_effort,
                "threshold_effort_present": threshold_effort,
                "short_fast_effort_present": short_fast,
                "all_easy": bool(yesterday.get("all_easy")),
                "quality_effort_count": quality_count,
                "race_execution_quality": race_execution_status,
            },
            "likely_effect_before_target": likely_effect,
            "fatigue_cost": fatigue_cost,
            "fitness_adaptation_window": fitness_window,
            "recommendation_bias": recommendation_bias,
            "confidence_or_sharpness_claim_allowed": can_claim_confidence,
            "must_ask_execution_followup": must_ask_how_it_went,
            "ask_after_work_instruction": (
                "State the verified work first, then ask how the race actually went "
                "because execution quality is missing or negative. Do not infer "
                "controlled execution, confidence, or a good race from intensity alone."
                if must_ask_how_it_went
                else None
            ),
            "coach_interpretation": (
                "Close to a target race, yesterday quality was real stress, but "
                "meaningful new fitness is unlikely to arrive before the target. "
                "If execution quality is unknown or poor, ask how it went before "
                "claiming confidence or sharpness; manage fatigue and preserve freshness."
                if close_to_target and quality_count
                else None
            ),
        },
        "unknowns": [],
        "provenance": [
            {
                "field_path": "blocks.training_adaptation_context.data",
                "source_system": "deterministic_computation",
                "source_id": None,
                "source_timestamp": generated_at,
                "observed_at": generated_at,
                "confidence": "high" if days_until is not None else "medium",
                "derivation_chain": ["calendar_context", "activity_evidence"],
            }
        ],
    }


def build_calendar_context_state(
    *,
    athlete_id: UUID,
    db: Session | None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    generated_at = (
        now_utc.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        if now_utc
        else _utc_now_iso()
    )
    if db is None:
        return {
            "schema_version": "coach_runtime_v2.calendar_context.v1",
            "status": "unavailable",
            "generated_at": generated_at,
            "data": {
                "today_local": None,
                "today_has_completed_activity": None,
                "today_has_completed_race": None,
                "upcoming_race": None,
                "latest_completed_activity": None,
                "recent_activities": [],
            },
            "unknowns": [
                {
                    "reason": "service_unavailable",
                    "field": "calendar_context",
                    "detail": "Database session unavailable during packet assembly.",
                    "retryable": True,
                }
            ],
            "provenance": [],
        }

    try:
        athlete_tz = get_athlete_timezone_from_db(db, athlete_id)
        today = athlete_local_today(athlete_tz, now_utc=now_utc)
        active_plan = (
            db.query(TrainingPlan)
            .filter(
                TrainingPlan.athlete_id == athlete_id,
                TrainingPlan.status == "active",
                TrainingPlan.goal_race_date >= today,
            )
            .order_by(TrainingPlan.goal_race_date.asc())
            .first()
        )
        recent_activities = (
            db.query(Activity)
            .filter(Activity.athlete_id == athlete_id)
            .order_by(Activity.start_time.desc())
            .limit(8)
            .all()
        )
    except Exception as exc:
        return {
            "schema_version": "coach_runtime_v2.calendar_context.v1",
            "status": "unavailable",
            "generated_at": generated_at,
            "data": {
                "today_local": None,
                "today_has_completed_activity": None,
                "today_has_completed_race": None,
                "upcoming_race": None,
                "latest_completed_activity": None,
                "recent_activities": [],
            },
            "unknowns": [
                {
                    "reason": "service_unavailable",
                    "field": "calendar_context",
                    "detail": exc.__class__.__name__,
                    "retryable": True,
                }
            ],
            "provenance": [],
        }

    summaries = []
    for activity in list(recent_activities or []):
        try:
            summaries.append(
                _activity_summary(activity, today=today, athlete_tz=athlete_tz)
            )
        except Exception:
            continue

    today_summaries = [item for item in summaries if item["date"] == today.isoformat()]
    upcoming_race = None
    if active_plan and isinstance(getattr(active_plan, "goal_race_date", None), date):
        race_date = active_plan.goal_race_date
        upcoming_race = {
            "name": active_plan.goal_race_name or active_plan.name,
            "date": race_date.isoformat(),
            "distance_m": (
                int(active_plan.goal_race_distance_m)
                if active_plan.goal_race_distance_m is not None
                else None
            ),
            "days_until_race": (race_date - today).days,
            "is_today": race_date == today,
            "source": "training_plan",
            "plan_id": str(active_plan.id),
        }

    return {
        "schema_version": "coach_runtime_v2.calendar_context.v1",
        "status": "complete",
        "generated_at": generated_at,
        "data": {
            "today_local": today.isoformat(),
            "today_has_completed_activity": bool(today_summaries),
            "today_has_completed_race": any(
                item["is_race"] for item in today_summaries
            ),
            "upcoming_race": upcoming_race,
            "latest_completed_activity": summaries[0] if summaries else None,
            "recent_activities": summaries[:5],
            "temporal_authority": (
                "For dates, races, completed activities, and current-day status, "
                "this calendar_context block is authoritative. Do not infer temporal "
                "facts from legacy_context_bridge."
            ),
        },
        "unknowns": (
            []
            if upcoming_race
            else [
                {
                    "reason": "no_active_plan",
                    "field": "upcoming_race",
                    "detail": "No active future race plan found.",
                    "retryable": False,
                }
            ]
        ),
        "provenance": [
            {
                "field_path": "blocks.calendar_context.data",
                "source_system": "deterministic_computation",
                "source_id": None,
                "source_timestamp": generated_at,
                "observed_at": generated_at,
                "confidence": "high",
                "derivation_chain": ["TrainingPlan", "Activity", "athlete_timezone"],
            }
        ],
    }


def quiet_legacy_context_bridge(legacy_context: str) -> tuple[str, int]:
    kept_lines = []
    removed_count = 0
    for line in (legacy_context or "").splitlines():
        if _TEMPORAL_BRIDGE_PATTERN.search(line):
            removed_count += 1
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines).strip(), removed_count


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", "")
    if not re.fullmatch(r"-?\d+", cleaned):
        return None
    return int(cleaned)


def _parse_optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", "")
    if not re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
        return None
    return float(cleaned)


def parse_same_turn_table_evidence(message: str) -> dict[str, Any] | None:
    """Parse athlete-pasted Garmin lap tables into stable current-turn evidence."""

    rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    for line in (message or "").splitlines():
        parts = [part for part in re.split(r"\s+", line.strip()) if part]
        if len(parts) < 9:
            continue
        first = parts[0].strip()
        if first.isdigit():
            split_number = int(first)
            distance_mi = _parse_optional_float(parts[3])
            elevation_gain_ft = _parse_optional_int(parts[8])
            elevation_loss_ft = _parse_optional_int(parts[9] if len(parts) > 9 else None)
            rows.append(
                {
                    "split_number": split_number,
                    "split_time": parts[1],
                    "cumulative_time": parts[2],
                    "distance_mi": distance_mi,
                    "avg_pace": parts[4],
                    "grade_adjusted_pace": parts[5] if len(parts) > 5 else None,
                    "avg_hr": _parse_optional_int(parts[6] if len(parts) > 6 else None),
                    "max_hr": _parse_optional_int(parts[7] if len(parts) > 7 else None),
                    "elevation_gain_ft": elevation_gain_ft,
                    "elevation_loss_ft": elevation_loss_ft,
                }
            )
        elif first.lower() == "summary":
            summary = {
                "split_time": parts[1],
                "distance_mi": _parse_optional_float(parts[3]),
                "avg_pace": parts[4],
                "grade_adjusted_pace": parts[5] if len(parts) > 5 else None,
                "avg_hr": _parse_optional_int(parts[6] if len(parts) > 6 else None),
                "max_hr": _parse_optional_int(parts[7] if len(parts) > 7 else None),
                "total_elevation_gain_ft": _parse_optional_int(
                    parts[8] if len(parts) > 8 else None
                ),
                "total_elevation_loss_ft": _parse_optional_int(
                    parts[9] if len(parts) > 9 else None
                ),
            }

    if len(rows) < 2:
        return None
    gain_by_split = [
        row["elevation_gain_ft"]
        for row in rows
        if row.get("elevation_gain_ft") is not None
    ]
    if not gain_by_split:
        return None
    total_gain = summary.get("total_elevation_gain_ft")
    if total_gain is None:
        total_gain = sum(gain_by_split)
    max_gain_row = max(rows, key=lambda row: row.get("elevation_gain_ft") or -1)
    return {
        "schema_version": "coach_runtime_v2.same_turn_table_evidence.v1",
        "status": "parsed",
        "source": "athlete_pasted_current_turn",
        "table_type": "garmin_lap_splits",
        "column_interpretation": {
            "col_1": "split_number",
            "col_2": "split_time",
            "col_3": "cumulative_time",
            "col_4": "distance_mi",
            "col_5": "avg_pace",
            "col_6": "grade_adjusted_pace",
            "col_7": "avg_hr",
            "col_8": "max_hr",
            "col_9": "elevation_gain_ft",
            "col_10": "elevation_loss_ft",
        },
        "rows": rows,
        "summary": summary,
        "derived": {
            "gain_by_split_ft": gain_by_split,
            "total_elevation_gain_ft": total_gain,
            "max_gain_split_number": max_gain_row.get("split_number"),
            "max_gain_ft": max_gain_row.get("elevation_gain_ft"),
        },
    }


def _extract_gain_sequence(text: str) -> list[int]:
    if "gain by mile" not in (text or "").lower():
        return []
    values = [int(match) for match in re.findall(r"\b\d{1,3}\b", text or "")]
    return values[:12]


def _extract_total_gain_ft(text: str) -> int | None:
    lower = (text or "").lower()
    patterns = (
        r"\b(\d{2,4})\s*(?:feet|ft)\s+of\s+(?:gain|elevation)",
        r"\b(\d{2,4})\s*(?:feet|ft)\s+gain",
        r"\bgain(?:\s+and\s+loss)?\D{0,20}\b(\d{2,4})\s*(?:feet|ft)",
        r"\b(\d{2,4})\s*(?:feet|ft)\s+of\s+gain\s+and\s+loss",
    )
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            return int(match.group(1))
    return None


def _conversation_text(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("content") or "")
    return str(getattr(entry, "content", "") or "")


def _conversation_role(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("role") or "")
    return str(getattr(entry, "role", "") or "")


def _same_turn_table_evidence_from_context(
    message: str, conversation_context: list[dict[str, str]]
) -> dict[str, Any] | None:
    evidence = parse_same_turn_table_evidence(message)
    if evidence:
        return evidence

    latest_total_gain: int | None = _extract_total_gain_ft(message)
    latest_gain_sequence = _extract_gain_sequence(message)
    for entry in reversed(conversation_context or []):
        if _conversation_role(entry) != "user":
            continue
        text = _conversation_text(entry)
        evidence = parse_same_turn_table_evidence(text)
        if evidence:
            evidence = dict(evidence)
            evidence["source"] = "athlete_pasted_recent_context"
            return evidence
        if latest_total_gain is None:
            latest_total_gain = _extract_total_gain_ft(text)
        if not latest_gain_sequence:
            latest_gain_sequence = _extract_gain_sequence(text)

    if latest_total_gain is None and not latest_gain_sequence:
        return None
    return {
        "schema_version": "coach_runtime_v2.same_turn_table_evidence.v1",
        "status": "parsed_partial",
        "source": "athlete_stated_recent_context",
        "table_type": "course_elevation_correction",
        "column_interpretation": {},
        "rows": [],
        "summary": {},
        "derived": {
            "gain_by_split_ft": latest_gain_sequence,
            "total_elevation_gain_ft": latest_total_gain,
            "max_gain_split_number": (
                latest_gain_sequence.index(max(latest_gain_sequence)) + 1
                if latest_gain_sequence
                else None
            ),
            "max_gain_ft": max(latest_gain_sequence) if latest_gain_sequence else None,
        },
    }


def _sanitize_recent_context_for_v2(
    conversation_context: list[dict[str, str]],
    *,
    same_turn_table_evidence: dict[str, Any] | None,
) -> list[dict[str, str]]:
    recent_context = list(conversation_context[-8:])
    if not same_turn_table_evidence:
        return recent_context
    corrected_gain = (
        (same_turn_table_evidence.get("derived") or {}).get("total_elevation_gain_ft")
    )
    if not corrected_gain:
        return recent_context

    sanitized: list[dict[str, str]] = []
    for entry in recent_context:
        role = _conversation_role(entry)
        content = _conversation_text(entry)
        if role == "assistant":
            gain_claims = [
                int(match.group(1))
                for match in re.finditer(
                    r"\b(\d{2,4})\s*(?:ft|feet)\b.{0,30}\bgain\b",
                    content,
                    flags=re.IGNORECASE,
                )
            ]
            gain_claims.extend(
                int(match.group(1))
                for match in re.finditer(
                    r"\bgain\b.{0,30}\b(\d{2,4})\s*(?:ft|feet)\b",
                    content,
                    flags=re.IGNORECASE,
                )
            )
            if any(value != corrected_gain for value in gain_claims):
                continue
        sanitized.append(entry)
    return sanitized


def extract_same_turn_overrides(message: str) -> list[dict[str, Any]]:
    lower = (message or "").lower()
    extracted_at = _utc_now_iso()
    overrides: list[dict[str, Any]] = []
    activity_override = _parse_activity_classification_override(message)
    execution_override = _parse_execution_quality_override(message)

    patterns = (
        (
            "subjective_state.fatigue",
            ("i'm tired", "im tired", "i am tired", "fatigued", "exhausted"),
            "current_turn",
        ),
        (
            "subjective_state.pain",
            ("pain", "hurts", "sore", "niggle", "calf", "knee", "achilles"),
            "current_turn",
        ),
        (
            "correction.current_turn",
            ("that's wrong", "that is wrong", "not true", "actually", "you missed"),
            "current_turn",
        ),
        (
            "race_context.current_turn",
            ("race today", "race day", "racing today", "5k today", "marathon today"),
            "current_turn",
        ),
        (
            "standing_overrides.coaching_boundary",
            (
                "no population models",
                "don't operate on population models",
                "do not operate on population models",
                "no fueling advice",
                "don't give me fueling advice",
                "do not give me fueling advice",
                "only do trap bar deadlifts",
                "my recovery is much faster",
            ),
            "standing",
        ),
    )
    for field_path, triggers, duration in patterns:
        if any(trigger in lower for trigger in triggers):
            overrides.append(
                {
                    "field_path": field_path,
                    "override_value": _override_value(
                        {"athlete_statement": message},
                        duration=duration,
                    ),
                    "athlete_statement": message,
                    "extracted_at": extracted_at,
                    "extractor_version": "coach_same_turn_extractor_v2_0_a",
                    "confidence": "high",
                    "expires": duration,
                    "provenance": [
                        {
                            "field_path": field_path,
                            "source_system": "athlete_stated",
                            "source_id": None,
                            "source_timestamp": extracted_at,
                            "observed_at": extracted_at,
                            "confidence": "high",
                            "derivation_chain": ["same_turn_regex"],
                        }
                    ],
                }
            )
    if activity_override is not None:
        field_path = "activity_classification_override.recent_activity"
        overrides.append(
            {
                "field_path": field_path,
                "override_value": _override_value(
                    activity_override,
                    duration="current_turn",
                ),
                "athlete_statement": message,
                "extracted_at": extracted_at,
                "extractor_version": "coach_same_turn_extractor_v2_0_a",
                "confidence": "high",
                "expires": "current_turn",
                "provenance": [
                    {
                        "field_path": field_path,
                        "source_system": "athlete_stated",
                        "source_id": None,
                        "source_timestamp": extracted_at,
                        "observed_at": extracted_at,
                        "confidence": "high",
                        "derivation_chain": ["same_turn_activity_regex"],
                    }
                ],
            }
        )
    if execution_override is not None:
        field_path = "execution_quality_override.recent_activity"
        overrides.append(
            {
                "field_path": field_path,
                "override_value": _override_value(
                    execution_override,
                    duration="current_turn",
                ),
                "athlete_statement": message,
                "extracted_at": extracted_at,
                "extractor_version": "coach_same_turn_extractor_v2_0_a",
                "confidence": "high",
                "expires": "current_turn",
                "provenance": [
                    {
                        "field_path": field_path,
                        "source_system": "athlete_stated",
                        "source_id": None,
                        "source_timestamp": extracted_at,
                        "observed_at": extracted_at,
                        "confidence": "high",
                        "derivation_chain": ["same_turn_execution_quality_regex"],
                    }
                ],
            }
        )
    return overrides


def classify_conversation_mode(
    message: str, same_turn_overrides: list[dict[str, Any]]
) -> dict[str, Any]:
    lower = (message or "").lower()
    triggers: list[str] = []
    secondary: list[str] = []

    correction_present = any(
        o["field_path"].startswith("correction.") for o in same_turn_overrides
    )
    pain_present = any(
        o["field_path"] == "subjective_state.pain" for o in same_turn_overrides
    )
    fatigue_present = any(
        o["field_path"] == "subjective_state.fatigue" for o in same_turn_overrides
    )

    if correction_present:
        primary = "correction"
        triggers.append("same_turn_correction")
    elif pain_present and any(
        term in lower for term in ("should i run", "run today", "race", "workout")
    ):
        primary = "pushback"
        triggers.append("pain_with_training_decision")
    elif any(
        term in lower
        for term in (
            "race",
            "5k",
            "10k",
            "marathon",
            "half marathon",
            "taper",
            "pace plan",
            "goal pace",
        )
    ):
        primary = "racing_preparation_judgment"
        triggers.append("race_language")
    elif any(
        term in lower
        for term in (
            "not sure",
            "confused",
            "doesn't make sense",
            "why",
            "should i",
            "what should",
        )
    ):
        primary = "engage_and_reason"
        triggers.append("reasoning_or_decision_request")
    elif any(
        term in lower
        for term in ("pb", "pr", "personal best", "nailed", "crushed", "win")
    ):
        primary = "celebration"
        triggers.append("celebration_language")
    elif any(term in lower for term in ("quick", "status", "how am i doing", "check")):
        primary = "brief_status_update"
        triggers.append("brief_status_language")
    else:
        primary = "observe_and_ask"
        triggers.append("default")

    if fatigue_present and primary != "engage_and_reason":
        secondary.append("engage_and_reason")
    if primary == "pushback":
        secondary.append("engage_and_reason")

    return {
        "primary": primary,
        "secondary": list(dict.fromkeys(secondary)),
        "query_class": detect_query_class(message),
        "confidence": "high" if triggers != ["default"] else "medium",
        "source": "deterministic_mode_classifier",
        "classifier_version": MODE_CLASSIFIER_VERSION,
        "triggers": triggers,
        "pushback": {
            "present": primary == "pushback",
            "basis": (
                "evidence_backed" if primary == "pushback" and pain_present else "none"
            ),
            "hunch_direction": "none",
            "max_repetitions_this_issue": (
                2 if primary == "pushback" and pain_present else 0
            ),
            "repeated_pushback_count": 0,
        },
        "emotional_content": {
            "present": any(
                term in lower
                for term in ("frustrated", "scared", "anxious", "excited", "stressed")
            ),
            "valence": (
                "frustrated"
                if "frustrated" in lower
                else (
                    "anxious"
                    if "anxious" in lower
                    else "positive" if "excited" in lower else "neutral"
                )
            ),
            "intensity": (
                "medium"
                if any(
                    term in lower
                    for term in (
                        "frustrated",
                        "scared",
                        "anxious",
                        "excited",
                        "stressed",
                    )
                )
                else "low"
            ),
        },
        "screen_privacy": {
            "framing": (
                "direct"
                if any(
                    term in lower
                    for term in (
                        "body fat",
                        "dexa",
                        "blood",
                        "period",
                        "stress",
                        "relationship",
                    )
                )
                else "elsewhere"
            ),
            "effect": (
                "soften_display"
                if any(
                    term in lower
                    for term in (
                        "body fat",
                        "dexa",
                        "blood",
                        "period",
                        "stress",
                        "relationship",
                    )
                )
                else "none"
            ),
        },
        "unknowns": [],
        "provenance": [
            {
                "field_path": "conversation_mode.primary",
                "source_system": "deterministic_computation",
                "source_id": None,
                "source_timestamp": _utc_now_iso(),
                "observed_at": _utc_now_iso(),
                "confidence": "high" if triggers != ["default"] else "medium",
                "derivation_chain": ["same_turn_overrides", "message_regex_precedence"],
            }
        ],
    }


def assemble_v2_packet(
    *,
    athlete_id: UUID,
    db: Session | None = None,
    message: str,
    conversation_context: list[dict[str, str]],
    legacy_athlete_state: str,
    finding_id: str | None = None,
    now_utc: datetime | None = None,
    pending_conflicts: list[PendingConflict] | None = None,
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    same_turn_overrides = extract_same_turn_overrides(message)
    same_turn_table_evidence = _same_turn_table_evidence_from_context(
        message, conversation_context
    )
    sanitized_recent_context = _sanitize_recent_context_for_v2(
        conversation_context,
        same_turn_table_evidence=same_turn_table_evidence,
    )
    conversation_mode = classify_conversation_mode(message, same_turn_overrides)
    if conversation_mode["primary"] not in ARTIFACT5_MODES:
        raise V2PacketInvariantError(f"invalid_mode:{conversation_mode['primary']}")
    query_class = conversation_mode.get("query_class") or "general"

    calendar_context = build_calendar_context_state(
        athlete_id=athlete_id,
        db=db,
        now_utc=now_utc,
    )
    activity_override = next(
        (
            _unwrap_override_value(override["override_value"])
            for override in same_turn_overrides
            if override["field_path"]
            == "activity_classification_override.recent_activity"
        ),
        None,
    )
    execution_override = next(
        (
            _unwrap_override_value(override["override_value"])
            for override in same_turn_overrides
            if override["field_path"] == "execution_quality_override.recent_activity"
        ),
        None,
    )
    activity_evidence = build_activity_evidence_state(
        athlete_id=athlete_id,
        db=db,
        calendar_context=calendar_context,
        activity_override=activity_override,
        execution_override=execution_override,
    )
    training_adaptation_context = build_training_adaptation_context(
        calendar_context=calendar_context,
        activity_evidence=activity_evidence,
    )
    unknowns = compute_unknowns(
        db,
        athlete_id,
        query_class,
        now_utc=now_utc,
    )
    performance_pace_context = build_performance_pace_context_state(
        athlete_id=athlete_id,
        db=db,
        message=message,
        query_class=query_class,
    )
    if performance_pace_context and performance_pace_context["status"] == "complete":
        unknowns = [
            unknown for unknown in unknowns if unknown.get("field") != "pace_zones"
        ]
    serialized_pending_conflicts = _serialize_pending_conflicts(pending_conflicts)
    conflict_fields = {conflict["field"] for conflict in serialized_pending_conflicts}
    if conflict_fields:
        unknowns = [
            unknown for unknown in unknowns if unknown.get("field") not in conflict_fields
        ]
    athlete_facts = _athlete_facts_payload(db, athlete_id)
    ledger_field_coverage = _ledger_field_coverage(athlete_facts)
    recent_activities = (
        compute_recent_activities(db, athlete_id, now_utc=now_utc)
        if db is not None
        else _empty_recent_activities(generated_at)
    )
    recent_threads = (
        recent_threads_block(db, athlete_id)
        if db is not None
        else _empty_recent_threads()
    )
    nutrition_context = build_nutrition_context_state(
        athlete_id=athlete_id,
        db=db,
        message=message,
        now_utc=now_utc,
    )
    legacy_context, removed_temporal_lines_count = quiet_legacy_context_bridge(
        (legacy_athlete_state or "").strip()
    )
    shim_threshold = _ledger_coverage_shim_threshold()
    if ledger_field_coverage >= shim_threshold or not legacy_context:
        legacy_context = ""
    else:
        logger.warning(
            "coach_runtime_v2_legacy_context_shim_active",
            extra={
                "athlete_id": str(athlete_id),
                "ledger_field_coverage": ledger_field_coverage,
                "threshold": shim_threshold,
                "legacy_context_chars": len(legacy_context),
                "removed_temporal_lines_count": removed_temporal_lines_count,
            },
        )

    legacy_context_omitted_for_budget = False
    data = {
        "conversation": {
            "user_message": message,
            "recent_context": sanitized_recent_context,
            "finding_id": finding_id,
            "same_turn_table_evidence": same_turn_table_evidence,
        },
        "calendar_context": calendar_context["data"],
        "activity_evidence_state": activity_evidence["data"],
        "training_adaptation_context": training_adaptation_context["data"],
        "athlete_facts": athlete_facts,
        "recent_activities": recent_activities["data"],
        "recent_threads": recent_threads["recent_threads"],
        "unknowns": unknowns,
        "pending_conflicts": serialized_pending_conflicts,
        "_legacy_context_bridge_deprecated": {
            "legacy_context_bridge": legacy_context[:LEGACY_CONTEXT_BRIDGE_MAX_CHARS],
            "bridge_note": (
                "Deprecated shim only. Structured athlete_facts, recent_activities, "
                "recent_threads, unknowns, calendar_context, and current_turn are the "
                "primary athlete state. Empty when ledger coverage is at or above "
                f"{shim_threshold:.0%}."
            ),
            "removed_temporal_lines_count": removed_temporal_lines_count,
            "ledger_field_coverage": ledger_field_coverage,
        },
    }
    if nutrition_context is not None:
        data["nutrition_context"] = nutrition_context["data"]
    if performance_pace_context is not None:
        data["performance_pace_context"] = performance_pace_context["data"]
    token_estimate = _estimated_tokens(data)
    if token_estimate > PACKET_MAX_ESTIMATED_TOKENS and data[
        "_legacy_context_bridge_deprecated"
    ][
        "legacy_context_bridge"
    ]:
        data["_legacy_context_bridge_deprecated"]["legacy_context_bridge"] = ""
        legacy_context_omitted_for_budget = True
        token_estimate = _estimated_tokens(data)
    token_estimate, budget_omissions = _trim_v2_data_to_budget(data)
    packet = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "packet_id": str(uuid4()),
        "packet_profile": "coach_runtime_v2.visible_founder_v0",
        "assembler_version": ASSEMBLER_VERSION,
        "tier1_registry_version": "coach_runtime_v2.tier1.v1",
        "permission_policy_version": "coach_runtime_v2.permissions.v1",
        "generated_at": generated_at,
        "as_of": generated_at,
        "conversation_mode": conversation_mode,
        "athlete_stated_overrides": same_turn_overrides,
        "pending_conflicts": data["pending_conflicts"],
        "blocks": {
            "conversation": {
                "schema_version": "coach_runtime_v2.block.conversation.v1",
                "status": "complete",
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": [
                    "current_turn",
                    "recent_context",
                    "same_turn_table_evidence",
                ],
                "available_sections": [
                    "current_turn",
                    "recent_context",
                    "same_turn_table_evidence",
                ],
                "data": data["conversation"],
                "completeness": [],
                "unknowns": [],
                "provenance": [],
                "token_budget": {
                    "target_tokens": 250,
                    "max_tokens": 450,
                    "estimated_tokens": _estimated_tokens(data["conversation"]),
                },
            },
            "calendar_context": {
                "schema_version": "coach_runtime_v2.block.calendar_context.v1",
                "status": calendar_context["status"],
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": [
                    "today",
                    "upcoming_race",
                    "completed_activity_status",
                    "recent_activity_dates",
                ],
                "available_sections": [
                    "today",
                    "upcoming_race",
                    "completed_activity_status",
                    "recent_activity_dates",
                ],
                "data": data["calendar_context"],
                "completeness": [
                    {
                        "section": "calendar_context",
                        "status": calendar_context["status"],
                        "coverage_start": data["calendar_context"].get("today_local"),
                        "coverage_end": data["calendar_context"].get("today_local"),
                        "expected_window": "today plus active race plan and recent activities",
                        "detail": "Authoritative temporal/race block for V2.0-a coach responses.",
                    }
                ],
                "unknowns": calendar_context["unknowns"],
                "provenance": calendar_context["provenance"],
                "token_budget": {
                    "target_tokens": 350,
                    "max_tokens": 650,
                    "estimated_tokens": _estimated_tokens(data["calendar_context"]),
                },
            },
            "activity_evidence_state": {
                "schema_version": "coach_runtime_v2.block.activity_evidence.v1",
                "status": activity_evidence["status"],
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": [
                    "recent_activity_effort",
                    "yesterday_effort_mix",
                    "same_turn_activity_override",
                ],
                "available_sections": [
                    "recent_activity_effort",
                    "yesterday_effort_mix",
                    "same_turn_activity_override",
                ],
                "data": data["activity_evidence_state"],
                "completeness": [
                    {
                        "section": "activity_evidence",
                        "status": activity_evidence["status"],
                        "coverage_start": (
                            data["activity_evidence_state"].get("yesterday") or {}
                        ).get("date"),
                        "coverage_end": data["calendar_context"].get("today_local"),
                        "expected_window": "recent runs with yesterday grouped",
                        "detail": "Classifies activity effort from pace, duration, race flags, effort classifier output, and same-turn athlete corrections; labels alone are not authoritative.",
                    }
                ],
                "unknowns": activity_evidence["unknowns"],
                "provenance": activity_evidence["provenance"],
                "token_budget": {
                    "target_tokens": 650,
                    "max_tokens": 1000,
                    "estimated_tokens": _estimated_tokens(
                        data["activity_evidence_state"]
                    ),
                },
            },
            "training_adaptation_context": {
                "schema_version": "coach_runtime_v2.block.training_adaptation.v1",
                "status": training_adaptation_context["status"],
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": [
                    "recent_stimulus_interpretation",
                    "target_race_timing",
                    "recommendation_bias",
                ],
                "available_sections": [
                    "recent_stimulus_interpretation",
                    "target_race_timing",
                    "recommendation_bias",
                ],
                "data": data["training_adaptation_context"],
                "completeness": [
                    {
                        "section": "training_adaptation",
                        "status": training_adaptation_context["status"],
                        "coverage_start": (
                            data["activity_evidence_state"].get("yesterday") or {}
                        ).get("date"),
                        "coverage_end": data["calendar_context"].get("today_local"),
                        "expected_window": "recent stimulus against active target race",
                        "detail": "Deterministic physiology interpretation: what the recent effort likely changes before the target race.",
                    }
                ],
                "unknowns": training_adaptation_context["unknowns"],
                "provenance": training_adaptation_context["provenance"],
                "token_budget": {
                    "target_tokens": 300,
                    "max_tokens": 550,
                    "estimated_tokens": _estimated_tokens(
                        data["training_adaptation_context"]
                    ),
                },
            },
            "unknowns": {
                "schema_version": "coach_runtime_v2.block.unknowns.v1",
                "status": "complete",
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": ["required_ledger_fields"],
                "available_sections": ["required_ledger_fields"],
                "data": data["unknowns"],
                "completeness": [],
                "unknowns": data["unknowns"],
                "provenance": [
                    {
                        "field_path": "blocks.unknowns.data",
                        "source_system": "athlete_facts_ledger",
                        "source_id": str(athlete_id),
                        "source_timestamp": generated_at,
                        "observed_at": generated_at,
                        "confidence": "high",
                        "derivation_chain": [
                            "conversation_mode.query_class",
                            "unknowns_block.required_field_map",
                            "athlete_facts.confirm_after",
                        ],
                    }
                ],
                "token_budget": {
                    "target_tokens": 250,
                    "max_tokens": 450,
                    "estimated_tokens": _estimated_tokens(data["unknowns"]),
                },
            },
            "athlete_facts": {
                "schema_version": "coach_runtime_v2.block.athlete_facts.v1",
                "status": "complete" if data["athlete_facts"] else "partial",
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": ["athlete_fact_ledger"],
                "available_sections": ["athlete_fact_ledger"],
                "data": data["athlete_facts"],
                "completeness": [
                    {
                        "section": "athlete_fact_ledger",
                        "status": (
                            "complete"
                            if ledger_field_coverage >= shim_threshold
                            else "partial"
                        ),
                        "coverage_start": None,
                        "coverage_end": generated_at,
                        "expected_window": "durable athlete-stated and derived facts",
                        "detail": "Artifact 9 ledger facts; athlete_stated confidence wins over derived facts.",
                    }
                ],
                "unknowns": [],
                "provenance": [
                    {
                        "field_path": "blocks.athlete_facts.data",
                        "source_system": "athlete_facts_ledger",
                        "source_id": str(athlete_id),
                        "source_timestamp": generated_at,
                        "observed_at": generated_at,
                        "confidence": "high",
                        "derivation_chain": ["athlete_facts.payload"],
                    }
                ],
                "token_budget": {
                    "target_tokens": 900,
                    "max_tokens": 1600,
                    "estimated_tokens": _estimated_tokens(data["athlete_facts"]),
                },
            },
            "recent_activities": {
                "schema_version": recent_activities["schema_version"],
                "status": recent_activities["status"],
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": ["recent_activity_atoms", "four_week_aggregates"],
                "available_sections": ["recent_activity_atoms", "four_week_aggregates"],
                "data": data["recent_activities"],
                "completeness": [],
                "unknowns": recent_activities["unknowns"],
                "provenance": recent_activities["provenance"],
                "token_budget": {
                    **recent_activities["token_budget"],
                    "estimated_tokens": _estimated_tokens(data["recent_activities"]),
                },
            },
            **(
                {
                    "performance_pace_context": {
                        "schema_version": "coach_runtime_v2.block.performance_pace_context.v1",
                        "status": performance_pace_context["status"],
                        "generated_at": generated_at,
                        "as_of": generated_at,
                        "selected_sections": [
                            "rpi_training_paces",
                            "rpi_race_equivalents",
                            "recent_race_history",
                        ],
                        "available_sections": [
                            "training_paces",
                            "race_equivalents",
                            "race_history",
                        ],
                        "data": data["performance_pace_context"],
                        "completeness": [
                            {
                                "section": "performance_pace_context",
                                "status": performance_pace_context["status"],
                                "coverage_start": None,
                                "coverage_end": generated_at,
                                "expected_window": "current RPI plus training paces and recent verified race anchors",
                                "detail": "Authoritative RPI-derived pace/race-equivalent context for training intensity, workout execution, race planning, and pace-zone disputes.",
                            }
                        ],
                        "unknowns": performance_pace_context["unknowns"],
                        "provenance": performance_pace_context["provenance"],
                        "token_budget": {
                            "target_tokens": 350,
                            "max_tokens": 650,
                            "estimated_tokens": _estimated_tokens(
                                data["performance_pace_context"]
                            ),
                        },
                    }
                }
                if performance_pace_context is not None
                else {}
            ),
            **(
                {
                    "nutrition_context": {
                        "schema_version": "coach_runtime_v2.block.nutrition_context.v1",
                        "status": nutrition_context["status"],
                        "generated_at": generated_at,
                        "as_of": generated_at,
                        "selected_sections": [
                            "query_matched_nutrition_slice",
                            "date_range_totals",
                            "bounded_entries",
                        ],
                        "available_sections": [
                            "current_log",
                            "date_range_log",
                            "training_day_fueling",
                            "race_fueling",
                            "body_composition",
                            "pattern_mining",
                        ],
                        "data": data["nutrition_context"],
                        "completeness": [
                            {
                                "section": "nutrition_context",
                                "status": nutrition_context["status"],
                                "coverage_start": (
                                    (data["nutrition_context"] or {}).get("coverage")
                                    or {}
                                ).get("start_date"),
                                "coverage_end": (
                                    (data["nutrition_context"] or {}).get("coverage")
                                    or {}
                                ).get("end_date"),
                                "expected_window": "only the nutrition slice relevant to the athlete's latest question",
                                "detail": "Live nutrition rows are partial logged-so-far records, not complete-day proof.",
                            }
                        ],
                        "unknowns": nutrition_context["unknowns"],
                        "provenance": nutrition_context["provenance"],
                        "token_budget": {
                            "target_tokens": 450,
                            "max_tokens": 800,
                            "estimated_tokens": _estimated_tokens(
                                data["nutrition_context"]
                            ),
                        },
                    }
                }
                if nutrition_context is not None
                else {}
            ),
            "recent_threads": {
                "schema_version": recent_threads["schema_version"],
                "status": recent_threads["status"],
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": ["closed_thread_summaries"],
                "available_sections": ["closed_thread_summaries"],
                "data": data["recent_threads"],
                "completeness": [],
                "unknowns": [],
                "provenance": [
                    {
                        "field_path": "blocks.recent_threads.data",
                        "source_system": "coach_thread_summary",
                        "source_id": str(athlete_id),
                        "source_timestamp": generated_at,
                        "observed_at": generated_at,
                        "confidence": "high",
                        "derivation_chain": ["coach_thread_summary"],
                    }
                ],
                "token_budget": {
                    **recent_threads["token_budget"],
                    "estimated_tokens": _estimated_tokens(data["recent_threads"]),
                },
            },
            "_legacy_context_bridge_deprecated": {
                "schema_version": "coach_runtime_v2.block.legacy_context_bridge_deprecated.v1",
                "status": (
                    "empty"
                    if not data["_legacy_context_bridge_deprecated"][
                        "legacy_context_bridge"
                    ]
                    else "deprecated_fallback"
                ),
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": ["deprecated_legacy_context_bridge"],
                "available_sections": ["deprecated_legacy_context_bridge"],
                "data": data["_legacy_context_bridge_deprecated"],
                "completeness": [],
                "unknowns": [],
                "provenance": [
                    {
                        "field_path": "blocks._legacy_context_bridge_deprecated.data.legacy_context_bridge",
                        "source_system": "deterministic_computation",
                        "source_id": None,
                        "source_timestamp": generated_at,
                        "observed_at": generated_at,
                        "confidence": "low",
                        "derivation_chain": [
                            "AICoach._build_athlete_state_for_opus",
                            "deprecated_packet_shim",
                        ],
                    }
                ],
                "token_budget": {
                    "target_tokens": (
                        0
                        if not data["_legacy_context_bridge_deprecated"][
                            "legacy_context_bridge"
                        ]
                        else 600
                    ),
                    "max_tokens": (
                        0
                        if not data["_legacy_context_bridge_deprecated"][
                            "legacy_context_bridge"
                        ]
                        else 1200
                    ),
                    "estimated_tokens": _estimated_tokens(
                        data["_legacy_context_bridge_deprecated"]
                    ),
                },
            },
        },
        "omitted_blocks": budget_omissions,
        "telemetry": {
            "estimated_tokens": token_estimate,
            "packet_block_count": None,
            "omitted_block_count": len(budget_omissions),
            "unknown_count": (
                len(calendar_context["unknowns"])
                + len(activity_evidence["unknowns"])
                + len(training_adaptation_context["unknowns"])
                + len(recent_activities["unknowns"])
                + (len(nutrition_context["unknowns"]) if nutrition_context else 0)
                + (
                    len(performance_pace_context["unknowns"])
                    if performance_pace_context
                    else 0
                )
                + len(unknowns)
            ),
            "unknowns_count": len(unknowns),
            "permission_redaction_count": 0,
            "coupling_count": 1,
            "multimodal_attachment_count": 0,
            "temporal_bridge_lines_removed": removed_temporal_lines_count,
            "legacy_context_bridge_omitted_for_budget": (
                legacy_context_omitted_for_budget
            ),
            "ledger_field_coverage": ledger_field_coverage,
            "anchor_atoms_per_answer": None,
            "unasked_surfacing": None,
            "template_phrase_count": 0,
            "generic_fallback_count": 0,
            "model": None,
            "thinking": "disabled_for_kimi_k2_6",
            "voice_alignment_judge_score": None,
        },
    }
    if token_estimate > PACKET_MAX_ESTIMATED_TOKENS:
        raise V2PacketInvariantError("packet_token_budget_exceeded")
    packet["telemetry"]["packet_block_count"] = len(packet["blocks"])
    return packet


def _block_for_llm(block: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": block.get("status"),
        "data": block.get("data"),
        "unknowns": block.get("unknowns") or [],
    }


def _direct_nutrition_log_prompt(blocks: dict[str, Any]) -> bool:
    nutrition_data = ((blocks.get("nutrition_context") or {}).get("data") or {})
    if nutrition_data.get("query_type") != "current_log":
        return False
    conversation_data = ((blocks.get("conversation") or {}).get("data") or {})
    message = str(conversation_data.get("user_message") or "").lower()
    broader_context_terms = (
        "run",
        "ran",
        "running",
        "training",
        "workout",
        "lift",
        "lifting",
        "strength",
        "race",
        "recovery",
        "recover",
        "fatigue",
        "fueling",
        "fuel",
        "support",
        "last few days",
        "trend",
        "pattern",
        "compare",
        "different from",
        "similar",
        "block",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "yesterday",
    )
    return not any(term in message for term in broader_context_terms)


def _direct_performance_pace_prompt(blocks: dict[str, Any]) -> bool:
    if "performance_pace_context" not in blocks:
        return False
    conversation_data = ((blocks.get("conversation") or {}).get("data") or {})
    message = str(conversation_data.get("user_message") or "").lower()
    direct_pace_terms = (
        "what pace",
        "which pace",
        "pace should",
        "should i run",
        "threshold workout",
        "threshold pace",
        "tempo pace",
        "interval pace",
        "easy pace",
        "marathon pace",
    )
    return any(term in message for term in direct_pace_terms) and not any(
        term in message
        for term in (
            "too much",
            "too hard",
            "too easy",
            "should i run easy",
            "race",
        )
    )


def _scoped_conversation_block_for_llm(
    block: dict[str, Any],
    *,
    scope_note: str = "Use the current turn and scoped context only.",
) -> dict[str, Any]:
    compact = _block_for_llm(block)
    data = dict(compact.get("data") or {})
    data["recent_context"] = []
    data["scope_note"] = scope_note
    compact["data"] = data
    return compact


def _compact_packet_for_llm(packet: dict[str, Any]) -> dict[str, Any]:
    blocks = packet.get("blocks") or {}
    conversation_mode = dict(packet.get("conversation_mode") or {})
    conversation_mode.pop("provenance", None)
    direct_nutrition_log = _direct_nutrition_log_prompt(blocks)
    direct_performance_pace = _direct_performance_pace_prompt(blocks)
    if direct_nutrition_log:
        compact_blocks = {
            "conversation": _scoped_conversation_block_for_llm(
                blocks.get("conversation") or {},
                scope_note=(
                    "Direct nutrition-log answer: use the current turn and "
                    "nutrition_context only."
                ),
            ),
            "nutrition_context": _block_for_llm(blocks.get("nutrition_context") or {}),
        }
    elif direct_performance_pace:
        compact_blocks = {
            "conversation": _scoped_conversation_block_for_llm(
                blocks.get("conversation") or {},
                scope_note=(
                    "Direct pace answer: use the current turn and "
                    "performance_pace_context only."
                ),
            ),
            "performance_pace_context": _block_for_llm(
                blocks.get("performance_pace_context") or {}
            ),
        }
    else:
        compact_blocks = {
            key: _block_for_llm(block)
            for key, block in blocks.items()
            if key != "_legacy_context_bridge_deprecated"
        }
    return {
        "schema_version": packet.get("schema_version"),
        "packet_profile": packet.get("packet_profile"),
        "generated_at": packet.get("generated_at"),
        "conversation_mode": conversation_mode,
        "athlete_stated_overrides": packet.get("athlete_stated_overrides") or [],
        "pending_conflicts": packet.get("pending_conflicts") or [],
        "blocks": compact_blocks,
        "omitted_blocks": packet.get("omitted_blocks") or [],
        "prompt_scope": (
            "direct_nutrition_log_only"
            if direct_nutrition_log
            else (
                "direct_performance_pace_only"
                if direct_performance_pace
                else "full_compact"
            )
        ),
        "telemetry": {
            "estimated_tokens": (packet.get("telemetry") or {}).get(
                "estimated_tokens"
            ),
            "ledger_field_coverage": (packet.get("telemetry") or {}).get(
                "ledger_field_coverage"
            ),
            "unknowns_count": (packet.get("telemetry") or {}).get("unknowns_count"),
        },
    }


def _timeout_retry_packet_for_llm(packet: dict[str, Any]) -> dict[str, Any]:
    compact = _compact_packet_for_llm(packet)
    blocks = compact.get("blocks") or {}
    keep_blocks = {
        "conversation",
        "calendar_context",
        "activity_evidence_state",
        "training_adaptation_context",
        "athlete_facts",
        "nutrition_context",
        "performance_pace_context",
        "unknowns",
    }
    compact["blocks"] = {
        key: value for key, value in blocks.items() if key in keep_blocks
    }
    compact["timeout_retry_instruction"] = (
        "Use only this compact packet and the athlete's latest message. "
        "Answer directly; if key evidence is missing, say what is missing."
    )
    return compact


def packet_to_prompt(packet: dict[str, Any], *, profile: str = "compact") -> str:
    if profile == "timeout_retry":
        payload = _timeout_retry_packet_for_llm(packet)
    elif profile == "audit":
        payload = packet
    else:
        payload = _compact_packet_for_llm(packet)
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
