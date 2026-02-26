'use client';

/**
 * Garmin Connect Button
 *
 * Garmin brand color: #007CC3 (blue)
 * Used for OAuth connect flow initiation.
 */

import React from 'react';

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
        inline-flex items-center justify-center gap-2
        rounded-md px-5 py-3
        font-semibold text-white text-sm
        transition-all duration-200
        hover:opacity-90 hover:shadow-lg
        focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900
        disabled:opacity-50 disabled:cursor-not-allowed
        ${className}
      `}
      style={{
        backgroundColor: '#007CC3',
        borderColor: '#006aaa',
        border: '1px solid',
        minHeight: '48px',
        minWidth: '193px',
        ['--tw-ring-color' as string]: '#007CC3',
      }}
    >
      <GarminWordmark />
      <span>Connect with Garmin Connect</span>
    </button>
  );
}

function GarminWordmark() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="white"
      aria-hidden="true"
    >
      <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 1.8a8.2 8.2 0 110 16.4A8.2 8.2 0 0112 3.8zm.9 3.5h-2.3v5.7h5.7v-2.3h-3.4V7.3z" />
    </svg>
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
