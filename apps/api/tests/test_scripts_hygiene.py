"""
Guardrails to prevent "scripts creep" from reintroducing hardcoded secrets/PII.

These scripts are intentionally run against real environments, but they must not
contain hardcoded personal credentials (emails/passwords) that can leak or spread.
"""

from __future__ import annotations

from pathlib import Path
import re


FORBIDDEN_REGEXES: list[re.Pattern[str]] = [
    # Any email address literal in scripts (should be env/arg).
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    # Brand-ish password literals are a common footgun (ex: "StrideIQ...!2026").
    # We only flag when it looks like a password token (digits and/or punctuation).
    re.compile(r"\bstrideiq[^\s]{4,}\b", re.IGNORECASE),
]


def _iter_script_files() -> list[Path]:
    root = Path(__file__).resolve().parents[1]  # /app
    scripts_dir = root / "scripts"
    return sorted([p for p in scripts_dir.glob("*.py") if p.is_file()])


def test_scripts_do_not_contain_forbidden_literals() -> None:
    offenders: list[str] = []

    for path in _iter_script_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for rx in FORBIDDEN_REGEXES:
            if rx.search(text):
                offenders.append(f"{path.name}: matches forbidden pattern {rx.pattern!r}")

    assert offenders == [], "Forbidden literals found in scripts:\n" + "\n".join(offenders)

