'use client';

/**
 * Strength v1 sandbox — manual log entry page.
 *
 * Wraps the SessionLogger inside ProtectedRoute. The component is a
 * single mobile-first surface; nothing else lives at this route.
 */

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { SessionLogger } from '@/components/strength/SessionLogger';

export default function StrengthLogPage() {
  return (
    <ProtectedRoute>
      <SessionLogger />
    </ProtectedRoute>
  );
}
