'use client';

/**
 * Authentication Context
 * 
 * Provides shared auth state across all components.
 * This ensures Navigation, pages, and components all see the same auth state.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { authService } from '../api/services/auth';
import { apiClient } from '../api/client';
import { clearQueryCache } from '../providers/QueryProvider';
import type { Athlete, LoginRequest, RegisterRequest } from '../api/types';

const AUTH_TOKEN_KEY = 'auth_token';
const AUTH_USER_KEY = 'auth_user';

export interface AuthState {
  user: Athlete | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

export interface AuthContextType extends AuthState {
  login: (credentials: LoginRequest) => Promise<any>;
  register: (data: RegisterRequest) => Promise<any>;
  logout: () => void;
  refreshUser: () => Promise<Athlete>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: null,
    isLoading: true,
    isAuthenticated: false,
  });

  // Initialize auth state from localStorage
  useEffect(() => {
    // Only run on client
    if (typeof window === 'undefined') return;

    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    const userStr = localStorage.getItem(AUTH_USER_KEY);
    
    if (!token) {
      setState({ user: null, token: null, isLoading: false, isAuthenticated: false });
      return;
    }
    
    // Set token on API client
    apiClient.setAuthToken(token);
    
    // Parse stored user
    let user = null;
    if (userStr && userStr !== 'undefined' && userStr !== 'null') {
      try {
        user = JSON.parse(userStr);
      } catch {
        // Invalid JSON
      }
    }
    
    // If we have valid user data, validate token before setting authenticated
    if (user && user.id) {
      // Quick validation - try to get current user from API
      authService.getCurrentUser()
        .then((freshUser) => {
          // Token is valid
          localStorage.setItem(AUTH_USER_KEY, JSON.stringify(freshUser));
          setState({
            user: freshUser,
            token,
            isLoading: false,
            isAuthenticated: true,
          });
        })
        .catch(() => {
          // Token is invalid/expired - clear auth state
          localStorage.removeItem(AUTH_TOKEN_KEY);
          localStorage.removeItem(AUTH_USER_KEY);
          apiClient.setAuthToken(null);
          setState({ user: null, token: null, isLoading: false, isAuthenticated: false });
        });
      return;
    }
    
    // Fetch user from API if missing
    const fetchUser = async () => {
      try {
        const freshUser = await authService.getCurrentUser();
        localStorage.setItem(AUTH_USER_KEY, JSON.stringify(freshUser));
        setState({
          user: freshUser,
          token,
          isLoading: false,
          isAuthenticated: true,
        });
      } catch {
        // Token expired/invalid
        localStorage.removeItem(AUTH_TOKEN_KEY);
        localStorage.removeItem(AUTH_USER_KEY);
        apiClient.setAuthToken(null);
        setState({ user: null, token: null, isLoading: false, isAuthenticated: false });
      }
    };
    
    fetchUser();
  }, []);

  const login = useCallback(async (credentials: LoginRequest) => {
    const response = await authService.login(credentials);
    apiClient.setAuthToken(response.access_token);
    localStorage.setItem(AUTH_TOKEN_KEY, response.access_token);
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(response.athlete));
    
    setState({
      user: response.athlete,
      token: response.access_token,
      isLoading: false,
      isAuthenticated: true,
    });
    
    return response;
  }, []);

  const register = useCallback(async (data: RegisterRequest) => {
    const response = await authService.register(data);
    apiClient.setAuthToken(response.access_token);
    localStorage.setItem(AUTH_TOKEN_KEY, response.access_token);
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(response.athlete));
    
    setState({
      user: response.athlete,
      token: response.access_token,
      isLoading: false,
      isAuthenticated: true,
    });
    
    return response;
  }, []);

  const logout = useCallback(() => {
    apiClient.setAuthToken(null);
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
    
    // Clear React Query cache to prevent stale data showing after logout
    clearQueryCache();
    
    setState({
      user: null,
      token: null,
      isLoading: false,
      isAuthenticated: false,
    });
  }, []);

  const refreshUser = useCallback(async () => {
    const user = await authService.getCurrentUser();
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
    setState(prev => ({ ...prev, user }));
    return user;
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
