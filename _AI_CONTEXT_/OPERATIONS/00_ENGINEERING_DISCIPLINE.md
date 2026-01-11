# Engineering Discipline: "Fix Fast, Build Careful"

**Status:** Active Operating Principle  
**Effective:** 2026-01-11  
**Scope:** All development on StrideIQ  

---

## The Rule

> **"Fix fast, build careful."**

Scale engineering rigor to match impact and risk. Most work is fast. Substantive changes get full treatment.

---

## Decision Tree

### Quick Pass (80% of work)

**Triggers:**
- Bug fixes
- Tweaks
- Small polish
- CSS/styling adjustments
- Copy changes
- Minor refactors (rename, extract, inline)
- Dependency updates
- Config changes

**Process:**
1. Fix it
2. Test locally
3. Commit
4. Move on

**No ceremony required.** Keep momentum.

---

### Full Rigor Mode (20% of work)

**Triggers:**
- New feature
- Major refactor
- UX flow changes
- New integration
- Attribution logic changes
- Plan generation changes
- New API endpoints
- Database schema changes
- Authentication/authorization changes
- Payment/billing logic
- Anything touching N=1 core (Athlete Intelligence Bank, correlations, insights)

**Process (The Checklist):**

| Step | Description | Artifact |
|------|-------------|----------|
| 1. **ADR** | Document the decision and why | `_AI_CONTEXT_/OPERATIONS/NN_*.md` |
| 2. **Audit Logging** | Log critical actions with before/after state | `services/plan_audit.py` pattern |
| 3. **Unit Tests** | Test new endpoints/logic | `tests/test_*.py` |
| 4. **Integration Tests** | Test frontend-backend flow | `tests/test_*.py` |
| 5. **Security Review** | Validate inputs, check IDOR, consider rate limits | In ADR |
| 6. **Feature Flag** | Enable gradual rollout if risky | `FeatureFlagService` |
| 7. **Rebuild + Verify** | Full rebuild, run tests, manual verification | `docker-compose up --build` |

---

## Why This Works

| Benefit | Explanation |
|---------|-------------|
| **Velocity preserved** | 80% of daily work stays fast and low-friction |
| **Quality where it matters** | New features get production-grade treatment |
| **No technical debt accumulation** | Tests + docs prevent "I'll fix it later" |
| **Manifesto protection** | ADRs ensure new features align with N=1 philosophy |
| **Acquisition-ready** | Professional practices visible in repo = credibility |

---

## Examples

### Quick Pass Examples

```
✓ Fix: Button color off by 1 shade
✓ Fix: Typo in error message
✓ Fix: Missing null check causing crash
✓ Tweak: Adjust padding on mobile
✓ Polish: Add loading spinner to button
```

### Full Rigor Examples

```
→ New: Full Workout Control (move/edit/add/delete workouts)
→ New: Coach Chat integration
→ Change: Plan generation algorithm
→ Change: Efficiency calculation formula
→ New: Stripe payment integration
→ Change: Age-grading methodology
→ New: Garmin sync integration
```

---

## Judgment Calls

When unsure, ask:

1. **Does this change user-facing behavior?** → Rigor
2. **Does this touch data integrity?** → Rigor
3. **Could this break existing functionality?** → Rigor
4. **Is this reversible without downtime?** → Maybe quick pass
5. **Would I be embarrassed if this broke in production?** → Rigor

---

## Non-Negotiables

Even in quick pass mode:

- ✅ Code must compile/build
- ✅ No regressions on existing tests
- ✅ No security vulnerabilities introduced
- ✅ Commit message describes what changed

---

## Enforcement

This document is the governing principle. When starting any task:

1. Categorize: Quick pass or full rigor?
2. If rigor → Start with ADR outline before coding
3. If quick → Just do it, test, commit

**No exceptions for "just this once" on rigor-level changes.**

---

*"The right amount of process is the minimum needed to ship quality at speed."*
