# Compare Tab Redesign — Discussion & Decisions

**Date:** April 18, 2026
**Status:** Discussion captured. Build sequenced behind Run Shape Canvas redesign.
**Author:** Founder + Opus 4.7 advisor
**Related code:**
- Frontend: `apps/web/components/activities/ComparablesPanel.tsx`
- Backend: `apps/api/services/comparison/comparable_runs.py`
- Endpoint: `GET /v1/activities/{id}/comparables`

---

## Why this document exists

The Compare tab on the activity page is the weakest tab in the product
by the founder's own assessment. Every major competitor (Strava, Garmin
Connect, Runalyze, Athletica, TrainingPeaks) has a stronger compare
experience. This document captures the full discussion, the four
directions evaluated, the founder's answers to scoping questions, and
the agreed direction — so the work can be picked up cleanly after the
Run Shape Canvas redesign lands.

This is **not** a build spec yet. It's the decision record. A build
spec follows once the canvas redesign is complete and the visual
vocabulary for the activity page is settled.

---

## Diagnosis — what's actually broken

Three failures, in order of severity:

1. **It's a navigation menu, not a comparison.** Every row in the
   current `ComparablesPanel` is a `<Link>` that routes away to another
   activity page. Clicking a comparable abandons the focus run AND every
   other comparable. There is no UI primitive for "stay here and look at
   two things side by side." This is the architectural sin. Polishing
   the rows doesn't fix it.
2. **No co-plotted data.** The 1.5-pixel pace bar per row is a
   sparkline pretending to be a chart. We never overlay HR streams,
   never co-plot pace, never show splits next to splits. Strava's free
   tier does pace/HR overlay; we don't.
3. **The bar is the wrong delta.** The pace bar shows raw pace. It
   doesn't show heat-adjusted pace, expected pace given conditions, or
   any of the contextual variables we already capture (dew, sleep
   going-in, HRV going-in, block position). All that data exists in our
   DB and we throw it away on this screen.

---

## The strategic question

What makes our Compare uncopyable — same way Run Shape is the
uncopyable Overview chart and Manual is the uncopyable retention loop?

Strava/Garmin compare is "two activities, here are the numbers, you
decide what they mean." Runalyze/Athletica is "two activities, here is
a physiological model interpretation."

We already have things they don't:
- Heat-adjusted pace (`heat_adjustment_pct` on every run)
- Going-in state on every run (Recovery HRV, sleep, RHR, Overnight HRV)
- Block context (5-week BUILD week 4 of 5)
- A causal attribution engine (`services/intelligence/attribution_engine.py`)
- Run shape detection with classification (intervals, fade, climbs)
- Per-rep interval analysis (recently hardened)

The question Compare must answer is whichever of these surfaces our
moat best.

---

## Four directions evaluated

### Direction 1 — "Side-by-side telemetry" (Strava, but actually good)

Two-stream overlay chart (pace + HR) of today vs a chosen comparable.
Picker on the right rail swaps the comparable in place. Metric chip
row below the chart with deltas. Heat-adjusted twin shown next to raw.

- **Cost:** Medium. Streams endpoint exists; new code is "fetch
  streams for comparable" + "swap in place" state model.
- **Why not enough alone:** Doesn't use any of our moat. Catches up to
  competitor baseline; doesn't surpass it. Two crisscrossing lines is
  the readability problem the founder already flagged on the existing
  Run Shape Canvas (two toggles can't be on at once).

### Direction 2 — "Gap decomposition" (Mockup B)

Pick one comparable. Lead with one sentence: "You ran 18 s/km slower
than your route best from Apr 5, 2025 — and 16 s/km of that gap is
explained by measurable conditions." Then a horizontal stacked bar:
`heat +12s` `block +4s` `sleep +2s` `residual 0s`. Below: comparables
list with same decomposition inline per row.

- **Cost:** High. `attribution_engine.py` does input → trend
  attribution today; pairwise attribution (run A → run B) is a
  different call signature that doesn't exist. Heat alone is
  straightforward (`heat_adjustment_pct` is a per-run number we can
  subtract). Block/sleep/HRV deltas are simple lookups. The hard part
  is the residual claim — that's the one that has to be honest, or
  the whole thing breaks trust.
- **Why powerful:** This is our voice. Nobody else can put a stacked
  attribution bar on a single pairwise comparison because nobody else
  has the attribution primitive.
- **Why risky:** If any of the four bars is wrong, athletes lose trust
  on the screen they came to learn from. Athlete Trust Safety
  Contract territory.

### Direction 3 — "Performance space" (Mockup A)

A 2D scatter of all this athlete's runs on this route. X-axis: heat
load composite. Y-axis: readiness composite. Today highlighted with a
ring. Color-coded by faster-than-expected / on-expectation /
slower-than-expected. Click any dot → side-panel comparison strip
slides in without leaving the scatter. Includes attribution flow row
(`RAW → HEAT → BLOCK → SLEEP → RES → ADJUSTED`) and three nearest
"physiological twins."

- **Cost:** Very high. Requires a per-athlete-per-route expected pace
  model (we don't have this; closest thing is the per-athlete
  fingerprint work in the correlation roadmap), a defined readiness
  composite (we have inputs, no canonical definition), a defined heat
  load composite, and enough runs on a given route to make a
  meaningful scatter.
- **Why seductive:** If data density is there, it's the most beautiful
  thing in the category.
- **Why deferred:** For ~80% of runs (route history thin, expected-pace
  model not yet built) it falls back to an almost-empty scatter — which
  makes the WORST first impression of the three. It's a "for routes
  with 8+ runs only" feature, with a different fallback for everything
  else. Cold-start dead.

### Direction 4 — "Shape-resolved comparison" (the founder's actual question)

**This is the agreed direction.**

Don't compare two runs as totals. Compare them as a sequence of
features: rep 1 vs rep 1, climb at km 7 vs climb at km 7, fade in the
back third vs fade in the back third.

Founder's exact words on the question Compare must answer:

> "have I improved generally on top end metrics, pace, hr, overall
> time, but then i typically dig into the shape....where was i
> challenged (hill, third rep, etc...)   did THAT improve?   what was
> my weakness then, now?"

Direction 4 names the weakness ("rep 4, your strongest last time, was
your slowest delta today") instead of forcing the athlete to find it
in overlapping HR lines. That's our voice; that's what the manifesto
promised.

---

## Founder answers to scoping questions

| Question | Answer |
|---|---|
| When you open Compare, what's the question in your head? | "Faster generally — pace, HR, overall time" first. Then dig into shape: where was I challenged, did THAT improve, what was my weakness then vs now. **Both top-line and shape-resolved.** |
| Same route only, or "closest physiological match across any route"? | Same-route is great when conditions match, but conditions vary so much (environment + going-in state) that condition-aware comparison is required even on same route. Don't assume same-route means comparable. |
| What if no comparable exists? | "Just say this run was unique — no other one on this or similar routing." Empty state with dignity. |
| How important is first-load freshness? | "What is important is that when it works, it works well." Quality bar over coverage. Don't ship a half-version. |

Founder also explicitly noted:
- **"Faster matters too."** Top-line metric deltas are first-class — not subordinate to shape diff. Header carries them.
- **The Run Shape Canvas itself is going to be redesigned.** Compare must NOT depend on the current canvas as its visual primitive. Independent.

---

## The decision

### Direction 4 is the centerpiece

Build shape-resolved comparison as the primary Compare experience.

- **Header strip** answers "have I improved generally": today vs
  comparable on pace, time, HR, decoupling — with deltas. Heat-adjusted
  twin shown next to raw. Going-in deltas (HRV, sleep, RHR) on display.
  Block context (week 4 of 5 BUILD).
- **Single delta strip** above the feature cards: one line representing
  today *minus* comparable along distance. Above zero = slower today,
  below = faster. Single signal, color-coded by feature underneath.
  This is the only "chart" on the page. No two-stream overlay.
- **Per-feature comparison cards** below: one card per identified
  segment (rep N, climb at km K, fade in segment S). Each card shows
  today's pace + HR, comparable's pace + HR, two delta numbers, and a
  one-line label naming the feature. Weakness call-outs ("rep 4 — your
  strongest last time") get visual emphasis. Reads like a stat sheet,
  not a chart.
- **Picker on the right rail**: tier list from current
  `ComparablesPanel` becomes a picker. Clicking a row **swaps** the
  comparable in place. Each row carries its conditions delta inline
  (`dew +9, sleep -0.5h, HRV -7`).

### Architectural rules (preserve no matter what)

1. **Picker swaps in place. Never navigate away.** Clicking a
   comparable updates the current view. Routing through to a
   different activity becomes an explicit secondary action.
2. **If no comparable exists in any tier, say so honestly.** Empty
   state names what we evaluated and rejected ("3 runs on same route
   but conditions too different — Apr 5 dew +18°F, …"). No invention.
3. **Tier system stays.** Same route year ago, same route recent,
   same workout this block, same workout similar conditions — those
   are the right buckets. They power a *picker*, not a list of links.
4. **Shape-compatibility gate on the picker.** Never offer a
   comparable whose shape can't be feature-aligned with today's. A
   long run vs interval workout has nothing to compare feature-by-
   feature; the picker excludes it.
5. **No dependency on the current Run Shape Canvas.** Compare is its
   own visual surface, built from primitives we already have (splits,
   intervals, climbs, fade detection).

### What's deferred

- **Direction 2 (gap decomposition / pairwise attribution)** is v2.
  When pairwise attribution is honest enough to ship, layer a "why"
  bar above the feature table — same screen, more depth. Not blocking
  v1. Gated on attribution engine extension.
- **Direction 3 (performance space scatter)** is deferred until we
  have a per-athlete-per-route expected pace model and clean readiness
  + heat load composites. Likely a future correlation engine layer.
- **Two-stream overlay chart (Direction 1's centerpiece)** is
  intentionally NOT built. The single delta strip replaces it. If
  athletes ask for raw stream overlay later, revisit; until then,
  one signal is the cleaner answer.

---

## Sequencing — why we wait

The Run Shape Canvas is being redesigned (founder will propose the
change). Compare's visual vocabulary inherits from the canvas. Three
reasons to sequence canvas-first, Compare-second:

1. The canvas redesign probably reshapes what Compare's "delta strip"
   should look like. Doing Compare first means re-doing it after.
2. The activity page reads as one piece (header → centerpiece visual →
   tabs). If the centerpiece changes and Compare doesn't, the page
   feels stitched together.
3. The current Compare panel isn't actively wrong, just weak. Nothing
   on it will be invalidated by canvas work. It can sit as-is without
   breaking trust the way the briefing miss did.

---

## Feature alignment — what works, what's hard

What we can align today (existing primitives):

- **Interval workouts:** Per-rep splits with HR, pace, distance.
  Alignment: rep N today vs rep N of comparable. Clean.
- **Same-route runs:** Per-km splits with elevation. Alignment by
  distance bucket. Climbs detected from elevation profile.
- **Long runs (any):** First third / middle third / back third bucket
  comparison. Always works as a fallback.

What's hard:

- **Different routes, different shapes:** No alignment possible. Shape
  diff doesn't apply. Falls back to overall metric deltas + same-
  distance HR/pace overlay. Or honest "no shape comparison available"
  message.
- **Misclassified features:** A misidentified climb, a ghost rep, a
  fade that wasn't really a fade — same risks we already have on the
  Athlete Intelligence panel. Same fix: suppress when not sure, never
  invent.

---

## When this gets picked up — checklist for the build agent

1. Confirm the canvas redesign has landed and the new visual
   vocabulary is documented.
2. Re-read this document. Re-read founder's answers. Don't drift.
3. Scope tier rules for shape compatibility (extend
   `comparable_runs.py` with a shape-compatibility filter).
4. Define the feature-alignment algorithm (intervals, routes, fallback
   for unstructured).
5. Write the empty-state copy ("this run was unique") — first-class
   screen, not afterthought.
6. Wireframe the header / delta strip / feature cards / picker layout
   against the new canvas vocabulary.
7. Test design before code, per founder operating contract:
   - Per-rep alignment with ghost-rep handling
   - Climb alignment on same-route comparables
   - Empty-state when no comparable passes shape-compatibility gate
   - Picker swap (in-place state update, no navigation)
   - Heat-adjusted twin rendering when both runs have weather data
   - Honest suppression when one run lacks comparable conditions data
8. Build, ship, watch CI, deploy, smoke-test on founder's account.

---

## References

- Founder Operating Contract: `docs/FOUNDER_OPERATING_CONTRACT.md`
- Product Manifesto: `docs/PRODUCT_MANIFESTO.md`
- Design Philosophy & Site Roadmap: `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`
- Athlete Trust Safety Contract: enforced via `n1_insight_generator.py`
- Attribution Engine: `apps/api/services/intelligence/attribution_engine.py`
- Comparable runs backend: `apps/api/services/comparison/comparable_runs.py`
- Current frontend: `apps/web/components/activities/ComparablesPanel.tsx`
