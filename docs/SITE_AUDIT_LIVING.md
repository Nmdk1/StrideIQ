# StrideIQ — Living Site Audit

**Purpose:** Canonical full-product audit. This is the always-current inventory of what exists on the site, what is shipped, and what operational tools are available.
**Last updated:** March 3, 2026
**Last updated by:** Builder session — N=1 Effort Classification shipped

---

## 0. Delta Since Last Audit (Feb 25 -> Mar 1)

Shipped and now live in product/system behavior:

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
| **Workers** | Celery | `apps/api/tasks/` (7 task modules — includes `runtoon_tasks.py`) |
| **Object Storage** | MinIO (S3-compatible) | Docker: `strideiq_minio`, private bucket `strideiq-runtoon` |
| **Cache/Queue** | Redis 7 Alpine | Celery broker + response cache |
| **Proxy** | Caddy 2 | Auto-TLS, reverse proxy |
| **CI** | GitHub Actions | `.github/workflows/` |
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

## 2. Codebase Scale (as of 2026-02-16 snapshot; recount pending)

| Metric | Count |
|--------|-------|
| SQLAlchemy models | 57 |
| FastAPI routers | 53 |
| Python services | 137 |
| Celery task modules | 7 (includes `runtoon_tasks.py`) |
| Test files | 144 |
| Alembic migrations | 66 |
| React pages | 43 |
| React components | 59 |
| TanStack Query hooks | 20 |
| Intelligence rules | 8 |

---

## 3. Core Data Models (57 tables)

### Athlete & Auth
- `Athlete` — core user record, includes `is_demo` flag (demo accounts cannot link Strava)
- `InviteAllowlist` — gated signup
- `Subscription`, `StripeEvent`, `Purchase`, `RacePromoCode` — payments/entitlements

### Activity & Performance
- `Activity` — ingested runs from Strava/Garmin
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
- `CoachChat` — conversation history
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

Discovers N=1 correlations between inputs (check-in data, training load, body composition) and outputs (efficiency, pace, completion rate).

- **Statistical gates:** p < 0.05, |r| >= 0.3, n >= 10
- **Time-shifted:** 0–7 day lags (catches "bad sleep → performance drops 2 days later")
- **Output metrics:** efficiency, pace_easy, pace_threshold, completion, efficiency by zone, PB events, race pace
- **Bonferroni correction** applied in N1 insight generator

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

### Readiness Score (`services/readiness_score.py`)

Phase 2A. Composite score from efficiency trend, recovery balance, completion rate, recovery days.
- Sleep currently **excluded** from readiness until correlation engine proves individual relationship (per rebuild plan)

---

## 5. Check-in Data Flow (End-to-End)

This is the full lifecycle of check-in data:

```
Athlete → Home Page Quick Check-in (or /checkin page)
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
| `/home` | Morning command center: run shape + compact PMC (visual pair), coach briefing, workout, check-in, race countdown | Working — compact PMC added Mar 1, moved to pos 2 |
| `/activities` | Activity list with mini charts | Working |
| `/activities/[id]` | Activity detail: Run Shape Canvas, Runtoon (above the fold), splits, analysis | Working — needs narrative moments |
| `/calendar` | Training calendar with plan overlay | Working |
| `/coach` | AI coach chat interface | Strongest surface in the product |
| `/progress` | D3 force-directed correlation web, expandable proved facts, coach-voice hero — replaces old card grid | Working |
| `/analytics` | Efficiency trends, correlations, load→response | Working |
| `/training-load` | PMC chart, N=1 zones, daily stress | Working |
| `/discovery` | What works / what doesn't (correlation insights) | Working |
| `/checkin` | Full check-in form (sliders) | Working |
| `/settings` | Strava/Garmin integration, preferences | Working |
| `/tools` | Pace calculator, age grading, heat adjustment | Working |
| `/nutrition` | Quick nutrition logging | Minimal/placeholder |
| `/insights` | Insight feed | Needs deduplication (noisy) |

### Data Fetching

TanStack Query (React Query) with 20 custom hooks in `apps/web/lib/hooks/queries/`.
API client at `apps/web/lib/api-client.ts`.

---

## 7. Build Priority & Phase Status

From `docs/TRAINING_PLAN_REBUILD_PLAN.md`:

| Phase | Status | Tests |
|-------|--------|-------|
| Phase 1 (Plans) | COMPLETE | 158 passing |
| Phase 2 (Adaptation) | COMPLETE | 29 passing |
| Phase 3A (Narration) | COMPLETE | 66 passing |
| Coach Trust | COMPLETE | 22 passing |
| Phase 3B (Workout Narratives) | CODE COMPLETE — gate accruing | 65+ passing, 24 xfail |
| Phase 3C (N=1 Insights) | CODE COMPLETE — gate accruing | 65+ passing, 26 xfail |
| Phase 4 (50K Ultra) | CONTRACT ONLY | 37 xfail |
| Monetization Tiers | v1 COMPLETE (core revenue surfaces shipped) | residual xfails remain for deferred advisory/intelligence tier contracts |

**Build priority order (current):**
1. Phase 4 (50K Ultra)
2. Phase 3B (when narration quality gate clears — >90% for 4 weeks)
3. Phase 3C (when per-athlete synced history + significant correlations exist)
4. Monetization deferred contracts (promote remaining xfails only as underlying features land)

**Open gates:**
- 3B: narration accuracy > 90% for 4 weeks (`/v1/intelligence/narration/quality`)
- 3C: per-athlete synced history + significant correlations (founder rule: immediate if history exists)

**119 xfail contract tests** become real tests when gates clear.

---

## 8. Known Issues & Technical Debt

### Active Issues
- **Garmin production-access process still pending final completion** — evaluation environment is active; endpoint compliance and submission package are in progress with Partner Services.
- **Garmin physiology coverage is underfed for connected athletes** — monitor now exists (`/v1/admin/ops/ingestion/garmin-health`) and currently indicates sparse sleep/HRV population for some athletes.
- ~~**Email deliverability wiring remains operationally sensitive**~~ — **RESOLVED (Feb 28, 2026).** Production email is live: `smtp.gmail.com:587`, sender `noreply@strideiq.run` via `michael@strideiq.run`. Password reset E2E verified by Codex. DNS hardening (SPF/DKIM/DMARC) still needed at Porkbun.
- **Coach has no Garmin Health API data in context (Mar 2, 2026):** `build_context()` in `ai_coach.py` only queries `DailyCheckin` (athlete self-report). It never queries `GarminDay` — Garmin watch-measured sleep, HRV, stress, resting HR are invisible to the coach. When asked about watch data, coach returns only Activity API metrics. This blocks Garmin partner compliance screenshots (Marc Lussi requested Health API evidence). Builder note: `docs/BUILDER_NOTE_2026-03-02_COACH_QUALITY.md`.
- **Coach hallucinations (Mar 2, 2026):** Coach referenced shin soreness that doesn't exist (check-in = None), a 15-mile Saturday run (actual = 10), and "cutting runs short this week" on Monday morning before any runs. Builder note tracks this.
- **Home briefing `coach_noticed` staleness (Mar 2, 2026):** Same "efficiency improved 4.4%" insight repeated for 4 days despite significant new training. No insight rotation or cooldown mechanism. Builder note tracks this.
- **Coach context distances in km (cosmetic):** `build_context()` internally formats distances in km before passing to LLM. Coach output is in miles (LLM converts), but feeding km into prompt risks occasional km in responses.
- **Insights feed noise:** `/insights` Active Insights section has duplicate volume alerts and low-quality achievement cards — needs deduplication and quality filter
- **Activity detail moments:** some key moments still show raw metrics that need stronger narrative translation
- **Home page dual voice:** `compute_coach_noticed` and `morning_voice` still overlap; unify into one coherent briefing voice

### Technical Debt (Tracked, Not Blocking)
- 8 services with local efficiency polarity assumptions — migrate to `OutputMetricMeta` registry
- Timezone-aware vs naive datetime comparisons in `ensure_fresh_token` (observed during Danny's Strava debug)
- Sleep weight = 0.00 in readiness score — excluded until correlation engine proves individual relationship

### Resolved Issues
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

---

## 12. Alembic Migration Chain

Current head: `runtoon_002` (chains off `runtoon_001` ← `corr_persist_001` ← `demo_guard_001` ← ...)

CI enforces single-head integrity via `.github/scripts/ci_alembic_heads_check.py`.
Max 2 roots allowed (main chain + phase chain).

When adding a new migration: **must chain off the current head** — update `down_revision` and `EXPECTED_HEADS` in the CI script.

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

Current code scan snapshot:
- SQLAlchemy model classes in `apps/api/models.py`: **60**
- Router modules in `apps/api/routers/`: **61** files
- Service modules in `apps/api/services/`: **152** files
- Task modules in `apps/api/tasks/`: **14** files
- API test files in `apps/api/tests/`: **176** files

### Frontend Inventory

Current code scan snapshot:
- App Router pages in `apps/web/app/**/page.tsx`: **63**
- UI/component files in `apps/web/components/**/*.tsx`: **70**
- Query hook modules in `apps/web/lib/hooks/queries/`: **21**

### User-Facing Product Surfaces (live)

- Core athlete app: `home`, `activities`, `activity detail`, `calendar`, `coach`, `progress`, `analytics`, `training-load`, `discovery`, `insights`, `settings`
- Plan surfaces: `plans/create`, `plans/preview`, `plans/[id]`, `plans/checkout`
- Auth/account: `register`, `login`, `forgot-password`, `reset-password`, `onboarding`, `profile`
- Admin/diagnostic surfaces: `admin`, `admin/diagnostics`, `diagnostic`, `diagnostic/report`
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
- Garmin Connect: OAuth + webhook ingest + GarminDay health storage + ingestion coverage monitoring
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
apps/api/models.py                          ← All 57 SQLAlchemy models
apps/api/core/auth.py                       ← Auth, RBAC, JWT
apps/api/core/database.py                   ← DB session, Base

# Intelligence Pipeline
apps/api/services/daily_intelligence.py     ← 8 intelligence rules
apps/api/services/correlation_engine.py     ← N=1 correlation discovery
apps/api/services/correlation_persistence.py ← Persistent findings + reproducibility
apps/api/services/n1_insight_generator.py   ← Polarity-aware insight generation
apps/api/services/adaptation_narrator.py    ← Gemini Flash narration + scoring
apps/api/services/readiness_score.py        ← Composite readiness
apps/api/tasks/intelligence_tasks.py        ← Daily intelligence orchestration

# Training Plans
apps/api/services/plan_framework/           ← Plan generation framework

# Strava/Garmin Integration
apps/api/routers/strava.py                  ← OAuth + API endpoints
apps/api/services/strava_service.py         ← Strava API wrapper
apps/api/tasks/strava_tasks.py              ← Background sync
apps/api/tasks/garmin_webhook_tasks.py      ← Garmin webhook ingest workers
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

# Config & Deploy
docker-compose.yml                          ← Container orchestration
apps/api/alembic/                           ← Migration management
.github/scripts/ci_alembic_heads_check.py   ← Migration integrity CI gate

# Docs (read these first)
docs/SITE_AUDIT_LIVING.md                   ← THIS FILE
docs/TRAINING_PLAN_REBUILD_PLAN.md          ← Build plan + phase gates
docs/FOUNDER_OPERATING_CONTRACT.md          ← How to work with the founder
docs/ARCHITECTURE_OVERVIEW.md               ← System design principles
```
