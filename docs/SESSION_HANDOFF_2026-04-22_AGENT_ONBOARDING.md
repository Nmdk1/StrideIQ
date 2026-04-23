# Agent Onboarding — April 22, 2026

**For:** New agent (any model)
**From:** Opus 4.6 (timezone migration, Kimi K2.6 upgrade, nutrition fixes)
**Production:** https://strideiq.run | Server: root@187.124.67.153

---

## HOW TO USE THIS DOCUMENT

This is your complete onboarding guide. It tells you what StrideIQ is, how the founder works, what's been built, what's in flight, and exactly which documents to read before you touch anything.

**Rule zero:** Do not start coding. Read first. Discuss first. The founder's workflow is discuss → scope → plan → test design → build. Violating this gets you terminated immediately. It has happened to multiple agents before you.

---

## MANDATORY READ ORDER

**Read ALL of 1-6 before proposing any feature or architecture. If you cannot reference specific content from these docs in your proposal, you haven't read them.**

| # | Document | What it is |
|---|----------|------------|
| 1 | `docs/FOUNDER_OPERATING_CONTRACT.md` | **How to work.** Non-negotiable. Defines the discuss→scope→plan→test→build loop, commit discipline, push rules, advisor relationship, testing schema, and every rule that keeps you alive. |
| 2 | `docs/PRODUCT_MANIFESTO.md` | **The soul.** StrideIQ gives an athlete's body a voice. 150+ intelligence tools study YOU. The product is not dashboards — it's contextual, spoken-style interpretation grounded in individual data. |
| 3 | `docs/PRODUCT_STRATEGY_2026-03-03.md` | **The moat.** Compounding athlete-specific intelligence that becomes irreplaceable over time. 16 priority-ranked product concepts. Historical data export as the acquisition hook. |
| 4 | `docs/specs/CORRELATION_ENGINE_ROADMAP.md` | **The engine.** 12-layer roadmap for the scientific instrument at the heart of the product. Layers 1-4 are built. Know what exists before proposing what to build. |
| 5 | `docs/FINGERPRINT_VISIBILITY_ROADMAP.md` | **Surface the moat.** How the built backend intelligence connects to the product strategy — what's surfaceable now, what needs more engine layers. |
| 6 | `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` | **How every screen should feel.** Visual first → interaction → wonder → narrative below. What's agreed, what's rejected — do NOT re-propose rejected decisions. |

**Context documents — read as needed for current work:**

| # | Document | What it is |
|---|----------|------------|
| 7 | `docs/wiki/index.md` | **Operational mental model.** Hub for 18 wiki pages covering every live subsystem. Authoritative for current state. |
| 8 | `docs/SITE_AUDIT_LIVING.md` | **Full product inventory.** What is shipped, delta log of recent changes. Dense but complete. |
| 9 | `docs/TRAINING_PLAN_REBUILD_PLAN.md` | **Build priority order.** Phase table, open gates, enforced contracts, 119 xfail contract tests. |
| 10 | `docs/AGENT_WORKFLOW.md` | **Build loop mechanics.** Research → test plan → tests first → implement → validate → commit. |
| 11 | `docs/RUN_SHAPE_VISION.md` | **Visual vision** for run data visualization. |
| 12 | `docs/BUILD_SPEC_HOME_AND_ACTIVITY.md` | **Active build spec** for home/activity pages (activity half partially superseded by Phase 1-4 rebuild). |
| 13 | `.cursor/rules/wiki-currency.mdc` | **Wiki currency contract.** Page-ownership map. Every behavior-changing commit must update the relevant wiki page. |

---

## WHAT THIS PRODUCT IS

StrideIQ is a running intelligence platform for competitive runners. It syncs data from Garmin (primary) and Strava, runs a correlation engine that discovers N=1 patterns in each athlete's data, and surfaces those findings through:

- **Morning briefing** — LLM-generated (Kimi K2.6) daily coaching briefing grounded in the athlete's actual data, served from Redis cache via Celery worker (Lane 2A).
- **AI Coach** — Conversational coach (Kimi K2.6) with tool-calling access to the athlete's full history via 20+ coach tools.
- **Personal Operating Manual** — Auto-generated document of the athlete's discovered physiological patterns.
- **Fingerprint** — Browsable correlation findings with confidence, thresholds, and lifecycle states.
- **Activity detail page** — CanvasV2 hero (real Mapbox GL 3D terrain) + 3 tabs (Splits / Coach / Compare), with unskippable FeedbackModal and pull-action ShareDrawer.
- **Training plans** — V1 (production default) and V2 (admin-only sandbox) plan generators.
- **Nutrition** — Photo/barcode/NL parsing, saved meals, fueling shelf, per-athlete food overrides, 60-day backlog window.
- **Strength** — In development on `strength-v1` branch (phases A-J complete, not yet merged to main).
- **Public tools** — Free SEO calculators (training pace, age grading, race equivalency, BQ times, heat adjustment).

---

## THE FOUNDER

Michael Shaffer (`mbshaf@gmail.com`) is the primary user and a competitive runner. His father (Adam Stewart, referred to as "BHL") is also an active user. Both are primarily desktop users; many athletes are mobile-first.

**How the founder works:**
- Expects discussion before code. Always.
- Has an advisor agent for architectural decisions and design review.
- Gives direct, sometimes blunt feedback. "If I was an athlete and saw this tab I would never open it again" is a real quote.
- Cares deeply about coaching quality — template/hallucinated language is unacceptable.
- Tests in production with real athletes. Never break production.
- Reviews diffs carefully. Claims about what changed must match reality.
- Will terminate agents who build without understanding.

---

## TECH STACK

### Backend (Python/FastAPI)
- **Framework:** FastAPI with SQLAlchemy ORM, Alembic migrations
- **Database:** PostgreSQL (container: `strideiq_postgres`)
- **Cache:** Redis (container: `strideiq_redis`)
- **Object storage:** MinIO (container: `strideiq_minio`)
- **Task queue:** Celery with Redis broker (containers: `strideiq_worker`, `strideiq_beat`, `strideiq_worker_default`)
- **LLM:** Kimi K2.6 (primary), fallback chain: K2.6 → Claude Sonnet 4 → Gemini 2.5 Flash
- **LLM client:** `core/llm_client.py` — centralized abstraction, all non-tool-call completions route through `call_llm()`
- **API container:** `strideiq_api`

### Frontend (Next.js/React)
- **Framework:** Next.js 14.2 with TypeScript
- **Styling:** Tailwind CSS + shadcn/ui components
- **State:** React Query (TanStack Query) for server state
- **Charts:** Custom SVG + Mapbox GL for maps
- **Container:** `strideiq_web`

### Infrastructure
- **Server:** Hostinger KVM 8 (8 vCPU, 32GB RAM) at `root@187.124.67.153`
- **Proxy:** Caddy (container: `strideiq_caddy`) — auto-HTTPS for strideiq.run
- **CI:** GitHub Actions on push to main
- **Deploy:** `cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build`

### Key directories
```
apps/api/                  # Backend
  core/                    # Config, security, LLM client, cache, feature flags
  models/                  # SQLAlchemy models (split from monolith into package)
  routers/                 # FastAPI route handlers
  services/                # Business logic
    coaching/              # AI Coach (decomposed from monolithic ai_coach.py)
    coach_tools/           # 20+ tools the coach can call
    intelligence/          # Correlation engine, N1 insights, narratives
    sync/                  # Garmin adapter, Strava sync, duplicate scanner
    timezone_utils.py      # Canonical timezone handling
  tasks/                   # Celery tasks (briefing, Garmin webhooks, etc.)
  tests/                   # pytest test suite
  migrations/              # Alembic migration chain

apps/web/                  # Frontend
  app/                     # Next.js pages (home, coach, calendar, nutrition, etc.)
  components/              # React components
  lib/                     # API services, hooks, contexts, utilities
    utils/date.ts          # localToday() — use this, not toISOString()
```

---

## CURRENT STATE (April 22, 2026)

### Recent deployments (this session)
1. **Timezone migration** — All `date.today()` and `.start_time.date()` across routers/services replaced with athlete-local timezone. Travel-aware via GPS coordinates + `TimezoneFinder`. Frontend `localToday()` utility replaces UTC `toISOString().split('T')[0]`.
2. **Kimi K2.6 upgrade** — All LLM calls upgraded from K2.5 to K2.6. Better instruction compliance, same API contract.
3. **Nutrition meal logging fix** — Meals tab was sending stale `selectedDate` instead of `entryDate`, causing logged meals to not appear in Today's Log.
4. **Briefing cache timezone fix** — Celery fingerprint used server `date.today()` instead of athlete-local, causing cache to flip at wrong boundary for evening users.

### Active branches
- `main` — Production. All deploys come from here.
- `strength-v1` — Strength training feature (phases A-J). Do NOT put non-strength work here.

### Test suite
- Backend: ~3600 tests passing in CI (PostgreSQL + full migration chain)
- Frontend: Jest tests for contracts, marketing claims, unit-bypass assertions
- CI is the source of truth. If CI is green, the code is correct.

### Known issues / tech debt
- Imperial-baked API field names (`distance_mi`, `pace_per_mile`) — frontend must convert. Every new surface that forgets is a unit-bug landmine.
- Compare tab is a placeholder — redesign spec exists at `docs/specs/COMPARE_REDESIGN.md`, sequenced behind canvas vocabulary redesign.
- 119 xfail contract tests for Phases 3B, 3C, Phase 4, and Monetization — these become real tests when gates clear.

---

## WIKI PAGES (operational reference)

Read the wiki page for any subsystem you're about to modify. The wiki is authoritative for what is live.

| Wiki page | Covers |
|-----------|--------|
| `docs/wiki/index.md` | Start here. Quick reference + maintenance contract. |
| `docs/wiki/briefing-system.md` | Morning briefing, Lane 2A cache, voice quality gates |
| `docs/wiki/coach-architecture.md` | AI Coach routing, tools, prompts, guardrails |
| `docs/wiki/correlation-engine.md` | Correlation layers, AutoDiscovery, fingerprint |
| `docs/wiki/activity-processing.md` | Activity pipeline, canvas, splits, maps, share |
| `docs/wiki/garmin-integration.md` | Garmin webhooks, FIT pipeline, OAuth, demo guards |
| `docs/wiki/frontend.md` | Routes, components, contexts, data layer |
| `docs/wiki/infrastructure.md` | Server, containers, Celery, DB, CI, env vars |
| `docs/wiki/plan-engine.md` | Plan engine V1/V2, constraint-aware generation |
| `docs/wiki/nutrition.md` | Nutrition parsing, overrides, saved meals |
| `docs/wiki/monetization.md` | Stripe, tiers, pricing |
| `docs/wiki/quality-trust.md` | Trust principles, KB registry, OutputMetricMeta |
| `docs/wiki/operating-manual.md` | Personal Operating Manual, findings, cascades |
| `docs/wiki/decisions.md` | ADR-style architectural decisions |
| `docs/wiki/reports.md` | Cross-domain reports |
| `docs/wiki/telemetry.md` | Page views, admin usage reports |
| `docs/wiki/log.md` | Chronological record of what shipped |
| `docs/wiki/product-vision.md` | Vision and competitive frame |

---

## CRITICAL CONTRACTS

### Athlete Trust Safety Contract
Efficiency is ambiguous (higher could mean fitter OR less effort). The system uses **neutral directional language only** for efficiency metrics. Never say "improving" or "declining" — say "trending higher" or "trending lower." See `n1_insight_generator.py`.

### No `git push` without founder approval
Local commits are expected. Pushing to `origin` requires explicit founder sign-off. The founder may say "push" or "deploy" — until then, keep work local.

### No new OAuth/API scopes without approval
Specs may describe future scopes. Code waits for sign-off.

### Wiki currency
Every commit that changes behavior must update the relevant wiki page in the same commit or follow-up. See `.cursor/rules/wiki-currency.mdc` for the page-ownership map.

### Scoped commits only
Never `git add -A`. Show `git diff --name-only --cached` before committing.

### CI first, local second
Always check CI (`gh run list` / `gh run view`) before debugging locally. CI has Postgres and the full migration chain.

---

## DEPLOY PROCEDURE

```bash
# SSH to production
ssh root@187.124.67.153

# Pull and rebuild
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build

# Check logs
docker logs strideiq_api --tail=50
docker logs strideiq_web --tail=50
```

### Container names
| Service | Container |
|---------|-----------|
| API | strideiq_api |
| Web | strideiq_web |
| Worker | strideiq_worker |
| Beat | strideiq_beat |
| DB | strideiq_postgres |
| Cache | strideiq_redis |
| Proxy | strideiq_caddy |
| Storage | strideiq_minio |

---

## SPECS LIBRARY (forward-looking)

66 spec files in `docs/specs/`. Key ones to know:

| Spec | What it defines |
|------|-----------------|
| `INTELLIGENCE_VOICE_SPEC.md` | Intelligence voice layer — how data speaks to athletes |
| `CORRELATION_ENGINE_ROADMAP.md` | 12-layer engine roadmap |
| `STRENGTH_V1_SCOPE.md` | Strength training feature scope (active on strength-v1 branch) |
| `COMPARE_REDESIGN.md` | Activity comparison tab redesign (sequenced behind canvas) |
| `PLAN_GENERATOR_ALGORITHM_SPEC.md` | Plan generation algorithm |
| `EFFORT_CLASSIFICATION_SPEC.md` | Effort classification system |
| `LIVING_FINGERPRINT_SPEC.md` | Living fingerprint feature |
| `MONETIZATION_RESET_SPEC.md` | Monetization tier structure |
| `PERSONAL_COACH_TIER_SPEC.md` | Personal coach tier |
| `NATIVE_APP_SPEC.md` | Native mobile app spec |
| `AUDIO_COACHING_SPEC.md` | Audio coaching feature |

---

## QUICK REFERENCE

- **Founder email:** mbshaf@gmail.com
- **Production URL:** https://strideiq.run
- **Server:** root@187.124.67.153
- **Primary LLM:** Kimi K2.6 (api.moonshot.ai/v1)
- **Fallback chain:** K2.6 → Claude Sonnet 4 → Gemini 2.5 Flash
- **Default branch:** main
- **Feature branch:** strength-v1 (strength only)
- **CI:** GitHub Actions — check with `gh run list --branch main --limit 1`
- **Key utility:** `services/timezone_utils.py` — always use for date/timezone operations
- **Frontend date utility:** `lib/utils/date.ts` — always use `localToday()`, never `toISOString().split('T')[0]`
