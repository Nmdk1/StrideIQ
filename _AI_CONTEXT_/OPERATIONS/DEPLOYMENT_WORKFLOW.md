# Deployment Workflow Guide

This document defines the standard workflow for debugging, committing, and deploying fixes to production.

## Owner Context

- **Owner:** Michael Shaffer (michael@strideiq.run)
- **Technical Level:** Non-technical. Provide explicit, step-by-step commands. Do not assume familiarity with CLI, git, or Docker.
- **Environment:** Windows 10, PowerShell, Cursor IDE
- **Production:** DigitalOcean droplet at `strideiq.run`

---

## Standard Development Workflow

### 1. Make Code Changes

When making changes:
- Read the file before editing
- Make the edit
- Check for linter errors with `ReadLints`
- Stage the changes with `git add`
- Show the diff with `git diff --staged`
- **STOP and wait for "commit approved"** before committing

### 2. Commit Process

After owner says "commit approved":

```bash
git commit -m "type(scope): description"
```

Commit message format:
- `feat(scope):` - New feature
- `fix(scope):` - Bug fix
- `docs:` - Documentation only
- `refactor(scope):` - Code refactor, no behavior change

**NEVER proceed to push without explicit approval.**

### 3. Push Process

After commit, push to remote:

```bash
git push origin phase8-s2-hardening
```

Show the push output to confirm success.

### 4. Deploy to Production

After push, provide the owner with explicit SSH command:

```
ssh root@strideiq.run
```

Then the deploy command (run on droplet):

```bash
cd /opt/strideiq/repo && git pull origin phase8-s2-hardening && docker compose -f docker-compose.prod.yml up -d --build
```

**Wait for build to complete.** The build takes 3-8 minutes. The owner will confirm completion.

### 5. Verify Deployment

After build completes, instruct owner to:
1. Check `docker ps` to verify containers are running
2. Test the specific feature that was fixed
3. Confirm functionality

---

## Debugging Production Issues

### Step 1: Gather Information

Ask the owner for:
- Screenshot of the issue
- URL where issue occurs
- Console errors (if visible)
- Steps to reproduce

### Step 2: Check Logs (if needed)

Provide explicit SSH commands:

```bash
ssh root@strideiq.run
docker logs strideiq_api --tail=50
docker logs strideiq_web --tail=50
docker logs strideiq_worker --tail=50
```

### Step 3: Diagnose

- Read relevant code files
- Identify the root cause
- Explain the issue clearly

### Step 4: Fix

- Make the fix
- Follow the standard commit/push/deploy workflow above

---

## Key Reminders

1. **Be explicit.** Owner is non-technical. Provide exact commands, not concepts.

2. **One step at a time.** Do not chain multiple operations without confirmation.

3. **Verify before proceeding.** Always confirm the previous step succeeded before moving to the next.

4. **No assumptions.** If unsure about something, ask.

5. **Test thoroughly.** Before staging, verify:
   - No linter errors
   - Logic is correct
   - All edge cases considered

6. **Document changes.** Show git diff before committing so owner can review.

---

## PowerShell Notes

- PowerShell does NOT support heredoc (`<<EOF`). Use simple one-line commit messages.
- Use `git commit -m "message"` format only.
- Commands with `&&` work in PowerShell 7+ but may fail in older versions. Chain with `;` if needed.

---

## Production Environment

| Service | Container Name | Purpose |
|---------|----------------|---------|
| API | strideiq_api | FastAPI backend |
| Web | strideiq_web | Next.js frontend |
| Worker | strideiq_worker | Celery background tasks |
| Database | strideiq_postgres | PostgreSQL |
| Cache | strideiq_redis | Redis |
| Proxy | strideiq_caddy | Reverse proxy + SSL |

---

## Emergency Rollback

If a deployment breaks production:

```bash
ssh root@strideiq.run
cd /opt/strideiq/repo
git log --oneline -5  # Find the last good commit
git checkout <commit-hash>
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Contact

For issues with this workflow, the owner (Michael Shaffer) has final authority on all decisions.
