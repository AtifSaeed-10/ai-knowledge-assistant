import { describe, expect, it } from "vitest";
import {
  STALL_TIMEOUT_MS,
  activityKey,
  shouldMarkProcessingStalled,
} from "./processingStall";

describe("processing stall", () => {
  it("does not fail a scan that is still extracting after two minutes", () => {
    expect(
      shouldMarkProcessingStalled({
        lastChangeAt: 0,
        now: 120_000,
        serverStatus: "extracting",
      })
    ).toBe(false);
  });

  it("fails only after a long silent extract", () => {
    expect(
      shouldMarkProcessingStalled({
        lastChangeAt: 0,
        now: STALL_TIMEOUT_MS + 1,
        serverStatus: "extracting",
      })
    ).toBe(true);
  });

  it("treats heartbeat and page count as activity", () => {
    expect(
      activityKey({ status: "extracting", totalPages: 0, indexUpdatedAt: "" })
    ).not.toEqual(
      activityKey({ status: "extracting", totalPages: 72, indexUpdatedAt: "t2" })
    );
  });
});
