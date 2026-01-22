/**
 * Training Availability Page
 * 
 * Displays and manages training availability grid.
 */

'use client';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';

import { AvailabilityGrid } from '@/components/availability/AvailabilityGrid';

export default function AvailabilityPage() {
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100 py-8">
      <div className="max-w-6xl mx-auto px-4">
        <h1 className="text-3xl font-bold mb-8">Training Availability</h1>
        <p className="text-slate-400 mb-6">
          Set your preferred training times. Click slots to cycle through: Unavailable → Available → Preferred
        </p>
        <AvailabilityGrid />
      </div>
    </div>
    </ProtectedRoute>
  );
}

