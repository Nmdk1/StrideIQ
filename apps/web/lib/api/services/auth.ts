/**
 * Authentication API Service
 */

import { apiClient } from '../client';
import type { LoginRequest, RegisterRequest, AuthResponse, Athlete } from '../types';

export const authService = {
  /**
   * Register new athlete
   */
  async register(data: RegisterRequest): Promise<AuthResponse> {
    return apiClient.post<AuthResponse>('/v1/auth/register', data, { skipAuth: true });
  },

  /**
   * Login
   */
  async login(data: LoginRequest): Promise<AuthResponse> {
    return apiClient.post<AuthResponse>('/v1/auth/login', data, { skipAuth: true });
  },

  /**
   * Get current user
   */
  async getCurrentUser(): Promise<Athlete> {
    return apiClient.get<Athlete>('/v1/auth/me');
  },

  /**
   * Refresh access token
   */
  async refreshToken(): Promise<{ access_token: string; token_type: string }> {
    return apiClient.post('/v1/auth/refresh');
  },

  /**
   * Update current athlete profile
   */
  async updateProfile(updates: {
    display_name?: string;
    birthdate?: string;
    sex?: string;
    height_cm?: number;
    email?: string;
    onboarding_stage?: string;
    onboarding_completed?: boolean;
  }): Promise<Athlete> {
    return apiClient.put<Athlete>('/v1/athletes/me', updates);
  },

  /**
   * Get the athlete's current Training Pace Profile (if present).
   */
  async getTrainingPaceProfile(): Promise<{ status: string; pace_profile?: any | null; updated_at?: string | null }> {
    return apiClient.get<{ status: string; pace_profile?: any | null; updated_at?: string | null }>(
      '/v1/athletes/me/training-pace-profile'
    );
  },
} as const;

