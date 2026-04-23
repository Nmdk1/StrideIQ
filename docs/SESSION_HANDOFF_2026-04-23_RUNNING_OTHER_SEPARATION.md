# Session handoff — Running vs other separation (2026-04-23)

## Scope

Delivered per `docs/BUILDER_NOTE_2026-04-23_RUNNING_OTHER_SEPARATION_CLEANUP.md`: home/calendar/analytics running-only mileage, calendar day split fields + day status, `other_sport_summary` display, shared `WeekChipDay`, tests, `.gitattributes`, hot-patch healthcheck, SITE_AUDIT + wiki, Group 2.5 audit comments.

## Group 2.5 audit table

| path | intent | change | regression test |
|------|--------|--------|-----------------|
| `apps/api/routers/compare.py:~171` | Running-focused backfill floor, not weekly mileage label | doc-comment | N/A |
| `apps/api/routers/progress.py:398` | Running-only period metrics | doc-comment (existing) | existing |
| `apps/api/routers/progress.py:~1595` | All-sport rows for data coverage | doc-comment | N/A |
| `apps/api/routers/training_load.py:~151` | Cross-sport TSS intentional | doc-comment | N/A |
| `apps/api/routers/onboarding.py:~74` | Running-only thin-history baseline | doc-comment | N/A |
| `apps/api/routers/attribution.py:~127` | Single-activity lookup | doc-comment | N/A |
| `apps/api/routers/attribution.py:~199` | Single-activity lookup | doc-comment | N/A |
| `apps/api/routers/fingerprint.py:~129` | All-sport strip volume | doc-comment | N/A |
| `apps/api/routers/fingerprint.py:~202` | All-sport browse count | doc-comment | N/A |
| `apps/api/routers/fingerprint.py:~242` | All-sport browse query | doc-comment | N/A |
| `apps/api/routers/fingerprint.py:~352` | Single-activity | doc-comment | N/A |
| `apps/api/routers/strava.py:~623` | All-sport name backfill | doc-comment | N/A |
| `apps/api/routers/admin.py:~1870` | All-sport platform counts | doc-comment | N/A |
| `apps/api/routers/admin.py:~2424` | All-sport batch classify | doc-comment | N/A |
| `apps/api/routers/nutrition.py` (4 call sites) | Single-activity / batch by id (any sport) | doc-comment | N/A |
| `apps/api/routers/run_analysis.py:~250` | Single-activity; run analysis | doc-comment | N/A |
| `apps/api/routers/run_delivery.py:~41` | Single-activity | doc-comment | N/A |
| `apps/api/routers/stream_analysis.py:~241` | Single-activity (streams) | doc-comment | N/A |
| `apps/api/services/correlation_engine.py` | Shim | doc-comment → real code in `intelligence/` | N/A |
| `apps/api/services/intelligence/correlation_engine.py` | Run-only aggregates + intentional CT buckets | module docstring + per-block comments | N/A |
| `apps/api/services/causal_attribution.py` | Shim | doc-comment | N/A |
| `apps/api/services/intelligence/causal_attribution.py` | Running-only comparison pool | doc-comment | N/A |
| `apps/api/services/fingerprint_context.py` | No Activity SQL | module docstring note | N/A |
| `apps/api/services/individual_performance_model.py` | Running-only / race rows | doc-comment (3 sites) | N/A |
| `apps/api/services/anchor_finder.py` | Running-only (8 query sites) | doc-comment | N/A |
| `apps/api/services/consistency_streaks.py` | Running-only streak logic | doc-comment (3 sites) | N/A |

## Tests (run locally)

```bash
cd apps/api
pytest tests/test_home_api.py tests/test_home_week_running_separation.py tests/test_calendar_running_separation.py tests/test_activities_summary_sport_buckets.py -v
```

```bash
cd apps/web
npx jest __tests__/home/week-chip.test.tsx __tests__/activities/sport-view-toggle.test.tsx
```

Paste verbatim outputs into PR / founder review; CI URL required before production deploy.

## Deploy / production verification

**Not executed in this workspace without founder-approved push.** After deploy, run the three curls from the builder note (`/v1/home`, `/v1/calendar/day/...`, `/v1/activities/summary`) and attach JSON.

## DOM / parity note

Analytics week strip uses the same `WeekChipDay` component as home; see `apps/web/app/analytics/page.tsx` and `apps/web/app/home/page.tsx`.
