'use client';

/**
 * InsightActionLink - Robust navigation for insight feed actions
 * 
 * Uses Next.js Link for client-side navigation.
 * Validates href before rendering.
 * Handles edge cases gracefully.
 */

import Link from 'next/link';
import { useRouter } from 'next/navigation';

interface InsightActionLinkProps {
  href: string;
  label: string;
  className?: string;
  variant?: 'default' | 'compact';
}

// Valid internal routes for insight actions
const VALID_ROUTES = [
  '/training-load',
  '/calendar',
  '/insights',
  '/analytics',
  '/settings',
  '/diagnostic',
  '/checkin',
  '/personal-bests',
  '/activities',
  '/coach',
  '/home',
];

function isValidHref(href: string): boolean {
  if (!href || typeof href !== 'string') return false;
  
  // Must start with /
  if (!href.startsWith('/')) return false;
  
  // Check against known valid routes
  const basePath = href.split('?')[0]; // Remove query params
  return VALID_ROUTES.some(route => basePath.startsWith(route));
}

export function InsightActionLink({ 
  href, 
  label, 
  className = '',
  variant = 'default'
}: InsightActionLinkProps) {
  const router = useRouter();
  
  // Validate href
  if (!isValidHref(href)) {
    console.warn(`[InsightActionLink] Invalid href: ${href}`);
    return null;
  }
  
  const baseClasses = variant === 'compact'
    ? 'shrink-0 px-2.5 py-2 bg-slate-800/60 border border-slate-700/60 hover:border-slate-600 rounded-lg text-xs font-medium text-slate-200 transition-colors'
    : 'px-3 py-2 bg-slate-900/40 border border-slate-700/50 hover:border-slate-600 rounded-lg text-sm font-medium transition-colors text-center';
  
  return (
    <Link
      href={href}
      className={`${baseClasses} ${className}`}
      onClick={(e) => {
        // Log for debugging (remove in production)
        console.debug(`[InsightActionLink] Navigating to: ${href}`);
      }}
    >
      {label}
    </Link>
  );
}

export default InsightActionLink;
