import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  getRaceCandidates,
  browseActivities,
  confirmRace,
  addRace,
  type RaceCandidateResponse,
  type BrowseResponse,
  type RacingLifeStripData,
} from '@/lib/api/services/fingerprint';

export function useRaceCandidates() {
  return useQuery<RaceCandidateResponse>({
    queryKey: ['fingerprint', 'candidates'],
    queryFn: getRaceCandidates,
    staleTime: 1000 * 60 * 10,
    refetchOnWindowFocus: false,
  });
}

export function useBrowseActivities(params: {
  distance_category?: string;
  day_of_week?: string;
  limit?: number;
  offset?: number;
  enabled?: boolean;
}) {
  return useQuery<BrowseResponse>({
    queryKey: ['fingerprint', 'browse', params.distance_category, params.day_of_week, params.offset],
    queryFn: () => browseActivities({
      distance_category: params.distance_category,
      day_of_week: params.day_of_week,
      limit: params.limit || 50,
      offset: params.offset || 0,
    }),
    staleTime: 1000 * 60 * 5,
    enabled: params.enabled !== false,
  });
}

export function useConfirmRace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ eventId, confirmed }: { eventId: string; confirmed: boolean }) =>
      confirmRace(eventId, confirmed),
    onSuccess: (data) => {
      queryClient.setQueryData<RaceCandidateResponse>(['fingerprint', 'candidates'], (old) => {
        if (!old) return old;
        return {
          ...old,
          strip_data: data.strip_data,
        };
      });
      queryClient.invalidateQueries({ queryKey: ['fingerprint'] });
      toast.success(data.status === 'confirmed' ? 'Race confirmed' : 'Removed from races');
    },
    onError: () => toast.error('Failed to update race'),
  });
}

export function useAddRace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (activityId: string) => addRace(activityId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['fingerprint'] });
      toast.success('Race added to your history');
    },
    onError: () => toast.error('Failed to add race'),
  });
}
