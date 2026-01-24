# StrideIQ Documentation (Start Here)

This folder is intended to be **readable diligence** for:
- **Prospective employers** (technical rigor + judgment)
- **Investors** (strategy + defensibility + execution)
- **Partners/operators** (how to run and extend the system safely)

## 1) Fast Orientation (10 minutes)
- **Product + positioning**: `docs/EXECUTIVE_REPORT.md`
- **Phased delivery ledger / roadmap**: `docs/PHASED_WORK_PLAN.md`
- **Architecture overview (systems + trust contracts)**: `docs/ARCHITECTURE_OVERVIEW.md`
- **Local dev + tests**: `docs/LOCAL_DEV_AND_TESTS.md`

**High-priority next build (post–Phase 9):** Coach Action Automation (propose → confirm → apply). Details live in `docs/PHASED_WORK_PLAN.md` under “Phase 10”.

## 2) Choose a “Read First” path
- **Employment (engineering)**: `docs/READ_FIRST_EMPLOYMENT.md`
- **Investor**: `docs/READ_FIRST_INVESTOR.md`
- **Partner / operator**: `docs/READ_FIRST_PARTNER.md`

## 3) Key Decision Records (ADRs)
Architecture decisions live in `docs/adr/`.

High-signal starting set:
- **N=1 core + planning**: `docs/adr/ADR-030-fitness-bank-framework.md`, `docs/adr/ADR-031-constraint-aware-planning.md`
- **Workout selection**: `docs/adr/ADR-036-n1-workout-selection-engine.md`, `docs/adr/ADR-050-3d-quality-session-selection-rollout.md`
- **Coach trust contract**: `docs/adr/ADR-044-ai-coach-launch-ready.md`, `docs/adr/ADR-047-coach-architecture-refactor.md`
- **Payments (Phase 6)**: `docs/adr/ADR-055-stripe-mvp-hosted-checkout-portal-and-webhooks.md`
- **Onboarding/Admin/Ops architecture (Phase 3–5)**:
  - `docs/adr/ADR-051-invite-only-access-and-auditable-invites.md`
  - `docs/adr/ADR-052-signed-oauth-state-and-latency-bridge-onboarding.md`
  - `docs/adr/ADR-053-admin-rbac-audit-and-impersonation-hardening.md`
  - `docs/adr/ADR-054-viral-safe-ingestion-resilience-and-emergency-brake.md`

## 4) Operations
- **Owner incident checklist**: `docs/OPS_PLAYBOOK.md`
- **Ops repair scripts**: `docs/OPS_REPAIR_SCRIPTS.md`
- **Backup/restore**: `docs/BACKUP_RESTORE.md`

## 5) Where to start in the codebase
- **API service layer**: `apps/api/services/`
- **Core auth/guards**: `apps/api/core/auth.py`
- **Admin + Ops endpoints**: `apps/api/routers/admin.py`
- **Ingestion worker logic**: `apps/api/tasks/strava_tasks.py`
- **Web app**: `apps/web/app/`

