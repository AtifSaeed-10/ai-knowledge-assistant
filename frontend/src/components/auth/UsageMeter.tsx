"use client";

import React from "react";

import { useAuthStore } from "@/store/useAuthStore";

/** Header sign-in. Usage counts stay off-screen so the workspace stays clean. */
export function UsageMeter() {
  const usage = useAuthStore((state) => state.usage);
  const user = useAuthStore((state) => state.user);
  const openSignup = useAuthStore((state) => state.openSignup);

  if (user || !usage?.authAvailable) return null;

  return (
    <button
      type="button"
      onClick={() => openSignup(null)}
      className="rounded-lg border border-line bg-surface px-2.5 py-1 text-ui font-medium text-ink transition-colors hover:border-line-strong hover:bg-surface-muted"
    >
      Sign in
    </button>
  );
}
