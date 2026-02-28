'use client';

/**
 * Garmin Connect Button
 *
 * Per Garmin API Brand Guidelines v2:
 * - Use the official Garmin Connect badge asset as the primary CTA visual.
 * - Keep the full app name "Garmin Connect™" — do not abbreviate or truncate.
 * - Do NOT recreate the badge with custom styling or a hand-drawn icon.
 * - Keep an accessible <button> wrapper for keyboard/focus/aria compliance.
 *
 * Asset: /garmin-connect-badge.png
 *   Source: Garmin_connect_badge_digital_RESOURCE_FILE-01.png (GCDP Branding Assets_v2)
 */

import React from 'react';
import Image from 'next/image';

interface GarminConnectButtonProps {
  onClick: () => void;
  disabled?: boolean;
  className?: string;
}

export function GarminConnectButton({
  onClick,
  disabled = false,
  className = '',
}: GarminConnectButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label="Connect your Garmin Connect account"
      className={`
        inline-flex items-center justify-center
        rounded-md
        focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 focus:ring-blue-400
        disabled:opacity-50 disabled:cursor-not-allowed
        transition-opacity hover:opacity-90
        ${className}
      `}
      style={{ minHeight: '48px', minWidth: '193px', background: 'none', border: 'none', padding: 0 }}
    >
      {/* Official Garmin Connect badge — do not modify dimensions or styling */}
      <Image
        src="/garmin-connect-badge.png"
        alt="Connect with Garmin Connect™"
        height={48}
        width={193}
        style={{ height: 48, width: 'auto', objectFit: 'contain' }}
        priority
        unoptimized
      />
    </button>
  );
}

export function GarminConnectLink({
  onClick,
  className = '',
}: {
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`text-sm underline ${className}`}
      style={{ color: '#007CC3' }}
      aria-label="Connect your Garmin Connect account"
    >
      Connect with Garmin Connect
    </button>
  );
}

export default GarminConnectButton;
