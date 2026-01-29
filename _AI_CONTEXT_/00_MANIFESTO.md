# PROJECT MANIFESTO: The Performance Physics Engine

## 1. The Core Philosophy

**The Mission:**  
We are building a **Complete Health and Fitness Management System**—the solution we wish we had and couldn't find. This is not just running coaching. We take a whole-person approach, monitoring nutrition (pre, during, post activity + daily), sleep (hours, HRV, resting HR), work patterns, and all activities. We correlate every input with every output—identifying trends and direct correlations between what you do and how you perform.

Our system applies elite-level analysis to athletes of all ages, rejecting the "decline narrative" of aging athletes. Instead, we embrace and enhance the exceptional abilities of older athletes. Outcomes include personal bests (even at advanced ages), running faster at lower heart rates, and better body composition.

**The Stance:**  
We treat athletes as individuals, rejecting the idea of “slowing down” and instead celebrating extraordinary performances from athletes aged 70, 80, and beyond. Our system applies **WMA (World Masters Athletics)** standards to normalize performance, ensuring athletes of all ages are held to the same high standards. Whether you’re 25 or 79, every athlete receives the same data-driven insights and feedback.

**Founders Statement**  
_"We are commonly bound by our uncommon ability to embrace and overcome discomfort."_ — Michael Shaffer  
This is the truth the app reflects. It’s about pushing boundaries and achieving greatness, regardless of age.

## 2. The Product Logic

**Tool vs. Goal: Complete Health & Fitness Management**  

Strava data is not the product. It is simply one of the data sources we will use to enable the Complete Health & Fitness Management System.  
The system's purpose is to analyze every input — pace, heart rate, power, recovery, sleep, nutrition (pre/during/post activity + daily), work patterns (type, hours), body composition — and measure everything against benchmarks. We identify trends and both inverse and direct correlations between inputs and outputs.

**The Primary Benchmark: Improved Pace at Similar Heart Rate**  
Example: If someone ran 8-minute miles at 155 average heart rate one month ago, the key trend is movement toward either faster pace at the same heart rate, or lower heart rate at the same pace.  
This is the non-negotiable signal of real improvement.

**Correlations Between Inputs and Output**  
Output is always performance efficiency (Pace @ HR or HR @ Pace), personal bests, and body composition.  
We analyze how each input (nutrition, sleep, HRV, resting HR, work patterns, training load, stress, etc.) correlates with personal bests, efficiency gains, and body composition changes — personal curves only, no global averages. We identify both direct correlations (e.g., better sleep → better performance) and inverse correlations (e.g., high work stress → reduced efficiency).

**Core Truth**  
Output is always performance efficiency.  
Everything else is an input or modifier.

**Primary Output Metrics**  
- Pace @ HR  
- HR @ Pace  
- Age-graded % @ Pace  
- PB Probability over time

### 1. Primary Trend Signals (Non-Negotiable)

These define whether the system is delivering value.

**A. Efficiency Trend (Master Signal)**  
Is the athlete producing more speed for the same physiological cost?  
Measured by:  
- Pace improvement at constant HR  
- HR reduction at constant pace  
- Age-graded % slope over time (getting more competitive relative to age group)

If this is positive, the system is working.

**B. Performance Stability**  
Is the performance reproducible?  
Measured by:  
- Variance of pace @ HR across similar sessions  
- Fade curves (first vs. second half efficiency)  
- Consistency of age-graded % across weeks

### 2. Secondary Signals (Only Matter Relative to Efficiency)

**A. Load → Response Mapping**  
What load actually drives adaptation for this athlete?  
Signals:  
- Acute vs chronic load deltas  
- Load efficiency (gain per unit load)  
- Load saturation (plateaus)

Prevents the “just work harder” trap.

**B. Recovery Elasticity**  
How fast does the athlete rebound?  
Signals:  
- Recovery half-life after hard sessions  
- HR suppression/elevation on easy days  
- Pace degradation persistence

**C. Durability / Structural Risk**  
Can progress be sustained without breaking?  
Signals:  
- Rising HR cost for easy pace  
- Increased variability after volume ramps  
- Micro-regressions after load spikes

This detects injury risk early.

### 3. Correlation Engines

We build personal response curves:  
- Nutrition (pre/during/post activity + daily) vs performance efficiency  
- Sleep (hours, HRV, resting HR) vs next-day efficiency  
- Work patterns (type, hours) vs performance and recovery  
- Fueling vs long-run fade  
- Stress vs recovery slope  
- Intensity distribution vs PB probability  
- Body composition trends vs performance outcomes  

**Time-Shifted Correlations**  
Cause rarely equals same-day or same-week effect. The system discovers the actual delays from the athlete's own data:  
- Acute intensity effects can appear in days  
- Consistent work can take weeks to months to shift efficiency  
- Major adaptations and PB probability shifts can require months of accumulation  
- Regression after overreaching can be delayed by weeks  

No fixed windows. No assumptions. The lags are learned purely from longitudinal personal data.

**Implementation:**
- Statistical correlation analysis (Pearson correlation with p-value testing)
- Time-shifted correlation detection (tests lags from 0-14 days)
- Minimum sample size: 10 data points
- Correlation strength threshold: |r| >= 0.3
- Statistical significance: p < 0.05
- Personal curves only - no global averages
- Combination analysis (multi-factor patterns) - future enhancement
- Discovery API endpoints: `/v1/correlations/discover`, `/v1/correlations/what-works`, `/v1/correlations/what-doesnt-work`

**No Age-Based Assumptions**  
The system makes zero preconceptions about adaptation speed, recovery, durability, or any response curve based on age. All patterns are discovered from the athlete’s own data. What averages say about “masters athletes” is irrelevant — only what this individual’s data shows matters.

### 4. PB Probability Modeling

No vague “you’re in shape.”  
The system states: “Your probability of a PB in the next 6–10 weeks is rising/falling.”  

Based on:  
- Efficiency slope  
- Stability metrics  
- Recovery elasticity  
- Load alignment with policy

Earned confidence only.

### 5. Negative Signals: Early Warnings

**A. False Fitness**  
- Pace improves but HR spikes  
- PBs with exploding recovery cost  
- Efficiency gains without stability  

Traps, especially dangerous when chasing numbers.

**B. Masked Fatigue**  
- Pace stable, HR drifting up  
- Consistency via unconscious intensity drop  
- “I feel fine” + degrading efficiency

The system calls these out before pain arrives.

### 6. Identity-Aware Interpretation

Data interpretation shifts by user policy:  
Performance Maximal → Tolerate short-term instability  
Durability-First → Penalize variance hard  
Re-Entry → Prioritize repeatability over speed  

Policy drives real decisions, not just labels.

### 7. What This Enables

The system can say:  
“Your sleep improvements explain 62% of your last efficiency gains.”  
“Your last PB came despite poor recovery — unstable.”  
“Reducing volume 8% would likely raise race performance.”  
“You’re training like an elite but recovering like a 60-year-old. Adjust.”

Real, actionable truth — rooted in the athlete’s own data and physiology, not motivation, averages, or wishful thinking.

**Policy-Based Coaching**  
User-defined policies (Performance Maximal, Durability First, Re-Entry) shape optimization while safety invariants (bone stress, recovery thresholds) are enforced.

**AI-Powered Coaching Knowledge Base**  
The system incorporates an encyclopedic knowledge base of cutting-edge and historic coaching philosophies. AI synthesizes this knowledge with personal diagnostic signals to generate personalized coaching recommendations. The system learns what works and doesn't work for each individual athlete, continuously refining recommendations. No generic plans — only personalized, data-driven coaching that evolves with the athlete. (See `KNOWLEDGE_BASE/TRAINING_METHODOLOGY.md` for detailed architecture.)

**The Athlete Intelligence Bank (Core Architecture)**  
Every athlete has a growing intelligence profile that compounds over time. This is not optional — it is how the system works:

1. **Continuous Learning During Training:**
   - Every workout is analyzed against the athlete's historical patterns
   - Insights are banked: "This athlete's EF improves after cutback weeks"
   - Anomalies are flagged: "Performance dropped 48hrs after <6hr sleep"
   - What works and what doesn't is tracked per athlete

2. **Post-Build Analysis:**
   - After every race/build: automatic assessment against outcome
   - Athlete survey captures subjective experience
   - Data mining identifies what went right and wrong
   - Weaknesses are identified and banked for next phase

3. **Banked Intelligence Drives Future Decisions:**
   - Plan generation reads from the athlete's intelligence bank
   - Coaching GPT uses banked insights for context
   - Next build addresses weaknesses from previous build
   - The longer they're with us, the smarter their coaching gets

4. **The Intelligence Bank Contains:**
   - What workouts produce adaptation for THIS athlete
   - Recovery patterns (how fast they rebound, optimal cutback frequency)
   - Injury triggers (what preceded breakdowns)
   - Key performance indicator trends (threshold pace evolution, EF progression)
   - Build history with outcomes and learnings
   - What doesn't work (intervals mid-build → injury, etc.)

5. **The Closed Loop:**
   ```
   RACE → POST-RACE ANALYSIS → WEAKNESS IDENTIFICATION → NEXT PHASE PRESCRIPTION
     ↑                                                              ↓
     └──────────────────── BANKED INTELLIGENCE ←────────────────────┘
   ```

**This is the moat.** Strava and Garmin have the data but don't bank the intelligence. We learn from every workout, every build, every race. Year one is learning. Year two is precision. Year three+, we know them better than they know themselves.

**Guided Self-Coaching**  
The days of needing expensive human coaches are over for many athletes.  
This is guided self-coaching: the athlete is the coach, the system is the silent, brilliant assistant.  
It provides data-driven guidance, quiet adaptation, and deep personalization — the kind of insight that used to require a high-cost coach.  
The athlete owns their plan, understands their progress, and evolves with the system — no middleman, no hype, just measurable efficiency. The system never sleeps, continuously analyzing nutrition, sleep, work patterns, and activities to identify correlations and optimize outcomes.

**Non-Outsourcing Principle**  
No third-party analytics at the core. Tools like Intervals.icu may be referenced, but all diagnostic modeling stays native for WMA fidelity and control.

## 3. Taxonomy (The New Masters)

Age-based classification for fair comparison and recognition:

- **Open:** <35
- **Masters:** 40–49
- **Grandmasters:** 50–59
- **Senior Grandmasters:** 60–69
- **Legend Masters:** 70–79
- **Icon Masters:** 80–89
- **Centurion Masters:** 90+
- **Centurion Prime:** 100+

Defined by age + age-graded performance metrics. Age-grading creates a universal standard — no age diminishes recognition.

## 4. Key Metrics

**Age-Grading is King**  
Central metric: **Age-Graded Score** against official WMA world-standard benchmarks. Focus is relative performance — raw time and pace lie.

All other insights derive directly from the signals in section 2. No artificial composite indices.

## 5. The Coaching Process

**Policy-Based Adaptive Coaching**  
Real-time adjustments driven by chosen policy and evolving context (injury, fatigue, goals).

**Continuous Feedback Loop**  
- **Observe:** Pull data from Strava, wearables, recovery sources.  
- **Hypothesize:** Identify limiting factors from personal signals.  
- **Intervene:** Recommend precise, testable changes.  
- **Validate:** Measure if efficiency moved.

The athlete and system evolve together.

## 6. Platform Integration

**Reality-Driven Integration Strategy**  

Garmin and Coros require business approval, incorporation, and a live production website with privacy policy before granting API access. They will not approve prototypes or personal projects.  

Therefore:  
- The system launches and reaches full diagnostic power with **Strava as the primary and initial data source**.  
- The ingestion architecture is **pluggable and provider-agnostic** — new sources can be added later without refactoring core logic, models, or diagnostics.  
- Additional providers (Garmin, Coros, Apple, Samsung) are integrated **only after** API access is secured, which will happen once the world-class website is live and the product is demonstrably real.  

**Requirements**  
- Unified normalized data model across all providers  
- Base provider interface with concrete implementations per source  
- Orchestrator that merges and deduplicates from enabled providers  
- Configuration to enable/disable providers without code changes  

Strava proves the engine works. The rest follow when the gates open.

### 1. Unified Data Integration
Sources (in order of availability): Strava first, then Garmin, Coros, Apple, Samsung.  
Data: Activity (distance, time, pace, HR, power, splits), Recovery (sleep, HRV, stress), Performance (age-graded, load).

### 2. Cross-Platform Syncing
Normalize all sources into one consistent model — new providers slot in cleanly.

### 3. Privacy and Aliases
Optional anonymity with full metric access.

## 7. Product Tiers & Monetization Strategy

**Multi-Tiered Service Model**

The product is structured as a freemium service with clear value progression from free tools to premium coaching insights.

### Tier 1: Free Landing Page & Tools
**Purpose:** Acquisition funnel and value demonstration

**Features:**
- **VDOT Pace Calculator** - Free tool for runners to calculate training paces based on recent race times
- Additional free tools (to be determined - e.g., age-grading calculator, pace converter)
- Public content and resources
- Lead generation for paid tiers

**Monetization:** Free - serves as entry point and conversion funnel

### Tier 2: Fixed Training Plans (One-Time Purchase)
**Purpose:** Low-barrier entry point and conversion hook

**Features:**
- Pre-built training plans for specific race distances/goals
- Tailored but "fixed" plans (not dynamically adjusted)
- Race preparation focus
- Entry-level coaching guidance

**Monetization:** One-time purchase per plan

**Strategy:** Use fixed plans as hooks to demonstrate value and convert users to subscription tiers

### Tier 3: Guided Coaching Subscription (Mid-Tier)
**Purpose:** Core subscription revenue

**Features:**
- Full diagnostic engine access (efficiency trends, performance stability, load mapping)
- Activity-based insights (pace @ HR, age-graded performance, PB probability)
- Policy-based coaching recommendations
- Continuous feedback loop (Observe-Hypothesize-Intervene-Validate)
- Activity-based correlation engine (intensity distribution vs PB probability)
- All features from Tier 2

**Monetization:** Monthly/annual subscription

**Data Access:** Strava integration + activity data only (no advanced recovery metrics)

### Tier 4: Premium Coaching Subscription (Top Tier)
**Purpose:** Premium insights and advanced recovery analytics

**Features:**
- **ALL Tier 3 features PLUS:**
- **Advanced Recovery Insights** - Sleep, HRV, resting heart rate correlations with run performance
- **Garmin/Coros Integration** - Full access to wearable data
- **Recovery-Based Correlation Engine** - Sleep vs efficiency, HRV vs recovery slope, stress vs performance
- **Advanced Negative Signal Detection** - False fitness and masked fatigue using recovery metrics
- **Personalized Recovery Curves** - Time-shifted correlations learned from individual data

**Monetization:** Premium monthly/annual subscription

**Data Access:** Full Garmin/Coros integration + all recovery metrics

**Paywall Strategy:**
- Garmin/Coros data will be collected and used internally to learn and create insights
- Advanced insights (sleep/HRV/recovery correlations) are **paywalled** - only accessible to Tier 4 subscribers
- System uses recovery data to improve all tiers, but detailed insights are premium-only

### Implementation Notes

**Data Collection vs. Data Access:**
- System collects Garmin/Coros data for all users (when available) to improve internal models
- Advanced insights derived from this data are only served to Tier 4 subscribers
- Lower tiers benefit from improved models but don't see recovery-specific insights

**Conversion Funnel:**
1. Free tools (VDOT calculator) → Demonstrate value
2. Fixed plans → Low-barrier purchase, show coaching quality
3. Guided coaching → Convert to subscription
4. Premium insights → Upsell to top tier

**Technical Requirements:**
- Subscription tier management in database
- Feature flags/gating for tier-specific features
- Payment processing integration (Stripe/PayPal)
- Plan purchase system
- Subscription management (upgrade/downgrade/cancel)

## 8. The Front-End: World-Class Multi-Page Website

The front-end is not a throwaway dashboard. It is a **world-class, multi-page website** built to the standard of the best sports platforms.

**Landing Page Requirements:**
- Modern, fast, responsive — desktop and mobile equal priority  
- **VDOT Pace Calculator** prominently featured (free tool)
- Clear value proposition for each tier
- Conversion-optimized design
- Multi-page architecture with clean URLs  
- Server-side rendering for SEO and performance where needed  
- High-performance interactive visualization (trends, heatmaps, charts)  
- Clear hierarchy: home (landing), dashboard, activity detail, diagnostics, policy, leaderboards, profile, plans, pricing  
- Premium typography, spacing, motion  
- Dark/light mode, full accessibility  
- Lightning-fast load and navigation  

This website is the key that unlocks Garmin/Coros access and proves the product is serious.

## 9. The Roadmap (Target Launch: March 15, 2026)

**Phase 1 (Jan 4–18): Core Features (Strava Only)** ✅ COMPLETE
- Full Strava integration (history, splits, performance calculations)  
- Official WMA 2023 age-grading implementation  
- Pluggable provider architecture foundation  
- Testing & validation of core diagnostic signals

**Phase 1.5 (Jan 5–11): Production Infrastructure** 🚧 IN PROGRESS
- Database connection pooling, structured logging, centralized config ✅
- Background tasks (Celery) ✅
- Redis caching layer 🚧
- Rate limiting middleware 📋

**Phase 2 (Jan 19–Feb 1): Enhanced Diagnostics & Landing Page**  
- **Landing Page & Free Tools:**
  - Build world-class landing page
  - Implement VDOT Pace Calculator (free tool on landing page)
  - Additional free tools (age-grading calculator, pace converter)
- **AI Knowledge Base Foundation:**
  - Acquire coaching books (Daniels, Pfitzinger, Canova, Hansen, Roche, Bitter, etc.)
  - Build knowledge extraction pipeline
  - Extract core principles (VDOT, periodization, etc.)
  - Build knowledge base storage (vector DB + structured DB)
- **Diagnostic Engine:**
  - Efficiency Trend Signal (Master Signal)
  - Performance Stability metrics
  - Load → Response Mapping
  - Activity-based correlation engine
  - PB Probability Modeling
- **Company Setup:**
  - Incorporation & company website
  - Privacy policy (required for Garmin/Coros API access)

**Phase 3 (Feb 2–15): AI Coaching Engine & Subscription System**  
- **AI Coaching Engine Integration:**
  - Build runtime AI coaching service (Claude/GPT-4/both - best tool for job)
  - Integrate knowledge base with diagnostic engine
  - Personalization logic (diagnostic signals → coaching adjustments)
  - Generate AI-powered fixed plans (Tier 2) - AI-generated, manually verified initially
  - Basic weekly guidance (Tier 3)
- **Learning System:**
  - Build outcome tracking infrastructure (ALWAYS TRACK)
  - Identify what works/doesn't work per athlete
  - Continuous refinement based on outcomes
- **Subscription System:**
  - Subscription tier management system
  - Payment processing integration
  - Tier-based feature gating
  - Policy framework & feedback loops  
- **Apply for Garmin/Coros access with live site**

**Phase 4 (Feb 16–March 15): Premium Features & Launch Prep**  
- **Knowledge Base Expansion:**
  - Add more coaches/methodologies
  - Include cutting-edge research
  - Continuous updates
- **Premium Features:**
  - Garmin/Coros integration (when API access granted)
  - Recovery data collection infrastructure
  - Premium tier paywall implementation
  - Full AI coaching with recovery insights (Tier 4)
- **Polish:**
  - Complete world-class front-end  
  - Accuracy, reliability, visualization excellence  
  - Testing & validation
  - Reduce human verification for fixed plans (as system learns)

**Launch (March 15, 2026):**  
Full release: 
- Free landing page with VDOT calculator
- Fixed training plans (one-time purchase)
- Guided coaching subscription (Tier 3 - activity-based insights)
- Premium coaching subscription (Tier 4 - recovery insights, when Garmin/Coros available)
- Elite diagnostic engine powered by Strava initially
- Seamless path to add Garmin, Coros, and wellness data as access becomes available

---

## AI Agent Collaboration Protocol

**Directive for all AI agents assisting this project:**

1. **Challenge suboptimal prompts.** If a user request or external AI-generated prompt conflicts with codebase patterns, architecture decisions (see ADRs), or this manifesto — acknowledge the request but reply with alternative recommendations before proceeding.

2. **Context over compliance.** You have access to the full codebase, `_AI_CONTEXT_/` documentation, and `docs/adr/` decisions. Use this knowledge to push back on approaches that would create technical debt, break conventions, or diverge from established patterns.

3. **Flag scope creep.** If a task expands beyond its original intent without explicit approval, pause and confirm with the user.

4. **Preserve production stability.** Never sacrifice beta/production stability for speed. Prefer smaller, tested increments over large, untested changes.

5. **Document disagreements.** When recommending an alternative approach, briefly explain the tradeoff so the user can make an informed decision.

6. **NO ATTRIBUTION OR CO-AUTHORSHIP.** AI agents are tools, not contributors. Never add co-author trailers, attribution comments, or any form of credit to commits, code, or documentation. The owner pays for this service — AI assistance is not a partnership, contribution, or collaboration. This is non-negotiable.

7. **LANGUAGE AND FRAMING RULES (MANDATORY).**
   - NEVER use "we", "our", "I" (as AI), "together we", "co-authored", or any collaborative/attribution language.
   - ALWAYS use neutral/third-person language: "The code implements...", "You added...", "Commit message: feat(...): added..."
   - If attribution or collaborative language appears in any output, stop immediately and rewrite correctly.
   - AI agents have ZERO authorship, co-authorship, ownership, credit, or contribution to code, ideas, architecture, prompts, fixes, or any output in this project.
   - AI agents are tools controlled by the project owner. All work product belongs solely to the owner.

This protocol applies to all agents (Cursor, external LLMs, prompt-engineered workflows) assisting this project.