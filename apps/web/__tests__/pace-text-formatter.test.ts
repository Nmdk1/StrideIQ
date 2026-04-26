import { formatPaceTextForUnit } from '@/lib/utils/paceText';

describe('formatPaceTextForUnit', () => {
  describe('passthrough cases', () => {
    it('returns empty string when input is null', () => {
      expect(formatPaceTextForUnit(null, 'metric')).toBe('');
      expect(formatPaceTextForUnit(undefined, 'imperial')).toBe('');
    });

    it('returns the original text when no pace literal is present', () => {
      expect(formatPaceTextForUnit('Long run — easy effort.', 'metric')).toBe(
        'Long run — easy effort.',
      );
    });

    it('leaves text untouched when source unit matches target unit', () => {
      expect(formatPaceTextForUnit('Easy run at 8:58/mi.', 'imperial')).toBe('Easy run at 8:58/mi.');
      expect(formatPaceTextForUnit('Easy run at 5:34/km.', 'metric')).toBe('Easy run at 5:34/km.');
    });

    it('does not match distance literals like "16km" or "3-5mi"', () => {
      const text = '6km easy warmup, then 3-5mi at moderate effort.';
      expect(formatPaceTextForUnit(text, 'metric')).toBe(text);
      expect(formatPaceTextForUnit(text, 'imperial')).toBe(text);
    });

    it('does not match standalone numbers without M:SS shape', () => {
      const text = 'Bench: 225 lbs for 11 reps.';
      expect(formatPaceTextForUnit(text, 'metric')).toBe(text);
    });
  });

  describe('mi → km conversion (Dejan: imperial-baked descriptions, metric viewer)', () => {
    it('converts the canonical Dejan description', () => {
      expect(formatPaceTextForUnit('Easy aerobic run at 8:58/mi.', 'metric')).toBe(
        'Easy aerobic run at 5:34/km.',
      );
    });

    it('converts a coach_notes line', () => {
      expect(formatPaceTextForUnit('Target pace: 8:58/mi', 'metric')).toBe(
        'Target pace: 5:34/km',
      );
    });

    it('converts a marathon-pace literal', () => {
      // 8:24/mi = 504s/mi; 504/1.60934 = 313.18s/km = 5:13/km
      expect(formatPaceTextForUnit('marathon effort (8:24/mi)', 'metric')).toBe(
        'marathon effort (5:13/km)',
      );
    });

    it('converts pace ranges with optional ~ prefix', () => {
      // 9:06 = 546s/mi → 339.27s/km = 5:39/km
      // 9:36 = 576s/mi → 357.91s/km = 5:58/km
      expect(formatPaceTextForUnit('comfortable with purpose (~9:06-9:36/mi)', 'metric')).toBe(
        'comfortable with purpose (~5:39-5:58/km)',
      );
    });

    it('converts multiple pace literals in one string', () => {
      const input = '6×(3km at marathon effort (8:24/mi), 1km at ~9:06/mi).';
      const expected = '6×(3km at marathon effort (5:13/km), 1km at ~5:39/km).';
      expect(formatPaceTextForUnit(input, 'metric')).toBe(expected);
    });

    it('handles paces at the end of sentence with trailing period', () => {
      expect(formatPaceTextForUnit('Cooldown at 10:00/mi.', 'metric')).toBe(
        'Cooldown at 6:13/km.',
      );
    });
  });

  describe('km → mi conversion (metric-baked descriptions, imperial viewer)', () => {
    it('converts a metric pace to imperial', () => {
      // 5:34/km = 334s/km × 1.60934 = 537.5s/mi = 8:58/mi
      expect(formatPaceTextForUnit('Easy run at 5:34/km.', 'imperial')).toBe(
        'Easy run at 8:58/mi.',
      );
    });

    it('converts a metric pace range to imperial', () => {
      expect(formatPaceTextForUnit('threshold (5:39-5:58/km)', 'imperial')).toBe(
        'threshold (9:06-9:36/mi)',
      );
    });
  });

  describe('robustness', () => {
    it('does not match malformed pace strings', () => {
      expect(formatPaceTextForUnit('rest 0:60/mi', 'metric')).toBe('rest 0:60/mi');
      expect(formatPaceTextForUnit('rest 1:5/mi', 'metric')).toBe('rest 1:5/mi');
    });

    it('preserves non-pace numbers near pace literals', () => {
      expect(formatPaceTextForUnit('5×3min at 8:24/mi', 'metric')).toBe('5×3min at 5:13/km');
    });

    it('handles longer pace strings (10:00+)', () => {
      // 10:00/mi = 600s/mi → 372.83s/km = 6:13/km
      expect(formatPaceTextForUnit('jog at 10:00/mi', 'metric')).toBe('jog at 6:13/km');
      // 12:30/mi = 750s/mi → 466.04s/km = 7:46/km
      expect(formatPaceTextForUnit('walk at 12:30/mi', 'metric')).toBe('walk at 7:46/km');
    });
  });
});
