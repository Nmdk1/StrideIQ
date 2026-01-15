'use client';

/**
 * SignalsBanner Component
 * 
 * Displays high-confidence analytics signals on the Home page glance layer.
 * Aggregates insights from: TSB, Efficiency, Critical Speed, Fingerprinting, Pace Decay.
 * 
 * ADR-013: Home Glance Signals Integration
 * 
 * TONE: Sparse, direct, data-driven. No prescriptiveness.
 */

import React from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  TrendingUp, 
  TrendingDown, 
  Battery, 
  BatteryLow,
  Target,
  Zap,
  AlertTriangle,
  CheckCircle2,
  Gauge,
  Timer,
  ChevronRight,
  Sparkles
} from 'lucide-react';
import { apiClient } from '@/lib/api/client';

// Signal interface matching backend
interface Signal {
  id: string;
  type: string;
  priority: number;
  confidence: string;
  icon: string;
  color: string;
  title: string;
  subtitle: string;
  detail?: string;
  action_url?: string;
}

interface SignalsResponse {
  signals: Signal[];
  suppressed_count: number;
  last_updated: string;
}

// Icon mapping
const ICON_MAP: Record<string, React.ReactNode> = {
  trending_up: <TrendingUp className="w-4 h-4" />,
  trending_down: <TrendingDown className="w-4 h-4" />,
  battery_full: <Battery className="w-4 h-4" />,
  battery_low: <BatteryLow className="w-4 h-4" />,
  target: <Target className="w-4 h-4" />,
  zap: <Zap className="w-4 h-4" />,
  alert: <AlertTriangle className="w-4 h-4" />,
  check: <CheckCircle2 className="w-4 h-4" />,
  gauge: <Gauge className="w-4 h-4" />,
  timer: <Timer className="w-4 h-4" />,
};

// Color mapping for Tailwind
const COLOR_MAP: Record<string, { bg: string; text: string; border: string; ring: string }> = {
  green: {
    bg: 'bg-green-500/20',
    text: 'text-green-400',
    border: 'border-green-500/30',
    ring: 'ring-green-500/30'
  },
  emerald: {
    bg: 'bg-emerald-500/20',
    text: 'text-emerald-400',
    border: 'border-emerald-500/30',
    ring: 'ring-emerald-500/30'
  },
  blue: {
    bg: 'bg-blue-500/20',
    text: 'text-blue-400',
    border: 'border-blue-500/30',
    ring: 'ring-blue-500/30'
  },
  orange: {
    bg: 'bg-orange-500/20',
    text: 'text-orange-400',
    border: 'border-orange-500/30',
    ring: 'ring-orange-500/30'
  },
  red: {
    bg: 'bg-red-500/20',
    text: 'text-red-400',
    border: 'border-red-500/30',
    ring: 'ring-red-500/30'
  },
  purple: {
    bg: 'bg-purple-500/20',
    text: 'text-purple-400',
    border: 'border-purple-500/30',
    ring: 'ring-purple-500/30'
  },
  yellow: {
    bg: 'bg-yellow-500/20',
    text: 'text-yellow-400',
    border: 'border-yellow-500/30',
    ring: 'ring-yellow-500/30'
  },
};

// Fetch signals from API
async function fetchSignals(): Promise<SignalsResponse> {
  return apiClient.get<SignalsResponse>('/home/signals');
}

// Confidence badge component
function ConfidenceBadge({ confidence }: { confidence: string }) {
  if (confidence === 'high') {
    return (
      <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-emerald-500/40 text-emerald-400">
        High
      </Badge>
    );
  }
  return null; // Don't show badge for moderate
}

// Single signal card
function SignalCard({ signal }: { signal: Signal }) {
  const colors = COLOR_MAP[signal.color] || COLOR_MAP.blue;
  const icon = ICON_MAP[signal.icon] || <Sparkles className="w-4 h-4" />;
  
  const content = (
    <Card className={`
      bg-slate-800/50 border-slate-700/50 hover:border-slate-600 
      transition-all duration-200 hover:scale-[1.02] cursor-pointer
      animate-in fade-in slide-in-from-bottom-2 duration-300
    `}>
      <CardContent className="py-3 px-4">
        <div className="flex items-start gap-3">
          <div className={`p-2 rounded-lg ${colors.bg} ring-1 ${colors.ring} flex-shrink-0`}>
            <span className={colors.text}>{icon}</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className={`font-semibold text-sm ${colors.text}`}>
                {signal.title}
              </span>
              <ConfidenceBadge confidence={signal.confidence} />
            </div>
            <p className="text-xs text-slate-400 truncate">
              {signal.subtitle}
            </p>
            {signal.detail && (
              <p className="text-[10px] text-slate-500 mt-1 font-mono">
                {signal.detail}
              </p>
            )}
          </div>
          <ChevronRight className="w-4 h-4 text-slate-500 flex-shrink-0 mt-1" />
        </div>
      </CardContent>
    </Card>
  );
  
  if (signal.action_url) {
    return (
      <Link href={signal.action_url} className="block">
        {content}
      </Link>
    );
  }
  
  return content;
}

// Main SignalsBanner component
export function SignalsBanner() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['home-signals'],
    queryFn: fetchSignals,
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
  });
  
  // Don't render anything while loading or on error (fail silently)
  if (isLoading || error || !data) {
    return null;
  }
  
  // Don't render if no signals
  if (data.signals.length === 0) {
    return null;
  }
  
  return (
    <section className="animate-in fade-in duration-500">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-4 h-4 text-orange-500" />
        <span className="text-sm font-semibold text-slate-300">Signals</span>
        <span className="text-xs text-slate-500">
          ({data.signals.length} insight{data.signals.length !== 1 ? 's' : ''})
        </span>
      </div>
      
      {/* Grid for signals - 1 column on mobile, 2 on larger screens */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {data.signals.map((signal, index) => (
          <div 
            key={signal.id}
            style={{ animationDelay: `${index * 100}ms` }}
          >
            <SignalCard signal={signal} />
          </div>
        ))}
      </div>
      
      {/* Show suppressed count if any */}
      {data.suppressed_count > 0 && (
        <p className="text-xs text-slate-600 mt-2 text-center">
          +{data.suppressed_count} more available in Analytics
        </p>
      )}
    </section>
  );
}

export default SignalsBanner;
