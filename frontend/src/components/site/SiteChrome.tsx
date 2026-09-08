import type { ReactNode } from "react";
import Link from "next/link";
import { Logo } from "@/components/ui/Logo";

export function SiteHeader() {
  return (
    <header className="flex h-16 items-center justify-between gap-3 border-b border-line bg-paper px-4 sm:px-6">
      <Link href="/" className="rounded-md" aria-label="DocuSage home">
        <Logo className="h-7 w-auto" />
      </Link>
      <nav className="flex items-center gap-1 sm:gap-2">
        <Link
          href="/privacy"
          className="rounded-lg px-2.5 py-1.5 text-ui font-medium text-ink-muted transition-colors hover:bg-surface hover:text-ink"
        >
          Privacy
        </Link>
        <Link
          href="/terms"
          className="hidden rounded-lg px-2.5 py-1.5 text-ui font-medium text-ink-muted transition-colors hover:bg-surface hover:text-ink sm:inline"
        >
          Terms
        </Link>
        <Link
          href="/"
          className="rounded-lg bg-olive px-3 py-1.5 text-ui font-medium text-white shadow-card transition-colors hover:bg-olive-dark"
        >
          Open workspace
        </Link>
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line px-4 py-6 sm:px-6">
      <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 text-meta text-ink-subtle">
        <p>DocuSage · answers from your PDFs, with the page</p>
        <nav className="flex gap-4">
          <Link href="/privacy" className="hover:text-ink">
            Privacy
          </Link>
          <Link href="/terms" className="hover:text-ink">
            Terms
          </Link>
          <Link href="/" className="hover:text-ink">
            Workspace
          </Link>
        </nav>
      </div>
    </footer>
  );
}

export function SiteShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-[100dvh] flex-col bg-paper text-ink">
      <SiteHeader />
      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10 sm:px-6 sm:py-14">
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}
