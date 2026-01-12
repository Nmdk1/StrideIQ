/**
 * API Configuration
 * 
 * Centralized API configuration that can be swapped for different environments
 * or implementations without breaking the rest of the application.
 */
export const API_CONFIG = {
  // Use local network IP for home testing, localhost for dev
  baseURL: typeof window !== 'undefined' && window.location.hostname !== 'localhost' 
    ? `http://${window.location.hostname}:8000`
    : 'http://localhost:8000',
  timeout: 30000, // 30 seconds
  retries: 3,
  retryDelay: 1000, // 1 second
} as const;

export type ApiConfig = typeof API_CONFIG;


