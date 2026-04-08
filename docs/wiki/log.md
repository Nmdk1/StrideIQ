# Wiki Log

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
