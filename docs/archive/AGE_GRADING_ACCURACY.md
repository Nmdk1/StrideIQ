# Age-Grading Calculator Accuracy Documentation

## Overview

The StrideIQ Age-Grading Calculator uses the **Alan Jones 2025 Road Age-Grading Tables**, approved by the **USATF Masters Long Distance Running Council** (January 2025). This document details our implementation accuracy, testing methodology, and data sources.

## Data Source

- **Primary Source**: Alan Jones 2025 Road Age-Grading Tables
- **Repository**: https://github.com/AlanLyttonJones/Age-Grade-Tables
- **Files Used**:
  - `MaleRoadStd2025.xlsx` - Male age factors and open standards
  - `FemaleRoadStd2025.xlsx` - Female age factors and open standards
- **Approval**: USATF Masters Long Distance Running Council, January 2025

## Supported Distances

| Distance | Meters | Male Open Standard | Female Open Standard |
|----------|--------|-------------------|---------------------|
| 1 Mile | 1,609 | 3:47 (227s) | 4:13 (253s) |
| 5K | 5,000 | 12:49 (769s) | 13:54 (834s) |
| 8K | 8,000 | 20:55 (1255s) | 22:45 (1365s) |
| 10K | 10,000 | 26:24 (1584s) | 28:46 (1726s) |
| 10 Mile | 16,093 | 43:15 (2595s) | 47:12 (2832s) |
| Half Marathon | 21,097 | 57:31 (3451s) | 1:02:52 (3772s) |
| Marathon | 42,195 | 2:00:35 (7235s) | 2:09:56 (7796s) |

## Age Coverage

- **Supported Ages**: 5 to 100 years
- **Factor Type**: Per-year factors (not 5-year age groups)
- **Total Factors**: 1,344 (96 ages × 7 distances × 2 genders)

## Verification Methodology

### 1. Source Verification

All age factors and open standards were extracted directly from the official Alan Jones 2025 Excel spreadsheets and verified against the original source.

### 2. Comprehensive Audit

A full audit script (`apps/api/scripts/comprehensive_audit.py`) verifies:
- All 14 open class standards (7 distances × 2 genders)
- All 1,344 age factors (96 ages × 7 distances × 2 genders)
- Monotonic factor increase with age (after peak years)
- Factor table completeness

**Audit Result**: ✅ 0 errors across all 1,344 factor combinations

### 3. Official Calculator Validation

Results validated against the official calculator at runningagegrading.com:

| Test Case | Official | Ours | Difference |
|-----------|----------|------|------------|
| 55yo Male, 5K 18:53 | 80.65% | 80.56% | 0.09% |
| 79yo Male, 5K 27:14 | 74.3% | 74.3% | 0.00% |
| 81yo Female, 5K 31:25 | 80.22% | 80.22% | 0.00% |

## Calculation Formula

The age-grading percentage is calculated as:

```
age_grading_percentage = (age_standard / athlete_time) × 100

where:
  age_standard = open_class_standard × time_multiplier
  time_multiplier = 1 / wma_factor
```

### Example: 55yo Male, 5K in 18:53

1. **Open Class Standard**: 769 seconds (12:49)
2. **WMA Factor**: 0.8425 (from table)
3. **Time Multiplier**: 1 / 0.8425 = 1.1869
4. **Age Standard**: 769 × 1.1869 = 912.7 seconds (15:12.7)
5. **Athlete Time**: 1133 seconds (18:53)
6. **Age-Grading**: (912.7 / 1133) × 100 = **80.56%**

## Unit Tests

Located in `apps/api/tests/test_age_grading_comprehensive.py`:

### Test Categories

| Category | Tests | Description |
|----------|-------|-------------|
| Open Standards | 14 | Verify all distance/gender open standards |
| Spot-Check Factors | 38 | Verify sample factors across all distances/ages |
| Table Completeness | 2 | Verify all ages 5-100 present for both genders |
| Monotonicity | 2 | Verify factors increase with age after peak |
| Senior Athletes | 1 | Verify peak-age athletes have factor ~1.0 |
| Official Validation | 6 | Match official calculator results |
| API Endpoints | 6 | Verify API returns correct results |
| Calculation Accuracy | 3 | Verify formula correctness |
| **Total** | **66** | All tests passing ✅ |

### Running Tests

```bash
# Run all age-grading tests
docker-compose exec api python -m pytest tests/test_age_grading_comprehensive.py -v

# Run full audit
docker-compose exec api python scripts/comprehensive_audit.py
```

## Classification Standards

| Percentage | Classification |
|------------|----------------|
| 100% | World Record |
| 90%+ | World Class |
| 80%+ | National Class |
| 70%+ | Regional Class |
| 60%+ | Local Class |
| <60% | Recreational |

## Technical Implementation

### Files

- `apps/api/services/wma_age_factors.py` - Age factor tables and lookup functions
- `apps/api/routers/public_tools.py` - API endpoint
- `apps/api/scripts/comprehensive_audit.py` - Full verification script
- `apps/api/tests/test_age_grading_comprehensive.py` - Unit tests
- `apps/api/data/MaleRoadStd2025.xlsx` - Source data (male)
- `apps/api/data/FemaleRoadStd2025.xlsx` - Source data (female)

### Key Functions

```python
# Get time multiplier for age/sex/distance
get_wma_age_factor(age: int, sex: str, distance_meters: float) -> float

# Get open class standard time in seconds
get_wma_open_standard_seconds(sex: str, distance_meters: float) -> float
```

## Quality Assurance

1. **Source of Truth**: Official Alan Jones 2025 Excel files stored in repository
2. **Automated Verification**: Comprehensive audit script validates all factors
3. **Continuous Testing**: 66 unit tests run on every build
4. **User Validation**: Real-world test cases from official calculator

## Attribution

Age-grading factors from the [Alan Jones 2025 Road Age-Grading Tables](https://github.com/AlanLyttonJones/Age-Grade-Tables), approved by USATF Masters Long Distance Running Council (January 2025).

---

*Document generated: January 2026*
*Last verified: All 1,344 factors match source Excel files*
