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

**Current state:** A vertical stack of six competing cards. Gradient
ribbon nobody understands. Coach Noticed and morning_voice as two
separate systems saying overlapping things. Workout wrapped in card
chrome. Nothing dominates. Nothing commands the page.

**Target state:**
- **Above the fold:** Gradient pace chart (full-bleed, the shape of
  your last run, effort-colored pace line). Below it, one paragraph —
  the morning voice, synthesizing ALL intelligence into the single thing
  that matters today. Below that, today's workout in plain text (title,
  why, paces, week context — no card chrome).
- **Below the fold:** Week strip. Check-in (if not done). Race countdown
  (if set). Recent Runs strip (3-5 compact cards, each with a mini
  gradient pace chart so you recognize runs by their shape).
- **Removed:** Separate Coach Noticed card (absorbed into morning voice).
  Gradient ribbon (replaced by pace chart). Workout card chrome.

**Home page state machine (future):**
- Post-run: Gradient pace chart hero (described above)
- Pre-workout: Today's planned workout in hero position with pace
  guidance and coach context
- Rest day: The system's single highest-priority intelligence signal
  (a correlation discovery, an efficiency trend, a race readiness update)

#### Activity Detail Page

**Current state:** Run Shape Canvas at top, then a disconnected scroll:
moments (metric labels), reflection, metrics, plan comparison, workout
type card, why this run, context analysis, compare button, old splits
chart AND splits table. Two charts on the same page. Moments are
unreadable. Ten sections competing for attention.

**Target state:**
- **Above the fold:** Run Shape Canvas with gradient pace line
  (effort-colored, the visual differentiator). Coachable moments
  below it as coaching sentences anchored to timestamps (LLM-generated,
  not metric labels). Reflection prompt (harder / as expected / easier).
  Metrics ribbon (compact horizontal strip).
- **Below the fold:** Expandable "Details" section containing plan
  comparison, why this run, context analysis, compare to similar, and
  splits table.
- **Removed:** Old Splits Chart (replaced by the canvas; table stays).
- **Fixed:** Gradient pace line (currently flat blue). Moment narratives
  (currently metric labels). Cadence in segment table (currently "--").
  HR sanity check (prevents wrong classifications from sensor glitches).

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

#### Insights Page

**Current state:** Top section (ranked insights) is decent. Bottom
section (active feed) is a repetitive log dump — five consecutive volume
alerts, four consecutive "you ran 6 times" achievements.

**Target state (principle, not spec):**
- Ranked insights stay as-is (they work)
- Active feed needs aggressive deduplication: if the same metric was
  flagged in the last N entries, suppress duplicates
- Quality floor: "you logged 6 runs this week" is not an achievement
  worth alerting. Set a minimum significance threshold.
- Consider a visual timeline (dots on a timeline, color-coded by type,
  expandable on tap) instead of a card list
- Narrative: the top insight should have a one-sentence "why this matters"
  interpretation

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

#### Discovery / Trends Pages

**Current state:** Overlapping with insights and analytics. The athlete
doesn't know where to look for correlations vs trends vs patterns.

**Target state:** Absorb into Analytics or Progress. These don't need to
be standalone pages if their content lives in a more natural home.

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
**Deferred.** The current tabs (Home | Calendar | Coach | Progress | More)
are fine. The verbs are right: See, Plan, Ask, Understand. The problem
isn't the tabs — it's what's inside them. Activities being buried behind
"More" is a friction problem solved by adding a Recent Runs strip on the
home page rather than changing the tab structure.

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

If a proposed change doesn't pass these five questions, it doesn't ship.

---

## Part 6: Read Order for New Agents

Any agent working on StrideIQ should read these documents in this order:

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how to work with this founder
2. `docs/PRODUCT_MANIFESTO.md` — the soul of the product
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — this document (how
   every screen should feel and what's been agreed)
4. `docs/RUN_SHAPE_VISION.md` — the visual vision for run data
5. `docs/SITE_AUDIT_2026-02-15.md` — honest assessment of current state
6. `docs/BUILD_SPEC_HOME_AND_ACTIVITY.md` — the active build spec
7. `docs/AGENT_WORKFLOW.md` — build loop mechanics

Do not start coding until you've read 1-6. Do not propose changes that
contradict decisions documented in Part 4 of this document without
discussing with the founder first.
