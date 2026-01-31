/**
 * Strava Connection Component
 * 
 * Handles Strava OAuth connection, sync status, and token verification.
 * Detects revoked tokens and provides disconnect functionality.
 */

'use client';

import { useState, useEffect } from 'react';
import { useStravaStatus, useTriggerStravaSync, useStravaSyncStatus } from '@/lib/hooks/queries/strava';
import { stravaService } from '@/lib/api/services/strava';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { StravaConnectButton, StravaConnectLink } from './StravaConnectButton';

export function StravaConnection() {
  const { data: status, isLoading: statusLoading, refetch: refetchStatus } = useStravaStatus();
  const triggerSync = useTriggerStravaSync();
  const [syncTaskId, setSyncTaskId] = useState<string | null>(null);
  const [syncStartTime, setSyncStartTime] = useState<number | null>(null);
  const { data: syncStatus } = useStravaSyncStatus(syncTaskId, !!syncTaskId);
  const [connectError, setConnectError] = useState<string | null>(null);
  
  // Token verification state
  const [isVerifying, setIsVerifying] = useState(false);
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [isDisconnecting, setIsDisconnecting] = useState(false);

  // Clear syncTaskId after success/error/unknown so stale status doesn't persist
  useEffect(() => {
    if (syncStatus?.status === 'success' || syncStatus?.status === 'error') {
      // Show the result for 3 seconds, then clear
      const timer = setTimeout(() => {
        setSyncTaskId(null);
        setSyncStartTime(null);
        // Refresh the main status to get updated last_sync
        refetchStatus();
      }, 3000);
      return () => clearTimeout(timer);
    }
    
    // Unknown status means task expired or was never tracked - clear immediately
    if (syncStatus?.status === 'unknown') {
      setSyncTaskId(null);
      setSyncStartTime(null);
      refetchStatus();
    }
  }, [syncStatus?.status, refetchStatus]);

  // Timeout safeguard: if sync is "pending" for over 2 minutes, assume stale
  // This is a backup in case Redis tracking fails
  useEffect(() => {
    if (syncTaskId && syncStartTime && syncStatus?.status === 'pending') {
      const elapsed = Date.now() - syncStartTime;
      if (elapsed > 120000) {
        // Task is likely stale
        setSyncTaskId(null);
        setSyncStartTime(null);
        refetchStatus();
      }
    }
  }, [syncTaskId, syncStartTime, syncStatus?.status, refetchStatus]);

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
        setTokenValid(true); // Just connected, token is valid
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

  // Verify token on mount when status shows connected
  useEffect(() => {
    if (status?.connected && tokenValid === null && !isVerifying) {
      setIsVerifying(true);
      stravaService.verifyConnection()
        .then((result) => {
          setTokenValid(result.valid);
          if (!result.valid && result.reason === 'revoked') {
            setConnectError('Strava access was revoked. Please reconnect.');
            refetchStatus(); // Refresh to update connected state
          }
        })
        .catch((error) => {
          console.error('Error verifying Strava connection:', error);
          // On error, assume valid to avoid false disconnects
          setTokenValid(true);
        })
        .finally(() => {
          setIsVerifying(false);
        });
    }
  }, [status?.connected, tokenValid, isVerifying, refetchStatus]);

  // Handle disconnect
  const handleDisconnect = async () => {
    if (!confirm('Disconnect Strava? Your synced activities will be preserved.')) {
      return;
    }
    
    setIsDisconnecting(true);
    try {
      await stravaService.disconnect();
      setTokenValid(null);
      setConnectError(null);
      refetchStatus();
    } catch (error) {
      console.error('Error disconnecting Strava:', error);
      setConnectError('Failed to disconnect. Please try again.');
    } finally {
      setIsDisconnecting(false);
    }
  };

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
      setSyncStartTime(Date.now());
    } catch (error) {
      console.error('Error triggering sync:', error);
    }
  };

  if (statusLoading) {
    return <LoadingSpinner />;
  }

  const isConnected = status?.connected || false;
  const isSyncing = syncStatus?.status === 'pending' || syncStatus?.status === 'started' || syncStatus?.status === 'progress';

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
          <div className="flex items-center gap-2">
            {isVerifying ? (
              <span className="px-3 py-1 bg-slate-700/50 border border-slate-600/50 rounded text-sm text-slate-400 flex items-center gap-2">
                <LoadingSpinner size="sm" />
                Verifying...
              </span>
            ) : tokenValid === false ? (
              <span className="px-3 py-1 bg-red-900/50 border border-red-700/50 rounded text-sm text-red-400">
                Disconnected
              </span>
            ) : (
              <span className="px-3 py-1 bg-green-900/50 border border-green-700/50 rounded text-sm text-green-400">
                Connected
              </span>
            )}
          </div>
        )}
      </div>

      {!isConnected ? (
        <div className="flex flex-col items-center">
          {/* Official Strava "Connect with Strava" button per brand guidelines */}
          <StravaConnectButton
            onClick={handleConnect}
            variant="orange"
          />
          
          {/* Accessibility fallback link */}
          <p className="text-xs text-slate-500 mt-3 text-center">
            You&apos;ll be redirected to Strava to authorize access
          </p>
          <StravaConnectLink
            onClick={handleConnect}
            className="mt-1"
          />
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
                  {syncStatus.status === 'progress' && (syncStatus.message || `Syncing ${syncStatus.current} of ${syncStatus.total}...`)}
                  {syncStatus.status === 'success' && 'Sync completed successfully!'}
                  {syncStatus.status === 'error' && `Sync failed: ${syncStatus.error}`}
                </span>
              </div>
              {/* Progress bar for active sync */}
              {syncStatus.status === 'progress' && (syncStatus.total ?? 0) > 0 && (
                <div className="mt-2">
                  <div className="w-full bg-slate-700 rounded-full h-2">
                    <div 
                      className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${Math.round(((syncStatus.current ?? 0) / (syncStatus.total ?? 1)) * 100)}%` }}
                    />
                  </div>
                  <div className="text-xs text-slate-400 mt-1 text-right">
                    {Math.round(((syncStatus.current ?? 0) / (syncStatus.total ?? 1)) * 100)}%
                  </div>
                </div>
              )}
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

          {/* Official Strava button for reconnection per brand guidelines */}
          <div className="flex flex-col items-center mt-2">
            <StravaConnectButton
              onClick={handleConnect}
              variant="orange"
            />
            <StravaConnectLink
              onClick={handleConnect}
              className="mt-2"
            />
          </div>

          {/* Disconnect button */}
          <div className="pt-4 border-t border-slate-700/50 mt-4">
            <button
              onClick={handleDisconnect}
              disabled={isDisconnecting}
              className="w-full px-4 py-2 bg-slate-700/50 hover:bg-red-900/30 hover:border-red-700/50 border border-slate-600/50 rounded text-slate-400 hover:text-red-400 text-sm font-medium transition-colors disabled:opacity-50"
            >
              {isDisconnecting ? (
                <>
                  <LoadingSpinner size="sm" className="inline mr-2" />
                  Disconnecting...
                </>
              ) : (
                'Disconnect Strava'
              )}
            </button>
            <p className="text-xs text-slate-500 mt-2 text-center">
              Your synced activities will be preserved
            </p>
          </div>
        </div>
      )}

      {triggerSync.isError && (
        <ErrorMessage error={triggerSync.error} className="mt-4" />
      )}

      {connectError && <ErrorMessage error={connectError} className="mt-4" />}
    </div>
  );
}

