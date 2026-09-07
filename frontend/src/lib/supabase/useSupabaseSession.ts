"use client";

import { useEffect } from "react";

import {
  getCurrentSession,
  isSupabaseConfigured,
  onAuthStateChange,
} from "./client";
import { applyAuthSession } from "@/lib/workspace/syncWorkspace";

/**
 * Keeps the Supabase session, the API token, and the workspace in sync.
 *
 * Sign-in claims any leftover guest trial, then always loads that account's
 * documents and chat history. Sign-out starts a fresh guest workspace.
 */
export function useSupabaseSession(): void {
  useEffect(() => {
    if (!isSupabaseConfigured()) return;

    void getCurrentSession().then((session) => void applyAuthSession(session));
    return onAuthStateChange((session) => void applyAuthSession(session));
  }, []);
}
