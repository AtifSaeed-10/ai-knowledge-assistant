import { API_CONFIG } from "./client";
import {
  ConversationDetail,
  ConversationSummary,
} from "@/types/conversation";

export const conversationsApi = {
  async list(): Promise<ConversationSummary[]> {
    const response = await fetch(`${API_CONFIG.baseUrl}/conversations`);
    if (!response.ok) {
      throw new Error("Failed to list conversations");
    }
    return response.json();
  },

  async create(title?: string): Promise<ConversationSummary> {
    const response = await fetch(`${API_CONFIG.baseUrl}/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title || null }),
    });
    if (!response.ok) {
      throw new Error("Failed to create conversation");
    }
    return response.json();
  },

  async get(id: string): Promise<ConversationDetail> {
    const response = await fetch(
      `${API_CONFIG.baseUrl}/conversations/${encodeURIComponent(id)}`
    );
    if (!response.ok) {
      throw new Error("Failed to load conversation");
    }
    return response.json();
  },

  async rename(id: string, title: string): Promise<ConversationSummary> {
    const response = await fetch(
      `${API_CONFIG.baseUrl}/conversations/${encodeURIComponent(id)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      }
    );
    if (!response.ok) {
      throw new Error("Failed to rename conversation");
    }
    return response.json();
  },

  async remove(id: string): Promise<void> {
    const response = await fetch(
      `${API_CONFIG.baseUrl}/conversations/${encodeURIComponent(id)}`,
      { method: "DELETE" }
    );
    if (!response.ok) {
      throw new Error("Failed to delete conversation");
    }
  },
};
