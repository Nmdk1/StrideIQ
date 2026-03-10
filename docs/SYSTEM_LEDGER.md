# System Ledger

Canonical source: `docs/SYSTEM_LEDGER.json`.

## Summary

- Backend routes: `329`
- Runtime-registered backend routes: `329`
- Broken unregistered backend routes: `0`
- Backend routes with frontend consumers: `163`
- Frontend pages: `57`
- Hidden/orphan frontend pages: `23`
- Frontend hooks: `116`
- Dormant frontend hooks: `43`
- Broken internal links: `0`
- Unmatched frontend API refs: `20`

## P0 Items

- None.

## Operating Rule

- Builder checks this ledger before touching any surface. If `P0`/`P1` exists on a target path, fix those first.
