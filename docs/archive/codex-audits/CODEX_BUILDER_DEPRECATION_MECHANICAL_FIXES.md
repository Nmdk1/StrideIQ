# Codex Builder Brief: Mechanical Deprecation Fixes (No Lifespan)

**Date:** March 8, 2026  
**Priority:** Background cleanup (safe to run in parallel)  
**Scope:** Mechanical, low-judgment refactors only

---

## Goal

Remove the three mechanical deprecation classes identified in CI:

1. Pydantic class-based `Config` deprecations
2. Deprecated `from database import ...` import path usage
3. HTTPX test warnings for raw-body upload via `data=...`

**Do not touch FastAPI lifespan migration (`@app.on_event`) in this session.**

---

## In Scope

### 1) Pydantic `class Config` -> `model_config = ConfigDict(...)`

Current warning:
- `PydanticDeprecatedSince20: Support for class-based config is deprecated ... removed in V3.0`

Known files:
- `apps/api/routers/plan_generation.py`
- `apps/api/routers/activity_reflection.py`
- `apps/api/routers/runtoon.py`
- `apps/api/core/bmi_config.py`

Task:
- Replace class-based `Config` usage with Pydantic v2 style.
- Preserve behavior exactly (especially `from_attributes=True` or equivalent flags).

---

### 2) Deprecated DB import path cleanup

Current warning:
- `DeprecationWarning: Importing from 'database' is deprecated. Use 'core.database' instead.`

Runtime warning origin seen in CI:
- `apps/api/routers/progress.py`

Repo-wide occurrences include router, main, scripts, and tests (mechanical import path updates).

Task:
- Replace `from database import ...` with `from core.database import ...` where applicable.
- Keep import symbol names and behavior unchanged.
- Treat scripts/tests as in scope unless a file is intentionally legacy-only and not imported in runtime paths.

---

### 3) HTTPX raw-body upload deprecation in tests

Current warning:
- `DeprecationWarning: Use 'content=<...>' to upload raw bytes/text content.`

Known files:
- `apps/api/tests/test_phase6_stripe_billing.py`
- `apps/api/tests/test_phase9_backend_smoke_golden_paths.py`

Task:
- Replace `client.post(..., data=<bytes_or_text>, ...)` with `client.post(..., content=<bytes_or_text>, ...)` for raw payload cases.
- Keep request semantics/signature validation behavior unchanged.

---

## Explicitly Out of Scope

- FastAPI lifespan migration in `apps/api/main.py`
- Any change to startup/shutdown ordering
- Feature behavior changes unrelated to deprecation cleanup

Reason: startup order is load-bearing and requires a dedicated verification session.

---

## Constraints

- Mechanical edits only; no architectural changes.
- No unrelated refactors.
- No scope expansion into other warning classes unless directly required for these replacements.
- Keep diffs small and reviewable by category.

---

## Verification / Evidence Required

1. **Targeted tests** for touched API test files still pass.
2. **CI run evidence** from the branch showing:
   - Pydantic class-config warning removed
   - DB import-path deprecation warning removed
   - HTTPX `data=` raw-content deprecation warning removed
3. **No regression claim without logs**:
   - include warning excerpts before/after from CI log sections.

---

## Deliverable

Return:

1. Files changed, grouped by:
   - Pydantic config
   - DB imports
   - HTTPX tests
2. CI evidence snippets for warning removal
3. Explicit statement that `@app.on_event` / lifespan migration was not touched

