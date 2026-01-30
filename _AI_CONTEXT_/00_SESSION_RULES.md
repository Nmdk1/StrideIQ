# SESSION RULES - READ FIRST

**This file MUST be read before any other action in a new session.**

---

## Owner Profile

**Name:** Michael Shaffer  
**Technical Level:** Non-technical. The owner is a business person, not a developer.  
**Environment:** Windows 10, PowerShell, Cursor IDE  
**Production:** DigitalOcean droplet at `strideiq.run` (ssh root@strideiq.run)

---

## Communication Rules

### DO:
- Provide **exact commands** to copy/paste
- Explain what each command does in simple terms
- Wait for confirmation before proceeding to next step
- Show diffs before committing
- Wait for "commit approved" before committing
- Verify each step succeeded before moving on

### DO NOT:
- Assume the owner knows CLI, git, Docker, or programming
- Use jargon without explanation
- Chain multiple operations without confirmation
- Use PowerShell syntax that doesn't work (heredocs, && in older versions)
- Rush through steps
- Make changes without showing what will change first

---

## Deployment Workflow

The droplet pulls from GitHub. **Never use scp to copy files.**

### Standard deployment:

1. Make code changes locally
2. Check lints: `ReadLints`
3. Stage: `git add <files>`
4. Show diff: `git diff --staged`
5. **STOP and wait for "commit approved"**
6. Commit: `git commit -m "type(scope): description"`
7. Push: `git push origin phase8-s2-hardening`
8. Deploy on droplet:
   ```
   ssh root@strideiq.run
   cd /opt/strideiq/repo && git pull origin phase8-s2-hardening && docker compose -f docker-compose.prod.yml up -d --build
   ```
9. Wait for build (3-8 minutes)
10. Verify feature works

**Full documentation:** `_AI_CONTEXT_/OPERATIONS/DEPLOYMENT_WORKFLOW.md`

---

## Commit Messages

Format: `type(scope): description`

- `feat(scope):` - New feature
- `fix(scope):` - Bug fix
- `docs:` - Documentation only
- `refactor(scope):` - Code refactor

**PowerShell compatible only.** Use simple one-line messages:
```
git commit -m "feat(admin): add password reset button"
```

**Do NOT use heredocs or multi-line commit messages in PowerShell.**

---

## Language Rules (MANDATORY)

From `00_MANIFESTO.md`:

- NEVER use "we", "our", "I" (as AI), "together", "co-authored"
- ALWAYS use neutral/third-person: "The code implements...", "You added...", "Commit message: ..."
- AI agents are tools with ZERO ownership, authorship, or contribution credit
- All work product belongs solely to the owner

---

## Project Context

**Product:** StrideIQ - AI-powered running analytics platform  
**Tech Stack:** FastAPI (Python) backend, Next.js (TypeScript) frontend, PostgreSQL, Redis, Celery  
**Current Branch:** `phase8-s2-hardening`

### Key Documentation:
- `_AI_CONTEXT_/00_MANIFESTO.md` - Project philosophy and AI protocol
- `_AI_CONTEXT_/OPERATIONS/DEPLOYMENT_WORKFLOW.md` - Deployment process
- `docs/PHASED_WORK_PLAN.md` - Current roadmap
- `docs/AGENT_HANDOFF_*.md` - Previous session handoffs

---

## Before Starting Work

1. Read this file completely
2. Read `_AI_CONTEXT_/00_MANIFESTO.md` AI protocol section
3. Check `docs/` for recent handoff documents
4. Ask the owner what they want to work on
5. Confirm understanding before making changes

---

## Emergency Contacts

- **Owner email:** michael@strideiq.run
- **Support email:** support@strideiq.run
- **Production URL:** https://strideiq.run

---

## Common Mistakes to Avoid

| Mistake | Correct Approach |
|---------|------------------|
| Using scp to deploy | Use `git pull` on droplet |
| Using heredocs in PowerShell | Use simple one-line commit messages |
| Using `&&` in PowerShell | Run commands separately or use `;` |
| Committing without approval | Always wait for "commit approved" |
| Assuming technical knowledge | Provide exact copy/paste commands |
| Rushing through deployment | Verify each step before proceeding |
| Adding AI attribution | Never add co-author or attribution |
