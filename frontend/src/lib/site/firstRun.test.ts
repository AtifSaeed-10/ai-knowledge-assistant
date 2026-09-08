import { beforeEach, describe, expect, it, vi } from "vitest";

describe("workspace tour flag", () => {
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
      },
    });
  });

  it("starts unseen and stays seen after the tour finishes", async () => {
    const firstRun = await import("./firstRun");

    expect(firstRun.hasSeenWorkspaceTour()).toBe(false);
    firstRun.markWorkspaceTourSeen();
    expect(firstRun.hasSeenWorkspaceTour()).toBe(true);
  });

  it("still honours a dismissal stored by the old upload tip", async () => {
    memory.set("docusage_seen_upload_guide", "true");
    const firstRun = await import("./firstRun");

    expect(firstRun.hasSeenWorkspaceTour()).toBe(true);
  });

  it("treats unreadable storage as seen so the tour never loops", async () => {
    vi.stubGlobal("window", {
      localStorage: {
        getItem: () => {
          throw new Error("blocked");
        },
        setItem: () => {
          throw new Error("blocked");
        },
      },
    });
    const firstRun = await import("./firstRun");

    expect(firstRun.hasSeenWorkspaceTour()).toBe(true);
    expect(() => firstRun.markWorkspaceTourSeen()).not.toThrow();
  });
});
