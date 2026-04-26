# Activity Processing

## Current State

Every activity goes through a processing pipeline that extracts meaning from raw data. The pipeline produces shape classifications, pace analysis, maps, wellness stamps, and visual assets (Runtoons).

## How It Works

### Shape Extraction

`services/shape_extractor.py` is the core stream analysis engine:

1. **Input:** Raw activity stream (velocity, HR, elevation, distance, time)
2. **Smoothing:** Rolling mean, velocity clamping, pace conversion
3. **Phase detection:** Segments the run into sustained effort phases with zone classification
4. **Acceleration detection:** Identifies pace changes (surges, strides, hill efforts)
5. **Summary computation:** Elevation profile, pace progression, overall shape metrics
6. **Classification:** `_derive_classification()` produces one of: `easy_run`, `long_run`, `medium_long_run`, `gray_zone_run`, `progression`, `tempo`, `threshold_intervals`, `track_intervals`, `hill_repeats`, `fartlek`, `strides`, `over_under`, `anomaly`

The classification uses a priority cascade: hill repeats → progression → strides → tempo → threshold intervals → track intervals → long run → medium long → fartlek → over/under → easy run → gray zone → fallback easy.

**Hilly terrain handling:** On hilly runs, downhill segments can mechanically push pace into faster zones. The classifier relaxes `all_easy_or_gray` gates for hilly terrain and skips interval detection when elevation explains pace variation.

### Shape Sentence

Stored as `Activity.shape_sentence` — a natural language description (e.g., "5.5 mi building from 8:57 to 8:04" or "8.9 km building from 5:34 to 4:59"). Generated from the shape classification and summary data, using the athlete's preferred units.

### Run Shape Data

Stored as `Activity.run_shape` (JSONB) — the full `RunShape` object containing phases, accelerations, and summary. Used by the workout structure detector and the briefing prompt.

### Stream Analysis & Caching

- `services/run_stream_analysis.py` — stream-based analysis
- `services/stream_analysis_cache.py` — caches expensive analyses
- `CachedStreamAnalysis` model — persisted cache
- Frontend: `useStreamAnalysis` hook; run activity detail renders **CanvasV2** (legacy `RunShapeCanvas` retained on disk for reference only)

### Effort Classification

`services/effort_classification.py` — classifies effort intensity:
- **Tier 1:** HR percentile-based
- **Tier 2:** HRR earned
- **Tier 3:** Workout type + RPE

No max_hr gate — effort classification works without a known max HR.

### Heat Adjustment

`services/heat_adjustment.py` — computes `heat_adjustment_pct` from dew point. Higher dew point = harder effort for the same pace. Used by the correlation engine and environmental comparison normalization.

### Wellness Stamps

`services/wellness_stamp.py` — stamps activities with pre-activity wellness context:
- `pre_recovery_hrv`, `pre_overnight_hrv`, `pre_resting_hr`, `pre_sleep_h`, `pre_sleep_score`
- Captures the athlete's state going INTO the activity, not just the activity metrics

### Maps

Run-activity maps live inside **CanvasV2** (`components/canvas-v2/`) using
**Mapbox GL JS** with the standard outdoor style and a 3D terrain DEM.
Cross-training sport pages still use the older Leaflet + CartoDB Dark Matter
implementation described below.

**CanvasV2 / TerrainMap3D (run activity hero, April 2026):**

- **Real 3D terrain:** Mapbox GL with DEM exaggeration `3.0`, `pitch: 62`,
  `bearing: -20` set in the `Map` constructor and re-applied at
  `style.load` via `map.jumpTo()`. Built-in `hillshade` layer is left
  untouched (earlier `setPaintProperty` attempts threw "cannot read
  properties of undefined (reading 'value')" because the layer uses
  expressions). Visibility comes from terrain exaggeration plus the
  three-layer route, not from re-painting hillshade.
- **Three-layer route for contrast on light terrain:** white casing (wide,
  low opacity) + emerald glow (medium width, mid opacity) + deep emerald
  line (narrow, full opacity). Replaces the original yellow route that
  vanished against pale terrain.
- **Distance hover card** (leftmost moment-readout card): distance in the
  athlete's preferred units (miles or km), two-decimal precision matching
  watch convention, with a secondary time line. Replaces the earlier
  inline distance label per founder direction.
- **Navigation:** Mapbox `NavigationControl` is mounted so runners can
  rotate, tilt, and zoom freely.
- **Fullscreen:** desktop-only fullscreen toggle (Google-Maps-style) on the
  map. Initial render zoom is tighter than fitBounds default so the course
  fills the frame.
- **Help / info box:** `CanvasHelpButton` in the top-right slot opens a
  dismissible card explaining navigation. `localStorage` flag
  `canvasV2:hintsSeen` keeps it discoverable once and quiet thereafter.
- **CSP:** Caddy's `connect-src` allows Mapbox tile/style/sprite domains
  and `worker-src`/`child-src` allows `blob:`. CSP changes require a
  Caddy container restart, not just `caddy reload` (Docker bind-mount
  caching artefact on Linux).
- **`mapbox-gl/dist/mapbox-gl.css`** is statically imported at the top of
  `TerrainMap3D.tsx` (not dynamically), and a `mountError` state plus
  `map.on('error')` handler surface failures inline instead of going dark.

**StreamsStack (HR / pace / elevation under the map):**

- Order is fixed: HR top, pace middle, elevation bottom (HR sits closest to
  the map so the eye reads cardiac-cost-by-terrain at a glance).
- **Pace chart uses Tukey's fence (IQR, k=3.0)** for outlier clipping
  (`robustDomain` in `StreamsStack.tsx`). The previous percentile clip
  flattened pace artificially and produced a "haywire" tail — Tukey
  preserves real variation while excluding one-off spikes.
- Elevation chart uses the same smoothed series the splits tab uses so
  it's "less pointy" than the raw stream.
- All charts share `StreamHoverContext` with `TerrainMap3D` and the
  moment-readout cards: hover anywhere drives the dot, the elevation
  highlight, and the readout cards in lockstep.

**Cross-training maps (cycling / hiking / flexibility):** still use Leaflet
+ react-leaflet with CartoDB Dark Matter tiles:

- **GPS trace:** Two-source normalization (Garmin `track` field and `streamPoints`), downsampled to 2000 points using RDP algorithm with adaptive epsilon
- **Pace-colored route:** Red = fast (red-lining), blue = slow (easy). 5th-95th percentile normalization
- **Distance markers:** Interval-based filtering (≤5mi/8km: every unit, 5-15mi/8-24km: every 2, 15+mi/24+km: every 5), displayed in athlete's preferred units
- **Start/end markers:** Combined when within 50m (loops)
- **Elevation profile:** Interactive — hover shows elevation, gradient, pace, HR; dot moves on map. Wired to `StreamHoverContext`
- **Map aspect ratio:** 4:3 for usable surface area
- **No ghost traces on map:** Removed — overlapping GPS traces on the same path are unreadable. Route comparison belongs on charts, not map overlays.
- **Route History (chart-based):** `RouteContext.tsx` fetches `GET /v1/activities/{id}/route-siblings`, `RouteHistory.tsx` renders a pace-over-distance comparison chart (capped at 6 runs: 5 most recent + current + all-time average). Summary line: "8 runs on this route · Trending 14s/mi faster". Weather normalization toggle using `heat_adjustment_pct`.

### Runtoons

`services/runtoon_service.py` — generates shareable cartoon images of runs:

- **Scene generation:** LLM prompt receives run context (distance, elevation, effort, conditions)
- **Image generation:** AI model creates the cartoon
- **Text overlay:** Pillow (`recompose_stories()`) renders stats line, caption, and watermark
- **Storage:** R2/MinIO via `services/storage_service.py`
- **Frontend:** `components/runtoon/` — RuntoonCard view, rendered inside
  the activity-page **ShareDrawer** (`components/activities/share/`). The
  global `RuntoonSharePrompt` mobile auto-popup was retired April 2026:
  it polled `/v1/runtoon/pending` every 10s and slid up on every recent
  run, which made sharing a push action nobody wanted. Sharing is now a
  pull action — the Share button in the activity-page chrome opens
  `ShareDrawer`, which currently hosts the runtoon and a roadmap
  placeholder for future share styles (photo overlays, customizable
  stats, modern backgrounds, flyovers). The `RuntoonSharePrompt.tsx`
  file is preserved on disk for reference / rollback but is not
  imported in `app/layout.tsx`.

**Requirements:**
1. Stats line: distance, pace, duration, HR, date
2. Caption text
3. "strideiq.run" watermark
4. Scene must visually relate to the actual run

**Caps:** Founder account has no generation limit. Standard users have a tries limit.

### Cross-Training Detail Pages

Sport-specific detail pages branch on `activity.sport`:

| Sport | Component | Key data |
|-------|-----------|----------|
| `run` | **CanvasV2** (hero, chromeless) + 3 tabs (Splits / Coach / Compare) | Full stream analysis, Mapbox 3D terrain, stacked HR/pace/elevation, FeedbackModal + ShareDrawer in page chrome |
| `cycling` | `CyclingDetail` | Duration, distance, elevation, HR zones, TSS |
| `strength` | `StrengthDetail` | Exercise sets (if available), duration, HR |
| `hiking` | `HikingDetail` | Duration, distance, elevation profile, HR |
| `flexibility` | `FlexibilityDetail` | Duration, HR, wellness stamps |

## Key Decisions

- **Shape extractor > mile splits:** Stream-level classification is more reliable than split-based workout structure detection
- **4:3 map ratio:** Gives usable surface area vs panoramic layouts (cross-training Leaflet maps)
- **RDP downsampling:** Preserves route shape while reducing to 2000 points
- **No ghost traces on map:** GPS overlays on the same path are unreadable; route comparison uses pace-over-distance charts instead
- **Pillow text overlay:** All text rendered by Pillow, not the image model (which produces unreliable text)
- **Run map = real 3D Mapbox, not extruded 2D ribbon:** The earlier abstract-terrain prototype was rejected ("gold blob of nothing"). Real terrain with the route as a glowing path through it is the agreed visual vocabulary for run activities. Cycling/hiking can stay on flat 2D Leaflet for now.
- **Tukey's fence over percentile clip for pace charts:** IQR-based outlier detection (k=3.0) preserves real pace variation while excluding noise spikes; percentile clipping flattened pace artificially.
- **Share is a pull action, feedback is a push action:** The unskippable `FeedbackModal` auto-opens once per recent activity (RPE / reflection / workout-type confirmation are required for downstream intelligence). Sharing is hidden behind the Share button — never auto-popped.
- **Real measured metrics only:** Garmin proprietary scores (training effect, body battery impact, performance condition) are not ingested. The FIT run pipeline shipped Apr 19, 2026 (`fit_run_001`) brings in measured fields the watch + sensor combo records: power, stride length, ground contact (time + L/R balance), vertical oscillation, vertical ratio, total descent, true moving time. Garmin self-eval (`garmin_feel`, `garmin_perceived_effort`) is captured as a low-confidence fallback only — `services/effort_resolver.py` enforces the rule that the athlete's own RPE always wins.

### FIT-derived metrics on the activity page

Surfaced via `RunDetailsGrid` (self-suppressing card grid below the hero) and the `SplitsTable` "Columns" toggle. Each cell suppresses individually when its metric is null; the whole `RunDetailsGrid` suppresses when no card has data, keeping the page clean for older Strava-only activities and watch-only setups (no HRM-Pro / no Stryd / no Forerunner Pro).

**Empty-state truth (Apr 19, 2026):** For activities where FIT metrics *should* exist (runs, walks, hikes, cycles) but none arrived — typically because the activity was synced before the FIT pipeline existed — `RunDetailsGrid` no longer disappears silently. It renders a single small line: *"Power, stride, and form metrics weren't captured for this run."* This makes the data gap visible instead of looking like the feature didn't ship. As soon as any FIT field is populated the line is replaced by the real cards. Sports where these metrics don't apply (strength, yoga, swim) still suppress entirely.

`GarminEffortFallback` renders the watch's self-eval just above the Coach tab content **only** when the athlete hasn't reflected via the FeedbackModal. Once the athlete logs their own RPE, the fallback disappears entirely.

## Known Issues

- **Exercise set data sparse:** FIT file pipeline for strength is from Apr 6, 2026; historical strength activities have no exercise sets.
- **Run FIT data sparse:** Run/walk/hike FIT pipeline is from Apr 19, 2026 (`fit_run_001`); historical run activities have null power / running dynamics / true moving time. Going forward, every new run with a FIT file gets the full set.
- **Runtoon scene relevance:** Scene generation prompt sometimes produces unrelated scenes; needs stronger run-context anchoring.
- **Map performance with many points:** Large activities (30+ miles) may need more aggressive downsampling.

## Sources

- `docs/BUILDER_INSTRUCTIONS_2026-04-05_MAP_QUALITY_FIX.md` — Phase 1 map fixes
- `docs/BUILDER_INSTRUCTIONS_2026-04-05_MAP_PHASE2.md` — Phase 2 map features
- `docs/BUILDER_INSTRUCTIONS_2026-04-05_MAP_POLISH.md` — map polish corrections
- `docs/BUILDER_INSTRUCTIONS_2026-04-06_MAP_FINAL_CORRECTIONS.md` — final corrections
- `docs/specs/CROSS_TRAINING_SESSION_DETAIL_SPEC.md` — sport-specific details
- `docs/specs/LIVING_FINGERPRINT_SPEC.md` — shape extraction foundation
- `apps/api/services/shape_extractor.py` — core shape analysis
- `apps/api/services/runtoon_service.py` — Runtoon pipeline
- `apps/web/components/canvas-v2/` — CanvasV2 hero (TerrainMap3D, StreamsStack, CanvasHelpButton, distance hover)
- `apps/web/components/activities/feedback/` — FeedbackModal, ReflectPill, useFeedbackCompletion, useFeedbackTrigger
- `apps/web/components/activities/share/` — ShareButton, ShareDrawer
- `apps/web/app/activities/[id]/page.tsx` — page composition (chrome pills, hero, 3 tabs)
