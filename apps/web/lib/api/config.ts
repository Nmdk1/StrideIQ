/**
 * API Configuration
 * 
 * Centralized API configuration that can be swapped for different environments
 * or implementations without breaking the rest of the application.
 * 
 * PRODUCTION: Set NEXT_PUBLIC_API_URL at build time (e.g., https://api.strideiq.run)
 * DEVELOPMENT: Falls back to localhost:8000 or local network IP
 */

function getApiBaseUrl(): string {
  // 1. Use environment variable if set (production)
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  
  // 2. Server-side rendering - use localhost
  if (typeof window === 'undefined') {
    return 'http://localhost:8000';
  }
  
  // 3. Client-side development - handle local network testing
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'http://localhost:8000';
  }
  
  // 4. Local network testing (e.g., testing from phone on same network)
  return `http://${window.location.hostname}:8000`;
}

export const API_CONFIG = {
  baseURL: getApiBaseUrl(),
  timeout: 30000, // 30 seconds
  retries: 3,
  retryDelay: 1000, // 1 second
} as const;

export type ApiConfig = typeof API_CONFIG;


