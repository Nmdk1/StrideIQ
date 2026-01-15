/**
 * Feature Flags System
 * 
 * Simple local storage-based feature flags for gradual rollout.
 * 
 * Usage:
 *   import { isFeatureEnabled } from '@/lib/featureFlags';
 *   
 *   if (isFeatureEnabled('time_input_v2')) {
 *     return <TimeInput ... />;
 *   } else {
 *     return <input type="text" ... />;
 *   }
 * 
 * Override in browser console:
 *   localStorage.setItem('ff_time_input_v2', 'true')
 *   localStorage.setItem('ff_time_input_v2', 'false')
 *   localStorage.removeItem('ff_time_input_v2')  // Use default
 */

/**
 * Feature flags that are ENABLED by default.
 * Add a flag here when ready for general rollout.
 */
const ENABLED_BY_DEFAULT: string[] = [
  'time_input_v2',  // Enabled - auto-formatting time input
  'age_grade_v2',   // Enabled - enhanced age-grading results display
];

/**
 * Check if a feature flag is enabled.
 * 
 * Priority:
 * 1. localStorage override (for testing/QA)
 * 2. ENABLED_BY_DEFAULT list
 * 3. Default: false
 * 
 * @param flag - Feature flag name (e.g., 'time_input_v2')
 * @returns true if feature is enabled
 */
export function isFeatureEnabled(flag: string): boolean {
  // SSR safety - no localStorage on server
  if (typeof window === 'undefined') {
    return ENABLED_BY_DEFAULT.includes(flag);
  }
  
  try {
    // Check for localStorage override
    const override = localStorage.getItem(`ff_${flag}`);
    if (override === 'true') return true;
    if (override === 'false') return false;
    
    // Fall back to default list
    return ENABLED_BY_DEFAULT.includes(flag);
  } catch {
    // localStorage may throw in private browsing
    return ENABLED_BY_DEFAULT.includes(flag);
  }
}

/**
 * Enable a feature flag (for testing).
 * 
 * @param flag - Feature flag name
 */
export function enableFeature(flag: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem(`ff_${flag}`, 'true');
  }
}

/**
 * Disable a feature flag.
 * 
 * @param flag - Feature flag name
 */
export function disableFeature(flag: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem(`ff_${flag}`, 'false');
  }
}

/**
 * Reset a feature flag to default behavior.
 * 
 * @param flag - Feature flag name
 */
export function resetFeature(flag: string): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(`ff_${flag}`);
  }
}

// Feature flag constants
export const FEATURE_FLAGS = {
  TIME_INPUT_V2: 'time_input_v2',
  AGE_GRADE_V2: 'age_grade_v2',  // Enhanced age-grading calculator with detailed results
} as const;
