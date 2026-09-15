"use client";

import { ThemeProvider as NextThemeProvider } from "next-themes";

/**
 * Appearance follows the operating system until the reader picks a side,
 * and that choice then survives reloads.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemeProvider>
  );
}
