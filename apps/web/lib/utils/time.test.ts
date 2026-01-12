/**
 * Tests for time conversion utilities
 */

import { 
  parseTimeToSeconds, 
  formatSecondsToTime, 
  formatPace,
  formatDigitsToTime,
  stripToDigits,
} from './time';

describe('parseTimeToSeconds', () => {
  it('parses H:MM:SS format correctly', () => {
    expect(parseTimeToSeconds('4:30:15')).toBe(16215); // 4*3600 + 30*60 + 15
    expect(parseTimeToSeconds('1:00:00')).toBe(3600);
    expect(parseTimeToSeconds('0:20:00')).toBe(1200);
  });

  it('parses MM:SS format correctly', () => {
    expect(parseTimeToSeconds('30:00')).toBe(1800);
    expect(parseTimeToSeconds('5:30')).toBe(330);
    expect(parseTimeToSeconds('20:15')).toBe(1215);
  });

  it('handles edge cases for marathon times', () => {
    expect(parseTimeToSeconds('4:00:00')).toBe(14400); // 4 hour marathon
    expect(parseTimeToSeconds('3:30:00')).toBe(12600); // 3:30 marathon
    expect(parseTimeToSeconds('2:59:59')).toBe(10799); // sub-3 marathon
  });

  it('returns null for invalid inputs', () => {
    expect(parseTimeToSeconds('')).toBeNull();
    expect(parseTimeToSeconds('invalid')).toBeNull();
    expect(parseTimeToSeconds('1:2:3:4')).toBeNull(); // too many parts
    expect(parseTimeToSeconds('1')).toBeNull(); // too few parts
  });

  it('returns null for negative values', () => {
    expect(parseTimeToSeconds('-1:30:00')).toBeNull();
    expect(parseTimeToSeconds('1:-30:00')).toBeNull();
  });

  it('returns null for invalid minutes/seconds', () => {
    expect(parseTimeToSeconds('1:60:00')).toBeNull(); // 60 minutes invalid
    expect(parseTimeToSeconds('1:30:60')).toBeNull(); // 60 seconds invalid
  });

  it('handles null and undefined', () => {
    expect(parseTimeToSeconds(null as unknown as string)).toBeNull();
    expect(parseTimeToSeconds(undefined as unknown as string)).toBeNull();
  });
});

describe('formatSecondsToTime', () => {
  it('formats seconds with hours correctly', () => {
    expect(formatSecondsToTime(16215)).toBe('4:30:15');
    expect(formatSecondsToTime(3600)).toBe('1:00:00');
    expect(formatSecondsToTime(14400)).toBe('4:00:00');
  });

  it('formats seconds without hours correctly', () => {
    expect(formatSecondsToTime(1800)).toBe('30:00');
    expect(formatSecondsToTime(330)).toBe('5:30');
    expect(formatSecondsToTime(65)).toBe('1:05');
  });

  it('handles zero correctly', () => {
    expect(formatSecondsToTime(0)).toBe('0:00');
  });

  it('handles negative values', () => {
    expect(formatSecondsToTime(-100)).toBe('0:00');
  });
});

describe('formatPace', () => {
  it('formats pace correctly', () => {
    expect(formatPace(570)).toBe('9:30'); // 9:30/mi
    expect(formatPace(480)).toBe('8:00');
    expect(formatPace(365)).toBe('6:05');
  });

  it('handles edge cases', () => {
    expect(formatPace(0)).toBe('--:--');
    expect(formatPace(-1)).toBe('--:--');
    expect(formatPace(Infinity)).toBe('--:--');
  });
});

describe('formatDigitsToTime', () => {
  describe('hhmmss mode (default)', () => {
    it('returns empty string for empty input', () => {
      expect(formatDigitsToTime('')).toBe('');
    });

    it('returns 1-2 digits as-is (partial seconds)', () => {
      expect(formatDigitsToTime('1')).toBe('1');
      expect(formatDigitsToTime('12')).toBe('12');
    });

    it('formats 3 digits as M:SS', () => {
      expect(formatDigitsToTime('123')).toBe('1:23');
    });

    it('formats 4 digits as MM:SS', () => {
      expect(formatDigitsToTime('1234')).toBe('12:34');
      expect(formatDigitsToTime('1853')).toBe('18:53');
      expect(formatDigitsToTime('0530')).toBe('05:30');
    });

    it('formats 5 digits as H:MM:SS', () => {
      expect(formatDigitsToTime('12345')).toBe('1:23:45');
      expect(formatDigitsToTime('30000')).toBe('3:00:00');
    });

    it('formats 6 digits as HH:MM:SS', () => {
      expect(formatDigitsToTime('123456')).toBe('12:34:56');
      expect(formatDigitsToTime('040000')).toBe('04:00:00');
    });

    it('truncates input beyond 6 digits', () => {
      expect(formatDigitsToTime('1234567')).toBe('12:34:56');
      expect(formatDigitsToTime('12345678')).toBe('12:34:56');
    });

    it('strips non-digit characters', () => {
      expect(formatDigitsToTime('1:23:45')).toBe('1:23:45');
      expect(formatDigitsToTime('12:34')).toBe('12:34');
      expect(formatDigitsToTime('abc123')).toBe('1:23');
      expect(formatDigitsToTime('1-2-3-4')).toBe('12:34');
    });

    it('handles marathon times', () => {
      // 4:00:00 marathon
      expect(formatDigitsToTime('40000')).toBe('4:00:00');
      // 3:30:00 marathon
      expect(formatDigitsToTime('33000')).toBe('3:30:00');
      // 2:59:59 sub-3 marathon
      expect(formatDigitsToTime('25959')).toBe('2:59:59');
    });

    it('handles 5K times', () => {
      // 18:53 5K
      expect(formatDigitsToTime('1853')).toBe('18:53');
      // 25:00 5K
      expect(formatDigitsToTime('2500')).toBe('25:00');
    });
  });

  describe('mmss mode', () => {
    it('returns empty string for empty input', () => {
      expect(formatDigitsToTime('', 'mmss')).toBe('');
    });

    it('returns 1-2 digits as-is', () => {
      expect(formatDigitsToTime('1', 'mmss')).toBe('1');
      expect(formatDigitsToTime('12', 'mmss')).toBe('12');
    });

    it('formats 3 digits as M:SS', () => {
      expect(formatDigitsToTime('123', 'mmss')).toBe('1:23');
      expect(formatDigitsToTime('530', 'mmss')).toBe('5:30');
    });

    it('formats 4 digits as MM:SS', () => {
      expect(formatDigitsToTime('1234', 'mmss')).toBe('12:34');
      expect(formatDigitsToTime('0845', 'mmss')).toBe('08:45');
    });

    it('truncates input beyond 4 digits', () => {
      expect(formatDigitsToTime('12345', 'mmss')).toBe('12:34');
      expect(formatDigitsToTime('123456', 'mmss')).toBe('12:34');
    });

    it('strips non-digit characters', () => {
      expect(formatDigitsToTime('12:34', 'mmss')).toBe('12:34');
      expect(formatDigitsToTime('8:30', 'mmss')).toBe('8:30');
    });
  });
});

describe('stripToDigits', () => {
  it('removes colons from time strings', () => {
    expect(stripToDigits('1:23:45')).toBe('12345');
    expect(stripToDigits('18:53')).toBe('1853');
  });

  it('removes all non-digit characters', () => {
    expect(stripToDigits('abc123def')).toBe('123');
    expect(stripToDigits('1-2-3-4')).toBe('1234');
    expect(stripToDigits('  12 34  ')).toBe('1234');
  });

  it('returns empty string for no digits', () => {
    expect(stripToDigits('')).toBe('');
    expect(stripToDigits('abc')).toBe('');
    expect(stripToDigits(':::---')).toBe('');
  });

  it('preserves all digits', () => {
    expect(stripToDigits('0123456789')).toBe('0123456789');
  });
});
