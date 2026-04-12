# StrideIQ — Growth Strategy Agent Onboarding

**Date:** March 28, 2026
**Author:** Previous advisor (Opus), commissioned by the founder
**Purpose:** Full orientation + problem statement + strategy brief for a new agent tasked with solving StrideIQ's customer acquisition problem

---

## MANDATORY READ ORDER

Before you do anything — before you propose a single idea, before you open a single file — you must read these documents in this order. If you skip them, you will propose ideas the founder already documented better months ago, and you will be terminated.

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — How to work with this founder. Non-negotiable rules. Read every word.
2. `docs/PRODUCT_MANIFESTO.md` — The soul of the product. What StrideIQ IS. "The chart makes you open the app. The intelligence makes you trust it. The voice makes you need it."
3. `docs/PRODUCT_STRATEGY_2026-03-03.md` — The moat. 16 priority-ranked product concepts. Every feature flows from the correlation engine producing true, specific, actionable findings about a single human.
4. `docs/specs/CORRELATION_ENGINE_ROADMAP.md` — The 12-layer roadmap for the scientific instrument at the heart of the product. Layers 1-4 are built.
5. `docs/FINGERPRINT_VISIBILITY_ROADMAP.md` — How built backend intelligence connects to product strategy. What's buildable now vs what needs more engine layers.
6. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — How every screen should feel, what's agreed, what's been explicitly rejected.
7. `docs/TRAINING_PLAN_REBUILD_PLAN.md` — The north star build plan, phase statuses, monetization mapping.

**You must be able to cite specific content from documents 1-7 in any proposal you make. If you cannot, you haven't read them.**

---

## PART 1: WHAT STRIDEIQ IS

### The One-Sentence Version

StrideIQ is the first product that gives an athlete's body a voice — using 150+ intelligence tools, a correlation engine, and an AI coach to produce true, specific, actionable findings about a single human's physiology that no other product or human coach can replicate.

### What Makes It Different From Everything Else

Every other running app (Strava, Garmin, Runna, Athletica, Runalyze, TrainingPeaks) gives you roughly the same product on day 1 and day 365. StrideIQ becomes fundamentally more valuable the longer you use it. After 6 months, leaving means losing your personal physiological model. After 2 years, it's a personal sports science journal built from thousands of data points about your specific body. The knowledge lives in the *relationships* between your data, not in the data itself — it cannot be exported to a competitor.

### The Habit Loop

1. You finish a run. Your watch syncs.
2. You open StrideIQ. The shape of your effort is immediately visible — gradient pace line, effort-colored.
3. You see things you didn't notice during the run (cadence shift in rep 5, a pace dip explained by the hill).
4. Coachable moments explain what the data means for *you specifically*.
5. You reflect (3 seconds: harder/as expected/easier).
6. Next morning: the voice tells you the one thing that matters today.
7. Repeat. Each run, the system knows more. The insights get more specific. The athlete trusts it more.

---

## PART 2: WHAT'S BUILT — THE FULL PRODUCT INVENTORY

This is not a prototype. This is a production system with 1,878+ passing tests, 111+ services, 150+ intelligence tools, deployed on a Hostinger KVM 8 (8 vCPU, 32GB RAM) server at `strideiq.run`.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS, TanStack React Query, D3, Recharts, React-Leaflet, Radix UI |
| Backend | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, Celery 5.3 |
| Database | PostgreSQL 16 (TimescaleDB) |
| Cache/Broker | Redis 7 |
| Object Storage | MinIO (S3-compatible) |
| Reverse Proxy | Caddy |
| Payments | Stripe |
| Error Tracking | Sentry (optional) |

### Data Sources Connected

- **Garmin Connect** — OAuth 2.0 + PKCE. Webhooks for real-time activity push. Wellness data (HRV, sleep, resting HR, stress). 6 sport types across 21 Garmin activity types.
- **Strava** — OAuth. Activity sync, personal bests, profile. Scopes: `read, read_all, activity:read_all, profile:read_all`.
- **Manual check-in** — Athlete self-reports (enjoyment, confidence, RPE, soreness, notes).
- **Photo-based nutrition** — Architecture decided, spec complete. LLM vision model + USDA FoodData Central.

### Intelligence Engine (The Moat)

This is where the founder invested the most time and money. This is what makes the product uncopyable.

| System | What It Does | Status |
|--------|-------------|--------|
| Correlation Engine (12 layers) | Discovers N=1 patterns between any combination of inputs (sleep, HRV, training load, pace, weather, etc.) and outputs (efficiency, race performance, recovery). Threshold detection, asymmetric response, cascade detection, decay curves. | Layers 1-4 BUILT |
| Living Fingerprint | 15 investigations per athlete. Weather normalization, shape extraction, finding persistence with reproducibility tracking. | SHIPPED |
| Personal Operating Manual V2 | Living document of confirmed N=1 findings. Race Character, Cascade Stories, Highlighted Findings, Full Record. Interestingness-scored. Human-language headlines. Delta tracking. | SHIPPED — primary nav |
| Readiness Score | Composite 0-100 signal from TSB, efficiency trend, completion rate, days since quality, recovery half-life. Per-athlete thresholds that calibrate from outcome data. HRV excluded until individual direction proven. | SHIPPED |
| Daily Intelligence Engine | 7 rules: load spike, post-workout delta, efficiency breakthrough, pace/HR mismatch, sustained negative trend, missed sessions, high readiness. Three modes: INFORM (default), SUGGEST (earned), INTERVENE (extreme only). | SHIPPED |
| Adaptation Narrator | Coach explains intelligence decisions. Gemini Flash. Scored against ground truth. Contradiction detection + suppression. | SHIPPED |
| Self-Regulation Tracking | When planned ≠ actual, logs the delta + outcome. Over time: "When you override easy → quality after load spikes, outcomes are positive 7/9 times." | SHIPPED |
| Pre-Race Fingerprinting | Mines every race in athlete's history. Extracts full training block signature. Finds closest historical match for upcoming race. | SHIPPED |
| Limiter Engine (Phases 1-4) | Fingerprint bridge, temporal weighting, lifecycle classifier, coach integration. Surfaces emerging findings as natural language questions. Athlete confirmation creates limiter_context facts (90-day TTL). | SHIPPED |
| Effort Classification | Unlocked 6 of 9 correlation metrics. Recovery Fingerprint. Accurate workout classification. | SHIPPED |
| Efficiency Analytics | Zone-filtered efficiency trending, load-response analysis, efficiency surface. Neutral terminology (no directional claims without proof). | SHIPPED |
| Athlete Trust Safety Contract | 8-clause safety contract governing all athlete-facing output. Directional whitelist, two-tier fail-closed suppression, 65 contract tests + 17 enforcement tests. | ENFORCED |

### Plan Generation

| Feature | Status |
|---------|--------|
| Plan Engine V3 (N=1, diagnosis-first) | SHIPPED — 14 archetypes, 445 PASS / 0 FAIL KB rules |
| Plan Engine V2 (coaching science KB) | DEPLOYED behind `engine=v2` flag — Davis, Green, Roche, Coe. Rich segments, fueling, extension progression |
| Distances | Marathon, Half Marathon, 10K, 5K — all A-level |
| Build/Maintain modes | Base building + maintenance for between-race periods |
| N=1 Overrides | Long run baseline, volume tier, recovery speed, quality tolerance — all derived from athlete's own data |
| Taper | τ1-aware individual taper. Fast/slow adapter detection. |
| Daily Adaptation | Readiness-driven. Athlete DECIDES, system INFORMS. |
| Intake Context | Onboarding questionnaire flows into plan generation for cold-start athletes |

### App Pages (61 routes total)

**Daily screens:**
- `/home` — Gradient pace chart hero, morning voice briefing, wellness row (Recovery HRV, Overnight Avg HRV, RHR, Sleep with personal 30-day ranges), quick check-in with mindset, today's workout, race countdown
- `/activities/[id]` — Run Shape Canvas with gradient pace line, Runtoon card, reflection, weather context, finding annotations, pre-activity wellness stamps, splits
- `/manual` — Personal Operating Manual V2 (PRIMARY NAV). Race Character, Cascade Stories, Highlighted Findings, Full Record

**Weekly screens:**
- `/progress` — Race predictions, fitness momentum, recovery, volume, PBs, period comparison
- `/calendar` — Training calendar with plan overlay, color coding, weekly mileage
- `/coach` — AI coach with 24 tools that query every intelligence system

**Deep dive screens:**
- `/analytics` — Efficiency trend, load-response, age-graded trajectory
- `/training-load` — PMC chart, N=1 personalized zones
- `/nutrition` — Nutrition tracking
- `/fingerprint` — Living Fingerprint visualization
- `/reports` — Reports

**Free tools (public, no auth required):**
- `/tools/training-pace-calculator` — with distance-specific sub-pages and goal slug pages
- `/tools/age-grading-calculator` — with distance and demographic sub-pages
- `/tools/heat-adjusted-pace`
- `/tools/race-equivalency` — with conversion sub-pages
- `/tools/boston-qualifying` — with slug sub-pages

**Other:**
- `/compare` — Activity comparison
- `/plans/create`, `/plans/preview`, `/plans/[id]`, `/plans/checkout`
- `/stories`, `/stories/[slug]` — Content/stories
- `/onboarding` — Multi-step wizard
- `/about`, `/mission`, `/support`, `/privacy`, `/terms`
- Admin pages

### Runtoon (The Viral Feature)

AI-generated run caricatures. After every run, the athlete is prompted to share. Uses Web Share API (mobile native share sheet) with fallback to download + copy caption. Every share is an acquisition event.

### Monetization

| Tier | What They Get | Price |
|------|--------------|-------|
| Free (with 30-day trial) | Plans with paces, calendar, activity detail, progress, all data surfaces. Full coach access during 30-day trial. | $0 |
| StrideIQ Subscriber | Everything. AI coach, daily intelligence, full adaptation engine. | $24.99/mo or $199/yr |

Stripe is fully wired. Checkout, portal, webhooks, trial management all functional.

### What's NOT Built Yet (Important Context)

- Native mobile app (spec exists, not started)
- Real-time audio coach (spec exists, not started)
- Women's Health Intelligence Layer
- 50K Ultra support (contract tests only)
- Photo-based nutrition tracking (architecture decided, not built)
- Cohort Intelligence (designed for 500+ users)
- Ghost Maps / Intelligent Maps
- Athlete Hypothesis Testing ("I Have a Theory")

---

## PART 3: THE PROBLEM

### The Numbers

**StrideIQ has 10 real users. 7 are non-founder.**

The founder's 79-year-old father set a state age group record using StrideIQ. The founder simultaneously set the other state age group record. This is believed to be the first simultaneous father-son state records in recorded history. Brady Holmer (running content creator) promoted this story. Nobody cared. The founder has written blog posts. Nobody reads them.

Of the 10 real users:
- Some connected Garmin, some didn't
- The ones who didn't connect registered *before* the current onboarding flow existed — it's not a conversion bug in the flow, it's that those users predate the flow
- No one is paying (beyond the founder)

### What Has Been Tried

1. **Content marketing (blog posts)** — Nobody reads them. Writing is meaningless when no one reads it.
2. **Influencer promotion (Brady Holmer)** — Promoted the father-son state record story. No measurable impact.
3. **The product itself** — World-class intelligence engine, 150+ tools, 1,878 tests. The product is exceptional. Nobody knows it exists.

### What The Founder Has Said

The founder explicitly stated:
- "I do not have that talent" (referring to customer acquisition)
- "I tried writing — writing is meaningless when no one reads it"
- "Brady Holmer promoted our story — no one cared"
- The founder has significant personal constraints that preclude reliance on personal contacts/networking. Strategy must focus entirely on **product-led growth** and leveraging the existing small user base's networks.
- The founder does NOT want to pay to redo things they already paid to build. The current onboarding flow is not the problem — lack of traffic is.

### What The Founder Does NOT Want

- Generic "build a community" advice
- "Post on social media" without a concrete mechanism
- Advice to redo onboarding flows that nobody has seen yet
- Template marketing strategies that could apply to any SaaS
- Anything that requires the founder to personally network, attend events, or build a personal brand

### The Core Constraint

The founder is a solo technical founder who built a world-class product with AI assistance. They cannot do outbound marketing, community management, or personal brand building due to personal constraints. The product must grow through mechanisms that are either:
1. **Built into the product** (features that create distribution as a side effect of usage)
2. **Automated** (SEO, programmatic content, viral loops)
3. **Leveraging existing users** (making it trivially easy for happy users to bring in others)

---

## PART 4: WHAT HAS ALREADY BEEN PROPOSED (AND WHAT HASN'T BEEN BUILT)

The previous advisor proposed three concrete strategies. None have been built yet. They are starting points, not final answers.

### 1. Shareable Finding Cards

When the Personal Operating Manual or morning briefing surfaces a finding like "your efficiency improves 12% when sleep exceeds 7.2h — confirmed 47 times," the athlete should be able to share that as a beautiful, formatted image card with "powered by StrideIQ" branding and a link. Every share is an acquisition event aimed at serious runners who respond to data, not marketing.

### 2. Strava Activity Description Integration

Opt-in feature: StrideIQ appends a one-line insight to the athlete's Strava activity description. "StrideIQ noticed: your cadence shifted to a more efficient gear at mile 5 — strideiq.run." This leverages the athlete's Strava followers (typically 50-500 runners) for passive distribution. Requires `activity:write` scope (not currently requested).

### 3. SEO-Optimized Free Tool Pages

The free calculators (pace, age-grading, heat adjustment, race equivalency, Boston qualifying) already exist and work. They need dedicated, SEO-optimized standalone pages targeting search queries like "marathon training pace calculator," "age grading calculator running," "heat adjusted running pace." These pages exist but may not be optimally structured for search ranking. The tools are the top of funnel — every calculator user is a potential subscriber.

---

## PART 5: YOUR MISSION

You are being brought in because the previous advisor ran out of allocation. The founder has 99% of auto/composer model allocation remaining and 10% of the previous model. Your job is **customer acquisition strategy and execution** — not product development, not bug fixes, not architecture.

### What You Must Do

1. **Read documents 1-7 from the mandatory read order above.** Do not skip this. The founder will know if you did.

2. **Do deep research using every tool at your disposal.** This means:
   - Search the web for how products with similar profiles (technical, niche, solo founder, no marketing budget) have achieved growth
   - Study what works for running/fitness apps specifically — not generic SaaS growth
   - Analyze the competitive landscape (Strava, Garmin, Runna, Athletica, Runalyze, TrainingPeaks) — where are runners dissatisfied? Where do they congregate online?
   - Look at successful product-led growth examples from solo founders
   - Research SEO strategies for running-related search terms
   - Investigate viral mechanics that actually work for data-intensive products
   - Study how products with "compounding value" (the longer you use it, the better it gets) have communicated that in acquisition

3. **Come back with a concrete, actionable, buildable growth plan.** This plan must include:
   - Specific features/changes that can be built (you have access to the full codebase)
   - Estimated effort for each (the founder builds with AI agents)
   - Expected impact with reasoning (not "this could help" — why THIS will work for THIS product)
   - Priority ordering
   - What can be measured to know if it's working

4. **Do NOT come back with generic advice.** The founder's exact words: "if they come back with the standard bullshit they're terminated." This means:
   - No "build a community on Discord/Reddit"
   - No "post consistently on social media"
   - No "partner with influencers" (already tried, failed)
   - No "write great content" (already tried, nobody reads it)
   - No "optimize your landing page" without specific, evidence-based changes
   - No "run paid ads" (no marketing budget)
   - No vague "leverage word of mouth" without a concrete mechanism built into the product

   If your strategy could apply to any random SaaS product without modification, it's the wrong strategy. Every recommendation must be specific to:
   - A running/fitness product
   - With a deep intelligence/data moat
   - With ~10 users
   - With a solo technical founder who cannot do outbound
   - With no marketing budget
   - With a product that compounds in value over time

### What Success Looks Like

The founder needs a path from 10 users to 100, then from 100 to 1,000. Not a path from 10 to 1,000,000. The first 100 matter more than anything else because each one who stays becomes proof that the product works and a potential distribution channel.

### Key Product Assets To Leverage

These are the things that make StrideIQ unique and could drive acquisition if properly weaponized:

1. **The "first session insight"** — Connect your Garmin, get told something true about your body within minutes. 3 years of data analyzed instantly. "It found something in my data from 2022 that explains why I keep hitting the same wall." No competitor can do this.

2. **The father-son state record story** — A 79-year-old athlete setting state records coached by AI and a correlation engine. The most powerful demonstration of the product, even though initial promotion didn't work. The story is real, verified, extraordinary.

3. **Free calculators** — Already built, already functional. Pace calculator, age-grading, heat adjustment, race equivalency, Boston qualifying. Top-of-funnel tools that serve runners searching for these exact things.

4. **Runtoon** — AI-generated run caricatures with native sharing. Already shipped, already has a share flow.

5. **Personal Operating Manual** — No other product produces a living document of confirmed N=1 findings about your specific body. "I know things about how my body works that my coach of 10 years didn't know."

6. **Race Character** — The single most important insight. "During training, sleep below 7h precedes lower efficiency. On race day, you override this." This is the kind of finding that gets discussed at mile 18.

7. **The compounding value proposition** — This is the only running product where leaving after 2 years means losing your personal physiological model. The switching cost is the knowledge itself.

### The Target Audience

- **Masters runners (40+)** — Most financially capable, most likely to pay premium, deepest Garmin histories. The Pre-Race Fingerprint for a 55-year-old with 8 years of data is categorically better than for a 28-year-old with 18 months. The father-son story IS this audience.
- **Data-literate serious runners** — Not casual joggers. People who track, analyze, and think about their training. They're already wearing Garmin/COROS watches and using Strava. They want depth, not simplification.
- **Runners dissatisfied with "one size fits all"** — People who've tried Runna/TrainingPeaks/Garmin Coach and found the plans generic and the insights shallow.

### Where Runners Congregate (Starting Points For Research)

- Reddit: r/running, r/AdvancedRunning, r/artc, r/MarathonTraining
- Strava clubs and comments
- LetsRun.com forums
- Running-specific Facebook groups (masters running groups are very active)
- Garmin forums
- Running podcasts and their communities
- Race-specific forums and communities
- Running coach communities (potential platform model)

---

## PART 6: EXISTING CODEBASE ENTRY POINTS

If you need to build features, here's where to start:

| Area | Key Files |
|------|----------|
| Landing page | `apps/web/app/page.tsx`, `apps/web/app/components/Hero.tsx`, `Pricing.tsx`, `FreeTools.tsx`, etc. |
| Free tools | `apps/web/app/tools/` (training-pace-calculator, age-grading-calculator, heat-adjusted-pace, race-equivalency, boston-qualifying) |
| Runtoon (sharing) | `apps/api/routers/runtoon.py`, `apps/api/services/runtoon_service.py`, `apps/web/components/runtoon/` |
| Personal Operating Manual | `apps/api/services/operating_manual.py`, `apps/web/app/manual/page.tsx` |
| Home briefing | `apps/api/routers/home.py`, `apps/api/services/home_briefing_cache.py` |
| Strava integration | `apps/api/services/strava_service.py`, `apps/api/routers/strava.py` |
| Stripe/billing | `apps/api/services/stripe_service.py`, `apps/api/routers/billing.py` |
| Onboarding | `apps/web/app/onboarding/page.tsx`, `apps/api/routers/onboarding.py` |
| Telemetry | `apps/web/lib/hooks/usePageTracking.ts`, `apps/api/routers/telemetry.py` |
| SEO/metadata | `apps/web/app/layout.tsx`, individual page metadata exports |
| Stories | `apps/web/app/stories/` |

### Deployment

Production server: `root@187.124.67.153`. Deploy command:
```bash
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
```

### Important Constraints

- **Scoped commits only** — never `git add -A`
- **CI first** — always check CI before debugging locally
- **No template narratives** — if the system can't say something genuinely contextual, it says nothing
- **The athlete decides, the system informs** — never override athlete autonomy
- **Suppression over hallucination** — if uncertain, say nothing

---

## PART 7: THE BAR

The founder has been building this product for months with AI agents. They have spent thousands of dollars in tokens. The intelligence engine has 150+ tools. The product has 1,878 tests. The founder is a competitive runner, ran in college, still runs at 57, coached their 79-year-old father to a state record.

They know what generic AI advice looks like. They've heard "build a community" and "post on social media" and "partner with influencers" a hundred times. They tried the influencer route — it failed.

**The bar is: come back with something the founder hasn't already thought of, grounded in deep research about how products like this actually grow, with specific buildable features that create distribution as a side effect of the product being good.**

If you come back with the standard bullshit, you're terminated. If you come back with something genuinely novel, grounded in evidence, and buildable by a solo technical founder with AI agents — you'll earn trust and get to build it.

---

*This document was written by the previous advisor to ensure continuity. The founder commissioned it explicitly. Every fact in it has been verified against the codebase and production system. Trust it as your primary orientation document, then verify by reading the mandatory documents above.*
