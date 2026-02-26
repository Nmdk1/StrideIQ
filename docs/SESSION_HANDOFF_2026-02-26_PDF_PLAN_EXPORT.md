# Session Handoff — PDF Plan Export (Revenue Artifact)

**Date:** 2026-02-26  
**Commits:** `48e1458` (backend), `2c643d2` (frontend)  
**Status:** SHIPPED — production healthy, endpoint live at `GET /v1/plans/{plan_id}/pdf`

---

## What Shipped

### Stream 1 — Backend: PDF generation service

**`apps/api/services/plan_pdf.py`** (new)

- `generate_plan_pdf(plan, workouts, athlete) -> bytes` — WeasyPrint + Jinja2
- Inline HTML template with `@page` CSS for Letter paper, footer on every page
- Page 1: StrideIQ branding, plan summary, 5-zone pace reference card (both min/mi and min/km computed from `baseline_rpi` via `calculate_training_paces()`)
- Pages 2+: weekly workout tables — Day | Type | Workout | Distance | Pace Target | Notes — one section per week
- Rest days explicitly rendered as table rows
- Unit display: weekly tables use `athlete.preferred_units` only; pace reference card always shows both
- `sanitize_pdf_filename(name)` — strips control chars, slashes, quotes, truncates at 50 chars
- No external asset fetches — all CSS inline, system fonts (DejaVu) via Docker

### Stream 2 — Backend: PDF endpoint

**`apps/api/routers/plan_export.py`** (modified)

- Added `GET /v1/plans/{plan_id}/pdf` to existing `plan_export` router (prefix `/v1/plans`)
- Access control:
  - **404** — plan missing or not owned by requesting athlete
  - **403** — owned but not entitled (free tier, no `PlanPurchase` record)
  - **200** — one-time purchaser, guided, or premium
- Reuses `can_access_plan_paces(athlete, plan_id, db)` — zero new tier logic
- Returns `StreamingResponse(application/pdf)` with `Content-Disposition: attachment; filename="<safe_name>_<date>.pdf"`
- Graceful error: 503 on `RuntimeError` (WeasyPrint not available), 500 on unexpected exception

### Stream 3 — Infrastructure: WeasyPrint deps

**`apps/api/Dockerfile`** (modified)

Added OS packages required by WeasyPrint for PDF text rendering:
```
libpango-1.0-0  libpangoft2-1.0-0  libharfbuzz0b
libfontconfig1  libffi-dev  fonts-dejavu-core
```

**`apps/api/requirements.txt`** (modified)
```
weasyprint>=60.0,<70.0
jinja2>=3.1.0,<4.0.0
```

Image size increase is expected and accepted per builder note (one-time, WeasyPrint is large).

### Stream 4 — Frontend: Download PDF button

**`apps/web/app/plans/[id]/page.tsx`** (modified)

- Added `downloadPdf()` handler — `fetch` to `/v1/plans/{id}/pdf`, creates `Blob` → `URL.createObjectURL` → programmatic `<a>` click → `revokeObjectURL`
- Button behavior tied to `plan.paces_locked`:
  - `paces_locked === false` → "Download PDF" button (slate-800 style, download icon)
  - `paces_locked === true` → "Unlock to download PDF" button (orange lock style, routes to `unlockPaces()`)
- User-visible error state: red dismissible banner if download fails (network error or non-200 response)
- Button renders in plan header row alongside plan name, disappears while loading

---

## Test Evidence

### Local: 27 new tests, 0 failures

```
tests/test_pdf_plan_export.py

Category 1 — helper functions (6 tests)
  TestFilenameHelper: safe name, strip slashes/quotes, strip control chars, truncate, empty fallback, preserve hyphens
  TestDistanceFormat: imperial output, metric output, None → dash
  TestPaceFormat: MM:SS format, None input, sec/km → sec/mi conversion

Category 2 — template rendering (7 tests, sys.modules mock — no WeasyPrint required locally)
  test_pdf_generates_valid_bytes             PASSED
  test_pdf_html_contains_plan_name           PASSED
  test_pdf_html_contains_pace_reference_card PASSED (both /mi and /km present)
  test_pdf_html_contains_all_weeks           PASSED (Week 1, Week 2)
  test_pdf_html_renders_rest_days            PASSED
  test_pdf_handles_missing_paces_gracefully  PASSED
  test_pdf_handles_no_baseline_rpi           PASSED (no pace card rendered)

Category 3 — endpoint access control (8 tests)
  test_pdf_endpoint_404_for_non_owner        PASSED
  test_pdf_endpoint_404_for_nonexistent_plan PASSED
  test_pdf_endpoint_403_for_free_without_purchase PASSED
  test_pdf_endpoint_200_for_plan_purchaser   PASSED
  test_pdf_endpoint_200_for_guided_athlete   PASSED
  test_pdf_endpoint_200_for_premium_athlete  PASSED
  test_pdf_endpoint_returns_correct_content_disposition PASSED
  test_pdf_endpoint_unauthenticated_returns_401 PASSED
```

### Regression: 88 passed, 12 xfailed, 0 failed

```
python -m pytest tests/test_pdf_plan_export.py tests/test_monetization_phase2.py tests/test_monetization_tier_mapping.py -q
88 passed, 12 xfailed, 106 warnings in 9.96s
```

### TypeScript: clean

```
npx tsc --noEmit   →   (no output = success)
```

---

## Access-Control Proof (by tier)

| Tier | HTTP Status | Mechanism |
|------|-------------|-----------|
| Free (no purchase) | 403 | `can_access_plan_paces()` returns False |
| Free (plan purchased) | 200 + PDF | `PlanPurchase` record found |
| Guided | 200 + PDF | `tier_satisfies(athlete.subscription_tier, "guided")` |
| Premium | 200 + PDF | `tier_satisfies(...)` |
| Non-owner | 404 | `TrainingPlan.athlete_id != athlete.id` |
| Unauthenticated | 401 | `get_current_user` dependency |

---

## PDF Content Checklist

| Requirement | Implemented |
|-------------|-------------|
| StrideIQ branding | ✅ |
| Athlete name | ✅ |
| Plan name | ✅ |
| Race distance, goal date, total weeks, start/end dates | ✅ |
| Baseline RPI (if present) | ✅ |
| Pace reference card — all 5 zones — both min/mi and min/km | ✅ |
| Generation timestamp | ✅ |
| Week headers: `Week N — Phase` | ✅ |
| Table columns: Day | Type | Workout | Distance | Pace Target | Notes | ✅ |
| Rest days as explicit rows | ✅ |
| Phase transitions visually separated | ✅ |
| Footer every page: StrideIQ URL + page numbering | ✅ (via CSS @page counter) |
| No external asset fetches | ✅ (base_url=None, all CSS inline) |
| Filename sanitized in content-disposition | ✅ (sanitize_pdf_filename) |

---

## Production Smoke Checks

```
GET https://strideiq.run/ping             → {"status":"alive"}
GET https://strideiq.run/                 → 200
GET https://strideiq.run/settings         → 200
GET /v1/plans/<uuid>/pdf (no auth)        → 401 ✅ (endpoint registered)
docker ps:
  strideiq_api     Up 2 minutes (healthy)
  strideiq_web     Up 11 seconds
  strideiq_worker  Up 2 minutes
  strideiq_caddy   Up 15 hours
  strideiq_postgres Up 26 hours (healthy)
  strideiq_redis   Up 26 hours (healthy)
```

---

## Deferred Items (explicit)

1. **PDF caching/pre-generation** — not in scope. Currently on-demand generation per request. If plans become very large (50+ weeks), split into dedicated service.
2. **PDF export analytics** — not tracked in this slice.
3. **Email delivery of PDF** — not in scope.
4. **Custom branded templates** — not in scope.
5. **Completed-workout log rendering in PDF** — not in scope (PDF shows the plan, not activity history).

---

## Next Priority (from TRAINING_PLAN_REBUILD_PLAN.md)

With monetization complete (all phases including PDF), the next major buildable item is:

**Phase 4 — 50K Ultra** — 37 xfail contract tests waiting, new primitives: back-to-back long runs, time-on-feet, RPE, nutrition, strength.

Gate is clear (Phases 1-2 complete). Needs a tight contract-first slice before full expansion.
