import Link from "next/link";

import { cn } from "@/lib/cn";

const LINKS = [
  { href: "/about", label: "About" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
] as const;

export function LegalLinks({
  className,
  linkClassName,
}: {
  className?: string;
  linkClassName?: string;
}) {
  return (
    <nav aria-label="About and legal" className={cn("flex flex-wrap items-center gap-x-1 gap-y-1", className)}>
      {LINKS.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className={cn(
            "-my-1.5 inline-flex min-h-[2.25rem] items-center rounded-md px-1.5 text-meta text-ink-subtle transition-colors hover:text-ink",
            linkClassName
          )}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
