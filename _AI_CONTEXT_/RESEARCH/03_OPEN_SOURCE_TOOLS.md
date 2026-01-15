# Open Source Tools & Libraries Reference

## Purpose

Catalog of useful open-source tools for **methods, algorithms, and code components** - not product features to copy.

---

## Essential Libraries (Already Using or Should Use)

### Data Access

| Library | Purpose | Link |
|---------|---------|------|
| **stravalib** | Strava API v3 wrapper (OAuth, pagination, rate limiting) | https://github.com/stravalib/stravalib |
| **python-fitparse** | Parse Garmin FIT files | https://github.com/dtcooper/python-fitparse |
| **gpxpy** | GPX/TCX parsing, elevation smoothing, segment extraction | https://github.com/tkrajina/gpxpy |
| **python-garminconnect** | Garmin Connect API (sleep, HRV, body comp) | https://github.com/cyberjunky/python-garminconnect |
| **python-ouraring** | Oura Ring API (sleep stages, HRV, readiness) | https://github.com/turing-complet/python-ouraring |

### Signal Processing

| Library | Purpose | Link |
|---------|---------|------|
| **NeuroKit2** | HRV/ECG signal processing, scientific-grade calculations | https://github.com/neuropsychology/NeuroKit |
| **scipy.signal** | Butterworth filtering, peak detection | Built-in |
| **numpy** | Numerical operations, FFT for frequency-domain HRV | Built-in |

### Statistics

| Library | Purpose | Link |
|---------|---------|------|
| **statsmodels** | Granger causality, time series analysis, regression | https://github.com/statsmodels/statsmodels |
| **scipy.stats** | t-tests, Mann-Whitney, correlation coefficients | Built-in |
| **scikit-learn** | Clustering, classification, feature importance | Built-in |

---

## Reference Implementations (Extract Algorithms From)

### Tier 1: Critical Value

| Project | What to Extract | Link |
|---------|-----------------|------|
| **fit.ly** | HRV correlation algorithms, Oura integration, training load visualization, Plotly Dash patterns | https://github.com/ethanopp/fitly |
| **Runalyze** | VO2max calculation, TRIMP formulas, marathon shape predictor, efficiency trending | https://github.com/codeproducer198/Runalyze |
| **GoldenCheetah** | Banister model, Critical Power/Speed, HRV analysis, W' balance | https://github.com/GoldenCheetah/GoldenCheetah |

### Tier 2: High Value

| Project | What to Extract | Link |
|---------|-----------------|------|
| **Endurain** | FastAPI patterns for Garmin sync, sleep/weight logging, PostgreSQL schema | https://github.com/endurain-project/endurain |
| **FitTrackee** | Activity file parsers, OAuth2 implementation, weather integration | https://github.com/SamR1/FitTrackee |
| **wger** | Nutrition API integration, Open Food Facts, macro tracking | https://github.com/wger-project/wger |
| **floodlight** | Metabolic power calculations, velocity/acceleration models | https://github.com/floodlight-sports/floodlight |

### Tier 3: Reference

| Project | What to Extract | Link |
|---------|-----------------|------|
| **Statistics for Strava** | PR detection algorithms, segment statistics, Eddington number | https://github.com/robiningelbrecht/statistics-for-strava |
| **gpxpy** | Elevation gain calculation, segment extraction, GPS smoothing | https://github.com/tkrajina/gpxpy |

---

## Nutrition Data Sources

| Source | Type | Notes |
|--------|------|-------|
| **Open Food Facts** | API/Database | Free, 2M+ products, barcode scanning | https://world.openfoodfacts.org/data |
| **wger API** | REST API | Self-hosted, integrates Open Food Facts |
| **USDA FoodData Central** | API | Official US nutrition database | https://fdc.nal.usda.gov/api-guide.html |

---

## Code Patterns Worth Adopting

### From fit.ly: Multi-Source Data Fusion

```python
# Pattern: Unified data model from multiple sources
class UnifiedHealthMetric:
    """Combine data from Oura, Garmin, Strava into single timeline"""
    
    def get_hrv(self, date: date) -> Optional[float]:
        """Try sources in priority order"""
        if self.oura_connected:
            return self.oura.get_hrv(date)
        elif self.garmin_connected:
            return self.garmin.get_hrv(date)
        return None
```

### From Runalyze: Efficiency Factor Calculation

```php
// Runalyze pattern (PHP) - port to Python
$efficiency_factor = $pace_in_m_per_min / $heart_rate;

// Normalized version
$normalized_ef = ($threshold_pace / $actual_pace) / ($actual_hr / $threshold_hr);
```

### From GoldenCheetah: Time-Series Modeling

```cpp
// Banister model pattern (C++) - port to Python
double fitness = 0, fatigue = 0;
for (int i = 0; i < days; i++) {
    double impulse = training_impulse[i];
    fitness = fitness * exp(-1.0/tau_fitness) + impulse;
    fatigue = fatigue * exp(-1.0/tau_fatigue) + impulse;
    performance[i] = fitness - fatigue;
}
```

---

## What NOT to Copy

| Anti-Pattern | Why It's Bad | Better Approach |
|--------------|--------------|-----------------|
| Generic "recovery scores" | Population averages, not individual | Personal fingerprinting |
| Fixed thresholds (e.g., "HRV < 50 = bad") | Individual baseline varies 10x | Deviation from YOUR baseline |
| Daily engagement prompts | Gimmick, not insight | Surface only when meaningful |
| Prescriptive language ("you should...") | N=1 philosophy violation | "Data suggests... Test it." |
| Gamification (streaks, badges) | Engagement trick, not value | Real insights create engagement |

---

## License Considerations

| License | Can Use | Must Do |
|---------|---------|---------|
| MIT | ✅ Yes | Include copyright notice |
| Apache 2.0 | ✅ Yes | Include license, state changes |
| GPL v3 | ⚠️ Careful | Derivative works must be GPL |
| AGPL | ⚠️ Careful | Network use triggers copyleft |
| Proprietary | ❌ No | Cannot use |

**StrideIQ approach:** Extract ALGORITHMS and METHODS (mathematical concepts are not copyrightable), reimplement in our own code. Do NOT copy code directly unless MIT/Apache licensed.

---

*Last updated: January 2026*
