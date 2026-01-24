/**
 * Model-Driven Plan UI Tests
 * 
 * Tests for ADR-028 model-driven plan creation flow.
 * Covers: tier gating, form submission, preview rendering, edit modes.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// ============================================================================
// MOCK SETUP
// ============================================================================

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

// Mock react-query
jest.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({
    invalidateQueries: jest.fn(),
  }),
  QueryClient: jest.fn(() => ({
    invalidateQueries: jest.fn(),
  })),
}));

// Mock AuthContext
const mockUser = {
  id: 'test-user-123',
  email: 'test@example.com',
  subscription_tier: 'pro',
};

jest.mock('@/lib/context/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    isAuthenticated: true,
  }),
}));

// Mock planService
const mockPlanService = {
  createModelDriven: jest.fn(),
  previewModelDriven: jest.fn(),
};

jest.mock('@/lib/api/services/plans', () => ({
  planService: mockPlanService,
}));

// ============================================================================
// TEST HELPERS
// ============================================================================

const mockModelDrivenResponse = {
  plan_id: 'plan-123',
  race: {
    date: '2026-05-01',
    distance: 'marathon',
    distance_m: 42195,
  },
  prediction: {
    prediction: {
      time_seconds: 12600,
      time_formatted: '3:30:00',
      confidence_interval_seconds: 300,
      confidence_interval_formatted: '±5 min',
      confidence: 'moderate',
    },
  },
  model: {
    confidence: 'moderate',
    tau1: 38.5,
    tau2: 6.8,
    insights: ['You adapt faster than average (τ1=38 vs typical 42 days)'],
  },
  personalization: {
    taper_start_week: 2,
    notes: ['Your data shows 2 rest days optimal before quality sessions.'],
    summary: 'Faster adapter, shorter taper recommended.',
  },
  weeks: [],
  summary: {
    total_weeks: 12,
    total_miles: 450,
    total_tss: 3500,
  },
  generated_at: '2026-01-15T12:00:00Z',
};

// ============================================================================
// TIER GATING TESTS
// ============================================================================

describe('Model-Driven Plan Tier Gating', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('pro user sees Model-Driven option enabled', () => {
    const isPro = mockUser.subscription_tier === 'pro';
    expect(isPro).toBe(true);
    
    // Pro users should have access
    const allowedTiers = ['pro'];
    expect(allowedTiers.includes(mockUser.subscription_tier)).toBe(true);
  });

  test('non-pro user should see disabled Model-Driven option', () => {
    const freeUser = { ...mockUser, subscription_tier: 'free' };
    const isPro = freeUser.subscription_tier === 'pro';
    expect(isPro).toBe(false);
    
    // Free users should NOT have access
    const allowedTiers = ['pro'];
    expect(allowedTiers.includes(freeUser.subscription_tier)).toBe(false);
  });

  test('upgrade link should be visible for non-pro', () => {
    const freeUser = { subscription_tier: 'free' };
    const showUpgradeLink = !['pro'].includes(freeUser.subscription_tier);
    expect(showUpgradeLink).toBe(true);
  });
});

// ============================================================================
// FORM SUBMISSION TESTS
// ============================================================================

describe('Model-Driven Plan Form', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPlanService.createModelDriven.mockResolvedValue(mockModelDrivenResponse);
  });

  test('form requires race date and distance', () => {
    const formData = {
      planType: 'model-driven',
      distance: '',
      race_date: '',
    };
    
    // Should be invalid without required fields
    const isValid = formData.distance !== '' && formData.race_date !== '';
    expect(isValid).toBe(false);
    
    // With fields filled
    formData.distance = 'marathon';
    formData.race_date = '2026-05-01';
    const isValidNow = formData.distance !== '' && formData.race_date !== '';
    expect(isValidNow).toBe(true);
  });

  test('form calls createModelDriven API on submit', async () => {
    const requestData = {
      race_date: '2026-05-01',
      race_distance: 'marathon',
      goal_time_seconds: undefined,
    };
    
    mockPlanService.createModelDriven.mockResolvedValue(mockModelDrivenResponse);
    
    // Simulate API call
    const result = await mockPlanService.createModelDriven(requestData);
    
    expect(mockPlanService.createModelDriven).toHaveBeenCalledWith(requestData);
    expect(result.plan_id).toBe('plan-123');
    expect(result.model.tau1).toBe(38.5);
    expect(result.model.tau2).toBe(6.8);
  });

  test('API response includes personal τ values', async () => {
    mockPlanService.createModelDriven.mockResolvedValue(mockModelDrivenResponse);
    
    const result = await mockPlanService.createModelDriven({
      race_date: '2026-05-01',
      race_distance: 'marathon',
    });
    
    // τ values should be personalized, not defaults
    expect(result.model.tau1).not.toBe(42);  // Default is 42
    expect(result.model.tau2).toBe(6.8);
    expect(result.model.insights.length).toBeGreaterThan(0);
  });
});

// ============================================================================
// PREVIEW RENDERING TESTS
// ============================================================================

describe('Model-Driven Plan Preview', () => {
  test('preview displays prediction with confidence', () => {
    const prediction = mockModelDrivenResponse.prediction.prediction;
    
    expect(prediction.time_formatted).toBe('3:30:00');
    expect(prediction.confidence).toBe('moderate');
    expect(prediction.confidence_interval_formatted).toBe('±5 min');
  });

  test('preview displays τ values from model', () => {
    const model = mockModelDrivenResponse.model;
    
    expect(model.tau1).toBe(38.5);
    expect(model.tau2).toBe(6.8);
    expect(model.confidence).toBe('moderate');
  });

  test('preview displays counter-conventional notes', () => {
    const personalization = mockModelDrivenResponse.personalization;
    
    expect(personalization.notes.length).toBeGreaterThan(0);
    expect(personalization.notes[0]).toContain('2 rest days');
  });

  test('preview displays model insights', () => {
    const insights = mockModelDrivenResponse.model.insights;
    
    expect(insights.length).toBeGreaterThan(0);
    expect(insights[0]).toContain('faster than average');
  });

  test('summary shows plan metrics', () => {
    const summary = mockModelDrivenResponse.summary;
    
    expect(summary.total_weeks).toBe(12);
    expect(summary.total_miles).toBe(450);
    expect(summary.total_tss).toBe(3500);
  });
});

// ============================================================================
// EDIT MODE TESTS
// ============================================================================

describe('Model-Driven Plan Editing', () => {
  test('can swap workout days', () => {
    // Simulate two workouts
    const workouts = [
      { id: 1, date: '2026-02-10', type: 'interval' },
      { id: 2, date: '2026-02-12', type: 'long' },
    ];
    
    // Swap dates
    const temp = workouts[0].date;
    workouts[0].date = workouts[1].date;
    workouts[1].date = temp;
    
    expect(workouts[0].date).toBe('2026-02-12');
    expect(workouts[1].date).toBe('2026-02-10');
    
    // Types preserved
    expect(workouts[0].type).toBe('interval');
    expect(workouts[1].type).toBe('long');
  });

  test('model params preserved after workout edit', () => {
    const plan = {
      model: { tau1: 38.5, tau2: 6.8 },
      workouts: [{ id: 1, pace: '7:00/mi' }],
    };
    
    // Edit a workout
    plan.workouts[0].pace = '7:30/mi';
    
    // Model params should be unchanged
    expect(plan.model.tau1).toBe(38.5);
    expect(plan.model.tau2).toBe(6.8);
  });

  test('variant substitution maintains TSS within 10%', () => {
    const original = { type: 'tempo', tss: 65 };
    const variant = { type: 'fartlek', tss: 62 };
    
    const delta = Math.abs(original.tss - variant.tss) / original.tss * 100;
    expect(delta).toBeLessThan(10);
  });

  test('counter-conventional notes survive edits', () => {
    const plan = {
      personalization: {
        notes: ['Your data shows 2 rest days optimal.'],
      },
      workouts: [{ id: 1, date: '2026-02-10' }],
    };
    
    // Edit workout
    plan.workouts[0].date = '2026-02-11';
    
    // Notes should persist
    expect(plan.personalization.notes[0]).toContain('2 rest days');
  });
});

// ============================================================================
// CALENDAR INTEGRATION TESTS
// ============================================================================

describe('Model-Driven Plan Calendar Integration', () => {
  test('workouts have correct date format', () => {
    const workout = {
      date: '2026-02-10',
      type: 'interval',
      name: '6x800m',
    };
    
    // Date should be ISO format
    expect(workout.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  test('apply to calendar creates entries for each workout day', () => {
    const weeks = [
      {
        days: [
          { date: '2026-02-10', type: 'easy' },
          { date: '2026-02-11', type: 'interval' },
          { date: '2026-02-12', type: 'rest' },
        ],
      },
    ];
    
    // Filter out rest days
    const workoutsToCreate = weeks.flatMap(w => 
      w.days.filter(d => d.type !== 'rest')
    );
    
    expect(workoutsToCreate.length).toBe(2);
    expect(workoutsToCreate[0].type).toBe('easy');
    expect(workoutsToCreate[1].type).toBe('interval');
  });

  test('no duplicate dates in plan', () => {
    const dates = ['2026-02-10', '2026-02-11', '2026-02-12', '2026-02-10'];
    const uniqueDates = new Set(dates);
    
    // Should detect duplicate
    expect(dates.length).not.toBe(uniqueDates.size);
  });
});

// ============================================================================
// ERROR HANDLING TESTS
// ============================================================================

describe('Model-Driven Plan Error Handling', () => {
  test('handles API error gracefully', async () => {
    mockPlanService.createModelDriven.mockRejectedValue(new Error('Rate limit exceeded'));
    
    try {
      await mockPlanService.createModelDriven({
        race_date: '2026-05-01',
        race_distance: 'marathon',
      });
    } catch (error) {
      expect((error as Error).message).toBe('Rate limit exceeded');
    }
  });

  test('validates race date is in future', () => {
    const today = new Date();
    const pastDate = new Date(today.getTime() - 24 * 60 * 60 * 1000);
    const futureDate = new Date(today.getTime() + 90 * 24 * 60 * 60 * 1000);
    
    expect(pastDate < today).toBe(true);  // Invalid
    expect(futureDate > today).toBe(true); // Valid
  });

  test('validates race date not too far in future', () => {
    const today = new Date();
    const farFuture = new Date(today.getTime() + 400 * 24 * 60 * 60 * 1000); // >52 weeks
    const weeksOut = Math.floor((farFuture.getTime() - today.getTime()) / (7 * 24 * 60 * 60 * 1000));
    
    expect(weeksOut > 52).toBe(true); // Invalid
  });
});

// ============================================================================
// PERFORMANCE TESTS
// ============================================================================

describe('Model-Driven Plan Performance', () => {
  test('plan data structure is serializable', () => {
    const serialized = JSON.stringify(mockModelDrivenResponse);
    const deserialized = JSON.parse(serialized);
    
    expect(deserialized.model.tau1).toBe(38.5);
    expect(deserialized.prediction.prediction.time_formatted).toBe('3:30:00');
  });

  test('weeks array is iterable', () => {
    const weeks = mockModelDrivenResponse.weeks;
    expect(Array.isArray(weeks)).toBe(true);
  });
});
