# Builder Note: Runtoon Infrastructure — MinIO Object Storage

**Date:** March 1, 2026
**Assigned to:** Infrastructure Builder (shell access to droplet)
**Priority:** HIGH — blocks Runtoon MVP launch
**Depends on:** Commit `652057a` (Runtoon MVP code — already merged to main)

---

## Objective

Set up MinIO as a self-hosted, S3-compatible object store on the existing Hostinger KVM 8 server. The Runtoon MVP code (`storage_service.py`) uses `boto3` with S3 API — MinIO is a drop-in backend. No code changes required.

After MinIO is running: deploy the app, run the migration, insert the feature flag, and smoke test.

---

## Why MinIO (not Cloudflare R2)

The founder does not have a Cloudflare account. MinIO runs as a Docker container on the existing server, requires no external vendor, and speaks the same S3 API that `storage_service.py` already targets. The config vars in `core/config.py` are named `R2_*` but they are generic S3-compatible settings — they work with MinIO unchanged.

At scale, migration to Cloudflare R2 or AWS S3 is a config-only change (swap 5 env vars). No code changes needed.

---

## Steps (execute in order on the droplet)

### 1. Add MinIO to `docker-compose.prod.yml`

Add this service block after `redis` and before `api`:

```yaml
  minio:
    image: minio/minio:latest
    container_name: strideiq_minio
    restart: unless-stopped
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-strideiq-minio-admin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
    expose:
      - "9000"   # S3 API
      - "9001"   # Admin console (internal only — not exposed via Caddy)
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

Add `minio_data` to the `volumes` section at the bottom:

```yaml
  minio_data:
    name: strideiq_minio_data
```

Add `minio` as a dependency for `api` and `worker` (in their `depends_on` blocks):

```yaml
      minio:
        condition: service_healthy
```

### 2. Generate MinIO credentials and add to `.env`

SSH to the droplet and generate a secure password:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add these lines to `/opt/strideiq/repo/.env`:

```
# MinIO Object Storage (S3-compatible — used by Runtoon via boto3)
MINIO_ROOT_USER=strideiq-minio-admin
MINIO_ROOT_PASSWORD=<paste the generated password>

# Runtoon storage config (reuses R2_* var names — S3-compatible)
R2_ACCESS_KEY_ID=strideiq-minio-admin
R2_SECRET_ACCESS_KEY=<same password as MINIO_ROOT_PASSWORD>
R2_BUCKET_NAME=strideiq-runtoon
R2_ENDPOINT_URL=http://minio:9000
R2_ACCOUNT_ID=local
```

**Note:** `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` are the MinIO root credentials. `R2_ENDPOINT_URL` uses the Docker network hostname `minio` on port `9000`. `R2_ACCOUNT_ID` is not used by MinIO but the config requires a value — `local` is fine.

### 3. Deploy (brings up MinIO + rebuilds API/worker with new env)

```bash
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
```

Wait for all containers to be healthy:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

All 7 containers should show `Up` + `(healthy)`:
- `strideiq_caddy`
- `strideiq_postgres`
- `strideiq_redis`
- `strideiq_minio` (new)
- `strideiq_api`
- `strideiq_worker`
- `strideiq_web`

### 4. Create the MinIO bucket

```bash
docker exec strideiq_minio mc alias set local http://localhost:9000 strideiq-minio-admin <MINIO_ROOT_PASSWORD>
docker exec strideiq_minio mc mb local/strideiq-runtoon
docker exec strideiq_minio mc anonymous set none local/strideiq-runtoon
```

That last command confirms the bucket is private (no public access). This should be the default, but we enforce it explicitly.

**Verify the bucket exists:**

```bash
docker exec strideiq_minio mc ls local/
```

Should show `strideiq-runtoon/`.

### 5. Verify migration ran

The API container runs `python run_migrations.py` on startup. Verify the Runtoon tables exist:

```bash
docker exec strideiq_postgres psql -U postgres -d running_app -c "\dt athlete_photo"
docker exec strideiq_postgres psql -U postgres -d running_app -c "\dt runtoon_image"
```

Both should show the table. Also verify the unique constraint:

```bash
docker exec strideiq_postgres psql -U postgres -d running_app -c "\d runtoon_image" | grep uq_runtoon
```

Should show `uq_runtoon_activity_attempt`.

### 6. Insert the feature flag (founder-only rollout)

Get the founder's athlete UUID first:

```bash
docker exec strideiq_postgres psql -U postgres -d running_app -c "SELECT id FROM athlete WHERE email='mbshaf@gmail.com';"
```

Then insert the flag:

```bash
docker exec strideiq_postgres psql -U postgres -d running_app -c "
INSERT INTO feature_flag (key, enabled, allowed_athlete_ids)
VALUES ('runtoon.enabled', true, '[\"<founder-uuid-from-above>\"]'::jsonb)
ON CONFLICT (key) DO UPDATE SET enabled = true, allowed_athlete_ids = '[\"<founder-uuid-from-above>\"]'::jsonb;
"
```

**Verify:**

```bash
docker exec strideiq_postgres psql -U postgres -d running_app -c "SELECT key, enabled, allowed_athlete_ids FROM feature_flag WHERE key='runtoon.enabled';"
```

### 7. Smoke test — verify storage_service can reach MinIO

```bash
docker exec strideiq_api python -c "
from services import storage_service
storage_service.upload_file('test/smoke.txt', b'runtoon smoke test', 'text/plain')
url = storage_service.generate_signed_url('test/smoke.txt', expires_in=60)
print(f'Signed URL: {url}')
storage_service.delete_file('test/smoke.txt')
print('Upload, sign, delete: all passed')
"
```

Expected output: `Upload, sign, delete: all passed`

### 8. Smoke test — verify API endpoints respond

Generate an auth token and hit the photo list endpoint:

```bash
TOKEN=$(docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
")

curl -s -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/runtoon/photos | python3 -m json.tool
```

Expected: `[]` (empty array — no photos uploaded yet). Not a 500 or 403.

### 9. Full health check

```bash
docker logs strideiq_api --tail=20
docker logs strideiq_worker --tail=20
docker logs strideiq_minio --tail=10
```

- API logs: no R2/storage errors
- Worker logs: no import errors for `runtoon_tasks`
- MinIO logs: healthy startup, no errors

---

## Hard Constraints

1. **MinIO console (port 9001) must NOT be exposed externally.** It is only on the Docker internal network. Do NOT add it to Caddy or expose it in `ports`. The only access is via `docker exec`.

2. **Bucket must be private.** Run `mc anonymous set none` after creation. Verify no public access.

3. **MINIO_ROOT_PASSWORD must be cryptographically secure.** Use `secrets.token_urlsafe(32)`. Never use a default or weak password.

4. **Do NOT modify any Python code.** This is infrastructure-only. The code at `652057a` is production-ready — it just needs the storage backend running.

---

## Acceptance Criteria

1. `docker ps` shows 7 healthy containers (caddy, postgres, redis, minio, api, worker, web)
2. MinIO bucket `strideiq-runtoon` exists and is private
3. `athlete_photo` and `runtoon_image` tables exist in PostgreSQL
4. `uq_runtoon_activity_attempt` constraint exists on `runtoon_image`
5. Feature flag `runtoon.enabled` is set with founder UUID
6. Storage smoke test passes (upload, sign, delete)
7. `GET /v1/runtoon/photos` returns `[]` (200, not 500/403)
8. No errors in API, worker, or MinIO logs

### Required Evidence

- `docker ps` output showing all 7 containers healthy
- `mc ls local/` output showing the bucket
- Storage smoke test output ("Upload, sign, delete: all passed")
- API response from `GET /v1/runtoon/photos`
- Last 10 lines of API and worker logs (no errors)

---

## Container Names (updated)

| Service | Container |
|---|---|
| API | strideiq_api |
| Web | strideiq_web |
| Worker | strideiq_worker |
| DB | strideiq_postgres |
| Cache | strideiq_redis |
| Proxy | strideiq_caddy |
| Storage | strideiq_minio (new) |

---

## Rollback

If anything goes wrong:
1. Remove the `minio` service from `docker-compose.prod.yml`
2. Remove `minio_data` from volumes
3. Remove `minio` from `depends_on` in api and worker
4. Remove the `MINIO_*` and `R2_*` lines from `.env`
5. Redeploy: `docker compose -f docker-compose.prod.yml up -d --build`

The Runtoon feature will silently degrade (no Runtoons generated, no errors surfaced to users) because `storage_service.py` raises on missing credentials and the Celery task catches all exceptions.
