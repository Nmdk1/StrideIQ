/**
 * AI Coach API Service
 */

import { apiClient } from '../client';

export interface ChatRequest {
  message: string;
  include_context?: boolean;
}

export interface ChatResponse {
  response: string;
  thread_id?: string;
  error: boolean;
}

export interface SuggestionsResponse {
  suggestions: string[];
}

export interface ContextResponse {
  context: string;
}

export interface NewConversationResponse {
  ok: boolean;
}

export const aiCoachService = {
  /**
   * Chat with the AI coach
   */
  async chat(request: ChatRequest): Promise<ChatResponse> {
    return apiClient.post<ChatResponse>('/v1/coach/chat', request);
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
};
