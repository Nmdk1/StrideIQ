# Read First (Partner / Operator)

## 1) Orientation
- `docs/README.md`
- `docs/ARCHITECTURE_OVERVIEW.md`

## 2) How to operate the system (day 1)
- `docs/OPS_PLAYBOOK.md`
- `docs/PHASED_WORK_PLAN.md` (for roadmap + constraints)

## 3) Key “ops/security” decisions
- `docs/adr/ADR-051-invite-only-access-and-auditable-invites.md`
- `docs/adr/ADR-053-admin-rbac-audit-and-impersonation-hardening.md`
- `docs/adr/ADR-054-viral-safe-ingestion-resilience-and-emergency-brake.md`

## 4) Where to start reading code
- Admin: `apps/api/routers/admin.py`, `apps/web/app/admin/page.tsx`
- Ingestion: `apps/api/tasks/strava_tasks.py`, `apps/api/services/ingestion_state.py`
- Onboarding: `apps/api/routers/strava.py`, `apps/web/app/home/page.tsx`

