# Next Session Instructions

**Last Updated:** 2026-01-14
**Previous Session:** Diagnostic Report Feature + CS Model Archival

---

## Session Summary

This session completed major features with full rigor:

1. **Critical Speed Model Archival** — Removed from UI/code, archived to `archive/cs-model-2026-01` branch
2. **On-Demand Diagnostic Report** — Full implementation with ADR, tests, frontend page

---

## Current State

### Branch
`stable-diagnostic-report-2026-01-14`

### Docker Status
Running. Containers: `api`, `web`, `worker`, `postgres`, `redis`

### All Tests Passing
- `test_athlete_diagnostic.py` — 35 tests
- All other tests remain passing

---

## New Feature: Diagnostic Report

### Files Created
- `docs/adr/ADR-019-diagnostic-report.md`
- `apps/api/services/athlete_diagnostic.py` (580 lines)
- `apps/api/tests/test_athlete_diagnostic.py` (300+ lines)
- `apps/web/app/diagnostic/page.tsx` (600+ lines)

### Files Modified
- `apps/api/routers/analytics.py` — added `/v1/analytics/diagnostic-report`
- `apps/api/scripts/seed_feature_flags.py` — added `analytics.diagnostic_report`
- `apps/api/core/rate_limit.py` — added rate limit (4/min)
- `apps/web/app/components/Navigation.tsx` — added nav link

### Access
- URL: `/diagnostic`
- API: `GET /v1/analytics/diagnostic-report`
- Feature Flag: `analytics.diagnostic_report` (enabled)

---

## Critical Speed Model — ARCHIVED

All CS code removed from main branch. Preserved in `archive/cs-model-2026-01`.

### Removed Files
- `apps/api/services/critical_speed.py`
- `apps/web/components/tools/CriticalSpeedPredictor.tsx`
- `apps/api/tests/test_critical_speed.py`
- `apps/api/tests/test_cs_prediction.py`

### Updated Files
- `apps/api/routers/analytics.py` — endpoint removed
- `apps/api/services/home_signals.py` — CS references removed
- `apps/api/services/run_attribution.py` — CS references removed
- `apps/api/services/trend_attribution.py` — CS references removed
- `docs/adr/ADR-011-critical-speed-model.md` — marked ARCHIVED
- `docs/adr/ADR-017-tools-critical-speed.md` — marked ARCHIVED
- `DEFERRED_REFACTOR_BACKLOG.md` — CS entry added

---

## Pending Discussion (Not Implemented)

User asked about PB page redundancy with Diagnostic PB section. Recommendation given:
- **Keep both pages** — PB page for management (sync/recalculate), Diagnostic for context
- Optional: Add "Manage PBs →" link from Diagnostic to PB page

User did NOT request implementation. Next session can implement if requested.

---

## Key Documentation

| Doc | Purpose |
|-----|---------|
| `DIAGNOSTIC_REPORT_USER1.md` | Example report for Michael's data |
| `docs/adr/ADR-019-diagnostic-report.md` | Diagnostic feature decisions |
| `DEFERRED_REFACTOR_BACKLOG.md` | Archived features |
| `_AI_CONTEXT_/MICHAELS_TRAINING_PROFILE.md` | Athlete context |

---

## Full Rigor Checklist (For Reference)

When implementing major features:
1. ADR (Architecture Decision Record)
2. Audit logging (if user interactions)
3. Unit tests
4. Integration tests
5. Security review (input validation)
6. Feature flag
7. Mobile responsiveness
8. Tone check (sparse/irreverent, manifesto alignment)
9. Rebuild/verify
10. Commit only when complete

---

## Commands to Resume

```bash
# Check status
docker-compose ps
docker-compose logs api --tail=50

# Run tests
docker-compose exec api python -m pytest tests/test_athlete_diagnostic.py -v

# Seed feature flags (if DB reset)
docker-compose exec api python scripts/seed_feature_flags.py
```

---

## User Preferences

- **Full rigor** on all major features
- **Sparse/irreverent tone** — "Data says X. Your call."
- **No over-engineering** — only what's requested
- **Wait for explicit "proceed"** before moving to next item
- **Tests must pass** before commit

---

*Session ended: 2026-01-14*
