/**
 * One-time workspace tour: what to point at, and where the card sits.
 *
 * Frontend only. The tour explains existing UI; it never changes retrieval,
 * document scope, or any request the app makes.
 */

export type TourPlacement = "right" | "left" | "top" | "bottom" | "center";

export interface TourRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

export interface TourStep {
  id: string;
  /** Matches a `data-tour` attribute in the workspace. */
  target: string;
  title: string;
  body: string;
  placement: TourPlacement;
  /** Step 3 shows the animated evidence mock instead of pointing at a citation. */
  demo?: boolean;
  /** The document list is inside the sidebar, which is hidden on phones. */
  needsSidebar?: boolean;
}

export const WORKSPACE_TOUR_STEPS: TourStep[] = [
  {
    id: "documents",
    target: "documents",
    title: "Your documents live here",
    body: "Add PDFs with New document — more than one is fine. The guest trial covers a single file, and signing in with Google raises that to five.",
    placement: "right",
    needsSidebar: true,
  },
  {
    id: "scope",
    target: "scope",
    title: "One file, or all of them",
    body: "All documents searches every ready PDF. Switch to One document when you want answers to stay inside the file you picked. The Web switch is a backup: PDFs first, and only if they don’t cover the question.",
    placement: "top",
  },
  {
    id: "evidence",
    target: "chat",
    title: "Every answer shows its evidence",
    body: "Answers cite the page they came from. Click a source and the PDF opens right there, with the quoted passage highlighted when the layout allows it.",
    placement: "center",
    demo: true,
  },
];

const FALLBACKS: Record<Exclude<TourPlacement, "center">, TourPlacement[]> = {
  right: ["right", "left", "bottom", "top"],
  left: ["left", "right", "bottom", "top"],
  top: ["top", "bottom", "right", "left"],
  bottom: ["bottom", "top", "right", "left"],
};

function clamp(value: number, min: number, max: number): number {
  if (max < min) return min;
  return Math.min(max, Math.max(min, value));
}

function fits(
  placement: TourPlacement,
  anchor: TourRect,
  viewport: { width: number; height: number },
  card: { width: number; height: number },
  gap: number,
  margin: number
): boolean {
  if (placement === "right") {
    return anchor.left + anchor.width + gap + card.width <= viewport.width - margin;
  }
  if (placement === "left") {
    return anchor.left - gap - card.width >= margin;
  }
  if (placement === "bottom") {
    return anchor.top + anchor.height + gap + card.height <= viewport.height - margin;
  }
  if (placement === "top") {
    return anchor.top - gap - card.height >= margin;
  }
  return true;
}

/**
 * Where the card goes for a given anchor. Falls back to the opposite side, then
 * to centre, so a narrow window never pushes the card off screen.
 */
export function placeTourCard(options: {
  anchor: TourRect | null;
  viewport: { width: number; height: number };
  card: { width: number; height: number };
  placement: TourPlacement;
  gap?: number;
  margin?: number;
}): { top: number; left: number; placement: TourPlacement } {
  const { anchor, viewport, card } = options;
  const gap = options.gap ?? 16;
  const margin = options.margin ?? 16;

  const centered = {
    top: Math.max(margin, (viewport.height - card.height) / 2),
    left: Math.max(margin, (viewport.width - card.width) / 2),
    placement: "center" as TourPlacement,
  };

  if (!anchor || options.placement === "center") return centered;

  const order = FALLBACKS[options.placement as Exclude<TourPlacement, "center">];
  const resolved = order.find((candidate) =>
    fits(candidate, anchor, viewport, card, gap, margin)
  );
  if (!resolved) return centered;

  const maxLeft = viewport.width - card.width - margin;
  const maxTop = viewport.height - card.height - margin;

  if (resolved === "right" || resolved === "left") {
    const left =
      resolved === "right"
        ? anchor.left + anchor.width + gap
        : anchor.left - gap - card.width;
    const top = anchor.top + anchor.height / 2 - card.height / 2;
    return {
      left: clamp(left, margin, maxLeft),
      top: clamp(top, margin, maxTop),
      placement: resolved,
    };
  }

  const top =
    resolved === "bottom"
      ? anchor.top + anchor.height + gap
      : anchor.top - gap - card.height;
  const left = anchor.left + anchor.width / 2 - card.width / 2;
  return {
    left: clamp(left, margin, maxLeft),
    top: clamp(top, margin, maxTop),
    placement: resolved,
  };
}

/** Grow the cutout a little so the target does not touch the dimmed edge. */
export function inflateTourRect(
  rect: TourRect | null,
  padding = 8
): TourRect | null {
  if (!rect) return null;
  return {
    top: rect.top - padding,
    left: rect.left - padding,
    width: rect.width + padding * 2,
    height: rect.height + padding * 2,
  };
}

export function sameTourRect(a: TourRect | null, b: TourRect | null): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  return (
    Math.abs(a.top - b.top) < 0.5 &&
    Math.abs(a.left - b.left) < 0.5 &&
    Math.abs(a.width - b.width) < 0.5 &&
    Math.abs(a.height - b.height) < 0.5
  );
}
