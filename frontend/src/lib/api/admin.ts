import { apiJson } from "./client";

export interface AdminPerson {
  actor_type: "user" | "guest" | string;
  actor_id: string;
  label: string;
  email: string | null;
  created_at: string | null;
  last_seen_at: string | null;
  pdfs: number;
  failed_pdfs: number;
  ready_pdfs: number;
  questions: number;
  chats: number;
  migrated_to: string | null;
}

export interface AdminUpload {
  document_id: string;
  filename: string;
  uploaded_at: string | null;
  total_pages: number | null;
  total_chunks: number | null;
  status: string;
  index_error: string | null;
  owner_type: string | null;
  owner_label: string;
}

export interface AdminEvent {
  event_id: string;
  created_at: string;
  actor_type: string | null;
  actor_id: string | null;
  actor_label: string;
  route: string | null;
  kind: string;
  provider: string | null;
  category: string | null;
  status_code: number | null;
  message: string | null;
  document_id: string | null;
}

export interface AdminTotals {
  signed_in_users: number;
  guest_sessions: number;
  pdfs: number;
  failed_pdfs: number;
  questions_this_month: number;
  questions_today: number;
  errors_recent: number;
}

export interface AdminGroq {
  configured: boolean;
  updated_at: string | null;
  remaining_requests: number | null;
  limit_requests: number | null;
  remaining_tokens: number | null;
  limit_tokens: number | null;
  reset_requests: string | null;
  reset_tokens: string | null;
  tokens_used_today: number;
  requests_today: number;
  last_error: string | null;
}

export interface AdminAzure {
  credit_start_usd: number;
  spend_usd: number | null;
  remaining_usd: number | null;
  expires: string | null;
  hourly_usd: number;
  estimated_monthly_usd: number;
  started_at: string | null;
  source: "manual" | "estimate" | "unknown" | string;
  as_of: string;
}

export interface AdminOverview {
  generated_at: string;
  totals: AdminTotals;
  people: AdminPerson[];
  uploads: AdminUpload[];
  events: AdminEvent[];
  groq: AdminGroq;
  azure: AdminAzure;
}

export const adminApi = {
  overview(): Promise<AdminOverview> {
    return apiJson<AdminOverview>("/admin/overview", {
      errorMessage: "Could not load operations",
    });
  },
};
