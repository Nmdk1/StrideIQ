# StrideIQ Plan Archetype Matrix

**Version:** 1.0  
**Date:** January 11, 2026  
**Purpose:** Define the complete set of plan archetypes to build

---

## Philosophy (from knowledge base)

1. **Age adjustments at pace calculation, not structure** - Same periodization for all ages
2. **Standardized first, personalization later** - These archetypes work with zero data
3. **Template structures + generator logic** - Not 92 static files

---

## The Matrix

### Dimensions

| Dimension | Options | Notes |
|-----------|---------|-------|
| **Distance** | 5K, 10K, Half Marathon, Marathon | 4 options |
| **Mileage Tier** | Low, Mid, High, Monster | 4 options |
| **Days/Week** | 4, 5, 6, 7 | 4 options (not all combos valid) |
| **Duration** | 8, 12, 16, 18 weeks | Race-dependent |

### Valid Combinations

Not every combination makes sense. A mileage monster doesn't run 4 days/week.

```
MARATHON (18 weeks default, 12-week option):
├── Low Mileage (25-40 mpw peak)
│   ├── 4 days/week ✓
│   ├── 5 days/week ✓
│   └── 6 days/week (stretch)
├── Mid Mileage (40-55 mpw peak) ← BUILT: marathon_mid_6d_18w
│   ├── 5 days/week ✓ (TODO)
│   └── 6 days/week ✓ (DONE)
├── High Mileage (55-75 mpw peak)
│   ├── 5 days/week ✓
│   ├── 6 days/week ✓
│   └── 7 days/week ✓
└── Monster (75-100+ mpw peak)
    ├── 6 days/week ✓
    └── 7 days/week ✓

HALF MARATHON (12 weeks default, 16-week option):
├── Low Mileage (20-35 mpw peak)
│   ├── 4 days/week ✓
│   └── 5 days/week ✓
├── Mid Mileage (35-50 mpw peak)
│   ├── 5 days/week ✓
│   └── 6 days/week ✓
├── High Mileage (50-65 mpw peak)
│   └── 6 days/week ✓
└── Monster (65+ mpw peak)
    └── 7 days/week ✓

10K (10 weeks default, 12-week option):
├── Low Mileage (15-30 mpw peak)
│   ├── 4 days/week ✓
│   └── 5 days/week ✓
├── Mid Mileage (30-45 mpw peak)
│   └── 5 days/week ✓
└── High Mileage (45-60 mpw peak)
    └── 6 days/week ✓

5K (8 weeks default, 10-week option):
├── Low Mileage (15-25 mpw peak)
│   ├── 4 days/week ✓
│   └── 5 days/week ✓
├── Mid Mileage (25-40 mpw peak)
│   └── 5 days/week ✓
└── High Mileage (40-55 mpw peak)
    └── 6 days/week ✓
```

---

## Priority Order (Build Sequence)

### Tier 1: Core Marathon Plans (Most Requested)
1. ✅ `marathon_mid_6d_18w` - DONE
2. `marathon_mid_5d_18w` - TODO
3. `marathon_low_5d_18w` - TODO
4. `marathon_high_6d_18w` - TODO

### Tier 2: Core Half Marathon Plans
5. `half_mid_5d_12w` - TODO
6. `half_low_4d_12w` - TODO
7. `half_high_6d_12w` - TODO

### Tier 3: Core 10K/5K Plans
8. `10k_mid_5d_10w` - TODO
9. `5k_mid_5d_8w` - TODO

### Tier 4: Duration Variants
10. `marathon_mid_6d_12w` (compressed) - TODO
11. `marathon_mid_5d_16w` (mid-length) - TODO
12. `half_mid_5d_16w` (extended) - TODO

### Tier 5: Advanced
13. `marathon_high_7d_18w` - TODO
14. `marathon_monster_7d_18w` - TODO
15. `half_high_7d_16w` - TODO

---

## Key Differences by Distance

### Marathon
- Long run peak: 22-24 miles
- MP work: In long runs (last 4-16 miles)
- T-block: Core quality workout
- Duration: 18 weeks standard

### Half Marathon
- Long run peak: 15-16 miles
- HMP work: In long runs and as tempo
- T-block: Core quality workout
- Duration: 12 weeks standard

### 10K
- Long run peak: 12-14 miles
- VO2max intervals: More prominent
- T-work: Still important
- Duration: 10 weeks standard

### 5K
- Long run peak: 10-12 miles
- VO2max intervals: Primary quality
- Speed work: Significant
- Duration: 8 weeks standard

---

## Key Differences by Mileage Tier

### Low Mileage (First-time racers, life-busy)
- Focus: Consistency, frequency
- Quality sessions: 0-1 per week
- Long run: Capped, never > 25% of weekly volume
- Recovery: Extra days

### Mid Mileage (Ready to race, not just finish)
- Focus: Durability, threshold development
- Quality sessions: 1 per week
- Long run: Progressive, proper periodization
- Recovery: Every 4th week cutback

### High Mileage (Experienced, chasing PRs)
- Focus: Full periodization, race-specific
- Quality sessions: 1-2 per week
- Long run: High volume, race simulation
- Recovery: Every 3-4 weeks

### Monster (Elite/sub-elite)
- Focus: Advanced periodization, doubles
- Quality sessions: 2 per week
- Long run: Peak volume, complex workouts
- Recovery: Built into weekly structure

---

## Next: Build marathon_mid_5d_18w

This is the 5-day variant of what we already have. Key changes from 6-day:
- Remove Saturday shakeout (merge into Friday)
- Thursday becomes dual-purpose (quality OR easy)
- Tuesday medium-long stays
- Weekly structure more compressed

Will build now.
