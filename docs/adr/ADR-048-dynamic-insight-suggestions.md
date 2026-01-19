# ADR-048: Dynamic Insight Suggestions

**Status:** Complete (Verified 2026-01-19)  
**Date:** 2026-01-19  
**Author:** Opus 4.5 (Planner)  
**Phase:** 4 of 5 (N=1 Insight Engine Roadmap)  
**Depends On:** ADR-046 (coach tools), ADR-047 (coach refactor)

---

## Context

### Current State

`get_dynamic_suggestions()` in `ai_coach.py` returns **static template questions**:
- "What should I focus on this week?"
- "Any tips for tomorrow's long run?"
- "How did today's run go?"
- "Am I getting fitter?"

These are generic and don't reference the athlete's actual data.

### Problem

1. **Suggestions are static** — Same questions regardless of what's happening
2. **No data references** — Don't mention specific runs, dates, metrics
3. **Miss anomalies** — Don't surface unusual patterns or insights
4. **Not ranked by relevance** — Generic order, not prioritized

### Root Trust Problem (the “why”)

Even when analytics exist, the UI can still feel like “hallucination” if the coach does not provide **receipts**.

**Receipts = date + UUID + human-readable value.**  
When the coach cites an `activity_id` or `personal_best` anchor, the user can verify the claim, which builds interaction trust.

### Target State

Suggestions like:
- "Your easy runs averaged 147 bpm last week — higher than your usual 135. Why?"
- "Your 10K on Tuesday showed 8% efficiency improvement. What contributed?"
- "You've hit 3 PBs in December. What's different about your training?"
- "Your TSB is +28 — optimal for a PR attempt. Ready for a race?"

---

## Decision

### Replace Static Templates with Computed Insights

Refactor `get_dynamic_suggestions()` to:

1. **Pull insights from `insight_aggregator`** (already built)
2. **Pull data from coach tools** (ADR-046)
3. **Format insights as questions** with specific data
4. **Rank by priority/recency**

### Add Citation-Forcing Suggestions

To prevent the “generic answer” failure mode, suggestions should be written to force a cited answer, e.g.:
- “Cite the activity id + date + value”
- “Cite two EF points (earliest + latest) with activity IDs”
- “Cite each PR’s activity id + date + TSB day-before”

This keeps the coach anchored in tool evidence without relying on the model to “remember” to cite.

### Implementation

```python
def get_dynamic_suggestions(self, athlete_id: UUID) -> List[str]:
    """
    Return 3-5 data-driven suggested questions.
    
    Sources:
    - insight_aggregator.get_active_insights (prioritized insights)
    - coach_tools.get_pb_patterns (recent PBs)
    - coach_tools.get_training_load (TSB state)
    - coach_tools.get_efficiency_by_zone (efficiency trends)
    """
    suggestions: List[str] = []
    
    def add(q: str) -> None:
        if q not in suggestions and len(suggestions) < 5:
            suggestions.append(q)
    
    # --- 1. Insights from insight_aggregator ---
    try:
        from services.insight_aggregator import get_active_insights
        insights = get_active_insights(self.db, athlete_id, limit=3)
        for insight in insights:
            if insight.title and insight.message:
                # Convert insight to question format
                q = self._insight_to_question(insight)
                if q:
                    add(q)
    except Exception:
        pass
    
    # --- 2. PB-driven suggestions ---
    try:
        result = coach_tools.get_pb_patterns(self.db, athlete_id)
        if result.get("ok") and result["data"].get("pb_count", 0) > 0:
            pb_count = result["data"]["pb_count"]
            tsb_range = result["data"].get("optimal_tsb_range")
            if pb_count >= 2 and tsb_range:
                add(f"You have {pb_count} PRs with optimal TSB {tsb_range[0]:.0f} to {tsb_range[1]:.0f}. What's your secret?")
    except Exception:
        pass
    
    # --- 3. TSB-driven suggestions ---
    try:
        result = coach_tools.get_training_load(self.db, athlete_id)
        if result.get("ok"):
            tsb = result["data"].get("tsb")
            if tsb is not None:
                if tsb > 20:
                    add("Am I fresh enough for a hard workout? Cite my current ATL/CTL/TSB and explain what that implies for today.")
                elif tsb < -30:
                    add("Am I overreaching? Cite my current ATL/CTL/TSB and give a recovery plan for the next 48 hours.")
    except Exception:
        pass
    
    # --- 4. Efficiency-driven suggestions ---
    try:
        result = coach_tools.get_efficiency_by_zone(self.db, athlete_id, "threshold", 90)
        if result.get("ok"):
            trend = result["data"].get("recent_trend_pct")
            if trend is not None:
                if trend < -10:
                    add(f"Your threshold efficiency improved {abs(trend):.0f}% recently. What's working?")
                elif trend > 10:
                    add(f"Your threshold efficiency dropped {trend:.0f}% — want to investigate?")
    except Exception:
        pass
    
    # --- 5. Recent activity suggestions ---
    try:
        today = date.today()
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
            add(f"Review my run from today ({distance_km:.1f} km). Cite the activity id + distance + pace + avg HR (from get_recent_runs).")
    except Exception:
        pass
    
    # --- Fallback defaults ---
    if len(suggestions) < 3:
        add("How is my training going overall? Cite at least 2 recent runs (date + activity id + distance + pace) and my current ATL/CTL/TSB.")
        add("Am I on track for my goal race? Use get_plan_week and get_training_load and cite specific workouts + current load.")
    
    return suggestions[:5]

def _insight_to_question(self, insight) -> Optional[str]:
    """Convert an insight object to a question format."""
    # Map insight types to question templates
    title = insight.title or ""
    
    if "improving" in title.lower():
        return f"{title} — what's driving this?"
    elif "declining" in title.lower() or "drop" in title.lower():
        return f"{title} — should we investigate?"
    elif "pattern" in title.lower():
        return f"{title} — is this intentional?"
    elif "risk" in title.lower() or "warning" in title.lower():
        return f"{title} — what should I do?"
    else:
        return f"{title} — tell me more?"
```

---

## Implementation

### File to Modify

`apps/api/services/ai_coach.py`

### Steps

1. Import `get_active_insights` from `insight_aggregator`
2. Replace body of `get_dynamic_suggestions()` with new implementation
3. Add `_insight_to_question()` helper method
4. Ensure coach_tools functions are available (already imported)

---

## Acceptance Criteria

### Must Pass

1. **Suggestions include specific data**
   ```
   At least one suggestion includes a number (TSB value, efficiency %, km distance)
   ```

2. **Suggestions reference insights**
   ```
   If athlete has active insights, they appear as suggestions
   ```

3. **TSB-aware suggestions**
   ```
   If TSB > 20: suggestion mentions freshness
   If TSB < -30: suggestion mentions fatigue
   ```

4. **Efficiency-aware suggestions**
   ```
   If efficiency improved >10%: suggestion asks what's working
   If efficiency dropped >10%: suggestion asks to investigate
   ```

5. **At least 3 suggestions returned**
   ```
   result = coach.get_dynamic_suggestions(athlete_id)
   assert len(result) >= 3
   ```

### Domain Validation

6. **Judge's data produces relevant suggestions**
   ```
   Judge has: 6 PBs, TSB ~28, efficiency improving
   → Should see: PB-related suggestion, freshness suggestion, or efficiency success suggestion

### Trust Validation (new hard requirement)

7. **Click → cited answer**
   - Clicking any suggestion in `/coach` must produce an answer containing at least one citation with:
     - a date (YYYY-MM-DD)
     - a UUID (activity id or PB anchor)
   ```

---

## Testing Protocol

**Tester MUST:**
1. Call `get_dynamic_suggestions()` for Judge's athlete
2. Verify at least one suggestion contains a specific number
3. Verify suggestions change based on TSB (compare with athlete at TSB < 0)
4. Cross-check suggestions against known athlete state
5. Verify end-to-end in the UI: `localhost:3000/coach` click suggestion → cited answer
6. Run repeatable headless check from `apps/web/`:
   - `node scripts/e2e_coach_suggestions.mjs`

---

## Notes for Builder

1. **Handle exceptions gracefully** — Each data source wrapped in try/except
2. **Fallback to defaults** — If all sources fail, return generic suggestions
3. **Limit to 5 suggestions** — UI expects 3-5
4. **insight_aggregator may return CalendarInsight objects** — Check actual return type

---

## Rollback Plan

If issues arise:
1. Revert to previous static `get_dynamic_suggestions()` 
2. No database changes required

---

## Dependencies

- ADR-046 coach tools: `get_pb_patterns`, `get_training_load`, `get_efficiency_by_zone`
- `insight_aggregator.get_active_insights`

---

**Verified 2026-01-19: end-to-end click → cited answer.**
