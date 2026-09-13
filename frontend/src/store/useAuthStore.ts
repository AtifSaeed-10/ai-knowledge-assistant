import { create } from 'zustand';

import { apiJson, setQuotaHandler, type QuotaErrorInfo } from '@/lib/api/client';
import { ensureGuestSession, setAccessToken } from '@/lib/guestSession';

export interface UsageSnapshot {
  tier: 'guest' | 'free';
  pdfsUsed: number;
  pdfsLimit: number;
  questionsUsed: number;
  questionsLimit: number;
  questionsWindow: 'trial' | 'month';
  maxPdfMb: number;
  authAvailable: boolean;
  admin: boolean;
}

interface UsageApiResponse {
  tier?: string;
  pdfs_used?: number;
  pdfs_limit?: number;
  questions_used?: number;
  questions_limit?: number;
  questions_window?: string;
  max_pdf_mb?: number;
  auth_available?: boolean;
  admin?: boolean;
}

export interface AuthUser {
  id: string;
  email: string | null;
  name: string | null;
  avatarUrl: string | null;
  seenWorkspaceTour: boolean;
}

interface AuthState {
  user: AuthUser | null;
  usage: UsageSnapshot | null;
  /** Why the signup modal opened, so the copy can match the blocked action. */
  signupReason: QuotaErrorInfo | null;
  isSignupOpen: boolean;

  initSession: () => void;
  refreshUsage: () => Promise<void>;
  openSignup: (reason?: QuotaErrorInfo | null) => void;
  closeSignup: () => void;
  setSession: (user: AuthUser | null, token: string | null) => void;
}

function mapUsage(data: UsageApiResponse): UsageSnapshot {
  return {
    tier: data.tier === 'free' ? 'free' : 'guest',
    pdfsUsed: data.pdfs_used ?? 0,
    pdfsLimit: data.pdfs_limit ?? 0,
    questionsUsed: data.questions_used ?? 0,
    questionsLimit: data.questions_limit ?? 0,
    questionsWindow: data.questions_window === 'month' ? 'month' : 'trial',
    maxPdfMb: data.max_pdf_mb ?? 25,
    authAvailable: data.auth_available === true,
    admin: data.admin === true,
  };
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  usage: null,
  signupReason: null,
  isSignupOpen: false,

  initSession: () => {
    ensureGuestSession();

    // Any route that reports a spent allowance opens the same modal, so new
    // endpoints get this behaviour for free.
    setQuotaHandler((info) => {
      set({ isSignupOpen: true, signupReason: info });
      void get().refreshUsage();
    });

    void get().refreshUsage();
  },

  refreshUsage: async () => {
    try {
      const data = await apiJson<UsageApiResponse>('/me/usage', {
        errorMessage: 'Could not load your usage',
      });
      set({ usage: mapUsage(data) });
    } catch {
      // The meter is informational; a failure must not block the workspace.
    }
  },

  openSignup: (reason = null) => set({ isSignupOpen: true, signupReason: reason }),

  closeSignup: () => set({ isSignupOpen: false }),

  setSession: (user, token) => {
    setAccessToken(token);
    set({ user, isSignupOpen: false, signupReason: null });
    void get().refreshUsage();
  },
}));

/** True when the actor has no questions left in the current window. */
export function questionsExhausted(usage: UsageSnapshot | null): boolean {
  if (!usage || usage.questionsLimit <= 0) return false;
  return usage.questionsUsed >= usage.questionsLimit;
}

/** True when the actor cannot upload another document. */
export function uploadsExhausted(usage: UsageSnapshot | null): boolean {
  if (!usage || usage.pdfsLimit <= 0) return false;
  return usage.pdfsUsed >= usage.pdfsLimit;
}
