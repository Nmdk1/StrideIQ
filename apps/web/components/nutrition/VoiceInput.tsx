"use client";

/**
 * Voice Input Component for Nutrition Logging
 * 
 * Allows athletes to speak their meals instead of typing.
 * Uses Web Speech API for browser-based recognition.
 * Falls back to Whisper API for better accuracy when available.
 * 
 * Example: "Had a banana and coffee for breakfast" 
 *   → Parsed: [{food: "banana", meal: "breakfast"}, {food: "coffee", meal: "breakfast"}]
 */

import { useState, useEffect, useCallback } from 'react';

interface VoiceInputProps {
  onTranscript: (text: string) => void;
  onParsedFood?: (foods: ParsedFood[]) => void;
  placeholder?: string;
  className?: string;
}

interface ParsedFood {
  food: string;
  quantity?: number;
  unit?: string;
  meal?: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  timing?: string;  // e.g., "pre-run", "post-run"
}

// Check for browser support
const isSpeechRecognitionSupported = () => {
  if (typeof window === 'undefined') return false;
  return 'SpeechRecognition' in window || 'webkitSpeechRecognition' in window;
};

export function VoiceInput({ 
  onTranscript, 
  onParsedFood,
  placeholder = "Tap mic and say what you ate...",
  className = ""
}: VoiceInputProps) {
  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsSupported(isSpeechRecognitionSupported());
  }, []);

  const startListening = useCallback(() => {
    if (!isSupported) {
      setError('Voice input not supported in this browser');
      return;
    }

    setError(null);
    setTranscript('');
    setIsListening(true);

    // Use Web Speech API
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';  // TODO: Use i18n locale

    recognition.onresult = (event: any) => {
      const current = event.resultIndex;
      const result = event.results[current];
      const text = result[0].transcript;
      
      setTranscript(text);
      
      if (result.isFinal) {
        onTranscript(text);
        
        // Try to parse foods from the transcript
        if (onParsedFood) {
          const parsed = parseNutritionFromText(text);
          if (parsed.length > 0) {
            onParsedFood(parsed);
          }
        }
      }
    };

    recognition.onerror = (event: any) => {
      console.error('Speech recognition error:', event.error);
      setError(`Error: ${event.error}`);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.start();
  }, [isSupported, onTranscript, onParsedFood]);

  const stopListening = useCallback(() => {
    setIsListening(false);
  }, []);

  if (!isSupported) {
    return (
      <div className={`text-slate-500 text-sm ${className}`}>
        Voice input not available in this browser.
        Try Chrome or Edge for voice support.
      </div>
    );
  }

  return (
    <div className={`relative ${className}`}>
      {/* Transcript display */}
      {transcript && (
        <div className="mb-3 p-3 bg-slate-800 rounded-lg text-slate-300 text-sm">
          <span className="text-slate-500 text-xs block mb-1">I heard:</span>
          {transcript}
        </div>
      )}

      {/* Microphone button */}
      <button
        type="button"
        onClick={isListening ? stopListening : startListening}
        className={`
          flex items-center justify-center gap-2 w-full py-3 px-4 rounded-lg
          font-medium transition-all
          ${isListening 
            ? 'bg-red-600 hover:bg-red-700 text-white animate-pulse' 
            : 'bg-slate-700 hover:bg-slate-600 text-slate-200'
          }
        `}
      >
        {/* Microphone icon */}
        <svg 
          className={`w-5 h-5 ${isListening ? 'animate-pulse' : ''}`} 
          fill="currentColor" 
          viewBox="0 0 24 24"
        >
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
          <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
        </svg>
        
        {isListening ? 'Listening...' : placeholder}
      </button>

      {/* Error display */}
      {error && (
        <div className="mt-2 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Usage hint */}
      <p className="mt-2 text-slate-500 text-xs text-center">
        Say something like &quot;Had oatmeal with banana for breakfast&quot;
      </p>
    </div>
  );
}

/**
 * Parse nutrition information from natural language
 * 
 * Examples:
 * - "banana and coffee" → [{food: "banana"}, {food: "coffee"}]
 * - "2 eggs for breakfast" → [{food: "eggs", quantity: 2, meal: "breakfast"}]
 * - "protein shake after my run" → [{food: "protein shake", timing: "post-run"}]
 */
function parseNutritionFromText(text: string): ParsedFood[] {
  const parsed: ParsedFood[] = [];
  const lower = text.toLowerCase();
  
  // Detect meal type
  let meal: ParsedFood['meal'] | undefined;
  if (lower.includes('breakfast')) meal = 'breakfast';
  else if (lower.includes('lunch')) meal = 'lunch';
  else if (lower.includes('dinner') || lower.includes('supper')) meal = 'dinner';
  else if (lower.includes('snack')) meal = 'snack';
  
  // Detect timing
  let timing: string | undefined;
  if (lower.includes('before') && (lower.includes('run') || lower.includes('workout'))) timing = 'pre-run';
  else if (lower.includes('after') && (lower.includes('run') || lower.includes('workout'))) timing = 'post-run';
  else if (lower.includes('pre-run') || lower.includes('pre run')) timing = 'pre-run';
  else if (lower.includes('post-run') || lower.includes('post run')) timing = 'post-run';
  
  // Simple food extraction (split on common connectors)
  // Remove common phrases first
  let cleaned = lower
    .replace(/for breakfast/gi, '')
    .replace(/for lunch/gi, '')
    .replace(/for dinner/gi, '')
    .replace(/for a snack/gi, '')
    .replace(/before (my )?run/gi, '')
    .replace(/after (my )?run/gi, '')
    .replace(/had /gi, '')
    .replace(/ate /gi, '')
    .replace(/i /gi, '')
    .trim();
  
  // Split on connectors
  const parts = cleaned.split(/\s+and\s+|\s*,\s*|\s+with\s+/);
  
  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed || trimmed.length < 2) continue;
    
    // Try to extract quantity (e.g., "2 eggs", "a banana")
    const quantityMatch = trimmed.match(/^(\d+|a|an|one|two|three|four|five)\s+(.+)/i);
    
    if (quantityMatch) {
      const quantityStr = quantityMatch[1].toLowerCase();
      let quantity = 1;
      
      const quantityMap: Record<string, number> = {
        'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5
      };
      
      quantity = quantityMap[quantityStr] || parseInt(quantityStr) || 1;
      
      parsed.push({
        food: quantityMatch[2].trim(),
        quantity,
        meal,
        timing,
      });
    } else {
      parsed.push({
        food: trimmed,
        meal,
        timing,
      });
    }
  }
  
  return parsed;
}

/**
 * Hook for using voice input with Whisper API (for better accuracy)
 * This is a placeholder for future implementation
 */
export function useWhisperVoiceInput() {
  // TODO: Implement Whisper API integration
  // This would:
  // 1. Record audio using MediaRecorder
  // 2. Send to Whisper API
  // 3. Get more accurate transcription
  // 4. Parse with GPT for food extraction
  
  return {
    isSupported: false,
    isRecording: false,
    startRecording: () => {},
    stopRecording: () => {},
    transcript: '',
    error: null,
  };
}


