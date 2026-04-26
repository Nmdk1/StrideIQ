# StrideIQ Architecture Overview

## Purpose
StrideIQ is built to produce **N=1, evidence-backed coaching** and to remain **viral-safe** under load spikes. The system is designed so the most important claims are:
- **Deterministic when they should be** (plans, selection, receipts)
- **Auditable** (admin actions, selection events, operator interventions)
- **Operationally controllable** (ingestion can be paused; rate limits defer instead of failing)

## High-level components
- **Web**: Next.js (UI surfaces: Home, Calendar, Coach, Admin)
- **API**: FastAPI (domain logic, auth, orchestration)
- **DB**: Postgres (durable truth: athletes, ingestion state, plans, audits, invites)
- **Workers**: Celery (background ingestion + heavy processing)
- **Cache/queue**: Redis (Celery broker/backend and caching)

## Core data flows

### 1) Onboarding (“Latency Bridge”)
1. Signup is **gated** (invite allowlist) and **auditable**.
2. Strava connect uses **signed OAuth state** to prevent tampering and bind the callback.
3. Callback stores tokens and **queues** ingestion (never blocks on long-running sync).
4. Web shows deterministic progress (no “dead air”).

### 2) Ingestion (viral-safe)
1. Workers call Strava with `allow_rate_limit_sleep=False`.
2. On **Strava 429**, workers:
   - mark ingestion as **deferred** (not error)
   - compute `deferred_until`
   - `self.retry(countdown=...)` to reschedule
3. A DB-backed **Emergency Brake** (`system.ingestion_paused`) can prevent enqueueing new ingestion work during incidents.

### 3) Coaching (trust contract)
1. Coach responses must be grounded in athlete data with **receipts** (date + run + values).
2. Prescriptions and analytics are produced by deterministic services; LLM usage (where present) is constrained by citations/tools.
3. **Planned (post–Phase 9, high priority): Coach Action Automation** will follow a strict **propose → athlete confirm → apply** pattern so training changes are **explicitly authorized**, **deterministic**, and **fully audited** (no silent/autonomous execution).

### 4) Admin operations (safety first)
1. `/admin` and `/v1/admin/*` are protected by role checks with a **permissions seam** (`admin_permissions`).
2. **Owner-only impersonation** is time-boxed and surfaced with a global banner.
3. Admin actions are appended to an **audit log** (actor, target, action, reason, payload).
4. System-level controls (`system.*`) require **explicit permission** (no implicit bootstrap access).

## Trust & safety “invariants”
- **Evidence contract**: user-facing, data-backed claims must cite verifiable sources.
- **No dead air**: onboarding must show progress deterministically.
- **Fail fast at HTTP edges**: HTTP endpoints queue work; retry/deferral logic lives in workers.
- **Auditable ops**: privileged actions are traceable and minimally sensitive.
- **Least privilege**: admin permissions are explicit; owner has a distinct role for highest-risk actions.

## Primary “read the code here” shortlist
- Auth / RBAC: `apps/api/core/auth.py`
- Admin ops: `apps/api/routers/admin.py`
- Strava callback: `apps/api/routers/strava.py`
- Ingestion state: `apps/api/services/ingestion_state.py`
- Strava API wrapper: `apps/api/services/strava_service.py`
- Celery ingestion tasks: `apps/api/tasks/strava_tasks.py`

