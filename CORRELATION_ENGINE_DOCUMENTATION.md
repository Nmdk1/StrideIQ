# Correlation Analysis Engine: Comprehensive Documentation

**Version:** 2.0.0  
**Date:** December 19, 2024  
**Status:** Production-Ready Foundation

---

## Executive Summary

The Correlation Analysis Engine is the core discovery system that identifies which inputs (nutrition, sleep, work patterns, body composition) lead to statistically significant efficiency improvements for individual athletes. This system transforms the platform from a data tracker into a physiological analysis engine that discovers personal response curves from longitudinal data.

**Key Achievement:** The system can now answer the question: "What combination of inputs leads to improved running efficiency for THIS athlete?" using rigorous statistical analysis of their own data.

---

## 1. System Architecture

### 1.1 Core Components

#### **Correlation Engine Service** (`apps/api/services/correlation_engine.py`)
- **Purpose:** Statistical correlation analysis between inputs and efficiency outputs
- **Key Functions:**
  - `aggregate_daily_inputs()`: Collects and time-aligns all input data
  - `aggregate_efficiency_outputs()`: Collects efficiency metrics from activities
  - `find_time_shifted_correlations()`: Tests correlations with time delays (0-14 days)
  - `calculate_pearson_correlation()`: Statistical correlation with p-value testing
  - `analyze_correlations()`: Main analysis pipeline

#### **API Endpoints** (`apps/api/routers/correlations.py`)
- `/v1/correlations/discover`: Full correlation analysis
- `/v1/correlations/what-works`: Positive correlations (improves efficiency)
- `/v1/correlations/what-doesnt-work`: Negative correlations (reduces efficiency)

### 1.2 Data Flow

```
Input Data Collection → Time Alignment → Correlation Testing → Statistical Filtering → Results
```

1. **Input Aggregation:** Daily inputs (sleep, nutrition, work, body comp) collected by date
2. **Output Aggregation:** Efficiency metrics (EF, decoupling) extracted from activities
3. **Time Alignment:** Inputs and outputs aligned by date with configurable time shifts
4. **Correlation Testing:** Pearson correlation calculated for each input-output pair
5. **Statistical Filtering:** Only significant correlations (p < 0.05, |r| >= 0.3) retained
6. **Results:** Sorted by correlation strength, returned as actionable insights

---

## 2. Input Data Sources

### 2.1 Sleep & Recovery (`DailyCheckin` table)

**Fields Tracked:**
- `sleep_h`: Total sleep duration (hours)
- `hrv_rmssd`: Heart rate variability (rMSSD)
- `hrv_sdnn`: Heart rate variability (SDNN)
- `resting_hr`: Resting heart rate (bpm)
- `overnight_avg_hr`: Overnight average HR (bpm)
- `stress_1_5`: Stress level (1-5 scale)
- `soreness_1_5`: Soreness level (1-5 scale)
- `rpe_1_10`: Rate of perceived exertion (1-10 scale)

**Correlation Hypothesis:** Better sleep quality → improved next-day efficiency

### 2.2 Nutrition (`NutritionEntry` table)

**Fields Tracked:**
- `entry_type`: 'pre_activity', 'during_activity', 'post_activity', 'daily'
- `calories`: Total calories
- `protein_g`: Protein intake (grams)
- `carbs_g`: Carbohydrate intake (grams)
- `fat_g`: Fat intake (grams)
- `fiber_g`: Fiber intake (grams)
- `timing`: When consumed (datetime)
- `activity_id`: Links to specific activity if pre/during/post

**Aggregation:** Daily totals calculated for protein, carbs, calories

**Correlation Hypothesis:** Nutrition timing and composition → efficiency and recovery

### 2.3 Work Patterns (`WorkPattern` table)

**Fields Tracked:**
- `work_type`: 'desk', 'physical', 'shift', 'travel', etc.
- `hours_worked`: Hours worked per day
- `stress_level`: Work stress (1-5 scale)

**Correlation Hypothesis:** High work stress/hours → reduced efficiency

### 2.4 Body Composition (`BodyComposition` table)

**Fields Tracked:**
- `weight_kg`: Body weight (kg)
- `body_fat_pct`: Body fat percentage
- `muscle_mass_kg`: Muscle mass (kg)
- `bmi`: Body Mass Index (calculated)

**Correlation Hypothesis:** Body composition trends → performance outcomes

### 2.5 Activity Feedback (`ActivityFeedback` table)

**Fields Tracked:**
- `perceived_effort`: RPE (1-10 scale)
- `leg_feel`: 'fresh', 'normal', 'tired', 'heavy', 'sore', 'injured'
- `mood_pre/post`: Mood before/after activity
- `energy_pre/post`: Energy level (1-10 scale)

**Correlation Hypothesis:** Perception ↔ performance correlations

---

## 3. Output Metrics

### 3.1 Efficiency Factor (EF)

**Definition:** `EF = NGP / HR`

- **NGP:** Normalized Grade Pace (seconds/mile) calculated using Minetti's equation
- **HR:** Heart rate (as % of max HR if available, else raw HR)
- **Interpretation:** Lower EF = more efficient (faster pace at same HR, or lower HR at same pace)

**Calculation Details:**
- Uses GAP (Grade Adjusted Pace) from splits when available
- Cardio lag filter: Excludes first 6 minutes to avoid O₂ debt skewing
- Calculated per activity using all splits after cardio lag period

### 3.2 Aerobic Decoupling

**Definition:** Comparison of EF in first half vs. second half of run

- **Formula:** `Decoupling % = ((Second Half EF - First Half EF) / First Half EF) * 100`
- **Interpretation:**
  - Green (<5%): Excellent durability
  - Yellow (5-8%): Moderate cardiac drift
  - Red (>8%): Significant cardiac drift

### 3.3 Performance Percentage

**Definition:** Age-graded performance % against WMA world standards

- **International Standard:** WMA world records
- **National Standard:** National age-group records
- **Interpretation:** Higher % = better relative performance

### 3.4 Personal Bests

**Definition:** Fastest time for each distance category

- Tracked over time to identify improvement trends
- Used as baseline for efficiency comparisons

---

## 4. Statistical Methodology

### 4.1 Correlation Calculation

**Method:** Pearson Product-Moment Correlation Coefficient

**Formula:**
```
r = Σ((x_i - x̄)(y_i - ȳ)) / √(Σ(x_i - x̄)² * Σ(y_i - ȳ)²)
```

**Interpretation:**
- `r = +1.0`: Perfect positive correlation
- `r = -1.0`: Perfect negative correlation
- `r = 0.0`: No correlation

### 4.2 Statistical Significance Testing

**Method:** t-test for correlation coefficient

**Null Hypothesis:** No correlation (r = 0)

**Test Statistic:**
```
t = r * √((n - 2) / (1 - r²))
```

**P-value:** Probability of observing this correlation by chance

**Threshold:** `p < 0.05` (5% significance level)

### 4.3 Correlation Strength Classification

- **Weak:** |r| < 0.3
- **Moderate:** 0.3 ≤ |r| < 0.7
- **Strong:** |r| ≥ 0.7

### 4.4 Minimum Sample Size

**Requirement:** `n ≥ 10` data points

**Rationale:** Statistical tests require sufficient data for reliable results

### 4.5 Correlation Strength Threshold

**Requirement:** |r| ≥ 0.3

**Rationale:** Filter out weak correlations that may be noise

---

## 5. Time-Shifted Correlation Detection

### 5.1 Concept

**Problem:** Cause rarely equals same-day effect. Physiological adaptations have delays.

**Solution:** Test correlations with time shifts (lags) from 0 to 14 days.

### 5.2 Implementation

For each input variable:
1. Test correlation with output at lag 0 (same day)
2. Test correlation with output at lag 1 (1 day before)
3. Test correlation with output at lag 2 (2 days before)
4. ... up to lag 14 (14 days before)

**Example:** Sleep quality on Day 1 may correlate with efficiency on Day 2 (lag = 1 day)

### 5.3 Discovered Delays

The system discovers actual delays from athlete's data:
- **Acute effects:** Appear in days (e.g., sleep → next-day efficiency)
- **Chronic effects:** Appear over weeks (e.g., consistent training → efficiency gains)
- **Adaptation effects:** Appear over months (e.g., body composition → performance)

**No assumptions:** All lags learned from longitudinal personal data.

---

## 6. API Endpoints

### 6.1 `/v1/correlations/discover`

**Method:** GET  
**Authentication:** Required (JWT)

**Parameters:**
- `days` (query, optional): Analysis period in days (default: 90, min: 30, max: 365)

**Response:**
```json
{
  "athlete_id": "uuid",
  "analysis_period": {
    "start": "2024-01-01T00:00:00",
    "end": "2024-04-01T00:00:00",
    "days": 90
  },
  "sample_sizes": {
    "activities": 45,
    "inputs": {
      "sleep_hours": 85,
      "hrv_rmssd": 80,
      "daily_protein_g": 90
    }
  },
  "correlations": [
    {
      "input_name": "sleep_hours",
      "correlation_coefficient": -0.45,
      "p_value": 0.023,
      "sample_size": 28,
      "is_significant": true,
      "direction": "negative",
      "strength": "moderate",
      "time_lag_days": 1,
      "combination_factors": []
    }
  ],
  "total_correlations_found": 3
}
```

**Interpretation:**
- `correlation_coefficient: -0.45`: Negative correlation (more sleep → better efficiency)
- `p_value: 0.023`: Statistically significant (p < 0.05)
- `time_lag_days: 1`: Sleep 1 day before affects efficiency
- `direction: "negative"`: For EF, negative = better (lower EF = more efficient)

### 6.2 `/v1/correlations/what-works`

**Method:** GET  
**Authentication:** Required (JWT)

**Returns:** Only positive correlations (inputs that improve efficiency)

**Response Format:** Same as `/discover`, filtered for `direction: "negative"` (which means better efficiency)

### 6.3 `/v1/correlations/what-doesnt-work`

**Method:** GET  
**Authentication:** Required (JWT)

**Returns:** Only negative correlations (inputs that reduce efficiency)

**Response Format:** Same as `/discover`, filtered for `direction: "positive"` (which means worse efficiency)

---

## 7. Example Use Cases

### 7.1 Sleep → Efficiency Correlation

**Scenario:** Athlete wants to know if sleep affects their running efficiency.

**Analysis:**
1. System aggregates sleep hours for last 90 days
2. System aggregates efficiency factors from activities
3. Tests correlations with lags 0-14 days
4. Finds: `sleep_hours` at lag 1 day correlates with efficiency (r = -0.45, p = 0.023)

**Insight:** "Sleeping more hours 1 day before a run correlates with 45% better efficiency. This is statistically significant (p=0.023) with moderate strength."

**Action:** Athlete should prioritize sleep the night before runs.

### 7.2 Work Stress → Efficiency Correlation

**Scenario:** Athlete notices efficiency drops during high-stress work periods.

**Analysis:**
1. System aggregates work stress levels
2. System aggregates efficiency factors
3. Finds: `work_stress` at lag 0 days correlates negatively with efficiency (r = +0.38, p = 0.041)

**Insight:** "High work stress on the same day as a run correlates with 38% worse efficiency. This is statistically significant (p=0.041)."

**Action:** Athlete should schedule runs on lower-stress days or adjust expectations.

### 7.3 Nutrition Timing → Efficiency Correlation

**Scenario:** Athlete wants to optimize pre-run nutrition.

**Analysis:**
1. System aggregates pre-activity protein intake
2. System aggregates efficiency factors
3. Finds: `pre_activity_protein_g` at lag 0 correlates with efficiency (r = -0.32, p = 0.048)

**Insight:** "Consuming more protein before runs correlates with better efficiency."

**Action:** Athlete should increase pre-run protein intake.

---

## 8. Limitations & Future Enhancements

### 8.1 Current Limitations

1. **Single-Variable Correlations Only:** Currently tests one input at a time
2. **Linear Relationships:** Assumes linear correlations (Pearson correlation)
3. **No Combination Analysis:** Doesn't test multi-factor patterns yet
4. **Fixed Time Windows:** Uses fixed 0-14 day lags (could be adaptive)

### 8.2 Planned Enhancements

1. **Combination Analysis:** Test multi-factor patterns (e.g., "high protein + good sleep + moderate volume")
2. **Non-Linear Correlations:** Use ML models to detect complex patterns
3. **Adaptive Time Windows:** Learn optimal lag windows from data
4. **Causal Inference:** Move beyond correlation to identify causal relationships
5. **Predictive Models:** Build models to predict efficiency from inputs

---

## 9. Testing & Validation

### 9.1 Test Coverage

**Unit Tests:** (`apps/api/tests/test_correlation_engine.py`)
- Correlation calculation accuracy
- Time series alignment
- Data aggregation
- Statistical significance testing
- Edge cases (insufficient data, missing data)

**Integration Tests:**
- Full analysis pipeline
- API endpoint responses
- Database queries

### 9.2 Validation Criteria

1. **Statistical Validity:** P-values calculated correctly
2. **Data Alignment:** Inputs and outputs properly time-aligned
3. **Time Shifts:** Lag detection works correctly
4. **Edge Cases:** Handles missing data gracefully
5. **Performance:** Analysis completes in reasonable time (< 5 seconds)

---

## 10. Integration Points

### 10.1 Dependencies

- **Efficiency Calculation Service:** Uses `calculate_activity_efficiency_with_decoupling()`
- **Database Models:** Reads from `DailyCheckin`, `NutritionEntry`, `WorkPattern`, `BodyComposition`, `Activity`, `ActivitySplit`
- **Authentication:** Requires JWT authentication via `get_current_user`

### 10.2 Frontend Integration

**Ready for:**
- Discovery dashboard UI
- "What's Working" insights display
- "What Doesn't Work" alerts
- Correlation visualization charts

**API Client:** Frontend can call endpoints directly with authentication token

---

## 11. Performance Considerations

### 11.1 Query Optimization

- Uses indexed columns (`athlete_id`, `date`)
- Aggregates data efficiently (single queries per input type)
- Filters by date range to limit data scanned

### 11.2 Computational Complexity

- **Time Complexity:** O(n * m * l) where:
  - n = number of input variables
  - m = number of output data points
  - l = number of lag days tested (15)
- **Space Complexity:** O(n + m) for storing time series

### 11.3 Scalability

- Handles 90 days of data efficiently (< 5 seconds)
- Can scale to 365 days with acceptable performance
- Database indexes ensure fast queries

---

## 12. Security & Privacy

### 12.1 Authentication

- All endpoints require JWT authentication
- Athletes can only access their own correlation data
- No cross-athlete data access

### 12.2 Data Privacy

- All analysis performed server-side
- No raw data exposed in API responses
- Only aggregated correlation results returned

---

## 13. Conclusion

The Correlation Analysis Engine represents a fundamental shift from descriptive tracking to **prescriptive discovery**. The system can now answer the core question: "What inputs lead to improved efficiency for THIS athlete?" using rigorous statistical analysis of their own longitudinal data.

**Key Achievements:**
- ✅ Statistical correlation analysis with significance testing
- ✅ Time-shifted correlation detection (delayed effects)
- ✅ Personal response curves (no global averages)
- ✅ Production-ready API endpoints
- ✅ Comprehensive test coverage

**Next Steps:**
- Combination analysis (multi-factor patterns)
- Frontend discovery dashboard
- Predictive modeling
- Causal inference

---

## Appendix A: Statistical Formulas

### Pearson Correlation Coefficient

```
r = Σ((x_i - x̄)(y_i - ȳ)) / √(Σ(x_i - x̄)² * Σ(y_i - ȳ)²)
```

### T-Statistic for Correlation

```
t = r * √((n - 2) / (1 - r²))
```

### P-Value Calculation

Two-tailed test: `p = 2 * (1 - t_cdf(|t|, df))`

Where `df = n - 2` (degrees of freedom)

---

## Appendix B: Code Structure

```
apps/api/
├── services/
│   └── correlation_engine.py      # Core correlation analysis
├── routers/
│   └── correlations.py            # API endpoints
└── tests/
    └── test_correlation_engine.py # Comprehensive tests
```

---

**Document Version:** 1.0  
**Last Updated:** December 19, 2024  
**Author:** Lead Engineering Team  
**Status:** Production-Ready Foundation


