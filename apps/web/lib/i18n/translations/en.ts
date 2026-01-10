/**
 * English Translations (Default)
 * 
 * Tone: Sparse, irreverent, value-first. No coaching-speak.
 */

export const en = {
  // Navigation
  nav: {
    dashboard: 'Dashboard',
    checkin: 'Check-in',
    activities: 'Activities',
    discovery: 'Discovery',
    nutrition: 'Nutrition',
    profile: 'Profile',
    settings: 'Settings',
    login: 'Log in',
    register: 'Sign up',
    logout: 'Log out',
  },
  
  // Landing page
  landing: {
    hero: {
      title: 'Find what actually works for you',
      subtitle: 'Not what works for "most runners." What works for YOUR body.',
      cta: 'Start free',
    },
    value: {
      efficiency: 'Are you getting fitter or just tired?',
      correlations: 'What helps YOUR running? We find out.',
      personal: 'Your data. Your patterns. Your insights.',
    },
  },
  
  // Dashboard
  dashboard: {
    title: 'Efficiency Dashboard',
    subtitle: 'Are you getting fitter or just accumulating work?',
    noData: 'Need at least 3 quality activities with pace and heart rate data.',
    timeRange: {
      '30': 'Last 30 days',
      '60': 'Last 60 days',
      '90': 'Last 90 days',
      '180': 'Last 6 months',
      '365': 'Last year',
    },
  },
  
  // Check-in
  checkin: {
    title: 'Check-in',
    sleep: 'Sleep',
    stress: 'Stress',
    soreness: 'Soreness',
    hrv: 'HRV',
    restingHr: 'Resting HR',
    optional: 'Optional',
    submit: 'Done',
    skip: 'Skip for today',
    success: 'Logged.',
    labels: {
      sleepLow: '0h',
      sleepHigh: '12h',
      stressLow: 'Low',
      stressHigh: 'High',
      sorenessLow: 'Fresh',
      sorenessHigh: 'Very sore',
    },
  },
  
  // Discovery / Correlations
  discovery: {
    title: 'What Works For You',
    whatWorks: 'What helps',
    whatDoesnt: 'What doesn\'t help',
    noData: 'Not enough data yet. Keep logging for 2-3 weeks.',
    correlation: {
      strong: 'Strong pattern',
      moderate: 'Moderate pattern',
      weak: 'Weak pattern',
    },
  },
  
  // Nutrition
  nutrition: {
    title: 'Nutrition',
    addMeal: 'Add meal',
    logFood: 'What did you eat?',
    when: 'When',
    notes: 'Notes',
    placeholder: 'e.g., Oatmeal with banana, black coffee',
  },
  
  // Activities
  activities: {
    title: 'Activities',
    noActivities: 'No activities synced yet',
    connectStrava: 'Connect Strava',
    pace: 'Pace',
    heartRate: 'HR',
    efficiency: 'Efficiency',
  },
  
  // Profile
  profile: {
    title: 'Profile',
    personalInfo: 'Personal Info',
    metrics: 'Your Metrics',
    age: 'Age',
    weight: 'Weight',
    height: 'Height',
  },
  
  // Settings
  settings: {
    title: 'Settings',
    integrations: 'Integrations',
    preferences: 'Preferences',
    privacy: 'Privacy',
    exportData: 'Export my data',
    deleteAccount: 'Delete account',
  },
  
  // Auth
  auth: {
    login: 'Log in',
    register: 'Create account',
    email: 'Email',
    password: 'Password',
    forgotPassword: 'Forgot password?',
    noAccount: 'Don\'t have an account?',
    hasAccount: 'Already have an account?',
  },
  
  // Educational / Onboarding
  education: {
    whyLog: {
      title: 'Why log?',
      reason: 'The more you log, the more patterns we can find.',
    },
    dataQuality: {
      title: 'Data Quality',
      ready: 'Ready for insights',
      building: 'Building patterns...',
    },
    emptyStates: {
      nutrition: {
        title: 'No meals logged yet',
        description: 'When you log what you eat, we can find patterns like:',
        example: '"Your pace improves 3% when you eat carbs 2 hours before running."',
        cta: 'Log a meal',
      },
      checkin: {
        title: 'No check-ins yet',
        description: 'A 5-second morning check-in lets us find patterns like:',
        example: '"You run 8% faster after 7+ hours of sleep."',
        cta: 'Do quick check-in',
      },
      correlations: {
        title: 'Not enough data for correlations yet',
        description: 'We need about 2-3 weeks of logging to find what actually works for you.',
      },
    },
  },
  
  // Common
  common: {
    save: 'Save',
    cancel: 'Cancel',
    delete: 'Delete',
    edit: 'Edit',
    loading: 'Loading...',
    error: 'Something went wrong',
    retry: 'Try again',
    next: 'Next',
    back: 'Back',
    skip: 'Skip',
    done: 'Done',
  },
  
  // Units
  units: {
    km: 'km',
    mi: 'mi',
    kg: 'kg',
    lb: 'lb',
    cm: 'cm',
    ft: 'ft',
    bpm: 'bpm',
    hours: 'h',
    minutes: 'min',
    seconds: 's',
  },
};

// Type that allows string values for translations
type DeepStringRecord<T> = {
  [K in keyof T]: T[K] extends Record<string, unknown> ? DeepStringRecord<T[K]> : string;
};

export type TranslationKeys = DeepStringRecord<typeof en>;

