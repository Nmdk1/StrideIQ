/**
 * Calendar React Query Hooks
 * 
 * The calendar is the central UI hub. These hooks provide
 * reactive data access for all calendar functionality.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { calendarService, CreateNoteRequest, CoachMessageRequest } from '@/lib/api/services/calendar';

// Query keys
export const calendarKeys = {
  all: ['calendar'] as const,
  range: (startDate?: string, endDate?: string) => [...calendarKeys.all, 'range', startDate, endDate] as const,
  day: (date: string) => [...calendarKeys.all, 'day', date] as const,
  week: (weekNumber: number) => [...calendarKeys.all, 'week', weekNumber] as const,
};

/**
 * Get calendar data for a date range
 * Defaults to current month if no dates provided
 */
export function useCalendarRange(startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: calendarKeys.range(startDate, endDate),
    queryFn: () => calendarService.getCalendar(startDate, endDate),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * Get full details for a specific day
 */
export function useCalendarDay(date: string, enabled = true) {
  return useQuery({
    queryKey: calendarKeys.day(date),
    queryFn: () => calendarService.getDay(date),
    enabled,
    staleTime: 1000 * 60 * 2, // 2 minutes
  });
}

/**
 * Get detailed view of a specific training week
 */
export function useCalendarWeek(weekNumber: number, enabled = true) {
  return useQuery({
    queryKey: calendarKeys.week(weekNumber),
    queryFn: () => calendarService.getWeek(weekNumber),
    enabled,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * Add a note to a calendar day
 */
export function useAddNote() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ date, note }: { date: string; note: CreateNoteRequest }) => 
      calendarService.addNote(date, note),
    onSuccess: (_, { date }) => {
      // Invalidate the day and range queries
      queryClient.invalidateQueries({ queryKey: calendarKeys.day(date) });
      queryClient.invalidateQueries({ queryKey: calendarKeys.all });
    },
  });
}

/**
 * Delete a note
 */
export function useDeleteNote() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ date, noteId }: { date: string; noteId: string }) => 
      calendarService.deleteNote(date, noteId),
    onSuccess: (_, { date }) => {
      queryClient.invalidateQueries({ queryKey: calendarKeys.day(date) });
      queryClient.invalidateQueries({ queryKey: calendarKeys.all });
    },
  });
}

/**
 * Send a message to the coach
 */
export function useSendCoachMessage() {
  return useMutation({
    mutationFn: (request: CoachMessageRequest) => 
      calendarService.sendCoachMessage(request),
  });
}
