/**
 * Discovery Dashboard Page
 * 
 * The correlation engine showcase - "What's Working" and "What Doesn't Work".
 * This is the core discovery feature that identifies which inputs lead to efficiency improvements.
 */

'use client';

import { useState } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useWhatWorks, useWhatDoesntWork } from '@/lib/hooks/queries/correlations';
import { WhatWorksSection } from '@/components/discovery/WhatWorksSection';
import { WhatDoesntWorkSection } from '@/components/discovery/WhatDoesntWorkSection';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';

export default function DiscoveryPage() {
  const [days, setDays] = useState(90);
  const { data: whatWorks, isLoading: loadingWorks, error: errorWorks } = useWhatWorks(days);
  const { data: whatDoesnt, isLoading: loadingDoesnt, error: errorDoesnt } = useWhatDoesntWork(days);

  const isLoading = loadingWorks || loadingDoesnt;
  const error = errorWorks || errorDoesnt;

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  if (error) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center p-4">
          <ErrorMessage error={error} title="Failed to load correlations" />
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
        <div className="max-w-6xl mx-auto px-4">
          {/* Header */}
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-3xl font-bold">Discovery</h1>
              <p className="text-gray-400 mt-2">
                What inputs lead to efficiency improvements? The data speaks.
              </p>
            </div>
            <div>
              <select
                value={days}
                onChange={(e) => setDays(parseInt(e.target.value))}
                className="px-4 py-2 bg-gray-800 border border-gray-700 rounded text-white"
              >
                <option value="30">Last 30 days</option>
                <option value="60">Last 60 days</option>
                <option value="90">Last 90 days</option>
                <option value="180">Last 6 months</option>
                <option value="365">Last year</option>
              </select>
            </div>
          </div>

          {/* What's Working */}
          <WhatWorksSection
            correlations={whatWorks?.what_works || []}
            className="mb-8"
          />

          {/* What Doesn't Work */}
          <WhatDoesntWorkSection
            correlations={whatDoesnt?.what_doesnt_work || []}
            className="mb-8"
          />

          {/* Analysis Period Info */}
          {whatWorks?.analysis_period && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 text-sm text-gray-400">
              <p>
                Analysis period: {new Date(whatWorks.analysis_period.start).toLocaleDateString()} -{' '}
                {new Date(whatWorks.analysis_period.end).toLocaleDateString()} ({whatWorks.analysis_period.days} days)
              </p>
              {whatWorks.count === 0 && whatDoesnt?.count === 0 && (
                <p className="mt-2">
                  Not enough data yet. Log more activities, sleep, nutrition to see patterns.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}


