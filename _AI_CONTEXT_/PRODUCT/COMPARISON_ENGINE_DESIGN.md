# Comparison Engine - Complete Design Specification

**Status:** Design Approved - Ready for Implementation  
**Priority:** Marquee Feature  
**Last Updated:** January 9, 2026

### Design Decisions (Approved)
- **Individual comparison:** Max 10 runs
- **Group comparison:** Max 2 groups (A vs B)
- **Correlation Engine:** Owner/Admin + Top Tier only
- **Iteration:** Will discover gaps through building

---

## Executive Summary

The Comparison Engine is a core differentiator for StrideIQ. Neither Garmin nor Strava offers the ability to:
- Select specific runs and compare them side-by-side
- Compare groups of runs by type, conditions, or time period
- Stack multiple filters to answer complex training questions

This document specifies the complete design before implementation.

---

## Part 1: Comparison Engine (Athlete-Facing)

### 1.1 Core Capabilities

| Capability | Description | Example |
|------------|-------------|---------|
| Individual Comparison | Compare 2-10 specific runs side-by-side | "These 5 threshold workouts from my last build" |
| Group Comparison | Compare aggregate stats of two run groups | "Tempo runs Oct-Nov vs Tempo runs Aug-Sep" |
| Trend Analysis | See how a workout type evolves over time | "My easy run efficiency over 6 months" |
| Condition Impact | See how conditions affect performance | "Hot day runs vs cool day runs" |

### 1.2 Selection Methods

Athletes need multiple ways to select runs for comparison:

#### Method A: Manual Selection (Activity List)
- Checkbox on each activity in the activities list
- "Add to comparison" button appears when items selected
- Selection basket shows at bottom of screen
- Max 10 activities for individual comparison

#### Method B: Type-Based Selection
- Dropdown: Select workout type
- Date range picker
- Optional: condition filters (when data available)
- Creates a "group" for comparison

#### Method C: Quick Compare (from Activity Detail)
- Button on activity detail page: "Compare to Similar"
- Automatically finds same workout type, similar distance
- User can adjust the auto-selection

#### Method D: Smart Filters (Power Users)
- Query builder interface
- Stack conditions: Type + Date Range + Distance Range + HR Range
- Save common comparisons as presets

### 1.3 Comparison Modes

#### Individual Mode (2-10 runs)
**Use case:** "Show me these 5 runs side by side"

**Output:**
- Horizontal card for each run with key metrics
- Overlay chart: pace over distance (all runs on same axes)
- Overlay chart: HR over distance
- Comparison table: metrics in rows, runs in columns
- Highlight: best/worst in each metric

**Data per run:**
- Date, name, workout type
- Distance, duration, pace
- Avg HR, Max HR
- Efficiency (speed/HR)
- Elevation gain
- Temperature (if available)
- Intensity Score
- RPE (if logged)
- Splits summary

#### Group Mode (Group A vs Group B)
**Use case:** "Compare my October training block to my August block"

**Output:**
- Side-by-side aggregate cards
- Average metrics per group
- Distribution charts (histogram of paces, etc.)
- Statistical comparison: which group performed better
- Trend within each group

**Aggregate metrics:**
- Total runs, total distance, total time
- Average pace, average HR, average efficiency
- Efficiency trend (first half vs second half of group)
- Best/worst run in each group

### 1.4 User Interface Concept

```
┌─────────────────────────────────────────────────────────────────┐
│  Compare Workouts                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ + Add Runs  │  │ By Type     │  │ Quick Match │             │
│  │  Manually   │  │ & Filters   │  │  (Similar)  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Selected for Comparison (3 of 10 max)                       ││
│  │ ┌─────────┐ ┌─────────┐ ┌─────────┐                        ││
│  │ │ Nov 15  │ │ Oct 23  │ │ Oct 10  │    [Compare Now →]     ││
│  │ │ 6mi T   │ │ 5mi T   │ │ 6mi T   │                        ││
│  │ │  ✕      │ │  ✕      │ │  ✕      │                        ││
│  │ └─────────┘ └─────────┘ └─────────┘                        ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ── OR compare groups ──                                        │
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │ Group A             │ vs │ Group B             │            │
│  │ Type: Tempo         │    │ Type: Tempo         │            │
│  │ Oct 1 - Nov 15      │    │ Aug 1 - Sep 15      │            │
│  │ [12 runs matched]   │    │ [8 runs matched]    │            │
│  └─────────────────────┘    └─────────────────────┘            │
│                                                                 │
│                         [Compare Groups →]                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.5 Results Display - Individual Comparison

```
┌─────────────────────────────────────────────────────────────────┐
│  Comparing 3 Threshold Runs                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  [Pace Overlay Chart - all 3 runs on same axes]           │ │
│  │  ───── Nov 15 (fastest)                                   │ │
│  │  - - - Oct 23                                             │ │
│  │  ..... Oct 10 (slowest)                                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Metrics Comparison                                             │
│  ┌──────────────┬───────────┬───────────┬───────────┐          │
│  │ Metric       │ Nov 15 🏆 │ Oct 23    │ Oct 10    │          │
│  ├──────────────┼───────────┼───────────┼───────────┤          │
│  │ Distance     │ 9.7 km    │ 8.1 km    │ 9.5 km    │          │
│  │ Pace         │ 4:32/km   │ 4:45/km   │ 4:48/km   │          │
│  │ Avg HR       │ 158 bpm   │ 162 bpm   │ 165 bpm   │          │
│  │ Efficiency   │ 0.083 🏆  │ 0.078     │ 0.076     │          │
│  │ Temp         │ 52°F      │ 68°F      │ 75°F      │          │
│  │ RPE          │ 7         │ 7         │ 8         │          │
│  └──────────────┴───────────┴───────────┴───────────┘          │
│                                                                 │
│  Key Insight: Nov 15 was 3.5% more efficient than Oct 10,      │
│  possibly due to cooler temperature (52°F vs 75°F)             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.6 Results Display - Group Comparison

```
┌─────────────────────────────────────────────────────────────────┐
│  Group Comparison: Tempo Runs                                   │
│  Oct 1 - Nov 15 (12 runs) vs Aug 1 - Sep 15 (8 runs)           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────┐    ┌───────────────────────┐        │
│  │ October Build         │    │ August Build          │        │
│  │ ━━━━━━━━━━━━━━━━━━━  │    │ ━━━━━━━━━━━━━━━━━━━  │        │
│  │ 12 runs               │    │ 8 runs                │        │
│  │ 89.2 km total         │    │ 58.4 km total         │        │
│  │ Avg pace: 4:38/km     │    │ Avg pace: 4:52/km     │        │
│  │ Avg HR: 159 bpm       │    │ Avg HR: 164 bpm       │        │
│  │ Avg efficiency: 0.081 │    │ Avg efficiency: 0.074 │        │
│  │ Trend: ↑ Improving    │    │ Trend: → Stable       │        │
│  └───────────────────────┘    └───────────────────────┘        │
│                                                                 │
│  Δ Summary                                                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ October was 9.5% MORE EFFICIENT than August                 ││
│  │ • Pace improved by 14 sec/km                                ││
│  │ • HR decreased by 5 bpm at similar efforts                  ││
│  │ • More volume (53% more total distance)                     ││
│  │                                                              ││
│  │ Factors to consider:                                         ││
│  │ • August avg temp: 82°F vs October avg: 58°F                ││
│  │ • October had more consistent weekly frequency              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Correlation Engine (Owner + Top Tier)

### 2.1 Purpose

The Correlation Engine answers: **"What factors predict my performance?"**

This is the productized version of the diagnostic analysis work.

**Access Levels:**
| Role | Access |
|------|--------|
| Owner/Admin | Full access to all athletes' data, raw queries, cohort analysis |
| Top Tier ($25/mo) | Access to their own data only, preset queries |
| Basic/Free | No access (upgrade prompt) |

### 2.2 Query Types

| Query | Question | Output |
|-------|----------|--------|
| Efficiency Correlates | What factors correlate with higher running efficiency? | Ranked list with effect sizes |
| Race Predictors | What training patterns predict good race performance? | Pre-race training signatures |
| Fatigue Signals | What metrics indicate I'm overtraining? | Warning indicators |
| Recovery Patterns | How does sleep/HRV/rest affect next-day performance? | Lag correlation analysis |
| Seasonal Patterns | How does my performance vary by month/season? | Cyclical trend charts |

### 2.3 Statistical Methods

For each correlation query:

1. **Calculate correlation coefficient** (Pearson r)
2. **Calculate p-value** (is this statistically significant?)
3. **Calculate effect size** (how big is the effect?)
4. **Report sample size** (how confident can we be?)
5. **Identify confounders** (what else might explain this?)

### 2.4 Confidence Levels

| Sample Size | Confidence Level | Display |
|-------------|------------------|---------|
| < 10 | Insufficient | "Not enough data" (grayed out) |
| 10-20 | Low | "Preliminary finding" (orange) |
| 20-50 | Moderate | "Probable pattern" (yellow) |
| 50+ | High | "Strong evidence" (green) |

### 2.5 Feature Access by Role

#### Top Tier Athletes ($25/mo)
- Run preset correlation queries on their own data
- "What factors affect my efficiency?"
- "What predicts my good races?"
- "How does sleep/HRV impact my performance?"
- View confidence levels and sample sizes
- Export their correlation reports

#### Owner/Admin Dashboard (You)
Everything Top Tier gets, PLUS:
- **All athletes** - Query any athlete's data
- **Raw query interface** - Run custom SQL/analytical queries
- **Cohort analysis** - Compare patterns across all athletes
- **Anomaly detection** - Find unusual patterns in any athlete's data
- **Model training data export** - Extract data for ML experiments
- **Feature flags** - Enable experimental features per athlete
- **System health** - API usage, costs, performance metrics

---

## Part 3: Data Requirements

### 3.1 Already Have
- ✅ Activity basics (distance, duration, pace, HR, elevation)
- ✅ Workout classification (type, zone, confidence)
- ✅ Activity splits (lap data)
- ✅ Temperature/weather (when available from Strava)
- ✅ ActivityFeedback (RPE, fatigue, etc.)
- ✅ Intensity Score

### 3.2 Need to Add/Improve

| Data Point | Source | Priority | Notes |
|------------|--------|----------|-------|
| Route clustering | Derived from GPS start/end | Medium | Group "same route" runs |
| Weather backfill | OpenWeather API | Low | Fill gaps in Strava weather |
| Wellness data | Garmin import | High | HRV, sleep, resting HR |
| Pre-run state | ActivityFeedback expansion | Medium | Sleep quality, stress, nutrition |

### 3.3 Route Detection (Future)

When GPS data is available:
1. Extract start point (lat/long)
2. Cluster activities by start point (within 500m)
3. For detailed matching: compare route shape using simplification algorithms
4. Label frequent routes (athlete can name them)

**Not blocking on this for V1** - we build with what we have, add route support later.

---

## Part 4: API Design

### 4.1 Comparison Endpoints

```
POST /v1/compare/individual
Body: {
  "activity_ids": ["uuid1", "uuid2", "uuid3"],  // 2-10 IDs
  "metrics": ["pace", "hr", "efficiency", "splits"]  // optional filter
}
Response: {
  "activities": [...],
  "comparison_table": {...},
  "charts": {
    "pace_overlay": [...],
    "hr_overlay": [...]
  },
  "insights": ["Nov 15 was most efficient..."]
}

POST /v1/compare/groups
Body: {
  "group_a": {
    "workout_type": "tempo_run",
    "date_start": "2025-10-01",
    "date_end": "2025-11-15",
    "filters": {}  // optional: temp_min, temp_max, etc.
  },
  "group_b": {
    "workout_type": "tempo_run", 
    "date_start": "2025-08-01",
    "date_end": "2025-09-15",
    "filters": {}
  }
}
Response: {
  "group_a_summary": {...},
  "group_b_summary": {...},
  "delta": {...},
  "insights": [...]
}

GET /v1/compare/quick/{activity_id}
# Auto-finds similar activities for comparison
Response: {
  "target_activity": {...},
  "similar_activities": [...],  // 5-10 similar runs
  "comparison": {...}
}
```

### 4.2 Correlation Endpoints (Owner Dashboard)

```
POST /v1/correlate/efficiency
Body: {
  "athlete_id": "uuid",  // owner can query any athlete
  "days": 180,
  "min_sample_size": 20
}
Response: {
  "correlations": [
    {"factor": "temperature_f", "r": -0.42, "p": 0.003, "effect": "moderate", "n": 45},
    {"factor": "prior_day_distance", "r": -0.28, "p": 0.05, "effect": "small", "n": 45},
    ...
  ],
  "insufficient_data": ["hrv", "sleep_hours"],  // factors with < min_sample_size
  "insights": [...]
}

POST /v1/correlate/custom
Body: {
  "athlete_id": "uuid",
  "target_metric": "pace_per_km",
  "factors": ["sleep_hours", "temperature_f", "prior_week_volume"],
  "workout_type": "threshold_run",  // optional filter
  "days": 365
}
```

---

## Part 5: Implementation Phases

### Phase 1: Individual Comparison (Core)
**Effort:** 2-3 days

- [ ] Backend: `/v1/compare/individual` endpoint
- [ ] Frontend: Activity selection UI (checkboxes on activity list)
- [ ] Frontend: Comparison basket component
- [ ] Frontend: Individual comparison results page
- [ ] Metrics table with highlighting
- [ ] Basic overlay charts (pace, HR)

### Phase 2: Group Comparison
**Effort:** 2-3 days

- [ ] Backend: `/v1/compare/groups` endpoint
- [ ] Frontend: Group builder UI (type + date range)
- [ ] Frontend: Group comparison results
- [ ] Side-by-side aggregate cards
- [ ] Delta summary with insights

### Phase 3: Quick Compare
**Effort:** 1 day

- [ ] Backend: `/v1/compare/quick/{id}` endpoint
- [ ] Frontend: "Compare to Similar" button on activity detail
- [ ] Auto-selection logic (same type, similar distance)

### Phase 4: Condition Filters
**Effort:** 1-2 days

- [ ] Add temperature range filters to group builder
- [ ] Add distance range filters
- [ ] Add HR range filters
- [ ] Filter indicator badges on results

### Phase 5: Correlation Engine (Owner)
**Effort:** 3-4 days

- [ ] Backend: Correlation calculation service
- [ ] Backend: `/v1/correlate/*` endpoints
- [ ] Owner dashboard: Correlation query interface
- [ ] Results display with confidence levels
- [ ] Insight generation

### Phase 6: Route Detection (Future)
**Effort:** TBD

- [ ] GPS start point extraction
- [ ] Clustering algorithm
- [ ] Route naming UI
- [ ] "Same route" filter option

---

## Part 6: Edge Cases & Error Handling

| Scenario | Handling |
|----------|----------|
| < 2 activities selected | "Select at least 2 activities to compare" |
| > 10 activities selected | "Maximum 10 activities for individual comparison" |
| No common metrics | Show available metrics only, gray out missing |
| Group with 0 matches | "No activities match these criteria" |
| Insufficient data for correlation | Show factor as "insufficient data" with sample size |
| One run missing HR data | Show "—" for that cell, calculate averages excluding it |

---

## Part 7: Success Metrics

How do we know this feature is successful?

1. **Usage:** Athletes use comparison at least 1x per week
2. **Depth:** Average comparison includes 4+ activities
3. **Retention:** Comparison users have higher monthly retention
4. **Feedback:** "This helped me understand my training" sentiment

---

## Appendix: Competitive Analysis

| Feature | Garmin | Strava | StrideIQ |
|---------|--------|--------|----------|
| List activities by type | ✅ | ✅ | ✅ |
| Side-by-side compare (2) | ❌ | ❌ | ✅ |
| Multi-run compare (3-10) | ❌ | ❌ | ✅ |
| Group vs Group | ❌ | ❌ | ✅ |
| Condition filters | ❌ | ❌ | ✅ |
| Overlay charts | ❌ | ❌ | ✅ |
| Efficiency tracking | Partial | ❌ | ✅ |
| Correlation mining | ❌ | ❌ | ✅ |

**This is our moat.**

---

*Document created: January 9, 2026*  
*Next step: Review with founder, then implement Phase 1*
