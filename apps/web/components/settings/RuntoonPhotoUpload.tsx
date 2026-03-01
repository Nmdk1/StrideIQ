'use client';

/**
 * RuntoonPhotoUpload — Settings panel for managing Runtoon reference photos.
 *
 * Placed at /settings#runtoon.
 *
 * Responsibilities:
 * - List existing photos with delete option
 * - Upload new photos (with consent gate)
 * - Show photo count / min-3 / max-10 guidance
 *
 * Privacy:
 * - All photos are displayed via 15-min signed URLs (never raw storage keys)
 * - Consent is collected before each upload batch
 */

import React, { useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';
import { Upload, Trash2, Image as ImageIcon, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Photo {
  id: string;
  photo_type: string;
  mime_type: string;
  size_bytes: number;
  signed_url: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PHOTO_TYPES = [
  { value: 'face', label: 'Face close-up' },
  { value: 'running', label: 'Running form' },
  { value: 'full_body', label: 'Full body' },
  { value: 'additional', label: 'Additional' },
];

const MAX_PHOTOS = 10;
const MIN_PHOTOS = 3;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RuntoonPhotoUpload() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedType, setSelectedType] = useState('face');
  const [consentChecked, setConsentChecked] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  // Fetch existing photos
  const { data: photos = [], isLoading } = useQuery<Photo[]>({
    queryKey: ['runtoon-photos'],
    queryFn: async () => {
      const res = await fetch(`${API_CONFIG.baseUrl}/v1/runtoon/photos`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 403) return [];  // Feature flag not enabled
      if (!res.ok) throw new Error('Failed to load photos');
      return res.json();
    },
    enabled: !!token,
    staleTime: 2 * 60 * 1000,
  });

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append('file', file);
      form.append('photo_type', selectedType);
      form.append('consent_given', 'true');

      const res = await fetch(`${API_CONFIG.baseUrl}/v1/runtoon/photos`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Upload failed.');
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runtoon-photos'] });
      setUploadError(null);
      setUploadSuccess(true);
      setTimeout(() => setUploadSuccess(false), 3000);
    },
    onError: (err: Error) => {
      setUploadError(err.message);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (photoId: string) => {
      const res = await fetch(`${API_CONFIG.baseUrl}/v1/runtoon/photos/${photoId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Delete failed.');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runtoon-photos'] });
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError(null);

    if (!consentChecked) {
      setUploadError('Please confirm your consent before uploading.');
      return;
    }

    uploadMutation.mutate(file);
    e.target.value = '';  // reset so same file can be re-selected
  };

  const canUpload = photos.length < MAX_PHOTOS && consentChecked && !uploadMutation.isPending;
  const hasEnough = photos.length >= MIN_PHOTOS;

  return (
    <div id="runtoon" className="space-y-4">
      {/* Status bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-300 font-medium">
            {photos.length} / {MAX_PHOTOS} photos
          </span>
          {hasEnough ? (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
              <CheckCircle className="w-3 h-3" /> Runtoon ready
            </span>
          ) : (
            <span className="text-xs text-slate-500">
              {MIN_PHOTOS - photos.length} more needed
            </span>
          )}
        </div>
      </div>

      {/* Existing photos grid */}
      {isLoading ? (
        <div className="flex items-center gap-2 text-slate-400 text-sm py-4">
          <Loader2 className="w-4 h-4 animate-spin" />
          Loading photos…
        </div>
      ) : photos.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-700 p-6 text-center">
          <ImageIcon className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <p className="text-sm text-slate-400">
            No photos yet. Upload at least {MIN_PHOTOS} to enable Runtoon.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          {photos.map((photo) => (
            <div key={photo.id} className="relative group rounded-md overflow-hidden aspect-square bg-slate-800">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={photo.signed_url}
                alt={photo.photo_type}
                className="w-full h-full object-cover"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-1.5 gap-1">
                <span className="text-xs text-slate-300 flex-1 truncate">{photo.photo_type}</span>
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(photo.id)}
                  disabled={deleteMutation.isPending}
                  className="p-1 rounded bg-red-500/80 hover:bg-red-500 text-white transition-colors"
                  aria-label="Delete photo"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload form */}
      {photos.length < MAX_PHOTOS && (
        <div className="space-y-3 pt-1">
          {/* Type selector */}
          <div className="flex flex-wrap gap-2">
            {PHOTO_TYPES.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setSelectedType(t.value)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  selectedType === t.value
                    ? 'bg-orange-500 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Consent checkbox */}
          <label className="flex items-start gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={consentChecked}
              onChange={(e) => setConsentChecked(e.target.checked)}
              className="mt-0.5 rounded border-slate-600 bg-slate-700 text-orange-500 focus:ring-orange-500"
            />
            <span className="text-xs text-slate-400 leading-relaxed">
              I consent to these photos being used by StrideIQ to generate personalized
              caricature images. Photos are stored privately and never shared.
            </span>
          </label>

          {/* Upload button */}
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={handleFileChange}
            />
            <button
              type="button"
              disabled={!canUpload}
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-md text-sm font-medium text-slate-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploadMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Upload className="w-4 h-4" />
              )}
              {uploadMutation.isPending ? 'Uploading…' : 'Choose photo'}
            </button>
            <p className="text-xs text-slate-500 mt-1.5">
              JPEG, PNG, or WebP · Max 7 MB
            </p>
          </div>

          {/* Feedback */}
          {uploadError && (
            <div className="flex items-start gap-1.5 text-xs text-red-400">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              {uploadError}
            </div>
          )}
          {uploadSuccess && (
            <div className="flex items-center gap-1.5 text-xs text-emerald-400">
              <CheckCircle className="w-3.5 h-3.5" />
              Photo uploaded successfully.
            </div>
          )}
        </div>
      )}

      {photos.length >= MAX_PHOTOS && (
        <p className="text-xs text-slate-500">
          Maximum {MAX_PHOTOS} photos reached. Delete one to add another.
        </p>
      )}
    </div>
  );
}
