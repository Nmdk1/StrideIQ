# General Advisor Brief — Post-Build State (Ledger P0 + Path A)

## Objective Completed

Executed the three-phase plan to:

1. Clear ledger P0 foundation issues.
2. Ship Path A visibility surfaces on Home and Activity.
3. Wire navigation + daily intelligence to reduce built-vs-visible gap.

## What Is Now True

- No known P0 link breaks in ledger (`broken_link_count=0`).
- No unregistered declared backend routes in ledger (`backend_broken_unregistered_count=0`).
- Four scoped commits shipped and CI-green for the phase sequence.

## Shipped Commit Chain

- `cac2d1e` — Foundation fixes (Phase 1)
- `a7c8ae0` — Home surfaces (Phase 2)
- `ac986eb` — Activity/nav/intelligence wiring (Phase 3)
- `fcf2527` — Site audit living update

## Verified CI

Latest CI runs for all four commits are `success` with ~11-12 minute durations.

## Remaining Risk Signals (Non-P0)

- `frontend_hidden_or_orphan_pages: 23`
- `frontend_dormant_hook_count: 43`
- `unmatched_api_ref_count: 20`

These are no longer P0 blockers but remain productization and maintainability debt.

## Local Environment Caveat

The local workspace is not currently a clean tree due to unrelated pre-existing modified/untracked files from prior sessions. The shipped commit chain and CI evidence remain valid.

## Advisor Ask (Recommended Next Decision)

Please recommend next priority among:

1. **P1 Path Integrity Sweep:** drive `unmatched_api_ref_count` down with explicit contract fixes.
2. **Discoverability Sweep:** reduce hidden/orphan surfaces by nav/entrypoint policy.
3. **Dormant Hook Reduction:** remove or wire dormant hooks to cut dead complexity.
4. **CI Ledger Guard Activation:** defer until local tree discipline and non-P0 baseline stabilize.

## Proposed Next Gate

Before enabling CI ledger guard, target:

- `unmatched_api_ref_count <= 5`
- documented exceptions list for intentional backend-only surfaces
- clean-tree enforcement policy agreed for builder sessions
