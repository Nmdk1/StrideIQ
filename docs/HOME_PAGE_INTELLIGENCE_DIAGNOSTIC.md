# Home Page Intelligence — Diagnostic Report

**Date:** March 9, 2026
**Author:** Top Advisor
**Purpose:** Comprehensive analysis of why the home page fails to deliver intelligence, with proposed solutions and failure mode analysis

---

## How the Home Page Briefing Is Generated

One LLM call generates ALL home page narrative text. The LLM receives a massive prompt assembled from 8+ data sources and returns a JSON object with 6 fields: `morning_voice`, `coach_noticed`, `today_context`, `week_assessment`, `checkin_reaction`, `race_assessment`. Each field becomes a separate visible section on the home page.

The prompt is ~2000+ tokens of instructions followed by the athlete's data. The LLM has to satisfy contradictory instructions, balance multiple data sources, and produce all sections in one shot. There is no per-section control — the LLM decides what goes where.

---

## Architecture Diagram

```
8 data sources → _build_rich_intelligence_context() → single "DEEP INTELLIGENCE" block
                                                           ↓
athlete brief + today's plan + check-in + sleep data → PROMPT (~2000 tokens of rules)
                                                           ↓
                                                      ONE LLM call
                                                           ↓
                                              6 JSON fields → 6 UI sections
```

---

## The 8 Intelligence Sources Feeding the Prompt

| # | Source | What it provides | Current state |
|---|--------|-----------------|---------------|
| 1 | N=1 insight generator | Live volatile correlations (Bonferroni-corrected) | Working — but these are RECOMPUTED each call, redundant with source 8 |
| 2 | Daily intelligence rules | Rules that fired today (load spike, efficiency break, etc.) | Working — 8 rules |
| 3 | Wellness trends | 28-day check-in aggregation narrative | Working |
| 4 | PB patterns | Training conditions preceding PBs | Working |
| 5 | Block comparison | This 28-day block vs previous 28-day block | Working |
| 6 | Training story engine | Race stories, progressions, campaign narrative | Broken campaign just fixed — now reads from real campaign detector |
| 7 | Recent activity shapes | This week's shape sentences | Working |
| 8 | Personal fingerprint | Confirmed CorrelationFindings with layer data (threshold, asymmetry, decay) | Working — 8 findings (2 strong, 6 emerging) |

**Problem 1: Sources 1 and 8 overlap.** Source 1 (N=1 insight generator) recomputes volatile correlations live. Source 8 (fingerprint context) reads persisted, confirmed findings. They're looking at the same underlying data but source 1 is volatile and source 8 is stable. The LLM sees both versions of the same patterns and picks whichever it wants. This creates inconsistency and amplifies repetition.

**Problem 2: Too much data, no hierarchy.** The LLM receives all 8 sources with equal weight. It has no way to know that the confirmed 17x readiness finding is more important than a PB pattern from 2024. It picks the most statistically impressive number ("confirmed 17 times") because the prompt says "reference them by evidence count."

**Problem 3: The prompt INSTRUCTS the LLM to cite confirmation counts.** Line 1315: "When the DEEP INTELLIGENCE section contains confirmed patterns, reference them by evidence count." Line 1319: "NEVER reference a pattern without its confirmation count." The system-speak isn't a model failure — it's following instructions.

---

## Issue-by-Issue Analysis

### Issue 1: "Confirmed 17 times" — System-Speak Facing the Athlete

**Root cause:** The prompt explicitly instructs the LLM to cite confirmation counts (lines 1315, 1319). The fingerprint context format includes `[STRONG 17x]` tier labels. The LLM is doing exactly what it was told.

**Fix:** Change the prompt instructions. Remove "reference them by evidence count" and "NEVER reference a pattern without its confirmation count." Replace with instructions to translate statistical evidence into coaching language. Change the fingerprint context format to use coaching language tiers ("proven pattern" / "emerging pattern") instead of `[STRONG 17x]`.

**Failure mode:** None. The LLM still receives the tier information for its own reasoning. It just stops quoting it to the athlete.

### Issue 2: Same Finding Repeated Across All Sections

**Root cause:** One LLM call generates all 6 sections. The LLM receives all findings in one prompt and naturally gravitates to the strongest one. There is no structural mechanism preventing it from using the same finding in `morning_voice`, `coach_noticed`, `checkin_reaction`, `week_assessment`, and `race_assessment` simultaneously.

The existing "ONE-NEW-THING RULE" (line 1452) says "contain exactly ONE observation the athlete didn't know yesterday." But this applies to the overall briefing, not per-section. And the LLM interprets "one observation" as "mention the strongest finding" — which it does in every section because nothing prevents it.

**Fix options (in order of reliability):**

**Option A (Structural — recommended):** Don't rely on the LLM for diversity. Assign each schema field a specific data source in the prompt:
- `morning_voice`: personal fingerprint findings ONLY (source 8)
- `coach_noticed`: daily intelligence rules or wellness trends (sources 2, 3) — NOT findings
- `checkin_reaction`: the athlete's check-in data + today's plan (deterministic data already in prompt)
- `week_assessment`: block comparison + activity shapes (sources 5, 7) — volume/load trajectory
- `race_assessment`: race countdown data + training story (deterministic race math)
- `today_context`: today's workout + plan adherence (deterministic data already in prompt)

This is structural because each field draws from a DIFFERENT source. The LLM can't repeat a finding across sections because only one section is allowed to reference findings. The others have their own designated data.

**Option B (Prompt-only):** Add a diversity instruction. Less reliable because LLMs don't consistently follow negative constraints across a complex JSON generation task.

**Failure mode for Option A:** If a designated source has no data (e.g., no daily intelligence rules fired today), the LLM has less material for that section. The instruction should say: "If no data exists for this section, write 1 short factual sentence or omit the field." The UI already handles null fields gracefully.

### Issue 3: Source 1 (N=1 Insights) Redundant with Source 8 (Fingerprint)

**Root cause:** Source 1 (`generate_n1_insights`) recomputes correlations live every time the home page loads. Source 8 (`build_fingerprint_prompt_section`) reads from persisted, confirmed CorrelationFindings. They're the same underlying analysis but source 1 is volatile and source 8 is curated. Both appear in the prompt, giving the LLM two versions of the same patterns.

**Fix:** Remove source 1 from `_build_rich_intelligence_context`. Source 8 is the curated, tier-labeled, layer-enriched version. Source 1 is its noisy predecessor. Removing it:
- Reduces prompt size
- Eliminates duplicate/conflicting pattern presentation
- Reduces compute (source 1 runs the correlation engine live, which is expensive)

**Failure mode:** If source 8 is empty (new athlete with no confirmed findings), source 1 would have provided volatile patterns. But these volatile patterns are exactly the kind of unconfirmed data that produces the "weak sauce" output. Silence is better until findings are confirmed.

### Issue 4: `compute_coach_noticed` Has TWO Paths That Both Use System-Speak

**Root cause:** `compute_coach_noticed` has a priority waterfall:
1. First: live `analyze_correlations()` with `r=` values and statistical language (line 1496-1525)
2. Then: persisted CorrelationFinding with "confirmed Nx" text (line 1529-1565)

Path 1 runs the full correlation engine live on every call, formats the result with `r={r:.2f}` and `{n} observations`, and returns it as athlete-facing text. This is raw statistical output shown directly to the athlete.

Path 1b reads persisted findings and formats them with "confirmed {f.times_confirmed}x".

Both paths produce system-speak because they're formatting raw data directly, not translating it.

**Fix:** 
- Remove path 1 entirely. It recomputes correlations live (expensive, volatile) and formats them with raw stats. The persisted findings in path 1b are the curated version.
- In path 1b, format the text as coaching language, not statistics. "Your readiness directly shapes how efficiently you run — the effect shows up about 3 days later" instead of "Readiness 1 5 positively correlates with your efficiency (r=0.56, 17 observations)."
- The `ask_coach_query` is fine as-is — it's a prompt for the athlete to ask the coach, not athlete-facing text.

**Failure mode:** If no persisted findings exist (new athlete), path 1b returns nothing and the waterfall falls through to paths 2-4 (home signals, insight feed, hero narrative). These already exist and work.

### Issue 5: Coach Noticed Always Shows the Same Finding

**Root cause:** The fingerprint query orders by `times_confirmed DESC` and takes `.first()`. The finding with the most confirmations always wins. The 48h Redis rotation (mentioned in the audit) applies to the LLM-generated `coach_noticed` field, not to the `compute_coach_noticed` deterministic output. These are separate systems that both produce "coach noticed" content.

**Fix:** Rotate through findings by day. Query top 5, select by `day_of_year % len(findings)`. This is deterministic (same finding all day, different finding tomorrow), requires no Redis state, and guarantees diversity.

**Failure mode:** If only 1 finding exists, rotation returns the same one daily. That's correct — there IS only one thing to notice. The failure mode is acceptable.

### Issue 6: Campaign Narrative Was Wrong (Now Fixed)

**Root cause:** Duplicate campaign detectors. The naive one in training_story_engine.py took `min(start)` to `max(end)` across all adaptation findings and called it one campaign. No disruption awareness. This produced "27-week campaign" when reality was two separate arcs split by a femur fracture.

**Status:** Fixed in commit `e27e204`. The naive detector is replaced with a reader of the real campaign detector's output. If no campaign data exists, returns None (silence). Regression-tested.

---

## Codex Review Findings (incorporated)

Three must-fix items identified by tech advisor:

1. **Change 2 is not structurally enforceable with one LLM call.** Prompt-only lane instructions can be ignored. Calling it "structural" was overstated. Need code-level enforcement.
2. **Contradictory instructions exist.** If `coach_noticed` is reassigned away from fingerprint, two existing instructions still mandate it draw from DEEP INTELLIGENCE. Both must be removed simultaneously.
3. **`compute_coach_noticed` uses `times_confirmed >= 1`** — surfaces emerging findings on a high-trust surface. Must be `>= 3` if trust-first.

All three are addressed in the revised solution below.

---

## Proposed Solution: Three Changes

### Change 1: Fix the Prompt Instructions

Remove system-speak instructions. Replace with coaching language instructions. Remove "cite confirmation count" mandate. Add "NEVER cite statistical values to the athlete." Change fingerprint context header to remove "Cite the confirmation count."

This is the prompt text changes from the builder instructions I already wrote. Those specific changes are correct. The problem was I didn't think through the downstream effects before presenting them.

### Change 2: Per-Field Context Injection + Post-Generation Validation

The Codex review correctly identified that prompt-only lane assignments are not structural — a single LLM call can ignore them. Two enforcement mechanisms are needed:

**2a: Embed per-field context into schema field descriptions.**

Instead of giving the LLM the full DEEP INTELLIGENCE block and hoping it respects lane assignments, pre-format the relevant data snippet INTO each schema field description. The LLM still receives the full context for reasoning, but each field description contains the specific data it should reference.

Updated `schema_fields` dict:

```python
schema_fields = {
    "morning_voice": f"One paragraph giving your athlete's data a voice. 40-280 chars. "
        f"YOUR DATA FOR THIS FIELD: {fingerprint_summary or 'No personal patterns yet — reference last run and today.'}. "
        f"Connect this to today. Must cite one specific number (pace, HR, distance). "
        f"ABSOLUTE BAN on CTL, ATL, TSB, confirmation counts, r-values.",

    "coach_noticed": f"The single most important coaching observation. "
        f"YOUR DATA FOR THIS FIELD: {coach_noticed_intel.text if coach_noticed_intel else 'No intelligence rule fired — reference this weeks training trend.'}. "
        f"DO NOT reference personal fingerprint findings here. 1-2 sentences.",

    "checkin_reaction": "Acknowledge how the athlete feels FIRST, then connect to what's ahead today. "
        "YOUR DATA: the check-in values above. "
        "DO NOT repeat any pattern or finding mentioned in morning_voice. 1-2 sentences.",

    "week_assessment": f"What this week's trajectory means for near-term training. "
        f"YOUR DATA FOR THIS FIELD: {week_context or 'Use volume and activity data above.'}. "
        f"DO NOT reference personal fingerprint findings here. 1 sentence.",

    "race_assessment": "Honest readiness assessment based on current fitness. "
        "YOUR DATA: race countdown and training load data above. "
        "DO NOT reference personal fingerprint findings here. 1-2 sentences.",

    "today_context": "Action-focused: what today should look like. "
        "YOUR DATA: today's plan and completed activities above. 1-2 sentences.",

    "workout_why": "One sentence: why today's workout matters. No sycophantic language.",
}
```

This requires building `fingerprint_summary`, `week_context`, etc. as short pre-formatted strings BEFORE prompt assembly. Each is a 1-2 sentence distillation of the relevant source, formatted in coaching language (not raw data).

**2b: Post-generation validator for cross-lane leakage.**

After the LLM returns the JSON, check for repetition before caching:

```python
def _validate_briefing_diversity(fields: dict) -> dict:
    """Flag or strip repeated phrases across fields."""
    fingerprint_terms = set()
    # Extract key terms from morning_voice (the only field allowed findings)
    mv = fields.get("morning_voice", "")
    # Simple: if a finding keyword (e.g., "readiness", "sleep cliff", "3-day") 
    # appears in morning_voice AND in 2+ other fields, strip it from the others
    for term in ["readiness", "efficiency", "sleep", "lag", "threshold", "asymmetry"]:
        if term in mv.lower():
            fingerprint_terms.add(term)
    
    for field_name in ["coach_noticed", "checkin_reaction", "week_assessment", "race_assessment"]:
        text = fields.get(field_name, "")
        overlap_count = sum(1 for t in fingerprint_terms if t in text.lower())
        if overlap_count >= 2:
            # Log the violation for monitoring; optionally regenerate
            logger.warning(f"Cross-lane leakage in {field_name}: {overlap_count} fingerprint terms found")
    
    return fields
```

This is a monitoring validator initially (log, don't block). Once we verify the prompt lanes work, it can become a hard gate.

**2c: Remove contradictory instructions (must-fix from Codex).**

Three locations must be updated simultaneously:

1. **Line 1355-1358** — Remove:
   ```
   "CRITICAL INSTRUCTION: The DEEP INTELLIGENCE section above contains findings",
   "the athlete CANNOT derive from looking at their own data. Your morning_voice",
   "and coach_noticed MUST draw from this section. If you ignore it and produce",
   "generic observations like weekly mileage totals, your output will be rejected.",
   ```
   Replace with:
   ```
   "CRITICAL INSTRUCTION: The DEEP INTELLIGENCE section above is for YOUR reasoning.",
   "Each output field below specifies which data source to draw from.",
   "Follow the YOUR DATA instruction in each field. Do not use fingerprint findings",
   "outside of morning_voice.",
   ```

2. **`schema_fields["coach_noticed"]`** (line 1463) — Currently says "Draw from the DEEP INTELLIGENCE personal patterns section." Must be changed to reference intelligence rules / wellness trends instead (as shown in 2a above).

3. **`schema_fields["morning_voice"]`** (line 1468) — Currently says "PRIORITIZE insights from the DEEP INTELLIGENCE section." Must be changed to reference the pre-formatted `fingerprint_summary` (as shown in 2a above).

**Failure mode analysis:**
- `morning_voice` with no findings: Pre-formatted `fingerprint_summary` says "No personal patterns yet — reference last run and today." The LLM coaches from deterministic data. Short, factual, no fabrication.
- `coach_noticed` with no intelligence rules: `compute_coach_noticed` waterfall falls through to wellness trends → home signals → insight feed → hero narrative. At least one will have data.
- `checkin_reaction` with no check-in: Field is already not required when no check-in data exists (line 1472-1473).
- `week_assessment` with no block comparison: Pre-formatted `week_context` falls back to "Use volume and activity data above." The LLM references the weekly run count and activity shapes already in the prompt.
- `race_assessment` with no race: Field is already not required (line 1474-1475).

No section goes empty. Each has a natural fallback within its designated source.

### Change 3: Remove Redundant Sources + Fix Thresholds

**3a: Remove source 1** (`generate_n1_insights`) from `_build_rich_intelligence_context`. Source 8 (persisted fingerprint) is the curated replacement. This reduces prompt size, eliminates duplicate pattern presentation, and removes an expensive live correlation recomputation on every home page load.

**Cold-start contract** (from Codex should-address): For athletes with no confirmed findings, the `_build_rich_intelligence_context` will have sources 2-7 but not 1 or 8. Each remaining source has its own try/except and returns empty on failure. The prompt already handles "if no confirmed patterns exist, do not mention the fingerprint." Explicit per-field fallback text is embedded in the schema field descriptions (Change 2a). No additional cold-start handling needed beyond what's already specified.

**3b: Remove path 1** (live `analyze_correlations()`) from `compute_coach_noticed` (lines 1494-1525). This path runs the full correlation engine live, formats with `r={r:.2f}` and `{n} observations`, and produces system-speak. The persisted findings in path 1b are the curated replacement.

**3c: Fix threshold in path 1b** (must-fix from Codex). Currently `times_confirmed >= 1`. Change to `times_confirmed >= 3`. Coach noticed is a high-visibility, high-trust surface. Emerging findings (1-2 confirmations) are not proven enough for a standalone claim. The morning voice can reference emerging findings with appropriate hedging because it's narrative context, not a standalone assertion.

**3d: Reformat path 1b text** to coaching language. Replace:
```python
detail_parts = [f"confirmed {f.times_confirmed}x"]
```
With coaching-language formatting (no confirmation counts, no r-values — describe what the pattern means for the athlete's next run).

**3e: Add daily rotation** to finding selection. Query top 5 findings (all `times_confirmed >= 3`), select by `date.today().toordinal() % len(findings)`. Deterministic within a day, different tomorrow.

**3f: Repetition enforcement test** (from Codex should-address). New test: generate a briefing payload from a fixture with known findings, assert the same finding keyword does not appear in more than 2 of the 6 output fields.

---

## What This Does NOT Fix (and shouldn't yet)

- **Visual design of the home page.** The sections are still text blocks with no visual hierarchy. That's a frontend design task, not a prompt task. Fix the intelligence quality first, then address presentation.
- **Weather surface.** Confirmed as a future permanent home page element. Needs forecast API integration. Not part of this fix.
- **Situational intelligence slot.** Race week, injury return, milestones. This is the next design decision after the prompts are clean.

---

## Sequencing

1. **Change 1 + Change 3** ship together — prompt text fixes + remove redundant sources + fix thresholds + rotation. All in `home.py` and `fingerprint_context.py`. Safe, narrow.
2. **Change 2** ships second — per-field context injection + contradictory instruction removal + post-generation validator. This is the enforcement layer. Touches schema field descriptions, prompt assembly, and adds a validator function.
3. **Founder validates.** Check the home page after each deploy:
   - Does any section say "confirmed", "times", "r=", or any confirmation count? → Fail
   - Does the same finding appear in 3+ sections? → Fail
   - Does any section fabricate data not in the prompt? → Fail
   - Does each section say something the athlete values? → Pass
4. **Repetition enforcement test** ships with Change 2 — automated guard against regression.

Changes 1+3 are safe and narrow. Change 2 is the enforcement layer. Both must ship before this is considered complete.

---

## Locations That Must Change (builder reference)

| Location | What changes | Change # |
|---|---|---|
| `home.py` lines 1314-1320 | PERSONAL FINGERPRINT CONTRACT — remove "cite confirmation count" | 1 |
| `home.py` lines 1355-1358 | CRITICAL INSTRUCTION — rewrite to respect per-field lanes | 2c |
| `home.py` line 1463 | `schema_fields["coach_noticed"]` — reassign away from DEEP INTELLIGENCE | 2c |
| `home.py` line 1468 | `schema_fields["morning_voice"]` — reference pre-formatted summary, not raw section | 2c |
| `home.py` lines 1494-1525 | `compute_coach_noticed` path 1 — remove live `analyze_correlations()` | 3b |
| `home.py` line 1539 | `compute_coach_noticed` path 1b threshold — change `>= 1` to `>= 3` | 3c |
| `home.py` line 1551 | `compute_coach_noticed` path 1b text — remove "confirmed Nx" formatting | 3d |
| `home.py` lines 1632-1654 | `_build_rich_intelligence_context` source 1 — remove `generate_n1_insights` | 3a |
| `fingerprint_context.py` lines 123-128 | Header text — remove "Cite the confirmation count" | 1 |
| New function in `home.py` | `_validate_briefing_diversity()` — cross-lane leakage check | 2b |
| New function in `home.py` | Pre-format `fingerprint_summary` and `week_context` for field injection | 2a |
| New test file | Repetition enforcement test — same finding can't dominate all fields | 3f |
