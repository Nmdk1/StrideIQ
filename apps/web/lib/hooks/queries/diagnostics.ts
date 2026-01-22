import { useQuery } from '@tanstack/react-query';
import { diagnosticsService } from '@/lib/api/services/diagnostics';

export const useDiagnosticsSummary = (opts?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: ['diagnostics', 'summary'],
    queryFn: () => diagnosticsService.getSummary(),
    staleTime: 60 * 1000, // 1 minute
    retry: 1,
    enabled: opts?.enabled ?? true,
  });
};

