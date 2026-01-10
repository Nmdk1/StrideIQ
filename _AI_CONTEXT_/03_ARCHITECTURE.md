# ARCHITECTURE & SCALABILITY PLAN

**Last Updated:** Jan 4, 2026  
**Status:** Production-Ready Architecture Design

## Core Principles

1. **Separation of Concerns**: API handles requests, Workers handle long-running tasks
2. **Horizontal Scalability**: All components must scale independently
3. **Fault Tolerance**: System must degrade gracefully, not fail catastrophically
4. **Observability**: Every operation must be traceable and monitorable
5. **Performance**: Sub-100ms API responses, async where possible

## Current Architecture Assessment

### ✅ What's Good
- Docker Compose setup with health checks
- TimescaleDB for time-series data
- Celery + Redis for background tasks
- FastAPI for async-capable API framework
- Alembic for migrations

### ⚠️ Critical Issues to Fix

#### 1. Database Connection Pooling
**Problem:** Default SQLAlchemy engine has no pool configuration  
**Impact:** Will exhaust connections under load, causing 500 errors  
**Fix:** Configure connection pool with appropriate limits

#### 2. Synchronous Blocking Operations
**Problem:** Strava sync runs synchronously in API request handler  
**Impact:** Blocks entire FastAPI server during sync (minutes)  
**Fix:** Move to Celery background tasks

#### 3. No Caching Layer
**Problem:** Every request hits database  
**Impact:** Unnecessary DB load, slower responses  
**Fix:** Redis caching for frequently accessed data

#### 4. No Rate Limiting
**Problem:** API endpoints have no rate limits  
**Impact:** Vulnerable to abuse, resource exhaustion  
**Fix:** Implement rate limiting middleware

#### 5. No Structured Logging
**Problem:** Print statements scattered throughout code  
**Impact:** Cannot debug production issues, no observability  
**Fix:** Structured logging with correlation IDs

#### 6. No Error Tracking
**Problem:** Errors silently fail or print to console  
**Impact:** Cannot detect issues in production  
**Fix:** Error tracking service (Sentry or similar)

#### 7. No Health Checks
**Problem:** Basic health check doesn't verify dependencies  
**Impact:** Cannot detect degraded state  
**Fix:** Comprehensive health checks (DB, Redis, external APIs)

#### 8. No Configuration Management
**Problem:** Environment variables scattered  
**Impact:** Hard to manage, easy to misconfigure  
**Fix:** Centralized configuration with validation

## Production-Ready Architecture

### Layer 1: Request Handling (FastAPI)
- **Purpose:** Handle HTTP requests, validate input, return responses
- **Responsibilities:**
  - Request validation (Pydantic schemas)
  - Authentication/Authorization
  - Rate limiting
  - Request logging
  - Enqueue background tasks
- **Must NOT:**
  - Perform long-running operations (>1 second)
  - Make external API calls synchronously
  - Hold database connections open

### Layer 2: Background Processing (Celery)
- **Purpose:** Handle long-running tasks asynchronously
- **Responsibilities:**
  - Strava sync operations
  - Data aggregation/calculation
  - External API calls
  - Scheduled tasks (cron-like)
- **Configuration:**
  - Task retries with exponential backoff
  - Task prioritization
  - Dead letter queue for failed tasks

### Layer 3: Data Layer (PostgreSQL + TimescaleDB)
- **Purpose:** Persistent storage
- **Optimizations:**
  - Connection pooling (20-50 connections per instance)
  - Read replicas for analytics queries
  - Proper indexes on foreign keys and query patterns
  - Partitioning for time-series data (TimescaleDB hypertables)

### Layer 4: Caching Layer (Redis)
- **Purpose:** Reduce database load, improve response times
- **Use Cases:**
  - Frequently accessed athlete data
  - Age-grading calculations (cacheable)
  - Rate limiting counters
  - Session storage (future)

### Layer 5: External Integrations
- **Purpose:** Integrate with third-party APIs
- **Pattern:**
  - All external calls go through service layer
  - Retry logic with exponential backoff
  - Circuit breaker pattern for failing services
  - Rate limit tracking per provider

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. ✅ Database connection pooling configuration
2. ✅ Move Strava sync to Celery tasks
3. ✅ Structured logging setup
4. ✅ Centralized configuration management
5. ✅ Health check improvements

### Phase 2: Performance (Week 2)
1. ✅ Redis caching layer
2. ✅ Database query optimization (indexes)
3. ✅ API response caching
4. ✅ Background task monitoring

### Phase 3: Reliability (Week 3)
1. ✅ Rate limiting middleware
2. ✅ Error tracking (Sentry)
3. ✅ Circuit breakers for external APIs
4. ✅ Comprehensive health checks
5. ✅ Database connection retry logic

### Phase 4: Observability (Week 4)
1. ✅ Metrics collection (Prometheus)
2. ✅ Distributed tracing
3. ✅ Log aggregation
4. ✅ Performance monitoring

## Scalability Targets

### Current Capacity (Single Instance)
- **API:** ~100 req/s
- **Database:** ~50 concurrent connections
- **Worker:** ~10 concurrent tasks

### Target Capacity (Production)
- **API:** 1000+ req/s (horizontal scaling)
- **Database:** 200+ concurrent connections (read replicas)
- **Worker:** 50+ concurrent tasks (multiple workers)

### Scaling Strategy
1. **Horizontal:** Add more API/Worker instances behind load balancer
2. **Vertical:** Increase database resources (CPU, RAM, connections)
3. **Caching:** Aggressive caching to reduce DB load
4. **Read Replicas:** Separate read/write traffic

## Code Organization

### Directory Structure
```
apps/api/
├── core/              # Core infrastructure
│   ├── config.py      # Configuration management
│   ├── logging.py     # Logging setup
│   ├── database.py    # DB connection pooling
│   └── cache.py       # Redis caching
├── routers/           # API endpoints
├── services/          # Business logic
├── tasks/             # Celery tasks
├── models/            # SQLAlchemy models
├── schemas/           # Pydantic schemas
└── utils/             # Shared utilities
```

### Service Layer Pattern
- **Services:** Pure business logic, no HTTP/DB concerns
- **Routers:** HTTP handling, call services
- **Tasks:** Background processing, call services
- **Models:** Database schema only

## Monitoring & Alerting

### Key Metrics
- API response times (p50, p95, p99)
- Database query times
- Background task duration
- Error rates by endpoint
- External API success rates
- Cache hit rates

### Alerts
- API error rate > 1%
- Database connection pool exhaustion
- Background task failures > 5%
- External API failures
- Response time degradation

## Security Considerations

1. **Authentication:** OAuth 2.0 (not implemented yet)
2. **Rate Limiting:** Per-user and per-IP limits
3. **Input Validation:** All inputs validated via Pydantic
4. **SQL Injection:** SQLAlchemy ORM prevents (raw SQL must be parameterized)
5. **Secrets Management:** Environment variables (move to secret manager in production)

## Future Considerations

1. **Message Queue:** Consider RabbitMQ for complex workflows
2. **Event Sourcing:** For audit trail and replay capability
3. **GraphQL:** For flexible frontend queries
4. **CDN:** For static assets and API responses
5. **Multi-Region:** For global scale


