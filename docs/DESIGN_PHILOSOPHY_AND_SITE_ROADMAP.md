# StrideIQ — Design Philosophy & Site-Wide Roadmap
## February 15, 2026

**This is the companion document to the Product Manifesto.** The manifesto
says what StrideIQ is. This document says how every screen should feel, what
we've agreed to build, and in what order. Written by the founder's vision
advisor after hours of discussion distilling what works, what's broken, and
what comes next.

**Read this after:** `docs/PRODUCT_MANIFESTO.md`, `docs/RUN_SHAPE_VISION.md`

---

## Part 1: The Design Principle

### Visual First, Narrative Bridge, Earned Fluency

Every intelligence surface in StrideIQ follows the same pattern. There are
no exceptions.

**1. Visual catches the eye.**
A chart, a gradient, a shape. Not a card with text. Not a metric in a
rectangle. Something the eye is drawn to before the brain engages. The
runner's eye runs to the chart first — always. This is biology, not
preference.

**2. The athlete interacts.**
Hover, drag, tap, explore. The visual is tactile, not static. It responds
to curiosity. The athlete plays with it because it invites play. This is
where engagement happens — not in reading, in touching.

**3. Wonder forms.**
"What does this mean?" The visual creates the question. A pace dip at
minute 23 that the athlete doesn't remember. An HR climb across reps
that's steeper than expected. A cadence shift they didn't notice during
the run. The visual plants seeds that the narrative will answer.

**4. The narrative answers.**
Below the visual — not beside it, not instead of it, BELOW it — the
system speaks. One paragraph. A coached interpretation. Specific numbers.
"Your cadence shifted from 168 to 174 at 42 minutes — your body found a
more efficient gear as fatigue set in." The narrative answers the question
the visual just created. The athlete reads it, then goes BACK to the
visual to see what the narrative described. Now they see it differently.

**5. Understanding deepens.**
The athlete returns to the visual with new eyes. The narrative reframed
what they're looking at. The pace dip at minute 23 isn't random anymore
— it's the hill the narrative just explained. The HR climb across reps
isn't scary anymore — it's normal cardiac drift the narrative just
contextualized. The visual and narrative together create understanding
that neither could alone.

**6. Trust is judged.**
"Is this real? Does this match what I felt?" This is where the product
lives or dies. If the narrative says something that contradicts the
athlete's felt experience without explaining why, trust breaks. If the
narrative says something the athlete didn't know but can verify in the
visual, trust builds. Every output must pass this test.

**7. Fluency becomes habit.**
Over time, the visual alone is enough. The runner reads the shape of
their effort like reading a sentence. They see the sawtooth of intervals,
the descending staircase of a progressive long run, the flat line of an
easy day — and they know what it means without reading a word. But they
only got there because the narrative built the bridge from "what am I
looking at" to "I know what this means."

**The narrative is not decoration on top of the chart. The narrative is
what teaches the athlete to read the chart.** Without it, the visual is
pretty but opaque — the athlete admires it but doesn't learn from it.
Without the visual, the narrative is useful but forgettable — the athlete
reads it but doesn't internalize it. Together, they build fluency. That
fluency is the product's moat.

---

### What This Means Concretely

**Every page needs both a visual anchor AND a narrative interpretation.**

This is where the current site fails. Some pages have visual but no
narrative (Training Load — nice PMC chart, nobody explains what it means
for tomorrow). Some pages have narrative but no visual (Progress, Insights
— good intelligence buried in text card walls that cause reading fatigue).
The activity page has both but they're disconnected (canvas at the top,
metric labels below, no bridge between them).

**Visuals must be meaningful, not decorative.** A colored ribbon that
nobody understands is not a visual. A gradient that maps to unreliable HR
data is not trustworthy. A bar chart of HR zones that calls a 6:47/mi
pace "Recovery" because the wrist sensor glitched is worse than no chart
at all. Every visual must pass the test: does the athlete understand what
they're looking at within 3 seconds? If not, it fails.

**Narratives must be specific, not generic.** "Great job on your run!"
fails. "Your pace held at 7:10/mi while HR climbed from 148 to 156 — your
aerobic system is doing more work to maintain the same output, which is
expected at mile 8 of a long run" passes. The difference is: does the
narrative teach the athlete something about THIS run that they didn't
already know?

**Templates are trust-breaking.** The moment an athlete sees the same
sentence twice with different numbers plugged in, the magic dies. Every
narrative must feel written for them, because it was — by an LLM that
received their specific context. If the LLM can't say something specific
and true, it says nothing. Suppress over hallucinate.

---

## Part 2: The Product Habit Loop

The entire product exists to create this daily loop:

1. **Trigger:** You finish a run. Your watch syncs.
2. **Open the app:** The shape of your effort is immediately visible.
   Gradient pace line, effort-colored. You recognize the run by its
   shape before reading a single number.
3. **Immediate reward:** You see things you didn't notice during the run.
   A cadence shift in rep 5. A pace dip explained by the hill. A clean
   negative split you didn't realize you executed.
4. **Deeper reward (one tap):** Coachable moments explain what the data
   means. "Your body found a more efficient gear when fatigue set in."
   You learn something about yourself.
5. **Investment:** You reflect (harder / as expected / easier — three
   seconds). You ask the coach. You log perception. Each investment
   makes the next session's intelligence sharper.
6. **Next morning:** You open the app. The voice tells you the one thing
   that matters today — grounded in yesterday's run, last night's sleep,
   today's plan, your trajectory. Not a card stack. One paragraph.
7. **Repeat.** Each run, the system knows more. The insights are more
   specific. The correlations are stronger. The athlete trusts it more
   because it keeps showing them things that are TRUE about their own
   body that they couldn't have known without the data.

The chart makes you open the app. The intelligence makes you trust it.
The voice makes you need it.

---

## Part 3: Screen-by-Screen Roadmap

### Tier 1: Daily Screens (build now)

These are the screens the athlete sees every day. If these feel wrong, the
whole product feels wrong — even if everything else works.

**Detailed build spec:** `docs/BUILD_SPEC_HOME_AND_ACTIVITY.md`

#### Home Page

**Current state (Apr 4, 2026):** Gradient pace chart hero, morning voice
briefing, wellness row (Recovery HRV, Overnight Avg HRV, Resting HR,
Sleep — all with personal 30-day ranges), quick check-in with mindset
fields (enjoyment + confidence), today's workout, race countdown, week
strip. Coach Noticed and morning_voice merged into per-field lane
injection. `/checkin` consolidated here — standalone page redirects to
`/home`.

**Shipped:**
- **Wellness Row:** Recovery HRV and Overnight Avg HRV displayed
  together with a hover tooltip explaining the difference. Both raw
  numbers always shown. Personal 30-day range context. RHR with status.
  Sleep hours + Garmin sleep score.
- **Quick Check-in with Mindset:** `enjoyment_1_5` and `confidence_1_5`
  added as optional collapsible section. No standalone check-in page.

**Home page state machine (future):**
- Post-run: Gradient pace chart hero
- Pre-workout: Today's planned workout in hero position with pace
  guidance and coach context
- Rest day: The system's single highest-priority intelligence signal
  (a correlation discovery, an efficiency trend, a race readiness update)

#### Activity Detail Page

**Current state (Apr 4, 2026):** Run Shape Canvas with gradient pace
line (above the fold), Runtoon card, reflection prompt, metrics,
weather context, finding annotations, splits table. **"Going In"
wellness snapshot** shows pre-activity Recovery HRV, Overnight HRV,
Resting HR, Sleep hours, Sleep score — stamped on every activity at
ingestion time from the corresponding GarminDay data.

**Shipped:**
- Run Shape Canvas gradient pace line (effort-colored)
- Weather context with heat adjustment
- Finding annotations (top 3 correlation findings)
- **Pre-activity wellness stamps** (`pre_recovery_hrv`, `pre_overnight_hrv`,
  `pre_resting_hr`, `pre_sleep_h`, `pre_sleep_score`) — enables
  wellness-vs-performance research alongside HR, cadence, and pace
- Runtoon above the fold

**Remaining:**
- Coachable moments still show raw metric labels in some cases
- Cadence in segment table still "--" for some activities

**Queued — Run Shape Canvas redesign (Apr 18, 2026):** Founder flagged
the current canvas as not telling the story well visually, with the
two-toggle layout being unreadable. A redesign proposal is pending. The
canvas is the centerpiece visual of the activity page; the redesign
sets the visual vocabulary that every other tab (especially Compare)
inherits.

**Queued — Compare tab redesign (Apr 18, 2026):** The current Compare
panel is the weakest tab in the product per founder's own assessment.
Full discussion and decisions captured in
`docs/specs/COMPARE_REDESIGN.md`. Direction: shape-resolved feature
comparison (rep N vs rep N, climb vs climb, fade vs fade) with a
single delta strip — NOT a two-stream overlay chart. Top-line metric
deltas (pace, time, HR, heat-adjusted twin) carry the "have I improved
generally" question in the header. Picker on the right rail swaps the
comparable in place — never navigate away. Empty state with dignity
when no comparable exists. **Sequenced behind the Run Shape Canvas
redesign** because Compare's visual vocabulary inherits from the
canvas; building Compare first means redoing it after.

#### Personal Operating Manual (`/manual`) — PRIMARY NAV (Apr 4, 2026)

**Current state:** V2 shipped. Four sections: Race Character (pace-gap
analysis, PR detection, race-day counterevidence), Cascade Stories
(multi-step mechanism chains with confound suppression), Highlighted
Findings (interestingness-scored), Full Record (all findings). Human-
language headline rewriter. `localStorage` delta tracking for "What
Changed." Contextual coach links per finding.

**Design decisions:**
- **Race Character is the single most important insight.** "During
  training, sleep below 7h precedes lower efficiency. On race day, you
  override this" — that is character, not a correlation. This section
  gets the most care.
- **Interestingness over frequency.** Cascade chains first, race
  character second, threshold findings third. Simple high-frequency
  correlations belong in the Full Record, not the lead.
- **Honest scoping.** Training-day findings must show race-day
  counterevidence when it exists. The system compares explicitly, not
  just lists separately.
- **Never hide numbers.** Raw values are always shown alongside
  interpretation and personal context. Athletes track trends, research,
  and compare — the numbers are the foundation.

**Backend:** `services/operating_manual.py`.
**Frontend:** `app/manual/page.tsx`.

---

### Tier 2: Weekly Screens (build after Tier 1 is solid)

These are screens the athlete visits a few times a week. They have good
data but need the Visual → Narrative treatment.

#### Progress Page

**Current state:** Text card wall. Race predictions, fitness momentum,
recovery, volume trajectory, PBs, period comparison — all as text in
rectangles. Good intelligence, exhausting to read. No visual anchors.

**Target state (principle, not spec):**
- Fitness/form/volume told as a compact visual (like Training Load's PMC
  chart — a line chart that tells the story at a glance)
- Race readiness as a visual gauge, not a text block
- Period comparison as overlapping line chart (this 4 weeks vs last 4
  weeks), not a table
- PBs with sparklines showing the trajectory toward each one
- "What's working / what's not" with visual correlation indicators
- Narrative interpretation below each visual section: what does this
  chart mean for your training this week?

#### Insights Page — DEPRECATED (Apr 4, 2026)

Permanently redirects to `/manual`. The Manual V2 interestingness filter
replaced the insight feed: cascade chains first, race character second,
threshold findings third, simple correlations in the full record.

#### Calendar Page

**Current state:** Works. Functional training calendar with color coding,
plan overlay, weekly mileage. Right sidebar with day detail.

**Target state:** Keep as-is for now. Future enhancement: the voice
narrates the week ("This was a 43-mile build week. Your body absorbed
Tuesday's threshold well — HR recovery was faster by Thursday. The weekend
long run will test whether that adaptation holds at distance.")

---

### Tier 3: Deep Dive Screens (build after Tier 2)

These are screens the athlete visits occasionally for deep analysis.

#### Training Load Page

**Current state:** Works well. PMC chart is the best visual in the
product. N=1 personalized zones. Clean presentation.

**Target state:** Add narrative interpretation. "Your fitness (CTL) has
climbed from 38 to 52 over the last 6 weeks. Current fatigue is elevated
(ATL 61) — you're in the loading phase of your build. Form (TSB -11) is
in the normal training range. If you hold this load through next week,
you'll enter taper with a CTL of ~55, which projects well for your goal
race pace." One paragraph below the chart. The visual already works —
it just needs the narrative bridge.

#### Analytics Page

**Current state:** Has charts (efficiency trend, load-response, age-graded
trajectory). Closest to working of the intelligence pages. Stability
metrics and correlation findings are useful.

**Target state:** Could absorb some content from other pages (discovery
correlations, trend data) to become the single "deep analytics" surface.
Narrative interpretation per chart section.

#### Discovery / Trends Pages — DEPRECATED (Apr 4, 2026)

`/discovery` permanently redirects to `/manual`. The Manual's Race
Character and Cascade Stories sections replace the standalone discovery
surface. Correlation insights that were on Discovery now live in the
Manual's Full Record with interestingness scoring.

---

### Tier 4: Infrastructure Fixes (weave in alongside Tiers 1-3)

These aren't screens — they're problems that affect multiple screens.

#### Units Regression
The site shows km instead of miles despite user setting. Affects
`RunShapeCanvas` tooltips, segment table, plan comparison distances, drift
labels, and `LastRunHero`. Every component that displays distance or pace
must use the `useUnits()` hook. This is a regression that needs a
systematic sweep, not per-component fixes.

#### HR Sanity Check
When wrist-based HR glitches, it poisons effort coloring, segment
classification, and any HR-derived insight. The backend needs a sanity
check during stream analysis: detect inversions, drops to zero, values
above max HR, pace-HR decorrelation. When HR fails, fall back to
pace-based effort estimation (Tier 4 behavior) and flag the data as
unreliable. This protects every surface that uses HR-derived data.

#### Progress.py Prompt Sycophancy
The progress page card generation prompt still says "ALWAYS lead each card
with what is going well before concerns" (line 839 of
`apps/api/routers/progress.py`). This produces output that reads as
flattery, not intelligence. Change to: "Lead with the most notable
observation. Cite numbers. Be specific. If nothing notable, say nothing."
One-line fix but it changes the tone of the entire progress experience.

#### Coach Intelligence Merge
`compute_coach_noticed` (deterministic) and `coach_briefing` (LLM/Opus)
are two parallel systems with weak data sharing. The morning voice should
be the synthesis layer that channels ALL intelligence — correlations,
signals, insight feed, check-in context, workout plan — into one voice.
The fix: run `compute_coach_noticed` first, feed its output into the Opus
prompt. This is detailed in `docs/BUILD_SPEC_HOME_AND_ACTIVITY.md` (H2).

---

## Part 4: What We Decided NOT To Do

These were discussed and explicitly rejected or deferred. Future agents
should not re-propose them without understanding why.

### Intelligence Page Consolidation (7 → 2)
**Rejected.** The original proposal was to collapse Discovery, Trends,
Training Load, and Analytics into Progress, leaving only Progress +
Insights. The founder pushed back: Training Load looks better than
Progress and Insights. Consolidating a text wall into another text wall
makes a bigger text wall. The better approach is to make each page
visual-first (Tier 2/3 work) rather than collapsing them.

### Templates for Coachable Moments
**Rejected.** Templates are repetitive, trust-breaking, and feel like
1990s software. The moment an athlete sees the same sentence pattern
twice, the magic dies. Moments get LLM-generated narrative — one batch
call per activity, cached. If the LLM can't say something specific and
true, it says nothing.

### Tab Navigation Restructuring
**PARTIALLY SHIPPED (Apr 4, 2026).** Primary nav is now:
Home | Manual | Progress | Calendar | Coach. Manual was promoted to
primary because the Personal Operating Manual is a standalone product
differentiator — it teaches the athlete about themselves. Insights and
Discovery were deprecated (redirected to Manual). Check-in consolidated
onto the home page. The "More" dropdown contains: Analytics, Training
Load, Tools, Nutrition, Settings.

### Coachable Moments on the Home Page Hero
**Rejected.** "Data doesn't hallucinate" — the canvas is pure signal.
Adding AI text to the highest-stakes screen introduces exactly the risk
the Athlete Trust Safety Contract was designed to prevent. Moments live
on the activity detail page where there's depth and context.

---

## Part 5: The Principle Behind Every Decision

The product manifesto says: "The chart makes you open the app. The
intelligence makes you trust it. The voice makes you need it."

This document operationalizes that into a design rule: **every screen
needs a visual that catches the eye, a narrative that builds
understanding, and an interaction model that builds fluency over time.**

When evaluating any proposed change, ask:
1. Where is the visual anchor? (If there isn't one, add one before
   adding more text.)
2. Where is the narrative bridge? (If the visual is unexplained, the
   athlete will admire it but not learn from it.)
3. Does this teach the athlete to read their own data? (If not, it's
   a feature, not intelligence.)
4. Would the athlete trust this? (If it contradicts their felt
   experience without explanation, it breaks trust.)
5. Does this serve the daily habit loop? (If it doesn't connect to
   the trigger → reward → investment cycle, it's a nice-to-have.)
6. **Are the raw numbers visible?** Hiding numbers is NEVER the right
   answer. Athletes get accustomed to their trends, research on their
   own, and compare themselves to others. The magic is making numbers
   understandable to a 79-year-old father AND meaningful to an elite —
   by layering interpretation on top of the data, not replacing it.
   Every metric surface must show: the value, an interpretation (e.g.,
   "low / normal / high"), and personal context (e.g., "your 30-day
   range: 45-72").

If a proposed change doesn't pass these six questions, it doesn't ship.

### HRV Display Standard (Apr 4, 2026)

Two HRV values from Garmin require distinct labeling everywhere:

| Internal name | Display label | What it is |
|---------------|---------------|------------|
| `hrv_5min_high` | **Recovery HRV** | Peak 5-min window during sleep. More predictive of next-day performance. Used by the correlation engine. |
| `hrv_overnight_avg` | **Overnight Avg HRV** | Full-night average. Matches the value Garmin shows on the watch sleep screen. |

Both values are always shown together (never just one). An info tooltip
or hover explains the difference. This prevents silent trust erosion —
athletes who see their Garmin watch say "36ms Avg Overnight HRV" and
then see StrideIQ say "HRV below 78" will lose trust instantly unless
the distinction is clear.

---

## Part 6: Read Order for New Agents

Any agent working on StrideIQ should read these documents in this order:

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how to work with this founder
2. `docs/PRODUCT_MANIFESTO.md` — the soul of the product
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — this document (how
   every screen should feel and what's been agreed)
4. `docs/RUN_SHAPE_VISION.md` — the visual vision for run data
5. `docs/SITE_AUDIT_LIVING.md` — honest assessment of current state
6. `docs/BUILD_SPEC_HOME_AND_ACTIVITY.md` — the active build spec
7. `docs/AGENT_WORKFLOW.md` — build loop mechanics

Do not start coding until you've read 1-6. Do not propose changes that
contradict decisions documented in Part 4 of this document without
discussing with the founder first.
