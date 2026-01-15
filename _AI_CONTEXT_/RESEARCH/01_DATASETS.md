# Research Datasets

## Available Datasets

### 1. Figshare Long-Distance Running Dataset (PRIMARY)

**Source:** https://figshare.com/articles/dataset/A_public_dataset_on_long-distance_running_training_in_2019_and_2020/16620238

| Metric | Value |
|--------|-------|
| Total Records | **10+ million training events** |
| Athletes | **36,000+** worldwide |
| Time Period | 2019-2020 |
| Size | ~2.5 GB |

**Contents:**
- Training activities with duration, distance, pace, elevation
- Activity types and timestamps
- Athlete anonymized IDs for longitudinal tracking

**Our Processing Goals:**
1. Filter to recreational athletes (not elites: <150km/week, >10km/week)
2. Age-grade where possible (if age/sex data available)
3. Extract patterns: volume progressions, efficiency trends, injury indicators
4. Build population baselines for "people like you" comparisons
5. Identify what ACTUALLY helps recreational runners improve

**Implementation:**
- Download script: `scripts/download_research_data.py`
- Processor: `apps/api/services/research_data/figshare_processor.py`
- Output baselines: `apps/api/services/research_data/baselines/`

**Citation:**
```
A public dataset on long-distance running training in 2019 and 2020. Figshare. 2021.
```

---

### 2. NRCD Collegiate Running Database

**Source:** https://arxiv.org/abs/2509.10600

| Metric | Value |
|--------|-------|
| Records | ~15,000 race results |
| Athletes | Collegiate runners (2023-2024) |
| Data Type | Race results, times, conditions |

**Use Cases:**
- Race prediction models
- Performance progression patterns
- Environmental impact on race times

---

### 3. Sport DB 2.0

**Source:** https://data.mendeley.com/datasets/kzkjkt7mx2/1

| Metric | Value |
|--------|-------|
| Records | 168 cardiorespiratory datasets |
| Data Type | VO2, HR, power, physiological measures |

**Use Cases:**
- Validate VO2max estimation algorithms
- Understand cardiorespiratory relationships
- Heart rate dynamics research

---

### 4. Alan Jones 2025 Age-Grading Tables (IMPLEMENTED)

**Source:** https://github.com/AlanLyttonJones/Age-Grade-Tables

| Metric | Value |
|--------|-------|
| Coverage | Ages 5-100, Male/Female |
| Distances | 7 road distances (1 Mile → Marathon) |
| Factors | 1,344 per-year age factors |
| Approval | USATF Masters Long Distance Running Council (Jan 2025) |

**Status:** ✅ Fully implemented and verified
- See: `docs/AGE_GRADING_ACCURACY.md`
- Implementation: `apps/api/services/wma_age_factors.py`
- Tests: `apps/api/tests/test_age_grading_comprehensive.py`

---

## Population Baselines Generated

From the Figshare dataset, we extract cohort baselines:

| Cohort | Weekly Volume | Use Case |
|--------|---------------|----------|
| 10-20km_week | Beginner | "People building to 5K" |
| 20-40km_week | Recreational | "Casual runners, 5K-10K focus" |
| 40-60km_week | Local Competitive | "Half marathon builders" |
| 60-80km_week | Competitive | "Marathon prep" |
| 80+km_week | Serious Competitive | "High-volume trainers" |

Each baseline includes:
- Volume distribution (mean, median, P25, P75)
- Typical easy pace
- Volume progression rate
- Risky volume increase thresholds

---

## Data Ethics

1. **Privacy:** All research data is anonymized at source
2. **Consent:** Public datasets with appropriate research licenses
3. **Attribution:** Proper citation in documentation and any publications
4. **Individual Data:** User's own data remains theirs; research data informs, not overrides

---

*Last updated: January 2026*
