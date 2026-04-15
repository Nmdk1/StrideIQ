# Builder Instructions: Weekly Digest Email Quality Fix

**Priority:** High — emails are going to real athletes right now with broken formatting  
**Scope:** 1 file change + 1 import  
**Risk:** Low — email formatting only, no backend logic changes

---

## Context

The weekly digest email ("Your Weekly Performance Insights") has three problems visible in production screenshots:

1. **`{analysis_period_days}` not interpolated** — the HTML template shows the literal placeholder
2. **Raw internal metric names** — athletes see "Garmin Hrv 5Min High", "Feedback Leg Feel", "Dew Point F" instead of human-readable names
3. **No directionality** — "Activity Intensity Score explains 95% of efficiency gains" doesn't tell the athlete whether MORE or LESS intensity is better

---

## Bug 1: Template Variable (30 seconds)

**File:** `apps/api/services/email_service.py`, line 106

The HTML intro line is a plain string, not an f-string. The plain-text version on line 143 is correct.

**Fix:** Change line 106 from:
```python
"<p>Here's what the data says about your performance over the last {analysis_period_days} days.</p>",
```
to:
```python
f"<p>Here's what the data says about your performance over the last {analysis_period_days} days.</p>",
```

---

## Bug 2: Human-Readable Metric Names (10 minutes)

**The mapping already exists.** `apps/api/services/n1_insight_generator.py` exports `friendly_signal_name()` with 100+ mappings. Examples:

| Internal key | Current email display | `friendly_signal_name()` output |
|---|---|---|
| `garmin_hrv_5min_high` | "Garmin Hrv 5Min High" | "Recovery HRV" |
| `feedback_leg_feel` | "Feedback Leg Feel" | "leg freshness" |
| `dew_point_f` | "Dew Point F" | "dew point" |
| `garmin_active_time_s` | "Garmin Active Time S" | "daily active time" |
| `activity_intensity_score` | "Activity Intensity Score" | "session intensity" |
| `garmin_sleep_deep_s` | "Garmin Sleep Deep S" | "deep sleep time" |
| `sleep_quality_1_5` | "Sleep Quality 1 5" | "sleep quality" |
| `consecutive_run_days` | "Consecutive Run Days" | "consecutive running days" |

**Fix:** In `email_service.py`:

1. Add import at top:
```python
from services.n1_insight_generator import friendly_signal_name
```

2. Replace ALL four instances of:
```python
input_name = correlation['input_name'].replace('_', ' ').title()
```
with:
```python
input_name = friendly_signal_name(correlation['input_name']).capitalize()
```

There are 4 occurrences: lines 113, 127, 149, 161.

---

## Bug 3: Directionality — Tell the Athlete WHAT to Do (30 minutes)

This is the most important fix. The current phrasing:
> **Session intensity** explains 95% of your efficiency gains. Pattern holds over 7 runs.

Does not tell the athlete whether higher or lower intensity is better. The correlation data has `correlation_coefficient` and `direction` — use them.

The correlation data from `digest_tasks.py` already separates into `what_works` (negative correlation = better efficiency) and `what_doesnt_work` (positive correlation = worse efficiency). But the email doesn't use the sign to tell the athlete the direction.

**Fix the "What's Working" section** to include direction:

The correlation object has `correlation_coefficient` (negative = good for efficiency in this context) and `direction`. Use the sign to determine if MORE or LESS of the input helps.

For "What's Working" items (negative correlation = the input improves efficiency):
- If the metric naturally increases as a positive (e.g., sleep, HRV, deep sleep): "**More deep sleep time** drives your best efficiency"
- If the metric naturally increases as a negative (e.g., stress, dew point): "**Lower dew point** drives your best efficiency"

Rather than trying to solve the semantic direction for every metric, use this simpler approach that's always accurate:

**What's Working:**
```
"<strong>{input_name}</strong> is one of your strongest efficiency drivers — confirmed over {sample_size} runs."
```

**What Doesn't Work:**
```
"<strong>{input_name}</strong> is dragging your efficiency down — confirmed across {sample_size} runs."
```

This removes the confusing "explains X% of your efficiency gains" phrasing (which Brian couldn't parse) and replaces it with clear athlete language. The percentage can appear as secondary detail if desired, but the primary message should be the human-readable verdict.

**Even better — if you want to include the direction for metrics where it's obvious:**

Add a small helper dict or use the correlation coefficient sign to determine "more" vs "less":

```python
HIGHER_IS_BETTER = {
    "garmin_sleep_score", "garmin_sleep_deep_s", "garmin_hrv_5min_high",
    "sleep_hours", "sleep_h", "sleep_quality_1_5", "feedback_leg_feel",
    "feedback_energy_pre", "garmin_body_battery_end",
}
LOWER_IS_BETTER = {
    "dew_point_f", "garmin_avg_stress", "garmin_max_stress",
    "garmin_sleep_awake_s", "stress_1_5", "soreness_1_5",
}
```

For metrics in `HIGHER_IS_BETTER`: "**More deep sleep time** drives your best running"
For metrics in `LOWER_IS_BETTER`: "**Lower dew point** drives your best running"
For everything else: "**{name}** is one of your strongest efficiency drivers"

This is optional for v1 — the simpler phrasing without direction is still a massive improvement over the current raw output.

---

## Summary of Changes

| File | Change |
|---|---|
| `apps/api/services/email_service.py` line 106 | Add `f` prefix to HTML template string |
| `apps/api/services/email_service.py` top | Add `from services.n1_insight_generator import friendly_signal_name` |
| `apps/api/services/email_service.py` lines 113, 127, 149, 161 | Replace `.replace('_', ' ').title()` with `friendly_signal_name().capitalize()` |
| `apps/api/services/email_service.py` lines 116-117, 130-131, 151-153, 163-165 | Rewrite finding phrasing to athlete language |

---

## Verification

After changes, run:
```bash
python -m pytest tests/ -k "digest or email" -x -q
```

Then manually trigger a digest for the founder to verify the email looks correct:
```python
from tasks.digest_tasks import send_weekly_digest_task
send_weekly_digest_task.delay("4368ec7f-c30d-45ff-a6ee-58db7716be24")
```

---

## Quality Principle

The correlation engine is doing real science. The email is the athlete's window into it. If Brian Levesque — a smart, motivated athlete — can't understand what the email is telling him, the science is wasted. Every finding must answer: **what happened, is it good or bad, and how confident are we?**
