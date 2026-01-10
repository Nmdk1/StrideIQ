/**
 * API Configuration
 * 
 * Centralized API configuration that can be swapped for different environments
 * or implementations without breaking the rest of the application.
 */
export const API_CONFIG = {
  // Hardcode for now - env vars aren't loading properly
  baseURL: 'http://localhost:8000',
  timeout: 30000, // 30 seconds
  retries: 3,
  retryDelay: 1000, // 1 second
} as const;

export type ApiConfig = typeof API_CONFIG;


