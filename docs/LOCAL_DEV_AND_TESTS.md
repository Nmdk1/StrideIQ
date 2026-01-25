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

## Provider file imports (Phase 7) local dev (optional)
Phase 7 introduces a shared uploads mount for file imports:
- Host dir: `./.uploads/` (gitignored)
- Container path (API + worker): `/uploads`

To enable Garmin file import in local dev:
- `docker compose exec -T postgres psql -U postgres -d running_app -c "update feature_flag set enabled=true where key='integrations.garmin_file_import_v1';"`
- In the web app: Settings → Integrations → Garmin (file import) → Upload ZIP

## Stripe (Phase 6) local dev (optional)
Stripe is integrated via hosted Checkout + Portal, so local dev generally only needs the API env vars and the app will redirect you to Stripe-hosted pages.

- **Required (API)**:
  - `STRIPE_SECRET_KEY`
  - `STRIPE_PRICE_PRO_MONTHLY_ID`
- **Webhook testing (optional)**:
  - `STRIPE_WEBHOOK_SECRET`
  - Forward Stripe events to `http://localhost:8000/v1/billing/webhooks/stripe`

## Common troubleshooting
- **DB state looks odd**: restart services: `docker compose down -v` then `docker compose up -d --build`
- **Port conflicts**: stop any other local services on 5432/6379/8000/3000

