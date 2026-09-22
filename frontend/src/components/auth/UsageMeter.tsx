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
      className="inline-flex h-10 items-center rounded-lg px-2.5 text-meta font-medium text-ink transition-colors hover:bg-surface-sunken sm:h-auto sm:py-1 sm:text-ui"
    >
      Sign in
    </button>
  );
}
