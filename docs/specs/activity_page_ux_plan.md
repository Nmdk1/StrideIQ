# Activity page UX plan (read-only audit)

**Date:** 2026-04-16
**Scope:** `apps/web` — activity detail route and its components.
**Prompt:** The founder flagged the page as "redundant, clunky and embarrassing compared to Strava." This document is evidence-first, surgical cleanup discipline (same as Pass A). No new features; no rewrites; consolidations / deletions / rearrangements only.

---

## 1. Current page anatomy (source order)

**Entry:** `apps/web/app/activities/[id]/page.tsx`

**Bootstrap and data (lines 128–184):** Client component. Loads activity (`GET /v1/activities/:id`), splits (`/v1/activities/:id/splits`), findings (`/v1/activities/:id/findings`), and stream analysis via `useStreamAnalysis` (`page.tsx:181–184`, import at `19`). Auth-loading and activity-loading each show a skeleton (`page.tsx:258–269`, `272–287`). Error/missing renders a red card with "Back to Home" (`290–306`).

**Header (`page.tsx:345–417`):** Back control, editable title (`resolved_title ?? name`, line `231`), inline date/time (`formatDate` + `formatTime` on `start_time`, `406–408` desktop, `415–416` mobile). Garmin badge when `provider === 'garmin'` (`411–413`). Data shown: title, start datetime, provider hint. Hidden: `shape_sentence` is not rendered as visible copy — it only appears in the reset-title affordance condition (`384–391`).

**Sport branching (`page.tsx:420–453` vs `454–662`):** If `sport_type` is set and not `'run'`, the page renders **no** `StreamHoverProvider`, **no** stats banner, **no** `ActivityTabs`, **no** run-specific intelligence stack. Shows `RouteContext` for GPS (`424–447`), then one of `CyclingDetail`, `StrengthDetail`, `HikingDetail`, `FlexibilityDetail` (`449–452`). For runs, execution continues into the main layout below.

**Stats banner (`page.tsx:456–488`):** Six-metric grid (`MetricPill`): Distance, Moving Time, Pace (from `moving_time_s` and `distance_m`, `320–323`, `461–463`), Avg HR, Elevation (`formatElevation` on `total_elevation_gain_m`), Cadence (normalized to spm, `121–126`, `474–481`). Optional heat line if `heat_adjustment_pct > 3` (`484–487`). Not shown here though present on the `Activity` type: `max_hr` (`46–47`), `elapsed_time_s`. No empty state beyond `--`.

**`GoingInStrip` (`page.tsx:491–495`, `GoingInStrip.tsx`):** Renders only if at least one of recovery HRV, RHR, or sleep hours exists (`GoingInStrip.tsx:16–17`). Horizontal strip with large numerals (`20–44`). Hidden entirely if all three null.

**`ActivityTabs` (`page.tsx:497–660`, `ActivityTabs.tsx`):** Five primary tabs — Overview, Splits, Analysis, Context, Feedback (`ActivityTabs.tsx:5–15`). Inactive panels stay **mounted** and are only hidden with `hidden`/`display` toggling (`20–21`, `52–63`), so all five panel trees exist in the DOM simultaneously.

**Run layout — Overview panel (`page.tsx:501–580`):**
1. **`RunShapeCanvas`** (`503–514`, `RunShapeCanvas.tsx`): stream-based RSI chart, fixed heights 200px/280px (`107–109`). Own loading / error+retry / empty / full chart (`1038–1073`), Tier 4 caveat (`1088–1096`), trace toggles HR/Cadence/Grade (`1098–1129`), terrain + pace + optional traces (`1151–1287`), interaction overlay (`1357–1365`), heat-adjusted pace note (`1368–1372`), HR reliability note (`1375–1385`), **duplicate drift metrics** (`1387–1390` via `DriftMetrics`), conditional **Plan comparison** (`1395–1398`). `TierBadge` and `LabModePanel` are **defined** in the same file (`512–534`, `644–741`) but **never rendered** in the JSX — dead UI paths.
2. **`RunIntelligence`** (`517–519`, `RunIntelligence.tsx`): fetches `/v1/activities/:id/intelligence`. Centered spinner while loading (`43–47`); on success, "Athlete Intelligence" card with headline, body, optional highlight chips (`53–86`); returns `null` on empty/error (`41`, `51`).
3. **Splits + map row (`522–575`):** If splits exist, left column (~55% on md) hosts `ActivitySplitsTabPanel` with `showMap={false}` (`525–546`) — splits/intervals only, no map. Right column: `RouteContext` with `streamPoints={analysisData?.stream}`, `mapAspectRatio="4 / 3"`, only after `clientReady` (`550–572`, SSR guard `186–190`). If no splits, map column still renders when GPS exists (`551–552`). **No `ElevationProfile` here** — that component is only used inside `ActivitySplitsTabPanel` when `showMap` is true (`ActivitySplitsTabPanel.tsx:139–163`).
4. **`RuntoonCard`** (`577–579`): photo/generation UX with loading/ready/timeout states; tall when image present.

**Splits tab panel (`page.tsx:582–616`):** A **second** full-width `RunShapeCanvas` instance (`584–594`), then `ActivitySplitsTabPanel` with `gpsTrack`, `showMap={clientReady}` (`596–615`). That panel shows map + `ElevationProfile` beside splits (`ActivitySplitsTabPanel.tsx:138–164, 174–179`). For structured workouts, nested Intervals vs Mile-splits toggle drives `IntervalsView` vs `SplitsTable` (`80–106`).

**Analysis tab (`page.tsx:618–625`, `AnalysisTabPanel.tsx`):** Passes drift, plan comparison, stream, effort intensity, moving time. Renders drift cards **again** if present (`46–69`), `PaceDistribution` effort-zone histogram (`72–77`, `PaceDistribution.tsx`), and plan vs actual **again** (`80–114`). Empty state: single line "No analysis data…" (`36–41`).

**Context tab (`page.tsx:627–646`):** `RunIntelligence` **again** (duplicate instance, `628–629`), `GoingInCard` (expanded wellness vs strip — `24–56`), `WhyThisRun` (attribution — `163–245`, collapsible, `defaultExpanded = true`), `FindingsCards` from findings query (`637–638`, `FindingsCards.tsx:16–35`), optional quoted `activity.narrative` (`639–644`).

**Feedback tab (`page.tsx:648–657`):** `ReflectionPrompt`, `PerceptionPrompt`, `WorkoutTypeSelector` compact.

**`MetricPill` helper (`page.tsx:681–698`):** ~56–72px per block vertically; two rows on narrow viewports due to `grid-cols-3` / `md:grid-cols-6`.

**Rough vertical budget (run, Overview, desktop):** header ~70–90px; stats banner ~110–140px + optional heat line; Going In ~45px; tab strip ~40px; RunShape stack ~320–520px; RunIntelligence ~120–220px; splits + 4:3 map pair often 400–600px+; Runtoon variable. Mobile stacks map under splits full-width; total scroll depth is large before any secondary tab.

---

## 2. Redundancy map

**Aggregate stats vs splits vs chart:** Distance, moving/elapsed time, pace, HR, cadence, elevation appear as **summary** in the stats banner (`page.tsx:458–482`) and again **per split** in `SplitsTable` / `IntervalsView` (`SplitsTable.tsx:83–116`, `IntervalsView.tsx:59–65` totals + rows). Pace/HR also appear in `RunShapeCanvas` tooltips and traces (`RunShapeCanvas.tsx:356–397`, `1228–1238`). Pace uses `moving_time_s / distance` in the banner (`page.tsx:461–463`) vs smoothed per-second pace on the chart (`RunShapeCanvas.tsx:820–844`, `1240–1247`) vs split-interval pace in tables (`SplitsTable.tsx:28–30`, `105–109`) — same concept, **different calculations and rounding**, reads as slightly different numbers without explanation.

**Drift metrics and plan comparison:** Rendered under `RunShapeCanvas` (`RunShapeCanvas.tsx:1387–1398`) **and again** in `AnalysisTabPanel` (`46–114`). Same underlying props on the page (`page.tsx:619–624`).

**`RunIntelligence`:** Mounted in **Overview** (`517–519`) **and** Context (`628–629`). Data is React-Query cached, but UI is duplicated.

**Going In:** `GoingInStrip` (HRV, RHR, sleep hours) above tabs (`491–495`). `GoingInCard` with overlapping fields + overnight HRV / sleep score in Context (`630–636`).

**`RunShapeCanvas`:** Two instances — Overview (`503–514`) and Splits (`584–594`). With all panels mounted (`ActivityTabs.tsx:52–63`), both canvases exist at once.

**Garmin attribution:** Header badge (`page.tsx:411–413`) and split footer (`SplitsTable.tsx:122–127`).

**Intervals summary vs banner:** `IntervalsView` prints total distance/time and derived total pace when structured (`IntervalsView.tsx:59–75`) — overlaps the global stats banner for the same activity.

---

## 3. Clunkiness and density

**Many primary surfaces:** Five top-level tabs (`ActivityTabs.tsx:5–15`) plus a secondary Intervals/Mile toggle **inside** the Splits panel with **orange** active styling (`ActivitySplitsTabPanel.tsx:80–105`) while tabs use **emerald** (`ActivityTabs.tsx:26–28`). Navigation within navigation for structured runs.

**All tab panels mounted:** `ActivityTabs.tsx:20–21` explicitly keeps inactive panels in the DOM → two `RunShapeCanvas` trees, duplicate `RunIntelligence`, etc.

**Competing accent colors:** Emerald tabs, orange secondary toggle, red/amber/purple chart toggles (`RunShapeCanvas.tsx:1100–1128`), amber heat callouts (`page.tsx:484–487`), multiple card borders — many simultaneous visual priorities without a single focal hierarchy.

**Dense intelligence stack:** Overview chains canvas → intelligence → splits → map → runtoon. Context adds long-form `WhyThisRun` cards (`WhyThisRun.tsx:199–244`) that **default to expanded** (`166–167`), so Context opens "everything" on first paint.

**Text that belongs adjacent to a chart:** Drift lines and plan blocks appear below the chart in `RunShapeCanvas` **and** as larger cards in Analysis — same information class repeated as prose-like rows (`RunShapeCanvas.tsx:1387–1398` / `AnalysisTabPanel.tsx:46–114`).

---

## 4. What Strava's activity detail has structurally that we do not (code-based)

**Synchronized hover across map + time-series chart + elevation strip:** **Implemented.** `StreamHoverProvider` wraps the run section (`page.tsx:455, 662`). `RunShapeCanvas` reads/writes `hoveredIndex` (`RunShapeCanvas.tsx:769–770`, `989–1017`). `ActivityMapInner` places a marker from `streamPoints[hoveredIndex]` (`301–306, 452–458`). `ElevationProfile` updates hover from mouse and shows cursor from shared index (`28, 54–72, 104–109`). **Gap:** Overview's map column does **not** include `ElevationProfile` (`page.tsx:522–575` vs `ActivitySplitsTabPanel.tsx:139–163`), so the classic map+elevation stack is **split across tabs**.

**Competitive segments / leaderboards:** No activity-detail UI references them; internal **workout segments** from stream analysis only appear as colored bands (`RunShapeCanvas.tsx:1147–1149`). No Strava-segment table surfaced. **Defer product decision.**

**Grade-adjusted pace in splits:** **Present** as a column when `gap_seconds_per_mile` exists (`SplitsTable.tsx:33–35, 88–111`). Not in the top stats banner.

**Elevation-over-distance profile:** **Present** as `ElevationProfile` beside the map on the **Splits** tab only (`ActivitySplitsTabPanel.tsx:160–162`). Terrain also in main chart as filled altitude (`RunShapeCanvas.tsx:1217–1226`) — two elevation visualizations, different tabs.

**Best-effort auto-detection:** Model has `best_efforts_extracted_at` (`apps/api/models/activity.py:57–59`). Web detail does not render best-effort rows; personal-bests page exists elsewhere. No activity-detail component to repoint without new wiring.

**HR distribution / histogram:** Not on this page. `PaceDistribution` buckets **effort intensity** into zones (`PaceDistribution.tsx:12–18, 26–77`) — effort distribution, not HR bins. Schema supports it; product decision.

**Social / kudos / feed:** Out of scope (section 7).

**Max HR, elapsed time, power, running dynamics:** Model includes `max_hr`, `moving_time_s`, Garmin power and dynamics columns (`activity.py:21–22, 88–98, 100–102`). Client type includes `max_hr` and `elapsed_time_s` (`page.tsx:43–45`) but the stats banner does not surface them; power/dynamics not in page-level interface — data likely available server-side, not wired.

---

## 5. What we do uniquely well (moat) — visibility risk

**Stream-native Run Shape canvas:** effort gradient, terrain, pace smoothing, heat-adjusted overlay, segment bands, drift, optional plan comparison — `RunShapeCanvas.tsx` (entire file; key UX `1086–1398`). Not a generic consumer lap table.

**Athlete Intelligence narrative:** `RunIntelligence.tsx:53–86`.

**Attribution ("Why This Run?"):** multi-card correlational explanations with confidence — `WhyThisRun.tsx:199–244` (Context tab only).

**Correlation findings:** `FindingsCards` — `page.tsx:637–638`, `FindingsCards.tsx:16–35` (Context only).

**Pre-run "Going In" context:** strip + richer card — `GoingInStrip.tsx`, `GoingInCard.tsx`.

**Reflection / perception / workout type:** Feedback tab (`page.tsx:648–657`).

**Route history vs past efforts on same route:** `RouteHistory` under `RouteContext` when siblings exist (`RouteContext.tsx:92–101`).

**Quoted narrative:** `activity.narrative` (`page.tsx:639–644`).

**Runtoon:** `RuntoonCard.tsx`.

**Moat visibility risks:** `shape_sentence` exists on the activity model (`activity.py:52–54`) and in the client type (`page.tsx:75–76`) but is **not shown as readable copy** on the detail page (only used for the reset-title affordance, `384–391`). `RunIntelligence` is above the fold on Overview (`517–519`) but duplicated in Context. `WhyThisRun` and `FindingsCards` sit **only** on Context (`637–638`) — below several tab switches for users who never leave Overview. `CoachableMoments` is defined as a component but not imported on this page — coach moments not surfaced.

---

## 6. Five-to-seven most important fixes — prioritized

**1. Remove duplicate `RunIntelligence` (keep one placement).** Show Athlete Intelligence once so Overview and Context do not repeat the same card. **Files:** `apps/web/app/activities/[id]/page.tsx` (`517–519` and/or `628–629`). **Effort:** S. **Why first:** duplicate blocks train users to ignore both; cheap, immediate hierarchy win. **Observable:** only one `RunIntelligence` region in the DOM per activity load.

**2. Stop rendering the same drift + plan comparison twice.** Keep drift/plan either under the chart **or** in Analysis, not both. **Files:** `apps/web/app/activities/[id]/page.tsx`, `AnalysisTabPanel.tsx:46–114`, optionally `RunShapeCanvas.tsx:1387–1398, 1395–1398`. **Effort:** M. **Why:** pure duplication of the same numbers with different padding. **Observable:** `AnalysisTabPanel` only adds unique content (`PaceDistribution` today); vertical height drops on tab switch.

**3. Collapse "Going In" to one surface.** Either the strip **or** the Context card owns HRV/RHR/sleep, not both with partial overlap. **Files:** `page.tsx` (`491–495, 630–636`), `GoingInStrip.tsx`, `GoingInCard.tsx`. **Effort:** S–M. **Why:** same metrics at different density reads as product indecision. **Observable:** one pre-run wellness section header in the DOM.

**4. Eliminate the second `RunShapeCanvas` on the Splits tab.** Reuse one canvas above tab content, or lift chart outside `panels` so Splits scrolls splits/map only. **Files:** `page.tsx` (`501–516` vs `582–595`), possibly `ActivityTabs.tsx`. **Effort:** L. **Why:** two mounted canvases (`ActivityTabs.tsx:52–63`) double the weight and confuse "which chart is real." **Observable:** single `data-testid="rsi-canvas"` per route; lower React tree size; no divergent hover state between hidden/visible charts.

**5. Flatten the Intervals/Mile-splits toggle when stacked under five tabs.** Avoid a second nav paradigm inside Splits unless it is the only control on screen. **Files:** `ActivitySplitsTabPanel.tsx` (`58–106`). **Effort:** M. **Why:** orange secondary toggles fight emerald primary tabs. **Observable:** fewer click targets to reach mile splits.

**6. Put map + elevation + splits on one coherent vertical for the default run view.** Overview omits `ElevationProfile` while Splits has it (`page.tsx:522–575` vs `ActivitySplitsTabPanel.tsx:139–163`); moving the profile beside the Overview map matches Strava's structural pairing using existing components. **Files:** `page.tsx`, possibly `ActivitySplitsTabPanel.tsx`. **Effort:** M. **Why:** reduces tab-hopping for "where + how hilly." **Observable:** users open Splits tab less often for GPS activities (if instrumented).

**7. Remove or wire dead RSI UI (`TierBadge`, `LabModePanel`).** Render per spec or delete the unused definitions. **Files:** `RunShapeCanvas.tsx:512–741`. **Effort:** S if delete, M if wire. **Why:** dead code signals unfinished layers and confuses future refactors. **Observable:** grep shows no orphan exported tier UI; tests stay green.

---

## 7. What not to do

No Strava social parity: **no feed, kudos, clubs, group challenges, segment leaderboards as a social game, route marketplace**. Orthogonal to N=1 instrument positioning, blows scope. No OAuth scope expansion without founder approval.

---

## 8. Deferred synthesis items

How `resolved_title`, `shape_sentence`, and `athlete_title` should relate in the hero (today `shape_sentence` is invisible). Whether `max_hr`, elapsed time, power, or running dynamics should appear in summary when present. Whether best-effort extraction should surface on activity detail vs only on `personal-bests`. Product call on segment efforts vs internal workout segments. Analytics on which tab athletes actually open (drives whether Context-only moats need to move up). Rounding contract between banner pace / split pace / chart pace so numbers never contradict without a labeled definition.

---

**Sources consulted:** `apps/web/app/activities/[id]/page.tsx`, `components/activities/ActivityTabs.tsx`, `ActivitySplitsTabPanel.tsx`, `rsi/RunShapeCanvas.tsx`, `RunIntelligence.tsx`, `AnalysisTabPanel.tsx`, `PaceDistribution.tsx`, `GoingInStrip.tsx`, `GoingInCard.tsx`, `WhyThisRun.tsx`, `FindingsCards.tsx`, `RuntoonCard.tsx`, `SplitsTable.tsx`, `IntervalsView.tsx`, `map/RouteContext.tsx`, `map/ActivityMapInner.tsx`, `map/ElevationProfile.tsx`, `map/RouteHistory.tsx`, `lib/context/StreamHoverContext.tsx`, `apps/api/models/activity.py`.
