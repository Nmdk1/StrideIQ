# Builder Note: Route Cleanup & Page Merges

**Date:** April 4, 2026
**Assigned to:** Builder
**Advisor sign-off required:** Yes (advisor session active)
**Urgency:** Medium — first task, trust-building

---

## Before Your First Tool Call

Read in order:
1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/AGENT_WORKFLOW.md`
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` (Part 4: What We Decided NOT To Do)
4. `docs/SITE_AUDIT_LIVING.md` (Section 6: Frontend Architecture → Key Pages)
5. This builder note

---

## Objective

Remove dead routes, merge orphaned pages into their natural homes, and
reduce navigation clutter — without changing any product behavior for
athletes or removing anything the founder uses.

---

## Scope

### Part 1: Delete Dead Routes (4 routes)

These are redirects or dev artifacts. Delete the page directories entirely.

| Route | What it is | Action |
|-------|-----------|--------|
| `/dashboard` | Redirect to `/discover` or `/home` | Delete `app/dashboard/` |
| `/home-preview` | Static dev layout preview (comment says "delete after approval") | Delete `app/home-preview/` |
| `/spike/rsi-rendering` | ADR-064 rendering spike (Recharts vs canvas benchmarks) | Delete `app/spike/` |
| `/diagnostic` | Redirect chain: → `/admin/diagnostics` or → `/insights` → `/manual` | Delete `app/diagnostic/` |

**For `/dashboard`:** Check if `/onboarding` pushes to `/dashboard` on
completion. If so, update it to push to `/home` directly. Search the
entire codebase for any remaining references to these routes.

### Part 2: Merge `/profile` into `/settings` (1 route)

`/profile` is name, email, and basic fields. `/settings` is integrations,
billing, preferences. Athletes shouldn't guess which page has their email.

1. Move profile fields (name, email, basic athlete info) into a section
   at the top of the Settings page.
2. Add a redirect from `/profile` → `/settings` (same pattern as the
   existing `/checkin` → `/home` redirect).
3. Remove `/profile` from any navigation references.
4. Update any links to `/profile` across the codebase to point to
   `/settings`.

### Part 3: Merge `/availability` into `/plans/create` (1 route)

The availability grid only matters during plan creation. Nobody visits
it standalone.

1. Integrate the `AvailabilityGrid` component into the plan creation
   wizard as a step.
2. Add a redirect from `/availability` → `/plans/create`.
3. Remove any standalone nav references to `/availability`.

### Part 4: Absorb `/trends` into `/analytics` (1 route)

`/trends` is a parallel efficiency/volume trends page using different
API endpoints than `/analytics`. Both answer "am I getting fitter?"

1. Identify what `/trends` shows that `/analytics` doesn't.
2. Add the unique trend visualizations to `/analytics` as a section
   (not as tabs — keep it as a scrollable page with clear section
   headers).
3. Add a redirect from `/trends` → `/analytics`.
4. Verify no data or API endpoints are lost.

---

## Out of Scope

- **Do NOT touch `/manual`.** It stays in primary nav exactly where it is.
- **Do NOT touch `/tools`.** It stays in nav. The founder uses it.
- **Do NOT touch `/nutrition`.** It stays as a placeholder. Founder decision pending.
- **Do NOT touch `/training-load`.** It stays as its own page — the PMC
  chart is the best visual in the product.
- **Do NOT merge Progress and Manual.** These serve different questions
  ("how am I growing?" vs "who am I as an athlete?").
- **Do NOT merge `/discover` into Home.** It's a first-session flow that
  works as-is.
- **Do NOT change the primary nav order.** Home | Manual | Progress |
  Calendar | Coach is intentional and stays.
- **Do NOT remove `/personal-bests`.** Low priority, leave it alone.

---

## Implementation Notes

**Files expected to change:**
- `app/dashboard/page.tsx` — delete
- `app/home-preview/page.tsx` — delete
- `app/spike/` — delete directory
- `app/diagnostic/` — delete directory (check if `diagnostic/report/` also)
- `app/profile/page.tsx` — convert to redirect after moving content
- `app/availability/page.tsx` — convert to redirect after integrating
- `app/trends/page.tsx` — convert to redirect after absorbing content
- `app/settings/page.tsx` — add profile section at top
- `app/plans/create/page.tsx` — integrate availability grid
- `app/analytics/page.tsx` — add trends content
- `app/onboarding/page.tsx` — update redirect target if it points to `/dashboard`
- `app/components/Navigation.tsx` — verify no dead links remain
- `app/components/BottomTabs.tsx` — verify no dead links remain

**Core contracts to preserve:**
- All existing redirects (`/checkin` → `/home`, `/insights` → `/manual`,
  `/discovery` → `/manual`) must continue working
- The `has_correlations` gating on Manual and Fingerprint nav items
  must not change
- No API endpoints are deleted — only frontend routes
- Settings page must retain all existing functionality (integrations,
  billing, preferences, consent) after absorbing profile

**Search for references before deleting:**
Run a codebase-wide search for each route string (`/dashboard`,
`/home-preview`, `/spike`, `/diagnostic`, `/profile`, `/availability`,
`/trends`) to find any links, redirects, or references that need updating.

---

## Tests Required

- **Frontend tests:** Verify no test files reference deleted routes.
  Update any that do.
- **Integration tests:** If any API tests reference `/profile` or
  `/availability`, update the references.
- **Build verification:** `cd apps/web && npx tsc --noEmit` — must pass
  with no type errors after all changes.
- **Route verification:** After changes, manually verify:
  - `/dashboard` → redirects to `/home`
  - `/diagnostic` → gone (404 is acceptable; or redirect to `/home`)
  - `/profile` → redirects to `/settings`
  - `/availability` → redirects to `/plans/create`
  - `/trends` → redirects to `/analytics`
  - `/settings` → shows profile section at top
  - `/analytics` → shows absorbed trends content
  - All existing redirects still work (`/checkin`, `/insights`, `/discovery`)
- **Production smoke:** After deploy, hit each redirect URL via curl and
  verify the Location header or page content.

Paste command output in handoff (no summaries only).

---

## Evidence Required in Handoff

1. `git diff --name-only` showing scoped file list
2. `npx tsc --noEmit` output (clean)
3. CI status (green)
4. Production smoke output for each redirect
5. Screenshot or curl output showing profile fields in Settings page

---

## Acceptance Criteria

1. `/dashboard`, `/home-preview`, `/spike/rsi-rendering`, `/diagnostic`
   no longer exist as pages (deleted or redirected)
2. `/profile` redirects to `/settings`; profile fields visible at top of
   Settings page
3. `/availability` redirects to `/plans/create`; availability grid is a
   step in plan creation
4. `/trends` redirects to `/analytics`; trend visualizations visible in
   Analytics page
5. No broken links anywhere in the app (search verified)
6. No references to deleted routes in navigation components
7. All existing redirects (`/checkin`, `/insights`, `/discovery`,
   `/plans/checkout`) still work
8. Frontend builds clean (`tsc --noEmit` passes)
9. CI green
10. Tree clean after commit

---

## Commit Discipline

This is multiple logical changes. Use **separate scoped commits**, not
one giant commit:

1. Delete dead routes (Part 1)
2. Merge profile into settings (Part 2)
3. Merge availability into plan creation (Part 3)
4. Absorb trends into analytics (Part 4)

Each commit: staged files shown, CI green, no unrelated changes.

---

## Mandatory: Site Audit Update

`docs/SITE_AUDIT_LIVING.md` must be updated in the same session:

1. New delta entry for route cleanup
2. Key Pages table updated (remove deleted routes, update merged routes)
3. Route count updated if tracked
4. Any navigation structure changes documented

No task is complete until this is done.
