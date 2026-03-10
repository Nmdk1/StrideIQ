# Activity Identity — Surface Spec

**Date:** March 8, 2026
**Status:** SHIPPED — Founder + top advisor + Codex reviewed. Builder reviewed, adjusted, and deployed. CI green.
**Depends on:** Shape sentences deployed (63% coverage, zero known false positives)
**Related:** `docs/specs/SHAPE_SENTENCE_SPEC.md` Parts 5-6 (gated Activity Identity Model)

---

## The Problem

The system generates natural-language descriptions of workout structure
for 63% of streamable activities with zero known false positives. These
sentences exist in the database and API response but are invisible to the
athlete on every surface.

Every activity displays its Strava/Garmin title — "Morning Run,"
"Lauderdale County Running" — regardless of what the system knows. The
activity list shows a week of identically-named runs. The system already
knows each one is different and doesn't say it.

---

## The Change

The shape sentence becomes the activity's displayed title. The athlete
can edit it in StrideIQ. Their edit becomes permanent. The resolved title
flows everywhere the activity name appears — list, detail, home,
calendar, compare, and share.

---

## Relationship to Parts 5-6 of the Shape Sentence Spec

The gated Activity Identity Model in Parts 5-6 specifies a full
three-tier authorship detection system (auto-generated, athlete-authored,
ambiguous) with Strava deferred-title fetch and subtitle rendering.

This spec originally solved the authorship problem through
**editability alone** — the system leads with the shape sentence,
the athlete corrects it. Detection was scoped out.

**Builder adjustment (shipped):** During implementation, the builder
identified that the simple priority chain (`athlete_title >
shape_sentence > name`) would silently override custom Strava/Garmin
titles on day one, before any athlete had edited. This required a
lightweight authorship detection layer:

- `_is_auto_generated_name()` detects Strava auto-names ("Morning Run",
  "Afternoon Run", etc.) and Garmin location patterns ("{City} Running")
- Race guard: `user_verified_race` or `is_race_candidate` → athlete's
  original name always wins
- Authored guard: any non-auto-generated name → athlete's voice leads,
  shape sentence becomes metadata only

This is not the full Identity Model from Parts 5-6. It is the minimum
viable detection needed to prevent the system from overriding athlete
voice. The editability mechanism and the full display priority chain
remain as specified. 34 tests verify correct resolution across all
athletes.

---

## Display Priority

Everywhere StrideIQ displays an activity title, this priority applies:

```
1. athlete_title        — the athlete edited it in StrideIQ → always wins
2. name (if race)       — user_verified_race or is_race_candidate → race title is sacred
3. name (if authored)   — custom Strava/Garmin titles → athlete's voice preserved
4. shape_sentence       — the system's structural understanding (auto-titled activities only)
5. name (if auto)       — original auto-generated title (final fallback)
```

The `resolve_activity_title()` helper applies this logic. It checks
whether the original name is auto-generated before allowing
`shape_sentence` to lead. This prevents the system from silently
overriding athlete-authored titles. Computed at read time, not stored.

**The 37% fallback is intentional.** Shape sentences currently cover
63% of streamable activities. The remaining 37% will display their
original Strava/Garmin title — "Morning Run," "Lauderdale County
Running." This is correct behavior, not a gap to fix. The fallback is
invisible: no placeholder, no "generating..." state, no hint the system
tried. Activities without sentences look exactly as they do today.
Activities with sentences are immediately better. As sentence coverage
grows, more activities gain real titles automatically — no migration,
no backfill, no athlete action required.

---

## Data Model

### New column

```
Activity.athlete_title  —  Text, nullable, default null
```

Migration required. No backfill — all existing activities start with
`athlete_title = null`.

### Existing columns (unchanged)

```
Activity.name            —  original Strava/Garmin title (preserved for sync)
Activity.shape_sentence  —  system-generated (regenerated without clobbering athlete_title)
```

### Resolved title (computed, not stored)

A shared helper function computes the resolved title. Every endpoint
and service that needs the display title calls this function — the
priority logic lives in one place, not reimplemented per-endpoint.

```python
def resolve_activity_title(activity) -> Optional[str]:
    """Single source of truth for activity display title.

    Priority: athlete_title > race name > authored name > shape_sentence > auto name.
    Used by activity list, detail, home, calendar, Runtoon, and compare.
    """
    if getattr(activity, 'athlete_title', None):
        return activity.athlete_title

    name = getattr(activity, 'name', None)
    sentence = getattr(activity, 'shape_sentence', None)
    provider = getattr(activity, 'provider', None) or ''
    is_race = (
        getattr(activity, 'user_verified_race', False)
        or getattr(activity, 'is_race_candidate', False)
    )

    if is_race and name:
        return name
    if name and not _is_auto_generated_name(name, provider):
        return name
    return sentence or name
```

This function is called explicitly when building response dicts.
It is NOT a model property or ORM-derived field — endpoints must
call it and include the result in their response.

If `resolve_activity_title(activity)` returns null (all three inputs null),
the endpoint applies its existing hard fallback (`"Run"` / `"Untitled Run"`)
at render-mapping time.

---

## API Changes

### 1. New endpoint: Update athlete title

```
PUT /v1/activities/{activity_id}/title

Request body:
{
    "title": "Father son, state age records 10 mile!"
}

Response: 200 with updated activity
```

Setting `title` to `null` or empty string clears the athlete title and
resets display to the system sentence (or original name). The endpoint
normalizes empty string to `null` before storing — the database should
only contain `null` or a real title, never `""`.

Auth: athlete must own the activity. Standard JWT auth.

Schema:

```python
class ActivityTitleUpdate(BaseModel):
    title: Optional[str] = None

    @field_validator('title')
    @classmethod
    def normalize_empty(cls, v):
        if v is not None and v.strip() == '':
            return None
        if v and len(v) > 200:
            raise ValueError('Title must be 200 characters or fewer')
        return v.strip() if v else v
```

**Max length: 200 characters.** Prevents UI overflow and unbounded
payloads in downstream contexts (Runtoon prompts, coach context).
Strava/Garmin titles are typically under 100 characters. 200 gives
the athlete room to write something personal without allowing abuse.

### 2. Add resolved_title to activity responses

Both list and detail endpoints add a computed `resolved_title` field:

```json
{
    "id": "...",
    "name": "Lauderdale County Running",
    "shape_sentence": "7 miles easy with 4 strides",
    "athlete_title": null,
    "resolved_title": "7 miles easy with 4 strides",
    ...
}
```

The `resolved_title` field applies the priority logic server-side so
the frontend doesn't need to reimplement it. The individual fields
(`name`, `shape_sentence`, `athlete_title`) are still returned for
transparency.

Add `athlete_title` and `resolved_title` to `ActivityResponse` schema.

**Note:** The list endpoint uses `ActivityResponse` (Pydantic schema).
The detail endpoint returns a separate `dict` built manually — it does
NOT use `ActivityResponse`. Both must be updated independently. The
detail endpoint must include `athlete_title`, `shape_sentence`, and
`resolved_title` (computed via `resolve_activity_title`) in its
response dict.

### 3. Add shape_sentence and resolved_title to LastRun

In `compute_last_run` (home.py), add `shape_sentence`, `athlete_title`,
and `resolved_title` to the `LastRun` response.

The activity model is already loaded in `compute_last_run` — these are
existing columns, just not selected into the response dict.

### 4. Add resolved_title to calendar ActivitySummary

The calendar API returns `ActivitySummary` with a `name` field. Add
`shape_sentence`, `athlete_title`, and `resolved_title` to the schema.

**Important:** The current calendar path uses
`ActivitySummary.model_validate(a)` with `from_attributes=True` to
build the response directly from the ORM object. This works for
`shape_sentence` and `athlete_title` (they are model columns) but
NOT for `resolved_title` (it is computed, not a column). The calendar
endpoint must explicitly compute `resolved_title` using
`resolve_activity_title(a)` and set it on the response dict before
validation, or switch from `model_validate(a)` to building the dict
manually. Same pattern as the activity list endpoint.

### 5. Add resolved_title to Runtoon context

In `runtoon_tasks.py`, add `shape_sentence` and `athlete_title` to the
`act_snapshot` dict:

```python
act_snapshot = {
    ...
    "name": getattr(activity, 'name', None),
    "shape_sentence": getattr(activity, 'shape_sentence', None),
    "athlete_title": getattr(activity, 'athlete_title', None),
}
```

In `runtoon_service.py` `_format_activity_context`, replace
`activity.name` with the resolved title via the shared helper:

```python
from routers.activities import resolve_activity_title
resolved = resolve_activity_title(activity)
if resolved:
    lines.append(f"Activity name: {resolved}")
```

---

## Frontend Changes

### 1. Types

Add to `Activity` interface in `lib/api/types.ts`:

```typescript
shape_sentence?: string | null;
athlete_title?: string | null;
resolved_title?: string | null;
```

Add to inline `Activity` type in `activities/[id]/page.tsx` (or unify
with shared type).

Add to `LastRun` type in `lib/api/services/home.ts`:

```typescript
shape_sentence?: string | null;
athlete_title?: string | null;
resolved_title?: string | null;
```

### 2. Activity list (ActivityCard.tsx)

Replace `activity.name` with `activity.resolved_title ?? activity.name`
as the displayed title.

The resolved title should have **leading presence** — it is the primary
text element on the card. Same weight or stronger than the current name
rendering.

No edit affordance on the list card. Editing happens on the detail page.

### 3. Activity detail page header

Replace the title in the header (currently `activity.name`) with
`resolved_title`.

**Edit affordance:** The title displays with a small pencil icon
beside it — visible but not dominant. Tapping the title or the icon
enters edit mode. Pattern follows the existing `WorkoutTypeSelector`
inline edit: tap → text input appears → Save / Cancel. Pre-populated
with the current resolved title.

On desktop, the pencil icon appears on hover. On mobile, the icon is
always visible (no hover state). The edit affordance must be
discoverable — a title that looks like static text but is secretly
editable is invisible UX.

When the athlete saves:
- `PUT /v1/activities/{activity_id}/title` with the new text
- Invalidate activity queries
- Title updates immediately (optimistic UI)

When the athlete wants to reset to the system sentence:
- Clear the text input and save (sends `title: null`)
- Display reverts to shape_sentence or name
- A small "Reset to auto-detected" option below the input when
  `athlete_title` is set and `shape_sentence` exists

### 4. Home last run hero (LastRunHero.tsx)

Replace `lastRun.name` with `lastRun.resolved_title ?? lastRun.name`
as the displayed title. Leading presence.

No edit affordance on the home page. The hero links to the detail page
where editing happens.

### 5. Calendar day detail panel (DayDetailPanel.tsx)

The calendar sidebar shows `activity.name || 'Run'` when a day is
clicked (line 376 of `DayDetailPanel.tsx`). Replace with resolved title.

### 6. Compare page (compare/page.tsx, ComparisonBasket.tsx)

The compare page renders `activity.name || 'Untitled Run'` (line 142
of `compare/page.tsx`) and `activity.name` in `ComparisonBasket.tsx`
(lines 41-46). Replace both with resolved title.

There is no separate compare-list endpoint for these cards today. The
compare page reads activities through the existing activities list flow
(`useActivities` -> `/v1/activities`). Ensure that flow returns
`athlete_title`, `shape_sentence`, and `resolved_title`.

Also update compare selection state wiring so the basket chips reflect
resolved titles:

- `activities/page.tsx` currently stores `name: activity.name` when
  toggling selection into `CompareContext`
- `CompareContext` stores that as `SelectedActivity.name`
- `ComparisonBasket.tsx` renders `activity.name`

Store the resolved display title in selection state
(`activity.resolved_title ?? activity.name`) so compare basket and
compare page stay consistent.

### 7. Query invalidation

After a title edit on the detail page, invalidate:
- `['activity', activityId]` — the detail view
- `['activities']` — the list view (title change should reflect)
- `['home']` — if this is the most recent activity, the hero updates

---

## Fallback Behavior

| State | What displays | Athlete sees |
|-------|--------------|--------------|
| athlete_title set | athlete_title | Their own words |
| name is athlete-authored (race, custom title) | name | Their original title preserved |
| shape_sentence exists, auto-generated name | shape_sentence | "7 miles easy with 4 strides" |
| no shape_sentence, auto-generated name | name | "Morning Run" (unchanged from today) |
| everything null | hard fallback | "Run" / "Untitled Run" |

No skeleton states. No "generating..." placeholders. No loading
indicators for the title. If the sentence doesn't exist, the original
name shows as it does today.

---

## Editing Contract

1. The athlete can edit the title of any of their activities at any time
2. The edit is persisted as `athlete_title` on the Activity model
3. The edit does NOT sync back to Strava or Garmin
4. The system can regenerate `shape_sentence` without overwriting
   `athlete_title` — the athlete's edit is never clobbered
5. Clearing the edit (setting to null/empty) resets to the system
   sentence or original name
6. Edit history is not preserved — last write wins
7. Max length: 200 characters

## Sentence Regeneration Stability

If the athlete has NOT edited (`athlete_title` is null) and
`shape_sentence` is regenerated with a different value (e.g., after
a coverage fix or shape extraction improvement), the displayed title
changes silently. **This is intentional.** The system is getting
smarter — the new sentence is more accurate than the old one. The
athlete didn't author the previous sentence, so updating it is not
overriding their voice.

If the athlete HAS edited (`athlete_title` is set), regeneration of
`shape_sentence` has no visible effect — `athlete_title` takes
priority. The system's updated understanding is preserved as metadata
but does not change what the athlete sees.

---

## Runtoon Integration

The resolved title flows into Runtoon generation context. When the
athlete taps "Share Your Run," the Runtoon prompt receives the best
available title:

- If the athlete titled it "Father son, state age records 10 mile!" →
  the Runtoon knows this was a celebration run
- If the system titled it "7 miles easy with 4 strides" → the Runtoon
  knows the workout structure
- If neither exists → the Runtoon gets "Morning Run" (as today)

The resolved title appears in the image prompt context (currently
`activity.name` at line 204-205 of `runtoon_service.py`). The caption
prompt does not currently use the activity name — no change needed
there unless desired.

---

## Migration

Single migration adding one column:

```python
"""add athlete_title to activity

Revision ID: activity_identity_001
"""

def upgrade():
    op.add_column('activity', sa.Column('athlete_title', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('activity', 'athlete_title')
```

Chain off current migration head (`lfp_005_sentence`). Update
`EXPECTED_HEADS` in `.github/scripts/ci_alembic_heads_check.py`.

---

## Testing

### Backend

1. **resolved_title logic** — unit tests for priority chain:
   - athlete_title set → returns athlete_title
   - athlete_title null, authored name → returns name (athlete voice)
   - athlete_title null, auto-generated name, shape_sentence set → returns shape_sentence
   - athlete_title null, auto-generated name, no shape_sentence → returns name
   - race activity → name always wins (race guard)
   - empty string athlete_title treated as null (cleared)
   - 34 tests shipped covering auto-detection, race priority, authored
     priority, and Runtoon integration

2. **PUT /v1/activities/{id}/title** — integration tests:
   - Set title → 200, athlete_title persisted
   - Clear title (null) → 200, athlete_title set to null
   - Wrong athlete → 403
   - Non-existent activity → 404

3. **Activity list response** — verify resolved_title present and correct

4. **LastRun response** — verify resolved_title present and correct

5. **Runtoon context** — verify resolved title flows into activity
   context (not raw name)

6. **Calendar ActivitySummary** — verify resolved_title present in
   calendar endpoint response

7. **Title max length** — verify 201-char title rejected, 200-char
   accepted, whitespace-only normalized to null

### Frontend

8. **ActivityCard** — renders resolved_title when present, falls back
   to name

9. **Detail page** — renders resolved_title, edit affordance works,
   save persists, cancel reverts, reset clears athlete_title

10. **Home hero** — renders resolved_title

11. **Calendar day detail** — renders resolved_title in sidebar

12. **Compare page** — renders resolved_title in comparison view
    and basket

13. **Compare selection state** — selecting from activity list stores
    resolved title (not raw `name`) in `CompareContext`, and basket chips
    render the same resolved title

---

## What This Enables

- **Activity list becomes a self-writing training log.** A week of runs
  reads as a coherent training narrative, not seven "Morning Run" entries.

- **Athlete voice enters the product.** Every edit is content that lives
  in StrideIQ and nowhere else. Over six months, the athlete has a
  personally-titled training log. Switching cost that compounds.

- **Foundation for the full Identity Model.** If authorship detection
  ships later, it determines which activities get the system sentence
  by default vs which preserve the athlete's Strava/Garmin title. The
  `athlete_title` field is ready for that — non-null means "the athlete
  spoke in StrideIQ." The priority chain doesn't change.

- **Runtoon shares carry real identity.** The share artifact references
  the run by its actual structure or the athlete's own description,
  not a generic platform title.

---

## Not In Scope

- Full three-tier authorship detection from Parts 5-6 (lightweight
  auto-generated name detection shipped as a builder adjustment —
  see "Relationship to Parts 5-6" above)
- Strava deferred-title fetch (async check for custom Strava titles)
- Heat adjustment display
- Training Story frontend surface
- RunShape canvas enhancements
- Gray Zone Intelligence (Part 6 of Shape Sentence Spec)
- Changes to shape sentence generation, classification, or coverage
