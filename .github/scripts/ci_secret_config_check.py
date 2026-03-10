"""CI secret config presence check - run from repo root."""
from __future__ import annotations
from pathlib import Path
import sys

required_groups: list[tuple[str, ...]] = [
    ("SECRET_KEY", "JWT_SECRET_KEY"),
    ("TOKEN_ENCRYPTION_KEY",),
    ("POSTGRES_PASSWORD",),
    ("STRAVA_CLIENT_SECRET",),
    ("STRAVA_WEBHOOK_VERIFY_TOKEN",),
    ("GARMIN_CLIENT_SECRET",),
    ("STRIPE_SECRET_KEY",),
    ("STRIPE_WEBHOOK_SECRET",),
]

candidate_files: list[Path] = []
for rel in ("docker-compose.yml", ".env.example"):
    p = Path(rel)
    if p.exists():
        candidate_files.append(p)

for d in ("deploy", "deployment", "k8s", "helm", "infra"):
    base = Path(d)
    if not base.exists():
        continue
    for p in base.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".yml", ".yaml", ".env", ".tmpl", ".template"):
            candidate_files.append(p)

seen: set[str] = set()
files = []
for p in candidate_files:
    s = str(p)
    if s not in seen:
        seen.add(s)
        files.append(p)

if not files:
    print("Secret config presence check FAILED: no template/config files found to scan.")
    sys.exit(1)

corpus = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in files)

missing: list[str] = []
for group in required_groups:
    if not any(name in corpus for name in group):
        missing.append(" or ".join(group))

if missing:
    print("Secret config presence check FAILED. Missing required secret names in templates:")
    for m in missing:
        print(f"- {m}")
    print("\nScanned files:")
    for p in files:
        print(f"- {p}")
    sys.exit(1)

print("Secret config presence check: OK")
print("Scanned files:")
for p in files:
    print(f"- {p}")
