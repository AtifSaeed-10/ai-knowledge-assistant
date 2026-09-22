/**
 * Decide what the workspace must do when the signed-in actor changes.
 *
 * The browser can hold one guest trial and one access token. Switching
 * people is not a token refresh: the visible library and chat history
 * have to be replaced, not patched.
 */

export type ActorKey = string | null;

export type IdentityEvent =
  | "boot_guest"
  | "boot_user"
  | "sign_in"
  | "sign_out"
  | "switch_user"
  | "token_refresh";

export type WorkspaceSyncPlan = {
  migrateGuest: boolean;
  retireGuestSession: boolean;
  reloadWorkspace: boolean;
};

export function actorKeyFromUserId(userId: string | null | undefined): ActorKey {
  const id = userId?.trim();
  return id ? `user:${id}` : null;
}

export function classifyIdentityChange(
  previousActor: ActorKey | undefined,
  nextActor: ActorKey
): IdentityEvent {
  if (previousActor === undefined) {
    return nextActor ? "boot_user" : "boot_guest";
  }
  if (previousActor === nextActor) {
    return "token_refresh";
  }
  if (previousActor && nextActor) {
    return "switch_user";
  }
  if (nextActor) {
    return "sign_in";
  }
  return "sign_out";
}

export function workspaceSyncPlan(event: IdentityEvent): WorkspaceSyncPlan {
  switch (event) {
    case "boot_guest":
      return {
        migrateGuest: false,
        retireGuestSession: false,
        reloadWorkspace: false,
      };
    case "boot_user":
    case "sign_in":
    case "switch_user":
      return {
        migrateGuest: true,
        retireGuestSession: true,
        reloadWorkspace: true,
      };
    case "sign_out":
      return {
        migrateGuest: false,
        retireGuestSession: true,
        reloadWorkspace: true,
      };
    case "token_refresh":
      return {
        migrateGuest: false,
        retireGuestSession: false,
        reloadWorkspace: false,
      };
  }
}
