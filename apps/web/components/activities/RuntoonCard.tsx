'use client';

/**
 * RuntoonCard — AI-generated personalized run caricature.
 *
 * Placed on the activity detail page. Shows:
 * - Generating state (polling every 5s, timeout 90s)
 * - Ready state (image + actions)
 * - Error state (neutral "unavailable" message — no scary errors)
 * - No-photos state (CTA to upload photos)
 *
 * Privacy: all image access is via signed URLs (15-min TTL). Never
 * exposes raw storage keys or bucket URLs.
 *
 * Interaction:
 * - "Download (1:1)" → signed URL for square image
 * - "Download (Stories)" → server-side 9:16 Pillow recompose
 * - "Regenerate" → POST to trigger a new generation (guided+ only, ≤3 total)
 */

import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';
import { Share2, RefreshCw, Sparkles, Image as ImageIcon } from 'lucide-react';
import { RuntoonShareView } from '@/components/runtoon/RuntoonShareView';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RuntoonData {
  id: string;
  activity_id: string;
  signed_url: string;
  attempt_number: number;
  generation_time_ms: number | null;
  cost_usd: number | null;
  created_at: string;
}


// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const POLL_INTERVAL_MS = 5000;     // 5s polling while generating
const POLL_TIMEOUT_MS = 90000;     // 90s max wait, then show "unavailable"
const SIGNED_URL_TTL_MS = 14 * 60 * 1000; // Refresh 1 min before 15-min TTL
const MIN_PHOTOS_REQUIRED = 3;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface RuntoonCardProps {
  activityId: string;
}

export function RuntoonCard({ activityId }: RuntoonCardProps) {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const pollStartRef = useRef<number | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const [shareViewOpen, setShareViewOpen] = useState(false);
  const [regenCount, setRegenCount] = useState(0);

  // Self-contained photo check — avoids prop-drilling from parent
  // Uses the same query key as RuntoonPhotoUpload so responses are cached
  const { data: photos, isLoading: photosLoading } = useQuery<{ id: string }[]>({
    queryKey: ['runtoon-photos'],
    queryFn: async () => {
      const res = await fetch(`${API_CONFIG.baseURL}/v1/runtoon/photos`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 403) return [];  // Feature flag not enabled — graceful
      if (!res.ok) return [];
      return res.json();
    },
    enabled: !!token,
    staleTime: 2 * 60 * 1000,
  });

  const hasPhotos = !photosLoading && (photos?.length ?? 0) >= MIN_PHOTOS_REQUIRED;

  // Poll for Runtoon — backs off after 90s
  const { data: runtoon, isLoading } = useQuery<RuntoonData | null>({
    queryKey: ['runtoon', activityId],
    queryFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/activities/${activityId}/runtoon`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) return null;
      const body = await res.json();
      return body ?? null;
    },
    enabled: !!token && !photosLoading && hasPhotos && !timedOut,
    refetchInterval: (data) => {
      // Stop polling once we have a result
      if (data?.state?.data) return false;
      // Track poll start time
      if (pollStartRef.current === null) pollStartRef.current = Date.now();
      const elapsed = Date.now() - (pollStartRef.current ?? Date.now());
      if (elapsed > POLL_TIMEOUT_MS) {
        setTimedOut(true);
        return false;
      }
      return POLL_INTERVAL_MS;
    },
    staleTime: SIGNED_URL_TTL_MS,
  });

  // Reset timeout when activityId changes
  useEffect(() => {
    pollStartRef.current = null;
    setTimedOut(false);
  }, [activityId]);

  // Regeneration mutation
  const regenMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(
        `${API_CONFIG.baseURL}/v1/activities/${activityId}/runtoon/generate`,
        { method: 'POST', headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to queue regeneration.');
      }
      return res.json();
    },
    onSuccess: () => {
      // Reset polling to wait for new generation
      pollStartRef.current = Date.now();
      setTimedOut(false);
      setRegenCount((c) => c + 1);
      // Invalidate so we start polling again
      queryClient.invalidateQueries({ queryKey: ['runtoon', activityId] });
    },
  });


  // ------------------------------------------------------------------
  // Render: photo check still in flight — show nothing yet
  // ------------------------------------------------------------------
  if (photosLoading) return null;

  // ------------------------------------------------------------------
  // Render: no photos uploaded yet
  // ------------------------------------------------------------------
  if (!hasPhotos) {
    return (
      <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 p-5 text-center">
        <ImageIcon className="w-8 h-8 text-slate-500 mx-auto mb-3" />
        <p className="text-sm font-medium text-slate-300 mb-1">Add your Runtoon photos</p>
        <p className="text-xs text-slate-400 mb-3">
          Upload 3+ reference photos to get a personalized caricature after each run.
        </p>
        <Link
          href="/settings#runtoon"
          className="inline-block text-xs font-semibold text-orange-400 hover:text-orange-300 transition-colors"
        >
          Upload photos →
        </Link>
      </div>
    );
  }

  // ------------------------------------------------------------------
  // Render: timed out or unavailable
  // ------------------------------------------------------------------
  if (timedOut) {
    return (
      <div className="rounded-lg border border-slate-700/40 bg-slate-800/20 p-4 text-center">
        <p className="text-sm text-slate-400">Runtoon unavailable for this run.</p>
      </div>
    );
  }

  // ------------------------------------------------------------------
  // Render: no Runtoon yet — show "Share Your Run" CTA (on-demand)
  // ------------------------------------------------------------------
  if (!runtoon && !isLoading) {
    return (
      <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/40">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-orange-400" />
            <span className="text-sm font-semibold text-slate-200">Your Runtoon</span>
          </div>
        </div>
        <div className="p-5 text-center">
          <p className="text-sm text-slate-400 mb-3">
            Get a personalized AI caricature of this run
          </p>
          <button
            type="button"
            onClick={() => setShareViewOpen(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-orange-500 hover:bg-orange-400 rounded-lg text-sm font-semibold text-white transition-colors active:scale-95"
          >
            <Share2 className="w-4 h-4" />
            Share Your Run
          </button>
        </div>
        {shareViewOpen && (
          <RuntoonShareView
            activityId={activityId}
            hasExistingRuntoon={false}
            onClose={() => {
              setShareViewOpen(false);
              queryClient.invalidateQueries({ queryKey: ['runtoon', activityId] });
            }}
          />
        )}
      </div>
    );
  }

  if (!runtoon && isLoading) {
    return (
      <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 p-5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-orange-500/40 border-t-orange-500 animate-spin flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-slate-200">Generating your Runtoon…</p>
            <p className="text-xs text-slate-400 mt-0.5">Usually ready in 15–30 seconds</p>
          </div>
        </div>
      </div>
    );
  }

  if (!runtoon) return null;

  // ------------------------------------------------------------------
  // Render: Runtoon ready
  // ------------------------------------------------------------------
  const canRegenerate = regenCount < 2; // 1 auto + 2 manual = 3 max; user sees 0 to 2

  return (
    <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/40">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-orange-400" />
          <span className="text-sm font-semibold text-slate-200">Your Runtoon</span>
        </div>
        <span className="text-xs text-slate-500">
          {runtoon.attempt_number > 1 ? `Attempt ${runtoon.attempt_number}` : 'AI-generated'}
        </span>
      </div>

      {/* Image */}
      <div className="relative">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={runtoon.signed_url}
          alt="AI-generated personalized run caricature"
          className="w-full object-contain"
          loading="lazy"
        />
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between gap-2 p-3 border-t border-slate-700/40">
        {/* Primary: Share Your Run */}
        <button
          type="button"
          onClick={() => setShareViewOpen(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-orange-500 hover:bg-orange-400 rounded-md text-xs font-semibold text-white transition-colors active:scale-95"
        >
          <Share2 className="w-3.5 h-3.5" />
          Share Your Run
        </button>

        {/* Secondary: Try another look (if attempts remain) */}
        {canRegenerate ? (
          <button
            type="button"
            onClick={() => regenMutation.mutate()}
            disabled={regenMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700/60 hover:bg-slate-700 rounded-md text-xs font-medium text-slate-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${regenMutation.isPending ? 'animate-spin' : ''}`} />
            {regenMutation.isPending ? 'Queued…' : 'Try another look'}
          </button>
        ) : (
          <span className="text-xs text-slate-500 px-2">3/3 used</span>
        )}
      </div>

      {regenMutation.isError && (
        <p className="px-4 pb-3 text-xs text-red-400">
          {regenMutation.error instanceof Error ? regenMutation.error.message : 'Failed to regenerate.'}
        </p>
      )}

      {/* Share View overlay */}
      {shareViewOpen && (
        <RuntoonShareView
          activityId={activityId}
          hasExistingRuntoon={true}
          onClose={() => setShareViewOpen(false)}
        />
      )}
    </div>
  );
}
