# ADR-019: On-Demand Diagnostic Report

## Status
Accepted

## Date
2026-01-14

## Context

### The Problem

Athletes need a comprehensive, plain-language summary of their training status, progress, and data quality. Currently:
- Data is scattered across multiple pages (Home, Analytics, Calendar, PBs)
- Athletes can't easily see the "big picture" of their training
- Missing data gaps are not clearly communicated
- Recommendations are implicit, not actionable

### The Opportunity

We demonstrated a diagnostic report format (DIAGNOSTIC_REPORT_USER1.md) that provides:
- Executive summary of training status
- Personal best profile with pace analysis
- Weekly volume trajectory with phase detection
- Efficiency trend analysis with interpretation
- Race history and remarkable findings
- Data quality assessment (what's missing)
- Actionable recommendations (what to do next)
- Honest caveats (what NOT to do based on current evidence)

This report should be available on-demand for any athlete.

### Design Principles

- **N=1 First**: Report is fully personalized to athlete's data
- **Plain Language**: No jargon, explains metrics in context
- **Honest About Gaps**: Clearly states what data is missing and impact
- **Sparse Tone**: Irreverent, not prescriptive ("Data says X. Your call.")
- **Actionable**: Ends with clear next steps, ranked by priority
- **Defensive**: States what would be reckless to change based on current data

## Decision

### 1. Backend: Diagnostic Report Service

New service: `apps/api/services/athlete_diagnostic.py`

Functions:
- `generate_diagnostic_report(athlete_id, db)` → Full report dict
- `get_personal_best_profile(athlete_id, db)` → PB summary
- `get_volume_trajectory(athlete_id, db, weeks=12)` → Weekly volume
- `get_efficiency_trend(athlete_id, db, weeks=12)` → Efficiency analysis
- `get_race_history(athlete_id, db, limit=5)` → Recent races
- `get_data_quality_assessment(athlete_id, db)` → Missing data gaps
- `generate_recommendations(report_data)` → Actionable next steps

### 2. API Endpoint

`GET /v1/analytics/diagnostic-report`

Response:
```json
{
  "generated_at": "2026-01-14T12:00:00Z",
  "athlete_id": "uuid",
  "period_start": "2025-07-05",
  "period_end": "2026-01-14",
  "executive_summary": {
    "total_activities": 196,
    "total_distance_km": 823,
    "peak_volume_km": 113,
    "current_phase": "recovery",
    "efficiency_trend_pct": -5.4,
    "key_findings": [
      {"type": "positive", "text": "Personal bests validated..."},
      {"type": "warning", "text": "Efficiency trending down..."}
    ]
  },
  "personal_bests": [
    {
      "distance": "5K",
      "distance_meters": 5000,
      "time_seconds": 1134,
      "pace_per_km": "3:45",
      "is_race": true,
      "validated": true
    }
  ],
  "volume_trajectory": {
    "weeks": [
      {"week": "2025-W47", "distance_km": 113, "runs": 8, "phase": "peak"}
    ],
    "total_km": 823,
    "total_runs": 71,
    "peak_week": "2025-W47",
    "current_vs_peak_pct": -70
  },
  "efficiency_analysis": {
    "average": 1.4526,
    "trend_pct": -5.4,
    "interpretation": "Expected during injury recovery",
    "recent_runs": [
      {"date": "2026-01-13", "distance_km": 19.3, "pace": 5.24, "hr": 139, "efficiency": 1.37}
    ]
  },
  "race_history": [
    {
      "date": "2025-11-29",
      "name": "Coastal Half Marathon",
      "distance_km": 21.2,
      "time_seconds": 5260,
      "pace_per_km": "4:08",
      "notes": "7-min PR, 4 days post-injury"
    }
  ],
  "data_quality": {
    "available": {
      "activities": {"count": 196, "quality": "excellent"},
      "heart_rate": {"count": 61, "quality": "good"},
      "personal_bests": {"count": 8, "quality": "validated"}
    },
    "missing": {
      "daily_checkins": {"impact": "Cannot correlate sleep/stress"},
      "hrv": {"impact": "Cannot assess readiness"},
      "nutrition": {"impact": "Cannot correlate fueling"}
    },
    "unanswerable_questions": [
      "Does sleep quality affect your running efficiency?",
      "Does stress correlate with performance?"
    ]
  },
  "recommendations": {
    "high_priority": [
      {
        "action": "Start morning check-ins",
        "reason": "Unlocks sleep/stress correlation analysis",
        "effort": "10 seconds/day for 4 weeks"
      }
    ],
    "medium_priority": [
      {"action": "Log weight weekly", "reason": "Enables body composition tracking"}
    ],
    "do_not_do": [
      {"action": "Chase efficiency metrics during recovery", "reason": "Decline is expected and normal"}
    ]
  }
}
```

### 3. Frontend: Diagnostic Report Page

New page: `/diagnostics` or `/insights/report`

Components:
- `DiagnosticReportPage.tsx` - Main page
- `ExecutiveSummary.tsx` - Key findings cards
- `PersonalBestTable.tsx` - PB list with pace analysis
- `VolumeChart.tsx` - Weekly volume visualization
- `EfficiencyTrend.tsx` - Efficiency over time
- `DataQualityPanel.tsx` - Missing data with calls to action
- `RecommendationsPanel.tsx` - Prioritized actions

Design:
- Use shadcn/ui Card, Badge, Progress, Table components
- Match Tools/Compare page style (dark theme, orange accents)
- Prominent "Generate Report" button
- Loading state with progress indicator
- Export to PDF/Markdown option (future)

### 4. Feature Flag

`analytics.diagnostic_report` — Enable for rollout

### 5. Rate Limiting

Report generation is compute-intensive. Apply:
- 1 report per 15 minutes per user
- Cache report for 1 hour (invalidate on new activity sync)

## Consequences

### Positive
- Athletes get comprehensive view of their training status
- Missing data is surfaced with actionable guidance
- Recommendations are personalized and prioritized
- Builds trust through transparency ("here's what we can't tell you")

### Negative
- Report generation has DB query overhead
- Stale data if not regenerated after activity sync
- May overwhelm new users with low data

### Mitigations
- Add caching layer for computed reports
- Show "last generated" timestamp
- Gracefully handle low-data states with encouraging messaging

## Test Plan

### Unit Tests
1. `test_generate_diagnostic_report` - Full report generation
2. `test_personal_best_profile` - PB extraction and validation
3. `test_volume_trajectory` - Weekly aggregation accuracy
4. `test_efficiency_trend` - Trend calculation
5. `test_data_quality_assessment` - Missing data detection
6. `test_generate_recommendations` - Priority ranking

### Integration Tests
1. API returns valid JSON with all sections
2. API handles athlete with no data gracefully
3. API handles athlete with minimal data (< 10 activities)
4. Rate limiting blocks excessive requests

### Frontend Tests
1. Page renders all sections
2. Generate button triggers API call
3. Loading state displayed during generation
4. Error state handled gracefully
5. Mobile responsive layout

## Security

- **Authentication Required**: Must be logged in
- **Authorization**: Can only view own report
- **No User Inputs**: Read-only from existing data
- **Rate Limited**: Prevent abuse
- **No PII in Logs**: Only log athlete_id, not email

## Tone Check

Report language follows manifesto:
- "Data says X. Your call." — not prescriptive
- "Cannot determine..." — honest about gaps
- "Do NOT do..." — clear guardrails
- No guilt-tripping for missing data
- Irreverent where appropriate ("Cool. Move on.")
