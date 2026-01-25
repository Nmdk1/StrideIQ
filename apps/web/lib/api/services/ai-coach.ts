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
}

export interface SuggestionsResponse {
  suggestions: string[];
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
      onDone?: (meta: { timed_out?: boolean; thread_id?: string }) => void;
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
      opts.onDone?.({ timed_out: r.timed_out, thread_id: r.thread_id });
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const handlePacket = (packet: string) => {
      const lines = packet.split(/\r?\n/);
      const dataLines: string[] = [];
      for (const line of lines) {
        if (line.startsWith('data:')) {
          // SSE spec: keep text after 'data:' (optionally a single leading space).
          const v = line.slice(5);
          dataLines.push(v.startsWith(' ') ? v.slice(1) : v);
        }
      }
      const dataStr = dataLines.join('\n').trim();
      if (!dataStr) return;
      let obj: any = null;
      try {
        obj = JSON.parse(dataStr);
      } catch {
        return;
      }
      if (obj?.type === 'delta' && typeof obj.delta === 'string') {
        opts.onDelta(obj.delta);
      }
      if (obj?.type === 'done') {
        opts.onDone?.({ timed_out: obj.timed_out, thread_id: obj.thread_id });
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // Normalize CRLF defensively (some environments/proxies).
      if (buffer.includes('\r\n')) buffer = buffer.replace(/\r\n/g, '\n');

      let idx = buffer.indexOf('\n\n');
      while (idx !== -1) {
        const packet = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        handlePacket(packet);
        idx = buffer.indexOf('\n\n');
      }
    }

    // Flush any remaining decoder state + trailing packet without delimiter.
    buffer += decoder.decode();
    if (buffer.includes('\r\n')) buffer = buffer.replace(/\r\n/g, '\n');
    if (buffer.trim()) {
      // If it ended with the delimiter, buffer will be empty; otherwise handle the last event.
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
