# StrideIQ Native App — Product Spec

**Date:** April 10, 2026
**Status:** PRELIMINARY — vision document, not build-ready
**Framework:** React Native + Expo (shared React knowledge, single codebase iOS + Android)

**BLOCKING DEPENDENCY:** This spec cannot be finalized until usage telemetry
has been running on the web app for a minimum of 4 weeks with real athlete
data. The screen priorities, navigation hierarchy, default tab selection,
pre-caching strategy, and push notification content in this document are
based on founder intuition and two data points (founder + Adam). Before
committing native development resources, we need evidence from all active
athletes showing:

- Which screens carry daily engagement (home vs calendar vs activity vs coach)
- Entry point patterns per athlete (what they tap first after opening)
- Session depth (glance vs deep read, per screen)
- Feature adoption rates (nutrition, coach chat, Manual, analytics)
- Time-of-day usage patterns (morning briefing check, post-run review, evening)

**See:** `docs/BUILDER_INSTRUCTIONS_2026-04-10_USAGE_TELEMETRY.md` for the
telemetry implementation that unblocks this spec.

---

## What This Is

The web app was the right vehicle to build the intelligence layer. The
intelligence layer is built. Now the product needs the surface it deserves.

This is not a wrapper around a website. This is a native app designed from
scratch around one idea: the athlete's day. Everything the athlete needs —
before, during, and after their run — in one experience that feels like it
was made by people who run.

---

## The Daily Experience

The app adapts to the time of day and the athlete's state. There is no
"home page." There is TODAY.

### Morning (wake up → pre-run)

The athlete wakes up. Lock screen notification:

> "Threshold day. 3×9min at 6:45/mi (adjusted for heat). HRV trending up."

They tap. The app opens to a single scrollable surface:

**Briefing card.** The morning voice — the same intelligence that powers
the web briefing, but spoken aloud if they want it. Tap the play button,
put the phone down, brush your teeth, listen to your coach tell you what
matters today. Or read it. Their choice.

**Today's workout.** Not a row in a calendar grid. A full card:
- Workout type, title, and purpose ("This session targets your VO2max
  ceiling, which the plan engine identified as your primary limiter")
- Target paces — weather-adjusted, with the adjustment visible
  ("6:45/mi — adjusted from 6:30 for 82°F dew point")
- Segment breakdown — warm up, work intervals, rest, cool down
- Estimated duration and distance
- **Start Coach** button — the primary CTA on workout days

**Wellness strip.** Sleep, HRV, resting HR, readiness — horizontal cards
with trend arrows. Not numbers dumped on a screen. Each one says what it
means for TODAY:
- Sleep: "5.3h — below your 6.2h cliff. Expect effort to feel harder."
- HRV: "42ms — trending up from 38 three days ago. Recovery is working."
- Readiness: "Moderate. Your data says this is fine for threshold work."

**Nutrition target.** A single ring showing daily target progress.
"2,850 cal — hard day. 160g protein." Tap to expand. Log breakfast with
one photo.

**Tomorrow preview.** A quiet line at the bottom: "Tomorrow: Recovery run,
45 min easy." The athlete always knows what's next.

### Pre-run

The athlete taps **Start Coach** on today's workout.

The screen simplifies to a pre-run checklist:
- GPS acquired (green dot)
- HR broadcast connected (green dot, or "Skip — pace only")
- Weather: 82°F, 71% humidity, dew point 72°F
- Paces loaded: threshold 6:45, easy 8:30, warm up 8:30
- "Start" button pulses gently

They tap Start. The phone goes in the pocket. Earbuds are in. The voice
begins: "Warm up at 8:30 pace. I'll check in at 10 minutes."

Garmin records. StrideIQ coaches.

### During run

The phone is in a pocket. The screen is off. Everything is audio.

Real-time coaching cues based on GPS pace and workout structure. Segment
transitions, pace feedback, distance markers, HR alerts (if connected).
Coexists with music — the coaching voice ducks the music momentarily for
each cue, then the music comes back.

If the athlete glances at the phone (e.g., waiting at a light), the lock
screen shows a minimal display:
- Current segment: "Interval 3 of 8"
- Current pace: "6:28/mi"
- Elapsed / remaining
- Heart rate (if connected)

### Post-run

Garmin syncs. The activity appears in the app within minutes (webhook push
notification → the athlete taps → activity detail).

**Run Shape.** The signature visualization — pace drift, cadence lock,
cardiac drift, efficiency. Native rendering, not a WebView. Smooth.
Buttery. 60fps scrubbing.

**Pace-colored map.** Native MapKit (iOS) / Google Maps (Android). Not
Leaflet in a div. Pinch to zoom, rotate, tilt. The route glows with pace
color. Elevation profile below, interactive — scrub and the dot moves on
the map. Ghost traces for repeat routes at whisper opacity.

**Interval summary.** If structured workout: table with work/rest segments,
paces, HR, fastest/slowest. The same data as the web but rendered natively
with smooth expand/collapse animations.

**"What does the data say"** — one-tap coach analysis. The same LLM-powered
analysis as the web coach, but presented as a card that expands inline, not
a chat window.

**Nutrition prompt.** A gentle card: "Post-run recovery window. Log your
meal?" Tap → camera opens → AI identifies food → macros populate → confirm.
One-tap for athletes who always eat the same post-run meal (meal templates
from history). Barcode scanner for packaged foods.

### Evening

**Check-in.** Two taps, not a form. "How do your legs feel?" [slider: 1-5].
"Mindset?" [slider: 1-5]. Done. These feed the correlation engine.

**Tomorrow's workout.** Expanded preview: tomorrow's session with paces,
weather forecast, and context. The athlete goes to bed knowing exactly
what they're doing in the morning.

**Weekly summary.** Once a week (Sunday evening): the LLM-interpreted
weekly digest. Not a database dump. A coach's note about the week.

### The Manual

Swipe right (or tap the second tab) to reach the Operating Manual. The
athlete's living science document:

- **Cascade stories** — multi-factor findings rendered as narrative cards
- **Race character** — the counterevidence section, "During training X
  predicts Y, but on race day you override this"
- **Domain wheel** — the knowledge completeness visualization
- **Change detection** — "New since your last visit" badge with delta
  highlighting

This page is the athlete's identity in data. It grows every week.

### The Calendar

Swipe left (or tap the third tab). Not a grid of boxes.

A vertical timeline. Days flow downward. Past is muted, future is vivid.
Today is highlighted. Each day shows the workout type icon, title, and
a thin intensity bar (color-coded: green easy, yellow moderate, red hard,
blue recovery).

Pinch to zoom: day view → week view → month view → season view. At season
scale, the periodization phases are visible as color bands — base (blue),
build (yellow), peak (orange), taper (green), race (red).

Tap any workout for detail. Long-press to move to a different day
(drag and drop). The plan adjusts.

---

## Design Language

### Dark by default

The app is dark. Not "dark mode as an option." Dark is the identity.
Deep blacks, not dark grays. Accent colors are specific and meaningful:
- Amber: the intelligence layer (findings, insights, coaching voice)
- Green: positive (on pace, good readiness, recovery complete)
- Red: intensity (hard effort, high HR, threshold/interval work)
- Blue: calm (easy runs, recovery, maintain mode)
- White: primary text, data, the athlete's numbers

### Typography

One typeface. Clean sans-serif. Large numbers for metrics (the athlete
is looking at this while sweating, one-armed, squinting). Small labels.
High contrast. No decorative fonts.

### Motion

Every transition has purpose. Cards expand from the content that triggered
them (tap a workout → the card grows into detail view, not a page push).
Numbers animate when they change. The readiness score counts up when it
loads. Pace colors sweep across the route polyline from start to finish
when the map first renders.

Nothing moves just to move. Every animation communicates state change.

### Haptics

- Light tap: card press, toggle, selection
- Medium impact: workout starts, interval transition, new finding discovered
- Success: workout complete, plan generated, correlation confirmed
- Warning: HR above threshold, pace significantly off target

The phone is in the athlete's pocket during a run. Haptics communicate
through the body when audio isn't appropriate (e.g., a subtle buzz for
"begin next interval" if they have audio off).

### Sound

The coaching voice is warm and direct. Not robotic. Not overly enthusiastic.
Not a podcast host. A coach who's been watching and knows when to speak and
when to stay quiet. Silence is part of the coaching experience — the absence
of a cue means "you're doing fine."

---

## Offline-First Architecture

Everything the athlete needs for today is cached locally before they need
it. The app does not require internet to function during a run.

**Pre-cached at briefing time (4am or when briefing generates):**
- Today's briefing text and audio
- Today's workout with segments, paces, weather adjustment
- Coaching cue audio clips (pre-generated TTS)
- Map tiles for the athlete's common running area (if identifiable from
  route history)
- Tomorrow's workout preview

**Synced when connected:**
- Activity data (from Garmin webhook → push → background fetch)
- Correlation findings updates
- Operating Manual changes
- Nutrition database (USDA subset for common foods — ~5MB local)

**Never requires live connection:**
- Viewing today's workout
- Starting a coached run
- Logging nutrition (queues for sync)
- Check-in submission (queues for sync)

---

## Push Notifications

Notifications are how the app enters the athlete's day without them
having to remember to open it.

| Trigger | Notification | Time |
|---------|-------------|------|
| Briefing generated | "Your briefing is ready. [one-line summary]" | 6am local |
| Activity synced | "Your 14.0mi run is analyzed. Negative cardiac drift — strong." | Minutes after sync |
| New finding confirmed | "New discovery: your threshold improves after 2+ easy days." | When confirmed |
| Plan auto-renewed | "Your next training block is ready. Build — Block 3." | When generated |
| Recovery ending | "Recovery wrapping up. What's next?" | 3 days before end |
| Race countdown | "14 days to Coke 10K. Taper starts Monday." | Daily in final 2 weeks |
| Weekly digest | "Your week in review." | Sunday evening |

Notifications are earned, not spammed. Every notification contains
specific, personal information. Never generic. Never promotional.

---

## Widgets

### Lock screen (iOS)
Small: Today's workout type icon + distance
"Threshold — 8.2mi"

### Home screen small
Readiness circle (color-coded) + workout type
Visual glance without opening the app.

### Home screen medium
Full workout preview:
"8×800m at 6:00/mi | Start Coach →"
Plus weather badge and readiness.

### Home screen large
Today's view compressed: briefing headline, workout card, wellness strip.
The entire morning experience in a widget.

### Apple Watch complication
Workout type icon. Tap to open app on phone.
Garmin owns the wrist for the current athlete profile — serious masters
runners on Forerunner/Fenix. The complication is a glanceable reminder
of what's on the calendar.

**Future consideration:** As StrideIQ scales beyond the Garmin-first cohort,
athletes on Apple Watch Series 10 and Ultra 2 will arrive. These athletes
use Apple Watch as their primary running device. Runna's thread shows them
underserved everywhere — screen scrolling, connectivity drops, metric display
complaints. A lightweight Apple Watch companion app (workout display, segment
cues, haptic interval transitions) is a genuine opportunity. Not in V1, but
the React Native architecture supports watchOS extensions via Swift bridging
when the time comes.

---

## Camera & Nutrition

The camera is a first-class feature, not a browser permission prompt.

**Photo nutrition logging:**
1. Tap "Log Meal" (or the nutrition ring on today's view)
2. Camera opens instantly (native, not WebView)
3. Frame the meal, tap shutter
4. AI identifies food in ~2 seconds (Kimi K2.5 / GPT-4.1 Mini)
5. Ingredient list with portions appears
6. Athlete confirms or adjusts (tap any item to edit)
7. Macros auto-calculate from USDA database
8. Saved. Ring updates. Correlation engine receives the data.

**Barcode scanning:**
1. Tap barcode icon on nutrition screen
2. Camera opens with barcode overlay
3. Scan → product identified → macros auto-populate
4. Confirm → saved

**Fueling shelf:**
Quick-log drawer for the athlete's pre-saved gels, drinks, bars.
"Maurten 160" → one tap → 40g carbs logged. No photo needed.

---

## Technical Architecture

### React Native + Expo

- **Expo Router** for navigation (file-based, matches Next.js mental model)
- **React Native Reanimated** for 60fps animations
- **React Native Gesture Handler** for swipe/pinch/long-press
- **React Native MMKV** for fast local storage (offline data)
- **React Native Maps** (MapKit on iOS, Google Maps on Android)
- **Expo Camera** for nutrition photos + barcode scanning
- **Expo Notifications** for push notifications
- **Expo AV** for audio playback (coaching cues, briefing audio)
- **Expo Haptics** for tactile feedback
- **react-native-background-geolocation** for live GPS during coached runs
- **react-native-ble-plx** for Garmin HR broadcast pairing

### Shared code with web app

The API client layer (`lib/api/`) can be shared between web and native.
The API contracts are identical — the native app calls the same endpoints.
Authentication uses the same JWT tokens. No backend changes needed for
basic functionality.

### Backend additions

| Addition | Purpose |
|----------|---------|
| Push notification service (FCM + APNs) | Deliver notifications |
| `POST /v1/devices/register` | Register device token |
| Webhook → push bridge | Activity synced → push notification |
| Briefing → push trigger | Briefing ready → push notification |
| `GET /v1/workouts/{id}/coaching-package` | Offline workout + paces + weather + cue clips in one response |
| `GET /v1/workouts/{id}/audio-cues` | Pre-generated TTS clips for coaching |
| OpenAI TTS integration | Generate voice cues |

### App Store

- **iOS:** App Store review process. Requires Apple Developer account ($99/yr).
  Review typically 24-48 hours. No reason for rejection — no user-generated
  content moderation issues, no in-app purchases initially (Stripe billing
  stays on web), no restricted APIs.
- **Android:** Google Play. $25 one-time. Faster review. Same app via React Native.

---

## What the Web App Becomes

The web app does not go away. It carries features that benefit from
a wide viewport and persistent session:

- Admin and coach dashboards
- Coach chat (extended conversation sessions)
- Plan creation wizard (full parameter control with tune-up races, peak overrides)
- Settings, integrations, billing management

**Everything else lives in BOTH surfaces.** The native app is not a
simplified view of a complex product. It IS the complex product, designed
for touch instead of mouse.

### The depth constraint (non-negotiable)

A 57-year-old masters runner who has trained for decades is not intimidated
by data. They came to StrideIQ because they want to go deeper than any
other platform lets them. The Operating Manual, the full correlation
findings, the PMC chart, the 14-day wellness history, the cascade stories —
these are not web-only features that get stripped in the native app. They
are the reason the athlete pays.

What changes in native is not the depth of data — it is how you move
through it:

- The Operating Manual that requires horizontal tabs on web becomes a
  vertical scroll of expandable cards on native. Every finding, every
  cascade story, every domain — present and drillable.
- The PMC chart that requires a wide viewport on web becomes a
  pinch-to-zoom canvas on native. The athlete can zoom from 7 days to
  6 months with a gesture.
- The activity detail page with Run Shape, intervals, map, and splits —
  all present, stacked vertically with smooth expand/collapse.
- The Analytics page with efficiency trends, load-response, correlations —
  stacked scrollable sections with pinch-to-zoom on each chart.

**Screens that cannot be simplified (but are NOT the daily product):**

The Operating Manual and Activity Detail must render completely in native —
every finding, every cascade chain, every Run Shape chart and pace-colored
map. But these are the library, not the lobby. The founder visits the
Manual periodically, not daily. Activity detail is accessed from the home
page hero (founder pattern) or from the calendar day (Adam's pattern),
not as a destination in itself.

**The two screens that carry almost all daily value (PENDING TELEMETRY
VALIDATION):**

1. **Home / TODAY.** The briefing, the last run hero (effort gradient
   canvas), the compact PMC, the wellness strip, today's workout. This
   is what the founder sees every morning. This is the screen that
   determines whether the app feels alive or dead.

2. **Calendar.** The plan rendered as a timeline. Tap a day to see the
   workout or the activity. This is Adam's primary surface.

These two screens should receive the most design investment in native.
The Operating Manual, Analytics, Training Load, and other deep surfaces
are important but secondary in daily usage. Telemetry will confirm or
correct this assumption.

The daily driver framing does not mean shallow. It means always available,
always current, always complete, and designed for touch.

---

## What Makes This World Class

1. **It knows you.** The app never shows generic content. Every number,
   every word, every notification is about THIS athlete. The briefing
   references your sleep. The workout cites your limiter. The recovery
   prompt knows your race is in 14 days.

2. **It disappears during the run.** Phone in pocket, screen off, voice
   in ear. No fumbling with screens at mile 6. No squinting at a watch
   face. Just a coach who speaks when it matters and stays quiet when
   it doesn't.

3. **It's fast.** Everything is pre-cached. The app opens to TODAY in
   under 500ms. No loading spinners. No skeleton screens. Data is there
   before you look for it.

4. **It's beautiful.** The Run Shape canvas, the pace-colored map, the
   Operating Manual — these are already visually distinctive. Rendered
   natively at 60fps with smooth animations, they become the kind of
   thing athletes screenshot and share because it looks incredible.

5. **It respects the athlete.** No gamification trophies. No streak
   guilt. No "you missed a workout!" shame. The app informs. The
   athlete decides. Rest days are presented with the same respect as
   threshold days.

6. **It gets smarter.** Every week the Operating Manual grows. Every
   correlation confirmed makes the coaching voice more specific. Every
   race adds to the race character profile. The app the athlete opens
   in month 12 is fundamentally more intelligent than the one they
   opened in month 1. That compounding is visible and felt.

---

## The Line

> "The chart makes you open the app. The intelligence makes you trust it.
> The voice makes you need it."

This is the positioning statement. It belongs in the App Store description,
the pitch, the race day conversation with athletes. It is the product
story in three sentences. It is permanent.

The web app delivered the chart and the intelligence. The native app
delivers the voice — both literally (audio coaching) and figuratively
(a product that speaks to the athlete throughout their day, not just
when they remember to open a browser tab).

This is the product that makes StrideIQ feel like a coach who's always
paying attention, not a website you visit after the run.

---

## Sequencing Note

The native app is the right next major build after the coaching dashboard
ships and there are 10-15 paying athletes validating the intelligence layer.
The correlation engine must be producing real findings for real athletes
before those findings appear on someone's lock screen. The credibility of
the product depends on the intelligence being right before it is amplified
by native distribution.

The web app got you here. The native app is how you scale.
