# Cline + Kimi K2.6 Setup Guide for StrideIQ

**Written**: 2026-05-03  
**Purpose**: One-time setup notes for transitioning from Cursor (Claude Sonnet) to Cline + OpenRouter (Kimi K2.6) as the primary coding agent.

---

## What Carries Over Automatically

- `AGENTS.md` at repo root — Cline reads this if configured to read repo root docs at session start
- `RULES.md` at repo root — same (once committed)
- `docs/wiki/` — operational state, current as of 2026-05-03
- All commit history — Kimi can inspect with `git log`, `git show`, etc.

## What Does NOT Carry Over from Cursor

### `.cursor/rules/` files
These are Cursor-specific and will not be auto-applied by Cline. They are consolidated into `RULES.md`. Options for applying them in Cline:

**Option A (recommended)**: Configure Cline to prepend `RULES.md` to every session via the "Custom Instructions" or system prompt field in Cline settings. Point it at the file or paste the contents.

**Option B**: Add a `.clinerules` file at repo root that instructs Kimi to read `AGENTS.md` and `RULES.md` at session start. Cline supports `.clinerules` similarly to how Cursor supports `.cursor/rules/`.

### The most critical rules to enforce in Cline's system prompt
At minimum, embed these if you can only configure a short prepend:

1. Never `git add -A`. Stage only files relevant to the current task.
2. No `git push` without founder approval.
3. No new OAuth or API permission scopes without founder approval.
4. Update `docs/wiki/` in the same session as any behavioral code change.
5. CI is the source of truth. Check `gh run view` before debugging locally.

---

## Cline Configuration Recommendations

### Model
Kimi K2.6 via OpenRouter. Use the latest available Kimi model slug on OpenRouter at time of setup.

### Context window
Kimi K2.6 has a large context window. Set Cline's context limit high — the StrideIQ codebase has many interdependencies and the coach services in particular are dense. Truncating context mid-session causes the same class of errors as not reading the docs.

### Auto-approval
Do NOT enable auto-approval for git operations (commit, push, branch). Require approval. Rule 11 (no push without founder approval) is governance, not preference.

### File read at session start
Configure Cline's "always read" list to include:
- `AGENTS.md`
- `RULES.md`
- `docs/wiki/index.md`

If Cline supports a `.clinerules` file, create one at repo root:

```
At the start of every session, read the following files before taking any action:
1. AGENTS.md
2. RULES.md
3. docs/wiki/index.md

Do not propose features, write code, or make architectural suggestions until you have read all three.
```

---

## OpenRouter Notes

- Kimi K2.6 is available on OpenRouter as of 2026-05. Verify the exact model slug at openrouter.ai/models before configuring.
- Set a spending limit on the OpenRouter account to avoid surprise costs during long sessions.
- The production coach uses Kimi K2.5 via Moonshot API (not OpenRouter). The coding agent (Kimi K2.6 via OpenRouter) and the production coach LLM are separate — do not conflate them.

---

## What to Test After Setup

Run this in the repo root to confirm Kimi can navigate the codebase correctly:

1. Ask: "What does `suppress_thread_storage` do and where is it used?" — should reference `core.py` and the calendar router
2. Ask: "What are the 119 xfail tests for?" — should reference Phase 3B/3C/4 gates
3. Ask: "Where does the morning briefing get assembled?" — should reference `routers/home.py` and `docs/wiki/briefing-system.md`

If Kimi answers these correctly without reading extra files, the session-start docs are working.

---

## Production Access

```
Server: root@187.124.67.153
Repo:   /opt/strideiq/repo
Deploy: cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
Logs:   docker logs strideiq_api --tail=50
```

Full deploy and smoke-check commands are in `RULES.md` under the Production Deployment section.
