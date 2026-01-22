/**
 * Diagnostics route (legacy)
 *
 * We intentionally keep this route to avoid breaking old links,
 * but the operator-focused dashboard lives under `/admin/diagnostics`.
 */

'use client';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/hooks/useAuth';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

export default function DiagnosticPage() {
  const router = useRouter();
  const { user } = useAuth();

  useEffect(() => {
    const isAdmin = user?.role === 'admin' || user?.role === 'owner';
    router.replace(isAdmin ? '/admin/diagnostics' : '/insights');
  }, [router, user?.role]);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <LoadingSpinner size="lg" />
          <p className="text-slate-400 mt-4">Redirecting…</p>
        </div>
      </div>
    </ProtectedRoute>
  );
}
