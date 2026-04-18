# Run 3D Map — Spec

**Status:** Draft. Not approved. Not in build queue.
**Author:** Sandbox handoff after canvas-v2 phase 1 review.
**Date:** 2026-04-18

---

## 1. Why this exists

The first pass at a 3D run visualization (`canvas-v2` sandbox, abstract
sculptural heightfield) was dead on arrival in founder review:

> "The terrain blob is of a place with two big lakes, 19 percent grade,
> hundreds of feet of elevation change, and looks like a gold blob of
> nothing... if that's the ceiling for that approach, it's a non-starter."

The fundamental problem: a path-only heightfield has **no surrounding
terrain context**. Lakes, hills, surrounding road network, and place
identity are all invisible. Without context, altitude alone reads as
noise. The existing 2D Leaflet map (route + pace coloring + basemap) is
strictly better than the abstract 3D blob — it shows the lakes, the
roads, where you actually were.

Founder bar (binding):
> "The existing map is the floor we're trying to leap over, not the bar."

So the goal of this spec is not "match the 2D map in 3D." It is "build a
3D run map that is **light years better** than the existing 2D map at
telling the story of one run."

---

## 2. What "light years better" looks like

The visualization must answer, at a glance:

1. **Where was this?** Real basemap, real water, real road network, real
   place. Recognizable to a local; orienting to a stranger.
2. **What was the terrain?** Real elevation. Hills you climbed should
   look like hills, not bumps on a mound. A flat run should look flat.
3. **What was the run?** Route overlaid as a glowing line, colored by
   pace (or HR, or grade — togglable). Direction indicated.
4. **Where am I right now in the run?** A position marker that scrubs in
   lockstep with the 2D Pace/HR/Elevation streams above. Hovering the
   pace chart at mile 6 moves the marker on the map to mile 6.
5. **What did the moment feel like?** Camera angle, terrain perspective,
   and elevation exaggeration combine so that the climb at mile 4 is
   visually *the* climb, not a generic bump.

Non-goals (v1):
- Photoreal satellite texture (Phase 2 if at all — license cost).
- Animated runner figure with stride mechanics (Phase 2; the dot is fine).
- Weather overlays, time-of-day lighting (Phase 2).
- Cinematic flythrough on load (Phase 2 — it's a feature, not a default).
- Editable 3D camera presets per athlete (Phase 3).

---

## 3. Engine evaluation

Four real options. All are mature, all can produce something dramatically
better than the abstract heightfield.

### Option A: Mapbox GL JS with `setTerrain`

**What it gives us:**
- Built-in 3D terrain via `mapbox-dem` raster-DEM source. Free tier.
- Wide choice of basemaps (streets, outdoors, satellite, custom styles).
- Native support for water bodies (lakes show up correctly with no extra
  work).
- Path overlay via `LineLayer` with feature-state for per-segment color
  (pace coloring is one source + a paint expression).
- Pitch / bearing / camera animation built-in. `flyTo` for cinematic moves.
- Mobile-good performance; we already render Leaflet on mobile fine.
- TypeScript SDK is mature.

**Costs:**
- Mapbox token required. Free tier: 50k map loads/month. After that
  ~$5/1k loads (cheap until ~10k MAU, real money at scale).
- Vendor lock-in. Style URLs are Mapbox-specific.

**Verdict:** Strongest default. Lowest engineering risk, highest visual
ceiling per dev-day, mature ecosystem, reasonable cost curve.

### Option B: MapLibre GL + open DEM

**What it gives us:**
- API-compatible with Mapbox GL (Mapbox forked v2 to closed source;
  MapLibre is the open community fork at v1).
- Free, no token, no per-load billing.
- Can consume Mapbox-style raster-DEM tiles from open sources (AWS
  Terrarium, MapTiler — MapTiler has a free tier too).
- Same `setTerrain` mental model.

**Costs:**
- DEM tile sourcing is on us. AWS Terrarium tiles are free but require
  setup. MapTiler free tier is generous but not unlimited.
- Basemap quality is *good* (MapTiler, Stadia) but not as visually polished
  as Mapbox's "outdoors" or custom styles.
- Less marketing-grade out of the box; more work to make it look stunning.

**Verdict:** Strong if cost or independence matter more than visual
ceiling. Real "no vendor lock-in" path.

### Option C: deck.gl (`TerrainLayer` + `PathLayer`)

**What it gives us:**
- WebGL2 layer composition. Pluggable basemap (Mapbox, MapLibre, plain
  background).
- Composable with our existing React tree more naturally than imperative
  Mapbox API.
- `TerrainLayer` consumes any DEM source (Mapbox or open).
- `PathLayer` and `TripsLayer` are first-class for animated route
  visualizations.

**Costs:**
- Steeper learning curve than Mapbox GL alone.
- We typically still pair it with Mapbox/MapLibre underneath for the
  basemap, so it's *additive* complexity, not a replacement.

**Verdict:** Best if we need heavy custom layer logic later (e.g., 3D
heatmaps, vector field overlays, multi-route comparisons). Overkill for v1.

### Option D: CesiumJS

**What it gives us:**
- The original geospatial 3D engine. Globe-scale terrain (Cesium World
  Terrain), curated.
- Best-in-class for cinematic camera, 3D buildings, time-dynamic data.
- Works well for dramatic, marketing-grade visuals.

**Costs:**
- Heavyweight. Bundle is large. Initial load slower.
- Cesium ion (their tile service) has a free tier but production usage
  often needs paid plans.
- Geared toward GIS / aerospace use cases. Overpowered for "show one run."

**Verdict:** Powerful but wrong tool for everyday run visualization. Worth
considering only if we ever build a "globe view of all your races" feature.

### Recommendation

**Mapbox GL JS for v1.** Lowest risk, highest visual ceiling per dev-day.
If/when we hit a cost wall, swap to MapLibre — the API surface we'd use
is ~95% compatible, so it's a real exit option, not just lock-in talk.

---

## 4. Data dependencies

What we need server-side. Most already exists.

### Already have
- `Activity.run_shape.stream` — LTTB-downsampled to ~500 points per run
  with `lat`, `lng`, `altitude`, `pace`, `hr`, `cadence`, `grade`, `time`.
  This is what the existing 2D map and the canvas-v2 streams already
  consume. No new endpoint needed for v1.

### Need to confirm
- That altitude on the stream matches what Garmin/Strava reports for the
  activity (not derived from a coarser DEM lookup). If derived, the elevation
  band on the stream chart and the terrain heights will agree by accident
  but won't match Garmin's official elevation summary. **Verify before build.**

### New (none for v1)
- v2: tile prefetch / cache headers on the API for race-week routes.
- v2: water mask polygon source for lakes if we want to render reflective
  water planes (Mapbox basemaps already show water styling — this is only
  if we want the cinematic version).

---

## 5. UX architecture

The 3D map replaces the deleted `TerrainPanel` slot in `CanvasV2.tsx`. The
rest of canvas-v2 stays as is:

```
SummaryCardsRow         (run-level, never scrubs)
StreamsStack            (Pace + HR + Elevation, drives scrub)
MomentReadout           (instantaneous values at scrub)
RunMap3D                (NEW — replaces the deleted terrain panel)
```

`RunMap3D` props:
- `track: TrackPoint[]` — already produced by `useResampledTrack`.
- `bounds: TrackBounds` — already computed.
- `colorMode: 'pace' | 'hr' | 'grade' | 'plain'` — toggle in the panel
  header. Defaults to `pace` to mirror the existing 2D map.

Internal state:
- Mount Mapbox GL with style `mapbox://styles/mapbox/outdoors-v12` (or a
  custom dark style we author).
- On mount: `setTerrain` with `mapbox-dem` source, exaggeration auto-tuned
  from `bounds.altitudeReliefM` (low-relief runs need 1.3–1.5×, mountain
  runs need 1.0× — too much exaggeration and Bonita Reservoir starts
  looking like the Alps; too little and a flat 5K looks like a parking
  lot).
- Add a `LineLayer` for the route, paint expression keyed to a
  per-segment numeric attribute (pace m/s normalized to color stops).
- Add a `SymbolLayer` or custom HTML overlay for the position marker;
  subscribe to `useScrubState` and update marker `lng,lat` on change.
- Initial camera: fit bounds with pitch ~55°, bearing aligned to the
  route's principal axis (compute via simple PCA on lat/lng so the route
  reads "lengthwise" not perpendicular to the camera).

---

## 6. Scope cuts (binding for v1)

To keep v1 shippable in days, not weeks, **explicitly out**:
- No animated camera flyovers ("cinematic mode").
- No multi-route comparison overlay (that's the Compare redesign).
- No labelled landmarks beyond what the basemap provides natively.
- No custom water reflectivity / lighting beyond Mapbox defaults.
- No mobile-tablet split (we render the same 3D map on all viewports;
  performance acceptable on iOS Safari with Mapbox GL — verify in build).
- No dark/light mode toggle — pick one (likely dark to match canvas-v2)
  and ship it.

---

## 7. Risks

1. **Mapbox cost at scale.** Free tier covers us until ~10k monthly active
   athletes loading maps. Past that, costs grow linearly. Mitigation:
   MapLibre exit path is real (see §3). Track map-load-per-MAU as a
   product metric from day 1.
2. **Mobile perf on iOS Safari.** Mapbox GL with terrain has a known set
   of perf cliffs on older iOS. Mitigation: spike a real-device test on an
   iPhone 12-equivalent before committing to the full build.
3. **Vertical exaggeration tuning.** If we get this wrong, low-relief runs
   look fake or high-relief runs look cartoonish. Mitigation: small
   calibration table keyed to relief-per-distance ratio, not raw relief.
4. **DEM resolution mismatch.** Mapbox's `mapbox-dem` is ~10m horizontal
   resolution at z14. Sharp single-track features (a 3m berm) will be
   smoothed away. Acceptable for road/trail runs; not for technical
   single-track. Document the limitation; do not market "perfect terrain."
5. **License/attribution.** Mapbox requires attribution in the corner.
   Our existing Leaflet map already shows OSM/CARTO attribution, so this
   is not a regression — just a UI requirement.

---

## 8. Build sequence (when approved)

1. **Engine spike** (½ day). Throwaway page, single hardcoded activity,
   prove Mapbox + DEM + route overlay + scrub marker works end-to-end on
   desktop and one real iPhone. Outcome: go/no-go on Mapbox.
2. **`RunMap3D` v0.1** (1 day). Production component, props-driven, no
   color toggle, no camera presets. Ships behind canvas-v2 founder gate.
3. **Founder review.** Same loop as canvas-v2 phase 1 — show, get
   feedback, decide whether to iterate or kill.
4. **Color toggle + camera tuning** (1 day, conditional on §3 going well).
   Pace / HR / grade color modes. PCA-based initial bearing. Auto vertical
   exaggeration calibration table.
5. **Perf + mobile pass** (½ day). Lazy-load the Mapbox bundle, verify
   First Load JS impact stays acceptable, iOS Safari real-device test.
6. **Promote out of sandbox** (½ day). Move from `canvas-v2` route to
   replace the existing 2D map, behind a percentage rollout flag.

Total: ~3.5 dev-days for v1, gated on founder approval at each step.

---

## 9. Decision points needed from founder before build

1. **Engine.** Mapbox GL (recommended) vs MapLibre vs deck.gl vs Cesium.
2. **Cost ceiling.** What's the monthly Mapbox bill we're willing to
   accept at 1k / 5k / 10k MAU before we either swap engines or pass cost
   along (e.g., paid tier feature)?
3. **Default color mode.** Pace, HR, grade, or plain glowing line.
4. **Scope cuts.** Confirm §6 cuts are acceptable for v1.
5. **Sequencing vs Compare redesign.** Compare redesign is queued behind
   canvas-v2 (per `docs/specs/COMPARE_REDESIGN.md`). Does this 3D map
   work re-open that sequencing question, or stay queued?

---

## 10. What this spec does *not* commit to

- A timeline.
- A specific engine (recommendation only).
- That we will build this at all. The path-only heightfield was killed
  for cause; this could be killed for cause too if cost, perf, or visual
  outcome don't clear the "light years better than the 2D map" bar.

---

## Appendix: rejected alternatives

- **Extruded 2D ribbon along the path.** Founder rejected: "kind of tacky."
- **Three.js custom heightfield from path-only altitude.** Built and
  killed (canvas-v2 phase 1, removed 2026-04-18). Cannot show surrounding
  context; is strictly worse than the existing 2D map.
- **Pure SVG isometric route.** Cute for marketing, doesn't scale to real
  terrain reading.
- **Static screenshot from a desktop GIS tool.** Not interactive; not a
  product.
