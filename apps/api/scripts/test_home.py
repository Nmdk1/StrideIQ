"""Test home API endpoint against a running stack (debug script)."""

from __future__ import annotations

import os

import requests


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.getenv("STRIDEIQ_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--email", default=os.getenv("STRIDEIQ_EMAIL"))
    parser.add_argument("--password-env", default="STRIDEIQ_PASSWORD")
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

    # Test home endpoint
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{base}/home", headers=headers, timeout=60)
    print(f"Home: {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()

        print("\n--- TODAY ---")
        today = data["today"]
        print(f"Has workout: {today['has_workout']}")
        if today["has_workout"]:
            print(f"  Title: {today.get('title')}")
            print(f"  Distance: {today.get('distance_mi')} mi")
            print(f"  Pace: {today.get('pace_guidance')}")
            print(f"  Why: {today.get('why_context')}")
            print(f"  Week: {today.get('week_number')}, Phase: {today.get('phase')}")

        print("\n--- YESTERDAY ---")
        yesterday = data["yesterday"]
        print(f"Has activity: {yesterday['has_activity']}")
        if yesterday["has_activity"]:
            print(f"  Name: {yesterday.get('activity_name')}")
            print(f"  Distance: {yesterday.get('distance_mi')} mi at {yesterday.get('pace_per_mi')}")
            print(f"  Insight: {yesterday.get('insight')}")

        print("\n--- WEEK ---")
        week = data["week"]
        print(f"Status: {week['status']}")
        print(f"Progress: {week['completed_mi']}/{week['planned_mi']} mi ({week['progress_pct']}%)")
        print(f"Week: {week.get('week_number')}/{week.get('total_weeks')}, Phase: {week.get('phase')}")
        print("Days:")
        for d in week["days"]:
            status = "✓" if d["completed"] else "○" if d["is_today"] else "·"
            dist = d.get("distance_mi", "-")
            print(f"  {d['day_abbrev']}: {status} {dist}")
    else:
        print(resp.text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
