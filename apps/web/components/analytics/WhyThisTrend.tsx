'use client';

/**
 * WhyThisTrend Component
 * 
 * Button + Modal for explaining "Why This Trend?"
 * Fetches attribution data and displays ranked factors.
 * 
 * ADR-014: Why This Trend? Attribution Integration
 * 
 * TONE: Sparse, direct, non-prescriptive. "Data hints X. Test it."
 */

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { 
  HelpCircle, 
  TrendingUp, 
  TrendingDown,
  Minus,
  Info,
  Moon,
  Heart,
  Gauge,
  Activity,
  Utensils,
  Scale,
  Battery,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Sparkles
} from 'lucide-react';
import { apiClient } from '@/lib/api/client';

// Types matching backend
interface TrendSummary {
  metric: string;
  direction: string;
  change_percent: number;
  p_value: number | null;
  confidence: string;
  period_days: number;
}

interface Attribution {
  factor: string;
  label: string;
  contribution_pct: number;
  correlation: number;
  confidence: string;
  insight: string;
  sample_size: number;
  time_lag_days: number;
}

interface MethodContributions {
  efficiency_trending: boolean;
  tsb_analysis: boolean;
  critical_speed: boolean;
  fingerprinting: boolean;
  pace_decay: boolean;
}

interface TrendAttributionResponse {
  trend_summary: TrendSummary | null;
  attributions: Attribution[];
  method_contributions: MethodContributions;
  generated_at: string;
  message?: string;
}

// Props
interface WhyThisTrendProps {
  metric?: string;
  days?: number;
  buttonVariant?: 'default' | 'outline' | 'ghost' | 'link';
  buttonSize?: 'default' | 'sm' | 'lg' | 'icon';
  className?: string;
}

// Icon mapping for factors
const FACTOR_ICONS: Record<string, React.ReactNode> = {
  sleep_quality: <Moon className="w-4 h-4" />,
  sleep_duration: <Moon className="w-4 h-4" />,
  hrv: <Heart className="w-4 h-4" />,
  resting_hr: <Heart className="w-4 h-4" />,
  stress: <AlertCircle className="w-4 h-4" />,
  soreness: <Activity className="w-4 h-4" />,
  fatigue: <Battery className="w-4 h-4" />,
  mood: <Sparkles className="w-4 h-4" />,
  calories: <Utensils className="w-4 h-4" />,
  protein: <Utensils className="w-4 h-4" />,
  carbs: <Utensils className="w-4 h-4" />,
  hydration: <Utensils className="w-4 h-4" />,
  weight: <Scale className="w-4 h-4" />,
  bmi: <Scale className="w-4 h-4" />,
  weekly_mileage: <Activity className="w-4 h-4" />,
  consistency: <CheckCircle2 className="w-4 h-4" />,
  long_run_pct: <Activity className="w-4 h-4" />,
  easy_run_pct: <Activity className="w-4 h-4" />,
  intensity: <Gauge className="w-4 h-4" />,
  tsb: <Battery className="w-4 h-4" />,
  atl: <TrendingUp className="w-4 h-4" />,
  ctl: <TrendingUp className="w-4 h-4" />,
};

// Confidence badge styling
function ConfidenceBadge({ confidence }: { confidence: string }) {
  if (confidence === 'high') {
    return (
      <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/40 text-[10px]">
        High
      </Badge>
    );
  } else if (confidence === 'moderate') {
    return (
      <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/40 text-[10px]">
        Moderate
      </Badge>
    );
  } else {
    return (
      <Badge className="bg-slate-500/20 text-slate-400 border-slate-500/40 text-[10px]">
        Low
      </Badge>
    );
  }
}

// Trend direction indicator
function TrendDirection({ direction, changePercent }: { direction: string; changePercent: number }) {
  if (direction === 'improving') {
    return (
      <div className="flex items-center gap-1 text-emerald-400">
        <TrendingUp className="w-5 h-5" />
        <span className="font-semibold">+{changePercent.toFixed(1)}%</span>
      </div>
    );
  } else if (direction === 'declining') {
    return (
      <div className="flex items-center gap-1 text-orange-400">
        <TrendingDown className="w-5 h-5" />
        <span className="font-semibold">-{changePercent.toFixed(1)}%</span>
      </div>
    );
  } else {
    return (
      <div className="flex items-center gap-1 text-slate-400">
        <Minus className="w-5 h-5" />
        <span className="font-semibold">Stable</span>
      </div>
    );
  }
}

// Single attribution card
function AttributionCard({ attribution, rank }: { attribution: Attribution; rank: number }) {
  const icon = FACTOR_ICONS[attribution.factor] || <Info className="w-4 h-4" />;
  const isPositive = attribution.correlation > 0;
  
  return (
    <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-700/50 hover:border-slate-600 transition-all">
      <div className="flex items-start gap-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-full bg-slate-700/50 text-slate-400 font-bold text-sm">
          {rank}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-slate-400">{icon}</span>
            <span className="font-medium text-slate-200">{attribution.label}</span>
            <ConfidenceBadge confidence={attribution.confidence} />
          </div>
          
          <div className="flex items-center gap-4 mb-2 text-sm">
            <span className={`font-semibold ${isPositive ? 'text-emerald-400' : 'text-orange-400'}`}>
              {attribution.contribution_pct.toFixed(0)}% contribution
            </span>
            <span className="text-slate-500">
              r = {attribution.correlation.toFixed(2)}
            </span>
            <span className="text-slate-500">
              n = {attribution.sample_size}
            </span>
          </div>
          
          <p className="text-sm text-slate-400 leading-relaxed">
            {attribution.insight}
          </p>
        </div>
      </div>
    </div>
  );
}

// Methods contribution summary
function MethodsSummary({ contributions }: { contributions: MethodContributions }) {
  const methods = [
    { key: 'efficiency_trending', label: 'Efficiency Trending', active: contributions.efficiency_trending },
    { key: 'tsb_analysis', label: 'TSB Analysis', active: contributions.tsb_analysis },
    { key: 'critical_speed', label: 'Critical Speed', active: contributions.critical_speed },
    { key: 'fingerprinting', label: 'Fingerprinting', active: contributions.fingerprinting },
    { key: 'pace_decay', label: 'Pace Decay', active: contributions.pace_decay },
  ];
  
  const activeCount = methods.filter(m => m.active).length;
  
  if (activeCount === 0) return null;
  
  return (
    <div className="mt-4 pt-4 border-t border-slate-700/50">
      <p className="text-xs text-slate-500 mb-2">
        Analysis powered by {activeCount} method{activeCount !== 1 ? 's' : ''}:
      </p>
      <div className="flex flex-wrap gap-1">
        {methods.filter(m => m.active).map(m => (
          <Badge key={m.key} variant="outline" className="text-[10px] border-slate-600 text-slate-400">
            {m.label}
          </Badge>
        ))}
      </div>
    </div>
  );
}

// Fetch attribution data
async function fetchTrendAttribution(metric: string, days: number): Promise<TrendAttributionResponse> {
  return apiClient.get<TrendAttributionResponse>(`/v1/analytics/trend-attribution?metric=${metric}&days=${days}`);
}

// Main component
export function WhyThisTrend({
  metric = 'efficiency',
  days = 28,
  buttonVariant = 'outline',
  buttonSize = 'sm',
  className = ''
}: WhyThisTrendProps) {
  const [open, setOpen] = useState(false);
  
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['trend-attribution', metric, days],
    queryFn: () => fetchTrendAttribution(metric, days),
    enabled: open, // Only fetch when dialog is opened
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
  });
  
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button 
          variant={buttonVariant} 
          size={buttonSize}
          className={`gap-1 ${className}`}
        >
          <HelpCircle className="w-4 h-4" />
          <span>Why This Trend?</span>
        </Button>
      </DialogTrigger>
      
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto bg-slate-900 border-slate-700">
        <DialogHeader>
          <DialogTitle className="text-xl flex items-center gap-2">
            <HelpCircle className="w-5 h-5 text-orange-500" />
            Why This Trend?
          </DialogTitle>
          <DialogDescription className="text-slate-400">
            Attribution analysis based on YOUR data patterns — not generic advice.
          </DialogDescription>
        </DialogHeader>
        
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
          </div>
        )}
        
        {error && (
          <div className="py-8 text-center">
            <AlertCircle className="w-8 h-8 mx-auto text-red-400 mb-2" />
            <p className="text-slate-400">Unable to load attribution data.</p>
            <Button 
              variant="outline" 
              size="sm" 
              className="mt-4"
              onClick={() => refetch()}
            >
              Try Again
            </Button>
          </div>
        )}
        
        {data && !isLoading && (
          <div className="space-y-4">
            {/* Trend Summary */}
            {data.trend_summary && (
              <Card className="bg-slate-800/50 border-slate-700/50">
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-slate-400 mb-1">
                        {data.trend_summary.metric.charAt(0).toUpperCase() + data.trend_summary.metric.slice(1)} Trend
                      </p>
                      <p className="text-xs text-slate-500">
                        Last {data.trend_summary.period_days} days
                      </p>
                    </div>
                    <div className="text-right">
                      <TrendDirection 
                        direction={data.trend_summary.direction} 
                        changePercent={data.trend_summary.change_percent} 
                      />
                      {data.trend_summary.p_value && (
                        <p className="text-xs text-slate-500 mt-1">
                          p = {data.trend_summary.p_value.toFixed(3)}
                        </p>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
            
            {/* No data message */}
            {data.message && (
              <div className="py-8 text-center">
                <Info className="w-8 h-8 mx-auto text-slate-500 mb-2" />
                <p className="text-slate-400">{data.message}</p>
                <p className="text-sm text-slate-500 mt-2">
                  Log more check-ins and activities to unlock attribution insights.
                </p>
              </div>
            )}
            
            {/* Attributions */}
            {data.attributions && data.attributions.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-slate-300">
                  Top Contributing Factors
                </h3>
                {data.attributions.map((attr, index) => (
                  <AttributionCard key={attr.factor} attribution={attr} rank={index + 1} />
                ))}
              </div>
            )}
            
            {/* No attributions but have data */}
            {data.attributions && data.attributions.length === 0 && !data.message && (
              <div className="py-6 text-center">
                <p className="text-slate-400">
                  No significant attributions found.
                </p>
                <p className="text-sm text-slate-500 mt-1">
                  Need more consistent check-in data to identify patterns.
                </p>
              </div>
            )}
            
            {/* Methods summary */}
            {data.method_contributions && (
              <MethodsSummary contributions={data.method_contributions} />
            )}
            
            {/* Disclaimer */}
            <p className="text-[11px] text-slate-600 text-center mt-4">
              Attributions are correlational, not causal. Use as hints to test, not prescriptions.
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default WhyThisTrend;
