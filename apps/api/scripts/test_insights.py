"""Test insights API endpoints against a running stack (debug script)."""

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

    headers = {"Authorization": f"Bearer {token}"}

    # Test build status
    print("\n--- BUILD STATUS ---")
    resp = requests.get(f"{base}/v1/insights/build-status", headers=headers, timeout=60)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Has active plan: {data.get('has_active_plan')}")
        print(f"Plan name: {data.get('plan_name')}")
        print(f"Week: {data.get('current_week')} of {data.get('total_weeks')}")
    else:
        print(f"Error: {resp.text[:500]}")

    # Test active insights
    print("\n--- ACTIVE INSIGHTS ---")
    resp = requests.get(f"{base}/v1/insights/active?limit=5", headers=headers, timeout=60)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Insights count: {len(data.get('insights', []))}")
        for i in data.get("insights", [])[:3]:
            print(f"  - {i.get('insight_type')}: {i.get('title')[:50]}...")
    else:
        print(f"Error: {resp.text[:500]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
