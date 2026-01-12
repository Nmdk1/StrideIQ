/**
 * Home Page Queries
 */

import { useQuery } from '@tanstack/react-query';
import { getHomeData } from '@/lib/api/services/home';

export function useHomeData() {
  return useQuery({
    queryKey: ['home'],
    queryFn: getHomeData,
    staleTime: 1000 * 60 * 5, // 5 minutes
    refetchOnWindowFocus: true,
  });
}
