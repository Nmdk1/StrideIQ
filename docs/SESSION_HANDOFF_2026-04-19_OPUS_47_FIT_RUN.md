# Session Handoff — April 19, 2026 (FIT Run Pipeline)

**For:** Next agent (any model)
**From:** Opus 4.7 — `fit_run_001` ingest, surface, coach context (3 phases, all live)
**Production:** https://strideiq.run | Server: `root@187.124.67.153`
**Previous handoff this same day:** `docs/SESSION_HANDOFF_2026-04-19_OPUS_47.md` (activity-page rebuild + backend sweep + wiki-currency rule)

---

## MANDATORY READ ORDER

**Read ALL of 1-6 before proposing anything.**

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — How to work. Non-negotiable. Includes rule 13 (wiki currency).
2. `docs/PRODUCT_MANIFESTO.md` — The soul.
3. `docs/PRODUCT_STRATEGY_2026-03-03.md` — The moat.
4. `docs/specs/CORRELATION_ENGINE_ROADMAP.md` — Layers 1-4 built.
5. `docs/FINGERPRINT_VISIBILITY_ROADMAP.md`.
6. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`.

**Then:**

7. `docs/wiki/index.md` — Operational mental model. **Authoritative for current state.**
8. `docs/wiki/log.md` — April 19 FIT run pipeline entry is at the top.
9. `docs/wiki/garmin-integration.md` — Updated FIT pipeline section + new Known Issue (`activityFiles` 404).
10. `docs/wiki/coach-architecture.md` — Updated `get_recent_runs()` description + Apr 19 decision.
11. `docs/wiki/activity-processing.md` — Updated FIT-derived metrics section.

---

## What shipped this session

The founder showed a side-by-side of our activity page vs. the Garmin app and asked us to close the gap. This session brought every measured field a Garmin watch + sensor combo records into StrideIQ — ingest, page surface, and coach context — in three phases, all live in production and CI-green.

### Phase 1 — Ingest (`fit_run_001` migration)

- **`apps/api/services/sync/fit_run_parser.py`** (new) — parses FIT `session` + `lap` messages with `fitparse`. Decodes the FIT SDK 5-point feel enum without losing nuance.
- **`apps/api/services/sync/fit_run_apply.py`** (new) — writes activity-level fields and per-lap fields. `extras` JSONB bag captures long-tail metrics (normalized power, kcal, lap trigger, max cadence).
- **`apps/api/tasks/garmin_webhook_tasks.py`** — `process_garmin_activity_file_task` now dispatches by sport: strength → exercise sets, run/walk/hike/cycle → run parser.
- **Migration `fit_run_001`** — adds `total_descent_m`, `moving_time_s`, `avg_power_w`, `max_power_w`, `avg_stride_length_m`, `avg_ground_contact_ms`, `avg_ground_contact_balance_pct`, `avg_vertical_oscillation_cm`, `avg_vertical_ratio_pct`, `garmin_feel`, `garmin_perceived_effort` on `Activity`; matching per-lap columns + `extras` JSONB on `ActivitySplit`. Now the head.
- **Cleanup:** `garmin_body_battery_end` removed from `LREC_INPUT_NAMES` / `INPUT_TO_LIMITER_TYPE` / `COACHING_LANGUAGE` (founder rule: "body battery is a fantasy"). Garmin proprietary scores (training effect, body battery impact, performance condition) are explicitly **not** ingested.

### Phase 2 — Activity page surface

- **`apps/api/routers/activities.py`** — `GET /v1/activities/{id}` exposes all FIT fields + Garmin self-eval pair. `moving_time_s` prefers FIT-derived over `duration_s` (true moving time excludes auto-pause).
- **`apps/web/components/activities/RunDetailsGrid.tsx`** (new) — self-suppressing card grid below `CanvasV2`. Each card hides individually when null; the whole grid hides when no card has data.
- **`apps/web/components/activities/SplitsTable.tsx`** — new "Columns" toggle for new per-lap fields. State persists in `localStorage`. Columns appear in the picker only if at least one split has data.
- **`apps/web/components/activities/GarminEffortFallback.tsx`** (new) — renders watch self-eval at the top of the Coach tab **only** when no `ActivityFeedback.perceived_effort` exists. Founder rule: athlete RPE always wins.

### Phase 3 — Coach + LLM context

- **`apps/api/services/effort_resolver.py`** (new) — single source of truth for "what did this run feel like?". Returns `{rpe, source, feel_label, confidence}` with order: athlete RPE (`high`) → Garmin RPE (`low`) → Garmin feel enum bucketed (`low`) → none. Pure function.
- **`apps/api/services/coach_tools/activity.py`** — `get_recent_runs()` bulk-loads `ActivityFeedback` (no N+1) and emits the FIT-derived metrics + the resolved effort envelope on every run row. The LLM now receives every measured field plus knows whether the RPE came from the athlete or the watch.

### Tests added

- `apps/api/tests/test_fit_run_parser.py` — parser unit tests.
- `apps/api/tests/test_fit_run_apply.py` — apply integration.
- `apps/api/tests/test_activity_detail_fit_fields.py` — API contract.
- `apps/api/tests/test_effort_resolver.py` — 12-case resolver suite.
- `apps/api/tests/test_coach_tools_fit_metrics.py` — 3-case snapshot end-to-end through `get_recent_runs`.
- `apps/web/components/activities/__tests__/RunDetailsGrid.test.tsx` — self-suppression + units.
- `apps/web/components/activities/__tests__/GarminEffortFallback.test.tsx` — precedence rule.
- `apps/web/components/activities/__tests__/SplitsTable.test.tsx` — column toggle + persistence.

### Commits + CI

| Phase | Commit | CI |
|------|--------|----|
| Phase 1 | `21b7210` (and earlier in chain) | Eventually green after `ci_alembic_heads_check.py` head bump + body-battery cleanup + docstring source-contract fix |
| Phase 2 | `2e292b4` | First failed `P0 plan registry gate` (commit touched `plan_framework/limiter_classifier.py` for the body-battery removal but didn't include `P0-GATE: WAIVER` in the message); subsequently green after the failing checks were addressed in Phase 3's commit |
| Phase 3 | `b0ff510` | Green |

### Production state

- All 8 services up; Alembic at `fit_run_001 (head)`.
- Smoke check on the founder's latest run returns `total_descent_m: 482.0`, `moving_time_s: 7529`. FIT-only fields still null on historical activities pending the next webhook push (or a working backfill — see Known Issues).
- During recreate, `strideiq_beat` had a stale container name conflict; resolved with `docker rm -f strideiq_beat` followed by re-up. Worth knowing for the next deploy.

---

## Known Issues opened this session

### `activityFiles` backfill returns 404 (pre-existing, surfaced by deploy)

`apps/api/services/sync/garmin_backfill.py::request_activity_files_backfill` posts to `/wellness-api/rest/backfill/activityFiles` but Garmin returns:

```
{"timestamp":..., "status":404, "error":"Not Found", "path":"/wellness-api/rest/backfill/activityFiles"}
```

The path is wrong or this endpoint isn't exposed for our scope. **Live webhook ingest works fine** — every new run with a FIT file picks up the new fields. Only on-demand historical backfill is broken. When you fix this, you can backfill ~30 days of history per athlete. Tracked in `docs/wiki/garmin-integration.md` Known Issues.

A killed runaway invocation rate-limited us briefly during deploy; rate limit cleared within ~60s. Don't loop-call this endpoint until the path is fixed.

---

## Conventions reinforced this session

- **Real measured metrics only.** Garmin proprietary scores are not ingested. If you find any sneaking back in, remove them.
- **Athlete subjective scores take full weight.** `services/effort_resolver.py` enforces this. Anywhere that previously read `Activity.garmin_perceived_effort` directly should go through the resolver instead. UI mirrors the same rule via `GarminEffortFallback`.
- **Self-suppressing UI for nullable metrics.** Don't render an "—" label when a whole metric is missing; suppress the card entirely. `RunDetailsGrid` is the pattern; copy it for any future per-metric grids.
- **Bulk-load to avoid N+1.** When extending `get_recent_runs` (or any tool function with a per-row sub-lookup), preload the join in one query before the loop.
- **CI gate awareness.** Touching `apps/api/services/plan_framework/**` or `apps/api/services/plan_engine_v2/**` requires `P0-GATE: GREEN` or `P0-GATE: WAIVER` in the commit message. This is enforced at push time. Plan accordingly when scoping commits.

---

## Tree state at handoff

- **Clean for the work above.** All Phase 1/2/3 changes committed and pushed.
- **Untracked debris in repo root** (pre-existing): many `.commit_*.txt` and `.tmp_*.py` files from previous sessions; safe to delete or leave.

---

## Suggested next steps

1. **Fix the `activityFiles` backfill path.** Once corrected, run the backfill loop in `.backfill_run.sh` (already on disk). Confirm the founder's older runs pick up power/stride/GCT/vertical fields.
2. **Wire FIT metrics into the briefing context** (`services/coach_brief_builder.py`). Phase 3 only wired them into `get_recent_runs` (the coach-tool path). The morning briefing builder should also consume the resolved effort envelope and the new per-run fields.
3. **Compare-tab redesign.** Still queued behind canvas (see `docs/specs/COMPARE_REDESIGN.md`). The new fields make this much more useful — comparing stride length and power across same-route runs is a story we can finally tell.
4. **Coach prompt update.** The system prompt should learn the new vocabulary: power as a directly-measured load proxy (when present), stride length and GCT as form indicators, the difference between athlete RPE and Garmin self-eval RPE.
