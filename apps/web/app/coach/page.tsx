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
import { MessageSquare, Send, Sparkles, Activity, BedDouble, Target, TrendingUp, RotateCcw, ShieldCheck, Trophy, BrainCircuit } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

type SuggestionCard = {
  title: string;
  description: string;
  prompt: string;
  Icon: React.ComponentType<{ className?: string }>;
};

function getSuggestionIcon(text: string) {
  const t = text.toLowerCase();
  if (t.includes('long run')) return Target;
  if (t.includes('overtraining') || t.includes('overtrain')) return Sparkles;
  if (t.includes('getting fitter') || t.includes('fitter') || t.includes('fitness')) return TrendingUp;
  if (t.includes("today")) return Activity;
  if (t.includes("focus on this week") || t.includes("this week")) return BedDouble;
  return Sparkles;
}

function buildSuggestionCard(prompt: string): SuggestionCard {
  const t = prompt.toLowerCase();

  // Treat the raw prompt as an internal payload; surface a human-readable card.
  if (t.includes("pr") || t.includes("personal best") || t.includes("get_pb_patterns")) {
    return {
      title: 'PR Analysis',
      description: 'What preceded your PRs — with receipts (dates, activity ids, TSB).',
      prompt,
      Icon: Trophy,
    };
  }

  if (t.includes("atl") || t.includes("ctl") || t.includes("tsb") || t.includes("training load")) {
    return {
      title: 'Training Load',
      description: 'Where you are today (ATL/CTL/TSB) and what it implies — cited.',
      prompt,
      Icon: ShieldCheck,
    };
  }

  if (t.includes("efficiency") || t.includes("get_efficiency")) {
    return {
      title: 'Efficiency Deep Dive',
      description: 'Compare concrete runs and show what changed — cited.',
      prompt,
      Icon: TrendingUp,
    };
  }

  if (t.includes("30-day") || t.includes("30 day") || t.includes("month") || t.includes("volume")) {
    return {
      title: 'Volume & Consistency',
      description: 'Your recent volume rhythm and how it’s trending — cited.',
      prompt,
      Icon: Activity,
    };
  }

  if (t.includes("this week") || t.includes("week")) {
    return {
      title: 'This Week',
      description: 'What you’ve done + what’s next, grounded in your plan and runs.',
      prompt,
      Icon: BedDouble,
    };
  }

  return {
    title: 'Ask the Coach',
    description: 'A focused question that triggers a data-backed answer with receipts.',
    prompt,
    Icon: BrainCircuit,
  };
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
        content: `Hi — I’m your StrideIQ Coach.\n\nI don’t guess. If I use numbers, I’ll cite receipts from your training data (dates + activity ids + values).\n\nWhat do you want to understand or decide today?`,
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
      <div className="min-h-screen bg-slate-900 text-slate-100">
        <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">

          {/* Header (match Home page shell) */}
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
                <MessageSquare className="w-6 h-6 text-orange-500" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-bold">Coach</h1>
                  <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30 text-xs">AI</Badge>
                </div>
                <p className="text-sm text-slate-400">High-trust analysis and prescriptive training, backed by receipts.</p>
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

          {/* Main grid (align with Home bento rhythm) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
            {/* Chat panel */}
            <Card className="lg:col-span-8 bg-slate-800/50 border-slate-700/50 overflow-hidden flex flex-col min-h-[68vh]">
              <CardContent className="p-0 flex flex-col flex-1">
                {/* Messages (taller + higher: less outer padding, more viewport usage) */}
                <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <Card
                        className={`max-w-[92%] ${
                          message.role === 'user'
                            ? 'bg-orange-600 border-orange-500 text-white'
                            : 'bg-slate-900/30 border-slate-700/60'
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
                      <Card className="bg-slate-900/30 border-slate-700/60">
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

                {/* Input (anchored inside chat panel) */}
                <div className="border-t border-slate-700/60 bg-slate-900/40 px-4 py-4">
                  <div className="flex gap-3">
                    <textarea
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Ask your coach anything..."
                      rows={1}
                      className="flex-1 px-4 py-3 bg-slate-950 border border-slate-700 rounded-xl text-white resize-none focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
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
                    Receipts required for athlete-specific numbers (dates + activity ids + values).
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Capabilities / suggestions panel */}
            <Card className="lg:col-span-4 bg-slate-800/50 border-slate-700/50 h-full">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-sm text-slate-300 mb-3">
                  <Sparkles className="w-4 h-4 text-orange-500" />
                  <span className="font-semibold">Try one of these</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-3">
                  {(suggestions || []).slice(0, 5).map((prompt, i) => {
                    const card = buildSuggestionCard(prompt);
                    const Icon = card.Icon;
                    return (
                      <button
                        key={i}
                        type="button"
                        onClick={() => handleSend(card.prompt)}
                        disabled={isLoading}
                        className="text-left rounded-lg border border-slate-700/60 bg-slate-900/30 hover:bg-slate-900/40 hover:border-orange-500/40 transition-colors p-4 disabled:opacity-60 disabled:cursor-not-allowed"
                      >
                        <div className="flex items-start gap-3">
                          <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-700/60">
                            <Icon className="w-4 h-4 text-orange-400" />
                          </div>
                          <div className="min-w-0">
                            <div className="font-semibold text-slate-100">{card.title}</div>
                            <div className="text-sm text-slate-400 mt-1 leading-snug">
                              {card.description}
                            </div>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
