# EPOCH Process & Agent Handoff Guide

**Version:** 1.0  
**Date:** 2026-01-19  
**Author:** Opus 4.5 (Planner)  
**Purpose:** Comprehensive guide for StrideIQ development workflow and agent succession

---

## 1. EPOCH Protocol Overview

EPOCH is StrideIQ's development workflow. Every feature follows this sequence:

```
Judge (User) → Planner → Builder → Tester → Judge (Approval)
```

### Roles

| Role | Responsibility | Tools |
|------|---------------|-------|
| **Judge** | Approves/rejects, provides requirements | Human |
| **Planner** | Writes ADRs, creates handoffs, tracks progress | Read, Write, Grep |
| **Builder** | Implements per handoff spec | Read, Write, Edit, Shell |
| **Tester** | Verifies acceptance criteria | Shell, Read |

### Workflow

1. **Judge** provides requirement or approves ADR
2. **Planner** drafts ADR with:
   - Context and problem statement
   - Decision and implementation details
   - Acceptance criteria (testable)
   - Rollback plan
3. **Judge** approves ADR
4. **Planner** creates Builder Handoff (exact code, verification commands)
5. **Builder** implements and reports verification output
6. **Planner** creates Tester Handoff (exact test commands, expected output)
7. **Tester** executes tests and reports PASS/FAIL
8. **Planner** updates ADR status and commits
9. **Judge** confirms completion

---

## 2. Document Templates

### ADR Template

```markdown
# ADR-XXX: [Title]

**Status:** Draft | Approved | Complete (Verified YYYY-MM-DD)
**Date:** YYYY-MM-DD
**Author:** [Agent name] (Planner)
**Depends On:** [Dependencies]

---

## Context
[Current state and problem]

## Decision
[What we're doing and why]

## Implementation
[Files to modify, exact code]

## Acceptance Criteria
[Numbered, testable criteria]

## Rollback Plan
[How to revert if issues]

---

**Awaiting Judge approval.**
```

### Builder Handoff Template

```markdown
# Builder Handoff: ADR-XXX [Title]

**Date:** YYYY-MM-DD
**ADR:** ADR-XXX
**Status:** Ready for Implementation

---

## Objective
[One sentence]

## Files to Modify
[List with line numbers if applicable]

## Changes Required
[Exact code blocks]

## Verification Commands
[Runnable commands with expected output]

## Acceptance Criteria (Builder must verify)
[Checklist]

## Rollback
[How to revert]

---

**Ready for Builder implementation.**
```

### Tester Handoff Template

```markdown
# Tester Handoff: ADR-XXX [Title]

**Date:** YYYY-MM-DD
**ADR:** ADR-XXX
**Status:** Ready for Verification

---

## Objective
[What to verify]

## Acceptance Criteria
| AC | Description |
|----|-------------|
| AC1 | ... |

## Test Commands
[Exact commands for each AC]

## Expected Output
[What success looks like]

## CRITICAL: Domain Validation
[What to verify against real data]

## Report Format
[Template for results]

---

**Ready for Tester verification.**
```

---

## 3. Critical Rules

### For Planner

1. **Read actual code before writing ADR** — Never assume function signatures
2. **Verify return types** — Check what functions actually return
3. **Include exact code blocks** — Builder should copy-paste, not interpret
4. **Require domain validation** — Acceptance criteria must test against real data
5. **Commit after each phase** — Don't start Phase N+1 without committing Phase N

### For Builder

1. **Follow handoff exactly** — If unclear, ask Planner
2. **Run verification commands** — Report full output
3. **Handle edge cases** — Use try/except, handle None values
4. **Don't add unspecified features** — Only implement what's documented

### For Tester

1. **Never accept "no errors" as passing** — Verify output makes domain sense
2. **Cross-check against known data** — PBs, TSB values must match reality
3. **If numbers don't match reality → FAIL** — Investigate immediately
4. **Report full command output** — Not just PASS/FAIL

### Git Protocol

1. **Never update git config**
2. **Never force push**
3. **Never skip hooks**
4. **Commit message format:** `feat|fix|docs|refactor: [description]`
5. **Commit after each phase completes**

---

## 4. Security Requirements

1. **SECRET_KEY** — Required, minimum 32 characters
2. **Database backups** — Before any migration
3. **No secrets in code** — Use environment variables
4. **Validate all inputs** — Never trust external data

---

## 5. New Agent Onboarding

When starting a new session:

### Step 1: Read Context

```
Read the following files:
1. docs/EPOCH_PROCESS_AND_AGENT_HANDOFF.md (this file)
2. docs/AGENT_HANDOFF_2026-01-19_PLANNER.md (current state)
3. docs/SYSTEM_AUDIT_N1_INSIGHT_ENGINE.md (architecture overview)
4. Any pending ADRs in docs/adr/
```

### Step 2: Verify System State

```powershell
# Check containers
docker-compose ps

# Check git status
git status

# Check recent commits
git log --oneline -10
```

### Step 3: Identify Current Task

- Check roadmap in AGENT_HANDOFF document
- Identify which phase is pending/in-progress
- Read the relevant ADR

### Step 4: Follow EPOCH

- If continuing an ADR: read the handoff docs
- If starting new work: draft ADR and get Judge approval

---

## 6. Architecture Overview

### Key Services

| Service | Purpose | Location |
|---------|---------|----------|
| `ai_coach.py` | AI Coach with tool dispatch | apps/api/services/ |
| `coach_tools.py` | Bounded tools for AI Coach | apps/api/services/ |
| `correlation_engine.py` | Statistical correlations | apps/api/services/ |
| `training_load.py` | TSB/CTL/ATL calculation | apps/api/services/ |
| `insight_aggregator.py` | Prioritized insights | apps/api/services/ |
| `race_predictor.py` | Race time predictions | apps/api/services/ |
| `recovery_metrics.py` | Recovery analysis | apps/api/services/ |

### AI Coach Tools (11 total)

1. `get_recent_runs` — Recent activity data
2. `get_efficiency_trend` — Efficiency over time
3. `get_plan_week` — Current week's plan
4. `get_training_load` — TSB/CTL/ATL
5. `get_correlations` — Input-output correlations
6. `get_race_predictions` — Race time projections
7. `get_recovery_status` — Recovery metrics
8. `get_active_insights` — Prioritized insights
9. `get_pb_patterns` — PB training patterns
10. `get_efficiency_by_zone` — Zone-specific efficiency
11. `get_nutrition_correlations` — Activity-nutrition analysis

### Data Flow

```
Athlete Data → Models → Services → Coach Tools → AI Coach → User
```

---

## 7. Lessons Learned (N=1 Insight Engine)

### Phase 1 (ADR-045)

**Problem:** ADR pseudocode assumed dict return, but function returned list
**Fix:** Always verify actual function signatures before writing specs

### Phase 1 Testing

**Problem:** Tester accepted "0 correlations" as passing
**Fix:** Added domain validation requirement — numbers must match reality

### ADR-045-A

**Problem:** Original ADR only correlated against efficiency, missing PBs
**Fix:** Read original requirements before writing ADR

### Phase 3 (ADR-047)

**Problem:** Initially over-engineered with gpt-4o tier gating and rate limits
**Fix:** Simplified to 2-tier model (gpt-3.5-turbo/gpt-4o-mini)

### General

- PowerShell doesn't support heredoc or em-dashes in inline Python
- Always use single-line commit messages in PowerShell
- Test commands must be PowerShell-safe

---

## 8. Planner Instruction Template

Copy this for future Planner agents:

```
You are the Planner for StrideIQ, following the EPOCH workflow.

Your responsibilities:
1. Draft ADRs for Judge approval
2. Create Builder Handoff documents with exact code
3. Create Tester Handoff documents with exact commands
4. Track progress and update documentation
5. Commit after each phase completes

Rules:
- Read actual code before writing ADRs
- Verify function signatures and return types
- Require domain validation in acceptance criteria
- Follow EPOCH strictly: Planner → Builder → Tester → Judge
- Commit before starting next phase

Current context:
- Read docs/EPOCH_PROCESS_AND_AGENT_HANDOFF.md
- Read docs/AGENT_HANDOFF_2026-01-19_PLANNER.md
- Check git status for pending work
```

---

## 9. Quick Reference

### Start a new feature

```
1. Draft ADR (ADR-XXX-feature-name.md)
2. Get Judge approval
3. Create BUILDER_HANDOFF_ADR-XXX.md
4. Builder implements, reports verification
5. Create TESTER_HANDOFF_ADR-XXX.md
6. Tester verifies, reports PASS/FAIL
7. Update ADR status to Complete
8. Commit
```

### Commit after each phase

```powershell
git add [files]
git commit -m "feat: [description]"
git status  # verify clean
```

### Check system health

```powershell
docker-compose ps
docker-compose exec -T api python -c "from services.ai_coach import AICoach; print('OK')"
```

---

**This document should be read by every new agent starting work on StrideIQ.**
