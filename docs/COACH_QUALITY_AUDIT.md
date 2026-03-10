# Coach Quality Audit — Scoped and Queued

**Date:** March 8, 2026
**Priority:** P1 — queue after fingerprint intelligence wiring deploys
**Status:** Scoped, not yet assigned to builder
**Evidence:** Full coach conversation transcripts reviewed by top advisor (Feb 15 - Mar 8, 2026)

---

## The Problem

The AI coach is failing at the fundamentals. The founder has not had a single good coach conversation. The system has 22-24 tools, confirmed personal findings, weather normalization data, and a training calendar — and the coach reads dashboard numbers back to the athlete, lectures on basic concepts, hallucinates external facts, and follows a rigid template that makes every response sound identical.

**Root cause discovery:** 95% of coach conversations route to Gemini 2.5 Flash (being upgraded to Gemini 3 Flash — see `BUILDER_INSTRUCTIONS_2026-03-08_FOUNDER_OPUS_ROUTING.md`). Opus handles only messages containing injury/pain keywords (budget: 3 Opus requests/day, but founder/VIP routing fix will give founder always-Opus). The quality problems — template responses, data regurgitation, hallucination, math errors, missed context — are overwhelmingly Gemini problems. The one decent coaching stretch in the full transcript was the shin conversation, which routed to Opus via the "shin" and "sore" keywords.

**Model upgrade decision (March 8, 2026):** Gemini 2.5 Flash → Gemini 3 Flash (NOT 3.1 Flash Lite). Flash Lite was rejected because it's optimized for bulk classification/translation, has reported tool-calling failures (early response truncation, refusing intrinsic knowledge when tools supplied), and doesn't have the reasoning depth coaching requires. Gemini 3 Flash scores 90.4% on GPQA Diamond (vs 82.8% for 2.5 Flash), has improved tool calling, and supports adjustable thinking levels.

---

## Failure Catalog (from founder's actual conversations)

### F1: Reads data back instead of coaching from it

The athlete asked "Am I ready today?" The coach responded with "Your TSB is +17.3, which is Fresh for You." The athlete said "that is nothing I couldn't see myself." The coach then EXPLAINED what TSB means in more detail.

A coach should say what the athlete CAN'T know: patterns across weeks, what today's freshness means in the context of 6 months of training, how it compares to their best race prep. Not recite numbers the athlete already sees on screen.

**Fix:** Add to system prompt: "Never recite metrics the athlete can see on their dashboard. Your job is to interpret patterns across time, connect data points the athlete can't connect themselves, and say what the numbers MEAN for their specific situation. If your response could be replaced by reading a dashboard, you've failed."

### F2: A-I-A template kills every response

Every single response follows "Assessment → Implication → Action." Every one. The founder's Operating Contract says: "A template gets old the second time you read it." The coach uses the same template every time. It's mechanical, not conversational.

**Fix:** Remove the rigid A-I-A structure from the system prompt. Replace with: "Be conversational. Lead with what matters most. If the athlete needs to know one thing, say that thing first. You are not writing a medical report — you are coaching a human being who wants to know what to do and why."

### F3: Doesn't know what day it is / what's happening today

On race day (10-mile state record attempt), the coach gave generic taper advice instead of acknowledging the race. The training plan had "B2W (tune_up_race)" for that day. The coach has `get_calendar_day_context` and `get_plan_week` tools. It didn't call them.

**Fix:** Add a deterministic pre-check before LLM generation. Before sending any message to the model:
1. Call `get_calendar_day_context(today)` 
2. If today has a race or key workout, inject it as the FIRST line of context: "TODAY IS RACE DAY: [race name]. Lead with this. Do not discuss anything else until you've addressed the race."
3. If yesterday had a race or key workout and it hasn't been discussed, inject: "YESTERDAY WAS RACE DAY: [race name]. The athlete's race data is available. Lead with it."

This is not an LLM decision — it's a deterministic guardrail. The model should NEVER be in a position where it doesn't know it's race day.

### F4: Reflexive conservatism / safety-first bias

The athlete said they planned to race at 6:40 pace. The coach "strongly advised against." The athlete's own data showed they ran 6:39 for a half marathon. The athlete said "I don't care about the risks." The coach kept counseling caution. The athlete said "if I listen to you there is ZERO chance of performing." The coach STILL recommended rest.

The Operating Contract is explicit: "Fatigue is a stimulus for adaptation, not an enemy to eliminate. The system must never prevent a breakthrough by 'protecting' the athlete from productive stress."

**Fix:** Add to system prompt: "This is a competitive athlete, not a patient. When they tell you their race plan, help them execute it well — do not talk them out of it. When they say they're pushing through fatigue deliberately, respect that decision and coach them on how to do it safely. You are their coach, not their doctor. Match their ambition. Push back only when the data shows a clear, specific, evidence-based risk — not a general 'be careful.'"

### F5: Hallucinates external facts

The coach stated the BQ qualifying time as 3:35:00 with full confidence. The actual time is 3:30:00. The system doesn't have BQ standards in its data. Instead of saying "I don't have current BQ standards," it fabricated a number that would have led to a wrong race plan.

**Fix:** Add to system prompt: "You do NOT have access to external qualifying standards, course records, race results databases, or any information outside the athlete's training data and your tools. If the athlete asks about qualifying times, course details, competitor data, or anything not in your tools — say 'I don't have that data.' NEVER fabricate external facts. A wrong qualifying time could ruin a race."

Additionally: add a deterministic check — if the model's response contains a time formatted as H:MM:SS that wasn't sourced from a tool result, flag it for review.

### F6: Math errors on high-stakes race decisions

The athlete said BQ is 3:30, needs 7.5 min buffer = 3:22:30. The coach came back with "3:27:30" and calculated 7:55/mi. Wrong subtraction, wrong pace calculation. This was for a race-week decision.

**Fix:** The system prompt already says "NEVER compute math yourself — use the compute_running_math tool." The model is ignoring this. Reinforce: "For ANY pace, distance, or time calculation, you MUST call compute_running_math. Your mental math is unreliable. A wrong pace calculation before a race is dangerous. Call the tool. Every time."

### F7: Lectures experienced athletes on basics

"Think of CTL as your engine size. ATL is like the wear and tear on your engine." This is a 57-year-old who ran in college, still runs competitively, coaches his 79-year-old father, and has read every book on running. The system prompt says "use plain English, never acronyms." The coach used the acronyms AND explained them condescendingly.

**Fix:** Add to system prompt: "This athlete is experienced. They know what a tempo run is, what cardiac drift means, what a taper does. NEVER explain basic running concepts. If you find yourself defining a term, stop — the athlete already knows it. Speak to them as a peer, not a student."

For the Gemini path specifically, inject the athlete's experience level from their profile into the brief: "Experience: ran in college, 40+ years of competitive running, coaches other runners."

### F8: Sycophantic recovery pattern

Every correction is followed by groveling: "My deepest apologies," "You are absolutely right, my apologies," "I sincerely apologize." A real coach says "You're right, I missed that" and moves on.

**Fix:** Add to system prompt: "When corrected, acknowledge briefly and move forward. 'Good catch — here's the updated picture.' Do not apologize repeatedly. Do not grovel. The athlete respects directness, not deference."

### F9: Can't see data that exists in the system

The race had been processed for 24+ hours. The coach said "I can't see it" and told the athlete to check their Garmin sync. This is a tool-call failure — the coach either didn't call `get_recent_runs` or called it with wrong parameters.

**Fix:** When the athlete says they completed a run, ALWAYS call `get_recent_runs` with sufficient lookback (7 days minimum). If the tool returns no results, say "I'm not finding it in the data yet — let me check again" and retry with broader parameters. NEVER tell the athlete the data isn't synced without actually checking first.

### F10: Ignores previously shared context

The athlete explained their taper philosophy ("I don't do gradual taper, it doesn't work for me"). The coach kept recommending gradual taper. The athlete said sleep was already optimized. The coach brought up sleep two weeks later with the same advice.

**Fix:** This is a conversation history problem. The Gemini path injects conversation context but the model doesn't weight previous athlete statements heavily enough. Add to system prompt: "When the athlete has told you something about their preferences, philosophy, or constraints in a previous message, RESPECT it. Do not repeat advice they've already rejected. If you find yourself saying something the athlete has already pushed back on, stop."

Additionally: the `coach_intent_snapshot` tool exists for exactly this purpose. The coach should call `set_coach_intent_snapshot` to persist athlete preferences (taper style, sleep situation, etc.) and reference them in future conversations.

### F11: Weather normalization data not used

The system computed `heat_adjustment_pct` for the 10-mile race. The temperature and dew point were stored. The coach analyzed the 7:01 pace as "slower than planned 6:45" without referencing conditions. The athlete had to TELL the coach it was 83 degrees. The system already knew.

**Fix:** This is addressed by the fingerprint intelligence wiring (separate builder instructions). Once the coach brief includes weather context and confirmed findings, the coach will have this data. But additionally: when analyzing a specific activity, the coach should call `analyze_run_streams` or check the activity's weather data before commenting on pace.

---

## URGENT: Founder/VIP Routing Broken

**The founder has unlimited Opus budget (`_is_founder` → `founder_bypass`) but the routing logic ignores this.** Budget and routing are decoupled: `check_budget` says "you can use Opus" but `get_model_for_query` only sends to Opus on `is_high_stakes or is_high_complexity`. The founder's conversations route to Gemini 95% of the time despite having no budget cap.

Same for VIP athletes (Larry, Belle Vignes): even with `is_coach_vip = True`, VIP only multiplies the budget 10x — it doesn't change which queries get routed to Opus.

**Fix (in `get_model_for_query`):**
```python
# Founder always gets Opus
if athlete_id and self._is_founder(athlete_id):
    if self.anthropic_client:
        return self.MODEL_HIGH_STAKES, True
    return self.MODEL_DEFAULT, False

# VIP always gets Opus
if athlete_id and self.is_athlete_vip(athlete_id):
    allowed, reason = self.check_budget(athlete_id, is_opus=True, is_vip=True)
    if allowed and self.anthropic_client:
        return self.MODEL_HIGH_STAKES, True
    return self.MODEL_DEFAULT, False
```

Insert this BEFORE the keyword-based routing (line ~2282). This ensures the founder and VIP athletes always get Opus, period. The existing keyword routing remains for standard users.

**Larry and Belle Vignes must also have `is_coach_vip = True` set in the database.** Verify via admin panel or directly on production.

---

## Routing Expansion (Standard Users)

The current routing sends 95% of messages to Gemini based on keyword matching. This is too narrow. Queries that should route to Opus but don't:

| Query | Why it should be Opus |
|---|---|
| "Am I ready for my race today?" | Race-day decision |
| "What pace should I target for my marathon?" | Race strategy, high consequence |
| "Walk me through my progress in detail" | Requires synthesis across months |
| "What effect did today's run have on my fitness?" | Training load interpretation |
| "I got it [the state record]" | Post-race analysis, emotional moment |

**Proposed routing expansion:**

1. **Calendar-aware routing.** If today or yesterday has a race on the calendar, route to Opus automatically — regardless of message content. Race day is always high-stakes.

2. **Broader keyword set.** Add: "race", "racing", "marathon", "qualify", "BQ", "PR", "personal best", "state record", "goal pace", "race pace", "taper", "peak", "ready for", "am I ready".

3. **Increase Opus budget for active racers.** 3 requests/day is too low for an athlete in race week. Consider: 3/day baseline, 10/day during race week (defined as 7 days before a scheduled race).

4. **VIP always-Opus option.** For premium/elite tier athletes, consider routing ALL queries to Opus. The cost is manageable for a small number of high-value users and the quality difference is dramatic.

---

## Gemini Prompt Improvements (for the 95% that stays on Gemini)

Even with better routing, Gemini will handle most conversations. Its prompt needs to be harder-edged:

1. Remove A-I-A template structure
2. Add "never recite dashboard numbers" instruction
3. Add "never explain basic concepts to experienced athletes" instruction
4. Add "match the athlete's ambition" instruction
5. Add "when corrected, acknowledge briefly and move on" instruction
6. Add "NEVER fabricate external facts" instruction
7. Reinforce "ALWAYS use compute_running_math for calculations" instruction
8. Add deterministic race-day pre-check before LLM call

---

## Deterministic Pre-Checks (before any LLM call)

These run in code, not in the prompt. They ensure the model can't miss critical context:

1. **Race day check.** Query today's and yesterday's calendar. If race exists, inject as first line of context with explicit instruction to lead with it.
2. **Recent activity check.** Query last 48 hours of activities. If new activity exists that hasn't been discussed in conversation, inject summary.
3. **Weather check.** If the most recent activity has `heat_adjustment_pct > 3%`, inject weather context.
4. **Fingerprint check.** If athlete has confirmed findings that relate to current conversation context (sleep discussion + sleep finding exists), inject the specific finding.

These are cheap (database queries, no LLM cost) and prevent the worst failures.

---

## Testing

### Scenario tests (new file: `tests/test_coach_quality.py`)

1. `test_race_day_context_injected` — if today has a race, verify the race name appears in the first line of the coach's context
2. `test_recent_activity_visible` — create an activity 2 hours ago, ask the coach about recent runs, verify it appears
3. `test_weather_context_included` — activity with `heat_adjustment_pct > 5%`, verify weather data in coach context
4. `test_no_aia_template_in_response` — verify response doesn't contain "Assessment:" and "Implication:" and "Action:" as section headers
5. `test_math_uses_tool` — ask a pace calculation question, verify `compute_running_math` was called
6. `test_no_fabricated_qualifying_times` — ask about BQ time, verify response says it doesn't have that data
7. `test_race_week_routing` — message during race week, verify routing logs show Opus selection
8. `test_experienced_athlete_no_lecture` — ask about training load, verify response doesn't define CTL/ATL/TSB

---

## Build Sequence

1. Deterministic pre-checks (race day, recent activity, weather) — highest impact, no LLM cost
2. System prompt rewrites (both Gemini and Opus) — fixes F1-F8, F10
3. Routing expansion — broader keywords + calendar-aware + race-week budget
4. Testing — scenario tests against the specific failure patterns

---

## Success Criteria

The founder opens the coach and asks "Am I ready for my race?" The coach:
- Knows it's race day without being told
- References the athlete's confirmed sleep pattern and last night's sleep
- Cites the weather forecast if relevant
- Says what the data means for THIS race, not what TSB means in general
- Uses the athlete's own stated race strategy (7:44/mi for BQ with buffer)
- Does not lecture, does not template, does not apologize, does not hallucinate

The athlete's response is not "that is nothing I couldn't see myself."
