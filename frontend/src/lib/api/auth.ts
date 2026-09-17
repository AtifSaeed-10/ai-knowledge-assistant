import { apiJson } from "./client";
import { ensureGuestSession, GUEST_SESSION_HEADER } from "@/lib/guestSession";

export interface MigrateGuestResult {
  documents_moved: number;
  conversations_moved: number;
  already_migrated: boolean;
}

export const authApi = {
  /**
   * POST /auth/migrate-guest
   *
   * Claims the trial's document and chat history for the signed-in user.
   * The guest id travels in a header alongside the new Bearer token, since
   * apiFetch sends the token once a session exists.
   */
  async migrateGuest(): Promise<MigrateGuestResult> {
    return apiJson<MigrateGuestResult>("/auth/migrate-guest", {
      method: "POST",
      headers: { [GUEST_SESSION_HEADER]: ensureGuestSession() },
      errorMessage: "Could not move your trial work to your account",
    });
  },
};
