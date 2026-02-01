/**
 * API Client
 * 
 * Abstracted API client that can be swapped for different implementations
 * (fetch, axios, etc.) without breaking the rest of the application.
 * 
 * Features:
 * - Type-safe requests/responses
 * - Automatic error handling
 * - Request/response interceptors
 * - Retry logic
 * - Authentication token management
 */

import { API_CONFIG } from './config';
import type { ApiError } from './types';

export class ApiClientError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: ApiError
  ) {
    super(message);
    this.name = 'ApiClientError';
  }
}

export interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
  retries?: number;
  timeoutMs?: number;
}

class ApiClient {
  private baseURL: string;
  private authToken: string | null = null;
  private tokenInitialized: boolean = false;

  constructor(baseURL: string = API_CONFIG.baseURL) {
    this.baseURL = baseURL;
    // Initialize token from localStorage immediately on construction
    this.initializeToken();
  }

  /**
   * Initialize auth token from localStorage.
   * Called on construction and can be called again if needed.
   */
  private initializeToken() {
    if (typeof window !== 'undefined' && !this.tokenInitialized) {
      const storedToken = localStorage.getItem('auth_token');
      if (storedToken) {
        this.authToken = storedToken;
      }
      this.tokenInitialized = true;
    }
  }

  setAuthToken(token: string | null) {
    this.authToken = token;
    this.tokenInitialized = true;
  }

  // Get token - check localStorage as fallback
  private getAuthToken(): string | null {
    // Ensure initialization happened (handles SSR -> client hydration)
    if (!this.tokenInitialized) {
      this.initializeToken();
    }
    
    if (this.authToken) return this.authToken;
    
    // Final fallback - check localStorage directly
    if (typeof window !== 'undefined') {
      const storedToken = localStorage.getItem('auth_token');
      if (storedToken) {
        this.authToken = storedToken;
        return storedToken;
      }
    }
    return null;
  }

  private async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const {
      skipAuth = false,
      retries = API_CONFIG.retries,
      timeoutMs = API_CONFIG.timeout,
      ...fetchOptions
    } = options;

    const url = `${this.baseURL}${endpoint}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(fetchOptions.headers as Record<string, string>),
    };

    const token = this.getAuthToken();
    if (!skipAuth && token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        // Timeout + cancellation support
        const controller = new AbortController();
        const originalSignal = fetchOptions.signal;
        if (originalSignal) {
          if (originalSignal.aborted) {
            controller.abort();
          } else {
            originalSignal.addEventListener('abort', () => controller.abort(), { once: true });
          }
        }
        const timeoutHandle =
          timeoutMs && timeoutMs > 0
            ? setTimeout(() => controller.abort(), timeoutMs)
            : null;

        const response = await fetch(url, {
          ...fetchOptions,
          headers,
          signal: controller.signal,
        });
        if (timeoutHandle) clearTimeout(timeoutHandle);

        if (!response.ok) {
          let errorData: ApiError | undefined;
          try {
            errorData = await response.json();
          } catch {
            // Response is not JSON
          }

          throw new ApiClientError(
            errorData?.detail || `HTTP ${response.status}: ${response.statusText}`,
            response.status,
            errorData
          );
        }

        // Handle empty responses
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          return await response.json();
        }

        // For 204 No Content or other non-JSON responses
        return undefined as T;
      } catch (error) {
        lastError = error as Error;

        // Abort should never retry
        if ((error as any)?.name === 'AbortError') {
          throw new Error('Request cancelled or timed out');
        }

        // Don't retry on client errors (4xx)
        if (error instanceof ApiClientError && error.status >= 400 && error.status < 500) {
          throw error;
        }

        // Retry with exponential backoff
        if (attempt < retries) {
          const delay = API_CONFIG.retryDelay * Math.pow(2, attempt);
          await new Promise(resolve => setTimeout(resolve, delay));
          continue;
        }
      }
    }

    throw lastError || new Error('Request failed');
  }

  async get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  async post<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'DELETE',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async patch<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }
}

// Singleton instance - can be swapped for testing or different implementations
export const apiClient = new ApiClient();

// Export type for dependency injection
export type ApiClientType = typeof apiClient;

