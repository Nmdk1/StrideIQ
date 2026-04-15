# Builder Instructions: Home Page Intelligence Lanes + System-Speak Removal

**Priority:** P0  
**Scope:** `apps/api/routers/home.py`, `apps/api/services/fingerprint_context.py`, targeted tests  
**Risk:** Medium (single-call prompt behavior), mitigated by validator + tests  
**Goal:** Stop system-speak and cross-section repetition on home briefing outputs.

---

## Why this change

Current home briefing still has:
- prompt instructions that explicitly force confirmation-count language
- contradictory instructions that tell both `morning_voice` and `coach_noticed` to pull from DEEP INTELLIGENCE
- single-call LLM behavior that repeats one finding across multiple sections
- redundant live correlation computation in `compute_coach_noticed`

We need code-level enforcement, not prompt-only hopes.

---

## Task 1 — Remove system-speak instructions and contradictory prompt rules

### File: `apps/api/routers/home.py`

In `generate_coach_home_briefing`:

1. Update `PERSONAL FINGERPRINT CONTRACT`:
- Remove any instruction requiring evidence counts / confirmation counts.
- Add explicit prohibition on athlete-facing stats (`confirmed N`, `r=`, `p-value`, `times_confirmed`, `correlation coefficient`).

2. Replace the contradictory DEEP INTELLIGENCE instruction block:
- Remove the block that says `morning_voice` and `coach_noticed` MUST draw from DEEP INTELLIGENCE.
- Replace with:
  - DEEP INTELLIGENCE is reasoning context
  - each output field has its own `YOUR DATA FOR THIS FIELD` lane
  - only `morning_voice` may use fingerprint findings directly

3. Update `schema_fields` guidance:
- `coach_noticed`: remove DEEP INTELLIGENCE personal-pattern mandate; bind to daily rules/wellness/home signals lane.
- `morning_voice`: bind to `fingerprint_summary` lane instead of generic DEEP INTELLIGENCE wording.

### File: `apps/api/services/fingerprint_context.py`

In `build_fingerprint_prompt_section(..., verbose=True)` header text:
- remove any instruction like “cite confirmation count”
- keep tier semantics (strong vs emerging) for model reasoning only
- add “translate to coaching language; do not expose statistical internals”

---

## Task 2 — Make lane assignment structural (single-call compatible)

### File: `apps/api/routers/home.py`

In `generate_coach_home_briefing`:

1. Build pre-formatted lane snippets before `schema_fields`:
- `fingerprint_summary`
- `coach_noticed_source_summary`
- `week_context_summary`
- `today_context_summary`
- optional `checkin_context_summary` and `race_context_summary`

Each snippet should be 1-2 short coaching-language sentences, no internal metrics.

2. Embed lane snippets directly in each schema field text:
- Use a literal prefix: `YOUR DATA FOR THIS FIELD: <snippet>`
- Required lane map:
  - `morning_voice` -> fingerprint summary
  - `coach_noticed` -> daily rules/wellness/signal summary (NOT fingerprint)
  - `checkin_reaction` -> check-in + today plan context
  - `week_assessment` -> week trajectory / block + shapes summary
  - `race_assessment` -> race countdown + readiness context
  - `today_context` -> today plan vs completed activity

3. Add post-generation diversity monitor:
- Implement `_validate_briefing_diversity(fields: dict) -> dict`
- Detect fingerprint-term leakage from `morning_voice` into 2+ other fields
- Log warning with athlete + leaking fields; return payload unchanged for now (monitor mode)
- Call it immediately after JSON parse and before caching/return

---

## Task 3 — Remove redundant live correlation path and tighten trust gating

### File: `apps/api/routers/home.py`

In `compute_coach_noticed`:

1. Remove live correlation path (`analyze_correlations`) entirely.
- Start waterfall at persisted fingerprint (or make fingerprint lane first) then existing signal/feed/narrative fallbacks.

2. Tighten persisted finding threshold:
- Change fingerprint query gate from `times_confirmed >= 1` to `times_confirmed >= 3`.

3. Reformat fingerprint text:
- Remove `confirmed Nx` and any statistical wording.
- Keep coaching implications (threshold/asymmetry/lag/decay) in plain language.

4. Add deterministic daily rotation across top findings:
- Query top 5 eligible findings ordered by `times_confirmed desc` then recency.
- Select one by date-based index (`date.today().toordinal() % len(findings)`).

### File: `apps/api/routers/home.py`

In `_build_rich_intelligence_context`:
- Remove Source 1 (`generate_n1_insights`) to eliminate redundancy with persisted fingerprint source.
- Keep source 8 (persisted fingerprint) and existing non-correlation context sources.

---

## Task 4 — Tests (required)

### Update/Create: `apps/api/tests/test_home_briefing_intelligence_lanes.py`

Add/ensure these tests:

1. `test_prompt_contract_removes_confirmation_count_instructions`
- prompt text does not contain “reference them by evidence count” / “NEVER reference without confirmation count”.

2. `test_schema_fields_have_explicit_lane_blocks`
- each required field description contains `YOUR DATA FOR THIS FIELD:`.

3. `test_compute_coach_noticed_uses_confirmed_threshold`
- persisted finding gate is `times_confirmed >= 3`.

4. `test_compute_coach_noticed_does_not_emit_stats_language`
- generated text excludes `confirmed`, `r=`, `correlation`, `observations`.

5. `test_diversity_validator_flags_cross_lane_leakage`
- fixture payload with same fingerprint terms in multiple fields triggers warning.

6. `test_repetition_enforcement_same_finding_not_in_3plus_fields`
- generated/fixture payload fails monitor criteria when a single finding dominates 3+ sections.

### Keep existing regression tests
- `apps/api/tests/test_training_story_engine.py`
- `apps/api/tests/test_findings_regression.py`

---

## Acceptance Criteria

1. Home briefing output contains no athlete-facing statistical phrasing (`confirmed`, `r=`, `p-value`, `times_confirmed`).
2. `coach_noticed` no longer depends on live `analyze_correlations()`.
3. Fingerprint references in `coach_noticed` require `times_confirmed >= 3`.
4. Repetition monitor logs when one fingerprint theme leaks into multiple non-morning fields.
5. Tests in Task 4 pass.

---

## Verification Commands

```bash
python -m pytest -q \
  apps/api/tests/test_home_briefing_intelligence_lanes.py \
  apps/api/tests/test_training_story_engine.py \
  apps/api/tests/test_findings_regression.py
```

Then production smoke:

```bash
TOKEN=$(docker exec strideiq_api python -c "
from core.security import create_access_token
from core.database import SessionLocal
from models import Athlete
db = SessionLocal()
u = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(u.id), 'email': u.email, 'role': u.role}))
db.close()
") && curl -s -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/home | python3 -m json.tool
```

Manual check on returned text:
- no `confirmed`, `r=`, `correlation`, `times`
- different themes across `morning_voice`, `coach_noticed`, `week_assessment`, `checkin_reaction`

---

## Copy-Paste Builder Brief

Implement Tasks 1-4 in `docs/BUILDER_INSTRUCTIONS_2026-03-09_HOME_PAGE_INTELLIGENCE.md` exactly. Do not add scope. No frontend changes. No model changes. This is a backend prompt/routing quality fix with test enforcement. Prioritize:
1) remove system-speak + contradictory prompt rules,
2) structural per-field lane injection + diversity monitor,
3) remove live correlation path and require `times_confirmed >= 3`,
4) add the required tests and run verification commands.
