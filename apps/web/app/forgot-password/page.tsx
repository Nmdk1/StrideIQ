/**
 * Forgot Password Page
 * 
 * Allows users to request a password reset email.
 */

'use client';

import { useState } from 'react';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import Link from 'next/link';
import { authService } from '@/lib/api/services/auth';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await authService.forgotPassword(email);
      setIsSuccess(true);
    } catch (err: any) {
      setError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSuccess) {
    return (
      <div className="min-h-screen bg-slate-900 text-slate-100 flex items-center justify-center py-12 px-4">
        <div className="max-w-md w-full">
          <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-8 text-center">
            <div className="w-16 h-16 bg-green-600/20 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold mb-2">Check your email</h1>
            <p className="text-slate-400 mb-6">
              If an account with that email exists, we&apos;ve sent a password reset link.
              The link expires in 1 hour.
            </p>
            <Link
              href="/login"
              className="inline-block px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium transition-colors"
            >
              Back to login
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex items-center justify-center py-12 px-4">
      <div className="max-w-md w-full">
        <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-8">
          <h1 className="text-3xl font-bold mb-2">Forgot password?</h1>
          <p className="text-slate-400 mb-6">
            Enter your email and we&apos;ll send you a link to reset your password.
          </p>

          {error && <ErrorMessage error={error} className="mb-6" />}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-2">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2 bg-slate-900 border border-slate-700/50 rounded text-white focus:outline-none focus:border-blue-600"
                placeholder="you@example.com"
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed rounded text-white font-medium transition-colors"
            >
              {isSubmitting ? <LoadingSpinner size="sm" /> : 'Send reset link'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <Link href="/login" className="text-sm text-blue-400 hover:text-blue-300">
              Back to login
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
