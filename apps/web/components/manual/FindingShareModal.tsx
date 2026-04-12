'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import {
  findingShareCaption,
  renderFindingShareCardPng,
  type FindingShareCardInput,
} from '@/components/manual/findingShareCanvas';
import { sendToolTelemetry } from '@/lib/hooks/useToolTelemetry';

export type FindingShareTelemetryType =
  | 'race_character'
  | 'cascade_story'
  | 'highlighted_finding';

export interface FindingShareModalProps {
  open: boolean;
  onClose: () => void;
  card: FindingShareCardInput;
  findingType: FindingShareTelemetryType;
  /** Stable id for cascade/highlighted; omit for race character */
  findingRef?: string;
}

export function FindingShareModal({
  open,
  onClose,
  card,
  findingType,
  findingRef,
}: FindingShareModalProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const blobRef = useRef<Blob | null>(null);
  const cardKeyRef = useRef<string>('');

  const metaBase = {
    finding_type: findingType,
    ...(findingRef ? { finding_ref: findingRef } : {}),
  };

  const manualPath = { path: '/manual' as const };

  const regenerate = useCallback(async () => {
    setGenerating(true);
    try {
      const blob = await renderFindingShareCardPng(card);
      blobRef.current = blob;
      const url = URL.createObjectURL(blob);
      setPreviewUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return url;
      });
    } catch {
      setToast('Could not create image — try again.');
    } finally {
      setGenerating(false);
    }
  }, [card]);

  useEffect(() => {
    if (!open) {
      setPreviewUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
      blobRef.current = null;
      cardKeyRef.current = '';
      return;
    }
    const key = JSON.stringify(card);
    if (cardKeyRef.current === key) return;
    cardKeyRef.current = key;
    void regenerate();
  }, [open, card, regenerate]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const handleShare = async () => {
    const blob = blobRef.current;
    if (!blob) {
      setToast('Image not ready yet.');
      return;
    }
    const file = new File([blob], 'strideiq-finding.png', { type: 'image/png' });
    const caption = findingShareCaption();

    try {
      if (typeof navigator.share === 'function' && navigator.canShare?.({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: 'StrideIQ finding',
          text: caption,
        });
        void sendToolTelemetry('finding_share_completed', metaBase, manualPath);
      } else {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'strideiq-finding.png';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        await navigator.clipboard.writeText(caption).catch(() => {});
        setToast('Image saved — paste the link wherever you share');
        void sendToolTelemetry('finding_share_completed', metaBase, manualPath);
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setToast('Share failed — try Save instead.');
      }
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center bg-black/70 px-4 py-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="finding-share-title"
    >
      <div className="w-full max-w-md rounded-2xl border border-slate-600 bg-[#141c2e] shadow-xl overflow-hidden flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/80">
          <h2 id="finding-share-title" className="text-sm font-semibold text-white">
            Share finding
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/80"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col items-center gap-4">
          <div
            className="relative w-full max-w-[280px] rounded-xl overflow-hidden bg-slate-900 border border-slate-700"
            style={{ aspectRatio: '1080 / 1350' }}
          >
            {generating && (
              <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80 z-10">
                <span className="text-xs text-slate-400">Preparing image…</span>
              </div>
            )}
            {previewUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={previewUrl} alt="Share preview" className="w-full h-full object-contain" />
            )}
          </div>
          <p className="text-xs text-slate-500 text-center leading-relaxed">
            Share cards link to StrideIQ free tools — no raw metrics or personal details on the
            image.
          </p>
        </div>

        <div className="px-4 pb-4 flex flex-col gap-2 border-t border-slate-700/80 pt-3">
          <button
            type="button"
            onClick={() => void handleShare()}
            disabled={generating || !previewUrl}
            className="w-full py-3 rounded-xl bg-orange-500 hover:bg-orange-400 disabled:opacity-50 text-white text-sm font-semibold"
          >
            Share or save image
          </button>
          {toast && <p className="text-xs text-amber-400/90 text-center">{toast}</p>}
        </div>
      </div>
    </div>
  );
}
