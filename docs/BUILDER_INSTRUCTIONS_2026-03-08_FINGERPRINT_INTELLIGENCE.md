# Builder Instructions: Wire Fingerprint Intelligence Forward

**Date:** March 8, 2026
**Priority:** P1 — execute after dedup/worker instructions deploy
**Scope:** Backend prompt enrichment + context wiring. No frontend changes.
**Estimated tests:** 15-20 new tests across 3 areas

---

## What This Does

The backend already computes confirmed personal findings (thresholds, asymmetry ratios, decay curves) and stores them in `CorrelationFinding` and `AthleteFinding`. But the systems that SPEAK to the athlete — the morning voice, the AI coach, the coach noticed signal — don't know about them. They run live correlations or use generic metrics instead of referencing the athlete's confirmed, persistent patterns.

This wires the confirmed intelligence forward so the athlete hears the system reference their specific patterns: "Your data shows your sleep cliff is at 6.2 hours — last night was 5.5, and the effect peaks tomorrow based on your decay curve."

Three changes, all backend. No new endpoints. No frontend work.

---

## Step 1: Enrich Morning Voice with Confirmed Fingerprint

**File:** `apps/api/routers/home.py`
**Function:** `_build_rich_intelligence_context()`

This function currently assembles 7 intelligence sources for the briefing prompt. Add an 8th source: the athlete's confirmed fingerprint from persisted `CorrelationFinding` rows.

**Add after source 7 (the "Recent activity shapes" block, which ends with the `sections.append("--- This Week's Training...")` call):**

```python
# 8. Personal Fingerprint — confirmed correlation findings with layer intelligence
try:
    from models import CorrelationFinding as _CF

    confirmed = (
        db.query(_CF)
        .filter(
            _CF.athlete_id == athlete_uuid,
            _CF.is_active == True,
            _CF.times_confirmed >= 3,
        )
        .order_by(_CF.times_confirmed.desc())
        .limit(8)
        .all()
    )

    if confirmed:
        lines = []
        for f in confirmed:
            parts = [
                f"- {f.input_name} → {f.output_metric}: "
                f"{f.insight_text or f.direction} "
                f"(confirmed {f.times_confirmed}x, r={f.correlation_coefficient:.2f}, "
                f"strength: {f.strength})"
            ]

            if f.threshold_value is not None:
                parts.append(
                    f"    Personal threshold: {f.input_name} cliff at "
                    f"{f.threshold_value:.1f} ({f.threshold_direction}). "
                    f"Below: r={f.r_below_threshold:.2f} (n={f.n_below_threshold}), "
                    f"Above: r={f.r_above_threshold:.2f} (n={f.n_above_threshold})"
                )

            if f.asymmetry_ratio is not None:
                parts.append(
                    f"    Asymmetry: {f.asymmetry_ratio:.1f}x "
                    f"({f.asymmetry_direction}). "
                    f"Below baseline: effect={f.effect_below_baseline:.2f}, "
                    f"Above baseline: effect={f.effect_above_baseline:.2f}"
                )

            if f.decay_half_life_days is not None:
                parts.append(
                    f"    Timing: effect half-life {f.decay_half_life_days:.1f} days "
                    f"({f.decay_type})"
                )

            lines.append("\n".join(parts))

        sections.append(
            "--- Personal Fingerprint (confirmed patterns with evidence counts) ---\n"
            "IMPORTANT: When referencing these patterns, cite the confirmation count. "
            "Use threshold values for specific recommendations. "
            "Use decay timing for forward-looking advice.\n\n"
            + "\n".join(lines)
        )
except Exception as e:
    logger.debug(
        "Personal fingerprint failed for home briefing (%s): %s",
        athlete_id, e,
    )
```

**Also: add prompt instruction.** In the `parts` list that builds the user prompt (inside `generate_coach_home_briefing`, after the "COACHING TONE RULES" entries), add:

```python
"PERSONAL FINGERPRINT CONTRACT:",
"- When the DEEP INTELLIGENCE section contains confirmed patterns, reference them by evidence count.",
"- Use threshold values to give specific advice ('your sleep cliff is at 6.2h — last night was 5.5').",
"- Use asymmetry ratios to convey magnitude ('bad sleep hurts you 3x more than good sleep helps').",
"- Use decay timing for forward-looking advice ('the effect peaks tomorrow based on your 2-day half-life').",
"- NEVER reference a pattern without its confirmation count. This builds athlete trust.",
"- If no confirmed patterns exist, do not mention the fingerprint — coach from the other data.",
"",
```

**Why this matters:** Source 1 (N=1 insights) runs live `analyze_correlations()` which is volatile — it may produce different results each time. Source 8 reads CONFIRMED, PERSISTED findings with their specific layer parameters. The athlete hears "confirmed 47 times" instead of a correlation that might not reproduce next time.

---

## Step 2: Enrich Coach Brief with Personal Fingerprint

**File:** `apps/api/services/coach_tools.py`
**Function:** `build_athlete_brief()`

The brief currently has 12 sections. Section 10 ("N-of-1 Insights") runs live `get_correlations()` which returns basic r/n/lag but NO layer data (no thresholds, no asymmetry ratios, no decay half-lives).

**Replace section 10 (the block starting with `# ── 10. N-OF-1 INSIGHTS` through its `except` handler) with an expanded version:**

```python
# ── 10. PERSONAL FINGERPRINT (confirmed patterns with layer intelligence) ──
try:
    from models import CorrelationFinding as _CF

    confirmed = (
        db.query(_CF)
        .filter(
            _CF.athlete_id == athlete_id,
            _CF.is_active == True,
            _CF.times_confirmed >= 3,
        )
        .order_by(_CF.times_confirmed.desc())
        .limit(10)
        .all()
    )

    if confirmed:
        lines = [
            "(These are confirmed personal patterns — cite evidence counts when referencing them. "
            "Use layer data for specific, grounded recommendations.)"
        ]
        for f in confirmed:
            entry = (
                f"  {f.input_name} → {f.output_metric}: {f.insight_text or f.direction} "
                f"(confirmed {f.times_confirmed}x, r={f.correlation_coefficient:.2f})"
            )

            details = []
            if f.threshold_value is not None:
                details.append(
                    f"Threshold: {f.input_name} cliff at {f.threshold_value:.1f}"
                )
            if f.asymmetry_ratio is not None:
                details.append(
                    f"Asymmetry: {f.asymmetry_ratio:.1f}x ({f.asymmetry_direction})"
                )
            if f.decay_half_life_days is not None:
                details.append(
                    f"Timing: half-life {f.decay_half_life_days:.1f} days ({f.decay_type})"
                )
            if f.time_lag_days and f.time_lag_days > 0:
                details.append(f"Lag: {f.time_lag_days} day(s)")

            if details:
                entry += " — " + ", ".join(details)

            lines.append(entry)

        sections.append("## Personal Fingerprint\n" + "\n".join(lines))
    else:
        corr = get_correlations(db, athlete_id, days=90)
        if corr.get("ok"):
            corr_data = corr.get("data", {})
            correlations = corr_data.get("correlations", []) if isinstance(corr_data, dict) else []
            if isinstance(correlations, list) and correlations:
                lines = []
                for c in correlations[:5]:
                    input_name = c.get("input_name", "?")
                    output_name = c.get("output_name", "?")
                    r = c.get("correlation_coefficient", 0)
                    n = c.get("sample_size", 0)
                    direction = "positively" if r > 0 else "inversely"
                    lines.append(
                        f"  {input_name} {direction} correlates with {output_name} "
                        f"(r={r:.2f}, n={n})"
                    )
                if lines:
                    sections.append("## N-of-1 Insights (Correlations)\n" + "\n".join(lines))
except Exception as e:
    logger.debug(f"Brief: personal fingerprint failed: {e}")
```

**Key design:** If confirmed findings exist (times_confirmed >= 3), show the rich fingerprint with layer data. If not (new athlete, insufficient data), fall back to the existing live correlation output. The coach always gets SOMETHING, but confirmed athletes get the full intelligence.

**Also add after section 10:** Investigation findings from `AthleteFinding`:

```python
# ── 10b. INVESTIGATION FINDINGS (race input analysis) ──
try:
    from services.finding_persistence import get_active_findings
    stored = get_active_findings(athlete_id, db)
    if stored:
        lines = [
            "(Investigation findings — what the system discovered about this athlete's training patterns.)"
        ]
        for f in stored[:8]:
            conf_label = f"confidence: {f.confidence}" if f.confidence else ""
            lines.append(f"  [{f.investigation_name}] {f.sentence} ({conf_label})")
        sections.append("## Training Discoveries\n" + "\n".join(lines))
except Exception as e:
    logger.debug(f"Brief: investigation findings failed: {e}")
```

---

## Step 3: Update Coach System Prompts

**File:** `apps/api/services/ai_coach.py`

### Gemini system prompt (in `query_gemini`, after the `COMMUNICATION STYLE:` section)

```
PERSONAL FINGERPRINT:
- The ATHLETE BRIEF may contain a "Personal Fingerprint" section with confirmed patterns.
- These patterns have been individually validated for THIS athlete — they are not population statistics.
- When relevant to the athlete's question, reference confirmed patterns by evidence count.
- Use threshold values for specific recommendations (e.g., "your data shows a sleep cliff at 6.2 hours").
- Use asymmetry data to convey magnitude (e.g., "bad sleep hurts you 3x more than good sleep helps").
- Use decay timing for forward-looking advice (e.g., "the effect typically peaks after 2 days for you").
- NEVER reference a pattern without its confirmation count. This is how the athlete trusts the system.
- If no fingerprint data exists, coach from the other brief sections normally.
```

### Opus system prompt (in `query_opus`, after the `COMMUNICATION:` section)

The Opus path does NOT inject the athlete brief today — it relies on tool calls. The existing `get_correlations` tool runs live volatile analysis and does NOT return persisted layer data (thresholds, asymmetry, decay). Two options to fix this:

**Option A (recommended): Inject the brief into the Opus path too.** In `query_opus()`, after building the system prompt, append the athlete brief the same way the Gemini path does:

```python
try:
    from services.coach_tools import build_athlete_brief
    brief = build_athlete_brief(self.db, athlete_id)
    if brief and "Personal Fingerprint" in brief:
        system_prompt += f"\n\nATHLETE BRIEF (pre-computed, confirmed patterns):\n{brief}"
except Exception:
    pass  # Opus falls back to tools
```

Then add to the Opus system prompt text:

```
PERSONAL FINGERPRINT:
- The ATHLETE BRIEF below may contain a "Personal Fingerprint" section with confirmed patterns.
- These have been individually validated for THIS athlete — they are not population statistics.
- When relevant, reference confirmed patterns by evidence count.
- Use threshold values, asymmetry ratios, and decay timing for specific, grounded advice.
- You still have tools — use them for data NOT in the brief. But prefer the brief for confirmed patterns.
```

**Option B (alternative): Add a new tool `get_personal_fingerprint`.** This queries persisted `CorrelationFinding` with layer data. More work, but cleaner separation. Only do this if Option A creates prompt-length issues.

**Do Option A.** The brief is already computed and cached (15-min TTL). Adding it to the Opus path costs one cache read and gives the most capable model access to the richest intelligence.

**Freshness contract (explicit):** `build_athlete_brief` is cached for 15 minutes. New/updated fingerprint findings may take up to 15 minutes to appear in coach responses unless athlete cache invalidation is triggered earlier by activity-write paths. This is acceptable for this phase (eventual consistency <= 15 min).

---

## Step 4: Upgrade `compute_coach_noticed`

**File:** `apps/api/routers/home.py`
**Function:** `compute_coach_noticed()`

The current priority waterfall is:
1. Strong live correlation (|r| >= 0.5, n >= 15)
2. Home signals
3. Insight feed card
4. Hero narrative fallback

**Add a new priority level between 1 and 2:** Recently confirmed fingerprint finding.

The function uses an early-return pattern — each priority level returns a `CoachNoticed` directly. Insert a new block between the existing `except` at the end of priority 1 (after the live correlation `try/except`) and the start of priority 2 (the `aggregate_signals` block):

```python
# 1b. Recently confirmed fingerprint finding (persisted, not volatile)
try:
    from models import CorrelationFinding as _CF
    _cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent_finding = (
        db.query(_CF)
        .filter(
            _CF.athlete_id == _UUID(athlete_id),
            _CF.is_active == True,
            _CF.times_confirmed >= 3,
            _CF.last_confirmed_at >= _cutoff,
        )
        .order_by(_CF.last_confirmed_at.desc())
        .first()
    )
    if recent_finding:
        f = recent_finding
        finding_text = f.insight_text or (
            f"{f.input_name.replace('_', ' ').title()} {f.direction}ly "
            f"affects your {f.output_metric.replace('_', ' ')}"
        )
        detail_parts = [f"confirmed {f.times_confirmed}x"]
        if f.threshold_value is not None:
            detail_parts.append(f"threshold at {f.threshold_value:.1f}")
        if f.asymmetry_ratio is not None:
            detail_parts.append(f"{f.asymmetry_ratio:.1f}x asymmetry")

        text = f"{finding_text} ({', '.join(detail_parts)})."
        return CoachNoticed(
            text=text,
            source="fingerprint",
            ask_coach_query=(
                f"Tell me more about how {f.input_name.replace('_', ' ')} "
                f"affects my {f.output_metric.replace('_', ' ')}"
            ),
        )
except Exception as e:
    logger.debug("Fingerprint finding for coach_noticed failed: %s", e)
```

Note: uses `datetime.now(timezone.utc)` (timezone-aware) and the early-return pattern matching the existing function style.

---

## Implementation Note: Shared Helper

Create a shared helper function to avoid drift between the home briefing and coach brief fingerprint formatting. Suggested location: `apps/api/services/fingerprint_context.py`.

```python
def get_fingerprint_context(athlete_id: UUID, db: Session, max_findings: int = 8) -> str:
    """Format confirmed CorrelationFinding rows with layer data for prompt injection."""
    ...
```

Both `_build_rich_intelligence_context()` in `home.py` and `build_athlete_brief()` in `coach_tools.py` call this helper. Single source of truth for formatting, limits, and ordering.

---

## What NOT to Change

- Do NOT modify the existing live correlation analysis (Source 1 in `_build_rich_intelligence_context`). It serves a different purpose — discovering new patterns. The new Source 8 surfaces confirmed, persistent ones.
- Do NOT remove the fallback in `build_athlete_brief` section 10. Athletes without confirmed findings still need the live correlation output.
- Do NOT change frontend. This is purely backend intelligence wiring.
- Do NOT modify `CorrelationFinding` or `AthleteFinding` models. Read only.

---

## Testing

### Unit tests for fingerprint context (new file: `tests/test_fingerprint_intelligence.py`)

1. `test_rich_context_includes_fingerprint_when_confirmed_findings_exist` — create `CorrelationFinding` with `times_confirmed=5`, verify it appears in `_build_rich_intelligence_context()` output
2. `test_rich_context_excludes_fingerprint_below_threshold` — `times_confirmed=2`, verify it does NOT appear
3. `test_rich_context_includes_threshold_data` — finding with `threshold_value`, verify "cliff at X" appears
4. `test_rich_context_includes_asymmetry_data` — finding with `asymmetry_ratio`, verify "Nx" appears
5. `test_rich_context_includes_decay_data` — finding with `decay_half_life_days`, verify "half-life" appears
6. `test_rich_context_inactive_findings_excluded` — `is_active=False`, verify excluded
7. `test_rich_context_limited_to_8` — create 12 findings, verify only 8 appear (highest confirmed first)

### Unit tests for coach brief enrichment

8. `test_brief_includes_personal_fingerprint` — confirmed findings present, verify "Personal Fingerprint" section in brief
9. `test_brief_falls_back_to_live_correlations` — no confirmed findings, verify "N-of-1 Insights" section
10. `test_brief_includes_investigation_findings` — create `AthleteFinding` rows, verify "Training Discoveries" section
11. `test_brief_fingerprint_includes_layer_data` — verify threshold/asymmetry/decay details in brief text
12. `test_brief_fingerprint_ordering` — verify findings are ordered by `times_confirmed` descending

### Unit tests for coach_noticed upgrade

13. `test_coach_noticed_surfaces_recent_fingerprint` — recent confirmed finding, verify it appears as `source="fingerprint"`
14. `test_coach_noticed_fingerprint_requires_recent_confirmation` — finding last confirmed 30 days ago, verify it does NOT surface (7-day window)
15. `test_coach_noticed_fingerprint_requires_min_confirmations` — `times_confirmed=1`, verify excluded

### Integration test

16. `test_home_briefing_prompt_contains_fingerprint_contract` — verify the "PERSONAL FINGERPRINT CONTRACT" text appears in the prompt sent to the LLM
17. `test_coach_system_prompt_contains_fingerprint_instructions` — verify both Gemini and Opus prompts reference fingerprint usage

---

## Verification

After deployment, run on production (founder account):

```bash
docker exec -w /app strideiq_api python -c "
import sys; sys.path.insert(0, '/app')
from services.coach_tools import build_athlete_brief
from core.database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
brief = build_athlete_brief(db, user.id)
if 'Personal Fingerprint' in brief:
    print('PASS: Fingerprint section present')
    start = brief.index('## Personal Fingerprint')
    end = brief.index('##', start + 5) if '##' in brief[start+5:] else len(brief)
    print(brief[start:end])
else:
    print('FAIL: No fingerprint section — check CorrelationFinding table')
db.close()
"
```

---

## Success Criteria

The morning voice says something like: "Your confirmed sleep pattern shows a cliff at 6.2 hours — last night was 5.5, and based on your 2-day decay curve, the impact peaks tomorrow." instead of generic commentary about sleep.

The coach, when asked "should I run hard tomorrow?", answers with: "Your data shows a 3x asymmetric response to poor sleep, confirmed 47 times. Combined with your 2-day decay half-life, tomorrow is when last night's short sleep hits hardest. I'd move your intervals to Thursday."

The athlete hears the system speak with knowledge it has EARNED through months of confirmed patterns, not with generic advice dressed up in their numbers.
