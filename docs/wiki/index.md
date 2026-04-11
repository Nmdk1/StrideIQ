# StrideIQ Internal Wiki

**Last updated:** April 11, 2026

This is the single onboarding document. Read this instead of the 12-document read order.

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
| **Coach model** | Kimi K2.5 (all athletes), Claude Sonnet 4.6 (fallback only) |
| **Briefing model** | Claude Opus 4.6 (primary), Gemini 2.5 Flash (fallback) — different from coach |
| **Plan engine (V1)** | `services/plan_framework/n1_engine.py` |
| **Plan engine (V2)** | `services/plan_engine_v2/engine.py` — active behind `engine=v2` flag, admin/owner only |
| **Deploy** | `ssh root@187.124.67.153` then `cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build` |
| **CI** | Must be green before deploy. `gh run list` to check. |

## Start Here

Before writing any code, understand these five things:

1. **[Quality & Trust Principles](./quality-trust.md)** — the five non-negotiable rules. N=1 only. Suppression over hallucination. The athlete decides. No threshold is universal. Never hide numbers. Violating these is the fastest way to lose the founder's trust.

2. **[Product Vision](./product-vision.md)** — what StrideIQ is and why. The intelligence moat. The visual → narrative → fluency loop. The founder is a BQ runner who coaches state-record holders. The bar is extremely high.

3. **[Coach Architecture](./coach-architecture.md)** — the most-used surface. Kimi K2.5 universal routing. Context builders. Anti-hallucination guardrails. Budget caps. Date rendering discipline.

4. **[Briefing System](./briefing-system.md)** — the most fragile surface. Lane 2A architecture. 8+ intelligence sources. Repeated regressions. **Approach with extreme caution.**

5. **[Infrastructure](./infrastructure.md)** — how to deploy, container names, beat startup dispatch pattern (daily tasks won't fire without it), database, CI pipeline.

## All Pages

| Page | What it covers |
|------|---------------|
| **[Quality & Trust Principles](./quality-trust.md)** | Five non-negotiable rules, KB registry, anti-hallucination, OutputMetricMeta, coach guardrails |
| **[Product Vision](./product-vision.md)** | Manifesto, strategy, 13 priorities, design philosophy, competitive frame, founder context |
| **[Coach Architecture](./coach-architecture.md)** | AI coach system — Kimi K2.5 routing, context builders, system prompt, tools, KB scanner, budget caps |
| **[Briefing System](./briefing-system.md)** | Morning briefing — Lane 2A, prompt assembly, 8 intelligence sources, workout structure detection, guardrails |
| **[Correlation Engine](./correlation-engine.md)** | N=1 intelligence pipeline — Layers 1-4, AutoDiscovery, finding lifecycle, limiter taxonomy, cross-training inputs, fingerprint bridge |
| **[Plan Engine](./plan-engine.md)** | V1 (N1 Engine V3) + **V2 deployed** — V2 wired to production behind `engine=v2` flag, 13 coaching science KB docs, extension-based progression, rich segments, fueling |
| **[Garmin Integration](./garmin-integration.md)** | Three webhook types, FIT file pipeline, weather enrichment (Open-Meteo), health API, accepted sports |
| **[Activity Processing](./activity-processing.md)** | Shape extraction, effort classification, heat adjustment, maps (Leaflet), Runtoons, cross-training detail pages |
| **[Operating Manual](./operating-manual.md)** | Personal Operating Manual V2 — findings display, cascade chains, race character, interestingness filter |
| **[Infrastructure](./infrastructure.md)** | Server, containers, deployment, Celery/Beat, database, CI, environment variables |
| **[Monetization](./monetization.md)** | Two-tier model ($24.99/mo), Stripe integration, promo codes |
| **[Frontend](./frontend.md)** | Next.js 14 routes, component architecture, data layer (TanStack Query), contexts |
| **[Nutrition](./nutrition.md)** | AI Nutrition Intelligence — photo/barcode/NL parsing, fueling shelf, nutrition planning, load-adaptive targets, first-class metric (#3 in hierarchy) |
| **[Usage Telemetry](./telemetry.md)** | First-party page view tracking — PageView model, tracking hook, admin usage reports |
| **[Unified Reports](./reports.md)** | Cross-domain reporting — health, activities, nutrition, body comp in configurable date ranges |
| **[Decisions](./decisions.md)** | 56 ADRs summarized — key architectural choices and their current state |

## Maintenance Contract

Every future code change that affects system behavior should include:

```
Wiki update: Update docs/wiki/[relevant-page].md with [what changed].
```

This is the same discipline as "update tests after code changes." The wiki stays current because every change includes a wiki update step.

## What This Wiki Is Not

- **Not a replacement for source docs.** The `docs/` folder is immutable raw source material. The wiki synthesizes it.
- **Not a spec.** Use `docs/specs/` for detailed specifications. The wiki summarizes current state.
- **Not a session log.** Use `docs/SESSION_HANDOFF_*.md` for session-specific context. The wiki is timeless.
