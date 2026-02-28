'use client';

/**
 * Garmin Connect Attribution Badge
 *
 * Per Garmin API Brand Guidelines v2:
 * - Use the official GARMIN® tag logo image (not a custom SVG).
 * - Data attribution text format: "[device model]" — e.g. "Forerunner 165".
 * - Do NOT use "Garmin Connect" as the data source name; "Garmin Connect" is
 *   the app name and is reserved for authentication/connection references only.
 * - If device model is unavailable, the logo wordmark alone is sufficient.
 */

import Image from 'next/image';

interface GarminBadgeProps {
  deviceName?: string | null;
  className?: string;
  size?: 'sm' | 'md';
}

export function GarminBadge({ deviceName, className = '', size = 'sm' }: GarminBadgeProps) {
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm';
  // Logo heights per brand guidelines: 12-16px for sm, 16-20px for md.
  const logoHeight = size === 'sm' ? 12 : 16;
  const formattedDevice = deviceName ? formatDeviceName(deviceName) : null;

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-slate-400 ${textSize} ${className}`}
      title={formattedDevice ? `Garmin ${formattedDevice}` : 'Garmin'}
    >
      {/* Official GARMIN® tag wordmark — do not replace with a custom icon */}
      <Image
        src="/garmin-tag-white.png"
        alt="GARMIN®"
        height={logoHeight}
        width={logoHeight * 4}
        style={{ height: logoHeight, width: 'auto', objectFit: 'contain' }}
        unoptimized
      />
      {formattedDevice && (
        <span>{formattedDevice}</span>
      )}
    </span>
  );
}

/**
 * Format a raw device name string for display.
 * e.g. "forerunner965" → "Forerunner 965", "fenix7" → "Fenix 7"
 */
export function formatDeviceName(raw: string): string {
  return raw
    .replace(/([a-z])(\d)/g, '$1 $2')
    .replace(/(\d)([a-z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default GarminBadge;
