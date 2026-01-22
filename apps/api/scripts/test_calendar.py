"""Test calendar API to verify plan workouts appear (debug script)."""

from __future__ import annotations

import os

import requests


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.getenv("STRIDEIQ_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--email", default=os.getenv("STRIDEIQ_EMAIL"))
    parser.add_argument("--password-env", default="STRIDEIQ_PASSWORD")
    parser.add_argument("--start", default="2026-01-12")
    parser.add_argument("--end", default="2026-01-18")
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
    login_resp = requests.post(
        f"{base}/v1/auth/login",
        json={"email": args.email, "password": password},
        timeout=30,
    )
    print(f"Login: {login_resp.status_code}")
    login_resp.raise_for_status()
    token = login_resp.json().get("access_token")
    if not token:
        print("ERROR: login succeeded but access_token missing")
        return 2

    # Get calendar
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        f"{base}/calendar",
        params={"start_date": args.start, "end_date": args.end},
        headers=headers,
        timeout=60,
    )

    data = resp.json()
    print(f"Calendar response: {resp.status_code}")

    if resp.status_code != 200:
        print(f"Error: {str(data)[:1000]}")
        return 1

    print(f"Days returned: {len(data.get('days', []))}")
    print(f"Active plan: {data.get('active_plan')}")
    print(f"Current week: {data.get('current_week')}")
    print(f"Current phase: {data.get('current_phase')}")

    for day in data.get("days", []):
        date_str = day["date"]
        planned = day.get("planned_workout")  # Singular!

        print(f"\n{date_str}:")
        if planned:
            notes = planned.get("coach_notes", "")[:60] if planned.get("coach_notes") else "No pace"
            print(f"  Planned: {planned.get('workout_type')} - {planned['title']}")
            print(f"    Pace: {notes}")
        else:
            print("  (no planned workout)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
