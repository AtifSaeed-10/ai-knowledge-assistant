import { describe, expect, it } from "vitest";

import { cn } from "./cn";

describe("cn", () => {
  it("keeps a named type size next to a text colour", () => {
    const result = cn("text-meta font-medium", "bg-warn-soft text-warn");
    expect(result).toContain("text-meta");
    expect(result).toContain("text-warn");
  });

  it("still lets a later colour win over an earlier one", () => {
    expect(cn("text-ink", "text-danger")).toBe("text-danger");
  });

  it("still lets a later size win over an earlier one", () => {
    expect(cn("text-ui", "text-body")).toBe("text-body");
  });

  it("merges ordinary conflicting utilities", () => {
    expect(cn("py-1", "py-2")).toBe("py-2");
  });
});
