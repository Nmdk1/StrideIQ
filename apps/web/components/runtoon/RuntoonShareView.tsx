'use client';

/**
 * RuntoonShareView — full-screen overlay for sharing a Runtoon.
 *
 * Used from:
 *   1. RuntoonSharePrompt (mobile bottom sheet CTA)
 *   2. RuntoonCard "Share Your Run" button (activity page)
 *
 * Flow:
 *   - If hasExistingRuntoon=false → triggers generation, shows skeleton (~15-20s)
 *   - If hasExistingRuntoon=true  → fetches existing Runtoon, goes straight to ready state
 *   - Ready: image (1:1 by default), format toggle, Save, Share (Web Share API), Regenerate
 *
 * Web Share API behaviour:
 *   - iOS Safari / Android Chrome: full native share sheet with files
 *   - Desktop / Firefox: fallback — download + copy caption + toast
 *
 * Privacy: no storage keys handled here. All image access via signed URLs.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';
import {
  X,
  Download,
  Share2,
  RefreshCw,
  Copy,
  Check,
  ChevronDown,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ActivitySummary {
  name: string | null;
  distance_mi: number;
  pace: string;
  duration: string;
}

interface RuntoonData {
  id: string;
  activity_id: string;
  signed_url: string;
  attempt_number: number;
  caption_text: string | null;
}

interface DownloadResponse {
  signed_url: string;
  format: string;
  expires_in: number;
}

interface RuntoonShareViewProps {
  activityId: string;
  activitySummary?: ActivitySummary;
  hasExistingRuntoon: boolean;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const POLL_INTERVAL = 5_000;
const POLL_TIMEOUT = 120_000; // 2 min — generation takes ~15-20s, allow buffer
const PER_ACTIVITY_CAP = 3;

async function authedFetch(url: string, token: string, opts: RequestInit = {}) {
  return fetch(url, {
    ...opts,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(opts.headers ?? {}),
    },
  });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RuntoonShareView({
  activityId,
  activitySummary,
  hasExistingRuntoon,
  onClose,
}: RuntoonShareViewProps) {
  const { token } = useAuth();
  const queryClient = useQueryClient();

  // Format toggle: 1:1 (default) or 9:16
  const [format, setFormat] = useState<'1:1' | '9:16'>('1:1');
  const [formatDropdownOpen, setFormatDropdownOpen] = useState(false);

  // Generation state
  const [generating, setGenerating] = useState(!hasExistingRuntoon);
  const [genTimedOut, setGenTimedOut] = useState(false);
  const [regenCount, setRegenCount] = useState(0);
  const [generationHint, setGenerationHint] = useState('Creating your Runtoon...');
  const pollStart = useRef(Date.now());
  const hintTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Share / copy state
  const [copied, setCopied] = useState(false);
  const [shareToast, setShareToast] = useState<string | null>(null);

  // Touch handling (swipe-down to close)
  const touchStartY = useRef<number | null>(null);

  // ---------------------------------------------------------------------------
  // Effect: update generation hint text
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!generating) return;
    hintTimer.current = setTimeout(() => {
      setGenerationHint('Almost there...');
    }, 10_000);
    return () => {
      if (hintTimer.current) clearTimeout(hintTimer.current);
    };
  }, [generating, regenCount]);

  // ---------------------------------------------------------------------------
  // Trigger generation (if needed)
  // ---------------------------------------------------------------------------

  const genMutation = useMutation({
    mutationFn: async () => {
      const res = await authedFetch(
        `${API_CONFIG.baseURL}/v1/activities/${activityId}/runtoon/generate`,
        token!,
        { method: 'POST' },
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? 'Failed to start generation.');
      }
      return res.json();
    },
    onSuccess: () => {
      pollStart.current = Date.now();
      setGenerating(true);
      setGenTimedOut(false);
      setGenerationHint('Creating your Runtoon...');
      queryClient.invalidateQueries({ queryKey: ['runtoon', activityId] });
    },
  });

  // Trigger generation on mount if no existing Runtoon
  useEffect(() => {
    if (!hasExistingRuntoon && token) {
      genMutation.mutate();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // Poll for Runtoon
  // ---------------------------------------------------------------------------

  const { data: runtoon } = useQuery<RuntoonData | null>({
    queryKey: ['runtoon', activityId],
    queryFn: async () => {
      if (!token) return null;
      const res = await authedFetch(
        `${API_CONFIG.baseURL}/v1/activities/${activityId}/runtoon`,
        token!,
      );
      if (res.status === 404) return null;
      if (!res.ok) return null;
      return res.json();
    },
    refetchInterval: (data) => {
      if (data) return false; // Stop polling once image is ready
      if (Date.now() - pollStart.current > POLL_TIMEOUT) return false;
      return POLL_INTERVAL;
    },
    enabled: !!token,
    staleTime: 0,
  });

  // When image arrives, stop generating spinner
  useEffect(() => {
    if (runtoon) setGenerating(false);
  }, [runtoon]);

  // Timeout detection
  useEffect(() => {
    if (!generating) return;
    const t = setTimeout(() => {
      if (!runtoon) setGenTimedOut(true);
    }, POLL_TIMEOUT);
    return () => clearTimeout(t);
  }, [generating, runtoon]);

  // ---------------------------------------------------------------------------
  // Download image blob
  // ---------------------------------------------------------------------------

  const fetchImageBlob = useCallback(
    async (fmt: '1:1' | '9:16'): Promise<{ blob: Blob; caption: string }> => {
      const res = await authedFetch(
        `${API_CONFIG.baseURL}/v1/runtoon/download/${runtoon!.id}?format=${encodeURIComponent(fmt)}`,
        token!,
      );
      if (!res.ok) throw new Error('Download URL unavailable.');
      const data: DownloadResponse = await res.json();

      const imgRes = await fetch(data.signed_url);
      if (!imgRes.ok) throw new Error('Image fetch failed.');
      const blob = await imgRes.blob();
      return { blob, caption: runtoon?.caption_text ?? 'Check out my run on StrideIQ! strideiq.run' };
    },
    [runtoon, token],
  );

  // ---------------------------------------------------------------------------
  // Save (download to device)
  // ---------------------------------------------------------------------------

  const handleSave = async () => {
    if (!runtoon) return;
    try {
      const { blob } = await fetchImageBlob(format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `runtoon-${format.replace(':', 'x')}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      setShareToast('Download failed — try again.');
    }
  };

  // ---------------------------------------------------------------------------
  // Record share analytics
  // ---------------------------------------------------------------------------

  const recordShare = useCallback(
    async (shareFormat: '1:1' | '9:16') => {
      if (!runtoon || !token) return;
      await authedFetch(`${API_CONFIG.baseURL}/v1/runtoon/${runtoon.id}/shared`, token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ share_format: shareFormat, share_target: null }),
      }).catch(() => { /* best-effort */ });
    },
    [runtoon, token],
  );

  // ---------------------------------------------------------------------------
  // Share (Web Share API + fallback)
  // ---------------------------------------------------------------------------

  const handleShare = async () => {
    if (!runtoon) return;
    try {
      const { blob, caption } = await fetchImageBlob(format);
      const file = new File([blob], 'runtoon.png', { type: 'image/png' });

      if (
        typeof navigator.share === 'function' &&
        navigator.canShare?.({ files: [file] })
      ) {
        await navigator.share({
          files: [file],
          title: 'My run on StrideIQ',
          text: caption,
        });
        await recordShare(format);
      } else {
        // Desktop fallback: save + copy caption
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'runtoon.png';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        await navigator.clipboard.writeText(caption).catch(() => {});
        setShareToast('Image saved — paste it wherever you share');
        await recordShare(format);
      }
    } catch (err) {
      // navigator.share AbortError = user cancelled; don't toast
      if ((err as Error).name !== 'AbortError') {
        setShareToast('Share failed — try Save instead.');
      }
    }
  };

  // Copy caption only
  const handleCopyCaption = async () => {
    const caption = runtoon?.caption_text ?? 'Check out my run on StrideIQ! strideiq.run';
    await navigator.clipboard.writeText(caption).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // ---------------------------------------------------------------------------
  // Regenerate
  // ---------------------------------------------------------------------------

  const handleRegen = () => {
    if (regenCount >= PER_ACTIVITY_CAP - 1) return;
    setRegenCount((c) => c + 1);
    genMutation.mutate();
  };

  const canRegen = regenCount < PER_ACTIVITY_CAP - 1;

  // ---------------------------------------------------------------------------
  // Touch swipe-down close
  // ---------------------------------------------------------------------------

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartY.current = e.touches[0].clientY;
  };
  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartY.current === null) return;
    const dy = e.changedTouches[0].clientY - touchStartY.current;
    if (dy > 80) onClose();
    touchStartY.current = null;
  };

  // ---------------------------------------------------------------------------
  // Auto-clear toast
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!shareToast) return;
    const t = setTimeout(() => setShareToast(null), 4000);
    return () => clearTimeout(t);
  }, [shareToast]);

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  const runLabel = activitySummary
    ? [
        `${activitySummary.distance_mi.toFixed(1)} mi`,
        activitySummary.pace,
        activitySummary.duration,
      ]
        .filter(Boolean)
        .join(' • ')
    : null;

  // ---------------------------------------------------------------------------
  // Render: generating state
  // ---------------------------------------------------------------------------

  const renderGenerating = () => (
    <div className="flex flex-col items-center justify-center flex-1 px-6 py-12">
      {/* Skeleton */}
      <div className="w-full max-w-xs aspect-square rounded-2xl bg-slate-700/60 animate-pulse mb-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-slate-600/30 to-transparent animate-shimmer" />
      </div>
      <p className="text-base font-semibold text-white mb-1">{generationHint}</p>
      <p className="text-sm text-slate-400">Usually ready in ~15 sec</p>
    </div>
  );

  // ---------------------------------------------------------------------------
  // Render: timed out
  // ---------------------------------------------------------------------------

  const renderTimedOut = () => (
    <div className="flex flex-col items-center justify-center flex-1 px-6 py-12 text-center">
      <p className="text-base text-slate-300 mb-2">Runtoon unavailable for this run.</p>
      <p className="text-sm text-slate-500">Generation took too long. Try again from the activity page.</p>
      <button
        onClick={onClose}
        className="mt-6 text-sm text-orange-400 hover:text-orange-300"
      >
        Close
      </button>
    </div>
  );

  // ---------------------------------------------------------------------------
  // Render: ready
  // ---------------------------------------------------------------------------

  const renderReady = () => (
    <>
      {/* Image — hero, top 60-65% */}
      <div className="relative w-full flex-shrink-0" style={{ aspectRatio: format === '9:16' ? '9/16' : '1/1', maxHeight: '65vh' }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={runtoon!.signed_url}
          alt="Your Runtoon"
          className="w-full h-full object-contain rounded-2xl animate-fade-in"
        />
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-3 px-6 py-4 w-full">
        {/* Format toggle */}
        <div className="relative">
          <button
            onClick={() => setFormatDropdownOpen((v) => !v)}
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200"
          >
            {format === '1:1' ? 'Square (1:1)' : 'Stories (9:16)'}
            <ChevronDown size={14} />
          </button>
          {formatDropdownOpen && (
            <div className="absolute bottom-full left-0 mb-1 rounded-lg bg-slate-700 border border-slate-600 shadow-lg overflow-hidden">
              {(['1:1', '9:16'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => { setFormat(f); setFormatDropdownOpen(false); }}
                  className={`block w-full px-4 py-2 text-sm text-left hover:bg-slate-600 ${
                    format === f ? 'text-orange-400 font-semibold' : 'text-slate-200'
                  }`}
                >
                  {f === '1:1' ? 'Square (1:1)' : 'Stories (9:16)'}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Primary action row */}
        <div className="flex gap-3">
          <button
            onClick={handleSave}
            className="flex items-center justify-center gap-2 flex-1 rounded-xl border border-slate-600 py-3 text-sm font-semibold text-slate-200 hover:bg-slate-700 active:scale-95 transition-all"
          >
            <Download size={16} />
            Save
          </button>
          <button
            onClick={handleShare}
            className="flex items-center justify-center gap-2 flex-[2] rounded-xl bg-orange-500 py-3 text-sm font-semibold text-white hover:bg-orange-400 active:scale-95 transition-all"
          >
            <Share2 size={16} />
            Share →
          </button>
        </div>

        {/* Copy caption */}
        <button
          onClick={handleCopyCaption}
          className="flex items-center justify-center gap-2 text-sm text-slate-400 hover:text-slate-200 py-1"
        >
          {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
          {copied ? 'Caption copied!' : 'Copy caption'}
        </button>

        {/* Try another look */}
        {canRegen && (
          <button
            onClick={handleRegen}
            disabled={genMutation.isPending}
            className="flex items-center justify-center gap-2 rounded-xl border border-slate-700 py-3 text-sm text-slate-400 hover:text-slate-200 hover:border-slate-500 disabled:opacity-40 transition-all"
          >
            <RefreshCw size={14} className={genMutation.isPending ? 'animate-spin' : ''} />
            {genMutation.isPending ? 'Generating...' : 'Try another look'}
          </button>
        )}
      </div>
    </>
  );

  // ---------------------------------------------------------------------------
  // Root render
  // ---------------------------------------------------------------------------

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-slate-900"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      role="dialog"
      aria-modal="true"
      aria-label="Share your Runtoon"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-safe pb-2">
        <button
          onClick={onClose}
          className="rounded-full p-2 text-slate-400 hover:text-white hover:bg-slate-800"
          aria-label="Close"
        >
          <X size={20} />
        </button>
        {runLabel && (
          <p className="text-sm text-slate-400 truncate max-w-xs">{runLabel}</p>
        )}
        <div className="w-10" /> {/* spacer */}
      </div>

      {/* Content */}
      <div className="flex flex-col items-center flex-1 overflow-y-auto">
        {genTimedOut
          ? renderTimedOut()
          : (generating && !runtoon)
          ? renderGenerating()
          : runtoon
          ? renderReady()
          : renderGenerating()}
      </div>

      {/* Toast */}
      {shareToast && (
        <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-60 rounded-lg bg-slate-700 px-4 py-2 text-sm text-slate-100 shadow-lg">
          {shareToast}
        </div>
      )}
    </div>
  );
}
