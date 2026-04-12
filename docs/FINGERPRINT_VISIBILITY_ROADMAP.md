# Living Fingerprint — From Built to Visible

**Date:** March 8, 2026
**Author:** Top Advisor (Opus)
**Status:** Strategic vision + build architecture — the north star for fingerprint visibility
**Read after:** `PRODUCT_STRATEGY_2026-03-03.md`, `specs/CORRELATION_ENGINE_ROADMAP.md`, `PRODUCT_MANIFESTO.md`, `RUN_SHAPE_VISION.md`, `DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`

---

## The Gap

The backend intelligence is built. The product vision is documented. The gap is between them.

The founder's product strategy defines 16 priority-ranked concepts, all powered by the correlation engine. The correlation engine roadmap defines 12 capability layers. Layers 1-4 are shipped. The Living Fingerprint — weather normalization, shape extraction, 15 investigations, finding persistence — is shipped. The Training Story Engine is shipped.

None of it speaks to the athlete.

The founder invested more time and resources in the Living Fingerprint than in the rest of the site combined. It is the moat. And right now the athlete's experience of it is: activity titles and a morning briefing.

This document defines the vision for making the fingerprint visible, the architecture for getting there without losing athletes along the way, and the quality standard that every visual must meet.

---

## Part 1: The Dream

The Living Fingerprint is not a dashboard. It is not a chart page. It is a living visual organism generated from the athlete's own physiology.

### The Fingerprint Organism

A dark canvas. At the center, an organic form — not geometric, not a chart. A data portrait unique to this athlete.

**The outer silhouette** is shaped by the athlete's response curves. Heat sensitivity stretches it in one direction. Sleep impact pulls it in another. Volume tolerance, recovery speed, cardiac drift rate — each is a vector that shapes the boundary. Michael's form looks nothing like Belle's because their bodies respond differently. The silhouette IS the sensitivity profile, made visible.

**Internal structure** shows finding confidence. Bright, defined filaments for patterns confirmed dozens of times — "your sleep cliff at 6.2h, confirmed 47 times across 9 months." Dim, nebulous regions for patterns still emerging — "possible correlation between afternoon runs and better sleep, seen 3 times, too early to confirm." The athlete sees at a glance how well the system knows them. A new athlete's fingerprint is mostly dim. After 6 months, it's rich and defined. After 2 years, it's a dense, intricate structure representing the most complete physiological self-knowledge any amateur athlete has ever had.

**Color is semantic.** Warm hues where the athlete is in an adaptation window. Cool hues where recovery is dominant. Bright accents where something is happening NOW — a threshold being tested, a pattern breaking, a finding just strengthened. The athlete learns the color language through the narrative bridge, not a legend.

**The form breathes.** Subtle, not distracting. When new data arrives — a run syncs, a night of sleep — a ripple propagates from the relevant region. The athlete sees the system absorbing their data. Over weeks, the shape evolves. They can scroll back and compare their fingerprint from a month ago. The growth IS the product.

**Touch any region and it speaks.** Tap a bright filament: "Your easy pace at 140bpm has improved 18 sec/mi over 9 weeks. Confirmed 12 times. Evidence strength: strong." Tap a dim area: "Possible sleep-to-efficiency cascade. HRV drops after <6h sleep, efficiency drops 48 hours later. Seen 4 times. Watching." The visual IS the finding. The touch reveals the words. The words send the athlete back to the visual to see where the finding lives in the context of their whole physiology.

### The Training Landscape

The athlete's training history rendered as topography.

**Elevation is load.** Peak training weeks rise into mountains. Recovery weeks drop into valleys. A 6-month base campaign looks like a high plateau — sustained altitude, months of consistent elevation. The taper before a race is a controlled descent to the starting line.

**Width is volume.** A 70-mile week is a broad mesa. A 30-mile recovery week is a narrow ridge. Big training takes up big visual space.

**Color maps to adaptation.** Green where the body was absorbing. Amber where it was stressed but productive. Red where the load was too much. Gold at the peaks — race days, PRs, breakthrough sessions. The landscape tells what worked and what didn't without a single word.

**Texture is variety.** Smooth terrain means monotonous training. Rough, varied terrain means diverse stimulus. The athlete sees it.

The athlete flies over their own training history. They recognize campaigns by their shape. They see the valley where they were injured and the climb back. They see the plateau where they stagnated and the breakthrough that followed a change.

The Pre-Race Fingerprint becomes spatial: "Your current position in the landscape most closely matches THIS point." A glowing marker on a historical ridge. The terrain around both points looks alike. The athlete SEES the similarity.

### The Run Signature

Every run produces a data portrait — a composition generated from that run's data. Not a miniature line chart. A form.

Pace profile is the primary shape — smooth and flowing for easy, jagged for intervals, descending staircase for progression. HR response overlays as texture — climbing HR at constant pace shows as visual strain. Cadence patterns create rhythm.

The activities page becomes a gallery. Not a list of titles and numbers — a visual diary where each run is a unique portrait. The athlete recognizes their sessions at a glance. Screenshot-worthy. Shareable. "What app makes those?" is the acquisition moment.

### The Morning Pulse

Every morning, the home page shows the fingerprint — the athlete's own form — subtly different from yesterday. The sleep region dimmed. The efficiency filament brightened. The heat sensitivity area has a new accent because tomorrow's forecast is 88°F and the system knows what that means for this athlete.

The athlete opens the app and sees THEMSELVES. Below the form, the morning voice explains the shift. Over time, the athlete reads the form before the words. That is fluency — the seventh step in the Design Philosophy.

### The Race Canvas

Before a target race, a dedicated surface assembles the full Pre-Race Fingerprint. The current training block's form merges with historical race blocks. Overlap = confidence. Where forms match, it glows. Where they don't, it's transparent.

"Your current block is 87% similar to the 18 weeks before your half marathon PR. The match includes: CTL trajectory, long run consistency, workout variety, and sleep patterns. The gap: your taper hasn't started yet."

After the race: the result is absorbed into the landscape. A new gold peak. The fingerprint strengthens. The findings that predicted it get brighter. The system got smarter. The athlete's portrait grew.

---

## Part 2: The Dual Pathway Architecture

The dream cannot be the athlete's first experience. A new user with 3 runs and no confirmed findings would see a mostly dim, mostly empty form — and leave. The Claude advisor identified this as the "failure window": the first two weeks, when the fingerprint is thin and the athlete doesn't know how to read it, is where churn lives.

The solution is a dual pathway that respects both the athlete and the vision.

### Path A: The Literacy Program

Path A uses the screens the athlete already visits. It surfaces fingerprint intelligence through BETTER versions of familiar patterns. No new visual vocabulary required.

Path A is curriculum. Every contextual annotation on a pace chart is a lesson the athlete doesn't know they're taking. By the time the fingerprint unlocks, they've internalized the vocabulary. They just haven't seen it arranged spatially yet.

**Home page — enhanced existing surfaces:**

1. **Weather context on last run hero.** If `heat_adjustment_pct > 3%`, the pace chart itself encodes the adjustment — color-coded by adjusted effort, not just raw pace. A run that looked "slow" in 90°F glows with the same effort intensity as a cool-weather PR pace. The narrative line below explains what the color shows. If conditions were normal, nothing changes.

2. **One finding, contextually rendered.** The most relevant active finding, with a visual micro-element (a sparkline, a trend arrow, a confidence indicator) alongside the text. "Your easy pace at 140bpm has improved 18 sec/mi over 9 weeks." Tap to see evidence. The finding is not a card — it's a living data element with visual weight proportional to its confidence.

3. **Sharper morning voice.** The top 2-3 active findings, weather adjustment, and shape classification are fed into the prompt. The morning voice references specific intelligence. Not a new field — a smarter prompt for the existing field.

**Activity detail — enhanced existing surfaces:**

4. **Weather-adjusted pace on the chart.** The existing pace chart gains a second layer: adjusted-effort coloring. The athlete sees that their "slow" hot-weather run was actually a hard effort. The narrative line below explains the adjustment with specific numbers.

5. **Findings as chart annotations.** When a finding relates to this activity — "your HR recovery after intervals is slowing over the past 3 sessions" — it appears as a contextual annotation pinned to the relevant point on the chart. The athlete sees the finding IN the data, not beside it in a card.

6. **Shape as visual identity.** The activity's classification (progression, tempo, fartlek) is rendered as a miniaturized pace profile icon near the title — not a text badge, but the actual shape of the effort, simplified. Over weeks, the athlete starts recognizing their run types by icon shape. This plants the seed for run signatures in Path B.

**Path A requires no minimum data threshold.** Even on day one, weather adjustment and shape work. The intelligence is thin early but it's never empty. It never requires learning a new visual vocabulary.

**Path A's purpose:** Teach the athlete what findings are, what confidence means, what the system pays attention to. Every interaction builds the vocabulary they'll need when Path B unlocks.

### Path B: The Dream Surfaces

The fingerprint organism, training landscape, run signatures, morning pulse, and race canvas. New visual paradigms. New literacy required.

**Path B is gated on data sufficiency AND finding diversity.**

Path B unlocks when the athlete has enough confirmed findings, across enough physiological domains, to produce a form that is rich enough to explore. The gates:

| Surface | Data Gate | Diversity Gate |
|---|---|---|
| Fingerprint organism | ≥8 active `AthleteFinding` with `times_confirmed ≥ 3` | Findings span ≥3 distinct domains (e.g., sleep, cardiac, pace, recovery, environmental) |
| Training landscape | ≥6 months of consistent activity history | ≥2 distinct training phases visible (build + recovery, or base + peak) |
| Run signatures | Activity has full stream data (pace, HR, cadence) | — |
| Race canvas | ≥3 races with ≥12 weeks of training block data each | — |
| Morning pulse | Fingerprint organism is unlocked | ≥1 finding updated in last 7 days |

An athlete with 10 findings all in pace efficiency would NOT unlock the fingerprint — the form would have filaments clustered in one region with nothing elsewhere. The diversity gate ensures the form has spatial variety when it first appears, making it feel like a portrait rather than a single data point rendered fancy.

**The gates are product moments, not loading screens.**

"Your fingerprint has 3 confirmed findings. At 8, the sleep region will take shape. At 15, you'll start reading the form before the words."

The athlete isn't waiting for a feature. They're growing toward a threshold of self-knowledge. Each confirmed finding is a new filament. Each month adds topography. The GROWTH of the visual is the product, not just the visual itself. A progress bar toward a feature is annoying. A progress bar toward understanding your own body is compelling.

### The Reconnection Moment

The reconnection moment is the acceptance test for the dual pathway. It is the specific instant where the athlete taps a fingerprint filament and RECOGNIZES a finding they've been seeing on their activity pages for weeks.

**The scenario:**

The athlete has been using StrideIQ for 3 months. During that time, Path A has shown them, repeatedly, on their activity detail page: "Your easy pace at 140bpm has improved 18 sec/mi over 9 weeks. Confirmed 12 times." They've seen it as an annotation on their pace chart. They've seen the sparkline next to it trend downward (faster pace at same HR). They know this finding. They trust it. It matches what they feel.

Then Path B unlocks. The fingerprint appears. There's a bright filament in the cardiac region. They tap it. It says: "Your easy pace at 140bpm has improved 18 sec/mi over 9 weeks. Confirmed 12 times. Evidence strength: strong."

They recognize it. They don't need the words. They already knew. The form just showed them WHERE this finding lives relative to everything else the system knows about their body. They see, for the first time, the spatial relationship between their cardiac efficiency improvement and their sleep sensitivity and their heat response curve.

**That is the moment the product becomes irreplaceable.** Not because the fingerprint is beautiful (though it must be). Because the athlete experienced the transition from data consumer to data reader. The visual taught them to see their own physiology as a connected whole, not a collection of separate metrics.

**Every Path A decision should be evaluated against:** "Does this make the reconnection moment more likely to land?" If a Path A feature teaches the athlete what a finding is and how confidence grows, it passes. If it's data display that doesn't build vocabulary, it fails.

---

## Part 3: Visual Quality Standard

This standard applies to ALL visual work — Path A and Path B. It is non-negotiable.

### The Bar

StrideIQ's visual standard is not "better than Garmin." It is not "competitive with Runalyze." It is: **the kind of data visualization that wins Information is Beautiful awards, rendered in real time from personal physiological data.**

Reference points for the quality floor:
- **The Pudding** (data journalism): Novel visual metaphors for data. The "Happy Map" turns 100,000 data points into explorable terrain. Every project uses a unique visual language invented for that specific dataset.
- **Giorgia Lupi** (data humanism): Personal data rendered as art. "Every brush stroke is a datapoint dripping with feelings." Cooper-Hewitt award. MoMA permanent collection.
- **Oura's progressive disclosure**: Three levels — abstract glance → focused metrics → detailed exploration. Semantic color system that communicates instantly.
- **Apple's Activity Rings**: One visual metaphor that defined an entire product category. Not a chart — a symbol.
- **F1 telemetry**: Dark backgrounds, thin bright lines, synchronized multi-stream overlays, precision engineering aesthetic. This is the specific aesthetic called out in `RUN_SHAPE_VISION.md`.

### What Fails the Standard

- Default chart library output with default colors (Chart.js, Recharts defaults)
- Text in rectangles (cards with numbers, no visual anchor)
- Line charts with no semantic color (meaningless blue line)
- Gradients that are decorative rather than data-mapped
- Any visual that could have been built with a charting library's demo theme
- Any visual that looks like it could be on Garmin Connect or Strava

### What Passes the Standard

- Custom visual language invented for StrideIQ's specific data
- Color that communicates meaning before reading (semantic, not decorative)
- Interaction that rewards curiosity (hover, tap, explore — not just look)
- Visual-first, narrative-below (the Design Philosophy's 7-step sequence)
- Something the athlete screenshots and shares without being asked
- Something that makes another runner ask "what app is that?"

### Regression is termination. Equivalence is redo. The goal is excellence.

---

## Part 4: Technology Landscape

These are the tools available now that enable the vision. Research conducted March 2026.

### GPU-Accelerated Rendering

**ChartGPU** (released January 2026): WebGPU-based charting library. 50 million data points at 60fps. Smooth panning/zooming with 1 million points. Line, area, scatter, heatmap, candlestick. React bindings via `chartgpu-react`. MIT licensed.

This enables: full-resolution stream data rendering. Every second of every run, interactive, no downsampling. The F1 telemetry feel — every sensor reading visible at whatever zoom level the athlete wants.

Browser support: Chrome 113+, Edge 113+, Safari 18+. Falls back gracefully.

### 3D / Immersive Visualization

**React Three Fiber** (R3F): React renderer for Three.js. Production-proven for 3D data visualization — interactive globes, atmospheric environments, force-directed graphs. The bridge between React components and WebGL.

This enables: the Training Landscape (3D terrain from time-series data), the Fingerprint Organism (organic 3D form from response curves), immersive data environments.

### Animation / Motion

**Framer Motion**: Already in the React ecosystem. Data-driven animations, layout transitions, keyframe sequences. The pace line that draws itself. The fingerprint that breathes. Morphing between states.

**Rive**: Data-driven state machine animations. Designer and developer iterate independently. Animations respond to data inputs via state bindings. Perfect for the fingerprint's response to new data — the ripple effect, the filament brightening.

### Generative / Creative Coding

**Custom WebGL shaders**: For the fingerprint organism's generative form. WGSL compute shaders via ChartGPU's infrastructure. Fragment shaders for per-pixel organic effects.

**p5.js**: For prototyping generative run signatures. Perlin noise for organic shapes, polar coordinates for circular structures. Quick iteration before production implementation.

### What NOT to use

- Chart.js / Recharts for anything athlete-facing (fine for admin/internal)
- Default themes from any charting library
- Static SVG where interactive Canvas/WebGL is possible
- 3D for its own sake (3D must serve comprehension, not spectacle)

---

## Part 5: The N=1 Ecosystem Philosophy

This section captures a foundational product decision that shapes the data architecture.

### Population Approach (What Everyone Else Does)

Aggregate data across thousands of athletes. Compute averages. Tell an individual where they fall on a distribution. "Athletes like you tend to..." The individual is a point in a cloud. The insight comes from the cloud.

This is statistical soup. The individual is lost in the aggregate. The athlete correctly thinks "I'm not a statistic."

### N=1 Ecosystem Approach (What StrideIQ Does)

Build a complete, individually confirmed fingerprint for each athlete. Each finding is proven for THAT person — "your sleep cliff at 6.2h, confirmed 47 times." Then connect fingerprints at the structural level — and ALWAYS surface the differences alongside the similarities.

The similarity validates: "4 other athletes have individually confirmed the same sleep-response pattern you have." The difference informs: "But your version is more severe — your asymmetric response is 3x, theirs range from 1.5-2x. Yours is delayed — peaks at day 2, not day 1. And yours cascades through HRV before hitting efficiency, while theirs hit efficiency directly."

The similarity says "this is a real pattern — you're not an outlier." The difference says "here's exactly how YOUR body's version works compared to others who share the same structural pattern." Together, they produce intelligence that neither population statistics nor isolated N=1 can provide.

This is what makes a fingerprint a fingerprint. Every human has ridges, loops, whorls. The structural categories are shared. No two are alike. The uniqueness IS the identity. If the system only shows similarities, it's a classification system wearing a better suit. If it shows similarities AND differences, it's a portrait.

The difference is trust. The population approach says "statistically, people your age tend to..." The N=1 ecosystem approach says "this specific pattern is confirmed in YOUR body AND in these other bodies, independently — and here's what makes yours unique." That's not a statistic — that's replication with characterization. That's the scientific method.

### Architecture Implications

The correlation engine roadmap maps to this cleanly:

- **Layers 1-8**: Build and validate the individual fingerprint
- **Layer 11 (Cohort Intelligence)**: Connect confirmed individual fingerprints — structural matching between proven patterns, not demographic clustering
- **Layer 12 (Temporal Population)**: Track how confirmed patterns evolve across the ecosystem over time

Layer 11 built ground-up on Layers 1-8 is fundamentally different from Layer 11 built on raw population data. One is replication. The other is regression. Athletes trust replication.

The data model for `CorrelationFinding` is already N=1 native — per-athlete, with evidence counts and confirmation history. The cross-athlete matching layer doesn't exist yet, but the building blocks are ready. When Layer 11 arrives, it queries confirmed findings across fingerprints rather than running regressions across raw data.

### Visual Expression

Two fingerprints overlaid should make the differences MORE visible than the similarities. The shared filament glows where the structural pattern matches. Everything around it is different: different silhouette (different sensitivity profile), different brightness (different confirmation strength), different spatial relationships to other findings. The overlay doesn't say "you're the same." It says "look how different you are, even where you're alike."

The system never shows a match without showing the divergence. "Your fingerprint shares a confirmed sleep-response pattern with 4 others — but your asymmetry ratio is the most extreme, your decay is the most delayed, and yours is the only one that cascades through HRV first." The similarity is the doorway. The difference is the intelligence. The combination is the portrait.

This is years away from production. But the data architecture must protect it from day one. Every `CorrelationFinding` stores not just the pattern type but the specific parameters (threshold value, asymmetry ratio, decay half-life, mediation chain). These parameters are what distinguish your version of a pattern from anyone else's.

---

## Part 6: What's Built (Backend Capabilities Inventory)

| Capability | Service | Status | Data Produced |
|---|---|---|---|
| Weather normalization | `heat_adjustment.py` | Shipped | `heat_adjustment_pct`, `dew_point_f` on every Activity |
| Shape extraction | `shape_extractor.py` | Shipped | `run_shape` JSONB: phases, accelerations, classification |
| Shape sentences | `shape_sentence.py` | Shipped | `shape_sentence` on Activity — human-readable workout description |
| 15 investigations | `race_input_analysis.py` | Shipped | Investigation results with evidence, magnitudes, trends |
| Finding persistence | `finding_persistence.py` | Shipped | `AthleteFinding` rows — one active per investigation×type, supersession |
| Correlation engine | `correlation_engine.py` | Shipped | `CorrelationFinding` with r, p, lag, times_confirmed |
| Threshold detection (L1) | `correlation_layers.py` | Shipped | Personal thresholds per input (e.g., "sleep cliff at 6.2h") |
| Asymmetric response (L2) | `correlation_layers.py` | Shipped | Asymmetry ratios (e.g., "bad sleep hurts 3× more than good sleep helps") |
| Cascade detection (L3) | `correlation_layers.py` | Shipped | Mediation chains via `CorrelationMediator` |
| Decay curves (L4) | `correlation_layers.py` | Shipped | Half-life per finding, decay classification (exponential/sustained/complex) |
| N=1 effort classification | `effort_classification.py` | Shipped | Personal HR zones: percentile, HRR, workout-type tiers |
| Training Story Engine | `training_story_engine.py` | Shipped | Race stories, build sequences, training progressions |
| Readiness score | `readiness_score.py` | Shipped | Composite readiness from efficiency, recovery, completion |
| Daily intelligence | `daily_intelligence.py` | Shipped | 8 rules, InsightLog entries, narrated |
| Adaptation narrator | `adaptation_narrator.py` | Shipped | LLM-narrated insights with quality scoring |

This is the instrument. It runs daily. It produces real findings about real athletes. Path A makes these findings visible through existing screens. Path B renders them as the fingerprint form.

---

## Part 7: Connecting Built Capabilities to Strategy Priorities

### Priority #1: Pre-Race Fingerprint

**What it needs:** Mine every race. Extract the full training block signature (16-20 weeks). Match current block to historical blocks. Surface the closest match.

**What's built:** Shape extraction, weather normalization, correlation layers 1-4, finding persistence, Training Story Engine.

**What's missing:** Block-level analysis (investigations are activity-level, not arc-level). Race-to-block matching logic. Correlation layers 5-6 (confidence trajectory, momentum). Minimum 3-5 races per athlete.

**Readiness:** ~60%. Raw materials exist. Assembly logic doesn't.

**Visual expression:** The Race Canvas (Path B). Training Landscape with historical block matching. Glowing markers showing current position relative to historical analogs.

### Priority #2: Proactive Coach

**What it needs:** The system reaches out at the right moment with specific, grounded intelligence.

**What's built:** Daily intelligence engine (8 rules), investigation findings, correlation findings, decay curves, weather normalization.

**What's missing:** Delivery mechanism beyond home briefing and coach chat. Morning voice doesn't reference specific findings. No forward-looking intelligence. No trigger-based surfacing.

**Readiness:** ~70%. Intelligence exists. Delivery is passive.

**Visual expression:** Morning Pulse (Path B). Fingerprint accents for real-time pattern matches.

### Priority #3: Personal Injury Fingerprint

**What it needs:** Mine pre-failure signatures. Continuous background monitor.

**What's built:** Correlation layers, shape analysis, effort classification.

**What's missing:** Failure event model. Retrospective block mining. Layer 8 (Failure Mode Detection). Minimum 3-5 failure events per athlete.

**Readiness:** ~30%. Needs failure event model and Layer 8.

### Priority #4: Deep Backfill on Connect

**What it needs:** New athlete connects, years of data, correlation engine runs, "within minutes: something true about your body."

**What's built:** Garmin Historical Data Export approved, Strava backfill works, correlation engine runs on all data, shape extraction, investigation registry.

**What's missing:** Performance at backfill scale. First-session experience design. UX for the "aha moment."

**Readiness:** ~75%. Infrastructure ready. Experience not designed.

**Note:** Deep backfill accelerates the path to Path B gates. An athlete with 2 years of history could reach the fingerprint gate in days, not months.

### Priority #5: Personal Operating Manual

**What it needs:** Living document. Every confirmed pattern, threshold, fingerprint match.

**What's built:** `CorrelationFinding` with `times_confirmed`, `AthleteFinding` with supersession, correlation layers 1-4, Training Story Engine.

**What's missing:** No manual surface. No accumulation view. Layers 5-6 for confidence trajectory.

**Readiness:** ~65%. Data exists. Assembly and presentation don't.

**Visual expression:** The Fingerprint Organism IS the operating manual, rendered visually. Each filament is an entry. The form is the document. Touch to read, scroll to see history, watch it grow.

---

## Part 8: Relationship to Correlation Engine Roadmap

| Engine Layer | What It Enables | Path | Status |
|---|---|---|---|
| L1: Threshold Detection | Surface personal thresholds as findings | Path A (annotations) | ✅ Built |
| L2: Asymmetric Response | Show directional sensitivity | Path A (annotations), Path B (filaments) | ✅ Built |
| L3: Cascade Detection | Multi-step pattern chains | Path B (fingerprint connections) | ✅ Built |
| L4: Decay Curves | Timing predictions | Path A (proactive voice), Path B (morning pulse) | ✅ Built |
| L5: Confidence Trajectory | Finding strength over time | Path B (filament brightness changes) | Not built |
| L6: Momentum Effects | Block-level matching | Path B (race canvas, landscape) | Not built |
| L7: Interaction Effects | Multi-input patterns | Path B (fingerprint complexity) | Not built (needs 300+ activities) |
| L8: Failure Mode Detection | Injury fingerprint | Path B (risk region) | Not built (needs failure event model) |
| L9: Context Weighting | Situation-specific adjustments | Path B (conditional intelligence) | Not built |
| L10: Adaptive Thresholds | Self-updating parameters | Path B (evolving form) | Not built |
| L11: Cohort Intelligence | N=1 ecosystem matching | Path B (structural resonance) | Not built (needs N=1 ecosystem architecture) |
| L12: Temporal Population | Cross-ecosystem evolution | Future | Not built |

---

## Part 9: Weather Intelligence Surface (Confirmed Product Decision — March 9, 2026)

Weather gets its own **permanent home on the home page** — not a situational alert, not buried in narrative. Runners check weather before every run. The difference is personalization via the athlete's heat resilience score.

**Daily (all athletes):** Current conditions + what they mean for THIS athlete's pace. "88°F, 72° dew point — expect 12% pace suppression based on your history."

**Race countdown (2 weeks out):** System starts pulling forecast data for race location. Daily updates showing forecast through the athlete's personal heat lens with adjusted pace targets.

**Race week (hourly when available):** Gun time conditions, mid-race conditions (estimated by pace), and what each means for pace. "By mile 20 (est. 9:30 AM): 67°F, dew point 51°F. No adjustment needed."

**Danger zone alerts:** When forecast crosses the athlete's personal heat ceiling, explicit recommendation. "96°F — your last 3 runs above 94° averaged 18% suppression. Treadmill day."

**Predicted weather (future):** As the system learns the athlete's seasonal patterns (e.g., summer outdoor runner forced to treadmill by August heat), proactive seasonal planning. "Based on your history, outdoor running becomes compromised for you around June 15 in your location."

**What's built:** Heat resilience score (`investigate_heat_tax`), Magnus formula dew point model, `heat_adjustment_pct` on every activity, personal threshold detection (L1). **What's needed:** Forecast data integration (API), race location weather pull, home page surface.

**No running app does this personalized.** Generic heat calculators exist. None say "based on YOUR body's history at this dew point, here's what to expect."

---

## Part 10: Build Sequence

### Phase 0 — Fix What's Broken — ✅ COMPLETE

Infrastructure stabilized (Mar 8-9):
- Strava dedup fixed
- Worker/beat split done
- Reliable home briefing generation via Redis cache (Lane 2A)

### Path A — The Literacy Program — SUBSTANTIALLY SHIPPED

Shipped (Mar 9 – Apr 4):
- ✅ Weather-adjusted effort coloring on pace charts (heat_adjustment_pct)
- ✅ Finding annotations on activity detail (top 3 findings)
- ✅ Sharper morning voice (finding-aware prompt, per-field lane injection)
- ✅ One finding with micro-visual on home page (day-based rotation)
- ✅ **Personal Operating Manual V2** (Apr 4) — the full literacy program:
  Race Character, Cascade Stories, Highlighted Findings, Full Record,
  human-language headlines, interestingness filter, delta tracking
- ✅ **Home Wellness Row** (Apr 4) — Recovery HRV, Overnight Avg HRV,
  RHR, Sleep with personal 30-day ranges and explanation tooltip
- ✅ **Activity Wellness Stamps** (Apr 4) — pre-activity wellness snapshot
  on every activity, visible in "Going In" section on detail page
- ✅ **Manual in primary nav** (Apr 4) — promoted to top-level, left of Progress
- Remaining: miniaturized shape icons on activity cards (deferred)

### Then: Path B Design Exploration (Separate Track, Non-Code)

Before any production code:
1. **Emotional storyboard.** Not wireframes — moments. "The athlete opens the app for the first time after the fingerprint unlocks. They see ___. They feel ___. They tap ___. They recognize ___." Get the feeling right before the form.
2. **Creative coding prototypes.** p5.js sketches exploring the fingerprint form, the run signature compositions, the landscape terrain. What does the organism look like with 8 findings? With 25? With 50?
3. **Technology proof-of-concept.** ChartGPU rendering full stream data at resolution. R3F terrain from training history. Framer Motion breathing animation. Prove the tech works before designing around it.
4. **Reconnection moment test.** Prototype the specific moment where a Path A finding appears as a Path B filament. Does the athlete recognize it? Does the transition feel like recognition or education?

### Later: Path B Production Build

Sequenced by athlete engagement frequency:
1. Run Signatures on activity cards (highest touch frequency — every run viewed)
2. Morning Pulse on home page (daily — but only after fingerprint gate cleared)
3. Fingerprint Organism (dedicated surface — the "understand me" page)
4. Training Landscape on progress (weekly — replace current text walls)
5. Race Canvas (event-triggered — before target races)

Each surface gates independently. The athlete doesn't wait for all of Path B to see any of it.

---

## Part 10: What Was Decided and Why

### Confirmed Decisions

- **Dual pathway architecture.** Path A (literacy) and Path B (dream) run in parallel. Path A is the ramp. Path B is the destination. Neither works alone.
- **Gates include diversity criterion.** Not just finding count — findings must span ≥3 physiological domains. An athlete with 10 pace-efficiency findings doesn't unlock a fingerprint that's clustered in one region.
- **Gates are product moments.** "Your fingerprint has 3 confirmed findings. At 8, the sleep region takes shape." The learning curve itself is visible.
- **The reconnection moment is the acceptance test.** If Path A doesn't set it up and Path B doesn't pay it off, something is wrong.
- **N=1 ecosystem, not population statistics.** Cross-athlete intelligence comes from matching confirmed individual findings, not from demographic regression. Ground-up, not top-down.
- **Path A first in build sequence.** Path B design exploration runs in parallel but no Path B production code until Path A is shipping and the emotional storyboard is right.

### Rejected Decisions

- **"4-6 sessions" timeline for the dream.** The fingerprint organism requires custom shader programming, generative art design, and extensive UX iteration. The training landscape is a significant 3D rendering project. These are weeks of focused work, not sessions.
- **Collaborative fingerprint ecosystem (leaderboards, physiological twins).** Premature and potentially corrosive to N=1 philosophy. The N=1 ecosystem approach (structural matching of confirmed findings) preserves individuality while enabling cross-athlete intelligence. The collaborative version may come eventually but not as comparison, competition, or averaging.
- **Starting with the fingerprint organism.** Cold-start problem. New users would see a dim, empty form and leave. Path A builds the vocabulary first.
- **GPT/OpenAI models for advisory input.** Founder decision based on trust, not capability.

---

## The Honest Assessment (Updated Apr 4, 2026)

Path A is substantially shipped. The Personal Operating Manual V2, home wellness row, activity wellness stamps, and finding annotations are live. The Manual is the product's primary intelligence surface — it teaches athletes about themselves using their own data. It has earned primary navigation placement.

Path B design exploration can start in parallel — emotional storyboards, creative coding sketches, technology proofs-of-concept. No production code until the aesthetic is right.

The fingerprint organism remains the highest-risk, highest-reward surface. The Manual V2 is Path A's culmination — it's where findings become story, character, and self-knowledge. Path B should build from this foundation, not replace it.

A key design principle emerged from Path A work: **never hide numbers.** Athletes track trends, research, and compare. The magic is making data understandable to a 79-year-old AND meaningful to an elite — interpretation layered on raw data, not replacing it. This principle applies to every Path B surface.

Phase 3 (Pre-Race Fingerprint / Race Canvas) remains the highest-impact strategic priority.

The N=1 ecosystem is years away from production but the architecture must protect it now. Every `CorrelationFinding` stored today is a building block for Layer 11 tomorrow. The data model is already N=1 native. Don't corrupt it with population aggregation.

The competitor who appeared with something similar matches population patterns. They cannot match the N=1 confirmation cycle. The moat isn't the algorithm. The moat is the accumulated evidence, rendered as a visual identity unique to each athlete. Every day they stay, the fingerprint gets sharper and harder to replicate. Every day the portrait grows. That growth — visible, personal, irreplaceable — is the product.
