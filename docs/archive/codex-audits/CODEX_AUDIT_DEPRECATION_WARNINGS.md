# Codex Audit Brief: Deprecation Warning Catalog

**Date:** March 8, 2026
**From:** Top advisor (Opus, Cursor)
**To:** Tech advisor (Codex)
**Priority:** Non-blocking — catalog only, no fixes

---

## What You're Doing

Catalog every deprecation warning emitted during a CI test run. Group
by severity. Prioritize by upgrade risk. This is an audit, not a fix
session.

---

## Known Warnings (Founder Has Seen These)

1. **`datetime.utcfromtimestamp()` deprecated** — Python 3.12+ flags
   this, removed in 3.14. `dateutil` triggers it, but we likely have
   our own calls too.

2. **Pydantic class-based `Config` deprecated** — using `class Config:`
   instead of `model_config = ConfigDict(...)`. Pydantic v2 tolerates
   it, v3 removes it.

3. **`from database import` deprecated path** — at least
   `routers/progress.py` uses the old import path instead of
   `core.database`.

4. **`@app.on_event("startup")` deprecated** — FastAPI wants `lifespan`
   event handlers instead.

---

## What to Produce

### 1. Full warning list

Run the test suite with warnings visible. Capture every unique
deprecation warning. For each one:

- Warning text (exact)
- Source (our code vs third-party dependency)
- File(s) where it originates
- How many times it fires

### 2. Severity grouping

| Severity | Meaning |
|----------|---------|
| **Will break** | Removed in the next major version of the dependency we're likely to upgrade to (Python 3.14, Pydantic v3, FastAPI 1.0). Fix before upgrading. |
| **Should fix** | Deprecated but not immediately dangerous. Fix when convenient to keep the codebase clean. |
| **Cosmetic / third-party** | Emitted by a dependency we don't control. No action unless we pin or fork. |

### 3. Fix complexity estimate

For each "will break" and "should fix" item, estimate:
- How many files are affected
- Whether it's a mechanical find-and-replace or requires logic changes
- Any risks (e.g., changing datetime handling could affect timezone logic)

---

## What NOT to Do

- Do not fix anything. Catalog only.
- Do not open PRs or create commits.
- Do not prioritize this above the Activity Identity build — it's
  background work.

---

## Deliverable

A structured list the founder can review and decide when to schedule
fixes. Return to the founder, who routes to the top advisor for
prioritization.
