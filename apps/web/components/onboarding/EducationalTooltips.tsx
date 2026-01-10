"use client";

/**
 * Educational Tooltips System
 * 
 * Teaches athletes why logging matters and what insights they'll unlock.
 * Tone: Curious, not guilt-inducing. "The more you log, the more we show you."
 */

import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';

interface TooltipStep {
  id: string;
  target: string; // CSS selector
  title: string;
  content: string;
  position: 'top' | 'bottom' | 'left' | 'right';
}

const ONBOARDING_STEPS: TooltipStep[] = [
  {
    id: 'welcome',
    target: '[data-tour="dashboard"]',
    title: 'Your Efficiency Dashboard',
    content: 'This is where the magic happens. We analyze your runs to show if you\'re getting fitter—or just accumulating miles.',
    position: 'bottom',
  },
  {
    id: 'checkin',
    target: '[data-tour="checkin"]',
    title: 'Morning Check-in (5 seconds)',
    content: 'Sleep, stress, soreness. Three sliders. We\'ll find patterns you can\'t see—like which sleep habits actually help your running.',
    position: 'bottom',
  },
  {
    id: 'nutrition',
    target: '[data-tour="nutrition"]',
    title: 'What You Eat Matters (Maybe)',
    content: 'Log meals when you remember. We\'ll tell you if pre-run coffee actually helps YOUR pace, not some study average.',
    position: 'bottom',
  },
  {
    id: 'discovery',
    target: '[data-tour="discovery"]',
    title: 'What Actually Works For You',
    content: 'After 2-3 weeks of logging, we\'ll show correlations unique to YOUR body. Everyone\'s different.',
    position: 'bottom',
  },
];

interface TooltipProps {
  step: TooltipStep;
  onNext: () => void;
  onSkip: () => void;
  currentStep: number;
  totalSteps: number;
}

function Tooltip({ step, onNext, onSkip, currentStep, totalSteps }: TooltipProps) {
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const target = document.querySelector(step.target);
    if (target) {
      const rect = target.getBoundingClientRect();
      const tooltipWidth = 320;
      const tooltipHeight = 180;
      
      let top = 0;
      let left = 0;
      
      switch (step.position) {
        case 'bottom':
          top = rect.bottom + 12;
          left = rect.left + (rect.width / 2) - (tooltipWidth / 2);
          break;
        case 'top':
          top = rect.top - tooltipHeight - 12;
          left = rect.left + (rect.width / 2) - (tooltipWidth / 2);
          break;
        case 'left':
          top = rect.top + (rect.height / 2) - (tooltipHeight / 2);
          left = rect.left - tooltipWidth - 12;
          break;
        case 'right':
          top = rect.top + (rect.height / 2) - (tooltipHeight / 2);
          left = rect.right + 12;
          break;
      }
      
      // Keep within viewport
      left = Math.max(16, Math.min(left, window.innerWidth - tooltipWidth - 16));
      top = Math.max(16, top);
      
      setPosition({ top, left });
      setVisible(true);
      
      // Highlight target
      target.classList.add('tour-highlight');
      return () => target.classList.remove('tour-highlight');
    }
  }, [step]);

  if (!visible) return null;

  return createPortal(
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-[9998]" onClick={onSkip} />
      
      {/* Tooltip */}
      <div
        className="fixed z-[9999] w-80 bg-gray-800 border border-gray-700 rounded-lg shadow-xl p-4 animate-fade-in"
        style={{ top: position.top, left: position.left }}
      >
        <div className="flex items-start justify-between mb-2">
          <h3 className="text-lg font-bold text-orange-400">{step.title}</h3>
          <span className="text-xs text-gray-500">{currentStep + 1}/{totalSteps}</span>
        </div>
        
        <p className="text-gray-300 text-sm mb-4">{step.content}</p>
        
        <div className="flex justify-between items-center">
          <button
            onClick={onSkip}
            className="text-sm text-gray-500 hover:text-gray-400"
          >
            Skip tour
          </button>
          <button
            onClick={onNext}
            className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {currentStep < totalSteps - 1 ? 'Next' : 'Got it'}
          </button>
        </div>
      </div>
    </>,
    document.body
  );
}

export function useOnboardingTour() {
  const [currentStep, setCurrentStep] = useState(-1);
  const [hasSeenTour, setHasSeenTour] = useState(true);

  useEffect(() => {
    const seen = localStorage.getItem('onboarding-tour-complete');
    if (!seen) {
      setHasSeenTour(false);
      // Delay start to let page render
      setTimeout(() => setCurrentStep(0), 1000);
    }
  }, []);

  const completeTour = () => {
    localStorage.setItem('onboarding-tour-complete', 'true');
    setCurrentStep(-1);
    setHasSeenTour(true);
  };

  const nextStep = () => {
    if (currentStep < ONBOARDING_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      completeTour();
    }
  };

  const skipTour = () => {
    completeTour();
  };

  const resetTour = () => {
    localStorage.removeItem('onboarding-tour-complete');
    setHasSeenTour(false);
    setCurrentStep(0);
  };

  const isActive = currentStep >= 0 && currentStep < ONBOARDING_STEPS.length;

  return {
    isActive,
    currentStep,
    totalSteps: ONBOARDING_STEPS.length,
    step: isActive ? ONBOARDING_STEPS[currentStep] : null,
    nextStep,
    skipTour,
    resetTour,
    hasSeenTour,
  };
}

export function OnboardingTour() {
  const { isActive, currentStep, totalSteps, step, nextStep, skipTour } = useOnboardingTour();

  if (!isActive || !step) return null;

  return (
    <Tooltip
      step={step}
      onNext={nextStep}
      onSkip={skipTour}
      currentStep={currentStep}
      totalSteps={totalSteps}
    />
  );
}

// CSS for tour highlight (add to globals.css)
export const tourStyles = `
.tour-highlight {
  position: relative;
  z-index: 9997 !important;
  box-shadow: 0 0 0 4px rgba(234, 88, 12, 0.5), 0 0 20px rgba(234, 88, 12, 0.3);
  border-radius: 8px;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.animate-fade-in {
  animation: fade-in 0.2s ease-out;
}
`;


