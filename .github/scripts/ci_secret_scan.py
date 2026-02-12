"""CI secret scan - run from repo root. Matches .github/workflows/ci.yml inline script."""
from __future__ import annotations
from pathlib import Path
import re
import sys

forbidden_regexes = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk_(?:live|test)_[A-Za-z0-9]{16,}"),
    re.compile(r"rk_(?:live|test)_[A-Za-z0-9]{16,}"),
    re.compile(r"whsec_[A-Za-z0-9]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"),
    re.compile(r"AWS_SECRET_ACCESS_KEY\s*="),
    re.compile(r"OPENAI_API_KEY\s*="),
    re.compile(r"STRAVA_CLIENT_SECRET\s*=\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"GARMIN_CLIENT_SECRET\s*=\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"SECRET_KEY\s*=\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"process\.env\.E2E_PASSWORD\s*\|\|\s*['\"]"),
    re.compile(r"process\.env\.E2E_EMAIL\s*\|\|\s*['\"]"),
    re.compile(r"Authorization\s*:\s*Bearer\s+eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
]

jwt_canary = "Authorization: " + "Bearer " + "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NSJ9.signature"
canaries = [
    "sk_test_1234567890abcdefghijklmnopqrstuvwxyz",
    "whsec_1234567890abcdefghijklmnopqrstuvwxyz",
    "ghp_1234567890abcdefghijklmnopqrstuvwxyz1234567890",
    jwt_canary,
]
for c in canaries:
    if not any(rx.search(c) for rx in forbidden_regexes):
        print(f"Secret scan self-test FAILED to match canary: {c!r}")
        sys.exit(1)

offenders: list[str] = []
root = Path(".")
scan_roots = [root / "apps", root / "scripts"]
for base in scan_roots:
    if not base.exists():
        continue
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        if any(
            part in p.parts
            for part in (".git", "node_modules", ".next", "dist", "build", "__pycache__", "venv", ".venv", "__pypackages__")
        ):
            continue
        try:
            data = p.read_bytes()
        except Exception:
            continue
        if b"\x00" in data:
            continue
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            continue

        for rx in forbidden_regexes:
            if rx.search(text):
                offenders.append(f"{p}: matches forbidden pattern: {rx.pattern}")

if offenders:
    print("Forbidden secrets/PII found:")
    print("\n".join(offenders[:80]))
    sys.exit(1)
print("Secret scan: OK")
