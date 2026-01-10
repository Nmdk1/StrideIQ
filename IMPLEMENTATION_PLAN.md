# Implementation Plan: Complete Health & Fitness Management System

## Core Principle: Waterfall Intake Approach

**Philosophy:** Following the manifesto's continuous feedback loop (Observe-Hypothesize-Intervene-Validate), we collect information gradually, not exhaustively in one sitting. The system evolves with the athlete.

**Waterfall Strategy:**
- **Initial:** Minimal info to start (email, basic goals, age/sex for age-grading)
- **Progressive:** Collect additional context as users engage with features
- **Contextual:** Ask for specific info when it becomes relevant (e.g., nutrition questions when they start tracking nutrition)
- **Continuous:** System learns and asks follow-up questions based on data patterns

---

## Phase 1: Foundation (Week 1-2)

### 1.1 User Authentication System

**Goal:** Enable personalized accounts and data collection

**Implementation:**
- Email/password authentication (simple, reliable)
- JWT tokens for session management
- Password hashing (bcrypt)
- Email verification (optional initially, required for paid tiers)
- Password reset flow

**Database:**
- Extend `Athlete` model with:
  - `email` (unique, required for auth)
  - `password_hash` (encrypted)
  - `email_verified` (boolean)
  - `onboarding_completed` (boolean, tracks waterfall progress)
  - `onboarding_stage` (string: 'initial', 'basic_profile', 'goals', 'nutrition_setup', 'work_setup', 'complete')
  - `height_cm` (numeric, nullable) - Required for BMI calculation

**API Endpoints:**
- `POST /auth/register` - Create account
- `POST /auth/login` - Authenticate
- `POST /auth/logout` - End session
- `POST /auth/refresh` - Refresh token
- `POST /auth/reset-password` - Request password reset
- `GET /auth/me` - Get current user

**Frontend:**
- Login/Register pages
- Protected route wrapper
- Auth context/provider
- Session management

---

### 1.2 Database Schema Expansion

**Goal:** Support all inputs for correlation analysis

#### New Tables:

**`intake_questionnaire`**
```sql
- id (UUID, PK)
- athlete_id (UUID, FK)
- stage (string: 'initial', 'basic_profile', 'goals', 'nutrition_setup', 'work_setup')
- responses (JSONB) - Flexible structure for stage-specific questions
- completed_at (timestamp)
- created_at (timestamp)
```

**`nutrition_entry`**
```sql
- id (UUID, PK)
- athlete_id (UUID, FK)
- date (date)
- entry_type (enum: 'pre_activity', 'during_activity', 'post_activity', 'daily')
- activity_id (UUID, FK, nullable) - Links to activity if pre/during/post
- calories (numeric, nullable)
- protein_g (numeric, nullable)
- carbs_g (numeric, nullable)
- fat_g (numeric, nullable)
- fiber_g (numeric, nullable)
- timing (time, nullable) - When consumed
- notes (text, nullable)
- created_at (timestamp)
```

**`work_pattern`**
```sql
- id (UUID, PK)
- athlete_id (UUID, FK)
- date (date)
- work_type (string) - 'desk', 'physical', 'shift', 'travel', etc.
- hours_worked (numeric)
- stress_level (integer, 1-5, nullable)
- notes (text, nullable)
- created_at (timestamp)
```

**`body_composition`**
```sql
- id (UUID, PK)
- athlete_id (UUID, FK)
- date (date)
- weight_kg (numeric, nullable)
- body_fat_pct (numeric, nullable)
- muscle_mass_kg (numeric, nullable)
- bmi (numeric, nullable) - Calculated automatically: weight_kg / (height_m)²
- measurements_json (JSONB, nullable) - Flexible for various measurements
- notes (text, nullable)
- created_at (timestamp)
```

**BMI Calculation Strategy (Hybrid Approach):**
- BMI calculated automatically in backend when weight is recorded
- Stored in `body_composition` table for trend analysis
- **Internal metric initially:** Not shown on dashboard until correlations are found
- **Reveal strategically:** Show BMI when meaningful correlations are identified
- **Full transparency later:** Once correlations established, show with context
- Formula: `BMI = weight_kg / (height_m)²` where `height_m = height_cm / 100`

**Indexes:**
- All tables: `(athlete_id, date)` for efficient time-series queries
- `intake_questionnaire`: `(athlete_id, stage)` for quick stage lookups

---

### 1.3 Waterfall Intake Questionnaire Design

**Goal:** Collect information progressively, not exhaustively

#### Stage 1: Initial (Required to Start)
**Trigger:** User registers account
**Questions:**
- Email (already have)
- Display name
- Birthdate (required - for age-grading)
- Sex (required - for age-grading)
- Height (cm or inches) - **Required** (no explanation, just like other metrics)
- Primary goal (dropdown: "Personal bests", "Run faster at lower HR", "Better body composition", "General fitness")
- Current activity level (1-5 scale)

**Completion:** User can immediately start using free calculators and connect Strava

#### Stage 2: Basic Profile (Progressive)
**Trigger:** User connects Strava OR tries to view their dashboard
**Questions:**
- Running experience (years)
- Typical weekly mileage
- Preferred race distances
- Injury history (yes/no, details optional)
- Current training approach (free text, optional)

**Completion:** Enables basic insights and activity analysis

#### Stage 3: Goals (Contextual)
**Trigger:** User views "Goals" section OR subscribes to a plan
**Questions:**
- Target race(s) and dates (if applicable)
- Performance goals (time targets, optional)
- Body composition goals (if selected as primary goal)
- Training policy preference (Performance Maximal, Durability First, Re-Entry)

**Completion:** Enables personalized plan generation

#### Stage 4: Nutrition Setup (Contextual)
**Trigger:** User clicks "Track Nutrition" OR system detects they want nutrition insights
**Questions:**
- Do you currently track nutrition? (yes/no)
- Typical meal timing
- Pre-activity fueling habits
- Post-activity recovery habits
- Dietary restrictions/preferences (optional)

**Completion:** Enables nutrition tracking and correlation analysis

#### Stage 5: Work Patterns (Contextual)
**Trigger:** User views "Work Patterns" section OR system asks about work stress
**Questions:**
- Work type (desk, physical, shift work, etc.)
- Typical work hours per week
- Work schedule consistency
- Work-related stress level (1-5)

**Completion:** Enables work-performance correlation analysis

**Implementation Notes:**
- Each stage can be completed independently
- Users can skip stages and return later
- System prompts for missing stages when relevant
- Progress saved incrementally (no "submit all" requirement)
- Visual progress indicator shows completion status

---

### 1.4 Basic Nutrition Tracking

**Goal:** Enable manual nutrition entry to start correlation analysis

**Features:**
- Daily nutrition log (calories, macros)
- Pre-activity nutrition (links to activity)
- Post-activity nutrition (links to activity)
- Simple entry form (not exhaustive)
- Optional: Quick entry templates

**UI:**
- Simple form with:
  - Date/time picker
  - Entry type selector (daily/pre/during/post)
  - Activity selector (if pre/during/post)
  - Basic macros (calories, protein, carbs, fat)
  - Optional notes
- List view of recent entries
- Basic visualization (daily totals, weekly averages)

**API:**
- `POST /v1/nutrition` - Create entry
- `GET /v1/nutrition` - List entries (with date range filter)
- `GET /v1/nutrition/{id}` - Get entry
- `PUT /v1/nutrition/{id}` - Update entry
- `DELETE /v1/nutrition/{id}` - Delete entry

**Correlation Foundation:**
- Store data now, build correlation engine later
- Data structure supports future analysis

---

## Phase 2: Enhanced Tracking (Week 3-4)

### 2.1 Work Pattern Tracking

**Implementation:** Similar to nutrition tracking
- Simple daily entry
- Work type, hours, stress level
- Optional notes

### 2.2 Body Composition Tracking

**Implementation:** 
- Periodic entries (not daily)
- Weight, body fat %, optional measurements
- Simple trend visualization

### 2.3 Enhanced Nutrition Tracking

**Add:**
- Meal timing
- Food logging (optional, can be simple text)
- Integration with MyFitnessPal API (future)

---

## Phase 3: Correlation Engine (Week 5-6)

### 3.1 Basic Correlation Analysis

**Start Simple:**
- Sleep → Performance efficiency (using existing HRV/resting HR data)
- Nutrition timing → Performance
- Work stress → Recovery

**Implementation:**
- Time-series analysis
- Correlation coefficients
- Visualizations showing relationships
- Simple insights: "Your best performances correlate with 7+ hours sleep"

### 3.2 Advanced Correlation Analysis

**Expand:**
- Multi-variable correlations
- Time-shifted correlations (manifesto principle)
- Personal response curves
- Inverse correlations

---

## Technical Implementation Order

1. **Database Migrations** (Alembic)
   - Create new tables
   - Add indexes
   - Add foreign keys

2. **Backend Schemas** (Pydantic)
   - Request/response models
   - Validation rules

3. **API Endpoints** (FastAPI)
   - CRUD operations
   - Authentication middleware
   - Authorization checks

4. **Frontend Components** (React/Next.js)
   - Forms for each intake stage
   - Tracking interfaces
   - Progress indicators

5. **Testing**
   - Unit tests for models/schemas
   - Integration tests for API
   - Component tests for UI

---

## Key Design Principles

1. **Waterfall, Not Waterfalling:** Information collected progressively, not all at once
2. **Contextual Prompts:** Ask for info when it becomes relevant
3. **Optional Depth:** Users can provide minimal or detailed info
4. **Progressive Enhancement:** Start simple, add complexity as users engage
5. **Data-Driven:** System learns what questions to ask based on user behavior
6. **No Friction:** Users can skip and return later

---

## Success Metrics

- **Onboarding Completion:** % of users completing each stage
- **Time to Value:** How quickly users see their first correlation insight
- **Engagement:** Daily active users for tracking features
- **Correlation Quality:** Accuracy of identified correlations
- **User Satisfaction:** Feedback on intake process (not overwhelming)

---

## Next Steps (Immediate)

1. Design database schema (this document)
2. Create Alembic migrations
3. Build authentication system
4. Implement Stage 1 intake (minimal)
5. Build basic nutrition tracking UI
6. Test end-to-end flow

---

**Note:** This plan aligns with the manifesto's continuous feedback loop. The system observes user behavior, hypothesizes what information would be valuable, intervenes by asking contextual questions, and validates by measuring engagement and correlation quality.

