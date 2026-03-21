"""Enforce workout-registry execution gate attestation when gated runtime paths change.

Attestation text may come from:
- Pull request body (team / PR workflow), or
- Commit message(s) in the pushed range (solo maintainer / push-to-main workflow).

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

# PR workflow (legacy env names kept for workflow compatibility)
PR_BODY_ENV = "PR_BODY"
BASE_SHA_ENV = "BASE_SHA"
HEAD_SHA_ENV = "HEAD_SHA"

# Explicit event mode (set by CI workflow)
GITHUB_EVENT_NAME_ENV = "GITHUB_EVENT_NAME"
# Push workflow: before/after SHAs from github.event
PUSH_BEFORE_ENV = "PUSH_BEFORE"
PUSH_AFTER_ENV = "PUSH_AFTER"
# Optional PR fields when event is pull_request
PR_BASE_SHA_ENV = "PR_BASE_SHA"
PR_HEAD_SHA_ENV = "PR_HEAD_SHA"


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


def _changed_files_single_commit(head: str) -> tuple[list[str] | None, str]:
    """Files touched by a single commit (e.g. push with github.event.before == null SHA)."""
    out = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", head],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        msg = out.stderr.strip() or out.stdout.strip() or "git diff-tree failed"
        return None, msg
    files = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    return files, ""


def _touches_gated(paths: list[str]) -> bool:
    for p in paths:
        norm = p.replace("\\", "/")
        if norm == PLAN_GENERATION_ROUTER or norm.startswith(PLAN_FRAMEWORK_PREFIX):
            return True
    return False


def _is_null_sha(s: str) -> bool:
    s = (s or "").strip().lower()
    return not s or set(s) <= {"0"}


def _git_commit_messages(base: str, head: str) -> str:
    """Concatenate commit subjects and bodies for base..head (exclusive..inclusive)."""
    if _is_null_sha(base):
        out = subprocess.run(
            ["git", "log", "-1", "--format=%B", head],
            capture_output=True,
            text=True,
            check=False,
        )
        return (out.stdout or "").strip()
    out = subprocess.run(
        ["git", "log", "--format=%B", f"{base}..{head}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return (out.stdout or "").strip()


def main() -> int:
    event = (os.environ.get(GITHUB_EVENT_NAME_ENV) or "").strip().lower()

    if event == "pull_request":
        base = (os.environ.get(PR_BASE_SHA_ENV) or os.environ.get(BASE_SHA_ENV) or "").strip()
        head = (os.environ.get(PR_HEAD_SHA_ENV) or os.environ.get(HEAD_SHA_ENV) or "").strip()
        body = os.environ.get(PR_BODY_ENV, "") or ""
    elif event == "push":
        base = (os.environ.get(PUSH_BEFORE_ENV) or "").strip()
        head = (os.environ.get(PUSH_AFTER_ENV) or "").strip()
        if not head:
            print("P0 registry gate: push event missing PUSH_AFTER; skipping.")
            return 0
        body = _git_commit_messages(base, head)
    else:
        # Back-compat: unnamed mode using BASE_SHA / HEAD_SHA / PR_BODY only
        base = os.environ.get(BASE_SHA_ENV, "").strip()
        head = os.environ.get(HEAD_SHA_ENV, "").strip()
        body = os.environ.get(PR_BODY_ENV, "") or ""

    if not head:
        print("P0 registry gate: missing head SHA; skipping.")
        return 0

    if event == "push" and _is_null_sha(base):
        changed, git_err = _changed_files_single_commit(head)
    elif not base:
        print("P0 registry gate: missing base SHA; skipping.")
        return 0
    else:
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
        where = "pull request description" if event == "pull_request" else "commit message(s)"
        print(
            "P0 registry gate: FAILED.\n"
            "This change touches plan_framework or plan_generation runtime code.\n"
            f"Per docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md (Execution gate / section 2), add to the {where}:\n"
            "  P0-GATE: GREEN   (recovery spec acceptance met for affected paths -- summarize)\n"
            "  or\n"
            "  P0-GATE: WAIVER\n"
            "  P0-WAIVER-REF: <one-line founder-scoped reason / ticket>\n"
            "\n"
            "Push-to-main: include those lines in the commit message (any commit in the push).\n"
            "See docs/specs/WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md",
            file=sys.stderr,
        )
        return 1

    kind = gate.group(1).upper()
    if kind == "WAIVER":
        if not re.search(r"P0-WAIVER-REF:\s*\S", body):
            print(
                "P0 registry gate: WAIVER requires a non-empty P0-WAIVER-REF: line "
                "(PR body or commit message).",
                file=sys.stderr,
            )
            return 1

    print(f"P0 registry gate: attestation OK ({kind}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
