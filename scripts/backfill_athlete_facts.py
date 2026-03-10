"""
One-time backfill: extract facts from all historical CoachChat conversations.

Usage:
    python scripts/backfill_athlete_facts.py
    python scripts/backfill_athlete_facts.py --resume-from-chat-id <uuid>
    python scripts/backfill_athlete_facts.py --dry-run

Idempotent: safe to re-run. The upsert logic skips existing facts with
matching values. Processes chats in chronological order so supersession
is correct (later values override earlier ones).
"""
import argparse
import logging
import sys
from pathlib import Path
from uuid import UUID

# Ensure the API root is on sys.path so imports resolve.
api_root = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(api_root))

from core.database import SessionLocal  # noqa: E402
from models import CoachChat  # noqa: E402
from tasks.fact_extraction_task import ExtractionError, _run_extraction, _upsert_fact  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 50


def backfill(resume_from: str = None, dry_run: bool = False):
    db = SessionLocal()
    try:
        query = (
            db.query(CoachChat)
            .filter(CoachChat.messages.isnot(None))
            .order_by(CoachChat.created_at.asc(), CoachChat.id.asc())
        )

        if resume_from:
            resume_chat = db.query(CoachChat).filter(CoachChat.id == UUID(resume_from)).first()
            if not resume_chat:
                logger.error("Resume chat %s not found — aborting", resume_from)
                return
            # Deterministic tuple boundary: strictly after (created_at, id)
            query = query.filter(
                (CoachChat.created_at > resume_chat.created_at)
                | (
                    (CoachChat.created_at == resume_chat.created_at)
                    & (CoachChat.id > resume_chat.id)
                )
            )
            logger.info("Resuming from chat %s (created_at=%s)", resume_from, resume_chat.created_at)

        processed = 0
        skipped = 0
        facts_found = 0

        for chat in query.yield_per(BATCH_SIZE):
            user_messages = [m for m in chat.messages if m.get("role") == "user"]
            if not user_messages:
                skipped += 1
                continue

            user_text = "\n".join(m["content"] for m in user_messages)

            if dry_run:
                logger.info("[DRY RUN] Would extract from chat %s (%d user msgs)", chat.id, len(user_messages))
                processed += 1
                continue

            try:
                extracted = _run_extraction(user_text)
            except ExtractionError as ee:
                logger.error("Extraction failed for chat %s — skipping (no checkpoint advance): %s", chat.id, ee)
                skipped += 1
                continue

            for fact in extracted:
                _upsert_fact(db, chat.athlete_id, chat.id, fact)
                facts_found += 1

            chat.last_extracted_msg_count = len(chat.messages)
            processed += 1

            if processed % BATCH_SIZE == 0:
                db.commit()
                logger.info(
                    "Backfill checkpoint: %d chats processed, %d facts found, last chat_id=%s",
                    processed, facts_found, chat.id,
                )

        if not dry_run:
            db.commit()
        logger.info(
            "Backfill %s: %d chats processed, %d skipped, %d facts extracted",
            "complete" if not dry_run else "dry-run complete",
            processed, skipped, facts_found,
        )

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill athlete facts from coach chats")
    parser.add_argument("--resume-from-chat-id", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Log what would be processed without extracting")
    args = parser.parse_args()
    backfill(resume_from=args.resume_from_chat_id, dry_run=args.dry_run)
