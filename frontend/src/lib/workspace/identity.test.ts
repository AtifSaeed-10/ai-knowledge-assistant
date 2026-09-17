import { describe, expect, it } from "vitest";

import {
  actorKeyFromUserId,
  classifyIdentityChange,
  workspaceSyncPlan,
} from "./identity";

describe("account identity changes", () => {
  it("treats the first guest load as a no-op so a refresh does not mint a new trial", () => {
    expect(classifyIdentityChange(undefined, null)).toBe("boot_guest");
    expect(workspaceSyncPlan("boot_guest")).toEqual({
      migrateGuest: false,
      retireGuestSession: false,
      reloadWorkspace: false,
    });
  });

  it("reloads the signed-in library on first page load with a restored session", () => {
    expect(classifyIdentityChange(undefined, "user:a")).toBe("boot_user");
    expect(workspaceSyncPlan("boot_user")).toEqual({
      migrateGuest: true,
      retireGuestSession: true,
      reloadWorkspace: true,
    });
  });

  it("reloads when a guest signs in, even if there is nothing left to claim", () => {
    expect(classifyIdentityChange(null, "user:a")).toBe("sign_in");
    expect(workspaceSyncPlan("sign_in").reloadWorkspace).toBe(true);
    expect(workspaceSyncPlan("sign_in").migrateGuest).toBe(true);
  });

  it("reloads when switching from one Google account to another", () => {
    expect(classifyIdentityChange("user:a", "user:b")).toBe("switch_user");
    expect(workspaceSyncPlan("switch_user")).toEqual({
      migrateGuest: true,
      retireGuestSession: true,
      reloadWorkspace: true,
    });
  });

  it("starts a fresh guest workspace on sign-out so the next person sees nothing", () => {
    expect(classifyIdentityChange("user:a", null)).toBe("sign_out");
    expect(workspaceSyncPlan("sign_out")).toEqual({
      migrateGuest: false,
      retireGuestSession: true,
      reloadWorkspace: true,
    });
  });

  it("does not touch the library on token refresh", () => {
    expect(classifyIdentityChange("user:a", "user:a")).toBe("token_refresh");
    expect(workspaceSyncPlan("token_refresh")).toEqual({
      migrateGuest: false,
      retireGuestSession: false,
      reloadWorkspace: false,
    });
  });

  it("keys signed-in actors by user id, not email", () => {
    expect(actorKeyFromUserId("abc")).toBe("user:abc");
    expect(actorKeyFromUserId("")).toBeNull();
    expect(actorKeyFromUserId(undefined)).toBeNull();
  });
});
