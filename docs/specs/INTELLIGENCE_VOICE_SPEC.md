# Intelligence Voice Spec

**Date:** April 12, 2026
**Author:** Founder + advisor session
**Status:** FOUNDATIONAL — read this before touching any athlete-facing text surface
**Applies to:** Every surface that speaks to the athlete — activity page, home briefing, manual, progress, coach, daily intelligence, weekly digest

---

## The Problem

The product manifesto says: "The chart makes you open the app. The intelligence makes you trust it. The voice makes you need it." And then: "It just doesn't speak yet."

The correlation engine works. It has found genuine, statistically confirmed patterns across 797+ activities for the founder. The stream analysis computes drift, decoupling, zones, moments. The daily intelligence engine fires rules on load spikes, efficiency breaks, pace improvements. The systems are built.

But the founder — the most engaged user — doesn't read the Manual page. Ever. Doesn't read the Progress page. Ever. The activity page intelligence ("Efficiency 7.2% worse than your recent recovery runs. Check for fatigue or illness.") was confidently wrong on a perfectly executed half marathon pacing run. Strava's shallow attaboys on the same run were correct.

The problem is not the intelligence. The problem is the translation from intelligence to language.

---

## The Diagnosis

### What's broken across every surface

**1. The system says obvious things.**
"YOUR running efficiency is noticeably associated with changes the following day when your leg freshness is higher." No athlete or coach needs a computer to tell them fresh legs help performance. A finding is only worth saying if the athlete would say "I didn't know that" or "I should change something." Obvious correlations must be suppressed.

**2. The language is algorithm-speak, not coaching.**
`"Based on your data: YOUR {output} is {strength} associated with changes{timing} when your {input} is higher."` Every finding reads the same. Same structure, same cadence, same dead energy. This is a template applied to a statistical output. It is not a voice.

**3. Insights state correlations without implications.**
"X is associated with Y" — so what? What should the athlete do? What does it mean for tomorrow? The system finds patterns but never closes the loop to understanding or action.

**4. The same findings appear everywhere regardless of context.**
The activity page shows the global top-3 correlation findings — the same three on every activity, whether it's a recovery jog or a marathon. They're not filtered by relevance to what happened on this run.

**5. Metrics are interpreted through a "something is wrong" lens.**
Efficiency factor (speed/HR) penalizes deliberately slow running. A pacing run at 9:30/mi (60sec slower than easy pace) scores "low efficiency" because speed is lower at the same HR. The system assumes deviation = problem. There is no pathway for "this was intentional."

**6. Comparisons are meaningless when the purpose differs.**
Comparing a 13-mile half marathon pacing effort to 5-mile recovery jogs by speed/HR ratio tells you nothing. The system lacks purpose-awareness — it doesn't understand that different runs serve different purposes and should be evaluated on different criteria.

---

## What Good Looks Like

### The Strava floor (correct but shallow)

Same run: Hattiesburg Half Marathon 9:30 pacer. 13.2mi, 9:16/mi, 127bpm avg, 1.2% cardiac drift.

Strava's "Athlete Intelligence" per chart:
- **Pace chart:** "Your pace held steady around 9:20-9:35/mi for the first 9 miles, then picked up slightly in the final miles. Very even splits show solid pacing discipline."
- **HR chart:** "You nailed the recovery pace for most of this run (83.5%), with brief dips into faster zones near the end. Great consistency for a half marathon pacing effort."
- **HR Zones:** "You stayed almost entirely in your endurance zone (95% of the run), keeping your heart rate steady around 126 bpm. This controlled effort is perfect for a pacing run."
- **Summary:** "Your pace was a touch slower than your typical 8:39/mi average, but that's expected when you're focused on pacing others rather than pushing yourself."

What Strava got right:
- Read the title ("9:30 pacer") → understood purpose
- Per-chart intelligence tied to what you're looking at
- Compared to athlete's own history ("slower than your typical 8:39")
- Explained the deviation ("expected when pacing others")
- No warnings, no red flags on a well-executed run

What Strava lacked:
- Nothing the athlete didn't already know
- Attaboys, not insights — "nice work" doesn't teach
- No longitudinal perspective (how this compares to 3 months ago)
- No physiological depth (drift trend, decoupling, aerobic development)
- Founder's reaction: "right, but not useful. Didn't stick."

### The StrideIQ standard (correct AND deep)

Same run. What the system SHOULD have said:

**After the run (activity page):**
"You held 127bpm across 13 miles with 1.2% cardiac drift. Three months ago you were drifting 6% at the same effort over 10 miles. Your aerobic base is genuinely rebuilding."

That's one sentence. It uses data the system already has (drift trend from stream analysis history). It tells the athlete something they didn't know — that today's stability represents measurable progress from where they were post-injury. It matters to them.

**Before a run (morning briefing):**
"You got 5.2 hours last night. Your data shows your easy pace suffers by about 15 seconds/mi when you sleep under 6. Today's tempo might feel harder than it should — don't chase the pace, run by effort."

Same correlation finding as "sleep associates with pace." But framed for THIS morning, connected to TODAY's workout, with actionable guidance.

**In the manual (stepping back):**
"Your body has a clear tell: when your morning HRV drops below 45, your efficiency tanks for TWO days, not one. The standard advice is 'rest when HRV is low.' Your data says you need an extra day beyond that. This has held up 12 times."

That's a genuine N=1 finding — specific threshold, specific lag, specific to this athlete, different from the generic advice. Worth reading.

---

## Principles

### 1. Only say what the athlete doesn't already know

If the insight is obvious to anyone who runs ("fresh legs help"), suppress it. The bar for speaking is: would this make the athlete say "huh, I didn't realize that" or "I should change something"? If not, say nothing.

### 2. Answer the question the athlete is actually asking

The athlete asks different questions in different places:
- **Activity page (after a run):** "What just happened and what does it mean?"
- **Morning briefing (before a run):** "What should I know going into today?"
- **Manual/progress (stepping back):** "What have I learned about my body?"

The same underlying finding should be expressed differently depending on context. Template strings cannot do this.

### 3. Connect to the athlete's arc, not just today's numbers

"1.2% cardiac drift" is a number. "1.2% drift — down from 6% three months ago over shorter distance" is a story. The system has longitudinal data. Use it. Show trajectory, not snapshots.

### 4. Suppress over hallucinate

The operating contract says this. It applies to intelligence with extra force. If the system doesn't have enough data to say something specific and true, it must say nothing. Zero insights on an activity is better than one wrong insight. Confidence thresholds should be high, and "I don't have enough data yet" is a valid (silent) response.

### 5. Purpose-aware evaluation

Different runs serve different purposes. A pacing run at 9:30/mi should be evaluated on consistency and HR stability, not on speed/HR efficiency. A tempo run should be evaluated on pace hold vs target. A recovery run should be evaluated on whether it was actually easy. The system must understand purpose before evaluating performance.

Purpose sources (in priority order):
1. Athlete's manual classification (WorkoutTypeSelector)
2. Planned workout from training plan (if matched)
3. Activity title parsing (WorkoutClassifier already does this during sync)
4. Effort classification from metrics (current fallback — keep as last resort)

### 6. Per-chart, not per-activity

Strava puts an "Athlete Intelligence" card under each chart. That's the right granularity. An insight about pace belongs next to the pace chart. An insight about HR belongs next to the HR chart. Not one block of text trying to cover everything.

Each insight card must describe something visible in the chart it's attached to, plus the deeper context the chart alone can't show (longitudinal trend, correlation finding, plan context).

### 7. Specificity over generality

Bad: "Your efficiency is associated with leg freshness."
Good: "Your efficiency improves 15% after a rest day, but only when you sleep over 7 hours."

Bad: "Check for fatigue or illness."
Good: "Your HR was 12bpm higher than your last 3 runs at this pace — could be the heat (66F, 92% humidity) or accumulated fatigue from the 70-mile week."

Numbers. Thresholds. Conditions. Exceptions. These are what make a finding specific to one human instead of generic advice.

---

## Architecture: The Translation Layer

The translation layer sits between the intelligence systems and every athlete-facing surface. It is not a single function — it is a design principle applied consistently.

### Input: What the system knows

| System | What it provides | Where it lives |
|--------|-----------------|----------------|
| Correlation engine | Bivariate patterns with lag, strength, confirmation count | `correlation_persistence.py` |
| Stream analysis | Drift, decoupling, zones, moments, segments | `run_stream_analysis.py` |
| Run attribution | Pace decay, TSB, pre-state, efficiency comparison | `run_attribution.py` |
| Run analysis engine | Effort classification, similar-run comparison, trends | `run_analysis_engine.py` |
| Daily intelligence | Load spikes, efficiency breaks, pace improvements | `daily_intelligence.py` |
| N1 insight generator | Formatted correlation findings | `n1_insight_generator.py` |
| Workout classifier | Purpose classification from title + metrics | `workout_classifier.py` |
| Training plan | Planned workout for this day (if plan active) | `TrainingPlan` + `PlannedWorkout` models |
| Athlete history | Longitudinal metrics across all activities | Activity table, stream analysis cache |

### Output: What the athlete sees

Every piece of athlete-facing text must pass through these gates:

1. **Novelty gate:** Is this something the athlete doesn't already know? If obvious, suppress.
2. **Relevance gate:** Is this relevant to what the athlete is looking at right now? If not, defer to the right surface.
3. **Confidence gate:** Is this supported by enough data to state with specificity? If not, suppress or qualify ("I'm watching this but need more data").
4. **Purpose gate:** Does this account for the run's purpose? If evaluating against wrong criteria, suppress.
5. **Voice gate:** Is this written like a coach who knows this athlete? If it reads like a template or a statistics report, rewrite.

### The efficiency metric problem

The current efficiency metric (`speed_mps / avg_hr`) is fundamentally unsuitable as a universal quality signal:
- It penalizes deliberately slow running (pacing, recovery)
- It rewards fast running at low HR (drafting, downhill) regardless of intent
- It compares runs of different purposes as if they're the same thing

**Replace with purpose-appropriate metrics:**
- Easy/recovery runs: cardiac decoupling (% HR drift across the run). Low drift = aerobically efficient regardless of pace.
- Workout/tempo runs: pace hold vs target (did they hit the prescribed intensity?)
- Races: split consistency, negative split analysis
- Long runs: cardiac decoupling + pace stability in final third

The EF metric (speed/HR) can remain as an internal diagnostic but should NOT be surfaced to the athlete as "efficiency" — it misleads when comparing across purposes.

### The comparison peer set problem

Current: Tier 1 matches by `workout_type` + distance ±30%. Falls back to Tier 2 (same type, any distance), then Tier 3 (any type, similar distance), then Tier 4 (everything in 28 days).

The fallback cascade means a 13-mile pacing run gets compared to 5-mile recovery jogs. The tiers should enforce minimum relevance — if there aren't enough similar runs to make a meaningful comparison, say nothing instead of falling back to meaningless peer sets.

### Activity-specific findings

Current: `GET /v1/activities/{id}/findings` returns global top-3 by `times_confirmed`. Same findings on every activity.

Required: Filter findings to those relevant to THIS activity. Show an efficiency finding when decoupling was notably high or low. Show a sleep finding when pre-run sleep was poor. Show a load finding after a volume spike week. Show nothing when nothing applies to this run.

---

## Surfaces and What Changes

### Activity page
- Replace generic WhyThisRun/RunContextAnalysis with per-chart intelligence cards
- Use purpose-appropriate metrics (cardiac decoupling for easy runs, not speed/HR)
- Show activity-relevant findings only (not global top-3)
- Suppress when there's nothing genuinely useful to say
- Read the title and stored workout_type for purpose framing

### Morning briefing (home)
- Already LLM-generated — needs better selection of WHAT findings to include
- Connect today's finding to today's planned workout
- Use specific numbers and thresholds, not generic patterns

### Manual page
- Rewrite finding display from template strings to coaching voice
- Add implications and action for each finding
- Suppress obvious findings (fresh legs → efficiency)
- Highlight surprising or athlete-specific findings with magnitude and thresholds
- Should read like a coach's notebook about this specific athlete

### Progress page
- Connect progress metrics to the athlete's stated goals
- Show trajectory, not snapshots
- Suppress generic encouragement

### Weekly digest
- Lead with the one most interesting finding from this week
- Connect to training plan progression
- Specific numbers, not generic summaries

---

## Relationship to Visual Layout

This spec defines WHAT to say. The tabbed layout spec (`BUILDER_INSTRUCTIONS_2026-04-12_ACTIVITY_PAGE_TABBED_LAYOUT.md`) defines WHERE to put it. Both are required. The visual layout is the delivery mechanism for intelligence that's actually worth delivering.

Building the layout without fixing the intelligence amplifies the presentation of bad content above the fold.

Building the intelligence without improving the layout buries good content below 4 viewports of scrolling.

**Build order:** Fix the intelligence quality first (this spec), then build the layout to present it. But spec both now so the layout design accounts for the intelligence architecture.

---

## What This Is Not

This is not a rewrite of the correlation engine. The engine finds real patterns. The engine is sound.

This is not an LLM wrapper on every surface. Some insights should be deterministic (drift comparison, zone breakdown). Some benefit from LLM voice (manual narratives, coach chat). The mechanism varies by surface.

This is not a Strava clone. Strava narrates what the chart already shows. StrideIQ tells you what the chart can't show — the longitudinal trend, the N=1 pattern, the plan context, the physiological implication. The floor is Strava's contextual correctness. The ceiling is genuine coaching intelligence.

---

*"The chart makes you open the app. The intelligence makes you trust it. The voice makes you need it." — Product Manifesto*

*This spec exists because the voice is currently absent or wrong. Every system below it works. This is the layer that makes them speak.*
