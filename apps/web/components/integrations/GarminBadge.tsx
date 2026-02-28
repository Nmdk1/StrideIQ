'use client';

/**
 * Garmin Connect Attribution Badge
 *
 * Uses the official "works with the app GARMIN CONNECT" badge asset
 * (Garmin_connect_badge_print_RESOURCE_FILE-01.png) for all data attribution
 * surfaces: activity detail, splits footer, home page last run.
 *
 * Device name is shown alongside the badge when available.
 * Badge asset is 193px wide × 48px tall (native). Scale proportionally.
 */

import Image from 'next/image';

interface GarminBadgeProps {
  deviceName?: string | null;
  className?: string;
  size?: 'sm' | 'md';
}

export function GarminBadge({ deviceName, className = '', size = 'sm' }: GarminBadgeProps) {
  const textSize = size === 'sm' ? 'text-sm' : 'text-base';
  // Badge renders at 24px height (sm, splits/footer) or 28px height (md, header) — preserves aspect ratio.
  const badgeHeight = size === 'sm' ? 24 : 28;
  const badgeWidth = Math.round(badgeHeight * (193 / 48));
  const formattedDevice = deviceName ? formatDeviceName(deviceName) : null;

  return (
    <span
      className={`inline-flex items-center gap-2 text-slate-200 ${textSize} ${className}`}
      title={formattedDevice ? `Works with Garmin Connect — ${formattedDevice}` : 'Works with Garmin Connect'}
    >
      {/* Official "works with the app GARMIN CONNECT" badge — Garmin brand guidelines v2 */}
      <Image
        src="/garmin-works-with-badge.png"
        alt="Works with the app GARMIN CONNECT"
        height={badgeHeight}
        width={badgeWidth}
        style={{ height: badgeHeight, width: 'auto', objectFit: 'contain' }}
        unoptimized
      />
      {formattedDevice && (
        <span className="text-slate-300">{formattedDevice}</span>
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
