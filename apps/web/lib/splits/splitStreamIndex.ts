import type { Split } from '@/lib/types/splits';
import type { StreamPoint } from '@/components/activities/rsi/hooks/useStreamAnalysis';

/**
 * Maps a 0-based split index (same convention as SplitsTable onRowHover: split_number - 1)
 * to a stream point index near the middle of that split's time window — for map/elevation/chart hover sync.
 */
export function splitMidStreamIndex(
  splits: Split[] | null | undefined,
  stream: StreamPoint[] | null | undefined,
  splitIndex0: number | null,
): number | null {
  if (splitIndex0 == null || !splits?.length || !stream?.length) return null;
  if (splitIndex0 < 0 || splitIndex0 >= splits.length) return null;

  let cumTime = 0;
  const boundaries: { start: number; end: number }[] = [];
  for (let i = 0; i < splits.length; i++) {
    const dur = splits[i].moving_time ?? splits[i].elapsed_time ?? 0;
    boundaries.push({ start: cumTime, end: cumTime + dur });
    cumTime += dur;
  }

  const { start, end } = boundaries[splitIndex0];
  const isLast = splitIndex0 === boundaries.length - 1;
  const indices: number[] = [];
  for (let j = 0; j < stream.length; j++) {
    const t = stream[j]?.time ?? 0;
    const inRange = isLast ? t >= start && t <= end : t >= start && t < end;
    if (inRange) indices.push(j);
  }
  if (indices.length === 0) {
    const midT = (start + end) / 2;
    let best = 0;
    let bestD = Infinity;
    for (let j = 0; j < stream.length; j++) {
      const d = Math.abs((stream[j]?.time ?? 0) - midT);
      if (d < bestD) {
        bestD = d;
        best = j;
      }
    }
    return best;
  }
  return indices[Math.floor(indices.length / 2)];
}
