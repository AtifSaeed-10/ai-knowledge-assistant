"use client";

import React from "react";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { useToastStore, type ToastVariant } from "@/store/useToastStore";

const ICONS: Record<ToastVariant, React.ComponentType<{ className?: string }>> = {
  error: AlertCircle,
  success: CheckCircle2,
  info: Info,
};

const ICON_TONE: Record<ToastVariant, string> = {
  error: "text-danger",
  success: "text-olive",
  info: "text-ink-muted",
};

export function Toaster() {
  const toasts = useToastStore((state) => state.toasts);
  const dismiss = useToastStore((state) => state.dismiss);

  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-4 bottom-4 z-[130] flex flex-col gap-2 sm:inset-x-auto sm:right-6 sm:w-[22rem]"
    >
      {toasts.map((toast) => {
        const Icon = ICONS[toast.variant];

        return (
          <div
            key={toast.id}
            role={toast.variant === "error" ? "alert" : "status"}
            className="pointer-events-auto flex animate-rise-in items-start gap-2.5 rounded-xl border border-line bg-surface px-3.5 py-3 shadow-raised"
          >
            <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${ICON_TONE[toast.variant]}`} />
            <div className="min-w-0 flex-1">
              <p className="text-ui font-semibold tracking-[-0.01em] text-ink break-anywhere">
                {toast.title}
              </p>
              {toast.description && (
                <p className="mt-0.5 text-meta leading-relaxed text-ink-muted break-anywhere">
                  {toast.description}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
              className="-mr-1 shrink-0 rounded-md p-1 text-ink-icon transition-colors hover:bg-surface-sunken hover:text-ink"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
