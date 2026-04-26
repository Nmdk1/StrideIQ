'use client';

/**
 * SymptomLogger — niggle / ache / pain / injury entry form.
 *
 * Friction contract (STRENGTH_V1_SCOPE §6.5):
 *   - Severity is the runner-language ladder, never a clinical scale.
 *   - The system does not auto-suggest a body area, never infers
 *     severity, and never adds a treatment recommendation. The form
 *     stores exactly what the athlete typed.
 *   - "Resolved today" pill is one tap on an active entry.
 */

import { useMemo, useState } from 'react';

import {
  useCreateSymptom,
  useDeleteSymptom,
  useSymptomList,
  useUpdateSymptom,
} from '@/lib/hooks/queries/symptoms';
import {
  BODY_AREAS,
  type BodyArea,
  type SymptomLogResponse,
  type SymptomSeverity,
} from '@/lib/api/services/symptoms';

const SEVERITIES: ReadonlyArray<{
  value: SymptomSeverity;
  label: string;
  hint: string;
}> = [
  { value: 'niggle', label: 'Niggle', hint: 'I notice it' },
  { value: 'ache', label: 'Ache', hint: 'It bothers me but I run through it' },
  { value: 'pain', label: 'Pain', hint: 'It changes how I run' },
  { value: 'injury', label: 'Injury', hint: "I can't train through it" },
];

function formatBodyArea(area: string): string {
  return area.replace(/_/g, ' ');
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function SymptomLogger() {
  const { data, isLoading, error } = useSymptomList();
  const create = useCreateSymptom();
  const update = useUpdateSymptom();
  const remove = useDeleteSymptom();

  const [bodyArea, setBodyArea] = useState<BodyArea>('left_calf');
  const [severity, setSeverity] = useState<SymptomSeverity>('niggle');
  const [startedAt, setStartedAt] = useState<string>(todayISO());
  const [triggered, setTriggered] = useState('');
  const [notes, setNotes] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const active = useMemo(() => data?.active ?? [], [data]);
  const history = useMemo(() => data?.history ?? [], [data]);

  const handleCreate = async () => {
    setFormError(null);
    try {
      await create.mutateAsync({
        body_area: bodyArea,
        severity,
        started_at: startedAt,
        triggered_by: triggered.trim() || null,
        notes: notes.trim() || null,
      });
      setTriggered('');
      setNotes('');
      setSeverity('niggle');
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message?: unknown }).message ?? '')
          : '';
      setFormError(msg || 'Could not log symptom.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-12">
      <header className="px-4 pt-6 pb-3 border-b border-slate-800">
        <p className="text-[11px] uppercase tracking-wide text-slate-500">
          Body
        </p>
        <h1 className="text-2xl font-bold mt-1">Niggles, aches & injuries</h1>
        <p className="text-sm text-slate-400 mt-2 max-w-prose">
          Log it when you feel it. We never tell you what to do about it; we
          just remember when it started, when it stopped, and what you were
          doing around it.
        </p>
      </header>

      <section className="px-4 pt-5">
        <h2 className="text-xs uppercase tracking-wide text-slate-500 mb-2">
          Log something new
        </h2>
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 space-y-3">
          <div>
            <label className="block text-[11px] uppercase tracking-wide text-slate-500 mb-1">
              Where
            </label>
            <select
              value={bodyArea}
              onChange={(e) => setBodyArea(e.target.value as BodyArea)}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-base text-slate-100 capitalize focus:outline-none focus:border-slate-600"
            >
              {BODY_AREAS.map((a) => (
                <option key={a} value={a}>
                  {formatBodyArea(a)}
                </option>
              ))}
            </select>
          </div>

          <fieldset>
            <legend className="block text-[11px] uppercase tracking-wide text-slate-500 mb-1">
              How bad
            </legend>
            <div className="grid grid-cols-2 gap-2">
              {SEVERITIES.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  onClick={() => setSeverity(s.value)}
                  className={`text-left rounded-md border px-3 py-2 ${
                    severity === s.value
                      ? 'border-emerald-500 bg-emerald-500/10 text-emerald-200'
                      : 'border-slate-700 bg-slate-900 text-slate-200 hover:border-slate-500'
                  }`}
                >
                  <p className="text-sm font-medium">{s.label}</p>
                  <p className="text-[11px] text-slate-400">{s.hint}</p>
                </button>
              ))}
            </div>
          </fieldset>

          <div>
            <label className="block text-[11px] uppercase tracking-wide text-slate-500 mb-1">
              Started
            </label>
            <input
              type="date"
              value={startedAt}
              onChange={(e) => setStartedAt(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-base text-slate-100 focus:outline-none focus:border-slate-600"
            />
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-wide text-slate-500 mb-1">
              Triggered by (optional)
            </label>
            <input
              type="text"
              value={triggered}
              onChange={(e) => setTriggered(e.target.value)}
              placeholder="after long run, deadlifts, slept wrong"
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-base text-slate-100 placeholder-slate-600 focus:outline-none focus:border-slate-600"
            />
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-wide text-slate-500 mb-1">
              Notes (optional)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full bg-slate-900 border border-slate-800 rounded-md px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-slate-600"
            />
          </div>

          {formError && (
            <p className="text-sm text-rose-400" role="alert">
              {formError}
            </p>
          )}

          <button
            type="button"
            onClick={handleCreate}
            disabled={create.isPending}
            className="w-full py-3 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-base font-semibold"
          >
            {create.isPending ? 'Logging…' : 'Log symptom'}
          </button>
        </div>
      </section>

      <section className="px-4 pt-6">
        <h2 className="text-xs uppercase tracking-wide text-slate-500 mb-2">
          Active ({active.length})
        </h2>
        {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
        {!isLoading && error && (
          <p className="text-sm text-slate-500">
            Symptom logging isn&apos;t enabled on your account yet.
          </p>
        )}
        {!isLoading && !error && active.length === 0 && (
          <p className="text-sm text-slate-500">Nothing active right now.</p>
        )}
        <ul className="space-y-2">
          {active.map((s) => (
            <li key={s.id}>
              <SymptomCard
                symptom={s}
                onResolveToday={() =>
                  update.mutate({
                    id: s.id,
                    updates: { resolved_at: todayISO() },
                  })
                }
                onDelete={() => remove.mutate(s.id)}
              />
            </li>
          ))}
        </ul>
      </section>

      {history.length > 0 && (
        <section className="px-4 pt-6">
          <h2 className="text-xs uppercase tracking-wide text-slate-500 mb-2">
            Resolved
          </h2>
          <ul className="space-y-2">
            {history.map((s) => (
              <li key={s.id}>
                <SymptomCard symptom={s} onDelete={() => remove.mutate(s.id)} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function severityClasses(sev: string): string {
  switch (sev) {
    case 'niggle':
      return 'bg-slate-700/40 text-slate-200';
    case 'ache':
      return 'bg-amber-500/20 text-amber-300';
    case 'pain':
      return 'bg-orange-600/30 text-orange-300';
    case 'injury':
      return 'bg-rose-600/30 text-rose-300';
    default:
      return 'bg-slate-700/40 text-slate-200';
  }
}

function SymptomCard({
  symptom,
  onResolveToday,
  onDelete,
}: {
  symptom: SymptomLogResponse;
  onResolveToday?: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium capitalize">
            {formatBodyArea(symptom.body_area)}
          </p>
          <p className="text-[11px] text-slate-500">
            since {symptom.started_at}
            {symptom.resolved_at ? ` → ${symptom.resolved_at}` : ''}
          </p>
        </div>
        <span
          className={`text-[11px] uppercase tracking-wide px-2 py-0.5 rounded ${severityClasses(
            symptom.severity,
          )}`}
        >
          {symptom.severity}
        </span>
      </div>
      {symptom.triggered_by && (
        <p className="mt-1 text-[12px] text-slate-400">
          Triggered: {symptom.triggered_by}
        </p>
      )}
      {symptom.notes && (
        <p className="mt-1 text-[12px] text-slate-400 whitespace-pre-wrap">
          {symptom.notes}
        </p>
      )}
      <div className="mt-2 flex items-center gap-2">
        {onResolveToday && (
          <button
            type="button"
            onClick={onResolveToday}
            className="text-xs px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700"
          >
            Resolved today
          </button>
        )}
        <button
          type="button"
          onClick={onDelete}
          className="text-xs px-3 py-1.5 rounded border border-slate-800 text-slate-500 hover:border-rose-700 hover:text-rose-400 ml-auto"
        >
          Delete
        </button>
      </div>
    </div>
  );
}
