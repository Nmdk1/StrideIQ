'use client';

import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api/client';
import { clearQueryCache } from '@/lib/providers/QueryProvider';

type ImpersonatedUser = { id: string; email?: string | null; display_name?: string | null } | null;

export function ImpersonationBanner() {
  const [active, setActive] = useState(false);
  const [user, setUser] = useState<ImpersonatedUser>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const isActive = localStorage.getItem('impersonation_active') === 'true';
    if (!isActive) return;

    const token = localStorage.getItem('impersonation_token');
    if (!token) return;

    setActive(true);
    setExpiresAt(localStorage.getItem('impersonation_expires_at'));
    try {
      const raw = localStorage.getItem('impersonated_user');
      if (raw) setUser(JSON.parse(raw));
    } catch {
      // ignore
    }
  }, []);

  if (!active) return null;

  const label = user?.email || user?.display_name || user?.id || 'unknown user';

  const stop = () => {
    if (typeof window === 'undefined') return;

    const original = localStorage.getItem('impersonation_original_auth_token');
    if (original) {
      localStorage.setItem('auth_token', original);
    } else {
      localStorage.removeItem('auth_token');
    }

    // Clear impersonation artifacts
    localStorage.removeItem('impersonation_active');
    localStorage.removeItem('impersonation_token');
    localStorage.removeItem('impersonation_expires_at');
    localStorage.removeItem('impersonated_user');
    localStorage.removeItem('impersonation_original_auth_token');

    // Force API client to pick up restored token and clear cached queries.
    apiClient.setAuthToken(original);
    clearQueryCache();

    if (process.env.NODE_ENV !== 'test') {
      window.location.reload();
    }
  };

  return (
    <div className="w-full bg-amber-600 text-slate-950 border-b border-amber-500">
      <div className="max-w-7xl mx-auto px-4 py-2 flex items-center justify-between gap-3">
        <div className="text-sm font-semibold">
          Impersonation active: <span className="font-mono">{label}</span>
          {expiresAt ? <span className="ml-2 text-xs font-normal opacity-90">(expires {expiresAt})</span> : null}
        </div>
        <button
          onClick={stop}
          className="px-3 py-1 rounded bg-slate-950/20 hover:bg-slate-950/30 text-sm font-semibold"
        >
          Stop impersonating
        </button>
      </div>
    </div>
  );
}

