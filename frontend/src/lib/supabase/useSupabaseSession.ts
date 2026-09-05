"use client";

import { useEffect, useRef } from "react";
import type { Session } from "@supabase/supabase-js";

import { authApi } from "@/lib/api/auth";
import { setAccessToken } from "@/lib/guestSession";
import {
  getCurrentSession,
  isSupabaseConfigured,
  onAuthStateChange,
} from "./client";
import { useAuthStore } from "@/store/useAuthStore";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/useDocumentStore";

function userFromSession(session: Session) {
  const meta = (session.user.user_metadata || {}) as Record<string, unknown>;
  return {
    email: session.user.email ?? null,
    name: typeof meta.full_name === "string" ? meta.full_name : null,
    avatarUrl: typeof meta.avatar_url === "string" ? meta.avatar_url : null,
  };
}

/**
 * Keeps the Supabase session, the API token, and the workspace in sync.
 *
 * On first sign-in it claims the guest trial's work, then reloads documents
 * and conversations so the user's own library is what they see.
 */
export function useSupabaseSession(): void {
  const setSession = useAuthStore((state) => state.setSession);
  const refreshUsage = useAuthStore((state) => state.refreshUsage);
  const reloadDocuments = useDocumentStore((state) => state.reload);
  const initializeConversations = useChatStore((state) => state.initializeConversations);

  // Migration is once per browser session, not once per token refresh.
  const migratedRef = useRef(false);

  useEffect(() => {
    if (!isSupabaseConfigured()) return;

    let cancelled = false;

    const applySession = async (session: Session | null) => {
      if (cancelled) return;

      if (!session) {
        setAccessToken(null);
        setSession(null, null);
        migratedRef.current = false;
        return;
      }

      setSession(userFromSession(session), session.access_token);

      if (migratedRef.current) return;
      migratedRef.current = true;

      try {
        const result = await authApi.migrateGuest();
        if (cancelled) return;
        if (result.documents_moved > 0 || result.conversations_moved > 0) {
          await reloadDocuments();
          await initializeConversations();
        }
      } catch {
        // A failed claim must not block a valid sign-in; the user keeps
        // their account and can re-upload.
      }
      if (!cancelled) await refreshUsage();
    };

    void getCurrentSession().then(applySession);
    const unsubscribe = onAuthStateChange((session) => void applySession(session));

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [setSession, refreshUsage, reloadDocuments, initializeConversations]);
}
