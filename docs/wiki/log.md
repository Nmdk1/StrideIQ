# Wiki Log

## [2026-04-10] rpi-table-fix | RPI calculator replaced with derived hardcoded table

- **Replaced:** `rpi_calculator.py` — removed the broken `INTENSITY_TABLE` + formula pipeline that regressed 3+ times at low RPIs (produced 7:41/mi interval for a 62:00 10K runner). Replaced with `_RPI_PACE_TABLE`: a 66-row hardcoded lookup (RPI 20-85) derived from the published Daniels/Gilbert oxygen cost + time-to-exhaustion equations, with a slow-runner correction for RPI < 39. Verified against official reference calculator to +/- 1 second at all tested levels.
- **New file:** `rpi_pace_derivation.py` — full derivation script with formulas, constants, verification against reference, and generated table. Serves as evidence the table was derived, not copied.
- **Removed:** `MAX_T_TO_I_GAP` band-aid from `workout_prescription.py` — no longer needed since the table produces physiologically correct T-I gaps natively.
- **Updated:** `plan-engine.md` — added RPI-to-Training-Pace Calculator section with derivation method, sample paces, and critical rule against formula replacement.
- **Production fix:** Larry Shaffer's plan paces updated from old values (E=12:30, T=9:37, I=7:41) to correct derived values (E=11:14, T=9:43, I=8:40, R=8:16).

## [2026-04-10] plan-engine-kb-nutrition-elevation | Plan engine V2 spec, coaching science KB, nutrition elevated

- **Updated:** `plan-engine.md` — Added "Next-Generation Algorithm Spec (V2)" section: Build/Maintain/Custom modes, extension-based progression, build-over-build memory, unified segments schema, effort-based descriptions, fueling targets. Added coaching science KB table (13 documents: Davis, Green, Roche). Added single-hierarchy sliding-bottleneck model. Updated sources list.
- **Updated:** `nutrition.md` — Added "Nutrition as a First-Class Metric" section: elevated to #3 in hierarchy, plan generator fueling targets by training age, briefing integration, future product calculator. Updated key decisions to reflect first-class status.
- **Updated:** `product-vision.md` — Plan engine now references V2 spec and 13 KB docs. Nutrition marked as first-class metric. Added priorities 19-22: Training Lifecycle (SPECIFIED), Algorithm V2 (SPECIFIED), Native App (PRELIMINARY), Audio Coach (SCOPED).
- **Updated:** `index.md` — date bumped.

## [2026-04-10] nutrition-telemetry-reports | Three features shipped, three wiki pages added

- **New page:** `nutrition.md` — AI Nutrition Intelligence: photo/barcode/NL parsing, fueling shelf, nutrition planning, load-adaptive targets, USDA integration, correlation engine wiring, coach tools
- **New page:** `telemetry.md` — Usage Telemetry: PageView model, usePageTracking hook, admin usage report, no third-party analytics
- **New page:** `reports.md` — Unified Reports: cross-domain health/activities/nutrition/body-comp reporting, curated + extended metrics, CSV export
- **Updated:** `index.md` — date bumped to Apr 10, All Pages table expanded with Nutrition, Telemetry, Reports links
- **Updated:** `product-vision.md` — priorities 16-18 marked SHIPPED, What's Built section expanded with nutrition, telemetry, reports. Scale numbers updated (85 models, 113 migrations, 79 correlation inputs)
- **Updated:** `frontend.md` — added `/nutrition` and `/reports` routes, `components/nutrition/` directory, `usePageTracking` hook, nutrition entry inline editing
- **Updated:** `infrastructure.md` — migration count 113, model count 85, expected heads `usage_telemetry_001`, new routers table (nutrition, reports, telemetry)
- **Updated:** `coach-architecture.md` — tools count ~26, added `get_nutrition_correlations` and `get_nutrition_log` tools, nutrition context in athlete brief, key decision entry
- **Updated:** `correlation-engine.md` — added Nutrition Inputs section with 9 metrics from `aggregate_fueling_inputs()`

## [2026-04-08] strategy-update | Strategy priorities 14-16 added

- Added Compound Recovery Signals (14), Personal Coach Tier (15), AI Nutrition Intelligence (16) to product-vision.md
- Added HRV÷RHR compound signal to correlation-engine.md What's Next

## [2026-04-08] review-fixes | Founder review — 5 corrections

- **Fixed:** Ghost traces incorrectly stated as removed; they are live in production (`RouteContext.tsx`, `RouteHistory.tsx`, opacity tiers by recency)
- **Fixed:** Deploy command used `docker restart` (old image) instead of `docker compose up -d --build` (rebuild all). Corrected in index.md and infrastructure.md.
- **Fixed:** Missing null-structure guardrail — the `else` branch in `_summarize_workout_structure` that explicitly tells the LLM "NO WORKOUT STRUCTURE DETECTED" was not documented
- **Fixed:** Token cap table now highlights that the opus cap is the binding constraint (2M standard, 5M VIP) since all traffic routes through the opus lane
- **Fixed:** Index Quick Reference now separates coach model (Kimi K2.5) from briefing model (Claude Opus 4.6)

## [2026-04-08] init | Wiki created from 339 source documents

- **Pages created:** index.md, product-vision.md, coach-architecture.md, briefing-system.md, correlation-engine.md, plan-engine.md, garmin-integration.md, activity-processing.md, operating-manual.md, infrastructure.md, monetization.md, frontend.md, quality-trust.md, decisions.md
- **Source documents read:** 339 markdown files across docs/, docs/specs/, docs/references/, docs/adr/, docs/garmin-portal/, docs/phase2/, docs/phase3/, docs/research/
- **Additional sources:** Codebase structure (services/, routers/, tasks/, models.py, components/, app/, docker-compose files, CI workflows)
- **Known gaps:**
  - Strava integration: minimal wiki coverage (Strava is secondary to Garmin; basic sync exists but not a focus area)
  - `docs/BUILDER_INSTRUCTIONS_2026-03-20_PLAN_QUALITY_RECOVERY_V2.md` referenced by other docs but missing from repo
  - ADR-052 has duplicate numbering (two different topics)
  - Women's Health Intelligence Layer: strategic priority #7 but no implementation or spec exists
  - Swimming data parsing: sport is accepted but no specialized processing beyond basic metrics
