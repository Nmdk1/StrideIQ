# Local Dev + Tests (5 minutes)

## Prereqs
- Docker Desktop (Compose v2)
- Node.js (for running web tests locally without Docker) — optional

## Start the stack
From repo root:

- Start services:
  - `docker compose up -d --build`
- API typically runs at: `http://localhost:8000`
- Web typically runs at: `http://localhost:3000`

## Run backend tests
Run inside the API container:
- `docker compose exec -T api python -m pytest -q`

Run a “golden path” subset (Phase 3 + Phase 5):
- `docker compose exec -T api python -m pytest -q tests/test_phase3_onboarding_golden_path_simulated.py tests/test_phase5_rate_limit_deferral.py tests/test_admin_actions_onboarding_ingestion_block.py`

## Run web tests
From `apps/web`:
- `npm ci`
- `npm test`

## Common troubleshooting
- **DB state looks odd**: restart services: `docker compose down -v` then `docker compose up -d --build`
- **Port conflicts**: stop any other local services on 5432/6379/8000/3000

