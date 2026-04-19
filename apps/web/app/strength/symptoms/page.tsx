'use client';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { SymptomLogger } from '@/components/strength/SymptomLogger';

export default function StrengthSymptomsPage() {
  return (
    <ProtectedRoute>
      <SymptomLogger />
    </ProtectedRoute>
  );
}
