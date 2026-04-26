# Session Handoff — April 15, 2026

**For:** Incoming Opus 4.7 agent
**From:** Opus 4.6 agent (project reorg + test suite cleanup session)
**Production:** https://strideiq.run | Server: root@187.124.67.153

---

## MANDATORY READ ORDER

**Read ALL of 1-6 before proposing anything. If you can't reference specific content from these docs, you haven't read them.**

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — How to work. Non-negotiable.
2. `docs/PRODUCT_MANIFESTO.md` — The soul. What this product IS.
3. `docs/PRODUCT_STRATEGY_2026-03-03.md` — The moat. 10 priority-ranked product concepts.
4. `docs/specs/CORRELATION_ENGINE_ROADMAP.md` — 12-layer roadmap. Layers 1-4 built.
5. `docs/FINGERPRINT_VISIBILITY_ROADMAP.md` — How backend intelligence connects to product.
6. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — How every screen should feel. What's rejected.

**Context docs (read as needed):**
7. `docs/TRAINING_PLAN_REBUILD_PLAN.md` — Build priority order, open gates, enforced contracts.
8. `docs/SITE_AUDIT_LIVING.md` — Honest full-product inventory (updated today).
9. `docs/wiki/index.md` — Wiki entry point with quick reference for all systems.
10. `docs/wiki/log.md` — Chronological record of what shipped (updated today).

---

## WHAT THIS PRODUCT IS

StrideIQ is a running intelligence platform for competitive runners. It syncs data from Garmin (primary) and Strava, runs a correlation engine that discovers N=1 patterns in each athlete's data, and surfaces those findings through:

- **Morning briefing** — LLM-generated daily coaching briefing grounded in the athlete's actual data
- **AI coach** — Conversational coach (Kimi K2.5) with tool-calling access to the athlete's full history
- **Personal Operating Manual** — Auto-generated document of the athlete's discovered patterns
- **Fingerprint** — Browsable correlation findings with confidence, thresholds, and lifecycle states
- **Training plans** — V1 (production default) and V2 (admin-only sandbox) plan generators
- **Public tools** — Free calculators (training pace, age grading, race equivalency, BQ times, heat adjustment) that drive SEO

The founder (Michael Shaffer) is the primary user and a competitive runner. His father is also an active user. Both are primarily desktop users. The product has real athletes on it — never break production.

---

## CURRENT STATE

### Test Suite
- **3,584 passed, 0 failed**, 808 skipped, 102 xfailed, 69 xpassed
- CI: green on main
- Last full run: April 15, 2026

### Production
- Deployed and smoke-tested April 15, 2026
- All containers healthy: API, Web, Worker, Beat, Postgres, Redis, Caddy, MinIO
- Key endpoints verified: `/v1/home` (200), `/v1/analytics/efficiency-trends` (200), `/v1/fingerprint/browse` (200), `/` (200)

### Codebase Structure (post-reorg)
```
apps/api/
  models/              # Split from monolithic models.py (8 domain files)
  services/
    coaching/          # Split from ai_coach.py (7 mixins + core)
    coach_tools/       # Split from coach_tools.py (9 submodules)
    sync/              # Garmin adapter, Strava, dedup, timezone
    intelligence/      # Correlation engine, N1 insights, narratives
    plan_engine_v2/    # V2 plan generator (sandbox)
    plan_framework/    # Limiter engine, adaptive replanner
  routers/
  tasks/
  data/                # workout_registry.json (relocated)
apps/web/              # Next.js frontend
```

All old import paths work via backward-compatible shims. `from services.ai_coach import AICoach` still resolves. The shims use `importlib` re-exports at the old module paths.

### Key Architecture
- **LLM routing:** Every coach query → Kimi K2.5. Briefings → Claude. Fallback → Sonnet.
- **Correlation engine:** Layers 1-4 built. Discovers N=1 patterns per athlete. Confounder control (partial correlation). Lifecycle states (emerging → active → resolving → closed).
- **RPI Calculator:** `_RPI_PACE_TABLE` — 66-row hardcoded lookup derived from Daniels/Gilbert equations on April 10, 2026. **DO NOT MODIFY THIS TABLE OR REPLACE IT WITH A FORMULA.** It cost $100+ to get right. It is verified to +/- 1 second against the official reference calculator.
- **Plan Engine V2:** Accessible via `?engine=v2` query param (admin only). V1 remains default. See `docs/TRAINING_PLAN_REBUILD_PLAN.md` for rollout gates.

---

## WHAT WAS JUST COMPLETED (This Session)

### Project Reorganization
- `_AI_CONTEXT_/` deleted (146 files, 77,495 lines of stale chat dumps)
- `models.py` → `models/` package (8 files)
- 16 sync services → `services/sync/`
- 16 intelligence services → `services/intelligence/`
- `ai_coach.py` (5,690 lines) → `services/coaching/` (7 mixins)
- `coach_tools.py` (4,860 lines) → `services/coach_tools/` (9 submodules)
- `workout_registry.json` → `data/` directory

### 65 Test Failures Root-Caused and Fixed
All fixes were root-cause, not patches. 10 categories:
1. UUID validation — tests passed invalid strings to code that now validates
2. Mock configuration — missing attributes, exhausted side_effects
3. Tuple unpacking — `_build_briefing_prompt` 7-tuple, mocks had 6
4. Phase 3B/3C logic — wrong LLM patch targets, obvious-metric filtering
5. RPI calibration — test expectations drifted from authoritative table
6. Assertion drift — tests checked implementation details not behavior
7. Mock blocking — singleton leaks, wrong patch targets
8. Garmin source contract — raw field names leaking past adapter
9. Logic bugs — duplicate scanner, fitness bank thresholds
10. Budget cap — patching env var vs module-level constant

### Production Code Improvements
- `duplicate_scanner.py` — distance check added to duration-based fallback
- `garmin_adapter.py` — `adapt_activity_file_record()` for source contract
- `n1_insight_generator.py` — `daily_caffeine_mg` added to FRIENDLY_NAMES
- `training-pace-tables.json` + PSEO pages — regenerated from RPI calculator
- `extract_athlete_profiles.py` — hardcoded email replaced with env var

---

## WHAT'S NEXT (Founder's Priority Order)

Consult `docs/TRAINING_PLAN_REBUILD_PLAN.md` for the canonical priority list:

1. **Monetization tier mapping** — Revenue unlock. Stripe integration exists but tier gating incomplete.
2. **Plan Engine V2 quality** — The founder has been reviewing generated plans. See `apps/api/services/plan_engine_v2/evaluation/` for test matrices and sample plans.
3. **Phase 3B graduation** — Narration quality gate: accuracy > 90% for 4 weeks.
4. **Phase 3C graduation** — Per-athlete synced history + significant correlations.

**DO NOT** start building without the founder's explicit direction. Ask what they want to work on.

---

## THINGS THAT WILL GET YOU FIRED

1. Modifying `_RPI_PACE_TABLE` in `rpi_calculator.py`
2. Starting to code when told to discuss
3. Running `git add -A` instead of scoped commits
4. Breaking production (real athletes use this daily)
5. Adding emoji, template narratives, or fluff to any output
6. Proposing features that contradict the Product Strategy or Design Philosophy
7. Ignoring test failures as "pre-existing"
8. Committing files with hardcoded PII

---

## DEPLOY COMMANDS

```bash
# SSH to server, pull, rebuild
ssh root@187.124.67.153
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build

# Generate auth token
docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
"

# Logs
docker logs strideiq_api --tail=50
docker logs strideiq_web --tail=50
```

---

## FOUNDER CONTEXT

Michael is technical enough to review code but not a developer. He cares deeply about coaching quality — the product must produce intelligence that a real competitive runner trusts. He has decades of running experience and strong opinions about training philosophy. He will challenge you. He will show you screenshots of what the product produces and ask if it's good enough. The bar is: *would a $200/month human coach say something this specific and accurate?*

The morning briefing produced today compared two half marathon results 364 days apart (Nov 2024 vs Nov 2025), attributed a 7-minute improvement to training density patterns, and connected it to the current week's plan. That is the quality bar. Everything you build should make moments like that more likely, more frequent, and more reliable.
