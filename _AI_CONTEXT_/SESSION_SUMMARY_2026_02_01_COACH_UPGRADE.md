# Session Summary: February 1, 2026 - Coach 90/10 Upgrade

## Completed Work

### 1. AI Coach 90/10 Model Split

Implemented comprehensive improvements to the AI coach to fix the "breaks after 1-2 follow-ups" issue.

**Changes to `apps/api/services/ai_coach.py`:**

| Sprint | Change | Impact |
|--------|--------|--------|
| 1 | Expand complexity classifier | Causal, ambiguity, decision queries → HIGH → Opus |
| 2 | Add tool validation | Logs when mini skips tool calls on data questions |
| 3 | Add data prefetch | Injects last 7 days of runs into mini's context |
| 4 | Simplify mini instructions | Shorter, clearer instructions for mini model |

**Cost Impact:**
- Before: $0.96/athlete/month (7.7% of revenue)
- After: $1.60/athlete/month (12.9% of revenue)
- Still sustainable with 87% gross margin on LLM

**Tests:** 124 coach-related tests passing, 1334 total tests passing

### 2. Production Deployment

- Merged to `main` branch
- Pushed to GitHub
- Deployed to DigitalOcean droplet (104.248.212.71)
- All containers healthy

### 3. Security Actions

- Password reset for owner account
- SECRET_KEY rotation to invalidate all sessions (unauthorized access remediation)
- All beta users logged out (required re-login)

### 4. COROS API Application

Submitted application for COROS API integration:
- Activity/Workout Data Sync
- Structured Workouts and Training Plans Sync
- Webhook endpoint: https://strideiq.run/v1/webhooks/coros
- Awaiting Client ID and API Keys

See `_AI_CONTEXT_/16_COROS_INTEGRATION.md` for full details.

## Files Modified

```
apps/api/services/ai_coach.py           # 90/10 classifier, tool validation, prefetch, simplified instructions
apps/api/tests/test_coach_model_tiering.py  # Updated tests for new classifier
apps/api/tests/test_coach_routing.py    # Updated tests for model parameter
_AI_CONTEXT_/01_PROJECT_STATUS.md       # Updated project status
_AI_CONTEXT_/16_COROS_INTEGRATION.md    # New: COROS integration tracking
```

## Git Commits

```
72037db feat(coach): implement 90/10 model split and mini scaffolding
```

## Production Server

- **IP:** 104.248.212.71
- **SSH:** `ssh root@104.248.212.71`
- **Repo:** `/opt/strideiq/repo`
- **Deploy:** `git pull origin main && docker compose -f docker-compose.prod.yml up -d --build`

## Next Steps

1. Test coach with real conversations to verify improvements
2. Wait for COROS API credentials
3. Send logo images to api@coros.com (4 sizes: 144px, 102px, 120px, 300px)
4. Monitor coach logs for tool validation failures
