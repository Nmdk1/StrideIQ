# Session Handoff — 2026-05-03 (Cursor → Kimi Transition)

**Agent**: Claude Sonnet 4.6 (Cursor)  
**Next agent**: Kimi K2.6 (Cline + OpenRouter)  
**Session date**: Sunday May 3, 2026

---

## What Was Fixed This Session

### 1. Calendar coach polluting open chat with system instructions (committed `ba3bb4e`)

**Problem**: The `/v1/calendar/coach` endpoint called `coach.chat(augmented_message)`, which internally called `_save_chat_messages` and wrote the AUTHORITATIVE FACT CAPSULE, RESPONSE CONTRACT, and all injection noise to the athlete's "open" context thread. Athletes saw these system instructions as their own messages in `/coach`.

**Root cause**: `_save_chat_messages` in `_thread.py` always writes to the "open" context_type `CoachChat`. The calendar endpoint does its own storage in a "day" context_type chat. The dual write was the bug.

**Fix**:
- Added `suppress_thread_storage: bool = False` to `AICoach.chat()` in `services/coaching/core.py`
- Calendar endpoint now passes `suppress_thread_storage=True`
- Both `_save_chat_messages` call sites in `core.py` are gated on this flag

### 2. JSON RESPONSE CONTRACT removed from calendar augmented message (same commit)

**Problem**: The augmented message injected into calendar day questions contained `RESPONSE CONTRACT (MANDATORY): Return JSON with keys: assessment, implication, action...`. V2 sometimes followed this mandate and returned raw JSON. That raw JSON was then stored in the open thread (see fix 1) and occasionally leaked to the athlete.

**Fix**:
- Removed the JSON format mandate entirely from the augmented message
- Kept the AUTHORITATIVE FACT CAPSULE (good grounding) but replaced the JSON instruction with a plain prose instruction: *"Answer in natural coaching prose — no JSON, no capsule label reprinting."*
- Response handler updated: V2 prose passes through `_sanitize_day_coach_text` and is used directly if > 80 chars. JSON path preserved for any legacy V1 responses.

### 3. "I cannot verify day facts safely right now." eliminated (same commit)

**Problem**: The RESPONSE CONTRACT contained a literal phrase the LLM was instructed to emit verbatim when it detected conflicting data. Athletes saw this canned string.

**Fix**: Instruction removed. V2 system prompt rule 5 handles partial evidence: give the best bounded answer, name what's missing.

### 4. "That's wrong" button removed from coach page (same commit)

**Problem**: The button pre-filled the input with `That's wrong. Please verify the data and correct this answer: "[180-char quote]"`. This formal, system-flavored correction prompt polluted conversation history and produced clunky coach interactions.

**Fix**: Button removed from `CoachTrustControls` component. `handleCorrection` function deleted. Athletes correct the coach by speaking directly — the global contract (rule 3: correction is highest-priority state) handles it.

**Tests updated**: `test_calendar_coach_trust_contract.py`, `apps/web/__tests__/coach-trust-ux.test.tsx`

---

## Current Production State

- All containers healthy as of 16:52 UTC today
- CI is green on commit `ba3bb4e`
- Coach V2 runtime is live for mbshaf@gmail.com
- Calendar coach endpoint is cleaner but has less test coverage than main coach path — it's a known gap

---

## Pending (Not Yet Committed)

### RULES.md
A consolidated operating rules document was drafted this session, consolidating all seven `.cursor/rules/*.mdc` files into a single portable markdown file for Cline/Kimi. **It has not been committed yet** — founder is reviewing per Rule 11 (no push without approval).

Location when committed: `RULES.md` at repo root.

---

## Known Issues Carried Forward (Not Fixed This Session)

### Race Outcome Reconciliation — trust-breaking, no fix yet
If an athlete DNFs a race and restarts their watch, the system sees two activity fragments and cannot distinguish a failed race from back-to-back easy runs. The morning briefing can narrate a failed race as "controlled comfortable effort." This happened to the founder during the Coke 10K on May 3. The brief said "skipping the planned race" and called it "controlled and comfortable."

**What's needed** (architectural, not a quick fix):
1. Detect planned race day from calendar
2. Gather all activities in race window
3. Stitch fragments or mark ambiguity
4. Compare expected race distance/goal to actual distance/pace/walk gaps
5. Incorporate athlete-reported outcome as authoritative
6. Classify outcome: completed, partial/DNF, skipped, ambiguous
7. Suppress positive performance narrative unless outcome is confirmed
8. Morning brief and coach both consume the reconciled outcome

This is Phase-level work. Do not patch around it. Build it properly or leave the brief silent on ambiguous race days.

---

## Kimi Transition Notes

- Read `AGENTS.md` (repo root) at session start — it is the static orientation document
- Read `RULES.md` (repo root) when committed — it replaces `.cursor/rules/`
- Read `docs/wiki/index.md` for current deployed state
- The `.cursor/rules/` directory still exists — do not delete it, it works for any future Cursor sessions
- The wiki at `docs/wiki/` is current as of today's session

---

## Read Order for Next Session

1. `AGENTS.md`
2. `RULES.md`
3. `docs/wiki/index.md`
4. This handoff document
5. Task-specific vision docs if building a new feature
