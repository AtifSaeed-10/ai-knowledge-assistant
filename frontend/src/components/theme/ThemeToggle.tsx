"use client";

import React, { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/cn";

/**
 * Two-state switch. Before mount the resolved theme is unknown, so a
 * same-sized placeholder holds the space and keeps the header from shifting.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const isDark = resolvedTheme === "dark";
  const label = isDark ? "Switch to light mode" : "Switch to dark mode";

  if (!mounted) {
    return (
      <div
        className={cn("h-10 w-10 shrink-0 sm:h-9 sm:w-9", className)}
        aria-hidden
      />
    );
  }

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      title={label}
      aria-label={label}
      className={cn(
        "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-surface hover:text-ink sm:h-9 sm:w-9",
        className
      )}
    >
      {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
    </button>
  );
}
