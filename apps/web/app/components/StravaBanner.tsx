"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/hooks/useAuth";
import { useStravaStatus } from "@/lib/hooks/queries/strava";
import { stravaService } from "@/lib/api/services/strava";
import { AlertTriangle } from "lucide-react";

/** Routes where the banner should NOT appear */
const HIDDEN_ROUTES = [
  "/",
  "/login",
  "/register",
  "/onboarding",
  "/about",
  "/mission",
  "/privacy",
  "/terms",
  "/support",
];

export default function StravaBanner() {
  const pathname = usePathname();
  const { isAuthenticated } = useAuth();
  const { data: status } = useStravaStatus();
  const [connecting, setConnecting] = useState(false);

  const shouldHide = HIDDEN_ROUTES.some(
    (r) => pathname === r || pathname?.startsWith(`${r}/`)
  );

  if (!isAuthenticated || shouldHide) return null;
  // Only show when we have status data and Strava is NOT connected
  if (!status || status.connected) return null;

  const handleReconnect = async () => {
    setConnecting(true);
    try {
      const { auth_url } = await stravaService.getAuthUrl(pathname || "/home");
      window.location.href = auth_url;
    } catch {
      setConnecting(false);
    }
  };

  return (
    <div className="bg-amber-900/30 border-b border-amber-800/50 px-4 py-2.5">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-amber-200 text-sm">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>Strava disconnected</span>
        </div>
        <button
          onClick={handleReconnect}
          disabled={connecting}
          className="px-3 py-1 rounded-lg text-xs font-semibold bg-orange-600 hover:bg-orange-700 
                     text-white transition-colors disabled:opacity-50 flex-shrink-0"
        >
          {connecting ? "Connecting..." : "Reconnect Now"}
        </button>
      </div>
    </div>
  );
}
