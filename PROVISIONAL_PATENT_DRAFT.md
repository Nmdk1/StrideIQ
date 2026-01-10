# PROVISIONAL PATENT APPLICATION

## METHOD AND SYSTEM FOR ATHLETE-SPECIFIC PERFORMANCE ATTRIBUTION USING TIME-LAGGED MULTI-FACTOR CAUSAL INFERENCE

---

**Applicant:** StrideIQ, Inc.  
**Filing Date:** [To be completed at filing]  
**Application Type:** Provisional Patent Application  
**Technology Classification:** Sports Analytics, Machine Learning, Biometric Data Analysis

---

## ABSTRACT

A computer-implemented method and system for identifying causal relationships between athlete inputs (sleep, training load, recovery metrics, nutrition, body composition) and performance outcomes (running efficiency, pace, endurance) using time-lagged multi-factor statistical analysis. The system employs a dual-frequency causal inference approach that separately analyzes acute readiness factors (0-7 day lag window) and chronic adaptation factors (14-42 day lag window) to discover leading indicators specific to individual athletes. Unlike population-based training systems, the invention prioritizes individual athlete data (N=1 methodology) and uses Granger causality testing to establish statistical precedence rather than mere correlation. The system generates athlete-specific "leading indicator profiles" that can be used for personalized coaching recommendations, performance prediction, and training optimization.

---

## BACKGROUND OF THE INVENTION

### Field of the Invention

This invention relates to athletic performance analysis systems, and more particularly to methods for identifying causal factors that influence individual athlete performance using time-lagged statistical analysis of personal training and lifestyle data.

### Description of Related Art

Existing athletic training systems suffer from significant limitations:

1. **Population-Based Averages:** Current systems (Strava, Garmin, TrainingPeaks) apply generalized population averages and standard training models. These fail to account for individual variation in physiology, recovery capacity, and response to training stimuli.

2. **Correlation Without Causation:** Existing analytics show correlations (e.g., "athletes who sleep more tend to perform better") but fail to identify whether inputs actually PRECEDE outcomes or are merely coincidental.

3. **Fixed Time Windows:** Current systems use arbitrary fixed time windows (e.g., 7-day averages, 28-day fitness) without discovering the optimal lag between inputs and outputs for each athlete.

4. **Single-Frequency Analysis:** Existing systems do not distinguish between acute readiness factors (sleep last night → performance today) and chronic adaptation factors (training volume 3 weeks ago → fitness today).

5. **Prescriptive Rather Than Forensic:** Existing systems prescribe training based on external research rather than discovering what actually works for each individual.

### Objects of the Invention

It is an object of the present invention to provide a method for identifying athlete-specific causal relationships between inputs and performance outcomes.

It is a further object to provide dual-frequency analysis that separately examines acute readiness and chronic adaptation factors.

It is a further object to discover optimal time lags between inputs and outcomes from individual athlete data.

It is a further object to provide statistically defensible leading indicators using Granger causality testing.

It is a further object to generate personalized coaching insights that are specific to each athlete's discovered response patterns.

---

## SUMMARY OF THE INVENTION

The present invention provides a computer-implemented method and system for athlete-specific performance attribution comprising:

### Core Innovation 1: N=1 Causal Inference

Rather than applying population research findings, the system discovers causal patterns from each athlete's own longitudinal data. The athlete IS the sample. Population research informs which questions to ask (e.g., "does sleep matter?"), but the answer comes from individual data, not external studies.

### Core Innovation 2: Dual-Frequency Lag Analysis

The system separates input analysis into two frequency domains:

**Readiness Loop (0-7 Day Lag):** Analyzes acute factors that impact near-term performance:
- Sleep duration and quality
- Heart rate variability (HRV)
- Subjective stress levels
- Muscle soreness
- Resting heart rate

**Fitness Loop (14-42 Day Lag):** Analyzes chronic factors that drive adaptation:
- Weekly training volume
- Workout type distribution (threshold, intervals, long runs)
- Training consistency (runs per week)
- Acute-to-Chronic Workload Ratio (ACWR)

### Core Innovation 3: Granger Causality Detection

The system employs Granger causality testing to establish that changes in inputs PRECEDE changes in outputs, providing statistical evidence of temporal precedence. This moves beyond simple correlation to establish that:

- Input X at time t-k helps predict Output Y at time t
- Better than Output Y's own history alone would predict
- With statistical significance (p-value threshold)

### Core Innovation 4: Contextual Comparison Baseline ("Ghost Average")

The system establishes performance expectations by comparing current runs against a "ghost average" - a dynamically computed baseline from similar past runs (matched by duration, distance, intensity, conditions, elevation). Performance is scored relative to this personalized baseline, not arbitrary targets.

### Core Innovation 5: Pattern Recognition Over Averages

Rather than computing simple averages, the system identifies:

- **Prerequisites:** Conditions that were TRUE for ≥80% of top performances
- **Deviations:** Ways the current run differs from the pattern
- **Common Factors:** Conditions present in 60-79% of similar runs

---

## DETAILED DESCRIPTION OF THE INVENTION

### System Architecture

The system comprises the following components:

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA COLLECTION LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│  Activity Data    │  Recovery Data    │  Lifestyle Data         │
│  (Strava, Garmin) │  (HRV, Sleep)     │  (Nutrition, Work)      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TIME SERIES ALIGNMENT                        │
│  - Daily aggregation of inputs                                  │
│  - Activity-level output metrics                                │
│  - Lag-shifted alignment for causality testing                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              DUAL-FREQUENCY CAUSAL ENGINE                       │
├─────────────────────────────────────────────────────────────────┤
│  READINESS LOOP          │  FITNESS LOOP                        │
│  Lag: 0-7 days           │  Lag: 14-42 days                     │
│  - Sleep                 │  - Weekly volume                     │
│  - HRV                   │  - Workout distribution              │
│  - Stress                │  - Long run percentage               │
│  - Soreness              │  - Training consistency              │
│  - Resting HR            │  - ACWR                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              GRANGER CAUSALITY TESTING                          │
│  - For each input variable at each lag:                         │
│    - Build restricted model (output history only)               │
│    - Build unrestricted model (output + input history)          │
│    - F-test for improvement in prediction                       │
│    - Identify optimal lag with lowest p-value                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              LEADING INDICATOR GENERATION                       │
│  - Rank inputs by Granger p-value                               │
│  - Classify confidence (High, Moderate, Suggestive)             │
│  - Generate sparse, forensic insights                           │
│  - Create context block for AI coach injection                  │
└─────────────────────────────────────────────────────────────────┘
```

### Method Steps

**Step 1: Data Collection and Normalization**

The system collects input data from multiple sources:
- Activity tracking platforms (Strava, Garmin, Coros)
- Wearable devices (HRV monitors, sleep trackers)
- Manual check-ins (stress, soreness, mood)
- Body composition tracking
- Nutrition logging

Data is normalized to daily time series with consistent date alignment.

**Step 2: Output Metric Calculation**

The system calculates performance output metrics:
- **Efficiency Factor (EF):** Pace divided by heart rate, lower is better
- **Aerobic Decoupling:** EF degradation from first to second half of run
- **Age-Graded Performance:** Normalized against World Masters Athletics standards

**Step 3: Dual-Frequency Loop Configuration**

The system configures two analysis loops:

*Readiness Loop:*
- Input variables: sleep_hours, hrv_rmssd, stress_1_5, soreness_1_5, resting_hr
- Lag range: 0-7 days
- Minimum samples: 5-7 per variable
- Physiological basis: Acute readiness factors that impact immediate performance

*Fitness Loop:*
- Input variables: weekly_volume_km, threshold_pct, long_run_pct, consistency, acwr
- Lag range: 14-42 days
- Minimum samples: 4+ per variable
- Physiological basis: Chronic adaptation requiring supercompensation period

**Step 4: Time Series Alignment with Lag**

For each input-output pair and each candidate lag:
- Shift input series earlier by lag days
- Align with output series on matching dates
- Create paired observations (input[t-lag], output[t])

**Step 5: Granger Causality Testing**

For each aligned series pair:

1. Build restricted model: Predict output[t] using only output[t-1], output[t-2], ..., output[t-k]
2. Build unrestricted model: Predict output[t] using output history PLUS input[t-1], input[t-2], ..., input[t-k]
3. Calculate RSS (Residual Sum of Squares) for both models
4. Compute F-statistic: F = ((RSS_restricted - RSS_unrestricted) / q) / (RSS_unrestricted / (n-k))
5. Calculate p-value from F-distribution
6. If p < 0.05: Input "Granger-causes" output at this lag

**Step 6: Optimal Lag Discovery**

For each input variable:
- Test all lags in the configured range
- Select lag with lowest p-value
- This is the "optimal lag" for this athlete and this input

**Step 7: Leading Indicator Classification**

Classify discovered relationships by confidence:
- **HIGH:** p < 0.01 and |correlation| >= 0.4
- **MODERATE:** p < 0.05
- **SUGGESTIVE:** p < 0.10 (worth watching, not actionable)
- **INSUFFICIENT:** p >= 0.10 or sample too small

**Step 8: Insight Generation**

Generate sparse, non-prescriptive insights:
- "Data hints: Sleep changes 2 days prior preceded efficiency gains (Granger p=0.02)"
- "Threshold work at 3-week lag correlates with pace improvement. Test it."
- Never prescribe. Report math. Athlete decides.

**Step 9: Context Block Generation**

Create structured text block for AI coach injection:
```
=== CAUSAL ATTRIBUTION CONTEXT ===

DISCOVERED LEADING INDICATORS:
1. 🟢 Sleep Duration (2d lag): ↑ HELPS | p=0.018
2. 🟡 Weekly Volume (21d lag): ↑ HELPS | p=0.042

INTERPRETATION:
- Leading indicators show what PRECEDED performance changes
- Lower p-value = stronger statistical confidence
- Lag = how many days before the effect appeared
```

### Contextual Comparison Method

**Ghost Baseline Computation:**

1. For a target activity, identify similarity factors:
   - Duration (within 15% tolerance)
   - Distance (within 15% tolerance)
   - Intensity (workout type match)
   - Conditions (temperature, humidity)
   - Elevation (total gain within tolerance)

2. Query historical activities matching similarity criteria

3. Compute weighted similarity score for each candidate:
   - Duration match: 20% weight
   - Intensity match: 25% weight
   - Workout type match: 20% weight
   - Conditions match: 15% weight
   - Elevation match: 10% weight
   - Distance match: 10% weight

4. Select top N matches as "ghost cohort"

5. Calculate ghost average for key metrics:
   - Average pace
   - Average heart rate
   - Average efficiency
   - Performance score baseline

6. Score current run against ghost baseline:
   - Performance Score = (Current Efficiency / Ghost Efficiency) * 100
   - Positive deviation = ran better than similar past runs
   - Negative deviation = ran worse than similar past runs

**Pattern Recognition:**

For the ghost cohort, analyze trailing context for each run:
- Calculate 28-day training history for each ghost run
- Identify PREREQUISITES (true for ≥80% of ghost runs)
- Identify COMMON FACTORS (true for 60-79%)
- Compare current run's trailing context to patterns
- Flag DEVIATIONS where current differs from pattern

---

## CLAIMS

### Independent Claims

**Claim 1:** A computer-implemented method for identifying athlete-specific causal relationships between input factors and performance outcomes, comprising:
a) Collecting time-series data for a plurality of input variables from an individual athlete;
b) Calculating performance output metrics from athlete activity data;
c) Configuring dual-frequency analysis loops with distinct lag ranges for acute readiness factors and chronic adaptation factors;
d) Performing Granger causality testing at multiple time lags for each input-output pair;
e) Identifying optimal lag for each input variable based on statistical significance;
f) Generating athlete-specific leading indicator profiles with confidence classifications;
g) Producing human-readable insights describing discovered causal relationships.

**Claim 2:** A computer-implemented method for performance comparison using a contextual baseline, comprising:
a) Receiving a target activity from an athlete;
b) Querying historical activities matching the target on multiple similarity dimensions;
c) Computing weighted similarity scores to identify a ghost cohort;
d) Calculating ghost average metrics from the cohort;
e) Scoring the target activity relative to the ghost baseline;
f) Analyzing trailing context patterns across the ghost cohort;
g) Identifying prerequisites, common factors, and deviations for the target activity.

**Claim 3:** A system for athlete-specific performance attribution, comprising:
a) A data collection module receiving input from activity platforms, wearables, and manual entry;
b) A time series alignment module creating lag-shifted input-output pairs;
c) A dual-frequency causal engine with separate readiness and fitness loop analyzers;
d) A Granger causality testing module with optimal lag discovery;
e) A pattern recognition module identifying prerequisites and deviations;
f) An insight generation module producing sparse, non-prescriptive athlete guidance;
g) A context injection module providing structured data for AI coaching systems.

### Dependent Claims

**Claim 4:** The method of Claim 1, wherein the acute readiness factors comprise sleep duration, heart rate variability, subjective stress level, muscle soreness, and resting heart rate, analyzed with lag ranges of 0-7 days.

**Claim 5:** The method of Claim 1, wherein the chronic adaptation factors comprise weekly training volume, threshold workout percentage, long run percentage, training consistency, and acute-to-chronic workload ratio, analyzed with lag ranges of 14-42 days.

**Claim 6:** The method of Claim 1, wherein Granger causality testing comprises building restricted models using only output history and unrestricted models using output history plus lagged input history, and computing F-statistics to test for significant improvement in prediction.

**Claim 7:** The method of Claim 1, wherein confidence classification comprises assigning HIGH confidence when p < 0.01 and correlation magnitude >= 0.4, MODERATE confidence when p < 0.05, and SUGGESTIVE confidence when p < 0.10.

**Claim 8:** The method of Claim 2, wherein similarity dimensions comprise duration, distance, intensity score, workout type, weather conditions, and elevation gain, with configurable tolerance thresholds for each dimension.

**Claim 9:** The method of Claim 2, wherein pattern recognition comprises calculating 28-day trailing context for each cohort run, identifying prerequisites true for at least 80% of cohort runs, and identifying common factors true for 60-79% of cohort runs.

**Claim 10:** The system of Claim 3, wherein the insight generation module produces non-prescriptive language that reports statistical findings without commanding athlete behavior.

**Claim 11:** The system of Claim 3, wherein the context injection module produces structured text blocks suitable for injection into large language model prompts for AI-assisted coaching.

---

## DRAWINGS

[Placeholder for formal drawings to be prepared by patent illustrator]

**Figure 1:** System Architecture Diagram showing data flow from collection through causal analysis to insight generation.

**Figure 2:** Dual-Frequency Loop Configuration showing Readiness Loop (0-7 days) and Fitness Loop (14-42 days) parameters.

**Figure 3:** Granger Causality Testing Flowchart showing restricted model, unrestricted model, F-test, and optimal lag selection.

**Figure 4:** Contextual Comparison Process showing ghost cohort selection, baseline computation, and pattern recognition.

**Figure 5:** Leading Indicator Profile Example showing discovered causal relationships with confidence levels and lags.

---

## DEFENSIBILITY ANALYSIS

### Why This Is Patentable

1. **Novel Combination:** While Granger causality is known in econometrics, its application to athletic performance with dual-frequency loop analysis and contextual ghost baselines is novel.

2. **Non-Obvious:** The combination of:
   - N=1 methodology rejecting population averages
   - Dual-frequency separation of acute/chronic factors
   - Granger causality for athletic inputs
   - Ghost cohort pattern recognition
   - Non-prescriptive insight generation
   ...would not be obvious to a practitioner skilled in the art.

3. **Specific Implementation:** The claims specify particular input variables, lag ranges, statistical thresholds, and output formats that are concrete and reproducible.

4. **Technical Effect:** The invention produces a technical result (statistical model, computed scores, ranked indicators) that improves athletic training systems.

### Differentiation from Prior Art

| Feature | Prior Art (Strava, TrainingPeaks) | This Invention |
|---------|-----------------------------------|----------------|
| Baseline | Fixed zones, population averages | Dynamic ghost cohort from individual data |
| Causality | Simple correlation | Granger causality with lag detection |
| Time Analysis | Fixed windows (7d, 28d) | Dual-frequency loops with optimal lag discovery |
| Personalization | Apply external research | N=1 discovery from athlete's own data |
| Guidance | Prescriptive ("do this") | Forensic ("data suggests this preceded that") |

---

## APPENDIX: IMPLEMENTATION REFERENCE

The invention has been reduced to practice in the following software modules:

- `causal_attribution.py`: Core Granger causality engine with dual-frequency analysis
- `pattern_recognition.py`: Pattern detection and prerequisite identification
- `contextual_comparison.py`: Ghost cohort selection and baseline computation
- `athlete_context.py`: Athlete profile and context block generation

Statistical methods implemented:
- Pearson correlation with p-value calculation
- Granger causality F-test
- Time series lag alignment
- Rolling window aggregation

---

**INVENTOR DECLARATION**

I hereby declare that I am the inventor of the subject matter claimed herein, that this provisional patent application accurately describes the invention, and that I have reviewed and understand this application.

[Signature line for inventor]

---

**NOTES FOR FILING**

1. This is a PROVISIONAL patent application
2. File with USPTO within 12 months to claim priority date
3. Consider international filing under PCT if pursuing global protection
4. Non-provisional must be filed within 12 months with formal claims
5. Recommended: Patent attorney review before filing

**Estimated Filing Cost:** $320 (micro entity) / $640 (small entity) / $1,600 (large entity)

---

*Document prepared for StrideIQ IP Protection Strategy*
*Version: 1.0*
*Date: January 2026*
