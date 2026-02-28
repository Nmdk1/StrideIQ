# Builder Note — Garmin Ingestion Health Monitor (Moat Reliability)

**Date:** 2026-02-28  
**Assigned to:** Backend Builder  
**Advisor sign-off required:** Yes (before deploy)  
**Urgency:** High ROI / High leverage

---

## Before Your First Tool Call

Read in order:
1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/TRAINING_PLAN_REBUILD_PLAN.md`
3. `docs/AGENT_WORKFLOW.md`
4. `docs/BUILDER_NOTE_2026-02-28_RUN_CONTEXT_GARMINDAY_MOAT.md`
5. This document

---

## Objective

Create internal monitoring so we can detect when Garmin-connected athletes are underfed for sleep/HRV in `garmin_day` despite working ingestion pipelines.

This is reliability work that protects the new science moat: if inputs are thin, insights degrade. We need continuous visibility.

---

## Scope (Approved)

Implement exactly these three deliverables:

1. **Authenticated internal API endpoint** for Garmin ingestion coverage over the last 7 days.
2. **Daily Celery check** that logs warnings when coverage is poor.
3. **Founder-readable single-line summary logs** per athlete.

No UI work, no schema changes, no new Garmin API calls.

---

## Auth / Access Decision (Non-Negotiable)

Use existing API auth and role guard:

- Endpoint must require auth via existing mechanisms.
- Endpoint must be accessible only to founder/admin role.
- Do **not** ship unauthenticated or IP-only access.

Reason: same ROI with lower security risk; reusable for future debug tooling.

---

## Deliverable 1 — Internal Health Endpoint

### Route

Add endpoint under internal/admin surface (consistent with existing router patterns), e.g.:
- `GET /v1/internal/garmin-ingestion-health`

### Response

For each **connected Garmin athlete**, return:

- `athlete_id`
- `email` (or masked identifier if needed by existing internal endpoint conventions)
- `last_row_date` (max `garmin_day.calendar_date`)
- `days_with_rows_7d`
- `sleep_days_non_null_7d`
- `hrv_days_non_null_7d`
- `resting_hr_days_non_null_7d`
- `sleep_coverage_7d` (ratio `sleep_days_non_null_7d / 7`)
- `hrv_coverage_7d` (ratio `hrv_days_non_null_7d / 7`)
- `resting_hr_coverage_7d` (ratio `resting_hr_days_non_null_7d / 7`)

Also return top-level summary:
- `total_connected_garmin_athletes`
- `athletes_below_threshold_count`
- `checked_at_utc`

### Query shape

- Single query (or single CTE chain) preferred.
- Use `athlete` + `garmin_day`.
- Window: last 7 calendar days including today.
- No heavy joins beyond what is required.

---

## Deliverable 2 — Daily Celery Health Check

Add a scheduled task (Celery Beat) to run once daily (morning UTC).

Task behavior:
- Reuse the same coverage computation logic as endpoint (shared helper/service).
- For each connected Garmin athlete, if:
  - `sleep_coverage_7d < 0.50` OR
  - `hrv_coverage_7d < 0.50`
  then emit warning log.

No paging integration in this task. Logging only.

---

## Deliverable 3 — Founder-Readable Log Line

For each checked athlete, emit one concise line in worker logs:

`[garmin-health] athlete=<id> sleep=<x>/7 hrv=<y>/7 resting_hr=<z>/7 last_row=<yyyy-mm-dd>`

For below-threshold athletes, include explicit marker:
- `status=underfed`

---

## Implementation Guidance

- Put metric computation in a shared service/helper so endpoint + task use identical logic.
- Use deterministic date boundaries (UTC date).
- Handle no-row athletes gracefully (coverage=0, last_row_date=null).
- Keep this isolated from ingestion codepaths; read-only monitoring only.

---

## What NOT To Do

- Do NOT add migrations/new tables.
- Do NOT add frontend UI/debug page in this task.
- Do NOT add user notifications/emails/push alerts.
- Do NOT call Garmin APIs directly from this monitor.
- Do NOT weaken auth for convenience.

---

## Tests Required

Add focused tests for:

1. **Endpoint auth/authorization**
   - unauthenticated denied
   - non-admin denied
   - founder/admin allowed

2. **Coverage math**
   - full data (7/7) computes 1.0
   - sparse data computes correct ratios
   - no rows computes zeros/null last date

3. **Threshold logic**
   - sleep below 50% triggers warning
   - hrv below 50% triggers warning
   - both above 50% does not trigger warning

4. **Log format contract**
   - emitted line includes required fields and counts

---

## Acceptance Criteria

- Endpoint returns correct 7-day coverage for connected Garmin athletes.
- Endpoint protected by auth + founder/admin authorization.
- Daily task runs and logs underfed athletes with deterministic thresholds.
- Founder can tail one-line summaries from worker logs.
- Tests pass with evidence pasted.

---

## Evidence Required in Handoff

1. Scoped changed-file list.
2. Test output pasted (auth, coverage math, threshold, log format).
3. Example endpoint response payload (redacted IDs acceptable).
4. Example worker log lines for:
   - healthy athlete
   - underfed athlete
5. Production smoke verification command + output snippet.

