"use client";

import BottomTabs from "./BottomTabs";
import StravaBanner from "./StravaBanner";
import { useAutoSync } from "@/lib/hooks/useAutoSync";
import { Toaster } from "sonner";

/**
 * Client-side shell that wraps every page.
 * Houses auto-sync, toaster, bottom tabs, and Strava banner.
 */
export default function ClientShell({
  children,
}: {
  children: React.ReactNode;
}) {
  useAutoSync();

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
