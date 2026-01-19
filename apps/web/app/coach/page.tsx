'use client';

/**
 * AI Coach Chat Page
 * 
 * Enhanced with shadcn/ui + Lucide.
 * Provides a chat interface to the AI running coach.
 */

import React, { useState, useRef, useEffect } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { aiCoachService } from '@/lib/api/services/ai-coach';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { MessageSquare, Send, Sparkles, Activity, BedDouble, Target, TrendingUp, RotateCcw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

function getSuggestionIcon(text: string) {
  const t = text.toLowerCase();
  if (t.includes('long run')) return Target;
  if (t.includes('overtraining') || t.includes('overtrain')) return Sparkles;
  if (t.includes('getting fitter') || t.includes('fitter') || t.includes('fitness')) return TrendingUp;
  if (t.includes("today")) return Activity;
  if (t.includes("focus on this week") || t.includes("this week")) return BedDouble;
  return Sparkles;
}

export default function CoachPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
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

  // Fetch dynamic suggestions on load
  useEffect(() => {
    let cancelled = false;
    aiCoachService.getSuggestions()
      .then((res) => {
        if (!cancelled) setSuggestions(res.suggestions || []);
      })
      .catch(() => {
        if (!cancelled) setSuggestions([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get response from coach');
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewConversation = async () => {
    if (isLoading) return;
    setError(null);
    setIsLoading(true);
    try {
      await aiCoachService.newConversation();
      setMessages([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start a new conversation');
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };
  
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col">
        {/* Header */}
        <div className="border-b border-slate-700 bg-slate-800/50 px-4 py-3">
          <div className="max-w-4xl mx-auto flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-gradient-to-br from-orange-500 to-orange-600 ring-2 ring-orange-500/30">
                <MessageSquare className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="font-semibold flex items-center gap-2">
                  StrideIQ Coach
                  <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30 text-xs">AI</Badge>
                </h1>
                <p className="text-xs text-slate-400">Data-driven training guidance</p>
              </div>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={handleNewConversation}
              disabled={isLoading}
              className="border-slate-700 hover:border-orange-500/50 hover:bg-slate-800 text-slate-300"
            >
              <RotateCcw className="w-3.5 h-3.5 mr-1.5 text-orange-500" />
              New conversation
            </Button>
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
                <Card
                  className={`max-w-[85%] ${
                    message.role === 'user'
                      ? 'bg-orange-600 border-orange-500 text-white'
                      : 'bg-slate-800 border-slate-700'
                  }`}
                >
                  <CardContent className="py-3 px-4">
                    {message.role === 'assistant' ? (
                      <div className="prose prose-invert prose-sm max-w-none">
                        <ReactMarkdown>{message.content}</ReactMarkdown>
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap">{message.content}</p>
                    )}
                    <p className={`text-xs mt-2 ${message.role === 'user' ? 'text-orange-200' : 'text-slate-500'}`}>
                      {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </CardContent>
                </Card>
              </div>
            ))}
            
            {isLoading && (
              <div className="flex justify-start">
                <Card className="bg-slate-800 border-slate-700">
                  <CardContent className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <LoadingSpinner size="sm" />
                      <span className="text-slate-400">Thinking...</span>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
            
            {error && (
              <div className="flex justify-center">
                <Card className="bg-red-900/50 border-red-700">
                  <CardContent className="py-3 px-4 text-red-300">
                    {error}
                  </CardContent>
                </Card>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </div>
        
        {/* Suggestions (show only when no messages yet) */}
        {messages.length <= 1 && suggestions.length > 0 && (
          <div className="px-4 pb-4">
            <div className="max-w-4xl mx-auto">
              <p className="text-xs text-slate-400 mb-2 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-orange-500" />
                Suggested questions:
              </p>
              <div className="flex flex-wrap gap-2">
                {suggestions.map((text, i) => {
                  const Icon = getSuggestionIcon(text);
                  return (
                  <Button
                    key={i}
                    variant="outline"
                    size="sm"
                    onClick={() => handleSend(text)}
                    disabled={isLoading}
                    className="border-slate-700 hover:border-orange-500/50 hover:bg-slate-800 text-slate-300"
                  >
                    <Icon className="w-3.5 h-3.5 mr-1.5 text-orange-500" />
                    {text}
                  </Button>
                  );
                })}
              </div>
            </div>
          </div>
        )}
        
        {/* Input */}
        <div className="border-t border-slate-700 bg-slate-800/50 px-4 py-4">
          <div className="max-w-4xl mx-auto flex gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask your coach anything..."
              rows={1}
              className="flex-1 px-4 py-3 bg-slate-900 border border-slate-600 rounded-xl text-white resize-none focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
            />
            <Button
              onClick={() => handleSend()}
              disabled={!input.trim() || isLoading}
              className="px-6 bg-orange-600 hover:bg-orange-500 disabled:bg-slate-700 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4 mr-1.5" />
              Send
            </Button>
          </div>
          <p className="text-xs text-slate-500 text-center mt-2">
            The coach uses your actual training data to provide personalized advice.
          </p>
        </div>
      </div>
    </ProtectedRoute>
  );
}
