# Runtoon "Share Your Run" — Product & UX Spec

**Author:** Founder + AI advisor  
**Date:** February 28, 2026  
**Status:** Spec — not yet built  
**Prereads:** `docs/PRODUCT_MANIFESTO.md`, `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`

---

## The Problem

Runtoons currently auto-generate in the background when a run syncs, then
sit on the activity page waiting to be discovered. This is backwards.
The athlete doesn't know a Runtoon was created. They have to scroll to the
activity page, see the card, and then decide to download. That's three steps
too many for a feature whose entire value is _sharing_.

The best moment to share a run is the 30 seconds after you stop your watch.
You're still sweating. You're proud or wrecked or both. You want to tell
someone. That window closes fast. By the time you shower, eat, and sit down,
the impulse is gone. If the share moment isn't _right there_ when the run
syncs, it doesn't happen.

## The Vision

**One tap. Right when the run lands. Image ready. Share done.**

The Runtoon isn't a page feature. It's a _moment_ — the post-run share
moment. The product's job is to catch that moment, hand the athlete a
beautiful, funny, personalized image, and get out of the way.

---

## Design Principles (from the manifesto)

1. **The athlete decides, the system informs.** Runtoons are opt-in per run,
   not auto-generated. The system prepares the image; the athlete chooses
   whether to share it. Never post on their behalf. Never assume they want
   to share every run.

2. **Mobile is about convenience, form factor is everything.** The share
   flow must work with one thumb, on a phone, while still catching your
   breath. No scrolling. No navigating to a page. No multi-step flows.

3. **Style and design matter deeply.** The share sheet isn't a modal with a
   button. It's a beautiful, full-screen moment — the Runtoon fills the
   viewport, the stats are legible, the action is obvious. It should feel
   like Instagram's story composer, not like a desktop dialog box.

---

## Architecture: What Changes

### Current Flow (remove)

```
Run syncs → Celery auto-generates Runtoon → sits on activity page → athlete
maybe finds it → downloads → manually shares
```

### New Flow

```
Run syncs → Frontend detects new activity → Shows "Share Your Run" prompt →
Athlete taps → Backend generates Runtoon on-demand (~15-20s) → Full-screen
Runtoon appears → One tap: Download / Share → Done
```

**Key decision: on-demand, not pre-generated.**

The Runtoon is generated only when the athlete taps "Share Your Run" — not
automatically on every sync. This means:

- **Zero wasted API cost.** Only runs the athlete wants to share cost money.
  At scale (1,000 users × 5 runs/week), this is the difference between
  $500/month in Gemini calls vs. paying only for images someone actually
  wants (~$50-100/month assuming 20-25% share rate).
- **No generation for throwaway runs.** A 2-mile shakeout, a treadmill
  warmup, a GPS-glitched false start — none of these trigger a $0.02 API
  call unless the athlete explicitly asks.
- **15-20 second wait is acceptable.** The athlete just tapped a button.
  They expect something to happen. A skeleton animation with "Creating
  your Runtoon..." and a progress hint keeps them engaged. They're
  looking at their phone post-run anyway. The wait builds anticipation.
- **"Later" works too.** If the athlete dismisses the prompt, they can
  always tap "Share Your Run" from the activity page card. Same flow,
  same on-demand generation, no time pressure.

The sync pipeline no longer triggers `generate_runtoon_for_latest`. That
call moves to the share flow's backend endpoint.

---

## UX Flow: Mobile (Primary)

### Step 0: Run Syncs

The athlete finishes a run. Their watch syncs via Garmin/Strava webhook.
The backend processes the activity as usual (stream analysis, intelligence
pipeline, etc.) but does NOT generate a Runtoon. No image generation
happens until the athlete explicitly requests it.

### Step 1: The Prompt

When the athlete opens StrideIQ (or if they're already on the app), they
see a **bottom sheet / slide-up prompt** — not a modal, not a page redirect.
It slides up from the bottom of whatever screen they're on (home, activities,
anywhere).

```
┌─────────────────────────────────────┐
│                                     │
│  (current page content, dimmed)     │
│                                     │
├─────────────────────────────────────┤
│  ┌───────────────────────────────┐  │
│  │  🏃 Your run just landed     │  │
│  │  13.0 mi • 7:27/mi • 1:37   │  │
│  │                               │  │
│  │  ┌─────────────────────────┐  │  │
│  │  │  Share Your Run  →      │  │  │
│  │  └─────────────────────────┘  │  │
│  │                               │  │
│  │  Not now              │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

**Design rules for the prompt:**
- Appears within 5 seconds of the app detecting a new synced activity
- Shows the run summary (distance, pace, duration) so the athlete knows
  which run
- One primary action: "Share Your Run" — large, tappable, unmissable
- One dismiss: "Not now" — small, text-only, no guilt
- Swipe-down dismisses (standard bottom sheet gesture)
- Tapping "Share Your Run" triggers generation (if no Runtoon exists yet)
  and opens the share view with a generation-in-progress skeleton
- Auto-dismisses after 10 minutes if not interacted with
- Does NOT appear if the athlete has no photos uploaded (they see the
  activity page CTA instead — existing behavior)
- Does NOT appear for non-running activities (cycling, swimming, etc.)
- Shows at most once per synced activity (persisted in local state)

### Step 2: The Share View (Full Screen)

Tapping "Share Your Run" opens a **full-screen overlay**. If no Runtoon
exists yet, it triggers generation and shows a creation state first.

**Generation state (15-20 seconds):**

```
┌─────────────────────────────────────┐
│  ✕ (top-left close)                │
│                                     │
│  ┌───────────────────────────────┐  │
│  │                               │  │
│  │   ┌─────────────────────┐     │  │
│  │   │  ░░░░░░░░░░░░░░░░░  │     │  │
│  │   │  ░░░ skeleton ░░░░  │     │  │
│  │   │  ░░░░░░░░░░░░░░░░░  │     │  │
│  │   └─────────────────────┘     │  │
│  │                               │  │
│  │   Creating your Runtoon...    │  │
│  │   Usually ready in ~15 sec    │  │
│  │                               │  │
│  └───────────────────────────────┘  │
│                                     │
└─────────────────────────────────────┘
```

The skeleton animates with a subtle shimmer. The text updates as the
generation progresses ("Almost there..." after 10s). When the image
arrives, it fades in and the action buttons appear below.

**Ready state:**

```
┌─────────────────────────────────────┐
│  ✕ (top-left close)                │
│                                     │
│  ┌───────────────────────────────┐  │
│  │                               │  │
│  │                               │  │
│  │     [RUNTOON IMAGE]           │  │
│  │     (full width, 1:1)         │  │
│  │                               │  │
│  │                               │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌─────────┐  ┌─────────────────┐  │
│  │  Save   │  │  Share  →       │  │
│  │  📥     │  │  (native share) │  │
│  └─────────┘  └─────────────────┘  │
│                                     │
│  ┌──────────────────────────────┐   │
│  │  Stories (9:16) ▾            │   │
│  └──────────────────────────────┘   │
│                                     │
│  ┌──────────────────────────────┐   │
│  │  🔄 Try another look        │   │
│  └──────────────────────────────┘   │
│                                     │
└─────────────────────────────────────┘
```

**Design rules for the share view:**
- Dark background (matches app theme, makes the Runtoon pop)
- Image is the hero — occupies the top 60-65% of the viewport
- **Save** — downloads to device (existing blob download, already works)
- **Share** — uses the Web Share API (`navigator.share()`) to invoke the
  native OS share sheet. This gives the athlete Instagram, iMessage,
  WhatsApp, Twitter, etc. in one tap with zero integration work from us.
  Falls back to "Copy link" on browsers that don't support Web Share API.
- **Stories (9:16)** — secondary action. Tapping toggles between the 1:1
  and 9:16 format previews. The selected format is what gets shared/saved.
- **Try another look** — triggers regeneration (same as existing
  Regenerate, respects the 3-attempt limit). Shows "Generating..." state
  with skeleton animation while the new image arrives.
- Close (✕) returns to the underlying page
- Swipe-down also closes

### Step 3: Native Share (The Money Tap)

When the athlete taps "Share":

```javascript
navigator.share({
  files: [new File([blob], 'runtoon.png', { type: 'image/png' })],
  title: 'My run on StrideIQ',
  text: captionText,  // the AI-generated caption
})
```

This opens the native share sheet on iOS/Android. The athlete picks their
destination (Instagram Story, iMessage, Twitter, etc.) and they're done.
One tap after the share view. Two taps total from sync.

**Fallback for desktop / unsupported browsers:**
- Download the image (existing behavior)
- "Copy caption" button to grab the text
- Show a toast: "Image saved — paste it wherever you share"

---

## UX Flow: Desktop (Secondary)

Desktop users don't get the bottom sheet prompt (it's a mobile pattern).
Instead:

1. **Activity page** — the RuntoonCard stays where it is (above the fold,
   already shipped). This is the desktop discovery surface.
2. **Home page** — after a run syncs, the home page could show a compact
   "Share your latest run" banner in the Recent Runs section. This is
   optional and lower priority than the mobile flow.
3. **Download + Share** — same as mobile share view but in a centered modal
   rather than full-screen overlay.

---

## Backend Changes

### 1. Remove auto-generation from sync pipeline

The current Garmin/Strava webhook calls to `generate_runtoon_for_latest`
are removed. The sync pipeline no longer triggers Runtoon generation.

**Files to change:**
- `apps/api/tasks/garmin_webhook_tasks.py` — remove the
  `generate_runtoon_for_latest.delay()` call (~line 557)
- `apps/api/tasks/strava_tasks.py` — remove the
  `generate_runtoon_for_latest.delay()` call (~line 1090)

### 2. New endpoint: `POST /v1/activities/{id}/runtoon/generate` (modify existing)

The existing generate endpoint becomes the sole trigger for Runtoon
creation. It is called when the athlete taps "Share Your Run" from either
the prompt or the activity page. Response should include a task ID or
poll URL so the frontend can wait for completion.

### 3. New endpoint: `GET /v1/runtoon/pending`

Returns the most recent **share-eligible activity** — not a Runtoon, an
activity. This is a "share candidate" check. It answers: "Is there a
recent run this athlete might want to share?"

The `has_runtoon` field tells the frontend what to do next:
- `false` → tapping "Share Your Run" must trigger generation first (show
  skeleton, wait ~15-20s)
- `true` → a Runtoon already exists (e.g. athlete generated one from the
  activity page earlier). Skip generation, go straight to share view.

```json
{
  "activity_id": "uuid",
  "activity_summary": {
    "name": "Afternoon Run",
    "distance_mi": 13.0,
    "pace": "7:27/mi",
    "duration": "1:37:00"
  },
  "has_runtoon": false
}
```

Returns 204 if no eligible activity exists.

**Eligibility rules (all must be true):**
- Activity synced within the last 24 hours
- Activity is a running type (not cycling, swimming, etc.)
- Activity distance >= 2 miles (3,218 meters). Shorter runs are still
  shareable from the activity page — they just don't get the auto-prompt.
- `Activity.share_dismissed_at` is null (athlete hasn't dismissed this one)
- Athlete has 3+ photos uploaded and feature flag enabled
- Activity has NOT already been shared (no `RuntoonImage` with
  `shared_at` set for this activity)

### 4. New endpoint: `POST /v1/activities/{id}/runtoon/dismiss`

Marks the **activity** (not Runtoon) as dismissed for share prompting.
This is keyed by `activity_id` because the dismiss happens at prompt
time — before any Runtoon image exists. The dismiss action says "I don't
want to share this run," not "I don't want this image."

Sets `Activity.share_dismissed_at = now()`. The `/pending` endpoint
excludes activities where this timestamp is set.

### 5. Share tracking: `POST /v1/runtoon/{id}/shared`

Analytics event. Tracks which Runtoons were actually shared. Records
`shared_at` timestamp and `share_format` ("1:1" or "9:16").

`share_target` is best-effort telemetry — the Web Share API does NOT
reliably report which app the user selected. This column is nullable
and defaults to `"unknown"`. Do not build any logic that depends on
knowing the share target. It's there if the browser happens to report
it, otherwise ignored.

---

## Frontend Components

### 1. `RuntoonSharePrompt` (new — bottom sheet)

- Polls `GET /v1/runtoon/pending` on app mount and after activity sync
  events (via React Query with a 10s refetch interval, stops after first
  result or 10 minutes)
- Renders as a bottom sheet (slide-up animation, backdrop dim)
- Placed in the root layout so it works on any page
- Dismisses: swipe-down, "Not now" tap, or timeout
- Calls `POST /v1/activities/{id}/runtoon/dismiss` on dismiss (keyed by activity, not runtoon)

### 2. `RuntoonShareView` (new — full-screen overlay)

- Receives Runtoon data from the prompt
- Shows image, format toggle (1:1 / 9:16), Save, Share, Regenerate
- Uses Web Share API for native sharing
- Falls back to download + copy for desktop
- Manages regeneration state (polling, skeleton, attempt counter)

### 3. `RuntoonCard` (existing — modify)

- Stays on activity page for browsing/discovery
- Remove the download dropdown (it's now in the share view)
- Add a "Share" button that opens `RuntoonShareView`
- Keep the "Upload photos" CTA for users without photos (no change)

---

## Data Model Changes

### `Activity` table addition

| Column | Type | Purpose |
|--------|------|---------|
| `share_dismissed_at` | `timestamp, nullable` | When athlete dismissed the share prompt for this activity. Set by `POST /v1/activities/{id}/runtoon/dismiss`. The `/pending` endpoint excludes activities where this is set. This lives on `Activity` — not on `RuntoonImage` — because the dismiss happens before any image exists. |

### `RuntoonImage` table additions

| Column | Type | Purpose |
|--------|------|---------|
| `shared_at` | `timestamp, nullable` | When athlete shared (first share event) |
| `share_format` | `varchar(10), nullable` | "1:1" or "9:16" — which format was shared |
| `share_target` | `varchar(50), nullable, default "unknown"` | Best-effort telemetry only. Web Share API does not reliably report the selected app. Nullable, defaults to "unknown". No logic should depend on this value. |

---

## Mobile Detection

The bottom sheet prompt is mobile-only. Detection:

```typescript
const isMobile = typeof window !== 'undefined' &&
  (window.innerWidth <= 768 || 'ontouchstart' in window);
```

Desktop gets the activity page card + optional home page banner. No bottom
sheet on screens wider than 768px — it doesn't feel right on desktop.

---

## Web Share API Support

| Platform | Support | Behavior |
|----------|---------|----------|
| iOS Safari | Full (files) | Native share sheet with Instagram, iMessage, etc. |
| Android Chrome | Full (files) | Native share sheet |
| Desktop Chrome | Partial (no files pre-2025) | Fallback: download + copy caption |
| Desktop Safari | Partial | Fallback: download + copy caption |
| Firefox | Limited | Fallback: download + copy caption |

The key insight: **this is a mobile-first feature**, and both iOS Safari
and Android Chrome fully support `navigator.share({ files: [...] })`.
Desktop fallback is acceptable but not the primary experience.

---

## What NOT to Build

1. **Direct Instagram/Twitter API integration.** The Web Share API handles
   this natively without us maintaining OAuth tokens for social platforms.
   Don't build what the OS gives you for free.

2. **A "feed" of Runtoons.** This is a share tool, not a gallery. The
   activity page shows the Runtoon for that activity. There's no need for
   a separate Runtoons page or collection view.

3. **Push notifications.** The prompt only appears when the athlete opens
   the app. No push infrastructure exists yet, and building it for this
   one feature isn't worth the complexity. If push is added later for
   morning briefings or insights, Runtoon prompts can ride that system.
   Don't build a push system just for this.

4. **Auto-sharing.** Never. The athlete decides. The system prepares.

---

## Success Metrics

| Metric | Target | How |
|--------|--------|-----|
| Prompt → Share View open rate | >50% | Of athletes who see the prompt, half open it |
| Share View → Share/Save rate | >40% | Of athletes who open the view, 40% share or save |
| Runtoon generation → Shared rate | >25% | Of all generated Runtoons, 25% get shared |
| Time from sync to share | <60 seconds | Median time from activity sync to share tap |
| Regeneration rate | <20% | Most athletes are happy with the first image |

---

## Build Priority

1. **Backend:** Migration (`Activity.share_dismissed_at` + `RuntoonImage` share columns) + `/pending` + `/dismiss` endpoints + remove auto-gen from sync
2. **Frontend:** `RuntoonSharePrompt` bottom sheet (mobile)
3. **Frontend:** `RuntoonShareView` full-screen overlay with Web Share API
4. **Frontend:** Modify existing `RuntoonCard` to link to share view
5. **Analytics:** Share tracking endpoint + events
6. **Desktop:** Home page banner (optional, low priority)

---

## Decided

- **On-demand generation, not pre-generated.** Founder decision Feb 28.
  Generate only when the athlete taps "Share Your Run." Zero wasted API
  cost. 15-20s wait is acceptable and builds anticipation. Remove
  auto-generation from sync pipeline.

- **Prompt threshold: >= 2 miles.** Founder decision Feb 28. The
  automatic "Share Your Run" bottom sheet only appears for runs of 2+
  miles. Shorter runs (shakeout, warmup, test) don't get the popup.
  However, the "Share Your Run" button is always available on the
  activity page RuntoonCard for ALL runs regardless of distance — the
  athlete just has to navigate there and tap it. The prompt is the
  convenience layer; the activity page is the always-available fallback.

- **AI caption pre-populates in share text.** Founder decision Feb 28.
  The AI-generated caption is part of the experience — it's the
  surprise, like opening a gift. The caption auto-fills the Web Share
  API `text` field. The athlete sees what the AI wrote and can edit it
  before sharing if they want, but the default is the AI's take on
  their run. This is what makes Runtoons shareable — the image AND
  the caption are both generated, both personalized, both surprising.

---

*This spec is the builder's complete guide. Read it, build it in order,
test on mobile first. The desktop experience is secondary — this feature
lives and dies on the phone.*
