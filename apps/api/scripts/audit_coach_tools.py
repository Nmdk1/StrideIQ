"""
Audit all 11 coach tools against a real athlete ID.

Usage (inside api container):
  python scripts/audit_coach_tools.py 4368ec7f-c30d-45ff-a6ee-58db7716be24
"""

from __future__ import annotations

import os
import json
import sys
from uuid import UUID

# Ensure /app is on sys.path when run as a script inside the container.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.database import SessionLocal
from services import coach_tools


TOOLS = [
    ("get_recent_runs", lambda db, athlete_id: coach_tools.get_recent_runs(db, athlete_id, days=14)),
    ("get_efficiency_trend", lambda db, athlete_id: coach_tools.get_efficiency_trend(db, athlete_id, days=120)),
    ("get_plan_week", lambda db, athlete_id: coach_tools.get_plan_week(db, athlete_id)),
    ("get_training_load", lambda db, athlete_id: coach_tools.get_training_load(db, athlete_id)),
    ("get_correlations", lambda db, athlete_id: coach_tools.get_correlations(db, athlete_id, days=120)),
    ("get_race_predictions", lambda db, athlete_id: coach_tools.get_race_predictions(db, athlete_id)),
    ("get_recovery_status", lambda db, athlete_id: coach_tools.get_recovery_status(db, athlete_id)),
    ("get_active_insights", lambda db, athlete_id: coach_tools.get_active_insights(db, athlete_id, limit=5)),
    ("get_pb_patterns", lambda db, athlete_id: coach_tools.get_pb_patterns(db, athlete_id)),
    (
        "get_efficiency_by_zone",
        lambda db, athlete_id: coach_tools.get_efficiency_by_zone(
            db, athlete_id, effort_zone="threshold", days=180
        ),
    ),
    ("get_nutrition_correlations", lambda db, athlete_id: coach_tools.get_nutrition_correlations(db, athlete_id, days=180)),
]


def validate_evidence(tool_name: str, res: object) -> list[str]:
    issues: list[str] = []
    if not isinstance(res, dict):
        return [f"not_dict:{type(res)}"]

    if res.get("tool") != tool_name:
        issues.append("tool_name_mismatch")

    if res.get("ok") is not True:
        issues.append("ok_false")

    ev = res.get("evidence")
    if ev is None:
        issues.append("missing_evidence")
        return issues
    if not isinstance(ev, list):
        issues.append("evidence_not_list")
        return issues

    for i, e in enumerate(ev):
        if not isinstance(e, dict):
            issues.append(f"evidence[{i}]_not_dict")
            continue
        for k in ["type", "id", "date", "value"]:
            if k not in e:
                issues.append(f"evidence[{i}]_missing_{k}")
            elif e.get(k) in [None, ""]:
                issues.append(f"evidence[{i}]_empty_{k}")
    return issues


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/audit_coach_tools.py <athlete_uuid>")
        return 2

    athlete_id = UUID(sys.argv[1])
    db = SessionLocal()
    try:
        report: dict[str, list[str]] = {}
        outputs: dict[str, object] = {}

        for name, fn in TOOLS:
            try:
                res = fn(db, athlete_id)
            except Exception as e:
                res = {"ok": False, "tool": name, "error": str(e), "data": {}, "evidence": []}
            outputs[name] = res
            report[name] = validate_evidence(name, res)

        print("EVIDENCE_VALIDATION_REPORT")
        print(json.dumps(report, indent=2, default=str))
        print("--- SAMPLE_OUTPUTS (truncated) ---")
        for name, res in outputs.items():
            s = json.dumps(res, indent=2, default=str)
            print(f"\n## {name}\n{s[:2500]}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

