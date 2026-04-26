'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';

const TOOL_PAGE_VIEW_DEDUPE_MS = 2500;
const recentToolPageViews = new Map<string, number>();

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

export type ToolFunnelEventType = 'tool_page_view' | 'tool_result_view' | 'signup_cta_click';

/**
 * First-party funnel events for public tools (and signup CTAs that include pathname).
 * Optional Bearer token correlates logged-in athletes; anonymous traffic is stored with athlete_id null.
 */
export async function sendToolTelemetry(
  eventType: ToolFunnelEventType,
  extra?: Record<string, unknown>,
): Promise<void> {
  if (typeof window === 'undefined') return;
  const path = window.location.pathname;
  try {
    const baseUrl = await getBaseUrl();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    const metadata =
      extra && Object.keys(extra).length > 0 ? (extra as Record<string, unknown>) : null;
    await fetch(`${baseUrl}/v1/telemetry/tool-event`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        event_type: eventType,
        path,
        metadata,
      }),
    });
  } catch {
    // fire-and-forget
  }
}

function shouldSendToolPageView(pathname: string): boolean {
  const now = Date.now();
  const last = recentToolPageViews.get(pathname) ?? 0;
  if (now - last < TOOL_PAGE_VIEW_DEDUPE_MS) return false;
  recentToolPageViews.set(pathname, now);
  return true;
}

/** One tool_page_view per navigation to a /tools URL (deduped across React Strict Mode remounts). */
export function useToolPageViewTelemetry(): void {
  const pathname = usePathname();
  useEffect(() => {
    if (!pathname?.startsWith('/tools')) return;
    if (!shouldSendToolPageView(pathname)) return;
    void sendToolTelemetry('tool_page_view');
  }, [pathname]);
}
