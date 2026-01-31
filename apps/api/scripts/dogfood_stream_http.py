"""
Dogfood: hit /v1/coach/chat/stream over HTTP and reconstruct deltas.

Goal:
- Prove the streamed response is not truncated (client-side parsing sanity).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import timedelta

import httpx

# Ensure /app is on path when executed in-container.
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete


def _parse_sse(stream_iter) -> tuple[str, dict]:
    """
    Very small SSE parser: accumulates delta payloads into full text.
    """
    buf = ""
    full = ""
    done_meta: dict = {}

    def handle_packet(packet: str) -> None:
        nonlocal full, done_meta
        # Collect all data: lines and parse JSON payload.
        data_lines = []
        for line in packet.splitlines():
            if line.startswith("data:"):
                v = line[5:]
                data_lines.append(v[1:] if v.startswith(" ") else v)
        data_str = "\n".join(data_lines).strip()
        if not data_str:
            return
        try:
            obj = json.loads(data_str)
        except Exception:
            return
        if obj.get("type") == "delta" and isinstance(obj.get("delta"), str):
            full += obj["delta"]
        if obj.get("type") == "done":
            done_meta = obj

    for chunk in stream_iter:
        if not chunk:
            continue
        buf += chunk.decode("utf-8", errors="replace")
        buf = buf.replace("\r\n", "\n")
        while True:
            idx = buf.find("\n\n")
            if idx == -1:
                break
            packet = buf[:idx]
            buf = buf[idx + 2 :]
            handle_packet(packet)

    # trailing packet without delimiter
    if buf.strip():
        handle_packet(buf.strip())

    return full, done_meta


def main() -> None:
    dogfood_email = os.environ.get("DOGFOOD_EMAIL")
    if not dogfood_email:
        raise RuntimeError("DOGFOOD_EMAIL environment variable not set")
    
    db = SessionLocal()
    try:
        athlete = db.query(Athlete).filter(Athlete.email == dogfood_email).first()
        if not athlete:
            raise RuntimeError(f"Athlete not found for {dogfood_email}")

        # Match auth router convention: sub is user id.
        token = create_access_token({"sub": str(athlete.id)}, expires_delta=timedelta(minutes=10))

        message = (
            "Today’s run was earlier than normal (4 am) due to a weather system moving in. "
            "It was the longest run I've done since coming back. I feel so slow — analyze and suggest adjustments."
        )

        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(base_url="http://localhost:8000", timeout=130.0, headers=headers) as client:
            with client.stream(
                "POST",
                "/v1/coach/chat/stream",
                json={"message": message, "include_context": True},
            ) as resp:
                resp.raise_for_status()
                text, meta = _parse_sse(resp.iter_bytes())

        print("done_meta=", meta)
        print("response_len=", len(text))
        print("----- STREAMED RESPONSE START -----")
        print(text)
        print("----- STREAMED RESPONSE END -----")
    finally:
        db.close()


if __name__ == "__main__":
    main()

