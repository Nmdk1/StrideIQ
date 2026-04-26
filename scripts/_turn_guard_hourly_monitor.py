#!/usr/bin/env python3
"""Hourly turn-guard monitor for production rollout decisions."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
import sys

sys.path.insert(0, "/opt/strideiq/repo/apps/api")
sys.path.insert(0, ".")

from services.turn_guard_monitor import build_rollout_report


def _read_docker_logs(container: str, since_minutes: int) -> list[str]:
    cmd = ["docker", "logs", container, f"--since={since_minutes}m"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    return proc.stdout.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate turn-guard hourly monitor report")
    parser.add_argument("--container", default="strideiq_api")
    parser.add_argument("--since-minutes", type=int, default=65)
    parser.add_argument("--min-organic-sample", type=int, default=50)
    parser.add_argument("--min-band-sample", type=int, default=10)
    parser.add_argument("--mismatch-threshold", type=float, default=0.08)
    parser.add_argument("--retry-success-threshold", type=float, default=0.60)
    parser.add_argument("--fallback-threshold", type=float, default=0.40)
    parser.add_argument("--output-path", default="/opt/strideiq/monitor/turn_guard_latest.json")
    parser.add_argument("--history-path", default="/opt/strideiq/monitor/turn_guard_history.jsonl")
    args = parser.parse_args()

    lines = _read_docker_logs(args.container, args.since_minutes)
    report = build_rollout_report(
        lines,
        min_organic_sample=args.min_organic_sample,
        min_band_sample=args.min_band_sample,
        mismatch_threshold=args.mismatch_threshold,
        retry_success_threshold=args.retry_success_threshold,
        fallback_threshold=args.fallback_threshold,
    )
    report["window"] = {
        "container": args.container,
        "since_minutes": args.since_minutes,
    }

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    history_path = Path(args.history_path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(report, separators=(",", ":")) + "\n")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
