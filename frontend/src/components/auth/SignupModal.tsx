"use client";

import React, { useState } from "react";
import { Check } from "lucide-react";

import { Dialog } from "@/components/ui/Dialog";
import { signInWithGoogle } from "@/lib/supabase/client";
import { useAuthStore } from "@/store/useAuthStore";

const GoogleMark = () => (
  <svg className="h-[18px] w-[18px]" viewBox="0 0 18 18" aria-hidden="true">
    <path
      fill="#4285F4"
      d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.71-1.58 2.68-3.9 2.68-6.62Z"
    />
    <path
      fill="#34A853"
      d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H1.96v2.33A8.99 8.99 0 0 0 9 18Z"
    />
    <path
      fill="#FBBC05"
      d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H1.96a9 9 0 0 0 0 8.1l2.01-2.33Z"
    />
    <path
      fill="#EA4335"
      d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.59A8.98 8.98 0 0 0 1.96 4.95l2.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"
    />
  </svg>
);

/**
 * Shown when the free trial runs out.
 *
 * The offer is storage and a bigger allowance, not a price — signing in is
 * free, so the copy never mentions upgrading or paying.
 */
export function SignupModal() {
  const isOpen = useAuthStore((state) => state.isSignupOpen);
  const reason = useAuthStore((state) => state.signupReason);
  const usage = useAuthStore((state) => state.usage);
  const closeSignup = useAuthStore((state) => state.closeSignup);

  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const authAvailable = usage?.authAvailable === true;

  const handleGoogle = async () => {
    setPending(true);
    setError(null);
    try {
      await signInWithGoogle();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not start sign-in. Please try again."
      );
      setPending(false);
    }
  };

  const headline = reason?.resource === "pdfs"
    ? "Add more documents — still free"
    : "Save your research and continue — still free";

  const benefits = [
    `${usage?.tier === "guest" ? "5 documents" : "More documents"} instead of ${usage?.pdfsLimit ?? 1}`,
    "100 questions every month",
    "100 trusted-site answers a month after you sign in",
    "Your PDFs and chats saved to your account",
  ];

  return (
    <Dialog
      open={isOpen}
      onClose={closeSignup}
      title={headline}
      description={
        reason?.message ||
        "You have reached the end of the free trial. Sign in with Google to keep going."
      }
    >
      <ul className="space-y-2.5">
        {benefits.map((benefit) => (
          <li key={benefit} className="flex items-start gap-2.5 text-body text-ink-muted">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-olive" aria-hidden />
            <span>{benefit}</span>
          </li>
        ))}
      </ul>

      <div className="mt-5">
        {authAvailable ? (
          <button
            type="button"
            onClick={handleGoogle}
            disabled={pending}
            className="inline-flex w-full items-center justify-center gap-2.5 rounded-lg border border-line bg-surface px-4 py-2.5 text-ui font-medium text-ink shadow-card transition-colors hover:border-line-strong hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-60"
          >
            <GoogleMark />
            {pending ? "Opening Google…" : "Continue with Google — free"}
          </button>
        ) : (
          <p className="rounded-lg border border-line bg-surface-muted px-4 py-3 text-meta text-ink-muted">
            Sign-in is not enabled on this server yet. Your trial usage resets
            when the beta opens.
          </p>
        )}

        {error && <p className="mt-2.5 text-meta text-clay">{error}</p>}

        <p className="mt-3 text-center text-meta text-ink-muted">
          No card, no Pro tier. DocuSage is free during the beta.
        </p>
      </div>
    </Dialog>
  );
}
