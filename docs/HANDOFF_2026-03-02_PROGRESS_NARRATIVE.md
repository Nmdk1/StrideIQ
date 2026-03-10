# Builder Handoff — Progress Page Narrative Redesign
**Written by:** Previous builder session  
**Date:** March 2, 2026  
**For:** Fresh builder session starting this task

---

## Read This First — In Order

Before any tool call:

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — non-negotiable, read every word
2. `docs/BUILDER_NOTE_2026-03-02_PROGRESS_NARRATIVE.md` — the assignment
3. `docs/specs/PROGRESS_NARRATIVE_SPEC_V1.md` — the full product spec

The assignment is GO. No scoping discussion needed.

---

## Who You Are Working With

**Michael Shaffer** — founder, sole developer, running this product in production.  
He has been through many builder sessions. He will not lose trust slowly. One hallucinated file, one invented claim presented as fact, one broken deploy — that's it.

**What earns trust:**
- Read before you touch. Every time. No exceptions.
- Show evidence, not claims. Paste test output. Paste logs. Screenshots.
- Scoped commits only. Never `git add -A`. Stage only the files this task changes.
- Say nothing if uncertain. Suppress over hallucinate.

**What revokes trust immediately:**
- Coding before scoping is confirmed (this task is pre-scoped — build it)
- Inventing file paths, function signatures, or behavior without reading first
- `git add -A` or bundling unrelated files in a commit
- Claiming tests pass without running them
- Generic narrative that could apply to any athlete (the spec explicitly rejects this)

---

## Production Environment

**Server:** `root@187.124.67.153` (Hostinger KVM 8)  
**Repo path on server:** `/opt/strideiq/repo`  
**Shell on dev machine:** PowerShell — use `;` not `&&` between commands

**Deploy command (run on server after git pull):**
```bash
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
```

**From PowerShell on dev machine, chain as:**
```powershell
git add <specific files>; git commit -m "message"; git push origin main
# Then SSH and deploy
ssh -o StrictHostKeyChecking=no root@187.124.67.153 "cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build 2>&1 | tail -15"
```

**Container names:**
| Service | Container |
|---------|-----------|
| API | `strideiq_api` |
| Web | `strideiq_web` |
| Worker | `strideiq_worker` |
| DB | `strideiq_postgres` |
| Cache | `strideiq_redis` |

**Generate auth token on server:**
```bash
docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
"
```

---

## Codebase Orientation

### API structure
```
apps/api/
  routers/progress.py         ← target file: add GET /v1/progress/narrative here
  models.py                   ← target file: add NarrativeFeedback model here
  alembic/versions/           ← target: new migration progress_narrative_001_*
  services/
    coach_tools.py            ← get_recovery_status, get_race_predictions,
                                 get_wellness_trends, get_weekly_volume
    training_load.py          ← TrainingLoadCalculator (CTL, ATL, TSB history)
    efficiency_analytics.py   ← get_efficiency_trends()
    recovery_metrics.py       ← calculate_consistency_index()
    correlation_persistence.py ← get_confirmed_correlations() — N=1 patterns
    ai_coach.py               ← LLM client setup — DO NOT TOUCH THIS FILE
  core/
    cache.py                  ← get_cache(key), set_cache(key, value, ttl=N)
    config.py                 ← settings (all env vars)
    database.py               ← get_db dependency, SessionLocal
```

### Frontend structure
```
apps/web/
  app/progress/page.tsx             ← target file: replace current card grid
  lib/hooks/queries/progress.ts     ← target file: add useProgressNarrative() hook
  components/progress/              ← target dir: new visual components (create fresh)
```

### What currently exists on the progress page
The current progress page (`apps/web/app/progress/page.tsx`) renders 12 text-based coach cards. It calls `GET /v1/progress/summary` and `GET /v1/progress/training-patterns`. **You are replacing this entire page.** The old endpoints stay in place (don't delete them — other code may reference them). You are adding `GET /v1/progress/narrative` as the new single endpoint and replacing the frontend to call it instead.

### The current progress router (`apps/api/routers/progress.py`)
Large file (~1000+ lines). It has:
- `GET /v1/progress/summary` — existing, keep it
- `GET /v1/progress/training-patterns` — existing, keep it
- Internal helpers for data assembly that overlap with what you need

**Read this file fully before adding your endpoint.** Several of the data assembly helpers you need are already written there. Reuse them, don't duplicate.

---

## LLM Setup — Critical

**Primary LLM:** Gemini 2.5 Flash — `GOOGLE_AI_API_KEY` env var  
**High-stakes LLM:** Anthropic Claude Opus — `ANTHROPIC_API_KEY` env var

For the progress narrative, **use Gemini 2.5 Flash**. It is the bulk/synthesis model. Look at how `services/ai_coach.py` initializes and calls `gemini_client.models.generate_content()` with model `"gemini-2.5-flash"` — follow the same pattern.

**Do NOT use the `AiCoach` class directly for the narrative endpoint.** It is a complex stateful class built for the coach chat surface. For the progress narrative, you want a clean, direct Gemini call. Build a slim `_generate_progress_narrative_llm()` helper in the router (or a small `services/progress_narrative_llm.py`) that:
1. Accepts the assembled visual data snapshot
2. Calls `gemini_client.models.generate_content()` directly
3. Returns narrative fields or raises (caught by fallback logic)

**LLM key pattern already in progress.py** — the file already imports anthropic at line 23-27 with a try/except guard. Use the same guard pattern for Gemini.

**Fallback is non-negotiable:** If `gemini_client` is None or the call raises, return deterministic fallback text from the spec's fallback table. The endpoint must never 500 due to LLM failure.

---

## Caching Pattern

The existing progress router already shows the exact pattern to use:

```python
from core.cache import get_cache, set_cache as _set_cache

cache_key = f"progress_narrative:{athlete_id}"
cached = get_cache(cache_key)
if cached is not None:
    return ProgressNarrativeResponse(**cached)

# ... build response ...

_set_cache(cache_key, response.model_dump(), ttl=1800)  # 30 min
```

Cache invalidation on new activity/checkin: look at how other routers call `invalidate_athlete_cache()` from `core.cache` — use the same pattern, or simply let TTL expire (30 min is acceptable for this surface).

---

## Data Services — What Exists and Where

All of these are already in the codebase. Read their signatures before calling them.

| Service call | Import path | What it returns |
|---|---|---|
| `TrainingLoadCalculator(db)` | `services.training_load` | Has `.get_ctl_history()` or similar — **read the file** |
| `get_efficiency_trends(db, athlete_id, days=90)` | `services.efficiency_analytics` | Time series of efficiency values |
| `get_confirmed_correlations(db, athlete_id)` | `services.correlation_persistence` | List of CorrelationFinding objects with times_confirmed |
| `get_weekly_volume(db, athlete_id, weeks=8)` | `services.coach_tools` | List of weekly mileage values |
| `get_wellness_trends(db, athlete_id, days=14)` | `services.coach_tools` | Sleep, HRV, RHR, stress time series |
| `get_recovery_status(db, athlete_id)` | `services.coach_tools` | Readiness composite, injury risk |
| `get_race_predictions(db, athlete_id)` | `services.coach_tools` | Race time estimates by distance |
| `calculate_consistency_index(db, str(athlete_id), days=90)` | `services.recovery_metrics` | Float 0-100 |

**Read each service file before calling it.** Return types, parameter names, and null behavior matter. Do not guess.

---

## Database / Models

**`apps/api/models.py`** is the single models file. Add `NarrativeFeedback` here. Look at how other recent models are structured (e.g., `GarminDay`, `DailyCheckin`) and follow the same pattern with `athlete_id` FK, timestamps, and `__tablename__`.

**Alembic migrations** live at `apps/api/alembic/versions/`. Run:
```bash
# On the server after deploy:
docker exec strideiq_api alembic upgrade head
```

Or from local (if DB tunnel is available). Name the migration file: `progress_narrative_001_add_narrative_feedback.py`. Follow the naming convention of other migration files in that directory.

---

## Frontend Component Approach

**No new npm packages** unless absolutely unavoidable. The codebase already uses:
- `recharts` — for charts (check `apps/web/package.json` to confirm)
- Standard SVG — for simple sparklines and rings

For the visual components in `apps/web/components/progress/`, create one file per component:
- `SparklineChart.tsx`
- `BarChart.tsx` (scoped name to avoid conflict with recharts)
- `HealthStrip.tsx`
- `FormGauge.tsx`
- `PairedSparkline.tsx`
- `CapabilityBars.tsx`
- `CompletionRing.tsx`
- `StatHighlight.tsx`

Keep each component **self-contained and stateless** — they receive data as props, they render, they're done. No internal data fetching.

**Units: miles only.** All distances to the user are in miles or `/mi`. No km anywhere on this page.

---

## TypeScript / API Hook

Add to `apps/web/lib/hooks/queries/progress.ts`. Look at existing hooks in that file for the pattern — they use `useQuery` from `@tanstack/react-query` with the authenticated fetch wrapper. Follow the same pattern for `useProgressNarrative()`.

The response type should mirror the JSON shape in the spec exactly. Define the full TypeScript interface.

---

## NarrativeFeedback Endpoint

You need a `POST /v1/progress/narrative/feedback` endpoint alongside the GET. It receives `{ athlete_id, feedback_type: "positive"|"negative"|"coach", feedback_detail?: string }` and writes to `NarrativeFeedback`. Keep it simple — no LLM, no cache, just write and return 200.

---

## Tests

Run tests from `apps/api/`:
```powershell
cd C:\Dev\StrideIQ\apps\api; python -m pytest tests/test_progress_narrative.py -v
```

The test file doesn't exist yet — you create it. Use the existing test patterns in `apps/api/tests/` for fixtures (`db`, mock athlete creation). The 12 required tests are in the builder note. All must pass, 0 failures, before you commit.

Local DB may not be running on the dev machine (tests that hit the DB will fail locally with connection error — that's pre-existing, not your fault). Run DB-dependent tests on the server if needed:
```bash
ssh root@187.124.67.153 "docker exec strideiq_api python -m pytest tests/test_progress_narrative.py -v 2>&1"
```

---

## What Will Bite You If You Don't Check First

1. **`apps/api/routers/progress.py` is long (~1000+ lines).** Read it. Services you need are already imported and partially called in the existing helper functions (`_build_progress_summary_data`, etc.). Do not re-import or duplicate.

2. **`TrainingLoadCalculator` method names** — read `services/training_load.py` to find the exact method that returns 8-week CTL history as a list. Do not guess the method name.

3. **`get_confirmed_correlations()` return shape** — read `services/correlation_persistence.py`. The `CorrelationFinding` object has specific field names. The `times_confirmed` field name and `confidence` field name must match what the object actually returns.

4. **Alembic import path** — `apps/api/alembic/env.py` uses `from models import Base`. New model in `models.py` is auto-included. But run `alembic revision --autogenerate -m "progress_narrative_001"` and inspect the generated file — don't write it by hand.

5. **`get_cache` returns `None` on miss** — the pattern is `if cached is not None`. Not `if cached`.

6. **PowerShell on dev machine** — no `&&`. Use `;` or separate commands. Multi-line Python in SSH requires a temp file (write to `tmp_*.py`, scp to server, exec, delete).

7. **Scoped commits** — one commit for backend (router + model + migration), one commit for frontend (components + page + hook). Do NOT bundle them. Do NOT `git add -A`.

8. **The "Not a dashboard" rejection test** — if a section looks like a data table or plain text box with numbers, it fails AC12. Every visual must catch the eye. Every narrative must teach. If you're not sure, re-read the spec's design principle section.

---

## Delivery Checklist (from builder note — all required)

Before posting your completion message, verify you have:

- [ ] Commit hash(es), scoped
- [ ] Files changed table (file + one-line purpose)
- [ ] Full `pytest` output verbatim (total passed, 0 failed)
- [ ] All 4 production smoke checks pasted
- [ ] Desktop + mobile screenshots of the page
- [ ] Fallback proof (LLM off → visuals + deterministic text still render)
- [ ] AC1–AC14 checklist with evidence per item
- [ ] `docs/SITE_AUDIT_LIVING.md` updated (delta entry + Progress page truth updated + last_updated date)

---

## If You Hit a Conflict With the Spec

Stop. Do not code around it. Post back: "Conflict found: [describe it]. Builder note says X, codebase shows Y. Waiting for instruction."

The founder reviews before accepting. A confident wrong turn that has to be unwound costs more than a pause.
