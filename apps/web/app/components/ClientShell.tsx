"use client";

import { useEffect } from "react";
import BottomTabs from "./BottomTabs";
import StravaBanner from "./StravaBanner";
import { useAutoSync } from "@/lib/hooks/useAutoSync";
import { usePageTracking } from "@/lib/hooks/usePageTracking";
import { useToolPageViewTelemetry } from "@/lib/hooks/useToolTelemetry";
import { Toaster } from "sonner";

/**
 * Client-side shell that wraps every page.
 * Houses auto-sync, toaster, bottom tabs, Strava banner, and page tracking.
 */
export default function ClientShell({
  children,
}: {
  children: React.ReactNode;
}) {
  useAutoSync();
  usePageTracking();
  useToolPageViewTelemetry();

  // Ensure no residual orientation lock (e.g. after PWA / fullscreen). Harmless if unsupported.
  useEffect(() => {
    try {
      const o = screen.orientation;
      if (o && typeof o.unlock === "function") {
        void o.unlock();
      }
    } catch {
      /* iOS may throw; ignore */
    }
  }, []);

  return (
    <>
      <Toaster
        position="top-center"
        richColors
        toastOptions={{
          className: "!bg-slate-800 !text-slate-100 !border-slate-700",
        }}
      />
      <StravaBanner />
      {children}
      <BottomTabs />
    </>
  );
}
