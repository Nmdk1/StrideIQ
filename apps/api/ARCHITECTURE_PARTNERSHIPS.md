# Partnership Architecture (Future Phase)

## Overview

This document outlines the architecture needed for coach and running club partnerships, to be implemented **after Garmin integration**.

## Partnership Types

### 1. Race Directors & Timing Companies
**Status:** ✅ Active (already have partnerships)
**Implementation:** Current
- Race-specific plan offerings
- Banner placements
- Perk programs

### 2. Running Clubs
**Status:** ⏳ Future Phase (Post-Garmin)
**Features Needed:**
- Club-specific pricing/discounts
- Club dashboard for admins
- Member management
- Bulk plan purchases
- Club performance analytics (aggregate, anonymized)

### 3. Coaches
**Status:** ⏳ Future Phase (Post-Garmin)
**Features Needed:**
- Coach dashboard
- Athlete management
- Plan customization tools
- Communication tools
- Performance reporting for clients
- White-label options

## Database Schema (Future)

```sql
-- Partnership organizations
CREATE TABLE partnership_organization (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- 'race', 'running_club', 'coach', 'timing_company'
    contact_email TEXT,
    contact_name TEXT,
    partnership_tier TEXT, -- 'basic', 'premium', 'enterprise'
    discount_code TEXT UNIQUE,
    discount_percentage INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    active BOOLEAN DEFAULT TRUE
);

-- Coach accounts
CREATE TABLE coach (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID REFERENCES athlete(id), -- Coach is also an athlete
    organization_id UUID REFERENCES partnership_organization(id),
    certification TEXT,
    bio TEXT,
    max_athletes INTEGER DEFAULT 50,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    active BOOLEAN DEFAULT TRUE
);

-- Coach-athlete relationships
CREATE TABLE coach_athlete (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    coach_id UUID REFERENCES coach(id),
    athlete_id UUID REFERENCES athlete(id),
    relationship_type TEXT DEFAULT 'coaching', -- 'coaching', 'consulting'
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    UNIQUE(coach_id, athlete_id)
);

-- Running club memberships
CREATE TABLE club_membership (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES partnership_organization(id),
    athlete_id UUID REFERENCES athlete(id),
    role TEXT DEFAULT 'member', -- 'member', 'admin', 'coach'
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    left_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(organization_id, athlete_id)
);

-- Partnership-specific plan purchases
CREATE TABLE partnership_plan_purchase (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID REFERENCES athlete(id),
    organization_id UUID REFERENCES partnership_organization(id),
    plan_id UUID REFERENCES training_plan(id),
    discount_applied INTEGER DEFAULT 0,
    purchase_price DECIMAL(10,2),
    purchased_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## API Endpoints (Future)

### Running Clubs
- `POST /v1/partnerships/clubs` - Create club partnership
- `GET /v1/partnerships/clubs/{club_id}/members` - Get club members
- `POST /v1/partnerships/clubs/{club_id}/invite` - Invite members
- `GET /v1/partnerships/clubs/{club_id}/analytics` - Club analytics (aggregate)

### Coaches
- `POST /v1/partnerships/coaches` - Register as coach
- `GET /v1/coaches/{coach_id}/athletes` - Get coach's athletes
- `POST /v1/coaches/{coach_id}/athletes/{athlete_id}` - Add athlete
- `GET /v1/coaches/{coach_id}/dashboard` - Coach dashboard data
- `POST /v1/coaches/{coach_id}/plans` - Create custom plan for athlete

### Race Directors
- `POST /v1/partnerships/races` - Create race partnership
- `GET /v1/partnerships/races/{race_id}/plans` - Get race-specific plans
- `GET /v1/partnerships/races/{race_id}/analytics` - Race participant analytics

## Feature Flags

```python
# Feature flags for gradual rollout
PARTNERSHIP_FEATURES = {
    "running_clubs": False,  # Enable after Garmin
    "coaches": False,  # Enable after Garmin + running clubs
    "race_partnerships": True,  # Already active
}
```

## Implementation Priority

1. ✅ **Race Partnerships** - Current (already working)
2. ⏳ **Running Clubs** - Post-Garmin
   - Club management
   - Member discounts
   - Bulk purchases
3. ⏳ **Coaches** - Post-Garmin + Running Clubs
   - Coach dashboard
   - Athlete management
   - Custom plan tools

## Notes

- Architecture is designed but not implemented
- Database schema ready for future migration
- API endpoints documented but not built
- Feature flags allow gradual rollout
- Race partnerships are already functional (current implementation)

