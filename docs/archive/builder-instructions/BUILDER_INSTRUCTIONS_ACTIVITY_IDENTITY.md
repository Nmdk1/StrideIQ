# Builder Instructions: Activity Identity Surface

**Date:** March 8, 2026
**Spec:** `docs/specs/ACTIVITY_IDENTITY_SURFACE_SPEC.md` (APPROVED)
**Priority:** High — closes the backend-to-frontend visibility gap

---

## Read Order (mandatory before writing any code)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/specs/ACTIVITY_IDENTITY_SURFACE_SPEC.md` — the full spec,
   every section. Do not skim.
3. This document

---

## What You're Building

Shape sentences exist in the API but are invisible to the athlete.
You are making them visible as the leading activity title across six
surfaces, adding athlete editability, and wiring the resolved title
into the Runtoon share flow.

**Display priority everywhere:**
```
athlete_title > shape_sentence > name
```

---

## Build Sequence

Do these in order. Each step should be testable independently.

### Step 1: Migration + Model

1. Create migration `activity_identity_001` chaining off
   `lfp_005_sentence`. Add `athlete_title` (Text, nullable) to the
   `activity` table.
2. Update `EXPECTED_HEADS` in
   `.github/scripts/ci_alembic_heads_check.py`.
3. Add the `athlete_title` column to the `Activity` model in
   `models.py`.

**Verify:** Migration applies cleanly. `alembic upgrade head` succeeds.
CI head check passes.

### Step 2: Shared resolver + API endpoint

1. Create `resolve_activity_title(activity) -> Optional[str]` as a
   shared helper. Location: a new function in a utils module or
   alongside the activity router — builder's call on placement, but it
   must be importable by all consumers.

   ```python
   def resolve_activity_title(activity) -> Optional[str]:
       return activity.athlete_title or activity.shape_sentence or activity.name
   ```

2. Create `PUT /v1/activities/{activity_id}/title` endpoint.
   - Schema: `ActivityTitleUpdate` with `@field_validator` that
     normalizes empty/whitespace to `null` and enforces 200-char max.
   - Auth: athlete must own the activity (403 otherwise).
   - Persist `athlete_title` on the Activity model.
   - Return 200 with the updated activity dict including
     `resolved_title`.

3. Update the activity **list** endpoint: add `resolved_title` to each
   `ActivityResponse` using `resolve_activity_title()`. The field
   `athlete_title` must also be on `ActivityResponse`.

4. Update the activity **detail** endpoint: add `athlete_title` and
   `resolved_title` to the response dict. The detail endpoint builds
   its response as a raw dict, NOT via `ActivityResponse` — update it
   independently. Include `shape_sentence` (already present — verify).

**Verify:** `GET /v1/activities` returns `resolved_title` on each
activity. `GET /v1/activities/{id}` returns `resolved_title`.
`PUT /v1/activities/{id}/title` sets and clears the title. 403 for
wrong athlete. 422 for >200 chars.

### Step 3: Home + Calendar + Runtoon API changes

1. **Home:** In `compute_last_run` (home.py), add `shape_sentence`,
   `athlete_title`, and `resolved_title` to the `LastRun` response
   dict. The Activity model is already loaded — read the columns and
   compute `resolved_title` via the shared helper.

2. **Calendar:** The calendar uses `ActivitySummary.model_validate(a)`
   with `from_attributes=True`. Add `shape_sentence`, `athlete_title`,
   and `resolved_title` to the `ActivitySummary` schema. **Critical:**
   `resolved_title` is NOT a model column — it will not auto-populate
   from ORM. You must either:
   - Build the dict manually and set `resolved_title` explicitly, OR
   - Use `model_validate(a)` then set `resolved_title` after via
     `summary.resolved_title = resolve_activity_title(a)`
     (Pydantic v2 allows this with `model_config` that permits
     assignment)
   
   Check all places in `calendar.py` where `ActivitySummary` is built
   (Codex found at least lines 785, 914, 1317).

3. **Runtoon:** In `runtoon_tasks.py`, add `shape_sentence` and
   `athlete_title` to the `act_snapshot` dict (around line 342-351).
   In `runtoon_service.py` `_format_activity_context` (line 204-205),
   replace `activity.name` with resolved title logic:
   ```python
   resolved = (
       getattr(activity, 'athlete_title', None)
       or getattr(activity, 'shape_sentence', None)
       or getattr(activity, 'name', None)
   )
   if resolved:
       lines.append(f"Activity name: {resolved}")
   ```

**Verify:** `GET /v1/home` returns `resolved_title` in `last_run`.
Calendar day data includes `resolved_title` in activity summaries.

### Step 4: Backend tests

Write tests covering:

1. `resolve_activity_title` priority chain (4 cases: athlete_title
   wins, shape_sentence wins, name wins, all null returns None)
2. `PUT /v1/activities/{id}/title` — set, clear (null), clear (empty
   string), wrong athlete (403), not found (404), >200 chars (422),
   whitespace-only normalized to null
3. Activity list response includes `resolved_title`
4. Activity detail response includes `resolved_title`
5. LastRun response includes `resolved_title`
6. Calendar ActivitySummary includes `resolved_title`
7. Runtoon context uses resolved title (mock/unit test on
   `_format_activity_context`)

**Verify:** All tests green. Run full test suite — no regressions.

### Step 5: Frontend types

1. Add to `Activity` interface in `lib/api/types.ts`:
   ```typescript
   shape_sentence?: string | null;
   athlete_title?: string | null;
   resolved_title?: string | null;
   ```

2. Add the same three fields to the inline `Activity` type in
   `activities/[id]/page.tsx` (lines 39-71). Or unify with the shared
   type — your call, but both must have the fields.

3. Add to `LastRun` type in `lib/api/services/home.ts`:
   ```typescript
   shape_sentence?: string | null;
   athlete_title?: string | null;
   resolved_title?: string | null;
   ```

### Step 6: Activity list (ActivityCard.tsx)

Replace `activity.name` with `activity.resolved_title ?? activity.name`
as the displayed title. The resolved title has **leading presence** —
the primary text element on the card.

No edit affordance on the list card.

### Step 7: Activity detail page — title + edit

1. Replace `activity.name` in the header with
   `activity.resolved_title ?? activity.name`.

2. Add edit affordance: pencil icon beside the title.
   - Desktop: pencil appears on hover.
   - Mobile: pencil always visible.
   - Tap title or icon → inline text input (pre-populated with
     current resolved title) + Save / Cancel buttons.
   - Follow the `WorkoutTypeSelector` inline edit pattern.

3. Save calls `PUT /v1/activities/{activity_id}/title`.
   Optimistic UI — title updates immediately.

4. Add "Reset to auto-detected" option visible when `athlete_title`
   is set AND `shape_sentence` exists. Clicking it sends
   `title: null` to clear the override.

5. On save/reset, invalidate:
   - `['activity', activityId]`
   - `['activities']`
   - `['home']`

### Step 8: Home last run hero (LastRunHero.tsx)

Replace `lastRun.name` with `lastRun.resolved_title ?? lastRun.name`.
Leading presence. No edit affordance — hero links to detail page.

### Step 9: Calendar day detail (DayDetailPanel.tsx)

Replace `activity.name || 'Run'` (line 376) with
`activity.resolved_title ?? activity.name ?? 'Run'`.

### Step 10: Compare page

1. In `compare/page.tsx` (line 142), replace
   `activity.name || 'Untitled Run'` with
   `activity.resolved_title ?? activity.name ?? 'Untitled Run'`.

2. In `ComparisonBasket.tsx` (lines 41-46), replace `activity.name`
   with `activity.resolved_title ?? activity.name`.

3. In `activities/page.tsx`, where activities are selected into
   `CompareContext`, store the resolved title:
   ```typescript
   name: activity.resolved_title ?? activity.name
   ```
   so basket chips don't regress to raw `name`.

---

## What NOT to do

- Do NOT build authorship detection (three-tier classification).
  That is gated in Parts 5-6 of the Shape Sentence Spec.
- Do NOT build Strava deferred-title fetch.
- Do NOT change shape sentence generation or classification logic.
- Do NOT add placeholders, skeletons, or "generating..." states for
  activities without shape sentences. The fallback is invisible.
- Do NOT use `git add -A`. Scoped commits only.

---

## Commit Strategy

Three scoped commits:

1. **Backend:** Migration + model + resolver + API endpoint + home +
   calendar + Runtoon changes + backend tests
2. **Frontend rendering:** Types + ActivityCard + detail page title
   display + home hero + calendar + compare
3. **Frontend editing:** Edit affordance on detail page + PUT call +
   invalidation + reset

If a commit gets large, split further. But keep backend and frontend
separate — backend can deploy and be verified independently.

---

## Evidence Required

After each commit, paste:
- `git diff --name-only --cached`
- Test output (relevant tests, not full suite)
- After final commit: full test suite output

After deploy:
- `GET /v1/activities` showing `resolved_title` for a real activity
- `GET /v1/home` showing `resolved_title` in `last_run`
- Screenshot or description of activity list with shape sentences
  as titles
