# Frontend Architecture

## Design Principles

This frontend is built for **long-term scalability and maintainability**. Every component can be swapped, refactored, or overhauled without breaking other parts of the system.

### 1. **Abstraction Layers**

#### API Client (`lib/api/client.ts`)
- Abstracted HTTP client that can be swapped for different implementations
- Type-safe request/response handling
- Automatic retry logic and error handling
- Authentication token management
- **Swap:** Replace `apiClient` instance for testing, different backends, or API changes

#### Service Layer (`lib/api/services/`)
- Isolated service modules for each domain
- Type-safe API calls
- **Swap:** Each service can be refactored independently
- **Example:** `activitiesService` can be swapped for GraphQL, REST, or mock implementation

#### React Query Hooks (`lib/hooks/queries/`)
- Centralized query keys for easy invalidation
- Optimistic updates support
- Automatic caching and refetching
- **Swap:** Can switch to SWR, Apollo, or custom solution without breaking components

### 2. **Type Safety**

#### Shared Types (`lib/api/types.ts`)
- Mirrors backend Pydantic schemas
- Single source of truth for API contracts
- **Update:** When backend changes, update types here - TypeScript will catch all breaking changes

### 3. **Component Architecture**

#### Atomic Design Pattern
- **Atoms:** `components/ui/` - Basic building blocks (LoadingSpinner, ErrorMessage)
- **Molecules:** `components/activities/`, `components/availability/` - Composed components
- **Organisms:** Pages - Complete features
- **Templates:** Layout components

#### Component Isolation
- Each component is self-contained
- Props interfaces clearly defined
- Can be swapped for different implementations
- **Example:** `ActivityInsights` can be replaced with chart visualization without breaking page

### 4. **State Management**

#### Server State: React Query
- Automatic caching
- Background refetching
- Optimistic updates
- Request deduplication

#### Client State: React Hooks
- Local component state for UI
- Context for global app state (auth)
- **Swap:** Can add Redux/Zustand later without breaking existing code

### 5. **Error Handling**

#### Error Boundaries
- Catches React errors gracefully
- Can be swapped for different error handling strategies
- Per-page or global error boundaries

#### API Error Handling
- `ApiClientError` class for typed errors
- Consistent error display components
- **Swap:** Error handling strategy can be changed globally

### 6. **Authentication**

#### Auth Hook (`lib/hooks/useAuth.ts`)
- Isolated authentication logic
- Token management
- **Swap:** Can switch to OAuth, magic links, or different auth providers

## File Structure

```
apps/web/
├── lib/
│   ├── api/
│   │   ├── config.ts          # API configuration (swappable)
│   │   ├── client.ts          # HTTP client abstraction
│   │   ├── types.ts           # Shared TypeScript types
│   │   └── services/          # Service layer (isolated modules)
│   │       ├── activities.ts
│   │       ├── availability.ts
│   │       └── auth.ts
│   ├── hooks/
│   │   ├── useApiClient.ts    # API client context
│   │   ├── useAuth.ts         # Authentication hook
│   │   └── queries/           # React Query hooks
│   │       ├── activities.ts
│   │       └── availability.ts
│   └── providers/
│       └── QueryProvider.tsx  # React Query setup
├── components/
│   ├── ui/                    # Atomic components
│   │   ├── LoadingSpinner.tsx
│   │   └── ErrorMessage.tsx
│   ├── activities/            # Activity-related components
│   │   ├── ActivityInsights.tsx
│   │   └── PerceptionPrompt.tsx
│   ├── availability/          # Availability components
│   │   └── AvailabilityGrid.tsx
│   └── ErrorBoundary.tsx      # Error handling
└── app/
    ├── activities/[id]/       # Activity detail page
    │   └── page.tsx
    └── availability/           # Availability page
        └── page.tsx
```

## How to Swap/Refactor Components

### Example: Swap API Client

```typescript
// Create new implementation
class GraphQLApiClient implements ApiClientType {
  // ... implementation
}

// Swap in provider
<ApiClientProvider client={new GraphQLApiClient()}>
  {children}
</ApiClientProvider>
```

### Example: Swap Activity Insights Display

```typescript
// Create new component
function ActivityInsightsChart({ delivery }: ActivityInsightsProps) {
  // Chart visualization
}

// Replace in page
<ActivityInsightsChart delivery={delivery} />
```

### Example: Add New Service

```typescript
// lib/api/services/nutrition.ts
export const nutritionService = {
  async getEntries() { ... }
}

// lib/hooks/queries/nutrition.ts
export function useNutritionEntries() {
  return useQuery({ ... });
}

// Use in component
const { data } = useNutritionEntries();
```

## Testing Strategy

Each layer can be tested independently:
- **API Client:** Mock HTTP responses
- **Services:** Mock API client
- **Hooks:** Mock services
- **Components:** Mock hooks

## Future-Proofing

- **API Changes:** Update types, TypeScript catches breaking changes
- **UI Overhaul:** Swap components, keep hooks/services
- **State Management:** Add Redux/Zustand, keep React Query for server state
- **Authentication:** Swap auth hook, rest of app unchanged
- **Backend Swap:** Update API client, services adapt automatically

## Key Benefits

1. **Modular:** Each piece can be swapped independently
2. **Type-Safe:** TypeScript catches errors at compile time
3. **Testable:** Each layer can be tested in isolation
4. **Scalable:** Easy to add new features without breaking existing ones
5. **Maintainable:** Clear separation of concerns


