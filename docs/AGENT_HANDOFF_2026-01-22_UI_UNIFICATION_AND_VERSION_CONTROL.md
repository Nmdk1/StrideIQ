## Agent Handoff: UI Unification + Version Control Cleanup

**Date:** 2026-01-22  
**Branch:** `stable-diagnostic-report-2026-01-14`  
**Owner intent:** Production-ready, cohesive product. “Uniform UX” is non-negotiable.  
**Context:** Session quality degraded; owner explicitly requested (1) documentation updates, (2) version control hygiene, (3) a handoff in the established style.

---

## Executive Summary

This session attempted to enforce **site-wide visual consistency**. The base background drift has largely been corrected (removing `bg-[#0a0a0f]` from pages/components and aligning on `bg-slate-900`), but the owner’s core complaint remains valid: **Home still reads as a different theme** because its **card surfaces are more translucent/darker** than Analytics/Calendar.

The repo has been cleaned up into **scoped commits** (code + docs). Before continuing feature work, the next agent should:

- stabilize the UI styling with **one enforced “page shell”** and **standard card surfaces**
- keep future work in **clean, scoped commits** (avoid committing one-off scripts)
- ensure `docs/PHASED_WORK_PLAN.md` remains the canonical workflow and is kept current

---

## What was intended / what actually happened

### Intended

- Make “entire site has the same look.”
- Specifically: ensure Analytics/Insights/Home share the same palette and background.

### Actual

- **Global base background** was unified to `bg-slate-900` (layout/body + many page wrappers).
- Many lingering `bg-[#0a0a0f]` usages were removed across `apps/web/app/*` and key components.
- **Owner-visible outcome** still felt inconsistent because **Home uses translucent surfaces** (`bg-slate-800/50` cards and nested `bg-slate-900/30` panels), while Analytics/Calendar are largely `bg-slate-800 border-slate-700` with `bg-slate-900` inputs.

---

## Current repo state (important)

As of this handoff, the branch contains **two clean commits**:

- `feat: harden ingestion, admin diagnostics, and web UX`
- `docs: update phased work plan and add 2026-01-22 handoff`

Current `git status` is clean **except** for **three untracked one-off scripts** in `apps/api/scripts/`:

- `backfill_best_efforts_fast.py`
- `find_better_mile_effort.py`
- `fix_planned_workout_glitch_2026_01_22.py`

These were intentionally left uncommitted because they look ad-hoc. Only commit them if the owner explicitly wants them retained as maintained operational tooling.

---

## UI consistency: what to fix next (high priority)

### 1) Home surface mismatch (owner complaint)

Home currently uses:
- `Card className="bg-slate-800/50 border-slate-700/50"`
- nested panels like `bg-slate-900/30 border-slate-700/60`

Analytics/Calendar commonly use:
- `Card className="bg-slate-800 border-slate-700"`
- inputs `bg-slate-900 border-slate-600`

**Fix direction:** align Home to solid surfaces:
- switch primary cards to `bg-slate-800 border-slate-700`
- switch nested panels to `bg-slate-900/20` (or `bg-slate-900`) with `border-slate-700`
- avoid mixing 3 different translucency levels on one screen

### 2) Prevent recurrence: introduce a shared page wrapper

Create a reusable wrapper (e.g. `components/layout/AppPage.tsx`) that enforces:
- `min-h-screen bg-slate-900 text-slate-100`
- consistent container width (`max-w-6xl` or `max-w-7xl`) and padding (`px-4 py-6` or `py-8`)

Then refactor pages to use it. This prevents future “dark as hell” drift.

### 3) Definition of “same look”

Use this as the enforcement contract:
- background: `bg-slate-900`
- cards: `bg-slate-800 border-slate-700`
- nested panels: `bg-slate-900/20 border-slate-700`
- inputs: `bg-slate-900 border-slate-600`

Reference: `apps/web/STYLE_GUIDE.md`

---

## Documentation updates required (owner request)

### Canonical plan

`docs/PHASED_WORK_PLAN.md` is the canonical workflow contract. It must be:
- committed
- updated after each sprint with a ledger entry

This session added a 2026-01-22 ledger entry acknowledging partial UI work and remaining mismatch.

### Handoff docs

- Existing: `docs/AGENT_HANDOFF_FULL_SYSTEM.md` (updated with 2026-01-22 delta)
- This file: `docs/AGENT_HANDOFF_2026-01-22_UI_UNIFICATION_AND_VERSION_CONTROL.md` (new)

---

## Version control plan (what to commit / what NOT to commit)

### Should be committed

- Web UI consistency changes (layout + pages + components)
- Diagnostics admin-only routes/pages (web + api), if they’re already in active use
- New migrations required by production flows
- Tests that validate these behaviors
- `docs/PHASED_WORK_PLAN.md` + this handoff doc + any updated handoff docs

### Should probably NOT be committed (unless owner explicitly wants)

- one-off scripts in `apps/api/scripts/` that are clearly ad-hoc (e.g. “fix_*_date.py”, “find_*”, “debug_*”)

---

## How to run / verify

### Web build

- `docker compose up -d --build web`
- Validate in browser:
  - Home vs Analytics vs Calendar: verify same background and card surfaces
  - Navigation dropdown surface matches background

### Fast UI sanity checks

- ensure no lingering `#0a0a0f` styling in web codebase (grep)
- ensure Home uses the same `Card` surface tokens as Analytics

---

## Owner context (tone + process)

- Owner has very low tolerance for iterative “close enough” UI attempts.
- Required process: **plan + mock + approval before build** for any visible UX redesign.
- Do not claim “fixed” unless owner confirms the UI matches the rest of the site visually.

