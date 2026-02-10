"use client";

import { useEffect, useRef } from "react";
import { useAuth } from "./useAuth";
import { useStravaStatus, useTriggerStravaSync } from "./queries/strava";
import { toast } from "sonner";

/**
 * Auto-sync hook: fires a Strava sync on page load when:
 *  1. User is authenticated
 *  2. Strava is connected
 *  3. last_sync is older than STALE_THRESHOLD (4 hours) or null
 *
 * Runs once per mount (guarded by ref). Shows toast feedback.
 */
const STALE_THRESHOLD_MS = 4 * 60 * 60 * 1000; // 4 hours

export function useAutoSync() {
  const { isAuthenticated } = useAuth();
  const { data: status, refetch: refetchStatus } = useStravaStatus();
  const sync = useTriggerStravaSync();
  const attemptedForSyncKey = useRef<string | null>(null);

  // If user returns after hours, force a fresh status read before deciding.
  useEffect(() => {
    const onFocus = () => {
      refetchStatus();
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        refetchStatus();
      }
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [refetchStatus]);

  useEffect(() => {
    if (!isAuthenticated) return; // not logged in yet
    if (!status) return; // still loading
    if (!status.connected) return; // not connected

    const syncKey = status.last_sync || "none";
    if (attemptedForSyncKey.current === syncKey) return;

    const parsedLastSync = status.last_sync ? new Date(status.last_sync).getTime() : 0;
    const lastSync = Number.isFinite(parsedLastSync) ? parsedLastSync : 0;
    const age = Date.now() - lastSync;

    if (age > STALE_THRESHOLD_MS) {
      attemptedForSyncKey.current = syncKey;
      sync.mutate(undefined, {
        onSuccess: () => {
          toast.success("Strava synced", {
            description: "Your latest activities have been imported.",
          });
        },
        onError: () => {
          toast.error("Strava sync failed", {
            description: "We'll try again next time you visit.",
          });
        },
      });
    }
  }, [isAuthenticated, status, sync]);
}
