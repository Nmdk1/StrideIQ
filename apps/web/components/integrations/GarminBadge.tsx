'use client';

/**
 * Garmin Connect Attribution Badge
 *
 * Per Garmin developer compliance: display attribution wherever Garmin data
 * is shown. Includes optional device name when available.
 */

interface GarminBadgeProps {
  deviceName?: string | null;
  className?: string;
  size?: 'sm' | 'md';
}

export function GarminBadge({ deviceName, className = '', size = 'sm' }: GarminBadgeProps) {
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm';
  const iconSize = size === 'sm' ? 'w-3 h-3' : 'w-4 h-4';

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-slate-400 ${textSize} ${className}`}
      title="Data from Garmin Connect"
    >
      <GarminIcon className={iconSize} />
      <span>
        {deviceName
          ? `Garmin Connect · ${formatDeviceName(deviceName)}`
          : 'Garmin Connect'}
      </span>
    </span>
  );
}

/**
 * Format a raw device name string for display.
 * e.g. "forerunner965" -> "Forerunner 965", "fenix7" -> "Fenix 7"
 */
function formatDeviceName(raw: string): string {
  // Insert space before digit sequences and title-case each word
  return raw
    .replace(/([a-z])(\d)/g, '$1 $2')
    .replace(/(\d)([a-z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function GarminIcon({ className = '' }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      style={{ color: '#007CC3' }}
    >
      {/* Garmin "G" simplified mark */}
      <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 1.8a8.2 8.2 0 110 16.4A8.2 8.2 0 0112 3.8zm.9 3.5h-2.3v5.7h5.7v-2.3h-3.4V7.3z" />
    </svg>
  );
}

export default GarminBadge;
