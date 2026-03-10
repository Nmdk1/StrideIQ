# Daily Production Experience Guardrail — Builder Spec

**Date:** March 10, 2026
**Priority:** P0 — ships before any new feature
**Estimated effort:** 5–6 hours
**Principle:** Assertions don't lie. This guardrail catches "technically correct but experientially wrong" bugs before the athlete sees them.

---

## Overview

A Celery beat task that runs daily against production. It hits every athlete-facing endpoint, cross-references what the API returns against what's in the database, scans every text field for banned content, and writes a permanent log entry with per-assertion pass/fail results.

This is not a code audit. It is an experience audit. It tests what the athlete actually sees.

---

## Architecture

### Execution

- **Runs as:** Celery beat task `daily-experience-guardrail`
- **Schedule:** Daily at 06:15 UTC (after morning intelligence at 05:00 local, after Garmin overnight sync)
- **Container:** `strideiq_api` (direct database and Redis access)
- **Method:** Calls Python functions directly — NOT HTTP. No auth token, no network. Imports the router/service functions and calls them with a real DB session.

### Scope

- **v1:** Founder account only (`mbshaf@gmail.com`)
- **v2 (later):** All athletes with `last_activity_at` within 14 days

### Preflight Check

Before running data truth assertions (Category 1), check:
```python
latest_garmin = (
    db.query(GarminDay)
    .filter(GarminDay.athlete_id == athlete_id)
    .order_by(GarminDay.calendar_date.desc())
    .first()
)
hours_since_garmin = (now_utc - latest_garmin.created_at).total_seconds() / 3600
if hours_since_garmin > 18:
    log WARNING "No Garmin data in 18h — skipping data truth assertions (rest day or sync delay)"
    skip Category 1 assertions (but still run Categories 2-5)
```

This prevents false failures on rest days or Garmin sync delays.

---

## Database Migration

### New table: `experience_audit_log`

```python
class ExperienceAuditLog(Base):
    __tablename__ = "experience_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    run_date = Column(Date, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    tier = Column(Text, nullable=False)  # 'daily_t1', 'daily_t2', 'weekly_t3'
    passed = Column(Boolean, nullable=False)
    total_assertions = Column(Integer, nullable=False)
    passed_count = Column(Integer, nullable=False)
    failed_count = Column(Integer, nullable=False)
    skipped_count = Column(Integer, nullable=False, server_default='0')
    results = Column(JSONB, nullable=False)
    summary = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint('athlete_id', 'run_date', 'tier', name='uq_audit_athlete_date_tier'),
    )
```

**Migration file:** `alembic/versions/add_experience_audit_log.py`

### `results` JSONB structure

```json
[
  {
    "id": 1,
    "name": "sleep_value_matches_source",
    "category": "data_truth",
    "passed": false,
    "skipped": false,
    "detail": "Morning voice says 7.5h, GarminDay.sleep_total_s = 22020 (6.12h), DailyCheckin.sleep_hours = 6.5",
    "endpoint": "GET /v1/home → coach_briefing.morning_voice",
    "severity": "critical"
  }
]
```

---

## Assertion Registry

### Category 1: Data Truth

These test whether what the athlete sees matches what's in the database. **Skipped if preflight Garmin check fails.**

#### Assertion #1: Sleep value matches source

- **Check:** Extract any numeric sleep reference from `coach_briefing.morning_voice` (regex: `(\d+\.?\d*)\s*(hours?|h)\s*(of\s+)?sleep`). Compare against `GarminDay.sleep_total_s / 3600` for today's date AND `DailyCheckin.sleep_hours` for today.
- **Pass:** Extracted value within 0.3h of at least one source, OR no sleep claim in text.
- **Fail:** Extracted value differs from both sources by more than 0.3h.
- **Source of truth:** `GarminDay` (filter: `calendar_date = local_today`, `sleep_total_s IS NOT NULL`), `DailyCheckin` (filter: `checkin_date = local_today`).
- **Severity:** critical

#### Assertion #2: Sleep is from today, not yesterday

- **Check:** If `coach_briefing.morning_voice` contains a Garmin sleep claim, verify a `GarminDay` row exists for `local_today` with non-null `sleep_total_s`. If the only available `GarminDay` is for `local_today - 1`, the morning voice must NOT present it as "last night."
- **Pass:** Garmin sleep claim sourced from today's row, OR no Garmin sleep claim in text.
- **Fail:** Text says "Garmin" + sleep number, but no `GarminDay` row for today exists.
- **Severity:** critical

#### Assertion #3: Last activity date matches database

- **Check:** Extract any date or temporal reference to the athlete's last run from `coach_briefing.morning_voice` (e.g., "yesterday's run", "Saturday's 10-miler", "your last run"). Compare against `Activity.start_date` for the most recent activity (ordered by `start_date DESC`, limit 1).
- **Pass:** Temporal reference is consistent with actual last activity date, OR no activity reference in text.
- **Fail:** Text references "yesterday" but last activity was 3 days ago, or similar mismatch.
- **Source of truth:** `Activity` table, `start_date` field.
- **Severity:** critical

#### Assertion #4: Shape sentence matches database

- **Check:** Compare `last_run.shape_sentence` from the `/v1/home` response against `Activity.shape_sentence` in the database for the same activity (matched by activity ID).
- **Pass:** Strings are identical, OR both are None/null.
- **Fail:** Strings differ.
- **Source of truth:** `Activity.shape_sentence` column.
- **Severity:** high

#### Assertion #5: Heat adjustment present when dew point exceeds 55°F

- **Check:** For the most recent activity, if `Activity.dew_point_f > 55`, verify that `Activity.heat_adjustment_pct` is not null and is > 0.
- **Pass:** `dew_point_f <= 55` (not applicable), OR `dew_point_f > 55` AND `heat_adjustment_pct > 0`.
- **Fail:** `dew_point_f > 55` AND (`heat_adjustment_pct` is null or 0).
- **Source of truth:** `Activity` table.
- **Severity:** high

#### Assertion #6: Race countdown days remaining is correct

- **Check:** If `race_countdown` is present in the home response, compute `(TrainingPlan.race_date - today).days` and compare to the displayed value.
- **Pass:** Values match exactly, OR no race countdown displayed and no active `TrainingPlan` with future `race_date`.
- **Fail:** Days remaining differs by more than 0.
- **Source of truth:** `TrainingPlan.race_date`.
- **Severity:** high

#### Assertion #7: Predicted race time is plausible

- **Check:** If `race_countdown.predicted_time` is present, verify it falls within a sane range for the athlete. Use the athlete's most recent activity paces to compute a floor (fastest recent pace × race distance) and ceiling (slowest easy pace × race distance × 1.5).
- **Pass:** Predicted time within floor-ceiling range, OR no prediction displayed.
- **Fail:** Predicted time outside range.
- **Severity:** medium

---

### Category 2: Language Hygiene

These scan every athlete-facing text field for banned content. **Never skipped.**

#### Assertion #8: No banned internal metrics in any text

- **Check:** Scan all text fields across all Tier 1 and Tier 2 endpoints for banned terms. Use word-boundary-aware matching (not substring — "metabolism" should not match "met").
- **Banned terms (case-insensitive, word boundary):**
  - `\btsb\b`, `\bctl\b`, `\batl\b`, `\bvdot\b`, `\brmssd\b`, `\bsdnn\b`, `\btrimp\b`
  - `\bchronic.load\b`, `\bacute.load\b`, `\bform.score\b`
  - `\bdurability.index\b`, `\brecovery.half.life\b`, `\binjury.risk.score\b`
- **Surfaces scanned:** Every text field in the response from every Tier 1 and Tier 2 endpoint (see Endpoint Tiers below).
- **Pass:** No matches.
- **Fail:** Any match found. Detail includes the field, the matched term, and a snippet of surrounding context.
- **Severity:** critical

#### Assertion #9: No sycophantic language

- **Check:** Scan all LLM-generated text fields for `_VOICE_BAN_LIST` terms: `incredible`, `amazing`, `phenomenal`, `extraordinary`, `fantastic`, `wonderful`, `awesome`, `brilliant`, `magnificent`, `outstanding`, `superb`, `stellar`, `remarkable`, `spectacular`.
- **Surfaces:** `coach_briefing.*`, `coach_noticed.text`, `coach_cards[].summary`, `verdict.text`, `hero.headline`, `hero.subtext`, any field identified as LLM-generated.
- **Pass:** No matches.
- **Severity:** medium

#### Assertion #10: No pseudo-causal claims

- **Check:** Scan all LLM-generated text for `_VOICE_CAUSAL_PHRASES`: `because you`, `caused by`, `due to your`, `as a result of your`, `that's why`, `which caused`, `which led to`.
- **Pass:** No matches.
- **Severity:** medium

#### Assertion #11: No raw Python identifiers in athlete text

- **Check:** Regex `\b[a-z]{2,}(?:_[a-z]{2,})+\b` in all text fields. Whitelist: `heart_rate` (contextually acceptable in some surfaces), `per_mile`, `per_km`. Anything else (e.g., `sleep_hours`, `pace_easy`, `weekly_volume_km`) is a leak.
- **Pass:** No non-whitelisted snake_case terms found.
- **Severity:** high

---

### Category 3: Structural Integrity

#### Assertion #12: Morning voice is one paragraph

- **Check:** `coach_briefing.morning_voice` stripped and checked for `\n`.
- **Pass:** No newline characters in trimmed text, OR morning_voice is null/missing.
- **Fail:** Contains `\n`.
- **Severity:** high

#### Assertion #13: Morning voice word count in range

- **Check:** `len(morning_voice.split())` is between 20 and 120.
- **Pass:** Word count in range, OR morning_voice is null.
- **Fail:** Below 20 or above 120.
- **Severity:** medium

#### Assertion #14: Morning voice contains numeric reference

- **Check:** `re.search(r'\d', morning_voice)` is truthy.
- **Pass:** At least one digit found.
- **Fail:** No digits in the morning voice.
- **Severity:** medium

#### Assertion #15: Finding cards non-empty when findings exist

- **Check:** Count `CorrelationFinding` rows where `is_active=True` and `times_confirmed >= 3` for the athlete. If count > 0, verify the home response contains at least one finding.
- **Pass:** Findings exist → cards shown, OR no findings exist → no cards shown.
- **Fail:** Active findings exist but home response shows no finding card.
- **Severity:** high

#### Assertion #16: No duplicate finding text across cards

- **Check:** Collect all `finding.text` values from the home response. Check for exact duplicates.
- **Pass:** All texts unique.
- **Fail:** Any duplicate text.
- **Severity:** medium

---

### Category 4: Temporal Consistency

#### Assertion #17: No finding repeats within 72h cooldown

- **Check:** For each finding surfaced in the home response, check Redis key `finding_surfaced:{athlete_id}:{input_name}:{output_metric}`. If the key exists AND was set within the last 72 hours AND the finding is currently being shown, it's a cooldown violation.
- **Implementation:** Query Redis for all `finding_surfaced:{athlete_id}:*` keys. Compare against finding cards in the response.
- **Pass:** No cooldown violations.
- **Fail:** A finding appears that was surfaced within the last 72 hours.
- **Severity:** high

#### Assertion #18: "Yesterday" references are correct

- **Check:** If `coach_briefing.morning_voice` or `yesterday.insight` contains the word "yesterday," verify the most recent activity was indeed yesterday (within `local_today - 1`).
- **Pass:** "Yesterday" reference matches actual date, OR no "yesterday" in text.
- **Fail:** "Yesterday" used but last activity was not yesterday.
- **Severity:** high

#### Assertion #19: Week trajectory covers actual last 7 days

- **Check:** If `week.trajectory_sentence` is present, count activities in the last 7 days from the `Activity` table. If the trajectory references a specific count (e.g., "3 runs this week"), verify it matches.
- **Pass:** Count matches, or no specific count referenced.
- **Fail:** Count mismatch.
- **Severity:** medium

---

### Category 5: Cross-Endpoint Consistency

#### Assertion #20: Shape sentence consistent across endpoints

- **Check:** Get `last_run.shape_sentence` from `/v1/home` and `shape_sentence` from `/v1/activities/{id}` for the same activity. Compare.
- **Pass:** Identical strings.
- **Fail:** Strings differ.
- **Severity:** high

#### Assertion #21: Finding text consistent across endpoints

- **Check:** If home has a finding from `CorrelationFinding` ID X, check the same finding's text in `/v1/activities/{id}/findings` (for the relevant activity). Text should match.
- **Pass:** Matching text, or finding not present in both.
- **Fail:** Same finding shows different text on different surfaces.
- **Severity:** high

#### Assertion #22: Progress headline doesn't contradict morning voice

- **Check:** Simple keyword-based tone check. If morning voice contains cautious/negative signals (`"fatigue"`, `"tired"`, `"overreaching"`, `"back off"`, `"recovery"`), the progress headline should not contain strong positive signals (`"breakthrough"`, `"peak"`, `"best week"`), and vice versa.
- **Implementation:** Define two keyword lists (cautious, positive). If morning voice triggers cautious AND progress headline triggers positive (or vice versa), flag it.
- **Pass:** No contradiction detected.
- **Fail:** Contradictory signals.
- **Severity:** medium

---

### Category 6: Trust Integrity

#### Assertion #23: Coach response does not reference superseded findings

- **Check:** Collect all text from `coach_briefing.*` fields (morning_voice, coach_noticed, today_context, week_assessment, workout_why). For each `AthleteFinding` where `is_active = False` (superseded), check whether the finding's `sentence` text appears (substring match, case-insensitive) in any coach output.
- **Also check:** `CorrelationFinding` where `is_active = False` — if its `insight_text` appears in any coach text.
- **Source of truth:** 
  - `AthleteFinding` table: `is_active = False` AND `superseded_at IS NOT NULL` → superseded.
  - `CorrelationFinding` table: `is_active = False` → deactivated (faded or confounded).
- **Pass:** No superseded finding sentence appears in any coach output.
- **Fail:** Superseded finding text found in coach output. Detail includes the finding sentence and the field it appeared in.
- **Severity:** critical

#### Assertion #24: Shape sentence classification matches workout structure

- **Check:** For the most recent activity with a `run_shape` (JSONB), extract `run_shape['summary']['workout_classification']`. Then check `Activity.shape_sentence` for consistency:
  - If `workout_classification = 'tempo'`, shape sentence must contain "tempo" (case-insensitive).
  - If `workout_classification = 'strides'`, shape sentence must contain "stride" (case-insensitive).
  - If `workout_classification = 'track_intervals'`, shape sentence must contain "interval" or a rep format like "x400" or "x800".
  - If `workout_classification = 'progression'`, shape sentence must contain "progression" or "building".
  - If `workout_classification = 'hill_repeats'`, shape sentence must contain "hill".
  - If `workout_classification = 'threshold_intervals'`, shape sentence must contain "threshold".
  - If `workout_classification = 'easy'`, shape sentence must NOT contain "tempo", "interval", "threshold", "hill" as primary descriptors.
  - If `workout_classification = 'long_run'`, shape sentence must contain "long" or reference the distance being notably longer than typical.
- **Source of truth:** `Activity.run_shape` JSONB → `summary.workout_classification`, compared against `Activity.shape_sentence`.
- **Pass:** Classification keyword found in sentence, OR `run_shape` is null, OR `shape_sentence` is null.
- **Fail:** Classification says one type but sentence describes a different type.
- **Severity:** high

---

## Endpoint Tiers

### Tier 1 — Full assertion battery, every daily run

| Endpoint | Assertions Applied |
|----------|--------------------|
| `GET /v1/home` (full response) | #1–#8, #9, #10, #11, #12–#16, #17–#19, #20, #22, #23, #24 |
| `GET /v1/activities` (most recent 5) | #4, #5, #8, #9, #11, #24 |
| `GET /v1/activities/{id}` (most recent) | #4, #5, #8, #9, #11, #20, #21, #24 |
| `GET /v1/progress/summary` | #8, #9, #10, #11, #22 |
| `coach_briefing` (all fields) | #1, #2, #3, #8, #9, #10, #11, #12, #13, #14, #23 |

### Tier 2 — Language hygiene scan (#8, #9, #10, #11), every daily run

| Endpoint |
|----------|
| `GET /v1/progress/narrative` |
| `GET /v1/progress/knowledge` |
| `GET /v1/progress/training-patterns` |
| `GET /v1/intelligence/today` |
| `GET /v1/insights/active` |
| `GET /v1/fingerprint/findings` |
| `GET /v1/run-analysis/{id}` (most recent) |
| `GET /v1/activities/{id}/attribution` (most recent) |
| `GET /v1/activities/{id}/findings` (most recent) |

### Tier 3 — Weekly check (language hygiene only, runs on Mondays)

| Endpoint |
|----------|
| `GET /v1/progress/training-story` |
| `GET /v1/athlete-profile/runner-type` |
| `GET /v1/athlete-profile/streak` |
| `GET /v1/coach/suggestions` |

---

## Implementation Structure

### File layout

```
apps/api/
├── services/
│   └── experience_guardrail.py       # Core assertion engine
├── tasks/
│   └── experience_guardrail_task.py  # Celery task wrapper
├── tests/
│   └── test_experience_guardrail.py  # Tests for the guardrail itself
```

### `experience_guardrail.py` — Core

```python
from dataclasses import dataclass
from typing import List, Optional
import re, logging
from datetime import date, datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class AssertionResult:
    id: int
    name: str
    category: str
    passed: bool
    skipped: bool
    detail: str
    endpoint: str
    severity: str  # "critical", "high", "medium"

class ExperienceGuardrail:
    """Runs all assertions for a single athlete against live data."""

    def __init__(self, athlete_id: str, db, redis_client):
        self.athlete_id = athlete_id
        self.db = db
        self.redis = redis_client
        self.results: List[AssertionResult] = []
        self.garmin_preflight_ok = True

    def run_preflight(self) -> bool:
        """Check Garmin data freshness. Returns False if stale (>18h)."""
        # Implementation: query latest GarminDay, check created_at
        ...

    def run_tier1(self, home_response: dict, activities: list, activity_detail: dict, progress_summary: dict):
        """Run full assertion battery against Tier 1 endpoints."""
        ...

    def run_tier2(self, endpoint_responses: dict):
        """Run language hygiene assertions against Tier 2 endpoints."""
        ...

    def run_tier3(self, endpoint_responses: dict):
        """Run language hygiene assertions against Tier 3 endpoints (weekly only)."""
        ...

    # --- Individual assertion methods ---
    def _assert_sleep_matches_source(self, morning_voice: str): ...
    def _assert_sleep_is_today(self, morning_voice: str): ...
    def _assert_last_activity_date(self, morning_voice: str): ...
    def _assert_shape_sentence_matches_db(self, home_shape: str, activity_id: str): ...
    def _assert_heat_adjustment_present(self, activity): ...
    def _assert_race_countdown_correct(self, race_countdown: dict): ...
    def _assert_predicted_time_plausible(self, race_countdown: dict): ...
    def _assert_no_banned_metrics(self, text: str, field_name: str, endpoint: str): ...
    def _assert_no_sycophantic_language(self, text: str, field_name: str, endpoint: str): ...
    def _assert_no_causal_claims(self, text: str, field_name: str, endpoint: str): ...
    def _assert_no_raw_identifiers(self, text: str, field_name: str, endpoint: str): ...
    def _assert_single_paragraph(self, morning_voice: str): ...
    def _assert_word_count_range(self, morning_voice: str): ...
    def _assert_numeric_reference(self, morning_voice: str): ...
    def _assert_findings_non_empty(self, finding: dict): ...
    def _assert_no_duplicate_findings(self, findings: list): ...
    def _assert_finding_cooldown(self, findings: list): ...
    def _assert_yesterday_correct(self, texts: list): ...
    def _assert_week_trajectory(self, trajectory: str): ...
    def _assert_shape_cross_endpoint(self, home_shape: str, activity_shape: str): ...
    def _assert_finding_cross_endpoint(self, home_finding: dict, activity_findings: list): ...
    def _assert_tone_consistency(self, morning_voice: str, headline: str): ...
    def _assert_no_superseded_findings(self, coach_texts: list): ...
    def _assert_classification_matches_sentence(self, run_shape: dict, shape_sentence: str): ...

    # --- Text extraction helpers ---
    def _extract_all_text_fields(self, response: dict) -> List[tuple]:
        """Recursively walk a response dict, yield (field_path, text_value) for all string fields."""
        ...

    def _extract_sleep_claim(self, text: str) -> Optional[float]:
        """Regex extract sleep hours from text. Returns None if no claim found."""
        ...

    def summarize(self) -> dict:
        """Return summary dict for logging."""
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed and not r.skipped)
        skipped = sum(1 for r in self.results if r.skipped)
        all_passed = failed == 0
        summary_text = (
            f"{passed}/{len(self.results)} passed"
            if all_passed
            else f"FAILED: " + ", ".join(
                f"#{r.id} {r.name}" for r in self.results if not r.passed and not r.skipped
            )
        )
        return {
            "passed": all_passed,
            "total_assertions": len(self.results),
            "passed_count": passed,
            "failed_count": failed,
            "skipped_count": skipped,
            "results": [r.__dict__ for r in self.results],
            "summary": summary_text,
        }
```

### `experience_guardrail_task.py` — Celery task

```python
@celery_app.task(name="daily-experience-guardrail", bind=True, max_retries=1)
def run_experience_guardrail(self):
    """Daily production experience audit."""
    db = SessionLocal()
    try:
        founder = db.query(Athlete).filter(Athlete.email == "mbshaf@gmail.com").first()
        if not founder:
            logger.error("Experience guardrail: founder account not found")
            return

        redis_client = get_redis()
        guardrail = ExperienceGuardrail(str(founder.id), db, redis_client)

        # Preflight
        garmin_ok = guardrail.run_preflight()

        # Fetch Tier 1 responses (call functions directly, not HTTP)
        home_response = _fetch_home(founder, db)
        activities = _fetch_activities(founder, db)
        most_recent = activities[0] if activities else None
        activity_detail = _fetch_activity_detail(founder, most_recent, db) if most_recent else None
        progress_summary = _fetch_progress_summary(founder, db)

        guardrail.run_tier1(home_response, activities, activity_detail, progress_summary)

        # Fetch Tier 2 responses
        tier2_responses = _fetch_tier2_endpoints(founder, most_recent, db)
        guardrail.run_tier2(tier2_responses)

        # Tier 3 — Mondays only
        if date.today().weekday() == 0:
            tier3_responses = _fetch_tier3_endpoints(founder, db)
            guardrail.run_tier3(tier3_responses)

        # Summarize and persist
        summary = guardrail.summarize()

        log_entry = ExperienceAuditLog(
            athlete_id=founder.id,
            run_date=date.today(),
            started_at=...,
            finished_at=datetime.now(timezone.utc),
            tier="daily_t1" if date.today().weekday() != 0 else "daily_t1_t2_t3",
            passed=summary["passed"],
            total_assertions=summary["total_assertions"],
            passed_count=summary["passed_count"],
            failed_count=summary["failed_count"],
            skipped_count=summary["skipped_count"],
            results=summary["results"],
            summary=summary["summary"],
        )
        db.add(log_entry)
        db.commit()

        if summary["passed"]:
            logger.info("Experience guardrail PASSED: %s", summary["summary"])
        else:
            logger.error("Experience guardrail FAILED: %s", summary["summary"])

    finally:
        db.close()
```

### `celerybeat_schedule.py` addition

```python
"daily-experience-guardrail": {
    "task": "daily-experience-guardrail",
    "schedule": crontab(hour=6, minute=15),
},
```

---

## Helper Functions for Fetching Endpoint Data

The Celery task calls endpoint functions directly. These helpers simulate what the frontend sees:

```python
def _fetch_home(athlete, db) -> dict:
    """Call the home endpoint logic for the athlete, return the response as a dict."""
    # Import and call the home endpoint's internal function
    # This returns a HomeResponse-like dict
    ...

def _fetch_activities(athlete, db) -> list:
    """Query most recent 5 activities."""
    ...

def _fetch_activity_detail(athlete, activity, db) -> dict:
    """Fetch single activity detail."""
    ...

def _fetch_progress_summary(athlete, db) -> dict:
    """Call progress summary logic."""
    ...

def _fetch_tier2_endpoints(athlete, most_recent_activity, db) -> dict:
    """Fetch all Tier 2 endpoint responses. Returns {endpoint_path: response_dict}."""
    ...

def _fetch_tier3_endpoints(athlete, db) -> dict:
    """Fetch all Tier 3 endpoint responses."""
    ...
```

**Builder note:** Some endpoints are async (`async def`). The Celery task runs in a sync context. Use `asyncio.run()` or `async_to_sync` to call async endpoint functions. Check each endpoint's signature. If an endpoint requires `Request` or `current_user` dependencies, mock or provide them directly.

---

## Tests for the Guardrail Itself

File: `apps/api/tests/test_experience_guardrail.py`

The guardrail itself must be tested. These are unit tests that verify each assertion catches what it's supposed to catch.

### Data Truth tests
1. `test_sleep_mismatch_detected` — morning voice says "7.5h", GarminDay says 6.1h → assertion #1 fails
2. `test_sleep_match_passes` — morning voice says "6.1h", GarminDay says 6.1h → passes
3. `test_stale_sleep_detected` — no GarminDay for today, only yesterday → assertion #2 fails
4. `test_activity_date_mismatch` — text says "yesterday" but last activity was 3 days ago → #3 fails
5. `test_shape_sentence_mismatch` — home says "easy" but DB says "tempo" → #4 fails
6. `test_heat_adjustment_missing` — dew_point_f = 70 but heat_adjustment_pct is null → #5 fails
7. `test_race_countdown_wrong` — shows 14 days but race_date - today = 12 → #6 fails

### Language Hygiene tests
8. `test_banned_metric_detected` — text contains "your tsb" → #8 fails
9. `test_banned_metric_word_boundary` — text contains "metabolism" → #8 passes (no false positive)
10. `test_sycophantic_detected` — text contains "incredible" → #9 fails
11. `test_causal_detected` — text contains "because you" → #10 fails
12. `test_snake_case_detected` — text contains "sleep_hours" → #11 fails
13. `test_whitelisted_snake_case_passes` — text contains "heart_rate" → #11 passes

### Structural tests
14. `test_multi_paragraph_detected` — morning voice has `\n` → #12 fails
15. `test_word_count_too_high` — 150-word morning voice → #13 fails
16. `test_no_numeric_detected` — morning voice with zero digits → #14 fails

### Temporal tests
17. `test_cooldown_violation_detected` — finding in Redis cooldown AND in response → #17 fails
18. `test_yesterday_wrong` — text says "yesterday" but last activity was Friday, today is Monday → #18 fails

### Trust Integrity tests
19. `test_superseded_finding_in_coach_output` — `AthleteFinding.is_active=False`, its `sentence` appears in `morning_voice` → #23 fails
20. `test_active_finding_in_coach_output_passes` — `AthleteFinding.is_active=True`, its `sentence` appears → #23 passes
21. `test_classification_sentence_mismatch` — `workout_classification='tempo'` but `shape_sentence` says "strides" → #24 fails
22. `test_classification_sentence_match` — `workout_classification='tempo'` and `shape_sentence` says "tempo" → #24 passes

### Preflight tests
23. `test_preflight_skips_data_truth_on_stale_garmin` — no Garmin data in 20h → Category 1 assertions skipped, others still run
24. `test_preflight_runs_all_on_fresh_garmin` — Garmin data from 4h ago → all assertions run

### Integration test
25. `test_full_guardrail_run_with_clean_data` — set up a founder-like athlete with clean, consistent data across all surfaces → all 24 assertions pass
26. `test_audit_log_written` — after a run, verify `ExperienceAuditLog` row exists with correct fields

---

## Acceptance Criteria

- [ ] Celery beat task `daily-experience-guardrail` runs at 06:15 UTC
- [ ] All 24 assertions implemented and individually testable
- [ ] Preflight check skips data truth on stale Garmin (>18h) without skipping other categories
- [ ] `experience_audit_log` table created via Alembic migration
- [ ] Each run writes exactly one row per tier to `experience_audit_log`
- [ ] Failed assertions log at `ERROR` level with full detail
- [ ] Passing runs log at `INFO` level with summary
- [ ] All 26 unit/integration tests pass
- [ ] The guardrail would have caught all three of today's bugs (sleep mismatch, two paragraphs, TSB in finding card) — verify by running the test suite with those specific failure scenarios

---

## What This Does NOT Do

- Does not fix bugs it finds (it reports only)
- Does not send alerts (v2 — email/Slack on failure)
- Does not run against all athletes (v1 is founder only)
- Does not replace unit tests (those test code paths; this tests experience truth)
- Does not call LLMs or regenerate content
