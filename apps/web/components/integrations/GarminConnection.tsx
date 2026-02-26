/**
 * Garmin Connect Integration Component
 *
 * Handles Garmin OAuth connection status and disconnect functionality.
 * Mirrors StravaConnection.tsx — Garmin is push-based so there is no
 * manual sync trigger (backfill runs automatically on connect via D7).
 */

'use client';

import { useState, useEffect } from 'react';
import { useGarminStatus } from '@/lib/hooks/queries/garmin';
import { garminService } from '@/lib/api/services/garmin';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { GarminConnectButton, GarminConnectLink } from './GarminConnectButton';
import { GarminBadge } from './GarminBadge';
import { GarminFileImport } from './GarminFileImport';

export function GarminConnection() {
  const { data: status, isLoading: statusLoading, refetch: refetchStatus } = useGarminStatus();
  const [connectError, setConnectError] = useState<string | null>(null);
  const [isDisconnecting, setIsDisconnecting] = useState(false);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const garminParam = urlParams.get('garmin');

    if (garminParam === 'connected') {
      setTimeout(() => {
        refetchStatus();
        setConnectError(null);
        window.history.replaceState({}, document.title, window.location.pathname);
      }, 500);
    }
    if (garminParam === 'error') {
      setConnectError('Garmin Connect connection failed. Please try again.');
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, [refetchStatus]);

  const handleConnect = async () => {
    try {
      const { auth_url } = await garminService.getAuthUrl('/settings');
      window.location.href = auth_url;
    } catch (error) {
      setConnectError(
        error instanceof Error ? error.message : 'Garmin Connect connection failed. Please try again.'
      );
    }
  };

  const handleDisconnect = async () => {
    if (
      !confirm(
        'Disconnect Garmin Connect? Your synced activities will be preserved, but wellness data (sleep, HRV, daily metrics) will be deleted.'
      )
    ) {
      return;
    }

    setIsDisconnecting(true);
    try {
      await garminService.disconnect();
      setConnectError(null);
      refetchStatus();
    } catch (error) {
      console.error('Error disconnecting Garmin:', error);
      setConnectError('Failed to disconnect. Please try again.');
    } finally {
      setIsDisconnecting(false);
    }
  };

  if (statusLoading) {
    return <LoadingSpinner />;
  }

  const isConnected = status?.connected ?? false;
  const canConnect = status?.garmin_connect_available ?? false;

  // If the flag is off and the athlete is not connected, render nothing.
  // Connected athletes always see their connected state + disconnect option.
  if (!isConnected && !canConnect && status !== undefined) {
    return null;
  }

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold">Garmin Connect</h3>
          <p className="text-sm text-slate-400 mt-1">
            Sync activities and wellness data (sleep, HRV, daily metrics)
          </p>
        </div>
        {isConnected && (
          <span className="px-3 py-1 bg-green-900/50 border border-green-700/50 rounded text-sm text-green-400">
            Connected
          </span>
        )}
      </div>

      {!isConnected ? (
        <div className="flex flex-col items-center">
          <GarminConnectButton onClick={handleConnect} />
          <p className="text-xs text-slate-500 mt-3 text-center">
            You&apos;ll be redirected to Garmin Connect to authorize access
          </p>
          <GarminConnectLink onClick={handleConnect} className="mt-1" />
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

          <div className="bg-slate-900/40 border border-slate-700/50 rounded p-3">
            <p className="text-sm text-slate-300 mb-1">
              Activities and wellness data sync automatically via Garmin Connect&apos;s push API.
            </p>
            <p className="text-xs text-slate-500">
              A 90-day backfill was requested when you connected. New data arrives within minutes of recording.
            </p>
          </div>

          <GarminBadge size="sm" className="mt-1" />

          {/* Garmin file import still available when connected */}
          <div className="pt-4 border-t border-slate-700/50">
            <p className="text-xs text-slate-500 mb-3">
              Already have a Garmin Connect export ZIP? You can still import it manually.
            </p>
            <GarminFileImport compact />
          </div>

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
                'Disconnect Garmin Connect'
              )}
            </button>
            <p className="text-xs text-slate-500 mt-2 text-center">
              Synced activities are preserved; wellness data will be deleted
            </p>
          </div>
        </div>
      )}

      {connectError && <ErrorMessage error={connectError} className="mt-4" />}
    </div>
  );
}
