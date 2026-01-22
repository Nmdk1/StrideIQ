'use client';

import { DiagnosticReportPage } from '@/components/diagnostic/DiagnosticReportPage';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuth } from '@/lib/hooks/useAuth';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

export default function DiagnosticReportRoute() {
  const router = useRouter();
  const { user } = useAuth();

  useEffect(() => {
    const isAdmin = user?.role === 'admin' || user?.role === 'owner';
    if (!isAdmin) router.replace('/insights');
  }, [router, user?.role]);

  const isAdmin = user?.role === 'admin' || user?.role === 'owner';
  if (!isAdmin) {
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

  return <DiagnosticReportPage />;
}

