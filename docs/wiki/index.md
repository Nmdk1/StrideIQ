# StrideIQ Internal Wiki

**Last updated:** April 28, 2026 (Apr 28: Coach Runtime V2 emergency stabilization keeps structured grounding/fail-closed behavior but moves intent, unknowns, and conversation mode back backstage: volume questions no longer force weekly-mileage/block-phase prompts, direct nutrition-only compaction is limited to pure current-log lookups, named weekday nutrition windows such as "Monday and today" are supported, multi-domain nutrition/training/lifting/recovery prompts keep full context, additional internal labels are blocked/cleaned, and `/coach` no longer renders conversation-contract badges; Coach Runtime V2 is now site-wide by resolver contract, so no real athlete chat can be blocked by founder-only `coach.runtime_v2.visible` flag drift or receive a “V2 not enabled for this account” response; Weekly digest now uses shared eligible persisted findings instead of raw 90-day correlation scans, suppresses sends with fewer than two safe findings, and rejects LLM scratchpad/filter notes before email delivery; AutoDiscovery nightly targeting now supports full-platform rollout from feature-flag rollout percentage while preserving founder allowlist pilots, excludes demo/blocked accounts, and persists `phase1_mutations` in run reports after live mutation; AutoDiscovery tuning loop FQS scoring handles transient `RaceInputFinding` outputs without persistence timestamps so manual/nightly runs do not partial on missing `last_confirmed_at`; Coach Runtime V2 performance pace context repair adds RPI-derived training paces, race equivalents, and recent race history to training-intensity/workout-execution/race-planning/pace-zone turns, suppresses stale `pace_zones` unknowns when those anchors exist, treats “you have my pace zones/RPI” as correction-dispute, tightens same-day race carry-forward, and blocks visible `The read:` / `The unasked:` labels at runtime; Apr 27: Coach Runtime V2 selective nutrition-context retrieval for food-log, fueling, pattern-mining, and body-composition turns, with current-log/date-range compact prompts scoped to the nutrition ask only; visible internal-language blocking for packet/tool/context terms; Coach Runtime V2 qualitative eval hardening for compression, relevance bleed, system-language leakage, numeric data dumps, repeated unknown prompts, visible rubric labels, and mode-conditioned decision-leading; Coach Runtime V2-only serving contract, V1 chat fallback removed, V2 fail-closed responses, Kimi V2 thinking disabled, compact V2 packet prompts, bounded timeout/empty-content handling with compact retries, deterministic same-turn/recent Garmin lap-table parsing, corrected course-gain evidence precedence over stale assistant claims, natural decision/race guardrail acceptance without brittle exact headings, generic workout warmup follow-ups kept out of race-day mode, and packet-budget trimming that preserves pasted athlete tables/current turns; Apr 26: Coach Runtime V2 first packet path, authoritative calendar/race context, activity evidence/execution-quality packet repair, Artifact 9 athlete truth ledger foundation, deterministic extraction semantics, recent-activities block, cross-thread memory foundation, unknowns block, V2 voice blocklist enforcement, Artifact 9 packet/prompt rewire, comparison harness, pending-conflict packet surfacing, configurable legacy bridge shim warnings, V2 deterministic turn-guard parity, and Docker image revision labels; ask-after-work adaptation context, bridge de-authoring, no-tools Kimi packet response, timeout fallback, packet/LLM telemetry, safety shell, fail-closed runtime flags, runtime metadata; Coach Artifact 7 replay validator, first Artifact 7 replay case, V2 canary temporal replay case, V2 activity fake-confidence replay case, and external reference ignore guard; Apr 25: race-week briefing load-safety gate; coach Phase 7 split-aware retrieval, race-day contract, direct voice, general-knowledge repair, cleanup, Phase 8 Real Coach Standard eval framework, live quality repair for race-day context bleed, and structured workout verification escalation; Apr 24: timezone two-model + home/effective split; nutrition autofill prevention; briefing clock time removed from LLM prompt; coach trust foundation slice; conversation contract enforcement; N=1 coaching memory; Race Strategist Mode foundation; Coach Value Eval Harness; Frontend Trust UX foundation)

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
| **Coach model** | **Coach Runtime V2 packet Kimi**: `COACH_CANARY_MODEL` (default `kimi-k2.6` in `apps/api/core/config.py`), OpenAI-compatible Moonshot API in `services/coaching/_llm.py` `query_kimi_v2_packet`. `AICoach.chat` is V2-only/fail-closed; it does not serve V1/Sonnet fallback answers. |
| **Briefing model** | Default **`BRIEFING_PRIMARY_MODEL`** = `claude-sonnet-4-6`. Optional **Kimi** for athletes listed when `KIMI_CANARY_ENABLED` + `KIMI_CANARY_ATHLETE_IDS` (model `KIMI_CANARY_MODEL`, default `kimi-k2.6`). Provider routing + **Sonnet → Gemini 2.5 Flash** fallback chain in `apps/api/core/llm_client.py` (`call_llm` / `call_llm_with_json_parse`). |
| **Plan engine (V1)** | `services/plan_framework/n1_engine.py` |
| **Plan engine (V2)** | `services/plan_engine_v2/engine.py` — active behind `engine=v2` flag, admin/owner only |
| **Deploy** | `ssh root@187.124.67.153` then `cd /opt/strideiq/repo && git pull origin main && GIT_SHA=$(git rev-parse HEAD) docker compose -f docker-compose.prod.yml up -d --build` |
| **CI** | Must be green before deploy. `gh run list` to check. |

## Start Here

Before writing any code, understand these five things:

1. **[Quality & Trust Principles](./quality-trust.md)** — the five non-negotiable rules. N=1 only. Suppression over hallucination. The athlete decides. No threshold is universal. Never hide numbers. Violating these is the fastest way to lose the founder's trust.

2. **[Product Vision](./product-vision.md)** — what StrideIQ is and why. The intelligence moat. The visual → narrative → fluency loop. The founder is a BQ runner who coaches state-record holders. The bar is extremely high.

3. **[Coach Architecture](./coach-architecture.md)** — the most-used surface. V2-only packet Kimi coach path. Fail-closed runtime behavior. Context builders. Anti-hallucination guardrails. Budget caps. Date rendering discipline.

4. **[Briefing System](./briefing-system.md)** — the most fragile surface. Lane 2A architecture. 8+ intelligence sources. Repeated regressions. **Approach with extreme caution.**

5. **[Infrastructure](./infrastructure.md)** — how to deploy, container names, beat startup dispatch pattern (daily tasks won't fire without it), database, CI pipeline.

## All Pages

| Page | What it covers |
|------|---------------|
| **[Quality & Trust Principles](./quality-trust.md)** | Five non-negotiable rules, KB registry, anti-hallucination, OutputMetricMeta, coach guardrails |
| **[Product Vision](./product-vision.md)** | Manifesto, strategy, 16 priority-ranked concepts, design philosophy, competitive frame, founder context |
| **[Coach Architecture](./coach-architecture.md)** | AI coach system — V2 packet Kimi (`COACH_CANARY_MODEL`), fail-closed serving contract, context injection, search/activity tools, conversation contracts, KB scanner, budget caps |
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
