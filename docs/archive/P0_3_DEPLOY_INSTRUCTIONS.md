# P0-3 Deployment Instructions

Run these commands to deploy b9f7ace to production.

## 1. SSH and deploy
```bash
ssh root@strideiq.run
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build api
```

**Required:** Production `.env` must have:
- `ENVIRONMENT=production`
- `DEBUG=false` (or unset)
- `CORS_ORIGINS=https://strideiq.run,https://www.strideiq.run` (or your production origins)
- `POSTGRES_PASSWORD` = strong password (min 12 chars, not postgres/password/admin/root/test)

If any of these are wrong, the API will **fail to start** with a clear error.

## 2. Verify deployment
```bash
docker compose -f docker-compose.prod.yml ps api
docker compose -f docker-compose.prod.yml logs --tail 120 api
```

## 3. Health check (from local machine)
```bash
curl -s "https://strideiq.run/health"
```
Expected: `{"status":"healthy",...}` with HTTP 200

## 4. Break-glass: simulate bad config (optional)
On droplet, temporarily set bad config to confirm startup fails:
```bash
# This will cause API to fail to start - container will exit
docker compose -f docker-compose.prod.yml run --rm -e ENVIRONMENT=production -e DEBUG=true -e CORS_ORIGINS=https://x.com -e POSTGRES_PASSWORD=secure123 api python -c "from core.config import settings; print('ok')"
```
Expected: exit non-zero with "DEBUG must be False" error.

Then restore normal deploy (step 1).

## 5. Rollback (if needed)
```bash
cd /opt/strideiq/repo
git revert b9f7ace --no-edit
docker compose -f docker-compose.prod.yml up -d --build api
```
