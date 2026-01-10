"use client";

/**
 * Units Context
 * 
 * Provides global unit preferences (metric/imperial) and conversion utilities.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { preferencesService, UnitSystem } from '../api/services/preferences';
import { useAuth } from '../hooks/useAuth';

// Conversion constants
const KM_TO_MILES = 0.621371;
const MILES_TO_KM = 1.60934;
const METERS_TO_FEET = 3.28084;

export interface UnitsContextValue {
  units: UnitSystem;
  setUnits: (units: UnitSystem) => Promise<void>;
  isLoading: boolean;
  
  // Conversion utilities
  formatDistance: (meters: number | null | undefined, decimals?: number) => string;
  formatPace: (secondsPerKm: number | null | undefined) => string;
  formatElevation: (meters: number | null | undefined) => string;
  
  // Raw conversions (for charts, calculations)
  convertDistance: (meters: number) => number;
  convertPace: (secondsPerKm: number) => number;
  
  // Labels
  distanceUnit: string;
  distanceUnitShort: string;
  paceUnit: string;
  elevationUnit: string;
}

const UnitsContext = createContext<UnitsContextValue | undefined>(undefined);

export function UnitsProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading: authLoading, token } = useAuth();
  const [units, setUnitsState] = useState<UnitSystem>('metric');
  const [isLoading, setIsLoading] = useState(true);
  const [hasLoadedPrefs, setHasLoadedPrefs] = useState(false);

  // Load preferences when authenticated AND we have a token
  useEffect(() => {
    // Wait for auth to finish loading
    if (authLoading) return;
    
    // Prevent duplicate loads
    if (hasLoadedPrefs) return;
    
    if (isAuthenticated && token) {
      // Token is available, fetch preferences
      setHasLoadedPrefs(true);
      preferencesService.getPreferences()
        .then(prefs => {
          setUnitsState(prefs.preferred_units);
        })
        .catch((error) => {
          // Silently default to metric - don't spam console
          setUnitsState('metric');
        })
        .finally(() => setIsLoading(false));
    } else if (!isAuthenticated) {
      // Not authenticated - check localStorage for guest preference
      setHasLoadedPrefs(true);
      if (typeof window !== 'undefined') {
        const stored = localStorage.getItem('preferred_units') as UnitSystem;
        if (stored === 'metric' || stored === 'imperial') {
          setUnitsState(stored);
        }
      }
      setIsLoading(false);
    }
  }, [isAuthenticated, authLoading, token, hasLoadedPrefs]);

  const setUnits = useCallback(async (newUnits: UnitSystem) => {
    setUnitsState(newUnits);
    
    if (isAuthenticated && token) {
      try {
        await preferencesService.updatePreferences({ preferred_units: newUnits });
      } catch (error) {
        // Save to localStorage as backup
        if (typeof window !== 'undefined') {
          localStorage.setItem('preferred_units', newUnits);
        }
      }
    } else {
      if (typeof window !== 'undefined') {
        localStorage.setItem('preferred_units', newUnits);
      }
    }
  }, [isAuthenticated, token]);

  // Conversion utilities
  const convertDistance = useCallback((meters: number): number => {
    const km = meters / 1000;
    return units === 'imperial' ? km * KM_TO_MILES : km;
  }, [units]);

  const convertPace = useCallback((secondsPerKm: number): number => {
    // Convert seconds/km to seconds/mile for imperial
    return units === 'imperial' ? secondsPerKm * MILES_TO_KM : secondsPerKm;
  }, [units]);

  const formatDistance = useCallback((meters: number | null | undefined, decimals: number = 1): string => {
    if (meters === null || meters === undefined) return '-';
    const value = convertDistance(meters);
    const unit = units === 'imperial' ? 'mi' : 'km';
    return `${value.toFixed(decimals)} ${unit}`;
  }, [convertDistance, units]);

  const formatPace = useCallback((secondsPerKm: number | null | undefined): string => {
    if (secondsPerKm === null || secondsPerKm === undefined) return '-';
    const seconds = convertPace(secondsPerKm);
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    const unit = units === 'imperial' ? '/mi' : '/km';
    return `${minutes}:${secs.toString().padStart(2, '0')}${unit}`;
  }, [convertPace, units]);

  const formatElevation = useCallback((meters: number | null | undefined): string => {
    if (meters === null || meters === undefined) return '-';
    if (units === 'imperial') {
      const feet = meters * METERS_TO_FEET;
      return `${Math.round(feet)} ft`;
    }
    return `${Math.round(meters)} m`;
  }, [units]);

  const value: UnitsContextValue = {
    units,
    setUnits,
    isLoading,
    formatDistance,
    formatPace,
    formatElevation,
    convertDistance,
    convertPace,
    distanceUnit: units === 'imperial' ? 'miles' : 'kilometers',
    distanceUnitShort: units === 'imperial' ? 'mi' : 'km',
    paceUnit: units === 'imperial' ? 'min/mi' : 'min/km',
    elevationUnit: units === 'imperial' ? 'ft' : 'm',
  };

  return (
    <UnitsContext.Provider value={value}>
      {children}
    </UnitsContext.Provider>
  );
}

export function useUnits(): UnitsContextValue {
  const context = useContext(UnitsContext);
  if (context === undefined) {
    throw new Error('useUnits must be used within a UnitsProvider');
  }
  return context;
}
