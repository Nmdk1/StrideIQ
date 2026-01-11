# Calendar & Plan UX Architecture

**Status:** ACTIVE - Governing Document  
**Created:** January 11, 2026  
**Standard:** Production-Ready (NOT MVP)

---

## Problem Statement

The Training Calendar is the **central UI hub** of StrideIQ [[memory:13193119]]. Currently it has critical UX failures:

1. **Plan Visibility Failure** - Plan exists but workouts are not clearly displayed or distinguishable
2. **No Plan Management** - Cannot withdraw, pause, modify, or adapt plans (injury, work, life)
3. **Dead-End Activity Popup** - Activity detail panel shows data but doesn't link to full analysis
4. **Broken Navigation** - Users cannot intuitively find plan creation, preview, or management
5. **No Workout Completion Flow** - No way to mark workouts complete, skip, or swap

---

## Guiding Principles

1. **User Mental Model First** — Design for how runners think, not how developers implement
2. **Progressive Disclosure** — Show what's needed, reveal depth on demand
3. **Every Element is Actionable** — If you can see it, you can interact with it
4. **Exit Paths Everywhere** — Never trap users in a dead end
5. **Adapt, Don't Break** — Life happens; the plan should flex
6. **Calendar is HOME** — Everything flows through the calendar

---

## User Journey Map

### The Happy Path
```
Landing → Register → Onboarding → Create Plan → Calendar (HOME)
                                       ↓
                              View Week → Click Day → See Workout
                                                         ↓
                                              Complete Activity → Match to Plan
                                                         ↓
                                              View Insights → Ask Coach
```

### The Adaptation Path
```
Calendar → Realize Issue (injury/travel/work)
    ↓
Click Plan Management → Options:
    ├── Pause Plan (keep plan, pause dates)
    ├── Skip Week (mark week skipped, adjust)
    ├── Modify Workout (swap day, change workout)
    ├── Withdraw from Race (archive plan)
    └── Change Race Date (recalculate plan)
```

### The Activity Analysis Path
```
Calendar → Click Day → See Activity in Panel
    ↓
Click Activity → Full Activity Detail Page
    ↓
├── View Splits
├── View Context Analysis  
├── Compare to Similar Runs
├── Log Perception (RPE)
├── See Insights
└── Return to Calendar
```

---

## Phase A: Fix Critical UX Gaps (Immediate)

### A1: Plan Visibility on Calendar

| Task | Description | Priority |
|------|-------------|----------|
| Clear Workout Cards | Show workout title, distance, and type prominently | P0 |
| Workout Type Colors | Consistent, meaningful color coding | P0 |
| Phase Context | Show phase name in week header | P1 |
| Week Focus | Show week focus/goal text | P1 |
| Today Highlight | Clear visual for "this is today" | P0 |
| Completion Status | Visual indicator for done/missed/modified | P0 |

**Current Issue:** DayCell shows workout type but it's small, colored blocks are not intuitive, no workout title visible in grid view.

**Solution:** Redesign DayCell to show:
- Workout title (e.g., "Easy + Strides" not "easy_strides")
- Target distance prominently
- Clear visual hierarchy

### A2: Activity Deep Linking

| Task | Description | Priority |
|------|-------------|----------|
| Activity Card Click | Click activity in panel → full detail page | P0 |
| View Full Details Button | Explicit CTA to activity page | P0 |
| Quick Compare Link | Link to contextual comparison | P1 |
| Back to Calendar | Clear navigation back | P0 |

**Current Issue:** DayDetailPanel shows activities with stats but no links to `/activities/[id]`.

**Solution:** Make activity cards in DayDetailPanel clickable with clear "View Details →" CTA.

### A3: Plan Management

| Task | Description | Priority |
|------|-------------|----------|
| Plan Banner Menu | Dropdown/modal for plan actions | P0 |
| Withdraw from Race | Archive plan, clear calendar | P0 |
| Pause Plan | Keep plan but pause progression | P1 |
| Change Race Date | Recalculate plan schedule | P1 |
| Skip Week | Mark week skipped, adjust | P1 |
| Swap Workout Days | Move workout to different day | P2 |

**Current Issue:** No plan management UI exists at all.

**Solution:** Add plan management modal accessible from PlanBanner with clear action buttons.

### A4: Navigation & Wayfinding

| Task | Description | Priority |
|------|-------------|----------|
| Clear Nav Labels | "Training Plan" not "Plans" | P0 |
| Active Plan Indicator | Show plan name in nav when active | P1 |
| Quick Actions Menu | Common actions accessible | P1 |
| Breadcrumbs | Where am I, how to get back | P1 |
| Plan Preview Access | From calendar, view full plan outline | P0 |

**Current Issue:** Users cannot find plan creation/preview intuitively.

**Solution:** 
- Add "Training Plan" to main nav with sub-menu
- When plan active: show plan name, link to plan view
- When no plan: prominent "Create Plan" CTA

---

## Phase B: Enhanced Calendar Experience (Week 2-3)

### B1: Week View Enhancement

| Task | Description |
|------|-------------|
| Week Summary Card | Volume, quality sessions, phase, focus |
| Week-at-a-Glance | Horizontal strip showing 7 days |
| Current Week Highlight | Clear "this is your week" |
| Upcoming Week Preview | What's next |
| Week Navigation | Jump to specific week |

### B2: Workout Detail Flow

| Task | Description |
|------|-------------|
| Workout Preview Modal | Full workout structure |
| Option A/B Selection | Choose alternate workout |
| Workout Modification | Adjust workout before doing |
| Pre-Workout Checkin | How do you feel? |
| Coach Explanation | "Why this workout today?" |

### B3: Activity Matching

| Task | Description |
|------|-------------|
| Auto-Match Activities | Link Strava activity to planned workout |
| Manual Match | "This is my Tuesday run" |
| Match Quality | Did they nail it, close, or miss? |
| Mismatch Detection | Alert when activity doesn't match plan |
| Completion Confirmation | Mark workout complete with feedback |

---

## Phase C: Plan Adaptation (Week 4-5)

### C1: Modification UI

| Task | Description |
|------|-------------|
| Day Swap | Drag-drop or select to swap days |
| Week Adjustment | Shift entire week forward/back |
| Workout Substitution | Replace with equivalent |
| Volume Reduction | "Make this week easier" |
| Extra Rest Day | Insert recovery day |

### C2: Lifecycle Management

| Task | Description |
|------|-------------|
| Plan Pause | Freeze dates, resume later |
| Plan Restart | Re-baseline from current fitness |
| Race Date Change | Recalculate with new target |
| Goal Time Change | Adjust paces and volumes |
| Plan Archive | Keep history, clear calendar |

### C3: Missed Workout Handling

| Task | Description |
|------|-------------|
| Miss Detection | Identify missed workout |
| Miss Options | Skip, reschedule, or make up |
| Automatic Adjustment | Rebalance week |
| Coach Guidance | "What should I do now?" |
| Pattern Detection | Recurring misses → intervention |

---

## Phase D: Polish & Delight (Week 6)

### D1: Micro-Interactions

| Task | Description |
|------|-------------|
| Workout Completion Animation | Satisfying checkmark |
| Week Complete Celebration | Small celebration for full weeks |
| Phase Transition | Visual phase change |
| Streak Display | Consecutive days/weeks |
| Personal Bests | Highlight PRs on calendar |

### D2: Mobile Excellence

| Task | Description |
|------|-------------|
| Touch-Friendly | Large tap targets |
| Swipe Navigation | Swipe between days/weeks |
| Quick Actions | Long-press for actions |
| Compact View | Optimized for small screens |
| Offline Support | View plan without connection |

---

## Component Architecture

### New Components Required

```
apps/web/components/
├── calendar/
│   ├── DayCell.tsx              (enhance)
│   ├── DayDetailPanel.tsx       (enhance)
│   ├── WeekSummaryRow.tsx       (exists)
│   ├── WeekHeader.tsx           (new)
│   ├── CreatePlanCTA.tsx        (exists)
│   └── PlanBanner.tsx           (extract from page)
│
├── plans/
│   ├── PlanManagementModal.tsx  (new - critical)
│   ├── PlanOverview.tsx         (new)
│   ├── WeekOverview.tsx         (new)
│   ├── WorkoutPreview.tsx       (new)
│   ├── WorkoutOptionSelector.tsx (new)
│   └── PlanTimeline.tsx         (new)
│
├── workouts/
│   ├── WorkoutCard.tsx          (new)
│   ├── WorkoutDetailModal.tsx   (new)
│   ├── CompletionFlow.tsx       (new)
│   └── SkipWorkoutModal.tsx     (new)
│
└── navigation/
    ├── TrainingPlanNav.tsx      (new)
    ├── QuickActionsMenu.tsx     (new)
    └── Breadcrumbs.tsx          (new)
```

### New API Endpoints Required

```
POST /v2/plans/{id}/pause
POST /v2/plans/{id}/resume
POST /v2/plans/{id}/withdraw
POST /v2/plans/{id}/change-date
POST /v2/plans/{id}/skip-week
POST /v2/plans/{id}/swap-days

PATCH /v2/planned-workouts/{id}/complete
PATCH /v2/planned-workouts/{id}/skip
PATCH /v2/planned-workouts/{id}/modify
POST /v2/planned-workouts/{id}/match-activity
```

---

## Implementation Order

### Sprint 1: Critical Fixes (This Week) ✅ COMPLETE

1. **Activity Deep Linking** - Make activities clickable in DayDetailPanel ✅
2. **Plan Management Modal** - Add withdraw/pause/modify options ✅
3. **Clear Workout Display** - Redesign DayCell with readable workout info ✅
4. **Navigation Fix** - Add Training Plan to nav, clear paths ✅
5. **Plan Overview Page** - Full plan view at `/plans/[id]` ✅
6. **Plan Management API** - Endpoints for pause/resume/withdraw/change-date ✅

### Sprint 2: Enhanced Display

5. **Week Headers** - Phase and focus info
6. **Completion Status** - Visual done/missed indicators
7. **Plan Overview Page** - Full plan view with all weeks
8. **Workout Preview** - Click to see full workout detail

### Sprint 3: Adaptation

9. **Day Swap** - Move workouts between days
10. **Skip Week** - Mark week as skipped
11. **Activity Matching** - Link activities to workouts
12. **Missed Workout Flow** - Handle missed workouts

### Sprint 4: Polish

13. **Mobile Optimization** - Touch, swipe, responsive
14. **Micro-Interactions** - Animations, celebrations
15. **Coach Integration** - Contextual coach availability
16. **Performance** - Caching, lazy loading

---

## Success Criteria

### Phase A Complete When:
- [ ] Clicking activity in panel goes to full activity page
- [ ] Plan banner has accessible management options
- [ ] Can withdraw from race/archive plan
- [ ] Workout titles visible in calendar grid
- [ ] Training Plan accessible from main nav
- [ ] User can find plan creation in < 2 clicks

### Phase B Complete When:
- [ ] Week view shows phase, volume, focus
- [ ] Can click workout to see full detail
- [ ] Option A/B selection works
- [ ] Pre-workout check-in captures readiness

### Phase C Complete When:
- [ ] Can swap workout days
- [ ] Can pause and resume plan
- [ ] Can change race date
- [ ] Missed workouts detected and handled

### Phase D Complete When:
- [ ] Mobile experience is excellent
- [ ] Micro-interactions feel polished
- [ ] Performance targets met
- [ ] No dead-ends in UI

---

## Visual Design Specifications

### Workout Type Colors (Consistent)

```css
/* Rest / Recovery */
--rest: gray-700
--recovery: gray-600

/* Easy / Aerobic */
--easy: emerald-600
--easy-strides: emerald-500
--easy-hills: emerald-400

/* Medium Effort */
--medium-long: sky-500
--tempo: amber-500

/* Quality Sessions */
--threshold: orange-500
--intervals: red-500
--long: blue-500
--long-mp: violet-500

/* Special */
--race: gradient pink→orange
--shakeout: gray-500
```

### Status Indicators

```
✓ Completed: emerald ring + checkmark
≈ Modified: amber ring + modified icon
✗ Missed: red ring (faded) + x icon
→ Future: no ring, full opacity
```

### Workout Card Layout (DayCell)

```
┌─────────────────────────┐
│ 14                      │  ← Day number
├─────────────────────────┤
│ ┌─────────────────────┐ │
│ │ THRESHOLD          │ │  ← Type badge (colored)
│ │ 3×10min @ T-pace   │ │  ← Title/description
│ │ 8.0 mi             │ │  ← Distance
│ └─────────────────────┘ │
│                         │
│ ┌─────────────────────┐ │
│ │ ✓ 7.9 mi | 7:12/mi │ │  ← Actual activity
│ └─────────────────────┘ │
│                         │
│ 📝 🔥                   │  ← Notes, insights icons
└─────────────────────────┘
```

---

## Revision History

| Date | Change | By |
|------|--------|-----|
| 2026-01-11 | Initial UX architecture created | AI |

---

*This document governs all calendar and plan UX development.*
*Production quality. User-first. Test everything.*
