# Correlation & Causation Methodology

## Core Principle

**Correlation is not causation, but proper methodology can establish causation.**

StrideIQ's differentiator is rigorous causal inference, not surface-level correlations.

---

## The Five Tests for Actionable Insights

Every insight must pass ALL five tests before surfacing to the user:

| Test | Question | Failure Mode |
|------|----------|--------------|
| **Repeatability** | Does this pattern hold across multiple instances? | One-off coincidence |
| **Mechanism** | Is there a plausible physiological explanation? | Spurious correlation |
| **Actionability** | Can the athlete DO something with this? | Interesting but useless |
| **Falsifiability** | Can we test if this is wrong? | Unfounded belief |
| **Individuality** | Does this hold for THIS athlete, not just "athletes"? | Population-level noise |

---

## Granger Causality Testing

### What It Is

Statistical test that determines whether one time series is useful in forecasting another. If X "Granger-causes" Y:
- Past values of X improve prediction of Y
- Beyond what Y's own past values provide

### Implementation

```python
from statsmodels.tsa.stattools import grangercausalitytests

def test_granger_causality(
    cause_series: List[float],  # e.g., sleep hours
    effect_series: List[float],  # e.g., next-day efficiency
    max_lag: int = 7
) -> dict:
    """
    Test if cause_series Granger-causes effect_series.
    
    Returns:
        best_lag: Lag with strongest causality
        p_value: Statistical significance
        f_stat: F-statistic
    """
    # Combine into DataFrame
    data = pd.DataFrame({
        'cause': cause_series,
        'effect': effect_series
    })
    
    # Run Granger test at multiple lags
    results = grangercausalitytests(data[['effect', 'cause']], maxlag=max_lag, verbose=False)
    
    # Find best lag
    best_lag = None
    best_p = 1.0
    
    for lag, test_result in results.items():
        p_value = test_result[0]['ssr_ftest'][1]  # p-value from F-test
        if p_value < best_p:
            best_p = p_value
            best_lag = lag
    
    return {
        'best_lag': best_lag,
        'p_value': best_p,
        'is_significant': best_p < 0.05,
        'f_stat': results[best_lag][0]['ssr_ftest'][0]
    }
```

### Interpretation

| P-Value | Confidence | Action |
|---------|------------|--------|
| < 0.01 | High | Surface as "established pattern" |
| 0.01 - 0.05 | Moderate | Surface with caveat |
| 0.05 - 0.10 | Suggestive | Track but don't surface yet |
| > 0.10 | No evidence | Do not surface |

---

## Dual-Frequency Analysis

Different inputs operate on different timescales:

### Acute Readiness Factors (0-7 day lag)

| Input | Typical Lag | Mechanism |
|-------|-------------|-----------|
| Sleep (last night) | 0-1 days | Recovery, hormone regulation |
| HRV | 0-2 days | Autonomic readiness |
| Stress (subjective) | 0-3 days | Cortisol, fatigue |
| Nutrition (day of) | 0 days | Glycogen, hydration |

### Chronic Adaptation Factors (14-42 day lag)

| Input | Typical Lag | Mechanism |
|-------|-------------|-----------|
| Training volume | 21-42 days | Aerobic base building |
| Intensity distribution | 14-28 days | Lactate threshold adaptation |
| Strength training | 28-42 days | Neuromuscular adaptation |
| Weight change | 14-21 days | Running economy impact |

### Implementation

```python
def dual_frequency_analysis(
    input_series: pd.Series,
    output_series: pd.Series,
    input_name: str
) -> dict:
    """
    Test input at both acute and chronic timescales.
    """
    # Acute window (0-7 days)
    acute_result = test_granger_causality(
        input_series, output_series, max_lag=7
    )
    
    # Chronic window (14-42 days) - use weekly aggregates
    input_weekly = input_series.resample('W').mean()
    output_weekly = output_series.resample('W').mean()
    
    chronic_result = test_granger_causality(
        input_weekly, output_weekly, max_lag=6  # 6 weeks
    )
    
    return {
        'input': input_name,
        'acute': {
            'lag_days': acute_result['best_lag'],
            'p_value': acute_result['p_value'],
            'significant': acute_result['is_significant']
        },
        'chronic': {
            'lag_weeks': chronic_result['best_lag'],
            'p_value': chronic_result['p_value'],
            'significant': chronic_result['is_significant']
        }
    }
```

---

## Effect Size (Practical Significance)

Statistical significance ≠ practical significance. A correlation with p < 0.01 but effect size of 0.5% pace improvement is useless.

### Minimum Meaningful Effects

| Metric | Minimum Effect | Rationale |
|--------|----------------|-----------|
| Pace improvement | 2% | Below natural variation |
| Efficiency (EF) | 3% | Measurement noise |
| HRV deviation | 10% | Day-to-day variation |
| Race performance | 1% | Meaningful for competitive |

### Cohen's d for Effect Size

```python
def calculate_effect_size(
    condition_a: List[float],  # e.g., performance after good sleep
    condition_b: List[float]   # e.g., performance after poor sleep
) -> dict:
    """
    Calculate Cohen's d effect size.
    """
    mean_a = statistics.mean(condition_a)
    mean_b = statistics.mean(condition_b)
    
    # Pooled standard deviation
    n_a, n_b = len(condition_a), len(condition_b)
    var_a = statistics.variance(condition_a)
    var_b = statistics.variance(condition_b)
    
    pooled_std = sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))
    
    cohens_d = (mean_a - mean_b) / pooled_std
    
    return {
        'cohens_d': cohens_d,
        'effect_size': classify_effect_size(cohens_d),
        'mean_difference': mean_a - mean_b,
        'pct_difference': (mean_a - mean_b) / mean_b * 100
    }

def classify_effect_size(d: float) -> str:
    d = abs(d)
    if d < 0.2:
        return 'negligible'
    elif d < 0.5:
        return 'small'
    elif d < 0.8:
        return 'medium'
    else:
        return 'large'
```

---

## Controlling for Confounders

### Common Confounders in Running Data

| Apparent Relationship | Likely Confounder |
|----------------------|-------------------|
| More sleep → faster pace | Taper (more sleep AND more rest) |
| Lower HRV → better race | Race importance (anxiety affects both) |
| More mileage → slower pace | Fatigue accumulation |
| Weight loss → faster pace | Training intensity (causes both) |

### Stratified Analysis

```python
def stratified_correlation(
    x: pd.Series,
    y: pd.Series,
    stratify_by: pd.Series,
    strata: List[str]
) -> dict:
    """
    Calculate correlation within each stratum to control for confounders.
    """
    results = {}
    
    for stratum in strata:
        mask = stratify_by == stratum
        x_stratum = x[mask]
        y_stratum = y[mask]
        
        if len(x_stratum) >= 10:
            corr, p_value = pearsonr(x_stratum, y_stratum)
            results[stratum] = {
                'correlation': corr,
                'p_value': p_value,
                'n': len(x_stratum)
            }
    
    # Check if relationship holds across strata
    correlations = [r['correlation'] for r in results.values()]
    consistent = all(c > 0 for c in correlations) or all(c < 0 for c in correlations)
    
    return {
        'strata_results': results,
        'consistent_across_strata': consistent
    }
```

---

## Sample Size Requirements

### Minimum Data for Causal Claims

| Claim Type | Minimum N | Rationale |
|------------|-----------|-----------|
| "This session helped" | 1 | Single observation, no causality claim |
| "Pattern observed" | 3 | Repeated observation |
| "Suggestive relationship" | 10 | Basic statistical test |
| "Established pattern" | 30 | Reliable correlation |
| "Causal relationship" | 50+ | Granger causality power |

### Communicating Uncertainty

```python
def get_confidence_qualifier(n: int, p_value: float) -> str:
    """
    Generate appropriate language for insight based on statistical power.
    """
    if n < 3:
        return "Single observation"
    elif n < 10:
        return "Preliminary pattern (needs more data)"
    elif p_value > 0.10:
        return "No clear relationship found"
    elif p_value > 0.05:
        return "Suggestive pattern (not statistically significant)"
    elif n < 30:
        return "Emerging pattern (moderate confidence)"
    elif p_value < 0.01:
        return "Established pattern (high confidence)"
    else:
        return "Established pattern"
```

---

## Insight Surfacing Rules

### When to Show

1. ✅ Pattern passes 5 tests
2. ✅ Effect size is practically meaningful
3. ✅ Athlete can take action
4. ✅ Timing is relevant (don't show taper insight mid-build)

### When NOT to Show

1. ❌ Single occurrence
2. ❌ Statistically significant but tiny effect
3. ❌ No actionable path forward
4. ❌ Contradicts known physiology without strong evidence

### Insight Template

```
Pattern: [What we observed]
Confidence: [Statistical backing]
Sample: [N occurrences over N weeks/months]
Actionable: [What athlete could do differently]
Test it: [How to verify if this works for you]
```

**Example:**
```
Pattern: Your efficiency improved 4% on days after 7+ hours sleep
         (vs. <6 hours sleep)
Confidence: Established pattern (n=34, p<0.01)
Sample: 34 pairs over 4 months
Actionable: Prioritize sleep before key sessions
Test it: Track next 2 weeks consciously
```

---

*Last updated: January 2026*
