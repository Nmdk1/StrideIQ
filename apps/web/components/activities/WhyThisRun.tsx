'use client';

/**
 * WhyThisRun Component
 * 
 * Displays attribution analysis for a single run.
 * Shows why the run went well/poorly based on multiple analytics signals.
 * 
 * ADR-015: Why This Run? Activity Attribution
 * 
 * TONE: Sparse, direct, non-prescriptive. "Data hints X. Test it."
 */

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  HelpCircle, 
  Timer,
  Battery,
  Target,
  Gauge,
  Zap,
  TrendingUp,
  TrendingDown,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Info
} from 'lucide-react';
import { apiClient } from '@/lib/api/client';

// Types matching backend
interface RunAttribution {
  source: string;
  priority: number;
  confidence: string;
  title: string;
  insight: string;
  icon: string;
  color: string;
  data: Record<string, unknown>;
}

interface RunAttributionResponse {
  activity_id: string;
  activity_name: string;
  attributions: RunAttribution[];
  summary: string | null;
  generated_at: string;
}

// Props
interface WhyThisRunProps {
  activityId: string;
  className?: string;
  defaultExpanded?: boolean;
}

// Icon mapping
const ICON_MAP: Record<string, React.ReactNode> = {
  timer: <Timer className="w-4 h-4" />,
  battery: <Battery className="w-4 h-4" />,
  target: <Target className="w-4 h-4" />,
  gauge: <Gauge className="w-4 h-4" />,
  zap: <Zap className="w-4 h-4" />,
  trending_up: <TrendingUp className="w-4 h-4" />,
  trending_down: <TrendingDown className="w-4 h-4" />,
};

// Color mapping for Tailwind
const COLOR_MAP: Record<string, { bg: string; text: string; border: string }> = {
  green: {
    bg: 'bg-green-500/20',
    text: 'text-green-400',
    border: 'border-green-500/30',
  },
  emerald: {
    bg: 'bg-emerald-500/20',
    text: 'text-emerald-400',
    border: 'border-emerald-500/30',
  },
  blue: {
    bg: 'bg-blue-500/20',
    text: 'text-blue-400',
    border: 'border-blue-500/30',
  },
  orange: {
    bg: 'bg-orange-500/20',
    text: 'text-orange-400',
    border: 'border-orange-500/30',
  },
  yellow: {
    bg: 'bg-yellow-500/20',
    text: 'text-yellow-400',
    border: 'border-yellow-500/30',
  },
  slate: {
    bg: 'bg-slate-500/20',
    text: 'text-slate-400',
    border: 'border-slate-500/30',
  },
  red: {
    bg: 'bg-red-500/20',
    text: 'text-red-400',
    border: 'border-red-500/30',
  },
};

// Confidence badge
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
  }
  return null;
}

// Single attribution card
function AttributionCard({ attribution }: { attribution: RunAttribution }) {
  const colors = COLOR_MAP[attribution.color] || COLOR_MAP.slate;
  const icon = ICON_MAP[attribution.icon] || <Info className="w-4 h-4" />;
  
  return (
    <div className={`p-4 rounded-lg border ${colors.border} ${colors.bg} transition-all hover:border-opacity-60`}>
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg bg-slate-800/50 ${colors.text} flex-shrink-0`}>
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`font-semibold text-sm ${colors.text}`}>
              {attribution.title}
            </span>
            <ConfidenceBadge confidence={attribution.confidence} />
          </div>
          <p className="text-sm text-slate-300 leading-relaxed">
            {attribution.insight}
          </p>
        </div>
      </div>
    </div>
  );
}

// Fetch attribution data
async function fetchRunAttribution(activityId: string): Promise<RunAttributionResponse> {
  return apiClient.get<RunAttributionResponse>(`/v1/activities/${activityId}/attribution`);
}

// Main component
export function WhyThisRun({
  activityId,
  className = '',
  defaultExpanded = true
}: WhyThisRunProps) {
  const [expanded, setExpanded] = React.useState(defaultExpanded);
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['run-attribution', activityId],
    queryFn: () => fetchRunAttribution(activityId),
    staleTime: 10 * 60 * 1000, // 10 minutes
    refetchOnWindowFocus: false,
    retry: 1, // Only retry once for 403/404
  });
  
  // Don't render if loading fails silently (feature disabled, etc.)
  if (error) {
    return null;
  }
  
  // Don't render while loading
  if (isLoading) {
    return (
      <Card className={`bg-slate-800/50 border-slate-700/50 ${className}`}>
        <CardContent className="py-6 flex items-center justify-center">
          <Loader2 className="w-5 h-5 animate-spin text-slate-500" />
        </CardContent>
      </Card>
    );
  }
  
  // Don't render if no attributions
  if (!data || data.attributions.length === 0) {
    return null;
  }
  
  return (
    <Card className={`bg-slate-800/50 border-slate-700/50 ${className}`}>
      <CardHeader 
        className="pb-2 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <HelpCircle className="w-5 h-5 text-orange-500" />
            Why This Run?
            <Badge variant="outline" className="text-[10px] border-slate-600 text-slate-400">
              {data.attributions.length} insight{data.attributions.length !== 1 ? 's' : ''}
            </Badge>
          </CardTitle>
          <button className="text-slate-400 hover:text-slate-300">
            {expanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
        </div>
        {data.summary && (
          <p className="text-sm text-slate-400 mt-1">
            {data.summary}
          </p>
        )}
      </CardHeader>
      
      {expanded && (
        <CardContent className="pt-2 pb-4">
          <div className="space-y-3">
            {data.attributions.map((attr, index) => (
              <div 
                key={attr.source}
                className="animate-in fade-in slide-in-from-top-2"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <AttributionCard attribution={attr} />
              </div>
            ))}
          </div>
          
          {/* Disclaimer */}
          <p className="text-[10px] text-slate-600 text-center mt-4">
            Attributions are correlational hints, not causal prescriptions.
          </p>
        </CardContent>
      )}
    </Card>
  );
}

export default WhyThisRun;
