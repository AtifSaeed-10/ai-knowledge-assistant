import React from "react";
import { cn } from "@/lib/cn";

const TILE = "#4A5D23";
const FOLD = "#6A8240";
const HIGHLIGHT = "#D5E4C8";

/**
 * Page + cited passage. Fills are real hex values so the mark cannot
 * inherit white text color or wait on CSS variables.
 */
function MarkGlyph() {
  return (
    <>
      <path
        fill={TILE}
        d="M10.5 3h6.65L26 11.9V25.5A2.5 2.5 0 0 1 23.5 28h-13A2.5 2.5 0 0 1 8 25.5v-20A2.5 2.5 0 0 1 10.5 3Z"
      />
      <path fill={FOLD} d="M17.15 3 26 11.9H17.15V3Z" />
      <rect fill={HIGHLIGHT} x="11.25" y="15.35" width="10.25" height="3.7" rx="1.15" />
    </>
  );
}

/** Icon-only mark. Square, so height and width stay matched at every size. */
export function LogoMark({
  className = "h-7 w-7",
  decorative = false,
}: {
  className?: string;
  /** Hide from AT when a parent already names the brand. */
  decorative?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={cn("logo-mark shrink-0", className)}
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : "DocuSage"}
      aria-hidden={decorative ? true : undefined}
      xmlns="http://www.w3.org/2000/svg"
    >
      <MarkGlyph />
    </svg>
  );
}

/** Mark + wordmark. The name is always ink, never the parent’s currentColor. */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-ink", className)}>
      <LogoMark className="h-7 w-7" decorative />
      <span className="translate-y-[0.5px] text-[0.9375rem] font-semibold leading-none tracking-[-0.04em] text-ink">
        DocuSage
      </span>
    </span>
  );
}
