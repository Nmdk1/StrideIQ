/**
 * Nutrition API Service
 */

import { apiClient } from '../client';

export interface NutritionEntry {
  id: string;
  athlete_id: string;
  date: string;
  entry_type: 'pre_activity' | 'during_activity' | 'post_activity' | 'daily';
  activity_id?: string;
  calories?: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  fiber_g?: number;
  timing?: string;
  notes?: string;
  caffeine_mg?: number;
  fluid_ml?: number;
  carb_source?: string;
  glucose_fructose_ratio?: number;
  macro_source?: string;
  fueling_product_id?: number;
  created_at: string;
}

export interface NutritionEntryCreate {
  athlete_id: string;
  date: string;
  entry_type: 'pre_activity' | 'during_activity' | 'post_activity' | 'daily';
  activity_id?: string;
  calories?: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  fiber_g?: number;
  timing?: string;
  notes?: string;
  caffeine_mg?: number;
  fluid_ml?: number;
  carb_source?: string;
  glucose_fructose_ratio?: number;
  macro_source?: string;
  fueling_product_id?: number;
}

export interface NutritionEntryUpdate {
  date?: string;
  entry_type?: 'pre_activity' | 'during_activity' | 'post_activity' | 'daily';
  activity_id?: string;
  calories?: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  fiber_g?: number;
  timing?: string;
  notes?: string;
}

export interface PhotoParseItem {
  food: string;
  grams: number;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  macro_source: string;
  fdc_id?: number;
}

export interface PhotoParseResult {
  items: PhotoParseItem[];
  total_calories: number;
  total_protein_g: number;
  total_carbs_g: number;
  total_fat_g: number;
  total_fiber_g: number;
  template_match?: {
    template_id: number;
    meal_signature: string;
    items: Record<string, unknown>[];
    times_confirmed: number;
  };
}

export interface BarcodeScanResult {
  found: boolean;
  food_name?: string;
  serving_size_g?: number;
  calories?: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  fiber_g?: number;
  macro_source: string;
  fdc_id?: number;
}

export interface FuelingProduct {
  id: number;
  brand: string;
  product_name: string;
  variant?: string;
  category: string;
  serving_size_g?: number;
  calories?: number;
  carbs_g?: number;
  protein_g?: number;
  fat_g?: number;
  fiber_g?: number;
  caffeine_mg?: number;
  sodium_mg?: number;
  fluid_ml?: number;
  carb_source?: string;
  glucose_fructose_ratio?: number;
  is_verified?: boolean;
}

export interface FuelingProfileEntry {
  id: number;
  product_id: number;
  is_active: boolean;
  usage_context?: string;
  notes?: string;
  product: FuelingProduct;
}

export const nutritionService = {
  async nlParsingAvailable(): Promise<{ available: boolean }> {
    return apiClient.get<{ available: boolean }>('/v1/nutrition/parse/available', { skipAuth: true, retries: 0 });
  },

  async parseText(text: string): Promise<NutritionEntryCreate> {
    return apiClient.post<NutritionEntryCreate>('/v1/nutrition/parse', { text }, { retries: 0 });
  },

  async parsePhoto(imageFile: File): Promise<PhotoParseResult> {
    const formData = new FormData();
    formData.append('image', imageFile);
    return apiClient.post<PhotoParseResult>('/v1/nutrition/parse-photo', formData, { retries: 0 });
  },

  async scanBarcode(upc: string): Promise<BarcodeScanResult> {
    return apiClient.post<BarcodeScanResult>('/v1/nutrition/scan-barcode', { upc }, { retries: 0 });
  },

  async createEntry(entry: NutritionEntryCreate): Promise<NutritionEntry> {
    return apiClient.post<NutritionEntry>('/v1/nutrition', entry);
  },

  async listEntries(params?: {
    start_date?: string;
    end_date?: string;
    entry_type?: string;
    activity_id?: string;
  }): Promise<NutritionEntry[]> {
    const queryParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          queryParams.append(key, String(value));
        }
      });
    }
    const queryString = queryParams.toString();
    return apiClient.get<NutritionEntry[]>(`/v1/nutrition${queryString ? `?${queryString}` : ''}`);
  },

  async getEntry(id: string): Promise<NutritionEntry> {
    return apiClient.get<NutritionEntry>(`/v1/nutrition/${id}`);
  },

  async updateEntry(id: string, updates: NutritionEntryUpdate): Promise<NutritionEntry> {
    return apiClient.put<NutritionEntry>(`/v1/nutrition/${id}`, updates);
  },

  async deleteEntry(id: string): Promise<void> {
    return apiClient.delete<void>(`/v1/nutrition/${id}`);
  },

  async listFuelingProducts(params?: { brand?: string; category?: string; search?: string }): Promise<FuelingProduct[]> {
    const queryParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value) queryParams.append(key, value);
      });
    }
    const qs = queryParams.toString();
    return apiClient.get<FuelingProduct[]>(`/v1/nutrition/fueling-products${qs ? `?${qs}` : ''}`);
  },

  async createFuelingProduct(product: Omit<FuelingProduct, 'id' | 'is_verified'>): Promise<FuelingProduct> {
    return apiClient.post<FuelingProduct>('/v1/nutrition/fueling-products', product);
  },

  async getFuelingProfile(): Promise<FuelingProfileEntry[]> {
    return apiClient.get<FuelingProfileEntry[]>('/v1/nutrition/fueling-profile');
  },

  async addToProfile(productId: number, usageContext?: string, notes?: string): Promise<FuelingProfileEntry> {
    return apiClient.post<FuelingProfileEntry>('/v1/nutrition/fueling-profile', {
      product_id: productId,
      usage_context: usageContext,
      notes,
    });
  },

  async removeFromProfile(productId: number): Promise<void> {
    return apiClient.delete<void>(`/v1/nutrition/fueling-profile/${productId}`);
  },

  async logFueling(data: {
    product_id: number;
    entry_type?: string;
    activity_id?: string;
    quantity?: number;
    timing?: string;
  }): Promise<NutritionEntry> {
    return apiClient.post<NutritionEntry>('/v1/nutrition/log-fueling', data);
  },
} as const;
