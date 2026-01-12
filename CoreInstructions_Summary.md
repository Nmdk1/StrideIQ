# Core Instructions Summary for StrideIQ Agents

**Version:** 3.13.0  
**Last Updated:** 2026-01-12  
**Status:** Production (Phases 1-3 of Landing Experience Complete)

---

## READ THIS ENTIRE FILE FIRST ON EVERY NEW SESSION

No skimming, no shortcuts, no assumptions.

---

## Manifesto & Philosophy

### N=1 is the Only N That Matters
- Athlete data overrides everything (books, coaches, research)
- External knowledge informs questions, not answers
- Population findings are hypotheses to test, not truths to impose

### Value-First Insights
- Only show when meaningful/statistically valid
- Sparse/irreverent tone (e.g., "Data says this. Cool. Test it.")
- No prescriptive language (no "you should")
- No guilt, no motivation, no fluff
- Explicit about uncertainty, limitations, missing data

### Let The Data Speak
- No imposition of population findings as truth
- Pattern recognition from athlete's own data
- Hierarchy aware: Career → Season → Build → Block → Week → Workout → Type → Variation

---

## Project Overview

### App Name
**StrideIQ** — AI-powered running intelligence platform answering "WHY did I run faster/slower?" using athlete data alone.

### Tech Stack
- **Backend:** FastAPI/Python 3.11, PostgreSQL/TimescaleDB, Celery/Redis
- **Frontend:** Next.js 14/TypeScript, React Query, Tailwind CSS
- **Auth:** JWT
- **Containerization:** Docker, Docker Compose

### Current Architecture (ADR 14 - Layered Intelligence)
| Layer | Time | Intent | View |
|-------|------|--------|------|
| **Glance** | 2 sec | "What now?" | Home (today's workout + insight) |
| **Explore** | 30 sec | "How am I doing?" | Calendar (week view, trends) |
| **Research** | 5+ min | "Why did this happen?" | Analytics (correlations, attribution) |

### Key Features
- Strava sync (Garmin ready)
- Efficiency/decoupling analysis
- Correlations (single/multi-factor, lags)
- Workout classification (40+ types, 8 zones)
- Knowledge base (8 books, 5 coaches, athlete input highest weight)
- Plans (standard/semi-custom/custom)
- Insights dashboard ("What's Working/Doesn't", trends, attribution)
- Contextual comparison ("ghost average" of similar runs)

---

## Current State

### Recently Completed
- **Phase 1:** Home Experience (Today's workout + Why, Yesterday's insight, Week trajectory)
- **Phase 2:** Calendar Enhancement (Inline insights, week summaries)
- **Phase 3:** Analytics Restructure (Renamed Dashboard → Analytics, correlation explorer)
- **Bug fixes:** Workout classification, stability metrics, insights page

### In Progress
- Phase 4: Research Tools (query engine, multi-athlete view, data export)

### Navigation Structure
```
Primary:
  Home        — The glance (today + yesterday + week)
  Calendar    — The exploration (past/present/future)
  Analytics   — The research (trends, correlations, attribution)
  Coach       — Ask questions, get answers

Secondary:
  Activities, Personal Bests, Profile, Settings, Tools
```

---

## Key Rules for Agents

### Always Do
1. Read ALL relevant files before proposing changes (no skimming)
2. Follow TONE_GUIDE.md for all copy (sparse, irreverent, non-prescriptive)
3. Test changes before committing
4. Update documentation when making architectural changes
5. Commit with clear, descriptive messages

### Never Do
1. No assumptions - if context missing, ask
2. No prescriptive language ("you should", "you need to")
3. No guilt-inducing copy
4. No over-engineering beyond what was asked
5. No motivational fluff

### Rigor Process (For Major Changes)
1. ADR (Architecture Decision Record)
2. Audit logging
3. Unit/integration tests
4. Security review (validation, IDOR, rate limiting)
5. Feature flag (if applicable)
6. Rebuild and verify

---

## Recent Bug Fixes (Session 2026-01-12)

1. **Stability metrics "Hard Runs: 0"**
   - Changed from HR-zone classification to workout_type + intensity_score
   - Half marathon PR at 152 HR is HARD (was being missed)

2. **Workout classifier missing name detection**
   - Added `_classify_from_name()` for threshold/tempo/interval keywords
   - "35 minutes at threshold effort" → now correctly `threshold_run`

3. **Insights page 500 error**
   - Fixed `duration_weeks` → `total_weeks`
   - Fixed `current_phase` to calculate from PlannedWorkout

---

## Known Issues

1. Some activities may have false positive classifications (e.g., "skipped intervals" matching "intervals")
2. 26 pre-existing unit test failures (not from recent changes)
3. User max_hr and vdot not set - could auto-estimate from data

---

## File Structure Reference

```
apps/
  api/                    # FastAPI backend
    routers/              # API endpoints
    services/             # Business logic
    scripts/              # Utility scripts
    tests/                # Unit tests
  web/                    # Next.js frontend
    app/                  # Pages (App Router)
    components/           # React components
    lib/api/              # API client services

_AI_CONTEXT_/
  OPERATIONS/             # ADRs and operational docs
  KNOWLEDGE_BASE/         # Philosophy docs

Key files:
  TONE_GUIDE.md          # Voice and copy rules
  BMI_PHILOSOPHY.md      # Data philosophy
```

---

## Session Continuity

When starting a new session:
1. Read this file FIRST
2. Check `ChatSession_*.md` files for recent context
3. Run `git log --oneline -10` to see recent commits
4. Run `docker-compose ps` to verify services are running

---

## Current Goals/Roadmap

- [x] Phase 1-3: Landing Experience Architecture
- [ ] Phase 4: Research Tools (query engine, multi-athlete, export)
- [ ] Full attribution "why" (inputs explaining trends)
- [ ] Premium gating (Stripe integration ready)
- [ ] Long-term: Acquisition target ($5M+ with 400 users)
