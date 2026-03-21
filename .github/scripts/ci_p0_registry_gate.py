"""Enforce workout-registry execution gate attestation on PRs that touch gated runtime paths.

See docs/specs/WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
# Paths (posix) — exact file or directory prefix under repo root
PLAN_FRAMEWORK_PREFIX = "apps/api/services/plan_framework/"
PLAN_GENERATION_ROUTER = "apps/api/routers/plan_generation.py"

PR_BODY_ENV = "PR_BODY"
BASE_SHA_ENV = "BASE_SHA"
HEAD_SHA_ENV = "HEAD_SHA"


def _changed_files(base: str, head: str) -> tuple[list[str] | None, str]:
    """Return (filenames, error). On success error is ''. On git failure return (None, message)."""
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{base}..{head}"],
            capture_output=True,
            text=True,
            check=False,
        )
    if out.returncode != 0:
        msg = out.stderr.strip() or out.stdout.strip() or "unknown git error"
        return None, msg
    files = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    return files, ""


def _touches_gated(paths: list[str]) -> bool:
    for p in paths:
        norm = p.replace("\\", "/")
        if norm == PLAN_GENERATION_ROUTER or norm.startswith(PLAN_FRAMEWORK_PREFIX):
            return True
    return False


def main() -> int:
    base = os.environ.get(BASE_SHA_ENV, "").strip()
    head = os.environ.get(HEAD_SHA_ENV, "").strip()
    body = os.environ.get(PR_BODY_ENV, "") or ""

    if not base or not head:
        print("P0 registry gate: missing BASE_SHA/HEAD_SHA; skipping.")
        return 0

    changed, git_err = _changed_files(base, head)
    if changed is None:
        print(
            "P0 registry gate: FAILED — could not list changed files (fail closed).\n"
            f"git: {git_err}",
            file=sys.stderr,
        )
        return 1
    if not changed:
        print("P0 registry gate: no changed files from diff; skipping.")
        return 0

    if not _touches_gated(changed):
        print("P0 registry gate: no gated paths touched; OK.")
        return 0

    gate = re.search(r"P0-GATE:\s*(GREEN|WAIVER)\b", body, re.IGNORECASE)
    if not gate:
        print(
            "P0 registry gate: FAILED.\n"
            "This PR modifies plan_framework or plan_generation runtime code.\n"
            "Per docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md (Execution gate / section 2), add to the PR description:\n"
            "  P0-GATE: GREEN   (recovery spec acceptance met for affected paths -- summarize)\n"
            "  or\n"
            "  P0-GATE: WAIVER\n"
            "  P0-WAIVER-REF: <one-line founder-scoped reason / ticket>\n"
            "\n"
            "See docs/specs/WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md",
            file=sys.stderr,
        )
        return 1

    kind = gate.group(1).upper()
    if kind == "WAIVER":
        if not re.search(r"P0-WAIVER-REF:\s*\S", body):
            print(
                "P0 registry gate: WAIVER requires a non-empty P0-WAIVER-REF: line in the PR body.",
                file=sys.stderr,
            )
            return 1

    print(f"P0 registry gate: attestation OK ({kind}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
