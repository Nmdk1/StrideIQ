/**
 * Strava Connection Component
 * 
 * Handles Strava OAuth connection and sync status.
 */

'use client';

import { useState, useEffect } from 'react';
import { useStravaStatus, useTriggerStravaSync, useStravaSyncStatus } from '@/lib/hooks/queries/strava';
import { stravaService } from '@/lib/api/services/strava';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';

export function StravaConnection() {
  const { data: status, isLoading: statusLoading, refetch: refetchStatus } = useStravaStatus();
  const triggerSync = useTriggerStravaSync();
  const [syncTaskId, setSyncTaskId] = useState<string | null>(null);
  const { data: syncStatus } = useStravaSyncStatus(syncTaskId, !!syncTaskId);
  const [connectError, setConnectError] = useState<string | null>(null);

  useEffect(() => {
    // Check if we're returning from Strava OAuth callback
    const urlParams = new URLSearchParams(window.location.search);
    const connected = urlParams.get('strava');
    const reason = urlParams.get('reason');

    if (connected === 'connected') {
      // Server-side callback redirects here; refresh status and clean the URL.
      setTimeout(() => {
        refetchStatus();
        setConnectError(null);
        window.history.replaceState({}, document.title, window.location.pathname);
      }, 500);
    }
    if (connected === 'error') {
      // Strava OAuth can fail for external reasons (e.g., app capacity). Surface a clear message.
      if (reason === 'capacity') {
        setConnectError(
          "Strava connect is temporarily unavailable (app capacity reached). Upload Garmin for now, or try again later."
        );
      } else {
        setConnectError('Strava connection failed. Please try again.');
      }
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, [refetchStatus]);

  const handleConnect = async () => {
    try {
      const { auth_url } = await stravaService.getAuthUrl('/settings');
      window.location.href = auth_url;
    } catch (error) {
      console.error('Error getting auth URL:', error);
      setConnectError(error instanceof Error ? error.message : 'Strava connection failed. Please try again.');
    }
  };

  const handleSync = async () => {
    try {
      const result = await triggerSync.mutateAsync();
      setSyncTaskId(result.task_id);
    } catch (error) {
      console.error('Error triggering sync:', error);
    }
  };

  if (statusLoading) {
    return <LoadingSpinner />;
  }

  const isConnected = status?.connected || false;
  const isSyncing = syncStatus?.status === 'pending' || syncStatus?.status === 'started';

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold">Strava Integration</h3>
          <p className="text-sm text-slate-400 mt-1">
            Connect your Strava account to automatically sync activities
          </p>
        </div>
        {isConnected && (
          <span className="px-3 py-1 bg-green-900/50 border border-green-700/50 rounded text-sm text-green-400">
            Connected
          </span>
        )}
      </div>

      {!isConnected ? (
        <div>
          <button
            onClick={handleConnect}
            className="w-full px-4 py-2 bg-orange-600 hover:bg-orange-700 rounded text-white font-medium transition-colors"
          >
            Connect Strava
          </button>
          <p className="text-xs text-slate-500 mt-2 text-center">
            You&apos;ll be redirected to Strava to authorize access
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {status?.last_sync && (
            <div className="text-sm">
              <span className="text-slate-400">Last sync:</span>{' '}
              <span className="text-white">
                {new Date(status.last_sync).toLocaleString()}
              </span>
            </div>
          )}

          {syncStatus && (
            <div className="bg-slate-900 rounded p-3">
              <div className="flex items-center gap-2">
                {isSyncing && <LoadingSpinner size="sm" />}
                <span className="text-sm">
                  {syncStatus.status === 'pending' && 'Sync queued...'}
                  {syncStatus.status === 'started' && 'Syncing activities...'}
                  {syncStatus.status === 'success' && 'Sync completed successfully!'}
                  {syncStatus.status === 'error' && `Sync failed: ${syncStatus.error}`}
                </span>
              </div>
              {syncStatus.result && (
                <div className="text-xs text-slate-400 mt-2">
                  {JSON.stringify(syncStatus.result, null, 2)}
                </div>
              )}
            </div>
          )}

          <button
            onClick={handleSync}
            disabled={isSyncing || triggerSync.isPending}
            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed rounded text-white font-medium transition-colors"
          >
            {isSyncing || triggerSync.isPending ? (
              <>
                <LoadingSpinner size="sm" className="inline mr-2" />
                Syncing...
              </>
            ) : (
              'Sync Activities Now'
            )}
          </button>

          <button
            onClick={handleConnect}
            className="w-full px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-white font-medium transition-colors"
          >
            Reconnect Strava
          </button>
        </div>
      )}

      {triggerSync.isError && (
        <ErrorMessage error={triggerSync.error} className="mt-4" />
      )}

      {connectError && <ErrorMessage error={connectError} className="mt-4" />}
    </div>
  );
}

