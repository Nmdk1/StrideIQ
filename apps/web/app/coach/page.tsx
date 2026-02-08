'use client';

/**
 * AI Coach Chat Page
 * 
 * Enhanced with shadcn/ui + Lucide.
 * Provides a chat interface to the AI running coach.
 */

import React, { useState, useRef, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { aiCoachService, type Suggestion } from '@/lib/api/services/ai-coach';
import { onboardingService } from '@/lib/api/services/onboarding';
import { useProgressSummary } from '@/lib/hooks/queries/progress';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { MessageSquare, Send, Sparkles, Activity, TrendingUp, RotateCcw, Trophy, BrainCircuit, Target, Zap, Heart } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { ProposalCard, type ProposalCardProposal } from '@/components/coach/ProposalCard';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content?: string;
  proposal?: ProposalCardProposal;
  timedOut?: boolean;
  retryMessage?: string;
  timestamp: Date;
}

function splitReceipts(content: string): { main: string; receipts: string | null } {
  // Split out a trailing "Receipts" section so the chat stays readable.
  // We expect markdown headings like "## Evidence" or "## Receipts".
  // (Backend is migrating from "Receipts" -> "Evidence", but we keep backwards compatibility.)
  const re = /(\n|^)##\s+(Evidence|Receipts)\s*\n/i;
  const m = content.match(re);
  if (!m || m.index == null) return { main: content, receipts: null };

  const idx = m.index + (m[1] === '\n' ? 1 : 0);
  const main = content.slice(0, idx).trimEnd();
  const receiptsRaw = content.slice(idx).trim();
  const receipts = receiptsRaw.replace(/^##\s+(Evidence|Receipts)\s*\n/i, '').trim();
  return { main, receipts: receipts || null };
}

function getSuggestionIcon(title: string) {
  const t = (title || '').toLowerCase();
  if (t.includes('pr') || t.includes('pb')) return Trophy;
  if (t.includes('tsb') || t.includes('load') || t.includes('fatigue') || t.includes('fresh')) return Zap;
  if (t.includes('efficiency')) return TrendingUp;
  if (t.includes('run') || t.includes('mi ')) return Activity;
  if (t.includes('days to') || t.includes('race') || t.includes('goal')) return Target;
  if (t.includes('improving') || t.includes('declining') || t.includes('trend')) return TrendingUp;
  if (t.includes('recovery') || t.includes('durability')) return Heart;
  return BrainCircuit;
}

// Suggestion rendering helper — renders a single structured suggestion card
function SuggestionButton({ suggestion, onClick, disabled }: { suggestion: Suggestion; onClick: () => void; disabled: boolean }) {
  const Icon = getSuggestionIcon(suggestion.title);
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="text-left rounded-lg border border-slate-700/60 bg-slate-900/30 hover:bg-slate-900/40 hover:border-orange-500/40 transition-colors p-4 disabled:opacity-60 disabled:cursor-not-allowed"
    >
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-700/60">
          <Icon className="w-4 h-4 text-orange-400" />
        </div>
        <div className="min-w-0">
          <div className="font-semibold text-slate-100">{suggestion.title}</div>
          <div className="text-sm text-slate-400 mt-1 leading-snug">
            {suggestion.description}
          </div>
        </div>
      </div>
    </button>
  );
}


export default function CoachPage() {
  return (
    <Suspense fallback={null}>
      <CoachPageInner />
    </Suspense>
  );
}

function CoachPageInner() {
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [stickToBottom, setStickToBottom] = useState(true);
  const [baselineNeeded, setBaselineNeeded] = useState(false);
  const [baselineOpen, setBaselineOpen] = useState(false);
  const [usedBaselineBanner, setUsedBaselineBanner] = useState(false);
  const [rebuildPlanPrompt, setRebuildPlanPrompt] = useState(false);
  
  // Progress summary for empty state brief + context panel
  const { data: progressData } = useProgressSummary(28);
  const [baselineDraft, setBaselineDraft] = useState({
    runs_per_week_4w: 3,
    weekly_volume_value: 15,
    weekly_volume_unit: 'miles' as 'miles' | 'km' | 'minutes',
    longest_run_last_month: 4,
    longest_run_unit: 'miles' as 'miles' | 'km',
    returning_from_break: false,
    return_date_approx: '',
  });
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const isEmptyConversation = messages.length <= 1;
  
  // Only auto-scroll if the user is already near the bottom.
  useEffect(() => {
    if (!stickToBottom) return;
    // rAF helps ensure the DOM has laid out (esp. when history loads)
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    });
  }, [messages, stickToBottom]);

  const handleTranscriptScroll = () => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    // If you're within ~80px of bottom, keep auto-scroll enabled.
    setStickToBottom(distanceFromBottom <= 80);
  };
  
  // Load persisted history (if available)
  useEffect(() => {
    let cancelled = false;
    aiCoachService.getHistory(80)
      .then((res) => {
        if (cancelled) return;
        const hist = (res?.messages || [])
          .filter((m) => (m.content || '').trim() || (m as any).proposal)
          .map((m, idx) => ({
            id: `hist_${idx}`,
            role: (m.role === 'user' ? 'user' : 'assistant') as Message['role'],
            content: m.content,
            proposal: (m as any).proposal,
            timestamp: m.created_at ? new Date(m.created_at) : new Date(),
          }));
        setMessages(hist);
      })
      .catch(() => {
        // If history fetch fails, fall back to new session UX.
      })
      .finally(() => {
        if (!cancelled) setHistoryLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Build coach brief from progress data for empty state
  const coachBrief = React.useMemo(() => {
    if (!progressData) return null;
    const lines: string[] = [];
    if (progressData.ctl !== null || progressData.tsb !== null) {
      const parts: string[] = [];
      if (progressData.ctl !== null) parts.push('CTL ' + progressData.ctl.toFixed(0));
      if (progressData.atl !== null) parts.push('ATL ' + progressData.atl.toFixed(0));
      if (progressData.tsb !== null) {
        const zone = progressData.tsb_zone ? ' (' + progressData.tsb_zone + ')' : '';
        parts.push('TSB ' + progressData.tsb.toFixed(0) + zone);
      }
      if (parts.length) lines.push('**Fitness:** ' + parts.join(' / '));
    }
    if (progressData.volume_trajectory) {
      const vol = progressData.volume_trajectory;
      if (vol.current_week_mi != null) {
        const target = vol.peak_week_mi ? ' (peak ' + vol.peak_week_mi.toFixed(0) + 'mi)' : '';
        lines.push('**This week:** ' + vol.current_week_mi.toFixed(1) + 'mi' + target);
      }
    }
    if (progressData.recovery) {
      const rec = progressData.recovery;
      if (rec.durability_index != null) {
        const halfLifeDays = rec.recovery_half_life_hours != null ? (rec.recovery_half_life_hours / 24).toFixed(1) : '?';
        lines.push('**Durability:** ' + rec.durability_index.toFixed(1) + ' / Half-life ' + halfLifeDays + ' days');
      }
    }
    if (progressData.goal_race_name && progressData.goal_race_days_remaining != null) {
      lines.push('**Race:** ' + progressData.goal_race_name + ' in ' + progressData.goal_race_days_remaining + ' days');
    }
    if (progressData.race_predictions && progressData.race_predictions.length > 0) {
      const pred = progressData.race_predictions[0];
      if (pred.predicted_time) lines.push('**Projection:** ' + pred.distance + ' - ' + pred.predicted_time);
    }
    return lines.length > 0 ? lines.join('\n\n') : null;
  }, [progressData]);

  // Add initial greeting (only after we attempted to load history)
  useEffect(() => {
    if (historyLoaded && messages.length === 0) {
      const brief = coachBrief
        ? 'Here\'s what I see in your data today:\n\n' + coachBrief + '\n\nWhat do you want to work on?'
        : 'I\'m your StrideIQ Coach. Everything I say is backed by your training data.\n\nWhat do you want to understand or decide today?';
      setMessages([{
        id: 'greeting',
        role: 'assistant',
        content: brief, // data-driven brief replaces generic greeting -- was: `Hi — I’m your StrideIQ Coach.\n\nI don’t guess. If I use numbers, I’ll cite evidence from your training data (dates + run names + key values).\n\nWhat do you want to understand or decide today?`,
        timestamp: new Date(),
      }]);
    }
  }, [historyLoaded, messages.length, coachBrief]);

  // Fetch dynamic suggestions on load
  useEffect(() => {
    let cancelled = false;
    aiCoachService.getSuggestions()
      .then((res) => {
        if (!cancelled) {
          // Normalize: backend may return strings (legacy) or {title,description,prompt} objects
          const raw = res.suggestions || [];
          const normalized = raw.map((s: unknown) =>
            typeof s === 'string'
              ? { title: s, description: '', prompt: s }
              : s as Suggestion
          );
          setSuggestions(normalized);
        }
      })
      .catch(() => {
        if (!cancelled) setSuggestions([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Deep link: read ?q= parameter and pre-fill input
  useEffect(() => {
    const q = searchParams?.get('q');
    if (q && !input) {
      setInput(q);
      // Focus the input so user can just hit send
      requestAnimationFrame(() => inputRef.current?.focus());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Thin-history fallback status (best-effort).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const st = await onboardingService.getStatus();
        if (cancelled) return;
        setBaselineNeeded(!!st?.baseline?.needed);
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const saveBaseline = async () => {
    setError(null);
    try {
      await onboardingService.saveIntake('baseline', baselineDraft as any, true);
      setBaselineNeeded(false);
      setUsedBaselineBanner(true);
      setBaselineOpen(false);
    } catch (e: any) {
      setError(e?.message || 'Failed to save baseline answers.');
    }
  };
  
  const handleSend = async (messageText?: string) => {
    const text = messageText || input.trim();
    if (!text || isLoading) return;

    // Production-beta fallback: if connected history is thin, capture a minimal baseline once.
    if (baselineNeeded) {
      setBaselineOpen(true);
      return;
    }
    
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
    
    // Get AI response (streamed)
    setIsLoading(true);
    try {
      const assistantId = (Date.now() + 1).toString();
      setMessages(prev => [
        ...prev,
        {
          id: assistantId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
        },
      ]);

      const controller = new AbortController();

      await aiCoachService.chatStream(
        { message: text },
        {
          signal: controller.signal,
          onDelta: (delta) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: `${m.content || ''}${delta}` }
                  : m
              )
            );
            // Keep the tail visible during streaming unless the user scrolled up.
            requestAnimationFrame(() => {
              if (stickToBottom) {
                messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
              }
            });
          },
          onDone: (meta) => {
            if (meta?.timed_out) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        timedOut: true,
                        retryMessage: text,
                        content:
                          (m.content || '').includes("Thinking took too long")
                            ? m.content
                            : `${m.content || ''}\n\n---\nThinking took too long — here's a partial response. Retry?`,
                      }
                    : m
                )
              );
            }
            if (meta?.used_baseline) {
              setUsedBaselineBanner(true);
            }
            if (meta?.rebuild_plan_prompt) {
              setRebuildPlanPrompt(true);
            }
          },
        }
      );
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
      {/* IMPORTANT: Navigation is a sticky h-16 (4rem). Fit coach *under* it. */}
      {/* The page should NOT scroll; only the transcript (and sidebar) should. */}
      <div
        data-testid="coach-shell"
        className="h-[calc(100vh-4rem)] h-[calc(100dvh-4rem)] overflow-hidden bg-slate-900 text-slate-100"
      >
        {/* NOTE: min-h-0 is critical so inner flex children can become scroll containers */}
        <div
          data-testid="coach-shell-inner"
          className="max-w-7xl mx-auto px-4 h-full min-h-0 flex flex-col"
        >

          {/* Header (match Home page shell) */}
          <div className="flex items-center justify-between gap-4 py-6 flex-none">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
                <MessageSquare className="w-6 h-6 text-orange-500" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-bold">Coach</h1>
                  <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30 text-xs">AI</Badge>
                </div>
                  <p className="text-sm text-slate-400">High-trust analysis and prescriptive training, backed by evidence.</p>
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

          {/* Main grid (fills viewport under header) */}
          <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_20rem] gap-6 items-stretch flex-1 min-h-0 pb-6">
            {/* Chat panel */}
            <Card className="bg-slate-800/50 border-slate-700/50 overflow-hidden flex flex-col h-full min-h-0 min-w-0">
              <CardContent
                data-testid="coach-chat-cardcontent"
                className="p-0 flex flex-col flex-1 min-h-0"
              >
                {/* Messages (taller + higher: less outer padding, more viewport usage) */}
                <div
                  data-testid="coach-transcript"
                  ref={scrollContainerRef}
                  onScroll={handleTranscriptScroll}
                  className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-4 py-4"
                >
                  {usedBaselineBanner && (
                    <div className="mb-4 rounded-md border border-slate-700/60 bg-slate-950/40 px-4 py-3 text-sm text-slate-200">
                      Using your answers for now — connect Strava/Garmin for better insights.
                    </div>
                  )}

                  {rebuildPlanPrompt && (
                    <div className="mb-4 rounded-md border border-slate-700/60 bg-slate-950/40 px-4 py-3 text-sm text-slate-200">
                      New training data detected. Want to rebuild your plan based on your recent history?
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            setRebuildPlanPrompt(false);
                            setInput(
                              "I just connected new training data — please rebuild my plan based on my last 8 weeks (keep it conservative if I'm returning)."
                            );
                            requestAnimationFrame(() => inputRef.current?.focus());
                          }}
                        >
                          Rebuild plan (ask Coach)
                        </Button>
                        <Button type="button" size="sm" variant="ghost" onClick={() => setRebuildPlanPrompt(false)}>
                          Not now
                        </Button>
                      </div>
                    </div>
                  )}

                  {baselineOpen && (
                    <Card className="mb-4 bg-slate-900/30 border-slate-700/60">
                      <CardContent className="py-4 px-5 space-y-3">
                        <div className="text-sm font-semibold text-slate-200">
                          Quick baseline (only because your connected history is thin)
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          <label className="text-sm text-slate-300">
                            Runs/week (last 4 weeks)
                            <select
                              className="mt-1 w-full rounded bg-slate-950 border border-slate-800 px-2 py-1"
                              value={baselineDraft.runs_per_week_4w}
                              onChange={(e) => setBaselineDraft((p) => ({ ...p, runs_per_week_4w: Number(e.target.value) }))}
                            >
                              {Array.from({ length: 8 }).map((_, i) => (
                                <option key={i} value={i}>
                                  {i}
                                </option>
                              ))}
                            </select>
                          </label>

                          <label className="text-sm text-slate-300">
                            Typical weekly miles/minutes (last 4 weeks)
                            <div className="mt-1 flex gap-2">
                              <input
                                type="number"
                                className="w-full rounded bg-slate-950 border border-slate-800 px-2 py-1"
                                value={baselineDraft.weekly_volume_value}
                                onChange={(e) => setBaselineDraft((p) => ({ ...p, weekly_volume_value: Number(e.target.value) }))}
                              />
                              <select
                                className="rounded bg-slate-950 border border-slate-800 px-2 py-1"
                                value={baselineDraft.weekly_volume_unit}
                                onChange={(e) => setBaselineDraft((p) => ({ ...p, weekly_volume_unit: e.target.value as any }))}
                              >
                                <option value="miles">miles</option>
                                <option value="km">km</option>
                                <option value="minutes">minutes</option>
                              </select>
                            </div>
                          </label>

                          <label className="text-sm text-slate-300">
                            Longest run in last month
                            <div className="mt-1 flex gap-2">
                              <input
                                type="number"
                                className="w-full rounded bg-slate-950 border border-slate-800 px-2 py-1"
                                value={baselineDraft.longest_run_last_month}
                                onChange={(e) => setBaselineDraft((p) => ({ ...p, longest_run_last_month: Number(e.target.value) }))}
                              />
                              <select
                                className="rounded bg-slate-950 border border-slate-800 px-2 py-1"
                                value={baselineDraft.longest_run_unit}
                                onChange={(e) => setBaselineDraft((p) => ({ ...p, longest_run_unit: e.target.value as any }))}
                              >
                                <option value="miles">miles</option>
                                <option value="km">km</option>
                              </select>
                            </div>
                          </label>

                          <div className="text-sm text-slate-300">
                            Returning from a break/injury?
                            <div className="mt-1 flex items-center gap-2">
                              <input
                                type="checkbox"
                                checked={baselineDraft.returning_from_break}
                                onChange={(e) => setBaselineDraft((p) => ({ ...p, returning_from_break: e.target.checked }))}
                              />
                              <span className="text-slate-400">Yes</span>
                              <input
                                type="date"
                                className="ml-auto rounded bg-slate-950 border border-slate-800 px-2 py-1"
                                value={baselineDraft.return_date_approx}
                                onChange={(e) => setBaselineDraft((p) => ({ ...p, return_date_approx: e.target.value }))}
                                disabled={!baselineDraft.returning_from_break}
                              />
                            </div>
                          </div>
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <Button type="button" size="sm" onClick={saveBaseline} disabled={isLoading}>
                            Save & continue
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setBaselineOpen(false);
                              setBaselineNeeded(false);
                            }}
                          >
                            Skip for now
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {isEmptyConversation ? (
                    <div className="h-full min-h-[52vh] flex flex-col items-center justify-center gap-6">
                      {messages.map((message) => (
                        <div
                          key={message.id}
                          className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} w-full`}
                        >
                          <Card
                            className={`max-w-[92%] w-full ${
                              message.role === 'user'
                                ? 'bg-orange-600 border-orange-500 text-white'
                                : 'bg-slate-900/30 border-slate-700/60'
                            }`}
                          >
                            <CardContent className="py-4 px-5">
                              {message.role === 'assistant' ? (
                                (() => {
                                  if (message.proposal) {
                                    return (
                                      <ProposalCard
                                        proposal={message.proposal}
                                        onAskFollowup={(suggestedText) => {
                                          setInput(suggestedText);
                                          requestAnimationFrame(() => inputRef.current?.focus());
                                        }}
                                      />
                                    );
                                  }
                                  const { main, receipts } = splitReceipts(message.content || '');
                                  return (
                                    <div className="space-y-3">
                                      <div className="prose prose-invert prose-sm max-w-none">
                                        <ReactMarkdown>{main}</ReactMarkdown>
                                      </div>
                                      {receipts && (
                                        <details className="rounded-lg border border-slate-700/60 bg-slate-950/40 px-4 py-3">
                                          <summary className="cursor-pointer text-xs font-semibold text-slate-300">
                                            Evidence (expand)
                                          </summary>
                                          <div className="mt-2 prose prose-invert prose-sm max-w-none text-slate-300">
                                            <ReactMarkdown>{receipts}</ReactMarkdown>
                                          </div>
                                        </details>
                                      )}
                                      {message.timedOut && message.retryMessage && (
                                        <div className="flex items-center gap-2">
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            disabled={isLoading}
                                            onClick={() => handleSend(message.retryMessage)}
                                            className="border-slate-700 hover:border-orange-500/50 hover:bg-slate-800 text-slate-300"
                                          >
                                            Retry
                                          </Button>
                                          <span className="text-xs text-slate-400">
                                            If this keeps timing out, ask a narrower question.
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  );
                                })()
                              ) : (
                                <p className="whitespace-pre-wrap">{message.content}</p>
                              )}
                              <p className={`text-xs mt-3 ${message.role === 'user' ? 'text-orange-200' : 'text-slate-500'}`}>
                                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </p>
                            </CardContent>
                          </Card>
                        </div>
                      ))}

                      {/* Mobile: inline suggestions under welcome (sidebar hidden) */}
                      {suggestions.length > 0 && (
                        <div className="w-full md:hidden" data-testid="coach-suggestions-mobile">
                          <div className="flex items-center gap-2 text-xs text-slate-400 mb-3">
                            <Sparkles className="w-3.5 h-3.5 text-orange-500" />
                            <span>I want to talk about...</span>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            {(suggestions || []).slice(0, 5).map((s, i) => (
                              <SuggestionButton
                                key={i}
                                suggestion={s}
                                onClick={() => handleSend(s.prompt)}
                                disabled={isLoading}
                              />
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-4">
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
                                (() => {
                                  if (message.proposal) {
                                    return (
                                      <ProposalCard
                                        proposal={message.proposal}
                                        onAskFollowup={(suggestedText) => {
                                          setInput(suggestedText);
                                          requestAnimationFrame(() => inputRef.current?.focus());
                                        }}
                                      />
                                    );
                                  }
                                  const { main, receipts } = splitReceipts(message.content || '');
                                  return (
                                    <div className="space-y-3">
                                      <div className="prose prose-invert prose-sm max-w-none">
                                        <ReactMarkdown>{main}</ReactMarkdown>
                                      </div>
                                      {receipts && (
                                        <details className="rounded-lg border border-slate-700/60 bg-slate-950/40 px-3 py-2">
                                          <summary className="cursor-pointer text-xs font-semibold text-slate-300">
                                            Evidence (expand)
                                          </summary>
                                          <div className="mt-2 prose prose-invert prose-sm max-w-none text-slate-300">
                                            <ReactMarkdown>{receipts}</ReactMarkdown>
                                          </div>
                                        </details>
                                      )}
                                      {message.timedOut && message.retryMessage && (
                                        <div className="flex items-center gap-2">
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            disabled={isLoading}
                                            onClick={() => handleSend(message.retryMessage)}
                                            className="border-slate-700 hover:border-orange-500/50 hover:bg-slate-800 text-slate-300"
                                          >
                                            Retry
                                          </Button>
                                          <span className="text-xs text-slate-400">
                                            If this keeps timing out, ask a narrower question.
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  );
                                })()
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
                    </div>
                  )}

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

                {/* When user scrolls up, offer a quick way back down */}
                {!stickToBottom && (
                  <div className="px-4 pt-3 flex justify-center">
                    <button
                      type="button"
                      onClick={() => {
                        setStickToBottom(true);
                        requestAnimationFrame(() => {
                          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
                        });
                      }}
                      className="text-xs font-semibold px-3 py-1.5 rounded-full border border-slate-700/60 bg-slate-950/40 text-slate-200 hover:border-orange-500/40 hover:text-white hover:bg-slate-950/60 transition-colors"
                    >
                      Jump to bottom
                    </button>
                  </div>
                )}

                {/* Input (anchored inside chat panel) */}
                <div className="border-t border-slate-700/60 bg-slate-900/40 px-4 py-4 flex-none">
                  <div className="flex">
                    <div className="relative flex-1">
                      <textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask your coach anything..."
                        rows={1}
                        className="w-full px-4 py-3 pr-12 bg-slate-950 border border-slate-700 rounded-xl text-white resize-none focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500/40"
                      />
                      <button
                        type="button"
                        onClick={() => handleSend()}
                        disabled={!input.trim() || isLoading}
                        className="absolute right-2 top-1/2 -translate-y-1/2 inline-flex items-center justify-center h-9 w-9 rounded-lg bg-orange-600 hover:bg-orange-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white"
                        aria-label="Send message"
                      >
                        <Send className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <p className="text-xs text-slate-400 text-center mt-2">
                    Evidence is attached to analytic claims (expand in-message).
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Context + suggestions panel (desktop sidebar) */}
            <Card
              className="hidden md:flex flex-col bg-slate-800/50 border-slate-700/50 h-full min-h-0 w-80"
              data-testid="coach-suggestions-sidebar"
            >
              <CardContent className="p-4 flex-1 min-h-0 overflow-y-auto space-y-5">
                {/* Context panel: live metrics */}
                {progressData && (progressData.ctl !== null || progressData.tsb !== null) && (
                  <div>
                    <div className="flex items-center gap-2 text-sm text-slate-300 mb-3">
                      <Activity className="w-4 h-4 text-orange-500" />
                      <span className="font-semibold">Your data</span>
                    </div>
                    <div className="space-y-2 text-sm">
                      {progressData.ctl !== null && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Fitness (CTL)</span>
                          <span className="text-slate-100 font-medium">
                            {progressData.ctl.toFixed(0)}
                            {progressData.ctl_trend && (
                              <span className={progressData.ctl_trend === 'up' ? 'text-green-400 ml-1' : progressData.ctl_trend === 'down' ? 'text-red-400 ml-1' : 'text-slate-400 ml-1'}>
                                {progressData.ctl_trend === 'up' ? '\u2191' : progressData.ctl_trend === 'down' ? '\u2193' : '\u2192'}
                              </span>
                            )}
                          </span>
                        </div>
                      )}
                      {progressData.tsb !== null && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Form (TSB)</span>
                          <span className="text-slate-100 font-medium">{progressData.tsb.toFixed(0)}</span>
                        </div>
                      )}
                      {progressData.recovery?.durability_index != null && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Durability</span>
                          <span className="text-slate-100 font-medium">{progressData.recovery.durability_index.toFixed(1)}</span>
                        </div>
                      )}
                      {progressData.goal_race_days_remaining != null && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Race</span>
                          <span className="text-slate-100 font-medium">{progressData.goal_race_days_remaining} days</span>
                        </div>
                      )}
                      {progressData.volume_trajectory?.current_week_mi != null && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">This week</span>
                          <span className="text-slate-100 font-medium">{progressData.volume_trajectory.current_week_mi.toFixed(1)}mi</span>
                        </div>
                      )}
                    </div>
                    <div className="border-b border-slate-700/50 mt-4" />
                  </div>
                )}

                {/* Suggestions */}
                {suggestions.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 text-sm text-slate-300 mb-3">
                      <Sparkles className="w-4 h-4 text-orange-500" />
                      <span className="font-semibold">I want to talk about...</span>
                    </div>
                    <div className="grid grid-cols-1 gap-3">
                      {(suggestions || []).slice(0, 5).map((s, i) => (
                        <SuggestionButton
                          key={i}
                          suggestion={s}
                          onClick={() => handleSend(s.prompt)}
                          disabled={isLoading}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
