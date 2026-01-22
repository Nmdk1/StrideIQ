"""Test Strava PB sync against a running stack (debug script)."""

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

    # Get profile to get athlete ID
    profile_resp = requests.get(f"{base}/v1/athletes/me", headers=headers, timeout=30)
    profile_resp.raise_for_status()
    athlete_id = profile_resp.json().get("id")
    print(f"Athlete ID: {athlete_id}")

    # Recalculate PBs (now uses Strava sync)
    print("\n--- RECALCULATING PBs (Strava sync) ---")
    resp = requests.post(f"{base}/v1/athletes/{athlete_id}/recalculate-pbs", headers=headers, timeout=120)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Strava synced: {data.get('strava_synced')} activities")
        print(f"Strava updated: {data.get('strava_updated')} PBs")
        print(f"Strava created: {data.get('strava_created')} PBs")
        print(f"Total PBs: {data.get('total_pbs')}")
    else:
        print(f"Error: {resp.text[:500]}")

    # Get current PBs
    print("\n--- CURRENT PBs ---")
    resp = requests.get(f"{base}/v1/athletes/{athlete_id}/personal-bests", headers=headers, timeout=30)
    if resp.status_code == 200:
        pbs = resp.json()
        for pb in pbs:
            mins = pb["time_seconds"] // 60
            secs = pb["time_seconds"] % 60
            print(f"  {pb['distance_category']}: {mins}:{secs:02d} ({pb['achieved_at'][:10]})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
