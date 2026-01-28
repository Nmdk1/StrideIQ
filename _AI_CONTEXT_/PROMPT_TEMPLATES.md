# AI Prompt Engineering Templates

> Reusable prompt patterns for Cursor AI (Claude) collaboration.
> These templates produce consistent, high-quality results with the StrideIQ codebase.

---

## Table of Contents

1. [Core Principles](#core-principles)
2. [Code Implementation Phase](#code-implementation-phase)
3. [Commit Workflow](#commit-workflow)
4. [Documentation Updates](#documentation-updates)
5. [Testing Workflow](#testing-workflow)
6. [Deploy Workflow](#deploy-workflow)
7. [Exploration & Analysis](#exploration--analysis)
8. [Error Recovery](#error-recovery)
9. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)

---

## Core Principles

### 1. Be Explicit, Not Implicit

```
❌ "Fix the coach"
✅ "Fix the routing logic in ai_coach.py so judgment questions bypass deterministic shortcuts"
```

### 2. Gate All Commits

```
❌ "Make the change and commit it"
✅ "Stage changes and show git diff --staged. Do NOT commit yet — wait for my 'commit approved' message."
```

### 3. Request Verification

```
❌ "Run the tests"
✅ "Run tests and show output. Then show git status."
```

### 4. One Task Per Prompt

```
❌ "Update the code, write tests, update docs, and deploy"
✅ Separate into 4 prompts with gates between each
```

### 5. Reference the Plan

```
❌ "Do the next thing"
✅ "Proceed to Phase 4: Code Architecture from COACH_ROBUSTNESS_PLAN.md"
```

---

## Code Implementation Phase

### Template: Start a New Phase

```markdown
Proceed to **Phase [N]: [Phase Name]** from [PLAN_DOC.md]:

- [Specific task 1]
- [Specific task 2]
- [Specific task 3]

Show:
- Code diffs for [files]
- New/updated test file(s) + output

Stage changes and show `git diff --staged` (full).

Do NOT commit yet — wait for my "commit approved" message.
```

### Example:

```markdown
Proceed to **Phase 4: Code Architecture** from COACH_ROBUSTNESS_PLAN.md:

- Split ai_coach.py into logical modules (routing.py, context.py)
- Extract detection methods to routing.py
- Add comprehensive tests for refactored structure

Show:
- Code diffs for new modules + updated imports
- New/updated test file(s) + output

Stage changes and show `git diff --staged` (full).

Do NOT commit yet — wait for my "commit approved" message.
```

---

## Commit Workflow

### Template: Approve and Commit

```markdown
Phase [N] [feature name] approved and staged.

Please commit all staged changes with this message:

git commit -m "[type](scope): [description]

- [bullet 1]
- [bullet 2]
- [bullet 3]"

Then show:
- git log -1 --pretty=fuller
- git status (should be clean)

After commit, [next action or "await further instructions"].
```

### Commit Types:

| Type | When to Use |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `refactor` | Code restructuring without behavior change |
| `docs` | Documentation only |
| `test` | Test additions or fixes |
| `chore` | Build, config, or maintenance |

### Example:

```markdown
Phase 5 conversation quality approved and staged.

Please commit all staged changes with this message:

git commit -m "feat(coach): Phase 5 conversation quality (beta-ready)

- Added conversation.py module with confidence gating
- Implemented question tracking to avoid repetition
- Added detail progression (FULL → MODERATE → BRIEF)
- 28 new tests (total 89 passing)"

Then show:
- git log -1 --pretty=fuller
- git status (should be clean)

After commit, update docs/COACH_ROBUSTNESS_PLAN.md to mark Phase 5 complete.
```

---

## Documentation Updates

### Template: Mark Phase Complete

```markdown
[Previous action] is complete and committed (commit [hash]).

Update [DOC_PATH]:
- Mark [Phase/Section] as **Complete**
- Append a brief "[Summary of what was done]" note with commit reference

Show the doc diff (no commit yet).

Awaiting "commit approved" for the doc update.
```

### Template: Commit Doc Update

```markdown
[Doc name] diff approved.

Please commit the staged doc change with this message:

git commit -m "docs: mark [Phase/Section] complete in [DOC_NAME]"

Then show:
- git log -1 --pretty=fuller
- git status (should be clean)
```

---

## Testing Workflow

### Template: Run Specific Tests

```markdown
Run tests for [feature/module]:

```bash
docker compose run --rm api python -m pytest [test_file(s)] -v --tb=short
```

Show full output.
```

### Template: Run All Coach Tests

```markdown
Run all coach-related tests to verify nothing broke:

```bash
docker compose run --rm api python -m pytest tests/test_coach_routing.py tests/test_coach_tools_phase3.py tests/test_coach_modules.py tests/test_conversation_quality.py -v --tb=short
```

Show summary (passed/failed count).
```

### Template: Fix Failing Tests

```markdown
[N] tests are failing. 

For each failure:
1. Show the test name and error
2. Identify the root cause
3. Fix the code (not the test, unless the test is wrong)
4. Re-run and confirm passing

Do NOT proceed until all tests pass.
```

---

## Deploy Workflow

### Template: Push to Remote

```markdown
Push all local commits to origin:

```bash
git push origin phase8-s2-hardening
```

Show:
- Push output
- Confirm success or report errors
```

### Template: Deploy to Production

```markdown
Deploy the current branch to production:

1. SSH to droplet: `ssh root@[IP]`
2. Pull latest: `cd /opt/strideiq/repo && git pull`
3. Rebuild: `docker compose -f docker-compose.prod.yml up -d --build`
4. Verify health: `curl -i https://strideiq.run/health`

Show output at each step. Stop if any step fails.
```

---

## Exploration & Analysis

### Template: Investigate a Bug

```markdown
The [feature] is [broken behavior].

1. Read the relevant code: [file paths]
2. Identify the root cause
3. Propose a fix (do NOT implement yet)
4. Estimate impact and risk

Show your analysis before proceeding.
```

### Template: Understand a System

```markdown
I need to understand how [system/feature] works.

1. Find the relevant files (use grep/glob)
2. Read the key functions/classes
3. Summarize the flow in plain English
4. Identify any issues or tech debt

Do NOT make any changes — this is exploration only.
```

### Template: Code Audit

```markdown
Audit [file/module] for:
- [ ] Code quality issues
- [ ] Missing error handling
- [ ] Performance concerns
- [ ] Security vulnerabilities
- [ ] Missing tests

Create a prioritized list of findings with severity (Critical/High/Medium/Low).
```

---

## Error Recovery

### Template: Undo Last Commit (Not Pushed)

```markdown
The last commit was incorrect. Undo it but keep the changes:

```bash
git reset --soft HEAD~1
```

Show git status after.
```

### Template: Discard Unstaged Changes

```markdown
Discard all unstaged changes (line-ending artifacts or unwanted edits):

```bash
git checkout -- [file1] [file2]
```

Show git status after (should be clean).
```

### Template: Recover from Failed Deploy

```markdown
The deploy failed. Recovery steps:

1. Check container logs: `docker compose logs api --tail=100`
2. Identify the error
3. If DB issue: check Alembic migrations
4. If code issue: identify bad commit and revert
5. Rebuild and restart

Show each step. Do NOT proceed blindly.
```

---

## Anti-Patterns to Avoid

### ❌ Vague Requests

```
"Make it better"
"Fix the issues"
"Clean up the code"
```

### ❌ Multiple Unrelated Tasks

```
"Update the coach, add tests, deploy to production, and update the docs"
```

### ❌ Skipping Verification

```
"Just commit it, I trust you"
```

### ❌ Ambiguous File References

```
"Update the main file"  → Which file?
"Fix the test"          → Which test?
```

### ❌ Assuming Context

```
"Continue from where we left off"  → Always re-state the task
```

---

## Session Management

### Starting a New Session

```markdown
I'm continuing work on [PROJECT]. 

Current state:
- Branch: [branch name]
- Last commit: [hash or description]
- Next task: [what needs to be done]

Read [relevant context files] and confirm you understand before proceeding.
```

### Ending a Session

```markdown
We're stopping here. Please:

1. Show git status
2. Show git log --oneline -5
3. List any uncommitted work
4. Summarize what's ready for next session
```

---

## Quick Reference: Prompt Modifiers

| Modifier | Effect |
|----------|--------|
| "Show:" | Request specific output/verification |
| "Do NOT commit yet" | Gate the commit for review |
| "Stage changes" | Prepare for review without committing |
| "Awaiting 'X approved'" | Explicit gate requiring user confirmation |
| "from [DOC.md]" | Reference the plan/spec |
| "One step at a time" | Force sequential execution |
| "(full)" | Request complete output, not truncated |

---

*Created: 2026-01-28*
*For use with: Cursor AI (Claude), StrideIQ codebase*
*Maintainer: Michael Shaffer*
