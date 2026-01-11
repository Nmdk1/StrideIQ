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
