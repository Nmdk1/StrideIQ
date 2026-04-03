'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Sparkles, ArrowRight } from 'lucide-react';
import { useFirstInsights } from '@/lib/hooks/queries/first-insights';

const DISMISSED_KEY = 'strideiq_first_insights_seen';

export function FirstInsightsBanner() {
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    setDismissed(localStorage.getItem(DISMISSED_KEY) === '1');
  }, []);

  const { data } = useFirstInsights(!dismissed);

  if (dismissed || !data?.ready) return null;

  const count = (data.top_correlations?.length ?? 0) + (data.top_investigations?.length ?? 0);
  if (count === 0) return null;

  return (
    <Link
      href="/discover"
      onClick={() => {
        localStorage.setItem(DISMISSED_KEY, '1');
      }}
      className="flex items-center gap-3 rounded-xl border border-orange-500/20 bg-orange-950/20 px-4 py-3 transition-colors hover:bg-orange-950/30 group"
    >
      <Sparkles className="w-5 h-5 text-orange-400 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-200">
          We found patterns in your data
        </p>
        <p className="text-xs text-slate-500 mt-0.5">
          {data.activity_count?.toLocaleString()} activities analyzed · {data.correlation_count} patterns detected
        </p>
      </div>
      <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-orange-400 transition-colors flex-shrink-0" />
    </Link>
  );
}
