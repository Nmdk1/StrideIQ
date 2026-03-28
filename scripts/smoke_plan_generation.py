"""
Automated smoke test for plan generation via /v2/plans/constraint-aware.

Usage:
  # Against production (uses SSH to get token):
  python scripts/smoke_plan_generation.py --env prod

  # Against local dev server (must be running on localhost:8000):
  python scripts/smoke_plan_generation.py --env local

  # Specific distance only:
  python scripts/smoke_plan_generation.py --env prod --distance 10k

  # With tune-up race:
  python scripts/smoke_plan_generation.py --env prod --distance 10k --tune-up
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import requests

PROD_HOST = "https://strideiq.run"
LOCAL_HOST = "http://localhost:8000"

DISTANCES = ["5k", "10k", "half_marathon", "marathon"]

RACE_OFFSETS_WEEKS = {
    "5k": 6,
    "10k": 8,
    "half_marathon": 12,
    "marathon": 16,
}


def get_prod_token() -> str:
    script = (
        "from core.security import create_access_token; "
        "from database import SessionLocal; "
        "from models import Athlete; "
        "db = SessionLocal(); "
        "user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first(); "
        "print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role})); "
        "db.close()"
    )
    result = subprocess.run(
        [
            "ssh", "root@187.124.67.153",
            f"docker exec strideiq_api python -c \"{script}\"",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    token = result.stdout.strip().split("\n")[-1]
    if not token or len(token) < 20:
        print(f"STDERR: {result.stderr}")
        sys.exit(f"Failed to get token. stdout={result.stdout!r}")
    return token


def get_local_token() -> str:
    token = os.environ.get("STRIDEIQ_TOKEN")
    if token:
        return token
    sys.exit(
        "Set STRIDEIQ_TOKEN env var for local testing.\n"
        "Generate with: cd apps/api && python -c \""
        "from core.security import create_access_token; "
        "from database import SessionLocal; from models import Athlete; "
        "db=SessionLocal(); u=db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first(); "
        "print(create_access_token(data={'sub':str(u.id),'email':u.email,'role':u.role})); db.close()\""
    )


def build_request(distance: str, *, tune_up: bool = False) -> Dict[str, Any]:
    weeks = RACE_OFFSETS_WEEKS.get(distance, 10)
    race_date = date.today() + timedelta(weeks=weeks)
    race_date_str = race_date.isoformat()

    body: Dict[str, Any] = {
        "race_date": race_date_str,
        "race_distance": distance,
    }

    if tune_up:
        tu_date = race_date - timedelta(weeks=2)
        body["tune_up_races"] = [
            {
                "race_date": tu_date.isoformat(),
                "distance": "5k",
                "race_name": "Smoke Test Tune-Up",
                "purpose": "threshold",
            }
        ]

    return body


def validate_plan(resp_json: Dict[str, Any], distance: str) -> List[str]:
    """Return list of issues found. Empty = pass."""
    issues = []

    if "error" in resp_json or "detail" in resp_json:
        detail = resp_json.get("detail", resp_json.get("error", "unknown"))
        if isinstance(detail, dict):
            reasons = detail.get("reasons", [])
            issues.append(f"API error: {'; '.join(reasons) if reasons else json.dumps(detail)}")
        else:
            issues.append(f"API error: {detail}")
        return issues

    plan = resp_json.get("plan", resp_json)
    weeks = plan.get("weeks", [])

    if not weeks:
        issues.append("No weeks in plan")
        return issues

    if len(weeks) < 4:
        issues.append(f"Only {len(weeks)} weeks (minimum 4 expected)")

    has_long = False
    has_quality = False
    has_rest = False
    total_days = 0

    for w in weeks:
        days = w.get("days", [])
        total_days += len(days)
        for d in days:
            wt = d.get("workout_type", "")
            if wt in ("long", "long_mp", "long_hmp", "easy_long"):
                has_long = True
            if wt in ("threshold", "intervals", "repetitions", "threshold_short"):
                has_quality = True
            if wt == "rest":
                has_rest = True

    if not has_long:
        issues.append("No long run found in plan")
    if not has_quality:
        issues.append("No quality session found in plan")
    if not has_rest:
        issues.append("No rest day found in plan")

    if distance == "marathon":
        has_mp = any(
            d.get("workout_type") in ("long_mp", "mp_medium")
            for w in weeks
            for d in w.get("days", [])
        )
        if not has_mp:
            issues.append("Marathon plan missing MP work")

    if distance == "half_marathon":
        has_hmp = any(
            d.get("workout_type") in ("long_hmp",)
            for w in weeks
            for d in w.get("days", [])
        )
        if not has_hmp:
            issues.append("Half marathon plan missing HMP work")

    return issues


def run_smoke(
    host: str,
    token: str,
    distances: List[str],
    tune_up: bool = False,
) -> bool:
    all_passed = True
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    for dist in distances:
        label = f"{dist.upper()}"
        if tune_up:
            label += " +tune-up"
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")

        body = build_request(dist, tune_up=tune_up)
        print(f"  Race date: {body['race_date']}")
        if body.get("tune_up_races"):
            print(f"  Tune-up:   {body['tune_up_races'][0]['race_date']} ({body['tune_up_races'][0]['distance']})")

        url = f"{host}/v2/plans/constraint-aware"
        t0 = time.time()
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=120)
        except requests.exceptions.ConnectionError:
            print(f"  FAIL  Connection refused ({host})")
            all_passed = False
            continue
        elapsed = time.time() - t0

        print(f"  Status:    {resp.status_code}  ({elapsed:.1f}s)")

        if resp.status_code == 200:
            data = resp.json()
            plan = data.get("plan", data)
            weeks = plan.get("weeks", [])
            print(f"  Weeks:     {len(weeks)}")

            if weeks:
                w1 = weeks[0]
                w1_total = sum(d.get("target_miles", 0) or 0 for d in w1.get("days", []))
                w1_long = max(
                    (d.get("target_miles", 0) or 0 for d in w1.get("days", [])
                     if d.get("workout_type", "") in ("long", "easy_long", "long_mp", "long_hmp")),
                    default=0,
                )
                print(f"  W1 total:  {w1_total:.1f}mi")
                print(f"  W1 long:   {w1_long:.1f}mi")

                wt_types = set()
                for w in weeks:
                    for d in w.get("days", []):
                        wt_types.add(d.get("workout_type", "unknown"))
                print(f"  Types:     {', '.join(sorted(wt_types))}")

            issues = validate_plan(data, dist)
            if issues:
                print(f"  FAIL")
                for issue in issues:
                    print(f"    - {issue}")
                all_passed = False
            else:
                print(f"  PASS")
        elif resp.status_code == 422:
            data = resp.json()
            detail = data.get("detail", {})
            if isinstance(detail, dict) and detail.get("quality_gate_failed"):
                reasons = detail.get("reasons", [])
                print(f"  FAIL  Quality gate blocked:")
                for r in reasons:
                    print(f"    - {r}")
            else:
                print(f"  FAIL  Validation error: {json.dumps(detail, indent=2)}")
            all_passed = False
        else:
            print(f"  FAIL  HTTP {resp.status_code}")
            try:
                print(f"  Detail: {resp.json()}")
            except Exception:
                print(f"  Body: {resp.text[:500]}")
            all_passed = False

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Plan generation smoke test")
    parser.add_argument("--env", choices=["prod", "local"], default="prod")
    parser.add_argument("--distance", choices=DISTANCES, help="Test single distance")
    parser.add_argument("--tune-up", action="store_true", help="Include a tune-up race")
    parser.add_argument("--token", help="Auth token (skips SSH/env lookup)")
    args = parser.parse_args()

    host = PROD_HOST if args.env == "prod" else LOCAL_HOST
    distances = [args.distance] if args.distance else DISTANCES

    print(f"Plan Generation Smoke Test")
    print(f"  Target: {host}")
    print(f"  Distances: {', '.join(distances)}")
    print(f"  Tune-up: {'yes' if args.tune_up else 'no'}")

    if args.token:
        token = args.token
    elif args.env == "prod":
        print("  Fetching token from production...")
        token = get_prod_token()
    else:
        token = get_local_token()

    print(f"  Token: ...{token[-8:]}")

    passed = run_smoke(host, token, distances, tune_up=args.tune_up)

    print(f"\n{'='*60}")
    if passed:
        print("  ALL PASSED")
    else:
        print("  SOME TESTS FAILED")
    print(f"{'='*60}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
