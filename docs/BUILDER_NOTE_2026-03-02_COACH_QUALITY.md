# Builder Note: Coach Quality — Health API Data + Insight Staleness + Hallucinations

**Date:** 2026-03-02
**Assigned to:** Builder
**Advisor sign-off required:** Yes
**Urgency:** High — coach is the strongest surface in the product, and it's currently broken in multiple ways

---

## Before Your First Tool Call

Read in order:
1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `docs/SITE_AUDIT_LIVING.md`
4. `docs/AGENT_WORKFLOW.md`
5. This builder note

---

## Problem Statement

Three distinct coach quality failures observed in production on March 2, 2026:

### Issue 1: No Garmin Health API data in coach context (CRITICAL)

The coach's `build_context()` method in `apps/api/services/ai_coach.py` (line ~1821) only queries `DailyCheckin` for wellness data. This is athlete self-reported data (motivation, sleep quality, soreness, stress).

**It never queries `GarminDay`** — which contains Garmin Health API data: watch-measured sleep duration, HRV, stress score, resting heart rate.

The coach literally cannot reference Health API data because it doesn't exist in the prompt context. When asked "how is my body responding based on my watch data?", the coach returned only Activity API metrics (mileage, TSB) and ignored sleep, HRV, and resting HR entirely.

The `get_wellness_trends` tool (line ~798) description says "from daily check-ins" — verify whether this tool also only queries `DailyCheckin` or if it already includes `GarminDay`. If it only queries check-ins, it needs the same fix.

**Evidence:** Founder asked: "Based on my watch data over the past two weeks, how is my body responding to the taper? Am I recovering well enough for Tobacco Road?" — response contained zero Health API data. No sleep hours, no HRV, no resting HR, no stress scores.

### Issue 2: Home briefing insight staleness (MEDIUM)

The `coach_noticed` section of the home briefing has been repeating the same "efficiency improved 4.4% over the last two weeks" message for 4 days despite:
- A 13-mile marathon pace run on Saturday
- A 5-mile recovery run on Sunday
- Daily check-ins with varying data

The intelligence pipeline's `EFFICIENCY_BREAK` rule keeps firing because the efficiency improvement is sustained. The LLM then keeps choosing it as the lead insight for `coach_noticed`. There is no mechanism to:
- Track which insights have already been shown to the athlete
- Rotate or suppress recently-surfaced insights
- Prioritize newer, more actionable signals over persistent background trends

**Evidence:** Redis-cached briefing regenerated 5 times on Mar 2 with same fingerprint `4cb8f3cf` — all producing the same efficiency narrative.

### Issue 3: Coach hallucinations (HIGH)

In the same coach response, multiple factual errors:

1. **"shin soreness you've experienced this week"** — Founder's check-in on the day the question was asked: Soreness = None. No shin soreness exists in any recent check-in data.
2. **"Saturday's planned 15-miler with 7:10 pace work"** — The actual weekly plan shows Saturday = 10 miles, not 15.
3. **"your decision to cut runs short this week"** — It was Monday morning. No runs had occurred yet this week.

These hallucinations may be caused by the coach referencing stale or incorrect plan/workout data in its context, or by the LLM confabulating details that aren't in the prompt.

### Issue 4: Context distances in km (LOW — cosmetic)

The `build_context()` method internally formats distances in kilometers (lines 1783, 1791, 1803, 1815) before passing to the LLM. The LLM is converting to miles in its output, so user-facing responses are correct. However, feeding km into the prompt risks the LLM occasionally outputting km. Consider converting to miles in the context itself for consistency.

---

## Scope

### In scope

- Add `GarminDay` data to `build_context()` in `ai_coach.py`: last 7 days of watch-measured sleep, HRV, stress, resting HR
- Verify and fix `get_wellness_trends` tool to include `GarminDay` data
- Add Garmin attribution in coach context when Health API data is included (e.g., "from Garmin watch")
- Convert all distances in `build_context()` from km to miles
- Investigate hallucination sources: verify plan/workout data in context matches actual DB state
- Add basic insight rotation for `coach_noticed` in home briefing (track last-shown insight, suppress for 48h minimum)

### Out of scope

- Rewriting the entire intelligence pipeline
- Changes to the 8 intelligence rules themselves
- Coach UI changes
- Runtoon or share flow changes

---

## Implementation Notes

### Files to change

| File | Change |
|------|--------|
| `apps/api/services/ai_coach.py` `build_context()` (~line 1821) | Add `GarminDay` query for last 7 days: `sleep_total_s`, `hrv_overnight_avg`, `avg_stress`, `resting_hr`, `sleep_score`. Format as "## Garmin Watch Data (Health API)" section. Convert all distances from km to miles. |
| `apps/api/services/ai_coach.py` `get_wellness_trends` tool call handler (~line 911) | Verify it queries `GarminDay` in addition to `DailyCheckin`. If not, add `GarminDay` data. |
| `apps/api/services/coach_tools.py` `get_wellness_trends()` | If this function only queries `DailyCheckin`, add `GarminDay` as a data source. |
| `apps/api/services/home_briefing.py` or equivalent | Add insight rotation: track `last_coach_noticed_insight_id` in Redis, suppress same insight for 48h. |

### GarminDay fields available (actual model fields)

From `apps/api/models.py`, the `GarminDay` model includes:
- `sleep_total_s` — total sleep in seconds (convert to hours for display)
- `sleep_score` — sleep score (0-100)
- `hrv_overnight_avg` — overnight HRV average (ms)
- `avg_stress` — average daily stress score
- `resting_hr` — resting heart rate from watch
- `body_battery_end` — end-of-day Body Battery
- `steps` — daily step count
- `active_kcal` — active calories burned

### Coach context format (proposed)

```
## Garmin Watch Data (last 7 days)
  03/01: Sleep: 6.1h | HRV: 42ms | Resting HR: 52 bpm | Stress: 28
  02/28: Sleep: 7.2h | HRV: 45ms | Resting HR: 51 bpm | Stress: 24
  02/27: Sleep: 6.8h | HRV: 39ms | Resting HR: 53 bpm | Stress: 31
  ...
```

### Distance conversion

Replace all instances of `/ 1000` (meters to km) with `/ 1609.344` (meters to miles) in `build_context()`. Update format strings from "km" to "mi".

### Founder decisions (non-negotiable)

1. **Never display in meters or km.** Always miles.
2. **The athlete decides, the system informs.** Coach observes, never prescribes without evidence.
3. **Suppression over hallucination.** If data is missing, say nothing. Never fabricate.
4. **Garmin Health API data must surface in coach context** — this is both a product quality requirement and a Garmin partner compliance requirement (demonstrating Health API usage in the product).

---

## Tests Required

### Unit tests

- `test_build_context_includes_garmin_day` — verify GarminDay data appears in context string when available
- `test_build_context_no_garmin_day_graceful` — verify context builds cleanly when no GarminDay records exist
- `test_build_context_distances_in_miles` — verify all distances are in miles, not km
- `test_wellness_trends_includes_garmin_data` — verify `get_wellness_trends` returns GarminDay data
- `test_insight_rotation_suppresses_repeat_48h` — freeze time and verify same insight is suppressed for 48h in `coach_noticed`
- `test_coach_no_fabricated_soreness` — when latest soreness is null/none, coach context/output must not claim soreness
- `test_coach_plan_distance_matches_db` — coach context for planned long run distance must match `PlannedWorkout`/`TrainingPlan` records
- `test_coach_no_this_week_runs_before_week_start` — on Monday pre-run state, coach must not claim "you cut runs short this week"

### Production smoke checks

```bash
# 1. Verify GarminDay data exists for founder
docker exec strideiq_api python -c "
from core.database import SessionLocal
from models import GarminDay, Athlete
db = SessionLocal()
a = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
days = db.query(GarminDay).filter(GarminDay.athlete_id==a.id).order_by(GarminDay.calendar_date.desc()).limit(7).all()
for d in days:
    print(f'{d.calendar_date}: sleep={d.sleep_total_s}s hrv={d.hrv_overnight_avg} rhr={d.resting_hr} stress={d.avg_stress}')
db.close()
"

# 2. Ask coach about watch data and verify Health API metrics appear in response
# (manual — check coach chat UI)

# 3. Verify home briefing rotates insight after fix
# (manual — check home page across two consecutive days)
```

---

## Acceptance Criteria

- [ ] AC1: Coach `build_context()` includes GarminDay data (sleep hours, HRV, resting HR, stress) for last 7 days
- [ ] AC2: Coach response to "how is my recovery based on my watch data?" references specific Health API metrics
- [ ] AC3: All distances in coach context are in miles, not km
- [ ] AC4: `get_wellness_trends` tool returns GarminDay data alongside DailyCheckin data
- [ ] AC5: Home briefing `coach_noticed` suppresses repeated insight for 48h, verified by deterministic time-frozen test
- [ ] AC6: No hallucinated plan details — workout context matches actual DB state
- [ ] AC7: Graceful degradation — coach works normally for athletes without Garmin data
- [ ] AC8: Tree clean, tests green, production healthy

---

## Evidence Required in Handoff

1. Scoped file list changed (no `git add -A`)
2. Verbatim test output for all new unit tests and any touched integration tests
3. Production verification output for the smoke checks above
4. Screenshot evidence:
   - Home briefing showing Garmin Health API-derived signals
   - Coach chat question + response referencing watch data (sleep/HRV/resting HR/stress)
5. Any relevant logs proving no fabrication and correct plan-context grounding

---

## Mandatory: Site Audit Update

`docs/SITE_AUDIT_LIVING.md` must be updated in the same session for every material ship.

Required update block in the delivery pack:

1. Exact section(s) updated in `docs/SITE_AUDIT_LIVING.md`
2. What changed in product truth (not plan text):
   - Coach context now includes GarminDay Health API signals
   - Distances normalized to miles in coach context
   - Coach-noticed insight rotation suppression added
   - Hallucination guardrails/tests added for coach grounding
3. Any inventory count/surface/tool updates

No task is complete until this is done.
