# Builder Handoff: ADR-048 Dynamic Insight Suggestions

**Date:** 2026-01-19  
**ADR:** ADR-048  
**Status:** Ready for Implementation

---

## Objective

Replace static suggestions in `get_dynamic_suggestions()` with data-driven suggestions using existing coach tools and insight aggregator.

---

## File to Modify

`apps/api/services/ai_coach.py`

---

## Changes Required

### 1. Replace `get_dynamic_suggestions()` method (lines 523-636)

Replace the entire method body with:

```python
def get_dynamic_suggestions(self, athlete_id: UUID) -> List[str]:
    """
    Return 3-5 data-driven suggested questions.
    
    Sources:
    - coach_tools.get_active_insights (prioritized insights)
    - coach_tools.get_pb_patterns (recent PBs)
    - coach_tools.get_training_load (TSB state)
    - coach_tools.get_efficiency_by_zone (efficiency trends)
    """
    suggestions: List[str] = []

    def add(q: str) -> None:
        if q and q not in suggestions and len(suggestions) < 5:
            suggestions.append(q)

    today = date.today()

    # --- 1. Insights from coach_tools.get_active_insights ---
    try:
        result = coach_tools.get_active_insights(self.db, athlete_id, limit=3)
        if result.get("ok"):
            for ins in result.get("data", {}).get("insights", []):
                q = self._insight_to_question(ins)
                if q:
                    add(q)
    except Exception:
        pass

    # --- 2. PB-driven suggestions ---
    try:
        result = coach_tools.get_pb_patterns(self.db, athlete_id)
        if result.get("ok"):
            data = result.get("data") or {}
            pb_count = data.get("pb_count", 0)
            tsb_range = data.get("optimal_tsb_range")
            if pb_count >= 2 and tsb_range:
                add(f"You have {pb_count} PRs with optimal TSB {tsb_range[0]:.0f} to {tsb_range[1]:.0f}. What's your secret?")
    except Exception:
        pass

    # --- 3. TSB-driven suggestions ---
    try:
        result = coach_tools.get_training_load(self.db, athlete_id)
        if result.get("ok"):
            tsb = result.get("data", {}).get("tsb")
            if tsb is not None:
                if tsb > 20:
                    add(f"Your TSB is +{tsb:.0f} — you're fresh. Ready for a hard effort?")
                elif tsb < -30:
                    add(f"Your TSB is {tsb:.0f} — heavy fatigue. Should we discuss recovery?")
    except Exception:
        pass

    # --- 4. Efficiency-driven suggestions ---
    try:
        result = coach_tools.get_efficiency_by_zone(self.db, athlete_id, "threshold", 90)
        if result.get("ok"):
            trend = result.get("data", {}).get("recent_trend_pct")
            if trend is not None:
                if trend < -10:
                    add(f"Your threshold efficiency improved {abs(trend):.0f}% recently. What's working?")
                elif trend > 10:
                    add(f"Your threshold efficiency dropped {trend:.0f}% — want to investigate?")
    except Exception:
        pass

    # --- 5. Recent activity suggestions ---
    try:
        start_of_today = datetime.combine(today, datetime.min.time())
        completed_today = (
            self.db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
                Activity.start_time >= start_of_today,
            )
            .first()
        )
        if completed_today:
            distance_km = (completed_today.distance_m or 0) / 1000
            add(f"You ran {distance_km:.1f} km today. How did it feel?")
    except Exception:
        pass

    # --- Fallback defaults ---
    if len(suggestions) < 3:
        add("How is my training going overall?")
        add("Am I on track for my goal?")

    return suggestions[:5]
```

### 2. Add `_insight_to_question()` helper method

Add this new method after `get_dynamic_suggestions()`:

```python
def _insight_to_question(self, insight: Dict[str, Any]) -> Optional[str]:
    """Convert an insight dict to a question format."""
    title = insight.get("title") or ""
    if not title:
        return None
    
    title_lower = title.lower()
    if "improving" in title_lower:
        return f"{title} — what's driving this?"
    elif "declining" in title_lower or "drop" in title_lower:
        return f"{title} — should we investigate?"
    elif "pattern" in title_lower:
        return f"{title} — is this intentional?"
    elif "risk" in title_lower or "warning" in title_lower:
        return f"{title} — what should I do?"
    else:
        return f"{title} — tell me more?"
```

---

## Key Implementation Notes

1. **Use coach_tools, NOT insight_aggregator directly**
   - ADR pseudocode showed `from services.insight_aggregator import get_active_insights`
   - CORRECT: Use `coach_tools.get_active_insights(self.db, athlete_id, limit=3)`
   - The coach_tools version returns `{"ok": True, "data": {"insights": [...]}}` format

2. **insight structure from coach_tools**
   - Returns dicts, not objects
   - Access via `insight.get("title")`, not `insight.title`

3. **coach_tools already imported** at top of file (line 36)

4. **Exception handling** — Each source wrapped in try/except so one failure doesn't break all

5. **No new imports required** — All dependencies already available

---

## Verification Commands

After implementation, run:

```powershell
# Check import works
docker-compose exec -T api python -c "from services.ai_coach import AICoach; print('Import OK')"

# Verify method exists and returns list
docker-compose exec -T api python -c "
from services.ai_coach import AICoach
from database import SessionLocal
from models import Athlete

db = SessionLocal()
athlete = db.query(Athlete).first()
if athlete:
    coach = AICoach(db)
    suggestions = coach.get_dynamic_suggestions(athlete.id)
    print(f'Suggestions count: {len(suggestions)}')
    for s in suggestions:
        print(f'  - {s}')
else:
    print('No athlete found')
db.close()
"
```

---

## Acceptance Criteria (Builder must verify)

1. ✅ Method returns `List[str]`
2. ✅ At least 3 suggestions returned
3. ✅ At least one suggestion contains a number (TSB, %, km)
4. ✅ No exceptions on athlete with data
5. ✅ No exceptions on athlete without data (fallback works)

---

## Rollback

If issues: revert `get_dynamic_suggestions()` to previous version (copy from git).

---

**Ready for Builder implementation.**
