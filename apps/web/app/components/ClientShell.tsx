"use client";

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
