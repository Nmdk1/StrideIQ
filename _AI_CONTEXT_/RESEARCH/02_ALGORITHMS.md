# Computational Methods & Algorithms

## Priority Methods to Implement

These algorithms enable **precise, repeatable, actionable insights** - not engagement gimmicks.

---

## 1. Effective VO2max from HR/Pace Regression

**Source:** Runalyze (codeproducer198/Runalyze)
**Scientific Basis:** Léger & Mercier oxygen cost equations

### What It Does
Estimates VO2max for each activity by analyzing the relationship between heart rate and pace. Unlike static fitness tests, this provides a continuous fitness signal from regular training.

### Why It Matters
- Detects fitness changes **2-3 weeks before race times reflect them**
- Identifies whether pace improvement is fitness gain vs. favorable conditions
- Enables "VO2max at current weight vs. goal weight" projections

### Key Formula
```
VO2 = -4.60 + 0.182 * velocity + 0.000104 * velocity^2  (ml/kg/min)

where velocity = meters per minute

Effective VO2max = VO2 / (HR / HRmax)
```

### Implementation Notes
- Requires: pace, HR, estimated HRmax
- Best from: threshold or tempo efforts (not easy runs)
- Trend over time is more valuable than single-point estimate

---

## 2. Critical Speed + D' Model (Running-Adapted CP)

**Source:** GoldenCheetah (adapted from cycling Critical Power)
**Scientific Basis:** Hyperbolic power-duration relationship

### What It Does
Fits a hyperbolic curve to distance/time PRs to identify two key parameters:
- **Critical Speed (CS):** Speed you can theoretically sustain indefinitely (aerobic ceiling)
- **D' (D-prime):** Anaerobic distance reserve above CS

### Why It Matters
- Predicts precise pacing for any race distance
- Identifies which energy system limits you (aerobic vs. anaerobic)
- Quantifies the trade-off between going out fast vs. steady

### Key Formula
```
Time = D' / (Speed - CS) + Distance / CS

Rearranged for speed:
Speed = CS + D' / Time
```

### From PRs
```python
def fit_critical_speed(prs: List[Tuple[distance_m, time_s]]):
    """
    Fit CS and D' from PR data.
    
    Minimum 3 PRs at different distances (e.g., 1 mile, 5K, 10K)
    """
    # Linear regression on: distance = CS * time + D'
    times = [pr[1] for pr in prs]
    distances = [pr[0] for pr in prs]
    
    # Solve: distance = CS * time + D'
    # Using least squares
    CS, D_prime = linear_regression(times, distances)
    
    return CS, D_prime  # m/s, meters
```

---

## 3. Banister Impulse-Response Model (Fitness/Fatigue)

**Source:** GoldenCheetah
**Scientific Basis:** Banister et al. (1975) systems model

### What It Does
Models performance as the difference between accumulated fitness and accumulated fatigue, each with different decay rates.

### Why It Matters
- Identifies YOUR optimal taper length (not generic "2 weeks")
- Predicts performance windows
- Quantifies when you're "fresh but fit" vs. "tired but fit"

### Key Formula
```
Performance(t) = Fitness(t) - Fatigue(t)

Fitness(t) = Σ [w(i) * k1 * e^(-(t-i)/τ1)]
Fatigue(t) = Σ [w(i) * k2 * e^(-(t-i)/τ2)]

where:
  w(i) = training impulse on day i
  τ1 = fitness decay constant (~42 days typical)
  τ2 = fatigue decay constant (~7 days typical)
  k1, k2 = scaling factors
```

### Individual Calibration
The key insight: τ1 and τ2 vary by individual. Elite: faster response. Masters: slower recovery. Discover YOUR time constants from YOUR data.

---

## 4. Training Stress Balance (TSB)

**Source:** fit.ly (ethanopp/fitly), TrainingPeaks methodology
**Scientific Basis:** Simplified Banister model

### What It Does
Tracks chronic training load (CTL/fitness) vs. acute training load (ATL/fatigue) to compute training stress balance.

### Key Metrics
```
CTL (Fitness) = 42-day exponential moving average of daily TSS
ATL (Fatigue) = 7-day exponential moving average of daily TSS
TSB (Form) = CTL - ATL
```

### TSS (Training Stress Score) for Running
```python
def calculate_running_tss(duration_sec, intensity_factor):
    """
    TSS = (duration * IF^2 * 100) / 3600
    
    IF = intensity factor = actual_pace / threshold_pace
    """
    return (duration_sec * intensity_factor**2 * 100) / 3600
```

### Actionable Zones
| TSB Range | State | Action |
|-----------|-------|--------|
| +15 to +25 | Fresh & fit | Race window |
| +5 to +15 | Recovering | Final taper |
| -10 to +5 | Optimal training | Continue building |
| -30 to -10 | Overreaching | Reduce volume |
| < -30 | Overtraining risk | Rest urgently |

---

## 5. Heart Rate Efficiency Trending

**Source:** Runalyze
**Scientific Basis:** Cardiac drift, aerobic efficiency

### What It Does
Tracks the ratio of pace to heart rate at standardized effort levels over time.

### Key Metric
```
Efficiency Factor (EF) = Pace (m/min) / HR (bpm)

# Or normalized:
EF = (Threshold_Pace / Actual_Pace) / (Actual_HR / Threshold_HR)
```

### Why It Matters
- Detects aerobic fitness changes independent of motivation/conditions
- Identifies cardiac drift within runs (fatigue marker)
- Separates "running faster" from "running more efficiently"

### Trend Interpretation
| EF Trend | Meaning |
|----------|---------|
| Increasing | Aerobic fitness improving |
| Stable | Maintenance phase |
| Decreasing | Fatigue accumulation, possible overtraining |

---

## 6. Metabolic Power from Velocity/Acceleration

**Source:** floodlight (floodlight-sports/floodlight)
**Scientific Basis:** di Prampero energy cost model

### What It Does
Quantifies the true physiological cost of variable-pace running by accounting for accelerations/decelerations.

### Why It Matters
- Interval sessions "feel" harder than steady runs - this quantifies why
- Enables fair comparison between variable and steady efforts
- Better load estimation for hilly or technical terrain

### Key Formula
```
Metabolic Power (W/kg) = EC * v

where:
  EC = Energy cost (J/kg/m) = 3.6 + 1.8 * sin(slope) + c * a
  v = instantaneous velocity (m/s)
  a = acceleration (m/s²)
  c = coefficient (~0.4 for running)
```

---

## 7. Pace Decay Analysis

**Source:** Custom (no one does this right)

### What It Does
Quantifies how YOUR pace degrades in final race segments, normalized for environmental factors.

### Why It Matters
- Identifies fueling gaps (glycogen depletion signature)
- Reveals pacing discipline issues
- Prescribes specific interventions

### Implementation
```python
def analyze_pace_decay(splits: List[float], distance: float):
    """
    Analyze pace decay pattern in race.
    
    Returns:
        decay_type: 'positive_split', 'negative_split', 'even', 'collapse'
        decay_rate: % slowdown per segment
        inflection_point: where decay accelerates (if applicable)
    """
    # Normalize splits to first half average
    first_half = splits[:len(splits)//2]
    second_half = splits[len(splits)//2:]
    
    first_avg = statistics.mean(first_half)
    second_avg = statistics.mean(second_half)
    
    decay_pct = (second_avg - first_avg) / first_avg * 100
    
    # Look for collapse (sudden >10% slowdown)
    for i, pace in enumerate(splits):
        if i > 0 and (pace - splits[i-1]) / splits[i-1] > 0.10:
            collapse_point = i
            break
    
    return {
        'decay_pct': decay_pct,
        'collapse_point': collapse_point if collapse_point else None,
        'pattern': classify_pattern(decay_pct)
    }
```

---

## 8. Pre-Race State Fingerprinting

**Source:** Custom - critical gap in existing tools

### What It Does
Cluster analysis of physiological state (HRV, sleep, training load, subjective readiness) before your BEST vs. WORST races to identify your personal readiness signature.

### Why It Matters (User's Own Data)
> "My best races were after the evening of my lowest HRV"

This contradicts conventional HRV wisdom. The algorithm must discover YOUR pattern, not impose population averages.

### Implementation Approach
```python
def fingerprint_pre_race_state(races: List[RaceResult]):
    """
    Build clusters of pre-race states for best vs worst performances.
    """
    features = []
    labels = []  # 'best', 'average', 'worst'
    
    for race in races:
        # Extract state 24-48h before race
        pre_race_state = {
            'hrv_vs_baseline': get_hrv_deviation(race.date - 1d),
            'sleep_quality': get_sleep_score(race.date - 1d),
            'training_load_7d': get_atl(race.date),
            'tsb': get_tsb(race.date),
            'days_since_last_hard': get_days_since_intensity(race.date),
        }
        features.append(pre_race_state)
        labels.append(classify_race_performance(race))
    
    # Find distinguishing features
    best_races = [f for f, l in zip(features, labels) if l == 'best']
    worst_races = [f for f, l in zip(features, labels) if l == 'worst']
    
    # Statistical comparison
    for feature in features[0].keys():
        best_values = [r[feature] for r in best_races]
        worst_values = [r[feature] for r in worst_races]
        
        # t-test or Mann-Whitney
        significance = statistical_test(best_values, worst_values)
        
        if significance < 0.05:
            yield f"Feature {feature} differs significantly: " \
                  f"Best={mean(best_values):.2f}, Worst={mean(worst_values):.2f}"
```

---

## Implementation Priority

| Algorithm | Value | Complexity | Priority |
|-----------|-------|------------|----------|
| Efficiency Trending | High | Low | **1 - Now** |
| Pre-Race Fingerprinting | Critical | Medium | **2 - Next** |
| TSB/ATL/CTL | High | Low | **3** |
| Critical Speed Model | High | Medium | **4** |
| Pace Decay Analysis | Medium | Low | **5** |
| Banister Model | Medium | High | **6** |
| Metabolic Power | Low | High | Later |

---

*Last updated: January 2026*
