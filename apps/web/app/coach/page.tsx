'use client';

/**
 * AI Coach Chat Page
 * 
 * Provides a chat interface to the AI running coach.
 * The coach has access to the athlete's training data and
 * provides personalized, data-driven advice.
 */

import React, { useState, useRef, useEffect } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { aiCoachService } from '@/lib/api/services/ai-coach';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import ReactMarkdown from 'react-markdown';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const SUGGESTED_QUESTIONS = [
  "How is my training going this week?",
  "Am I ready for a hard workout tomorrow?",
  "What should I focus on in my next long run?",
  "How does my current fitness compare to a month ago?",
  "What's the most important thing I should do this week?",
];

export default function CoachPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  
  // Add initial greeting
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([{
        id: 'greeting',
        role: 'assistant',
        content: `👋 Hi! I'm your StrideIQ AI Coach. I have access to your training data and can help you with:

- **Training analysis** - How your recent runs look
- **Workout guidance** - What to do next
- **Recovery advice** - When to push, when to rest
- **Goal planning** - Am I on track for my goal?

Ask me anything about your training!`,
        timestamp: new Date(),
      }]);
    }
  }, [messages.length]);
  
  const handleSend = async (messageText?: string) => {
    const text = messageText || input.trim();
    if (!text || isLoading) return;
    
    setInput('');
    setError(null);
    
    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    
    // Get AI response
    setIsLoading(true);
    try {
      const response = await aiCoachService.chat({ message: text });
      
      if (response.error) {
        setError(response.response);
      } else {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response.response,
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, assistantMessage]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to get response from coach');
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };
  
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 flex flex-col">
        {/* Header */}
        <div className="border-b border-gray-700 bg-gray-800/50 px-4 py-3">
          <div className="max-w-4xl mx-auto flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center text-white font-bold text-lg">
              AI
            </div>
            <div>
              <h1 className="font-semibold">StrideIQ Coach</h1>
              <p className="text-xs text-gray-400">AI-powered training guidance</p>
            </div>
          </div>
        </div>
        
        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="max-w-4xl mx-auto space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-lg px-4 py-3 ${
                    message.role === 'user'
                      ? 'bg-orange-600 text-white'
                      : 'bg-gray-800 border border-gray-700'
                  }`}
                >
                  {message.role === 'assistant' ? (
                    <div className="prose prose-invert prose-sm max-w-none">
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  )}
                  <p className={`text-xs mt-2 ${message.role === 'user' ? 'text-orange-200' : 'text-gray-500'}`}>
                    {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </div>
            ))}
            
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-2">
                    <LoadingSpinner size="sm" />
                    <span className="text-gray-400">Thinking...</span>
                  </div>
                </div>
              </div>
            )}
            
            {error && (
              <div className="flex justify-center">
                <div className="bg-red-900/50 border border-red-700 rounded-lg px-4 py-3 text-red-300">
                  {error}
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </div>
        
        {/* Suggestions (show only when no messages yet) */}
        {messages.length <= 1 && (
          <div className="px-4 pb-4">
            <div className="max-w-4xl mx-auto">
              <p className="text-xs text-gray-400 mb-2">Suggested questions:</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTED_QUESTIONS.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(q)}
                    disabled={isLoading}
                    className="text-sm px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
        
        {/* Input */}
        <div className="border-t border-gray-700 bg-gray-800/50 px-4 py-4">
          <div className="max-w-4xl mx-auto flex gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask your coach anything..."
              rows={1}
              className="flex-1 px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white resize-none focus:outline-none focus:ring-2 focus:ring-orange-500"
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || isLoading}
              className="px-6 py-3 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
            >
              Send
            </button>
          </div>
          <p className="text-xs text-gray-500 text-center mt-2">
            The coach uses your actual training data to provide personalized advice.
          </p>
        </div>
      </div>
    </ProtectedRoute>
  );
}
