/**
 * React Query hooks for unified reports
 */

import { useQuery } from '@tanstack/react-query';
import { reportService, type ReportCategory } from '@/lib/api/services/reports';

export const reportKeys = {
  all: ['reports'] as const,
  report: (start: string, end: string, cats: ReportCategory[]) =>
    ['reports', start, end, cats.sort().join(',')] as const,
};

export function useReport(params: {
  start_date: string;
  end_date: string;
  categories: ReportCategory[];
}) {
  return useQuery({
    queryKey: reportKeys.report(params.start_date, params.end_date, params.categories),
    queryFn: () => reportService.getReport(params),
    staleTime: 60_000,
    enabled: !!params.start_date && !!params.end_date && params.categories.length > 0,
  });
}
