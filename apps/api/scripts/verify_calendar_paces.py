"""Verify calendar API returns coach_notes (paces) (debug script)."""

from __future__ import annotations

import os

import requests


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.getenv("STRIDEIQ_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--email", default=os.getenv("STRIDEIQ_EMAIL"))
    parser.add_argument("--password-env", default="STRIDEIQ_PASSWORD")
    parser.add_argument("--start", default="2026-01-13")
    parser.add_argument("--end", default="2026-01-17")
    args = parser.parse_args()

    if not args.email:
        print("ERROR: missing STRIDEIQ_EMAIL (or pass --email)")
        return 2
    password = os.getenv(args.password_env)
    if not password:
        print(f"ERROR: missing env var {args.password_env} (login password)")
        return 2

    base = args.base.rstrip("/")

    # Login
    resp = requests.post(
        f"{base}/v1/auth/login",
        json={"email": args.email, "password": password},
        timeout=30,
    )
    print(f"Login: {resp.status_code}")
    resp.raise_for_status()
    token = resp.json()["access_token"]

    # Get calendar
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        f"{base}/calendar",
        params={"start_date": args.start, "end_date": args.end},
        headers=headers,
        timeout=60,
    )

    data = resp.json()
    print(f"Calendar: {resp.status_code}")

    for day in data.get("days", []):
        pw = day.get("planned_workout")
        if not pw:
            continue
        print(f"\n{day['date']}: {pw.get('workout_type')} - {pw.get('title')}")
        notes = pw.get("coach_notes")
        if notes:
            print(f"  PACE: {notes}")
        else:
            print("  ERROR: coach_notes is MISSING!")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
