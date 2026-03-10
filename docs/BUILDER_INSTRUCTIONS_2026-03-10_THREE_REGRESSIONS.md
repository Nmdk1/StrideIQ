# Builder Instructions — Three Home Page Regressions

**Date:** March 10, 2026
**Priority:** P0 — all three ship today
**Context:** Founder saw wrong sleep value, two paragraphs in morning voice, and "tsb" in finding card on home page this morning.

---

## Fix 1: Stale/Wrong Garmin Sleep in Morning Voice

### Problem

`_get_garmin_sleep_h_for_last_night` (line 629 of `apps/api/routers/home.py`) tries `local_today`, then falls back to `local_today - 1`. When today's Garmin sleep hasn't synced yet (or a partial push arrived during the night with an inflated value), the function silently serves yesterday's value as "last night's sleep." The prompt labels it `GARMIN_LAST_NIGHT_SLEEP_HOURS` and the LLM presents it as fact.

Additionally, `process_garmin_health_task` in `apps/api/tasks/garmin_webhook_tasks.py` (line 795) calls `enqueue_briefing_refresh` WITHOUT `force=True`, so even when corrected sleep data arrives, the refresh can be blocked by the 60-second cooldown.

### Fix

**File: `apps/api/routers/home.py`, function `_get_garmin_sleep_h_for_last_night` (lines 629-687)**

When the function falls back to `local_today - 1`, it must signal that the data is NOT from last night. Change the return to include a staleness flag:

```python
def _get_garmin_sleep_h_for_last_night(
    athlete_id: str, db
) -> tuple:
    # ... existing timezone/date logic ...

    for candidate_date in [local_today, local_today - timedelta(days=1)]:
        row = (
            db.query(GarminDay)
            .filter(
                GarminDay.athlete_id == athlete_id,
                GarminDay.calendar_date == candidate_date,
                GarminDay.sleep_total_s.isnot(None),
            )
            .first()
        )
        if row and row.sleep_total_s:
            sleep_h = round(row.sleep_total_s / 3600, 2)
            is_today = (candidate_date == local_today)
            logger.debug(
                "Garmin sleep grounding: athlete=%s date=%s sleep_h=%.2f is_today=%s",
                athlete_id, candidate_date, sleep_h, is_today,
            )
            return sleep_h, str(candidate_date), is_today

    return None, str(local_today), False
```

**Then update the SLEEP SOURCE CONTRACT section** (around lines 1446-1465) to suppress stale Garmin sleep:

```python
garmin_sleep_h, garmin_date_used, garmin_is_today = _get_garmin_sleep_h_for_last_night(athlete_id, db)

sleep_parts: list = ["=== SLEEP SOURCE CONTRACT ==="]
if garmin_sleep_h is not None and garmin_is_today:
    sleep_parts.append(
        f"GARMIN_LAST_NIGHT_SLEEP_HOURS: {garmin_sleep_h:.2f}h "
        f"(device-measured, date={garmin_date_used}, source=garmin_device)"
    )
elif garmin_sleep_h is not None and not garmin_is_today:
    sleep_parts.append(
        f"GARMIN SLEEP NOT YET AVAILABLE for last night. "
        f"Do NOT cite a Garmin sleep number. The most recent Garmin sleep "
        f"is from {garmin_date_used} ({garmin_sleep_h:.2f}h) — that is NOT last night."
    )
    garmin_sleep_h = None  # Prevent validator from accepting stale value
```

**Update all callers** that destructure the return value — search for `_get_garmin_sleep_h_for_last_night` in the file. The function currently returns a 2-tuple; it now returns a 3-tuple. There are callers in `generate_coach_home_briefing` and possibly in `home_briefing_tasks.py`.

**File: `apps/api/tasks/garmin_webhook_tasks.py`, around line 795**

Change `enqueue_briefing_refresh` call to use `force=True` when sleep data updates:

```python
if processed > 0:
    try:
        from services.home_briefing_cache import mark_briefing_dirty
        from tasks.home_briefing_tasks import enqueue_briefing_refresh

        mark_briefing_dirty(str(athlete_id))
        enqueue_briefing_refresh(str(athlete_id), force=True)  # Sleep corrections must bypass cooldown
```

Check if `enqueue_briefing_refresh` accepts a `force` parameter. If not, check the function signature and pass whatever parameter bypasses the cooldown.

### Tests

1. `test_garmin_sleep_returns_stale_flag_when_fallback` — mock GarminDay with only yesterday's date → `is_today=False`
2. `test_garmin_sleep_returns_fresh_flag_when_today` — mock GarminDay with today's date → `is_today=True`
3. `test_sleep_contract_suppresses_stale_garmin` — when `is_today=False`, prompt must NOT contain `GARMIN_LAST_NIGHT_SLEEP_HOURS`
4. `test_sleep_contract_shows_fresh_garmin` — when `is_today=True`, prompt contains the value
5. `test_garmin_health_refresh_uses_force` — verify `enqueue_briefing_refresh` is called with force when sleep updates

---

## Fix 2: Two Paragraphs in Morning Voice

### Problem

`validate_voice_output` (line 740 of `apps/api/routers/home.py`) has no paragraph detection. The comment at line 801 says "Structure is enforced by the prompt" — but the LLM ignores the prompt constraint. After removing the 280-char cap, the LLM now generates multi-paragraph output with nothing to stop it.

### Fix

**File: `apps/api/routers/home.py`, function `validate_voice_output` (around line 808, after the length check)**

Add a paragraph enforcement check before the final `return {"valid": True}`:

```python
    # 5. Paragraph enforcement — ONE paragraph only, mechanically enforced.
    # The prompt says "ONE paragraph only" but LLMs ignore this without a backstop.
    if field == "morning_voice":
        stripped = text.strip()
        if "\n" in stripped:
            first_para = stripped.split("\n")[0].strip()
            if len(first_para) >= 40 and re.search(r'\d', first_para):
                logger.warning(
                    "morning_voice had %d paragraphs; truncated to first (%d chars)",
                    stripped.count("\n") + 1, len(first_para),
                )
                return {"valid": True, "truncated_text": first_para}
            return {
                "valid": False,
                "reason": "structure:multiple_paragraphs_short_first",
                "fallback": _VOICE_FALLBACK,
            }

    return {"valid": True}
```

**Then update the callers** that use `validate_voice_output` to check for the `truncated_text` key. There are two callers:

1. `generate_coach_home_briefing` (around line 1170):
```python
    voice_check = validate_voice_output(raw_voice, field="morning_voice")
    if not voice_check["valid"]:
        result["morning_voice"] = voice_check["fallback"]
    elif voice_check.get("truncated_text"):
        result["morning_voice"] = voice_check["truncated_text"]
```

2. `home_briefing_tasks.py` — search for `validate_voice_output` and apply the same pattern.

### Tests

1. `test_single_paragraph_passes` — text with no newlines → `valid=True`, no `truncated_text`
2. `test_multi_paragraph_truncated_to_first` — text with `\n\n` → `valid=True`, `truncated_text` = first paragraph
3. `test_multi_paragraph_short_first_fails` — first paragraph < 40 chars → `valid=False`
4. `test_newline_only_in_non_morning_voice_ignored` — field="workout_why" with newlines → no truncation (paragraph check only for morning_voice)

---

## Fix 3: "tsb" Leaking in Finding Card

### Problem

`HomeFinding.text` (line 2830 of `apps/api/routers/home.py`) uses `CorrelationFinding.insight_text` directly. That text is built by `_build_insight_text` in `apps/api/services/n1_insight_generator.py`, which calls `_friendly("tsb")`. But `FRIENDLY_NAMES` (line 89 of `n1_insight_generator.py`) doesn't include `tsb`, `ctl`, or `atl`, so they pass through as raw acronyms. No sanitization happens between database and frontend.

### Fix (two layers)

**Layer 1 — Fix at source: `apps/api/services/n1_insight_generator.py`, `FRIENDLY_NAMES` dict (around line 89)**

Add the missing internal metrics:

```python
FRIENDLY_NAMES: Dict[str, str] = {
    # ... existing entries ...
    "tsb": "form (training readiness)",
    "ctl": "fitness (training load)",
    "atl": "fatigue (recent load)",
    "chronic_load": "fitness (training load)",
    "acute_load": "fatigue (recent load)",
    "form_score": "form (training readiness)",
}
```

**Layer 2 — Fix at display: `apps/api/routers/home.py`, where `HomeFinding` is constructed (around line 2829)**

Add a sanitization pass on the text before it reaches the frontend:

```python
def _sanitize_finding_text(text: str) -> str:
    """Remove internal metric references from finding text shown to athletes."""
    replacements = {
        " tsb ": " form ",
        " ctl ": " fitness ",
        " atl ": " fatigue ",
        " tsb.": " form.",
        " ctl.": " fitness.",
        " atl.": " fatigue.",
        "your tsb": "your form",
        "your ctl": "your fitness",
        "your atl": "your fatigue",
    }
    lower = text
    for raw, clean in replacements.items():
        lower = lower.replace(raw, clean)
    return lower
```

Apply it at line 2830:

```python
raw_text = f.insight_text or f"{f.input_name.replace('_', ' ')} affects your {f.output_metric}"
home_finding = HomeFinding(
    text=_sanitize_finding_text(raw_text),
    ...
)
```

Also apply it in the `compute_coach_noticed` finding path (around lines 1630-1657) where `finding_text` is built from `f.insight_text` and `f.input_name` — same pattern, same raw metrics.

**Layer 3 — Backfill existing insight_text** (optional but recommended):

The `insight_text` values stored in `CorrelationFinding` rows still contain "tsb". On the next daily correlation sweep, newly confirmed findings will get clean text from the updated `FRIENDLY_NAMES`. For existing rows, either:
- Let them get overwritten on next confirmation, OR
- Run a one-time update: `UPDATE correlation_finding SET insight_text = REPLACE(insight_text, 'your tsb', 'your form') WHERE insight_text LIKE '%tsb%'`

### Tests

1. `test_friendly_names_includes_tsb_ctl_atl` — assert "tsb", "ctl", "atl" all in `FRIENDLY_NAMES`
2. `test_sanitize_finding_text_replaces_tsb` — "when your tsb is higher" → "when your form is higher"
3. `test_sanitize_finding_text_no_change_clean_text` — text without internal metrics passes through unchanged
4. `test_home_finding_text_sanitized` — mock a CorrelationFinding with "tsb" in insight_text, verify HomeFinding.text doesn't contain it

---

## Deployment Order

1. Fix 3 (TSB leak) — smallest, no risk
2. Fix 2 (two paragraphs) — straightforward validator addition
3. Fix 1 (sleep staleness) — largest, changes return signature

All three can ship in one commit if tests pass. Run `test_home_voice.py`, `test_race_week_weather.py`, and the new regression tests.

---

## Acceptance Criteria

- [ ] Morning voice is always ONE paragraph. If LLM generates two, the second is stripped.
- [ ] No athlete-facing surface shows "tsb", "ctl", or "atl" as raw text.
- [ ] When Garmin sleep for today hasn't synced, the system does NOT present yesterday's value as "last night." It either uses the check-in value or says nothing about Garmin sleep.
- [ ] When Garmin health data (sleep) arrives, briefing refresh bypasses cooldown.
