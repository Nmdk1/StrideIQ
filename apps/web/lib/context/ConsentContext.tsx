'use client';

/**
 * ConsentContext — AI processing consent state for the entire app.
 *
 * Fetches GET /v1/consent/ai once on auth, exposes grantConsent / revokeConsent,
 * and re-fetches after every mutation so all consumers stay in sync.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/hooks/useAuth';
import { apiClient } from '@/lib/api/client';

interface ConsentData {
  ai_consent: boolean;
  granted_at: string | null;
  revoked_at: string | null;
}

interface ConsentContextValue {
  /** null = not yet loaded; boolean = loaded value */
  aiConsent: boolean | null;
  grantedAt: string | null;
  revokedAt: string | null;
  loading: boolean;
  grantConsent: () => Promise<void>;
  revokeConsent: () => Promise<void>;
  refetch: () => Promise<void>;
}

const ConsentContext = createContext<ConsentContextValue>({
  aiConsent: null,
  grantedAt: null,
  revokedAt: null,
  loading: false,
  grantConsent: async () => {},
  revokeConsent: async () => {},
  refetch: async () => {},
});

export function ConsentProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [aiConsent, setAiConsent] = useState<boolean | null>(null);
  const [grantedAt, setGrantedAt] = useState<string | null>(null);
  const [revokedAt, setRevokedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refetch = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const data = await apiClient.get<ConsentData>('/v1/consent/ai');
      setAiConsent(data.ai_consent);
      setGrantedAt(data.granted_at);
      setRevokedAt(data.revoked_at);
    } catch {
      // Fail-open: don't block UI if consent fetch fails.
      // Treat as unknown (null) — prompt will not show.
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      refetch();
    } else {
      setAiConsent(null);
      setGrantedAt(null);
      setRevokedAt(null);
    }
  }, [isAuthenticated, refetch]);

  const grantConsent = useCallback(async () => {
    await apiClient.post('/v1/consent/ai', { granted: true });
    await refetch();
  }, [refetch]);

  const revokeConsent = useCallback(async () => {
    await apiClient.post('/v1/consent/ai', { granted: false });
    await refetch();
  }, [refetch]);

  return (
    <ConsentContext.Provider
      value={{ aiConsent, grantedAt, revokedAt, loading, grantConsent, revokeConsent, refetch }}
    >
      {children}
    </ConsentContext.Provider>
  );
}

export function useConsent(): ConsentContextValue {
  return useContext(ConsentContext);
}
