# Race Detection & Age-Grading Fixes Applied
**Date:** January 4, 2026

## Issues Fixed

### 1. Race Detection - Too Sensitive ✅ FIXED
**Problem:** System was marking too many activities as races (10+ activities marked as races when only 2-3 were actual races).

**Solution:**
- Increased confidence threshold from 0.60 to 0.80 (0.85 for 5K races)
- Made standard distance match REQUIRED (non-standard distances automatically excluded)
- Increased HR intensity requirement (>88% for longer distances, >90% for 5K)
- Made HR data REQUIRED (no HR = not a race)
- Stricter pace consistency requirements

**Results:**
- Before: 10+ activities marked as races
- After: 3 activities marked as races
  - 12/13/2025 - 6.28mi (10K) ✓ Correct
  - 11/29/2025 - 13.18mi (Half Marathon) ✓ Correct
  - 8/30/2025 - 3.13mi (5K) - May need manual verification

### 2. Age-Grading Not Populating ✅ FORMULA FIXED
**Problem:** Age-grading showing "--" for all activities.

**Root Cause:** 
- Athlete missing `birthdate` and `sex` in database
- Age-grading formula was incorrect

**Solution:**
- Fixed age-grading formula to use proper WMA calculation:
  - Age-graded pace = Actual pace / Age factor
  - Performance % = (World Record Pace / Age-graded pace) * 100
- Added reference world record paces for different distances
- Added sex adjustment for women's records

**Status:**
- Formula is now correct
- **REQUIRES USER ACTION:** Athlete must have `birthdate` and `sex` set in database for age-grading to work
- Once birthdate/sex are set, age-grading will populate automatically on next sync

### 3. Race Detection Logic Improvements ✅ COMPLETE

**Changes Made:**
1. **Standard Distance Requirement:** Only activities matching standard race distances (5K, 10K, Half, Full) can be races
2. **HR Intensity:** Increased threshold to >88% (5K requires >90%)
3. **Confidence Threshold:** Increased to 0.80 (0.85 for 5K)
4. **HR Data Required:** Activities without HR data cannot be marked as races

**Files Modified:**
- `apps/api/services/performance_engine.py` - Updated `detect_race_candidate()` function
- `apps/api/scripts/fix_race_detection.py` - Created script to reset and recalculate all races

## Next Steps

### For Age-Grading to Work:
1. Set athlete `birthdate` in database
2. Set athlete `sex` in database ('M' or 'F')
3. Run sync or recalculate metrics

### For Production WMA Tables:
- Current implementation uses simplified factors and reference paces
- For production, need to integrate official WMA age-grading tables
- Options:
  1. Download WMA tables from official website
  2. Convert to JSON/database format
  3. Integrate into `get_wma_age_factor()` function
  4. Update `calculate_age_graded_performance()` to use official world record paces

## Testing

Run the fix script to reset and recalculate:
```bash
docker compose exec api python scripts/fix_race_detection.py
```

Check races detected:
```bash
docker compose exec api python -c "from database import SessionLocal; from models import Activity; db = SessionLocal(); races = db.query(Activity).filter(Activity.is_race_candidate == True).all(); print(f'Races: {len(races)}'); [print(f'  {r.start_time.date()} - {r.distance_m/1609.34:.2f}mi') for r in races]; db.close()"
```

## Summary

✅ Race detection is now much more accurate (3 races vs 10+)
✅ Age-grading formula is correct
⚠️ Age-grading requires birthdate/sex to be set
⚠️ WMA tables need to be integrated for production-grade accuracy


