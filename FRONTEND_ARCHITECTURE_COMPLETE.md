# Frontend Architecture Complete

## Overview

Built a **production-ready, scalable frontend architecture** that can withstand full overhauls of any component without breaking other parts. This is not MVP code—this is enterprise-grade architecture designed to scale to the final product.

## Architecture Layers

### 1. API Client Layer (`lib/api/`)

**Purpose:** Abstracted HTTP client that can be swapped for any implementation

**Files:**
- `config.ts` - Centralized API configuration
- `client.ts` - Abstracted HTTP client with retry logic, error handling
- `types.ts` - Shared TypeScript types (mirror backend schemas)
- `services/` - Isolated service modules

**Key Features:**
- Type-safe requests/responses
- Automatic retry with exponential backoff
- Authentication token management
- **Swappable:** Can replace with GraphQL, gRPC, or mock implementations

### 2. Service Layer (`lib/api/services/`)

**Purpose:** Domain-specific API services that can be refactored independently

**Services:**
- `activities.ts` - Activity-related API calls
- `availability.ts` - Training availability API calls
- `auth.ts` - Authentication API calls

**Key Features:**
- Each service is isolated
- Type-safe function signatures
- **Swappable:** Each service can be swapped independently

### 3. React Query Hooks (`lib/hooks/queries/`)

**Purpose:** Type-safe, cached data fetching with automatic invalidation

**Hooks:**
- `activities.ts` - Activity data fetching hooks
- `availability.ts` - Availability data fetching hooks

**Key Features:**
- Centralized query keys for easy invalidation
- Optimistic updates support
- Automatic caching and background refetching
- **Swappable:** Can switch to SWR, Apollo, or custom solution

### 4. Component Architecture

**Atomic Design Pattern:**
- **Atoms:** `components/ui/` - Basic building blocks
  - `LoadingSpinner.tsx`
  - `ErrorMessage.tsx`
- **Molecules:** Domain-specific components
  - `components/activities/ActivityInsights.tsx`
  - `components/activities/PerceptionPrompt.tsx`
  - `components/availability/AvailabilityGrid.tsx`
- **Organisms:** Pages
  - `app/activities/[id]/page.tsx`
  - `app/availability/page.tsx`

**Key Features:**
- Each component is self-contained
- Clear prop interfaces
- **Swappable:** Components can be replaced without breaking pages

### 5. Error Handling

**Files:**
- `components/ErrorBoundary.tsx` - React error boundary
- `components/ui/ErrorMessage.tsx` - Consistent error display

**Key Features:**
- Graceful error handling
- Consistent error display
- **Swappable:** Error handling strategy can be changed globally

### 6. Authentication

**Files:**
- `lib/hooks/useAuth.ts` - Authentication hook
- `lib/api/services/auth.ts` - Auth service

**Key Features:**
- Token management
- LocalStorage persistence
- **Swappable:** Can switch to OAuth, magic links, or different providers

## Pages Built

### Activity Detail Page (`/activities/[id]`)
- Displays activity metrics
- Shows efficiency insights (if meaningful)
- Perception feedback collection
- Complete run delivery experience

### Training Availability Page (`/availability`)
- Interactive 7×3 grid
- Click to toggle: Unavailable → Available → Preferred
- Real-time summary statistics
- Bulk update support

## Dependencies Added

- `@tanstack/react-query` - Server state management
- `@tanstack/react-query-devtools` - Development tools

## Key Design Decisions

### 1. **Abstraction Over Implementation**
Every layer is abstracted so implementations can be swapped:
- API client can be replaced
- Services can be refactored independently
- Components can be swapped
- State management can be changed

### 2. **Type Safety First**
- Shared types mirror backend schemas
- TypeScript catches breaking changes
- Single source of truth for API contracts

### 3. **Modular Architecture**
- Each service is isolated
- Each component is self-contained
- Clear separation of concerns

### 4. **Future-Proof**
- Easy to add new features
- Easy to swap implementations
- Easy to refactor components
- Easy to scale

## How to Extend

### Add New Service
1. Create service in `lib/api/services/new-service.ts`
2. Create types in `lib/api/types.ts`
3. Create React Query hooks in `lib/hooks/queries/new-service.ts`
4. Use hooks in components

### Swap Implementation
1. Create new implementation
2. Replace in provider/context
3. Rest of app adapts automatically

### Refactor Component
1. Create new component
2. Replace in page
3. No other changes needed

## Testing Strategy

Each layer can be tested independently:
- **API Client:** Mock HTTP responses
- **Services:** Mock API client
- **Hooks:** Mock services
- **Components:** Mock hooks

## Production Readiness

✅ Type-safe API layer
✅ Error handling
✅ Loading states
✅ Authentication integration ready
✅ Modular component architecture
✅ Scalable state management
✅ Comprehensive documentation

## Next Steps

1. **Activity List Page** - Build with filtering/pagination
2. **Authentication Pages** - Login/register forms
3. **Dashboard** - Overview with efficiency trends
4. **Owners Dashboard** - Cross-athlete queries (backend ready)

**Status: Foundation complete. Ready to build features on top of this architecture.**


