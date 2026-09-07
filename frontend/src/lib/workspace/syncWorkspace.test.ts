import { describe, expect, it, vi } from "vitest";

import { executeWorkspacePlan } from "./syncWorkspace";
import { workspaceSyncPlan } from "./identity";

function mockDeps() {
  return {
    migrateGuest: vi.fn().mockResolvedValue({
      documents_moved: 0,
      conversations_moved: 0,
      already_migrated: true,
    }),
    resetGuestSession: vi.fn(),
    beginSwitch: vi.fn(),
    reload: vi.fn().mockResolvedValue(undefined),
  };
}

describe("workspace sync after identity change", () => {
  it("reloads the library on sign-in even when the guest trial has already been claimed", async () => {
    const deps = mockDeps();
    await executeWorkspacePlan(workspaceSyncPlan("sign_in"), deps);

    expect(deps.migrateGuest).toHaveBeenCalledOnce();
    expect(deps.resetGuestSession).toHaveBeenCalledOnce();
    expect(deps.beginSwitch).toHaveBeenCalledOnce();
    expect(deps.reload).toHaveBeenCalledOnce();
  });

  it("reloads when switching accounts so the second person cannot keep the first library", async () => {
    const deps = mockDeps();
    await executeWorkspacePlan(workspaceSyncPlan("switch_user"), deps);

    expect(deps.reload).toHaveBeenCalledOnce();
    expect(deps.beginSwitch).toHaveBeenCalledOnce();
  });

  it("restores a signed-in user's history on a cold page load", async () => {
    const deps = mockDeps();
    await executeWorkspacePlan(workspaceSyncPlan("boot_user"), deps);

    expect(deps.reload).toHaveBeenCalledOnce();
    expect(deps.migrateGuest).toHaveBeenCalledOnce();
  });

  it("clears the screen on sign-out and retires the claimed guest id", async () => {
    const deps = mockDeps();
    await executeWorkspacePlan(workspaceSyncPlan("sign_out"), deps);

    expect(deps.migrateGuest).not.toHaveBeenCalled();
    expect(deps.resetGuestSession).toHaveBeenCalledOnce();
    expect(deps.reload).toHaveBeenCalledOnce();
  });

  it("does nothing on token refresh", async () => {
    const deps = mockDeps();
    await executeWorkspacePlan(workspaceSyncPlan("token_refresh"), deps);

    expect(deps.migrateGuest).not.toHaveBeenCalled();
    expect(deps.resetGuestSession).not.toHaveBeenCalled();
    expect(deps.reload).not.toHaveBeenCalled();
  });

  it("still signs the user in if claiming the guest trial fails", async () => {
    const deps = mockDeps();
    deps.migrateGuest.mockRejectedValue(new Error("offline"));

    await executeWorkspacePlan(workspaceSyncPlan("sign_in"), deps);

    expect(deps.reload).toHaveBeenCalledOnce();
  });
});
