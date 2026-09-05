"use client";

import React from "react";

import { questionsExhausted, useAuthStore } from "@/store/useAuthStore";

/**
 * Quiet usage readout for the header.
 *
 * Deliberately understated: it turns amber only when the allowance is nearly
 * gone, so the workspace never feels like a paywall.
 */
export function UsageMeter() {
  const usage = useAuthStore((state) => state.usage);
  const user = useAuthStore((state) => state.user);
  const openSignup = useAuthStore((state) => state.openSignup);

  if (!usage) return null;

  const questionsLeft = Math.max(0, usage.questionsLimit - usage.questionsUsed);
  const exhausted = questionsExhausted(usage);
  const nearlyDone = !exhausted && questionsLeft <= Math.max(1, Math.ceil(usage.questionsLimit * 0.2));

  const tone = exhausted
    ? "text-clay"
    : nearlyDone
      ? "text-ink"
      : "text-ink-muted";

  const label = `${usage.pdfsUsed}/${usage.pdfsLimit} PDF${usage.pdfsLimit === 1 ? "" : "s"} · ${usage.questionsUsed}/${usage.questionsLimit} question${usage.questionsLimit === 1 ? "" : "s"}`;
  const windowLabel = usage.questionsWindow === "month" ? "this month" : "free trial";

  return (
    <div className="hidden items-center gap-2 sm:flex">
      <span
        className={`text-ui tabular-nums ${tone}`}
        title={`${label} used — ${windowLabel}`}
      >
        {label}
      </span>

      {!user && usage.authAvailable && (
        <button
          type="button"
          onClick={() => openSignup(null)}
          className="rounded-lg border border-line bg-surface px-2.5 py-1 text-ui font-medium text-ink transition-colors hover:border-line-strong hover:bg-surface-muted"
        >
          Sign in
        </button>
      )}
    </div>
  );
}
