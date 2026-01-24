'use client';

/**
 * Plan Checkout Page (Legacy)
 *
 * StrideIQ has converged to Free vs Pro subscription (Phase 6).
 * We keep this route as a safe redirect to prevent broken deep-links, but
 * all one-time plan purchase flows are deprecated.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function CheckoutPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/settings');
  }, [router]);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex items-center justify-center">
      <div className="bg-slate-800 border border-slate-700/50 rounded-xl p-8 max-w-md w-full text-center">
        <h1 className="text-2xl font-bold text-white mb-4">Checkout is no longer used</h1>
        <p className="text-slate-400">
          StrideIQ uses membership (Free vs Pro). Redirecting you to Settings…
        </p>
      </div>
    </div>
  );
}
