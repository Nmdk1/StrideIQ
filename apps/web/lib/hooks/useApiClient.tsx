/**
 * API Client Hook
 * 
 * Provides access to the API client with authentication.
 * Can be swapped for different implementations (mocking, different backends, etc.)
 */

import React, { useContext, createContext, type ReactNode } from 'react';
import { apiClient, type ApiClientType } from '../api/client';

const ApiClientContext = createContext<ApiClientType>(apiClient);

interface ApiClientProviderProps {
  children: ReactNode;
  client?: ApiClientType;
}

export function ApiClientProvider({ 
  children, 
  client = apiClient 
}: ApiClientProviderProps) {
  return (
    <ApiClientContext.Provider value={client}>
      {children}
    </ApiClientContext.Provider>
  );
}

export function useApiClient(): ApiClientType {
  return useContext(ApiClientContext);
}

