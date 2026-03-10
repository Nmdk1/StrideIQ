# Engineering Working Agreement

This document defines the non-negotiable delivery bar for all product and engineering work.

## Core Standards

- Ship production-quality code only.
- Keep technical debt at minimum (preferably zero) in touched areas.
- No fast fixes, no band-aids, no "we will clean this later" debt.
- Leave touched files cleaner than you found them.
- Keep the tree clean and deterministic after each work item.

## Code Hygiene

- Remove trailing whitespace in all touched files.
- Normalize line endings in touched files to project conventions.
- Use clear naming and small, composable functions.
- Prefer explicit behavior over hidden side effects.
- Add comments only when they clarify non-obvious logic.

## Documentation Requirements

- Any behavior/API change must update relevant docs in the same work item.
- Feature-level and architecture-level changes must include an ADR.
- Operational changes (deploy/runbook/testing workflow) must update runbook docs.

## ADR Trigger Rubric

Create or update an ADR when any of the following is true:

- New feature spans multiple subsystems (API, data, frontend, infra).
- Data contracts or schemas change in durable ways.
- Prompt architecture or coach behavior guardrails materially change.
- Caching strategy, invalidation behavior, or data freshness semantics change.
- New external dependency or service integration is introduced.
- Trade-off decision has long-term maintenance implications.

## Testing Standards

- Add or update tests for every behavior change.
- Run targeted tests for touched areas during implementation.
- Run full backend and frontend suites before declaring complete for cross-cutting changes.
- Do not mark complete until tests are green and failures are resolved.
- Explicitly distinguish local test status from CI test status.

## Definition of Done

All items below must be true:

- Implementation complete and reviewed for clarity.
- Whitespace/line endings clean in touched files.
- Tests updated and passing at required scope.
- Docs updated for user-visible or operational changes.
- ADR added/updated when rubric conditions are met.
- Git status clean after commit/push.
- CI status accurately reported (pending vs green).

## Quality Guardrails for Coach Experience

- Never use legacy trademarked terminology in athlete-facing language; use RPI.
- Never expose raw internal metrics directly to athletes.
- Never contradict athlete self-report.
- Lead with what went well, then give forward-looking action.
- Keep outputs athlete-specific (N=1), not generic templates.
