# StrideIQ Build Roadmap — The Engine Speaks

**Date:** March 9, 2026
**Status:** Canonical. This is the build north star. Every session starts here.
**Origin:** Consensus of three advisors (Opus, GPT 5.4, Stride) + founder validation.
**Replaces:** Scattered builder instructions, session handoffs as build direction.

---

## The Diagnosis (agreed by all three advisors independently)

The engine is built. The surfaces aren't. The product's differentiator is invisible to the people using it.

- 152 services. 1,878 tests. 4 correlation engine layers. 15 investigations. Weather normalization. Shape extraction. Finding persistence. Daily intelligence.
- The athlete sees: activity titles, a morning briefing, a finding card on home.
- The athlete does not see: their sleep cliff, their recovery half-life, their weather sensitivity curve, their decay timing, their asymmetry ratios, or any finding rendered in context on any chart.

The problem is not lack of intelligence. It is lack of **earned visibility**.

---

## The Principle

Path A first. Existing screens. No new visual vocabulary. The activity detail page is the primary teaching surface — it's where trust is won fastest because the athlete can verify findings against their felt experience. Home is the habit surface. Both must speak before anything else matters.

Path B (dream surfaces — fingerprint organism, training landscape, run signatures, race canvas) is gated on data sufficiency, finding diversity, AND a passed design exploration. No Path B production code until Path A is shipping and the emotional storyboard lands.

No more engine layers before these surfaces exist. Making existing intelligence visible is 10x higher ROI than making it more powerful.

---

## Priority 0: Race-Week Weather (THIS WEEK — before Saturday March 15)

Michael's first marathon is Saturday. The system has `investigate_heat_tax`, Magnus formula dew point, personal heat resilience score, and `heat_adjustment_pct` on every historical activity. It knows what heat does to Michael's body, specifically.

**Build:** Pull the weather forecast for Tobacco Road marathon (Cary, NC). Run it through Michael's personal heat model. Surface it in morning voice or as a home card starting Wednesday.

Even a minimal version (manually input the forecast, let the model personalize) delivers value:

> "Saturday forecast: 58°F, dew point 44°F. Based on your history, no heat adjustment expected. Your last 3 races at similar conditions averaged -0.2% — essentially neutral."

**Why P0:** Time-sensitive. After Saturday it's worthless. And it's the exact sentence the strategy doc describes: "Something nobody else can say." This is a 1-day build that proves the product strategy is real, not theoretical.

**What's built:** `heat_adjustment.py`, `investigate_heat_tax`, L1 threshold detection on heat. **What's needed:** Forecast data for race location + date, surface on home or morning voice.

---

## Horizon 1: The Engine Speaks (Now → 3 weeks)

The intelligence that exists reaches the athlete through screens they already visit. Zero new pages. Zero new visual vocabulary. Just better versions of what's there.

| # | Item | Surface | What's Built | Est. |
|---|------|---------|------------|------|
| 1a | Findings pinned to chart timestamps on activity detail | Activity detail | `GET /v1/activities/{id}/findings` (shipped below Runtoon as cards) | 3-4 days |
| 1b | Weather-adjusted effort coloring on pace chart | Activity detail + home hero | `heat_adjustment_pct` on Activity | 2-3 days |
| 1c | Shape icons on activity list cards | Activity list | `run_shape` JSONB on Activity | 2-3 days |
| 1d | Morning voice references specific findings | Home | Fingerprint context wiring (shipped Mar 9) | 1-2 days |
| 1e | "What this run taught us" narrative block below chart | Activity detail | Shape, weather, findings data all exist | 2-3 days |
| 1f | Coach quality fixes — deterministic pre-checks | Coach | `COACH_QUALITY_AUDIT.md` scoped | 3-4 days |

### The architectural correction (1a)

The finding annotations shipped March 9 as cards below the Runtoon card. That breaks the Design Philosophy's 7-step sequence. Findings must be **contextual annotations pinned to the relevant point on the chart**. The athlete should see a marker at minute 23 on the pace line, tap it, and read the finding. The visual creates the question, the annotation answers it.

Right now the finding is disconnected from the visual — it's a card below another card. The bridge isn't built. This is the single most important item in Horizon 1.

### Gate

The athlete opens the app after a run and sees:
- Weather-adjusted effort coloring on the pace chart
- A finding pinned to a moment on their chart
- An activity list where they recognize runs by shape
- A morning voice that says something specific about their body

If this doesn't happen, nothing else matters.

---

## Horizon 2: Proof of Moat (Weeks 3–8)

Two things happen that no other running app can do. One looks backward (Pre-Race Fingerprint retrospective). One looks forward (race countdown weather). Both produce sentences the athlete says out loud to their running partner.

| # | Item | Surface | Depends On | Est. |
|---|------|---------|------------|------|
| 2a | Pre-Race Fingerprint retrospective (Michael's marathon) | Progress or dedicated surface | Racing Fingerprint Phase 1 (deployed), race result | 1-2 weeks |
| 2b | Race countdown weather — forecast API + personal heat model | Home (race card) | P0 weather work, forecast API | 1 week |
| 2c | Deep backfill first-session experience (Belle) | Home + activity list | Correlation engine, shape extraction | 1 week |
| 2d | Daily intelligence → frontend consumers | Insights page, home | `daily_intelligence.py` (built, unwired) | 3-4 days |
| 2e | Progress narrative activation | Progress page | `useProgressNarrative` hook (built, dormant) | 2-3 days |
| 2f | Personal Operating Manual Lite — fingerprint evidence page | New or existing page | Active `CorrelationFinding` grouped by domain, coaching language | 1-2 weeks |

### The Operating Manual Lite (2f)

The product needs a place where the athlete sees "what the system knows about me" NOW, without waiting for the fingerprint organism.

**Contents:**
- Active `CorrelationFinding` grouped by domain (sleep, cardiac, pace, recovery, environmental)
- Threshold, asymmetry, decay, and mediation data rendered in coaching language
- Evidence drilldown (tap to see the data)
- Confidence / confirmation state
- Recent changes / strengthened findings
- Links back to activities where the finding was observed

This gives the differentiator a home. It uses already-built engine output. It does not violate the dual-pathway architecture.

### The retrospective (2a)

Michael will have just raced. Build the analysis: compare the training block that produced this race to his historical blocks. Show the match. Show what predicted vs what happened.

More valuable POST-race than pre-race because you have the result to validate against. This becomes the seed for the forward-looking pre-race version.

### Gate

Michael sees his marathon block compared to his historical blocks. Belle sees something true about her body in her first week. The race countdown tells Michael something personalized about conditions 10 days before his next race. If the retrospective makes Michael say "that's real," the product has earned the right to build the forward-looking version.

---

## Horizon 3: The Instrument Sharpens + Path B Design (Weeks 8–16)

Two parallel tracks. One deepens the engine. The other explores the visual future.

### Track A: Engine Layers 5-6 + Pre-Race v1

| # | Item | What It Enables | Est. |
|---|------|----------------|------|
| 3a | L5: Confidence Trajectory | "Strengthening", "stable", "weakening", "stale" per finding | 1-2 weeks |
| 3b | L6: Rate of Change Correlations | Momentum — "sleep trending up 3 days predicts better than stable sleep" | 1-2 weeks |
| 3c | Pre-Race Fingerprint v1 — forward-looking | Block-level matching for upcoming race | 2-3 weeks |
| 3d | Personal Operating Manual (full) | Accumulation view, ≥8 active findings | 1-2 weeks |

### Track B: Path B Design Exploration (non-code, parallel)

| # | Item | Output | Est. |
|---|------|--------|------|
| 3e | Emotional storyboard | Moment-by-moment narrative of fingerprint unlock | 1 week |
| 3f | Creative coding prototypes | p5.js sketches: fingerprint with 8 / 25 / 50 findings | 2 weeks |
| 3g | Technology proof-of-concept | ChartGPU stream rendering, R3F terrain, Framer breathing | 2 weeks |
| 3h | Reconnection moment test | Prototype: Path A finding appears as Path B filament | 1 week |

### Gate for Track A

L5 produces confidence trajectories. At least one finding shows "strengthening" or "weakening" that matches Michael's felt experience. Operating Manual has ≥8 entries.

### Gate for Track B

The emotional storyboard makes the founder feel something. The p5.js sketch with 25 findings looks like a portrait, not a chart. The reconnection moment test works. **If the storyboard or sketch is mediocre, stop. Path B at mediocre quality is worse than no Path B.**

---

## Horizon 4: The Dream Takes Shape (Weeks 16–28)

Path B production code begins. Only if Horizon 3 Track B gates passed. Sequenced by athlete touch frequency.

| # | Item | Touch Frequency | Est. |
|---|------|----------------|------|
| 4a | Run Signatures on activity cards | Every run viewed | 3-4 weeks |
| 4b | Morning Pulse on home page | Daily | 2-3 weeks |
| 4c | Fingerprint Organism — dedicated surface | Weekly | 4-6 weeks |
| 4d | Race Canvas | Event-triggered (before races) | 3-4 weeks |
| 4e | L7: Interaction Effects | Multi-input patterns | 2-3 weeks |
| 4f | L8: Failure Mode Detection | Injury fingerprint foundation | 2-3 weeks |

### Gate

The run signature makes another runner ask "what app is that?" The morning pulse shows the fingerprint subtly different from yesterday and the athlete reads the form before the words. The fingerprint organism triggers the reconnection moment: the athlete taps a filament and recognizes a finding they've been seeing on their activity pages for weeks.

---

## Horizon 5: The Moat Becomes Permanent (Weeks 28+)

| # | Item | What It Creates |
|---|------|----------------|
| 5a | Training Landscape | 3D terrain from training history |
| 5b | Personal Injury Fingerprint | Continuous background monitor |
| 5c | Women's Health Intelligence Layer | Cycle-aware training |
| 5d | L9-L12 engine layers | Antagonistic pairs, seasonal patterns, adaptive weighting, cohort intelligence |
| 5e | Personal Operating Manual (full maturity) | 40 entries after 2 years |

No gate — this is the long game. Each layer makes the product harder to leave.

---

## The Dependency Graph

```
P0: Race-week weather (THIS WEEK)
│
Horizon 1 (Engine Speaks — 3 weeks)
│   ├── Findings on chart (not below it)
│   ├── Weather-adjusted effort coloring
│   ├── Shape icons on activity list
│   ├── Smart morning voice
│   └── Coach quality fixes
│
├── Horizon 2 (Proof of Moat — weeks 3-8)
│   ├── Pre-Race Fingerprint retrospective
│   ├── Race countdown weather
│   ├── Belle deep backfill
│   ├── Daily intelligence → frontend
│   ├── Progress narrative activation
│   └── Operating Manual Lite
│
├── Horizon 3A (Engine L5-6 — weeks 8-16)
│   ├── Confidence trajectory
│   ├── Momentum effects
│   └── Pre-Race Fingerprint v1 (forward)
│
├── Horizon 3B (Path B Design — PARALLEL, non-code)
│   ├── Emotional storyboard
│   ├── p5.js prototypes
│   ├── Tech proof-of-concept
│   └── Reconnection test
│        └── GATE: beauty + recognition
│
└── Horizon 4 (Dream — weeks 16-28) — ONLY if gate passes
    ├── Run signatures
    ├── Morning pulse
    ├── Fingerprint organism
    └── Race canvas
         └── Horizon 5 (Moat — weeks 28+)
```

---

## What Is Explicitly NOT On This Map

- **Path B production code before Path A ships and design gate passes.** Non-negotiable.
- **More engine layers (L5-12) before Horizon 1 surfaces exist.** Visibility > power.
- **Tab navigation restructuring.** Rejected (Design Philosophy Part 4).
- **Intelligence page consolidation (7→2).** Rejected.
- **Templates for coachable moments.** Rejected.
- **Collaborative fingerprint / leaderboards.** Rejected as premature.
- **50K Ultra (Phase 4).** Training plan feature, not visibility. Builds when gated tests promote.
- **Phase 3B/3C workout narratives and N=1 insights.** Gate-accruing. Monitor, don't plan.
- **Campaign detection frontend.** Let data accumulate first.
- **Full Pre-Race Fingerprint before the marathon.** 6 days is not enough. The weather intelligence IS the pre-race fingerprint at its simplest.

---

## What This Map Protects Against

The biggest risk is not building the wrong thing. It's building the right thing in the wrong order.

- The fingerprint organism without Path A curriculum = an empty form that teaches nothing.
- The Pre-Race Fingerprint without the retrospective = a prediction with no validation.
- Engine L5-12 without visible L1-4 = a more powerful instrument that still doesn't speak.

Every horizon earns the right to attempt the next one. Skip a gate and the thing you build will be technically correct and emotionally empty.

The manifesto says: "The chart makes you open the app. The intelligence makes you trust it. The voice makes you need it." That's the sequence. Not the other way around.

---

## Read Order for Any Agent Starting Work

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. This document (`docs/BUILD_ROADMAP_2026-03-09.md`)
4. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`
5. `docs/SITE_AUDIT_LIVING.md`
6. Relevant horizon-specific docs as needed

Do not start coding until you know which horizon item you're building, what gate it serves, and what's already built.
