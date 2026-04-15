# StrideIQ — Complete Product Briefing

**Purpose:** Single document for external research. Covers what StrideIQ is, what it has built, and what makes it novel.
**Date:** April 6, 2026

---

## 1. The Soul (Product Manifesto)

StrideIQ is the first product that gives an athlete's body a voice.

Every runner generates thousands of data points — heart rate, pace, cadence, elevation, effort — and alongside those, they live a life: they sleep well or poorly, they're stressed or calm, they're sore or fresh. Today, all of that data sits in silos. Strava shows you a line chart. Garmin shows you five disconnected panels. Runna gives you a workout. None of them connect your Tuesday sleep to your Thursday tempo. None of them notice that your best races happen when you back off volume two days before, not three. None of them see that your body's strongest adaptation pattern is the 48-hour rebound after threshold work, and that last night's 6 hours of sleep is about to blunt it.

StrideIQ sees all of it. Not because it has better charts — because it has 150+ intelligence tools that have been studying YOU. Your correlations. Your causal patterns. Your time-lagged responses. Your self-regulation habits. Your readiness signals. Your efficiency trajectory. Your recovery fingerprint. Individually, each is a feature. Together, they are a portrait of your body that no human coach could hold in their head across two years of training.

The vision is not to show that portrait as pages of analytics. The vision is to give it a voice.

When you open the app in the morning, your data speaks to you. Not a compliment. Not a card stack. Your body's analyst tells you what it sees — the one thing that matters today, grounded in your numbers, contextualized by your plan, informed by your history.

When you finish a run, the effort flows through the pace line in color — cool blues where you were easy, warm amber where you pushed, deep crimson at your limit. You see the shape of your effort, and scattered along that shape are moments where the system noticed something you couldn't feel.

The surface is running. But underneath, the system understands you as a whole person — because your sleep affects your tempo run, your stress affects your recovery, your nutrition affects your long run, and no running app has ever connected those dots for the individual.

**The chart makes you open the app. The intelligence makes you trust it. The voice makes you need it.**

---

## 2. The Moat (Product Strategy)

### The Core Insight

Every other running app gives you roughly the same product on day 1 and day 365. The insights don't compound. The intelligence doesn't accumulate. If you leave and come back, it doesn't remember anything. The product is stateless at the human level.

StrideIQ is the opposite. A product that becomes fundamentally more valuable, more accurate, and more irreplaceable the longer an athlete uses it. After 6 months, leaving means losing your personal physiological model. After 2 years, it's your personal sports science journal built from thousands of data points about your specific body. You cannot export that knowledge to another platform because the knowledge lives in the relationships between your data, not in the data itself.

### What Makes This Uncopyable

The knowledge is structural. It's not stored data — it's learned relationships. A competitor could steal the UI. They cannot steal 2 years of confirmed N=1 findings about a specific human body.

### Priority-Ranked Product Concepts

1. **Pre-Race Fingerprint** — Mine every race in an athlete's history. For each one, extract the full training block signature (16-20 weeks). For any upcoming race, find the closest historical match from their own history. "Your current block most closely matches the 18 weeks before your best race."

2. **Proactive Coach** — A coach that reaches out at the right moment. "Your HRV has been declining for 6 consecutive days while your planned long run is tomorrow. Based on your history, this combination has preceded your worst long runs 3 out of 4 times."

3. **Personal Injury Fingerprint** — Mine every DNS, forced rest week, injury. Find the common pre-injury signature. Run it as a continuous background monitor. "Your body is showing the same pattern it showed in the 3 weeks before your stress fracture in 2022."

4. **Deep Backfill on OAuth Connect** — New athlete connects. 3 years of data. Correlation engine runs. Within minutes: "Every time your HRV dropped below 32ms for 5 consecutive days, your next race was below your capability — that happened 4 times in your history."

5. **Personal Operating Manual** — V2 SHIPPED (Apr 4, 2026). A living document that grows. Race Character, Cascade Stories, interestingness-scored findings, human-language headlines, delta tracking. Promoted to primary navigation.

6. **Correlation Web on Progress Page** — Visual evidence of confirmed N=1 patterns. D3 force-directed graph.

7. **Women's Health Intelligence Layer** — Garmin Women's Health API approved. Cycle-aware training load, recovery, and performance expectations.

8. **Runtoon** (shipped, shareable) — AI-generated personalized run caricature with stats overlay. Every share is an acquisition event.

9. **Masters Athlete Positioning** — Most financially capable segment, deepest Garmin histories. The founder and his 79-year-old father set simultaneous state age group records — first in recorded history.

10. **Cohort Intelligence** — N=1 ecosystem: connect confirmed individual fingerprints, not demographic regression.

---

## 3. The N=1 Philosophy

### Population Approach (What Everyone Else Does)

Aggregate data across thousands of athletes. Compute averages. Tell an individual where they fall on a distribution. "Athletes like you tend to..." The individual is a point in a cloud.

### N=1 Ecosystem Approach (What StrideIQ Does)

Build a complete, individually confirmed fingerprint for each athlete. Each finding is proven for THAT person — "your sleep cliff at 6.2h, confirmed 47 times." Then connect fingerprints at the structural level — always surface the differences alongside the similarities.

The similarity validates: "4 other athletes have individually confirmed the same sleep-response pattern you have." The difference informs: "But your version is more severe — your asymmetric response is 3x, theirs range from 1.5-2x."

This is what makes a fingerprint a fingerprint. Every human has ridges, loops, whorls. The structural categories are shared. No two are alike. The uniqueness IS the identity.

---

## 4. What Is Built — Infrastructure

| Component | Technology |
|-----------|-----------|
| **Web** | Next.js 14 (App Router) |
| **API** | FastAPI (Python 3.11) |
| **Database** | TimescaleDB (PostgreSQL 16) |
| **Workers** | Celery (14 task modules) |
| **Object Storage** | MinIO (S3-compatible) |
| **Cache/Queue** | Redis 7 |
| **Proxy** | Caddy 2 (Auto-TLS) |
| **CI** | GitHub Actions (push: smoke+lint+migration; nightly: full 4,036+ test suite) |
| **Production** | Hostinger KVM 8 (8 vCPU, 32GB RAM) |

### Codebase Scale

| Metric | Count |
|--------|-------|
| SQLAlchemy models | 53 |
| FastAPI routers | 55 |
| Python services | ~120 |
| Celery task modules | 14 |
| Test files | 175+ |
| Passing tests | 4,036+ |
| KB rule evaluator | 445 PASS / 0 FAIL (33 rules × 14 archetypes) |
| Alembic migrations | 95 |
| Correlation engine inputs | 70 |
| React pages | 63 |
| React components | 70 |
| TanStack Query hooks | 21 |
| Intelligence rules | 8 |

---

## 5. What Is Built — Intelligence Pipeline

### Correlation Engine (the core scientific instrument)

Discovers N=1 correlations between inputs and outputs for each individual athlete.

- **70 input signals** across 5 categories: Garmin wearable (14), activity-level (18), feedback/reflection (5), checkin/composition/nutrition (6), derived training patterns (6)
- **9 output metrics:** efficiency, pace_easy, pace_threshold, completion, efficiency_threshold, efficiency_race, efficiency_trend, pb_events, race_pace
- **Statistical gates:** p < 0.05, |r| >= 0.3, n >= 10, Bonferroni correction
- **Time-shifted:** 0-7 day lags (catches "bad sleep → performance drops 2 days later")
- **Confounder control:** explicit confounder map, partial correlation
- **Direction expectations:** sanity checks on known relationships

### Correlation Engine Layers (second-pass analysis on confirmed findings)

| Layer | Capability | Status |
|-------|-----------|--------|
| L1: Threshold Detection | Finds the input value where the correlation changes character ("sleep cliff at 6.2h") | ✅ Built |
| L2: Asymmetric Response | Detects whether bad inputs hurt more than good inputs help ("downside is 3× stronger") | ✅ Built |
| L3: Cascade Detection | Multi-step mechanism chains via partial correlation and mediation | ✅ Built |
| L4: Decay Curves | Full lag profile (0-7 days), half-life, decay classification | ✅ Built |
| L5: Confidence Trajectory | Finding strength over time | Not built |
| L6: Momentum Effects | Block-level matching | Not built |
| L7: Interaction Effects | Multi-input patterns (needs 300+ activities) | Not built |
| L8: Failure Mode Detection | Injury fingerprint | Not built |
| L9: Context Weighting | Situation-specific adjustments | Not built |
| L10: Adaptive Thresholds | Self-updating parameters | Not built |
| L11: Cohort Intelligence | N=1 ecosystem matching | Not built |
| L12: Temporal Population | Cross-ecosystem evolution | Not built |

### Correlation Persistence & Lifecycle

Findings are permanently stored with a full lifecycle:

1. **Upsert on confirm:** Same (athlete, input, output, lag) → `times_confirmed += 1`
2. **Lifecycle states:** `emerging` → `active` → `resolving` → `closed` (or `structural`)
3. **Surfacing gate:** Only findings with `times_confirmed >= 3` are eligible
4. **Transition detection:** `active` → `resolving` when recent |r| drops below 0.30. `resolving` → `closed` after 4-week window without reassertion. `resolving` → `active` if correlation reasserts.
5. **Next frontier scan:** When a finding closes, identifies the next-highest-priority emerging candidates

### Limiter Engine (Phases 1-5 Complete)

Translates correlation findings into personalized training plan modifications:

1. **Fingerprint Bridge** — Structural traits (recovery half-life) modify spacing, cutback frequency, quality caps
2. **Temporal Weighting** — L30: 4×, L31-90: 2×, L91-180: 1×, >180d: 0.5× (weakens old solved-problem correlations)
3. **Lifecycle Classifier** — Every finding gets a lifecycle state; plan engine reads only `active` limiters
4. **Coach Integration** — `emerging` findings surfaced as natural language questions; athlete answers drive lifecycle promotion
5. **Transition Detection** — Self-correcting lifecycle. Resolving/closed transitions when recent data changes

### AutoDiscovery Engine (Phases 0A-0C Complete)

Nightly Bayesian research engine that autonomously discovers new patterns:

- **Multi-window rescan** (30/60/90/180/365/full-history)
- **Pairwise interaction loop** — median-split testing, Cohen's d effect size
- **Registry tuning loop** — step-up/step-down parameter exploration
- **Finding Quality Score (FQS)** — multi-component scoring for candidate ranking
- **Durable candidate memory** — recurring shadow candidates tracked across runs
- **Founder review state machine** — approve/reject/defer/stage with full audit trail
- **Controlled promotion staging** — four explicit promotion targets, staging is label-only

### Daily Intelligence Engine (8 Rules)

| Rule | Mode | Trigger |
|------|------|---------|
| LOAD_SPIKE | INFORM | Volume/intensity up >15% week-over-week |
| SELF_REG_DELTA | LOG | Planned workout ≠ actual |
| EFFICIENCY_BREAK | INFORM | Efficiency improved >3% over 2 weeks |
| PACE_IMPROVEMENT | INFORM | Faster pace + lower HR vs target |
| SUSTAINED_DECLINE | FLAG | 3+ weeks declining efficiency |
| SUSTAINED_MISSED | ASK | >25% skip rate over 2 weeks |
| READINESS_HIGH | SUGGEST | High readiness + easy-only for 10+ days |
| CORRELATION_CONFIRMED | INFORM | Reproducible check-in → performance pattern (3+ confirmations) |

### Living Fingerprint Pipeline

1. **Weather Normalization** — Magnus formula dew point + combined value heat model. Personal heat resilience score. All pace comparisons heat-adjusted.
2. **Shape Extraction** — 1,331 lines pure computation. Per-second stream → phases, accelerations (dual-channel: velocity + cadence), classification (easy_run, progression, tempo, fartlek, strides, threshold_intervals, speed_intervals, hill_repeats, long_run).
3. **Investigation Registry** — 15 registered investigations with signal coverage and honest gap reporting.
4. **Finding Persistence** — One active finding per investigation×type. Supersession logic.

### N=1 Plan Engine V3

Diagnosis-first architecture. Legacy generators deleted (-16,920 lines). New engine (1,078 lines):

1. Diagnose adaptation needs from athlete state and goal distance (6 needs: ceiling, threshold, durability, race-specific, neuromuscular, aerobic base)
2. Select training tools from KB variant library
3. Set dosage and progression
4. Schedule anchor sessions first
5. Fill with purposeful easy running
6. Phases are labels applied AFTER the plan is built

Validated against 14-archetype evaluator: 445 PASS, 0 FAIL (33 KB rules). 7-day athlete support, tune-up race handling, athlete-specified taper preference.

### Adaptive Re-Plan (N1 Engine Phase 4)

Plans adapt to reality. Three triggers: missed long run, 3+ consecutive missed days, 5+ days of low readiness. Generates constrained 2-week micro-plan via existing N1 engine. Day-level diff for athlete approval. Guiding principle: "The system INFORMS, the athlete DECIDES."

### AI Coach

- Universal Kimi K2.5 routing (Moonshot AI) with Claude Sonnet fallback
- 24 tools that query every intelligence system
- Athlete-calibrated tone (experience-based coaching posture)
- Data-verification discipline (must call tools before citing performance data)
- Model audit trail in every chat message
- Athlete fact extraction from conversations (coach memory)
- Tappable briefing → coach flow with finding deep links

### Athlete Fact Extraction (Coach Memory)

Facts extracted from coach conversations. Concurrency-safe upsert. Incremental extraction via checkpoint. Active facts injected into coach prompts, morning voice, and briefing prompts.

### Experience Guardrail

25 daily assertions across 6 categories: Data Truth, Language Hygiene, Structural Integrity, Temporal Consistency, Cross-Endpoint Consistency, Trust Integrity. Runs daily via Celery beat.

---

## 6. What Is Built — Athlete-Facing Product

### Home Page
- Gradient pace chart hero
- Morning voice briefing (LLM-generated, finding-aware, per-field lane injection)
- Wellness Row: Recovery HRV + Overnight Avg HRV + Resting HR + Sleep (all with personal 30-day ranges, explanation tooltip)
- Tappable coach-noticed text with finding deep links (→ opens coach chat with pre-loaded context)
- Quick check-in with mindset fields (enjoyment, confidence)
- Compact 30-day PMC chart (Fitness/Fatigue/Form)
- Today's workout with pace guidance
- Race countdown
- Weekly activity chips with cross-training sport icons
- Adaptation proposal card (accept/reject plan adjustments)

### Activity Detail Page
- **Runs:** Run Shape Canvas with gradient effort-colored pace line, weather context with heat adjustment, finding annotations (top 3 correlation findings), Runtoon card, splits table, analysis
- **Cycling:** Duration, distance, avg speed, elevation, HR
- **Strength:** Exercise sets grouped by movement pattern with sets × reps × weight, estimated 1RM, volume distribution, session type badge. Data sourced from Garmin FIT files via Activity Files webhook pipeline.
- **Hiking:** Elevation gain hero, distance, speed, HR
- **Flexibility:** Duration, HR if available
- **Universal:** "Going In" wellness stamps (pre-activity Recovery HRV, RHR, sleep), Training Load card (TSS + weekly context), title editing

### Personal Operating Manual (`/manual`) — Primary Navigation
Four sections:
1. **Race Character** — The single most important insight. Pace-gap analysis comparing race vs training performance. Race-day counterevidence identifies where the athlete performs well despite adverse conditions. "During training, sleep below 7h precedes lower efficiency. On race day, you override this."
2. **Cascade Stories** — Multi-step correlation chains (input → mediator → output) surfaced as mechanism narratives
3. **Highlighted Findings** — Interestingness-scored: cascade chains first, race character second, threshold findings third
4. **Full Record** — Complete finding list with human-language headlines, delta tracking via localStorage

### Progress Page
- D3 force-directed correlation web (interactive, hover evidence panels)
- Expandable proved facts with confidence tiers (emerging/confirmed/strong)
- Coach-voice hero with animated CTL stats

### Coach Chat
- AI coach with 24 intelligence tools
- Universal Kimi K2.5 model
- Finding-aware context loading via deep links from briefing
- Athlete fact extraction from conversations

### Training Load
- PMC chart (CTL/ATL/TSB) with N=1 personalized zones
- Cross-training TSS disclosure with expandable 7-day breakdown by sport

### Analytics
- Efficiency trends, load-response, correlations
- Trends summary (absorbed from `/trends`) with root cause analysis

### Calendar
- Training calendar with plan overlay, color coding, weekly mileage

### Runtoon (Share Your Run)
- AI-generated personalized caricature (Gemini image model)
- AI-generated caption with quality gates
- Pillow text overlay (stats line, caption, watermark)
- 9:16 Stories format for social sharing
- Web Share API (native share sheet on iOS/Android)
- On-demand generation (triggered by share, not by sync)

### Public Tools (no-auth, SEO acquisition)
- Training pace calculator
- Age-grading calculator
- Race equivalency calculator
- Heat-adjusted pace calculator
- Boston qualifying tools

---

## 7. What Is Built — Data Model (53 Tables)

### Key Models
- **Activity** — Ingested from Strava/Garmin. 6 sports (run, cycling, walking, hiking, strength, flexibility). Cross-training columns, pre-activity wellness stamps, run shape JSONB, heat adjustment.
- **CorrelationFinding** — Persistent N=1 correlation discoveries. 14 enrichment columns (threshold, asymmetry, decay, mediators). Lifecycle states. Times confirmed.
- **AthleteFinding** — Investigation-level findings with supersession.
- **AthleteFact** — Coach memory. Facts extracted from conversations.
- **DailyReadiness** — Composite readiness score.
- **RuntoonImage** — AI-generated caricature with attempt tracking.
- **PlanAdaptationProposal** — Pending/accepted/rejected plan adjustments.
- **AutoDiscoveryRun/Experiment/Candidate/ChangeLog** — Autonomous discovery infrastructure.
- **ExperienceAuditLog** — Daily experience guardrail results.

### Integrations
- **Strava:** OAuth + webhook + sync + background ingest
- **Garmin Connect:** OAuth + webhook ingest (6 sports) + GarminDay health storage + ingestion monitoring + Activity Files webhook (FIT file download for exercise set data). Production environment approved.
- **Stripe:** Hosted checkout + portal + webhook entitlements for 4-tier monetization

---

## 8. What Is Built — Background Tasks (Nightly Pipeline)

| Time (UTC) | Task | Purpose |
|------------|------|---------|
| 04:00 | AutoDiscovery nightly | Autonomous pattern discovery across multiple time windows |
| 04:00+ | Morning intelligence | Readiness + 8 intelligence rules + narration (then every 15 min) |
| 06:00 | Fingerprint refresh | Living fingerprint recalculation |
| 06:15 | Experience guardrail | 25 assertions across 6 categories |
| 07:00 | Garmin ingestion health | Ingestion coverage monitoring |
| 08:00 | Daily correlation sweep | Full correlation analysis + layer enrichment + transition detection |

Pipeline is deployment-proof: beat startup dispatch ensures tasks fire on container restart if they haven't run recently.

---

## 9. Design Philosophy

### Visual First, Narrative Bridge, Earned Fluency

Every intelligence surface follows a 7-step sequence:
1. Visual catches the eye
2. The athlete interacts (hover, tap, explore)
3. Wonder forms ("what does this mean?")
4. The narrative answers (below the visual, specific numbers)
5. Understanding deepens (athlete returns to visual with new eyes)
6. Trust is judged ("does this match what I felt?")
7. Fluency becomes habit (visual alone is enough over time)

### Key Design Principles
- **Never hide numbers.** Athletes track trends, research, compare. The magic is making data understandable to a 79-year-old AND meaningful to an elite — by layering interpretation on raw data, not replacing it.
- **Suppression over hallucination.** If uncertain, say nothing.
- **The athlete decides, the system informs.** Never override the athlete.
- **No template narratives.** Either say something genuinely contextual or say nothing at all.
- **Templates are trust-breaking.** The moment an athlete sees the same sentence twice with different numbers plugged in, the magic dies.

---

## 10. The Fingerprint Visibility Roadmap

### Path A: The Literacy Program (SUBSTANTIALLY SHIPPED)
Uses screens the athlete already visits. Surfaces fingerprint intelligence through better versions of familiar patterns:
- ✅ Weather-adjusted effort coloring on pace charts
- ✅ Finding annotations on activity detail
- ✅ Finding-aware morning voice
- ✅ Home page finding rotation with micro-visual
- ✅ Personal Operating Manual V2 (Race Character, Cascades, Highlighted, Full Record)
- ✅ Wellness Row with dual HRV and personal ranges
- ✅ Activity wellness stamps
- ✅ Manual in primary nav

### Path B: The Dream (Future — Design Phase)
New visual paradigms requiring new literacy:
- **Fingerprint Organism** — dark canvas, organic form shaped by the athlete's response curves, filament brightness = finding confidence
- **Training Landscape** — training history as topography (elevation = load, width = volume, color = adaptation)
- **Run Signatures** — every run produces a unique data portrait
- **Morning Pulse** — fingerprint subtly different from yesterday
- **Race Canvas** — Pre-Race Fingerprint as spatial overlay

Path B gates on data sufficiency AND finding diversity (≥8 active findings spanning ≥3 physiological domains).

### The Reconnection Moment
The acceptance test for the dual pathway: the athlete taps a fingerprint filament and RECOGNIZES a finding they've been seeing on their activity pages for weeks. They already knew. The form just showed them WHERE this finding lives relative to everything else.

---

## 11. The Father-Son Story

The founder (50s) and his 79-year-old father both use StrideIQ. They set simultaneous state age group records — first in recorded history. A 79-year-old athlete setting state records coached by AI and a correlation engine is the most powerful demonstration of the product.

---

## 12. Competitive Landscape

No running app does what StrideIQ does:
- **Strava:** Social network. Shows line charts. No intelligence.
- **Garmin Connect:** Device dashboard. Five disconnected panels. Body Battery is notoriously unreliable.
- **Runna:** Gives you a workout. No personalization beyond pace zones.
- **Athletica/Runalyze:** Training load analytics. Population-level models.
- **TrainingPeaks:** PMC/TSS tracking. No N=1 correlation discovery.
- **Whoop:** Recovery scores from population models. Not N=1.

The competitor who appeared with something similar matches population patterns. They cannot match the N=1 confirmation cycle. The moat isn't the algorithm — it's the accumulated evidence, rendered as a visual identity unique to each athlete.

---

## 13. What No One Else Has

These capabilities exist in production today:

1. **N=1 Correlation Engine with 70 inputs** — Discovers personal correlations between sleep, stress, training patterns, and performance for each individual. Not population averages. Confirmed per person.

2. **4-Layer Enrichment on Confirmed Findings** — Every correlation gets threshold detection ("your sleep cliff is at 6.2h"), asymmetric response analysis ("bad sleep hurts 3× more than good sleep helps"), cascade detection (multi-step mechanism chains), and decay curves (half-life of effects).

3. **Lifecycle-Managed Findings** — Findings emerge, get confirmed, can resolve when the athlete solves the problem, and close. The system knows when a pattern is no longer active. Next-frontier scanning identifies new constraints when old ones resolve.

4. **Race Character Analysis** — Compares training-day patterns against race-day patterns. Identifies where the athlete overrides their own physiology on race day. "During training, sleep below 7h precedes lower efficiency. On race day, you override this." This is character, not a correlation.

5. **Autonomous Discovery (AutoDiscovery)** — Nightly engine that autonomously explores new pattern spaces, pairwise interactions, and parameter tuning without human direction.

6. **Diagnosis-First Plan Engine** — Plans built from athlete's actual physiological needs, not from templates. 33 KB rules × 14 archetypes validated. Plans adapt to reality via 2-week micro-plans with athlete approval.

7. **Pre-Activity Wellness Stamps** — Every activity is stamped with the athlete's sleep, HRV (two values), and resting HR from that morning. This creates the dataset for wellness-vs-performance research at the individual level.

8. **Coach with Finding Deep Links** — Tappable briefing text opens coach chat with pre-loaded finding context. The coach has 24 tools that query every intelligence system. Model audit trail on every message.

9. **AI-Generated Personalized Run Caricature (Runtoon)** — Contextual scene generation based on actual run data, with Pillow-overlaid stats. Shareable. Every share is an acquisition event.

10. **Shape Extraction** — Per-second stream data decomposed into phases, accelerations, and classifications. Dual-channel detection (velocity + cadence).

11. **Personal Heat Resilience Score** — Not generic heat calculators. Personal threshold based on the athlete's own history at specific dew points.

12. **6-Sport Cross-Training Integration** — Not just running. Cycling, hiking, strength, flexibility, walking all integrated with sport-aware TSS, activity detail pages, and correlation engine inputs.

---

*This document consolidates: Product Manifesto, Product Strategy, Site Audit, Fingerprint Visibility Roadmap, and Design Philosophy. Source documents live in `docs/` for full detail.*
