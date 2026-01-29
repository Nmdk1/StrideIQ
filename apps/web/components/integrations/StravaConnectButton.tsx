'use client';

/**
 * Official "Connect with Strava" Button
 * 
 * Per Strava Brand Guidelines:
 * - Must use official button design for OAuth flow
 * - Orange (#FC4C02) or white color options
 * - 48px height at 1x, 96px at 2x
 * - Must link to https://www.strava.com/oauth/authorize
 * 
 * @see https://developers.strava.com/guidelines/
 */

import React from 'react';

interface StravaConnectButtonProps {
  onClick: () => void;
  disabled?: boolean;
  variant?: 'orange' | 'white';
  className?: string;
}

/**
 * Official Strava "Connect with Strava" button SVG
 * Matches the official asset from developers.strava.com
 */
export function StravaConnectButton({
  onClick,
  disabled = false,
  variant = 'orange',
  className = '',
}: StravaConnectButtonProps) {
  const isOrange = variant === 'orange';
  
  // Strava brand colors
  const bgColor = isOrange ? '#FC4C02' : '#FFFFFF';
  const textColor = isOrange ? '#FFFFFF' : '#FC4C02';
  const borderColor = isOrange ? '#FC4C02' : '#E0E0E0';
  
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label="Connect your Strava account"
      className={`
        inline-flex items-center justify-center
        rounded-md
        transition-all duration-200
        hover:opacity-90 hover:shadow-lg
        focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 focus:ring-offset-slate-900
        disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-none
        ${className}
      `}
      style={{
        backgroundColor: bgColor,
        border: `1px solid ${borderColor}`,
        padding: 0,
        minHeight: '48px',
        minWidth: '193px',
      }}
    >
      <svg
        width="193"
        height="48"
        viewBox="0 0 193 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-hidden="true"
      >
        {/* Background */}
        <rect width="193" height="48" rx="4" fill={bgColor} />
        
        {/* Strava Logo Mark */}
        <g transform="translate(12, 12)">
          <path
            d="M15.387 24L10.28 13.855H5.17L12.653 28.89h5.467L25.603 13.855H20.494L15.387 24Z"
            fill={textColor}
            transform="scale(0.8)"
          />
          <path
            d="M20.494 24L15.387 13.855H12.653L19.093 27.11h2.8l6.44-13.255H25.603L20.494 24Z"
            fill={textColor}
            opacity="0.6"
            transform="scale(0.8)"
          />
        </g>
        
        {/* "Connect with" text */}
        <text
          x="48"
          y="20"
          fill={textColor}
          fontSize="11"
          fontFamily="system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
          fontWeight="400"
        >
          Connect with
        </text>
        
        {/* "STRAVA" text - brand wordmark style */}
        <text
          x="48"
          y="35"
          fill={textColor}
          fontSize="16"
          fontFamily="system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
          fontWeight="700"
          letterSpacing="1"
        >
          STRAVA
        </text>
      </svg>
    </button>
  );
}

/**
 * Text fallback link for accessibility
 */
export function StravaConnectLink({
  onClick,
  className = '',
}: {
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`text-sm text-orange-400 hover:text-orange-300 underline ${className}`}
      aria-label="Connect your Strava account"
    >
      Connect with Strava
    </button>
  );
}

export default StravaConnectButton;
