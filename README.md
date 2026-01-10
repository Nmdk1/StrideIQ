# Performance Focused Coaching System

A complete health and fitness management platform built with Next.js, FastAPI, PostgreSQL (TimescaleDB), Celery, and Redis. Comprehensive monitoring, correlation analysis, and outcomes-driven guidance.

## Product Overview

**Complete Health & Fitness Management**: A solution for high-level health and fitness management with outcomes such as personal bests (even at advanced ages), running faster at lower heart rates, and better body composition. We take a whole-person approach—monitoring nutrition, sleep, work patterns, and activities to understand how every input affects your performance. 

**Comprehensive Monitoring**: Tracks nutrition (pre, during, post activity + daily), sleep (hours slept, HRV, resting heart rate), work patterns (type and hours), and all activities via real-time API integration (Strava). 

**Correlation Analysis**: Identifies trends and both inverse and direct correlations between inputs (nutrition, sleep, work, training) and outputs (performance, heart rate efficiency, body composition). 

**Guided Self-Coaching**: AI-powered adaptive training plans that learn from your data and never sleep. Built for serious athletes who can't access elite guidance—whether you're in a rural area, treated as "fragile" because of your age, or simply want a system that continuously optimizes based on YOUR data.

### Free Tools (No Signup Required)

Three research-backed calculators available immediately:

1. **Training Pace Calculator** - Get your complete training pace table (E/M/T/I/R) based on recent race performance
2. **WMA Age-Grading Calculator** - See how you measure against world-class performance at any age
3. **Heat-Adjusted Pace Calculator** - Adjust training paces for heat and humidity conditions

All calculators use research-backed formulas and provide instant, shareable results.

### Pricing Tiers

- **Free** ($0) - All calculators + basic insights
- **Fixed Plan** ($9/plan) - One-time purchase, custom training plan, 4-18 week duration
- **Race-Specific Plan** ($12/plan) - Race-targeted plan with intake questionnaire
- **Guided Self-Coaching** ($24/month) - Premium adaptive coaching with continuous plan updates, efficiency analysis, and AI-powered adaptation

## Prerequisites

Before you begin, ensure you have the following installed on your system:

- **Docker** (version 20.10 or higher)
- **Docker Compose** (version 2.0 or higher)

You can verify your installation by running:
```bash
docker --version
docker-compose --version
```

## Project Structure

This is a monorepo containing:

- `apps/web` - Next.js frontend application (TypeScript)
- `apps/api` - FastAPI backend application
- `apps/worker` - Celery worker for background jobs
- `docker-compose.yml` - Orchestration file for all services

## Getting Started

### 1. Clone the repository

```bash
git clone <repository-url>
cd running-app
```

### 2. Set up environment variables

Create a `.env` file in the root directory with the following content (or copy from `.env.example` if it exists):

```env
# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=running_app
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Application Configuration
NODE_ENV=production
```

Edit `.env` if you need to customize any values (defaults should work for local development).

### 3. Start all services

Build and start all containers:

```bash
docker-compose up --build
```

This will:
- Build Docker images for web, api, and worker
- Start PostgreSQL with TimescaleDB extension
- Start Redis
- Start the FastAPI backend on port 8000
- Start the Celery worker
- Start the Next.js frontend on port 3000

### 4. Verify services are running

- **Frontend**: Open [http://localhost:3000](http://localhost:3000)
- **API Health Check**: Open [http://localhost:8000/health](http://localhost:8000/health)
- **PostgreSQL**: Available on `localhost:5432`
- **Redis**: Available on `localhost:6379`

**Note**: Database migrations run automatically when the API container starts. The initial migration creates the database schema and enables the TimescaleDB extension.

## Database Migrations

The project uses Alembic for database migrations. Migrations are automatically applied when the API container starts.

### Migration Commands

All migration commands should be run inside the API container:

#### Generate a new migration

```bash
# Enter the API container
docker-compose exec api bash

# Generate a new migration (after modifying models)
alembic revision --autogenerate -m "description of changes"

# Exit the container
exit
```

#### Apply migrations

Migrations are automatically applied on container startup. To manually apply migrations:

```bash
# Enter the API container
docker-compose exec api bash

# Apply all pending migrations
alembic upgrade head

# Exit the container
exit
```

#### Rollback migrations

```bash
# Enter the API container
docker-compose exec api bash

# Rollback one migration
alembic downgrade -1

# Rollback to a specific revision
alembic downgrade <revision_id>

# Rollback all migrations
alembic downgrade base

# Exit the container
exit
```

#### View migration history

```bash
# Enter the API container
docker-compose exec api bash

# Show current revision
alembic current

# Show migration history
alembic history

# Exit the container
exit
```

### Reset Database

To completely reset the database (this will delete all data):

```bash
# Stop and remove containers and volumes
docker-compose down -v

# Start fresh (migrations will run automatically)
docker-compose up --build
```

**Warning**: This will delete all data in PostgreSQL.

## Stopping Services

To stop all services:

```bash
docker-compose down
```

To stop services and remove volumes (this will delete all data):

```bash
docker-compose down -v
```

## Resetting Volumes

If you need to reset the database or Redis data:

```bash
# Stop and remove containers and volumes
docker-compose down -v

# Start fresh
docker-compose up --build
```

**Warning**: This will delete all data in PostgreSQL and Redis.

## Development

### Running services individually

You can also run services individually for development:

- **API**: `cd apps/api && uvicorn main:app --reload`
- **Web**: `cd apps/web && npm run dev`
- **Worker**: `cd apps/worker && celery -A main worker --loglevel=info`

Note: You'll need PostgreSQL and Redis running separately if running services individually.

## API Endpoints

### Public Tools (No Authentication Required)
- `POST /api/public/age-grade` - Calculate WMA age-grading percentage
- `POST /api/public/vdot/calculate` - Calculate fitness score from race time
- `POST /api/public/vdot/race-paces` - Get training paces and equivalent race times
- `POST /api/public/vdot/equivalents` - Calculate equivalent race times

### Athlete Management (`/v1`)
- `POST /v1/athletes` - Create a new athlete
- `GET /v1/athletes/{id}` - Get an athlete by ID

### Activities (`/v1`)
- `POST /v1/activities` - Create a new activity
- `GET /v1/activities/{activity_id}/analysis` - Get activity efficiency analysis
- `GET /v1/activities/{activity_id}/delivery` - Get complete run delivery (insights + perception prompts)

### Daily Checkins (`/v1`)
- `POST /v1/checkins` - Create a new daily checkin

### Body Composition (`/v1`)
- `POST /v1/body-composition` - Create body composition entry (BMI calculated automatically)
- `GET /v1/body-composition` - List body composition entries (with date filtering)
- `GET /v1/body-composition/{id}` - Get specific entry
- `PUT /v1/body-composition/{id}` - Update entry (BMI recalculated)
- `DELETE /v1/body-composition/{id}` - Delete entry

### Nutrition (`/v1`)
- `POST /v1/nutrition` - Create nutrition entry (pre/during/post activity or daily)
- `GET /v1/nutrition` - List nutrition entries (with date/type/activity filtering)
- `GET /v1/nutrition/{id}` - Get specific entry
- `PUT /v1/nutrition/{id}` - Update entry
- `DELETE /v1/nutrition/{id}` - Delete entry

### Work Patterns (`/v1`)
- `POST /v1/work-patterns` - Create work pattern entry (one per date)
- `GET /v1/work-patterns` - List work pattern entries (with date filtering)
- `GET /v1/work-patterns/{id}` - Get specific entry
- `PUT /v1/work-patterns/{id}` - Update entry
- `DELETE /v1/work-patterns/{id}` - Delete entry

### Activity Feedback (`/v1`)
- `POST /v1/activity-feedback` - Create perception feedback for activity
- `GET /v1/activity-feedback/activity/{activity_id}` - Get feedback for activity
- `GET /v1/activity-feedback/pending` - Get pending feedback prompts (last 24h)
- `PUT /v1/activity-feedback/{feedback_id}` - Update feedback
- `DELETE /v1/activity-feedback/{feedback_id}` - Delete feedback

### Training Availability (`/v1`)
- `GET /v1/training-availability/grid` - Get full availability grid (21 slots)
- `POST /v1/training-availability` - Create/update availability slot
- `PUT /v1/training-availability/{slot_id}` - Update slot
- `PUT /v1/training-availability/bulk` - Bulk update multiple slots
- `DELETE /v1/training-availability/{slot_id}` - Set slot to unavailable
- `GET /v1/training-availability/summary` - Get availability summary statistics

### Authentication (`/auth`)
- `POST /auth/register` - Register new athlete
- `POST /auth/login` - Login and get access token
- `GET /auth/me` - Get current user info
- `POST /auth/refresh` - Refresh access token

### Strava Integration (`/strava`)
- `GET /strava/auth` - Initiate Strava OAuth flow
- `GET /strava/callback` - Handle Strava OAuth callback
- `POST /strava/webhook` - Receive Strava webhook events

## Database Schema

The database includes the following main tables:

1. **athlete** - Stores athlete information
   - id (UUID, primary key)
   - created_at (timestamp)
   - email (text, unique, nullable)
   - display_name (text, nullable)
   - birthdate (date, nullable)
   - sex (text, nullable)
   - height_cm (numeric, nullable) - Required for BMI calculation
   - subscription_tier (text, default 'free')
   - strava_athlete_id, strava_access_token, strava_refresh_token

2. **activity** - Stores activity records
   - id (UUID, primary key)
   - athlete_id (UUID, foreign key, indexed)
   - start_time (timestamp, not null)
   - sport (text, default 'run')
   - source (text, default 'manual')
   - duration_s (integer, nullable)
   - distance_m (integer, nullable)
   - avg_hr (integer, nullable)
   - performance_percentage (age-graded performance)

3. **daily_checkin** - Stores daily check-in data
   - id (UUID, primary key)
   - athlete_id (UUID, foreign key, indexed)
   - date (date, not null)
   - sleep_h (numeric, nullable)
   - stress_1_5 (integer, nullable)
   - soreness_1_5 (integer, nullable)
   - rpe_1_10 (integer, nullable)
   - notes (text, nullable)
   - Unique constraint on (athlete_id, date)

4. **body_composition** - Stores body composition tracking
   - id (UUID, primary key)
   - athlete_id (UUID, foreign key, indexed)
   - date (date, not null)
   - weight_kg (numeric, not null)
   - body_fat_percent (numeric, nullable)
   - bmi (numeric, nullable) - Calculated automatically: weight_kg / (height_m)²
   - notes (text, nullable)
   - Unique constraint on (athlete_id, date)
   - **Note:** BMI is just a number. Meaning derived from performance correlations, not categories.

5. **intake_questionnaire** - Stores waterfall intake responses
   - id (UUID, primary key)
   - athlete_id (UUID, foreign key, indexed)
   - stage (text: 'initial', 'basic_profile', 'goals', 'nutrition_setup', 'work_setup')
   - responses (JSONB) - Flexible structure for stage-specific questions
   - completed_at (timestamp, nullable)
   - Unique constraint on (athlete_id, stage)

6. **nutrition_entry** - Stores nutrition tracking (pre/during/post activity + daily)
   - id (UUID, primary key)
   - athlete_id (UUID, foreign key, indexed)
   - date (date, not null)
   - entry_type (text: 'pre_activity', 'during_activity', 'post_activity', 'daily')
   - activity_id (UUID, foreign key, nullable)
   - calories, protein_g, carbs_g, fat_g, fiber_g (numeric, nullable)
   - timing (time, nullable)
   - notes (text, nullable)

7. **nutrition_entry** - Stores nutrition tracking (pre/during/post activity + daily)
   - id (UUID, primary key)
   - athlete_id (UUID, foreign key, indexed)
   - date (date, not null)
   - entry_type (text: 'pre_activity', 'during_activity', 'post_activity', 'daily')
   - activity_id (UUID, foreign key, nullable) - Links to activity if pre/during/post
   - calories, protein_g, carbs_g, fat_g, fiber_g (numeric, nullable)
   - timing (datetime, nullable) - When consumed
   - notes (text, nullable)
   - Index on (athlete_id, date)

8. **work_pattern** - Stores work pattern tracking
   - id (UUID, primary key)
   - athlete_id (UUID, foreign key, indexed)
   - date (date, not null)
   - work_type (text, nullable)
   - hours_worked (numeric, nullable)
   - stress_level (integer, 1-5, nullable)
   - notes (text, nullable)
   - Unique constraint on (athlete_id, date)

9. **activity_feedback** - Stores perceptual feedback for activities
   - id (UUID, primary key)
   - activity_id (UUID, foreign key, indexed)
   - athlete_id (UUID, foreign key, indexed)
   - perceived_effort (integer, 1-10, nullable) - RPE scale
   - leg_feel (text, nullable) - 'fresh', 'normal', 'tired', 'heavy', 'sore', 'injured'
   - mood_pre, mood_post (text, nullable)
   - energy_pre, energy_post (integer, 1-10, nullable)
   - notes (text, nullable)
   - Unique constraint on (activity_id)

10. **training_availability** - Stores training availability grid
    - id (UUID, primary key)
    - athlete_id (UUID, foreign key, indexed)
    - day_of_week (integer, 0-6) - 0=Sunday, 6=Saturday
    - time_block (text) - 'morning', 'afternoon', 'evening'
    - status (text) - 'available', 'preferred', 'unavailable'
    - notes (text, nullable)
    - Unique constraint on (athlete_id, day_of_week, time_block)

TimescaleDB extension is enabled but hypertables are not created yet.

## Services

- **Web** (port 3000): Next.js frontend with React, TypeScript, Tailwind CSS
- **API** (port 8000): FastAPI backend with `/health` endpoint
- **PostgreSQL** (port 5432): Database with TimescaleDB extension
- **Redis** (port 6379): Message broker for Celery
- **Worker**: Celery worker for background tasks (Strava sync, Garmin sync)

## Frontend Features

### Landing Page
- **Hero Section** - Value proposition with clear CTAs
- **Quick Value** - Above-the-fold stats (4 free calculators, $24/month pricing, 24/7 availability)
- **Free Tools** - All calculators prominently displayed
- **Pricing** - All tiers visible in comparison grid, premium highlighted
- **Sticky Navigation** - Always-visible nav with calculator quick link
- **Smooth Scrolling** - Hash navigation with proper offset for sticky nav

### Frontend Architecture (Version 2.0.0)
- **Scalable API Client** - Abstracted HTTP client (swappable implementations)
- **Service Layer** - Isolated domain services (activities, availability, auth)
- **React Query** - Server state management with caching and invalidation
- **Type Safety** - Shared TypeScript types mirroring backend schemas
- **Component Architecture** - Atomic design pattern (atoms, molecules, organisms)
- **Error Handling** - Error boundaries and consistent error display
- **Authentication** - Auth hooks and context ready for integration

### Activity Pages
- **Activity Detail** (`/activities/[id]`) - Complete run delivery experience
  - Activity metrics display
  - Efficiency insights (if meaningful)
  - Perception feedback collection
- **Training Availability** (`/availability`) - Interactive 7×3 grid
  - Click to toggle: Unavailable → Available → Preferred
  - Real-time summary statistics
  - Bulk update support

### UX Improvements (Latest)
- Sticky navigation bar with backdrop blur
- Smooth scroll behavior for anchor links
- Premium pricing tier highlighted with visual emphasis
- Responsive design optimized for mobile, tablet, and desktop
- All pricing tiers visible above the fold
- Trust indicators and value propositions throughout

## Testing

### Backend Tests
```bash
# Run all backend tests
cd apps/api
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_vdot_calculator.py
```

See `apps/api/README_TESTING.md` for detailed testing documentation.

### Frontend Tests
```bash
# Run all frontend tests
cd apps/web
npm test

# Run with coverage
npm run test:coverage

# Watch mode
npm run test:watch
```

See `TESTING_SETUP.md` for comprehensive testing setup guide.

### Run All Tests
```bash
# Windows
.\run_tests.ps1

# Linux/Mac
./run_tests.sh
```

## Version Control

This project uses Git for version control. Commits are made automatically at logical stopping points:
- After completing features or fixes
- When significant functionality is working
- Before major refactoring
- At natural stopping points

See `GIT_SETUP.md` for detailed Git workflow documentation.

## Recent Updates

### January 2026
- ✅ Fixed pricing section alignment - bottom premium box aligns perfectly with pricing grid
- ✅ Added smooth scroll navigation for hash links
- ✅ Improved sticky navigation with calculator quick link
- ✅ Enhanced hero section with scroll indicators
- ✅ Added QuickValue component for immediate value proposition
- ✅ Updated FreeTools section with trust indicators
- ✅ Comprehensive testing setup (backend and frontend)
- ✅ Git version control initialized with file deletion protection

## Troubleshooting

### Port conflicts

If ports 3000, 8000, 5432, or 6379 are already in use, you can modify the port mappings in `docker-compose.yml`.

### Container issues

To view logs for a specific service:
```bash
docker-compose logs <service-name>
```

To rebuild a specific service:
```bash
docker-compose build <service-name>
docker-compose up <service-name>
```

### Site not loadingIf the site is down:
1. Check Docker Desktop is running
2. Verify containers are up: `docker compose ps`
3. Check web logs: `docker compose logs web`
4. Rebuild if needed: `docker compose build web && docker compose up -d web`### Browser caching issuesIf changes aren't showing:
- Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
- Clear browser cache
- Try incognito/private browsing mode