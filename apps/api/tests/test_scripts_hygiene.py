"""
Guardrails to prevent "scripts creep" from reintroducing hardcoded secrets/PII.

These scripts are intentionally run against real environments, but they must not
contain hardcoded personal credentials (emails/passwords) that can leak or spread.
"""

from __future__ import annotations

from pathlib import Path


FORBIDDEN_LITERALS = [
    # Personal / environment-specific strings that should never be hardcoded.
    "mbshaf@gmail.com",
    "StrideIQ2026!",
    "StrideIQLocal!2026",
]


def _iter_script_files() -> list[Path]:
    root = Path(__file__).resolve().parents[1]  # /app
    scripts_dir = root / "scripts"
    return sorted([p for p in scripts_dir.glob("*.py") if p.is_file()])


def test_scripts_do_not_contain_forbidden_literals() -> None:
    offenders: list[str] = []

    for path in _iter_script_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lit in FORBIDDEN_LITERALS:
            if lit in text:
                offenders.append(f"{path.name}: contains forbidden literal {lit!r}")

    assert offenders == [], "Forbidden literals found in scripts:\n" + "\n".join(offenders)

