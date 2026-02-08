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
  const { data: status } = useStravaStatus();
  const sync = useTriggerStravaSync();
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return;
    if (!isAuthenticated) return; // not logged in yet
    if (!status) return; // still loading
    if (!status.connected) return; // not connected

    const lastSync = status.last_sync ? new Date(status.last_sync).getTime() : 0;
    const age = Date.now() - lastSync;

    if (age > STALE_THRESHOLD_MS) {
      fired.current = true;
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
