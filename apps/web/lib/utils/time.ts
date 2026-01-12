/**
 * Time Conversion Utilities
 * 
 * Handles conversion between time string formats and seconds.
 */

/**
 * Parse a time string to total seconds.
 * 
 * Supports formats:
 * - "H:MM:SS" (e.g., "4:30:15" = 4h 30m 15s = 16215 seconds)
 * - "MM:SS" (e.g., "30:15" = 30m 15s = 1815 seconds)
 * - "M:SS" (e.g., "5:30" = 5m 30s = 330 seconds)
 * 
 * @param timeStr - Time string in H:MM:SS or MM:SS format
 * @returns Total seconds, or null if parsing fails
 */
export function parseTimeToSeconds(timeStr: string): number | null {
  if (!timeStr || typeof timeStr !== 'string') {
    return null;
  }

  const parts = timeStr.trim().split(':').map(p => parseInt(p, 10));
  
  // Check all parts are valid numbers
  if (parts.some(isNaN) || parts.some(p => p < 0)) {
    return null;
  }

  if (parts.length === 3) {
    // H:MM:SS
    const [hours, minutes, seconds] = parts;
    if (minutes > 59 || seconds > 59) {
      return null;
    }
    return hours * 3600 + minutes * 60 + seconds;
  } else if (parts.length === 2) {
    // MM:SS
    const [minutes, seconds] = parts;
    if (seconds > 59) {
      return null;
    }
    return minutes * 60 + seconds;
  }

  return null;
}

/**
 * Format seconds to a human-readable time string.
 * 
 * @param totalSeconds - Total seconds
 * @returns Formatted string (e.g., "4:30:15" or "30:15")
 */
export function formatSecondsToTime(totalSeconds: number): string {
  if (totalSeconds < 0 || !Number.isFinite(totalSeconds)) {
    return '0:00';
  }

  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

/**
 * Format pace (seconds per mile) to mm:ss/mi string.
 * 
 * @param secondsPerMile - Pace in seconds per mile
 * @returns Formatted pace string (e.g., "8:30")
 */
export function formatPace(secondsPerMile: number): string {
  if (secondsPerMile <= 0 || !Number.isFinite(secondsPerMile)) {
    return '--:--';
  }

  const minutes = Math.floor(secondsPerMile / 60);
  const seconds = Math.floor(secondsPerMile % 60);
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

/**
 * Format raw digit string into time display (auto-insert colons).
 * 
 * Used by TimeInput component for auto-formatting as user types.
 * 
 * Examples (hhmmss mode):
 *   "1"     → "1"
 *   "12"    → "12"
 *   "123"   → "1:23"
 *   "1234"  → "12:34"
 *   "12345" → "1:23:45"
 *   "123456"→ "12:34:56"
 * 
 * Examples (mmss mode):
 *   "1"     → "1"
 *   "12"    → "12"
 *   "123"   → "1:23"
 *   "1234"  → "12:34"
 * 
 * @param digits - Raw digit string (non-digits will be stripped)
 * @param maxLength - 'mmss' (4 digits) or 'hhmmss' (6 digits)
 * @returns Formatted time string with colons
 */
export function formatDigitsToTime(
  digits: string, 
  maxLength: 'mmss' | 'hhmmss' = 'hhmmss'
): string {
  // Strip non-digits and limit length
  const cleanDigits = digits.replace(/\D/g, '');
  const maxDigits = maxLength === 'mmss' ? 4 : 6;
  const trimmed = cleanDigits.slice(0, maxDigits);
  
  if (trimmed.length === 0) return '';
  if (trimmed.length <= 2) return trimmed;
  
  if (maxLength === 'mmss') {
    // MM:SS format (max 4 digits)
    const secs = trimmed.slice(-2);
    const mins = trimmed.slice(0, -2);
    return `${mins}:${secs}`;
  } else {
    // hhmmss format (max 6 digits)
    if (trimmed.length <= 4) {
      // MM:SS
      const secs = trimmed.slice(-2);
      const mins = trimmed.slice(0, -2);
      return `${mins}:${secs}`;
    } else {
      // H:MM:SS or HH:MM:SS
      const secs = trimmed.slice(-2);
      const mins = trimmed.slice(-4, -2);
      const hrs = trimmed.slice(0, -4);
      return `${hrs}:${mins}:${secs}`;
    }
  }
}

/**
 * Strip non-digit characters from a string.
 * 
 * @param value - Input string potentially containing colons or other chars
 * @returns String containing only digits
 */
export function stripToDigits(value: string): string {
  return value.replace(/\D/g, '');
}
