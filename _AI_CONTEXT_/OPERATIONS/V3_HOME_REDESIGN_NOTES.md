# V3 Home Page Redesign — Coach-First Layout

**Status:** Deferred from V2. Revisit after V2 phases complete.

## Core Problem (V2 still has this)

The home page layout is a traditional card-based dashboard. Coaching voice is crammed into the same UI pattern that Garmin, Strava, TrainingPeaks, and every other fitness app uses. The medium contradicts the message — it says "coach" but looks "dashboard."

## V3 Vision: The Coach Speaks First

### Above the fold — ONE coaching narrative

When the athlete opens the app, they see a message from their coach. Not cards. Not widgets. A flowing paragraph that weaves together:

- Key insight (what the coach noticed)
- Reaction to check-in state (if checked in)
- Today's workout context and focus
- Week trajectory
- Race readiness (if applicable)

Example:

> "Your pacing on yesterday's 16-miler was elite-level — -0.1% decay. You're feeling fine with mild soreness, which is exactly where you should be in week 3 of the rebuild. Today's another long easy effort — 16 miles, 8:14 pace. Focus on staying relaxed through miles 10-14 where fatigue usually creeps in. You're 39.9 of 37.2 miles this week, slightly ahead — don't let enthusiasm become overtraining with Tobacco Road 35 days out."

One voice. One flow. Data woven into narrative, not separated into labeled boxes.

### "Reply to Coach" button

Deep-links to `/coach` with context pre-loaded. The home page becomes the opening of a conversation, not a static display.

### Below the fold — Supporting detail (secondary)

- Quick check-in (if not done)
- Today's workout card (collapsible — distance, pace, details)
- This week chart (day chips + progress bar — data viz, not narrative)
- Race countdown (days + stats)

Cards become reference material. The coaching voice is the product.

## Backend Changes

- Replace 5 separate `coach_briefing` JSON fields with ONE field: `daily_briefing` — a single coaching paragraph
- Same Gemini call, same data context, same Redis cache
- Prompt changes to request flowing prose instead of structured sections

## Frontend Changes

- Hero section: large text, generous spacing, coach avatar/icon, the briefing as dominant visual
- Cards demoted below fold, collapsible by default on mobile
- "Reply to Coach" CTA prominent
- Typography: larger base size for the briefing, distinct from card text

## Design Principles

1. Opening the app should feel like checking a message from your coach, not opening a dashboard
2. Data supports narrative, not the other way around
3. No resemblance to existing fitness app patterns
4. The coach's voice is the product — everything else is supporting material

---

# V3 Progress Page: Personal Bests in Context

**Status:** Deferred from V2. PB table is functional — this is about coaching framing.

## Core Problem

The PB section is a raw table of times and dates. The ADR says it should be "coaching framing, not a table." The interesting question isn't "what are my PRs" — it's "what do they mean NOW."

## V3 Vision: PBs Organized by Relevance

### Recent PBs (last 90 days) — "What Worked"

Celebrate + analyze. What training conditions produced this PR? Can you replicate them?

> "You set your 10K PR (39:14) 8 weeks ago during consistent 45mi weeks and 7h sleep. You're still in that groove — a 5K PR attempt might be ripe."

Uses `get_pb_patterns()` for historical conditions (TSB, volume, sleep at time of PR).

### Older PBs (3-12 months) — "Are You Close to Breaking It?"

Compare current race predictions against the PR. The gap is the insight.

> "Your half marathon PR is 1:27:14 from November. Current prediction: 1:25:xx. You're fitter now than when you set it."

Uses `get_race_predictions()` for current projections vs stored PB times.

### Ancient PBs (1-2 years) — "Benchmarks"

Pure context. How does current fitness compare to when these were set?

> "You've never broken 39:14 for 10K. Current projection: 38:xx — this might be the block where it falls."

## Data Sources (all exist)

- `get_pb_patterns()` — TSB, volume, training patterns before each PB
- `get_race_predictions()` — current race time projections
- `build_athlete_brief()` — current state for comparison
- `PersonalBest` model — PR times, dates, activity links

## Implementation Notes

- Group PBs by recency tier, not by distance
- Each tier gets different coaching treatment
- Consider LLM narrative per tier (like home briefing) vs deterministic templates
- Raw table can remain as collapsible "All PBs" detail below the coaching framing

---

---

# Phase 4: Coach as Primary Experience

**Status:** Approved. Build after PB fix deployment.

## Core Thesis

The coach is the product. Everything else is supporting material. The athlete opens StrideIQ and they're talking to their coach — not looking at a dashboard with a chat feature buried in a tab. The 150+ coach tools and years of data make this the natural language interface to their training. The goal: make it so valuable that athletes depend on it daily, and price accordingly.

## Deliverables

### 1. Structured Suggestions — Coach's Daily Agenda

**Problem:** Current suggestions are static category tiles ("PR Analysis", "Training Load") generated by keyword-matching raw LLM prompt strings. They look the same every visit regardless of what's happening.

**Fix:** Backend returns `{ title, description, prompt }` with real athlete data baked into title/description. Frontend becomes a dumb renderer. Examples:

- "You PRed your 10K last Saturday" / "TSB was -8, similar to your other 2 PRs. Is there a fatigue sweet spot?"
- "TSB is -32 — you're digging deep" / "ATL 42 vs CTL 31. Should we ease up before Tobacco Road?"
- "Today's 8mi easy run" / "You ran 8:12/mi at 142bpm — want a full breakdown?"
- "38 days to Tobacco Road" / "Current projection: 3:21. What should race week look like?"

Delete `buildSuggestionCard()` and `getSuggestionIcon()` from frontend entirely.

### 2. Coach Brief as Empty State

**Problem:** Empty state is a generic greeting: "Hi — I'm your StrideIQ Coach. I don't guess..."

**Fix:** Replace with the coach's actual read on your current state, pulled from `/v1/progress/summary`. The coach speaks first with your real numbers. Not a greeting, not a placeholder — a condensed briefing.

### 3. Desktop Context Panel

**Problem:** Desktop sidebar is just "Try one of these" with suggestion cards.

**Fix:** Add compact metric rows above suggestions — CTL, TSB, durability, race countdown, weekly volume. Your data visible alongside the conversation at all times. Reduces "what's my CTL?" messages to zero.

### 4. Deep Link Reception (`?q=`)

**Problem:** Home and Progress have "Ask Coach" links pointing to `/coach?q=...` but the coach page ignores the query param.

**Fix:** On mount, read `q` from URL search params. Set as input value. Don't auto-send — athlete taps send when ready. Every "Ask Coach" link across the site actually works.

### 5. Navigation Weight Shift

**Problem:** Coach is one tab among four with equal weight.

**Fix:** Coach gets visual prominence as center tab / primary experience. Other pages still accessible but coach is the gravitational center.

## Files Touched

- `apps/api/services/ai_coach.py` — `get_dynamic_suggestions()` returns structured objects
- `apps/web/app/coach/page.tsx` — empty state brief, context panel, `?q=` param, delete buildSuggestionCard
- `apps/web/lib/hooks/queries/progress.ts` — reuse `useProgressSummary` (already exists)
- `apps/web/app/components/BottomTabs.tsx` — coach tab visual prominence

## Files NOT Touched

- `apps/api/routers/ai_coach.py` — endpoint wrapper, minimal change
- Chat streaming, history, evidence, proposals — zero changes
- `apps/api/services/coach_tools.py` — tools stay as-is

---

## Dependencies

- V2 Phase 3 complete (Progress page functional with PB table)
- PB merge fix deployed (Garmin PBs no longer wiped by Strava sync)
- User feedback on V2 coaching voice quality to inform prompt tuning

---

# Phase 5: LLM-Generated Coach Observations (Kill All Templates)

**Status:** Next. Supersedes Phase 4 Deliverable #1 (structured suggestions).

## Core Problem

Phase 4 replaced generic suggestion titles with data-driven titles, but the prompts are still templates. `if tsb > 20: show("you're fresh")` is the same card for every athlete with positive TSB. A template is a template no matter how well the copy reads. Every template breaks the N=1 promise.

A real coach doesn't have 6 pre-written cards. They look at YOUR data and decide what's worth talking about. The suggestions must be LLM-generated, not template-selected.

## Design

### Trigger
After every activity sync (Strava webhook or Garmin import), fire a lightweight async task.

### Task: `generate_coach_observations`
1. Gather a compact data snapshot via existing coach_tools:
   - `get_training_load` (current CTL/ATL/TSB + zone)
   - `get_recent_runs` (last 3-5 runs with pace/HR/distance)
   - `get_pb_patterns` (any recent PRs)
   - `get_active_insights` (system-generated insights)
   - `get_efficiency_by_zone` (threshold trend)
   - Goal race info (name, date, days out)
   - Current plan week (if active plan)
2. Send to Gemini Flash with a system prompt:
   > You are an elite running coach reviewing this athlete's latest data.
   > Write 3-5 short observations — things you'd mention if they walked
   > in the door right now. Each observation must be specific to THIS
   > athlete's data (not generic coaching advice). Focus on: what changed,
   > what's surprising, what needs attention, what's going well.
   > Return JSON array: [{title, description, prompt}]
   > - title: 8 words max, specific (not "How's training going")
   > - description: 1 sentence, references actual numbers/dates
   > - prompt: the question the athlete would ask to explore this
3. Store result in a new `coach_observations` table or a JSON column on Athlete.
4. `/v1/coach/suggestions` serves stored observations instead of running template logic.

### Cost
- 1 Gemini Flash call per activity sync (~$0.001)
- No LLM call on page load (served from cache)
- Observations refresh naturally with each new activity

### What Dies
- `get_dynamic_suggestions()` template logic (the entire if/elif tree)
- `getSuggestionIcon()` frontend mapping (LLM can specify icon hint)
- All hardcoded suggestion prompts

### What Stays
- `SuggestionButton` component (renders whatever the backend sends)
- Coach brief empty state (from progress data, not suggestions)
- Desktop context panel (live metrics, independent of suggestions)

## Files
- `apps/api/tasks/coach_observation_tasks.py` — new async task
- `apps/api/services/ai_coach.py` — replace `get_dynamic_suggestions()` with DB read
- `apps/api/routers/ai_coach.py` — `/v1/coach/suggestions` reads from stored observations
- Model/migration for observation storage

---

# Phase 6: Dual-Layer What's Working + Visualization Upgrade

**Status:** Layer 1 built. Visualization research complete.

## What Was Built

### Dual-Layer What's Working / What's Not

The Progress page now shows TWO layers of intelligence:

**Layer 1 — Training Patterns (always available):**
- Source: `InsightAggregator.get_athlete_intelligence()` via new `/v1/progress/training-patterns` (no tier gate)
- Analyzes: activity data only (frequency, volume, intensity, clustering, consistency)
- Available day one with any activity history
- Example: "Consistency (last 12w): ≥4 runs in 9/12 weeks"

**Layer 2 — Personal Correlations (grows with check-ins):**
- Source: Correlation Engine via `/v1/correlations/what-works`
- Analyzes: check-in data (sleep, soreness, motivation) correlated against efficiency
- Requires 10+ check-ins per variable to produce results
- Example: "Sleep > 7h → 12% better efficiency (r=0.6, n=23)"

**When Layer 2 isn't ready:** Shows a progress bar with `{checkin_count}/{checkins_needed} check-ins` and explains what daily check-ins will unlock. The athlete sees their N=1 model building.

**Injury Patterns:** Now shown as a dedicated section when InsightAggregator detects risk patterns (ramp rate, return-to-run gaps, phase context).

### Files Changed
- `apps/api/routers/progress.py` — new `/v1/progress/training-patterns` endpoint
- `apps/web/lib/hooks/queries/progress.ts` — new `useTrainingPatterns` hook
- `apps/web/app/progress/page.tsx` — dual-layer rendering with progress indicator

## Page Retention Decisions

**Training Load page (`/training-load`):** KEEP. The dedicated load page with its chart is useful as a focused view. The Progress page summarizes load, the Training Load page goes deep. No redirect.

**Analytics page (`/analytics`):** Phase out gradually. Most of the data is better served through the coach ("Ask Coach" deep links) and through the Progress page sections. The raw charts aren't meaningful to most athletes without coaching context. However, the chart *visualizations themselves* need to level up.

## Visualization Upgrade Research

**Current state:** Recharts 3.6.0 (already installed). Basic SVG charts. Functional but not visually impressive.

**Research findings:**

| Library | Best For | Style | Size | License |
|---------|----------|-------|------|---------|
| **Recharts 3.x** (current) | Standard charts | Clean, composable | ~45KB | MIT |
| **Tremor** | Analytics dashboards | Beautiful defaults, Tailwind-native | ~50KB | Apache 2.0 |
| **Nivo** | Rich, animated charts | D3-based, highly customizable | Modular | MIT |
| **Lightweight Charts (TradingView)** | Time-series data | Financial-grade, Canvas rendering | 35KB | Apache 2.0 |

**Recommendation:** Two-library approach:

1. **Tremor** for dashboard components — spark charts, progress bars, data bars, trackers. Tailwind-native means zero design friction. Already built on Recharts under the hood. Adds the "at a glance" visualizations the Progress page needs (spark lines in metric cards, mini trend indicators).

2. **Lightweight Charts (TradingView)** for the deep-dive time-series charts — CTL/ATL/TSB history, efficiency trends, volume trajectory. Financial-grade interactivity (crosshair, zoom, pan, real-time streaming). Canvas-rendered at 35KB. The visual DNA of finance dashboards that makes data feel alive.

**What this enables:**
- CTL/ATL/TSB chart that looks like a Bloomberg terminal, not a school report
- Sparklines in every metric card (fitness trending up, volume trending down)
- Interactive hover that shows exact values at any point in time
- Smooth animations on data transitions
- Touch-optimized for mobile (pinch zoom, swipe)

**Implementation approach:**
- Phase 6a: Add Tremor spark components to Progress page metric cards
- Phase 6b: Replace CTL/ATL/TSB chart with Lightweight Charts
- Phase 6c: Replace Training Load page chart with Lightweight Charts
- Phase 6d: Replace efficiency trend chart

**What NOT to do:**
- Don't remove Recharts (other pages still use it)
- Don't upgrade everything at once
- Don't add 3D charts or animations that slow mobile
