'use client';

/**
 * Dashboard Redirect
 * 
 * Dashboard has been renamed to Analytics (research layer).
 * Redirects legacy /dashboard URLs to /home.
 * After trial start (Stripe checkout return), routes through /discover
 * for the first-session aha moment.
 */

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

function DashboardRedirectInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  useEffect(() => {
    const trialStarted = searchParams.get('trial') === 'started';
    router.replace(trialStarted ? '/discover' : '/home');
  }, [router, searchParams]);
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900">
      <p className="text-slate-400">Redirecting...</p>
    </div>
  );
}

export default function DashboardRedirect() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <p className="text-slate-400">Redirecting...</p>
      </div>
    }>
      <DashboardRedirectInner />
    </Suspense>
  );
}
