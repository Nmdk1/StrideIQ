# Product Vision

## Current State

StrideIQ is a running intelligence platform that gives the athlete's data a voice. It integrates training, sleep, HRV, stress, weather, nutrition, and cross-training data to discover individual patterns and coach accordingly. The product is pre-launch, preparing for the founder's 10K race (RUNTHEDIST promo code, ~10 days away as of Apr 8, 2026).

## The Core Thesis

> "The chart makes you open the app. The intelligence makes you trust it. The voice makes you need it."

StrideIQ is not a dashboard with a chatbot. It is a system that **knows you** longitudinally and **gives that knowledge a voice** — through the morning briefing, the coach, the Personal Operating Manual, and every surface.

### What Makes This Uncopyable

The moat is **structural knowledge** — relationships between an athlete's sleep, HRV, training load, weather sensitivity, and performance outcomes. These relationships are individual (N=1), discovered over months, and stored as `CorrelationFinding` rows. They cannot be exported as CSV. They compound with time.

### Competitive Frame

| Competitor | What they do | What they don't |
|-----------|-------------|-----------------|
| Strava | Social + activity log | No intelligence, no coach, no plan |
| Garmin Connect | Device data display | Raw numbers, no interpretation |
| Runna | Plan generation | Template plans, no individual learning |
| Athletica | AI training | Population-based, not N=1 |
| Runalyze | Data analysis | Self-serve analytics, no voice |

StrideIQ's differentiation: **knows you** (correlation engine) + **gives it a voice** (coach, briefing, Manual).

## Design Philosophy

From `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`:

### The Visual → Narrative → Fluency Loop

1. Visual catches the eye (chart, pace gradient, shape)
2. Athlete interacts (hover, tap)
3. Wonder forms ("why was that mile faster?")
4. Narrative answers (below the visual, not instead of it)
5. Understanding deepens
6. Trust is judged
7. Fluency becomes habit

### Six Evaluation Questions

Every surface must pass:
1. Does it have a visual anchor?
2. Does the narrative bridge visual to meaning?
3. Does it teach the athlete to read their own data?
4. Does it earn trust (specific, verifiable, humble when uncertain)?
5. Does it contribute to the daily habit loop?
6. Are raw numbers visible? (Never hide numbers)

### HRV Display Standard

Always show both values:
- **Recovery HRV** = `hrv_5min_high`
- **Overnight Avg HRV** = `hrv_overnight_avg`

## Strategic Priorities

From `docs/PRODUCT_STRATEGY_2026-03-03.md` (16 priority-ranked concepts). Rows 17–22 below are wiki extensions beyond that document:

1. **Pre-Race Fingerprint** — full race signature; acquisition + retention
2. **Proactive Coach** — word-of-mouth moments
3. **Personal Injury Fingerprint** — fear/retention
4. **Deep Backfill on OAuth** — acquisition hook
5. **Personal Operating Manual** — V2 shipped Apr 4, 2026
6. **Correlation Web on Progress Page** — retention
7. **Women's Health Intelligence Layer** — rigor caveat
8. **Runtoon** — shipped, viral potential
9. **Masters Athlete Positioning** — targeting
10. **Athlete Hypothesis Testing** — retention through ownership
11. **Forward-Projection of Findings** — prompt-engineering leverage
12. **Intelligent Maps** — screenshot virality (6-step build sequence)
13. **Cohort Intelligence** — build at ~500 users
14. **Compound Recovery Signals** — HRV÷RHR ratio as derived correlation input (scoped, 1 session)
15. **Personal Coach Tier** — service model (founder coaches using StrideIQ) vs platform model (coaches bring athletes). Requires dedicated planning.
16. **AI Nutrition Intelligence** — **SHIPPED** (Apr 9-10). Photo/barcode/NL parsing, USDA integration, fueling shelf, load-adaptive planning, correlation engine wiring.
17. **Usage Telemetry** — **SHIPPED** (Apr 10). First-party page tracking. Evidence-based product decisions for native app spec.
18. **Unified Reports** — **SHIPPED** (Apr 10). Cross-domain reporting for athletes, coaches, clinicians.
19. **Training Lifecycle Product** — **SPECIFIED** (Apr 10). Build/Maintain/Custom plan modes, auto-renewal, post-race transitions. Builder instructions at `docs/BUILDER_INSTRUCTIONS_2026-04-10_TRAINING_LIFECYCLE.md`.
20. **Plan Generator Algorithm V2** — **SPECIFIED** (Apr 10). Full algorithm spec with 13 coaching science KB documents (Davis, Green, Roche), extension-based progression, build-over-build memory, unified segments schema, effort-based descriptions. Spec at `docs/specs/PLAN_GENERATOR_ALGORITHM_SPEC.md`.
21. **Native Mobile App** — **PRELIMINARY** (Apr 10). React Native + Expo vision. Blocked on usage telemetry data. Spec at `docs/specs/NATIVE_APP_SPEC.md`.
22. **Real-Time Audio Coach** — **SCOPED** (Apr 10). Full real-time audio coaching during runs. Spec at `docs/specs/AUDIO_COACHING_SPEC.md`.

## What's Built (Apr 2026)

- **Intelligence engine complete:** N=1 correlation engine (4 layers + nutrition inputs), temporal weighting, lifecycle classifier (6 states), AutoDiscovery, fingerprint bridge
- **Plan engine complete:** Diagnosis-first, KB-grounded (76 rules, 445 PASS), 14 archetypes, 38 workout variants. V2 algorithm spec written with Build/Maintain/Custom modes, extension-based progression, 13 coaching science KB documents (Davis, Green, Roche)
- **Nutrition intelligence:** Photo/barcode/NL parsing, USDA integration (1.8M foods), fueling shelf (97 products), load-adaptive daily targets, 9 correlation inputs. Elevated to first-class metric (#3 in hierarchy)
- **Athlete experience:** Personal Operating Manual V2, morning briefing, AI coach (Kimi K2.5), activity calendar, cross-training (6 sports), Runtoons, maps, unified reports
- **Telemetry:** First-party usage tracking, admin dashboard — no third-party analytics
- **Business:** Stripe integration, 30-day trial, 2-tier monetization ($24.99/mo or $199/yr), RUNTHEDIST promo code

### Scale (as of Apr 2026)

~85 models, 60+ routers, ~120 services, 14 task modules, 175+ test files, 4,036+ passing tests, 113 migrations, 79 correlation inputs (incl. 9 nutrition), 65+ pages, 70+ components, 23+ TanStack hooks, 8 intelligence rules.

## Founder Context

The founder is a BQ runner (Boston Qualifier), masters athlete, has produced six state records as a coach, races 7% faster than training. The product is built for athletes like him — experienced, data-literate, intolerant of generic advice. The bar is: **would the founder use this instead of coaching himself?**

## Sources

- `docs/PRODUCT_MANIFESTO.md` — soul of the product
- `docs/PRODUCT_STRATEGY_2026-03-03.md` — strategic moat, 16 priority-ranked concepts
- `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — visual → narrative loop, HRV standard
- `docs/FOUNDER_OPERATING_CONTRACT.md` — how to work with the founder
