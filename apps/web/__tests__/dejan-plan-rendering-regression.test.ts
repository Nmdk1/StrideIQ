/**
 * Regression: Dejan's archived "Model-Driven Half Marathon Plan" persists workout
 * descriptions and coach_notes with `8:58/mi` baked in even though Dejan is metric.
 * This test locks in that the display-time formatter renders his exact data correctly
 * for both metric and imperial viewers, so the "8:58/mi for a metric athlete" failure
 * cannot regress.
 *
 * Source data (verified on production droplet 2026-04-22):
 *   athlete: 6764d1a0-e246-4f8b-85f3-be80d1e7157e (preferred_units = "metric")
 *   plan:    1b93cdef-a72f-4c4a-9858-ae1ce0492bb8
 *   workout: 946bac80-8c9b-4edf-817e-db4db2519770 (Easy Run, 2026-04-21)
 *     description: "Easy aerobic run at 8:58/mi."
 *     coach_notes: "Target pace: 8:58/mi"
 */

import { formatPaceTextForUnit } from '@/lib/utils/paceText';

describe('Dejan archived plan rendering regression', () => {
  const DEJAN_DESCRIPTION = 'Easy aerobic run at 8:58/mi.';
  const DEJAN_COACH_NOTES = 'Target pace: 8:58/mi';

  describe('metric viewer (Dejan)', () => {
    it('renders the easy-run description in km', () => {
      expect(formatPaceTextForUnit(DEJAN_DESCRIPTION, 'metric')).toBe(
        'Easy aerobic run at 5:34/km.',
      );
    });

    it('renders the coach_notes in km', () => {
      expect(formatPaceTextForUnit(DEJAN_COACH_NOTES, 'metric')).toBe('Target pace: 5:34/km');
    });

    it('renders strides workout coach_notes with all imperial paces converted', () => {
      const stridesNotes =
        'Target pace: 8:58/mi | Strides maintain leg speed without fatigue | Focus on quick, light turnover - not max effort | Full recovery between each (60-90 seconds)';
      const expected =
        'Target pace: 5:34/km | Strides maintain leg speed without fatigue | Focus on quick, light turnover - not max effort | Full recovery between each (60-90 seconds)';
      expect(formatPaceTextForUnit(stridesNotes, 'metric')).toBe(expected);
    });

    it('renders the strides description', () => {
      const stridesDesc =
        'Easy run at 8:58/mi, then 6×20s strides. Strides: accelerate smoothly to ~90% effort over 15-20 seconds, hold 5 seconds, decelerate. Walk back to start. Stay relaxed, not sprinting.';
      const result = formatPaceTextForUnit(stridesDesc, 'metric');
      expect(result).toContain('Easy run at 5:34/km, then 6×20s strides.');
      expect(result).not.toContain('/mi');
    });
  });

  describe('imperial viewer (existing imperial users)', () => {
    it('leaves the description untouched', () => {
      expect(formatPaceTextForUnit(DEJAN_DESCRIPTION, 'imperial')).toBe(DEJAN_DESCRIPTION);
    });

    it('leaves the coach_notes untouched', () => {
      expect(formatPaceTextForUnit(DEJAN_COACH_NOTES, 'imperial')).toBe(DEJAN_COACH_NOTES);
    });
  });
});
