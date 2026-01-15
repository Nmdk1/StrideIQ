'use client';

/**
 * Dashboard Redirect
 * 
 * Dashboard has been renamed to Analytics (research layer).
 * Redirects legacy /dashboard URLs to /home.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function DashboardRedirect() {
  const router = useRouter();
  
  useEffect(() => {
    router.replace('/home');
  }, [router]);
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]">
      <p className="text-slate-400">Redirecting...</p>
    </div>
  );
}
