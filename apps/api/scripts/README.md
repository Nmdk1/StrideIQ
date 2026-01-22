## `apps/api/scripts/` (ops + verification scripts)

This directory contains **runtime scripts** that operate against a real database / running stack.

It intentionally includes a mix of:
- **Ops/repair tooling** (data backfills, migrations, safety repairs)
- **Verification harnesses** (golden path checks, production sanity scripts)
- **Ad-hoc debugging scripts** (should be safe and parameterized)

### Non-negotiable rules (repo hygiene)

- **No hardcoded credentials** (email/passwords/tokens/keys) in source.
  - Use environment variables and/or explicit CLI args.
  - Avoid passing passwords on the command line; prefer `--password-env VAR`.
- **Mutating scripts must be safe-by-default**:
  - Default mode is **DRY_RUN**.
  - Require an explicit `--commit` to persist changes.
- **No token printing**:
  - Never print access tokens, refresh tokens, or encryption keys in logs.
  - If you need to confirm behavior, log **athlete id** and counts, not secrets.
- **No “personal” hardcoding**:
  - Don’t bake in a specific athlete email/id/date. Use `STRIDEIQ_EMAIL` or args.

### Where to put scratch work

Use `apps/api/scripts/_scratch/` for local experiments. That folder is gitignored so it can’t creep into commits.

### Maintained repair scripts

See `docs/OPS_REPAIR_SCRIPTS.md` for the maintained repair scripts and how to run them safely.

