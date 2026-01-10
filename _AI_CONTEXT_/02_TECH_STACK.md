# TECHNICAL STACK & RULES

## Core Stack
* **Language:** Python 3.11
* **Framework:** FastAPI (with async support)
* **Database:** PostgreSQL 16 (TimescaleDB extension)
* **ORM:** SQLAlchemy 2.0 (with connection pooling, raw SQL for critical reads)
* **Migrations:** Alembic
* **Task Queue:** Celery + Redis
* **Containerization:** Docker Compose
* **External APIs:** Strava API v3 (with rate limiting and retry logic)
* **Configuration:** Pydantic Settings (centralized config management)
* **Logging:** Structured JSON logging (production-ready)

## Architecture Layers
* **`apps/api/core/`** - Core infrastructure (NEW)
  * `config.py` - Centralized configuration with validation
  * `database.py` - Connection pooling and session management
  * `logging.py` - Structured logging setup
  * `cache.py` - Redis caching layer (planned)
* **`apps/api/routers/`** - API endpoints (HTTP layer)
* **`apps/api/services/`** - Business logic (domain layer)
* **`apps/api/tasks/`** - Celery background tasks (planned)
* **`apps/api/models.py`** - SQLAlchemy ORM models
* **`apps/api/schemas.py`** - Pydantic validation schemas

## Key Services & Modules
* **`apps/api/services/strava_service.py`:** Strava API integration with retry logic and rate limiting
* **`apps/api/services/performance_engine.py`:** WMA age-grading calculator and race detection logic
* **`apps/api/routers/strava.py`:** Strava sync endpoint with raw SQL queries for reliable state reading
* **`apps/api/core/database.py`:** Production-ready connection pooling (20 connections, 10 overflow)

## Production-Ready Features
* **Connection Pooling:** QueuePool with 20 base connections, 10 overflow
* **Structured Logging:** JSON format in production, text in development
* **Health Checks:** Database connectivity verification
* **Request Logging:** Automatic request/response logging with timing
* **Error Handling:** Global exception handler with proper error responses
* **Configuration Management:** Environment-based config with validation

## Development Rules
1. **No Sloppy Code:** Do not suggest "dropping constraints" to fix bugs. Fix the root cause in the ingestion logic.
2. **Type Safety:** Use Pydantic models for all data validation.
3. **Context Awareness:** Always assume the user is running via `docker compose exec api ...`. Do not suggest running local Python commands.
4. **Rate Limiting:** Always implement retry logic with exponential backoff for external API calls. Use delays between requests to respect API limits.
5. **SQLAlchemy Best Practices:** For critical reads (like sync state), use raw SQL queries to bypass identity map cache when freshness is required.
6. **Architecture:** Use `core.*` modules for new code. Legacy `database` imports still work but are deprecated.
7. **Background Tasks:** Long-running operations (>1 second) must use Celery, not synchronous API handlers.
8. **Scalability:** Design for horizontal scaling - no state in API instances, use Redis for shared state.

## AI Usage Discipline
* **Composer 1 / Sonnet-Class:** Default for Phase 1–2 (Verification, Ingestion, Scripts, Debugging).
* **Opus / High-Reasoning Models:** Reserved for Phase 3+ (Architecture, Policy Engine, Physiological Math, Cross-System Design).