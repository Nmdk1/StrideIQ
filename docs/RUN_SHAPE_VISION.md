# Run Shape Intelligence — What You're Actually Building

Read this before you write a single line of code. This is not a technical spec.
This is the soul of the feature, written by the agent who scoped it with the
founder over hours of conversation. If you build something technically correct
that misses what's described here, you will have failed.

---

## Start With The Runner

You just finished a workout. 6x800m on the track. You're standing there,
hands on knees, breathing hard, watch beeping. You open Strava. What do you
see?

A jagged pace line that looks like a seismograph. A table of laps with
numbers. Average pace: 6:42/mi. Average HR: 162. Twelve data points in a
grid. That's it. That's what the market leader gives you after the hardest
workout of your week.

You know something happened in that workout. You felt the fourth rep start
to bite. The sixth one you held on for dear life but something was different
about how you held on — you shortened your stride and increased turnover
instead of muscling through. Your recovery jogs felt longer than they
should have. But none of that is visible. The data that would show it exists
on their servers. They just don't show it to you.

Now open Garmin Connect. Five separate panels stacked vertically. Pace in one
box. HR in another. Cadence in a third. Elevation in a fourth. Each one has
its own axis, its own scale, its own tiny font. Your job is to mentally
overlay them — to hold the pace chart in your mind while your eyes move down
to the HR chart and try to see if that HR spike at minute 23 lines up with
the pace dip you think you saw three panels up. It's work. It's frustrating.
And after two years of doing it, you still can't extract the meaning that's
hiding in plain sight across those five boxes.

**This is the problem you are solving.**

---

## What The Athlete Should See

The athlete opens StrideIQ after that 6x800m workout. One chart. Dark
background, clean lines, no noise. The pace curve is smooth — not the
jagged second-by-second spikes, but a rolling average that shows the actual
shape of the effort. Six clear peaks where the hard reps were. Six valleys
where the recovery jogs brought them back down.

Underneath the pace line, the heart rate traces its own story — and here's
where it gets interesting. The pace peaks are consistent (3:12, 3:14, 3:11,
3:13, 3:15, 3:18), but the HR peaks are climbing (168, 170, 172, 174, 176,
179). The athlete can see this instantly because both metrics share the same
time axis on the same canvas. They don't have to mentally overlay anything.
The relationship between pace and HR is right there, in the visual
relationship between the two curves.

Elevation is not a line competing for attention — it's a subtle shaded fill
at the bottom, giving context without demanding focus. If there's meaningful
grade, the fill shifts color: green for flat, amber for moderate, red for
steep. So when the athlete sees a pace dip, they can glance down and
instantly see "oh, that was the hill section" without reading a number.

Cadence and stride length are toggle layers. Turn them on and they appear as
subtle secondary traces. Turn them off and the chart is cleaner. The athlete
controls the information density. Some runners want everything. Some want
just pace and HR. Both are right.

**The key insight: every layer shares the same time axis.** One crosshair
moves across all of them simultaneously. Hover at minute 23 and you see
your pace, HR, cadence, elevation, and grade at that exact moment. That
single interaction replaces five separate Garmin panels. That's the
simplification. That's why this is better.

---

## The Texture of the Data

Runners are scientists. Doctors. Attorneys. Engineers. Data geeks. They ran
in college and they still run at 57. They run their fastest on 70-mile weeks
with 20-mile long runs. They have theories about 24-28 mile long runs for
competitive marathoners, validated by watching Rory Linkletter train under
Jon Green. They listen to every running podcast and get frustrated because
they all regurgitate the same tired formulas.

These people LOVE seeing their data. The chart is not a vehicle for AI
insights. The chart is the product. The moment you finish a run and see the
shape of your effort rendered beautifully — that's the dopamine hit. That's
why you open the app. That's the stickiness.

A progressive long run should look like a descending staircase — pace
stepping down every two miles, HR rising in response, the gap between them
telling you whether you have more in the tank or you're redlining. A runner
who executes that well wants to see it. They want to screenshot it and send
it to their training partner. They want to show their coach. Make that
moment beautiful.

A fast finish should show the sudden pace drop in the last 2-3 miles with
the HR response — did the HR spike to match the pace, or did the runner
hold pace with controlled HR? That distinction is invisible in a split
table. It's obvious in a well-rendered chart.

Hill repeats should show the sawtooth pattern with the elevation fill
underneath explaining every pace variation. The runner shouldn't have to
wonder "why was rep 4 slower?" They should see the amber-colored elevation
fill under rep 4 and know it immediately — that one had more grade.

**An interval session is the most important use case.** 12x400m should show
twelve clean spikes with recovery valleys between them. The consistency (or
drift) of those spikes is the story of the workout. Did the runner hold
pace but with climbing HR? That's cardiac drift — they're working harder for
the same output. Did they slow down in the last four reps? That's
fatigue-induced pace decay. Did they speed up? That's a negative split
session — the most rare and rewarding pattern in interval training. All of
this is invisible in a split table. All of it is instantly visible in a
single well-rendered chart.

---

## Then The Coach Enters

Now imagine the same chart, and scattered along the timeline are small
markers — coachable moments. Not many. Three, maybe four per workout.
Each one pinned to a specific timestamp.

The runner taps one at minute 18 (the start of rep 5). The coach says:

> "Rep 5 was your steadiest rep. Your pace was 3:12 with HR at 174, but
> your cadence shifted — you were at 188 spm for the first four reps and
> hit 192 here. That usually means you shortened your stride and increased
> turnover to maintain pace at higher fatigue. That's a good adaptation.
> Your body found a more efficient gear when the legs got heavy."

The runner didn't notice the cadence shift. It happened unconsciously. But
the system saw it in the stream data, recognized the pattern, and surfaced
it. That's the moment where the product becomes indispensable. Not because
it told the runner something obvious — but because it told them something
TRUE about their own body that they couldn't have known without the data.

Another marker at minute 32 (the recovery jog after rep 8):

> "Your HR took 47 seconds to drop below 150 after rep 8, compared to
> 31 seconds after rep 4. Recovery is slowing. This is normal for the back
> half of an interval session, but the magnitude (50% longer recovery time)
> suggests you were approaching your session limit. The last four reps
> were productive but not free — you were earning them."

The runner knows they were tired. But "50% longer recovery time" is precise.
It's a number they can track across sessions. Next time they do 6x800m, they
can look at whether that recovery degradation improved. The system just gave
them a personal metric to track that they didn't know existed.

---

## The Coach's View: Why This Changes Everything

Right now, the AI coach in StrideIQ has access to aggregate metrics. Average
pace, average HR, total distance, split summaries. When an athlete asks
"how was my workout?" the coach can say "you averaged 6:42/mi at 162bpm,
which is consistent with your recent threshold sessions." That's better than
nothing but it's barely coaching. It's reciting numbers.

With stream data, the coach can see the SHAPE of the effort. It can detect:

- **Cardiac drift** — HR climbing at constant pace, the earliest signal of
  fatigue or insufficient recovery. Invisible in averages. Obvious in
  streams.
- **Pace decay** — the last third of a tempo run slowing by 5 seconds/mile.
  Was it fatigue? Was it a hill? The elevation stream answers immediately.
- **Decoupling** — the moment where pace and HR diverge from their earlier
  relationship. This is the single most important signal in endurance
  training and NO competitor surfaces it automatically.
- **Recovery quality between reps** — not just "did they jog?" but "how
  fast did HR come down?" and "is it taking longer as the session
  progresses?"
- **Effort consistency** — did the athlete execute even splits, positive
  splits, or negative splits? What does their pattern look like across
  the last 10 interval sessions?
- **Cadence/stride adaptations** — when the athlete maintains pace but
  shifts mechanics (shorter stride, higher turnover), that's a fatigue
  compensation strategy. The system can detect it and explain it.

This is what makes the coaching content around structured workouts
transformative instead of generic. The difference between "nice interval
session, try to stay more consistent" and "your first five reps were
textbook, but rep 6 showed a cadence shift and 50% longer recovery — you
were at your limit. Next session, consider stopping at 5 reps and building
from there" is the difference between a chat bot and a coach.

---

## The Comparison: Why They Come Back

The chart for one run is compelling. The chart for two runs compared is
addictive.

The athlete ran the same 10K route two weeks apart. Same distance, same
terrain. The comparison overlay shows both pace curves on the same canvas,
time-aligned. Where they diverge tells the whole story.

Two weeks ago, their pace was 7:15/mi for the first 4 miles, then they
faded to 7:45 in the last two. Today, they held 7:10 flat through all
six miles. The two curves overlap for the first half and then one stays
flat while the other droops. That visual IS the improvement. It's more
convincing than any metric, any percentage, any trend line. You can SEE
yourself getting better.

And the coach adds: "Your pace at the same HR dropped 12 seconds per mile
over two weeks. Your aerobic efficiency is improving — you're producing
more speed at the same cardiovascular cost. This is the adaptation we
expected to see from the past three weeks of threshold work."

That's the moment where the athlete connects the WORK to the RESULT. The
threshold sessions they've been grinding through for three weeks just
produced a visible, undeniable improvement on their favorite route. The
chart shows it. The coach explains it. The connection between training
stimulus and performance outcome is no longer something they have to take
on faith — they can see it.

THAT is why they come back. THAT is why they stay subscribed. THAT is the
moat.

---

## What This Is NOT

- This is NOT a dashboard. Do not build a page with six cards showing
  different metrics. That's what everyone else does. Build ONE canvas.
- This is NOT a data export tool. The point is not to show every number.
  The point is to show the SHAPE and let the athlete explore depth on
  demand.
- This is NOT an AI feature with a chart attached. The chart must be
  excellent with no AI at all. Beautiful, interactive, information-dense
  without being cluttered. Something a runner screenshots and sends to
  their training partner. The AI layer is what elevates it from excellent
  to indispensable.
- This is NOT Garmin or Strava with a different skin. If it looks like
  either of them, you've failed. Both of their charts are data displays
  from 2015. You're building a run review experience for 2026. F1
  telemetry aesthetic — the kind of data visualization that makes
  engineers jealous.

---

## The Technical Work Serves The Experience

When you build the `ActivityStream` model, you're not building a database
table. You're building the foundation that makes it possible for a runner
to see their 6th interval rep's cadence shift. Every technical decision
flows from: does this serve what the athlete sees and what the coach can
interpret?

When you build the `analyze_run_streams` coach tool, you're not building
a data analysis function. You're building the intelligence that turns a
beautiful chart into a coached experience — the thing that makes the
runner's training partner ask "how does your app know that?"

When you build the chart component, you're building the thing the runner
opens the app for. The thing that replaces their Garmin Connect ritual.
The thing that makes them feel like a professional athlete reviewing their
telemetry. Get this right and everything else follows — the engagement,
the retention, the word-of-mouth, the subscriptions.

Build the experience first. Let the experience dictate the architecture.

---

## One Last Thing

The founder built this app because they're a runner who wanted better
tools. They've read every book published on running. They ran in college.
They're 57, about to set a state record, and they coach their 79-year-old
father who will set one on the same day. Puma sponsors them. They listen
to running podcasts all day and get frustrated because the industry
regurgitates the same tired formulas.

They don't want a better Garmin. They don't want a better Strava. They
want to genuinely be an additive part of an athlete's journey — a trusted
partner in helping them build to their goals. Sometimes friend, sometimes
coach, sometimes advisor. Always N=1. Always understanding that every
runner's data tells a unique story.

This feature is where that vision becomes tangible. The chart is where the
athlete meets their own data for the first time as a narrative, not a
spreadsheet. The coach is where the narrative becomes a conversation.
Together, they create something no competitor has: a run review experience
that makes you smarter about your own body every time you open it.

Build something worthy of that vision.
