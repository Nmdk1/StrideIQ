/**
 * React Query Provider
 * 
 * Wraps the app with React Query for server state management.
 * Can be swapped for different query libraries or implementations.
 */

'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useState, useEffect } from 'react';

// Shared QueryClient instance for access outside React tree (e.g., logout)
let sharedQueryClient: QueryClient | null = null;

export function getQueryClient(): QueryClient | null {
  return sharedQueryClient;
}

/**
 * Clear all cached query data (call on logout)
 */
export function clearQueryCache(): void {
  if (sharedQueryClient) {
    sharedQueryClient.clear();
  }
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            refetchOnWindowFocus: false,
            retry: 1,
          },
          mutations: {
            retry: 1,
          },
        },
      })
  );
  
  // Store reference to shared client
  useEffect(() => {
    sharedQueryClient = queryClient;
    return () => {
      sharedQueryClient = null;
    };
  }, [queryClient]);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === 'development' && <ReactQueryDevtools />}
    </QueryClientProvider>
  );
}


