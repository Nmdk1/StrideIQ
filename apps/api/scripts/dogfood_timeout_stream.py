"""
Dogfood: Coach timeout + streaming readiness

This is a local verification script (not meant for production use).
"""

from __future__ import annotations

import asyncio
import sys

# Ensure /app is on path when executed in-container.
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from core.database import SessionLocal
from models import Athlete
from services.ai_coach import AICoach


def main() -> None:
    db = SessionLocal()
    try:
        athlete = db.query(Athlete).filter(Athlete.email == "mbshaf@gmail.com").first()
        if not athlete:
            raise RuntimeError("Athlete not found for mbshaf@gmail.com")

        coach = AICoach(db)
        message = (
            "Today’s run was earlier than normal (4 am) due to a weather system moving in. "
            "It was the longest run I've done since coming back. I feel so slow — analyze and suggest adjustments."
        )

        result = asyncio.run(coach.chat(athlete.id, message, include_context=True))
        print("timed_out=", bool(result.get("timed_out", False)))
        print("error=", bool(result.get("error", False)))
        print("thread_id=", result.get("thread_id"))
        print("response_len=", len(result.get("response") or ""))
        print("----- RESPONSE START -----")
        print(result.get("response") or "")
        print("----- RESPONSE END -----")
    finally:
        db.close()


if __name__ == "__main__":
    main()

