# Codex Diagnostic Brief — Full System Audit

**Date:** March 9, 2026
**From:** Top Advisor
**To:** Codex (Tech Advisor)
**Purpose:** Deep diagnostic of current system state — loading speed, built-vs-visible gap, path traces for known issues, cold-start assessment for new athletes.

---

## What We Need From You

A code-level diagnostic report covering four areas. For each one: trace the actual code paths, report what you find (not what the docs say should happen), and flag discrepancies. Paste evidence — function signatures, line numbers, query counts, cache keys. We need facts, not summaries.

---

## Area 1: Home Page Loading Speed

### Context
The founder reported 34-second load times, then 90+ seconds, at a race on March 8. Today (March 9) it "seemed faster." Between those two observations, we removed two expensive live computations from the home page path:
- Source 1 (`generate_n1_insights` / live correlation engine) was removed from `_build_rich_intelligence_context`
- Path 1 (live `analyze_correlations()`) was removed from `compute_coach_noticed`

The home briefing was moved to Celery + Redis cache on Feb 18 (Lane 2A, ADR-065). At that time, p95 went from 13s to under 2s.

### What to trace

1. **Request path for `GET /v1/home`:** Trace `get_home_data()` (line 2104 of `home.py`). List every DB query and external call made on the request thread. Count them. Are any of these N+1 or unbounded?

2. **Briefing cache path:** `services/home_briefing_cache.py` has `CACHE_TTL_S = 3600` (1 hour) and `STALE_MAX_S = 3600` (1 hour). When cache is fresh, the `/v1/home` endpoint should return cached data without any LLM call. Trace: what happens on cache miss? What happens on stale? Does the endpoint block on LLM, or does it return stale data and enqueue a refresh?

3. **Briefing generation path:** `tasks/home_briefing_tasks.py` builds the prompt via `_build_briefing_prompt()` which calls `generate_coach_home_briefing()`. After the intelligence lanes fix (commit `1df7eb6`), this function now builds 6 lane snippets (`fingerprint_summary`, `coach_noticed_source`, `today_summary`, `checkin_summary`, `race_summary`, `week_context`). How many DB queries does this prompt assembly make? List each source and its query cost.

4. **`compute_coach_noticed` after the fix:** The live `analyze_correlations()` path is removed. The persisted finding path queries `CorrelationFinding` with `times_confirmed >= 3`. What's the actual query? Is it indexed? What's the fallback waterfall cost (home_signals, insight_feed, hero_narrative)?

5. **Celery beat schedule:** `refresh-home-briefings` runs every 15 minutes (`celerybeat_schedule.py` line 30-33). The task is `tasks.refresh_active_home_briefings`. Trace: which athletes get refreshed? How does it determine "active in last 24h"? If all athletes get refreshed every 15 minutes, what's the LLM token cost?

6. **What we need answered:**
   - Is the home page load time currently under 5 seconds for a cache-hit path? Measure or estimate from code.
   - Is there any remaining LLM call on the request path (not the worker path)?
   - What's the worst-case cache-miss scenario? Does the user see a blank page, stale data, or a loading spinner for 30+ seconds?
   - Did removing `generate_n1_insights` and `analyze_correlations()` materially reduce the briefing generation time on the worker path?

---

## Area 2: Built vs. Visible — Complete Gap Analysis

The founder invested more in the Living Fingerprint and correlation engine than in the rest of the site combined. 14 backend capabilities are producing real intelligence. The question is: for each capability, what can the athlete actually see?

### Trace each capability end-to-end

For each row below, trace: (1) the backend service that produces the data, (2) the API endpoint/field that exposes it, (3) the frontend component that renders it. If any link in the chain is missing, mark it.

| # | Capability | Backend Service | API Exposure | Frontend Rendering | Status |
|---|---|---|---|---|---|
| 1 | Weather normalization | `heat_adjustment.py` | ? | ? | ? |
| 2 | Shape extraction | `shape_extractor.py` | ? | ? | ? |
| 3 | Shape sentences | `shape_sentence.py` | Activity endpoints expose `shape_sentence` | Activity detail uses `resolved_title` which may include it | ? |
| 4 | 15 investigations | `race_input_analysis.py` | ? | ? | ? |
| 5 | Finding persistence | `finding_persistence.py` → `AthleteFinding` | ? | ? | ? |
| 6 | Correlation engine | `correlation_engine.py` → `CorrelationFinding` | ? | ? | ? |
| 7 | Threshold detection (L1) | `correlation_layers.py` | ? | ? | ? |
| 8 | Asymmetric response (L2) | `correlation_layers.py` | ? | ? | ? |
| 9 | Cascade detection (L3) | `correlation_layers.py` | ? | ? | ? |
| 10 | Decay curves (L4) | `correlation_layers.py` | ? | ? | ? |
| 11 | N=1 effort classification | `effort_classification.py` | ? | ? | ? |
| 12 | Training Story Engine | `training_story_engine.py` | ? | ? | ? |
| 13 | Readiness score | `readiness_score.py` | ? | ? | ? |
| 14 | Daily intelligence rules | `daily_intelligence.py` | ? | ? | ? |
| 15 | Campaign detection | `campaign_detection.py` | ? | ? | ? |

For each "?" — fill in the actual state. Specifically:

- **Weather normalization:** `heat_adjustment_pct` and `dew_point_f` are on every `Activity` record. Is this field exposed in any API response? Does any frontend component render it? The home page `LastRun` response model does NOT include `heat_adjustment_pct`. The activity detail page does NOT show weather-adjusted pace. The tools page has a heat-adjusted pace calculator but it's generic (not personal).

- **Shape sentences:** The `resolved_title` flows to activity detail and activity list. Verify: does the home page `LastRun` hero actually render `resolved_title`? Check `apps/web/app/home/page.tsx` — we found zero matches for `shape_sentence`, `heat_adjustment`, `weather`, `fingerprint`, or `finding` in the home page frontend code.

- **Correlation findings:** These are consumed by `_build_rich_intelligence_context` (source 8) and `compute_coach_noticed` (path 1b) — both feed the LLM briefing. But is there ANY direct rendering of findings on ANY frontend page? Check the progress page (`/progress`) — it has a D3 correlation web. What data does it query? Does it read from `CorrelationFinding` or does it recompute live?

- **Layer data (L1-L4):** Threshold values, asymmetry ratios, cascade chains, decay half-lives are stored on `CorrelationFinding`. They now flow into the morning voice via the fingerprint context. But are they visible ANYWHERE as structured data (not LLM prose)? Any API endpoint that returns them directly?

- **Investigation results / AthleteFinding:** Are these visible on ANY page besides feeding the LLM briefing prompt?

- **Campaign detection:** `campaign_detection.py` produces campaigns stored in `PerformanceEvent.campaign_data`. The training story engine now reads from this. But does any frontend surface show campaign information directly?

### What we need answered:
- For each of the 15 capabilities: is the athlete-facing visibility (a) direct/structured, (b) indirect/LLM-mediated, or (c) invisible?
- Which capabilities have API endpoints that expose their data but no frontend consuming them?
- Which capabilities have neither API exposure nor frontend rendering?

---

## Area 3: Morning Voice Prompt — Internal Repetition

### Context
Today's home page shows two paragraphs in `morning_voice` that restate the same finding:

> "7.5 hours of sleep last night. Your readiness today is good — and your body tends to run its most efficient about 3 days after days like this. Race week timing is lining up."

> "Your body consistently runs more efficiently about 3 days after you report feeling good — and today you checked in with good readiness and 7.5 hours of sleep. That means Wednesday through Friday of race week, your efficiency should be at its best, which is exactly when you want it peaking heading into Sunday's marathon."

Both paragraphs reference the same 3-day readiness→efficiency finding. The second restates the first with more words.

### What to trace

1. **`schema_fields["morning_voice"]`** in `home.py` (around line 1468 after the lanes fix). What is the current character limit? Is there a paragraph count constraint? The original spec said "40-280 characters" but the output is clearly exceeding that.

2. **The `fingerprint_summary` lane snippet** that feeds into `morning_voice`. How is it built? Does it contain multiple findings or one? If it contains one finding, why is the LLM restating it twice?

3. **What we need answered:**
   - What is the current character/length constraint on `morning_voice`?
   - Is the LLM ignoring the constraint, or is the constraint missing/wrong?
   - Proposed fix: tighten to "One paragraph only. 40-280 characters. Do not restate the same finding in different words."

---

## Area 4: Belle Vignes Cold-Start Experience

### Context
Belle Vignes just signed up, connected, backfilled, and created a plan. She is the first real beta tester who isn't the founder or his father. She has zero confirmed correlation findings, zero investigation results (those need the daily fingerprint refresh to run), and a limited activity history.

### What to trace

1. **What does Belle's home page show right now?** Trace `get_home_data()` for an athlete with:
   - No `CorrelationFinding` rows
   - No `AthleteFinding` rows  
   - Possibly no `DailyCheckin` rows
   - Limited activities (how many does she have? Check the DB if possible, or estimate from "connected, backfilled")
   - An active training plan (she created one)

2. **What does `_build_rich_intelligence_context` return for Belle?** Each of the 8 sources (now 7, after removing source 1). Which ones produce data? Which return empty?

3. **What does `compute_coach_noticed` return for Belle?** The fingerprint path requires `times_confirmed >= 3` — she has none. The daily intelligence rules — have they run for her yet? (They run on a 15-minute schedule checking for 5 AM local time.) The home signals, insight feed, hero narrative fallbacks — which one fires?

4. **What does the LLM produce when the context is thin?** The `fingerprint_summary` lane snippet will be empty. The `coach_noticed_source` will be from a fallback. Several lane snippets will say "No data for this field." Does the LLM produce a decent briefing from thin data, or does it hallucinate/pad?

5. **Briefing generation timing for Belle:** With fewer intelligence sources, is her briefing faster to generate? Or does the prompt assembly still make all the same DB queries regardless?

6. **What does Belle see on the progress page?** The D3 correlation web needs correlation data. What renders when there are no correlations?

7. **What does Belle see on activity detail?** `resolved_title` — does it work for her activities? Shape sentences — has the shape pipeline run on her backfilled activities?

### What we need answered:
- Is Belle's experience currently "empty but honest" or "broken/confusing"?
- Are there any error states (500s, empty renders, loading spinners that never resolve) for a new athlete?
- What's the minimum data threshold before the home page starts producing useful intelligence for a new athlete?

---

## Area 5: Garmin Attribution Regression

### Context
Earlier today, the founder reported "all the Garmin attributions are gone." Activities that previously showed Garmin device info were showing differently. Builder instructions were written for this (`docs/BUILDER_INSTRUCTIONS_2026-03-09_GARMIN_ATTRIBUTION.md` or similar — check if this exists and was deployed).

### What to trace

1. **Activity `provider` and `device_name` fields:** How are these set during ingestion? Check `strava_tasks.py` and `garmin_webhook_tasks.py`. When both Garmin and Strava have the same activity, which one wins?

2. **Duplicate resolution:** `di1_autoconfirm.py` or similar dedup logic. When a Garmin activity and Strava activity are matched as duplicates, which record survives? Does the surviving record preserve the Garmin device attribution?

3. **The `LastRun` response on the home page** includes `provider` and `device_name`. What values does the founder's most recent activity have?

4. **What we need answered:**
   - Is the Garmin attribution issue fixed (was it part of today's deploys)?
   - If not, what's the root cause — dedup keeping Strava record over Garmin, or field not being preserved during merge?

---

## Deliverable Format

For each area, provide:
1. **Code trace** — actual function calls, line numbers, query counts
2. **Current state** — what's working, what's broken, what's missing
3. **Severity** — blocking (must fix before Path A), degraded (fix alongside), cosmetic (queue)
4. **Recommended fix** — specific code changes, not general advice

Prioritize Area 1 (speed) and Area 4 (Belle) — these determine whether we can build Path A or need to fix the foundation first.

---

## Files to Read (Minimum)

| File | Why |
|---|---|
| `apps/api/routers/home.py` | Home endpoint, briefing generation, compute_coach_noticed, intelligence context |
| `apps/api/services/home_briefing_cache.py` | Cache TTL, stale logic, circuit breaker |
| `apps/api/tasks/home_briefing_tasks.py` | Worker-path briefing generation |
| `apps/api/celerybeat_schedule.py` | All periodic tasks and their schedules |
| `apps/api/services/fingerprint_context.py` | How findings are formatted for prompts |
| `apps/api/routers/activities.py` | Activity endpoints, what fields are exposed |
| `apps/api/services/correlation_persistence.py` | Finding lifecycle, surfacing threshold |
| `apps/api/services/campaign_detection.py` | Campaign data production |
| `apps/api/services/training_story_engine.py` | Campaign consumption after fix |
| `apps/api/tasks/intelligence_tasks.py` | Fingerprint refresh, correlation sweep |
| `apps/api/tasks/strava_tasks.py` | Post-sync processing, dedup |
| `apps/web/app/home/page.tsx` | Frontend — what fields does it actually render? |
| `apps/web/app/activities/[id]/page.tsx` | Frontend — activity detail rendering |
| `apps/web/app/activities/page.tsx` | Frontend — activity list rendering |
| `apps/web/app/progress/page.tsx` | Frontend — progress page, correlation web |
| `apps/api/routers/progress.py` | Progress endpoint — what data does it return? |
