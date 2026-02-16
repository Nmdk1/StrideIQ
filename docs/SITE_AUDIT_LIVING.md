# StrideIQ — Living Site Audit

**Purpose:** Single source of truth for every new builder session. Updated every session.
**Last updated:** February 16, 2026
**Last updated by:** Builder session that shipped correlation persistence + check-in optimistic UI

---

## 1. Infrastructure & Deployment

| Component | Technology | Location |
|-----------|-----------|----------|
| **Web** | Next.js 14 (App Router) | `apps/web/` |
| **API** | FastAPI (Python 3.11) | `apps/api/` |
| **Database** | TimescaleDB (PostgreSQL 16) | Docker: `timescale/timescaledb:latest-pg16` |
| **Workers** | Celery | `apps/api/tasks/` (6 task modules) |
| **Cache/Queue** | Redis 7 Alpine | Celery broker + response cache |
| **Proxy** | Caddy 2 | Auto-TLS, reverse proxy |
| **CI** | GitHub Actions | `.github/workflows/` |
| **Production** | DigitalOcean Droplet (1 vCPU, 2GB) | `104.248.212.71` |
| **Domain** | `strideiq.run` / `www.strideiq.run` / `api.strideiq.run` | Caddy routes |
| **Repo** | `github.com/Nmdk1/StrideIQ` | Single `main` branch |

### Production Layout

```
/opt/strideiq/repo/          ← Git checkout
docker compose up -d         ← 6 containers: api, web, caddy, postgres, redis, worker
API runs migrations on boot  ← alembic upgrade head in entrypoint
```

### Deployment Workflow

```
local: git push origin main
droplet: cd /opt/strideiq/repo && git pull origin main && docker compose up -d --build
```

Migration runs automatically on API container startup. Manual migration: `docker compose exec api alembic upgrade head`.

---

## 2. Codebase Scale (as of 2026-02-16)

| Metric | Count |
|--------|-------|
| SQLAlchemy models | 57 |
| FastAPI routers | 53 |
| Python services | 137 |
| Celery task modules | 6 |
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
| `/home` | Morning command center: coach briefing, workout, check-in, race countdown | Working — optimistic check-in fix shipped 2/16 |
| `/activities` | Activity list with mini charts | Working |
| `/activities/[id]` | Activity detail: Run Shape Canvas, splits, analysis | Working — needs narrative moments |
| `/calendar` | Training calendar with plan overlay | Working |
| `/coach` | AI coach chat interface | Strongest surface in the product |
| `/progress` | Race readiness, predictions, pace zones, PBs | Working |
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
| Monetization Tiers | CONTRACT ONLY | 29 xfail |

**Build priority order:**
1. Monetization tier mapping (revenue unlock)
2. Phase 4 (50K Ultra)
3. Phase 3B (when narration quality gate clears — >90% for 4 weeks)
4. Phase 3C (when per-athlete synced history + significant correlations exist)

**Open gates:**
- 3B: narration accuracy > 90% for 4 weeks (`/v1/intelligence/narration/quality`)
- 3C: per-athlete synced history + significant correlations (founder rule: immediate if history exists)

**119 xfail contract tests** become real tests when gates clear.

---

## 8. Known Issues & Technical Debt

### Active Issues
- **GitHub Actions billing:** CI runs failing due to payment issue — not a code problem, needs billing fix in GitHub Settings > Billing & plans
- **Insights feed noise:** `/insights` Active Insights section has duplicate volume alerts and low-quality achievement cards — needs deduplication and quality filter
- **Activity detail moments:** Key Moments show raw numbers ("Grade Adjusted Anomaly: 4.7") — need narrative translation
- **Home page dual voice:** `compute_coach_noticed` and `morning_voice` are separate systems producing overlapping content — should be merged into single synthesis

### Technical Debt (Tracked, Not Blocking)
- 8 services with local efficiency polarity assumptions — migrate to `OutputMetricMeta` registry
- Timezone-aware vs naive datetime comparisons in `ensure_fresh_token` (observed during Danny's Strava debug)
- Sleep weight = 0.00 in readiness score — excluded until correlation engine proves individual relationship

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

---

## 10. Celery Background Tasks

| Module | Purpose |
|--------|---------|
| `strava_tasks.py` | Strava activity sync, token refresh |
| `intelligence_tasks.py` | Daily intelligence + narration (every 15 min) |
| `best_effort_tasks.py` | Best effort extraction from activities |
| `import_tasks.py` | Bulk data import |
| `digest_tasks.py` | Digest generation |
| `garmin_tasks.py` | Garmin data import |

---

## 11. Alembic Migration Chain

Current head: `corr_persist_001` (chains off `demo_guard_001` ← `sleep_quality_001` ← `rsi_cache_001` ← ...)

CI enforces single-head integrity via `.github/scripts/ci_alembic_heads_check.py`.
Max 2 roots allowed (main chain + phase chain).

When adding a new migration: **must chain off the current head** — update `down_revision` and `EXPECTED_HEADS` in the CI script.

---

## 12. Session Handoff Protocol

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
