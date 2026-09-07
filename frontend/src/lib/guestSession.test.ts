import { beforeEach, describe, expect, it, vi } from "vitest";

const memory = new Map<string, string>();

beforeEach(() => {
  memory.clear();
  vi.resetModules();
  vi.stubGlobal("window", {
    localStorage: {
      getItem: (key: string) => memory.get(key) ?? null,
      setItem: (key: string, value: string) => {
        memory.set(key, value);
      },
      removeItem: (key: string) => {
        memory.delete(key);
      },
    },
  });
});

describe("guest session identity", () => {
  it("reuses the same trial id until it is retired", async () => {
    const guest = await import("./guestSession");
    const first = guest.ensureGuestSession();
    const second = guest.ensureGuestSession();
    expect(second).toBe(first);
  });

  it("mints a new trial id on reset so the next person starts empty", async () => {
    const guest = await import("./guestSession");
    const first = guest.ensureGuestSession();
    const next = guest.resetGuestSession();
    expect(next).not.toBe(first);
    expect(guest.ensureGuestSession()).toBe(next);
  });

  it("sends the guest header while signed out and the bearer token while signed in", async () => {
    const guest = await import("./guestSession");
    const sessionId = guest.ensureGuestSession();
    expect(guest.sessionHeaders()).toEqual({
      [guest.GUEST_SESSION_HEADER]: sessionId,
    });

    guest.setAccessToken("jwt-token");
    expect(guest.sessionHeaders()).toEqual({
      Authorization: "Bearer jwt-token",
    });
  });
});
