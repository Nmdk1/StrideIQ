# Version History

## Version 3.18.0 - Causal Attribution Engine & IP Protection (2026-01-10)

### The Moat Phase: Engineering the Intelligence

This release implements the core intellectual property that differentiates StrideIQ from all competitors. We've moved from "what correlates" to "what causes" performance changes.

### Module 1: Causal Attribution Engine (`causal_attribution.py`)

**The Brain** - Time-lagged causal inference for athlete-specific performance attribution.

**Dual-Frequency Analysis:**
- **Readiness Loop (0-7 days):** Sleep, HRV, Stress, Soreness, Resting HR
- **Fitness Loop (14-42 days):** Volume, Threshold %, Long Run %, Consistency, ACWR

**Granger Causality Testing:**
- Tests if input X at time t-k helps predict output Y at time t
- Discovers optimal lag for each input-output pair per athlete
- Provides statistical backing: "Sleep changes preceded efficiency gains by 2 days (Granger p<0.05)"

**N=1 Philosophy:**
- Population research informs questions, not answers
- If athlete's PRs correlate with low sleep and low HRV, that's the pattern we surface
- The athlete IS the sample

**API Endpoints:**
- `GET /v1/causal/analyze` - Full dual-frequency causal analysis
- `POST /v1/causal/explain-trend` - "Why This Trend?" explanations
- `GET /v1/causal/context-block` - GPT injection context
- `GET /v1/causal/readiness` - Readiness loop indicators only
- `GET /v1/causal/fitness` - Fitness loop indicators only

### Module 2: Provisional Patent Draft (`PROVISIONAL_PATENT_DRAFT.md`)

**The Shield** - IP documentation for USPTO filing.

**Key Claims Documented:**
1. N=1 Causal Inference methodology
2. Dual-Frequency Lag Analysis (Readiness + Fitness loops)
3. Granger Causality Detection for athletic inputs
4. Contextual Comparison with Ghost Baseline
5. Pattern Recognition Over Averages

**Differentiators from Prior Art:**
| Feature | Prior Art | StrideIQ |
|---------|-----------|----------|
| Baseline | Fixed zones, population averages | Dynamic ghost cohort |
| Causality | Simple correlation | Granger causality with lag detection |
| Time Analysis | Fixed 7d/28d windows | Dual-frequency with optimal lag discovery |
| Guidance | Prescriptive | Forensic ("data suggests...") |

**Filing Instructions:**
- Provisional application ready for USPTO
- 12-month priority window for non-provisional
- Cost estimates included ($320 micro entity)

### Module 3: Anonymized Data Export (`data_export.py`)

**The Asset** - GDPR-compliant data aggregation for acquisition value.

**Privacy Principles:**
- All PII stripped (name, email, location, GPS)
- Only mathematical relationships exported
- Explicit opt-in required
- GDPR Article 17 compliant (right to erasure)

**Consent Management:**
- `GET /v1/data-export/consent` - Check status
- `POST /v1/data-export/consent` - Opt in/out
- `POST /v1/data-export/erasure-request` - GDPR Article 17

**Admin Export:**
- `GET /v1/data-export/admin/summary` - Export preview
- `GET /v1/data-export/admin/export` - Bulk JSON/CSV export
- `GET /v1/data-export/admin/ml-training-data` - ML-ready format

**Anonymization:**
- Age groups, not exact ages
- Volume categories, not exact km
- Pattern prevalence across cohorts
- No absolute values that could identify individuals

**Tone:** "Your choice. Data stays yours."

### Files Created

**Services:**
- `apps/api/services/causal_attribution.py` - Granger causality engine
- `apps/api/services/data_export.py` - GDPR-compliant export service

**Routers:**
- `apps/api/routers/causal.py` - Causal attribution endpoints
- `apps/api/routers/data_export.py` - Data export endpoints

**Documentation:**
- `PROVISIONAL_PATENT_DRAFT.md` - USPTO provisional patent application

### Files Modified

- `apps/api/main.py` - Added causal and data_export routers

### Manifesto Alignment

All outputs follow manifesto principles:
- **Value-first insights:** Report what the data shows
- **No prescriptive language:** "Data hints X preceded Y. Test it."
- **Sparse/irreverent tone:** Forensic, not preachy
- **Athlete-specific data only:** N=1, population research informs questions only

---

## Version 3.17.0 - Security Hardening (2026-01-08)

### Security Headers Middleware
- Added `SecurityHeadersMiddleware` with industry-standard headers
- X-Content-Type-Options: nosniff (prevents MIME sniffing)
- X-Frame-Options: DENY (prevents clickjacking)
- X-XSS-Protection: 1; mode=block (legacy XSS protection)
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: disables camera, microphone, payment, etc.
- Strict-Transport-Security: 1 year with preload (production only)
- Content-Security-Policy: restrictive policy (production only)

### Account Lockout Protection
- Added `account_security.py` module
- Locks account after 5 failed login attempts
- 15-minute lockout duration
- Tracks attempts in 30-minute rolling window
- Prevents user enumeration (same response for non-existent accounts)
- Shows remaining attempts when approaching lockout

### Dependency Security Audit
- Fixed critical Next.js vulnerability (14.2.34 → 14.2.35)
- Addressed 13 CVEs including SSRF, cache poisoning, DoS
- All npm packages now passing audit

### Security Checklist
Created comprehensive `_AI_CONTEXT_/SECURITY_CHECKLIST.md`:
- Documents implemented vs pending security measures
- Implementation priorities for beta and production
- Cost estimates for security services

**Files Created:**
- `apps/api/core/security_headers.py`
- `apps/api/core/account_security.py`
- `_AI_CONTEXT_/SECURITY_CHECKLIST.md`

**Files Modified:**
- `apps/api/main.py` - Added SecurityHeadersMiddleware
- `apps/api/routers/auth.py` - Added account lockout logic
- `apps/web/package.json` - Updated Next.js to 14.2.35

---

## Version 3.16.0 - Deep Analysis & Garmin Integration (2026-01-08)

### Garmin Data Import
- Created Garmin export parser for HRV, Resting HR, Sleep data
- Imported 505 days of wellness data for analysis
- Merged wellness with Strava activities for correlation

### Wellness vs Performance Analysis
Analyzed correlation between wellness metrics and running efficiency:

**Key Finding: HRV Does NOT Predict Performance (for this athlete)**

| Factor | Correlation | Interpretation |
|--------|-------------|----------------|
| HRV → Efficiency | r = -0.069 | No effect |
| Resting HR → Efficiency | r = +0.046 | No effect |
| Sleep → Efficiency | r = +0.086 | No effect |

PRs were achieved on LOW HRV (19-30) and SHORT sleep (4.7-5.4h).

### What Actually Drives Improvement
Analyzed factors that correlate with efficiency gains:

| Factor | Correlation | Strength |
|--------|-------------|----------|
| Time → HR (dropping) | r = -0.582 | STRONG |
| Consistency Streak | r = +0.398 | MODERATE |
| Cumulative Volume | r = +0.308 | MODERATE |
| Long Run → Next Week Eff | r = +0.347 | MODERATE |

**Key Insight:** HR dropped 12 bpm over training period, efficiency improved 4.2%.

### Deep Analysis Report Product
Designed product specification for personalized analysis reports:
- One-time deep dive ($49-99)
- Monthly insights subscription ($15/mo add-on)
- Coach package ($199/athlete)

### Methodology Sanitization Continued
Created sanitized methodology documents:
- `02_TRAINING_ZONES.md` - Zone system without coach names
- `03_PERIODIZATION.md` - Training cycles
- `04_INJURY_PREVENTION.md` - Recovery and prevention

**Files Created:**
- `apps/api/scripts/import_garmin_export.py`
- `apps/api/scripts/correlate_wellness_to_strava.py`
- `apps/api/scripts/analyze_improvement_factors.py`
- `_AI_CONTEXT_/ANALYSIS_FINDINGS_2026_01_08.md`
- `_AI_CONTEXT_/PRODUCT/DEEP_ANALYSIS_REPORT.md`
- `_AI_CONTEXT_/METHODOLOGY/02_TRAINING_ZONES.md`
- `_AI_CONTEXT_/METHODOLOGY/03_PERIODIZATION.md`
- `_AI_CONTEXT_/METHODOLOGY/04_INJURY_PREVENTION.md`

---

## Version 3.15.0 - Agent Architecture & Methodology Sanitization (2026-01-08)

### AI Agent System Design

Designed the complete agent architecture for personalized AI coaching:

**Agent System:**
- OpenAI Assistants API as primary engine
- Persistent conversation threads (no "starting over")
- Tool-based data access (query_activities, get_training_load, etc.)
- Per-athlete memory and context

**Context Window (4 Tiers):**
- Tier 1: Last 7 days (full detail)
- Tier 2: Last 30 days (weekly summaries)
- Tier 3: Last 120-160 days (training block, phase detection)
- Tier 4: Career (PRs, injuries, what works)

**Usage Limits by Subscription:**
| Tier | Price | Queries/Month | Token Budget |
|------|-------|---------------|--------------|
| Free | $0 | 10 | 50K |
| Base | $5 | 50 | 250K |
| Pro | $25 | 300 | 1.5M |
| Team | $75 | 1000 | 5M |

### Methodology Sanitization

Created legally-safe methodology documentation without coach names:

**Files Created:**
- `_AI_CONTEXT_/METHODOLOGY/00_CORE_PRINCIPLES.md` - Core training principles
- `_AI_CONTEXT_/METHODOLOGY/01_WORKOUT_TYPES.md` - Complete workout library
- `_AI_CONTEXT_/ARCHITECTURE/AGENT_SYSTEM.md` - Agent architecture design

**Principles Extracted:**
1. Suit plans to athletes, not athletes to plans
2. Easy must be easy
3. Individualization is everything
4. Consistency beats intensity
5. Context changes everything
6. Show patterns, don't prescribe

### Michael's Training Profile

Documented the founder's story:
- Couch to 1:27 half marathon in 2 years
- Age 57
- While working 50 hours/week
- While reversing insulin resistance, obesity, and GERD
- Both PRs run while injured

**Files Updated:**
- `_AI_CONTEXT_/MICHAELS_TRAINING_PROFILE.md` - Complete training profile
- `_AI_CONTEXT_/NEXT_SESSION.md` - Session continuity notes

---

## Version 3.14.0 - Coaching Knowledge Base + Code Quality (2026-01-08)

### Comprehensive Coaching Knowledge Extraction

Extracted insights from 8 training books, synthesized with 5 coaches, created unified workout library.

**Books Extracted:**

| # | Book | Author | Key Insights |
|---|------|--------|--------------|
| 1 | Run Faster | Brad Hudson | Adaptive running, 9 workout types |
| 2 | Hansons Method | Luke Humphrey | Cumulative fatigue, 6 days/week |
| 3 | Fast 5K | Pete Magill | Goal-pace timing, Central Governor |
| 4 | Advanced Marathoning | Pete Pfitzinger | HR zones, medium-long runs |
| 5 | Daniels' Formula | Jack Daniels | VDOT, E/M/T/I/R zones |
| 6 | Science of Running | Steve Magness | Amplifiers/dampeners of adaptation |
| 7 | Perfect Race | Matt Fitzgerald | Pacing mastery, 30-second rule |
| 8 | 80/20 Running | Matt Fitzgerald | 80/20 intensity distribution |

**Unified Workout Library Created:**
- 8 workout zones, 40+ workout types
- Cross-referenced across Daniels, McMillan, Pfitzinger, Hudson
- Auto-classification rules for workout tagging
- Location: `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/WORKOUT_LIBRARY.md`

**Key Principles Captured:**
- Easy needs to be EASY (not 80/20 dogma)
- HRV as correlation, not prescription
- Positive splits valid for 5K (McMillan insight)
- RPE works for experienced runners, not beginners
- Build stress metrics from data, not self-report

**Code Quality Fixes:**
- Fixed API auth alias (`get_current_athlete`)
- Fixed 8 frontend TypeScript errors
- Fixed ESLint unescaped entities
- Fixed i18n type system for translations
- Fixed Recharts formatter types
- All builds passing (API + Frontend)

**Files Added/Modified:**
- `_AI_CONTEXT_/KNOWLEDGE_BASE/coaches/` - 8 new book extractions
- `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/WORKOUT_LIBRARY.md` - Unified library
- `apps/api/core/auth.py` - Added alias for backward compatibility
- Multiple frontend component fixes

---

## Version 3.13.0 - Coach-Inspired Features (2026-01-07)

### Runner Typing, Mindset Tracking, Consistency Streaks

Implemented insights from 5 elite running coaches:
- Greg McMillan, John Davis, Ed Eyestone, Andrew Snow, Jonathan Green

**New Features:**

**Runner Typing (McMillan-inspired):**
- Auto-classifies athletes as `speedster`, `endurance_monster`, or `balanced`
- Based on race performance across distances
- Tailors training recommendations

**Mindset Tracking (Snow-inspired):**
- "The mind is the limiter of performance"
- Added `enjoyment_1_5`, `confidence_1_5`, `motivation_1_5` to daily check-in
- Collapsible UI section for quick entry

**Consistency Streaks (Green-inspired):**
- "If you don't enjoy it, you won't be consistent"
- Tracks consecutive weeks meeting training targets
- Milestone celebrations (4, 8, 12, 16, 26, 52 weeks)
- At-risk warnings when streak might break

**New API Endpoints:**
- `GET /v1/athlete-profile/runner-type` - Get runner classification
- `GET /v1/athlete-profile/streak` - Get consistency streak
- `GET /v1/athlete-profile/mindset` - Get mindset summary
- `GET /v1/athlete-profile/summary` - Complete profile summary

**New Files:**
- `services/runner_typing.py` - Runner type classification engine
- `services/consistency_streaks.py` - Streak tracking service
- `routers/athlete_profile.py` - New profile endpoints

**Database Migration:**
- Added runner type fields to `athlete`
- Added streak fields to `athlete`
- Added mindset fields to `daily_checkin`

**Knowledge Base:**
- Added coaching philosophy docs for all 5 coaches
- Created synthesis document with integration recommendations

---

## Version 3.12.0 - US Age Group Records + Enhanced Age Grading (2026-01-07)

### National + Global Benchmarking

Athletes can now see their performance against BOTH world and US age-group records.

**New Records Database:**

| Age Group | 5K (M/F) | 10K (M/F) | Half (M/F) | Marathon (M/F) |
|-----------|----------|-----------|------------|----------------|
| **Open** | 12:51/14:12 | 26:33/29:56 | 59:36/1:04:02 | 2:04:38/2:18:29 |
| **M/W 40** | 13:38/15:19 | 28:00/31:32 | 1:01:18/1:08:50 | 2:08:24/2:28:40 |
| **M/W 45** | 14:44/16:03 | 30:18/33:10 | 1:06:52/1:13:30 | 2:19:29/2:37:06 |
| **M/W 50** | 15:09/17:07 | 31:18/35:30 | 1:09:00/1:17:45 | 2:26:22/2:49:57 |
| **M/W 55** | 16:04/18:22 | 33:01/38:00 | 1:13:40/1:23:24 | 2:38:15/3:02:00 |
| **M/W 60** | 16:59/19:28 | 35:15/40:44 | 1:18:10/1:29:42 | 2:49:47/3:17:30 |
| **M/W 65** | 17:56/20:48 | 37:32/43:29 | 1:22:30/1:35:48 | 2:58:48/3:31:26 |
| **M/W 70** | 19:16/22:29 | 40:18/47:15 | 1:28:54/1:44:00 | 3:13:44/3:52:32 |
| **M/W 75** | 21:06/22:41 | 44:26/50:14 | 1:38:12/1:50:18 | 3:33:50/4:04:23 |
| **M/W 80** | 23:43/25:44 | 50:20/55:00 | 1:52:00/2:02:30 | 4:05:15/4:34:38 |

**Three Layers of Context:**

Example: 45-year-old male runs 3:30 marathon

| Metric | Value | What It Means |
|--------|-------|---------------|
| **World Age-Grade** | ~59% | vs Kipchoge's WR adjusted for M45 |
| **US Age-Grade** | ~66% | vs US M45 record (2:19:29) |
| **Population Percentile** | ~58% | Faster than 58% of M 35-54 in dataset |

**Enhanced `AgeGradedResult`:**
- Added `us_age_grade_percentage` 
- Added `us_record_seconds`
- Both world and national benchmarks in one call

---

## Version 3.11.0 - Research Data LIVE (2026-01-07)

### 🎯 26.6 Million Training Records Now Powering Insights!

Downloaded and processed the actual Figshare Long-Distance Running Dataset.
"People Like You" comparisons are now backed by REAL DATA.

**Dataset Statistics:**
- **26,617,172** daily training records
- **36,412** unique athletes
- **2 years** of data (2019-2020)
- All 6 World Marathon Majors represented

**Race Data Available:**
| Distance | Sample Size | Use Case |
|----------|-------------|----------|
| 5K | 799,138 races | Percentile comparisons |
| 10K | 1,133,947 races | Race predictions |
| Half Marathon | 310,720 races | Progression tracking |
| Marathon | 66,298 races | "Your 3:45 is faster than X%" |

**Weekly Volume Baselines by Age/Gender:**
- M 18-34: Median 32.3 km/week (8,378 athletes)
- M 35-54: Median 32.9 km/week (16,972 athletes)
- M 55+: Median 33.5 km/week (2,173 athletes)
- F 18-34: Median 28.0 km/week (3,864 athletes)
- F 35-54: Median 31.2 km/week (4,629 athletes)
- F 55+: Median 34.5 km/week (396 athletes)

**New API Endpoints:**
- `POST /v1/population/research/volume` - Compare weekly km to 26.6M records
- `POST /v1/population/research/race` - Compare race time to your cohort
- `GET /v1/population/research/baselines` - Raw baseline data

**New Files:**
- `scripts/build_research_baselines.py` - Processes parquet → JSON baselines
- `apps/api/services/research_data/baselines/population_baselines.json` - Pre-computed stats

**Sample Insight:**
> "Your 45 km/week puts you in the 75th percentile of male runners aged 35-54.
> The median for your cohort is 32.9 km/week."

---

## Version 3.10.0 - Research Data Integration (2026-01-07)

### External Research Data Pipeline
Infrastructure for ingesting and processing external research datasets
to provide "people like you" comparisons.

**Key Principle:** Focus on RECREATIONAL athletes, not elites.
Regular people with jobs and lives who want to improve.

**Datasets Identified:**
- Figshare Long-Distance Running: 10M+ records, 36K+ athletes
- NRCD Collegiate Running: 15K+ race results
- Sport DB 2.0: Cardiorespiratory data
- Canberra Triathlete Metabolic Data

**New Services:**

`research_data/age_grading.py`:
- WMA age-grading factors for fair comparison
- Support for all standard distances
- Population percentile calculations
- Performance level classification (beginner → competitive)

`research_data/figshare_processor.py`:
- Data loader for Figshare CSV format
- Recreational athlete filtering (not elites)
- Athlete profile builder
- Population baseline generator
- Export to JSON for API use

`research_data/population_comparison.py`:
- "People Like You" comparison service
- Cohort classification (beginner, recreational, local_competitive, competitive)
- Peer comparisons for volume, frequency, consistency
- Progression assessment vs typical patterns
- Risk indicators from research patterns

**API Endpoints:**
- `GET /v1/population/compare` - Compare to peer cohort
- `GET /v1/population/progression` - Assess progression vs typical
- `GET /v1/population/insights` - Notable differences from peers
- `GET /v1/population/summary` - Complete comparison summary
- `GET /v1/population/cohort` - Your cohort classification

**Data Pipeline Script:**
`scripts/download_research_data.py`
- Downloads datasets from academic sources
- Processes and builds population baselines
- Sample mode for testing
- Exports JSON baselines for production use

**Pre-computed Baselines:**
Based on running research literature:
- Beginner: ~15 km/week, 7:00/km easy pace
- Recreational: ~32 km/week, 6:00/km easy pace
- Local Competitive: ~52 km/week, 5:10/km easy pace
- Competitive: ~75 km/week, 4:40/km easy pace

**Philosophy:**
- Study what helps REGULAR people improve
- Age-grade everything for fair comparison
- Focus on the 10-100 km/week population
- Never compare users to elites
- Data-driven, not rules-based

---

## Version 3.9.0 - Training Load System (2026-01-07)

### Training Load Calculator
Complete ATL/CTL/TSB tracking system for training stress management.

**TSS Calculation Methods:**
- hrTSS: Heart rate-based training stress (most accurate for running)
- rTSS: Running TSS based on pace vs threshold
- Estimated TSS: Duration/intensity heuristics when data limited

**Training Metrics:**
- ATL (Acute Training Load): 7-day exponential moving average (fatigue)
- CTL (Chronic Training Load): 42-day exponential moving average (fitness)
- TSB (Training Stress Balance): Form = CTL - ATL

**Features:**
- Per-workout TSS calculation with method transparency
- Daily load aggregation
- Trend detection (rising/falling/stable)
- Training phase detection (building/maintaining/tapering/recovering)
- Context-aware recommendations (non-prescriptive, manifesto-compliant)
- 60-day load history for charting

**API Endpoints:**
- `GET /v1/training-load/current` - Current ATL/CTL/TSB
- `GET /v1/training-load/history` - Daily load history
- `GET /v1/training-load/tss/{activity_id}` - TSS for specific workout

**Frontend:**
- Performance Management Chart (PMC) visualization
- ATL/CTL/TSB curves with TSB area fill
- Daily TSS bar chart
- Phase indicator with icons
- Educational section explaining metrics

**Database Updates:**
- Added to Athlete model:
  - `max_hr`: Maximum heart rate
  - `resting_hr`: Resting heart rate
  - `threshold_pace_per_km`: LT pace in seconds/km
  - `threshold_hr`: Lactate threshold HR
  - `vdot`: Current VDOT from race/test

---

## Version 3.8.0 - Run Analysis Engine (2026-01-07)

### Core Intelligence Layer: Run Analysis Engine
The heart of the platform - contextual analysis for every run.

**Architecture:**
- `RunAnalysisEngine` - Main engine class (~600 lines)
- Complete dataclass-based type system
- Pluggable trend detection and root cause analysis

**Workout Classification:**
- Automatic classification: Easy, Moderate, Tempo, Interval, Long Run, Recovery, Race
- HR-based and duration-based classification with confidence scores
- Foundation for future ML-based classification

**Input Snapshot System:**
- Captures ALL inputs leading up to a run:
  - Sleep (last night, 3-day avg, 7-day avg)
  - Stress and Soreness (current + rolling averages)
  - HRV and Resting HR (current + rolling averages)
  - Training load metrics (ATL, CTL, TSB placeholders)
  - Weekly context (days since last run, runs this week, volume)

**Historical Context Engine:**
- Multi-scale temporal analysis:
  - This Week: runs, volume, efficiency
  - This Month: runs, volume, efficiency
  - This Year: runs, volume, efficiency
- Similar workout finder - compares to same workout type
- Percentile ranking vs similar efforts

**Trend Detection:**
- Statistical trend analysis using linear regression
- Signal vs noise filtering with significance thresholds
- Efficiency trend (HR/pace ratio over time)
- Volume trend (weekly mileage progression)
- R-squared confidence scoring
- 3% change threshold for stability determination
- 5% change threshold for significance

**Root Cause Analysis:**
- Activated when declining trends detected
- Correlates efficiency changes with:
  - Sleep patterns
  - Stress levels
  - Soreness accumulation
  - Training volume changes
- Generates human-readable hypotheses with confidence scores

**Outlier & Red Flag Detection:**
- Statistical outlier detection (top/bottom 5% of similar workouts)
- Red flags for concerning patterns:
  - HR near maximum for extended periods
  - Quality sessions on minimal sleep (<5h)
  - Hard efforts with high stress + high soreness
- Non-reactive philosophy: flags don&apos;t trigger prescriptive advice

**API Endpoints:**
- `GET /v1/run-analysis/{activity_id}` - Complete analysis for a run
- `GET /v1/run-analysis/trends/efficiency` - Efficiency trend analysis
- `GET /v1/run-analysis/trends/volume` - Volume trend analysis
- `GET /v1/run-analysis/root-causes` - Root cause analysis for trends

**Frontend Component:**
- `RunContextAnalysis.tsx` - Complete visualization component
- Workout type badge with confidence
- Insights list
- Outlier/red flag cards
- Percentile comparison chart
- Trend cards with direction and magnitude
- Expandable pre-run state details
- Responsive design (mobile-first)

**Design Philosophy:**
- Look at EVERYTHING against each run
- Historical context at multiple time scales
- Compare to similar workouts
- Detect trends, not noise
- Don&apos;t react to single bad workouts
- Root cause analysis when trends emerge
- Suit analysis to athlete, not athlete to analysis

---

## Version 3.7.0 - Major Feature Scaffolding (2026-01-07)

### Educational System
- Onboarding tooltip tour for new users
- Empty state components with educational prompts
- Data quality indicator
- Weekly logging nudge (manifesto-aligned, no guilt)

### Internationalization (i18n)
- Full i18n infrastructure with React Context provider
- English, Spanish, Japanese translations complete
- Language selector component
- Prepared for German, French, Portuguese, Chinese

### Lab Results System
- Database schema for blood work tracking
- 20+ common biomarkers with athlete-optimal ranges
- API endpoints for CRUD and trend analysis
- Categories: iron, blood, vitamins, hormones, thyroid

### Voice Input for Nutrition
- Web Speech API integration for browser voice input
- Natural language parsing for meals
- Scaffold for Whisper API (future)

### Race Profiles Database
- Schema with course characteristics
- Pre-seeded: Boston, Tokyo, Berlin, Chicago, NYC, London
- Elevation, weather, difficulty, pacing notes

### Knowledge Base Structure
- Document templates for Michael's coaching knowledge
- Periodization framework template
- Race-specific prep templates
- Knowledge extraction interview (18 questions)

---

## Version 3.6.0 - Production Ready (2026-01-07)

### Critical Fixes
- Fixed `Optional` import in strava_webhook.py
- Fixed `UUID` import in perception_prompts.py
- Fixed `RateLimitMiddleware` import in main.py
- Fixed `admin` router import in main.py

### PWA Complete
- Generated PWA icons (192x192, 512x512)
- Generated favicon.ico
- All manifest.json requirements satisfied

### Testing Complete
- All 14 frontend pages returning 200
- All public API endpoints verified working
- VDOT calculator: ✅
- Age-grade calculator: ✅
- Health endpoint: ✅

---

## Version 3.5.0 - Cross-Platform Mobile Support (2026-01-07)

### PWA Support
- `manifest.json` for add-to-homescreen (iOS/Android)
- Apple web app metadata for iOS standalone mode
- Theme color for address bar styling

### iPhone/iOS Specific
- Safe area insets for notch and home indicator
- `viewport-fit: cover` for edge-to-edge
- Prevented iOS input zoom (16px min font)

### Touch & Mobile UX
- 44px minimum touch targets (Apple HIG compliant)
- Range slider styling for iOS/Android
- Mobile nav with scroll support
- Dashboard controls stack on mobile

### CSS Utilities
- `.safe-area-bottom` / `.safe-area-top`
- `.touch-target` for minimum 44px
- `.scrollbar-hide` for cleaner mobile
- Global range slider cross-browser styling

### Documentation
- `CROSS_PLATFORM_CHECKLIST.md` with testing procedures

---

## Version 3.4.0 - SEO & Launch Prep (2026-01-07)

### SEO Fixes
- **robots.txt**: Added with proper disallow rules for protected pages
- **sitemap.ts**: Dynamic sitemap generation for Next.js
- **Meta Tags**: Enhanced with keywords, OpenGraph, Twitter cards
- **Title Template**: Page-specific titles with template

### Legal Pages (required for beta + API access)
- **Privacy Policy** (`/privacy`): Comprehensive data handling disclosure
- **Terms of Service** (`/terms`): Legal terms with health disclaimer

### Documentation
- **SITE_AUDIT_REPORT.md**: Comprehensive audit with action items
  - UX improvements
  - Performance tweaks  
  - Mobile responsiveness
  - SEO recommendations
  - Launch strategy for bootstrapping

---

## Version 3.3.0 - Friction-Free Check-in + UI Fixes (2026-01-07)

### Friction Reduction
- **Morning Check-in Page** (`/checkin`): Ultra-fast daily check-in
  - 3 sliders (Sleep 0-12h, Stress 1-5, Soreness 1-5)
  - 2 optional number fields (HRV, Resting HR)
  - Designed to complete in <5 seconds
  - Green "Check-in" button in navigation for logged-in users

### Bug Fixes
- Fixed pricing buttons (were `<button>` elements, now `<Link>` to `/register`)
- Fixed all ESLint unescaped entity errors
- Fixed TypeScript errors in dashboard, profile, and SplitsChart
- Fixed API client HeadersInit type for Authorization header
- Added missing `role` and metrics fields to Athlete type

### API Endpoints
- `POST /v1/daily-checkin` - Create or update daily check-in
- `GET /v1/daily-checkin/today` - Get today's check-in
- `GET /v1/daily-checkin/{date}` - Get check-in for specific date
- `GET /v1/daily-checkin` - List recent check-ins

---

## Version 3.2.0 - Launch Blockers Complete (2026-01-15)

### Launch Blockers Addressed
All identified launch blockers have been completed:

1. **Onboarding Flow Polish** ✅
   - Added Strava connection step
   - Improved tone (sparse, non-guilt)
   - Better progress indicator

2. **Nutrition Logging UX** ✅
   - Already tone-compliant
   - Quick presets, optional everything

3. **Profile/Settings Pages** ✅
   - GDPR export/delete functionality
   - Subscription tier display
   - Future integrations placeholder

4. **Tone Verification** ✅
   - Audited all UI copy
   - No forbidden phrases found
   - Minor fix to register page

5. **Recovery Metrics** ✅
   - Recovery half-life calculation
   - Durability index calculation
   - Consistency index calculation
   - False fitness detection
   - Masked fatigue detection

6. **Combination Correlation Analysis** ✅
   - Multi-factor pattern discovery
   - Effect size calculation (Cohen's d)
   - Unified insights endpoint

7. **Integration Requirements Documentation** ✅
   - Full requirements for Garmin, Coros, Whoop, Apple Health, MyFitnessPal
   - Application checklist for post-launch
   - Priority order for integrations

### New API Endpoints
- `GET /v1/recovery-metrics/me` - Get recovery metrics
- `POST /v1/recovery-metrics/refresh` - Force refresh
- `GET /v1/recovery-metrics/warnings` - Get warnings
- `GET /v1/correlations/combinations` - Multi-factor correlations
- `GET /v1/correlations/insights` - Unified insights view

### New Documentation
- `INTEGRATION_REQUIREMENTS.md` - Full integration requirements

---

## Version 3.1.0 - Comprehensive Architectural Review (2026-01-15)

### Architectural Review
- Created comprehensive project review report (`ARCHITECTURAL_REVIEW_REPORT.md`)
- Full manifesto alignment assessment with gap analysis
- Scalability assessment (1 to 50k users)
- Future integration planning for external data streams

### Data Streams Architecture
- Created `data_streams` module for extensible integrations
- Base adapter classes for Activity, Recovery, Nutrition streams
- Unified data models (`UnifiedActivityData`, `UnifiedRecoveryData`, `UnifiedNutritionData`)
- Registry pattern for adapter management

### Future Integration Support
- Architecture now supports adding:
  - Garmin, Coros, Whoop, Intervals.icu (activity platforms)
  - MyFitnessPal, Cronometer (nutrition apps)
  - Apple Health, Samsung Health, Oura (recovery/wellness)
- All without breaking existing functionality

### Identified Action Items
- **Launch Blockers:** UI polish, tone verification, E2E testing, production deployment
- **Post-Launch Sprint 1:** Garmin adapter, MyFitnessPal, combination analysis
- **Post-Launch Sprint 2:** Apple Health, Coros, PB probability modeling

---

## Version 3.0.0 - Phase 3 Complete (2026-01-15)

### Phase 3: Robustness & Scalability

**Database Optimization**
- Fixed N+1 queries with bulk loading
- Optimized aggregation queries (SQL aggregation)
- Added composite indexes for common query patterns

**Caching Layer**
- Redis integration with graceful degradation
- Cache decorators and helpers
- Cache invalidation on data updates
- TTLs: Efficiency trends (1h), Correlations (24h), Activities (5min)

**Rate Limiting**
- Token bucket algorithm
- Per-user and per-endpoint limits
- Rate limit headers
- Fail-open if Redis unavailable

**Security Enhancements**
- GDPR compliance endpoints (export, delete)
- Neutral, empowering tone
- Complete data export
- Cascade deletion

**Extensibility Hooks**
- Lightweight event system
- Event subscription/emission
- Event decorators
- Common event names

**Load Testing**
- Locust script for load testing
- Performance targets documented
- Realistic user simulation

## Version 2.0.0 - Phase 2 Complete (2026-01-10)

### Phase 2: Integration & Automation

**Scheduled Digests**
- Email service with SMTP support
- Weekly digest task (Monday 9 AM UTC)
- Individual digest tasks per athlete
- Email includes "What's Working" and "What Doesn't Work" correlations

**Data Sync/Import**
- Strava webhook subscription service
- Webhook verification endpoint
- Event handler for automatic activity sync
- Signature verification for security

**User Feedback Loop**
- InsightFeedback model and migration
- API endpoints for submitting/listing feedback
- InsightFeedback component for rating insights
- Feedback statistics endpoint

**Admin/Owners Dashboard**
- Admin API router with endpoints
- User management (list, search, filter, impersonate)
- System health monitoring
- Site metrics (growth, engagement)
- Correlation testing endpoint
- Cross-athlete query endpoint
- Frontend dashboard with tabs
- Role-based access control (admin/owner only)

## Version 1.0.0 - Phase 1 Complete (2026-01-05)

### Phase 1: Complete Athlete-Facing Experience

**Discovery Dashboard**
- Correlation cards for "What's Working" and "What Doesn't Work"
- Charts and filters
- Insight feedback integration

**Profile & Settings**
- Profile management page
- Settings page with Strava integration
- API endpoint for updating athlete profiles

**Onboarding Flow**
- Multi-step onboarding wizard
- 5 stages: Welcome, Basic Profile, Goals, Connect Strava, Body Composition

**Nutrition Logging**
- Low-friction nutrition logging interface
- Non-guilt-inducing prompts
- Optional fields

**Activity Detail Page**
- Efficiency comparisons
- Decoupling badge
- Activity metrics
- Splits chart

**Frontend Architecture**
- Next.js, React, TypeScript
- Tailwind CSS
- React Query for server state
- Modular component architecture
- Typed API client
- Error boundaries
- Authentication context/hooks

