"""
Celery task: extract structured facts from coach conversation messages.

Fires asynchronously after _save_chat_messages in ai_coach.py.
Processes only NEW messages since the last extraction checkpoint.
"""
import json
import logging
import os
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func

from tasks import celery_app
from core.database import SessionLocal
from models import AthleteFact, CoachChat

logger = logging.getLogger(__name__)

FACT_TTL_CATEGORIES = {
    "injury_history": 14,
    "current_symptoms": 14,
    "training_phase": 21,
    "equipment": 90,
    "strength_pr": 30,
}

EXTRACTION_PROMPT = """You are extracting structured facts from an athlete's messages to their running coach.

Extract any concrete, specific factual claims the athlete made about:
- Their body (weight, height, body composition, bone density, body fat %)
- Their strength (lift PRs, max weights, rep schemes)
- Their injury history (past injuries, current pain, recovery status)
- Their preferences (when they like to run, what they eat before runs, etc.)
- Their life context (age, occupation, years running, other sports)
- Their race history (PRs, recent race results, upcoming goals)
- Their health (resting heart rate, blood pressure, medications, etc.)
- Anything else specific and factual that would be useful coaching context

For each fact, return:
- fact_type: one of [body_composition, strength_pr, injury_history, current_symptoms, training_phase, equipment, preference, life_context, race_history, health, other]
- fact_key: a snake_case identifier (e.g., "dexa_bone_density_t_score", "deadlift_1rm_lbs")
- fact_value: the value as a string (e.g., "3.2", "315", "before 8am")
- numeric_value: the numeric value if applicable, else null
- source_excerpt: the exact quote from the athlete that contains this fact

Rules:
- Only extract facts the ATHLETE explicitly stated. Do not infer or deduce facts.
- Only extract concrete, specific facts. Do not extract opinions, feelings, or vague statements.
- If the athlete says "I deadlift around 300-315", use the higher value (315) and note the range in source_excerpt.
- Use consistent fact_key naming: lowercase snake_case, include units where relevant (e.g., _lbs, _in, _pct).
- If the same fact appears multiple times with different values, extract only the most recent/specific version.

Return as a JSON array. If no facts found, return [].
"""


class ExtractionError(Exception):
    """Raised when the LLM provider fails (not when it returns empty)."""


def _run_extraction(user_text: str) -> list:
    """
    Call Gemini to extract structured facts from athlete messages.

    Returns [] when the LLM finds no facts (legitimate empty).
    Raises ExtractionError on provider/parse failures so the caller
    can distinguish "nothing found" from "couldn't reach the model".
    """
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        raise ExtractionError("google-genai not installed")

    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        raise ExtractionError("GOOGLE_AI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    config = genai_types.GenerateContentConfig(
        temperature=0.1,
        response_mime_type="application/json",
    )
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=f"{EXTRACTION_PROMPT}\n\nATHLETE MESSAGES:\n{user_text}")],
                ),
            ],
            config=config,
        )
        raw = response.text.strip()
        facts = json.loads(raw)
        if not isinstance(facts, list):
            raise ExtractionError(f"Extraction returned non-list: {type(facts)}")
        return facts
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"LLM call failed: {e}") from e


def _upsert_fact(db, athlete_id: UUID, chat_id: UUID, extracted: dict):
    """
    Insert a new fact, superseding any existing fact with the same key.

    Uses a nested transaction (savepoint) so that an IntegrityError from the
    partial unique index does not rollback prior successful inserts in the
    same extraction run.
    """
    existing = (
        db.query(AthleteFact)
        .filter(
            AthleteFact.athlete_id == athlete_id,
            AthleteFact.fact_key == extracted["fact_key"],
            AthleteFact.is_active == True,  # noqa: E712
        )
        .first()
    )

    if existing:
        if existing.fact_value == extracted["fact_value"]:
            return
        existing.superseded_at = func.now()
        existing.is_active = False
        logger.info(
            "Superseding athlete fact %s: %s -> %s",
            extracted["fact_key"], existing.fact_value, extracted["fact_value"],
        )

    new_fact = AthleteFact(
        athlete_id=athlete_id,
        fact_type=extracted["fact_type"],
        fact_key=extracted["fact_key"],
        fact_value=extracted["fact_value"],
        numeric_value=extracted.get("numeric_value"),
        confidence="athlete_stated",
        source_chat_id=chat_id,
        source_excerpt=extracted["source_excerpt"],
        temporal=FACT_TTL_CATEGORIES.get(extracted["fact_type"]) is not None,
        ttl_days=FACT_TTL_CATEGORIES.get(extracted["fact_type"]),
    )

    try:
        with db.begin_nested():
            db.add(new_fact)
            db.flush()
    except IntegrityError:
        # Savepoint rolled back by context manager; parent transaction intact.
        winner = (
            db.query(AthleteFact)
            .filter(
                AthleteFact.athlete_id == athlete_id,
                AthleteFact.fact_key == extracted["fact_key"],
                AthleteFact.is_active == True,  # noqa: E712
            )
            .first()
        )
        if winner and winner.fact_value == extracted["fact_value"]:
            logger.debug("Concurrent insert resolved: same value, skipping %s", extracted["fact_key"])
        elif winner:
            logger.warning(
                "Concurrent insert conflict for %s: winner=%s, ours=%s — keeping winner",
                extracted["fact_key"], winner.fact_value, extracted["fact_value"],
            )


@celery_app.task(name="tasks.extract_athlete_facts", bind=True, max_retries=2)
def extract_athlete_facts(self, athlete_id: str, chat_id: str):
    """Extract structured facts from NEW messages in a coach conversation."""
    db = SessionLocal()
    try:
        chat = db.query(CoachChat).filter(CoachChat.id == UUID(chat_id)).first()
        if not chat or not chat.messages:
            return

        last_idx = chat.last_extracted_msg_count or 0
        all_messages = chat.messages or []

        if last_idx >= len(all_messages):
            return

        new_messages = all_messages[last_idx:]
        user_messages = [m for m in new_messages if m.get("role") == "user"]

        if not user_messages:
            chat.last_extracted_msg_count = len(all_messages)
            db.commit()
            return

        user_text = "\n".join(m["content"] for m in user_messages)

        try:
            extracted = _run_extraction(user_text)
        except ExtractionError as ee:
            # Provider failure — do NOT advance checkpoint so retry processes same messages.
            logger.error("Fact extraction provider failed for chat %s: %s", chat_id, ee)
            raise self.retry(exc=ee)

        for fact in extracted:
            _upsert_fact(db, UUID(athlete_id), UUID(chat_id), fact)

        chat.last_extracted_msg_count = len(all_messages)
        db.commit()

    except ExtractionError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error("Fact extraction failed for chat %s: %s", chat_id, e)
        raise self.retry(exc=e)
    finally:
        db.close()
