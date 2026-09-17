export interface ConversationSummary {
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  preview?: string;
}

export interface StoredMessage {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  citations?: unknown;
  created_at?: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: StoredMessage[];
}
