# Codex Review Brief: Activity Identity Surface Spec

**Date:** March 8, 2026
**From:** Top advisor (Opus, Cursor)
**To:** Tech advisor (Codex)
**Role:** Review only — do not build

---

## What You're Reviewing

`docs/specs/ACTIVITY_IDENTITY_SURFACE_SPEC.md`

A spec to surface shape sentences as leading activity titles across
five frontend surfaces (activity list, activity detail, home hero,
calendar sidebar, Runtoon share context), with athlete editability
in StrideIQ.

---

## Context

Shape sentences are deployed and running. 63% coverage across three
athletes, zero known false positives. The sentences exist in the API
response (`shape_sentence` on `ActivityResponse`) but are not rendered
anywhere in the frontend. The athlete sees "Morning Run" when the
system knows it was "7 miles easy with 4 strides."

This spec makes the sentence the displayed title, adds an
`athlete_title` column so the athlete can edit it in StrideIQ, and
defines the display priority: `athlete_title > shape_sentence > name`.

---

## What to Verify

### Data model
1. Is a single nullable `athlete_title` Text column sufficient, or are
   there edge cases that need additional fields?
2. The `resolved_title` is computed at read time (`athlete_title or
   shape_sentence or name`). In Python, `""` is falsy — the spec
   normalizes empty strings to `null` in the validator. Confirm this
   is clean and there are no other falsy edge cases.
3. Migration chains off `lfp_004_layer`. Confirm that is still the
   current head.

### API
4. The spec adds a `PUT /v1/activities/{activity_id}/title` endpoint.
   Review against the existing activity update pattern — there is no
   generic PATCH on activities; updates go through dedicated endpoints
   (`/workout-type`, `/reflection`, etc.). Is PUT correct, or should
   this follow a different verb/pattern for consistency?
5. `resolved_title` is added to `ActivityResponse`, `LastRun`, and
   `ActivitySummary` (calendar). Verify that adding these fields to
   the schemas won't break existing frontend consumers that may not
   expect them.
6. The Runtoon snapshot in `runtoon_tasks.py` (line 342-351) builds
   an `act_snapshot` dict. The spec adds `shape_sentence` and
   `athlete_title` to it. Verify the `_ActivityProxy` pattern handles
   these correctly via `setattr`.

### Frontend
7. The activity detail page has an inline `Activity` type (lines 39-71
   of `activities/[id]/page.tsx`) that does not match
   `lib/api/types.ts`. The spec says "add to both or unify." What's
   the right call — unify now or patch both?
8. The spec says `resolved_title` is returned server-side so the
   frontend doesn't reimplement priority logic. But the frontend uses
   `activity.resolved_title ?? activity.name` as a safety fallback.
   Is that defensive enough, or should there be a shared utility?

### Surfaces
9. Verify that the five surfaces identified (activity list, detail,
   home hero, calendar sidebar, Runtoon) are exhaustive. Are there
   other places in the codebase that render `activity.name`?
10. The calendar `ActivitySummary` is built with
    `ActivitySummary.model_validate(a)` with `from_attributes=True`.
    Confirm that adding `shape_sentence`, `athlete_title`, and
    `resolved_title` to the schema works with this pattern — the first
    two are model columns, but `resolved_title` is computed, not a
    column. How should the calendar endpoint compute it?

### Edge cases
11. What happens if `shape_sentence` is regenerated (e.g., shape
    extraction reruns after a coverage fix) and the new sentence is
    different? The athlete hasn't edited — their title silently changes.
    Is that acceptable, or should there be a stability mechanism?
12. The spec says the endpoint normalizes whitespace-only input to
    `null`. Should there be a max length on `athlete_title`?

---

## What NOT to Do

- Do not write code or create builder instructions
- Do not propose alternative architectures unless you find a concrete
  problem with the current spec
- Do not expand scope (authorship detection, Strava deferred fetch,
  heat adjustment — all explicitly out of scope)
- Focus on: correctness, completeness, edge cases, implementation
  feasibility

---

## Deliverable

A list of findings categorized as:
- **Must fix** — spec is wrong or will cause a bug
- **Should address** — gap that will cause confusion or rework
- **Nice to have** — improvement that isn't blocking

Return findings to the founder. The founder routes to the top advisor.
We refine, then create builder instructions.
