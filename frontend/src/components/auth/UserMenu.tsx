"use client";

import React, { useEffect, useId, useRef, useState } from "react";
import { LayoutDashboard, LogOut } from "lucide-react";
import Link from "next/link";

import { signOut } from "@/lib/supabase/client";
import { applyAuthSession } from "@/lib/workspace/syncWorkspace";
import { useAuthStore, type AuthUser } from "@/store/useAuthStore";

function displayName(user: AuthUser): string {
  if (user.name?.trim()) return user.name.trim();
  const email = user.email?.trim() || "";
  const local = email.split("@")[0] || "";
  if (!local) return "Signed in";
  return local.replace(/[._-]+/g, " ");
}

function initials(user: AuthUser): string {
  const name = displayName(user);
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function Avatar({ user, size = 32 }: { user: AuthUser; size?: number }) {
  const [failed, setFailed] = useState(false);
  const showPhoto = Boolean(user.avatarUrl) && !failed;

  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-olive text-white"
      style={{ width: size, height: size }}
      aria-hidden
    >
      {showPhoto ? (
        // Google avatar is a remote URL; hide it if the request fails.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={user.avatarUrl || ""}
          alt=""
          className="h-full w-full object-cover"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className="text-[11px] font-semibold leading-none tracking-wide">
          {initials(user)}
        </span>
      )}
    </span>
  );
}

/**
 * ChatGPT-style account control: avatar opens name, email, and sign out.
 */
export function UserMenu() {
  const user = useAuthStore((state) => state.user);
  const isAdmin = useAuthStore((state) => state.usage?.admin === true);

  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;

    const onPointer = (event: MouseEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;

  const name = displayName(user);

  const handleSignOut = async () => {
    setBusy(true);
    try {
      await signOut();
    } finally {
      await applyAuthSession(null);
      setBusy(false);
      setOpen(false);
    }
  };

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        aria-label="Open account menu"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((current) => !current)}
        className="inline-flex h-10 w-10 items-center justify-center rounded-full outline-none ring-olive/30 transition hover:ring-2 focus-visible:ring-2 sm:h-9 sm:w-9"
      >
        <Avatar user={user} />
      </button>

      {open && (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 z-50 mt-2 w-[min(18rem,calc(100vw-1.5rem))] origin-top-right rounded-xl border border-line bg-surface py-2 shadow-overlay animate-rise-in"
        >
          <div className="flex items-start gap-3 px-3.5 pb-3 pt-1.5">
            <Avatar user={user} size={40} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-body font-semibold text-ink">{name}</p>
              {user.email && (
                <p className="truncate text-meta text-ink-muted">{user.email}</p>
              )}
              <p className="mt-1 text-meta text-ink-subtle">Your workspace · Free</p>
            </div>
          </div>

          <div className="mx-2 border-t border-line" />

          {isAdmin ? (
            <Link
              href="/admin"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="mx-1.5 mt-1.5 flex w-[calc(100%-0.75rem)] items-center gap-2.5 rounded-lg px-3 py-2 text-left text-ui text-ink transition-colors hover:bg-surface-muted"
            >
              <LayoutDashboard className="h-4 w-4 text-ink-muted" />
              Operations
            </Link>
          ) : null}

          <Link
            href="/about"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="mx-1.5 mt-1.5 flex w-[calc(100%-0.75rem)] items-center gap-2.5 rounded-lg px-3 py-2 text-left text-ui text-ink transition-colors hover:bg-surface-muted"
          >
            About
          </Link>
          <Link
            href="/privacy"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="mx-1.5 flex w-[calc(100%-0.75rem)] items-center gap-2.5 rounded-lg px-3 py-2 text-left text-ui text-ink transition-colors hover:bg-surface-muted"
          >
            Privacy
          </Link>
          <Link
            href="/terms"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="mx-1.5 flex w-[calc(100%-0.75rem)] items-center gap-2.5 rounded-lg px-3 py-2 text-left text-ui text-ink transition-colors hover:bg-surface-muted"
          >
            Terms
          </Link>

          <button
            type="button"
            role="menuitem"
            disabled={busy}
            onClick={() => void handleSignOut()}
            className="mx-1.5 mt-1.5 flex w-[calc(100%-0.75rem)] items-center gap-2.5 rounded-lg px-3 py-2 text-left text-ui text-ink transition-colors hover:bg-surface-muted disabled:opacity-60"
          >
            <LogOut className="h-4 w-4 text-ink-muted" />
            {busy ? "Signing out…" : "Sign out"}
          </button>
        </div>
      )}
    </div>
  );
}
