# Activity Page Design Spec — Strava-Caliber Visual Quality

**Date:** April 12, 2026
**Reference:** 25 Strava screenshots (desktop + mobile) from founder's actual account
**Status:** SPEC ONLY — do not build until founder approves
**Applies to:** `apps/web/app/activities/[id]/page.tsx` and all activity components

---

## What This Spec Is

A pixel-level design reference derived from Strava's desktop and mobile activity pages. The goal is not to copy Strava's product — it's to match their visual quality: typography, spacing, layout ratios, card patterns, and information hierarchy. StrideIQ's data is deeper. The presentation needs to match.

---

## Desktop Layout (from Strava screenshots)

### Structure

```
┌─────────────────────────────────────────────────────────┐
│  Global Nav                                              │
├──────────┬──────────────────────────────────────────────┤
│          │  Athlete Name — Run                    ⌃ 9 💬0│
│ Overview │──────────────────────────────────────────────│
│          │                                              │
│ ▶Analysis│  7.55 mi   1:03:03   8:21 /mi   37          │
│  Pace    │  Distance   Moving    Pace    Relative       │
│  Pace    │             Time              Effort         │
│  Dist    │                                              │
│  Rel.Eff │  Elevation  0 ft   Calories  768             │
│  HR      │  Elapsed   1:22:48                           │
│          │                                              │
│ Segments │  ☀ Clear 55°F  Humidity 86%  Wind 4.0mi/h    │
│ Laps     │  Garmin Forerunner 165   Shoes: —            │
│ Best Eff │                                              │
│ Matched  │  Activity title + description                │
│          │  Social (kudos, private notes)                │
│          │                                              │
│  ✏ ···  │  ┌─── Splits ───┐  ┌──── Map ─────┐         │
│          │  │ Mile Pace GAP│  │               │         │
│          │  │ 1   9:05 9:05│  │   (route)     │         │
│          │  │ 2   8:11 8:11│  │               │         │
│          │  │ ...          │  └───────────────┘         │
│          │  └──────────────┘                            │
│          │  ┌─── Elevation Profile (full width) ───┐   │
│          │  └──────────────────────────────────────┘   │
│          │                                              │
│          │  Pace  GAP   HR    Cadence  Temp             │
│          │  Avg   8:21  8:21  130bpm  188spm  73°F      │
└──────────┴──────────────────────────────────────────────┘
```

### Key Desktop Design Patterns

1. **Left sidebar (~120px):** Text navigation with section groups. "Overview" is top-level. "Analysis" expands to show sub-pages (Pace Analysis, Pace Distribution, Relative Effort, Heart Rate). Then Segments, Laps, Best Efforts, Matched Runs. Each click loads different content in the main area — not tabs, but actual distinct views.

2. **Stats header:** Numbers are LARGE — approximately 28-32px bold. Labels are small gray text below (~11px). The hierarchy is unmistakable: your eye goes to the numbers first. Stats laid out in a 2-3 column grid with generous spacing.

3. **Two-column sections:** Splits table (left ~55%) + Map (right ~45%) side by side. Elevation profile spans full width below. This is the pattern that works.

4. **Analysis sub-pages:** Each has the same big stats header at top, then a full-width chart, then a data table. Pace Analysis shows a bar chart with elevation overlay. Pace Distribution shows horizontal zone bars. Heart Rate shows a zone table. Each is a complete, self-contained view.

5. **Clean backgrounds:** White/light content cards on a slightly off-white page. Clear borders. No dark-on-dark-on-dark layering.

6. **Tables:** Clean, well-spaced rows. Consistent column alignment. No cramped text. Headers are gray, data is black/bold.

---

## Mobile Layout (from Strava screenshots)

### Structure: Continuous Vertical Scroll

No tabs on mobile. Everything is a single scroll with clear section separators.

```
┌─────────────────────┐
│  ← Run        🔖 ··· │
├─────────────────────┤
│                     │
│   FULL-BLEED MAP    │  ← Hero, ~40% viewport
│   (route overlay)   │
│         ▶           │  ← 3D playback button
│                     │
├─────────────────────┤
│ 👤 Michael Shaffer  │
│ 🏃 Yesterday 7:00AM │
│                     │
│ Hattiesburg Half    │  ← LARGE bold title (~24px)
│ Marathon 9:30 pacer │
│                     │
│ 62°F ☀ Dew pt: 56°F│  ← Description text
├─────────────────────┤
│                     │
│ Distance  Avg Pace  │  ← 2x3 stats grid
│ 13.28 mi  9:16/mi   │  ← Numbers ~28px bold
│                     │
│ Moving    Elevation │
│ 2:03:03   374 ft    │
│                     │
│ Calories  Avg HR    │
│ 1,506     127 bpm   │
│                     │
├─────────────────────┤
│ ┌─────────────────┐ │
│ │🔥 Athlete Intel │ │  ← Orange accent border
│ │                 │ │
│ │ Solid half      │ │  ← 2-3 sentence insight
│ │ marathon pacing │ │
│ │ effort...       │ │
│ │                 │ │
│ │ [Say More]      │ │  ← Expands to full analysis
│ └─────────────────┘ │
├─────────────────────┤
│ Prediction Improved │  ← Achievement card
│ Marathon 3h 9m ▼51s │
├─────────────────────┤
│ Results             │
│ Best Efforts 11     │
│ Segments     4      │
│ Half-Marathon 2:02  │
│ 20K          1:55   │
│ [View All Results]  │
├── thin line ────────┤
│ Workout Analysis    │  ← Section header
│ ┌─────────────────┐ │
│ │ pace bar chart  │ │  ← Per-lap bars
│ └─────────────────┘ │
│ [View Workout]      │
├── thin line ────────┤
│ Splits              │
│ Mi  Pace [bars] Elev│  ← Pace has visual bars
│ 1   9:23  ████  9   │
│ 2   9:21  ████  -14 │
│ ...                 │
├── thin line ────────┤
│ Pace            ⓘ  │  ← Section title + info
│ ┌─────────────────┐ │
│ │ area chart      │ │  ← Filled area chart
│ │ (blue/gray)     │ │
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │🔥 Athlete Intel │ │  ← PER-CHART intelligence
│ │ Your pace held  │ │
│ │ steady around   │ │
│ │ 9:20-9:35/mi... │ │
│ └─────────────────┘ │
│ Avg Pace    9:16/mi │  ← Label left, value right
│ Moving Time 2:03:03 │
│ Fastest Split 8:23  │
├── thin line ────────┤
│ Grade Adj Pace  ⓘ  │
│ [area chart]        │
│ Avg GAP     9:11/mi │
├── thin line ────────┤
│ 🔥 Pace Zones      │
│ Z6  11%    <5:53    │  ← Horizontal bars
│ Z5  18%    5:53-6:15│
│ Z4   1%    6:15-6:41│
│ ...                 │
│ ┌─────────────────┐ │
│ │🔥 Athlete Intel │ │
│ │ You mixed       │ │
│ │ recovery (39%)  │ │
│ │ and endurance...│ │
│ └─────────────────┘ │
│ [View aggregate]    │
├── thin line ────────┤
│ Heart Rate      ⓘ  │
│ [area chart - pink] │
│ ┌─────────────────┐ │
│ │🔥 Athlete Intel │ │
│ │ HR stayed mostly│ │
│ │ steady...       │ │
│ └─────────────────┘ │
│ Avg HR     127 bpm  │
│ Max HR     160 bpm  │
├── thin line ────────┤
│ 🔥 HR Zones        │
│ Z5  0%    >175      │
│ Z4  0%    160-174   │
│ ...                 │
│ ┌─────────────────┐ │
│ │🔥 Athlete Intel │ │
│ │ You stayed in   │ │
│ │ endurance zone  │ │
│ │ (95%)...        │ │
│ └─────────────────┘ │
├── thin line ────────┤
│ Power           ⓘ  │
│ [area chart-purple] │
│ Avg Power   278 W   │
│ Total Work  2,052kJ │
│ Max Power   450 W   │
├── thin line ────────┤
│ Cadence         ⓘ  │
│ [area chart - pink] │
│ Avg Cadence 182 spm │
│ Max Cadence 204 spm │
└─────────────────────┘
```

### Key Mobile Design Patterns

1. **No tabs.** Continuous vertical scroll with thin line separators between sections. This is the opposite of what we built.

2. **Map as hero.** Full-bleed map takes the top ~40% of the viewport. No border, no card — edge to edge.

3. **Large stats grid.** 2x3 grid with ~28px bold numbers, ~12px gray labels. Distance, Avg Pace, Moving Time, Elevation, Calories, Avg HR.

4. **Athlete Intelligence cards.** Orange accent (left border or icon), rounded corners, placed DIRECTLY BELOW the chart they describe. Each chart gets its own intelligence card. The card contains 2-3 specific sentences about what the chart shows + what it means.

5. **Per-section pattern:** Section title (large, bold, left-aligned) → Chart (full width, filled area) → Intelligence card (if applicable) → Key stats (label left, bold value right) → thin separator → next section.

6. **Pace bars in splits.** Each split row has a horizontal bar proportional to the pace. Visual, not just numbers.

7. **"Say More" expansion.** The summary intelligence card has a "Say More" button that opens a full-screen modal with detailed analysis (multiple paragraphs). This is how Strava handles the depth vs brevity tension.

---

## What StrideIQ Must Change

### Typography
- Stats numbers: increase to ~28px bold (currently ~16px)
- Stats labels: ~11px gray, below the number (currently same size as numbers)
- Section headers: ~20px bold (currently ~14px)

### Layout — Desktop
- Keep the left sidebar navigation pattern (Strava uses it)
- But the sidebar needs REAL sub-pages, not empty tab panels
- Two-column for splits+map (we already have this in the Splits tab)
- Overview should show: big stats → activity description → splits+map side by side → elevation → summary stats bar

### Layout — Mobile
- Consider: drop tabs, switch to continuous scroll like Strava
- If keeping tabs: make them prominent, not an afterthought
- Map should be large and at the top (hero)
- Stats grid should be 2x3 with LARGE numbers

### Intelligence Cards
- Place below the relevant chart, not in a separate tab
- Orange/emerald accent left border
- 2-3 sentence contextual insight
- "Show more" expansion for detailed analysis
- Show nothing if there's nothing worth saying (empty state = no card)

### Spacing
- Double the current spacing between sections
- Generous padding inside cards (~16-20px)
- Clear visual breathing room between chart and stats below it

### Charts
- Full-width filled area charts (not just lines)
- Strava uses filled areas with color (blue for pace, pink/red for HR, purple for power)
- Our RunShapeCanvas gradient is already better than Strava's charts — keep it as the hero

### Splits
- Add visual pace bars (horizontal colored bars proportional to pace)
- Clean table with generous row height
- Headers gray, data black/white + bold

---

## What StrideIQ Already Does Better

1. **RunShapeCanvas** — our gradient effort visualization is genuinely more informative than Strava's bar charts. This is our visual differentiator.

2. **Cardiac decoupling / drift metrics** — Strava doesn't surface this. Our Analysis tab data is deeper.

3. **N=1 correlation findings** — Strava's intelligence is LLM attaboys. Our correlation engine finds real patterns. The intelligence content is better when the voice layer is complete.

4. **Going In pre-run state** — Strava doesn't show HRV, sleep, or readiness context. This is unique.

5. **StreamHoverContext** — chart-map-elevation hover linkage. Strava has it too, but ours works across components.

---

## Build Priority

1. **Typography + spacing overhaul** — biggest visual impact for least risk. Change font sizes, padding, margins. No layout restructuring.

2. **Desktop Overview layout** — two-column splits+map, big stats header. Match Strava's information density.

3. **Intelligence card pattern** — bordered card with accent, placed per-chart. Infrastructure for when Opus builder delivers per-chart insights.

4. **Mobile map hero** — full-bleed map at top of page.

5. **Splits pace bars** — horizontal visual bars in the splits table.

6. **Decide: tabs vs continuous scroll on mobile** — this is a product decision, not a build decision. Strava uses no tabs on mobile. We could go either way.

---

## Reference Screenshots (saved to workspace)

All 25 Strava screenshots are saved in `assets/` directory. Key reference files:

**Desktop:**
- Overview page with stats + splits + map
- Pace Analysis with bar chart
- Pace Distribution with zone bars
- Relative Effort with weekly chart
- Heart Rate zones
- Segments table
- Laps table
- Best Efforts table
- Matched Runs trend

**Mobile (Hattiesburg Half Marathon):**
- Map hero + title + stats
- Athlete Intelligence summary + expanded modal
- Results + Workout Analysis
- Pace chart + intelligence card
- GAP chart + Pace Zones
- HR chart + intelligence card + HR Zones
- Power chart
- Cadence chart

**Mobile (Meridian 1200s workout):**
- Pace chart + intelligence card (intervals)
- Intelligence expanded modal
- Splits with pace bars
