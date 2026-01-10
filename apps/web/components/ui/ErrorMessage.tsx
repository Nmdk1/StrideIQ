/**
 * Error Message Component
 * 
 * Displays error messages consistently across the app.
 * Can be swapped for different error display styles.
 */

import { ApiClientError } from '@/lib/api/client';

interface ErrorMessageProps {
  error: Error | ApiClientError | unknown;
  title?: string;
  className?: string;
}

export function ErrorMessage({ error, title = 'Error', className = '' }: ErrorMessageProps) {
  let message = 'An unexpected error occurred';
  let status: number | undefined;

  if (error instanceof ApiClientError) {
    message = error.message;
    status = error.status;
  } else if (error instanceof Error) {
    message = error.message;
  } else if (typeof error === 'string') {
    message = error;
  }

  return (
    <div className={`bg-red-900/50 border border-red-500/50 rounded-lg p-4 ${className}`}>
      <h3 className="text-red-400 font-semibold mb-2">{title}</h3>
      <p className="text-gray-300 text-sm">{message}</p>
      {status && (
        <p className="text-gray-400 text-xs mt-2">Status: {status}</p>
      )}
    </div>
  );
}


