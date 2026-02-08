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
