# ADR 17: V2 Coach-Led Experience — Navigation, Home, Progress, Mobile

**Status:** Approved  
**Date:** 2026-02-08  
**Author:** AI Assistant + Founder  
**Trigger:** Full Rigor — touches every user-facing surface, navigation, page structure, mobile experience  
**Depends on:** ADR-16 (Coach Context Architecture — completed)

---

## Build Process

Every phase follows the same loop. A phase is NOT complete until it is live in production and verified.

```
┌──────────────────────────────────────────────────────────────────┐
│  1. SCOPE    — List exact files to create/edit, describe changes │
│  2. BUILD    — Implement per ADR spec                            │
│  3. TEST     — pytest -v (full), tsc --noEmit, npm run build     │
│  4. FIX      — Fix any failures                                  │
│  5. TEST     — Re-run until green                                │
│  6. LINT     — ReadLints on all edited files                     │
│  7. JUDGE    — Present summary, deviations, test results         │
│  8. GATE     — Founder reviews → explicit "approved" or changes  │
│  9. COMMIT   — One commit, conventional message                  │
│ 10. PUSH     — Push to main                                      │
│ 11. CI       — GitHub Actions must pass (all jobs green)          │
│ 12. DEPLOY   — Founder runs deploy on droplet (commands provided)│
│ 13. VERIFY   — API smoke test + founder visual check             │
│ 14. DONE     — Phase complete. Next phase begins at SCOPE.       │
└──────────────────────────────────────────────────────────────────┘
```

### Step Details

- **SCOPE**: Files to touch, changes per file, rationale. Founder sees the plan before code is written.
- **BUILD**: Code changes, adherent to ADR spec.
- **TEST**: Backend `pytest -v` from `apps/api/` — full suite, zero failures. Frontend `npx tsc --noEmit` + `npm run build` from `apps/web/` — zero errors. If frontend tests exist for affected areas, run those too.
- **FIX**: Fix failures — regressions or test assertions that changed intentionally.
- **LINT**: `ReadLints` on all edited files. No new linter errors introduced.
- **JUDGE**: Present to founder: what was built, any deviations from ADR (and why), test results (pass counts), decisions made, things to verify visually.
- **GATE**: Founder reviews and says "approved" or requests changes. If changes requested, loop back to BUILD within the same phase. Nothing advances without explicit approval.
- **COMMIT**: One commit per phase. Conventional message format: `feat(scope): description`. PowerShell-safe (no heredoc).
- **PUSH**: `git push origin main`. Show push output to confirm.
- **CI**: Wait for GitHub Actions. All jobs must pass: backend tests, frontend build, security scan, Docker build. If CI fails, fix locally, amend or new commit, re-push until green.
- **DEPLOY**: Provide founder with exact commands:
  ```
  ssh root@strideiq.run
  cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
  ```
  Founder runs on droplet. Build takes 3-8 minutes. Founder confirms completion.
- **VERIFY**: Two parts:
  1. **API smoke test** — Provide founder with `curl` commands to run on droplet to verify backend endpoints.
  2. **Visual check** — Provide founder with specific things to check in browser (mobile + desktop). Example: "Open home page on your phone. Do you see the Coach Noticed card?"
- **DONE**: Phase complete only after live verification passes.

### Rules

1. Phase N+1 does not start until Phase N is live and verified.
2. No silent decisions. If something isn't in the ADR, stop and ask.
3. ADR is the spec. Deviations are explained in JUDGE.
4. Tests are non-negotiable. Green suite before JUDGE.
5. Old pages stay live until Phase 5, and only removed with explicit founder approval at that gate.

### Rollback Plan

If a deployment breaks production:
```bash
# On droplet:
cd /opt/strideiq/repo
git revert <phase-commit-hash>
docker compose -f docker-compose.prod.yml up -d --build
```
Each phase = one commit = clean revert. No other phases affected.

---

## Context

The product has a powerful analytical backend (22 coach tools, correlation engine, efficiency analytics, durability indexing, race predictor, 1,409+ passing tests) but the frontend fails to surface it meaningfully. The founder's diagnosis: "feature rich, but doesn't provide any meaning — even to me, who built it."

### Observed Problems

| Problem | Impact |
|---------|--------|
| Home page is generic dashboard cards with no coaching voice | No reason to return |
| Strava connection breaks daily (token refresh bug) | Trust-killer, #1 friction point |
| Coach is hidden behind a nav tab, looks like a generic chatbot | Central product feels optional |
| Coach suggestions are static/repeated | Missed opportunity for engagement |
| Mobile uses hamburger menu — features are buried | Runners are mobile-first |
| Analytics, Training Load, Compare, PBs, Insights are 5 separate pages answering the same question | Fragmented experience |
| Pages show raw data, not coaching interpretations | "Interesting but not useful" |
| No subjective check-in in the natural flow | Missing the feedback loop |
| 3 insight systems of varying quality, worst ones persisted | Best insights never surface |
| No toast/notification system | Mutations succeed/fail silently |

### Root Cause: Strava Daily Breakage

The `/verify` endpoint treats an expired token (HTTP 401) identically to a revoked token — it deletes access token, refresh token, AND strava_athlete_id. The refresh token is valid and could get a new access token. Instead it gets nuked. User must re-authorize daily.

---

## Decision

**Redesign the entire authenticated experience around the coach's voice.** Every screen answers a coaching question. Conclusions first, evidence second, raw data third. Mobile-first with bottom tab navigation.

### Design Principles

1. **The coach speaks through the app, not just in the chat.** The home page IS the coach. The insights ARE the coach. The chat is where you talk back.
2. **Conclusion first, evidence second, data third.** No page exists just to display numbers.
3. **Subjective over objective.** The athlete's feel is the primary input. Objective data (HRV, sleep scores) flows in silently from wearables and gets correlated against subjective reports and performance outcomes.
4. **Build resilient to change.** This project is early-stage and rapidly evolving. Every component should be loosely coupled and replaceable.
5. **Never engagement farm.** Every notification, every email, every prompt must provide clear benefit. If the coach has nothing to say, it stays silent.

---

## Phase 0: Strava Token Refresh Hotfix (0.5 days)

### The Bug

```
User visits → /verify called → access token expired (6h TTL) → Strava returns 401
→ /verify treats 401 as "revoked" → DELETES access_token, refresh_token, strava_athlete_id
→ User sees "Strava disconnected" → must re-authorize
```

### The Fix

1. **`/verify` endpoint**: On 401, attempt `refresh_access_token()` with stored refresh token before wiping. Only wipe if refresh also fails.
2. **Store `strava_token_expires_at`** on Athlete model. Save during `exchange_code_for_token()` and `refresh_access_token()`.
3. **Store `timezone`** on Athlete model. Derive from Strava API response during OAuth callback (Strava returns athlete timezone).
4. **Proactive pre-flight**: Before any Strava API call, check `if expires_at < now + 5min: refresh()`.
5. **Fix `get_activity_laps()`**: Update `strava_refresh_token` after refresh (like other functions do).
6. **Add `db.commit()`** after token refresh in service layer to ensure persistence.

### Migration

Add columns: `strava_token_expires_at` (DateTime, nullable), `timezone` (Text, nullable).

---

## Phase 1: Navigation + Foundations (2 days)

### 1A. Bottom Tab Navigation (Mobile)

Replace hamburger menu with sticky bottom tabs:

```
[ 🏠 Home ]  [ 💬 Coach ]  [ 📅 Calendar ]  [ 📈 Progress ]  [ ••• More ]
```

- 60px height + safe area padding for notched phones
- Active state: orange icon + label. Inactive: slate icon + label.
- Only on authenticated routes. Desktop keeps top nav.
- Coach tab: subtle dot indicator when new daily insight exists.

### 1B. Toast System

Add `sonner` (lightweight, <5KB). Wire to all mutations for success/error feedback.

### 1C. Strava Reconnect Banner

Persistent banner on every authenticated page when `strava_connected === false`:

```
⚠️ Strava disconnected — [Reconnect Now]
```

One-click triggers OAuth flow. Dismisses on successful reconnect. Fallback for edge cases where Phase 0 fix doesn't cover (user revokes on Strava.com, capacity limits).

---

## Phase 2: Coach-Led Home Page (3-4 days)

### Layout: Tiered, Mobile-First

**Tier 1 — Always Visible (above the fold):**

**Coach Noticed Card** — The single most important insight. One sentence, maybe two. Rotates through sources in priority order:
1. Strong correlation finding ("Sleep > 7h → 12% better efficiency, r=0.6, 23 observations")
2. Top signal from `home_signals.py` (efficiency trend shift, TSB zone change)
3. Top feed card summary from `build_insight_feed_cards()`
4. Hero narrative fallback

Changes daily. Ends with "[Ask Coach →]" deep-link to coach chat with that insight pre-loaded.

**Quick Check-in** — Three subjective fields, three taps:
- "How do you feel today?" — [Great] [Fine] [Tired] [Rough]
- "Sleep?" — [Great] [OK] [Poor]
- "Any soreness?" — [No] [Mild] [Yes]

Inline submission. Disappears after completion today. No numbers, no scales.

**Tier 2 — Below the fold, expandable cards:**

- **Today** — Planned workout with `why_context` from correlation engine. Empty state: "[Ask Coach what to do →]"
- **This Week** — Progress bar, partial-week awareness, volume trajectory sentence. Compact.
- **Race Countdown** — Goal race, date, days remaining, goal time, goal pace, current prediction. Built resilient: reads from plan model but gracefully handles missing/changed plan structure.

### Backend Changes

Enhance `GET /v1/home`:
- Add `coach_noticed`: best signal/insight/correlation (one sentence)
- Add `race_countdown`: from plan data (resilient to missing plan)
- Add `checkin_needed`: boolean (has user checked in today?)
- Add `strava_status`: connection health detail

Add weekly metric snapshot: store key metrics (CTL, ATL, durability, efficiency, volume) as JSONB on Athlete model. `build_athlete_brief()` compares current vs snapshot for delta headlines in Progress page.

### What's Removed from Home

- Quick Access card (bottom tabs replace it)
- Yesterday card (coach references it naturally)
- Hero narrative (replaced by Coach Noticed)
- Welcome card (onboarding flow, not a persistent card)
- Import progress (moved to Strava banner)

---

## Phase 3: Progress Page (3-4 days)

### Merge: Analytics + Training Load + Compare + PBs + Insights → Progress

Five pages asking variations of "Am I getting better?" become one page with sections.

**Old pages stay live during Phase 3.** They are only removed/redirected in Phase 5 after the founder has lived with Progress and confirmed it's better.

### Section 1: The Headline

One dynamic sentence. Compares current state vs weekly snapshot (delta):
> "Fitness up 12% from last week, but durability dropped 4 points — your volume is outpacing your recovery."

Falls back to goal-oriented if no delta:
> "You're 12% ahead of half-marathon pace trajectory."

### Section 2: What's Working / What's Not

The manifesto's promise made visible. Sources:
- `useWhatWorks()` and `useWhatDoesntWork()` hooks (already exist)
- Correlation engine findings with r-values and sample sizes

Examples:
- "Working: Monday rest days → 8% better Tuesday tempo efficiency (r=0.6, n=23)"
- "Not working: Long runs after <6h sleep → 18% efficiency drop"

This is the N-of-1 intelligence. The moat.

### Section 3: Fitness & Load

- Conclusion first: "Building phase. Fatigue elevated but manageable."
- CTL/ATL/TSB chart (collapsible)
- Form zone indicator
- Replaces Training Load page.

### Section 4: Efficiency Trend

- Conclusion first: "Easy-run efficiency improving. Threshold efficiency plateaued."
- EF chart with zone breakdown (collapsible)
- Replaces efficiency section of Analytics page.

### Section 5: Personal Bests — In Context

Coaching framing, not a table:
> "Your HM PR (1:27:12, Nov 29) came at 42 mi/week, TSB +5, sleeping 7.2h. You're currently at 50 mi/week, TSB -12, sleeping 6.8h. You have the fitness — you need the freshness and sleep."

Uses `get_pb_patterns()` which already computes TSB-before-PR. Frontend frames it as a lesson.

### Section 6: Period Comparison

- Last 28 days vs prior 28 days: volume, pace, HR, efficiency
- Uses existing `compare_training_periods()` tool
- Collapsible detail

### Every Section: [Ask Coach →]

Each section has a deep-link to coach chat with the section's finding pre-loaded as a question.

---

## Phase 4: Coach Refinements (2-3 days)

### 4A. Coach Empty State

When conversation is empty, show condensed brief instead of blank chat:

```
"Here's what I see in your data today:
• Volume: 50 mi last week, 31 mi so far (3 of 6 runs)
• Fitness building (+12% CTL over 3 weeks)
• 38 days to race day — goal pace 7:15/mi

What do you want to work on?"
```

3 dynamic prompts from `get_dynamic_suggestions()` (backend already produces these from real athlete data).

### 4B. Desktop Context Panel

Replace static suggestion sidebar with "Coach's Context" panel: 3-4 key metrics from the brief (volume trend, fitness direction, recovery status, race countdown). Provides context while chatting.

### 4C. Deep Linking

Every "[Ask Coach →]" link across the app opens `/coach?q=...` with the question pre-filled. Coach Noticed card, What's Working findings, PB insights — all one tap to discuss.

### 4D. Verify Dynamic Suggestions

Confirm frontend calls `GET /v1/coach/suggestions` (the dynamic endpoint). If suggestions are still static/repeated, trace and fix the frontend rendering. Backend already pulls from real data.

### 4E. Weekly Digest Enhancement

Add "What's Working" teaser to existing Monday 9am digest email. One line from the top correlation finding.

---

## Phase 5: Cleanup + Mobile Polish (2-3 days)

### 5A. Remove Old Pages (after founder approval)

Redirect `/analytics`, `/training-load`, `/compare`, `/personal-bests` to `/progress`. Update all internal links. Only after founder confirms Progress page is better.

### 5B. Insights Page Simplification

Keep: Insight Feed (high-quality evidence-backed cards), Athlete Intelligence (Elite feature).
Remove: Active Insights section (low-quality InsightAggregator output). Best insights now surface through Coach Noticed and What's Working.

### 5C. Mobile Polish

- Bottom tab safe-area handling verification
- Touch targets audit (44px minimum)
- PWA manifest + service worker for add-to-homescreen
- Pull-to-refresh on home page

### 5D. Insight Quality

Raise InsightAggregator thresholds. "You ran 3 times this week" is not an insight. Frame everything against the athlete's own baseline and goals.

---

## Post-V2: Phase 6 — Insight Pipeline Unification (1-2 days)

Deprecate `InsightAggregator`. Route all insight generation through `build_insight_feed_cards()` + correlation engine. Persist only high-confidence insights. Everything else computed on the fly via the brief.

---

## Navigation Map (V2)

### Bottom Tabs (Mobile) / Top Nav (Desktop)

```
Home (/home)          — Coach's daily briefing
Coach (/coach)        — AI coach chat
Calendar (/calendar)  — Training schedule + execution
Progress (/progress)  — Am I getting better? (merged page)
More                  — Activities, Nutrition, Tools, Settings
```

### Removed from Primary Navigation

- Analytics → merged into Progress
- Training Load → merged into Progress
- Insights → partially merged into Progress, remainder stays simplified
- Compare → merged into Progress
- Personal Bests → merged into Progress
- Check-in → inline on Home page

---

## Inline Check-in Design

### Subjective-First Philosophy

Objective data (HRV, sleep scores, resting HR) flows in silently from wearable integrations (Garmin, Coros — coming soon). The inline check-in captures subjective feel.

Over time, the correlation engine discovers which signal — subjective or objective — better predicts performance outcomes for each individual athlete. "For YOU, subjective feel predicts performance better than your watch does." This is an N-of-1 insight no competitor offers.

### Fields

| Question | Options | Taps |
|----------|---------|------|
| How do you feel today? | Great / Fine / Tired / Rough | 1 |
| Sleep? | Great / OK / Poor | 1 |
| Any soreness? | No / Mild / Yes | 1 |

Total: 3 taps. Inline on home page. Disappears after submission. Full check-in form (with numbers) remains accessible from More menu.

---

## Resilience Principles

1. **Loose coupling**: Every component reads from API hooks, never directly from models. If the plan model changes, only the API needs updating.
2. **Graceful degradation**: Every card handles missing data (no plan, no correlations, no check-in). Empty states are coaching opportunities, not error messages.
3. **Feature flags**: New pages/sections can be toggled per-user for gradual rollout.
4. **Old pages preserved**: During transition, old routes stay live. Only removed after founder approval in Phase 5.
5. **No hardcoded content**: Every insight, suggestion, and narrative comes from the athlete's data through the analytics engine. Nothing is static.

---

## Acceptance Criteria (Per Phase)

### Build Loop (every phase)

```
SCOPE → BUILD → TEST → FIX → TEST → LINT → JUDGE → GATE → NEXT
```

**TEST means:**
- Backend: `pytest -v` from `apps/api/` — full suite, zero failures
- Frontend: `npx tsc --noEmit` + `npm run build` from `apps/web/` — zero errors
- Lint: `ReadLints` on all edited files — no new errors introduced

**GATE means:**
- Summary of what was built and any deviations from ADR
- Test results (pass count)
- Founder reviews and explicitly approves before next phase

---

### Phase 0: Strava Token Refresh Hotfix

**Files touched:**
- `apps/api/routers/strava.py` — `/verify` endpoint
- `apps/api/services/strava_service.py` — `refresh_access_token()`, `get_activity_laps()`, new pre-flight helper
- `apps/api/models.py` — Athlete model (2 new columns)
- `apps/api/alembic/versions/` — new migration file
- `apps/api/tests/` — new or updated test file for Strava token refresh

**Acceptance Criteria:**

| # | Criterion | How to verify |
|---|-----------|---------------|
| P0-1 | `/verify` attempts `refresh_access_token()` when Strava returns 401, using stored `strava_refresh_token` | Unit test: mock Strava returning 401, assert refresh is attempted, tokens NOT wiped |
| P0-2 | `/verify` only wipes tokens if refresh also fails (e.g., 400 from Strava = truly revoked) | Unit test: mock refresh returning 400, assert tokens ARE wiped |
| P0-3 | `/verify` returns `valid: True` after successful refresh (no second Strava call needed) | Unit test: mock 401 then successful refresh, assert response `valid: True` |
| P0-4 | `strava_token_expires_at` column added to Athlete model (DateTime, nullable) | Migration runs without error; column exists in DB |
| P0-5 | `timezone` column added to Athlete model (Text, nullable) | Migration runs without error; column exists in DB |
| P0-6 | `exchange_code_for_token()` stores `expires_at` from Strava response | Code inspection: Strava returns `expires_at` (Unix epoch), stored as DateTime |
| P0-7 | `refresh_access_token()` stores new `expires_at` after refresh | Code inspection: new expiry saved to athlete model |
| P0-8 | `refresh_access_token()` in service layer commits to DB (`db.commit()` or equivalent) | Code inspection: explicit commit after token update |
| P0-9 | Pre-flight helper: before Strava API calls, checks `if expires_at < now + 5min: refresh()` | Code inspection: helper function exists and is called from data-fetching functions |
| P0-10 | `get_activity_laps()`: on 401 refresh, stores BOTH new access token AND new refresh token | Code inspection: `athlete.strava_refresh_token = encrypt_token(token["refresh_token"])` added |
| P0-11 | OAuth callback stores `timezone` from Strava athlete response | Code inspection: `athlete.timezone = athlete_data.get("timezone")` or equivalent |
| P0-12 | All existing backend tests pass (`pytest -v`) | Zero failures |
| P0-13 | New tests cover: successful refresh, failed refresh (wipe), pre-flight refresh, laps refresh token persistence | At least 4 new test cases |

**Not in scope:** Frontend changes (those are Phase 1). This phase is backend-only.

---

### Phase 1: Navigation + Foundations

**Files touched:**
- `apps/web/app/components/Navigation.tsx` — add bottom tab bar (mobile), keep top nav (desktop)
- `apps/web/app/layout.tsx` — add `<Toaster />` from sonner
- `apps/web/package.json` — add `sonner` dependency
- `apps/web/app/components/StravaBanner.tsx` — new component
- `apps/web/app/components/BottomTabs.tsx` — new component (or inline in Navigation)
- Various mutation hooks — add toast calls on success/error

**Acceptance Criteria:**

| # | Criterion | How to verify |
|---|-----------|---------------|
| P1-1 | Bottom tab bar visible on screens <768px width | `npm run build` succeeds; visual: 5 tabs at bottom on mobile viewport |
| P1-2 | Bottom tabs: Home, Coach, Calendar, Progress, More | Tabs link to `/home`, `/coach`, `/calendar`, `/progress`, and More opens a menu/sheet |
| P1-3 | Active tab shows orange icon + label; inactive shows slate | CSS/Tailwind inspection |
| P1-4 | Bottom tabs have 60px height + `pb-safe` (safe area padding for notched phones) | CSS inspection: `env(safe-area-inset-bottom)` or equivalent |
| P1-5 | Bottom tabs only render on authenticated routes (not on `/`, `/login`, `/register`, `/onboarding/*`) | Code inspection: conditional rendering based on auth state and route |
| P1-6 | Desktop (>=768px) still shows top navigation bar, bottom tabs hidden | Responsive behavior via `md:hidden` or similar |
| P1-7 | Existing top nav items reorganized: primary items match bottom tabs, secondary items under More | Navigation items match ADR nav map |
| P1-8 | `sonner` installed, `<Toaster />` rendered in root layout | `package.json` includes sonner; layout.tsx renders `<Toaster />` |
| P1-9 | At least 3 existing mutation hooks wired with toast (success + error) | Example: check-in submit, strava connect, settings save — each shows toast |
| P1-10 | Strava reconnect banner appears on all authenticated pages when `strava_connected === false` | Component rendered conditionally; uses existing `/v1/strava/verify` response |
| P1-11 | Banner shows warning icon + "Strava disconnected" + [Reconnect Now] button | Visual + code inspection |
| P1-12 | [Reconnect Now] triggers OAuth flow (same flow as settings page) | Code inspection: calls same `stravaService.getAuthUrl()` or equivalent |
| P1-13 | Banner dismisses when Strava reconnects (not just on close) | Re-verification after OAuth callback clears the banner |
| P1-14 | `npx tsc --noEmit` passes with zero errors | TypeScript compilation clean |
| P1-15 | `npm run build` succeeds | Next.js build clean |
| P1-16 | All existing frontend tests pass (`npm test`) | Zero failures |
| P1-17 | No layout shift — page content is not obscured by bottom tabs | `pb-[60px]` or equivalent padding on page container for mobile |
| P1-18 | `/progress` route exists (can be empty placeholder page) | Route resolves, no 404 — Progress page built in Phase 3 |

---

### Phase 2: Coach-Led Home Page

**Files touched:**
- `apps/api/routers/home.py` — enhance `GET /v1/home` response
- `apps/api/routers/daily_checkin.py` — possibly add quick-checkin endpoint
- `apps/web/app/home/page.tsx` — full redesign
- `apps/web/lib/hooks/queries/home.ts` — update hook for new response fields
- `apps/web/lib/api/services/home.ts` — update types
- `apps/api/tests/test_home_api.py` — update tests for new response fields

**Acceptance Criteria:**

| # | Criterion | How to verify |
|---|-----------|---------------|
| **Backend** | | |
| P2-1 | `GET /v1/home` returns `coach_noticed: {text: str, source: str, ask_coach_query: str}` | API response includes field; test covers it |
| P2-2 | `coach_noticed` priority: (1) strong correlation (abs(r) >= 0.5, n >= 15), (2) top signal from `home_signals`, (3) top insight feed card, (4) hero_narrative fallback | Code inspection: priority waterfall implemented |
| P2-3 | `GET /v1/home` returns `race_countdown: {race_name, race_date, days_remaining, goal_time, goal_pace, predicted_time}` or `null` if no plan | API response; handles missing plan gracefully |
| P2-4 | `GET /v1/home` returns `checkin_needed: bool` (true if no check-in for today's date) | API response; test covers both states |
| P2-5 | `GET /v1/home` returns `strava_status: {connected: bool, last_sync: str, needs_reconnect: bool}` | API response includes field |
| P2-6 | Race countdown reads from `TrainingPlan` model but does NOT crash if plan model changes — uses `getattr()` or `try/except` for all plan fields | Code inspection: resilient access patterns |
| P2-7 | `coach_noticed` computation does not add >500ms to home page response time | Timing: compare baseline vs new response time |
| P2-8 | Quick check-in can use existing `POST /v1/daily-checkin` endpoint with only 3 fields populated (all other fields optional in `DailyCheckinCreate`) | Test: POST with only subjective fields, assert 200 |
| P2-9 | All existing home API tests pass | `pytest tests/test_home_api.py -v` — zero failures |
| P2-10 | New tests cover: coach_noticed with correlation, coach_noticed fallback, race_countdown present, race_countdown null, checkin_needed true/false | At least 5 new test cases |
| **Frontend** | | |
| P2-11 | Home page Tier 1 (above fold): Coach Noticed card + Quick Check-in | Visual: these two elements visible without scrolling on mobile |
| P2-12 | Coach Noticed card shows one coaching sentence + "[Ask Coach →]" link | Visual + code inspection |
| P2-13 | "[Ask Coach →]" links to `/coach?q={encoded_query}` | Code inspection: link href is correct |
| P2-14 | Quick Check-in: 3 questions, tap-to-select options, inline submit | Visual: no page navigation, no modal, no number inputs |
| P2-15 | Check-in options: Feel (Great/Fine/Tired/Rough), Sleep (Great/OK/Poor), Soreness (No/Mild/Yes) | Visual: exact options rendered |
| P2-16 | Check-in maps to existing API: Feel → `motivation_1_5`, Sleep → `sleep_h` bucket, Soreness → `soreness_1_5` | Code inspection: mapping exists; values are reasonable (e.g., Great=5, Rough=1) |
| P2-17 | Check-in disappears after submission (for today) | `checkin_needed` drives visibility; re-fetch after submit |
| P2-18 | Tier 2 cards: Today (planned workout), This Week (progress bar + trajectory), Race Countdown | Visual: below fold, expandable or visible on scroll |
| P2-19 | Today card empty state: "[Ask Coach what to do →]" | Visual when no planned workout |
| P2-20 | This Week card shows partial-week awareness (e.g., "3 of 7 days") | Code inspection: uses `days_elapsed` or equivalent |
| P2-21 | Race Countdown card handles no plan gracefully (hidden or "No race scheduled" message) | Visual: no crash, no empty card shell |
| P2-22 | Removed from home: Quick Access card, Yesterday card, Hero Narrative card, Welcome card, Import Progress | Code inspection: components removed or conditionally hidden |
| P2-23 | `npx tsc --noEmit` + `npm run build` pass | Zero errors |
| P2-24 | All backend tests pass (`pytest -v`) | Zero failures |

---

### Phase 3: Progress Page

**Files touched:**
- `apps/web/app/progress/page.tsx` — new page (or replace placeholder from P1)
- `apps/web/lib/hooks/queries/progress.ts` — new hook aggregating multiple API calls
- `apps/api/routers/progress.py` — possibly new endpoint for headline/delta, or computed frontend-side
- Existing pages (`analytics`, `training-load`, `compare`, `personal-bests`, `insights`) — **NOT touched** (stay live)

**Acceptance Criteria:**

| # | Criterion | How to verify |
|---|-----------|---------------|
| P3-1 | `/progress` route renders a full page with 6 sections | Visual: page loads, all sections present |
| P3-2 | **Section 1 — Headline**: One dynamic sentence comparing current vs prior week (e.g., "Fitness up 12%...") | Visual + code inspection: uses CTL/ATL/durability delta |
| P3-3 | Headline falls back to goal-oriented sentence if no prior snapshot exists | Code inspection: fallback path |
| P3-4 | **Section 2 — What's Working / What's Not**: Lists correlation findings with r-values and sample sizes | Visual: at least 1 item per category if correlations exist |
| P3-5 | What's Working/Not sources from `useWhatWorks()` / `useWhatDoesntWork()` hooks OR correlation engine | Code inspection: uses existing hooks/API |
| P3-6 | Empty state for What's Working: "Not enough data yet — keep logging check-ins and running" or similar | Visual: no crash, no empty container |
| P3-7 | **Section 3 — Fitness & Load**: Conclusion sentence + collapsible CTL/ATL/TSB chart + form zone | Visual: conclusion visible by default, chart collapsed |
| P3-8 | Chart uses same data source as `/training-load` page (no data duplication) | Code inspection: same API hook |
| P3-9 | **Section 4 — Efficiency Trend**: Conclusion sentence + collapsible EF chart with zone breakdown | Visual: conclusion visible, chart collapsed |
| P3-10 | **Section 5 — Personal Bests in Context**: Coaching framing (PR + conditions at time of PR + current conditions) | Visual: narrative sentence, not a raw table |
| P3-11 | PBs use `get_pb_patterns()` or equivalent (TSB-before-PR data) | Code inspection: uses existing API |
| P3-12 | **Section 6 — Period Comparison**: Last 28d vs prior 28d — volume, pace, HR, efficiency | Visual: comparison table or cards |
| P3-13 | Period comparison uses existing `compare_training_periods()` tool or equivalent API | Code inspection |
| P3-14 | Every section has "[Ask Coach →]" link with the section's finding as a pre-filled query | Code inspection: 6 deep links |
| P3-15 | All collapsible sections default to collapsed on mobile, expanded on desktop | Responsive behavior |
| P3-16 | Old pages (`/analytics`, `/training-load`, `/compare`, `/personal-bests`) remain fully functional | Manual: old routes still work, no regressions |
| P3-17 | `npx tsc --noEmit` + `npm run build` pass | Zero errors |
| P3-18 | All backend tests pass (`pytest -v`) | Zero failures |
| P3-19 | Page handles missing data for every section without crashing (new user with no activities) | Code inspection: every section has empty/fallback state |

---

### Phase 4: Coach Refinements

**Files touched:**
- `apps/web/app/coach/page.tsx` — empty state, context panel, deep link handling
- `apps/web/app/home/page.tsx` — ensure deep links work from Coach Noticed
- `apps/web/app/progress/page.tsx` — ensure deep links work from all sections
- `apps/api/routers/ai_coach.py` — verify `GET /v1/coach/suggestions` returns dynamic data
- `apps/api/tasks/digest_tasks.py` — add What's Working teaser
- `apps/api/services/email_service.py` — update digest template

**Acceptance Criteria:**

| # | Criterion | How to verify |
|---|-----------|---------------|
| **Coach Empty State** | | |
| P4-1 | When no conversation exists, coach page shows condensed athlete brief (not blank chat) | Visual: volume, fitness direction, race countdown visible |
| P4-2 | Brief pulls from `build_athlete_brief()` or home API data (not hardcoded) | Code inspection: dynamic data source |
| P4-3 | Below the brief: 3 dynamic suggestion prompts from `GET /v1/coach/suggestions` | Visual: 3 tappable prompts |
| P4-4 | Tapping a suggestion sends it as a message (starts conversation) | Visual: message appears in chat, coach responds |
| **Desktop Context Panel** | | |
| P4-5 | Desktop (>=768px): right sidebar shows "Coach's Context" — 3-4 key metrics from brief | Visual: volume trend, fitness direction, recovery, race countdown |
| P4-6 | Context panel replaces or augments the existing suggestion sidebar | Code inspection: old static suggestions removed or replaced |
| P4-7 | Context panel updates when new data is available (not stale across sessions) | Code inspection: re-fetches on mount or uses React Query |
| **Deep Linking** | | |
| P4-8 | `/coach?q=...` reads query param and pre-fills input field | Code: `useSearchParams()` reads `q`, sets input value |
| P4-9 | Pre-filled query does NOT auto-send (user must tap send) | Code inspection: no auto-submit on mount |
| P4-10 | Deep links from Home (Coach Noticed) arrive with correct query text | Manual: tap "[Ask Coach →]" on home, verify coach page has query |
| P4-11 | Deep links from Progress (all 6 sections) arrive with correct query text | Manual: tap "[Ask Coach →]" on progress, verify |
| **Dynamic Suggestions** | | |
| P4-12 | Frontend calls `GET /v1/coach/suggestions` (not static/hardcoded prompts) | Code inspection: API call in hook or component |
| P4-13 | Suggestions are not repeated (de-duplicated in frontend or backend) | Code inspection: de-dup logic exists |
| P4-14 | If suggestions API fails, graceful fallback (empty or generic prompts, not crash) | Code inspection: error handling |
| **Weekly Digest Enhancement** | | |
| P4-15 | `send_weekly_digest_task` includes top "What's Working" correlation in email body | Code inspection: correlation finding added to email template |
| P4-16 | Email template has a one-line teaser (not full analysis dump) | Code inspection: brief sentence, not a table |
| P4-17 | Digest still sends if no correlations found (graceful skip of that section) | Code inspection: conditional rendering in email |
| **Tests** | | |
| P4-18 | `npx tsc --noEmit` + `npm run build` pass | Zero errors |
| P4-19 | All backend tests pass (`pytest -v`) | Zero failures |
| P4-20 | Digest task test covers: with correlations, without correlations | At least 1 new/updated test |

---

### Phase 5: Cleanup + Mobile Polish

**Files touched:**
- Old page files — redirect logic or removal (ONLY after founder approval at gate)
- `apps/web/app/insights/page.tsx` — simplify
- `apps/web/app/components/Navigation.tsx` — remove old nav items
- `apps/web/public/manifest.json` — PWA manifest
- Various components — touch target audit

**Acceptance Criteria:**

| # | Criterion | How to verify |
|---|-----------|---------------|
| **Old Page Removal (requires explicit founder approval at gate)** | | |
| P5-1 | `/analytics` redirects to `/progress` (HTTP redirect or client-side) | Browser: navigating to old URL lands on progress |
| P5-2 | `/training-load` redirects to `/progress` | Same |
| P5-3 | `/compare` redirects to `/progress` | Same |
| P5-4 | `/personal-bests` redirects to `/progress` | Same |
| P5-5 | All internal links updated (no dead links to old routes) | Code search: no remaining `href="/analytics"` etc. |
| P5-6 | Old nav items removed from Navigation component | Code inspection |
| **Insights Simplification** | | |
| P5-7 | Insights page keeps: Insight Feed (high-quality cards), Athlete Intelligence | Visual |
| P5-8 | Insights page removes: Active Insights section (InsightAggregator output) | Visual: section gone |
| P5-9 | Insights page does not crash if feed is empty | Visual: empty state message |
| **Mobile Polish** | | |
| P5-10 | Bottom tab safe-area padding works on iOS Safari (notched phones) | CSS: `env(safe-area-inset-bottom)` applied |
| P5-11 | All tappable elements are at least 44x44px | CSS audit: buttons, links, tab targets |
| P5-12 | `manifest.json` exists with app name, icons, `display: "standalone"`, theme color | File inspection |
| P5-13 | Home page supports pull-to-refresh (or manual refresh button for MVP) | Visual: pull gesture or button triggers data re-fetch |
| **Insight Quality** | | |
| P5-14 | InsightAggregator thresholds raised: trivial insights (e.g., "You ran 3 times") no longer generated | Code inspection: minimum confidence/significance thresholds increased |
| P5-15 | All remaining insights framed against athlete's baseline (not absolute statements) | Code inspection: comparative language |
| **Tests** | | |
| P5-16 | `npx tsc --noEmit` + `npm run build` pass | Zero errors |
| P5-17 | All backend tests pass (`pytest -v`) | Zero failures |
| P5-18 | No broken links across the entire app | Manual: navigate all primary routes |

---

## Timeline

| Phase | Scope | Est. Days |
|-------|-------|-----------|
| 0 | Strava token refresh hotfix + timezone + migration | 0.5 |
| 1 | Bottom nav + toast system + Strava banner | 2 |
| 2 | Coach-led home page + inline check-in + home API enhancements | 3-4 |
| 3 | Progress page (merge 5 pages, conclusion-first) | 3-4 |
| 4 | Coach refinements + deep linking + digest enhancement | 2-3 |
| 5 | Page cleanup + mobile polish + insight quality | 2-3 |
| 6 | (Post-V2) Insight pipeline unification | 1-2 |

**Total V2: 13-17 days**

---

## Alignment with Manifesto

> "The athlete is the coach; the system is the silent, brilliant assistant."

The coach speaks through the home page, through insights, through every "[Ask Coach →]" link. The chat is where the athlete speaks back.

> "The Intelligence Bank is the moat."

"What's Working / What's Not" makes the intelligence bank visible. The correlation engine's findings reach the athlete through every surface.

> "Personal curves only, no global averages."

Every insight, every headline, every check-in correlation is derived from THIS athlete's data. Nothing generic.

> "No hype, just measurable efficiency."

No daily engagement emails. No gamification streaks. No "you ran 3 times!" celebrations. The coach speaks when it has something real to say.
