import { apiFetch, apiJson } from "./client";
import {
  ConversationDetail,
  ConversationSummary,
} from "@/types/conversation";

export const conversationsApi = {
  async list(): Promise<ConversationSummary[]> {
    return apiJson<ConversationSummary[]>("/conversations", {
      errorMessage: "Failed to list conversations",
    });
  },

  async create(title?: string, signal?: AbortSignal): Promise<ConversationSummary> {
    return apiJson<ConversationSummary>("/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title || null }),
      errorMessage: "Failed to create conversation",
      signal,
    });
  },

  async get(id: string): Promise<ConversationDetail> {
    return apiJson<ConversationDetail>(
      `/conversations/${encodeURIComponent(id)}`,
      { errorMessage: "Failed to load conversation" }
    );
  },

  async rename(id: string, title: string): Promise<ConversationSummary> {
    return apiJson<ConversationSummary>(
      `/conversations/${encodeURIComponent(id)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
        errorMessage: "Failed to rename conversation",
      }
    );
  },

  async remove(id: string): Promise<void> {
    await apiFetch(`/conversations/${encodeURIComponent(id)}`, {
      method: "DELETE",
      errorMessage: "Failed to delete conversation",
    });
  },
};
