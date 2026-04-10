'use client';

import { useEffect, useRef, useCallback } from 'react';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/hooks/useAuth';

const SCREEN_MAP: Record<string, string> = {
  '/home': 'home',
  '/calendar': 'calendar',
  '/manual': 'manual',
  '/coach': 'coach',
  '/progress': 'progress',
  '/analytics': 'analytics',
  '/training-load': 'training_load',
  '/nutrition': 'nutrition',
  '/reports': 'reports',
  '/settings': 'settings',
  '/fingerprint': 'fingerprint',
  '/trends': 'trends',
  '/activities': 'activities',
  '/discover': 'discover',
  '/onboarding': 'onboarding',
  '/checkin': 'checkin',
  '/compare': 'compare',
  '/personal-bests': 'personal_bests',
};

const UNAUTHENTICATED_ROUTES = ['/', '/login', '/register', '/about', '/mission', '/privacy', '/terms', '/support', '/forgot-password', '/reset-password'];

function resolveScreen(pathname: string): string | null {
  if (UNAUTHENTICATED_ROUTES.some((r) => pathname === r || pathname.startsWith(`${r}/`))) {
    return null;
  }
  if (SCREEN_MAP[pathname]) return SCREEN_MAP[pathname];
  if (pathname.startsWith('/activities/')) return 'activity_detail';
  if (pathname.startsWith('/plans/create')) return 'plan_create';
  if (pathname.startsWith('/plans/')) return 'plan_detail';
  if (pathname.startsWith('/tools/')) return 'tools';
  return pathname.replace(/^\//, '').replace(/\//g, '_') || 'home';
}

function extractMetadata(pathname: string): Record<string, string> | undefined {
  if (pathname.startsWith('/activities/')) {
    const id = pathname.split('/')[2];
    if (id) return { activity_id: id };
  }
  return undefined;
}

let apiBaseUrl: string | null = null;

async function getBaseUrl(): Promise<string> {
  if (apiBaseUrl) return apiBaseUrl;
  const { API_CONFIG } = await import('@/lib/api/config');
  apiBaseUrl = API_CONFIG.baseURL;
  return apiBaseUrl;
}

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('auth_token');
}

async function postPageView(
  screen: string,
  referrerScreen: string | null,
  metadata?: Record<string, string>,
): Promise<string | null> {
  try {
    const token = getToken();
    if (!token) return null;
    const baseUrl = await getBaseUrl();
    const res = await fetch(`${baseUrl}/v1/telemetry/page-view`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        screen,
        referrer_screen: referrerScreen,
        metadata: metadata || null,
      }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.id || null;
  } catch {
    return null;
  }
}

function sendExit(pageViewId: string): void {
  try {
    const token = getToken();
    if (!token || !apiBaseUrl) return;
    const url = `${apiBaseUrl}/v1/telemetry/page-view/${pageViewId}/exit`;
    const body = JSON.stringify({});
    const headers = {
      type: 'application/json',
    };
    const blob = new Blob([body], headers);
    if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
      const beaconUrl = `${url}?token=${token}`;
      navigator.sendBeacon(beaconUrl, blob);
    }
    fetch(url, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body,
      keepalive: true,
    }).catch(() => {});
  } catch {
    // fire-and-forget
  }
}

export function usePageTracking(): void {
  const pathname = usePathname();
  const { user } = useAuth();
  const currentViewId = useRef<string | null>(null);
  const previousScreen = useRef<string | null>(null);

  const exitCurrent = useCallback(() => {
    if (currentViewId.current) {
      sendExit(currentViewId.current);
      currentViewId.current = null;
    }
  }, []);

  useEffect(() => {
    if (!user || !pathname) return;

    const screen = resolveScreen(pathname);
    if (!screen) return;

    exitCurrent();

    const metadata = extractMetadata(pathname);
    postPageView(screen, previousScreen.current, metadata).then((id) => {
      currentViewId.current = id;
    });
    previousScreen.current = screen;
  }, [pathname, user, exitCurrent]);

  useEffect(() => {
    if (!user) return;

    const handleBeforeUnload = () => {
      exitCurrent();
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        exitCurrent();
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      exitCurrent();
    };
  }, [user, exitCurrent]);
}
