# Real-Time Audio Coach — Product Spec

**Date:** April 10, 2026
**Status:** SCOPED — not scheduled, build when prioritized
**Estimated effort:** 1-2 sprints (native mobile app required)
**Depends on:** Training lifecycle product (planned workouts with segments)

---

## What This Is

A real-time voice in the athlete's ear that watches what they're doing and
responds. Not an audiobook. Not a pre-recorded briefing. A coach that sees
your pace, knows your workout, and tells you what to do right now.

"Begin interval one."
[athlete runs]
"6:25 — right on your threshold target. Hold this."
[90 seconds later]
"Interval one done. Walk it out. 90 seconds rest."
[athlete rests too long]
"Time's up. Begin interval two when you're ready."
[athlete goes out too fast]
"6:05 — you're 20 seconds fast. This is effort three of eight. Save something."
[approaching the end]
"Last interval. Leave it all out there."
[cooldown]
"Eight of eight. Average 6:28. Your fastest was number six. Cool down easy."

This is coaching. It requires knowing what's happening in real time and
deciding what to say based on it.

---

## Why No Competitor Does This Well

Runna has audio cues but they're device TTS reading scripted prompts —
"begin fast segment," "return to easy pace." No awareness of actual pace.
No adaptation. Robotic voice. Their users are begging for better.

Garmin reads pace numbers in a monotone at fixed intervals. No coaching
context, no workout awareness, no intelligence.

No consumer running product delivers real-time adaptive coaching with a
natural voice that knows the athlete's data, their workout structure,
their weather conditions, and their personal patterns.

StrideIQ has everything needed for the intelligence layer. The missing
piece is the delivery surface — a live connection to the athlete during
the run.

---

## Architecture

The athlete records with Garmin on their wrist (as they do now). StrideIQ
provides the coaching voice through a phone companion app that runs alongside.

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│ Garmin Watch │     │ StrideIQ Phone   │     │ StrideIQ    │
│ (records)    │────▶│ Companion App    │────▶│ Backend     │
│              │ BT  │                  │ API │             │
│ HR broadcast │     │ GPS tracking     │     │ Workout plan│
│              │     │ Audio cues       │     │ Paces/zones │
│              │     │ Coaching logic   │     │ Weather adj │
└─────────────┘     └──────────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ AirPods /    │
                    │ Earbuds      │
                    │ (athlete     │
                    │  hears cues) │
                    └──────────────┘
```

**Garmin stays the recorder.** We are not building a recording app. We are
not competing with Garmin for the watch screen. The athlete starts their
Garmin activity as usual. They also open the StrideIQ companion and tap
"Start Coach" on today's workout. The companion tracks GPS from the phone,
optionally receives HR broadcast from the Garmin via Bluetooth, and delivers
audio coaching through earbuds.

After the run, Garmin syncs the activity via webhook as it does today. The
companion app closes. The coaching session data (cues delivered, pace at
each cue, athlete response patterns) is logged for future improvement.

---

## What the Coach Knows (intelligence inputs)

All of this already exists in the backend:

- **Today's planned workout** — segments, distances, target paces, rest durations
- **Weather-adjusted paces** — dew point, temperature, heat adjustment percentage
- **Athlete's Operating Manual** — "you perform better when first intervals are
  controlled," "your efficiency drops after mile 10," "your threshold ceiling
  is 6:25"
- **RPI paces** — exact pace targets per workout type
- **Race context** — "27 days to the Coke 10K"
- **Historical performance** — "your fastest 800 this cycle was 2:52"
- **Fingerprint** — recovery patterns, quality spacing preferences

The companion app downloads the workout context (one API call before the run
starts) and runs the coaching logic locally. No streaming API calls during
the run. No dependency on cell coverage mid-run.

---

## What the Coach Says (cue types)

### Segment transitions
- "Warm up at 8:30 pace. I'll let you know when to start."
- "Warm up complete. Begin interval one when you're ready."
- "Interval done. Rest for 90 seconds."
- "Begin interval two."
- "Last one."
- "Cool down. Easy pace. Well done."

### Pace feedback (adaptive)
- "6:28 — right on target."
- "You're running 7:45. Your easy ceiling is 8:05. You're fine."
- "6:05 — you're 25 seconds fast. This is interval three of eight. Save something."
- "You've slowed to 7:10 — that's below threshold. Pick it up if you can, or
  hold what you've got."

### Heart rate feedback (when HR broadcast available)
- "Heart rate is 165 — you're in your threshold zone."
- "HR is climbing past 175. Ease back slightly."
- "Heart rate recovered to 120. Ready for the next one."

### Distance/time markers
- "One mile. 8:02."
- "Halfway. You're on pace for a 42:30 finish."
- "Two miles to go."

### Contextual (from Operating Manual / weather)
- "Dew point is 72 today. Expect paces to feel 5% harder than normal."
- "Your data shows you negative split best when the first half is controlled."

### Post-workout summary (spoken)
- "Eight intervals complete. Average 6:28 per 800. Fastest was number six at
  6:18. Slowest was number eight at 6:41 — normal fatigue pattern. Total
  distance 9.2 miles including warm up and cool down. Good session."

---

## Coaching Logic (on-device, not server)

The coaching decisions run on the phone, not the server. This ensures
zero-latency cues and works without cell coverage.

Decision rules (examples):

```
IF current_pace < target_pace - 15s/mi AND segment_type == "work":
    speak("You're running [pace]. Target is [target]. Ease back.")
    cooldown: 60s before next pace cue

IF current_pace > target_pace + 20s/mi AND segment_type == "work":
    speak("You've slowed to [pace]. Pick it up if you can.")
    cooldown: 45s

IF distance_in_segment >= segment_target_distance:
    speak("Interval [n] done. [rest_instruction].")
    transition to rest segment

IF time_in_rest >= rest_duration:
    speak("Ready. Begin interval [n+1].")
    transition to work segment

IF distance_total % 1_mile == 0:
    speak("[mile_number] miles. [pace].")
```

These rules are downloaded with the workout context. More sophisticated
rules can reference the athlete's Operating Manual findings:

```
IF interval_number == 1 AND finding("controlled_first_interval"):
    speak("Stay controlled on this first one. Your data shows it pays off.")
```

---

## Technical Requirements

### Native Mobile App (React Native)

A PWA won't work reliably. iOS Safari kills background web processes when
the screen locks. Runners lock their phones. The coaching must continue
when the phone is in a pocket with the screen off.

React Native provides:
- Background GPS tracking (react-native-background-geolocation)
- Background audio playback (keeps the app alive via audio session)
- Bluetooth LE for Garmin HR broadcast (react-native-ble-plx)
- Offline capability (workout context downloaded before start)

### Voice Generation

Two options:

**Option A: Pre-generate all possible cue fragments per workout.**
Before the run, generate ~30-50 short audio clips via OpenAI TTS:
"Begin interval one," "Begin interval two," ... "6:20," "6:25," "6:30,"
... "Ease back," "Pick it up," "Right on target," etc. Store on device.
The coaching logic assembles and plays the right clips in real time.
Latency: near zero (local playback). Voice quality: excellent.
Cost: ~$0.01 per workout (50 clips × ~20 chars each = 1,000 chars).

**Option B: On-device TTS.**
Use the device's built-in TTS engine. iOS Neural voices (Siri voice) are
significantly better than old "Samantha." Android TTS is also improved.
Latency: near zero. Cost: zero. Quality: good, not great.

**Recommendation: Option A with Option B as fallback.** Pre-generate the
workout-specific clips (segment transitions, target paces) via OpenAI TTS
for natural voice. Use on-device TTS for dynamic real-time cues (actual
pace numbers, HR feedback) that can't be pre-generated because they depend
on what happens during the run. The athlete hears a consistent warm voice
for planned cues and a slightly different but still natural voice for
adaptive feedback.

### Garmin HR Broadcast

Many Garmin watches support Bluetooth LE heart rate broadcast mode. The
athlete enables "Broadcast Heart Rate" in Garmin settings. The companion
app pairs via BLE and receives real-time HR. This is optional — GPS-only
coaching (pace-based) works without it. HR adds cardiovascular feedback.

### Battery

GPS + BLE + audio for a 2-hour long run. Typical impact: 15-20% battery
on modern phones. Acceptable for most athletes. Include a battery warning
if starting below 30%.

---

## MVP Scope (what to build first)

1. React Native app shell (iOS first — primary athlete platform)
2. Background GPS tracking with pace computation (rolling 30-second average)
3. Workout context download from StrideIQ API (one call at start)
4. Segment transition logic (warm up → work → rest → work → ... → cool down)
5. Pre-generated voice clips via OpenAI TTS (segment transitions + target paces)
6. On-device TTS for dynamic cues (actual pace, mile markers)
7. Basic coaching rules (too fast, too slow, on target, segment transitions)
8. Post-workout spoken summary
9. Audio plays alongside music/podcasts (audio session mixing)

**NOT in MVP:**
- Garmin BLE HR pairing (add after GPS-only coaching validates)
- Android (iOS first, Android fast follow if adoption proves out)
- Coaching session logging/analytics (add after core works)
- Operating Manual finding injection into cues (add after core works)
- Social/sharing features
- Any recording functionality (Garmin does this)

---

## Success Criteria

- Athlete completes an interval workout with live coaching from start to finish
- Segment transitions fire within 5 seconds of actual distance thresholds
- Pace feedback is accurate to ±5 seconds/mile
- Audio continues uninterrupted when phone screen locks
- Audio coexists with music playback (mixing, not replacing)
- Works offline after initial workout download (no cell needed during run)
- Battery impact < 20% for a 90-minute session

---

## Why This Matters

The morning briefing makes you open the app. The Operating Manual makes
you trust it. The real-time coach makes you need it. Every single run.

This is the product that makes StrideIQ feel like a person standing next
to you at the track, not a website you check after the run.
