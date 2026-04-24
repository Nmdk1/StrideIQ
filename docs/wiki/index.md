# StrideIQ Internal Wiki

**Last updated:** April 24, 2026 (Apr 24: timezone two-model + home/effective split; nutrition autofill prevention; briefing clock time removed from LLM prompt; coach trust foundation slice; conversation contract enforcement; N=1 coaching memory; Race Strategist Mode foundation; Coach Value Eval Harness; Frontend Trust UX foundation)

This is the single onboarding document. Read this instead of the 12-document read order.

> **Wiki currency is mandatory** — `.cursor/rules/wiki-currency.mdc` and the
> Founder Operating Contract treat a stale wiki as a trust failure, not a
> documentation gap. Every behavior-changing commit owes a wiki edit in the
> same commit (or a follow-up commit in the same session). Bump the
> `Last updated:` date above whenever any wiki page is edited.

## Quick Reference

| Item | Value |
|------|-------|
| **Server** | `187.124.67.153` (Hostinger KVM 8, 8 vCPU, 32GB RAM) |
| **Domain** | `strideiq.run` |
| **Repo** | `github.com/Nmdk1/StrideIQ` |
| **Founder ID** | `4368ec7f-c30d-45ff-a6ee-58db7716be24` |
| **Founder env** | `OWNER_ATHLETE_ID` — bypasses all caps |
| **API container** | `strideiq_api` |
| **Worker containers** | `strideiq_worker`, `strideiq_worker_default` |
| **Beat container** | `strideiq_beat` |
| **Coach model** | **Kimi** primary: `COACH_CANARY_MODEL` (default `kimi-k2.6` in `apps/api/core/config.py`), OpenAI-compatible Moonshot API in `services/coaching/_llm.py` `query_kimi_coach`. **Claude Sonnet 4.6** silent fallback on Kimi errors. Gemini is not primary, but remains a turn-guard retry fallback when Anthropic is unavailable. |
| **Briefing model** | Default **`BRIEFING_PRIMARY_MODEL`** = `claude-sonnet-4-6`. Optional **Kimi** for athletes listed when `KIMI_CANARY_ENABLED` + `KIMI_CANARY_ATHLETE_IDS` (model `KIMI_CANARY_MODEL`, default `kimi-k2.6`). Provider routing + **Sonnet → Gemini 2.5 Flash** fallback chain in `apps/api/core/llm_client.py` (`call_llm` / `call_llm_with_json_parse`). |
| **Plan engine (V1)** | `services/plan_framework/n1_engine.py` |
| **Plan engine (V2)** | `services/plan_engine_v2/engine.py` — active behind `engine=v2` flag, admin/owner only |
| **Deploy** | `ssh root@187.124.67.153` then `cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build` |
| **CI** | Must be green before deploy. `gh run list` to check. |

## Start Here

Before writing any code, understand these five things:

1. **[Quality & Trust Principles](./quality-trust.md)** — the five non-negotiable rules. N=1 only. Suppression over hallucination. The athlete decides. No threshold is universal. Never hide numbers. Violating these is the fastest way to lose the founder's trust.

2. **[Product Vision](./product-vision.md)** — what StrideIQ is and why. The intelligence moat. The visual → narrative → fluency loop. The founder is a BQ runner who coaches state-record holders. The bar is extremely high.

3. **[Coach Architecture](./coach-architecture.md)** — the most-used surface. Universal Kimi coach path + Sonnet fallback. Context builders. Anti-hallucination guardrails. Budget caps. Date rendering discipline.

4. **[Briefing System](./briefing-system.md)** — the most fragile surface. Lane 2A architecture. 8+ intelligence sources. Repeated regressions. **Approach with extreme caution.**

5. **[Infrastructure](./infrastructure.md)** — how to deploy, container names, beat startup dispatch pattern (daily tasks won't fire without it), database, CI pipeline.

## All Pages

| Page | What it covers |
|------|---------------|
| **[Quality & Trust Principles](./quality-trust.md)** | Five non-negotiable rules, KB registry, anti-hallucination, OutputMetricMeta, coach guardrails |
| **[Product Vision](./product-vision.md)** | Manifesto, strategy, 16 priority-ranked concepts, design philosophy, competitive frame, founder context |
| **[Coach Architecture](./coach-architecture.md)** | AI coach system — Kimi primary (`COACH_CANARY_MODEL`), Sonnet fallback, context injection, search/activity tools, conversation contracts, KB scanner, budget caps |
| **[Briefing System](./briefing-system.md)** | Morning briefing — Lane 2A, prompt assembly, 8 intelligence sources, workout structure detection, guardrails |
| **[Correlation Engine](./correlation-engine.md)** | N=1 intelligence pipeline — Layers 1-4, AutoDiscovery, finding lifecycle, limiter taxonomy, cross-training inputs, fingerprint bridge |
| **[Plan Engine](./plan-engine.md)** | V1 (N1 Engine V3) + **V2 deployed** — V2 wired to production behind `engine=v2` flag, 13 coaching science KB docs, extension-based progression, rich segments, fueling |
| **[Garmin Integration](./garmin-integration.md)** | Three webhook types, FIT file pipeline, weather enrichment (Open-Meteo), health API, accepted sports |
| **[Activity Processing](./activity-processing.md)** | Shape extraction, effort classification, heat adjustment, run maps (**CanvasV2** / Mapbox GL), Leaflet on some cross-training surfaces, Runtoons, activity detail tabs |
| **[Operating Manual](./operating-manual.md)** | Personal Operating Manual V2 — findings display, cascade chains, race character, interestingness filter |
| **[Infrastructure](./infrastructure.md)** | Server, containers, deployment, Celery/Beat, database, CI, environment variables |
| **[Monetization](./monetization.md)** | Two-tier model ($24.99/mo), Stripe integration, promo codes |
| **[Frontend](./frontend.md)** | Next.js 14 routes, component architecture, data layer (TanStack Query), contexts |
| **[Nutrition](./nutrition.md)** | AI Nutrition Intelligence — photo/barcode/NL parsing, fueling shelf, nutrition planning, load-adaptive targets, first-class metric (#3 in hierarchy) |
| **[Usage Telemetry](./telemetry.md)** | First-party page view tracking — PageView model, tracking hook, admin usage reports |
| **[Unified Reports](./reports.md)** | Cross-domain reporting — health, activities, nutrition, body comp in configurable date ranges |
| **[Units System](./units.md)** | Canonical units contract — API ships meters/seconds, `useUnits()` hook, `CoachUnits` backend helper, country-aware defaults |
| **[Decisions](./decisions.md)** | 56 ADRs summarized — key architectural choices and their current state |

## Maintenance Contract (binding)

Every code change that affects system behavior, surfaces, contracts, models,
deploy posture, env vars, or routes **must** include a wiki update — in the
same commit or a follow-up commit in the same session. This is enforced by
`.cursor/rules/wiki-currency.mdc` and rule 13 of the Founder Operating
Contract. Same standard as tests.

A wiki update should:

1. Reflect the **shipped** state, not the proposed state. (Specs live in `docs/specs/`.)
2. Be specific enough that another agent reading only the wiki could rebuild
   the same mental model the founder has.
3. Remove or move stale content rather than letting it pile up. The wiki is
   not append-only.
4. Link source files (path-only) where the behavior actually lives.

Always bump the `Last updated:` date at the top of this file. For
cross-cutting changes that don't fit one page cleanly, append a dated entry
to [`log.md`](./log.md).

## Project Structure (April 2026 Reorganization)

### Backend (`apps/api/`)

```
models/                     # ORM models split by domain
  __init__.py               # Re-exports all 87 models for backward compat
  athlete.py                # Athlete, goals, overrides, calibration, photos
  activity.py               # Activity, splits, streams, PBs, best efforts
  plan.py                   # TrainingPlan, PlannedWorkout, templates, calendar
  checkin.py                # DailyCheckin, body comp, readiness, work pattern
  nutrition.py              # Nutrition goals/entries, fueling products
  coaching.py               # CoachChat, recommendations, intent snapshots
  correlation.py            # Findings, auto-discovery, narration logs
  system.py                 # Billing, invites, ingestion state, telemetry

services/
  sync/                     # Strava, Garmin, dedup, backfill (16 files)
  intelligence/             # Correlation engine, attribution, narration, n1 insights (16 files)
  plan_framework/           # Plan generation engine (V1)
  plan_engine_v2/           # Plan generation engine (V2)
  auto_discovery/           # Correlation auto-discovery pipeline
  coaching/                 # AI coach split into mixins + core (was ai_coach.py god file)
                            #   core.py (AICoach class), _context.py, _llm.py, _thread.py,
                            #   _tools.py, _budget.py, _guardrails.py, _prescriptions.py,
                            #   _constants.py, __init__.py
  coach_tools/              # Coach tool functions split by concern (was coach_tools.py god file)
                            #   brief.py, insights.py, activity.py, wellness.py,
                            #   performance.py, plan.py, profile.py, load.py, _utils.py
  ai_coach.py               # 5-line backward-compat shim → services/coaching
                            # (legacy import path `from services.ai_coach import AICoach` still works)
  [other services]          # Analysis, shape, email, stripe, etc.

data/
  workout_variants/         # Workout registry JSON + pilot markdowns
  *.xlsx                    # Performance standards data
```

### Documentation (`docs/`)

```
docs/
  FOUNDER_OPERATING_CONTRACT.md   # How agents work with the founder
  PRODUCT_MANIFESTO.md            # Product soul
  PRODUCT_STRATEGY_2026-03-03.md  # 16-concept moat
  TRAINING_PLAN_REBUILD_PLAN.md   # Build plan north star
  SITE_AUDIT_LIVING.md            # Current state inventory
  wiki/                           # Synthesized system docs (this wiki)
  specs/                          # Detailed specifications
  references/                     # Coaching science references
  adr/                            # Architecture decision records
  archive/                        # Historical builder instructions, handoffs, notes
```

### Backward Compatibility

All service files moved to `services/sync/` or `services/intelligence/` have **shim files** at their old paths that redirect imports transparently. Existing `from services.strava_service import X` continues to work. These shims can be removed once all imports are updated to the new paths.

## What This Wiki Is Not

- **Not a replacement for source docs.** The `docs/` folder is immutable raw source material. The wiki synthesizes it.
- **Not a spec.** Use `docs/specs/` for detailed specifications. The wiki summarizes current state.
- **Not a session log.** Use `docs/SESSION_HANDOFF_*.md` for session-specific context. The wiki is timeless.
