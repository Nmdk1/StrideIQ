# StrideIQ Site Audit — February 15, 2026

Full-site visual audit conducted by the founder with the vision advisor.
Screenshots captured from every page of the live production site (strideiq.run).

---

## What's Working

### Coach Page (/coach)
The strongest surface in the product. Conversations are specific, data-grounded,
cite real numbers, and give verdicts with reasoning. Example output: "Nailed it.
You went a bit longer but kept it genuinely easy — 9:26/mi at 125 bpm is
textbook recovery pace." The sidebar shows real-time athlete data (Fitness CTL,
Form TSB, Durability, Race countdown, This week mileage) and ranked insight
prompts. The coach already HAS the voice described in the manifesto — it just
lives only in the chat interface, not on other surfaces.

### Calendar (/calendar)
Solid functional training calendar. Real workouts with color coding, plan
overlay with actuals, weekly mileage totals. Right sidebar shows day detail
with planned workout, recent activity card, and coach prompt buttons. This
page works. It could be better (the voice should eventually narrate the week)
but it's not broken.

### Progress (/progress)
Real substance. Race Readiness with predicted splits across distances (18:54 5K,
39:12 10K, 1:26:44 half, 3:00:56 marathon). Fitness Momentum, Recovery
Readiness, Volume Pattern, Consistency Signal — all with "Ask Coach" links.
Recovery & Durability section. Runner Profile with all pace zones (Easy 8:05,
Marathon 6:57, Threshold 6:32, Interval 5:43, Rep 5:20). Volume Trajectory
chart showing the 20→24→36→43→50→60→48 ramp with +1097.5% label. Personal
Bests across 8 distances. Last 28 Days vs Prior 28 Days comparison table.

### Analytics (/analytics)
Efficiency Trend chart with 60-day average overlay. Stability Metrics
(Consistency Score 100/100, Easy/Moderate/Hard run counts). Age-Graded
Trajectory showing long-term performance arc. Load → Response chart showing
weekly efficiency deltas. Correlation findings ("What Correlates with Better/
Worse Efficiency"). Race plan banner with progress bar.

### Training Load (/training-load)
PMC chart (Fitness/Fatigue/Form/TSB). N=1 Personalized zones (not population
defaults). Current state: TSB -11, within typical training range. Daily
Training Stress chart. This is deep analytical content that serious runners
value.

### Coach Intelligence (backend)
The deterministic `compute_coach_noticed` pipeline synthesizes correlations,
home signals, insight feed cards, and hero narrative. The LLM `coach_briefing`
(Opus) generates morning_voice, coach_noticed, workout_why, week_assessment,
checkin_reaction, and race_assessment. These are powerful but currently operate
as two separate systems with weak data sharing between them.

### Tools (/tools)
Training Pace Calculator, Age-Grading Calculator, Heat-Adjusted Pace calculator.
Clean, functional, useful public-facing tools.

### Settings (/settings)
Strava integration (connected), Garmin file import (525 activities imported),
unit preferences (Miles selected), PRO Plan active, data export/delete.
Functional.

### Check-in (/checkin)
Clean slider-based input for Sleep, Stress, Soreness with optional HRV,
Resting HR, and Mindset check. Works.

---

## What's Not Working

### Home Page (/home)
The gradient ribbon at the top is a colored strip that nobody understands.
Even the founder — the most data-literate user the product will ever have —
found it useless and confusing. It's based on heart rate which is unreliable
from wrist sensors (yesterday's data was inverted due to HR glitch).

Coach Noticed and morning_voice are two separate systems producing overlapping
content on the same page. The Coach Noticed card has sycophantic tone baked
into its prompt ("ALWAYS lead with what went well, celebrate effort first").

The workout card has unnecessary chrome (Card wrapper, icon box, badge,
Sparkles icon, "Ask Coach" link).

The page is a vertical stack of cards — gradient, Coach Noticed, workout,
check-in, This Week, Race Countdown. Six things competing for attention.
Nothing dominates. Nothing commands the page.

The voice described in the manifesto — "your body's analyst tells you the one
thing that matters today" — does not exist on this page. What exists is two
separate text blocks (morning_voice + Coach Noticed) saying overlapping things
from different data sources.

### Activity Detail Page (/activities/[id])
TWO CHARTS on the same page. The Run Shape Canvas (stream-based, top of page)
and the old Splits/Laps chart (split-based, bottom of page). One should have
replaced the other.

Key Moments are labels with numbers ("Grade Adjusted Anomaly: 4.7", "Pace
Surge: 15.3"), not coached interpretations. The athlete doesn't know what
these mean. There's no narrative explaining what happened or why it matters.

"Your reflection" (harder/as expected/easier) exists and works but is buried
below moments nobody reads.

The page is long and disconnected: Canvas → Moments → Reflection → Metrics →
Workout Type → Why This Run → Run Analysis → Compare → Splits Chart → Split
Table. No cohesive flow. The canvas sits at the top but nothing below it
feels like it belongs to the same experience.

The Run Shape Canvas itself — while technically functional — doesn't live up
to the vision. The pace line is flat-colored (not effort-gradient-colored).
The elevation fill, cadence toggle, and grade toggle exist but the overall
visual is not the "F1 telemetry" quality described. Strava's basic two-color
chart with map tracing is arguably more useful in its current state.

### Activities List (/activities)
Plain metric cards (name, date, distance, pace, duration, HR). No visual
identity per run. No mini charts, no effort indicators. Just numbers in boxes.
This is where the "recognize your run by its shape" concept would eventually
apply — but currently every run looks the same.

### Insights Feed (/insights — Active Insights section)
Repetitive and noisy. Five consecutive "30-day volume: XXX miles" TREND ALERT
cards followed by four consecutive "This week: 6 runs, XX.X mi" ACHIEVEMENT
cards. This is not curated intelligence — it's a log dump. The ranked "Top
Insights" section above it is much better (Load Response, Efficiency Trend,
Plan status, Readiness, Personal Bests with confidence badges). The Active
Insights feed below it undermines the quality above.

### Nutrition (/nutrition)
Minimal. Quick add with preset buttons and custom entry. No logged data shown.
No connection to training intelligence visible. Low priority but currently
feels like a placeholder.

---

## The Core Problem

The intelligence is built. It's real, it's tested, it's statistically rigorous.
150+ tools, 111 services, 1878 tests. The coach can already speak with the
voice described in the manifesto — it does so in the chat interface.

But the daily experience — the home page, the activity page, the surfaces the
athlete sees every day — doesn't channel that intelligence. It displays cards.
It stacks components. It shows data without giving it a voice.

The gap is not in the backend. The gap is in the last mile: translating the
intelligence into an experience that makes the athlete feel known.

---

## Priority Fixes (discussed, not yet specified)

1. **Home page: merge the two intelligence systems into one voice.** Feed
   `compute_coach_noticed` output into the Opus `coach_briefing` call so
   `morning_voice` becomes the true synthesis layer. One paragraph. All the
   intelligence. No separate Coach Noticed card.

2. **Home page: replace the gradient ribbon.** Either with a compact version
   of the real pace chart (mini pace curve with effort-colored line) or with
   a clean last-run summary while the chart is improved. TBD — needs design
   decision.

3. **Home page: strip the workout to plain text.** No Card wrapper, no icon
   box, no badge. Title, why, paces, week/phase. Already partially implemented
   in advisor's edit to page.tsx.

4. **Activity detail: remove the old Splits/Laps chart.** One canvas. The
   Run Shape Canvas replaces it, not supplements it.

5. **Activity detail: moments need narrative.** "Grade Adjusted Anomaly 4.7"
   must become "Your pace dropped here but the 4.7% grade explains it — your
   effort was steady through this climb." Backend translation service needed.

6. **Insights feed: deduplicate and curate.** The Active Insights section
   needs deduplication (not 5 consecutive volume alerts) and a quality filter
   (don't show achievements that are just "you logged runs this week").

7. **Coach Noticed prompt: data-first, no sycophancy.** Remove "ALWAYS lead
   with what went well" and "celebrate effort." Replace with "lead with the
   most notable observation, cite numbers, be specific."

---

## What The Founder Needs To Hear

You have more product than you think. The coach works. The progress page has
genuine predictive value. The calendar is functional. The analytics are deep.
The training load page would make any serious runner happy. The intelligence
bank is real.

What's broken is the two screens the athlete sees MOST — the home page and the
activity detail page. Those are the daily touchpoints. When they feel wrong,
the whole product feels wrong, even though 80% of it works.

Fix those two screens. Give the intelligence a voice on the home page. Give the
activity page one cohesive canvas. That's the gap between "a product that works"
and "a product that makes you feel known."
