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

Stored as `Activity.shape_sentence` — a natural language description (e.g., "5.5 miles building from 8:57 to 8:04"). Generated from the shape classification and summary data.

### Run Shape Data

Stored as `Activity.run_shape` (JSONB) — the full `RunShape` object containing phases, accelerations, and summary. Used by the workout structure detector and the briefing prompt.

### Stream Analysis & Caching

- `services/run_stream_analysis.py` — stream-based analysis
- `services/stream_analysis_cache.py` — caches expensive analyses
- `CachedStreamAnalysis` model — persisted cache
- Frontend: `useStreamAnalysis` hook for the RunShapeCanvas

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

Activity maps use Leaflet + react-leaflet with CartoDB Dark Matter tiles:

- **GPS trace:** Two-source normalization (Garmin `track` field and `streamPoints`), downsampled to 2000 points using RDP algorithm with adaptive epsilon
- **Pace-colored route:** Red = fast (red-lining), blue = slow (easy). 5th-95th percentile normalization
- **Mile markers:** Interval-based filtering (≤5mi: every mile, 5-15mi: every 2, 15+: every 5)
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
- **Frontend:** `components/runtoon/` — share prompt and view

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
| `run` | Existing RunShapeCanvas | Full stream analysis, pace zones |
| `cycling` | `CyclingDetail` | Duration, distance, elevation, HR zones, TSS |
| `strength` | `StrengthDetail` | Exercise sets (if available), duration, HR |
| `hiking` | `HikingDetail` | Duration, distance, elevation profile, HR |
| `flexibility` | `FlexibilityDetail` | Duration, HR, wellness stamps |

## Key Decisions

- **Shape extractor > mile splits:** Stream-level classification is more reliable than split-based workout structure detection
- **4:3 map ratio:** Gives usable surface area vs panoramic layouts
- **RDP downsampling:** Preserves route shape while reducing to 2000 points
- **No ghost traces on map:** GPS overlays on the same path are unreadable; route comparison uses pace-over-distance charts instead
- **Pillow text overlay:** All text rendered by Pillow, not the image model (which produces unreliable text)

## Known Issues

- **Exercise set data sparse:** FIT file pipeline is new (Apr 6, 2026); historical activities have no exercise sets
- **Runtoon scene relevance:** Scene generation prompt sometimes produces unrelated scenes; needs stronger run-context anchoring
- **Map performance with many points:** Large activities (30+ miles) may need more aggressive downsampling

## Sources

- `docs/BUILDER_INSTRUCTIONS_2026-04-05_MAP_QUALITY_FIX.md` — Phase 1 map fixes
- `docs/BUILDER_INSTRUCTIONS_2026-04-05_MAP_PHASE2.md` — Phase 2 map features
- `docs/BUILDER_INSTRUCTIONS_2026-04-05_MAP_POLISH.md` — map polish corrections
- `docs/BUILDER_INSTRUCTIONS_2026-04-06_MAP_FINAL_CORRECTIONS.md` — final corrections
- `docs/specs/CROSS_TRAINING_SESSION_DETAIL_SPEC.md` — sport-specific details
- `docs/specs/LIVING_FINGERPRINT_SPEC.md` — shape extraction foundation
- `apps/api/services/shape_extractor.py` — core shape analysis
- `apps/api/services/runtoon_service.py` — Runtoon pipeline
