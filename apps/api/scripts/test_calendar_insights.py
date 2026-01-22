"""Test calendar API inline insights against a running stack (debug script)."""

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

    # Test calendar endpoint
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{base}/calendar", headers=headers, timeout=60)
    print(f"Calendar: {resp.status_code}")

    if resp.status_code != 200:
        print(resp.text[:1000])
        return 1

    data = resp.json()

    print("\n--- CALENDAR DATA ---")
    print(f"Start: {data['start_date']}")
    print(f"End: {data['end_date']}")
    print(f"Active plan: {data.get('active_plan', {}).get('name', 'None')}")
    print(f"Current week: {data.get('current_week')}")
    print(f"Current phase: {data.get('current_phase')}")
    print(f"Days: {len(data['days'])}")
    print(f"Week summaries: {len(data.get('week_summaries', []))}")

    # Check for inline insights
    days_with_insights = [d for d in data["days"] if d.get("inline_insight")]
    print("\n--- INLINE INSIGHTS ---")
    print(f"Days with inline insights: {len(days_with_insights)}")
    for d in days_with_insights[:5]:
        insight = d["inline_insight"]
        print(f"  {d['date']}: {insight['metric']} = {insight['value']} ({insight['sentiment']})")

    # Check activities
    days_with_activities = [d for d in data["days"] if d.get("activities")]
    print("\n--- ACTIVITIES ---")
    print(f"Days with activities: {len(days_with_activities)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
