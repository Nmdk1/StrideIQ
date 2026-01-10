/**
 * Spanish Translations
 * 
 * Target markets: Spain, Mexico, Argentina, Colombia, Chile, Peru
 * Tone: Same as English - sparse, direct, no fluff
 */

import type { TranslationKeys } from './en';

export const es: TranslationKeys = {
  // Navigation
  nav: {
    dashboard: 'Panel',
    checkin: 'Check-in',
    activities: 'Actividades',
    discovery: 'Descubrimientos',
    nutrition: 'Nutrición',
    profile: 'Perfil',
    settings: 'Ajustes',
    login: 'Iniciar sesión',
    register: 'Registrarse',
    logout: 'Cerrar sesión',
  },
  
  // Landing page
  landing: {
    hero: {
      title: 'Descubre qué funciona para ti',
      subtitle: 'No lo que funciona para "la mayoría". Lo que funciona para TU cuerpo.',
      cta: 'Empezar gratis',
    },
    value: {
      efficiency: '¿Estás mejorando o solo cansándote?',
      correlations: '¿Qué ayuda a TU running? Lo descubrimos.',
      personal: 'Tus datos. Tus patrones. Tus insights.',
    },
  },
  
  // Dashboard
  dashboard: {
    title: 'Panel de Eficiencia',
    subtitle: '¿Estás mejorando o solo acumulando trabajo?',
    noData: 'Necesitas al menos 3 actividades con ritmo y frecuencia cardíaca.',
    timeRange: {
      '30': 'Últimos 30 días',
      '60': 'Últimos 60 días',
      '90': 'Últimos 90 días',
      '180': 'Últimos 6 meses',
      '365': 'Último año',
    },
  },
  
  // Check-in
  checkin: {
    title: 'Check-in',
    sleep: 'Sueño',
    stress: 'Estrés',
    soreness: 'Dolor muscular',
    hrv: 'VFC',
    restingHr: 'FC reposo',
    optional: 'Opcional',
    submit: 'Listo',
    skip: 'Saltar por hoy',
    success: 'Registrado.',
    labels: {
      sleepLow: '0h',
      sleepHigh: '12h',
      stressLow: 'Bajo',
      stressHigh: 'Alto',
      sorenessLow: 'Fresco',
      sorenessHigh: 'Muy adolorido',
    },
  },
  
  // Discovery / Correlations
  discovery: {
    title: 'Qué Funciona Para Ti',
    whatWorks: 'Qué ayuda',
    whatDoesnt: 'Qué no ayuda',
    noData: 'Aún no hay suficientes datos. Sigue registrando 2-3 semanas.',
    correlation: {
      strong: 'Patrón fuerte',
      moderate: 'Patrón moderado',
      weak: 'Patrón débil',
    },
  },
  
  // Nutrition
  nutrition: {
    title: 'Nutrición',
    addMeal: 'Añadir comida',
    logFood: '¿Qué comiste?',
    when: 'Cuándo',
    notes: 'Notas',
    placeholder: 'ej., Avena con plátano, café negro',
  },
  
  // Activities
  activities: {
    title: 'Actividades',
    noActivities: 'No hay actividades sincronizadas',
    connectStrava: 'Conectar Strava',
    pace: 'Ritmo',
    heartRate: 'FC',
    efficiency: 'Eficiencia',
  },
  
  // Profile
  profile: {
    title: 'Perfil',
    personalInfo: 'Información Personal',
    metrics: 'Tus Métricas',
    age: 'Edad',
    weight: 'Peso',
    height: 'Altura',
  },
  
  // Settings
  settings: {
    title: 'Ajustes',
    integrations: 'Integraciones',
    preferences: 'Preferencias',
    privacy: 'Privacidad',
    exportData: 'Exportar mis datos',
    deleteAccount: 'Eliminar cuenta',
  },
  
  // Auth
  auth: {
    login: 'Iniciar sesión',
    register: 'Crear cuenta',
    email: 'Correo electrónico',
    password: 'Contraseña',
    forgotPassword: '¿Olvidaste tu contraseña?',
    noAccount: '¿No tienes cuenta?',
    hasAccount: '¿Ya tienes cuenta?',
  },
  
  // Educational / Onboarding
  education: {
    whyLog: {
      title: '¿Por qué registrar?',
      reason: 'Cuanto más registres, más patrones podemos encontrar.',
    },
    dataQuality: {
      title: 'Calidad de Datos',
      ready: 'Listo para insights',
      building: 'Construyendo patrones...',
    },
    emptyStates: {
      nutrition: {
        title: 'Sin comidas registradas',
        description: 'Cuando registras lo que comes, podemos encontrar patrones como:',
        example: '"Tu ritmo mejora 3% cuando comes carbohidratos 2 horas antes de correr."',
        cta: 'Registrar comida',
      },
      checkin: {
        title: 'Sin check-ins aún',
        description: 'Un check-in de 5 segundos nos permite encontrar patrones como:',
        example: '"Corres 8% más rápido después de 7+ horas de sueño."',
        cta: 'Hacer check-in rápido',
      },
      correlations: {
        title: 'Aún no hay suficientes datos para correlaciones',
        description: 'Necesitamos unas 2-3 semanas de registros para encontrar qué funciona para ti.',
      },
    },
  },
  
  // Common
  common: {
    save: 'Guardar',
    cancel: 'Cancelar',
    delete: 'Eliminar',
    edit: 'Editar',
    loading: 'Cargando...',
    error: 'Algo salió mal',
    retry: 'Reintentar',
    next: 'Siguiente',
    back: 'Atrás',
    skip: 'Saltar',
    done: 'Listo',
  },
  
  // Units
  units: {
    km: 'km',
    mi: 'mi',
    kg: 'kg',
    lb: 'lb',
    cm: 'cm',
    ft: 'ft',
    bpm: 'ppm',
    hours: 'h',
    minutes: 'min',
    seconds: 's',
  },
};


