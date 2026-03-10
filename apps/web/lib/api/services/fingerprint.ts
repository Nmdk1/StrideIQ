import { apiClient } from '../client';

export interface RaceCard {
  event_id: string | null;
  activity_id: string;
  name: string | null;
  date: string;
  time_of_day: string | null;
  day_of_week: string | null;
  distance_category: string;
  distance_meters: number;
  pace_display: string;
  duration_display: string;
  avg_hr: number | null;
  detection_confidence: number | null;
  detection_source: string | null;
  user_confirmed: boolean | null;
  is_personal_best: boolean;
}

export interface RacePin {
  event_id: string;
  date: string;
  distance_category: string;
  time_seconds: number;
  is_personal_best: boolean;
  performance_percentage: number | null;
}

export interface WeekData {
  week_start: string;
  total_volume_km: number;
  intensity: string;
  activity_count: number;
}

export interface RacingLifeStripData {
  weeks: WeekData[];
  pins: RacePin[];
}

export interface RaceCandidateResponse {
  confirmed: RaceCard[];
  candidates: RaceCard[];
  browse_count: number;
  strip_data: RacingLifeStripData;
}

export interface BrowseResponse {
  items: RaceCard[];
  total: number;
  offset: number;
  limit: number;
}

export async function getRaceCandidates(): Promise<RaceCandidateResponse> {
  return apiClient.get<RaceCandidateResponse>('/v1/fingerprint/race-candidates');
}

export async function browseActivities(params: {
  distance_category?: string;
  day_of_week?: string;
  limit?: number;
  offset?: number;
}): Promise<BrowseResponse> {
  const query = new URLSearchParams();
  if (params.distance_category) query.set('distance_category', params.distance_category);
  if (params.day_of_week) query.set('day_of_week', params.day_of_week);
  if (params.limit) query.set('limit', String(params.limit));
  if (params.offset) query.set('offset', String(params.offset));
  return apiClient.get<BrowseResponse>(`/v1/fingerprint/browse?${query.toString()}`);
}

export async function confirmRace(eventId: string, confirmed: boolean): Promise<{ status: string; strip_data: RacingLifeStripData }> {
  return apiClient.post(`/v1/fingerprint/confirm-race/${eventId}?confirmed=${confirmed}`);
}

export async function addRace(activityId: string): Promise<{ status: string; event_id: string; strip_data: RacingLifeStripData }> {
  return apiClient.post(`/v1/fingerprint/add-race/${activityId}`);
}

export async function getStripData(): Promise<{ strip_data: RacingLifeStripData }> {
  return apiClient.get('/v1/fingerprint/strip');
}
