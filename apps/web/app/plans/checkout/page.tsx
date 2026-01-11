'use client';

/**
 * Plan Checkout Page
 * 
 * Payment flow for semi-custom and custom plans.
 * Placeholder for Stripe integration.
 */

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

const PLAN_PRICES = {
  standard: { price: 0, label: 'Free' },
  semi_custom: { price: 5, label: '$5' },
  custom: { price: 24, label: '$24/month' },
};

function CheckoutContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  const [isLoading, setIsLoading] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  
  // Get plan details from URL params
  const planTier = (searchParams.get('tier') || 'semi_custom') as keyof typeof PLAN_PRICES;
  const distance = searchParams.get('distance') || 'marathon';
  const duration = searchParams.get('duration') || '18';
  const daysPerWeek = searchParams.get('days') || '6';
  const volumeTier = searchParams.get('volume') || 'mid';
  
  const planPrice = PLAN_PRICES[planTier] || PLAN_PRICES.semi_custom;
  
  useEffect(() => {
    const token = localStorage.getItem('token');
    setIsAuthenticated(!!token);
    
    // If free plan, skip checkout
    if (planTier === 'standard') {
      router.push('/plans/create');
    }
  }, [planTier, router]);
  
  const handlePurchase = async () => {
    setIsLoading(true);
    
    // TODO: Integrate with Stripe
    // For now, simulate a successful purchase
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    // Store purchase in session
    sessionStorage.setItem('plan_purchased', JSON.stringify({
      tier: planTier,
      distance,
      duration,
      daysPerWeek,
      volumeTier,
      purchaseTime: Date.now(),
    }));
    
    // Redirect to plan creation with purchase confirmation
    router.push(`/plans/create?purchased=true&tier=${planTier}`);
  };
  
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-900 text-gray-100 flex items-center justify-center">
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-8 max-w-md w-full text-center">
          <h1 className="text-2xl font-bold text-white mb-4">Sign In Required</h1>
          <p className="text-gray-400 mb-6">
            Please sign in to purchase a training plan.
          </p>
          <a
            href="/login?redirect=/plans/checkout"
            className="inline-block px-6 py-3 bg-gradient-to-r from-pink-600 to-orange-600 rounded-lg font-semibold text-white"
          >
            Sign In
          </a>
        </div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 py-12">
      <div className="max-w-lg mx-auto px-4">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Complete Your Purchase</h1>
          <p className="text-gray-400">Get your personalized training plan</p>
        </div>
        
        {/* Order Summary */}
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
          <h2 className="text-lg font-bold text-white mb-4">Order Summary</h2>
          
          <div className="space-y-4">
            <div className="flex justify-between">
              <span className="text-gray-400">Plan Type</span>
              <span className="text-white capitalize">{planTier.replace('_', '-')} Plan</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Distance</span>
              <span className="text-white capitalize">{distance.replace('_', ' ')}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Duration</span>
              <span className="text-white">{duration} weeks</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Days/Week</span>
              <span className="text-white">{daysPerWeek} days</span>
            </div>
            
            <div className="border-t border-gray-700 pt-4 mt-4">
              <div className="flex justify-between text-lg">
                <span className="font-semibold text-white">Total</span>
                <span className="font-bold text-orange-400">{planPrice.label}</span>
              </div>
            </div>
          </div>
        </div>
        
        {/* Benefits */}
        <div className="bg-gradient-to-br from-pink-900/20 to-orange-900/20 border border-pink-700/30 rounded-xl p-6 mb-6">
          <h3 className="text-sm font-semibold text-pink-400 uppercase tracking-wider mb-3">
            What You Get
          </h3>
          <ul className="space-y-2 text-sm text-gray-300">
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              Personalized training paces based on your fitness
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              Scientifically periodized plan structure
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              Day-by-day workout prescriptions
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">✓</span>
              Calendar integration
            </li>
            {planTier === 'custom' && (
              <>
                <li className="flex items-center gap-2">
                  <span className="text-green-400">✓</span>
                  AI-powered plan adaptation
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-green-400">✓</span>
                  GPT coach access
                </li>
              </>
            )}
          </ul>
        </div>
        
        {/* Payment Button */}
        <button
          onClick={handlePurchase}
          disabled={isLoading}
          className="w-full px-6 py-4 bg-gradient-to-r from-pink-600 to-orange-600 hover:from-pink-700 hover:to-orange-700 rounded-lg font-semibold text-white disabled:opacity-50 flex items-center justify-center gap-2 transition-all"
        >
          {isLoading ? (
            <>
              <LoadingSpinner size="sm" />
              Processing...
            </>
          ) : (
            `Pay ${planPrice.label}`
          )}
        </button>
        
        {/* Security Notice */}
        <p className="text-center text-xs text-gray-500 mt-4">
          🔒 Secure payment powered by Stripe
        </p>
        
        {/* Back Link */}
        <div className="text-center mt-6">
          <a
            href="/plans/create"
            className="text-sm text-gray-400 hover:text-pink-400"
          >
            ← Back to plan configuration
          </a>
        </div>
      </div>
    </div>
  );
}

export default function CheckoutPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    }>
      <CheckoutContent />
    </Suspense>
  );
}
