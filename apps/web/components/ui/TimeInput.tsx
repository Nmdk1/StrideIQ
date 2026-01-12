"use client";

import React, { useState, useRef, useEffect } from 'react';

interface TimeInputProps {
  value: string;
  onChange: (formatted: string, rawDigits: string) => void;
  placeholder?: string;
  className?: string;
  maxLength?: 'mmss' | 'hhmmss';
  label?: string;
}

/**
 * Auto-formatting time input component.
 * 
 * Users type digits only - colons are inserted automatically.
 * Examples:
 *   - Type "1853" → displays "18:53"
 *   - Type "30000" → displays "3:00:00"  
 *   - Type "12345" → displays "1:23:45"
 * 
 * Props:
 *   - value: The formatted time string (with colons)
 *   - onChange: Called with (formattedValue, rawDigits)
 *   - maxLength: 'mmss' (4 digits max) or 'hhmmss' (6 digits max, default)
 */
export default function TimeInput({
  value,
  onChange,
  placeholder = "0:00:00",
  className = "",
  maxLength = 'hhmmss',
  label,
}: TimeInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [cursorPosition, setCursorPosition] = useState<number | null>(null);

  // Extract just digits from the current value
  const getDigits = (val: string): string => val.replace(/\D/g, '');

  // Format digits into time string
  const formatTime = (digits: string): string => {
    const maxDigits = maxLength === 'mmss' ? 4 : 6;
    const trimmed = digits.slice(0, maxDigits);
    
    if (trimmed.length === 0) return '';
    
    // Pad with leading zeros for consistent formatting
    // For hhmmss: up to 6 digits (h:mm:ss or hh:mm:ss)
    // For mmss: up to 4 digits (m:ss or mm:ss)
    
    if (maxLength === 'mmss') {
      // Format as MM:SS or M:SS
      if (trimmed.length <= 2) {
        return trimmed; // Just seconds or partial
      } else if (trimmed.length <= 4) {
        const secs = trimmed.slice(-2);
        const mins = trimmed.slice(0, -2);
        return `${mins}:${secs}`;
      }
    } else {
      // Format as HH:MM:SS, H:MM:SS, MM:SS, or M:SS
      if (trimmed.length <= 2) {
        return trimmed; // Just seconds or partial
      } else if (trimmed.length <= 4) {
        // MM:SS format
        const secs = trimmed.slice(-2);
        const mins = trimmed.slice(0, -2);
        return `${mins}:${secs}`;
      } else {
        // H:MM:SS or HH:MM:SS format
        const secs = trimmed.slice(-2);
        const mins = trimmed.slice(-4, -2);
        const hrs = trimmed.slice(0, -4);
        return `${hrs}:${mins}:${secs}`;
      }
    }
    
    return trimmed;
  };

  // Calculate cursor position after formatting
  const calculateCursorPosition = (digits: string, oldDigits: string, oldPos: number): number => {
    const formatted = formatTime(digits);
    
    // Count how many digits are before the cursor in the new value
    const digitsBeforeCursor = digits.length;
    
    // Count colons before this position in formatted string
    let digitCount = 0;
    let pos = 0;
    for (let i = 0; i < formatted.length; i++) {
      if (formatted[i] !== ':') {
        digitCount++;
      }
      if (digitCount >= digitsBeforeCursor) {
        pos = i + 1;
        break;
      }
    }
    
    return Math.min(pos, formatted.length);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const input = e.target;
    const rawValue = input.value;
    const selStart = input.selectionStart || 0;
    
    // Get only digits
    const newDigits = getDigits(rawValue);
    const oldDigits = getDigits(value);
    
    // Format the new value
    const formatted = formatTime(newDigits);
    
    // Calculate new cursor position
    const newCursorPos = calculateCursorPosition(newDigits, oldDigits, selStart);
    setCursorPosition(newCursorPos);
    
    onChange(formatted, newDigits);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const input = e.currentTarget;
    const selStart = input.selectionStart || 0;
    
    // Handle backspace specially - skip over colons
    if (e.key === 'Backspace' && selStart > 0) {
      const charBefore = value[selStart - 1];
      if (charBefore === ':') {
        // Move cursor back one more to delete the digit before the colon
        e.preventDefault();
        const digits = getDigits(value);
        
        // Find which digit we're deleting
        let digitIndex = 0;
        for (let i = 0; i < selStart - 1; i++) {
          if (value[i] !== ':') digitIndex++;
        }
        
        // Remove that digit
        const newDigits = digits.slice(0, digitIndex - 1) + digits.slice(digitIndex);
        const formatted = formatTime(newDigits);
        
        onChange(formatted, newDigits);
        
        // Set cursor position
        const newPos = Math.max(0, selStart - 2);
        setCursorPosition(newPos);
      }
    }
  };

  // Restore cursor position after render
  useEffect(() => {
    if (cursorPosition !== null && inputRef.current) {
      inputRef.current.setSelectionRange(cursorPosition, cursorPosition);
      setCursorPosition(null);
    }
  }, [cursorPosition, value]);

  return (
    <div>
      {label && (
        <label className="block text-sm font-medium mb-2">{label}</label>
      )}
      <input
        ref={inputRef}
        type="text"
        inputMode="numeric"
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className={`bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white font-mono ${className}`}
      />
    </div>
  );
}
