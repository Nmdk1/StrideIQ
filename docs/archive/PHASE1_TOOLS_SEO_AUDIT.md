# Phase 1 — Public tools URL audit (StrideIQ)

**Generated:** 2026-04-12  
**Scope:** All routes implemented under `apps/web/app/tools/` (App Router), including dynamic segments driven by JSON data files.

## Summary

| Pattern | Count (approx.) | Data source |
|--------|-----------------|-------------|
| Hub + tool roots | 7 | — |
| `training-pace-calculator/[distance]` | 4 | Fixed slugs in page |
| `training-pace-calculator/goals/[slug]` | 44 | `goal-pace-tables.json` |
| `age-grading-calculator/[distance]` | 4 | Fixed slugs |
| `age-grading-calculator/demographics/[slug]` | 56 | `age-gender-tables.json` |
| `race-equivalency/[conversion]` | 15 | `equivalency-tables.json` |
| `boston-qualifying/[slug]` | 22 | `bq-tables.json` |
| **Total tool URLs** | **~152** | Sitemap entries align with these generators |

`robots.ts` does **not** disallow `/tools`. The Next.js `sitemap.ts` enumerates static tool paths and expands dynamic routes from the same JSON keys (goals, demographics, equivalency, BQ).

---

## Route inventory and target search queries

Queries are **primary SEO intents** aligned to page H1/title (not exhaustive long-tail variants).

### Hub

| URL | Target query |
|-----|----------------|
| `/tools` | free running calculators; training pace calculator; running tools |

### Training pace

| URL | Target query |
|-----|----------------|
| `/tools/training-pace-calculator` | training pace calculator; VDOT training paces; running pace zones from race time |
| `/tools/training-pace-calculator/5k-training-paces` | 5K training paces; 5K pace zones by time |
| `/tools/training-pace-calculator/10k-training-paces` | 10K training paces; 10K pace table |
| `/tools/training-pace-calculator/half-marathon-training-paces` | half marathon training paces |
| `/tools/training-pace-calculator/marathon-training-paces` | marathon training paces |
| `/tools/training-pace-calculator/goals/[slug]` | goal-specific (e.g. sub-20 5K training paces, sub-3 marathon training paces) — one primary query per slug |

### Age grading

| URL | Target query |
|-----|----------------|
| `/tools/age-grading-calculator` | WMA age grading calculator; age graded running percentage |
| `/tools/age-grading-calculator/good-5k-times-by-age` | good 5K time by age |
| `/tools/age-grading-calculator/good-10k-times-by-age` | good 10K time by age |
| `/tools/age-grading-calculator/good-half-marathon-times-by-age` | good half marathon time by age |
| `/tools/age-grading-calculator/good-marathon-times-by-age` | good marathon time by age |
| `/tools/age-grading-calculator/demographics/[slug]` | demographic benchmarks (e.g. 5K times for women 40s, marathon men 50s) — per-page titles |

### Heat

| URL | Target query |
|-----|----------------|
| `/tools/heat-adjusted-pace` | heat adjusted pace calculator; running in humidity pace adjustment |

### Race equivalency

| URL | Target query |
|-----|----------------|
| `/tools/race-equivalency` | race equivalency calculator; equivalent race times different distances |
| `/tools/race-equivalency/[conversion]` | pair-specific (e.g. 5K to marathon equivalent time, 10K to half marathon equivalent) |

### Boston qualifying

| URL | Target query |
|-----|----------------|
| `/tools/boston-qualifying` | Boston Marathon qualifying times 2026; BQ standards by age |
| `/tools/boston-qualifying/[slug]` | BQ time men/women [age group]; Boston qualifying training paces |

---

## Telemetry (Phase 1)

First-party events stored via `POST /v1/telemetry/tool-event` (no auth required; optional Bearer for correlation):

- `tool_page_view` — pathname under `/tools`
- `tool_result_view` — calculator produced a result (embedded tools)
- `signup_cta_click` — user clicked a tracked `/register` CTA from tools or marketing Hero

See `apps/web/lib/hooks/useToolTelemetry.ts` and `apps/api/routers/telemetry.py`.
