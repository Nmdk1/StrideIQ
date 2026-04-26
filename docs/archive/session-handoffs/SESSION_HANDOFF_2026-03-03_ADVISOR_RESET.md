# Session Handoff — Advisor Reset
**Date:** March 3, 2026
**Outgoing role:** Builder/advisor (terminated for trust failure)
**Incoming role:** New advisor — clean slate

---

## Why This Handoff Exists

The founder fired the previous advisor after a failed progress page implementation. The builder followed a bad spec mechanically, added a wall of generic cards on top of a focused page the founder had already built, deployed it to production, and only realized it was wrong when the founder showed screenshots. The revert cost real money in wasted compute. Trust is at zero.

The new advisor starts fresh. Read everything below before engaging.

---

## Read Order (Non-Negotiable)

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how to work with this founder. Every rule is a bright line. Read every word.
2. `docs/PRODUCT_MANIFESTO.md` — what StrideIQ is. The product gives an athlete's body a voice by connecting training, sleep, stress, and recovery. 150+ intelligence tools, N=1 correlation engine, single morning voice. The engine is built; the work is making it speak clearly.
3. `docs/PRODUCT_STRATEGY_2026-03-03.md` — the moat is compounding intelligence. The correlation engine is the root. Every feature flows from it producing true, specific, actionable findings about a single human.
4. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — the design principle that was violated. **Visual First, Narrative Bridge, Earned Fluency.** Visual catches the eye → athlete interacts → wonder forms → narrative answers → understanding deepens → trust is judged → fluency becomes habit. The narrative teaches the athlete to read the chart. Without it, the visual is opaque. Without the visual, the narrative is forgettable. Together they build the moat.
5. `docs/specs/CORRELATION_ENGINE_ROADMAP.md` — 12-layer engine roadmap. Layers 1-4 are shipped. Layers 5-12 are the long-term moat.
6. `docs/TRAINING_PLAN_REBUILD_PLAN.md` — build priorities, phase gates, what's shipped vs gated.
7. This document — what just happened and what's broken.

---

## What Just Happened (The Failure)

### The Problem
The progress page is empty for athletes without correlation findings. The founder's father has 414 activities and sees: a hero, a progress bar, and an "Ask Coach" button. Nothing else. The backend endpoint `GET /v1/progress/narrative` returns rich activity-derived data (PBs, volume, efficiency, training load, race readiness). It was never connected to the frontend.

### The Bad Spec
`docs/specs/PROGRESS_NARRATIVE_WIRING_SPEC.md` was written to fix this. Its approach:
- Map 8 visual components to chapter topics in cards
- Render each chapter as: visual component + observation text + interpretation + action
- Stack them vertically between the hero and the correlation web

### What Actually Happened
The builder followed the spec and produced a wall of generic cards:
- Sparkline showing "0.0 → 0.0" (efficiency values too small for display)
- Bar chart with "Weekly volume: 8.0mi this week. 60% vs 4 week average." (a fact, not coaching)
- Gauge showing "+2.9 Normal Training" (unexplained)
- StatHighlight with "New 30K PB: 2:47:49 on Feb 08." (data, not narrative)
- LLM-generated interpretation rendered as small italic text below charts nobody can read

This is exactly the pattern the founder killed when they replaced the old progress page (12 generic text cards) with the current focused page (hero + correlation web + proved facts + recovery fingerprint). The builder rebuilt the card wall on top of the good page.

### What Was Reverted
- Commit `48974fb` added the card wall
- Commit `69f7b5f` reverted it
- Both are pushed and deployed. Production is back to the pre-failure state.
- Three new component files were created and deleted: `VerdictSection.tsx`, `ChapterCard.tsx`, `LookingAhead.tsx`

### The Spec Is Wrong
`docs/specs/PROGRESS_NARRATIVE_WIRING_SPEC.md` should be rewritten or deleted. Its fundamental error: it treats narrative as decoration on top of visuals. The design philosophy says the opposite — the visual creates the question, the narrative answers it. The spec produced cards with charts and one-liner captions. That's not narrative. That's a dashboard.

---

## Current Production State

### Progress Page (What the Athlete Sees)
The page calls `useProgressKnowledge()` only. Layout:
1. **Hero** — headline, subtext, stats (fitness then/now, days out or patterns found)
2. **Correlation Web** — D3 force graph (only if findings exist)
3. **Patterns Forming** — progress bar (only if no findings but check-ins exist)
4. **What the Data Proved** — expandable fact list with confidence tiers
5. **Recovery Fingerprint** — Canvas 2D animated recovery curves
6. **Ask Coach CTA**
7. **Data coverage footer** — patterns, confirmed, check-ins

**For athletes WITHOUT correlation findings:** Hero + patterns forming bar + Ask Coach. That's it. The page is empty. This is the #1 UX problem.

### Backend Data Available But Not Surfaced
`GET /v1/progress/narrative` returns for the father's account (zero correlations):
- **Verdict:** rising fitness, 8 sparkline points [11.7→32.5], confidence high
- **4 chapters:** Personal Best, Volume Trajectory, Efficiency Trend, Training Load — each with LLM-generated `interpretation` and `action` text
- **Looking ahead:** race variant (10K Starter Plan, 60 days, readiness 68.6%)
- **Coverage:** 36 activity days, 23 check-ins, 32 Garmin days

This data is real and populated. The question is HOW to surface it — not whether to.

### What's Healthy
- All 7 containers running (api, web, worker, postgres, redis, minio, caddy)
- All test suites passing (verified this session: coach_quality 28, correlation_quality 14, progress_knowledge 15, progress_narrative 14, effort_classification 32, correlation_layers 25, and others)
- CI green
- Recent ships all stable: readiness relabel, effort classification, correlation layers 1-4, briefing cooldown

---

## Recent Ship History (Last 2 Weeks)

| Date | Commit | What Shipped |
|------|--------|-------------|
| Mar 3 | `69f7b5f` | Revert progress page wiring (this failure) |
| Mar 3 | `c7c7578` | Rename motivation_1_5 → readiness_1_5 everywhere + finding-level briefing cooldown (72h Redis TTL) + one-new-thing prompt rule |
| Mar 3 | `085a878` | Correlation engine layers 1-4 (threshold, asymmetry, decay, cascade) |
| Mar 3 | `8885c9e` + `dab42c5` | Tier 0 TPP effort classification (pace-first, HR confirms) |
| Mar 3 | `25a8a96` | Progress page fixes: hero layout, no-race mode, acronym enforcement |
| Mar 3 | `8ad62e2` | Interval detection fix, CI green restoration |
| Mar 2 | Various | Progress Knowledge v2 (hero, correlation web, what data proved), Recovery Fingerprint |
| Mar 1 | Various | Runtoon share flow, correlation quality fix (confounder control) |

---

## The Unsolved Problem

**How do you make the progress page useful for athletes who have activity data but no correlation findings?**

The data exists. The endpoint works. The visual components exist (8 of them). The question is design — how to present activity-derived intelligence (volume trends, efficiency changes, PBs, training load, race readiness) without creating a card wall.

The design philosophy gives the answer pattern: visual catches eye → narrative teaches → fluency builds. But the previous spec inverted this (visual as primary, narrative as afterthought) and the result was a dashboard, not intelligence.

What the founder wants (inferred from their reactions and the design philosophy):
- NOT a card per metric
- NOT charts with one-liner captions
- NOT a dashboard
- The narrative IS the page. The visual supports the narrative, not the other way around.
- One coached interpretation that synthesizes multiple signals, with a visual anchor that the narrative teaches you to read
- If there's nothing genuinely useful to say, say nothing. Silence over slop.

This is the problem the new advisor needs to solve WITH the founder, not FOR them. Discuss first. Do not spec. Do not build. Discuss.

---

## Architecture Quick Reference

| Layer | Key Files | Notes |
|-------|-----------|-------|
| Correlation Engine | `services/correlation_engine.py` | Bivariate Pearson, 0-7 day lags, partial correlation, 9 output metrics |
| Correlation Layers | `services/correlation_layers.py` | Threshold, asymmetry, decay, cascade — second pass on confirmed findings |
| Effort Classification | `services/effort_classification.py` | TPP (primary) + HR (confirming), 3-tier fallback |
| Coach Briefing | `routers/home.py` | Morning voice, finding cooldown (72h Redis), one-new-thing rule |
| Progress Knowledge | `routers/progress.py` → `/v1/progress/knowledge` | Hero, correlation web, proved facts, recovery curve |
| Progress Narrative | `routers/progress.py` → `/v1/progress/narrative` | Verdict, chapters, patterns, looking ahead (NOT wired to frontend) |
| Frontend Progress | `apps/web/app/progress/page.tsx` | Only calls knowledge endpoint. Narrative hook exists but unused. |
| Visual Components | `apps/web/components/progress/` | 8 components built: BarChart, SparklineChart, HealthStrip, FormGauge, CompletionRing, StatHighlight, PairedSparkline, CapabilityBars |

---

## Founder Communication Notes

- The founder is a competitive runner (57 years old, ran in college, still competes). They have deep domain expertise.
- Short messages are not dismissive. "discuss" means deep discussion. "no code" means absolutely no code.
- They will challenge your reasoning. Engage honestly. Push back with evidence if you disagree.
- They are building this for themselves, their father, and eventually other serious runners.
- The father's account (`wlsrangertug@gmail.com`) is the acid test — 414 activities, zero correlations, the page must be useful for him.
- The founder's account (`mbshaf@gmail.com`) has rich data — 8 active correlation findings, 2 personal patterns, race in 11 days.
- **Do NOT start coding when you receive a feature.** Discuss → scope → plan → test design → build. If the founder says "discuss," they mean discuss.
- **Show evidence, not claims.** Paste output. Paste screenshots. "It should work" is not acceptable.
- **Suppression over hallucination.** If uncertain, say nothing.

---

## What the New Advisor Should Do First

1. Read the documents in the read order above.
2. Open the progress page in a browser for both accounts (founder and father) to see the current state.
3. When the founder is ready to discuss: listen. They know what they want. The design philosophy document articulates it clearly. The problem is translating "Visual First, Narrative Bridge" into a concrete design for the progress page that doesn't produce a card wall.
4. Do not propose the same approach (cards with visuals + observation text). It was tried. It failed.
5. Do not write a spec until the founder says "write the spec."

---

## Server / Deploy Reference

- **Server:** root@187.124.67.153 (Hostinger KVM 8 — 8 vCPU, 32GB RAM)
- **Repo:** /opt/strideiq/repo
- **Deploy:** `cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build`
- **Container names:** strideiq_api, strideiq_web, strideiq_worker, strideiq_postgres, strideiq_redis, strideiq_minio, strideiq_caddy
- **Logs:** `docker logs strideiq_api --tail=50`
- **Token generation:** See `docs/FOUNDER_OPERATING_CONTRACT.md` or `.cursor/rules/production-deployment.mdc`
