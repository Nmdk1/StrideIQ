# Personal Operating Manual

## Current State

The Personal Operating Manual (`/manual`) is the athlete's comprehensive self-knowledge page. V2 shipped Apr 4, 2026. It is a primary navigation item. Backend: `services/operating_manual.py`. Frontend: `app/manual/page.tsx`.

## How It Works

### Data Flow

1. **Correlation engine** discovers findings → `CorrelationFinding` rows
2. **Operating manual service** queries confirmed findings (lifecycle state `active`, `structural`, `active_fixed`)
3. **Interestingness filter** excludes tautologies (e.g., "fresh legs = better performance" is obvious)
4. **Cascade chains** reconcile contradictions and show cause-effect relationships
5. **Sections rendered** on the frontend with athlete-understandable language

### Sections

The Manual contains several sections derived from different data sources:

- **Race Character:** How the athlete performs in races vs training. Derived from race-flagged activities and the pre-race fingerprint pipeline (`services/pre_race_fingerprinting.py`)
- **What Works:** Confirmed positive correlations — behaviors that improve performance
- **What Doesn't Work:** Confirmed negative correlations — behaviors that hurt performance
- **Cascade Stories:** Multi-step cause-effect chains (e.g., sleep → HRV → efficiency)
- **Environmental Profile:** Temperature/humidity sensitivity from `heat_adjustment_pct` and dew point correlations
- **Recovery Profile:** How long the athlete takes to recover, half-life patterns

### Display Names

The `FRIENDLY_NAMES` dict in `services/n1_insight_generator.py` maps internal signal names to athlete-readable names:
- `garmin_sleep_deep_s` → "Deep Sleep"
- `dew_point_f` → "Dew Point"
- `feedback_leg_feel` → "Leg Feel"
- `activity_intensity_score` → "Session Intensity"

100+ mappings. Used by the Manual, home page, and weekly digest email.

### Findings Lifecycle on the Manual

The Manual automatically reflects lifecycle changes:
- **`active` findings** appear in What Works / What Doesn't Work
- **`resolving` findings** naturally fall out of active surfaces
- **`closed` findings** are archived
- **`structural` findings** appear in the Recovery/Environmental profiles

When the correlation engine discovers a new pattern or an existing one resolves, the Manual updates on the next load — no manual intervention needed.

## Key Decisions

- **V2 replaced Insights page** (Apr 4, 2026) — `/insights` redirects to `/manual`
- **Interestingness filter:** Not every confirmed finding is worth showing. Obvious relationships are suppressed.
- **Cascade chains:** Show the athlete why things connect, not just that they correlate
- **Primary navigation:** The Manual is a top-level nav item, not buried in settings

## Known Issues

- **Weekly digest bypasses Manual intelligence:** The email runs raw correlations instead of pulling from the Manual's curated findings. Long-term fix: wire digest to confirmed findings and Manual changes.

## What's Next

- Briefing questions that reference Manual findings should be tappable → opens coach with finding context
- Manual V3: more interactive, possibly with the "Fingerprint Organism" visualization from Path B

## Sources

- `docs/PRODUCT_STRATEGY_2026-03-03.md` — Priority #5
- `docs/FINGERPRINT_VISIBILITY_ROADMAP.md` — Path A (Manual V2) and Path B (dream surfaces)
- `docs/specs/RACING_FINGERPRINT_AND_PROGRESS_STATE_MACHINE_SPEC.md` — race character
- `apps/api/services/operating_manual.py` — backend
- `apps/web/app/manual/page.tsx` — frontend
