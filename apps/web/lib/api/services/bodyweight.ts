/**
 * Bodyweight quick-entry service (Strength v1 sandbox).
 *
 * Wraps the existing /v1/body-composition endpoints — we are
 * piggybacking on the table that already stores weight_kg, body_fat_pct,
 * etc. The strength sandbox just needs a fast path to log today's
 * weight, not a new table.
 *
 * lbs ↔ kg conversion happens here so the rest of the UI stays in
 * the athlete's preferred unit.
 */

import { apiClient } from '../client';

export interface BodyCompEntry {
  id: string;
  athlete_id: string;
  date: string;
  weight_kg?: number | null;
  body_fat_pct?: number | null;
  muscle_mass_kg?: number | null;
  bmi?: number | null;
  notes?: string | null;
  created_at: string;
}

export interface BodyCompCreate {
  athlete_id: string;
  date: string;
  weight_kg?: number | null;
  body_fat_pct?: number | null;
  muscle_mass_kg?: number | null;
  notes?: string | null;
}

export const KG_TO_LBS = 2.20462262;
export const LBS_TO_KG = 1 / KG_TO_LBS;

export const bodyweightService = {
  async list(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<BodyCompEntry[]> {
    const qs = new URLSearchParams();
    if (params?.start_date) qs.set('start_date', params.start_date);
    if (params?.end_date) qs.set('end_date', params.end_date);
    const suffix = qs.toString() ? `?${qs}` : '';
    return apiClient.get<BodyCompEntry[]>(`/v1/body-composition${suffix}`);
  },

  async create(payload: BodyCompCreate): Promise<BodyCompEntry> {
    return apiClient.post<BodyCompEntry>('/v1/body-composition', payload);
  },

  async update(
    id: string,
    payload: BodyCompCreate,
  ): Promise<BodyCompEntry> {
    return apiClient.put<BodyCompEntry>(
      `/v1/body-composition/${id}`,
      payload,
    );
  },

  async upsertToday(opts: {
    athleteId: string;
    weightLbs: number;
    bodyFatPct?: number | null;
    notes?: string | null;
  }): Promise<BodyCompEntry> {
    const today = new Date().toISOString().slice(0, 10);
    const payload: BodyCompCreate = {
      athlete_id: opts.athleteId,
      date: today,
      weight_kg: opts.weightLbs * LBS_TO_KG,
      body_fat_pct: opts.bodyFatPct ?? null,
      notes: opts.notes ?? null,
    };
    try {
      return await this.create(payload);
    } catch (err) {
      // 400 means today already has an entry; find it and update.
      const status = (err as { status?: number }).status;
      if (status !== 400) throw err;
      const existing = await this.list({
        start_date: today,
        end_date: today,
      });
      const todayEntry = existing.find((e) => e.date === today);
      if (!todayEntry) throw err;
      return this.update(todayEntry.id, payload);
    }
  },
};
