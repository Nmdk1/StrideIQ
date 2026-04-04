'use client';

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  ArrowRight,
  Check,
  X,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Calendar,
} from 'lucide-react';

interface ProposalChange {
  scheduled_date: string;
  day_of_week: number;
  original_type: string;
  original_title: string;
  original_miles: number | null;
  proposed_type: string;
  proposed_title: string;
  proposed_miles: number | null;
  reason: string;
  changed: boolean;
}

interface AdaptationProposal {
  id: string;
  trigger_type: string;
  trigger_detail: Record<string, unknown> | null;
  proposed_changes: ProposalChange[];
  affected_week_start: number;
  affected_week_end: number;
  status: string;
  created_at: string;
  expires_at: string;
  adaptation_number: number;
}

const TRIGGER_LABELS: Record<string, string> = {
  missed_long_run: 'Missed long run',
  consecutive_missed: 'Multiple missed days',
  readiness_tank: 'Extended low readiness',
};

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function formatWorkoutType(type: string): string {
  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function DayDiffRow({ change }: { change: ProposalChange }) {
  const dayName = DAY_NAMES[change.day_of_week] || 'Day';
  const dateStr = new Date(change.scheduled_date + 'T12:00:00').toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });

  if (!change.changed) {
    return (
      <div className="flex items-center gap-3 py-1.5 text-sm text-slate-500">
        <span className="w-16 text-xs font-medium">{dayName} {dateStr}</span>
        <span className="flex-1">{formatWorkoutType(change.original_type)}</span>
        <span className="text-xs text-slate-600">unchanged</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 py-2 text-sm border-l-2 border-blue-500 pl-3 -ml-3">
      <span className="w-16 text-xs font-semibold text-blue-400">{dayName} {dateStr}</span>
      <div className="flex-1 flex items-center gap-2">
        <span className="text-slate-400 line-through text-xs">
          {formatWorkoutType(change.original_type)}
          {change.original_miles ? ` ${change.original_miles}mi` : ''}
        </span>
        <ArrowRight className="w-3 h-3 text-blue-400 flex-shrink-0" />
        <span className="text-slate-200 font-medium">
          {formatWorkoutType(change.proposed_type)}
          {change.proposed_miles ? ` ${change.proposed_miles}mi` : ''}
        </span>
      </div>
    </div>
  );
}

export function AdaptationProposalCard() {
  const [expanded, setExpanded] = useState(false);
  const queryClient = useQueryClient();

  const { data: proposal, isLoading } = useQuery<AdaptationProposal | null>({
    queryKey: ['adaptation-proposal'],
    queryFn: async () => {
      const res = await apiClient.get<AdaptationProposal | null>(
        '/v1/training-plans/adaptation-proposals/pending'
      );
      return res;
    },
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  });

  const acceptMutation = useMutation({
    mutationFn: async (id: string) => {
      return apiClient.post(`/v1/training-plans/adaptation-proposals/${id}/accept`, {});
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adaptation-proposal'] });
      queryClient.invalidateQueries({ queryKey: ['home'] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: async (id: string) => {
      return apiClient.post(`/v1/training-plans/adaptation-proposals/${id}/reject`, {});
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adaptation-proposal'] });
    },
  });

  if (isLoading || !proposal) return null;

  const changedDays = proposal.proposed_changes.filter((c) => c.changed);
  const triggerLabel = TRIGGER_LABELS[proposal.trigger_type] || proposal.trigger_type;
  const expiresDate = new Date(proposal.expires_at);
  const daysLeft = Math.max(
    0,
    Math.ceil((expiresDate.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
  );
  const isActing = acceptMutation.isPending || rejectMutation.isPending;

  return (
    <Card className="border-blue-500/30 bg-blue-500/5">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-semibold text-blue-300">Plan Adjustment Suggested</span>
          </div>
          <Badge variant="outline" className="text-[10px] border-slate-600 text-slate-400">
            {daysLeft}d left
          </Badge>
        </div>

        <p className="text-sm text-slate-300">
          {triggerLabel}. Here&apos;s a proposed adjustment for weeks{' '}
          {proposal.affected_week_start}–{proposal.affected_week_end}
          {changedDays.length > 0 && ` (${changedDays.length} day${changedDays.length > 1 ? 's' : ''} changed)`}.
        </p>

        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          <Calendar className="w-3 h-3" />
          {expanded ? 'Hide' : 'Show'} day-by-day diff
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>

        {expanded && (
          <div className="space-y-0.5 pt-1">
            {proposal.proposed_changes.map((change) => (
              <DayDiffRow key={change.scheduled_date} change={change} />
            ))}
          </div>
        )}

        <div className="flex items-center gap-2 pt-1">
          <Button
            size="sm"
            variant="default"
            className="flex-1 bg-blue-600 hover:bg-blue-500 text-white"
            disabled={isActing}
            onClick={() => acceptMutation.mutate(proposal.id)}
          >
            <Check className="w-3.5 h-3.5 mr-1" />
            Accept
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="flex-1 border-slate-600 text-slate-300 hover:bg-slate-800"
            disabled={isActing}
            onClick={() => rejectMutation.mutate(proposal.id)}
          >
            <X className="w-3.5 h-3.5 mr-1" />
            Keep Original
          </Button>
        </div>
        <p className="text-[10px] text-slate-500 text-center">
          No response = keep original plan
        </p>
      </CardContent>
    </Card>
  );
}
