import { describe, expect, it } from "vitest";

import {
  WORKSPACE_TOUR_STEPS,
  inflateTourRect,
  placeTourCard,
  sameTourRect,
} from "./tourSteps";

const viewport = { width: 1280, height: 800 };
const card = { width: 320, height: 200 };

describe("workspace tour steps", () => {
  it("runs documents, then scope, then evidence", () => {
    expect(WORKSPACE_TOUR_STEPS.map((step) => step.id)).toEqual([
      "documents",
      "scope",
      "evidence",
    ]);
  });

  it("points every step at an anchor that exists in the workspace", () => {
    const targets = WORKSPACE_TOUR_STEPS.map((step) => step.target);
    expect(targets).toEqual(["documents", "scope", "chat"]);
    expect(new Set(targets).size).toBe(targets.length);
  });

  it("only asks for the sidebar on the documents step", () => {
    const needsSidebar = WORKSPACE_TOUR_STEPS.filter((step) => step.needsSidebar);
    expect(needsSidebar.map((step) => step.id)).toEqual(["documents"]);
  });
});

describe("placeTourCard", () => {
  it("sits beside the anchor and stays vertically centred on it", () => {
    const anchor = { top: 200, left: 0, width: 300, height: 600 };
    const position = placeTourCard({ anchor, viewport, card, placement: "right" });

    expect(position.placement).toBe("right");
    expect(position.left).toBe(316);
    expect(position.top).toBe(400);
  });

  it("flips to the other side when the preferred side has no room", () => {
    const anchor = { top: 300, left: 1000, width: 260, height: 120 };
    const position = placeTourCard({ anchor, viewport, card, placement: "right" });

    expect(position.placement).toBe("left");
    expect(position.left + card.width).toBe(anchor.left - 16);
  });

  it("keeps the card inside the viewport when the anchor hugs an edge", () => {
    const anchor = { top: 760, left: 1240, width: 40, height: 40 };
    const position = placeTourCard({ anchor, viewport, card, placement: "top" });

    expect(position.top).toBeGreaterThanOrEqual(16);
    expect(position.left).toBeLessThanOrEqual(viewport.width - card.width - 16);
  });

  it("centres the card when there is no anchor or the step asks for it", () => {
    const centred = placeTourCard({ anchor: null, viewport, card, placement: "right" });

    expect(centred).toEqual({ top: 300, left: 480, placement: "center" });
    expect(
      placeTourCard({
        anchor: { top: 0, left: 0, width: 100, height: 100 },
        viewport,
        card,
        placement: "center",
      }).placement
    ).toBe("center");
  });

  it("falls back to centre on a viewport too small for any side", () => {
    const position = placeTourCard({
      anchor: { top: 10, left: 10, width: 300, height: 300 },
      viewport: { width: 340, height: 320 },
      card,
      placement: "right",
    });

    expect(position.placement).toBe("center");
  });
});

describe("spotlight rect helpers", () => {
  it("pads the cutout on every side", () => {
    expect(inflateTourRect({ top: 100, left: 50, width: 200, height: 80 })).toEqual({
      top: 92,
      left: 42,
      width: 216,
      height: 96,
    });
    expect(inflateTourRect(null)).toBeNull();
  });

  it("ignores sub-pixel drift so the overlay does not re-render every frame", () => {
    const rect = { top: 10, left: 10, width: 100, height: 40 };

    expect(sameTourRect(rect, { ...rect, top: 10.2 })).toBe(true);
    expect(sameTourRect(rect, { ...rect, top: 12 })).toBe(false);
    expect(sameTourRect(null, rect)).toBe(false);
    expect(sameTourRect(null, null)).toBe(true);
  });
});
