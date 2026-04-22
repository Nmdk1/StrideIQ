/**
 * Date utilities — local-timezone-aware date strings.
 *
 * `new Date().toISOString().split('T')[0]` returns the UTC date, which is
 * wrong for users west of UTC after their local midnight diverges from UTC
 * midnight (e.g. 8 PM CDT Sunday = 1 AM UTC Monday → returns Monday).
 *
 * `localToday()` returns the YYYY-MM-DD string in the user's local timezone.
 */

/**
 * Return today's date as a YYYY-MM-DD string in the user's local timezone.
 */
export function localToday(): string {
  return new Date().toLocaleDateString('en-CA');
}
