# HRV Research & Counter-Conventional Findings

## Critical Insight (User Data)

> "My best races were after the evening of my lowest HRV"

This observation contradicts conventional fitness app wisdom but aligns with sports science research. This document captures the nuance that consumer apps miss.

---

## The Pre-Race HRV Paradox

### Conventional Wisdom (Flawed)

| Assumption | Reality |
|------------|---------|
| High HRV = ready to race | High HRV = relaxed parasympathetic state (good for recovery, NOT racing) |
| Low HRV = overtrained/fatigued | Low HRV can = sympathetic activation (fight-or-flight priming) |
| Morning HRV predicts performance | Evening HRV before race captures anticipatory stress response |

### Why Low Pre-Race HRV Can Be GOOD

1. **Anticipatory Stress Response**
   - Before important races, autonomic nervous system shifts toward sympathetic dominance
   - This LOWERS HRV but PRIMES you for peak performance
   - Elevated cortisol, mobilized glycogen, heightened alertness

2. **Taper Supercompensation**
   - During proper taper, HRV often drops as body enters heightened readiness
   - Apps misread this as "poor recovery"
   - Actually signals successful adaptation

3. **Yerkes-Dodson Curve**
   - Optimal performance requires optimal arousal
   - Too relaxed (high HRV) = not primed
   - Chronically low HRV = overtrained
   - Race-eve low HRV = sweet spot for many athletes

4. **Individual Signatures**
   - HRV response is highly individual
   - What matters: YOUR pattern relative to YOUR baseline
   - Not absolute values or population norms

---

## Context-Aware HRV Interpretation

### Wrong Approach (What Apps Do)

```python
# Simplistic, context-free
if hrv > baseline:
    readiness = "good"
else:
    readiness = "poor"
```

### Correct Approach (What Science Says)

```python
def interpret_hrv(hrv, baseline, context):
    deviation = (hrv - baseline) / baseline
    
    if context == "race_eve":
        # INVERT the relationship for many athletes
        if -0.25 < deviation < -0.10:
            return "primed_for_performance"  # Sympathetic activation
        elif deviation > 0.10:
            return "possibly_undertapered"   # Too relaxed
        elif deviation < -0.30:
            return "over_anxious"            # Excessive stress
            
    elif context == "training_day":
        # Standard interpretation for training decisions
        if deviation > 0.05:
            return "recovered_can_push"
        elif deviation < -0.15:
            return "accumulating_fatigue"
        else:
            return "normal_proceed_as_planned"
            
    elif context == "rest_day":
        # Monitor for overtraining
        if deviation < -0.20:
            return "monitor_for_overtraining"
```

---

## HRV Metrics That Matter

### Time Domain

| Metric | What It Measures | Use Case |
|--------|------------------|----------|
| **rMSSD** | Parasympathetic activity (short-term variability) | Recovery status, most useful for daily tracking |
| **SDNN** | Overall variability | Longer-term fitness trends |
| **pNN50** | % of successive intervals differing >50ms | Parasympathetic indicator |

### Frequency Domain

| Metric | What It Measures | Use Case |
|--------|------------------|----------|
| **LF (Low Frequency)** | Mixed sympathetic/parasympathetic | Less useful in isolation |
| **HF (High Frequency)** | Parasympathetic activity | Recovery indicator |
| **LF/HF Ratio** | Sympathovagal balance | CAUTION: oversimplified in apps |

### What Actually Matters for Athletes

1. **Trend over time** (7-day rolling average vs. 30-day)
2. **Deviation from personal baseline** (not absolute value)
3. **Context** (rest day, training day, race eve)
4. **Correlation with YOUR performance outcomes**

---

## Building Personal HRV Patterns

### Step 1: Establish Baseline

```python
def calculate_hrv_baseline(hrv_readings: List[Tuple[date, float]], days: int = 30):
    """
    Calculate rolling baseline from last N days.
    Exclude outliers (illness, alcohol, travel).
    """
    recent = [v for d, v in hrv_readings if d >= today - timedelta(days=days)]
    
    # Remove outliers (>2 std from mean)
    mean = statistics.mean(recent)
    std = statistics.stdev(recent)
    cleaned = [v for v in recent if abs(v - mean) < 2 * std]
    
    return statistics.mean(cleaned)
```

### Step 2: Track Deviation Patterns

```python
def track_hrv_deviation(hrv: float, baseline: float) -> dict:
    """
    Track deviation and build pattern history.
    """
    deviation_pct = (hrv - baseline) / baseline * 100
    
    return {
        'date': today,
        'hrv': hrv,
        'baseline': baseline,
        'deviation_pct': deviation_pct,
        'deviation_class': classify_deviation(deviation_pct)
    }

def classify_deviation(pct: float) -> str:
    if pct > 15:
        return 'high_positive'
    elif pct > 5:
        return 'moderate_positive'
    elif pct > -5:
        return 'normal'
    elif pct > -15:
        return 'moderate_negative'
    else:
        return 'high_negative'
```

### Step 3: Correlate with Performance Outcomes

```python
def correlate_hrv_with_performance(
    hrv_history: List[dict],
    race_results: List[RaceResult]
) -> dict:
    """
    Find YOUR HRV-performance pattern.
    """
    correlations = []
    
    for race in race_results:
        # Get HRV deviation 24h before race
        race_eve = race.date - timedelta(days=1)
        hrv_eve = get_hrv_for_date(hrv_history, race_eve)
        
        if hrv_eve:
            correlations.append({
                'race': race,
                'hrv_deviation': hrv_eve['deviation_pct'],
                'performance_pct': race.age_graded_pct
            })
    
    # Find pattern
    best_races = sorted(correlations, key=lambda x: x['performance_pct'], reverse=True)[:3]
    worst_races = sorted(correlations, key=lambda x: x['performance_pct'])[:3]
    
    best_hrv_avg = statistics.mean([r['hrv_deviation'] for r in best_races])
    worst_hrv_avg = statistics.mean([r['hrv_deviation'] for r in worst_races])
    
    return {
        'best_race_hrv_pattern': best_hrv_avg,
        'worst_race_hrv_pattern': worst_hrv_avg,
        'pattern_type': 'inverted' if best_hrv_avg < worst_hrv_avg else 'conventional',
        'confidence': len(correlations)
    }
```

---

## Research References

1. **Plews et al. (2013)** - "Training Adaptation and Heart Rate Variability in Elite Endurance Athletes"
   - HRV decreases during heavy training, increases during taper
   - But performance peaks DURING the decrease phase, not after

2. **Stanley et al. (2013)** - "Cardiac Parasympathetic Reactivation Following Exercise"
   - Recovery HRV != readiness HRV
   - Context matters enormously

3. **Buchheit (2014)** - "Monitoring Training Status with HR Measures"
   - Individual response patterns vary significantly
   - Population norms are starting points, not answers

4. **Flatt & Esco (2016)** - "Smartphone-Derived Heart Rate Variability and Training Load"
   - Day-to-day variation is noise
   - 7-day rolling averages more meaningful

---

## Implementation in StrideIQ

### What We Should Build

1. **Personal HRV Baseline** (not population)
   - Rolling 30-day mean with outlier removal
   - Track deviation, not absolute

2. **Context-Aware Interpretation**
   - Training day vs. rest day vs. race eve
   - Different thresholds for each

3. **Pattern Discovery**
   - Correlate YOUR pre-race HRV with YOUR race outcomes
   - Surface insight only when pattern has statistical power

4. **Inverted Pattern Detection**
   - Alert when athlete shows inverted HRV-performance relationship
   - "Your best races followed evenings with HRV 15-20% below baseline"

### What We Should NOT Build

- ❌ Generic "recovery score"
- ❌ Fixed thresholds ("HRV < 50 = bad")
- ❌ Daily prescriptive guidance based on HRV alone
- ❌ Population comparisons ("you're in the 40th percentile")

---

*Last updated: January 2026*
*Note: This document includes findings from user's personal data that contradict conventional HRV wisdom*
