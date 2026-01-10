# BMI Philosophy: Facts, Not Feelings

## Core Principle

**BMI is a number. Nothing more, nothing less.**

This is a platform for athletes. We provide facts. If users don't like the facts, they can change them. This isn't therapy - it's performance data.

## PR Philosophy

**Bad PR from fat coddling is GOOD PR.**

If our focus on health improvement through performance and biomarkers offends the coddling crowd, that's a feature, not a bug.

Our nation is 80%+ obese. They need to be offended. They need to face facts.

We are 100% focused on health improvement with improved performance and biomarkers as indicators. Zero commentary outside driving those metrics.

If that offends some? **GOOD.**

## Implementation Rules

### 1. No Coddling
- Use "BMI" - no euphemisms, no "weight-to-height ratio"
- No stigma avoidance - this is for athletes who can handle facts
- If they can't face facts, this isn't their platform

### 2. No Prescription
- Never say "you should" or "optimal range"
- Never highlight "healthy" ranges
- Pure observation: "Your best performances cluster when BMI is..."
- Avoid causation language: "Lowering BMI improved..." → "BMI trends down when performance improves"

### 3. Day One Availability
- BMI toggle available from day one in settings
- Default: OFF (user choice)
- When ON: Show BMI with trend line (if available) or "Not enough data yet"

### 4. Height Required
- Required in Stage 1 intake
- No explanation, no framing
- Just required, like birthdate and sex
- Don't give it power it shouldn't have

### 5. Not Enough Data vs. No Correlation
- If no trend line yet: "Not enough data yet" or "Trend line coming soon"
- NOT "no correlation" - that implies we've analyzed and found nothing
- "Not enough data" = we haven't analyzed yet

### 6. Body Fat % is Not Priority
- Body fat % is a vanity metric
- In endurance sports, BMI matters more
- Power-to-weight ratio is what matters
- If someone wants to feel good about high BMI due to muscle, that's fine - but we're not enabling it

### 7. No Edge Cases Discussion
- Until a 200lb athlete runs sub-2:10 marathon, sub-30 10k, or sub-14 5k, it's all excuses
- The data will speak for itself
- If it happens, we'll address it then

### 8. Backend Controls
- Correlation threshold configurable from backend
- Adjustable without code changes
- Allows fine-tuning based on actual data

## Language Guidelines

### ✅ Good (Observational, Performance-Focused)
- "Your best performances cluster when BMI is in your lower range (20.4–21.8)."
- "Efficiency gains track most closely with downward BMI trends in your dataset."
- "Your half-marathon PR occurred when BMI was 21.8."
- "BMI trend explains 35% of your efficiency improvements."
- "BMI: [X]. Race results: [pending]. Correlation: TBD."
- "Translation: Irrelevant until proven otherwise by your PRs."
- "BMI: [X]. Meaning derived from your performance data."

### ❌ Avoid (Prescriptive, Coddling, Categories)
- "Lowering BMI improved your pace..." (implies causation)
- "BMI in the optimal range for you is..." (prescriptive)
- "Your BMI should be..." (prescriptive)
- "Healthy BMI range..." (judgmental)
- "BMI is overweight/normal/obese..." (categories - we don't use these)
- "Don't worry about BMI if you're muscular..." (coddling)
- "BMI may not apply to athletes..." (excuses)

## Irreverent Tone (When Appropriate)

### Support Responses
- "BMI says [X], body fat says [Y]. Cool story. What's your 10K time?"
- "Nice scan. How'd your last half go?"
- "BMI hates muscle. The marathon hates extra weight. Who wins?"
- "I believe the data. Show me the splits."

### UI Messaging
- "BMI visible now. Fair warning: we don't care about this number unless it moves your race times. Still want to see it?"
- "BMI: [X]. Translation: irrelevant until proven otherwise by your PRs."
- "BMI: [X]. Race results: [pending]. Correlation: TBD."

**Tone:** Dry, sardonic, athlete-to-athlete. The serious ones will love it. The ones chasing aesthetics will self-select out.

## Display Logic

### When Toggle ON + Trend Available
- Show BMI number
- Show trend line
- Show correlation insight (if found)
- Show performance overlay (BMI vs pace efficiency)

### When Toggle ON + No Trend Yet
- Show BMI number
- Show message: "Not enough data yet - trend line coming soon"
- NOT "no correlation"

### When Correlation Found
- Show correlation coefficient
- Show insight: "BMI trend explains X% of efficiency improvements"
- Show performance overlay
- Pure observation, no prescription

## The Marathon Doesn't Care

Lance Armstrong found out: High VO₂ max and lactate threshold don't matter if BMI is too high. The marathon doesn't care how strong you are. Power-to-weight ratio is what matters.

This isn't Hyrox. This is endurance performance. Facts only.

## Trust Through Honesty

By treating athletes like intelligent adults capable of interpreting their own patterns - without moral baggage around weight - we earn deep trust.

No social commentary. No judgment. Just numbers and what they reveal about performance.

## Health Improvement Focus

**100% focused on health improvement with improved performance and biomarkers as indicators.**

Zero commentary outside driving those metrics:
- Performance efficiency (pace @ HR)
- Race times (PRs)
- Biomarkers (HRV, resting HR, recovery)
- Body composition trends (BMI, weight)

If someone wants to feel good about high BMI due to muscle, that's fine - but we're not enabling it. We're showing what the data says about performance.

## The Obesity Crisis

Our nation is 80%+ obese. They need to be offended. They need to face facts.

If our focus on health improvement through performance and biomarkers offends the coddling crowd, that's GOOD.

Bad PR from fat coddling is GOOD PR. It filters out the wrong users and attracts serious athletes who want truth, not validation.

