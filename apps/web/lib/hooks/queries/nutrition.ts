/**
 * React Query hooks for nutrition
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  nutritionService,
  type NutritionEntryCreate,
  type NutritionEntryUpdate,
  type NutritionEntry,
  type PhotoParseResult,
  type BarcodeScanResult,
  type FuelingProduct,
  type FuelingProfileEntry,
  type NutritionSummary,
  type ActivityNutritionResponse,
  type NutritionGoal,
  type NutritionGoalRequest,
  type DailyTarget,
  type MealTemplate,
  type MealTemplateCreate,
  type MealTemplateUpdate,
  type MealTemplateLogRequest,
} from '../../api/services/nutrition';

export type { NutritionEntry, PhotoParseResult, BarcodeScanResult, FuelingProduct, FuelingProfileEntry, NutritionSummary, ActivityNutritionResponse, NutritionGoal, DailyTarget, MealTemplate, MealTemplateCreate, MealTemplateUpdate, MealTemplateLogRequest };

export const nutritionKeys = {
  all: ['nutrition'] as const,
  lists: () => [...nutritionKeys.all, 'list'] as const,
  list: (params?: Record<string, unknown>) => [...nutritionKeys.lists(), params] as const,
  detail: (id: string) => [...nutritionKeys.all, 'detail', id] as const,
  nlParsingAvailable: () => [...nutritionKeys.all, 'nlParsingAvailable'] as const,
  fuelingProducts: (params?: Record<string, unknown>) => [...nutritionKeys.all, 'fuelingProducts', params] as const,
  fuelingProfile: () => [...nutritionKeys.all, 'fuelingProfile'] as const,
  summary: (days: number) => [...nutritionKeys.all, 'summary', days] as const,
  activityLinked: (days: number) => [...nutritionKeys.all, 'activityLinked', days] as const,
  goal: () => [...nutritionKeys.all, 'goal'] as const,
  dailyTarget: (date?: string) => [...nutritionKeys.all, 'dailyTarget', date] as const,
  meals: () => [...nutritionKeys.all, 'meals'] as const,
} as const;

export function useNLParsingAvailable() {
  return useQuery<{ available: boolean }>({
    queryKey: nutritionKeys.nlParsingAvailable(),
    queryFn: () => nutritionService.nlParsingAvailable(),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

export function useNutritionEntries(params?: {
  start_date?: string;
  end_date?: string;
  entry_type?: string;
  activity_id?: string;
}) {
  return useQuery<NutritionEntry[]>({
    queryKey: nutritionKeys.list(params as Record<string, unknown>),
    queryFn: () => nutritionService.listEntries(params),
    staleTime: 30 * 1000,
  });
}

export function useNutritionEntry(id: string) {
  return useQuery<NutritionEntry>({
    queryKey: nutritionKeys.detail(id),
    queryFn: () => nutritionService.getEntry(id),
    enabled: !!id,
  });
}

export function useCreateNutritionEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (entry: NutritionEntryCreate) => nutritionService.createEntry(entry),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.lists() });
    },
  });
}

export function useParseNutritionText() {
  return useMutation({
    mutationFn: (text: string) => nutritionService.parseText(text),
    retry: false,
  });
}

export function useParsePhoto() {
  return useMutation<PhotoParseResult, Error, File>({
    mutationFn: (file: File) => nutritionService.parsePhoto(file),
    retry: false,
  });
}

export function useScanBarcode() {
  return useMutation<BarcodeScanResult, Error, string>({
    mutationFn: (upc: string) => nutritionService.scanBarcode(upc),
    retry: false,
  });
}

export function useFuelingProducts(params?: { brand?: string; category?: string; search?: string }) {
  return useQuery<FuelingProduct[]>({
    queryKey: nutritionKeys.fuelingProducts(params as Record<string, unknown>),
    queryFn: () => nutritionService.listFuelingProducts(params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useFuelingProfile() {
  return useQuery<FuelingProfileEntry[]>({
    queryKey: nutritionKeys.fuelingProfile(),
    queryFn: () => nutritionService.getFuelingProfile(),
    staleTime: 60 * 1000,
  });
}

export function useAddToProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { productId: number; usageContext?: string; notes?: string }) =>
      nutritionService.addToProfile(data.productId, data.usageContext, data.notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.fuelingProfile() });
    },
  });
}

export function useRemoveFromProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (productId: number) => nutritionService.removeFromProfile(productId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.fuelingProfile() });
    },
  });
}

export function useLogFueling() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { product_id: number; entry_type?: string; activity_id?: string; quantity?: number; date?: string }) =>
      nutritionService.logFueling(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.lists() });
    },
  });
}

export function useUpdateNutritionEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: NutritionEntryUpdate }) =>
      nutritionService.updateEntry(id, updates),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.detail(data.id) });
      queryClient.invalidateQueries({ queryKey: nutritionKeys.lists() });
    },
  });
}

export function useDeleteNutritionEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => nutritionService.deleteEntry(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.all });
    },
  });
}

export function useNutritionSummary(days: number = 7) {
  return useQuery<NutritionSummary>({
    queryKey: nutritionKeys.summary(days),
    queryFn: () => nutritionService.getSummary(days),
    staleTime: 60 * 1000,
  });
}

export function useActivityLinkedNutrition(days: number = 30) {
  return useQuery<ActivityNutritionResponse>({
    queryKey: nutritionKeys.activityLinked(days),
    queryFn: () => nutritionService.getActivityLinked(days),
    staleTime: 60 * 1000,
  });
}

export function useNutritionGoal() {
  return useQuery<NutritionGoal | null>({
    queryKey: nutritionKeys.goal(),
    queryFn: () => nutritionService.getGoal(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useUpsertNutritionGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (goal: NutritionGoalRequest) => nutritionService.upsertGoal(goal),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.goal() });
      queryClient.invalidateQueries({ queryKey: nutritionKeys.all });
    },
  });
}

export function useDailyTarget(targetDate?: string) {
  return useQuery<DailyTarget | null>({
    queryKey: nutritionKeys.dailyTarget(targetDate),
    queryFn: () => nutritionService.getDailyTarget(targetDate),
    staleTime: 60 * 1000,
  });
}

export function useMealTemplates() {
  return useQuery<MealTemplate[]>({
    queryKey: nutritionKeys.meals(),
    queryFn: () => nutritionService.listMeals(),
    staleTime: 30 * 1000,
  });
}

export function useCreateMealTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (meal: MealTemplateCreate) => nutritionService.createMeal(meal),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.meals() });
    },
  });
}

export function useUpdateMealTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, updates }: { id: number; updates: MealTemplateUpdate }) =>
      nutritionService.updateMeal(id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.meals() });
    },
  });
}

export function useDeleteMealTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => nutritionService.deleteMeal(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.meals() });
    },
  });
}

export function useLogMealTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: MealTemplateLogRequest }) =>
      nutritionService.logMeal(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nutritionKeys.lists() });
      queryClient.invalidateQueries({ queryKey: nutritionKeys.summary(7) });
      queryClient.invalidateQueries({ queryKey: nutritionKeys.meals() });
    },
  });
}
