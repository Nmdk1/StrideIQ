# Read First (Employment / Engineering)

## 1) What this project optimizes for
- **N=1 determinism**: athlete-specific modeling and selection without generic “LLM vibes”
- **Evidence / receipts**: data-backed claims are traceable
- **Operational safety**: viral-safe behavior under load spikes

Start with:
- `docs/EXECUTIVE_REPORT.md`
- `docs/ARCHITECTURE_OVERVIEW.md`

## 2) Architectural decision highlights (ADRs)
- Deterministic planning core: `docs/adr/ADR-030-fitness-bank-framework.md`, `docs/adr/ADR-031-constraint-aware-planning.md`
- Coach trust contract: `docs/adr/ADR-044-ai-coach-launch-ready.md`, `docs/adr/ADR-047-coach-architecture-refactor.md`
- Phase 3–5 ops/security architecture:
  - `docs/adr/ADR-051-invite-only-access-and-auditable-invites.md`
  - `docs/adr/ADR-053-admin-rbac-audit-and-impersonation-hardening.md`
  - `docs/adr/ADR-054-viral-safe-ingestion-resilience-and-emergency-brake.md`

## 3) “Show me the code” starting points
- RBAC + guards: `apps/api/core/auth.py`
- Admin endpoints + audits: `apps/api/routers/admin.py`
- Ingestion tasks + deferral: `apps/api/tasks/strava_tasks.py`

## 4) Verification signals
- Phase/flow ledger (what shipped, when): `docs/PHASED_WORK_PLAN.md`
- Ops playbook (how to operate during incidents): `docs/OPS_PLAYBOOK.md`
- CI (smoke + full runs): `.github/workflows/ci.yml`

