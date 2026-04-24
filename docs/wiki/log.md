# Wiki Log

## [2026-04-24] Timezone two-model, autofill fix, briefing clock time removed

**Trigger:** Three separate production issues surfaced in one session.

### 1. Timezone — Two-Timezone Model (home vs. effective)

The founder's briefing showed `2:31 AM` when the actual time was `1:31 AM` (Central). Root cause: `Athlete.timezone` was `America/New_York` because `infer_and_persist_athlete_timezone` used the single most-recent GPS activity (a March trip to NC) rather than the mode. Strava OAuth was also incorrectly overwriting an existing timezone on re-auth.

**Fixes shipped:**
- `infer_and_persist_athlete_timezone` now samples last 30 GPS activities in 90 days and uses the mode — a single trip no longer poisons the home timezone.
- `get_athlete_effective_timezone()` added to `services/timezone_utils.py` — read-only, returns the most-recent GPS timezone within 72 hours (detects travel), falls back to home.
- Briefing `local_now` now uses effective timezone. Training day windows (local_today, day bounds) keep home timezone.
- Briefing fingerprint includes `tz:{effective_timezone}` so travel triggers cache invalidation and fresh LLM generation.
- Strava OAuth callback only writes `Athlete.timezone` when it is currently unset; discrepancies on re-auth are logged, not applied.

**Files:** `apps/api/services/timezone_utils.py`, `apps/api/routers/home.py`, `apps/api/routers/strava.py`, `apps/api/tasks/home_briefing_tasks.py`

**Wiki:** `docs/wiki/briefing-system.md` — Two-Timezone Model section added/updated.

### 2. Nutrition — browser/OS autofill offering credit cards

A recent web container rebuild caused Android's autofill service to re-analyze the nutrition page DOM. The macro entry grid (Calories, Protein, Carbs, Fat) matched payment-form heuristics and Android offered the athlete's credit card.

**Fix:** `apps/web/app/nutrition/page.tsx` — added `autoComplete="off"` + semantic `name` attributes to every unguarded `<input>` and `<textarea>` (food-description, notes, catalog search, meal name, meal-item food fields, meal NL-parse textarea, history edit notes) and `autoComplete="off"` to both surrounding `<form>` elements.

**Wiki:** `docs/wiki/nutrition.md` — Frontend Notes section added; Known Gap documented for text-keyed overrides.

### 3. Briefing — clock time removed from LLM prompt

The LLM was told the exact clock time (`It is 2:00 AM`) via the system prompt. This text appeared verbatim in generated briefings. Two problems: (a) the athlete has a clock; (b) the briefing is pre-generated up to 40 minutes before it is read, so the stated time is always stale.

**Fix:** `apps/api/routers/home.py` `_call_opus_briefing_sync` — removed `_time_str` entirely. The system prompt now passes only the time-of-day period (`morning` / `afternoon` / `evening`) with an explicit instruction never to state the clock time. Natural relative phrasing ("this morning", "tonight") is preserved.

**Wiki:** `docs/wiki/briefing-system.md` — Clock Time Removed section added; Two-Timezone table updated (no longer says "It's 7 AM").



**Trigger:** The canonical units migration eliminated all hardcoded imperial API fields (`distance_mi`, `pace_per_mile`, `completed_mi`, etc.) and replaced them with SI-adjacent canonical units (`distance_m`, `pace_s_per_km`, `duration_s`). Frontend converts at render via `useUnits()` hook. Backend LLM text uses `CoachUnits` helper. CSV exports respect athlete preference. Country-aware defaults from IANA timezone.

**Documentation updates:**

- **New:** `docs/wiki/units.md` — canonical units contract, `useUnits()` API, `CoachUnits` API, country-aware defaults, migration changelog.
- **Updated:** `docs/wiki/index.md` — added Units System to All Pages table, bumped last-updated.
- **Updated:** `docs/wiki/reports.md` — CSV export now respects athlete preferred units (was hardcoded imperial).
- **Updated:** `docs/wiki/briefing-system.md` — specificity fix marked SHIPPED; findings use athlete preferred units via CoachUnits.
- **Updated:** `docs/wiki/plan-engine.md` — `target_peak_weekly_m` (was `_miles`); V2 volume control note about API-to-engine conversion.
- **Updated:** `docs/wiki/activity-processing.md` — shape sentence uses preferred units; distance hover card unit-aware; distance markers unit-aware.
- **Updated:** `docs/SITE_AUDIT_LIVING.md` — §0 delta rewritten: imperial debt marked RESOLVED; field names corrected (`distance_m`, `completed_m`); §14 contract updated.
- **Updated:** `docs/SESSION_HANDOFF_2026-04-22_AGENT_ONBOARDING.md` — imperial debt marked RESOLVED.
- **Updated:** `docs/BUILDER_NOTE_2026-04-23_RUNNING_OTHER_SEPARATION_CLEANUP.md` — field references corrected to `_m`.
- **Updated:** `docs/PLAN_ENGINE_V2_MASTER_PLAN.md` — pace calculator note about API boundary conversion.
- **Updated:** 4 specs (RUNTOON_SHARE_FLOW, P4_LOAD_CONTEXT, LIVING_FINGERPRINT, PHASE2_TEST) — API response field names updated.
- **Updated:** 6 ADRs (017, 019, 030, 032, 038, 048) — field names updated or migration notes added.
- **Unchanged:** `docs/GARMIN_API_REFERENCE.md` (describes Garmin's raw format, not our API output); `docs/references/*` (coaching references using running terminology); `docs/archive/*` (historical); `PLAN_GENERATOR_ALGORITHM_SPEC.md` internal segment fields (V2 engine internals).

## [2026-04-23] Running vs other activity separation (home, calendar, analytics)

**Trigger:** Builder note `docs/BUILDER_NOTE_2026-04-23_RUNNING_OTHER_SEPARATION_CLEANUP.md` — eliminate mixed-sport aggregation for athlete-facing running mileage and planned-run completion; surface cross-training explicitly.

**Shipped behavior (summary):**

- `apps/api/routers/home.py`: `other_sport_summary` raw aggregation (no per-activity minute rounding before sum); week/day running fields runs-only per prior contract.
- `apps/api/routers/calendar.py`: `running_*` / `other_*` on day payloads; `get_day_status` uses running distance vs planned run targets; week completed miles from running totals.
- `apps/web/components/home/WeekChipDay.tsx`: shared week-strip cell (home + `app/analytics/page.tsx`); `app/calendar/page.tsx` prefers `running_distance_m` for rollups.
- `docs/SITE_AUDIT_LIVING.md` §0, §6, §14 contract subsection; Group 2.5 doc-comments across listed routers/services.

**Wiki:** `docs/wiki/frontend.md` route + component table updates. Session handoff: `docs/SESSION_HANDOFF_2026-04-23_RUNNING_OTHER_SEPARATION.md`.

## [2026-04-23] Docs aligned to shipped coach/briefing models + two-tier billing

**Trigger:** `SITE_AUDIT_LIVING.md` §6 still described Run Shape Canvas + Opus/Gemini coach split + “placeholder” `/nutrition`; §10/§15 still said **4-tier** Stripe while code has been on **`free` / `subscriber`** normalization (`apps/api/core/tier_utils.py`) since the Mar 19 monetization reset. Internal wiki Quick Reference still listed **Opus** for briefing and **Kimi K2.5** as the hard-coded coach id.

**Verified in code (this session):**

- Coach chat: `AICoach.chat` → `_query_kimi_with_fallback` → `query_kimi_coach` uses `settings.COACH_CANARY_MODEL` (default **`kimi-k2.6`**, `apps/api/core/config.py`); Sonnet fallback in `services/coaching/_llm.py`.
- Briefing: `resolve_briefing_model` (`apps/api/core/llm_client.py`); defaults **`BRIEFING_PRIMARY_MODEL=claude-sonnet-4-6`**; optional Kimi when canary env + athlete allow-list; centralized fallbacks in `call_llm*`.

**Doc edits:** `docs/SITE_AUDIT_LIVING.md` (§6 table, §10, §15, top “Last updated”, delta bullet), `docs/wiki/index.md` Quick Reference + coach row in All Pages + activity-processing blurb, `docs/wiki/coach-architecture.md`, `docs/wiki/briefing-system.md`, `docs/wiki/activity-processing.md` (stream-analysis hook line), `docs/wiki/nutrition.md` (parser/photo model ids), `docs/wiki/product-vision.md`, `docs/wiki/decisions.md`. No runtime code changes in this entry.

## [2026-04-16] Marketing voice rewrite — Hero, WhyGuidedCoaching, Mission, case studies; CC claim contract restored

Outside-Opus advisor reading the live landing page surfaced two issues the April 16 marketing review (`docs/reviews/MARKETING_REVIEW_2026-04-16.md`) had missed: zero customer social proof, and the calculator distribution flywheel as an underused asset. Founder also re-prioritized Priority 2 of the original review (Hero + WhyGuidedCoaching voice rewrite), which had shipped neither in the original review pass nor in the subsequent claim-contract fix (`0bd5f24`).

During CC-claim verification (per the April 16 review's call-out on unverifiable claims), discovered a shipped-to-production trust rupture: `apps/web/app/components/Hero.tsx` advertised **"No credit card required"** while the actual onboarding flow (`onboarding/page.tsx:110`) POSTs to `/v1/billing/checkout/trial` (`apps/api/routers/billing.py:128`), which creates a Stripe Checkout Session that **does** collect a credit card. Every user who completed onboarding hit a Stripe card form. The marketing claim was directly false.

**Decisions and shipped changes:**

1. **Hero (`apps/web/app/components/Hero.tsx`)** — full content rewrite. New manifesto H1: *"Your body has a voice. StrideIQ gives it one."* Tagline *"Deep Intelligence. Zero Fluff."* preserved as supporting line. Outcome-named value-prop stack (*"What's making you faster. What's holding you back. What no template can see — because it's specific to you."*). Subhead *"Personal patterns. Real evidence. Coaching that can't be faked."* replaces the orange uppercase "AI Running Coach" pill. The false "No credit card required" trust pill is replaced with **"Cancel anytime via Stripe"** (truthful — `billing.py:137` confirms Customer Portal cancel-anytime). Adam S. testimonial added directly under the value-prop stack (founder pre-cleared, distillation: *"Ask Coach is getting more detailed and more dialed in every week. You've got something pretty awesome here."*).
2. **QuickValue (`apps/web/app/components/QuickValue.tsx`)** — drop the "3 / 360° / 24/7" fake-precision stat trio. Replaced with a single capability stripe naming the actual data sources.
3. **WhyGuidedCoaching (`apps/web/app/components/WhyGuidedCoaching.tsx`)** — full rewrite. Title now *"Why StrideIQ exists"*. Drops the "AI Running Coach vs Human Running Coach" comparison and the $50–$300 price comparison. Four cooperative cards: Memory, Pattern detection, Availability, Evidence. Adds a callout linking to the new DEXA case study.
4. **FAQ #7 (`apps/web/app/components/FAQ.tsx`)** — replaced keyword-bend question (*"What is the best AI running coach for marathon training?"*) with a real prospective-user question: *"Does StrideIQ tell me what my sleep or nutrition did to my training?"*
5. **Mission page (`apps/web/app/mission/page.tsx`)** — drops the "New Masters" 8-tier taxonomy (Open / Masters / Grandmasters / Senior Grandmasters / Legend Masters / Icon Masters / Centurion Masters / Centurion Prime), drops the external Unsplash background image (referrer leak + asset drift), rewrites the *"silent, brilliant assistant"* and *"measurable efficiency"* paragraphs (the latter violated the `OUTPUT_METRIC_REGISTRY` polarity contract).
6. **Training Pace page (`apps/web/app/tools/training-pace-calculator/page.tsx`)** — adds an RPI/VDOT reconciliation paragraph for SEO (readers arriving from "VDOT" searches now immediately understand what they are looking at).
7. **NEW — case studies.** `/case-studies` (index), `/case-studies/dexa-and-the-7-pound-gap`, `/case-studies/strength-and-durability`. Both de-identified per Brian's pre-cleared permission. Real numbers, real coach output, no names / race names / triangulating dates. Architecture intent: case studies are durable artifacts for community-seeding (forum links to specific findings rather than a generic landing page).

**Test contract.** `apps/web/__tests__/marketing-claim-contracts.test.ts` extended from 5 to 16 tests. New tests lock in the manifesto H1, the Adam S. attribution, the absence of the "No credit card required" claim, the absence of the "3 / 360° / 24/7" stat trio, the cooperative WhyGuidedCoaching title, the absence of the human-coach fight framing, the absence of the New Masters taxonomy and the Unsplash URL, the absence of the "measurable efficiency" claim, the absence of the "silent, brilliant assistant" line, and the RPI/VDOT reconciliation. Full web suite still 459/459 green.

**What we did not do.** We did not migrate onboarding from `/checkout/trial` to `/trial/start`. Founder rejected option B (no-CC trial flow) in favor of option A (drop the false claim). Stripe-collected trials convert ~2-3x better than no-card trials; the conversion math wins. The product flow is unchanged. Only the marketing claim is now true.

**Out of scope (separate tickets).** Calculator share-link / community-seeding affordance (UTM-tagged share button on `/tools/*`); footer brand-copy strengthening; OG image refresh; Person/Author JSON-LD schema; Brian DEXA-flow product surfacing once strength v1 ships.

Spec lives at `docs/specs/MARKETING_VOICE_REWRITE_2026-04-16.md`.

## [2026-04-19] garmin-fit-backfill quarantined + activity page tells the truth on missing FIT data

After Phase 3 of `fit_run_001` shipped, the founder asked why no FIT cards were visible on the activity page in production. Audit revealed the truth:

- The components (`RunDetailsGrid`, `SplitsTable` columns, `GarminEffortFallback`) **are** deployed and bundled correctly.
- They render only when the underlying FIT fields are populated. Across 24,186 historical run activities in prod, every FIT-derived activity-level field (`avg_power_w`, `avg_stride_length_m`, `avg_ground_contact_ms`, `avg_vertical_oscillation_cm`, `moving_time_s`) was 0 / NULL. `total_descent_m` was present in only ~1.8% of runs. `garmin_feel` was NULL for all activities.
- New runs synced going forward will populate these fields via the live `activityFiles` webhook PING. Historical activities synced before the FIT pipeline existed will not.
- We tried to backfill the historical gap with `request_activity_files_backfill`. Garmin returned **404 from `/wellness-api/rest/backfill/activityFiles` on every attempt**, across multiple agents over multiple sessions. The endpoint is not a real capability against our scopes. Continued attempts wasted Garmin rate-limit headroom.

**Actions:**

1. **Backfill quarantined.** `services/sync/garmin_backfill.request_activity_files_backfill` now raises `ActivityFilesBackfillUnavailable` immediately. The matching Celery task `request_garmin_activity_files_backfill_task` returns `{"status": "unavailable", "reason": "garmin_activity_files_backfill_not_supported"}` instead of attempting the call. Import of the quarantined function was removed from `garmin_webhook_tasks.py`. Locked in by `apps/api/tests/test_activity_files_backfill_quarantined.py` (3 tests: function raises, task returns stable envelope, task module does not import the quarantined function).
2. **Activity page tells the truth.** `RunDetailsGrid` no longer silently disappears for runs / walks / hikes / cycles missing FIT data. It renders one small line: *"Power, stride, and form metrics weren't captured for this run."* As soon as any FIT field is present, the line is replaced by the real cards. Sports where these metrics never apply (strength, yoga, swim) still suppress fully. New `showMissingNote` prop on `RunDetailsGrid`; gated in `apps/web/app/activities/[id]/page.tsx` by sport_type. Test coverage added for both states (note shown when empty, note hidden when any metric present).
3. **Documentation updated.** `docs/wiki/garmin-integration.md` "Known Issues" rewritten to reflect that activityFiles backfill is permanently unavailable, not "tracked for future fix." `docs/wiki/activity-processing.md` documents the empty-state truth line.

**The deeper rule going forward:** when our UI suppresses for a real, common reason (missing data, missing source, missing connection), the suppression must be visible enough that an athlete can tell whether the feature shipped or not. Silent disappearance is the same failure mode as a hallucinated narrative — both leave the athlete uncertain about what's real.

## [2026-04-19] garmin-fit-run-pipeline | `fit_run_001` — full FIT ingest for run/walk/hike/cycle, activity-page surfacing, coach context with effort attribution

A three-phase ingest-to-coach pipeline that closes the gap between "what Garmin records" and "what StrideIQ uses." Triggered by the founder showing a side-by-side of our activity page vs. the Garmin app: missing power, stride length, ground contact, vertical oscillation, true moving time, and total descent.

**Founder rules applied (binding):**
- "Bring in everything real" — measured fields only. Garmin proprietary scores (training effect, body battery, performance condition) explicitly **not** ingested. Body battery called out by name as "a fantasy."
- "Stride length and inter-run variation is crucial" — surfaced as a first-class card and per-lap column.
- Athlete subjective scores take **full weight**; Garmin self-eval (`garmin_feel`, `garmin_perceived_effort`) is a low-confidence fallback only. Never blended.

**Phase 1 — Ingest (`apps/api/services/sync/fit_run_parser.py`, `fit_run_apply.py`, `tasks/garmin_webhook_tasks.py`, migration `fit_run_001`):**
- `fit_run_parser.py` reads FIT `session` + `lap` messages with `fitparse`, extracts every measured run field a Garmin watch + sensor combo records, and decodes the FIT SDK 5-point feel enum (`very_strong` … `very_weak`) without losing nuance.
- `fit_run_apply.py` writes activity-level fields (`avg_power_w`, `max_power_w`, `total_descent_m`, `moving_time_s`, `avg_stride_length_m`, `avg_ground_contact_ms`, `avg_ground_contact_balance_pct`, `avg_vertical_oscillation_cm`, `avg_vertical_ratio_pct`, `garmin_feel`, `garmin_perceived_effort`) and matching per-lap fields on `ActivitySplit`, plus an `extras` JSONB bag for long-tail metrics (normalized power, kcal, lap trigger, max cadence).
- `process_garmin_activity_file_task` dispatches by sport: strength → existing exercise-set parser, run/walk/hike/cycle → new run parser. Migration `fit_run_001` adds the columns + extras JSONB and is now the head.
- Cleanup: `garmin_body_battery_end` removed from `LREC_INPUT_NAMES` / `INPUT_TO_LIMITER_TYPE` / `COACHING_LANGUAGE` per the "real measured metrics only" rule. CI source-contract tests updated; `garmin_webhook_tasks.py` docstring rephrased to drop raw Garmin field names (those translations live in `garmin_adapter.py`).

**Phase 2 — Surface in API + activity page (`apps/api/routers/activities.py`, `apps/web/components/activities/`):**
- `GET /v1/activities/{id}` extended with all FIT-derived activity-level fields and the Garmin self-eval pair. `moving_time_s` now prefers the FIT-derived value over `duration_s` (true moving time excludes auto-pause).
- `RunDetailsGrid` (new) — self-suppressing card grid below `CanvasV2`. Each card hides individually when null; the whole grid hides when no card has data, keeping the page clean for older Strava-only activities.
- `SplitsTable` — new "Columns" toggle exposes the new per-lap fields (Max HR, Ascent, Descent, Power, Stride, GCT, Vert Osc, Vert Ratio). Toggle state persists in `localStorage`. Columns only appear in the picker if at least one split has data; cells render `—` for missing values.
- `GarminEffortFallback` (new) — renders the watch's perceived-effort + feel above the Coach tab content **only** when no `ActivityFeedback.perceived_effort` exists for the activity. Once the athlete reflects, this card disappears entirely.

**Phase 3 — Coach + LLM context (`apps/api/services/effort_resolver.py`, `apps/api/services/coach_tools/activity.py`):**
- `services/effort_resolver.py` (new) is the single source of truth for "what did this run feel like?". Resolves to `{rpe, source, feel_label, confidence}` with order: `ActivityFeedback.perceived_effort` (`high`) → `garmin_perceived_effort` (`low`) → `garmin_feel` enum bucketed to RPE (`low`) → empty (`none`). Pure function; no DB I/O. 12-case test suite covers precedence, fallback, unknown labels, invalid ranges.
- `get_recent_runs()` bulk-loads `ActivityFeedback` rows once (no N+1) and emits the FIT-derived metrics + the resolved effort envelope on every run row. The LLM now receives every measured field plus knows whether the RPE it sees came from the athlete or from the watch.
- 3-case snapshot test (`test_coach_tools_fit_metrics.py`) proves the envelope shape end-to-end: athlete RPE wins over Garmin, Garmin fills in when feedback absent, all-nulls render cleanly when nothing is recorded.

**Production deploy:** All three phases shipped in three commits (`21b7210`, `2e292b4`, `b0ff510`), each green in CI. Docker bind-mount cleanup needed `docker rm -f strideiq_beat` after the recreate to clear a stale container name. Alembic at `fit_run_001 (head)` on prod. Smoke check confirms `/v1/activities/{id}` returns the new fields (`total_descent_m: 482.0`, `moving_time_s: 7529` on the founder's latest run; FIT-only fields still null pending the next webhook push).

**Known gap (pre-existing):** `request_activity_files_backfill` posts to `/wellness-api/rest/backfill/activityFiles` and Garmin returns 404 — this endpoint either has the wrong path or isn't exposed for our scope. Live webhook ingest of new activities works; only on-demand historical FIT backfill is broken. Tracked in `garmin-integration.md` Known Issues.

## [2026-04-19] activity-page-rebuild-phases-1-4 + backend-green | CanvasV2 hero, 3-tab restructure, unskippable FeedbackModal, ShareDrawer, RuntoonSharePrompt retired, 39 backend failures fixed

A four-phase rebuild of the run-activity page shipped end-to-end in one session, plus a sweep that resolved 39 pre-existing backend test failures discovered when the backend-test job ran after the frontend changes pushed.

**Phase 1 — CanvasV2 as the activity hero (`apps/web/components/canvas-v2/CanvasV2.tsx`, `apps/web/app/activities/[id]/page.tsx`):**
- New `chromeless` prop on `CanvasV2` suppresses the internal title/subtitle/help block and moves `CanvasHelpButton` to a minimal right-aligned slot. Run activities now render `CanvasV2` chromeless as the hero, replacing `RunShapeCanvas`.
- `TerrainMap3D.tsx`: `mapbox-gl/dist/mapbox-gl.css` lifted from a dynamic `useEffect` import to a static top-level import (was causing the map to render entirely dark on production); `pitch: 62`, `bearing: -20`, DEM exaggeration `3.0` set in the constructor and re-applied at `style.load` via `map.jumpTo()`. Built-in `hillshade` is left untouched after `setPaintProperty` attempts threw "cannot read properties of undefined (reading 'value')". Visibility instead comes from a three-layer route: white casing + emerald glow + deep emerald line, replacing the original yellow that vanished against pale terrain. `NavigationControl` mounted (rotate/tilt/zoom). Desktop fullscreen toggle. Initial render zoom tightened so the course fills the frame. Caddy CSP updated to allow Mapbox tile/style/sprite domains in `connect-src` and `blob:` in `worker-src`/`child-src`; CSP changes required a Caddy container restart, not just `caddy reload`, due to a Docker bind-mount caching artefact on Linux.
- `StreamsStack.tsx`: chart order locked to HR top, pace middle, elevation bottom; pace chart `robustDomain` switched from percentile clipping to **Tukey's fence (IQR, k=3.0)** to preserve real pace variation while clipping spikes; elevation now uses the smoothed series the splits tab uses (less pointy).
- Distance moved from inline label to the leftmost moment-readout hover card: two-decimal miles + secondary time line.

**Phase 2 — Activity-page tab restructure (6 → 3):**
- `Splits` (no map; the hero already has it), `Coach` (absorbs `RunIntelligence`, `FindingsCards`, `WhyThisRun`, `GoingInCard`, `AnalysisTabPanel`, and `activity.narrative`), and `Compare` (placeholder; redesign sequenced behind the canvas — see `docs/specs/COMPARE_REDESIGN.md`). The `RuntoonCard` is no longer rendered at the bottom of the page (lives in the ShareDrawer now).

**Phase 3 — Unskippable FeedbackModal + ReflectPill (`apps/web/components/activities/feedback/`):**
- `FeedbackModal` has three sections (reflection text, RPE, workout-type confirmation) and **no escape hatch**: no X, Cancel, Skip, or backdrop-click dismissal. Save & Close stays disabled until all three are complete. Auto-classified workout types require explicit "Looks right" confirmation: `workoutTypeAcked` is only pre-true when `existingWorkoutType.is_user_override === true`.
- `useFeedbackTrigger` auto-opens the modal once per recent, incomplete run, gated on a `localStorage` flag so it doesn't keep popping up after save. Edits remain available later via the `ReflectPill` in the page chrome (which sources status from `useFeedbackCompletion`).
- Test fixes: lint refactor moved `apiClient` mocks from `require()` calls to module-level `jest.fn()` instances wrapped by `jest.mock()` (the project's ESLint config doesn't register `@typescript-eslint/no-require-imports`, so the eslint-disable comments produced "rule definition not found" errors that broke the Next build). Test regexes for the "no escape hatch" assertion were tightened (anchored `^cancel$`, `^×$|^x$`) so they stop matching the legitimate "Save & Close" button.

**Phase 4 — Share is now a pull action (`apps/web/components/activities/share/`, `apps/web/app/layout.tsx`):**
- New `ShareButton` page-chrome pill (next to `ReflectPill`, run-only) opens a new `ShareDrawer` modal that hosts the `RuntoonCard` and a roadmap placeholder for future share styles (photo overlays, customizable stats, modern backgrounds, flyovers). Drawer dismisses via close button, Escape, or backdrop click.
- `RuntoonSharePrompt` removed from `app/layout.tsx` (was polling `/v1/runtoon/pending` every 10s and sliding up on every recent run — the founder explicitly rejected push-style sharing). Component file preserved on disk for reference / rollback; intentionally not imported. Static regression test `apps/web/__tests__/layout-no-runtoon-prompt.test.ts` enforces this.

**Backend-green sweep — 39 pre-existing failures resolved:**
- The `backend-test` CI job runs only on `schedule` / `workflow_dispatch` (not on `push`), so the failures had been hiding on `main`. Running it manually surfaced 39 broken tests across five clusters; all fixed in the same merge:
  - `test_scripts_hygiene` — `apps/api/scripts/clone_athlete_to_demo.py` docstring referenced hardcoded example emails; replaced with env-var placeholders.
  - Garmin D5/D6 source-contract tests — `apps/api/tasks/garmin_webhook_tasks.py` accessed `activityId` from the raw payload, violating the rule that all raw Garmin field names go through `garmin_adapter.py`. Routed through `adapt_activity_detail_envelope` to extract `garmin_activity_id`.
  - Garmin D5 stream-ingestion tests (`StopIteration`, `assert 1==2`) — `process_garmin_activity_detail_task` was re-querying for the `Activity` after `_ingest_activity_detail_item`, blowing past the mock's `side_effect` list. Refactored: `_ingest_activity_detail_item_full(...) -> (Activity | None, bool)` is the new internal API, with `_ingest_activity_detail_item` retained as a boolean wrapper for backward compat. Caller now consumes the returned `Activity` directly.
  - Garmin feature-flag and D7 backfill tests — the `_make_*` helpers built `MagicMock` athletes with truthy `is_demo`, which tripped the demo-account guard added later in `routers/garmin.py` and produced 403s with plain-string detail instead of the expected JSON envelope. Helpers now explicitly set `is_demo = False`. The D7 callback test also patches `routers.garmin.is_feature_enabled` to `True` so the backfill task `delay()` is reached.
  - `test_phase3b_graduation::test_quality_score_attached_to_result` — the test was hitting the real LLM route and returning `suppressed=True` in CI (no API keys). Patched `services.intelligence.workout_narrative_generator._call_narrative_llm` to a canned narrative so the quality scorer is exercised.
  - Nutrition API tests (21 failures) — `routers/nutrition.py` enforces `MAX_BACKLOG_DAYS = 60` on POST/PUT; hardcoded `2024-XX-XX` dates were now older than 60 days, returning 400s that cascaded into `KeyError: 'id'` on downstream GET/DELETE. Introduced `TODAY = date.today()` + `_d(offset_days)` helper and replaced every hardcoded date in test data and URLs.

**Wiki + cursor rules:**
- New `.cursor/rules/wiki-currency.mdc` makes wiki currency a binding rule with the same standard as tests. The Founder Operating Contract gains rule 13 (wiki must always be current) and adds `docs/wiki/index.md` to the read order. `docs/wiki/index.md` `Last updated:` bumped to April 19, 2026, and the Maintenance Contract section reworded with teeth.

**Production smoke (post-deploy):** `/ping`, `/v1/home`, `/v1/coach/brief`, `/v1/activities` all 200; CanvasV2 renders Mapbox terrain end-to-end on real activity URLs; `RuntoonSharePrompt` confirmed absent from the layout.

## [2026-04-18] demo-pipeline-and-intelligence-honesty | Demo athlete cloning + interval/cooldown gates + briefing fingerprint + Compare redesign decision

Three commits + one decision doc. The day's theme: stop the briefing and Athlete Intelligence panel from inventing structure that isn't there, and stop them from missing structure that is.

**Activity Intelligence + Home Briefing Honesty (`apps/api/services/run_intelligence.py`, `apps/api/routers/home.py`, `apps/api/tasks/home_briefing_tasks.py`):**
- `_is_interval_workout()` widened from a single-signal gate (`workout_type` only) to a three-signal OR: explicit `workout_type` ∈ canonical interval set, `run_shape.summary.workout_classification` ∈ `STRUCTURED_SHAPE_CLASSIFICATIONS` frozenset, or `workout_name` matches rep-notation regex (`6x800`, `4 x mile`) / structured-workout keywords (interval, repeats, fartlek, tempo, cruise, threshold, hill repeats). Founder regression: Garmin labelled a "Meridian — 2 x 2 x mile" workout as `medium_long_run` and `run_shape` classified as `anomaly`; old gate missed it, new gate catches it via name.
- New `_label_cooldown()` finds the trailing post-rep split that meets four gates: position after last rep, slower than work pace (but not >3.0× work pace — excludes walking-pace recovery jogs), avg HR ≥12 bpm below avg work-rep HR, substantial duration (≥0.4 mi or ≥3 min). Heat-aware: HR-drop floor relaxes to ≥6 bpm when `dew_point_f ≥ 60` or `heat_adjustment_pct ≥ 2.5%` (cardiac drift masks the normal post-effort HR drop). Result surfaced into LLM data context as `intervals.cooldown` so summaries say "the last mile was a cooldown" instead of "you hit a wall."
- System prompt updated to interpret `intervals.cooldown`, `workout_name`, and `shape_classification` correctly; explicitly forbids inferring planned reps from workout names.
- `_build_data_fingerprint()` (in `home_briefing_tasks.py`) now includes `Activity.workout_type`, `ActivitySplit` count, and `run_shape.summary.workout_classification`. Cache invalidates and brief regenerates when these async data points arrive — root cause of the "describes mile repeats as continuous effort" regression where the brief generated before splits landed and never re-ran.
- `routers/home.py` workout-structure prompt logic refactored into `_render_workout_structure_block()` with three honest branches: structured workout found (with shape-classification cross-check), splits available but no structure detected, splits not yet processed. New `splits_available` flag prevents prompts from falsely claiming splits were "examined" when they hadn't been processed.

**Demo Athlete Cloning Pipeline (`apps/api/scripts/clone_athlete_to_demo.py`, `apps/api/routers/garmin.py`):**
- New script clones a real athlete's full data into a demo account (e.g., `demo@strideiq.run`) for race-director / partner / investor walkthroughs. Transactional dry-run/commit modes; `COPY_TABLES` / `SKIP_TABLES` classification; dynamic schema introspection via `information_schema` to tolerate model-vs-DB drift; FK remapping with special case for `athlete_id`-as-PK 1:1 tables; "demo-" prefix on `external_activity_id` to dodge `uq_activity_provider_external_id`; Redis cache invalidation post-commit.
- Garmin OAuth guards added: `is_demo` flag on `Athlete` blocks `/auth-url` (403) and `/callback` (redirect to error). Mirrors existing Strava pattern. Demo viewers can navigate but cannot connect their own Garmin/Strava or modify the source athlete's data.
- Verified end-to-end on production for `demo@strideiq.run` — full data cloned, briefing regenerated through standard K2.5 pathway.

**Compare Tab Redesign — Strategic Decision (`docs/specs/COMPARE_REDESIGN.md`, `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`):**
- Founder identified the activity-page Compare tab as the weakest tab in the product. Decision captured: build "shape-resolved comparison" (rep N vs rep N, climb vs climb, fade vs fade) with single delta strip + per-feature cards + in-place picker. Top-line metric deltas (pace/time/HR/heat-adjusted) carry the "have I improved generally" question in the header. Empty-state with dignity when no comparable.
- **Sequenced behind Run Shape Canvas redesign** (founder flagged the current canvas as not telling the story well; redesign proposal pending) because Compare inherits the canvas's visual vocabulary. Direction 2 (pairwise gap decomposition / attribution bar) deferred to v2 pending honest pairwise attribution. Direction 3 (performance space scatter) deferred pending per-athlete-per-route expected pace model.

**Tests:** 11 new tests for heat-aware cooldown, 7 new tests for interval gate multi-signal, 4 new tests for prompt honesty, 3 new tests for fingerprint expansion, plus Garmin guard tests + cloning correctness/safety tests. Full `test_run_intelligence.py` suite green.

## [2026-04-18] briefing-morning-voice-quality-gates | Tighten morning_voice content gates without breaking the 80% good

The founder showed a production briefing that asked the athlete a literal question, stitched two findings together with "Separately,", and exceeded the 2-3 sentence morning_voice contract. About 80% of briefings are exceptional and improving; this change is purely additive so the good output keeps shipping unchanged.

**Root cause:** `build_fingerprint_prompt_section`'s EMERGING PATTERN block literally instructed the LLM to "rewrite in your coaching voice" the question "What do you think is driving this?". That framing is correct for the conversational coach but wrong for the one-way morning briefing.

**Three-layer fix in `services/coaching/_context.py`, `services/voice_validator.py`, `tasks/home_briefing_tasks.py`, `routers/home.py`:**
1. **Source:** `build_fingerprint_prompt_section` gains `include_emerging_question` kwarg. The morning_voice lane in `generate_coach_home_briefing` and `_build_rich_intelligence_context` now passes `False`, which rewrites the EMERGING block as a low-confidence observation with explicit "do not lead, do not ask a question" guidance. The chat coach (`coach_tools/brief.py`) keeps the question.
2. **Defense in depth:** `validate_voice_output` gains four content gates for `morning_voice` + `coach_noticed`:
   - `interrogative` (any "?" in the field)
   - `multi_topic` ("Separately,", "Additionally,", "Also,", "Meanwhile,", "On another note,", "Beyond that,")
   - `meta_preamble` ("Your data shows", "worth discussing/noting", "I've noticed a pattern", "Looking at your data", "The data suggests")
   - `sentence_cap` (>3 sentences in morning_voice)
3. **Recovery:** new `_strip_disallowed_sentences` helper removes only the sentences that trip the content gates and re-validates the remainder. The worker (`home_briefing_tasks`) and the read-time normaliser (`_normalize_cached_briefing_payload`) both call strip-and-recover before falling back to the deterministic string. Preserves the 80% of good content in a partially-bad briefing — only when nothing usable remains do we publish the fallback.

**Sentence splitter** now preserves terminators (required for the interrogative gate to detect "?"-ending sentences after splitting) and keeps mid-decimal dots together (so "7.5 hours" stays one token, which the existing sleep-grounding strip relies on).

**Tests:** 30 new tests in `test_home_voice_quality_gates.py` against the verbatim bad text from the production screenshot — every gate is covered and the verbatim good `coach_noticed` from the same screenshot is asserted to keep passing. Existing 274 briefing/coach tests stay green.

## [2026-04-18] nutrition-phases-1-2-3-end-to-end | Past-day editing, per-athlete food overrides, saved meals (meal templates)

Three product phases + two follow-up fixes shipped in one morning. Athletes can backfill missed meals on past days, the system remembers macro corrections per athlete, and recurring meals can be saved by name and re-logged in one tap.

**Phase 1 — Past-day editing (60-day window) (`apps/api/routers/nutrition.py`, `apps/web/app/nutrition/page.tsx`):**
- New `_validate_entry_date()` helper + `MAX_BACKLOG_DAYS=60` constant. Wired into `POST /v1/nutrition`, `PUT /v1/nutrition/{id}`, `PATCH /v1/nutrition/{id}`. Future dates → 400; >60d old → 400; today..today-60 allowed.
- **Phase 1 redo (commit `501e823`):** the first pass shipped a macros-only inline form on the History tab. That defeated the whole point — food database, photo parser, barcode scanner, NL parser, and fueling shelf were all unreachable when adding to a prior day. The redo introduces a shared `entryDate` state (today on Today tab, `selectedDate` on History) threaded through every create path: photo confirm, barcode confirm, NL parse draft, manual form, and shelf one-tap log. The hidden file input and Type/NL form are lifted to page root so they stay mounted across tab switches. `FuelingLogRequest` gains an optional `entry_date`; `log_fueling` defaults to athlete-local today and runs through `_validate_entry_date` so shelf-tap backfill respects the same window. Toast copy distinguishes today vs backfill ("Logged to Apr 17"). The originally-shipped pass was sub-par; the redo is the change that should have shipped first.
- **Field rename (commit `53fe7d7`):** `FuelingLogRequest.date` → `entry_date`. Pydantic v2 was silently coercing the new `Optional[date]` field to `None` because the field name `date` shadowed the imported `date` type during annotation evaluation, so every backfill request returned 422 `none_required` ("Input should be None"). Renaming eliminates the shadowing.

**Phase 2 — Per-athlete food overrides (`athlete_food_override_001` migration, `services/food_override_service.py`):**
- When the user edits the macros of a logged food that came from a barcode scan or USDA lookup, persist that correction as an `athlete_food_override` keyed on `(athlete_id, identifier)`. Next scan/parse for the same food returns the corrected values automatically and tags the response with `is_athlete_override=true` so the UI can show a "Your values" chip.
- New `athlete_food_override` table with one-identifier check constraint covering UPC, FDC ID, and `fueling_product_id`, plus unique partial indexes per identifier. New `source_fdc_id` and `source_upc` columns on `nutrition_entry` so the edit handler can attribute the entry back to a food.
- `food_override_service`: `find_override` (precedence UPC > FPID > FDC), `upsert_override`, `record_override_applied`, schema-light response patcher.
- Wires: `scan_barcode` and `parse_photo` apply overrides; both also honour overrides for foods we don't have in our catalog yet. `create_nutrition_entry` / `update_nutrition_entry` / `patch_nutrition_entry` persist source ids and auto-learn an override on macro edits (best-effort, never blocks the user's save).
- **Edit auto-learn fix (commit `8d08436`):** `_maybe_learn_override_from_entry` was passing `fluid_ml=None` and `sodium_mg=None` to `upsert_override`, but `upsert_override` only accepts `sodium_mg`. The TypeError was swallowed by the helper's broad `except`, so edits silently failed to persist any override. Both unsupported kwargs dropped.

**Phase 3 — Saved meals + name-this-meal prompt (`meal_template_named_001` migration, `services/meal_template_service.py`):**
- Athletes can save recurring meals ("Workday Breakfast") under a name and re-log them in one tap. Implicitly learned meal patterns now surface a "name this meal" prompt once they've been confirmed three times so they become reusable.
- Schema: `meal_template` gains `name`, `is_user_named`, `name_prompted_at`, `created_at`. Partial index on `(athlete_id) WHERE is_user_named = true` for the named-meals picker.
- Service rewrite: `TemplateItem` dataclass + `save_named_template` that promotes an existing implicit row instead of duplicating; `list_named_templates` / `get` / `update` / `delete` CRUD; `log_template_for_athlete` that builds a `NutritionEntry` with summed macros and `macro_source = "meal_template"`; `mark_name_prompt_shown` (idempotent); `find_template` returns `should_prompt_name` + `is_user_named`.
- **Critical fix:** `upsert_template` now skips single-item entries to stop the implicit learner from polluting the table with single barcode logs (this was the root of the "templates are noise" bug).
- Endpoints: `GET/POST/PATCH/DELETE /v1/nutrition/meals`, `POST /v1/nutrition/meals/{id}/log` (respects 60-day past-day window), `POST /v1/nutrition/meals/{id}/dismiss-name-prompt`. `create_nutrition_entry` no longer upserts noise — only learns from comma-separated, multi-item, non-barcode entries.
- Frontend: new "Meals" tab with create/edit form (name + per-item macros), saved-meals list, one-tap "Log" / "Edit" / delete. Logs land on `selectedDate` so the same picker doubles as a backfill tool.

**CI:** Phase 1/2/3 nutrition tests added to the Backend Smoke (Golden Paths) job so they actually run on every push (Backend Tests was gated to schedule/dispatch only, which had silently skipped Phase 2). `EXPECTED_HEADS` bumped to `meal_template_named_001`.

**Tests:** Override service unit tests (identifier validation, upsert/find roundtrip, precedence, list, record-applied, response patcher) + endpoint integration tests for the full scan→log→edit→rescan loop, PATCH auto-learn, per-athlete isolation. Meal template service unit tests (signature normalization, single-item skip, threshold gating, named promotion, list filter, rename, item replace, delete, log totals, idempotent name-prompt) + endpoint integration tests (create + list, log creates entry with correct macros, log respects past-day/future-date guard, rename, delete, per-athlete isolation). 14 cases in `test_nutrition_past_day_window.py` covering validator boundaries, POST window, PUT window, GET roundtrip on backfilled day.

**Known gap (carried forward):** the Meals-tab create form takes per-item macros as raw inputs — it does not yet wire to `/v1/nutrition/parse` or USDA autocomplete, so first-time saved-meal creation still requires typing macros. Wiring is the next nutrition task.

## [2026-04-15] test-suite-root-cause-fixes | 53 test failures root-caused and fixed (3584 pass, 0 fail)

Following the project reorg (models/, services/sync/, services/intelligence/, services/coaching/, services/coach_tools/ package splits), 53 tests failed. All were diagnosed to root causes across 9 categories and fixed with production-quality corrections — not test patches.

**Production code fixes (5 files):**
- `duplicate_scanner.py`: Duration-based duplicate fallback now also checks distance — prevents merging activities with identical durations but vastly different distances (e.g., a 30-min easy run and a 30-min tempo run).
- `garmin_adapter.py`: New `adapt_activity_file_record()` function translates raw Garmin activity-file webhook fields (`summaryId`, `fileType`, `callbackURL`) into internal names at the adapter boundary. Garmin field names no longer leak past the adapter layer.
- `n1_insight_generator.py`: Added `daily_caffeine_mg` to `FRIENDLY_NAMES` — was causing KeyError when caffeine correlations surfaced.
- `extract_athlete_profiles.py`: Replaced hardcoded email list with `STRIDEIQ_TARGET_EMAILS` env var. No PII in source.
- `training-pace-tables.json` + `page.tsx`: Regenerated all pace values from the authoritative `_RPI_PACE_TABLE` in `rpi_calculator.py`. Updated 24 hardcoded pace references across 4 distance PSEO pages (5K, 10K, half, marathon BLUFs and FAQs).

**Test fix categories (20 test files):**
1. **UUID validation (11 tests)**: Tests passed string IDs like `"athlete-1"` to code that now correctly validates UUIDs. Updated to `str(uuid4())`.
2. **Mock configuration (9 tests)**: Missing `activity.sport = "run"` on fixtures, insufficient `side_effect` entries for sequential DB queries, missing `threshold_value = None` on mock findings.
3. **Tuple unpacking (9 tests)**: `_build_briefing_prompt` returns 7-tuple but mocks provided 6. Added `local_now` as 7th value.
4. **Assertion drift (5 tests)**: Tests checked implementation details (`".limit(3)" in src`) instead of behavior (`len(result) >= 3`). Updated to match current code.
5. **Mock blocking (2 tests)**: Timezone singleton not reset between tests; wrong patch target for `get_athlete_timezone_from_db`.
6. **Garmin source contract (2 tests)**: Tests referenced raw Garmin field names that now only exist inside the adapter.
7. **Phase 3B/3C logic (9 tests)**: Tests patched wrong LLM call path; used `efficiency` metric that hits `_is_obvious` filter. Updated to patch `_call_narrative_llm` directly and use `completion_rate`.
8. **RPI calibration (9 tests)**: `PACE_TESTS` reference values drifted from `_RPI_PACE_TABLE`. Aligned with authoritative source.
9. **Logic bugs (2 tests)**: Fitness bank RPI threshold test expected `< 35.0` but code correctly uses `>= 15.0` (inclusive of beginners). Cost cap test asserted old defaults instead of current env-var-loaded values.
10. **Budget cap test (1 test)**: `patch.dict("os.environ")` has no effect on constants evaluated at import time. Patched module-level constant directly.

## [2026-04-11] plan-engine-v2-wired | V2 plan engine wired to production route

- **New file:** `plan_saver.py` — Maps V2WeekPlan/V2DayPlan to TrainingPlan + PlannedWorkout DB rows. Handles distance estimation from segments (explicit distance_m, time-based duration×pace, distance_range midpoint), duration estimation, JSONB segment serialization, coach notes. Sets `generation_method = "v2"`.
- **New file:** `router_adapter.py` — Loads FitnessBank, FingerprintParams, LoadContext from DB; maps ConstraintAwarePlanRequest to V2 inputs (including TuneUpRace conversion); calls `generate_plan_v2()`; saves via plan_saver; stitches V1-compatible response shape (fitness_bank, model, prediction, volume_contract, weeks).
- **New file:** `test_plan_saver.py` — 17 unit tests covering distance/duration estimation, segments JSON, coach notes, tune-up race mapping, plan start alignment.
- **Modified:** `routers/plan_generation.py` — Added `engine: Optional[str] = None` query parameter to `POST /v2/plans/constraint-aware`. When `engine=v2` and user is admin/owner, routes through V2. V1 remains default.
- **Updated:** `plan-engine.md` — Added "V2 Engine — Production Status" section with architecture table, V1 vs V2 comparison, API access, production verification results, rollout plan.
- **Updated:** `infrastructure.md` — Migration heads updated to `plan_engine_v2_001`, recent migrations list updated.
- **Updated:** `index.md` — Plan engine quick reference shows both V1 and V2. All Pages table updated.
- **Updated:** `frontend.md` — Plans/create route note about `engine=v2` query param.
- **Updated:** `PLAN_ENGINE_V2_MASTER_PLAN.md` — Phases 1-5 marked complete, Phase 6 partially complete.
- **Updated:** `TRAINING_PLAN_REBUILD_PLAN.md` — Operational update for V2 sandbox + migration wiring.
- **Production verified:** V2 dry-run (23-week marathon, 1208mi total, 62.6 peak) and V1 default (24-week marathon, 1161mi total) both passing on production.

## [2026-04-10] rpi-table-fix | RPI calculator replaced with derived hardcoded table

- **Replaced:** `rpi_calculator.py` — removed the broken `INTENSITY_TABLE` + formula pipeline that regressed 3+ times at low RPIs (produced 7:41/mi interval for a 62:00 10K runner). Replaced with `_RPI_PACE_TABLE`: a 66-row hardcoded lookup (RPI 20-85) derived from the published Daniels/Gilbert oxygen cost + time-to-exhaustion equations, with a slow-runner correction for RPI < 39. Verified against official reference calculator to +/- 1 second at all tested levels.
- **New file:** `rpi_pace_derivation.py` — full derivation script with formulas, constants, verification against reference, and generated table. Serves as evidence the table was derived, not copied.
- **Removed:** `MAX_T_TO_I_GAP` band-aid from `workout_prescription.py` — no longer needed since the table produces physiologically correct T-I gaps natively.
- **Updated:** `plan-engine.md` — added RPI-to-Training-Pace Calculator section with derivation method, sample paces, and critical rule against formula replacement.
- **Production fix:** Larry Shaffer's plan paces updated from old values (E=12:30, T=9:37, I=7:41) to correct derived values (E=11:14, T=9:43, I=8:40, R=8:16).

## [2026-04-10] plan-engine-kb-nutrition-elevation | Plan engine V2 spec, coaching science KB, nutrition elevated

- **Updated:** `plan-engine.md` — Added "Next-Generation Algorithm Spec (V2)" section: Build/Maintain/Custom modes, extension-based progression, build-over-build memory, unified segments schema, effort-based descriptions, fueling targets. Added coaching science KB table (13 documents: Davis, Green, Roche). Added single-hierarchy sliding-bottleneck model. Updated sources list.
- **Updated:** `nutrition.md` — Added "Nutrition as a First-Class Metric" section: elevated to #3 in hierarchy, plan generator fueling targets by training age, briefing integration, future product calculator. Updated key decisions to reflect first-class status.
- **Updated:** `product-vision.md` — Plan engine now references V2 spec and 13 KB docs. Nutrition marked as first-class metric. Added priorities 19-22: Training Lifecycle (SPECIFIED), Algorithm V2 (SPECIFIED), Native App (PRELIMINARY), Audio Coach (SCOPED).
- **Updated:** `index.md` — date bumped.

## [2026-04-10] nutrition-telemetry-reports | Three features shipped, three wiki pages added

- **New page:** `nutrition.md` — AI Nutrition Intelligence: photo/barcode/NL parsing, fueling shelf, nutrition planning, load-adaptive targets, USDA integration, correlation engine wiring, coach tools
- **New page:** `telemetry.md` — Usage Telemetry: PageView model, usePageTracking hook, admin usage report, no third-party analytics
- **New page:** `reports.md` — Unified Reports: cross-domain health/activities/nutrition/body-comp reporting, curated + extended metrics, CSV export
- **Updated:** `index.md` — date bumped to Apr 10, All Pages table expanded with Nutrition, Telemetry, Reports links
- **Updated:** `product-vision.md` — priorities 16-18 marked SHIPPED, What's Built section expanded with nutrition, telemetry, reports. Scale numbers updated (85 models, 113 migrations, 79 correlation inputs)
- **Updated:** `frontend.md` — added `/nutrition` and `/reports` routes, `components/nutrition/` directory, `usePageTracking` hook, nutrition entry inline editing
- **Updated:** `infrastructure.md` — migration count 113, model count 85, expected heads `usage_telemetry_001`, new routers table (nutrition, reports, telemetry)
- **Updated:** `coach-architecture.md` — tools count ~26, added `get_nutrition_correlations` and `get_nutrition_log` tools, nutrition context in athlete brief, key decision entry
- **Updated:** `correlation-engine.md` — added Nutrition Inputs section with 9 metrics from `aggregate_fueling_inputs()`

## [2026-04-08] strategy-update | Strategy priorities 14-16 added

- Added Compound Recovery Signals (14), Personal Coach Tier (15), AI Nutrition Intelligence (16) to product-vision.md
- Added HRV÷RHR compound signal to correlation-engine.md What's Next

## [2026-04-08] review-fixes | Founder review — 5 corrections

- **Fixed:** Ghost traces incorrectly stated as removed; they are live in production (`RouteContext.tsx`, `RouteHistory.tsx`, opacity tiers by recency)
- **Fixed:** Deploy command used `docker restart` (old image) instead of `docker compose up -d --build` (rebuild all). Corrected in index.md and infrastructure.md.
- **Fixed:** Missing null-structure guardrail — the `else` branch in `_summarize_workout_structure` that explicitly tells the LLM "NO WORKOUT STRUCTURE DETECTED" was not documented
- **Fixed:** Token cap table now highlights that the opus cap is the binding constraint (2M standard, 5M VIP) since all traffic routes through the opus lane
- **Fixed:** Index Quick Reference now separates coach model (Kimi K2.5) from briefing model (Claude Opus 4.6)

## [2026-04-08] init | Wiki created from 339 source documents

- **Pages created:** index.md, product-vision.md, coach-architecture.md, briefing-system.md, correlation-engine.md, plan-engine.md, garmin-integration.md, activity-processing.md, operating-manual.md, infrastructure.md, monetization.md, frontend.md, quality-trust.md, decisions.md
- **Source documents read:** 339 markdown files across docs/, docs/specs/, docs/references/, docs/adr/, docs/garmin-portal/, docs/phase2/, docs/phase3/, docs/research/
- **Additional sources:** Codebase structure (services/, routers/, tasks/, models.py, components/, app/, docker-compose files, CI workflows)
- **Known gaps:**
  - Strava integration: minimal wiki coverage (Strava is secondary to Garmin; basic sync exists but not a focus area)
  - `docs/BUILDER_INSTRUCTIONS_2026-03-20_PLAN_QUALITY_RECOVERY_V2.md` referenced by other docs but missing from repo
  - ADR-052 has duplicate numbering (two different topics)
  - Women's Health Intelligence Layer: strategic priority #7 but no implementation or spec exists
  - Swimming data parsing: sport is accepted but no specialized processing beyond basic metrics
