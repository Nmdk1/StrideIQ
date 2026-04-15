# Briefing Fix Notes

Parked issues to address when we return to briefing quality.

---

## 1. Model: Kimi K2 Turbo is primary for ALL athletes

Production has `BRIEFING_PRIMARY_MODEL=kimi-k2-turbo-preview`. Briefings degraded after this switch from Claude Sonnet. Cannot switch back due to cost. Fix must be better prompts/context, not model swap.

## 2. Temporal lifecycle: system has no concept of post-race

- `build_athlete_brief()` sends negative "days away" for completed races (e.g. "-14 days away")
- No state transition: plan stays "active" after race date passes
- LLM anchors on marathon context weeks after the race
- Coach told founder to "stay off legs tomorrow" 2 weeks post-marathon during normal training
- Briefing cache fingerprint did NOT include calendar date (fix was staged but needs verification)

## 3. Run comparisons ignore environmental context

**Critical.** The briefing has compared the founder's March run to a July run THREE times. July was 100F+ with dew points in the 70s. March is completely different conditions. Comparing pace/HR across those conditions is meaningless and makes the system look stupid.

**Rule:** When comparing runs across time, the system MUST account for temperature and humidity. Valid comparisons:
- Same conditions (similar temp/humidity)
- Year-over-year same month (March 2025 vs March 2026)
- Environmental adjustment applied (heat-adjusted pace)

**Invalid comparisons:**
- March to July with no environmental context
- Any cross-season comparison that ignores weather

The LLM prompt needs an explicit constraint: "When comparing to historical runs, only compare to runs in similar environmental conditions (within 10F and similar humidity) OR apply heat adjustment. NEVER compare a cool-weather run to a hot-weather run without noting the conditions."

## 4. Generic coaching voice / rest day hallucination

- "protect tomorrow's rest" — telling a healthy, recovered runner to rest is bad coaching
- "guard that with a true rest day today" — told to athlete ON a build-back week where they run 6 days straight
- "the cheapest way to keep that pattern paying off" — template filler
- The operating contract bans template narratives: "Either say something genuinely contextual or say nothing at all"
- The LLM has NO visibility into the athlete's weekly training pattern (6 days/wk, rest Mondays). It defaults to recommending rest after any moderate effort. Fix: inject weekly schedule pattern and current week context (build week, cutback, rest day already taken, etc.)

## 6. Sleep schedule: LLM invents bedtime without data

- "lights-out by 10:15 tonight" — the founder goes to sleep at 6:30 PM and wakes at 1:30–2:00 AM every day. 10:15 PM is 4 hours AFTER he's asleep.
- The LLM is fabricating a "normal" bedtime because it doesn't have the athlete's actual sleep schedule.
- **Rule:** If the system has Garmin sleep data, use it to determine the athlete's actual sleep schedule. If it does NOT have sleep data, do NOT mention bedtime or sleep timing at all. Suppression over hallucination.
- Garmin sleep data exists (GarminDay table has sleep_total_s, sleep fields). The brief should include typical bedtime/wake time derived from the last 7-14 days of Garmin sleep data, or say nothing.

## 7. "Yesterday's" when run was today — cache staleness

- Briefing said "Yesterday's 12.0 miles" when the run was 5 hours ago (today).
- Root cause: TWO separate cache layers (task-based fingerprint in `home_briefing_tasks.py` and inline cache in `home.py`) did not include the calendar date in the cache key. A briefing generated yesterday with similar data would be served today.
- Fixed (2026-03-24): added `date.today().isoformat()` to both cache fingerprints.
- NOTE: The task-based fix was originally applied 2026-03-22 but was overwritten by Northstar's lint sweep commit `3f3d0e2`. Must protect this file from bulk lint operations.

## 5. Cache source_model is wrong

`write_briefing_cache` always writes `source_model = "claude-sonnet-4-6"` regardless of which model actually generated the briefing. Can't evaluate model quality from cache metadata.
