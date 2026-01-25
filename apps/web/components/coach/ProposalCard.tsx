import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { coachActionsService } from '@/lib/api/services/coach-actions';

type ProposalStatus = 'proposed' | 'confirmed' | 'rejected' | 'applied' | 'failed';

export type ProposalCardProposal = {
  proposal_id: string;
  status: ProposalStatus;

  // These fields may be injected by the Coach orchestrator payload.
  plan_name?: string | null;
  reason?: string | null;

  // From Phase 10 API surfaces
  target_plan_id?: string | null;
  diff_preview: Array<{
    plan_id: string;
    workout_id: string;
    before: {
      id: string;
      scheduled_date: string | null;
      title: string | null;
      workout_type: string | null;
      target_distance_km?: number | null;
      target_duration_minutes?: number | null;
      skipped?: boolean | null;
    };
    after: {
      id: string;
      scheduled_date: string | null;
      title: string | null;
      workout_type: string | null;
      target_distance_km?: number | null;
      target_duration_minutes?: number | null;
      skipped?: boolean | null;
    };
  }>;
  risk_notes: string[];

  created_at?: string | null;
};

type Props = {
  proposal: ProposalCardProposal;
  onAskFollowup?: (suggestedText: string) => void;
};

function fmtDate(d: string | null | undefined): string {
  if (!d) return '—';
  // Prefer YYYY-MM-DD if already.
  if (/^\d{4}-\d{2}-\d{2}$/.test(d)) return d;
  try {
    return new Date(d).toISOString().slice(0, 10);
  } catch {
    return d;
  }
}

function fmtWorkoutType(t: string | null | undefined): string {
  const raw = (t || '').trim();
  if (!raw) return '—';
  const spaced = raw.replace(/[_-]+/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function fmtDistanceKm(km?: number | null): string | null {
  if (km == null) return null;
  const v = Number(km);
  if (Number.isNaN(v)) return null;
  return `${v.toFixed(v >= 10 ? 0 : 1)} km`;
}

function fmtDurationMin(min?: number | null): string | null {
  if (min == null) return null;
  const v = Number(min);
  if (Number.isNaN(v)) return null;
  return `${Math.round(v)} min`;
}

function makeIdempotencyKey(prefix: string) {
  // Browser-safe, test-safe (no crypto requirement).
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export function ProposalCard({ proposal, onAskFollowup }: Props) {
  const [status, setStatus] = useState<ProposalStatus>(proposal.status);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [receiptSummary, setReceiptSummary] = useState<string | null>(null);
  const confirmIdempotencyKeyRef = useRef<string>(makeIdempotencyKey('confirm'));
  const toastTimerRef = useRef<number | null>(null);

  const headerPlanName = proposal.plan_name?.trim() || 'your plan';
  const reason = proposal.reason?.trim() || '—';

  const totalChanges = useMemo(() => proposal.diff_preview?.length || 0, [proposal.diff_preview]);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) {
        window.clearTimeout(toastTimerRef.current);
        toastTimerRef.current = null;
      }
    };
  }, []);

  const onConfirm = async () => {
    setError(null);
    setIsSubmitting(true);
    try {
      const res = await coachActionsService.confirm(proposal.proposal_id, confirmIdempotencyKeyRef.current);
      setStatus(res.status);
      if (res.status === 'applied') {
        const appliedAt = res.applied_at ? fmtDate(res.applied_at) : 'now';
        const actionsApplied = res.receipt?.actions_applied ?? 0;
        const changes = res.receipt?.changes?.length ?? 0;
        const msg = `Applied ${actionsApplied} action${actionsApplied === 1 ? '' : 's'} (${changes} change${changes === 1 ? '' : 's'}) • ${appliedAt}`;
        setToast('Apply receipt');
        setReceiptSummary(msg);
        // Auto-hide the toast label; keep the receipt summary visible.
        if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
        toastTimerRef.current = window.setTimeout(() => setToast(null), 2500);
      }
    } catch (e) {
      setError(e);
      setStatus('failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const onReject = async () => {
    setError(null);
    setIsSubmitting(true);
    try {
      await coachActionsService.reject(proposal.proposal_id, 'Athlete rejected in Coach chat');
      setStatus('rejected');
    } catch (e) {
      setError(e);
      setStatus('failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const canAct = status === 'proposed' || status === 'failed';

  return (
    <Card className="bg-slate-950/40 border-slate-700/60">
      <CardContent className="p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-slate-100">
              Proposed changes to <span className="text-orange-300">{headerPlanName}</span>
            </div>
            <div className="text-xs text-slate-400 mt-1">
              {totalChanges} change{totalChanges === 1 ? '' : 's'} • Status:{' '}
              <span className="text-slate-200">{status}</span>
            </div>
          </div>

          {toast && (
            <div
              role="status"
              aria-live="polite"
              className="text-xs font-semibold px-3 py-1.5 rounded-full border border-orange-500/30 bg-orange-500/10 text-orange-200"
            >
              {toast}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-slate-700/60 bg-slate-900/30 p-4">
          <div className="text-xs font-semibold text-slate-300 mb-2">Reason</div>
          <div className="text-sm text-slate-100 whitespace-pre-wrap">{reason}</div>
        </div>

        <div className="rounded-lg border border-slate-700/60 bg-slate-900/30 p-4">
          <div className="text-xs font-semibold text-slate-300 mb-3">Diff preview</div>
          <div className="space-y-3">
            {proposal.diff_preview.map((d) => {
              const beforeDistance = fmtDistanceKm(d.before.target_distance_km);
              const beforeDuration = fmtDurationMin(d.before.target_duration_minutes);
              const afterDistance = fmtDistanceKm(d.after.target_distance_km);
              const afterDuration = fmtDurationMin(d.after.target_duration_minutes);
              const beforeType = fmtWorkoutType(d.before.workout_type);
              const afterType = fmtWorkoutType(d.after.workout_type);
              const beforeSkipped = d.before.skipped === true;
              const afterSkipped = d.after.skipped === true;
              return (
                <div key={`${d.workout_id}`} className="rounded-md border border-slate-800 bg-slate-950/40 p-3">
                  <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 items-start">
                    <div>
                      <div className="text-xs text-slate-400">Before</div>
                      <div className="text-sm text-slate-100 font-semibold">{d.before.title || 'Workout'}</div>
                      <div className="text-xs text-slate-400 mt-1">
                        {fmtDate(d.before.scheduled_date)} • {beforeType}
                        {beforeDistance ? ` • ${beforeDistance}` : ''}
                        {beforeDuration ? ` • ${beforeDuration}` : ''}
                        {beforeSkipped ? ' • Skipped' : ''}
                      </div>
                    </div>
                    <div className="text-xs text-slate-500 font-semibold self-center">→</div>
                    <div>
                      <div className="text-xs text-slate-400">After</div>
                      <div className="text-sm text-slate-100 font-semibold">{d.after.title || 'Workout'}</div>
                      <div className="text-xs text-slate-400 mt-1">
                        {fmtDate(d.after.scheduled_date)} • {afterType}
                        {afterDistance ? ` • ${afterDistance}` : ''}
                        {afterDuration ? ` • ${afterDuration}` : ''}
                        {afterSkipped ? ' • Skipped' : ''}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {proposal.risk_notes?.length > 0 && (
          <div className="rounded-lg border border-slate-700/60 bg-slate-900/30 p-4">
            <div className="text-xs font-semibold text-slate-300 mb-2">Risk notes</div>
            <ul className="list-disc pl-5 space-y-1 text-sm text-slate-200">
              {proposal.risk_notes.map((n, idx) => (
                <li key={idx}>{n}</li>
              ))}
            </ul>
          </div>
        )}

        {receiptSummary && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-100">
            {receiptSummary}
          </div>
        )}

        {!!error && (
          <div role="alert">
            <ErrorMessage error={error} title="Apply failed" />
          </div>
        )}

        <div className="flex flex-wrap gap-2 pt-1">
          <Button
            type="button"
            onClick={onConfirm}
            disabled={!canAct || isSubmitting}
            className="bg-orange-600 hover:bg-orange-500"
          >
            Confirm &amp; Apply
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={onReject}
            disabled={!canAct || isSubmitting}
            className="border-slate-700 bg-transparent hover:bg-slate-900/40 text-slate-200"
          >
            Reject
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => onAskFollowup?.('Before I confirm: what is the intent behind these changes, and what should I watch for?')}
            disabled={isSubmitting}
            className="text-slate-200 hover:bg-slate-900/40"
          >
            Ask follow-up
          </Button>

          {status === 'failed' && (
            <Button
              type="button"
              variant="secondary"
              onClick={onConfirm}
              disabled={isSubmitting}
              className="bg-slate-800 hover:bg-slate-700 text-slate-100"
            >
              Retry apply
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

