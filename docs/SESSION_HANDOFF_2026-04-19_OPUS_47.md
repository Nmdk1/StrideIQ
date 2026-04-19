# Session Handoff — April 19, 2026

**For:** Next agent (any model)
**From:** Opus 4.7 (activity-page rebuild + backend-green sweep + wiki-currency rule)
**Production:** https://strideiq.run | Server: root@187.124.67.153

---

## MANDATORY READ ORDER

**Read ALL of 1-6 before proposing anything. If you can't reference specific content from these docs, you haven't read them.**

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — How to work. Non-negotiable. **Now includes rule 13: wiki must always be current.**
2. `docs/PRODUCT_MANIFESTO.md` — The soul. What this product IS.
3. `docs/PRODUCT_STRATEGY_2026-03-03.md` — The moat. 16 priority-ranked product concepts.
4. `docs/specs/CORRELATION_ENGINE_ROADMAP.md` — 12-layer roadmap. Layers 1-4 built.
5. `docs/FINGERPRINT_VISIBILITY_ROADMAP.md` — How backend intelligence connects to product.
6. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — How every screen should feel. What's rejected. **New contracts added: 3D Terrain Standard, Feedback Push / Share Pull, Wiki Currency.**

**Context docs (read as needed):**

7. `docs/wiki/index.md` — **Operational mental model of the live system. Authoritative for current state. Treat the page-ownership map as binding.**
8. `docs/wiki/log.md` — Chronological record of what shipped (April 19 entry on top).
9. `docs/TRAINING_PLAN_REBUILD_PLAN.md` — Build priority order, open gates, enforced contracts.
10. `docs/SITE_AUDIT_LIVING.md` — Honest full-product inventory (updated today).
11. `docs/BUILD_SPEC_HOME_AND_ACTIVITY.md` — Activity Detail half is now superseded by the Phase 1-4 rebuild section near the bottom; Home half still partially in force.
12. `.cursor/rules/wiki-currency.mdc` — Wiki currency contract with page-ownership map and session-end checklist.

---

## WHAT THIS PRODUCT IS

StrideIQ is a running intelligence platform for competitive runners. It syncs data from Garmin (primary) and Strava, runs a correlation engine that discovers N=1 patterns in each athlete's data, and surfaces those findings through:

- **Morning briefing** — LLM-generated daily coaching briefing grounded in the athlete's actual data.
- **AI coach** — Conversational coach (Kimi K2.5) with tool-calling access to the athlete's full history.
- **Personal Operating Manual** — Auto-generated document of the athlete's discovered patterns.
- **Fingerprint** — Browsable correlation findings with confidence, thresholds, and lifecycle states.
- **Activity detail page** — Now CanvasV2 (real Mapbox 3D terrain) hero + 3 tabs (Splits / Coach / Compare), with unskippable FeedbackModal and pull-action ShareDrawer in the page chrome.
- **Training plans** — V1 (production default) and V2 (admin-only sandbox) plan generators.
- **Public tools** — Free calculators (training pace, age grading, race equivalency, BQ times, heat adjustment) that drive SEO.

The founder (Michael Shaffer) is the primary user and a competitive runner. His father is also an active user. Both are primarily desktop users; a large fraction of athletes are mobile-first. The product has real athletes on it — never break production.

---

## CURRENT STATE

### Test Suite

- Frontend Build, Frontend Tests, Docker Build: green on `main`.
- Backend Tests (the manual `workflow_dispatch` job): green after this session's 39-failure sweep — see "What Was Just Completed."
- The `backend-test` job runs only on `schedule` / `workflow_dispatch`, **not on `push`**. If you change backend code, run it manually after merging or before declaring a session done. (`gh workflow run "Backend Tests"`.)

### Production

- Deployed and smoke-tested April 19, 2026.
- All containers healthy: API, Web, Worker, Beat, Postgres, Redis, Caddy, MinIO.
- Smoke checks: `/ping` 200, `/v1/home` 200 with full key set, `/v1/coach/brief` 200, `/v1/activities` 200 with list payload.
- CanvasV2 renders Mapbox terrain end-to-end on real activity URLs (verified on the founder's Bonita Lakes loop, https://strideiq.run/activities/33175a1e-42f9-43d1-b410-c2c7e4dcc725).
- `RuntoonSharePrompt` confirmed absent from the global layout.

### Codebase Notes (post this session)

- `apps/web/components/canvas-v2/` — CanvasV2 (chromeless prop), TerrainMap3D (Mapbox GL real 3D terrain), StreamsStack (HR/pace/elevation, Tukey-fence outlier clip), CanvasHelpButton, distance hover card.
- `apps/web/components/activities/feedback/` — FeedbackModal, ReflectPill, useFeedbackCompletion, useFeedbackTrigger.
- `apps/web/components/activities/share/` — ShareButton, ShareDrawer.
- `apps/web/app/activities/[id]/page.tsx` — page composition (chrome pills, hero, 3 tabs).
- `apps/web/app/layout.tsx` — `RuntoonSharePrompt` import removed (preserved on disk; intentionally not mounted). Static regression test at `apps/web/__tests__/layout-no-runtoon-prompt.test.ts` enforces this.
- `apps/api/tasks/garmin_webhook_tasks.py` — `_ingest_activity_detail_item_full(...) -> (Activity | None, bool)` is the new internal API; `_ingest_activity_detail_item` retained as a boolean wrapper for backward compat. Garmin field-name access goes through `adapt_activity_detail_envelope` from `garmin_adapter.py`.
- `.cursor/rules/wiki-currency.mdc` — new always-applied rule.
- `.cursor/rules/founder-operating-contract.mdc` — gains rule 13 (wiki) and adds `docs/wiki/index.md` to the read order.

### Key Architecture (unchanged)

- **LLM routing:** Every coach query → Kimi K2.5. Briefings → Claude Opus. Fallback → Claude Sonnet 4.6.
- **Correlation engine:** Layers 1-4 built. Discovers N=1 patterns per athlete. Confounder control (partial correlation). Lifecycle states (emerging → active → resolving → closed).
- **RPI Calculator:** `_RPI_PACE_TABLE` — 66-row hardcoded lookup. **DO NOT MODIFY OR REPLACE WITH A FORMULA.** Verified to ±1 second against the official reference calculator.
- **Plan Engine V2:** Accessible via `?engine=v2` query param (admin/owner only). V1 remains default. See `docs/TRAINING_PLAN_REBUILD_PLAN.md` for rollout gates.

---

## WHAT WAS JUST COMPLETED (This Session)

### Activity Page Rebuild — Phases 1-4 (shipped end-to-end in one session)

- **Phase 1 — CanvasV2 as the hero.** `chromeless` prop on `CanvasV2`; runs render it as the page hero. `TerrainMap3D.tsx` uses Mapbox GL with `pitch: 62`, `bearing: -20`, DEM exaggeration `3.0`. Three-layer route (white casing + emerald glow + deep emerald line). `mapbox-gl/dist/mapbox-gl.css` lifted to a static top-level import (was the cause of the production "completely dark map" regression). `NavigationControl` mounted; desktop fullscreen toggle; tighter initial zoom; distance moved to a leftmost moment-readout hover card (two-decimal miles + secondary time line). `StreamsStack` order locked to HR top / pace middle / elevation bottom; pace `robustDomain` switched to **Tukey's fence (IQR, k=3.0)** to preserve real pace variation; elevation uses the smoothed series the splits tab uses. Caddy CSP allows Mapbox tile/style/sprite domains in `connect-src` and `blob:` in `worker-src`/`child-src`; CSP changes require a Caddy container restart, not just `caddy reload` (Docker bind-mount cache).
- **Phase 2 — Tabs 6 → 3.** `Splits` (no map; the hero already has it), `Coach` (absorbs `RunIntelligence`, `FindingsCards`, `WhyThisRun`, `GoingInCard`, `AnalysisTabPanel`, and `activity.narrative`), `Compare` (placeholder; redesign sequenced behind the canvas — see `docs/specs/COMPARE_REDESIGN.md`). The bottom-of-page `RuntoonCard` is gone (lives in ShareDrawer now).
- **Phase 3 — Unskippable FeedbackModal + ReflectPill.** Three sections (reflection, RPE, workout-type confirmation), no escape hatch (no X / Cancel / Skip / backdrop dismiss). Save & Close stays disabled until all three are complete. Auto-classified workout types require explicit "Looks right" confirmation (`workoutTypeAcked` only pre-true when `existingWorkoutType.is_user_override === true`). `useFeedbackTrigger` auto-opens once per recent run, gated on a `localStorage` flag so it doesn't re-pop after save. Edits remain available later via `ReflectPill` — sources status from `useFeedbackCompletion`.
- **Phase 4 — Share is a pull action.** `ShareButton` page-chrome pill (next to `ReflectPill`, run-only) opens `ShareDrawer`, which hosts the `RuntoonCard` and a roadmap placeholder (photo overlays, customizable stats, modern backgrounds, flyovers). Drawer dismisses via close button, Escape, or backdrop click. `RuntoonSharePrompt` removed from `app/layout.tsx`.

### Backend-Green Sweep — 39 Pre-Existing Failures Resolved

The `backend-test` CI job runs only on `schedule` / `workflow_dispatch`, so a cluster of failures had been hiding on `main` for weeks. Running it manually surfaced 39 broken tests across five clusters; all fixed in the same merge:

1. `test_scripts_hygiene` — docstring example emails replaced with env-var placeholders.
2. **Garmin D5/D6 source-contract** — `apps/api/tasks/garmin_webhook_tasks.py` accessed `activityId` from raw payload; now routed through `adapt_activity_detail_envelope`.
3. **Garmin D5 stream-ingestion** (`StopIteration`, `assert 1==2`) — refactored to `_ingest_activity_detail_item_full(...) -> (Activity | None, bool)`; caller consumes the returned `Activity` directly instead of re-querying.
4. **Garmin feature-flag and D7 backfill** — `_make_*` helpers built `MagicMock` athletes with truthy `is_demo`, tripping the demo-account guard. Helpers now explicitly set `is_demo = False`. D7 callback test patches `routers.garmin.is_feature_enabled` to `True`.
5. **`test_phase3b_graduation::test_quality_score_attached_to_result`** — patched `services.intelligence.workout_narrative_generator._call_narrative_llm` to a canned narrative so the quality scorer is exercised in CI.
6. **Nutrition API tests (21 failures)** — `MAX_BACKLOG_DAYS = 60` made hardcoded `2024-XX-XX` dates obsolete. Introduced `TODAY = date.today()` + `_d(offset_days)` helper; replaced every hardcoded date in test data and URLs.

### Wiki Currency Made Mandatory

- `.cursor/rules/wiki-currency.mdc` — new always-applied rule with page-ownership map, session-end checklist, and clear separation between wiki / specs / vision docs.
- `.cursor/rules/founder-operating-contract.mdc` — rule 13 added; `docs/wiki/index.md` added to read order.
- `docs/wiki/index.md` — `Last updated:` bumped to April 19; Maintenance Contract reworded with teeth.
- `docs/wiki/frontend.md` — activity-page rebuild captured (CanvasV2 hero, 3 tabs, FeedbackModal/ReflectPill, ShareButton/ShareDrawer, RuntoonSharePrompt retired, Mapbox CSP note).
- `docs/wiki/activity-processing.md` — Maps section split into "CanvasV2 / TerrainMap3D" (run hero) and "cross-training maps" (legacy Leaflet); StreamsStack documented with Tukey's fence; runtoon section updated to reflect ShareDrawer; Sport branching table updated; Key Decisions extended with three new entries.
- `docs/wiki/log.md` — dated entry for April 19 covering everything above.

### Documentation Updates (this session)

- `docs/SITE_AUDIT_LIVING.md` — three new top entries (Activity Page Rebuild Phases 1-4, Backend-Green Sweep, Wiki Currency), `Last updated:` bumped.
- `docs/BUILD_SPEC_HOME_AND_ACTIVITY.md` — superseded-by banner at top; new "Shipped After Original Spec — Activity-Page Rebuild Phases 1-4" section near bottom that explicitly maps which original A1/A2/.../A6 changes are superseded vs still relevant.
- `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — three new contracts: Run-Activity 3D Terrain Standard, Feedback Push / Share Pull, Wiki Currency.
- `docs/SESSION_HANDOFF_2026-04-19_OPUS_47.md` — this file.

---

## WHAT'S NEXT (Founder's Priority Order)

Consult `docs/TRAINING_PLAN_REBUILD_PLAN.md` for the canonical priority list.

In addition, the following carry-overs are open from this session:

1. **Compare tab redesign** — placeholder sits in the new 3-tab layout as an "urgent reminder." Sequenced behind the canvas vocabulary; see `docs/specs/COMPARE_REDESIGN.md`. The founder explicitly wants this done — when, is up to them.
2. **Share Drawer roadmap** — the placeholder in `ShareDrawer` lists photo overlays, customizable stats, modern backgrounds, flyovers. None built yet. Sharing has been intentionally re-architected as a pull action; future share styles plug in here.
3. **Nutrition meal builder** — the Meals tab create form takes per-item macros as raw inputs and does not yet wire to `/v1/nutrition/parse` or USDA autocomplete. Documented in `docs/SITE_AUDIT_LIVING.md` Phase 3 entry as the next nutrition task.

**DO NOT** start building without the founder's explicit direction. Ask what they want to work on.

---

## THINGS THAT WILL GET YOU FIRED

1. Modifying `_RPI_PACE_TABLE` in `rpi_calculator.py`.
2. Starting to code when told to discuss.
3. Running `git add -A` instead of scoped commits.
4. Breaking production (real athletes use this daily).
5. Adding emoji, template narratives, or fluff to any output.
6. Proposing features that contradict the Product Strategy or Design Philosophy.
7. Ignoring test failures as "pre-existing." If `backend-test` is red on `main`, fix it; the job not running on `push` is not an excuse.
8. Committing files with hardcoded PII.
9. **Skipping a wiki update on a behavior-changing commit.** New as of this session — see `.cursor/rules/wiki-currency.mdc`.
10. Pushing to `origin` without explicit founder approval for that batch.

---

## DEPLOY COMMANDS

```bash
ssh root@187.124.67.153
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build

docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
"

docker logs strideiq_api --tail=50
docker logs strideiq_web --tail=50
```

If you change `Caddyfile`, restart the Caddy container — `caddy reload` alone does not pick up changes through the Docker bind-mount on this host.

---

## FOUNDER CONTEXT

Michael is technical enough to review code but not a developer. He cares deeply about coaching quality and visual quality — the product must produce intelligence that a real competitive runner trusts, and screens that don't look like every other running app. He has decades of running experience and strong opinions about training philosophy. He will challenge you. He will show you screenshots and ask if it's good enough. He dreams out loud — distinguish a vision he's testing on you ("3D is amazing if it's possible") from a decision he's locked in. He only locks in decisions with you, not with mockup agents or competitors.

Today the activity page went from a colored ribbon nobody understood to a real Mapbox 3D terrain hero with the route as a glowing path through it, three honest stacked charts, an unskippable feedback modal, and a share drawer that waits to be summoned. The morning briefing now correctly labels mile-repeat workouts as intervals instead of continuous effort. That is the quality bar. Everything you build should make moments like that more likely, more frequent, and more reliable.
