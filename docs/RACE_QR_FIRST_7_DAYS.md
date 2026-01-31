# Race QR Code: First 7 Days Experience

## Context
Runner scans QR code at packet pickup. They're about to race (or just finished). High intent, high emotion.

---

## Day 0: The Hook

**Where they are:** Standing at packet pickup, phone in hand, adrenaline building for tomorrow's race (or endorphins flowing from just finishing).

**What they see:**
1. Registration page with purple "Race Day Special" banner confirming their free trial
2. Connect Strava (one tap)
3. Brief intake: What's your goal? (dropdown: "Race faster" / "Stay healthy" / "Just curious")
4. **Immediate value:** Within 60 seconds of connecting Strava, they see:
   - Their VDOT calculated from recent race or best effort
   - "Based on your [5K time], here's what your training paces should be"
   - Today's training load status (fresh/tired/danger zone)

**The feeling:** "Holy shit, it already knows me."

---

## Days 1-3: The Insight That Hooks

**Day 1 (post-race):**
- Push notification or email: "How are your legs feeling after [Race Name]?"
- Coach gives recovery guidance based on their actual race distance and TSB
- Shows how long until they're ready to train hard again
- **Key insight:** "Your body needs X days before quality work. Here's why."

**Day 2:**
- They ask the coach something like "When can I run again?"
- Coach responds with actual data: their current TSB, how much load that race added, and a specific recommendation
- They see the difference between generic advice and *their* advice

**Day 3:**
- They get curious and explore: "What should my easy pace be?"
- Coach returns authoritative answer from VDOT calculator, not guesses
- They try a recovery run and it *feels right*
- **Key insight:** The paces aren't arbitrary numbers—they're derived from their actual performance

**The hook:** They've asked 2-3 questions and gotten answers that feel personal, not generic. The coach remembers context. It feels like talking to someone who's been watching their training.

---

## Day 7: The Decision Point

**What's happened:**
- They've recovered from race day
- They've asked the coach 3-5 questions
- They've seen their training load chart showing the race spike and recovery
- Maybe they've started thinking about their next goal

**Why they stay (convert to paid):**
1. **Trust established:** The paces worked. The recovery advice was right.
2. **Habit forming:** They opened the app 4-5 times without thinking about it
3. **Next goal emerges:** "If this worked for recovery, what about building to my next race?"
4. **Fear of loss:** "I've been using this for a week. My data is here. The coach knows me."

**Why they leave:**
1. Coach gave generic/wrong answer to a key question
2. Data didn't sync or was confusing
3. No clear reason to come back after recovery was done
4. Trial felt like a sales pitch, not a tool

---

## What This Means for Build Priorities

### Coach behavior
- Day 0-3: Be helpful, not pushy. They're recovering.
- Recovery questions should feel like talking to an experienced runner, not a doctor or a sales rep
- Pace questions MUST use the authoritative VDOT calculator (we fixed this today)
- Context matters: Don't recommend intervals to someone who raced 48 hours ago

### Onboarding copy
- Don't explain features. Show their data.
- First screen after Strava connect should be a personalized insight, not a tour
- The VDOT/pace calculation is the "aha moment" - make it visible immediately

### Which LLM to lean on
- Day 0-3 questions are often simple but high-stakes: "What should my pace be?" "When can I run again?"
- These need to be RIGHT, not elaborate
- GPT-4o-mini with proper tool access is sufficient for most
- Opus is for Week 2+ when they ask complex training plan questions

### Retention mechanics
- Day 3: Prompt them with something like "Ready to think about what's next?"
- Day 5: If they haven't engaged, surface an interesting insight from their data
- Day 7: Soft nudge about trial ending, but lead with value not urgency

---

## The Single Sentence

**A runner who scans our QR code should feel, within 60 seconds, that we already understand their body better than any app they've tried—and by Day 7, they should trust us enough to plan their next race with us.**
