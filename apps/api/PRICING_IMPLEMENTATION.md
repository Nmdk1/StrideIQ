# Pricing Implementation Guide

## Current Pricing Structure

### Tier 1: Free
- **Price**: $0
- **Features**: 
  - Training Pace Calculator
  - WMA Age-Grading Calculator
  - Heat-Adjusted Pace Calculator
  - Basic insights

### Tier 2: Fixed Plan
- **Price**: $9 (one-time)
- **Rationale**: Static plans are commoditized - low price for entry
- **Features**:
  - Everything in Free
  - Custom tailored training plan
  - 4-18 week duration
  - Plan delivered instantly
  - Static plan (no updates)

### Tier 3: Race-Specific Plan
- **Price**: $12 (one-time)
- **Rationale**: Slight premium for customization and intake questionnaire
- **Features**:
  - Everything in Fixed Plan
  - Intake questionnaire
  - Race date-specific plan
  - Optimized for your race
  - Available through race partnerships

### Tier 4: Guided Self-Coaching ⭐ PREMIUM
- **Price**: $24/month
- **Rationale**: This is our DIFFERENTIATED product - AI adaptation commands premium
- **Features**:
  - Everything in Race-Specific Plan
  - Adaptive plan updates based on progress
  - Efficiency trend analysis
  - Performance diagnostics
  - Strava integration
  - Continuous plan refinement

## Implementation Requirements

### Race-Specific Plan Flow

1. **Intake Questionnaire** (Required)
   - Current fitness level
   - Training history
   - Weekly volume capacity
   - Injury history/concerns
   - Time availability
   - Goal race time (optional)

2. **Race Information** (Required)
   - Race name
   - Race date
   - Race distance
   - Race type (road/trail/ultra)
   - Course profile (flat/hilly)

3. **Plan Generation**
   - Calculate weeks until race
   - Generate 4-18 week plan based on race date
   - Optimize for race distance and course
   - Include taper period

4. **Delivery**
   - Instant plan generation
   - PDF export option
   - Calendar integration (future)

### Database Schema Updates Needed

```sql
-- Add plan_type to track plan purchases
ALTER TABLE athlete ADD COLUMN plan_purchases JSONB DEFAULT '[]'::jsonb;

-- Create training_plan table
CREATE TABLE training_plan (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID REFERENCES athlete(id),
    plan_type TEXT NOT NULL, -- 'fixed', 'race_specific', 'guided'
    race_name TEXT,
    race_date DATE,
    race_distance_meters INTEGER,
    race_type TEXT, -- 'road', 'trail', 'ultra'
    course_profile TEXT, -- 'flat', 'rolling', 'hilly'
    start_date DATE,
    end_date DATE,
    weeks INTEGER,
    plan_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT DEFAULT 'active' -- 'active', 'completed', 'cancelled'
);

-- Create intake_questionnaire table
CREATE TABLE intake_questionnaire (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID REFERENCES athlete(id),
    plan_id UUID REFERENCES training_plan(id),
    current_fitness_level TEXT,
    training_history TEXT,
    weekly_volume_capacity INTEGER, -- hours per week
    injury_history TEXT,
    time_availability TEXT,
    goal_race_time INTEGER, -- seconds
    responses JSONB, -- Store full questionnaire responses
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### API Endpoints Needed

1. **POST /v1/plans/fixed**
   - Create fixed plan purchase
   - Generate plan
   - Return plan data

2. **POST /v1/plans/race-specific**
   - Accept intake questionnaire
   - Accept race information
   - Generate race-specific plan
   - Return plan data

3. **POST /v1/plans/guided/subscribe**
   - Create subscription
   - Generate initial plan
   - Set up recurring billing

4. **GET /v1/plans/{plan_id}**
   - Retrieve plan details

5. **GET /v1/plans/athlete/{athlete_id}**
   - Get all plans for athlete

6. **POST /v1/questionnaire**
   - Submit intake questionnaire
   - Link to plan

### Stripe Integration

- **Fixed Plan**: One-time payment $19
- **Race-Specific Plan**: One-time payment $24
- **Guided Self-Coaching**: Recurring monthly $15

### Race Partnership Flow

For selling through race partnerships:
1. Race provides unique link/code
2. Athletes use link to purchase Race-Specific Plan
3. System tracks which race the plan is for
4. Race gets commission/reporting (future)

## Next Steps

1. ✅ Update pricing display (Pricing.tsx)
2. ✅ Update Terms of Service
3. ⏳ Create intake questionnaire component
4. ⏳ Create race information form
5. ⏳ Update database schema
6. ⏳ Create API endpoints
7. ⏳ Integrate Stripe payments
8. ⏳ Build plan generation flow

