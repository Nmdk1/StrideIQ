#!/usr/bin/env python3
"""
Golden path automated check (viral-safe regression test).

This is intentionally a *runtime* check against a running local stack, using the real
athlete account, without creating test data.

Checks:
- Auth works
- Best-efforts status endpoint works (and includes ingestion_state)
- Queue a small best-efforts chunk and poll task status (optional if remaining > 0)
- PBs endpoint returns non-empty
- Coach suggestions and chat return a response containing at least one UUID + date
- Plan generator endpoint responds 200 (constraint-aware)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from typing import Any, Dict, Optional

import requests


UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")


def _req(method: str, url: str, token: Optional[str] = None, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {}) or {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    kwargs["headers"] = headers
    r = requests.request(method, url, **kwargs)
    return r


def _poll_task(base: str, token: str, task_id: str, timeout_s: int = 180) -> Dict[str, Any]:
    started = time.time()
    while time.time() - started < timeout_s:
        r = _req("GET", f"{base}/v1/tasks/{task_id}", token=token, timeout=30)
        r.raise_for_status()
        payload = r.json()
        if payload.get("status") in ("success", "error"):
            return payload
        time.sleep(2.0)
    return {"task_id": task_id, "status": "error", "error": "Timed out polling task"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.getenv("STRIDEIQ_BASE_URL", "http://localhost:8000"))
    # No defaults for credentials. Provide via env or explicit flags.
    parser.add_argument("--email", default=os.getenv("STRIDEIQ_EMAIL"))
    parser.add_argument(
        "--password-env",
        default="STRIDEIQ_PASSWORD",
        help="env var containing login password (default: STRIDEIQ_PASSWORD)",
    )
    parser.add_argument("--skip-best-efforts", action="store_true")
    parser.add_argument("--skip-coach", action="store_true")
    parser.add_argument("--skip-plan", action="store_true")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    if not args.email:
        raise SystemExit("ERROR: missing STRIDEIQ_EMAIL (or pass --email)")
    password = os.getenv(args.password_env)
    if not password:
        raise SystemExit(f"ERROR: missing env var {args.password_env} (login password)")

    # Auth
    r = _req(
        "POST",
        f"{base}/v1/auth/login",
        json={"email": args.email, "password": password},
        timeout=30,
    )
    r.raise_for_status()
    token = r.json()["access_token"]

    # Athlete profile (id)
    me = _req("GET", f"{base}/v1/athletes/me", token=token, timeout=30)
    me.raise_for_status()
    athlete_id = me.json()["id"]

    # Best-efforts status (includes ingestion_state)
    be = _req("GET", f"{base}/v1/athletes/{athlete_id}/best-efforts/status", token=token, timeout=30)
    be.raise_for_status()
    be_payload = be.json()
    assert be_payload.get("status") == "success"
    assert "best_efforts" in be_payload
    assert "ingestion_state" in be_payload

    remaining = int(be_payload["best_efforts"].get("remaining_activities", 0) or 0)

    # Queue a tiny chunk (only if there is remaining work)
    if (not args.skip_best_efforts) and remaining > 0:
        q = _req(
            "POST",
            f"{base}/v1/athletes/{athlete_id}/sync-best-efforts/queue",
            token=token,
            timeout=30,
        )
        q.raise_for_status()
        task_id = q.json()["task_id"]
        task = _poll_task(base, token, task_id, timeout_s=240)
        assert task.get("status") == "success", task

    # Personal bests should exist
    pbs = _req("GET", f"{base}/v1/athletes/{athlete_id}/personal-bests", token=token, timeout=30)
    pbs.raise_for_status()
    pb_list = pbs.json()
    assert isinstance(pb_list, list)
    assert len(pb_list) > 0

    # Coach: suggestions + one chat
    if not args.skip_coach:
        sugg = _req("GET", f"{base}/v1/coach/suggestions", token=token, timeout=60)
        sugg.raise_for_status()
        suggestions = sugg.json().get("suggestions") or []
        message = suggestions[0] if suggestions else "What was my freshest week recently? Cite your evidence."

        chat = _req(
            "POST",
            f"{base}/v1/coach/chat",
            token=token,
            json={"message": message, "include_context": True},
            timeout=180,
        )
        chat.raise_for_status()
        text = chat.json().get("response") or ""
        assert UUID_RE.search(text), "Coach response missing UUID citation"
        assert DATE_RE.search(text), "Coach response missing date"

    # Plan generator (constraint-aware) basic smoke
    if not args.skip_plan:
        plan = _req(
            "POST",
            f"{base}/v2/plans/constraint-aware",
            token=token,
            json={
                "race_date": "2026-03-15",
                "race_distance": "marathon",
                "race_name": "Golden Path Check",
                "tune_up_races": [],
            },
            timeout=180,
        )
        plan.raise_for_status()
        assert plan.status_code == 200

    print("GOLDEN PATH: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

