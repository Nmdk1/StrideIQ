'use client';

/**
 * RuntoonSharePrompt — mobile bottom sheet for the post-run share moment.
 *
 * Polls GET /v1/runtoon/pending every 10s.
 * Appears only on mobile (≤768px), only when:
 *   - User is authenticated
 *   - A share-eligible activity exists (running, ≥2mi, synced <24h,
 *     not dismissed, athlete has 3+ photos, feature flag enabled)
 *
 * On "Share Your Run" → opens RuntoonShareView.
 * On "Not now" / swipe-down / 10-min timeout → calls dismiss endpoint
 *   and hides prompt permanently for this activity.
 *
 * Privacy: never handles storage keys. Signed URLs come from the backend.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';
import { X, Zap } from 'lucide-react';
import { RuntoonShareView } from './RuntoonShareView';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ActivitySummary {
  name: string | null;
  distance_mi: number;
  pace: string;
  duration: string;
}

interface PendingRuntoon {
  activity_id: string;
  activity_summary: ActivitySummary;
  has_runtoon: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const AUTO_DISMISS_MS = 10 * 60 * 1000; // 10 minutes per spec

function formatDistance(mi: number): string {
  return `${mi.toFixed(1)} mi`;
}

async function authedFetch(url: string, token: string, opts: RequestInit = {}) {
  return fetch(url, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(opts.headers ?? {}),
    },
  });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RuntoonSharePrompt() {
  const { token, isAuthenticated } = useAuth();
  const queryClient = useQueryClient();

  const [visible, setVisible] = useState(false);
  const [shareViewOpen, setShareViewOpen] = useState(false);
  const [dismissedActivityId, setDismissedActivityId] = useState<string | null>(null);

  // Touch handling for swipe-down dismiss
  const touchStartY = useRef<number | null>(null);
  const sheetRef = useRef<HTMLDivElement>(null);

  // Auto-dismiss timer
  const autoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Mobile detection — SSR-safe
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const check = () =>
      setIsMobile(window.innerWidth <= 768 || 'ontouchstart' in window);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  // ---------------------------------------------------------------------------
  // Poll /pending
  // ---------------------------------------------------------------------------

  const { data: pending } = useQuery<PendingRuntoon | null>({
    queryKey: ['runtoon-pending'],
    queryFn: async () => {
      if (!token) return null;
      const res = await authedFetch(`${API_CONFIG.baseURL}/v1/runtoon/pending`, token);
      if (res.status === 204) return null;
      if (!res.ok) return null;
      return res.json();
    },
    enabled: isAuthenticated && isMobile,
    refetchInterval: (query) => {
      if (query.state.data !== undefined && query.state.data !== null) return false;
      return 10_000;
    },
    staleTime: 0,
    retry: false,
  });

  // ---------------------------------------------------------------------------
  // Show / hide logic
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!pending) return;
    if (pending.activity_id === dismissedActivityId) return;
    setVisible(true);

    // Auto-dismiss after 10 minutes if untouched
    if (autoTimer.current) clearTimeout(autoTimer.current);
    autoTimer.current = setTimeout(() => {
      handleDismiss(pending.activity_id, /* silent */ true);
    }, AUTO_DISMISS_MS);

    return () => {
      if (autoTimer.current) clearTimeout(autoTimer.current);
    };
    // handleDismiss is stable via useCallback; intentionally omitted from deps
    // to prevent infinite re-trigger when dismiss state changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending, dismissedActivityId]);

  // ---------------------------------------------------------------------------
  // Dismiss mutation
  // ---------------------------------------------------------------------------

  const dismissMutation = useMutation({
    mutationFn: async (activityId: string) => {
      if (!token) return;
      await authedFetch(
        `${API_CONFIG.baseURL}/v1/activities/${activityId}/runtoon/dismiss`,
        token,
        { method: 'POST' },
      );
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['runtoon-pending'] });
    },
  });

  const handleDismiss = useCallback(
    (activityId: string, silent = false) => {
      setVisible(false);
      setDismissedActivityId(activityId);
      if (autoTimer.current) clearTimeout(autoTimer.current);
      if (!silent) {
        dismissMutation.mutate(activityId);
      }
    },
    [dismissMutation],
  );

  // ---------------------------------------------------------------------------
  // Touch / swipe-down
  // ---------------------------------------------------------------------------

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartY.current = e.touches[0].clientY;
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartY.current === null || !pending) return;
    const dy = e.changedTouches[0].clientY - touchStartY.current;
    if (dy > 60) {
      // Swipe down ≥60px → dismiss
      handleDismiss(pending.activity_id);
    }
    touchStartY.current = null;
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (!isAuthenticated || !isMobile || !visible || !pending) return null;
  if (shareViewOpen) return null; // Share view takes over

  const { activity_id, activity_summary, has_runtoon } = pending;
  const { name, distance_mi, pace, duration } = activity_summary;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
        onClick={() => handleDismiss(activity_id)}
        aria-hidden="true"
      />

      {/* Bottom sheet */}
      <div
        ref={sheetRef}
        className="fixed bottom-0 left-0 right-0 z-50 animate-slide-up"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        role="dialog"
        aria-modal="true"
        aria-label="Share your run"
      >
        <div className="mx-auto max-w-lg rounded-t-2xl bg-slate-800 border border-slate-700 p-6 pb-safe shadow-2xl">
          {/* Drag handle */}
          <div className="mx-auto mb-4 h-1 w-12 rounded-full bg-slate-600" />

          {/* Header */}
          <div className="mb-1 flex items-center gap-2">
            <span className="text-xl">🏃</span>
            <span className="text-sm font-semibold text-orange-400 uppercase tracking-wide">
              Your run just landed
            </span>
            <button
              onClick={() => handleDismiss(activity_id)}
              className="ml-auto rounded p-1 text-slate-400 hover:text-slate-200"
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>

          {/* Run summary */}
          <p className="mb-1 text-lg font-bold text-white truncate">
            {name ?? 'Recent Run'}
          </p>
          <p className="mb-5 text-sm text-slate-400">
            {formatDistance(distance_mi)}
            {pace ? ` • ${pace}` : ''}
            {duration ? ` • ${duration}` : ''}
          </p>

          {/* Primary CTA */}
          <button
            onClick={() => setShareViewOpen(true)}
            className="mb-3 flex w-full items-center justify-center gap-2 rounded-xl bg-orange-500 px-6 py-4 text-base font-semibold text-white shadow-lg hover:bg-orange-400 active:scale-95 transition-all"
          >
            <Zap size={18} />
            Share Your Run
            <span className="ml-1 text-orange-200">→</span>
          </button>

          {/* Secondary dismiss */}
          <button
            onClick={() => handleDismiss(activity_id)}
            className="w-full py-2 text-sm text-slate-500 hover:text-slate-300 transition-colors"
          >
            Not now
          </button>
        </div>
      </div>

      {/* Share View (rendered in portal, not inside the bottom sheet) */}
      {shareViewOpen && (
        <RuntoonShareView
          activityId={activity_id}
          activitySummary={activity_summary}
          hasExistingRuntoon={has_runtoon}
          onClose={() => {
            setShareViewOpen(false);
            setVisible(false);
            setDismissedActivityId(activity_id);
            if (autoTimer.current) clearTimeout(autoTimer.current);
          }}
        />
      )}
    </>
  );
}
