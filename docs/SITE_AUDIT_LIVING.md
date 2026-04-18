# StrideIQ — Living Site Audit

**Purpose:** Canonical full-product audit. This is the always-current inventory of what exists on the site, what is shipped, and what operational tools are available.
**Last updated:** April 18, 2026 (Activity Intelligence + home briefing honesty fixes — multi-signal interval gate, heat-aware cooldown labelling, fingerprint expansion to invalidate stale briefs, honest split-availability prompt; demo athlete cloning pipeline + Garmin OAuth `is_demo` guards; nutrition Phases 1-3 — past-day backfill in 60-day window using all input modes, per-athlete food overrides, saved meal templates with name-this-meal prompt; morning_voice quality gates — interrogative/multi-topic/meta-preamble/sentence-cap with strip-and-recover; Compare tab redesign decision captured + sequenced behind Run Shape Canvas redesign. Prior: Project reorg — models/, services/ package splits; god file decomposition — ai_coach.py into coaching/ package, coach_tools.py into coach_tools/ package; 53 test failures root-caused and fixed; Plan Engine V2 wired to production)
**Last updated by:** Agent (advisor + builder)

---

## 0. Delta Since Last Audit (Apr 6)

Shipped and now live in product/system behavior:

- **Activity Intelligence + Home Briefing Honesty Fixes (Apr 18, 2026)**: Three commits shipped. **(1) Interval gate broadened** in `services/run_intelligence.py` — `_is_interval_workout()` now triggers on any of three signals: `workout_type` in canonical interval set, `run_shape.summary.workout_classification` in `STRUCTURED_SHAPE_CLASSIFICATIONS` frozenset, or `workout_name` matches rep-notation regex (`6x800`, `4 x mile`) / structured-workout keywords (interval, repeats, fartlek, tempo, cruise, threshold, hill repeats). Founder regression: Garmin tagged a "Meridian — 2 x 2 x mile" workout as `medium_long_run` and `run_shape` classified as `anomaly` — old gate missed it; new gate catches it via name. **(2) Cooldown labeller added** — new `_label_cooldown()` finds the trailing post-rep split that meets four gates: position after last rep, slower than work pace (but not >3.0x — excludes walking-pace recovery jogs), avg HR ≥12 bpm below avg work-rep HR (heat-relaxed to ≥6 bpm when `dew_point_f >= 60` or `heat_adjustment_pct >= 2.5%` — accounts for cardiac drift), substantial duration (`>=0.4 mi or >=3 min`). Result surfaced into LLM data context as `intervals.cooldown`. **(3) System prompt updated** to interpret `intervals.cooldown`, `workout_name`, and `shape_classification` correctly — explicitly forbids inferring planned reps from workout names. **(4) Home briefing fingerprint expanded** in `tasks/home_briefing_tasks.py` — `_build_data_fingerprint()` now includes `Activity.workout_type`, `ActivitySplit` count, and `run_shape.summary.workout_classification` so cache invalidates and brief regenerates when these async data points arrive (root cause of "describes mile repeats as continuous effort" regression). **(5) Honest split-availability prompt** in `routers/home.py` — refactored workout structure prompt logic into `_render_workout_structure_block()` with three branches: structured workout found (with shape-classification cross-check), splits available but no structure detected, splits not yet processed. New `splits_available` flag prevents prompts from falsely claiming splits were "examined" when they hadn't been. **(6) Tests:** 11 new tests for heat-aware cooldown, 7 new tests for interval gate multi-signal, 4 new tests for prompt honesty, 3 new tests for fingerprint expansion. All 116 tests in `test_run_intelligence.py` pass. **(7) Production verified:** Founder's Meridian — 2 x 2 x mile activity now correctly labeled as intervals; brief regenerated with "mile repeats averaging 6:23/mi" instead of "continuous effort." Files: `apps/api/services/run_intelligence.py`, `apps/api/routers/home.py`, `apps/api/tasks/home_briefing_tasks.py`, `apps/api/tests/test_run_intelligence.py`, `apps/api/tests/test_home_briefing_cache.py`.

- **Demo Athlete Cloning Pipeline (Apr 18, 2026)**: New script `apps/api/scripts/clone_athlete_to_demo.py` clones a real athlete's full data into a demo account (e.g., `demo@strideiq.run`) for race-director / partner / investor walkthroughs without exposing the source athlete's account or letting the demo viewer modify data or connect their own Garmin/Strava. **(1) Garmin OAuth guards** added to `routers/garmin.py` — `is_demo` flag on `Athlete` blocks `/auth-url` (403) and `/callback` (redirect to error). Mirrors existing Strava pattern. **(2) Cloning script** with transactional dry-run/commit modes, `COPY_TABLES`/`SKIP_TABLES` classification, dynamic schema introspection via `information_schema` to tolerate model-vs-DB drift, FK remapping with special-case for `athlete_id`-as-PK tables, "demo-" prefix on `external_activity_id` to dodge `uq_activity_provider_external_id`, Redis cache invalidation post-commit. **(3) Tests:** Garmin guard tests + cloning correctness/safety tests. **(4) Verified end-to-end on production** for `demo@strideiq.run` — full data cloned, Garmin/Strava connect blocked, briefing regenerated through standard K2.5 pathway.

- **Strategic Decision Captured: Compare Tab Redesign (Apr 18, 2026)**: Founder identified the activity-page Compare tab as the weakest tab in the product. Full discussion captured in `docs/specs/COMPARE_REDESIGN.md`. Decision: build "shape-resolved comparison" (rep N vs rep N, climb vs climb, fade vs fade) with single delta strip + per-feature cards + in-place picker. Top-line metric deltas (pace/time/HR/heat-adjusted) carry the "have I improved generally" question in the header. Empty-state with dignity when no comparable. **Sequenced behind Run Shape Canvas redesign** (founder flagged the current canvas as not telling the story well; redesign proposal pending) because Compare inherits the canvas's visual vocabulary. Direction 2 (pairwise gap decomposition / attribution bar) deferred to v2 pending honest pairwise attribution. Direction 3 (performance space scatter) deferred pending per-athlete-per-route expected pace model. Design philosophy doc updated to reference the spec under Activity Detail Page.

- **Briefing morning_voice quality gates (Apr 18, 2026)**: Founder showed a production briefing that asked the athlete a literal question, stitched two findings together with "Separately,", and exceeded the 2-3 sentence morning_voice contract. About 80% of briefings were already exceptional; this change is purely additive so the good output keeps shipping unchanged. **(1) Source fix:** `build_fingerprint_prompt_section` (in `services/coaching/_context.py`) gains `include_emerging_question` kwarg. The morning_voice lane in `generate_coach_home_briefing` and `_build_rich_intelligence_context` passes `False`, which rewrites the EMERGING PATTERN block as a low-confidence observation with explicit "do not lead, do not ask a question" guidance. The chat coach (`coach_tools/brief.py`) keeps the question — root cause was that one prompt block literally instructed the LLM to "rewrite in your coaching voice" the question "What do you think is driving this?", which is correct for the conversational coach but wrong for the one-way morning briefing. **(2) Defense in depth:** `validate_voice_output` gains four content gates for `morning_voice` + `coach_noticed`: `interrogative` (any "?"), `multi_topic` ("Separately,", "Additionally,", "Also,", "Meanwhile,", "On another note,", "Beyond that,"), `meta_preamble` ("Your data shows", "worth discussing/noting", "I've noticed a pattern", "Looking at your data", "The data suggests"), `sentence_cap` (>3 sentences in morning_voice). **(3) Recovery:** new `_strip_disallowed_sentences` helper removes only the offending sentences and re-validates the remainder. The worker (`tasks/home_briefing_tasks.py`) and the read-time normaliser (`_normalize_cached_briefing_payload` in `routers/home.py`) both call strip-and-recover before falling back to the deterministic string — preserves 80% good content in a partially-bad briefing. **(4) Sentence splitter** now preserves terminators (the interrogative gate needs to see "?"-ending sentences after splitting) and keeps mid-decimal dots together (so "7.5 hours" stays one token, which the existing sleep-grounding strip relies on). **(5) Tests:** 30 new tests in `test_home_voice_quality_gates.py` against the verbatim bad text from the production screenshot — every gate covered, verbatim good `coach_noticed` from the same screenshot asserted to keep passing. Existing 274 briefing/coach tests stay green.

- **Nutrition Phases 1-3 — Past-day editing, food overrides, saved meals (Apr 18, 2026)**: Three product phases + two follow-up fixes shipped in one morning. **(1) Phase 1 — Past-day editing (60-day window):** new `_validate_entry_date()` + `MAX_BACKLOG_DAYS=60` wired into `POST/PUT/PATCH /v1/nutrition` and `POST /v1/nutrition/log-fueling`. Future dates → 400; >60d old → 400. The first pass shipped a macros-only inline form on History tab (sub-par — defeated the point); **redo (commit `501e823`)** introduced shared `entryDate` state threaded through every create path: photo confirm, barcode confirm, NL parse draft, manual form, and shelf one-tap log. Hidden file input and Type/NL form lifted to page root so they stay mounted across tab switches. Toast copy distinguishes today vs backfill ("Logged to Apr 17"). Field rename `FuelingLogRequest.date` → `entry_date` (commit `53fe7d7`) — Pydantic v2 was silently coercing the new `Optional[date]` field to `None` because the field name `date` shadowed the imported `date` type during annotation evaluation, returning 422 `none_required`. **(2) Phase 2 — Per-athlete food overrides:** new `athlete_food_override` table (migration `athlete_food_override_001`) keyed on `(athlete_id, identifier)` with one-identifier check constraint and unique partial indexes per identifier (UPC > FPID > FDC). New `source_fdc_id` and `source_upc` columns on `nutrition_entry`. Service `services/food_override_service.py`: `find_override`, `upsert_override`, `record_override_applied`, response patcher. Wired into `scan_barcode`, `parse_photo`, `create_nutrition_entry`, `update_nutrition_entry`, `patch_nutrition_entry`. UI shows "Your values" chip when `is_athlete_override=true`. **Edit auto-learn fix (commit `8d08436`):** `_maybe_learn_override_from_entry` was passing `fluid_ml=None` and `sodium_mg=None` to `upsert_override` which only accepts `sodium_mg`; TypeError swallowed by broad `except`, edits silently failed to persist any override. Both unsupported kwargs dropped. **(3) Phase 3 — Saved meals + name-this-meal prompt:** new `meal_template` schema (migration `meal_template_named_001`) gains `name`, `is_user_named`, `name_prompted_at`, `created_at` with partial index on `(athlete_id) WHERE is_user_named = true`. Service `services/meal_template_service.py` rewrite: `TemplateItem` dataclass, `save_named_template` promotes existing implicit row in place, full CRUD, `log_template_for_athlete` builds `NutritionEntry` with summed macros and `macro_source = "meal_template"`, `mark_name_prompt_shown` (idempotent). **Critical fix:** `upsert_template` now skips single-item entries to stop the implicit learner from polluting the table with single barcode logs (root of "templates are noise" bug). Endpoints: `GET/POST/PATCH/DELETE /v1/nutrition/meals`, `POST /v1/nutrition/meals/{id}/log` (respects 60-day window), `POST /v1/nutrition/meals/{id}/dismiss-name-prompt`. Frontend: new "Meals" tab with create/edit form, saved-meals list, one-tap "Log"/"Edit"/delete; logs land on `selectedDate` so the picker doubles as a backfill tool. **(4) CI:** Phase 1/2/3 nutrition tests added to Backend Smoke (Golden Paths) so they actually run on every push (Backend Tests was gated to schedule/dispatch only and silently skipped Phase 2). `EXPECTED_HEADS` bumped to `meal_template_named_001`. **(5) Tests:** override service unit tests + endpoint integration tests for full scan→log→edit→rescan loop, PATCH auto-learn, per-athlete isolation; meal template service unit tests + endpoint integration tests; 14 cases in `test_nutrition_past_day_window.py`. **(6) Known gap:** Meals-tab create form takes per-item macros as raw inputs — does not yet wire to `/v1/nutrition/parse` or USDA autocomplete, so first-time saved-meal creation still requires typing macros. Wiring the parser into the meal builder is the next nutrition task. Files: `apps/api/routers/nutrition.py`, `apps/api/services/food_override_service.py`, `apps/api/services/meal_template_service.py`, `apps/api/migrations/versions/athlete_food_override_001.py`, `apps/api/migrations/versions/meal_template_named_001.py`, `apps/web/app/nutrition/page.tsx`.

- **Project Reorg — Package Splits (Apr 15, 2026)**: Monolithic files split into maintainable packages with backward-compatible shims. **(1) models.py** (2800+ lines) split into `models/` package: `activity.py`, `athlete.py`, `plan.py`, `checkin.py`, `intelligence.py`, `garmin.py`, `coaching.py`, `nutrition.py`, `misc.py`. All 50+ model classes accessible via `from models import X` (unchanged). **(2) services/sync/** — Garmin adapter, Strava sync, duplicate scanner, timezone utils moved from flat services/. **(3) services/intelligence/** — Correlation engine, N1 insight generator, workout narrative, trend attribution, fingerprint context moved. **(4) ai_coach.py** (5690 lines) decomposed into `services/coaching/` package with 7 mixins: `_budget.py`, `_context.py`, `_llm.py`, `_prescriptions.py`, `_tools.py`, `_wellness.py`, `_constants.py`, `core.py`. AICoach class uses mixin inheritance. **(5) coach_tools.py** (4860 lines) decomposed into `services/coach_tools/` package with 9 submodules: `brief.py`, `wellness.py`, `fitness.py`, `nutrition.py`, `plans.py`, `progress.py`, `formatting.py`, `run_context.py`, `race.py`. **(6) All old import paths** work via `importlib` re-export shims — zero breaking changes for existing code or tests. **(7) `_AI_CONTEXT_/`** directory (146 files, 77,495 lines) deleted — stale chat dumps that added noise to every agent session. **(8) `workout_registry.json`** relocated from `services/` to `data/` with P0-GATE waiver attestation.

- **53 Test Failures Root-Caused and Fixed (Apr 15, 2026)**: Full test suite brought from 53 failures to 0 (3584 pass). Not test patches — root cause fixes that improve program quality. **(1) Production:** Duplicate scanner strengthened with distance check on duration fallback. Garmin adapter source contract enforced. Missing FRIENDLY_NAMES entry added. Hardcoded PII removed. PSEO pace tables regenerated from authoritative calculator. **(2) Tests:** 9 categories of root causes fixed across 20 test files. See wiki log for full breakdown.

- **Plan Engine V2 Wired to Production (Apr 11, 2026)**: V2 plan engine accessible via `POST /v2/plans/constraint-aware?engine=v2` (admin/owner only). New files: `plan_saver.py`, `router_adapter.py`, 17 unit tests. V1 remains default. Production verified: V2 dry-run (23-week marathon, 1208mi total, 62.6 peak) and V1 default both passing.

- **RPI Calculator Table Fix (Apr 10, 2026)**: Broken `INTENSITY_TABLE` + formula pipeline replaced with `_RPI_PACE_TABLE`: 66-row hardcoded lookup derived from published Daniels/Gilbert equations. Verified to +/- 1 second against official reference. `MAX_T_TO_I_GAP` band-aid removed.

Previous delta (Apr 4-6):

- **Garmin Activity Files Webhook — FIT File Pipeline (Apr 6, 2026)**: Strength exercise set data now flows from Garmin watches to the existing `StrengthDetail.tsx` display. **(1) Webhook endpoint:** `POST /v1/garmin/webhook/activity-files` added to `routers/garmin_webhooks.py` — follows the same Layer 1-4 security pattern as all other Garmin webhooks (auth header, envelope parsing with `data_key="activityFiles"`, athlete resolution, fire-and-forget dispatch). Always returns 200 to prevent Garmin retry storms. **(2) Celery task:** `process_garmin_activity_file_task` in `tasks/garmin_webhook_tasks.py` — downloads FIT file from Garmin's callback URL (temporary token in URL, no auth header needed), parses via `fitparse`, matches to existing Activity via `garmin_activity_id` or `external_id`, and feeds parsed data into existing `process_strength_activity()` pipeline. Non-strength activities gracefully skipped. Activity-not-found triggers retry with 30s countdown (timing race with activity webhook). **(3) FIT parser:** New `services/fit_parser.py` — `extract_exercise_sets_from_fit()` converts binary FIT bytes into the `{"exerciseSets": [...]}` format expected by `strength_parser.parse_exercise_sets()`. Handles FIT SDK integer enums for 34 exercise categories and set types, weight normalization (grams → kg heuristic for values > 1000), duration normalization (ms → seconds for values > 60000). Logs first `set` message field names for verification. **(4) Dead code removed:** `fetch_garmin_exercise_sets_task` (called non-existent REST endpoint `/wellness-api/rest/activities/{id}/exerciseSets`), its dispatch from `process_garmin_activity_task`, and associated constants (`_GARMIN_ACTIVITY_API_BASE`, `_EXERCISE_SETS_TIMEOUT_S`) all deleted. **(5) Dependency:** `fitparse>=1.0.0,<2.0.0` added to `requirements.txt`. **(6) Limitation:** No backfill endpoint exists for Garmin activityFiles (confirmed 404). Existing strength activities with `sets=0` cannot be retroactively enriched via API. Pipeline works for new activities going forward. Files: `apps/api/routers/garmin_webhooks.py`, `apps/api/tasks/garmin_webhook_tasks.py`, `apps/api/services/fit_parser.py`, `apps/api/requirements.txt`.

- **LLM-Coached Weekly Digest Email (Apr 6, 2026)**: Weekly digest email now uses Kimi K2.5 to filter and interpret raw correlation findings instead of dumping them directly. **(1) Coaching prompt:** `_DIGEST_COACHING_SYSTEM` in `services/email_service.py` — instructs LLM to filter findings through four rules: actionable (athlete can change it), non-obvious (not tautologies), reliable data (low-confidence signals deprioritized), non-contradictory (reconcile or pick strongest). Writing rules: plain athlete language, direction + strength per bullet, max 3-5 bullets, under 120 words, no greetings/sign-offs. **(2) Pipeline:** `digest_tasks.py` builds structured `findings_context` string with `friendly_signal_name`, raw key, correlation coefficient, direction, strength percentage, and sample size for top 20 correlations. Passes to `email_service.send_coached_digest()`. **(3) LLM call:** `_generate_coached_body()` calls Kimi K2.5 with `max_tokens=400`, `temperature=0.3`, `disable_thinking=True`. **(4) Fallback:** If LLM returns empty/too-short body or call fails, falls back to template-based email (renamed `_send_template_fallback()`). **(5) Template fixes (shipped alongside):** `{analysis_period_days}` f-string interpolation bug fixed, raw metric names replaced with `friendly_signal_name()` mappings, directionality added via `_HIGHER_IS_BETTER`/`_LOWER_IS_BETTER` sets and `_direction_phrase()` helper. **(6) Critical fix:** `LLMResponse` text field accessed via `result.get("text")` not `result.get("content")` — the `content` key does not exist on `LLMResponse(TypedDict)`. Files: `apps/api/services/email_service.py`, `apps/api/tasks/digest_tasks.py`.

- **Fact Extraction → Lifecycle Wire (Apr 5, 2026)**: After `extract_athlete_facts` commits new facts from a coach conversation, the task now checks if any `limiter_context` facts were extracted. If so, it immediately invokes `classify_lifecycle_states()` for the athlete. This closes the briefing→coach response loop: athlete taps emerging pattern → talks to coach → provides context → fact extracted → lifecycle classifier runs → finding promoted to `active` (confirmed) or `closed` (explained away) → briefing stops asking the same question. Previously, this reclassification only happened during the nightly correlation sweep, meaning responses could lag 12-24 hours before affecting the briefing. Non-limiter facts (body_composition, strength_pr, etc.) do not trigger reclassification. Classifier failure is non-fatal — logged as warning, does not affect fact persistence. File: `apps/api/tasks/fact_extraction_task.py`.

- **Tappable Briefing → Coach Flow with Finding Deep Link (Apr 5, 2026)**: The morning briefing's `coach_noticed` text is now tappable when it comes from a fingerprint finding, creating a seamless briefing→coach conversation flow. **(1) Backend — `CoachNoticed` schema:** Added `finding_id: Optional[str]` field. When `compute_coach_noticed()` selects a fingerprint-sourced finding, the `CorrelationFinding.id` is passed through. **(2) Backend — `ChatRequest`:** Added `finding_id: Optional[str]` to both `/v1/coach/chat` and `/v1/coach/chat/stream` endpoints. **(3) Backend — Finding context builder:** New `_build_finding_deep_link_context()` on `AICoach` — when `finding_id` is present in the first message, loads the `CorrelationFinding` by ID, builds a rich context block including: finding direction/strength, threshold with units, asymmetry, time lag, decay, lifecycle state, and the last 10 runs with timestamps/distances/paces. Injected into the athlete state with explicit instructions: "The athlete just tapped on this pattern from their morning briefing. They already read the question. Do NOT repeat it. Open mid-conversation with specific evidence, then invite response." **(4) Frontend — Home page:** `coach_noticed` text renders as a tappable `Link` (orange text with "→ Ask coach" indicator) when `finding_id` is present, navigating to `/coach?finding_id=<uuid>&q=<ask_coach_query>`. Both primary (when no morning_voice) and secondary positions handled. Non-fingerprint `coach_noticed` renders as plain text (unchanged). **(5) Frontend — Coach page:** `?finding_id` URL param detected. When both `finding_id` and `q` are present, message auto-sends on page load (no manual tap needed). `finding_id` passed in the first `chatStream` request body. Subsequent messages in the same session do not re-send `finding_id`. **(6) Frontend — TypeScript types:** `CoachNoticed.finding_id` and `ChatRequest.finding_id` added. Files: `apps/api/routers/home.py`, `apps/api/routers/ai_coach.py`, `apps/api/services/ai_coach.py`, `apps/web/app/home/page.tsx`, `apps/web/app/coach/page.tsx`, `apps/web/lib/api/services/home.ts`, `apps/web/lib/api/services/ai-coach.ts`.

- **Briefing Specificity Fix — Unit-Aware Finding Presentation (Apr 5, 2026)**: Correlation findings surfaced in the briefing and fingerprint prompt context now render with proper athlete-facing units instead of raw numbers. **(1) `SIGNAL_UNITS` dict** added to `services/fingerprint_context.py` — maps 80+ signal names to their display units (pace → min/mi, sleep → hours, time of day → AM/PM, elevation → ft, HRV → ms, etc.). **(2) `_format_value_with_unit()` helper** handles special formatting: pace as `M:SS/mi`, time of day as `7 AM`, elevation meters converted to feet, weight kg converted to lbs, duration seconds to minutes. **(3) `compute_coach_noticed()`** (`routers/home.py`) enriched: threshold values now render with units ("threshold is around 6.2 hours" not "cliff is around 6.2"), time lag included ("shows up 1 day(s) later"), sample size as coaching language ("consistent across 45 of your runs" — no statistical terms). **(4) Emerging pattern section** in `build_fingerprint_prompt_section()` enriched: includes threshold with units, observation counts per side, time lag. LLM instructed to "Be SPECIFIC — include the threshold, observation count, and direction" and rewrite in coaching voice while keeping the specifics. Question format changed from vague "Has anything shifted recently?" to specific "Your data shows a pattern: your easy pace improves based on time of day. 34x observed. [evidence]. What do you think is driving this?" **(5) `format_finding_line()`** updated: r-values removed from prompt output, replaced with `n=` sample size. Threshold lines use unit-aware formatting. Asymmetry description translated from raw direction string ("negative_dominant") to coaching language ("the downside hits harder than the upside helps"). **(6) `coach_noticed` schema field instruction** updated: demands specificity in athlete's training units (pace/mi, miles, hours, counts). Provides example of vague vs specific. Bans statistical language explicitly. **(7) `PERSONAL FINGERPRINT CONTRACT`** in briefing prompt updated: threshold advice must include units, specificity requirement added ("'I've noticed a pattern' is vague and useless. 'Your easy runs before 7 AM are consistently slower — that threshold has held across 18 observations' is specific and actionable."). Stats language ban clarified with coaching alternatives. **(8) `SEASONAL COMPARISON DISCIPLINE`** added to briefing prompt: Never compare runs across seasons without acknowledging temperature/humidity differences. Use `heat_adjustment_pct` data when available. If no environmental data, compare within same 4-week window or acknowledge limitation. **(9) Tests updated:** `test_fingerprint_intelligence.py` (6 assertions), `test_coach_lifecycle_quality.py` (1 assertion), `test_home_briefing_intelligence_lanes.py` (1 test expectation). All 178 related tests pass. Files: `apps/api/services/fingerprint_context.py`, `apps/api/routers/home.py`.

- **Universal Kimi K2.5 Coach Routing (Apr 4, 2026)**: Every coach query now routes to Kimi K2.5 (Moonshot AI) via the tool-calling premium path. Gemini Flash retired from the coach path. Canary gating removed — Kimi is the production model, not a canary. Claude Sonnet 4.6 remains as silent fallback on Kimi errors only. **(1) `get_model_for_query()`** simplified: always returns `MODEL_HIGH_STAKES, True` regardless of athlete tier, query complexity, or VIP status. Budget checks still apply per tier. **(2) `_handle_coach_query()`** routing: removed Gemini standard path, removed canary athlete check, removed Gemini→Sonnet fallback chain. Single path: `_query_kimi_with_fallback()` for all athletes. **(3) Tests updated:** `test_coach_model_tiering.py`, `test_coach_kimi_canary.py`, `test_coach_model_routing_reset.py`, `test_coach_output_contract_chat.py`, `test_coach_quality_fixes_hardened.py` — all assertions updated from `MODEL_DEFAULT`/`is_opus=False` to `MODEL_HIGH_STAKES`/`is_premium=True`. Old canary routing tests replaced with universal routing test. **(4) No changes to:** `query_gemini()` method (still exists for briefing and other non-coach paths), cost tracking schema, `CoachUsage` columns, Kimi tool format, Sonnet fallback mechanics. File: `apps/api/services/ai_coach.py`.

- **Coach Chat Model Audit Trail (Apr 4, 2026)**: `_save_chat_messages()` now records which LLM model served each response. New optional `model` parameter added. Assistant message dict in the `coach_chat` JSONB `messages` array gains `"model"` field: `"kimi-k2.5"` for primary, `"claude-sonnet-4-6"` for fallback, `"deterministic"` for shortcut paths (profile edits, no-data responses). Audit trail survives container restarts — persisted in PostgreSQL, not logs. File: `apps/api/services/ai_coach.py`.

- **Celery Beat Startup Dispatch Fix (Apr 4, 2026)**: All daily scheduled tasks (AutoDiscovery nightly 4AM UTC, morning intelligence, living fingerprint refresh, daily correlation sweep, experience guardrail, plan lifecycle cleanup, timezone backfill, Garmin ingestion health check) were never firing on their natural cron schedule because Docker deployments recreate the beat container before the scheduled time arrives. **(1) Fix:** `beat_init` signal handler in `celery_app.py` checks each daily task's last execution via DB/Redis markers on container startup. If any task hasn't run in the last 20 hours, it's dispatched immediately. **(2) Result:** Tasks now fire reliably on every deployment regardless of timing. Startup log shows "Beat startup dispatch complete: N dispatched, M skipped (recent)." **(3) Verified:** AutoDiscovery run, morning intelligence, and correlation sweep all produced DB records after fix deployed. Natural cron fires pending overnight verification (requires container surviving from pre-4AM to post-4AM without deployment).

- **AutoDiscovery Data Persistence Fix — Savepoints (Apr 4, 2026)**: AutoDiscovery orchestrator runs completed successfully in logs but produced zero database records. Root cause: `db.rollback()` calls within `_upsert_candidates()` and `_write_change_log()` in `services/auto_discovery/orchestrator.py` were rolling back the *entire transaction* (not just the failed nested operation) when an `IntegrityError` occurred on duplicate upserts. **(1) Fix:** Replaced bare `db.rollback()` with `db.begin_nested()` (SQLAlchemy savepoints). `IntegrityError` on duplicate candidate upsert now rolls back only the savepoint, preserving all other candidates and change log entries in the transaction. **(2) Verified:** Post-fix manual trigger produced 11 stable findings, 7 strengthening patterns, 20 interaction candidates, 62 stability annotations, ~100 promoted findings — all persisted in DB. File: `apps/api/services/auto_discovery/orchestrator.py`.

- **Pre-Existing Test Fixes (Apr 4, 2026)**: Four test failures fixed that predated this session's work. **(1) `correlation_engine.py`:** Missing `Athlete` import — `aggregate_cross_training_inputs()` referenced `Athlete` model without importing it. Added to import list. **(2) `test_coach_brief_builder.py`:** `test_brief_includes_all_sections` used a brittle `side_effect` list for mock DB queries that broke when the Athlete Experience Calibration section added more `.first()` calls. Replaced with model-aware `_route_query()` function that returns the correct mock based on queried model class. **(3) `test_coach_routing.py`:** `test_return_context_includes_post_return_guidance` and `test_prescription_request_includes_conservative_bounds` asserted the word "conservative" which was replaced by athlete-calibrated language in the prompt quality fix. Updated to assert "experience level" and "caution level". **(4) `test_daily_checkin_briefing_refresh.py`:** 5 tests asserted `mark_briefing_dirty` was called in `_trigger_briefing_refresh()`, but the function was intentionally refactored to NOT call it (prevents stale-page flash while LLM regenerates replacement briefing). Tests updated to match current behavior: only `enqueue_briefing_refresh` is called.

- **Coach Prompt Quality Fix — Data Verification & Athlete Calibration (Apr 4, 2026)**: Three trust-breaking patterns fixed in the AI coach system prompt (now applied to Kimi K2.5 universal path with Sonnet fallback). **(1) Data-verification discipline (NON-NEGOTIABLE):** Coach must call tools (get_recent_runs, get_mile_splits) before citing specific paces, splits, or workout comparisons. Never infer performance from workout titles/summaries. If data hasn't been looked up, coach says "let me check" instead of guessing. Applied to both SYSTEM_INSTRUCTIONS and _build_coach_system_prompt. **(2) Athlete-calibrated coaching tone:** New "Athlete Experience Calibration" section added to build_athlete_brief (`coach_tools.py`) that injects FitnessBank experience level, peak/current volume, race count, and confirmed pattern count into the brief. Prompt instructions calibrate coaching posture: experienced athletes (advanced/elite, extensive race history, high peak volume) get peer-level coaching — no default caution, no protective load warnings, respect for deliberate overreach. Intermediate athletes get balanced tone. Beginners/returning-from-break get conservative guidance. Replaces blanket "Be conservative with injury-related advice" with experience-gated behavior. **(3) Fatigue threshold context awareness:** Confirmed thresholds are real data but citation timing is now phase-aware. During deliberate build/overreach approaching a race: thresholds acknowledged as context, not cited as warnings. During maintenance/recovery/unexplained decline: cited actively. When athlete asks: always shared. **(4) Return-from-injury/prescription instructions updated:** Removed hardcoded "10-15% weekly increase" cap and "prioritize injury prevention" for all athletes. Now calibrated to experience level — experienced returning athletes can handle faster ramps. Prescription mode checks current form before intensity recommendations without blanket conservatism. **(5) No changes to:** tool infrastructure, cost caps, zero-hallucination rule, temporal accuracy rules, banned openers, anti-leakage rules, or fingerprint/emerging pattern handling.

- **N1 Engine Phase 4 — Adaptive Re-Plan (Apr 4, 2026)**: Plans now adapt to reality. When the system detects meaningful divergence (missed long run, 3+ consecutive missed days, 5+ days of low readiness), it generates a constrained 2-week micro-plan via the existing N1 engine and presents a day-level diff for athlete approval. **(1) Triggers:** `check_adaptation_triggers()` in `services/plan_framework/adaptive_replanner.py` evaluates three conditions in priority order. Missed long run: any planned long run skipped or date passed in the last 7 days (excluding 48h cooldown). Consecutive missed: 3+ non-rest workouts missed in 7 days. Readiness tank: 5+ consecutive days below the athlete's `reduce_volume_threshold` (per-athlete, from `AthleteAdaptationThresholds`). **(2) Micro-plan generation:** `generate_adaptation_proposal()` calls `generate_n1_plan()` with current athlete state, phase context, and actual recent volume. Phase context derived from `PlannedWorkout.phase` and `week_number` columns. `phase_week` now populated in new plan saves. **(3) Diff:** `_compute_diff()` compares original workouts against micro-plan output. Changed days shown with original → proposed type and mileage. **(4) Guardrails:** Max 2 accepted adaptations per plan cycle. Max 5 changed days per proposal. 48h cooldown between proposals. No adaptation during taper phase. **(5) Athlete approval:** Home page card (`AdaptationProposalCard.tsx`) shows trigger reason, expandable day-by-day diff, accept/reject buttons. Silence = keep original plan (proposal expires end-of-day Sunday of the second adjusted week). **(6) Accept flow:** `accept_proposal()` mutates `PlannedWorkout` rows for changed days, logs every mutation to `PlanModificationLog` with `source="adaptive_replan"`. **(7) Briefing integration:** Pending proposals injected into LLM prompt as `=== PENDING PLAN ADJUSTMENT ===` with instruction to briefly acknowledge without describing specifics or pressuring. **(8) Wired into morning intelligence** (`intelligence_tasks.py`): after readiness + intelligence rules + narration, checks for adaptation triggers. Creates `PlanAdaptationProposal` row if triggered. Nightly `expire_stale_proposals()` marks expired pending proposals. **(9) API endpoints:** `GET /v1/training-plans/adaptation-proposals/pending`, `POST .../accept`, `POST .../reject`. **(10) No changes to:** how plans are initially generated, N1 engine dosing logic, correlation engine, Manual, coach chat. Guiding principle #12: "The system INFORMS, the athlete DECIDES."

- **Limiter Engine Phase 5 — Transition Detection (Apr 4, 2026)**: Self-correcting lifecycle for correlation findings. `check_transitions()` in `services/plan_framework/limiter_classifier.py` evaluates all `active` and `resolving` findings per athlete. **(1) active → resolving:** Recomputes L30-weighted correlation via the same aggregation/correlation pipeline as the main engine (90-day window, temporal weighting). When recent `|r|` drops below 0.30 significance threshold, finding transitions to `resolving`. `resolving_context` captured at transition for coach attribution. **(2) resolving → closed:** After 4-week resolving window without reassertion, finding transitions to `closed` and `is_active` set to False. Athlete solved the problem and it stayed solved. **(3) resolving → active (reassertion):** If L30-weighted correlation reasserts (`|r| >= 0.30`) during the resolving window, finding returns to `active`. Pattern wasn't actually resolved. **(4) closed → next frontier scan:** `_scan_next_frontier()` identifies the next-highest-priority emerging candidates (times_confirmed >= 2) when a finding closes. What's the new constraint now that the old one is resolved? **(5) Wired into daily correlation sweep** (`correlation_tasks.py`) after lifecycle classification pass and before Layer 1-4 processing. Runs for every athlete with new data. **(6) No changes to:** how findings become `active` (Phases 1-4 intact), Manual/briefing/coach (they already filter by lifecycle state — resolving/closed findings naturally fall out of active surfaces), direction expectations (empty for cross-training inputs). Founder account verification: 100 active findings evaluated, 0 transitions triggered (all correlations still holding strong in L30 data — correct behavior for established account).

- **Runtoon Image Quality Fix (Apr 4, 2026)**: Stripped all text-rendering instructions from the Gemini image generation prompt. The model was attempting to render stats, captions, and watermarks inside the generated image, producing garbled/misspelled text ("LEGLE", nonsensical sign text) that made every Runtoon look broken. **(1) STYLE_ANCHOR:** Removed `IMAGE LAYOUT` section (65/35 split with text banner), removed "only text allowed" clause. Replaced speech-bubble ban with comprehensive no-text instruction: "DO NOT include any text, words, letters, numbers, signs, labels, speech bubbles... The image must be PURELY VISUAL." Added "Fill the entire frame with the caricature scene." **(2) Image prompt:** Removed `STATS TO RENDER IN IMAGE`, `CAPTION TO RENDER IN IMAGE`, and `WATERMARK` sections. Added closing reinforcement: "Remember: absolutely NO text, words, or letters anywhere in the image." **(3) 9:16 recompose:** `recompose_stories()` updated to render stats line and caption text via Pillow (previously assumed the model baked them in). Stats in slate-200 bold, caption in slate-400 with word-wrap, watermark unchanged. **(4) No changes to:** caption generation (still Gemini 2.5 Flash, same quality gates), share flow, frontend UX, or Runtoon style guidelines. File: `apps/api/services/runtoon_service.py`.

- **Correlation Engine Cross-Training Signals — Phase 5 (Apr 4, 2026)**: Correlation engine now receives load-level cross-training inputs. In `aggregate_cross_training_inputs()` (`services/correlation_engine.py`), 5 new per-run rolling 7-day inputs added: `ct_strength_sessions_7d` (count), `ct_strength_tss_7d` (TSS via TrainingLoadCalculator), `ct_cycling_tss_7d`, `ct_cross_training_tss_7d` (total non-run TSS), `ct_hours_since_cross_training` (hours since any non-run activity). For each running activity in the analysis window, looks back 7 days and computes surrounding cross-training load context. Inputs flow through existing statistical pipeline (correlation, threshold detection, Bonferroni correction, confirmation tracking). Direction expectations intentionally empty — no pre-baked assumptions about whether strength helps or hurts running efficiency. Engine discovers. Friendly display names registered in `FRIENDLY_NAMES` dict (`n1_insight_generator.py`): "strength sessions (7-day)", "cross-training load (7-day)", etc. Existing daily cross-training signals (ct_strength_sessions, ct_lower_body_sets, ct_hours_since_strength, etc.) and all run-only filters unchanged. No exercise-level signals yet (requires accumulated StrengthExerciseSet data). No changes to briefing, Manual, or coach context — those already consume correlation findings and will surface any discoveries automatically.

- **Briefing Cross-Training Awareness — Phase 4 (Apr 4, 2026)**: Morning briefing LLM prompt now receives cross-training context from the last 48 hours. In `generate_coach_home_briefing()` (`routers/home.py`), a new query fetches recent non-run activities (cycling, walking, hiking, strength, flexibility) with sport type, duration, TSS (via `TrainingLoadCalculator`), session type, and hours-ago. Injected as `=== RECENT CROSS-TRAINING ===` prompt section with explicit rules: mention only when relevant to today's running context (heavy strength before quality run = relevant; yoga before rest day = not), connect to running narrative, never predict how athlete will feel (correlation engine's job, Phase 5). Run-only queries for yesterday's run, fingerprint context, and `compute_coach_noticed` unchanged. When no cross-training exists in last 48h, prompt is identical to before — no empty section injected. No changes to deterministic intelligence path.

- **PMC Transparency Disclosure — Phase 3 (Apr 4, 2026)**: Training load numbers now disclose that they include all training activities, not just runs. **(1) Backend:** `/v1/training-load/history` response gains `weekly_tss_split` field containing 7-day TSS breakdown by sport (sport name, TSS, activity count per sport). One additional query — no new service. **(2) Training Load page (`/training-load`):** Below the PMC chart, expandable disclosure: "Training load includes all activities (running + cross-training)" — click to expand 7-day breakdown showing per-sport TSS and total. **(3) Home page Compact PMC:** Subtle info line below legend: "Includes all activities (running, cross-training)." Never-hide-numbers principle: the athlete sees exactly what feeds their load. No changes to TSS calculation math, no include/exclude toggles, no correlation engine or briefing changes.

- **Non-Run Activity Detail Pages — Phase 2 (Apr 4, 2026)**: Activity detail page now branches on `sport_type`. Run experience unchanged. Each non-run sport gets a dedicated component in `components/activities/cross-training/`. **(1) Cycling:** Duration, distance, avg speed, elevation, HR, max HR. **(2) Strength:** Exercise sets grouped by movement pattern (hip_hinge, squat, push, pull, core, etc.) with sets × reps × weight, estimated 1RM, volume summary with lower/upper/core distribution bar, session type badge (maximal/strength_endurance/hypertrophy/endurance/power/mixed). Placeholder state when no `StrengthExerciseSet` data exists. **(3) Hiking:** Elevation gain hero, distance, speed, HR. Walking activities use the same layout. **(4) Flexibility:** Honest minimalism — duration, HR if available. **Universal across all sports:** "Going In" wellness stamps (Recovery HRV, RHR, sleep), Training Load card (TSS + intensity factor + weekly running/cross-training activity count), header with title editing, Garmin badge. **Backend:** Activity detail endpoint (`GET /v1/activities/{id}`) now returns `session_detail`, `strength_session_type`, computed `tss`/`tss_method`/`intensity_factor` (from `TrainingLoadCalculator`), `weekly_context` (7-day running vs cross-training counts), and `exercise_sets` array for strength activities (from `StrengthExerciseSet` table). No changes to run endpoint. No prescriptive coaching claims — data only per suppression-over-hallucination principle.

- **Cross-Training Sport Icons — Phase 1 (Apr 4, 2026)**: Activity list and weekly chips now show the full training week, not just runs. **(1) Backend:** `ActivityResponse` schema gains `sport` field. Activity list endpoint returns sport per activity. Home page weekly actuals query no longer filters `sport == "run"` — strength, cycling, hiking, walking, and flexibility activities now appear in weekly chips. `WeekDay` schema gains `sport` field. **(2) Frontend:** `Activity` TypeScript type and `WeekDay` interface gain `sport` field. `ActivityCard` shows sport-specific icons (Dumbbell for strength, Bike for cycling, Mountain for hiking, Footprints for walking, StretchHorizontal for flexibility) and a sport label badge for non-run activities. Home and analytics weekly chips display sport icons instead of checkmark+distance for cross-training days. Accepted sports: run, cycling, walking, hiking, strength, flexibility (from `_ACCEPTED_SPORTS` in garmin_adapter). Yesterday's insight and "last activity" queries remain run-only (running-specific context). Phase 2 scope: non-run activity detail pages, Run Shape Canvas adaptation.

- **Route Cleanup & Page Merges (Apr 4, 2026)**: Removed 4 dead routes, merged 3 orphaned pages. **(1) Deleted:** `/dashboard` (was redirect to `/home`), `/home-preview` (dev preview artifact), `/spike/rsi-rendering` (ADR-064 rendering spike — 7 files). **(2) `/diagnostic`** converted to server redirect → `/home`; `/diagnostic/report` redirects → `/admin/diagnostics`. **(3) `/profile` merged into `/settings`** — Personal Information section (name, email, birthdate, sex, height, age category) now top section of Settings page with inline edit/save. `/profile` route redirects → `/settings`. Coach tool routing updated (`/profile` → `/settings`). **(4) `/availability` redirects → `/plans/create`** — plan wizard already has scheduling step. **(5) `/trends` absorbed into `/analytics`** — TrendsSummary component added to Analytics page showing efficiency trend, volume trend, and root cause analysis with correlation badges. `/trends` route redirects → `/analytics`. All backend references updated (billing checkout URL, insight feed actions, diagnostics router, coach tools). `robots.ts` updated. All existing redirects preserved (`/checkin`, `/insights`, `/discovery`). Frontend builds clean (`tsc --noEmit`).

- **Personal Operating Manual V2 (Apr 4, 2026)**: The `/manual` page rebuilt from raw correlation list to insight-driven document. Four sections: **(1) Race Character** — pace-gap analysis comparing race vs training performance; PR detection; narrative summary of the athlete's racer-vs-trainer identity. Race-day counterevidence: identifies "good races" where the athlete performed well despite adverse wellness conditions (e.g., low sleep, poor HRV), producing specific contradiction narratives. **(2) Cascade Stories** — multi-step correlation chains (input → mediator → output) surfaced as mechanism narratives. Confound detection suppresses stories where input and mediator measure the same phenomenon. Garmin noise metrics filtered from mediator role. **(3) Highlighted Findings** — interestingness-scored findings prioritizing cascade chains, asymmetry, non-obvious patterns over raw frequency. Baseline threshold suppression hides non-actionable thresholds (>85% data on one side). **(4) Full Record** — complete finding list sorted by interestingness then confirmation count. Human-language headline rewriter replaces templated insight text with natural sentences. Manual-specific translation dictionary (`_MANUAL_LANGUAGE`) for jargon-free display. `localStorage` delta tracking for "What Changed" between visits. Contextual coach links for each finding. Backend: `services/operating_manual.py`. Frontend: `app/manual/page.tsx`.

- **Manual Promoted to Primary Navigation (Apr 4, 2026)**: `/manual` added as primary nav item (left of Progress) on desktop (`Navigation.tsx`) and mobile (`BottomTabs.tsx`). `/insights` page replaced with permanent redirect to `/manual`. `/discovery` page replaced with permanent redirect to `/manual`. "Check-in" removed from secondary navigation.

- **Daily Check-in Consolidated to Home (Apr 4, 2026)**: Standalone `/checkin` page replaced with redirect to `/home`. Mindset fields (`enjoyment_1_5`, `confidence_1_5`) added to `QuickCheckin` component on home page as optional collapsible section. `QuickCheckinPayload` type updated. All links to `/checkin` across the codebase updated to `/home`.

- **Home Page Wellness Row (Apr 4, 2026)**: New `garmin_wellness` field on `/v1/home` API response. Backend `_build_garmin_wellness()` queries today's `GarminDay` + 30-day history to compute personal ranges. Frontend `WellnessRow` component shows: **(1)** Recovery HRV (5-min peak) with value, status (low/normal/high), personal range, plus Garmin overnight avg below it. **(2)** Resting HR with status and range. **(3)** Sleep hours with Garmin sleep score. `HrvTooltip` info icon explains the difference between Recovery HRV and Overnight Avg HRV ("Both are valid — they measure different things. Recovery HRV is more predictive of next-day performance."). Positioned between coach briefing and workout.

- **HRV Labeling Standardized (Apr 4, 2026)**: `garmin_hrv_5min_high` renamed from "5-minute peak HRV" to "Recovery HRV" across the entire system: `operating_manual.py` (`_MANUAL_LANGUAGE`, `_INPUT_CONDITIONS`), `n1_insight_generator.py` (`COACHING_LANGUAGE`), home page wellness row, activity detail page. Prevents confusion with Garmin watch's "Avg Overnight HRV" display.

- **Pre-Activity Wellness Stamps (Apr 4, 2026)**: Five new columns on `Activity`: `pre_sleep_h`, `pre_sleep_score`, `pre_resting_hr`, `pre_recovery_hrv`, `pre_overnight_hrv`. Migration: `wellness_stamp_001`. Stamped at ingestion time across all four paths (Strava sync, Strava index, Strava ingest, Garmin webhook). Retro-stamp on health data arrival: when GarminDay data arrives after an activity, unstamped activities from that date are automatically filled. Admin backfill endpoint: `POST /v1/admin/users/{id}/wellness-backfill`. Service: `services/wellness_stamp.py`. Activity detail API (`GET /v1/activities/{id}`) returns wellness snapshot. Frontend shows "Going In" section with Recovery HRV, RHR, and sleep context on each activity.

- **Strength Exercise Sets (Apr 1-6, 2026)**: `StrengthExerciseSet` model and table for Garmin strength session detail. `strength_session_type` on Activity. Migration: `cross_training_003`. **Data pipeline (Apr 6):** Garmin Activity Files webhook → FIT file download → `fitparse` extraction → `process_strength_activity()`. Previous REST-based fetch task removed (endpoint never existed). See "Garmin Activity Files Webhook" entry above.

- **Repository Cleanup (Apr 4, 2026)**: ~145 untracked scratch files deleted (one-off diagnostics, hardcoded-token scripts, test output captures, completed builder instructions). `.gitignore` rules added for `/_*.py`, `/_*.sh`, `scripts/_check_*`, `scripts/_diag_*`, diagnostic `.txt` outputs, `apps/api/tmp_debug_*.py`. Reusable utilities tracked: `scripts/_get_token.py`, `scripts/_probe_exercise_sets_endpoint.py`, `scripts/generate_realistic_synthetic_population.py`. Active docs tracked: 6 specs, 3 references, 2 session handoffs, mockups. Cleanup policy: `docs/CLEANUP_POLICY.md`.

---

## 0. Delta Since Last Audit (Apr 1)

Shipped and now live in product/system behavior:

- **Plan Volume Regression Fix + Goal-Time Pace Derivation (Apr 1, 2026)**: Three-commit fix for plan generation regression affecting athletes without race history. **(1) Volume ramp fix** — The 10K volume contract cap (`min(applied_peak, max(band_max, band_center))`) was arbitrarily crushing `applied_peak` to `band_max` (~26mi) for 10K plans, making abbreviated plans flat when `starting_vol` was ~25mi. Removed the 10K-specific cap entirely (no distance should arbitrarily cap an athlete's mileage below their proven capability). Abbreviated plan peak now guarantees at least `starting_vol + days_per_week` (1 mile per running session build room), capped at historical peak for safety. Day builder gained undershoot handler: when assembled days fall below target volume, shortfall is distributed to easy runs (up to their caps). Larry Shaffer's 10K plan now ramps 27.2→29.2→32.0mi (was flat at ~26). **(2) Goal-time pace derivation** — `_find_best_race` default changed from 45.0 RPI to 0.0 (no fabricated data). `_estimate_rpi_from_training` removed entirely. When `best_rpi` is 0 and athlete provides a goal time, RPI is derived via `calculate_rpi_from_race_time`. Frontend gained "Goal Time (optional)" input field on the constraint-aware plan form with `parseTimeToSeconds` conversion. Backend parsers (`_parse_goal_seconds`, `_parse_goal_time`) updated to handle both H:MM:SS and raw integer-as-string seconds. **(3) Race prediction fix** — `_predict_race` treated `best_rpi=0.0` as valid (not `None`), producing 5-hour 10K base predictions. Now derives RPI from goal time when available, falls back to volume-based estimate. **Test fixes included:** 3 fitness bank tests updated for 0.0 default. IndexError: 3 in 6 test files fixed (robust repo root finder for Docker/CI path depth). Fingerprint intelligence test assertions updated for Phase 4 lifecycle labels. tasks/__init__.py lint errors fixed. CI #804 and #805 both GREEN. Commits: `f258cd4`, `6aa149e`, `f0cbb21`.

---

## 0. Delta Since Last Audit (Mar 29 → Apr 1)

Shipped and now live in product/system behavior:

- **Cross-Training Activity Storage — Workstream 1: Data Infrastructure (Apr 1, 2026)**: Four-commit workstream making the platform multi-sport safe. **(Commit 1) Downstream consumer audit** — 76 `Activity.sport == "run"` filters added across 16 files. Every running-specific consumer (training load, correlation engine, run analysis, readiness score, recovery metrics, home dashboard, briefing, contextual comparison, race predictor, pre-race fingerprinting, anchor finder, experience guardrail, insight aggregator, model cache, daily intelligence, self-regulation) now explicitly filters by sport. Intentionally unfiltered: by-ID lookups, `has_any_activities` gate, briefing refresh triggers. New `test_cross_training_sport_filter.py` with mixed-sport and cycling-only fixtures proving falsifiable assertions. **(Commit 2) Adapter expansion + ingest filter** — `_ACTIVITY_TYPE_MAP` expanded from 5 run types to 21 types across 6 sports: run (9 Garmin types including TRACK_RUNNING, ULTRA_RUN, OBSTACLE_RUN), cycling (CYCLING, INDOOR_CYCLING, MOUNTAIN_BIKING, ELLIPTICAL, STAIR_CLIMBING), walking, hiking, strength, flexibility (YOGA, PILATES). Three new columns on Activity: `garmin_activity_type` (preserves raw Garmin type for audit), `cadence_unit` (spm/rpm/null by sport), `session_detail` (JSONB for non-run detail payloads). Ingest filter changed from `sport != "run"` to `sport not in _ACCEPTED_SPORTS`. Detail webhook guard: non-run activity details stored in `session_detail` instead of creating stream/split rows. Migration: `cross_training_001`. **(Commit 3) Sport-aware TSS routing** — `TrainingLoadCalculator.calculate_workout_tss()` now routes non-run activities to `_calculate_cross_training_tss()`: hrTSS when HR available, sport-specific duration-based estimates otherwise (cycling IF=0.70, hiking 0.60, strength 0.65, flexibility 0.20). `compute_training_state_history` and `get_load_history` include all accepted sports in EMA computation. Running TSS path unchanged. **(Commit 4) Partial index** — `ix_activity_athlete_start_run` on `(athlete_id, start_time) WHERE sport = 'run'` keeps the dominant query pattern fast as cross-training rows grow. Migration: `cross_training_002`. CI migration heads updated. Commits: `ca47d6e` through `dd3291b`. All CI green.

---

## 0. Delta Since Last Audit (Mar 26 → Mar 29)

Shipped and now live in product/system behavior:

- **N=1 Plan Engine V3 — Complete Rebuild (Mar 26-29, 2026)**: Legacy plan generators deleted (-16,920 lines). New `n1_engine.py` (1,078 lines) rebuilt from scratch with diagnosis-first architecture per ADR `docs/specs/N1_ENGINE_ADR_V2.md`. The algorithm: (1) diagnose adaptation needs from athlete state and goal distance, (2) select training tools from KB variant library, (3) set dosage and progression, (4) schedule anchor sessions first, (5) fill with purposeful easy running. Phases are labels applied AFTER the plan is built, not drivers of workout selection. **Key capabilities:** 6 adaptation needs (ceiling, threshold, durability, race-specific, neuromuscular, aerobic base). 7-day athlete support (no forced rest day). Tune-up race handling (mini-taper + post-race absorption). Half-marathon readiness gate with comeback exemption. Athlete-specified taper preference (1-3 weeks). Post-quality easy day cap. MLR floor respects athlete history. Volume distribution with sawtooth fidelity. Repetition pace zone now distinct from interval pace. **Validated against 14-archetype evaluator: 143 PASS, 0 FAIL, 11 WAIVED.** Commits: `2eff725` through `f09687b`.

- **KB Rule Evaluator — Full Knowledge Base Gate (Mar 29, 2026)**: New `scripts/eval_kb_rules.py` replaces the 12-BC evaluator as the primary quality gate. Checks 33 HARD rules from the founder-annotated knowledge base (`docs/specs/KB_RULE_REGISTRY_ANNOTATED.md`) across all 14 archetypes. Rules sourced directly from coaching KB: phase progression (PH), volume/recovery (VR), session structure (SS), tempo/threshold (TP), interval/rep (IR), recovery (RC), marathon-specific (MA), plan progression (PP), easy day (ED), taper (TA), N=1 (N1), day quality (DQ), readiness gate (RG). **Result: 445 PASS, 0 FAIL, 0 WARN, 17 WAIVED.** Three engine bugs caught and fixed: (1) Couch-to-10K ignored `days_per_week` constraint — now adds rest days; (2) taper strides missing for low-day athletes — now placed on first available easy day; (3) MLR exceeded 75% of same-week LR — now capped at `min(mlr, lr * 0.75)`. Legacy 12-BC evaluator also verified clean (143 PASS). Both evaluators agree. 159 plan-related tests pass.

- **Variant Dropdown — N1 Engine Phase 3 (Mar 29, 2026)**: Frontend can now render workout variant selection from the registry. Each plan day emits `workout_stem`, `phase_context`, `week_in_phase`, `experience`, and `stimulus_already_covered` — enabling the dropdown to filter valid variants per `build_context_tags`, `when_to_avoid`, `pairs_poorly_with`, and `sme_status == "approved"`. The athlete picks; the system serves only valid options.

- **Limiter Engine — Phases 1-4 Complete (Mar 29-31, 2026)**: Four-phase build of the N=1 limiter intelligence system. **(Phase 1) Fingerprint-to-Plan Bridge** — `fingerprint_bridge.py` translates confirmed correlation findings into plan delivery modifications. Structural traits (recovery half-life, L-REC) modify spacing, cutback frequency, and quality caps. Active limiters adjust session type ratios within distance floors. **(Phase 2) Temporal Weighting** — Correlation engine now weights observations by recency (L30: 4×, L31-90: 2×, L91-180: 1×, >180d: 0.5×). This correctly weakens old solved-problem correlations (Michael's L-VOL) while preserving stable structural signals (Brian's L-REC). **(Phase 3) Lifecycle State Classifier** — Every `CorrelationFinding` gains a lifecycle state: `emerging`, `active`, `resolving`, `closed`, `structural`. Plan engine reads only `active` limiters. **(Phase 4) Coach Layer Integration** — `emerging` findings surfaced to athletes via the AI coach as natural language questions. Athlete's answer becomes a `limiter_context` fact (90-day TTL) that drives lifecycle promotion (`emerging` → `active` via confirmation, `emerging` → `closed` via historical acknowledgment). Three production fixes: (a) emerging findings invisible due to sort-by-confirmation cutoff — fixed with independent lifecycle queries; (b) model ignoring emerging directive — fixed with structural separation (dedicated `=== EMERGING PATTERN ===` block above active findings) + pre-generated natural language question + tightened system prompt directive; (c) checkin field translations added (`readiness_1_5` → "readiness", etc.). Tier 2 quality validation on founder account: prompt dump ACCEPT, active-pattern coaching ACCEPT, emerging question PASS (MR-1 through MR-5 all green after tuning). Spec: `docs/specs/LIMITER_TAXONOMY.md`.

- **Plan Quality Evaluator (Mar 26, 2026)**: New `scripts/eval_plan_quality.py` (852 lines). Original automated evaluator checks 12 Blocking Criteria across 14 archetypes from the ADR. Now serves as secondary validation alongside the KB Rule Evaluator. Generates full plan dumps (every day, every week) in human-readable format.

- **RPI Pace Recalibration (Mar 28-29, 2026)**: Interval and repetition paces recalibrated against reference pace calculator. I/R paces in the 50-55 RPI band were 13-17s too fast. R > I ordering corrected at low RPIs (30-35) where linear extrapolation crossed pace lines — fixed with R_int = I_int * 1.04 anchor. Zone ordering (E>M>T>I>R) and monotonicity verified for full RPI 30-70 range. PSEO data regenerated from local formula (no API dependency). Commits: `2d4d2d3`, `f09687b`.

- **Coaching Quality Patches (Mar 28, 2026)**: (1) Repetition pace zone: `workout_prescription.py` now surfaces R-pace from athlete data instead of hardcoded "1500m pace" text. (2) Post-quality easy day cap: day after threshold/intervals capped at `min(8mi, target_vol/days * 0.8)`. (3) MLR floor: uses `max(lr*0.75, current_lr*0.75)` capped at 15mi. (4) Two-race taper: tune-up week gets mini-taper + post-race absorption. Evaluator excludes tune-up/recovery weeks from sawtooth trend. Commit: `437ee66`.

- **Structured Workout Splits in Briefing (Mar 28, 2026)**: Home page LLM briefing now receives detailed workout structure from `ActivitySplit` data instead of just overall average pace. New `_summarize_workout_structure()` helper detects warmup, work intervals (rep count, average pace, pace range, HR), and recovery segments. Prompt explicitly instructs LLM to coach from split breakdown, not the meaningless average pace. Fixes: interval workouts no longer misidentified as "disciplined aerobic pacing." Commit: `f6a6a85`.

- **CI Split to Nightly (Mar 29, 2026)**: Full backend test suite (3,575+ tests) moved to nightly scheduled run + manual trigger. Push commits run fast gate only: backend-smoke (golden path tests), migration integrity, lint. Nightly failure reporting: GitHub issue auto-opened with `nightly-ci` label on failure, auto-closed with recovery comment when green. Codecov upload gated on token presence. Commit: `cb31509`.

- **Intake Context Wiring (Mar 26, 2026)**: Onboarding questionnaire data now flows into plan generation. New `services/intake_context.py` with `IntakeContext` dataclass. `ConstraintAwarePlanner.generate_plan()` seeds cold-start FitnessBank from self-reported data (current long run, estimated weekly volume). Safety gate: athletes with <10 synced runs AND incomplete intake blocked with clear `intake_required` error. Questionnaire expanded with running experience, current runs/week, longest recent run, sport background. Commit: `2e1238d`.

---

## 0. Delta Since Last Audit (Mar 12 — 3B graduation)

Shipped and now live in product/system behavior:

- **Phase 3B Graduation Controls (Mar 12, 2026)**:

- **Coach VIP Sonnet Cap Raise + Production Deploy Verification (Mar 12, 2026):** VIP premium Anthropic lane defaults increased to `COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP=15` and `COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP=1000000` in `services/ai_coach.py`. Canonical runtime cap doc updated at `docs/COACH_RUNTIME_CAP_CONFIG.md`. Production deploy completed from commit `9a82a0d` using standard compose rebuild command. Live verification in `strideiq_api` confirmed constants loaded from `/app/services/ai_coach.py` and `get_budget_status()` now reports `opus_requests_limit_today=15` and `opus_tokens_limit_this_month=1000000` for VIP athletes. Founder uncapped bypass and non-VIP caps remain unchanged.

---

## 0. Delta Since Last Audit (Mar 11 -> Mar 12)

Shipped and now live in product/system behavior:

- **Garmin Sync Test Flake Fixed (Mar 12, 2026)**: Graduation layer added on top of the already-built 3B workout narrative generator. **(1) Global kill switch in generator** — `STRIDEIQ_3B_KILL_SWITCH` env var now checked directly inside `generate_workout_narrative()`, not just in the router eligibility path. This means the kill switch is enforced even when the generator is called directly from tasks or scripts. DB FeatureFlag fallback also wired. Machine-readable `suppression_reason="3B workout narratives globally disabled (kill_switch)."` returned. Env var also surfaced as `kill_switch_active` field in `WorkoutNarrativeResponse`. **(2) Gate-aware rollout state** — `WorkoutNarrativeResponse` now includes `gate_open: bool` (True only when narration accuracy > 90% for 4 weeks) and `kill_switch_active: bool`. Provisional eligibility (gate not yet met) is explicit and machine-readable. **Preflight gate state:** `/v1/intelligence/narration/quality` currently returns `passes_90_threshold=false` (no production `NarrationLog.score` rows yet). Rollout is founder-controlled/provisional. **(3) Founder review endpoint** — `GET /v1/intelligence/admin/narrative-review` (founder-gated, not tier-gated; `Depends(get_current_user)` + explicit founder check): returns `NarrationLog` rows with `rule_id="WORKOUT_NARRATIVE"`, including narrative text, prompt, model, tokens, latency, suppression state, `quality_score` breakdown, and eligibility context. Query params: `athlete_id` (UUID, 422 on malformed), `limit` (default 50 for first-50 review), `days` (default 28), `suppressed_only` (for suppression diagnostics). **(4) 4-criterion quality scorer** — new `score_narrative_quality(text, ctx, recent_narratives)` function in `workout_narrative_generator.py` scores each narrative on: `contextual` (has specific week/phase/recent/upcoming reference), `non_repetitive` (not >50% token overlap with recent), `physiologically_sound` (no intensity encouragement in wrong context), `tone_rules_ok` (no banned metrics, no prescriptive drift, no generic sludge). Each criterion returns a pass/fail bool + machine-readable `_fail_reason` label for founder triage. `criteria_passed` (0-4) and `score` (0.0-1.0) computed. **(5) Quality score persisted** — `quality_score` dict now stored in `NarrationLog.ground_truth['quality_score']` on every generated narrative, making it available for founder review without re-scoring. **(6) Per-narrative suppression unchanged** — banned metric check, intensity-in-taper guard, and similarity >50% suppression all remain independent of the global kill switch. **(7) Rollout surface unchanged** — `GET /v1/intelligence/workout-narrative/{target_date}` remains the only 3B product surface. No UI expansion in this pass. **(8) Runtime cap contract preserved** — no changes to `ai_coach.py` cap logic; `COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP` and `COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP` as separate hard caps unchanged. 30 new tests in `test_phase3b_graduation.py`. Autouse `_kill_switch_off` fixture added to `test_workout_narrative_generator.py` to prevent FeatureFlag DB query from consuming mock slots. 161 total tests pass (24 xfailed expected). 3B contract tests remain xfailed pending gate open.

Shipped and now live in product/system behavior:

- **Garmin Sync Test Flake Fixed (Mar 12, 2026)**: Root cause identified and eliminated. The Garmin D5 (activity sync) and D6 (health sync) test suites were hanging because tests calling `process_garmin_activity_task.run()` / `process_garmin_health_task.run()` with activity-changing payloads triggered the briefing refresh code path. That path calls `enqueue_briefing_refresh()` → `generate_home_briefing_task.apply_async()` (Celery broker). Additionally, `invalidate_athlete_cache()` in the activity task repeatedly called `get_redis_client()`, failing DNS lookup for `redis:6379` each time (~3-4s/call × 10 calls = 30s/test). Fix: added an `autouse=True` fixture (`_no_briefing_side_effects`) to both `test_garmin_d5_activity_sync.py` and `test_garmin_d6_health_sync.py` that patches all three entry points (`services.home_briefing_cache.mark_briefing_dirty`, `tasks.home_briefing_tasks.enqueue_briefing_refresh`, `core.cache.invalidate_athlete_cache`) as no-ops for every test in those modules. The existing tests that explicitly assert briefing dispatch (`TestLastGarminSyncUpdate.test_briefing_refresh_triggered_when_activity_changes`, `TestHealthBriefingRefreshTrigger.test_refresh_triggered_when_processed`) still work correctly because their inner `patch()` context managers override the autouse fixture within their scope. Verified: 84 tests pass in <7s on 3 consecutive runs. Timeout containment (`pytest-timeout`) remains but is no longer the practical defense.

- **Phase 3C Graduation Controls (Mar 12, 2026)**: Graduation layer added on top of the already-built 3C statistical intelligence path. **(1) Per-insight suppression** — new `N1InsightSuppression` model (`n1_insight_suppression` table, migration `phase3c_001`) stores `(athlete_id, insight_fingerprint)` with `UniqueConstraint`. Fingerprint is a stable 16-char SHA-256 prefix of `input_name:direction:output_metric` — survives text rewrites, stable across deployments. `generate_n1_insights()` loads suppression records before returning insights; suppressed patterns are filtered. Suppression table unavailable → fail open (all insights still surface). **(2) Founder review endpoint** — `GET /v1/insights/admin/n1-review` (founder-only, checks `OWNER_ATHLETE_ID` or `mbshaf@gmail.com`): lists generated 3C insights across eligible athletes with text, fingerprint, confidence, category, evidence, eligibility reason, and Bonferroni-corrected count. Optional `athlete_id` query param for single-athlete review. **(3) Suppression action endpoint** — `POST /v1/insights/admin/n1-suppress` (founder-only): accepts `athlete_id` + `fingerprint` + optional `reason`; idempotent (no error on double-suppress). **(4) Kill switch behavior tested** — existing `STRIDEIQ_3C_KILL_SWITCH` env var + FeatureFlag table dual-check already worked; new tests verify the kill switch disables eligibility, `evidence.kill_switch=True` is returned in ineligible response, and `generate_n1_insights` returns empty list cleanly when no correlations survive gates. **(5) Language verified data-derived** — "Based on your data: YOUR [metric] is moderately associated with changes when your [input] is higher." format unchanged; no prescriptions, no generic advice, no internal acronyms. **(6) `N1Insight` dataclass** gains `fingerprint` field; `IntelligenceItemResponse` schema gains optional `fingerprint` for frontend to display per-insight review actions. **(7) Statistical gates unchanged** — `p < 0.05` (Bonferroni-corrected), `|r| >= 0.3`, `n >= 10`, banned acronym filter, all enforced before and after graduation layer. 26 new tests in `test_phase3c_graduation.py`. Migration: `phase3c_001` (chains off `auto_discovery_002`). 3B explicitly deferred — no 3B changes in this pass.

## 0. Delta Since Last Audit (Mar 9 -> Mar 11)

Shipped and now live in product/system behavior:

- **Coach Model Routing Reset (Mar 11, 2026)**: (1) `MODEL_HIGH_STAKES` changed from `claude-opus-4-6` to `claude-sonnet-4-6` — no live Opus path remains. (2) `home.py` `_call_opus_briefing_sync` and `home_briefing_tasks.py` `source_model` both updated to `claude-sonnet-4-6`. (3) Gemini `thought_signature` INVALID_ARGUMENT fix: multi-turn tool loop now strips thought parts from model content before appending to conversation history; `google-genai` pinned to `>=1.66.0`. (4) Premium lane cap model preserved (later adjusted Mar 12): VIP hard caps, no multiplier logic, founder always uncapped. Canonical cap reference: `docs/COACH_RUNTIME_CAP_CONFIG.md`. 13 targeted tests in `test_coach_model_routing_reset.py`. Commit: `68700b2`.

- **AutoDiscovery Phase 0C (Mar 11, 2026)**: Founder review + controlled promotion staging layer. Five workstreams: **(1) 0B fidelity gaps closed** — `interaction_scan` score summary now value-bearing (real aggregate `baseline_score` from mean `interaction_score` of kept candidates, not count-based `None` placeholder); FQS provenance block (`component_values`, `component_quality`, `has_inferred_components`) now preserved in every experiment `result_summary` and report path for all three loop families; `_score_rescan_window()` now returns `score_provenance` alongside aggregate scores. **(2) Durable cross-run candidate memory** — new `auto_discovery_candidate` table (migration `auto_discovery_002`) with deterministic stable key uniqueness enforced at DB level (`UniqueConstraint(athlete_id, candidate_type, candidate_key)`); orchestrator `_upsert_candidates()` runs after each nightly pass to group recurring shadow candidates; candidate re-appearance increments `times_seen` and updates tracking fields without ever overwriting founder review state. **(3) Founder review state machine** — `review_candidate()` function in orchestrator supports approve/reject/defer/stage actions; every action writes an `auto_discovery_review_log` row for full auditability; staging sets `promotion_target` label on candidate (no auto-mutation). **(4) Controlled promotion staging** — four explicit promotion targets (`surface_candidate`, `registry_change_candidate`, `investigation_upgrade_candidate`, `manual_research_candidate`); staging is label-only, no live athlete-facing or registry writes occur. **(5) Founder review query** — `get_founder_review_summary()` returns structured sections: open candidates sorted by value, candidates seen 2+ times, approved/rejected/deferred history; no manual JSON diffing required. Schema: `auto_discovery_candidate` + `auto_discovery_review_log` (migration `auto_discovery_002`). 32 new tests + 86 total AutoDiscovery tests passing. CI green.

- **AutoDiscovery Phase 0B (Mar 11, 2026)**: Founder-only shadow learning platform extended from scaffold to real intellectual work. Four workstreams: **(1) Shadow isolation hardening** — `analyze_correlations()` gains `shadow_mode=True` parameter that skips all production cache reads and writes (`get_cache` / `set_cache` bypassed entirely), rescan loop lag field fixed from `lag_days` to `time_lag_days` (matching `CorrelationResult.to_dict()`), Celery task refactored to evaluate loop-family enablement per-athlete rather than task-wide. **(2) Real FQS integration** — `CorrelationFindingFQSAdapter` gains `score_shadow_dict(c)` method that scores raw shadow correlation dicts without committed `CorrelationFinding` rows; `AthleteFindingFQSAdapter` gains `score_finding_list(findings)` aggregate; orchestrator now stores real FQS `baseline_score` on every rescan experiment; report `score_summary` includes `aggregate_baseline_score` per loop family. **(3) Pairwise interaction loop** — new `services/auto_discovery/interaction_loop.py`: median-split pairwise testing across 4 output metrics (`efficiency`, `pace_easy`, `pace_threshold`, `completion`), Cohen's d effect size, transparent `interaction_score` with `effect_size_norm` + `sample_support` components, `INTERACTION_KEEP_THRESHOLD = 0.35`, persisted as `AutoDiscoveryExperiment` rows. **(4) Pilot registry tuning loop** — new `services/auto_discovery/tuning_loop.py`: reads `InvestigationParamSpec` metadata for all 6 pilot investigations, generates step-up/step-down candidates (20% of param range), temporarily patches `spec.min_activities` and `spec.min_data_weeks` during shadow evaluation then restores originals (no registry mutation), uses `AthleteFindingFQSAdapter.score_finding_list()` for baseline vs candidate scoring, keep rule: `score_delta > 0.03` AND no stability regression. **(5) Report upgrade** — `candidate_interactions` and `registry_tuning_candidates` are now structured dicts with `cleared_threshold` + `candidates` or explicit `reason`; score_summary includes FQS values per loop family; `production_cache_polluted: false` added to `no_surface_guarantee`; schema_version bumped to 2. Sample report: `docs/sample_auto_discovery_phase0b_run_report.json`. 35+ new tests in `apps/api/tests/test_auto_discovery_phase0b.py` (54 pass, 22 skip — no local Postgres). Safety guarantees unchanged: no athlete-facing table mutations, no live registry mutations, no production cache writes from shadow paths.

- **AutoDiscovery Phase 0A (Mar 11, 2026)**: Experiment ledger (`auto_discovery_run` + `auto_discovery_experiment` tables), founder-only orchestrator (shadow mode), FQS v1 adapters, feature flags, multi-window rescan (30/60/90/180/365/full-history), nightly Celery beat task. Migration: `auto_discovery_001` (chained off `temporal_fact_001`). Sample report: `docs/sample_auto_discovery_run_report.json`. 37 tests passing. CI green.

- **Full Correlation Engine Input Wiring (Mar 10, 2026)**: Engine expanded from 21 to 70 input signals across 5 phases. Phase 1: 14 GarminDay wearable signals (sleep score, deep/REM/light sleep, body battery, stress, HRV, resting HR, steps, respiratory rate, SpO2, aerobic/anaerobic TE). Phase 2: 18 activity-level signals (cadence, elevation, ground contact, power, dew point, temperature, etc.) via new `aggregate_activity_level_inputs()`. Phase 3: 5 feedback/reflection signals via new `aggregate_feedback_inputs()`. Phase 4: 6 checkin/composition/nutrition signals. Phase 5: 6 derived training pattern signals (weekly volume, long run ratio, quality session frequency, rest day frequency, intensity score, session variety) via new `aggregate_training_pattern_inputs()`. All new inputs wired into `analyze_correlations()` and `discover_combination_correlations()`. FRIENDLY_NAMES added to `n1_insight_generator.py` for all 49 new keys. DIRECTION_EXPECTATIONS and CONFOUNDER_MAP extended. Ban list verified (no new keys in `_VOICE_INTERNAL_METRICS`). 22 new tests in `test_correlation_inputs.py`. Spec: `docs/specs/CORRELATION_ENGINE_FULL_INPUT_WIRING_SPEC.md`. Audit: `docs/DATA_INTELLIGENCE_AUDIT_2026-03-10.md`. Commit: `d074587`.
- **Fingerprint Backfill (Mar 10-11, 2026)**: New script `apps/api/scripts/backfill_correlation_fingerprint.py`. Runs correlation analysis across 7 overlapping windows (30/60/90/120/180/270/365 days) × 9 output metrics per athlete. Computes robustness count per finding key (# windows where significant). Bounded bootstrap promotion: if `times_confirmed < 3` and robustness >= 3 windows, set `times_confirmed = 3`. Never boosts above 3 from backfill. Reruns are idempotent (no confirmation inflation). After correlation passes, runs L1-L4 layer enrichment and investigation engine refresh. Founder results: 38 active findings, 23 surfaceable, 14 layer-enriched, 15 investigation findings updated. Runtime: 27.5s. Targeted briefing refresh via `apps/api/scripts/refresh_briefings.py` (no `FLUSHALL`). Verification script at `apps/api/scripts/verify_backfill.py`. Commits: `f89d269` through `9a6dd59`.
- **Athlete Fact Extraction (Mar 10, 2026)**: Coach memory layer 1. New `AthleteFact` model with partial unique index `UNIQUE (athlete_id, fact_key) WHERE is_active = true`. Concurrency-safe upsert using `db.begin_nested()` savepoints — `IntegrityError` rolls back savepoint only, not parent transaction. Incremental extraction via `CoachChat.last_extracted_msg_count` checkpoint — only processes new messages since last extraction. Checkpoint advances only on successful extraction (not on LLM failure). Extraction triggers after `_save_chat_messages()`. Active facts injected into coach prompts (15 fact cap, ordered by `confirmed_by_athlete DESC, extracted_at DESC`). Injected into morning voice and Opus briefing prompts. Backfill script at `scripts/backfill_athlete_facts.py` with `--resume-from-chat-id` (strict `(created_at, id)` tuple boundary). Experience guardrail assertion #25: key-scoped superseded fact leak detection with numeric boundary matching. 26 tests in `test_fact_extraction.py`. Migration: `athlete_fact_001`. Commit: `0e9b6a9`.
- **Daily Experience Guardrail (Mar 10, 2026)**: 25 assertions across 6 categories: Data Truth (#1-#7), Language Hygiene (#8-#11), Structural Integrity (#12-#16), Temporal Consistency (#17-#19), Cross-Endpoint Consistency (#20-#22), Trust Integrity (#23-#25). Runs daily via Celery beat at 06:15 UTC. Preflight check: if no Garmin data in 18h, skip Category 1 (no wolf-crying on rest days). `coach_briefing` gets full assertion battery in Tier 1. Results logged to `ExperienceAuditLog` table. New service: `services/experience_guardrail.py`. New task: `tasks/experience_guardrail_task.py`. Migration: `exp_audit_001`. Spec: `docs/specs/DAILY_EXPERIENCE_GUARDRAIL_SPEC.md`. Commit: `0c4aa45`.
- **CI Hardening (Mar 10, 2026)**: Added `pytest-timeout` (120s per test) to prevent indefinite CI hangs. Backend Tests job has 20-minute timeout. Commit: `faa2463`.

### Previous delta (Mar 5 -> Mar 9)

- **Ledger P0 Fixes (Mar 9, 2026)**: (1) Removed live `analyze_correlations()` from Home request path — replaced with persisted `CorrelationFinding` lookup (`is_active=True`, `times_confirmed >= 3`), coaching language formatting. (2) Fixed 5 broken frontend links: removed dead `/lab-results` CTA from EmptyStates, changed `/plans` to `/plans/create` in insights, added `id="ai-powered-insights"` anchor on privacy page, added `id="runtoon"` anchor on settings page. (3) Deleted dead `apps/api/routers/lab_results.py` backend router. (4) Tightened `morning_voice` schema to one paragraph/2-3 sentences/no restatement, added warning telemetry at >240 chars (fail-close >280 unchanged). (5) Fixed ledger script to strip anchor fragments before route matching. Ledger P0 count = 0. Commit: `5d53e70`.
- **Home Page Intelligence Surfaces (Mar 9, 2026)**: (1) `heat_adjustment_pct` added to `LastRun` model and populated from activity data — frontend shows weather-adjusted pace context on home when >3%. (2) `HomeFinding` typed model with `finding: Optional[HomeFinding]` and `has_correlations: bool` on `HomeResponse`. Day-based rotation across top active confirmed findings. (3) Cold-start state on home: `<10` activities → "Getting started", `10-30` → "Patterns forming", `30+` with no confirmed finding → "Analysis in progress". (4) Activity detail response now includes `dew_point_f` and `heat_adjustment_pct`; frontend renders weather context when >3%. Commit: `02e2a26`.
- **Activity Intelligence + Navigation Gating + Daily Intelligence (Mar 9, 2026)**: (1) New `GET /v1/activities/{id}/findings` endpoint returns top 3 active confirmed `CorrelationFinding` entries as annotation cards. Frontend renders below Runtoon card. (2) `has_correlations` added to `/v1/auth/me` payload — Discovery and Fingerprint nav items in `Navigation.tsx` and `BottomTabs.tsx` only shown when `has_correlations=True`. (3) `TodayIntelligenceSection` wired into Insights page, fetching from `GET /v1/intelligence/today` — tier-safe (hides silently on 403), renders nothing if empty. Commit: `ac986eb`.
- **Founder/VIP Always-Opus Routing (Mar 8, 2026)**: `get_model_for_query()` now routes founder (`OWNER_ATHLETE_ID`) and VIP (`is_coach_vip = True`) athletes to Opus for ALL coach queries — no keyword gating. Previously, founder/VIP status only affected budget caps, not routing. `OWNER_ATHLETE_ID` set in production `.env`. Belle Vignes set as VIP. Larry was already VIP. Commit: `35b27ad`.
- **Gemini 2.5 Flash → Gemini 3 Flash Upgrade (Mar 8, 2026)**: Standard coaching model upgraded from `gemini-2.5-flash` to `gemini-3-flash-preview`. GPQA Diamond: 90.4% (was 82.8%). Improved tool calling with stricter validation. Two hardcoded model strings in `query_gemini()` replaced with `self.MODEL_DEFAULT` to prevent drift. Cost calculation updated ($0.50/$3.00 per 1M tokens). Gemini 3.1 Flash Lite was evaluated and rejected — it's optimized for bulk classification, not reasoning-heavy coaching. Commit: `35b27ad`.
- **Fingerprint Intelligence Wiring (Mar 8, 2026)**: All three narrative wiring tasks deployed. (1) Morning voice (`_build_rich_intelligence_context()`) now includes confirmed `CorrelationFinding` with layer data. (2) Coach brief (`build_athlete_brief()`) now injects "Personal Fingerprint" section (confirmed findings with layer data) and "Training Discoveries" section (`AthleteFinding`). Opus prompt in `_call_opus()` receives the full brief. (3) `compute_coach_noticed()` has a priority level surfacing recent confirmed fingerprint findings. 8 active patterns now visible to coach (2 STRONG at 7x/17x confirmed, 6 EMERGING at 1-2x). **Note:** Original "Personal Fingerprint Contract" prompt (which mandated citing confirmation counts) was removed in Intelligence Lanes fix (`1df7eb6`). System-speak instructions replaced with coaching language mandate.
- **Correlation Persistence Regression Fix (Mar 8, 2026)**: Mature findings (`times_confirmed >= 3`) no longer deactivated on a single sweep miss. Previously, any finding absent from one sweep was killed regardless of confirmation count. Confounded findings (`is_confounded = True`) always deactivate. Reactivated 2 findings (readiness 16x→17x, TSB 7x). Commit: `c3c3c57`.
- **Activity Identity Surface (Mar 7-8, 2026)**: `resolve_activity_title()` implements priority: athlete_title (editable) > shape_sentence (when auto-generated name detected) > original name. Auto-generated name detection covers Strava patterns ("Morning Run", "Afternoon Run"), Garmin location patterns ("{City} Running"), and demo titles. Race guard: `user_verified_race` or `is_race_candidate` → athlete name always wins. `PUT /v1/activities/{id}/title` endpoint for athlete editing. Title flows to Runtoon via `_ActivityProxy`. 34 tests. Spec: `docs/specs/ACTIVITY_IDENTITY_SURFACE_SPEC.md`. Commits: `e93a400`, `ee1171f`.
- **Home Page Intelligence Lanes (Mar 9, 2026)**: Structural fix for system-speak, finding repetition, and source redundancy in home briefing. (1) System-speak banned: removed prompt instructions mandating confirmation counts; added explicit ban on `confirmed N`, `r=`, `p-value`, `times_confirmed` in athlete-facing text. `fingerprint_context.py` header now says "Translate to coaching language." (2) Per-field lane injection: 6 pre-formatted context snippets (`fingerprint_summary`, `coach_noticed_source`, `today_summary`, `checkin_summary`, `race_summary`, `week_context`) bound to schema fields via `YOUR DATA FOR THIS FIELD:`. `morning_voice` = fingerprint findings only; `coach_noticed` = daily rules/wellness/signals; other fields have dedicated sources. (3) Live correlation path removed from `compute_coach_noticed` — was recomputing full correlation engine on every call with `r=` formatting. Persisted findings gate tightened from `times_confirmed >= 1` to `>= 3`. Daily rotation across top 5 findings. Coaching language formatting: threshold→"cliff", asymmetry→"downside Nx stronger", decay→"effect peaks within N days". (4) Source 1 (`generate_n1_insights`) removed from `_build_rich_intelligence_context` — redundant with persisted fingerprint context. (5) `_validate_briefing_diversity()` added (monitor mode): detects cross-lane fingerprint term leakage across fields. 6 new tests + 3 updated. Diagnostic: `docs/HOME_PAGE_INTELLIGENCE_DIAGNOSTIC.md`. Commit: `1df7eb6`.
- **Campaign Detection Fix (Mar 9, 2026)**: Replaced naive `detect_campaign()` in training story engine (merged all adaptation dates into single arc, producing wrong "27-week campaign" for injury-split history) with `_get_campaign_from_events()` that reads from real campaign detector output in `PerformanceEvent.campaign_data`. Returns None (silence) if no campaign data. Regression test added. Commit: `e27e204`.
- **Deprecation Cleanup (Mar 8, 2026)**: Three tracks resolved. (1) Pydantic v2: `class Config` → `ConfigDict`/`SettingsConfigDict` in 4 files. (2) DB imports: `from database import` → `from core.database import` across all API files. (3) HTTPX: raw `data=payload` → `content=payload` in 2 test files.
- **CI Hardening (Mar 8, 2026)**: Sentry atexit noise silenced in CI (explicit `init(dsn="")` when no DSN). `CODECOV_TOKEN` param added to Codecov action. `test_wrong_athlete_403` creates a real athlete record so auth returns 403 not 401. Commit: `6487e8a`.

### Previous delta (Feb 25 -> Mar 5)

- **Living Fingerprint — Full Build (Mar 3-5, 2026)**: 9,486 lines across 35 files. Four capabilities: (1) **Weather Normalization** — `heat_adjustment.py` (Magnus formula dew point + combined value heat model, cross-validated against TypeScript implementation). `dew_point_f` and `heat_adjustment_pct` columns on Activity. All pace comparisons in investigations now use heat-adjusted pace. `investigate_heat_tax` refactored to personal heat resilience score. Migration `lfp_001_heat`. (2) **Activity Shape Extraction** — `shape_extractor.py` (1,331 lines pure computation, no DB/IO). Extracts phases, accelerations, shape summary, and classification from per-second stream data. Dual-channel detection: velocity (GPS) + cadence (watch accelerometer) merged with deduplication. HR recovery rate computed per acceleration. Classifications: `easy_run`, `progression`, `tempo`, `fartlek`, `strides`, `threshold_intervals`, `speed_intervals`, `hill_repeats`, `long_run`, `anomaly`, `null`. `run_shape` JSONB column on Activity. Migration `lfp_002_shape`. Gate L passed: founder's progression, Larry's strides (cadence channel), BHL's tempo, easy run suppression — all correct. (3) **Investigation Registry** — `@investigation` decorator with `InvestigationSpec`, `INVESTIGATION_REGISTRY`, signal coverage checking, honest gap reporting. 15 registered investigations (10 original + 5 shape-aware). Legacy investigations wrapped with error handling. Migration `lfp_003_registry`. (4) **Shape-Aware Investigations** — 5 new: stride progression, cruise interval quality, interval recovery trend (cardiac recovery rate bpm/s), workout variety effect (RPI-normalized), progressive run execution. Migration `lfp_004_layer`. **Integration:** Strava post-sync runs weather→shape→findings chain. Garmin webhook runs shape extraction. Daily Celery beat refresh at 06:00 UTC. Finding persistence with supersession logic (one active per investigation×type pair). Coach fast path reads stored `AthleteFinding`. Training story reads from stored findings. **Quality:** `investigate_interval_recovery_trend` tracks HR bpm/s drop rate (not just pace recovery). `investigate_workout_variety_effect` uses `rpi_at_event` (eliminates cross-distance confound). Cadence-based stride detection works for all runner speeds. `MIN_ACCELERATION_DURATION_S = 8`. 55 tests. 9 commits from `0f066d6` to `189a53e`. CI all green. Production deployed and healthy.
- **Correlation Engine Layers 1–4 (Mar 3, 2026)**: Four second-pass analyses on confirmed correlation findings during the daily sweep. New file `services/correlation_layers.py` with four functions: (1) `detect_threshold()` — finds the input value where the correlation changes character (split-point scan, min 5 per segment, min |Δr| 0.2). (2) `detect_asymmetry()` — regression-slope comparison on each side of median baseline to detect whether bad inputs hurt more than good inputs help (t-test p < 0.1 gate). (3) `compute_decay_curve()` — full lag profile (0–7 days), classified as exponential (monotonic decay, half-life computed), sustained (4+ significant lags), or complex (non-monotonic). (4) `detect_mediators()` — cascade detection via existing `compute_partial_correlation()`, mediation ratio > 0.4, full mediation when partial_r < 0.3. New `CorrelationMediator` table for mediator rows. 14 new nullable columns on `CorrelationFinding` (6 threshold, 5 asymmetry, 3 decay). Migration `correlation_layers_001`. Second pass wired into `correlation_tasks.py` — runs after first pass for each athlete, only on confirmed findings (is_active AND times_confirmed >= 3). Fire-and-forget: layer failures logged but never break the sweep. 25 new tests in `test_correlation_layers.py` (all passing). Production: migration applied, all 14 columns verified, `CorrelationMediator` table created. Founder has 7 active findings (max 2x confirmed) — layers will activate as findings cross the 3x confirmation gate via daily sweeps. Commit: `085a878`.
- **Progress Page Fixes (Mar 3, 2026)**: (1) Hero layout changed from side-by-side flex to stacked column — headline full width, stats row below. (2) No-race hero mode now shows contextual content: CTL delta headline when fitness surged, patterns-found count, N=1 messaging. "Weeks tracked" stat replaced with "Patterns found". (3) Acronym fix: `_build_headline()` no longer lowercases metric labels — "Form (TSB)" stays as-is instead of becoming "form (tsb)". (4) Full correlation sweep triggered post effort-classification: 7 correlations found across 7 metrics (was 1), 5 new findings created. Commit: `25a8a96`.
- **N=1 Effort Classification (Mar 3, 2026)**: Replaced all `athlete.max_hr`-gated effort classification across 8 services (13 code paths) with a single shared function `classify_effort()` in new `services/effort_classification.py`. Three tiers: (1) HR percentile from athlete's own distribution (primary, always works), (2) HRR with observed peak (earned after 20+ activities and 3+ hard sessions), (3) Workout type + RPE (sparse HR data). Results: Recovery Fingerprint now renders real data (was `None`). All 6 correlation aggregate functions produce non-empty output (were `[]`). No `220-age` or hardcoded `185` in any consumer service. Founder thresholds: Tier=hrr, P80=145, P40=133, 381 activities, 85 hard sessions, observed peak 180, resting HR 59. 17 new tests, 60 total passing. 4 commits: `4abce42`, `9e052b7`, `c7ceab3`, `ab91715`.
- **Garmin Connect Enabled for All Users (Mar 3, 2026)**: Feature flag `garmin_connect_enabled` set to 100% rollout. Flag system remains in code for instant rollback. No code change — SQL-only gate.
- **Progress Page Phase 2 (Mar 3, 2026)**: Four items shipped. (1) CorrelationWeb desktop fixes: skip force simulation for ≤5 nodes (fixed positions), `alphaDecay` increased to 0.1, batched position updates via `requestAnimationFrame` (only on >1px change), edge hit target widened to 40px on desktop (`pointer: fine`), `sim.on('end')` handler stops ticks after convergence. (2) Acronym rule enforcement: `_humanize_metric()` replaced with explicit lookup table (25 entries). Hero stat labels changed from "CTL then"/"CTL now" to "Fitness then"/"Fitness now". Node labels and fact headlines use human names: "Session Stress", "Form (TSB)", "Personal Bests", "Motivation", etc. No raw CTL/ATL/TSB/HRV on any athlete-facing surface. (3) Daily correlation sweep: new Celery task `run_daily_correlation_sweep` in `correlation_tasks.py`, runs `analyze_correlations()` for all 9 output metrics (efficiency, pace_easy, pace_threshold, completion, efficiency_threshold, efficiency_race, efficiency_trend, pb_events, race_pace) for athletes with activity in last 24h. Scheduled at 08:00 UTC daily in `celerybeat_schedule.py`. Supports manual `athlete_ids` override for backfills. Founder backfill: 0 → 2 active findings across 9 metrics. (4) Recovery Fingerprint: `compute_recovery_curve()` in `recovery_metrics.py` finds hard sessions (avg_hr > 85% max_hr), tracks efficiency on days 0-7 after, normalizes as % of baseline, compares "now" (90d) vs "before" (180d). Added `recovery_curve` to `GET /v1/progress/knowledge` response. Frontend: `RecoveryFingerprint.tsx` Canvas 2D animated curve with dashed "before" line, solid green "now" curve with gradient fill and glow dot, hover tooltips, fallback message for insufficient data. 43 tests (all passing). 3 commits: `f208195`, `fb7bc4f`, `bd557d2`.
- **Garmin Production Environment Approved (Mar 3, 2026)**: Marc Lussi (Garmin Connect Partner Services) approved StrideIQ for the Garmin Connect Developer Program Production Environment. Approved API: **Health**. Approved for commercial/study use. The evaluation app was upgraded to production in-place — same credentials, same endpoints, no code changes needed. Rate limits lifted (100 → 10,000 days/min for backfill). Historical Data Export approved. Unscheduled follow-up review expected within weeks. Evaluation environment retained as sandbox/staging.
- **Correlation Engine Quality Fix + Correction (Mar 3, 2026)**: Two-phase fix. (1) Partial correlation confounder control: `compute_partial_correlation()` implements r_xy.z formula. Explicit `CONFOUNDER_MAP` (12 entries) and `DIRECTION_EXPECTATIONS` (13 entries). 5 new fields on `CorrelationFinding`: `partial_correlation_coefficient`, `confounder_variable`, `is_confounded`, `direction_expected`, `direction_counterintuitive` (migration `correlation_quality_001`). (2) Post-delivery correction: ATL was wrong confounder for acute-stress relationships (7-day rolling average misses single-session spikes). Replaced with `daily_session_stress` (daily sum of distance_m × avg_hr) via new `aggregate_daily_session_stress()`. TSB entries also switched from ATL (mathematically circular: TSB = CTL - ATL). Safety gate added: `direction_counterintuitive = True` now sets `is_active = False` regardless of partial r (temporary until confounder methodology fully validated). Result: founder's two problematic findings (motivation→efficiency, TSB→efficiency) now `is_active = False` — no longer visible on Progress page. 14 tests (all passing). No frontend changes needed.
- **Progress Knowledge v2 (Mar 2, 2026)**: Second rewrite of progress page. Replaces five-act narrative with three sections matching mockup v2: (1) Hero — gradient header with CTL stats (3.7→43.2), race countdown, coach-voice headline (LLM-generated with fallback), count-up animations. (2) Correlation Web — D3 force-directed graph showing N=1 confirmed correlations from `CorrelationFinding` model. Input nodes (blue, left) → output nodes (green, right). Edge thickness = |r|. Solid green = positive, dashed red = inverse. Hover any edge for detail panel with r-value, lag days, confirmation count, evidence narrative. (3) What the Data Proved — expandable fact list ordered by `times_confirmed` desc. Confidence tiers: emerging (1-2×, "signal to watch"), confirmed (3-5×, "becoming reliable"), strong (6+×, "consistently shows"). LLM generates per-finding implications with causal language rejected for emerging patterns. Backend: `GET /v1/progress/knowledge` — single endpoint, deterministic assembly <500ms, LLM <5s, Redis cached 30min. 15 new tests all passing. Frontend: `ProgressHero.tsx`, `CorrelationWeb.tsx`, `WhatDataProved.tsx`, `useProgressKnowledge()` hook. D3 dependency added. Old five-act components kept in codebase (other pages may use them) but removed from progress page.
- **Progress Narrative v1 (Mar 2, 2026, SUPERSEDED)**: Full replacement of 12-card progress page with visual-first five-act narrative. Backend: `GET /v1/progress/narrative` assembles deterministic visuals from training load (CTL/ATL/TSB), efficiency analytics, recovery metrics, correlation findings, coach tools (volume, wellness, PBs, race predictions), and consistency index. Gemini 2.5 Flash synthesizes narrative bridges (consent-gated via `has_ai_consent`, graceful fallback to deterministic-only). Redis-cached 30min, invalidated on new activity/check-in. `POST /v1/progress/narrative/feedback` logs athlete feedback to new `NarrativeFeedback` table (`progress_narrative_001` migration). Five-act structure: (1) Verdict — fitness arc sparkline + coach voice, (2) Chapters — topic-specific visuals (bar chart, sparkline, health strip, gauge, stat highlight, completion ring) with observation/evidence/interpretation/action, empty chapters suppressed, (3) N=1 Patterns — paired sparklines for confirmed correlations with confidence gating (no causal language for "emerging" patterns), patterns-forming progress bar when insufficient data, (4) Looking Ahead — race readiness gauge + scenarios when training plan exists, or capability trajectory bars otherwise, (5) Athlete Controls — feedback buttons + "Ask Coach" deep link. Frontend: 8 new visual components (`SparklineChart`, `BarChart`, `HealthStrip`, `FormGauge`, `PairedSparkline`, `CapabilityBars`, `CompletionRing`, `StatHighlight`), `useProgressNarrative()` + `useNarrativeFeedback()` hooks. 14 new backend tests passing. Production verified: endpoint returns full response with real athlete data in 8ms (cached).
- **Coach quality fixes (Mar 2, 2026)**: Three production failures addressed. (1) **GarminDay Health API data now in coach context**: `build_context()` in `ai_coach.py` queries `GarminDay` for last 7 days — `sleep_total_s` (shown as hours), `hrv_overnight_avg`, `resting_hr`, `avg_stress`, `sleep_score`, `body_battery_end` — formatted as "## Garmin Watch Data (Health API)" section with date-by-date rows. `get_wellness_trends()` in `coach_tools.py` now also queries `GarminDay` alongside `DailyCheckin`, adding Garmin-sourced sleep, HRV, RHR, stress to the narrative and a `garmin_health_api` data block. Attribution explicit: "source: Garmin Health API" in all narrative lines. (2) **Distances normalized to miles throughout coach context**: all `/ 1000` (km) replaced with `/ 1609.344` (miles), `_format_pace` now outputs `/mi`. (3) **Coach-noticed 48h rotation**: after each briefing write, `coach_noticed` text persisted to Redis `coach_noticed_last:{athlete_id}` with 49h TTL. Prompt for next briefing includes `ROTATION CONSTRAINT` instructing LLM not to repeat it. (4) **Hallucination guardrails**: soreness null → prompt says "not reported today — do NOT claim any soreness"; week run count explicitly grounded as `Runs completed this week so far: N` with LLM ban on fabricating missed/cut-run claims. 15 new unit tests (all passing). 117 pre-existing tests unchanged.
- **Runtoon Share Flow live and verified (Mar 1, 2026)**: Major UX pivot — Runtoon is now generated on-demand when the athlete taps "Share Your Run," not automatically on sync. Confirmed working end-to-end on mobile: WhatsApp and Google Messages sharing verified. Backend: `runtoon_002` migration (`share_dismissed_at` on `Activity`, `shared_at`/`share_format`/`share_target` on `RuntoonImage`). 3 new endpoints: `GET /v1/runtoon/pending` (share-eligible activity check, 8 eligibility rules, 2-mile threshold, 24h window), `POST /v1/activities/{id}/runtoon/dismiss` (idempotent, keyed by activity), `POST /v1/runtoon/{id}/shared` (analytics, `share_target` best-effort/nullable). Auto-generation removed from Garmin/Strava sync pipelines. Frontend: new `RuntoonSharePrompt` (mobile bottom sheet, polls `/pending` every 10s, auto-dismisses after 10min), new `RuntoonShareView` (full-screen overlay, generation skeleton with "Almost there..." hint, Web Share API with native share sheet on iOS/Android, desktop download+copy fallback). `RuntoonCard` updated: shows "Share Your Run" CTA for all runs (with or without existing Runtoon). All endpoints gated behind feature flag. 39 new tests (81 total for Runtoon system). **3 post-deploy fixes applied:** (1) download endpoint was passing raw storage key instead of signed URL, (2) duplicate `to_public_url` function shadowed the MinIO-to-Caddy URL rewriter — all browser-facing URLs were pointing to internal Docker address, (3) `RuntoonCard` returned null when no Runtoon existed — now shows on-demand generation CTA.
- **Runtoon MVP live (Feb 28–Mar 1, 2026)**: Full-stack AI-generated personalized run caricature. Backend: `AthletePhoto` + `RuntoonImage` models, `runtoon_001` Alembic migration, `storage_service.py` (boto3 → MinIO), `runtoon_service.py` (Gemini `gemini-3.1-flash-image-preview` for image, `gemini-2.5-flash` for caption), `runtoon_tasks.py` (Celery async), `runtoon.py` router. Frontend: `RuntoonCard` on activity detail (above the fold), `RuntoonPhotoUpload` in settings. Feature-flagged (`runtoon.enabled`) — founder + father rollout. Object storage: MinIO (self-hosted S3-compatible, `strideiq_minio` container, private bucket `strideiq-runtoon`). Caddy proxy route (`/storage/*`) serves signed MinIO URLs to browsers. Style: no speech bubbles/comic sound effects — humor from scene composition and expressions. Captions: AI-generated with quality gates (min 20 chars, multi-word, blocklist, retry on rejection). Rich context: weekly mileage, upcoming race, training phase, coach insights fed to both image and caption prompts. 9:16 Stories recompose: Pillow-based, centered letterbox with watermark. Download: blob-based file save (not new-tab). Daily cap: 5 generations/athlete/day.
- **Compact PMC chart added to home page (Mar 1, 2026)**: 30-day Fitness/Fatigue/Form chart now visible on home in position 2 (directly below LastRunHero, above Morning Voice). Self-contained component `CompactPMC.tsx` fetches from existing `/v1/training-load/history?days=30` endpoint (5-min cache). Renders nothing if no data. "View training load →" CTA + chart body click navigates to `/training-load`. Legend tooltips explain each metric independently. UTC-safe date formatting.
- **Chart date labels timezone fix (Mar 1, 2026)**: All Recharts date axes now use UTC methods — chart labels no longer shift one day back for US timezone users.
- **Monetization v1 completed**: 4-tier pricing UX, checkout flows, settings tier display, plan pace lock/unlock UX, register intent carry-through.
- **PDF plan export shipped**: entitlement-gated endpoint `GET /v1/plans/{plan_id}/pdf`, WeasyPrint/Jinja backend generation, guarded limits.
- **Garmin brand/compliance surfaces updated**: official badge/icon usage on settings + activity/home surfaces; attribution wording tightened.
- **Home briefing reliability hardening shipped**: force-refresh triggers on Garmin/Strava sync paths plus deterministic fallback when LLM path is unavailable.
- **Run context science moat upgrade shipped**: `GarminDay` now gap-fills run context inputs when check-ins are missing; explicit source labeling and device stress qualifier path added.
- **Garmin ingestion health monitor shipped**: admin endpoint `GET /v1/admin/ops/ingestion/garmin-health` + daily Celery task + underfed coverage logging.
- **Email transport hardening shipped**: SMTP timeout control, explicit TLS context, and reset-link base URL now sourced from `WEB_APP_BASE_URL`.

---

## 1. Infrastructure & Deployment

| Component | Technology | Location |
|-----------|-----------|----------|
| **Web** | Next.js 14 (App Router) | `apps/web/` |
| **API** | FastAPI (Python 3.11) | `apps/api/` |
| **Database** | TimescaleDB (PostgreSQL 16) | Docker: `timescale/timescaledb:latest-pg16` |
| **Workers** | Celery | `apps/api/tasks/` (14 task modules) |
| **Object Storage** | MinIO (S3-compatible) | Docker: `strideiq_minio`, private bucket `strideiq-runtoon` |
| **Cache/Queue** | Redis 7 Alpine | Celery broker + response cache |
| **Proxy** | Caddy 2 | Auto-TLS, reverse proxy |
| **CI** | GitHub Actions (push: smoke+lint+migration; nightly: full suite) | `.github/workflows/` |
| **Production** | Hostinger KVM 8 (8 vCPU, 32GB RAM, 400GB NVMe) | `187.124.67.153` |
| **Domain** | `strideiq.run` / `www.strideiq.run` / `api.strideiq.run` | Caddy routes |
| **Repo** | `github.com/Nmdk1/StrideIQ` | Single `main` branch |

### Production Layout

```
/opt/strideiq/repo/          ← Git checkout
docker compose up -d         ← 7 containers: api, web, caddy, postgres, redis, worker, minio
API runs migrations on boot  ← alembic upgrade head in entrypoint
```

### Deployment Workflow

```
local: git push origin main
droplet: cd /opt/strideiq/repo && git pull origin main && docker compose up -d --build
```

Migration runs automatically on API container startup. Manual migration: `docker compose exec api alembic upgrade head`.

---

## 2. Codebase Scale (as of 2026-04-01)

| Metric | Count |
|--------|-------|
| SQLAlchemy models | 53 |
| FastAPI routers | 55 |
| Python services | ~120 |
| Celery task modules | 14 |
| Test files | 175+ |
| Passing tests | 4,036+ (nightly full suite) |
| KB rule evaluator | 445 PASS / 0 FAIL / 17 WAIVED (33 rules × 14 archetypes) |
| Legacy BC evaluator | 143 PASS / 0 FAIL (12 BCs × 14 archetypes, secondary gate) |
| Alembic migrations | 95 |
| Correlation engine inputs | 70 |
| React pages | 63 |
| React components | 70 |
| TanStack Query hooks | 21 |
| Intelligence rules | 8 |

---

## 3. Core Data Models (53 tables)

### Athlete & Auth
- `Athlete` — core user record, includes `is_demo` flag (demo accounts cannot link Strava)
- `InviteAllowlist` — gated signup
- `Subscription`, `StripeEvent`, `Purchase`, `RacePromoCode` — payments/entitlements

### Activity & Performance
- `Activity` — ingested activities from Strava/Garmin (run, cycling, walking, hiking, strength, flexibility). Cross-training columns: `garmin_activity_type`, `cadence_unit`, `session_detail` (JSONB). Pre-activity wellness stamps: `pre_sleep_h`, `pre_sleep_score`, `pre_resting_hr`, `pre_recovery_hrv`, `pre_overnight_hrv` (migration `wellness_stamp_001`)
- `ActivitySplit` — per-split metrics
- `ActivityStream` — raw stream data (HR, pace, altitude, cadence)
- `PersonalBest`, `BestEffort` — PR tracking across distances
- `CachedStreamAnalysis` — versioned stream analysis cache (bump `CURRENT_ANALYSIS_VERSION` to invalidate)
- `ActivityFeedback`, `ActivityReflection` — athlete subjective input per activity

### Check-in & Wellness
- `DailyCheckin` — **the check-in data**: `sleep_h`, `sleep_quality_1_5`, `stress_1_5`, `soreness_1_5`, `rpe_1_10`, `motivation_1_5`, `confidence_1_5`, `enjoyment_1_5`, `hrv_rmssd`, `hrv_sdnn`, `resting_hr`, `overnight_avg_hr`
- `BodyComposition` — weight, body fat, BMI
- `NutritionEntry` — nutrition tracking (minimal)
- `WorkPattern` — work/life pattern tracking

### Training Plans
- `TrainingPlan` — generated plans
- `PlannedWorkout` — individual planned sessions
- `PlanModificationLog` — audit trail for plan changes
- `WorkoutTemplate`, `WorkoutDefinition`, `PhaseDefinition`, `ScalingRule`, `PlanTemplate` — plan framework
- `TrainingAvailability` — athlete schedule constraints
- `PlanAdaptationProposal` — pending/accepted/rejected plan adjustment proposals (adaptive re-plan)

### Intelligence & Adaptation
- `DailyReadiness` — readiness score computation
- `AthleteAdaptationThresholds` — per-athlete adaptation parameters
- `ThresholdCalibrationLog` — threshold learning audit
- `SelfRegulationLog` — planned vs actual deltas
- `InsightLog` — every intelligence insight (8 rules), with narrative attachment
- `NarrationLog` — narration scoring audit trail (3 binary criteria)
- `CorrelationFinding` — **NEW (2026-02-16)**: persistent correlation discoveries with reproducibility tracking
- `AthleteLearning`, `AthleteCalibratedModel`, `AthleteWorkoutResponse` — N=1 learning

### Coach
- `CoachChat` — conversation history (includes `last_extracted_msg_count` for incremental fact extraction)
- `AthleteFact` — coach memory: facts extracted from chat (partial unique index on active key per athlete)
- `CoachIntentSnapshot` — coach decision audit
- `CoachActionProposal` — proposed actions (propose → confirm → apply)
- `CoachUsage` — LLM usage tracking
- `CoachingKnowledgeEntry`, `CoachingRecommendation`, `RecommendationOutcome` — knowledge base

### Calendar & Insights
- `CalendarInsight`, `CalendarNote` — calendar-attached intelligence
- `InsightFeedback` — athlete response to insights
- `FeatureFlag` — feature gating

### Athlete Profile
- `AthleteRaceResultAnchor`, `AthleteTrainingPaceProfile` — race anchors and pace zones
- `AthleteGoal` — training goals
- `IntakeQuestionnaire` — onboarding data
- `AthleteIngestionState`, `AthleteDataImportJob` — Strava/Garmin sync state

### Admin & Audit
- `InviteAuditEvent`, `AdminAuditEvent` — admin operation audit trail
- `WorkoutSelectionAuditEvent` — workout selection transparency
- `ExperienceAuditLog` — daily experience guardrail assertion results

---

## 4. Intelligence Pipeline

### Daily Intelligence Engine (`services/daily_intelligence.py`)

Runs via `tasks/intelligence_tasks.py` every 15 minutes. For each qualifying athlete:
readiness → intelligence rules → narrate → persist.

**8 Rules:**

| # | Rule ID | Mode | Trigger |
|---|---------|------|---------|
| 1 | `LOAD_SPIKE` | INFORM | Volume/intensity up >15% week-over-week |
| 2 | `SELF_REG_DELTA` | LOG | Planned workout ≠ actual workout |
| 3 | `EFFICIENCY_BREAK` | INFORM | Efficiency improved >3% over 2 weeks |
| 4 | `PACE_IMPROVEMENT` | INFORM | Faster pace + lower HR vs target |
| 5 | `SUSTAINED_DECLINE` | FLAG | 3+ weeks declining efficiency |
| 6 | `SUSTAINED_MISSED` | ASK | >25% skip rate over 2 weeks |
| 7 | `READINESS_HIGH` | SUGGEST | High readiness + easy-only for 10+ days |
| 8 | `CORRELATION_CONFIRMED` | INFORM | Reproducible check-in → performance pattern (3+ confirmations) |

### Correlation Engine (`services/correlation_engine.py`)

Discovers N=1 correlations between inputs and outputs. **Expanded from 21 to 70 input signals on March 10, 2026.**

- **70 input signals** across 5 categories: GarminDay wearable (14), activity-level (18), feedback/reflection (5), checkin/composition/nutrition (6), derived training patterns (6), plus original daily inputs (21)
- **Statistical gates:** p < 0.05, |r| >= 0.3, n >= 10
- **Time-shifted:** 0–7 day lags (catches "bad sleep → performance drops 2 days later")
- **Output metrics:** efficiency, pace_easy, pace_threshold, completion, efficiency_threshold, efficiency_race, efficiency_trend, pb_events, race_pace
- **Bonferroni correction** applied in N1 insight generator
- **Aggregation functions:** `aggregate_daily_inputs()`, `aggregate_activity_level_inputs()`, `aggregate_feedback_inputs()`, `aggregate_training_pattern_inputs()`
- **Confounder control:** `CONFOUNDER_MAP` with explicit pairs, partial correlation via `compute_partial_correlation()`
- **Direction expectations:** `DIRECTION_EXPECTATIONS` for sanity checks on known relationships

### Correlation Persistence (`services/correlation_persistence.py`) — NEW

Findings are now stored permanently in `correlation_finding` table:

1. **Upsert on confirm:** Same (athlete, input, output, lag) → `times_confirmed += 1`
2. **Deactivate on fade:** Previously-significant finding drops below threshold → `is_active = False`
3. **Surfacing gate:** Only findings with `times_confirmed >= 3` are eligible
4. **Cooldown:** Once surfaced, 14-day cooldown before re-surfacing
5. **Confidence boost:** `confidence * (1 + 0.1 * (times_confirmed - 1))`, capped at 1.0
6. **Daily limit:** Max 2 correlation insights per day per athlete

### N1 Insight Generator (`services/n1_insight_generator.py`)

Generates polarity-aware insights from correlation engine output. Categorizes as `what_works`, `what_doesnt`, or `pattern` (ambiguous metrics). Uses `OutputMetricMeta` registry for polarity.

### Adaptation Narrator (`services/adaptation_narrator.py`)

Phase 3A. Gemini Flash generates 2–3 sentence coaching narrations for each InsightLog entry.
- Scored against engine ground truth (3 binary criteria: factually correct, no raw metrics, actionable language)
- Score < 0.67 → suppressed (silence > bad narrative)
- Contradiction detected → suppressed
- Results stored in `NarrationLog`

### Living Fingerprint — Activity Intelligence Pipeline

Persistent, incrementally-updated intelligence layer. Four capabilities:

1. **Weather Normalization** (`services/heat_adjustment.py`) — Magnus formula dew point + combined value heat adjustment. All pace comparisons heat-adjusted.
2. **Shape Extraction** (`services/shape_extractor.py`) — 1,331 lines pure computation. Per-second stream → phases, accelerations (dual-channel: velocity + cadence), shape summary, classification. JSONB on Activity.
3. **Investigation Registry** (`services/race_input_analysis.py`) — `@investigation` decorator, 15 registered investigations, signal coverage, honest gaps.
4. **Finding Persistence** (`services/finding_persistence.py`) — `AthleteFinding` model. Supersession logic. One active per investigation×type. Coach fast path.

Refresh: daily Celery beat task at 06:00 UTC (`refresh_living_fingerprint`). Also runs inline on every Strava sync and Garmin webhook.

### Training Story Engine (`services/training_story_engine.py`)

Synthesizes findings into race stories, build sequences, and training progressions. Operates on `mine_race_inputs()` output without re-querying DB. Connection types: input→adaptation, adaptation→outcome, compounding, confound adjustment.

### Readiness Score (`services/readiness_score.py`)

Phase 2A. Composite score from efficiency trend, recovery balance, completion rate, recovery days.
- Sleep currently **excluded** from readiness until correlation engine proves individual relationship (per rebuild plan)

---

## 5. Check-in Data Flow (End-to-End)

This is the full lifecycle of check-in data:

```
Athlete → Home Page Quick Check-in (consolidated — /checkin now redirects to /home)
    ↓
POST /v1/daily-checkin → DailyCheckin table
    ↓ (optimistic UI update — UI switches instantly, background refetch)
    ↓
Correlation Engine (called on-demand or via daily intelligence)
    ↓ aggregates: sleep_h, soreness_1_5, motivation_1_5, stress_1_5, etc.
    ↓ correlates with: activity efficiency, pace, completion
    ↓ time-shifted: 0–7 day lags
    ↓
persist_correlation_findings() → correlation_finding table
    ↓ upsert: increment times_confirmed or create new
    ↓ deactivate faded patterns
    ↓
Daily Intelligence Engine (Rule 8: CORRELATION_CONFIRMED)
    ↓ checks: times_confirmed >= 3, is_active, not recently surfaced
    ↓
InsightLog → Adaptation Narrator → Narrated to athlete
    ↓
"Based on your data: your running efficiency noticeably tends to
 improve within 2 days when your sleep hours are higher. This
 pattern has been confirmed 4 times — it's becoming a reliable signal."
```

**Also consumed by:**
- `run_analysis_engine.py` — same-day + trailing checkin context for individual run analysis
- `causal_attribution.py` — Granger causality testing (0–7 day impacts)
- `trend_attribution.py` — identifies factors preceding efficiency trends (0–2 day lags)
- `pattern_recognition.py` — trailing context for PR pattern analysis
- `pre_race_fingerprinting.py` — race-day wellness vs baseline
- `ai_coach.py` — recent checkin data in coaching context
- `coach_tools.py` — `get_wellness_trends()` aggregation

---

## 6. Frontend Architecture

### Key Pages

| Route | Purpose | Status |
|-------|---------|--------|
| `/home` | Morning command center: run shape + compact PMC (visual pair), coach briefing, **wellness row** (Recovery HRV + overnight avg + RHR + sleep with personal ranges), **mindset check-in** (enjoyment + confidence), workout, race countdown, **weekly chips show cross-training with sport icons** | Working — cross-training chips shipped Apr 4 |
| `/manual` | **Primary nav.** Personal Operating Manual: Race Character, Cascade Stories, Highlighted Findings, Full Record, What Changed delta tracking | Working — V2 shipped Apr 4 |
| `/activities` | Activity list with sport icons (dumbbell/bike/mountain/footprints/stretch for cross-training), compare mode | Working — cross-training icons shipped Apr 4 |
| `/activities/[id]` | Activity detail: **Runs:** Run Shape Canvas, Runtoon, splits, weather context, finding annotations, wellness snapshot, analysis. **Non-run:** sport-specific layouts — cycling (metrics + HR + elevation), strength (exercise sets by movement pattern + session type + volume), hiking (elevation hero + metrics), flexibility (minimal). Universal: wellness stamps, TSS training load card, title editing | Working — sport-specific detail pages shipped Apr 4 |
| `/calendar` | Training calendar with plan overlay | Working |
| `/coach` | AI coach chat interface | Strongest surface — founder/VIP always Opus, standard users Gemini 3 Flash |
| `/progress` | D3 force-directed correlation web, expandable proved facts, coach-voice hero — replaces old card grid | Working |
| `/analytics` | Efficiency trends, correlations, load→response, **trends summary** (efficiency/volume trends + root cause analysis, absorbed from `/trends`) | Working — trends absorbed Apr 4 |
| `/training-load` | PMC chart, N=1 zones, daily stress, **cross-training TSS disclosure with expandable 7-day breakdown** | Working — transparency disclosure shipped Apr 4 |
| `/settings` | **Personal Information** (name, email, birthdate, sex, height — absorbed from `/profile`), Strava/Garmin integration, preferences, membership, data/privacy | Working — profile section added Apr 4 |
| `/tools` | Pace calculator, age grading, heat adjustment | Working |
| `/nutrition` | Quick nutrition logging | Minimal/placeholder |
| `/insights` | **DEPRECATED** — permanent redirect to `/manual` | Redirect shipped Apr 4 |
| `/discovery` | **DEPRECATED** — permanent redirect to `/manual` | Redirect shipped Apr 4 |
| `/checkin` | **DEPRECATED** — permanent redirect to `/home` | Redirect shipped Apr 4; mindset fields on home |
| `/dashboard` | **DELETED** — was redirect to `/home` | Deleted Apr 4 |
| `/home-preview` | **DELETED** — dev layout preview | Deleted Apr 4 |
| `/spike/rsi-rendering` | **DELETED** — ADR-064 rendering spike | Deleted Apr 4 |
| `/diagnostic` | **DEPRECATED** — server redirect to `/home` | Redirect Apr 4 |
| `/diagnostic/report` | **DEPRECATED** — server redirect to `/admin/diagnostics` | Redirect Apr 4 |
| `/profile` | **DEPRECATED** — redirect to `/settings` | Redirect Apr 4 (merged into Settings) |
| `/availability` | **DEPRECATED** — redirect to `/plans/create` | Redirect Apr 4 |
| `/trends` | **DEPRECATED** — redirect to `/analytics` | Redirect Apr 4 (absorbed into Analytics) |

**Navigation structure (current):**
- **Primary (desktop top bar / mobile bottom tabs):** Home | Manual | Progress | Calendar | Coach
- **Secondary ("More" dropdown):** Analytics | Training Load | Tools | Nutrition | Settings
- **Removed from nav:** Insights, Discovery, Check-in, Profile, Availability, Trends, Dashboard

### Data Fetching

TanStack Query (React Query) with 20 custom hooks in `apps/web/lib/hooks/queries/`.
API client at `apps/web/lib/api-client.ts`.

---

## 7. Build Priority & Phase Status

From `docs/TRAINING_PLAN_REBUILD_PLAN.md`:

| Phase | Status | Tests |
|-------|--------|-------|
| Phase 1 (Plans) | **V3 REBUILT** — diagnosis-first N=1 engine | 445 PASS, 0 FAIL (KB rule evaluator, 33 rules × 14 archetypes) |
| Phase 2 (Adaptation) | COMPLETE | 29 passing |
| Phase 3A (Narration) | COMPLETE | 66 passing |
| Coach Trust | COMPLETE | 22 passing |
| Phase 3B (Workout Narratives) | CODE COMPLETE — gate accruing | 65+ passing, 24 xfail |
| Phase 3C (N=1 Insights) | CODE COMPLETE — gate accruing | 65+ passing, 26 xfail |
| Phase 4 (50K Ultra) | CONTRACT ONLY | 37 xfail |
| Monetization Tiers | v2 COMPLETE (2-tier model shipped) | residual xfails remain for deferred contracts |

**Plan engine and intelligence context (Mar 26-29):**
Legacy plan generators were deleted and replaced. The new engine (`n1_engine.py`, 1,078 lines) passes 33 KB rules across 14 archetypes (445 PASS, 0 FAIL). Limiter engine Phases 1-3 complete: fingerprint bridge, temporal weighting, lifecycle classifier. Variant dropdown shipped. The system now produces individualized, KB-grounded plans with N=1 limiter intelligence and evaluator-enforced quality gates.

**Build priority order (current):**
1. ~~Limiter Engine Phase 4: Coach layer integration~~ — ✅ COMPLETE (Mar 31). Emerging surfacing + fact-driven promotion verified in production.
2. ~~Cross-Training Activity Storage — Workstream 1: Data Infrastructure~~ — ✅ COMPLETE (Apr 1). 76 sport filters + adapter expansion + sport-aware TSS + partial index.
3. ~~Limiter Engine Phase 5: Transition detection~~ — ✅ COMPLETE (Apr 4). `active` → `resolving` → `closed` triggers next-frontier scan. Wired into nightly sweep.
4. ~~N1 Engine Phase 4: Adaptive Re-Plan~~ — ✅ COMPLETE (Apr 4). Three triggers (missed long run, 3+ consecutive missed, 5-day readiness tank). 2-week micro-plan via N1 engine with phase-aware constraints. Day-level diff with accept/reject card on home page. Briefing acknowledges pending proposal. Max 2 adaptations/cycle, max 5 changed days, 48h cooldown, no taper. Silence = keep original. `PlanAdaptationProposal` model + migration. P0-gated.
5. Phase 4 (50K Ultra) — new user segment + differentiation (37 xfail contract tests waiting)
6. Phase 3B (when narration quality gate clears — >90% for 4 weeks)
7. Phase 3C (when per-athlete synced history + significant correlations exist)

**Open gates:**
- 3B: narration accuracy > 90% for 4 weeks (`/v1/intelligence/narration/quality`)
- 3C: per-athlete synced history + significant correlations (founder rule: immediate if history exists)

---

## 8. Known Issues & Technical Debt

### Active Issues
- **Garmin physiology coverage is underfed for connected athletes** — monitor now exists (`/v1/admin/ops/ingestion/garmin-health`) and currently indicates sparse sleep/HRV population for some athletes.
- ~~**Email deliverability wiring remains operationally sensitive**~~ — **RESOLVED (Feb 28, 2026).** Production email is live: `smtp.gmail.com:587`, sender `noreply@strideiq.run` via `michael@strideiq.run`. Password reset E2E verified by Codex. DNS hardening (SPF/DKIM/DMARC) still needed at Porkbun.
- **Coach quality audit scoped (Mar 8, 2026):** Full audit of 11 failure patterns documented in `docs/COACH_QUALITY_AUDIT.md`. Covers: A-I-A template rigidity, reflexive conservatism, hallucinated external facts, math errors, sycophantic recovery, lecturing experienced athletes, not using tools, ignoring prior context. Fixes scoped: deterministic pre-checks (race day, recent activity, weather), system prompt rewrites, routing expansion for standard users. Queued behind current work.
- **Campaign detection wired but post-sync path lacks behavioral test:** `services/campaign_detection.py` wired into `refresh_living_fingerprint` and `post_sync_processing_task`. Refresh path has behavioral CI guard. Post-sync path has best-effort `try/except` but only source-level test coverage. Builder instructions: `docs/BUILDER_INSTRUCTIONS_2026-03-09_CAMPAIGN_WIRING_AND_REGRESSION_TEST.md`.
- ~~**Insights feed noise:**~~ RESOLVED (Apr 4). `/insights` now permanently redirects to `/manual`. The Manual V2 interestingness filter replaces the feed — cascade chains first, race character second, threshold findings third, simple correlations in full record.
- **Activity detail moments:** some key moments still show raw metrics that need stronger narrative translation
- **Home page dual voice:** RESOLVED (Mar 9). `morning_voice` now draws from fingerprint findings; `coach_noticed` draws from daily rules/wellness/signals. Per-field lane injection prevents overlap. Commit: `1df7eb6`.
- **No findings regression test:** RESOLVED (Mar 9). `test_findings_regression.py` asserts mature findings survive sweeps, surfacing threshold, and campaign wiring. Commit: `e27e204`.
- **Broken frontend links:** RESOLVED (Mar 9). All 5 broken links fixed. Dead `/lab-results` CTA removed. Lab-results backend router deleted. Ledger script fixed to handle anchor fragments. `broken_link_count = 0`. Commit: `5d53e70`.
- **Live `analyze_correlations()` in Home path:** RESOLVED (Mar 9). Replaced with persisted `CorrelationFinding` lookup. Commit: `5d53e70`.

### Technical Debt (Tracked, Not Blocking)
- 8 services with local efficiency polarity assumptions — migrate to `OutputMetricMeta` registry
- Timezone-aware vs naive datetime comparisons in `ensure_fresh_token` (observed during Danny's Strava debug)
- Sleep weight = 0.00 in readiness score — excluded until correlation engine proves individual relationship
- Recovery-modulated ramp ceiling: use the athlete's actual tau1/tau2/HRV signature to determine how aggressively they can absorb volume increases, instead of a blanket 1mi/session floor for everyone. Floor is session-based, ceiling should be N=1.

### Resolved Issues
- **Garmin production-access process (Mar 3, 2026):** Marc Lussi (Partner Services) approved StrideIQ for production environment. Health API approved for commercial/study use. Rate limits lifted. Historical Data Export approved.
- **Coach Garmin Health API data (Mar 2 → resolved Mar 2, 2026):** `build_context()` now queries `GarminDay` for last 7 days. Sleep, HRV, RHR, stress, body battery in coach context with "source: Garmin Health API" attribution.
- **Coach hallucinations (Mar 2 → resolved Mar 2, 2026):** Soreness null → prompt says "not reported today — do NOT claim any soreness." Week run count grounded with explicit count and fabrication ban.
- **Coach noticed staleness (Mar 2 → resolved Mar 2, 2026):** 48h rotation via Redis persistence + ROTATION CONSTRAINT in prompt.
- **Coach context distances in km (Mar 2 → resolved Mar 2, 2026):** All distances normalized to miles, `_format_pace` outputs `/mi`.
- **Founder/VIP Opus routing broken (discovered Mar 8 → resolved Mar 8, 2026):** `OWNER_ATHLETE_ID` was never set in production env, so `_is_founder()` always returned False. Budget bypass was dead code. Fixed: env var set, routing logic updated to route ALL founder/VIP queries to Opus. Commit: `35b27ad`.
- **Chart date labels shifted by one day in US timezones (Mar 1, 2026)** — All Recharts date axes now use UTC methods (`getUTCMonth()`, `getUTCDate()`, `timeZone: 'UTC'`) to prevent local-timezone date shift. Fixed in `training-load/page.tsx` (PMC + Daily TSS charts, 4 locations) and `LoadResponseChart.tsx`, `AgeGradedChart.tsx`, `EfficiencyChart.tsx` (3 locations). 7 locations total.
- **Monetization v1 closure (Feb 26, 2026)** — 4-tier purchase and entitlement surfaces now shipped end-to-end (pricing/settings/checkout/locked-pace UX/register carry-through).
- **PDF plan export shipped (Feb 26, 2026)** — entitlement-gated download endpoint and full backend generation path live.
- **Garmin sync-to-briefing staleness hardening (Feb 27-28, 2026)** — Garmin/Strava sync paths now explicitly mark briefing dirty and enqueue refresh; deterministic fallback prevents stale lock-in when LLM path fails.
- **Run context GarminDay gap-fill (Feb 28, 2026)** — run analysis now consumes Garmin physiology when check-ins are missing, without overwriting athlete self-report.
- **Garmin ingestion health monitor (Feb 28, 2026)** — new admin endpoint and daily worker checks make underfed physiology visible.
- **Password-reset email transport hardening (Feb 28, 2026)** — SMTP send path now uses timeout + TLS context; reset links now derive from `WEB_APP_BASE_URL`; logging clarified for send failure scenarios.
- **Sleep prompt grounding (Feb 24, 2026)** — Home morning briefing cited wrong sleep hours (7.5h vs 6h45 Garmin / 7.0h manual). Fixed with: `_build_checkin_data_dict()` (sleep_h numeric now in prompt), `_get_garmin_sleep_h_for_last_night()` (device sleep as ground truth), SLEEP SOURCE CONTRACT in prompt, `validate_sleep_claims()` validator (0.5h tolerance), wellness trends recency prefix. 22 new regression tests. Commit `494b9e9`.
- **Garmin disconnect 500 (Feb 24, 2026)** — `POST /v1/garmin/disconnect` crashed with `ForeignKeyViolation` on `activity_split`. Fixed by deleting `ActivitySplit` rows before `Activity` rows in the disconnect handler. Commit `9b11504`.
- **SEV-1: Coach stream hanging on "Thinking..." (Feb 17, 2026)** — fixed with 120s hard timeout + try/except + SSE error event in `ai_coach.py`
- **SEV-1: Home page LLM blocking all requests (Feb 17, 2026)** — fixed by splitting `generate_coach_home_briefing` into two phases: DB on request thread, LLM on worker thread via `asyncio.to_thread` + 15s `asyncio.wait_for`
- **SEV-1: `--workers 3` OOM (Feb 17, 2026)** — reverted; 1 vCPU / 2GB droplet cannot run multiple uvicorn workers

### Demo Account Safety
- `is_demo` flag on Athlete model (migration: `demo_guard_001`)
- Strava `/auth-url` and `/callback` endpoints return 403 for demo accounts
- Demo accounts use synthetic data only

---

## 9. Key Operational Procedures

### Strava Sync Troubleshooting
1. Check `AthleteIngestionState` for the athlete
2. Verify token validity: `ensure_fresh_token` may have timezone issues
3. Check Strava scopes — must include `activity:read_all`
4. If scope missing: athlete must revoke on `strava.com/settings/apps`, then reconnect ensuring checkbox is selected
5. Direct OAuth URL can be generated server-side for low-friction reconnect

### Cache Invalidation
- Stream analysis: bump `CURRENT_ANALYSIS_VERSION` in the analysis service
- Correlation cache: Redis 24h TTL, auto-expires
- Home page: `invalidateQueries({ queryKey: ['home'] })` from frontend

### Emergency Brake
- `system.ingestion_paused` DB flag prevents new ingestion work during incidents
- Workers on 429 mark as deferred (not error) with `deferred_until`

### Email Delivery Activation (Production)
1. Update `/opt/strideiq/repo/.env` (compose env file in current production setup) with:
   - `EMAIL_ENABLED=true`
   - `SMTP_SERVER=smtp.gmail.com`
   - `SMTP_PORT=587`
   - `SMTP_USERNAME=<workspace sender>`
   - `SMTP_PASSWORD=<google app password>`
   - `FROM_EMAIL=<workspace sender>`
   - `FROM_NAME=StrideIQ`
2. Recreate API service (restart alone does not reload env vars):
   - `docker compose -f docker-compose.prod.yml up -d --force-recreate api`
3. Runtime verify inside container:
   - print effective email settings (excluding password)
4. Run forgot-password E2E and verify sender branding/domain in inbox.

### Infrastructure Constraints (HARD RULES)
- **Server: Hostinger KVM 8 — 8 vCPU, 32GB RAM, 400GB NVMe.** Migrated from DigitalOcean (1 vCPU, 2GB) on Feb 25, 2026. Old droplet `104.248.212.71` kept as 24-48h safety net.
- **Uvicorn workers:** Currently 1. Safe to increase to 3-4 with 32GB RAM (each worker uses ~600MB). Increase requires founder sign-off.
- **Deploys are faster on 8 vCPU** but still cause brief downtime during `docker compose up -d --build`. Do not deploy during demo calls.
- **LLM calls MUST have hard timeouts.** Every external LLM call (Anthropic, Gemini) must have both an SDK-level timeout AND a callsite-level `asyncio.wait_for` timeout. Best practice regardless of worker count.
- **Never pass a request-scoped SQLAlchemy `db` session to `asyncio.to_thread`.** Sessions are not thread-safe. Do DB work on the request thread, pass pure data to the worker thread.
- **Home page (`/v1/home`) must never block on LLM.** If LLM times out, return `coach_briefing=None` and let deterministic data render. The page must load in <5s worst case.

---

## 10. Billing / Monetization Integration (Live)

| Item | Value |
|---|---|
| Model | 4-tier: Free / One-time $5 / Guided $15/mo ($150/yr) / Premium $25/mo ($250/yr) |
| Webhook endpoint | `https://strideiq.run/v1/billing/webhooks/stripe` |
| Core webhook events | `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted` |
| Entitlement enforcement | Canonical tier utilities + pace-access checks |
| Revenue artifact | PDF plan export gated by paid entitlement |

**Key files:**
- `apps/api/core/tier_utils.py` — canonical tier normalization/satisfaction
- `apps/api/services/stripe_service.py` — checkout, portal, webhook processing, idempotency
- `apps/api/routers/billing.py` — billing endpoints
- `apps/api/core/pace_access.py` — one-time unlock + tier entitlement checks
- `apps/api/routers/plan_export.py` and `apps/api/services/plan_pdf.py` — paid PDF export path

**Subscription flow:** Stripe webhook updates subscription mirror and athlete tier state used by gating utilities.

**ADR:** `docs/adr/ADR-055-stripe-mvp-hosted-checkout-portal-and-webhooks.md`

---

## 11. Celery Background Tasks

| Module | Purpose |
|--------|---------|
| `strava_tasks.py` | Strava sync + post-sync processing |
| `garmin_webhook_tasks.py` | Garmin activities/health webhook processing |
| `intelligence_tasks.py` | Daily intelligence + narration (every 15 min) |
| `home_briefing_tasks.py` | Home briefing generation/refresh orchestration |
| `best_effort_tasks.py` | Best effort extraction from activities |
| `import_tasks.py` | Bulk data import |
| `digest_tasks.py` | Digest generation |
| `progress_prewarm_tasks.py` | Progress endpoint/cache prewarm |
| `garmin_health_monitor_task.py` | Daily Garmin ingestion coverage monitoring |
| `runtoon_tasks.py` | On-demand Runtoon generation (triggered by share flow, not by sync) |
| `correlation_tasks.py` | Daily correlation sweep + layer enrichment |
| `fact_extraction_task.py` | Athlete fact extraction from coach chat (triggered after message save) |
| `experience_guardrail_task.py` | Daily experience guardrail (06:15 UTC via Celery beat) |
| `auto_discovery_tasks.py` | Founder-only nightly AutoDiscovery shadow pass (04:00 UTC, Phase 0B) |

---

## 12. Alembic Migration Chain

Two active heads (both valid, separate chains):
- `wellness_stamp_001` — main chain (pre-activity wellness snapshot, chains from `cross_training_003`)
- `athlete_override_001` — override chain

CI enforces head integrity via `.github/scripts/ci_alembic_heads_check.py`.
`EXPECTED_HEADS = {"wellness_stamp_001", "athlete_override_001"}`.

When adding a new migration: **must chain off one of the current heads** — update `down_revision` and `EXPECTED_HEADS` in the CI script.

---

## 13. Session Handoff Protocol

**Every session must:**
1. Read this document first to understand current state
2. Read `docs/TRAINING_PLAN_REBUILD_PLAN.md` for build priorities and gates
3. Read `docs/FOUNDER_OPERATING_CONTRACT.md` for working style expectations
4. Update this document before closing with:
   - Any new models/tables added
   - Any new services created
   - Any infrastructure changes
   - Updated counts if significant
   - New known issues discovered
   - Issues resolved

**Session handoff files** are in `docs/SESSION_HANDOFF_YYYY-MM-DD.md` — these capture session-specific details. This living audit captures cumulative system state.

---

## 14. Audit Contract (Always-Current Requirement)

This document is not a session recap. It is the founder-facing master audit.

Non-negotiable operating rules:

1. Every material ship updates this file in the same session.
2. Changes must reflect product truth (shipped behavior), not plans.
3. New route/surface/tool means inventory update here before closeout.
4. "Built but hidden/flagged" must still be listed with flag/gate status.
5. If something is uncertain, mark it as unknown explicitly (never assume).

---

## 15. Current Platform Inventory (Founder View)

### Backend/API Inventory

Current code scan snapshot (Apr 1, 2026):
- SQLAlchemy model classes in `apps/api/models.py`: **53**
- Router modules in `apps/api/routers/`: **55** files
- Service modules in `apps/api/services/`: **~120** files
- Task modules in `apps/api/tasks/`: **14** files
- API test files in `apps/api/tests/`: **175+** files
- Correlation engine input signals: **70** (expanded from 21 on Mar 10)
- Plan engine: **1,078** lines (N=1 V3, diagnosis-first)
- Plan evaluator: **852** lines (14 archetypes × 12 BCs)

### Frontend Inventory

Current code scan snapshot:
- App Router pages in `apps/web/app/**/page.tsx`: **63**
- UI/component files in `apps/web/components/**/*.tsx`: **70**
- Query hook modules in `apps/web/lib/hooks/queries/`: **21**

### User-Facing Product Surfaces (live)

- Core athlete app: `home`, `activities`, `activity detail`, `calendar`, `coach`, `progress`, `analytics` (includes absorbed trends), `training-load`, `settings` (includes absorbed profile)
- Plan surfaces: `plans/create` (includes availability scheduling), `plans/preview`, `plans/[id]`, `plans/checkout`
- Auth/account: `register`, `login`, `forgot-password`, `reset-password`, `onboarding`
- Admin surfaces: `admin`, `admin/diagnostics`
- Redirects: `insights` → `manual`, `discovery` → `manual`, `checkin` → `home`, `diagnostic` → `home`, `diagnostic/report` → `admin/diagnostics`, `profile` → `settings`, `availability` → `plans/create`, `trends` → `analytics`
- Marketing/site surfaces: `about`, `mission`, `stories`, `support`, `terms`, `privacy`

### Public Tool Surfaces (no-auth acquisition tools)

- Training pace calculator (`/tools/training-pace-calculator`)
- Age-grading calculator (`/tools/age-grading-calculator`)
- Race equivalency calculator (`/tools/race-equivalency`)
- Heat-adjusted pace (`/tools/heat-adjusted-pace`)
- Boston qualifying tools (`/tools/boston-qualifying`)

Supporting public API surface:
- `apps/api/routers/public_tools.py` provides unauthenticated calculation endpoints for pace and age-grade workflows.

### Integrations

- Strava: OAuth + webhook + sync + background ingest
- Garmin Connect: OAuth + webhook ingest (6 sports: run, cycling, walking, hiking, strength, flexibility) + GarminDay health storage + ingestion coverage monitoring
- Stripe: hosted checkout + portal + webhook entitlements for 4-tier monetization model

### Founder/Ops Tooling (live)

- Admin API surface under `apps/api/routers/admin.py` (feature flags, user ops, ingestion ops, billing ops, diagnostics, query tools)
- Garmin ingestion health endpoint: `GET /v1/admin/ops/ingestion/garmin-health`
- Daily Garmin ingestion health task: `apps/api/tasks/garmin_health_monitor_task.py`
- Home briefing reliability orchestration: `apps/api/tasks/home_briefing_tasks.py`

---

## 16. Update Checklist (must run at session close)

Before any agent marks work complete:

1. Update shipped behavior in this audit (not just handoff doc).
2. Update inventory lists if routes/tools/modules changed.
3. Move/annotate items between Active Issues and Resolved Issues.
4. Update build priority order if phase status changed.
5. Ensure this file can stand alone for founder review without reading handoffs.

---

## Appendix: Key File Paths

```
# Core
apps/api/models.py                          ← All 53 SQLAlchemy models (includes AthleteFact, ExperienceAuditLog)
apps/api/core/auth.py                       ← Auth, RBAC, JWT
apps/api/core/database.py                   ← DB session, Base

# Intelligence Pipeline
apps/api/services/daily_intelligence.py     ← 8 intelligence rules
apps/api/services/correlation_engine.py     ← N=1 correlation discovery (70 inputs, 4 aggregate functions)
apps/api/services/correlation_persistence.py ← Persistent findings + reproducibility
apps/api/services/correlation_layers.py     ← L1-L4 enrichment (threshold, asymmetry, decay, mediators)
apps/api/services/n1_insight_generator.py   ← Polarity-aware insight generation + FRIENDLY_NAMES
apps/api/services/adaptation_narrator.py    ← Gemini Flash narration + scoring
apps/api/services/experience_guardrail.py   ← 25 daily assertions across 6 categories
apps/api/services/readiness_score.py        ← Composite readiness
apps/api/tasks/intelligence_tasks.py        ← Daily intelligence orchestration
apps/api/tasks/correlation_tasks.py         ← Daily correlation sweep + layer enrichment
apps/api/tasks/fact_extraction_task.py      ← Athlete fact extraction from coach chat
apps/api/tasks/experience_guardrail_task.py ← Daily experience guardrail (06:15 UTC)

# Living Fingerprint
apps/api/services/heat_adjustment.py        ← Weather normalization (Magnus + combined value)
apps/api/services/shape_extractor.py        ← Activity shape extraction (1,331 lines pure computation)
apps/api/services/race_input_analysis.py    ← Investigation registry + 15 investigations
apps/api/services/finding_persistence.py    ← AthleteFinding persistence + supersession
apps/api/services/training_story_engine.py  ← Training story synthesis
apps/api/services/weather_backfill.py       ← Historical weather data retrieval

# Training Plans
apps/api/services/plan_framework/n1_engine.py ← N=1 Plan Engine V3 (1,078 lines, diagnosis-first)
apps/api/services/constraint_aware_planner.py ← Orchestrator (wires athlete data → engine)
apps/api/services/intake_context.py         ← Onboarding questionnaire → plan generation bridge
scripts/eval_kb_rules.py                    ← KB Rule Evaluator: 33 rules × 14 archetypes (primary gate)
scripts/eval_plan_quality.py                ← Legacy 12-BC evaluator (852 lines, secondary gate)
docs/specs/KB_RULE_REGISTRY.md              ← Rule registry (33 HARD rules from coaching KB)
docs/specs/KB_RULE_REGISTRY_ANNOTATED.md    ← Founder-annotated rule source
scripts/smoke_plan_generation.py            ← Production plan generation smoke test
docs/specs/N1_ENGINE_ADR_V2.md              ← ADR governing engine rebuild
docs/specs/LIMITER_TAXONOMY.md              ← Limiter → session type mapping (lifecycle-aware)
apps/api/services/fingerprint_bridge.py     ← Correlation findings → plan delivery modifications
apps/api/services/plan_framework/           ← Plan generation framework (supporting modules)

# Strava/Garmin Integration
apps/api/routers/strava.py                  ← OAuth + API endpoints
apps/api/services/strava_service.py         ← Strava API wrapper
apps/api/tasks/strava_tasks.py              ← Background sync
apps/api/tasks/garmin_webhook_tasks.py      ← Garmin webhook ingest workers (6-sport filter)
apps/api/services/garmin_adapter.py         ← Garmin → internal field translation (21 activity types → 6 sports)
apps/api/services/garmin_ingestion_health.py ← GarminDay coverage computation

# Progress Knowledge (v2 — current)
apps/api/routers/progress.py                ← GET /v1/progress/knowledge + /v1/progress/narrative (legacy)
apps/api/tests/test_progress_knowledge.py   ← 15 tests: shape, dedup, edge mapping, tiers, cache, hero, LLM gating
apps/api/tests/test_progress_narrative.py   ← 14 tests: legacy narrative endpoint
apps/web/app/progress/page.tsx              ← D3 correlation web + proved facts + hero
apps/web/components/progress/CorrelationWeb.tsx  ← D3 force graph with hover evidence panels
apps/web/components/progress/ProgressHero.tsx    ← Gradient header with animated CTL stats
apps/web/components/progress/WhatDataProved.tsx  ← Expandable fact list with confidence tiers
apps/web/components/progress/               ← Also: 8 legacy visual components (kept for other pages)
apps/web/lib/hooks/queries/progress.ts      ← useProgressKnowledge + useProgressNarrative hooks
docs/references/progress_page_mockup_v2_2026-03-02.html ← Design target
docs/specs/PROGRESS_NARRATIVE_SPEC_V1.md    ← Full product spec

# Runtoon (Share Your Run)
apps/api/routers/runtoon.py                 ← Runtoon API (photos, generate, pending, dismiss, shared, download)
apps/api/services/runtoon_service.py        ← Gemini image+caption generation, style anchor, 9:16 recompose
apps/api/tasks/runtoon_tasks.py             ← Celery task: on-demand generation with rich context
apps/api/services/storage_service.py        ← MinIO/S3 file ops + to_public_url (Caddy proxy rewriter)
apps/web/components/activities/RuntoonCard.tsx       ← Activity page card (CTA or image + share button)
apps/web/components/runtoon/RuntoonSharePrompt.tsx   ← Mobile bottom sheet (polls /pending)
apps/web/components/runtoon/RuntoonShareView.tsx     ← Full-screen share overlay (Web Share API)
docs/specs/RUNTOON_SHARE_FLOW_SPEC.md       ← Full product spec (all decisions finalized)

# Frontend
apps/web/app/home/page.tsx                  ← Home page
apps/web/lib/hooks/queries/home.ts          ← Home data + check-in mutation
apps/web/lib/api-client.ts                  ← API client

# Scripts (production utility)
apps/api/scripts/backfill_correlation_fingerprint.py ← Multi-window correlation backfill + bootstrap
apps/api/scripts/refresh_briefings.py       ← Targeted home briefing refresh (no FLUSHALL)
apps/api/scripts/verify_backfill.py         ← Post-backfill verification
scripts/backfill_athlete_facts.py           ← Historical fact extraction with resume

# Config & Deploy
docker-compose.yml                          ← Container orchestration
apps/api/alembic/                           ← Migration management
.github/scripts/ci_alembic_heads_check.py   ← Migration integrity CI gate

# Docs (read these first)
docs/SITE_AUDIT_LIVING.md                   ← THIS FILE
docs/TRAINING_PLAN_REBUILD_PLAN.md          ← Build plan + phase gates
docs/FOUNDER_OPERATING_CONTRACT.md          ← How to work with the founder
docs/SESSION_HANDOFF_2026-03-11_NEW_BUILDER_ONBOARDING.md ← Comprehensive new-builder onboarding
docs/ARCHITECTURE_OVERVIEW.md               ← System design principles
docs/specs/CORRELATION_ENGINE_FULL_INPUT_WIRING_SPEC.md ← 70-input correlation engine spec
docs/DATA_INTELLIGENCE_AUDIT_2026-03-10.md  ← Data blind spots audit
docs/BUILDER_INSTRUCTIONS_2026-03-10_FINGERPRINT_BACKFILL.md ← Backfill safety rules
```
