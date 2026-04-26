# Cleanup Policy

What gets deleted after a session vs retained as reusable tooling.

## Delete after merge / session completion

| Category | Pattern | Location | Why |
|----------|---------|----------|-----|
| One-off diagnostics | `_check_*.py`, `_diag_*.py`, `_fix_*.py` | `scripts/`, root | Hardcoded athlete IDs, single-use DB probes |
| Temp debug scripts | `tmp_debug_*.py`, `tmp_*.py` | `apps/api/`, root | Scratch reproduction scripts |
| Smoke curls with tokens | `_smoke*.sh`, `_quality.sh` | root | Contain hardcoded JWTs — security risk |
| Athlete-specific flushes | `_flush_{name}_*.py` | `scripts/` | Athlete-specific cache operations |
| Test output captures | `diag_*.txt`, `full_*_report.txt`, `test_*.txt`, `eval_*_report.txt` | root | Point-in-time snapshots with no ongoing value |
| Completed builder instructions | `BUILDER_INSTRUCTIONS_*.md` | `docs/` | Work orders for shipped features; code is the record |
| Old session handoffs | `SESSION_HANDOFF_*.md` older than 2 weeks | `docs/` | Keep latest 1-2 for context bootstrap, delete older |

## Retain as reusable tooling

| File | Purpose |
|------|---------|
| `scripts/_get_token.py` | Auth token generator (no hardcoded secrets) |
| `scripts/_flush_all_caches.py` | General-purpose Redis cache flush |
| `scripts/_flush_briefing_cache.py` | Briefing cache reset |
| `scripts/_flush_manual_cache2.py` | Manual cache reset |
| `scripts/_probe_exercise_sets_endpoint.py` | Garmin strength API health check |
| `scripts/generate_realistic_synthetic_population.py` | Synthetic athlete population generator |
| `_fetch_plan.sh` | Plan inspection harness (mints fresh token) |
| `_get_token_and_test.py` | Auth + quality gate checks |
| `_run_coach_test.py` | Coach quality regression harness |
| `_smoke_manual.py` | Manual endpoint smoke test |

## Retain as living docs

| File | Purpose |
|------|---------|
| `docs/specs/*.md` | Active feature specifications |
| `docs/references/*.md` | Domain knowledge reference library |
| `docs/BRIEFING_FIX_NOTES.md` | Active backlog items |
| `docs/COMPOSER2_PROTOCOL_PLAYBOOK.md` | Agent workflow reference |
| `docs/mockups/*.html` | Visual design references |
| Latest 1-2 `SESSION_HANDOFF_*.md` | Context bootstrap for new sessions |

## .gitignore enforcement

The `.gitignore` file contains patterns that prevent accidental tracking of
scratch scripts and diagnostic outputs. If a script should be tracked,
name it without the `_` prefix or add it explicitly with `git add -f`.

## Security

Never commit files containing hardcoded JWTs, API keys, or bearer tokens.
If a script needs authentication, mint a fresh token at runtime (see
`scripts/_get_token.py` for the pattern).
