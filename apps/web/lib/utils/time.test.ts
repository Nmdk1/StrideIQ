/**
 * Tests for time conversion utilities
 */

import { parseTimeToSeconds, formatSecondsToTime, formatPace } from './time';

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
