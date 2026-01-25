/**
 * Garmin File Import Component (Phase 7)
 *
 * Upload a Garmin export ZIP and track import jobs.
 * Feature is gated server-side by `integrations.garmin_file_import_v1`.
 */

'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API_CONFIG } from '@/lib/api/config';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Watch, Upload, RefreshCw } from 'lucide-react';

type ImportJob = {
  id: string;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  provider: string;
  status: 'queued' | 'running' | 'success' | 'error' | string;
  original_filename?: string | null;
  file_size_bytes?: number | null;
  stats?: any;
  error?: string | null;
};

function formatBytes(bytes?: number | null) {
  if (!bytes || bytes <= 0) return null;
  const units = ['B', 'KB', 'MB', 'GB'];
  let v = bytes;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function GarminFileImport() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const token = useMemo(() => (typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null), []);

  const fetchJobs = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_CONFIG.baseURL}/v1/imports/jobs?provider=garmin&limit=10`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (resp.status === 403) {
        setEnabled(false);
        setJobs([]);
        return;
      }
      if (!resp.ok) {
        setEnabled(true);
        setError('Failed to load import jobs.');
        return;
      }
      setEnabled(true);
      const data = await resp.json();
      setJobs(Array.isArray(data?.jobs) ? data.jobs : []);
    } catch (e) {
      setEnabled(true);
      setError('Failed to load import jobs.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  const handleUpload = async (file: File) => {
    if (!token) return;
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const resp = await fetch(`${API_CONFIG.baseURL}/v1/imports/garmin/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (resp.status === 403) {
        setEnabled(false);
        return;
      }
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        setEnabled(true);
        setError(body?.detail || 'Upload failed.');
        return;
      }
      setEnabled(true);
      await fetchJobs();
    } catch (e) {
      setEnabled(true);
      setError('Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card className="bg-slate-700/50 border-slate-600">
      <CardContent className="py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-slate-600/50 rounded-lg">
              <Watch className="w-5 h-5 text-slate-200" />
            </div>
            <div>
              <p className="font-medium text-slate-200">Garmin (file import)</p>
              <p className="text-sm text-slate-400">
                Upload your Garmin export ZIP. We import activities asynchronously.
              </p>
            </div>
          </div>

          {enabled === false ? (
            <Badge variant="outline" className="text-slate-400 border-slate-500">
              Coming Soon
            </Badge>
          ) : (
            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip"
                className="sr-only"
                disabled={uploading}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleUpload(f);
                  e.currentTarget.value = '';
                }}
              />

              <Button
                type="button"
                variant="secondary"
                className="bg-slate-900 border border-slate-600 hover:bg-slate-800"
                disabled={loading}
                onClick={fetchJobs}
              >
                {loading ? (
                  <>
                    <LoadingSpinner size="sm" className="mr-2" />
                    Refresh
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Refresh
                  </>
                )}
              </Button>

              <Button
                type="button"
                disabled={uploading}
                className="bg-orange-600 hover:bg-orange-700"
                onClick={() => fileInputRef.current?.click()}
              >
                {uploading ? (
                  <>
                    <LoadingSpinner size="sm" className="mr-2" />
                    Uploading…
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4 mr-2" />
                    Upload ZIP
                  </>
                )}
              </Button>
            </div>
          )}
        </div>

        {enabled !== false && (
          <div className="mt-4">
            {error && <div className="text-sm text-red-400">{error}</div>}
            {loading && jobs.length === 0 ? (
              <div className="text-sm text-slate-400 flex items-center gap-2">
                <LoadingSpinner size="sm" />
                Loading recent imports…
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-sm text-slate-400">No Garmin imports yet.</div>
            ) : (
              <div className="space-y-2">
                {jobs.map((j) => (
                  <div key={j.id} className="flex items-center justify-between rounded-md border border-slate-600 bg-slate-900/40 px-3 py-2">
                    <div className="min-w-0">
                      <div className="text-sm text-slate-200 truncate">
                        {j.original_filename || 'garmin_export.zip'}{' '}
                        {j.file_size_bytes ? <span className="text-slate-400">({formatBytes(j.file_size_bytes)})</span> : null}
                      </div>
                      <div className="text-xs text-slate-500">
                        {new Date(j.created_at).toLocaleString()}
                        {j.stats?.created != null ? ` • ${j.stats.created} created` : ''}
                        {j.stats?.already_present != null ? ` • ${j.stats.already_present} already` : ''}
                        {j.stats?.skipped_possible_duplicate != null ? ` • ${j.stats.skipped_possible_duplicate} dup-skipped` : ''}
                      </div>
                      {j.status === 'error' && j.error ? (
                        <div className="text-xs text-red-400 mt-1 truncate">{j.error}</div>
                      ) : null}
                    </div>
                    <Badge
                      variant="outline"
                      className={
                        j.status === 'success'
                          ? 'border-green-700 text-green-400'
                          : j.status === 'error'
                            ? 'border-red-700 text-red-400'
                            : j.status === 'running'
                              ? 'border-blue-700 text-blue-400'
                              : 'border-slate-600 text-slate-300'
                      }
                    >
                      {j.status}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

