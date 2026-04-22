/**
 * Pace string display formatting.
 *
 * Workout description and coach_notes strings are persisted in the DB by the plan
 * generators with pace literals like `"8:58/mi"` baked in. The DB columns
 * (`target_distance_km`, `target_pace_per_km_seconds`) carry the unit-neutral
 * source of truth, but the human-readable strings are pre-rendered.
 *
 * Unit formatting is fundamentally a presentation concern. This utility does the
 * unit conversion at display time so a metric athlete viewing a description that
 * was authored as `"Easy aerobic run at 8:58/mi."` sees `"Easy aerobic run at 5:34/km."`,
 * regardless of when the plan was generated.
 *
 * The matcher only touches pace patterns (`M:SS/mi`, `M:SS/km`, optionally with `~`
 * prefix and `M:SS-M:SS` ranges). Distance literals like `"16km"` and `"3-5mi"` are
 * left untouched.
 */

const MI_TO_KM = 1.60934;

type UnitSystem = 'metric' | 'imperial';

function parsePaceMSS(s: string): number | null {
  const m = s.match(/^(\d+):(\d{2})$/);
  if (!m) return null;
  const minutes = parseInt(m[1], 10);
  const seconds = parseInt(m[2], 10);
  if (Number.isNaN(minutes) || Number.isNaN(seconds) || seconds >= 60) return null;
  return minutes * 60 + seconds;
}

function formatSecondsAsPace(totalSeconds: number): string {
  let secs = Math.round(totalSeconds);
  if (secs < 0) secs = 0;
  const minutes = Math.floor(secs / 60);
  const remainder = secs % 60;
  return `${minutes}:${remainder.toString().padStart(2, '0')}`;
}

/**
 * Convert pace literals embedded in arbitrary text to the athlete's unit preference.
 *
 * Matches:
 *   - `"M:SS/mi"`, `"M:SS/km"` (single pace)
 *   - `"M:SS-M:SS/mi"`, `"M:SS-M:SS/km"` (pace range)
 *   - Optional leading `~` for approximations: `"~9:06-9:36/mi"`
 *
 * Leaves untouched:
 *   - Distance literals like `"16km"`, `"3-5mi"` (no colon, no slash)
 *   - Pace strings already in the target unit
 *   - Strings with no pace literal
 */
export function formatPaceTextForUnit(text: string | null | undefined, units: UnitSystem): string {
  if (!text) return text ?? '';
  const targetUnit = units === 'metric' ? 'km' : 'mi';

  return text.replace(
    /(~)?(\d+:\d{2})(?:-(\d+:\d{2}))?\/(mi|km)\b/g,
    (match, tilde, leftPace, rightPace, sourceUnit) => {
      if (sourceUnit === targetUnit) return match;

      const convertOne = (paceStr: string): string | null => {
        const sourceSeconds = parsePaceMSS(paceStr);
        if (sourceSeconds === null) return null;
        const targetSeconds =
          sourceUnit === 'mi' ? sourceSeconds / MI_TO_KM : sourceSeconds * MI_TO_KM;
        return formatSecondsAsPace(targetSeconds);
      };

      const left = convertOne(leftPace);
      if (left === null) return match;
      const prefix = tilde ?? '';
      if (rightPace) {
        const right = convertOne(rightPace);
        if (right === null) return match;
        return `${prefix}${left}-${right}/${targetUnit}`;
      }
      return `${prefix}${left}/${targetUnit}`;
    },
  );
}

/**
 * Convert distance literals embedded in arbitrary text to the athlete's unit
 * preference. Handles whole and decimal distances with `mi` or `km` suffixes,
 * including ranges (`3-5 mi`) and tildes (`~12 mi`).
 *
 * Matches:
 *   - `"16 mi"`, `"3.5mi"`, `"5 km"`
 *   - `"3-5 mi"`, `"3.5-5.0km"`
 *   - Optional leading `~` for approximations
 *
 * Leaves untouched anything that already matches the target unit.
 */
export function formatDistanceTextForUnit(
  text: string | null | undefined,
  units: UnitSystem,
): string {
  if (!text) return text ?? '';
  const targetUnit = units === 'metric' ? 'km' : 'mi';

  return text.replace(
    /(~)?(\d+(?:\.\d+)?)(?:-(\d+(?:\.\d+)?))?\s*(mi|km)\b/gi,
    (match, tilde, leftDist, rightDist, sourceUnitRaw) => {
      const sourceUnit = sourceUnitRaw.toLowerCase();
      if (sourceUnit === targetUnit) return match;

      const convertOne = (distStr: string): string | null => {
        const value = parseFloat(distStr);
        if (Number.isNaN(value)) return null;
        const converted = sourceUnit === 'mi' ? value * MI_TO_KM : value / MI_TO_KM;
        return converted < 10 ? converted.toFixed(1) : Math.round(converted).toString();
      };

      const left = convertOne(leftDist);
      if (left === null) return match;
      const prefix = tilde ?? '';
      if (rightDist) {
        const right = convertOne(rightDist);
        if (right === null) return match;
        return `${prefix}${left}-${right} ${targetUnit}`;
      }
      return `${prefix}${left} ${targetUnit}`;
    },
  );
}

/**
 * Convenience wrapper that rewrites both pace AND distance literals in one
 * pass. Use this for athlete-facing narrative text (briefings, week
 * trajectories, coach notes) that may contain both kinds of literal.
 */
export function formatTextForUnit(
  text: string | null | undefined,
  units: UnitSystem,
): string {
  return formatDistanceTextForUnit(formatPaceTextForUnit(text, units), units);
}
