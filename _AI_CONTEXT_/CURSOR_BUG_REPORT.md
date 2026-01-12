# Cursor IDE Bug Report: Serialization Overflow Crash

**Date:** 2026-01-11  
**Cursor Version:** (Check Help > About in Cursor)  
**OS:** Windows 10 (Build 10.0.26200)  
**Shell:** PowerShell  

---

## Summary

Agent mode crashes with `ConnectError: [internal] serialize binary: invalid int 32: 4294967295` during complex multi-step operations.

---

## Error Message

```
Request ID: f72e02a0-2e04-40a1-8c0a-bb11ffe07584
ConnectError: [internal] serialize binary: invalid int 32: 4294967295
    at aou.$endAiConnectTransportReportError (vscode-file://vscode-app/c:/Program%20Files/cursor/resources/app/out/vs/workbench/workbench.desktop.main.js:12706:475325)
    at JXe._doInvokeHandler (vscode-file://vscode-app/c:/Program%20Files/cursor/resources/app/out/vs/workbench/workbench.desktop.main.js:13633:23170)
    at JXe._invokeHandler (vscode-file://vscode-app/c:/Program%20Files/cursor/resources/app/out/vs/workbench/workbench.desktop.main.js:13633:22912)
    at JXe._receiveRequest (vscode-file://vscode-app/c:/Program%20Files/cursor/resources/app/out/vs/workbench/workbench.desktop.main.js:13633:21544)
    at JXe._receiveOneMessage (vscode-file://vscode-app/c:/Program%20Files/cursor/resources/app/out/vs/workbench/workbench.desktop.main.js:13633:20361)
    at mMt.value (vscode-file://vscode-app/c:/Program%20Files/cursor/resources/app/out/vs/workbench/workbench.desktop.main.js:13633:18388)
    at ke._deliver (vscode-file://vscode-app/c:/Program%20Files/cursor/resources/app/out/vs/workbench/workbench.desktop.main.js:49:2962)
    at ke.fire (vscode-file://vscode-app/c:/Program%20Files/cursor/resources/app/out/vs/workbench/workbench.desktop.main.js:49:3283)
    at Gyt.fire (vscode-file://vscode-app/c:/Program%20Files/cursor/resources/app/out/vs/workbench/workbench.desktop.main.js:12691:12156)
    at MessagePort.<anonymous> (vscode-file://vscode-app/c:/Program%20Files/cursor/resources/app/out/vs/workbench/workbench.desktop.main.js:15679:18406)
```

---

## Reproduction Steps

1. Open a large project in Cursor (monorepo with ~500+ files)
2. Start an Agent mode conversation
3. Request a complex multi-step task (e.g., "run full build check, fix all errors, verify migrations, commit changes")
4. Agent begins executing multiple tool calls:
   - Shell commands with large outputs (git status, docker logs, alembic history)
   - File reads/writes
   - Creating inline scripts with 50+ lines
5. **Crash occurs** mid-operation, typically after 3-5 sequential complex tool calls

---

## Analysis

### The Value `4294967295`

- `4294967295` = `2^32 - 1` = Maximum unsigned 32-bit integer
- Also equals `-1` when interpreted as signed 32-bit integer
- This suggests an **integer underflow or overflow** in the serialization layer

### Likely Cause

The error `serialize binary: invalid int 32` indicates:
1. A length or size field is being set to an invalid value
2. Possibly a buffer size calculation going negative and wrapping to max uint32
3. Could be triggered by cumulative message size exceeding expected limits

### Trigger Conditions

The crash occurred when the agent was:
- Creating large inline Python scripts (60+ lines)
- Processing `git diff --stat` output with many files
- Running `alembic history --verbose` with long output
- Executing multiple Docker commands in sequence

---

## Workaround

Breaking operations into smaller chunks prevents the crash:
- Write scripts to files instead of inline creation
- Limit individual tool call output size
- Avoid chaining many complex operations

---

## Environment Details

- **Project Size:** ~500 files, Next.js frontend + FastAPI backend + Docker
- **Conversation Length:** Extended session with prior context summary
- **Agent Model:** Claude (via Cursor Agent mode)

---

## Request IDs

Two crashes in same session:
1. `f72e02a0-2e04-40a1-8c0a-bb11ffe07584`
2. `f1b044f9-2541-41e5-abe2-022d8da75646`

---

## Suggested Fix Areas

Based on stack trace, investigate:
- `aou.$endAiConnectTransportReportError` - Error reporting/transport layer
- `JXe._receiveRequest` / `JXe._receiveOneMessage` - Message receiving handlers
- Binary serialization of int32 fields, especially size/length calculations

---

## Impact

- Agent conversation terminates unexpectedly
- User must restart and re-explain context
- Work in progress may be lost
- Reduces trust in Agent mode for complex tasks
