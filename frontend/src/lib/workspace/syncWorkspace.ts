import type { Session } from "@supabase/supabase-js";

import { authApi } from "@/lib/api/auth";
import { resetGuestSession } from "@/lib/guestSession";
import { accountHasSeenWorkspaceTour, syncWorkspaceTourWithAccount } from "@/lib/site/firstRun";
import { useAuthStore } from "@/store/useAuthStore";
import { useChatStore } from "@/store/useChatStore";
import { useDocumentStore } from "@/store/useDocumentStore";
import {
  actorKeyFromUserId,
  classifyIdentityChange,
  workspaceSyncPlan,
  type ActorKey,
  type WorkspaceSyncPlan,
} from "./identity";

function firstString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return null;
}

export function userFromSession(session: Session) {
  const meta = (session.user.user_metadata || {}) as Record<string, unknown>;
  return {
    id: session.user.id,
    email: session.user.email ?? null,
    name: firstString(meta.full_name, meta.name, meta.given_name),
    avatarUrl: firstString(meta.avatar_url, meta.picture),
    seenWorkspaceTour: accountHasSeenWorkspaceTour(meta),
  };
}

export type WorkspaceSyncDeps = {
  migrateGuest: () => Promise<unknown>;
  resetGuestSession: () => void;
  beginSwitch: () => void;
  reload: () => Promise<void>;
};

/**
 * Run the side effects for an identity change. Extracted so the "always
 * reload after sign-in" rule can be unit-tested without React.
 */
export async function executeWorkspacePlan(
  plan: WorkspaceSyncPlan,
  deps: WorkspaceSyncDeps
): Promise<void> {
  if (plan.migrateGuest) {
    try {
      await deps.migrateGuest();
    } catch {
      // A failed claim must not block a valid sign-in.
    }
  }
  if (plan.retireGuestSession) {
    deps.resetGuestSession();
  }
  if (plan.reloadWorkspace) {
    deps.beginSwitch();
    await deps.reload();
  }
}

let appliedActor: ActorKey | undefined;

export function resetAppliedActorForTests(): void {
  appliedActor = undefined;
}

function liveDeps(): WorkspaceSyncDeps {
  return {
    migrateGuest: () => authApi.migrateGuest(),
    resetGuestSession,
    beginSwitch: () => {
      useDocumentStore.getState().beginIdentitySwitch();
      useChatStore.getState().beginIdentitySwitch();
    },
    reload: async () => {
      await Promise.all([
        useDocumentStore.getState().reload(),
        useChatStore.getState().reloadConversations(),
        useAuthStore.getState().refreshUsage(),
      ]);
    },
  };
}

/**
 * Keep the API token and the visible workspace on the same person.
 *
 * Sign-in, sign-out, and account switch always reload that person's
 * documents and chat history. Token refresh does not.
 */
export async function applyAuthSession(session: Session | null): Promise<void> {
  const nextActor = actorKeyFromUserId(session?.user.id);
  const event = classifyIdentityChange(appliedActor, nextActor);
  const plan = workspaceSyncPlan(event);
  appliedActor = nextActor;

  if (session) {
    useAuthStore.getState().setSession(userFromSession(session), session.access_token);
    void syncWorkspaceTourWithAccount(
      (session.user.user_metadata || {}) as Record<string, unknown>
    );
  } else {
    useAuthStore.getState().setSession(null, null);
  }

  await executeWorkspacePlan(plan, liveDeps());
}
