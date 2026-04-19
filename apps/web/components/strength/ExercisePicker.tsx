'use client';

/**
 * ExercisePicker — search-first exercise selection sheet.
 *
 * Mobile contract:
 *   - Search input is auto-focused on open. Typing filters live.
 *   - "Recent" section is shown above results when no query is typed.
 *   - Single tap on a row commits the selection and dismisses the sheet.
 *   - If the typed query has no taxonomy match, an "Use as-is" row is
 *     surfaced so the athlete is never blocked by a missing entry.
 *
 * The picker never invents canonical names; if the athlete uses a
 * free-text exercise, it ships through to the API as-typed and gets
 * classified server-side (or stays "other / other" — no fabrication).
 */

import { useEffect, useMemo, useRef, useState } from 'react';

import { useStrengthExercises } from '@/lib/hooks/queries/strength';
import type { ExercisePickerEntry } from '@/lib/api/services/strength';

export interface ExercisePickerProps {
  open: boolean;
  onClose: () => void;
  onSelect: (entry: ExercisePickerEntry) => void;
}

function formatPattern(p: string | null | undefined): string {
  if (!p || p === 'other') return '';
  return p.replace(/_/g, ' ');
}

export function ExercisePicker({ open, onClose, onSelect }: ExercisePickerProps) {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (open) {
      setQuery('');
      const t = setTimeout(() => inputRef.current?.focus(), 60);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [open]);

  const trimmed = query.trim();
  const { data, isLoading } = useStrengthExercises(trimmed || undefined);

  const showRecent = !trimmed && (data?.recent.length ?? 0) > 0;
  const results = data?.results ?? [];

  const showFreeText = useMemo(() => {
    if (!trimmed) return false;
    const lower = trimmed.toLowerCase();
    const exact = results.some((r) => r.name.toLowerCase() === lower);
    return !exact;
  }, [trimmed, results]);

  if (!open) return null;

  const handleSelect = (entry: ExercisePickerEntry) => {
    onSelect(entry);
    onClose();
  };

  const handleFreeText = () => {
    handleSelect({
      name: trimmed,
      movement_pattern: 'other',
      muscle_group: null,
      is_unilateral: false,
    });
  };

  return (
    <div
      role="dialog"
      aria-label="Pick an exercise"
      className="fixed inset-0 z-50 flex flex-col bg-slate-950/95 backdrop-blur-sm"
    >
      <div className="flex items-center gap-2 px-4 pt-3 pb-2 border-b border-slate-800">
        <button
          type="button"
          onClick={onClose}
          className="text-sm text-slate-400 hover:text-slate-200 px-2 py-2 -ml-2"
          aria-label="Close exercise picker"
        >
          Cancel
        </button>
        <input
          ref={inputRef}
          type="text"
          inputMode="search"
          enterKeyHint="search"
          placeholder="Search or type a new exercise"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-base text-slate-100 placeholder-slate-500 focus:outline-none focus:border-slate-500"
        />
      </div>

      <div className="flex-1 overflow-y-auto pb-32">
        {isLoading && (
          <p className="px-4 py-6 text-sm text-slate-500">Loading exercises…</p>
        )}

        {showFreeText && (
          <button
            type="button"
            onClick={handleFreeText}
            className="w-full text-left px-4 py-4 border-b border-slate-800 hover:bg-slate-900"
          >
            <p className="text-base text-slate-100">
              Use &ldquo;{trimmed}&rdquo;
            </p>
            <p className="text-xs text-slate-500 mt-0.5">
              Logged as-typed. We won&apos;t guess what muscle group it hits.
            </p>
          </button>
        )}

        {showRecent && (
          <section aria-label="Recent exercises">
            <h3 className="px-4 pt-4 pb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Recent
            </h3>
            <ul>
              {data!.recent.map((entry) => (
                <li key={`recent-${entry.name}`}>
                  <ExerciseRow entry={entry} onSelect={handleSelect} />
                </li>
              ))}
            </ul>
          </section>
        )}

        {results.length > 0 && (
          <section aria-label="All exercises">
            {showRecent && (
              <h3 className="px-4 pt-4 pb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                All
              </h3>
            )}
            <ul>
              {results.map((entry) => (
                <li key={entry.name}>
                  <ExerciseRow entry={entry} onSelect={handleSelect} />
                </li>
              ))}
            </ul>
          </section>
        )}

        {!isLoading && !showFreeText && !showRecent && results.length === 0 && (
          <p className="px-4 py-6 text-sm text-slate-500">
            No matches. Type the exercise you actually did and tap{' '}
            <span className="text-slate-300">Use &ldquo;…&rdquo;</span>.
          </p>
        )}
      </div>
    </div>
  );
}

function ExerciseRow({
  entry,
  onSelect,
}: {
  entry: ExercisePickerEntry;
  onSelect: (e: ExercisePickerEntry) => void;
}) {
  const pattern = formatPattern(entry.movement_pattern);
  const muscle = entry.muscle_group ?? '';
  const meta = [pattern, muscle].filter(Boolean).join(' · ');

  return (
    <button
      type="button"
      onClick={() => onSelect(entry)}
      className="w-full text-left px-4 py-3 border-b border-slate-800/70 hover:bg-slate-900 active:bg-slate-800"
    >
      <p className="text-base text-slate-100 capitalize">{entry.name}</p>
      {meta && (
        <p className="text-xs text-slate-500 mt-0.5 capitalize">
          {meta}
          {entry.is_unilateral ? ' · unilateral' : ''}
        </p>
      )}
    </button>
  );
}
