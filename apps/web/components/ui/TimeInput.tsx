"use client";

/**
 * TimeInput Component
 * 
 * Auto-formatting time input for race times.
 * Users type only digits - colons are inserted automatically.
 * 
 * Examples:
 *   Type "1853"   → displays "18:53"
 *   Type "30000"  → displays "3:00:00"
 *   Type "12345"  → displays "1:23:45"
 * 
 * Benefits:
 *   - Faster input (no colon key switching on mobile)
 *   - Fewer format errors
 *   - Numeric keyboard on mobile (inputMode="numeric")
 * 
 * @see _AI_CONTEXT_/OPERATIONS/15_TIMEINPUT_COMPONENT_ADR.md
 */

import React, { useState, useRef, useEffect, useCallback, useId } from 'react';
import { formatDigitsToTime, stripToDigits } from '@/lib/utils/time';

export interface TimeInputProps {
  /** Current formatted value (with colons) */
  value: string;
  /** Called when value changes: (formattedValue, rawDigits) */
  onChange: (formatted: string, rawDigits: string) => void;
  /** Placeholder text */
  placeholder?: string;
  /** Additional CSS classes */
  className?: string;
  /** Max format: 'mmss' (4 digits) or 'hhmmss' (6 digits) */
  maxLength?: 'mmss' | 'hhmmss';
  /** Label text (optional) */
  label?: string;
  /** Disabled state */
  disabled?: boolean;
  /** Error message (optional) */
  error?: string;
  /** Input ID for accessibility */
  id?: string;
  /** Name attribute */
  name?: string;
  /** Required field indicator */
  required?: boolean;
  /** aria-describedby for accessibility */
  'aria-describedby'?: string;
}

/**
 * TimeInput - Auto-formatting time input component.
 */
export default function TimeInput({
  value,
  onChange,
  placeholder = "",
  className = "",
  maxLength = 'hhmmss',
  label,
  disabled = false,
  error,
  id,
  name,
  required,
  'aria-describedby': ariaDescribedBy,
}: TimeInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [cursorPosition, setCursorPosition] = useState<number | null>(null);
  
  // Generate stable ID for accessibility (must be at top level, not conditional)
  const generatedId = useId();

  /**
   * Calculate cursor position after formatting.
   * 
   * When user types a digit, cursor should be at the end.
   * When user deletes, cursor should be after the deletion point.
   */
  const calculateCursorPosition = useCallback((
    newDigits: string,
    oldValue: string,
    selectionStart: number,
    isDeleting: boolean
  ): number => {
    const formatted = formatDigitsToTime(newDigits, maxLength);
    
    if (isDeleting) {
      // After delete, count colons before the cursor position
      // and adjust accordingly
      let targetDigitPos = 0;
      for (let i = 0; i < Math.min(selectionStart, oldValue.length); i++) {
        if (oldValue[i] !== ':') targetDigitPos++;
      }
      targetDigitPos = Math.max(0, targetDigitPos - 1);
      
      // Find position in formatted string
      let digitsSeen = 0;
      for (let i = 0; i < formatted.length; i++) {
        if (formatted[i] !== ':') {
          if (digitsSeen === targetDigitPos) {
            return i;
          }
          digitsSeen++;
        }
      }
      return formatted.length;
    }
    
    // For typing, put cursor at end
    return formatted.length;
  }, [maxLength]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const input = e.target;
    const rawValue = input.value;
    const selStart = input.selectionStart || 0;
    
    // Extract only digits
    const newDigitsRaw = stripToDigits(rawValue);
    const oldDigits = stripToDigits(value);
    
    // Truncate to max length (same truncation as formatDigitsToTime)
    const maxDigits = maxLength === 'mmss' ? 4 : 6;
    const newDigits = newDigitsRaw.slice(0, maxDigits);
    
    // Determine if this is a deletion
    const isDeleting = newDigits.length < oldDigits.length;
    
    // Format the new value
    const formatted = formatDigitsToTime(newDigits, maxLength);
    
    // Calculate new cursor position
    const newCursorPos = calculateCursorPosition(
      newDigits, 
      value, 
      selStart, 
      isDeleting
    );
    setCursorPosition(newCursorPos);
    
    // Emit change (both formatted and raw are now truncated consistently)
    onChange(formatted, newDigits);
  }, [value, maxLength, onChange, calculateCursorPosition]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    const input = e.currentTarget;
    const selStart = input.selectionStart || 0;
    const selEnd = input.selectionEnd || 0;
    
    // Handle backspace - skip over colons smartly
    if (e.key === 'Backspace' && selStart === selEnd && selStart > 0) {
      const charBefore = value[selStart - 1];
      
      if (charBefore === ':') {
        // If cursor is right after a colon, backspace should delete
        // the digit before the colon (skip the colon)
        e.preventDefault();
        
        // Find the digit position to delete
        let digitIndex = 0;
        for (let i = 0; i < selStart - 1; i++) {
          if (value[i] !== ':') digitIndex++;
        }
        
        // Remove that digit from rawDigits
        const rawDigits = stripToDigits(value);
        if (digitIndex > 0 && digitIndex <= rawDigits.length) {
          const newDigits = rawDigits.slice(0, digitIndex - 1) + rawDigits.slice(digitIndex);
          const formatted = formatDigitsToTime(newDigits, maxLength);
          
          // Calculate new cursor position
          const newPos = calculateCursorPosition(
            newDigits,
            value,
            selStart - 1,
            true
          );
          setCursorPosition(newPos);
          
          onChange(formatted, newDigits);
        }
      }
    }
    
    // Handle Delete key similarly if needed
    if (e.key === 'Delete' && selStart === selEnd && selStart < value.length) {
      const charAfter = value[selStart];
      
      if (charAfter === ':') {
        // Skip the colon and delete the next digit
        e.preventDefault();
        
        // Find the digit position after the colon
        let digitIndex = 0;
        for (let i = 0; i <= selStart; i++) {
          if (value[i] !== ':') digitIndex++;
        }
        
        const rawDigits = stripToDigits(value);
        if (digitIndex < rawDigits.length) {
          const newDigits = rawDigits.slice(0, digitIndex) + rawDigits.slice(digitIndex + 1);
          const formatted = formatDigitsToTime(newDigits, maxLength);
          
          setCursorPosition(selStart);
          onChange(formatted, newDigits);
        }
      }
    }
  }, [value, maxLength, onChange, calculateCursorPosition]);

  // Restore cursor position after React re-render
  useEffect(() => {
    if (cursorPosition !== null && inputRef.current) {
      // Use requestAnimationFrame to ensure DOM is updated
      requestAnimationFrame(() => {
        if (inputRef.current) {
          inputRef.current.setSelectionRange(cursorPosition, cursorPosition);
        }
        setCursorPosition(null);
      });
    }
  }, [cursorPosition, value]);

  // Use provided ID or generated ID
  const inputId = id || `time-input-${generatedId}`;
  const errorId = error ? `${inputId}-error` : undefined;

  return (
    <div className="time-input-wrapper">
      {label && (
        <label 
          htmlFor={inputId}
          className="block text-sm font-medium mb-2 text-slate-300"
        >
          {label}
          {required && <span className="text-red-400 ml-1">*</span>}
        </label>
      )}
      <input
        ref={inputRef}
        id={inputId}
        name={name}
        type="text"
        inputMode="numeric"
        pattern="[0-9:]*"
        autoComplete="off"
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        required={required}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={
          [ariaDescribedBy, errorId].filter(Boolean).join(' ') || undefined
        }
        className={`
          bg-slate-800 border rounded px-3 py-2 text-white font-mono
          transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
          ${error ? 'border-red-500' : 'border-slate-700/50'}
          ${className}
        `.trim()}
      />
      {error && (
        <p 
          id={errorId}
          className="mt-1 text-sm text-red-400"
          role="alert"
        >
          {error}
        </p>
      )}
    </div>
  );
}
