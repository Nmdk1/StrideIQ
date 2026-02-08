"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useRef, useEffect } from "react";
import {
  Home,
  MessageSquare,
  CalendarDays,
  TrendingUp,
  MoreHorizontal,
} from "lucide-react";

const TABS = [
  { href: "/home", label: "Home", icon: Home },
  { href: "/coach", label: "Coach", icon: MessageSquare },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/progress", label: "Progress", icon: TrendingUp },
] as const;

const MORE_ITEMS = [
  { href: "/activities", label: "Activities" },
  { href: "/nutrition", label: "Nutrition" },
  { href: "/checkin", label: "Check-in" },
  { href: "/tools", label: "Tools" },
  { href: "/insights", label: "Insights" },
  { href: "/settings", label: "Settings" },
];

/** Routes where bottom tabs should NOT appear */
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

export default function BottomTabs() {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  const sheetRef = useRef<HTMLDivElement>(null);

  // Close sheet on route change
  useEffect(() => {
    setMoreOpen(false);
  }, [pathname]);

  // Close on outside click
  useEffect(() => {
    if (!moreOpen) return;
    const handler = (e: MouseEvent | TouchEvent) => {
      if (sheetRef.current && !sheetRef.current.contains(e.target as Node)) {
        setMoreOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    document.addEventListener("touchstart", handler);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("touchstart", handler);
    };
  }, [moreOpen]);

  // Hide on public/unauthenticated routes
  const shouldHide = HIDDEN_ROUTES.some(
    (r) => pathname === r || pathname?.startsWith(`${r}/`)
  );
  if (shouldHide) return null;

  const isMoreActive =
    pathname === "/settings" ||
    MORE_ITEMS.some((item) => pathname === item.href);

  return (
    <>
      {/* Overlay for More sheet */}
      {moreOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 md:hidden"
          onClick={() => setMoreOpen(false)}
        />
      )}

      {/* More sheet (slides up from bottom) */}
      {moreOpen && (
        <div
          ref={sheetRef}
          className="fixed bottom-[calc(60px+env(safe-area-inset-bottom))] left-0 right-0 z-50 md:hidden
                     bg-slate-900 border-t border-slate-700 rounded-t-2xl shadow-2xl
                     animate-in slide-in-from-bottom-4 duration-200"
        >
          <div className="w-10 h-1 bg-slate-600 rounded-full mx-auto mt-3 mb-2" />
          <div className="px-4 pb-4 grid grid-cols-3 gap-2">
            {MORE_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center justify-center px-3 py-3 rounded-xl text-sm font-medium transition-colors ${
                  pathname === item.href
                    ? "bg-orange-600/20 text-orange-400"
                    : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Bottom tab bar */}
      <nav
        className="fixed bottom-0 left-0 right-0 z-40 md:hidden
                   bg-slate-900/95 backdrop-blur-sm border-t border-slate-800"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        <div className="flex items-center justify-around h-[60px]">
          {TABS.map((tab) => {
            const isActive = pathname === tab.href;
            const Icon = tab.icon;
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`flex flex-col items-center justify-center gap-0.5 w-full h-full transition-colors ${
                  isActive
                    ? "text-orange-500"
                    : "text-slate-500 active:text-slate-300"
                }`}
              >
                <Icon className="w-5 h-5" strokeWidth={isActive ? 2.5 : 2} />
                <span className="text-[10px] font-medium">{tab.label}</span>
              </Link>
            );
          })}

          {/* More tab */}
          <button
            type="button"
            onClick={() => setMoreOpen((v) => !v)}
            className={`flex flex-col items-center justify-center gap-0.5 w-full h-full transition-colors ${
              moreOpen || isMoreActive
                ? "text-orange-500"
                : "text-slate-500 active:text-slate-300"
            }`}
          >
            <MoreHorizontal
              className="w-5 h-5"
              strokeWidth={moreOpen || isMoreActive ? 2.5 : 2}
            />
            <span className="text-[10px] font-medium">More</span>
          </button>
        </div>
      </nav>
    </>
  );
}
