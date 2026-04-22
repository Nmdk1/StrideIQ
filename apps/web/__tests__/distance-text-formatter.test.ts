import { formatDistanceTextForUnit, formatTextForUnit } from '@/lib/utils/paceText';

describe('formatDistanceTextForUnit', () => {
  describe('passthrough cases', () => {
    it('returns empty string when input is null or undefined', () => {
      expect(formatDistanceTextForUnit(null, 'metric')).toBe('');
      expect(formatDistanceTextForUnit(undefined, 'imperial')).toBe('');
    });

    it('returns the original text when no distance literal is present', () => {
      expect(formatDistanceTextForUnit('Long run, easy effort.', 'metric')).toBe(
        'Long run, easy effort.',
      );
    });

    it('leaves text untouched when source unit matches target unit', () => {
      expect(formatDistanceTextForUnit('Run 16 mi today.', 'imperial')).toBe('Run 16 mi today.');
      expect(formatDistanceTextForUnit('Run 26 km today.', 'metric')).toBe('Run 26 km today.');
    });
  });

  describe('mi -> km conversion', () => {
    it('converts a whole-number distance', () => {
      expect(formatDistanceTextForUnit('Run 10 mi', 'metric')).toBe('Run 16 km');
    });

    it('converts a decimal distance under 10', () => {
      // 5 mi = 8.0467 km -> 8.0
      expect(formatDistanceTextForUnit('Long run 5 mi', 'metric')).toBe('Long run 8.0 km');
    });

    it('rounds distances >= 10 km to whole numbers', () => {
      // 16 mi = 25.7494 km -> 26
      expect(formatDistanceTextForUnit('Long run 16 mi', 'metric')).toBe('Long run 26 km');
    });

    it('converts a distance range', () => {
      // 3-5 mi -> 4.8-8.0 km
      expect(formatDistanceTextForUnit('Tempo 3-5 mi at threshold', 'metric')).toBe(
        'Tempo 4.8-8.0 km at threshold',
      );
    });

    it('preserves an optional ~ prefix', () => {
      expect(formatDistanceTextForUnit('Easy ~6 mi', 'metric')).toBe('Easy ~9.7 km');
    });

    it('handles attached and spaced suffixes', () => {
      expect(formatDistanceTextForUnit('Run 6mi', 'metric')).toBe('Run 9.7 km');
      expect(formatDistanceTextForUnit('Run 6 mi', 'metric')).toBe('Run 9.7 km');
    });
  });

  describe('km -> mi conversion', () => {
    it('converts a whole-number distance', () => {
      // 16 km = 9.94 mi -> 9.9
      expect(formatDistanceTextForUnit('Run 16 km', 'imperial')).toBe('Run 9.9 mi');
    });

    it('converts a decimal distance over 10', () => {
      // 26 km = 16.155 mi -> 16
      expect(formatDistanceTextForUnit('Long run 26 km', 'imperial')).toBe('Long run 16 mi');
    });
  });
});

describe('formatTextForUnit (combined pace + distance)', () => {
  it('rewrites both pace and distance in the same string for metric', () => {
    expect(formatTextForUnit('Run 16 mi at 8:24/mi pace', 'metric')).toBe(
      'Run 26 km at 5:13/km pace',
    );
  });

  it('rewrites only pace when distance is already in target unit', () => {
    expect(formatTextForUnit('Run 16 km at 8:24/mi pace', 'metric')).toBe(
      'Run 16 km at 5:13/km pace',
    );
  });

  it('passes through cleanly for imperial when input is imperial', () => {
    expect(formatTextForUnit('Run 16 mi at 8:24/mi pace', 'imperial')).toBe(
      'Run 16 mi at 8:24/mi pace',
    );
  });
});
