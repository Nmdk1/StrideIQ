/**
 * AI Coach API Service
 */

import { apiClient } from '../client';
import { API_CONFIG } from '../config';

export interface ChatRequest {
  message: string;
  include_context?: boolean;
}

export interface ChatResponse {
  response: string;
  thread_id?: string;
  // Optional Phase 10 payload: when the coach proposes deterministic actions.
  // This is populated by the coach orchestrator layer (not by the plain text response).
  proposal?: unknown;
  error: boolean;
  timed_out?: boolean;
  history_thin?: boolean;
  used_baseline?: boolean;
  baseline_needed?: boolean;
  rebuild_plan_prompt?: boolean;
}

export interface Suggestion {
  title: string;
  description: string;
  prompt: string;
}

export interface SuggestionsResponse {
  suggestions: Suggestion[];
}

export interface ContextResponse {
  context: string;
}

export interface ThreadMessage {
  role: 'user' | 'assistant' | string;
  content: string;
  proposal?: unknown;
  created_at?: string | null;
}

export interface HistoryResponse {
  thread_id?: string;
  messages: ThreadMessage[];
}

export interface NewConversationResponse {
  ok: boolean;
}

export const aiCoachService = {
  /**
   * Chat with the AI coach
   */
  async chat(request: ChatRequest): Promise<ChatResponse> {
    // Coach calls can be legitimately slow (tool calls + reasoning).
    // Override the default 30s client timeout.
    return apiClient.post<ChatResponse>('/v1/coach/chat', request, { timeoutMs: 120_000 });
  },

  /**
   * Stream chat response (SSE over fetch; supports auth headers).
   *
   * Emits "delta" chunks progressively. Heartbeats are ignored by default.
   */
  async chatStream(
    request: ChatRequest,
    opts: {
      onDelta: (delta: string) => void;
      onDone?: (meta: {
        timed_out?: boolean;
        thread_id?: string;
        history_thin?: boolean;
        used_baseline?: boolean;
        baseline_needed?: boolean;
        rebuild_plan_prompt?: boolean;
      }) => void;
      signal?: AbortSignal;
    }
  ): Promise<void> {
    const token =
      typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_CONFIG.baseURL}/v1/coach/chat/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify(request),
      signal: opts.signal,
    });

    if (!res.ok) {
      let detail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const data = await res.json();
        detail = data?.detail || detail;
      } catch {
        // ignore
      }
      throw new Error(detail);
    }

    if (!res.body) {
      // Extremely old environments; fall back to non-stream call.
      const r = await aiCoachService.chat(request);
      opts.onDelta(r.response || '');
      opts.onDone?.({
        timed_out: r.timed_out,
        thread_id: r.thread_id,
        history_thin: r.history_thin,
        used_baseline: r.used_baseline,
        baseline_needed: r.baseline_needed,
        rebuild_plan_prompt: r.rebuild_plan_prompt,
      });
      return;
    }

    const IDLE_TIMEOUT_MS = 135_000; // 135s — slightly above backend 120s hard ceiling
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let receivedDone = false;

    const handlePacket = (packet: string) => {
      const lines = packet.split(/\r?\n/);
      const dataLines: string[] = [];
      for (const line of lines) {
        if (line.startsWith('data:')) {
          const v = line.slice(5);
          dataLines.push(v.startsWith(' ') ? v.slice(1) : v);
        }
      }
      const dataStr = dataLines.join('\n').trim();
      if (!dataStr) return;
      let obj: Record<string, unknown> | null = null;
      try {
        obj = JSON.parse(dataStr);
      } catch {
        return;
      }
      if (obj?.type === 'delta' && typeof obj.delta === 'string') {
        opts.onDelta(obj.delta);
      }
      if (obj?.type === 'error' && typeof obj.error === 'string') {
        opts.onDelta(`\n\n${obj.error}`);
      }
      if (obj?.type === 'done') {
        receivedDone = true;
        opts.onDone?.({
          timed_out: obj.timed_out as boolean | undefined,
          thread_id: obj.thread_id as string | undefined,
          history_thin: obj.history_thin as boolean | undefined,
          used_baseline: obj.used_baseline as boolean | undefined,
          baseline_needed: obj.baseline_needed as boolean | undefined,
          rebuild_plan_prompt: obj.rebuild_plan_prompt as boolean | undefined,
        });
      }
    };

    const readWithTimeout = async (): Promise<ReadableStreamReadResult<Uint8Array>> => {
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          reject(new Error('Coach response timed out — please try again.'));
        }, IDLE_TIMEOUT_MS);
        reader.read().then(
          (result) => { clearTimeout(timer); resolve(result); },
          (err) => { clearTimeout(timer); reject(err); },
        );
      });
    };

    try {
      while (true) {
        const { done, value } = await readWithTimeout();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        if (buffer.includes('\r\n')) buffer = buffer.replace(/\r\n/g, '\n');

        let idx = buffer.indexOf('\n\n');
        while (idx !== -1) {
          const packet = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          handlePacket(packet);
          idx = buffer.indexOf('\n\n');
        }
      }
    } catch (timeoutErr) {
      reader.cancel().catch(() => {});
      if (!receivedDone) {
        opts.onDone?.({ timed_out: true });
      }
      throw timeoutErr;
    }

    // Flush any remaining decoder state + trailing packet without delimiter.
    buffer += decoder.decode();
    if (buffer.includes('\r\n')) buffer = buffer.replace(/\r\n/g, '\n');
    if (buffer.trim()) {
      handlePacket(buffer.trim());
    }
  },

  /**
   * Start a new conversation (clears persisted thread)
   */
  async newConversation(): Promise<NewConversationResponse> {
    return apiClient.post<NewConversationResponse>('/v1/coach/new-conversation', {});
  },

  /**
   * Get suggested questions
   */
  async getSuggestions(): Promise<SuggestionsResponse> {
    return apiClient.get<SuggestionsResponse>('/v1/coach/suggestions');
  },

  /**
   * Get the context that would be sent to the AI
   */
  async getContext(days?: number): Promise<ContextResponse> {
    const url = days ? `/v1/coach/context?days=${days}` : '/v1/coach/context';
    return apiClient.get<ContextResponse>(url);
  },

  /**
   * Get persisted coach history (if available)
   */
  async getHistory(limit: number = 50): Promise<HistoryResponse> {
    return apiClient.get<HistoryResponse>(`/v1/coach/history?limit=${limit}`);
  },
};
